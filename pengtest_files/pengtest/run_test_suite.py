#!/usr/bin/python3

# Copyright (c) 2017 Cacti Council Inc., 2018-2020 University of Florida

import argparse
import glob
import os
import shutil
import sys
import subprocess
import time
import os.path
import traceback
import numbers
import string
import logging

from . import toolbox
from .vm_wrapper import VmWrapper
from concurrent import futures

VERSION = '0.9.9.5'

cfg = argparse.Namespace()
cfg.runtime = argparse.Namespace()


# handle command line args
def parse_arguments():
#    global cfg
#    cfg.runtime = parser.parse_args(sys.argv[1:], cfg.runtime)
#    cfg.logformat = "%(message)s"
#    cfg.logformat = "[%(levelname)s] %(message)s"
    parser = argparse.ArgumentParser(description='A program to run a set of tests for a programming assignment.')
    parser.add_help = True
    parser.add_argument('suite_path', nargs='?', default="./", help='path of test suite to load')
    parser.add_argument('target_path', nargs='?', default="Projects", help='path of target projects (by subdirectory)')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s ' + VERSION)
    parser.add_argument('-q', '--quiet', dest='INFO', action='store_false', help='execute in quiet mode (console)')
    parser.add_argument('-w', '--warn', dest='WARN', action='store_true', help='display warning information (console)')
    parser.add_argument('-d', '--debug', dest='DEBUG', action='store_true', help='capture debug information (logfile)')
    parser.add_argument('-s', '--set', dest='set', default="*", help = 'test only projects designated (e.g., *_LATE*')
    config = parser.parse_args(sys.argv[1:])
    config.logformat = "%(message)s"
    return config
#    cfg.runtime = parser.parse_args(sys.argv[1:], cfg.runtime)
#    cfg.logformat = "[%(levelname)s] %(message)s"


def build_project(source_root, build_root, build_cfg, submission):
    result_error = None
    current_dir = os.getcwd()

    # If there is a not a specified build directory, fall back to the source directory instead.
    if not build_root:
        build_root = source_root

    if build_root:
        # If the build exists, remove old project folder, recreate it, and switch to it.
        if os.path.isdir(build_root) and not build_root == source_root:
            shutil.rmtree(build_root)
        if not os.path.exists(build_root):
            os.makedirs(build_root)
        os.chdir(build_root)

    if build_cfg.vm.is_vm == True:
        staging_log, build_log = build_cfg.vm_inst.make_vm(submission)

    else:
        try:
            # Prepare to make substitutions to the prep / build commands if applicable.
            replacements = {key : value for key, value in build_cfg.__dict__.items() if not key in ['prep_cmd', 'compile_cmd']}
            replacements["source_dir"] = source_root
            replacements["build_dir"] = build_root
            template = string.Template("")

            if build_cfg.prep_cmd:
                # Apply substitutions from the build configuration to the prep command
                prep_cmd = []
                for entry in build_cfg.prep_cmd:
                    template.template = entry
                    prep_cmd.append(template.substitute(**replacements))
                subprocess.check_output(prep_cmd, stderr=subprocess.STDOUT)

            if build_cfg.compile_cmd:
                # Apply substitutions from the build configuration to the compile command
                compile_cmd = []
                for entry in build_cfg.compile_cmd:
                    template.template = entry
                    compile_cmd.append(template.substitute(**replacements))
                subprocess.check_output(compile_cmd, stderr=subprocess.STDOUT)

        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            result_error = error
    os.chdir(current_dir)
    return result_error


