__author__ = "Tyler Maiello, Boris Ermakov-Spektor"

import os
import requests
import csv
import json
from dotenv import load_dotenv
import sys
import argparse
from herptest import canvas
from herptest.env_wrapper import EnvWrapper

# Version Number for Release
VERSION_NUM = '0.9.9.5'

# handle command line args
def parse_arguments():
    parser = argparse.ArgumentParser(description='A program to upload a CSV for a rubric based assignment to Canvas')
    parser.add_help = True
    parser.add_argument('-V', '-v', '--version', action='version', version='%(prog)s ' + str(VERSION_NUM))
    parser.add_argument('-S', '-s', '--setupenv', action='store_true', help='Run the setup wizard for Canvas API Key Environment Variables')
    config = parser.parse_args(sys.argv[1:])
    config.logformat = "%(message)s"
    return config

def env_setup():
    e = EnvWrapper()
    print("-=- Welcome to the Canvas API Key setup tool, you will be prompted to enter your Canvas key and your Canvas Beta key -=-")
    print("-=- If you only wish to use one of these keys, you can leave the other blank / submit any text. To reinstall, run this command again -=-")
    e.populate_env()

def main():
    # consts that can be swapped out if changing use case.
    PRODUCTION_URL = "https://ufl.instructure.com/api/v1"# Canvas Production is live Canvas where changes will be applied to students.
    BETA_URL = "https://ufl.beta.instructure.com/api/v1" # Canvas Beta is for testing changes that won't apply to courses yet.
    DOT_ENV_PATH = "canvas.env"
    PRODUCTION_TOKEN_TYPE = "TOKEN"
    BETA_TOKEN_TYPE = "BETA_TOKEN"

    # Parse arguments
    arg_config = parse_arguments()
    if arg_config.setupenv == True:
        env_setup()

    # Choosing between live and beta canvas, then creating appropriate canvas util driver object

    # CanvasWrapper object, driver object for functionality,
    # if you want beta or production, a different .env path, or token, enter here into constructor.
    user_type = input("Are you using Canvas as a Teacher or a TA? {Choices: teacher, ta} ")
    if user_type != "teacher" and user_type != "ta":
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)
    canvas_type = input("Would you like to upload to Live Canvas or Canvas Beta? {Choices: Live, Beta} ")
    if canvas_type == "Live" or canvas_type == "live":
        canvas_wrapper = CanvasWrapper(PRODUCTION_URL,DOT_ENV_PATH,PRODUCTION_TOKEN_TYPE, user_type)
        print("Starting CSV Uploader With Parameters -> API_URL:",PRODUCTION_URL,"-> DOT_ENV: ",DOT_ENV_PATH,"-> TOKEN_TYPE:",PRODUCTION_TOKEN_TYPE)
    elif canvas_type == "Beta" or canvas_type == "beta":
        canvas_wrapper = CanvasWrapper(BETA_URL,DOT_ENV_PATH,BETA_TOKEN_TYPE, user_type)
        print("Starting CSV Uploader With Parameters -> API_URL:",BETA_URL,"-> DOT_ENV:",DOT_ENV_PATH,"-> TOKEN_TYPE:",BETA_TOKEN_TYPE)
    else:
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)

    # try to retrieve courses from canvas API, will gracefully fail if API key not present or invalid
    try:
        courses = canvas_wrapper.get_courses_this_semester()
    except:
        print("| CanvasWrapper Object failed to be created. Is your API key valid?")
        print("| Hint: try using --setupenv to set up your environment variables.")
        print("└─> exiting with error")
        exit(-1)
    # gets list of all courses
    course_names = list(courses.keys())
    print(course_names)
    print(f"-=- Listing all courses for which you have role: {canvas_wrapper.userType} in current enrollment period -=-")
    temp_count = 0
    # iterate over list of courses and print of the choices
    for name in courses:
        print(f"{temp_count}. {name} - {courses[name]}")
        temp_count = temp_count + 1
    
    # choosing a course from the list
    print("-=- Which course are you choosing? {Enter Number, 0 indexed} -=-")
    index_choice = input()
    try:
        course_id = courses[course_names[int(index_choice)]]
    except ValueError:
        print("| ValueError: Your choice could not be converted from str -> int")
        print("└─> exiting with error")
        exit(-1)

    # find course id information and fetch sections
    print("| loading course information, this may take a few seconds...")    
    section_ids = canvas_wrapper.get_section_ids(course_id)
    print(f"└─> {len(section_ids)} section(s) found")

    # enter a portion of all of the assignment name for a class assignment
    print("-=- Type some part of the title of your assignment - if it's \"Python Pitches\", type \"Pitches\" -=-")
    try:
        assignment_name = input()
        assignment_id = canvas_wrapper.get_assignment_id_by_name(course_id, assignment_name)
    except:
        print("| Error: No matching assignment found")
        print("└─> exiting with error")
        exit(-1)
    print(f"└─> Found assignment ID: {assignment_id}")

    # fetch all student ids via sections in a course
    user_ids = {}
    for section in section_ids:
        canvas_wrapper.get_student_ids_by_section(course_id, section, user_ids)

    # input CSV path that you with to upload
    print("-=- Please input path of CSV file: {If on WSL, remember to use mounted drives and linux formatted paths} -=-")
    csv_path = input()
    try:
        students_from_file = canvas_wrapper.populate_students_from_csv(csv_path)
    except FileNotFoundError:
        print("| FileNotFoundError: The file path you specified could not be located")
        print("└─> exiting with error")
        exit(-1)

    # try to create rubric and load rubric formatting
    try:
        rubric_id = canvas_wrapper.get_rubric_id(course_id, assignment_id)
        rubric_format = canvas_wrapper.generate_rubric(course_id, rubric_id)
    except:
        print("| Rubric operation failed")
        print("└─> exiting with error")
        exit(-1)
    
    # try to upload grades via API
    try:
        canvas_wrapper.upload_grades(course_id, user_ids, assignment_id, students_from_file, rubric_format)
    except:
        print("| Rubric Upload operation failed")
        print("└─> exiting with error")
        exit(-1)
    
    print("-=- Rubric Upload Complete. Shutting down -=-")

if __name__ == "__main__":
    main()
