import math
import os
import shutil
from canvasapi import Canvas
from canvasapi.rubric import RubricAssessment
from csv import reader
from dotenv import load_dotenv
import requests, urllib.request
import sys
import argparse
# from pengtest.env_wrapper import EnvWrapper
from herptest.env_wrapper import EnvWrapper

# For testing purposes- turn off when not testing
testStudent = True

class CanvasWrapper:
    def __init__(self, API_URL, env_path, user_type, token_type="TOKEN"): #Initializes CanvasWrapper object which stores an authenticated CanvasAPI Canvas object
        self.canv_url = API_URL
        load_dotenv(env_path)
        self.canv_token = os.getenv(token_type)
        self.canv = Canvas(API_URL, self.canv_token)
        self.userType = user_type

    # Leave as tbd for later okay Luna	
    # def get_courses(self): #Get all courses with enrollment type of whatever is passed in	
    #     return self.canv.get_courses(enrollment_type=self.userType)	
    def get_courses(self): #Get all courses with enrollment type of teacher	
        # return self.canv.get_courses(enrollment_type='teacher')	
        return self.canv.get_courses(enrollment_type=self.userType)
    
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
        # default directory- recreate if already exists
        subdir = os.getcwd() + "/submissions"
        if(os.path.exists(subdir)):
            shutil.rmtree(subdir)
        else:
            os.mkdir(subdir)
        # UserID : lastnamefirstname
        names = {1267749: 'studenttest'}
        for courses in self.get_courses():
            if courses.name == _course:
                for user in courses.get_users():
                    splitName = user.name.split()
                    names[user.id] = splitName[1].lower() + splitName[0].lower()
        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                allSubmissions = assn.get_submissions()
                if(assn.use_rubric_for_grading):
                    print("Downloading Grading rubric")
                    test = assn.rubric
                else:
                    print("Does not use a rubric for grading")

                for subm in allSubmissions:
                    for attch in subm.attachments:
                        submissionFile = requests.get(attch.url)
                        if (subm.late):
                            if not os.path.exists("submissions"):
                                os.mkdir("submissions")
                            open("submissions/" + str(names[subm.user_id]) + "_LATE_" + str(subm.user_id) + "_" + str(subm.assignment_id) + "_" + attch.filename, "wb").write(submissionFile.content)
                        else:
                            if not os.path.exists("submissions"):
                                os.mkdir("submissions")
                            open("submissions/" + str(names[subm.user_id]) + "_" + str(subm.user_id) + "_" + str(subm.assignment_id) + "_" + attch.filename, "wb").write(submissionFile.content)
                        shutil.make_archive("submissions", 'zip', subdir)
                return assn.submissions_download_url
            
    def download_submissions(self, _course, assignment, path): #Automatically download submissions.zip from a course assignment (course name, assignment name) to the given path
        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                # Retrofit this code to actually authenticate
                #r = requests.get(assn.submissions_download_url, auth=grade_csv_uploader.BearerAuth(self.canv_token))
                #open(path, 'wb').write(r.content)

                allSubmissions = assn.get_submissions()
                for subm in allSubmissions:
                    for attch in subm.attachments:
                        print(attch.url)
                
                #this code works on matty's machine apparently,  but nowhere else
                #urllib.request.urlretrieve(assn.submissions_download_url, path)


    def push_grades(self, _course, assignment, path, late_policy): #Push grades to Canvas assignment (course name, assignment name) using the summary.csv from the given path
        try:
            results = self.get_results(path)
        except:
            print("| InputError: Your path does not lead to summary.csv.")
            print("└─> exiting with error")
            exit(-1)

        for assn in self.get_assignments(list(course.id for course in self.get_courses() if course.name == _course)[0]):
            if(assignment == assn.name):
                # Setting up rubric functionality
                counter = 0
                # print("\nFormat of rubric details:", *assn.rubric_settings, "\nID:", assn.rubric_settings["id"], "\n\n")
                # print(*assn.rubric)

                if assn.use_rubric_for_grading:
                    criterion = {}
                    rating_dict = {}
                    for section in assn.rubric:
                        for rating in section["ratings"]:
                            rating_dict[section['id']] = {float(rating["points"]): rating["id"]}

                        criterion[section['id']] = {
                            'rating_id': rating_dict[section['id']][float(0)],
                            'points': 0,
                            'comments': "Testing Rubric comments"
                        }

                for sub in assn.get_submissions():
                    for res in results:
                        if(str(sub.user_id) == res[1]):
                            # If the submission is late, then there 10% off for each day late
                            # [temporary proof of concept for automatic late penalties]
                            if(sub.late):
                                # Converts Canvas late info (in seconds) into day value then compares with late policy input list
                                days_late = math.ceil(sub.seconds_late/86400.0)
                                if days_late < len(late_policy):
                                    res[2] = float(res[2]) - late_policy[days_late - 1]
                                elif len(late_policy) != 0:
                                    res[2] = float(res[2]) - late_policy[-1]
                                else:
                                    print("-=- No late policy specified. No points deducted for late submissions. -=-")

                            print("Score of " + res[0] + ", ID: " + res[1] + " changed from " + str(sub.score) + " to " + str(float(res[2])) + ".")
                            sub.edit(
                                comment = {
                                    #Have commented when testing or a lot of comments will appear :(
                                    'text_comment' : "HELP ME"
                                },
                                submission = {
                                    'posted_grade' : str(res[2]) + "%"
                                }
                            )
                            course = None
                            for test_course in self.get_courses():
                                if test_course.name == _course:
                                    course = test_course
                            if course == None:
                                print("Error: valid course could not be found (Check around line 130)!!")
                            else:
                                if assn.use_rubric_for_grading:
                                    rubric = RubricAssessment(self.canv_url, {
                                        'id': counter,
                                        'bookmarked' : True,
                                        'artifact_type': "Submission",
                                        'rubric_assessment': {
                                            'user_id': 1267749,
                                            'assessment_type': "grading"
                                        }
                                    })
                                    counter = counter + 1
                                    rubric.rubric_assessment.update(criterion)
                                    print("checking rubric:", assn.rubric_settings)
                                    sub.edit(
                                        rubric_assessment={rubric}
                                    )
                                    print(rubric.rubric_assessment)


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
    
    user_type = input("Are you using Canvas as a Teacher or a TA? {Choices: teacher, ta} ")	
    if user_type != "teacher" and user_type != "ta":
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)
    else:	
        canvas_type = input("Would you like to upload to Live Canvas or Canvas Beta? {Choices: Live, Beta} ")	
        if canvas_type == "Live" or canvas_type == "live":	
            canvas = CanvasWrapper(PRODUCTION_URL,DOT_ENV_PATH,user_type,PRODUCTION_TOKEN_TYPE)	
            print("Starting CSV Uploader With Parameters -> API_URL:",PRODUCTION_URL,"-> DOT_ENV: ",DOT_ENV_PATH,"-> TOKEN_TYPE:",PRODUCTION_TOKEN_TYPE)	
        elif canvas_type == "Beta" or canvas_type == "beta":	
            canvas = CanvasWrapper(BETA_URL,DOT_ENV_PATH,user_type,BETA_TOKEN_TYPE)	
            print("Starting CSV Uploader With Parameters -> API_URL:",BETA_URL,"-> DOT_ENV:",DOT_ENV_PATH,"-> TOKEN_TYPE:",BETA_TOKEN_TYPE)	
        else:	
            print("| InputError: Your input does not match one of the chosen types.")	
            print("└─> exiting with error")	
            exit(-1)

    # CanvasWrapper object, driver object for functionality, if you want beta or production, a different .env path, or token, enter here into constructor.

    try:
        courses = canvas.get_courses()
        print(courses[0])
    except:
        print(f"| Canvas Util Object failed to be created. Either your API key is invalid or you have no courses as a {user_type}.")
        print("| Hint: try using --setupenv to set up your environment variables.")
        print("└─> exiting with error")
        exit(-1)

    print(f"-=- Listing all courses for which you have role: {user_type} -=-")
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
        print("-=- Specify late policy (enter a single-space separated list for total point deductions each day late (starting at 1 day late)) -=-")
        # Turns user input from spaced ints into list (ex. input: "10 20 30 60" becomes [10, 20, 30, 60])
        invalid_policy = True
        while invalid_policy:
            try:
                late_policy = list(map(int, input().split()))
                invalid_policy = False
            except ValueError:
                print("-=- Invalid late policy (check for non-space, non-float values). Please input again.-=-")
                invalid_policy = True
        print("-=- Pushing grades to Canvas -=-")
        canvas.push_grades(course_name, assn_name, submission_path, late_policy)
        print("-=- Grades pushed successfully. Shutting down -=-")

    elif choice == "Pull":
        print("-=- Fetching assignment download link w/ manual download mode enabled... -=-")
        dl_link = canvas.get_download_link(course_name, assn_name)
        print("Downloaded successfully.")
        print("-=- Shutting down -=-")

if __name__ == "__main__":
    main()
