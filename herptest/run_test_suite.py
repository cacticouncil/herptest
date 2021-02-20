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
import dill
import pathos.pools as pools

from . import toolbox
from concurrent import futures

VERSION = '0.9.9.6'


# handle command line args
def parse_arguments():
    parser = argparse.ArgumentParser(description='A program to run a set of tests for a programming assignment.')
    parser.add_help = True
    parser.add_argument('suite_path', nargs='?', default="./", help='path of test suite to load')
    parser.add_argument('target_path', nargs='?', default="Projects", help='path of target projects (by subdirectory)')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s ' + VERSION)
    parser.add_argument('-t', '--threads', dest='threads', action='store_true', help='use threads instead of processes')
    parser.add_argument('-q', '--quiet', dest='INFO', action='store_false', help='execute in quiet mode (console)')
    parser.add_argument('-w', '--warn', dest='WARN', action='store_true', help='display warning information (console)')
    parser.add_argument('-d', '--debug', dest='DEBUG', action='store_true', help='capture debug information (logfile)')
    parser.add_argument('-s', '--set', dest='set', default="*", help = 'test only projects designated (e.g., *_LATE*')
    config = parser.parse_args(sys.argv[1:])
    config.logformat = "%(message)s"
    return config


def build_project(source_root, build_root, build_cfg):
    result_error = None
    current_dir = os.getcwd()

    # If there is a not a specified build directory, fall back to the source directory instead.
    if not build_root:
        build_root = source_root

    # If the build exists, remove old project folder, recreate it, and switch to it.
    if os.path.isdir(build_root) and not build_root == source_root:
        shutil.rmtree(build_root)
    if not os.path.exists(build_root):
        os.makedirs(build_root)
    os.chdir(build_root)

    try:
        # Prepare to make substitutions to the prep / build commands if applicable.
        replacements = {key : value for key, value in build_cfg.__dict__.items() if not key in ['prep_cmd', 'compile_cmd', 'post_cmd']}
        replacements["source_dir"] = source_root
        replacements["build_dir"] = build_root
        template = string.Template("")

        if hasattr(build_cfg, 'prep_cmd') and build_cfg.prep_cmd:
            # Apply substitutions from the build configuration to the prep command(s)
            source_cmds = build_cfg.prep_cmd if isinstance(build_cfg.prep_cmd, tuple) else (build_cfg.prep_cmd,)
            for source_cmd in source_cmds:
                prep_cmd = []
                for entry in source_cmd:
                    template.template = entry
                    prep_cmd.append(template.substitute(**replacements))
                subprocess.check_output(prep_cmd, stderr=subprocess.STDOUT)

        if hasattr(build_cfg, 'compile_cmd') and build_cfg.compile_cmd:
            # Apply substitutions from the build configuration to the compile command
            source_cmds = build_cfg.compile_cmd if isinstance(build_cfg.compile_cmd, tuple) else (build_cfg.compile_cmd,)
            for source_cmd in source_cmds:
                compile_cmd = []
                for entry in build_cfg.compile_cmd:
                    template.template = entry
                    compile_cmd.append(template.substitute(**replacements))
                subprocess.check_output(compile_cmd, stderr=subprocess.STDOUT)

        if hasattr(build_cfg, 'post_cmd') and build_cfg.post_cmd:
            # Apply substitutions from the build configuration to the prep command(s)
            source_cmds = build_cfg.post_cmd if isinstance(build_cfg.post_cmd, tuple) else (build_cfg.post_cmd,)
            for source_cmd in source_cmds:
                post_cmd = []
                for entry in source_cmd:
                    template.template = entry
                    post_cmd.append(template.substitute(**replacements))
                subprocess.check_output(post_cmd, stderr=subprocess.STDOUT)

    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        result_error = error

    os.chdir(current_dir)
    return result_error


def run_suite_tests(subject, framework, cfg):
    results = []
    exception_sets = {}

    # Run each project's tests.
    for test_set in cfg.sets:
        data_set, score, penalty_totals, exception_list = run_test_set(test_set, subject, framework, cfg)
        exception_sets[test_set.name] = exception_list

        # If the project didn't compile, just add a single line indicating that.
        if isinstance(data_set, str):
            exception_sets[test_set.name].append(data_set)
            data_set = [[], ["Grade: 0 (Does not compile / run)"]]
            score = 0

        else:
            # Add info on the score and penalty values for the project.
            data_set += [ [], ["Test Cases: %.2f (%.2f%%)" % (score * test_set.max_score, score * 100) ] ]
            overall_penalty = 0

            for penalty_num, case_penalty in enumerate(test_set.case_penalties):
                penalty_name, magnitude, _ = case_penalty
                overall_penalty += penalty_totals[penalty_num]
                data_set += [ [ "%s Penalty (overall): %.2f%%" % (penalty_name, penalty_totals[penalty_num] * 100) ] ]

            for penalty_num, set_penalty in enumerate(test_set.set_penalties):
                penalty_name, magnitude, _ = test_set.set_penalties[penalty_num]
                penalty_ind = penalty_num + len(test_set.case_penalties)
                overall_penalty += penalty_totals[penalty_ind]
                data_set += [ [ "%s Penalty (overall): %.2f%%" % (penalty_name, penalty_totals[penalty_ind] * 100) ] ]

            # Apply the penalties and scale to the number of points
            score = (score - min(test_set.max_penalty, overall_penalty)) * test_set.max_score

        # Add to the results list.
        data_set = [ ["Test-Set %s" % test_set.name] ] + data_set
        results.append((test_set.name, score, data_set))

    return results, exception_sets