def run_suite_tests(framework, subject, proj_settings, submission):
    global cfg
    results = []

    if cfg.build.vm.is_vm == True:
        for project in proj_settings.projects:
            display_name, identifier, points = project
            context = proj_settings.initialize_project(identifier, framework, subject, proj_settings)
            num_of_tests = proj_settings.get_number_of_tests(context)

            if not isinstance(num_of_tests, int) or num_of_tests == 0:
                proj_settings.shutdown_project(context)
                return "get_number_of_tests() returned [%s]" % num_of_tests, None, None

            # Add the initial notes at the top
            data_set = [ [ "Number of tests: %d." % num_of_tests ], [] ]

            # Run the tests that have been staged to the VM for the submission
            run_log = cfg.build.vm_inst.run_tests(submission)

            # Analyze the run.log for what to put in the csv
            log_result, score = proj_settings.analyze_run_log(run_log)

            # Add to the results list.
            data_set = [ ["Project %s" % display_name] ] + data_set + log_result
            results.append((display_name, score, data_set))
    
    else:
        # Run each project's tests.
        for project in proj_settings.projects:
            display_name, identifier, points = project
            data_set, score, penalty_totals = run_project_tests(identifier, framework, subject, proj_settings)

            # If the project didn't compile, just add a single line indicating that.
            if isinstance(data_set, str):
                logging.error("Error: %s" % data_set)
                data_set = [[], ["Grade: 0 (Does not compile / run)"]]
                score = 0

            else:
                # Add info on the score and penalty values for the project.
                data_set += [ [], ["Test Cases: %.2f (%.2f%%)" % (score * points, score * 100) ] ]
                overall_penalty = 0

                for penalty_num in range(0, len(proj_settings.test_case_penalties)):
                    penalty_name, magnitude = proj_settings.test_case_penalties[penalty_num]
                    overall_penalty += penalty_totals[penalty_num]
                    data_set += [ [ "%s Penalty (overall): %.2f%%" % (penalty_name, penalty_totals[penalty_num] * 100) ] ]

                for penalty_num in range(0, len(proj_settings.project_penalties)):
                    penalty_name, magnitude = proj_settings.project_penalties[penalty_num]
                    penalty_ind = penalty_num + len(proj_settings.test_case_penalties)
                    overall_penalty += penalty_totals[penalty_ind]
                    data_set += [ [ "%s Penalty (overall): %.2f%%" % (penalty_name, penalty_totals[penalty_ind] * 100) ] ]

                # Apply the penalties and scale to the number of points
                score = (score - min(proj_settings.max_penalty, overall_penalty)) * points

            # Add to the results list.
            data_set = [ ["Project %s" % display_name] ] + data_set
            results.append((display_name, score, data_set))

    return results


def run_project_tests(name, framework, subject, proj_settings):
    context = proj_settings.initialize_project(name, framework, subject, proj_settings)
    penalty_totals = [0] * (len(proj_settings.test_case_penalties) + len(proj_settings.project_penalties))
    num_of_tests = proj_settings.get_number_of_tests(context)

    if not isinstance(num_of_tests, int) or num_of_tests == 0:
        proj_settings.shutdown_project(context)
        return "get_number_of_tests() returned [%s]" % num_of_tests, None, None

    # Add the initial notes at the top (might adjust this later for 'pure' CSV output)
    data_set = [ [ "Number of tests: %d." % num_of_tests ], [] ]

    # Prepare the header.
    header = [ 'Test No.', 'Score', 'Message', 'Desc.' ]
    header.extend(["%s-Pen" % name for name, pct in proj_settings.test_case_penalties])
    data_set.append(header)

    score = 0
    for test_num in range(0, num_of_tests):
        # Set up the row for this test and run it.
        row = [ '%d' % test_num ]
        case_result = proj_settings.run_case_test(test_num, context)

        # If we successfuly completed the run, this should be a number; otherwise, a message.
        if isinstance(case_result, numbers.Number):
            case_score = case_result
            message = None
        else:
            case_score = 0
            message = case_result

        score += case_score
        # Add score, run message, and description as applicable
        row.append('%.2f%%' % (case_score * 100))
        row.append(message if message else '')
        row.append(proj_settings.get_test_description(test_num, context) if round(case_score, 10) < 1 else '')

        if case_score == 0:
            data_set.append(row)
            continue

        for penalty_num in range(0, len(proj_settings.test_case_penalties)):
            pen_result = proj_settings.test_case_penalties[penalty_num]
            penalty = proj_settings.run_case_penalty(penalty_num, test_num, context)

            # If we successfuly completed the run, this should be a tuple; otherwise, a message.
            if isinstance(pen_result, tuple):
                penalty_name, magnitude = pen_result
                message = None
            else:
                penalty_name = None
                maginitude = 0
                message = pen_result

            penalty_totals[penalty_num] += penalty * magnitude * case_score / num_of_tests
            row.append('%.2f%%' % (penalty * 100))

        # Add this test data to the data set.
        data_set.append(row)

    for penalty_num in range(0, len(proj_settings.project_penalties)):
        penalty_name, magnitude = proj_settings.project_penalties[penalty_num]
        penalty = proj_settings.run_project_penalty(penalty_num, context) * score * magnitude
        penalty_totals[penalty_num + len(proj_settings.test_case_penalties)] = penalty

    # Return the data set, score (proportion), and penalty totals
    proj_settings.shutdown_project(context)
    return data_set, score / num_of_tests, penalty_totals


