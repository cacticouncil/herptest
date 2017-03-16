#!/usr/bin/python3

# Copyright (c) 2016 Cacti Council Inc.

import argparse
import ctypes
import glob
import hashlib
import os
import shutil
import sys
import tempfile
import subprocess

import ctypes.util as c_util
import distutils.dir_util as dir_util
import importlib.util as import_util

import suite_module

cfg = argparse.Namespace()
cfg.runtime = argparse.Namespace()

cfg.runtime.prep_cmd = ["cmake"]#, "-G", "Unix Makefiles"
cfg.runtime.build_cmd = ["make", "all"]
#cfg.build_cmd = ["devenv", "TestProgram.sln", "/Build Release"]


def info(message):
    if not cfg.runtime.quiet:
        sys.stdout.write(message)


# handle command line args
def parseArguments():
    global config
    parser = argparse.ArgumentParser(description='A program to run a set of tests for a programming assignment.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_help = True
    parser.add_argument('suite_path', nargs='?', default="./", help='path of test suite to load')
    parser.add_argument('target_path', nargs='?', default=None, help='path of the target projects to consider (by subdirectory / folder)')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.1')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='execute in quiet mode')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='display debug information')
    cfg.runtime = parser.parse_args(sys.argv[1:], cfg.runtime)

    if not cfg.runtime.target_path:
        cfg.runtime.target_path = os.path.join(cfg.runtime.test_path, "Projects")

    # debug program
    if cfg.runtime.debug:
        print("SYSTEM ", sys.version)

    return


def loadModule(filename, module_name=None):
    if not module_name:
        module_name = 'unnamed_module.' + os.path.basename(os.path.splitext(filename)[0])

    spec = import_util.spec_from_file_location(module_name, filename)
    module = import_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_project(sourceRoot, buildRoot, prepare_cmd, build_cmd):
    resultError = None

    # If it exists, remove old project folder
    if os.path.isdir(buildRoot):
        shutil.rmtree(buildRoot)
    os.makedirs(buildRoot)

    # Build the project
    currentDir = os.getcwd()
    os.chdir(buildRoot)

    try:        
        with open(os.devnull, 'w') as devnull:
            subprocess.check_output(prepare_cmd + [sourceRoot], stderr=subprocess.STDOUT)
        with open(os.devnull, 'w') as devnull:
            subprocess.check_output(build_cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        resultError = error

    os.chdir(currentDir)
    return resultError


def run_suite_tests(framework, subject, settings):
    results = []
#    currentDir = os.getcwd() <--- These are needed for standalone only
#    os.chdir(subject)

    # Run each project's tests.
    for project in settings.projects:
        displayName, identifier, points = project
        info("\nRunning project " + displayName + "...\n")
        score, penaltyTotals = run_project_tests(identifier, framework, subject, settings)

        # If the project didn't compile, just print out a single line indicating that.
        if not score:
            info("Grade:\t0 (Does not compile)\n")
            score = 0

        else:
            # Print out info (for debugging purposes) on the score and penalty values for the project.
            info("\nTest Cases:  " + str(score * points) + "\n")
            overallPenalty = 0

            for penaltyNum in range(0, len(settings.testCasePenalties)):
                penaltyName, magnitude = settings.testCasePenalties[penaltyNum]
                overallPenalty += penaltyTotals[penaltyNum]
                info(penaltyName + ":\t" + str(penaltyTotals[penaltyNum]) + "\n")

            for penaltyNum in range(0, len(settings.projectPenalties)):
                penaltyName, magnitude = settings.projectPenalties[penaltyNum]
                penaltyIndex = penaltyNum + len(settings.testCasePenalties)
                overallPenalty += penaltyTotals[penaltyIndex]
                info(penaltyName + ":\t" + str(penaltyTotals[penaltyIndex]) + "\n")

            # Apply the penalties and scale to the number of points
            score = (score + max(-settings.maxPenalty, overallPenalty)) * points

        # Add to the results list.
        results.append((displayName, score))

#    os.chdir(currentDir) <--- standalone / blackbox only
    return results


def run_project_tests(name, framework, subject, settings):
    context = settings.initializeProject(name, framework, subject, settings)
    penaltyTotals = [0] * (len(settings.testCasePenalties) + len(settings.projectPenalties))

    try:
        numOfTests = settings.getNumberOfTests(context)
    except Exception as error:
        info("Error getting number of tests; " + type(error).__name__ + ": " + str(error) + "\n")
        numOfTests = 0

    if numOfTests == 0:
        return None, None

    info("Number of tests: " + str(numOfTests) + ".\n")

    score = 0
    for testNum in range(0, numOfTests):
        info("Test case " + str(testNum) + "... ")

        try:
            caseScore = settings.runCaseTest(testNum, context)
        except Exception as error:
            info(type(error).__name__ + ": " + str(error) + ". Score: 0\n")
            caseScore = 0
            continue

        score += caseScore
        info("Score: " + str(caseScore))

        for penaltyNum in range(0, len(settings.testCasePenalties)):
            penaltyName, magnitude = settings.testCasePenalties[penaltyNum]

            try:
                penalty = settings.runCasePenalty(penaltyNum, testNum, context)
            except Exception as error:
                info(type(error).__name__ + ": " + str(error) + "\n")
                penalty = 1

            penaltyTotals[penaltyNum] += penalty * magnitude * caseScore
            info(";\t" + penaltyName + ": " + str(penalty))

        if caseScore < 1:
            try:
                info(";\t" + settings.getTestDescription(testNum, context))
            except Exception as error:
                info("ERROR GETTING DESCRIPTION - " + type(error).__name__ + ": " + str(error) + "\n")
        info(".\n")

    for penaltyNum in range(0, len(settings.projectPenalties)):
        penaltyName, magnitude = settings.projectPenalties[penaltyNum]

        try:
            penalty = settings.runProjectPenalty(penaltyNum, context) * score * magnitude
        except Exception as error:
            info(type(error).__name__ + ": " + str(error))
            penalty = score * magnitude

        penaltyTotals[penaltyNum + len(settings.testCasePenalties)] = penalty

    return score / numOfTests, penaltyTotals


def makeBuildPathsAbsolute(settings):
    settings.destination = os.path.abspath(settings.destination)
    settings.base = os.path.abspath(settings.base)

    settings.subject_src = os.path.abspath(settings.subject_src)
    settings.subject_bin = os.path.abspath(settings.subject_bin)
    settings.framework_src = os.path.abspath(settings.framework_src)
    settings.framework_bin = os.path.abspath(settings.framework_bin)


def main():
    parseArguments()

    # Save the current folder and move to the test suite location.
    startingDir = os.getcwd()
    os.chdir(cfg.runtime.suite_path)

    # Load the settings for this project.
    settings = loadModule("settings.py")
    cfg.project = settings.project
    cfg.build = settings.build

    cfg.project.importToolbox(suite_module)
    makeBuildPathsAbsolute(cfg.build)

    # Build the environment components (only need to do this once.)
    info("Preparing framework environment... ")
    build_project(cfg.build.framework_src, cfg.build.framework_bin, cfg.runtime.prep_cmd, cfg.runtime.build_cmd)
    frameworkContext = cfg.project.initializeFramework(cfg.build.framework_bin)
    info("done.\n")

    # For each submission, copy the base files, then the submission, into the destination folder.
    for submission in glob.glob(os.path.join(cfg.runtime.target_path, "*")):
        if not os.path.isdir(submission):
            continue

        # Create a new subject folder with base files in it - then copy oer the submission to be tested.
        if os.path.isdir(cfg.build.destination):
            shutil.rmtree(cfg.build.destination)
        os.makedirs(cfg.build.destination)
        dir_util.copy_tree(cfg.build.base, cfg.build.destination)
        dir_util.copy_tree(submission, cfg.build.destination)

        # Build the project.
        info("Preparing project for " + submission + "... ")
        resultError = build_project(cfg.build.subject_src, cfg.build.subject_bin, cfg.runtime.prep_cmd, cfg.runtime.build_cmd)
        subjectContext = cfg.project.initializeSubject(cfg.build.subject_bin)
        info("done.\n")

        if resultError != None:
            print("Project failed to build.")
#            print "Process error with " + str(error.cmd) + ": Returned " + str(error.returncode) + ", Output: " + error.output
            suiteResults = []
        else:
            suiteResults = run_suite_tests(frameworkContext, subjectContext, cfg.project)

        # Track the scores.
        grandTotal = 0.0

        print("\nScores for " + submission + ":")
        for name, result in suiteResults:
            print(name + ": " + str(result))
            grandTotal += result
        print("Overall score: " + str(grandTotal) + "\n")

    # Return to where we started at.
    os.chdir(startingDir)

if __name__ == "__main__":
    main()