def run_test_set(test_set, subject, framework, cfg):
    # Prepare data structures and initialize the test set.
    exception_list = []
    set_context = cfg.initialize_test_set(test_set, subject, framework)
    num_of_tests = test_set.get_num_tests(set_context, subject, framework, cfg)
    penalty_totals = [0] * (len(test_set.case_penalties) + len(test_set.set_penalties))

    if not isinstance(num_of_tests, int) or num_of_tests == 0:
        cfg.shutdown_test_set(set_context)
        return "get_number_of_tests() returned [%s]" % num_of_tests, None, None, exception_list

    # Add the initial notes at the top (might adjust this later for 'pure' CSV output)
    data_set = [ [ "Number of tests: %d." % num_of_tests ], [] ]

    # Prepare the header.
    header = [ 'Test No.', 'Score', 'Message', 'Desc.' ]
    header.extend(["%s-Pen" % penalty[0] for penalty in test_set.case_penalties])
    data_set.append(header)

    score = 0
    for test_num in range(0, num_of_tests):
        # Set up the row for this test and run it.
        row = [ '%d' % test_num ]
        try:
            case_result = test_set.run_case_test(test_num, set_context, subject, framework, cfg)
        except Exception as e:
            stack_trace = traceback.format_exc()
            exception_list.append("Test %d, %s: %s\n%s" % (test_num, type(e).__name__, e, stack_trace))
            case_result = 0


        # If we successfuly completed the run, this should be a number; otherwise, a message.
        if isinstance(case_result, numbers.Number):
            case_score = case_result
            message = None
        else:
            case_score = 0
            message = str(case_result)

        score += case_score
        # Add score, run message, and description as applicable
        row.append('%.2f%%' % (case_score * 100))
        row.append(message if message else '')
        row.append(test_set.get_test_desc(test_num, set_context, subject, framework, cfg) if round(case_score, 10) < 1 else '')

        if case_score == 0:
            data_set.append(row)
            continue

        # Go through each penalty and run it (if valid).
        for penalty_num, case_penalty in enumerate(test_set.case_penalties):
            penalty_name, magnitude, pen_function = case_penalty
            penalty = pen_function(penalty_num, test_num, set_context, subject, framework, cfg)
            penalty_totals[penalty_num] += penalty * magnitude * case_score / num_of_tests
            row.append('%.2f%%' % (penalty * 100))

        # Add this test data to the data set.
        data_set.append(row)

    for penalty_num, set_penalty in enumerate(test_set.set_penalties):
        penalty_name, magnitude, pen_function = set_penalty
        penalty = pen_function(penalty_num, set_context, subject, framework, cfg) * score * magnitude
        penalty_totals[penalty_num + len(test_set.case_penalties)] = penalty

    # Return the data set, score (proportion), and penalty totals
    cfg.shutdown_test_set(set_context)
    return data_set, score / num_of_tests, penalty_totals, exception_list


# Build the environment components (only need to do this once.)
def prepare_and_init_framework(cfg):
    if cfg.build.framework_src and cfg.build.framework_bin:
        if cfg.build.prep_cmd or cfg.build.compile_cmd:
            logging.info("Prepping / building framework environment... ")
            result_error = build_project(cfg.build.framework_src, cfg.build.framework_bin, cfg.build)
            if result_error:
                logging.info("%s: %s\n" % (type(result_error).__name__, result_error))
                return

        logging.info("initializing framework... ")
        framework_data = cfg.initialize_framework()
        logging.info("done.\n")
    else:
        framework_data = None
    return framework_data

