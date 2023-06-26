import math
import os
from canvasapi import Canvas
from csv import reader
from dotenv import load_dotenv
import requests, urllib.request
import sys
import argparse
from pengtest.env_wrapper import EnvWrapper



class CanvasWrapper:
    def __init__(self, API_URL, env_path, token_type="TOKEN"): #Initializes CanvasWrapper object which stores an authenticated CanvasAPI Canvas object
        self.canv_url = API_URL
        load_dotenv(env_path)
        self.canv_token = os.getenv(token_type)
        self.canv = Canvas(API_URL, self.canv_token)

    def get_courses(self): #Get all courses with enrollment type of teacher
        return self.canv.get_courses(enrollment_type='teacher')
    
    def get_assignments(self, course): #Get all assignments in a course using the passed in course ID
        return self.canv.get_course(course).get_assignments()

    def get_students(self, course): #Get all students in a course using the passed in course ID
        students = []
        for student in self.canv.get_course(course).get_users(enrollment_type='student'):
            students.append(student.name.split(' ') + [student.id])
        return students

    def get_results(self, path): #Get the results CSV in the format [['studentname', student_ID, grade]]
        results = []
        with open(path, 'r') as _summary:
            csv_reader = reader(_summary)
            header = next(csv_reader)
            if header != None:
                for row in csv_reader:
                    results.append(row)
        return results


    def get_download_link(self, _course, assignment): #Get submissions.zip download link from a given course assignment using the passed in course name and assignment name
        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                return assn.submissions_download_url

    def download_submissions(self, _course, assignment, path): #Automatically download submissions.zip from a course assignment (course name, assignment name) to the given path
        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                print(assn.submissions_download_url)
                # Retrofit this code to actually authenticate
                #r = requests.get(assn.submissions_download_url, auth=grade_csv_uploader.BearerAuth(self.canv_token))
                #open(path, 'wb').write(r.content)
                
                #this code works on matty's machine apparently,  but nowhere else
                urllib.request.urlretrieve(assn.submissions_download_url, path)


    def push_grades(self, _course, assignment, path): #Push grades to Canvas assignment (course name, assignment name) using the summary.csv from the given path
        try:
            results = self.get_results(path)
        except:
            print("| InputError: Your path does not lead to summary.csv.")
            print("└─> exiting with error")
            exit(-1)
        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                for sub in assn.get_submissions():
                    for res in results:
                        if(str(sub.user_id) == res[1]):
                            # If the submission is late, then there 10% off for each day late
                            # [temporary proof of concept for automatic late penalties]
                            if(sub.late):
                                res[2] = float(res[2]) - (10 * math.ceil(sub.seconds_late/86400.0))
                            print("Score of " + res[0] + ", ID: " + res[1] + " changed from " + str(sub.score) + " to " + str(float(res[2])) + ".")
                            sub.edit(
                                submission = {
                                    'posted_grade' : float(res[2])
                                }
                            )
                    

def env_setup():
    e = EnvWrapper()
    print("-=- Welcome to the Canvas API Key setup tool, you will be prompted to enter your Canvas key and your Canvas Beta key -=-")
    print("-=- If you only wish to use one of these keys, you can leave the other blank / submit any text. To reinstall, run this command again -=-")
    e.populate_env()


def parse_arguments():
    parser = argparse.ArgumentParser(description='A program to automatically push grades or pull submissions to a Canvas assignment')
    parser.add_help = True
    parser.add_argument('-S', '-s', '--setupenv', action='store_true', help='Run the setup wizard for Canvas API Key Environment Variables')
    config = parser.parse_args(sys.argv[1:])
    config.logformat = "%(message)s"
    return config