def process_configuration(config):
    if not config:
        return None

    # Fill default values
    if not hasattr(config.build, 'prep_cmd'):
        config.build.prep_cmd = []
    if not hasattr(config.build, 'compile_cmd'):
        config.build.compile_cmd = []

    # Make configuration paths absolute
    config.general.result_path = os.path.abspath(config.general.result_path) if config.general.result_path else None

    config.build.base = os.path.abspath(config.build.base) if config.build.base else None
    config.build.destination = os.path.abspath(config.build.destination) if config.build.destination else None
    config.build.resources = os.path.abspath(config.build.resources) if config.build.resources else None

    config.build.subject_src = os.path.abspath(config.build.subject_src) if config.build.subject_src else None
    config.build.subject_bin = os.path.abspath(config.build.subject_bin) if config.build.subject_bin else None
    config.build.framework_src = os.path.abspath(config.build.framework_src) if config.build.framework_src else None
    config.build.framework_bin = os.path.abspath(config.build.framework_bin) if config.build.framework_bin else None

    return config

# For each submission, copy the base files, then the submission, into the destination folder.
def prepare_and_test_submission(framework_context, submission):
    global cfg

    if not os.path.isdir(submission):
        return None

    # Create a new subject folder with base files in it - then copy over the submission to be tested.
    if os.path.isdir(cfg.build.destination):
        shutil.rmtree(cfg.build.destination)

    os.makedirs(cfg.build.destination)
    if cfg.build.base:
        shutil.copytree(cfg.build.base, cfg.build.destination, dirs_exist_ok=True)
    shutil.copytree(submission, cfg.build.destination, dirs_exist_ok=True)

    # Build the project.
    logging.info("Prepping / building project(s) for " + submission + "... ")
    error = build_project(cfg.build.subject_src, cfg.build.subject_bin, cfg.build, submission)
    if error:
        logging.info("error building (see logs)... ")
        logging.error("Error prepping/building %s - %s: %s" % (submission, type(error).__name__, error))

    logging.info("Initializing... ")
    subject_context = None
    starting_dir = os.getcwd()

    try:
        subject_context = cfg.project.initialize_subject(cfg)
    except Exception as error:
        logging.error("Error initializing subject %s - %s: %s" % (submission, type(error).__name__, error))
        logging.info("error initializing (see logs)... ")

    os.chdir(starting_dir)
    logging.info("done.\n")

    starting_dir = os.getcwd()
    results = run_suite_tests(framework_context, subject_context, cfg.project, submission)
    cfg.project.shutdown_subject(subject_context)

    if cfg.build.vm.is_vm:
        # Windows does not always path back to the right directory for VM projects, so explicitly change it
        os.chdir(cfg.build.vm.payload_dir)
    else:
        os.chdir(starting_dir)
    
    return results


