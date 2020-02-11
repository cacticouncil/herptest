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


def build_project(source_root, build_root, prepare_cmd, compile_cmd):
    result_error = None

    # If it exists, remove old project folder
    if os.path.isdir(build_root):
        shutil.rmtree(build_root)
    os.makedirs(build_root)

    # Build the project
    current_dir = os.getcwd()
    os.chdir(build_root)

    try:
        subprocess.check_output(prepare_cmd + [source_root], stderr=subprocess.STDOUT)
        subprocess.check_output(compile_cmd, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        result_error = error

    os.chdir(current_dir)
    return result_error


def run_suite_tests(framework, subject, proj_settings):
    results = []

    # Run each project's tests.
    for project in proj_settings.projects:
        display_name, identifier, points = project
        stdpipe.println("Running project " + display_name + "...")
        score, penalty_totals = run_project_tests(identifier, framework, subject, proj_settings)

        # If the project didn't compile, just print out a single line indicating that.
        if score == None:
            stdpipe.println("\nGrade:\t0 (Does not compile)\n")
            score = 0

        else:
            # Print out info (for debugging purposes) on the score and penalty values for the project.
            stdpipe.println("\nTest Cases:  " + str(score * points) + "\n")
            overall_penalty = 0

            for penalty_num in range(0, len(proj_settings.test_case_penalties)):
                penalty_name, magnitude = proj_settings.test_case_penalties[penalty_num]
                overall_penalty += penalty_totals[penalty_num]
                stdpipe.println(penalty_name + ":\t" + str(penalty_totals[penalty_num]))

            for penalty_num in range(0, len(proj_settings.project_penalties)):
                penalty_name, magnitude = proj_settings.project_penalties[penalty_num]
                penalty_index = penalty_num + len(proj_settings.test_case_penalties)
                overall_penalty += penalty_totals[penalty_index]
                stdpipe.println(penalty_name + ":\t" + str(penalty_totals[penalty_index]))

            # Apply the penalties and scale to the number of points
            score = (score - min(proj_settings.max_penalty, overall_penalty)) * points

        # Add to the results list.
        results.append((display_name, score))

    return results


def run_project_tests(name, framework, subject, proj_settings):
    context = proj_settings.initialize_project(name, framework, subject, proj_settings)
    penalty_totals = [0] * (len(proj_settings.test_case_penalties) + len(proj_settings.project_penalties))
    num_of_tests = proj_settings.get_number_of_tests(context)

    if num_of_tests == 0:
        return None, None

    stdpipe.println("Number of tests: " + str(num_of_tests) + ".")

    score = 0
    for test_num in range(0, num_of_tests):
        stdpipe.print("Test case " + str(test_num) + "... ")
        case_score = proj_settings.run_case_test(test_num, context)
        score += case_score
        stdpipe.print("Score: " + str(case_score))

        if case_score < 1:
            stdpipe.print("\t[" + proj_settings.get_test_description(test_num, context) + "]")

        if case_score == 0:
            stdpipe.println(".")
            continue

        for penalty_num in range(0, len(proj_settings.test_case_penalties)):
            penalty_name, magnitude = proj_settings.test_case_penalties[penalty_num]
            penalty = proj_settings.run_case_penalty(penalty_num, test_num, context)
            penalty_totals[penalty_num] += penalty * magnitude * case_score
            stdpipe.print(";\t" + penalty_name + ": " + str(penalty))

        stdpipe.println(".")

    for penalty_num in range(0, len(proj_settings.project_penalties)):
        penalty_name, magnitude = proj_settings.project_penalties[penalty_num]
        penalty = proj_settings.run_project_penalty(penalty_num, context) * score * magnitude
        penalty_totals[penalty_num + len(proj_settings.test_case_penalties)] = penalty

    return score / num_of_tests, penalty_totals


def make_build_paths_absolute(settings):
    settings.base = os.path.abspath(settings.base) if settings.base else None
    settings.destination = os.path.abspath(settings.destination) if settings.destination else None
    settings.resources = os.path.abspath(settings.resources) if settings.resources else None

    settings.subject_src = os.path.abspath(settings.subject_src) if settings.subject_src else None
    settings.subject_bin = os.path.abspath(settings.subject_bin) if settings.subject_bin else None
    settings.framework_src = os.path.abspath(settings.framework_src) if settings.framework_src else None
    settings.framework_bin = os.path.abspath(settings.framework_bin) if settings.framework_bin else None


# For each submission, copy the base files, then the submission, into the destination folder.
def prepare_and_test_submission(framework_context, submission):
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
    subject_context = cfg.project.initialize_subject(cfg.build.subject_bin)
    info("done.\n")
    return run_suite_tests(framework_context, subject_context, cfg.project)


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
        result_error = build_project(cfg.build.framework_src, cfg.build.framework_bin, cfg.build.prep_cmd, cfg.build.compile_cmd)
        if result_error:
            info(type(resultError).__name__ + ": " + str(result_error) + "\n")
            return
        info("initializing framework... ")
        framework_context = cfg.project.initialize_framework(cfg.build.framework_bin)
        info("done.\n")
    else:
        framework_context = None

    # Prepare and run each submission.
    for submission in glob.glob(os.path.join(cfg.runtime.target_path, "*")):
        with futures.ThreadPoolExecutor() as executor:
            future = executor.submit(prepare_and_test_submission, framework_context, submission)
            try:
                suite_results = future.result()
            except Exception as e:
                errpipe.print("Error preparing / running " + submission + " - " + type(e).__name__ + ": " + str(e))
                sys.stderr.write(errpipe.read().decode('utf-8'))
                continue

        # Track the scores.
        grand_total = 0.0

        stdpipe.println("Scores for " + submission + ":")
        if suite_results:
            for name, result in suite_results:
                stdpipe.println(name + ": " + str(result))
                grand_total += result

        stdpipe.println("Overall score: " + str(grand_total))
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