def main():
    # consts that can be swapped out if changing use case.
    PRODUCTION_URL = "https://ufl.instructure.com" # Canvas Production is live Canvas where changes will be applied to students.
    BETA_URL = "https://ufl.beta.instructure.com" # Canvas Beta is for testing changes that won't apply to courses yet.
    DOT_ENV_PATH = "canvas.env" 
    PRODUCTION_TOKEN_TYPE = "TOKEN"
    BETA_TOKEN_TYPE = "BETA_TOKEN"

    arg_config = parse_arguments()
    if arg_config.setupenv == True:
        env_setup()
    
    canvas_type = input("Would you like to upload to Live Canvas or Canvas Beta? {Choices: Live, Beta} ")
    if canvas_type == "Live" or canvas_type == "live":
        canvas = CanvasWrapper(PRODUCTION_URL,DOT_ENV_PATH,PRODUCTION_TOKEN_TYPE)
        print("Starting CSV Uploader With Parameters -> API_URL:",PRODUCTION_URL,"-> DOT_ENV: ",DOT_ENV_PATH,"-> TOKEN_TYPE:",PRODUCTION_TOKEN_TYPE)
    elif canvas_type == "Beta" or canvas_type == "beta":
        canvas = CanvasWrapper(BETA_URL,DOT_ENV_PATH,BETA_TOKEN_TYPE)
        print("Starting CSV Uploader With Parameters -> API_URL:",BETA_URL,"-> DOT_ENV:",DOT_ENV_PATH,"-> TOKEN_TYPE:",BETA_TOKEN_TYPE)
    else:
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)

    # CanvasWrapper object, driver object for functionality, if you want beta or production, a different .env path, or token, enter here into constructor.

    try:
        courses = canvas.get_courses()
    except:
        print("| Canvas Util Object failed to be created. Is your API key valid?")
        print("| Hint: try using --setupenv to set up your environment variables.")
        print("└─> exiting with error")
        exit(-1)

    print("-=- Listing all courses for which you have role: Teacher -=-")
    temp_count = 0
    for course in courses:
        print(f"{temp_count}. {course.name}")
        temp_count = temp_count + 1

    print("-=- Which course are you choosing? {Enter Number, 0 indexed} -=-")
    index_choice = input()
    try:
        course_name = courses[int(index_choice)].name
    except ValueError:
        print("| ValueError: Your choice could not be converted from str -> int")
        print("└─> exiting with error")
        exit(-1)

    print("-=- Listing all assignments for the course: " + course_name + " -=-")
    assignments = canvas.get_assignments(list(course.id for course in courses if course.name == course_name)[0])
    temp_count = 0
    for assn in assignments:
        print(f"{temp_count}. {assn.name}")
        temp_count = temp_count + 1

    print("-=- Which assignment are you choosing? {Enter Number, 0 indexed} -=-")
    index_choice = input()
    try:
        assn_name = assignments[int(index_choice)].name
    except ValueError:
        print("| ValueError: Your choice could not be converted from str -> int")
        print("└─> exiting with error")
        exit(-1)

    print("-=- Would you like to push grades or pull submissions for assignment: " + assn_name + " -=-")
    temp_count = 0
    choices = ["Push", "Pull"]
    for choice in choices:
        print(f"{temp_count}. {choice}")
        temp_count = temp_count + 1

    index_choice = input()
    try:
        choice = choices[int(index_choice)]
    except ValueError:
        print("| ValueError: Your choice could not be converted from str -> int")
        print("└─> exiting with error")
        exit(-1)
    
    if choice == "Push":
        print("-=- Enter the relative path for your summary.csv file in your Test Suite's 'Results' folder {If on WSL, remember to use mounted drives and linux formatted paths} -=-")
        submission_path = input()
        print("-=- Pushing grades to Canvas -=-")
        canvas.push_grades(course_name, assn_name, submission_path)
        print("-=- Grades pushed successfully. Shutting down -=-")

    elif choice == "Pull":
        print("-=- Fetching assignment download link w/ manual download mode enabled... -=-")
        dl_link = canvas.get_download_link(course_name, assn_name)
        print("-=- Open the download link in your browser to download the assignment submissions -=-")
        print(dl_link)
        print("-=- Shutting down -=-")

if __name__ == "__main__":
    main()
