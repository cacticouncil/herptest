#!/usr/bin/python3

# Copyright (c) 2017 Cacti Council Inc.

import argparse
import glob
import os
import shutil
import sys
import subprocess
import time
import os.path

from . import toolbox
from concurrent import futures

cfg = argparse.Namespace()
cfg.runtime = argparse.Namespace()

stdpipe = toolbox.PipeSet()
errpipe = toolbox.PipeSet()


# Fill default values
def fill_defaults():
    global cfg

    if not cfg.build.prep_cmd:
        cfg.build.prep_cmd = [ "cmake" ]
    if not cfg.build.compile_cmd:
        cfg.build.compile_cmd = [ "make", "all" ]


def info(message):
    if not cfg.runtime.quiet:
        sys.stdout.write(message)
        sys.stdout.flush()


# handle command line args
def parse_arguments():
    global cfg
    parser = argparse.ArgumentParser(description='A program to run a set of tests for a programming assignment.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_help = True
    parser.add_argument('suite_path', nargs='?', default="./", help='path of test suite to load')
    parser.add_argument('target_path', nargs='?', default="Projects", help='path of the target projects to consider (by subdirectory / folder)')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.1')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='execute in quiet mode')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='display debug information')
    cfg.runtime = parser.parse_args(sys.argv[1:], cfg.runtime)

    # debug program
    if cfg.runtime.debug:
        print("SYSTEM ", sys.version)

    return


def build_project(sourceRoot, buildRoot, prepare_cmd, compile_cmd):
    resultError = None

    # If it exists, remove old project folder
    if os.path.isdir(buildRoot):
        shutil.rmtree(buildRoot)
    os.makedirs(buildRoot)

    # Build the project
    currentDir = os.getcwd()
    os.chdir(buildRoot)

    try:
        subprocess.check_output(prepare_cmd + [sourceRoot], stderr=subprocess.STDOUT)
        subprocess.check_output(compile_cmd, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        resultError = error

    os.chdir(currentDir)
    return resultError


def run_suite_tests(framework, subject, proj_settings):
    results = []

    # Run each project's tests.
    for project in proj_settings.projects:
        displayName, identifier, points = project
        stdpipe.println("Running project " + displayName + "...")
        score, penaltyTotals = run_project_tests(identifier, framework, subject, proj_settings)

        # If the project didn't compile, just print out a single line indicating that.
        if score == None:
            stdpipe.println("\nGrade:\t0 (Does not compile)\n")
            score = 0

        else:
            # Print out info (for debugging purposes) on the score and penalty values for the project.
            stdpipe.println("\nTest Cases:  " + str(score * points) + "\n")
            overallPenalty = 0

            for penaltyNum in range(0, len(proj_settings.testCasePenalties)):
                penaltyName, magnitude = proj_settings.testCasePenalties[penaltyNum]
                overallPenalty += penaltyTotals[penaltyNum]
                stdpipe.println(penaltyName + ":\t" + str(penaltyTotals[penaltyNum]))

            for penaltyNum in range(0, len(proj_settings.projectPenalties)):
                penaltyName, magnitude = proj_settings.projectPenalties[penaltyNum]
                penaltyIndex = penaltyNum + len(proj_settings.testCasePenalties)
                overallPenalty += penaltyTotals[penaltyIndex]
                stdpipe.println(penaltyName + ":\t" + str(penaltyTotals[penaltyIndex]))

            # Apply the penalties and scale to the number of points
            score = (score - min(proj_settings.maxPenalty, overallPenalty)) * points

        # Add to the results list.
        results.append((displayName, score))

    return results


def run_project_tests(name, framework, subject, proj_settings):
    context = proj_settings.initializeProject(name, framework, subject, proj_settings)
    penaltyTotals = [0] * (len(proj_settings.testCasePenalties) + len(proj_settings.projectPenalties))
    numOfTests = proj_settings.getNumberOfTests(context)

    if numOfTests == 0:
        return None, None

    stdpipe.println("Number of tests: " + str(numOfTests) + ".")

    score = 0
    for testNum in range(0, numOfTests):
        stdpipe.print("Test case " + str(testNum) + "... ")
        caseScore = proj_settings.runCaseTest(testNum, context)
        score += caseScore
        stdpipe.print("Score: " + str(caseScore))

        if caseScore < 1:
            stdpipe.print("\t[" + proj_settings.getTestDescription(testNum, context) + "]")

        if caseScore == 0:
            stdpipe.println(".")
            continue

        for penaltyNum in range(0, len(proj_settings.testCasePenalties)):
            penaltyName, magnitude = proj_settings.testCasePenalties[penaltyNum]
            penalty = proj_settings.runCasePenalty(penaltyNum, testNum, context)
            penaltyTotals[penaltyNum] += penalty * magnitude * caseScore
            stdpipe.print(";\t" + penaltyName + ": " + str(penalty))

        stdpipe.println(".")

    for penaltyNum in range(0, len(proj_settings.projectPenalties)):
        penaltyName, magnitude = proj_settings.projectPenalties[penaltyNum]
        penalty = proj_settings.runProjectPenalty(penaltyNum, context) * score * magnitude
        penaltyTotals[penaltyNum + len(proj_settings.testCasePenalties)] = penalty

    return score / numOfTests, penaltyTotals


def make_build_paths_absolute(settings):
    settings.base = os.path.abspath(settings.base) if settings.base else None
    settings.destination = os.path.abspath(settings.destination) if settings.destination else None
    settings.resources = os.path.abspath(settings.resources) if settings.resources else None

    settings.subject_src = os.path.abspath(settings.subject_src) if settings.subject_src else None
    settings.subject_bin = os.path.abspath(settings.subject_bin) if settings.subject_bin else None
    settings.framework_src = os.path.abspath(settings.framework_src) if settings.framework_src else None
    settings.framework_bin = os.path.abspath(settings.framework_bin) if settings.framework_bin else None


# For each submission, copy the base files, then the submission, into the destination folder.
def prepare_and_test_submission(frameworkContext, submission):
    global cfg
    if not os.path.isdir(submission):
        return None

    # Create a new subject folder with base files in it - then copy oer the submission to be tested.
    if os.path.isdir(cfg.build.destination):
        shutil.rmtree(cfg.build.destination)

    os.makedirs(cfg.build.destination)
    shutil.copytree(cfg.build.base, cfg.build.destination, dirs_exist_ok=True)
    shutil.copytree(submission, cfg.build.destination, dirs_exist_ok=True)

    # Build the project.

    info("Building project(s) for " + submission + "... ")
    resultError = build_project(cfg.build.subject_src, cfg.build.subject_bin, cfg.build.prep_cmd, cfg.build.compile_cmd)
    if resultError:
        info("error building (see logs). ")
        errpipe.print(type(resultError).__name__ + ": " + str(resultError) + "\n")

    info("Initializing... ")
    subjectContext = cfg.project.initializeSubject(cfg.build.subject_bin)
    info("done.\n")
    return run_suite_tests(frameworkContext, subjectContext, cfg.project)


def main():
    global cfg
    parse_arguments()

    # Save the current folder and move to the test suite location.
    starting_dir = os.getcwd()
    os.chdir(cfg.runtime.suite_path)

    # Load the config for this project.
    config = toolbox.load_module("config.py")

    if not config:
        return

    cfg.project = config.project
    cfg.build = config.build
    cfg.result_path = config.result_path
    cfg.result_log = config.result_log
    cfg.err_suffix = config.err_suffix
    fill_defaults()

    # Prepare paths
    make_build_paths_absolute(cfg.build)
    cfg.result_path = os.path.abspath(cfg.result_path) if cfg.result_path else None

    if not os.path.isdir(cfg.result_path):
        os.mkdir(cfg.result_path)

    # Build the environment components (only need to do this once.)
    if cfg.build.framework_src and cfg.build.framework_bin:
        info("Building framework environment... ")
        resultError = build_project(cfg.build.framework_src, cfg.build.framework_bin, cfg.build.prep_cmd, cfg.build.compile_cmd)
        if resultError:
            info(type(resultError).__name__ + ": " + str(resultError) + "\n")
            return
        info("initializing framework... ")
        frameworkContext = cfg.project.initializeFramework(cfg.build.framework_bin)
        info("done.\n")
    else:
        frameworkContext = None

    # Prepare and run each submission.
    for submission in glob.glob(os.path.join(cfg.runtime.target_path, "*")):
        with futures.ThreadPoolExecutor() as executor:
            future = executor.submit(prepare_and_test_submission, frameworkContext, submission)
            try:
                suiteResults = future.result()
            except Exception as e:
                errpipe.print("Error preparing / running " + submission + " - " + type(e).__name__ + ": " + str(e))
                sys.stderr.write(errpipe.read().decode('utf-8'))
                continue

        # Track the scores.
        grandTotal = 0.0

        stdpipe.println("Scores for " + submission + ":")
        if suiteResults:
            for name, result in suiteResults:
                stdpipe.println(name + ": " + str(result))
                grandTotal += result

        stdpipe.println("Overall score: " + str(grandTotal))
        errpipe.println("")

        output_dir = os.path.join(cfg.result_path, os.path.basename(submission))
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)

        toolbox.data_to_file(stdpipe.read(), os.path.join(output_dir, cfg.result_log))
        toolbox.data_to_file(errpipe.read(), os.path.join(output_dir, cfg.result_log + cfg.err_suffix))
        time.sleep(2)

    # Return to where we started at.
    os.chdir(starting_dir)


if __name__ == "__main__":
    main()