def main():
    global cfg # TODO: Eventually take this out of global scope for simplicity
    cfg.runtime = parse_arguments()
    console_logger = toolbox.SelectiveStreamHandler(INFO=cfg.runtime.INFO, WARNING=cfg.runtime.WARN, CRITICAL=True)
    logging.basicConfig(format=cfg.runtime.logformat, level=logging.DEBUG, handlers=[console_logger])
    root_logger = logging.getLogger('')
    console_logger.terminator = ""

    # Save the current folder and move to the test suite location.
    starting_dir = os.getcwd()
    os.chdir(cfg.runtime.suite_path)

    # Load the config for this project.
    if not (config := process_configuration(toolbox.load_module("config.py"))):
        logging.info("Error: no configuration file. Exiting...\n")
        return

    cfg.project = config.project
    cfg.build = config.build
    cfg.general = config.general

    # Prepare paths
    if not os.path.isdir(cfg.general.result_path):
        os.mkdir(cfg.general.result_path)

    summary_path = os.path.join(cfg.general.result_path, cfg.general.summary_file)

    try:
        toolbox.save_csv(summary_path, [[ "Student", "LMS ID", "Score" ]])
    except Exception as e:
        logging.info("Warning: couldn't open summary file for writing: [%s]" % summary_path)
    
    # Check if we are building a VM first
    if cfg.build.vm.is_vm == True:
        # Create a new VM wrapper
        vm = VmWrapper(cfg.build.vm)

        # Start up the VM software (i.e. a VMWare host)
        vm.start_vm()
        cfg.build.vm_inst = vm

    # Build the environment components (only need to do this once.)
    if cfg.build.framework_src and cfg.build.framework_bin and cfg.build.vm.is_vm == False:
        if cfg.build.prep_cmd or cfg.build.compile_cmd:
            logging.info("Prepping / building framework environment... ")
            result_error = build_project(cfg.build.framework_src, cfg.build.framework_bin, cfg.build, "framework")
            if result_error:
                logging.info("%s: %s\n" % (type(result_error).__name__, result_error))
                return

        logging.info("initializing framework... ")
        framework_context = cfg.project.initialize_framework(cfg)
        logging.info("done.\n")
    else:
        framework_context = None

    # Prepare and run each submission.
    for submission in glob.glob(os.path.join(cfg.runtime.target_path, cfg.runtime.set)):
        submission_info = os.path.basename(submission).split("_", 1)
        student_name, lms_id = submission_info + ["NONE"] * (2 - len(submission_info))
        output_dir = os.path.join(cfg.general.result_path, os.path.basename(submission))

        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)

        logfile = filename=os.path.join(output_dir, cfg.general.error_log)
        file_logger = toolbox.SelectiveFileHandler(logfile, mode="w", DEBUG=cfg.runtime.DEBUG, ERROR=True)
        root_logger.addHandler(file_logger)

        with futures.ThreadPoolExecutor() as executor:
            future = executor.submit(prepare_and_test_submission, framework_context, submission)
            try:
                suite_results = future.result()
            except Exception as e:
                logging.error("Error preparing / running %s - %s: %s" % (submission, type(e).__name__, e))
                root_logger.removeHandler(file_logger)
                file_logger.close()
                continue

        # Generate and save individual test score information to results file.
        grand_total = 0.0

        file_data = [["Scores for %s (LMS ID: %s)..." % (student_name, lms_id)]]

        if suite_results:
            for name, result, data_set in suite_results:
                file_data.extend(data_set + [ [ "%s: %.3f" % (name, result) ] ])
                grand_total += result

        file_data.append([ "Overall score: %.2f" % grand_total ])
        toolbox.save_csv(os.path.join(output_dir, cfg.general.result_file), file_data)

        # Add data to summary file for this submission.
        try:
            toolbox.append_csv(summary_path, [[student_name, lms_id, grand_total]])
        except:
            # Fail silently; we should have already detected the error when creating the file.
            pass

        root_logger.removeHandler(file_logger)
        file_logger.close()
        time.sleep(2)

    cfg.project.shutdown_framework(framework_context)
    # Return to where we started at.
    os.chdir(starting_dir)


if __name__ == "__main__":
    main()
