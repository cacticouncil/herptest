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
from herptest.env_wrapper import EnvWrapper

# For testing purposes- turn off when not testing
testStudent = True

class Rubric:
    def __init__(self):
        self.criteria: list[Criterion] = []
        self.id = ""

    class Criterion:
        def __init__(self):
            self.ratings: list[Rating] = []
            self.id = ""

        class Rating:
            def __init__(self):
                self.points = 0
                self.id = ""


class Student:
    def __init__(self):
        self.last_name = ""
        self.first_name = ""
        self.grade = 0
        self.rubric: list[(float, str)] = []

    def __str__(self):
        print(f"Last Name: {self.last_name}")
        print(f"First Name: {self.last_name}")
        print(f"ID: {self.id}")
        print(f"Grade: {self.last_name}")
        print(f"Rubric: {self.rubric}")

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
        return self.canv.get_courses(enrollment_state='active', enrollment_type=self.userType)
    
    def get_assignments(self, course): #Get all assignments in a course using the passed in course ID
        return self.canv.get_course(course).get_assignments()
    #equivalent to get_assignment_list

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

                try:
                    if(assn.use_rubric_for_grading):
                        print("Downloading Grading rubric")
                        test = assn.rubric
                    else:
                        print("Does not use a rubric for grading")
                except:
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
                # Add attribute use_rubric_for_grading and set to False if not present (prevents exceptions)
                try:
                    test = assn.use_rubric_for_grading
                except:
                    assn.use_rubric_for_grading = False
                # Prevents divide by zero error if points_possible not set (defaults to 0)
                if assn.points_possible == 0:
                    assn.points_possible = 100
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
                                    res[2] = float(res[2]) - (late_policy[days_late - 1])
                                elif len(late_policy) != 0:
                                    res[2] = float(res[2]) - (late_policy[-1])
                                else:
                                    print("-=- No late policy specified. No points deducted for late submissions. -=-")

                            print("Score of " + res[0] + ", ID: " + res[1] + " changed from " + str(sub.score / assn.points_possible * 100) + " to " + str(float(res[2])) + ".")
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

    def get_courses_this_semester(self) -> dict:
        """
        Get dictionary (name -> id) of courses in this semester
        """
        content = self.get_courses()
        # Filter for courses
        result = {}
        for course in content:
            try:
                result[course.name] = int(course.id)
            except:
                pass
        return result

    def get_section_ids(self, course_id: str) -> list:
        """
        Get a list of all section IDs in a specific course
        """
        section_ids = []
        for course in self.get_courses():
            if course.id == course_id:
                    for section in course.get_sections():
                        section_ids.append(section.id)
        return section_ids

    def get_assignment_id_by_name(self, course_id: str, assignment_name: str) -> str:
        """
        Get the id of the first assignment with a name that matches the input
        """
        for course in self.canv.get_course(course_id):
            for assignment in course.get_assignments():
                if str(assignment.name).lower().count(assignment_name.lower()):
                    print(f"| Found assignment: {assignment.name}")
                    return str(assignment.id)

        raise Exception("ERROR: No matching assignment found!")

    def get_assignment_list(self, course_id: str) -> dict:
        """
        Get the list of assignments for the specified course id
        """
        course = self.canv.get_course(course_id)
        assignments = []
        for assns in course.get_assignments():
            assignments.append(assns)

        assignment_list = {}
        for assignment in assignments:
            #print(f"| Found assignment: {assignment['name']},{assignment['id']}")
            assignment_list[assignment.name] = assignment.id

        if len(assignment_list) == 0:
            raise Exception("ERROR: No assignments found!")

        return assignment_list

    def get_student_ids_by_section(self, course_id: str, section_id: str, results: dict):
        """
        Get list of students from a particular section (by Canvas supplied Section ID) and store them in the dictionary
        """

        section = self.canv.get_course(course_id).get_section(section_id)
        student_ids = []
        if section.students is not None:
            for student in section.students:
                results[str(student.name).lower()] = student.id

    def get_rubric_id(self, course_id: str, assignment_id: str) -> str:
        assignment = self.canv.get_course(course_id).get_assignment(assignment_id)
        return assignment.rubric_settings.id

    def generate_rubric(self, course_id: str, rubric_id: str) -> Rubric:
        result_rubric = Rubric()
        result_rubric.id = rubric_id

        content = self.canv.get_course(course_id).get_rubric(rubric_id)

        criteria_data = content.data

        for criterion in criteria_data:
            temp_criterion = Rubric.Criterion()
            temp_criterion.id = criterion.id
            rating_data = criterion.ratings

            for rating in rating_data:
                temp_rating = Rubric.Criterion.Rating()
                temp_rating.id = rating.id
                temp_rating.points = float(rating.points)
                temp_criterion.ratings.append(temp_rating)

            result_rubric.criteria.append(temp_criterion)

        return result_rubric

    def populate_students_from_csv(self, csv_path: str) -> list:
        students = []
        with open(csv_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            column_end_index = -1
            for i, row in enumerate(csv_reader):
                if i == 0:
                    for j, val in enumerate(row):
                        if val == "Total Left":
                            column_end_index = j
                            break
                else:
                    student = Student()
                    name = str(row[0]).split(',')
                    student.last_name = name[0].strip()
                    student.first_name = name[1].strip()
                    for i in range(2, column_end_index, 2):
                        try:
                            grade = float(row[i])
                        except:
                            grade = 0
                        student.rubric.append((grade, row[i + 1]))
                    students.append(student)
        return students

    def upload_grades(self, course_id: str, user_ids: dict, assignment_id: str, students_from_file: list,
                      rubric: Rubric):
        counter = 0

        for student in students_from_file:
            student_name = f"{student.first_name} {student.last_name}".lower()

            if student_name in user_ids:

                content = self.canv.get_course(course_id).get_assignment(assignment_id).get_submission(user_ids[student_name])

                # PROMPT WHEN OVERWRITING GRADES
                if content.grade is not None:
                    print(f"{student_name}: grade not null!")
                    # print("Confirm grade replacement with 'Y'.")
                    # if input().lower() != 'y':
                    #     sys.exit(0)
                    print(f"replacing grade of {student_name}")

                payload = {}

                if len(student.rubric) != len(rubric.criteria):
                    raise Exception("Criteria length mismatch!"+str(len(student.rubric))+"!="+str(len(rubric.criteria)))

                for i, criterion in enumerate(rubric.criteria):
                    payload[f"rubric_assessment.{criterion.id}.points"] = student.rubric[i][0]
                    payload[f"rubric_assessment.{criterion.id}.comments"] = str(student.rubric[i][1])
                    rating_id_chosen = ""
                    for j, rating in enumerate(criterion.ratings):
                        if criterion.ratings[j].points <= student.rubric[i][0]:
                            rating_id_chosen = criterion.ratings[j].id
                            break
                    payload[f"rubric_assessment.{criterion.id}.rating_id"] = rating_id_chosen

                self.canv.get_course(course_id).get_assignment(assignment_id).get_submission(user_ids[student_name]).edit(params=payload)


                counter = counter + 1
                print(f"{counter} student(s) graded.")

    def process_and_upload_file(self, course_id: str, assignment_name: str, csv_path: str):
        section_ids = self.get_section_ids(course_id)
        user_ids = {}
        for section in section_ids:
            self.get_student_ids_by_section(course_id, section, user_ids)

        try:
            assignment_id = self.get_assignment_id_by_name(course_id, assignment_name)
            students_from_file = self.populate_students_from_csv(csv_path)
            rubric_id = self.get_rubric_id(course_id, assignment_id)
            rubric_format = self.generate_rubric(course_id, rubric_id)
            self.upload_grades(course_id, user_ids, assignment_id, students_from_file, rubric_format)
        except:
            return -1
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
