#!/usr/bin/python

# Copyright (c) 2016 Cacti Council Inc.

import argparse
import shutil
import os
import sys
import subprocess
import hashlib
import tempfile

import ctypes
from ctypes import util
from subprocess import Popen, PIPE, STDOUT, check_output
import test_configuration as config
from os import path

def info(message):
    if not config.isQuiet:
        sys.stdout.write(message)

def parseArguments(config_object):

    # handle command line args
    parser = argparse.ArgumentParser(description='A program to run a set of tests for a programming assignment.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_help = True
    parser.add_argument('path', nargs='?', default="Projects", help='path of the projects to consider (by subdirectory / folder)')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s 0.1')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='execute in quiet mode')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='display debug information')
    args = parser.parse_args()
    config_object.submissionPath = args.path

    if args.quiet:
        config_object.isQuiet = True
    if args.debug:
        config_object.isDebugging = True

    # debug program
    if config_object.isDebugging:
        print "SYSTEM"
        print sys.version
        print
    return

def determineEnvironment(config_object):
    config_object.PREPARE_BUILD = ["cmake"]#, "-G", "Unix Makefiles"]
    config_object.BUILD_PROJECT = ["make", "all"]
#CMAKE = "cmake"
#MAKE = "devenv"
#MAKE_PARAMS = "TestProgram.sln /Build Release"
#MAKE = "make"
#MAKE_PARAMS = "all"


def build_project(sourceRoot, buildRoot, prepare_cmd, build_cmd):
    resultError = None

    # If it exists, remove old project folder
    if path.isdir(buildRoot):
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

def run_project_tests(environment, target):
    results = []
    currentDir = os.getcwd()
    os.chdir(target)

    # Run each project's tests.
    for project in config.projects:
        displayName, identifier, projectType, points = project
        info("\nRunning project " + displayName + "...\n")

        # Based on the project type, gather necessary data and execute as appropriate.
        if projectType == config.ProjectTypes.library:
            score, penaltyTotals = runLibraryTests(identifier, environment, target)
        elif projectType == config.ProjectTypes.standalone:
            score, penaltyTotals = runStandaloneTests(os.path.join(target, identifier))
        else:
            score, penaltyTotals = (0, None)

        # If the project didn't compile, just print out a single line indicating that.
        if not score:
            info("Grade:\t0 (Does not compile)\n")
            score = 0

        else:
            # Print out info (for debugging purposes) on the score and penalty values for the project.
            info("\nTest Cases:  " + str(score * points) + "\n")
            overallPenalty = 0

            for penaltyNum in range(0, len(config.testCasePenalties)):
                penaltyName, magnitude = config.testCasePenalties[penaltyNum]
                overallPenalty += penaltyTotals[penaltyNum]
                info(penaltyName + ":\t" + str(penaltyTotals[penaltyNum]) + "\n")

            for penaltyNum in range(0, len(config.projectPenalties)):
                penaltyName, magnitude = config.projectPenalties[penaltyNum]
                penaltyIndex = penaltyNum + len(config.testCasePenalties)
                overallPenalty += penaltyTotals[penaltyIndex]
                info(penaltyName + ":\t" + str(penaltyTotals[penaltyIndex]) + "\n")

            # Apply the penalties and scale to the number of points
            score = (score + max(-config.maxPenalty, overallPenalty)) * points

        # Add to the results list.
        results.append((displayName, score))

    # Change back to the starting directory and return the results.
    os.chdir(currentDir)
    return results

def runLibraryTests(name, core, target):
    # Grab the libraries needed to process these tests.
    coreFile = util.find_library(path.join(core, name)) or util.find_library(path.join(core, "lib" + name))
    if not coreFile:
        coreFile = path.join(core, "lib" + name + ".so")

    coreLib = ctypes.CDLL(coreFile)
    targetLib = loadTempLibrary(target, name)

    config.initializeLibrary(name, coreLib)
    config.initializeLibrary(name, targetLib)

    penaltyTotals = [0] * (len(config.testCasePenalties) + len(config.projectPenalties))
    numOfTests = config.getNumberOfTests(name)
    score = 0

    if numOfTests == 0:
        return None, None

    info("Number of tests: " + str(numOfTests) + ".\n")
    for testNum in range(0, numOfTests):
        info("Test case " + str(testNum) + "... ")
        caseScore = config.runCaseTest(name, testNum, coreLib, targetLib)
        score += caseScore
        info("Score: " + str(caseScore))

        for penaltyNum in range(0, len(config.testCasePenalties)):
            penaltyName, magnitude = config.testCasePenalties[penaltyNum]
            penalty = config.runCasePenalty(name, testNum, penaltyName, coreLib, targetLib)
            penaltyTotals[penaltyNum] += penalty * magnitude * caseScore
            info(";\t" + penaltyName + ": " + str(penalty))
        info(".\n")

        if caseScore < 1:
            info(config.getTestDescription(name, testNum))

    for penaltyNum in range(0, len(config.projectPenalties)):
        penaltyName, magnitude = config.projectPenalties[penaltyNum]
        penalty = config.runProjectPenalty(name, penaltyName, coreLib, targetLib) * magnitude / numOfTests
        penaltyTotals[penaltyNum + len(config.testCasePenalties)] = penalty

    return score / numOfTests, penaltyTotals

def runStandaloneTests(command):
    penaltyTotals = [0] * (len(config.testCasePenalties) + len(config.projectPenalties))
    numOfTests = 0
    score = 0

    try:
        numOfTests = int(subprocess.check_output([ command, "-n" ]))
    except subprocess.CalledProcessError as error:
        print("Error getting number of tests: " + error.output)
    except Exception as error:
        print("Error calling command " + command + " -n")
        raise error

    if numOfTests == 0:
        return None, None

    info("Number of tests: " + str(numOfTests) + ".\n")
    for testNum in range(0, numOfTests):
        info("Test " + str(testNum) + "... ")
        try:
            output = subprocess.check_output([ command, "-c" + str(testNum) ])
            caseScore = float(subprocess.check_output([ command, "-c" + str(testNum) ]))
        except Exception as error:
            info(type(error).__name__ + ": " + str(error))
            caseScore = 0
            
        score += caseScore
        info("Score: " + str(caseScore))

        for penaltyNum in range(0, len(config.testCasePenalties)):
            penaltyName, magnitude = config.testCasePenalties[penaltyNum]
            try:
                penalty = float(subprocess.check_output([ command, "--" + penaltyName + " " + str(testNum) ])) - 1
            except Exception as error:
                info(type(error).__name__ + ": " + str(error))
                penalty = 1

            penaltyTotals[penaltyNum] += penalty * magnitude * caseScore
            info(";\t" + penaltyName + ": " + str(penalty))
        info(".\n")

        if caseScore < 1:
            try:
                info(subprocess.check_output([ command, "-d" + str(testNum) ]))
            except Exception as error:
                info("ERROR GETTING DESCRIPTION - " + type(error).__name__ + ": " + str(error))

    for penaltyNum in range(0, len(config.projectPenalties)):
        penaltyName, magnitude = config.projectPenalties[penaltyNum]
        try:
            penalty = ((float(subprocess.check_output([ command, "--" + penaltyName ])) - 1) * score) * magnitude / numOfTests
        except Exception as error:
            info(type(error).__name__ + ": " + str(error))
            penalty = score * magnitude / numOfTests

        penaltyTotals[penaltyNum + len(config.testCasePenalties)] = penalty

    return score / numOfTests, penaltyTotals

def main():
    import glob
    import distutils.dir_util

    parseArguments(config)
    determineEnvironment(config)

    # Build the environment components (only need to do this once.)
    info("Building test environment... ")
    build_project(config.testerSource, config.testerBuild, config.PREPARE_BUILD, config.BUILD_PROJECT)
    info("done.\n")

    # For each student submission, copy the base files, then the submission, into the "Student" folder.
    for submission in glob.glob(path.join(config.submissionPath, "*")):
        if not path.isdir(submission):
            continue

        # Create a new target folder with base files in it
        if path.isdir(config.studentSource):
            shutil.rmtree(config.studentSource)
        os.makedirs(config.studentSource)
        distutils.dir_util.copy_tree(config.baseSource, config.studentSource)

        # Special kludge for common mistake (placing files in a "Project" directory)
        if path.isdir(path.join(submission, "Project")):
            distutils.dir_util.copy_tree(path.join(submission, "Project"), config.studentSource)
        else:
            distutils.dir_util.copy_tree(submission, config.studentSource)

        # Build the project.
        info("Building project for " + submission + "... ")
        resultError = build_project(config.targetSource, config.targetBuild, config.PREPARE_BUILD, config.BUILD_PROJECT)
        info("done.\n")

        if resultError != None:
            print "Project failed to build."
#            print "Process error with " + str(error.cmd) + ": Returned " + str(error.returncode) + ", Output: " + error.output
            projectResults = []
        else:
            projectResults = run_project_tests(config.testerBuild, config.targetBuild)

        # Track the scores.
        grandTotal = 0.0

        print "\nScores for " + submission + ":"
        for name, result in projectResults:
            print name + ": " + str(result)
            grandTotal += result
        print "Overall score: " + str(grandTotal) + "\n"

if __name__ == "__main__":
    main()