# For each submission, copy the base files, then the submission, into the destination folder.
def prepare_and_test_submission(submission, framework_context, cfg):
    # Because this might be in a new process, we wil need to reset the console logger when prep the project.
    console_logger = toolbox.SelectiveStreamHandler(INFO=cfg.runtime.INFO, WARNING=cfg.runtime.WARN, CRITICAL=True)
    logging.basicConfig(format=cfg.runtime.logformat, level=logging.DEBUG, handlers=[console_logger])
    root_logger = logging.getLogger('')
    console_logger.terminator = ""

    if not os.path.isdir(submission):
        return None

    # Create a new subject folder with base files in it - then copy oer the submission to be tested.
    if os.path.isdir(cfg.build.destination):
        shutil.rmtree(cfg.build.destination)

    os.makedirs(cfg.build.destination)
    if cfg.build.base:
        shutil.copytree(cfg.build.base, cfg.build.destination, dirs_exist_ok=True)
    shutil.copytree(submission, cfg.build.destination, dirs_exist_ok=True)

    # Build the project.
    setup_exceptions = []
    logging.info("Prepping / building project(s) for " + submission + "... ")
    error = build_project(cfg.build.subject_src, cfg.build.subject_bin, cfg.build)
    if error:
        logging.info("error building (see logs)... ")
        setup_exceptions.append("While prepping/building %s - %s: %s" % (submission, type(error).__name__, error))

    logging.info("Initializing... ")
    subject_context = None
    starting_dir = os.getcwd()

    try:
        subject_context = cfg.initialize_subject(submission, framework_context)
    except Exception as error:
        logging.info("error initializing (see logs)... ")
        setup_exceptions.append("Error initializing subject %s - %s: %s" % (submission, type(error).__name__, error))

    os.chdir(starting_dir)
    logging.info("done.\n")

    starting_dir = os.getcwd()
    results, exception_sets = run_suite_tests(subject_context, framework_context, cfg)
    cfg.shutdown_subject(subject_context)
    os.chdir(starting_dir)
    if len(setup_exceptions) < 0:
        exception_sets["Setup"] = setup_exceptions

    return results, exception_sets


def main():
    dill.settings['recurse']=True
    runtime = parse_arguments()

    # Save the current folder and move to the test suite location.
    starting_dir = os.getcwd()
    os.chdir(runtime.suite_path)

    # Load the config file for this project.
    if not os.path.isfile("config.py") or not (config := toolbox.load_module("config.py")):
        sys.stderr.write("Error: no configuration file. Exiting...\n")
        return

    cfg = config.get_suite_config(runtime)
    cfg.make_paths_absolute()

    # Prepare result paths.
    if not os.path.isdir(cfg.general.result_path):
        os.mkdir(cfg.general.result_path)
    summary_path = os.path.join(cfg.general.result_path, cfg.general.summary_file)

    # Set up logging.
    console_logger = toolbox.SelectiveStreamHandler(INFO=cfg.runtime.INFO, WARNING=cfg.runtime.WARN, CRITICAL=True)
    logging.basicConfig(format=cfg.runtime.logformat, level=logging.DEBUG, handlers=[console_logger])
    root_logger = logging.getLogger('')
    console_logger.terminator = ""

    logfile = os.path.join(cfg.general.result_path, cfg.general.error_log)
    file_logger = toolbox.SelectiveFileHandler(logfile, mode="w", DEBUG=cfg.runtime.DEBUG, ERROR=True)
    root_logger.addHandler(file_logger)

    # Write header for summary file.
    try:
        toolbox.save_csv(summary_path, [[ "Student", "LMS ID", "Score" ]])
    except Exception as e:
        logging.info("Warning: couldn't open summary file for writing: [%s]" % summary_path)

    # Initialize the framework / get any important info
#    with futures.ProcessPoolExecutor() as executor:
#        try:
#            future = executor.submit(prepare_and_init_framework, cfg)
#            framework_context = future.result()
            # This is a fatal error; if we can't initalize the framework, we should stop here.
#        except Exception as e:
#            sys.stderr.write("Error initializing framework - %s: %s. Exiting.\n" % (type(e).__name__, e))
#            exit()
    framework_context = prepare_and_init_framework(cfg)

    # Close general log file and move on to student-specific logs.
    root_logger.removeHandler(file_logger)
    file_logger.close()

    # Prepare and run each submission.
    for submission in glob.glob(os.path.join(cfg.runtime.target_path, cfg.runtime.set)):
        submission_info = os.path.basename(submission).split("_", 1)
        student_name, lms_id = submission_info + ["NONE"] * (2 - len(submission_info))
        output_dir = os.path.join(cfg.general.result_path, os.path.basename(submission))

        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)

        logfile = os.path.join(output_dir, cfg.general.error_log)
        file_logger = toolbox.SelectiveFileHandler(logfile, mode="w", DEBUG=cfg.runtime.DEBUG, ERROR=True)
        root_logger.addHandler(file_logger)

        exec_class = pools.ThreadPool if cfg.runtime.threads else pools.ProcessPool
#        exec_class = futures.ThreadPoolExecutor if cfg.runtime.threads else futures.ProcessPoolExecutor
        with exec_class() as executor:
            try:
#                future = executor.submit(prepare_and_test_submission, submission, framework_context, cfg)
#                suite_results, exception_sets = future.result()
                future = executor.apipe(prepare_and_test_submission, submission, framework_context, cfg)
                suite_results, exception_sets = future.get()
                # If there were exceptions in the tests, we should log them.
                for project, exception_list in exception_sets.items():
                   if len(exception_list) > 0:
                       log_header = "Exceptions for %s\n%s\n" % (project, "-"*(15 + len(project)))
                       logging.error(log_header + "\n".join(exception_list))
            except Exception as e:
                stack_trace = traceback.format_exc()
                logging.error("Error preparing / running %s - %s: %s\n%s" % (submission, type(e).__name__, e, stack_trace))
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

    cfg.shutdown_framework(framework_context)
    print("Framework shutdown")
    # Return to where we started at.
    os.chdir(starting_dir)


if __name__ == "__main__":
    main()
