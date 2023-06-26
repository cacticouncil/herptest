__author__ = "Tyler Maiello, Boris Ermakov-Spektor"

import os
import requests
import csv
import json
from dotenv import load_dotenv
import sys
import argparse
from env_wrapper import EnvWrapper

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

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r: requests.Request):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r


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
        print(f"Grade: {self.last_name}")
        print(f"Rubric: {self.rubric}")


class CanvasUtil:
    def __init__(self, canvas_url, dotenv_path, token_type, userType):
        self.canvas_api_url = canvas_url
        load_dotenv(dotenv_path)  # load token from .env file
        self.token = os.getenv(token_type)
        self.userType = userType

    def get_courses_this_semester(self) -> dict:
        """
        Get dictionary (name -> id) of courses in this semester
        """

        response = requests.get(f"{self.canvas_api_url}/courses?enrollment_type=" + self.userType + "&include=items&per_page=1000", auth=BearerAuth(self.token))
        content = response.json()
        # try:
        #     enrollment_term_id = content[0]["enrollment_term_id"]
        # except:
        #     #if there are no valid courses, return an empty dict
        #     return {}
        # for course in content:  # Find the current enrollment term
        #     try:
        #         enrollment_term_id = max(enrollment_term_id, int(course["enrollment_term_id"]))
        #     except:
        #         pass

        # Filter for courses
        result = {}
        for course in content:
            try:
                result[course["name"]] = int(course["id"])
                ## ----------TEMPORARY FOR TESTING PURPOSES---------------
                if course["course_code"] == "BLANCHARD":
                    result[course["name"]] = int(course["id"])
            except:
                pass
        return result

    def get_section_ids(self, course_id: str) -> list:
        """
        Get a list of all section IDs in a specific course
        """
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/sections?include=items&per_page=100", auth=BearerAuth(self.token))
        content = response.json()
        section_ids = []
        for section in content:
            section_ids.append(section["id"])
        return section_ids

    def get_assignment_id_by_name(self, course_id: str, assignment_name: str) -> str:
        """
        Get the id of the first assignment with a name that matches the input
        """
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/assignments?include=items&per_page=100", auth=BearerAuth(self.token))
        content = response.json()
        for assignment in content:

            if str(assignment["name"]).lower().count(assignment_name.lower()):
                print(f"| Found assignment: {assignment['name']}")
                return str(assignment["id"])

        raise Exception("ERROR: No matching assignment found!")

    def get_assignment_by_id(self, course_id: str, assignment_id: int) -> str:
        """
        Get the id of the first assignment with a name that matches the input
        """
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/assignments/{assignment_id}?include=items&per_page=100", auth=BearerAuth(self.token))
        content = response.json()
        if content['id'] == assignment_id:
            print(f"| Found assignment: {content['name']}")
            return str(content['id'])

        raise Exception("ERROR: No matching assignment found!")

    def get_assignment_list(self, course_id: str) -> dict:
        """
        Get the list of assignments for the specified course id
        """
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/assignments?include=items&per_page=100", auth=BearerAuth(self.token))
        content = response.json()
        assignment_list = {}
        for assignment in content:
            #print(f"| Found assignment: {assignment['name']},{assignment['id']}")
            assignment_list[assignment['name']] = assignment['id']

        if len(assignment_list) == 0:
            raise Exception("ERROR: No assignments found!")

        return assignment_list

    def get_student_ids_by_section(self, course_id: str, section_id: str, results: dict):
        """
        Get list of students from a particular section (by Canvas supplied Section ID) and store them in the dictionary
        """
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/sections/{section_id}?include[]=students",
                                auth=BearerAuth(self.token))
        content = response.json()
        student_ids = []
        if content["students"] is not None:
            for student in content["students"]:
                results[str(student["name"]).lower()] = student["id"]

    def get_rubric_id(self, course_id: str, assignment_id: str) -> str:
        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/assignments/{assignment_id}",
                                auth=BearerAuth(self.token))
        content = response.json()
        return content["rubric_settings"]["id"]

    def generate_rubric(self, course_id: str, rubric_id: str) -> Rubric:
        result_rubric = Rubric()
        result_rubric.id = rubric_id

        response = requests.get(f"{self.canvas_api_url}/courses/{course_id}/rubrics/{rubric_id}",
                                auth=BearerAuth(self.token))
        content = response.json()

        criteria_data = content["data"]

        for criterion in criteria_data:
            temp_criterion = Rubric.Criterion()
            temp_criterion.id = criterion["id"]
            rating_data = criterion["ratings"]

            for rating in rating_data:
                temp_rating = Rubric.Criterion.Rating()
                temp_rating.id = rating["id"]
                temp_rating.points = float(rating["points"])
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
                        # TODO: change the logic of this to be more robust.
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
                gradeURI = f"{self.canvas_api_url}/courses/{course_id}/assignments/{assignment_id}/submissions/{user_ids[student_name]}"

                response = requests.get(gradeURI, auth=BearerAuth(self.token))
                content = response.json()

                # PROMPT WHEN OVERWRITING GRADES
                if content["grade"] is not None:
                    print(f"{student_name}: grade not null!")
                    # print("Confirm grade replacement with 'Y'.")
                    # if input().lower() != 'y':
                    #     sys.exit(0)
                    print(f"replacing grade of {student_name}")

                payload = {}

                if len(student.rubric) != len(rubric.criteria):
                    raise Exception("Criteria length mismatch!"+str(len(student.rubric))+"!="+str(len(rubric.criteria)))

                for i, criterion in enumerate(rubric.criteria):
                    payload[f"rubric_assessment[{criterion.id}][points]"] = student.rubric[i][0]
                    payload[f"rubric_assessment[{criterion.id}][comments]"] = str(student.rubric[i][1])
                    rating_id_chosen = ""
                    for j, rating in enumerate(criterion.ratings):
                        if criterion.ratings[j].points <= student.rubric[i][0]:
                            rating_id_chosen = criterion.ratings[j].id
                            break
                    payload[f"rubric_assessment[{criterion.id}][rating_id]"] = rating_id_chosen

                response = requests.put(gradeURI, params=payload, auth=BearerAuth(self.token))

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

    # CanvasUtil object, driver object for functionality,
    # if you want beta or production, a different .env path, or token, enter here into constructor.
    user_type = input("Are you using Canvas as a Teacher or a TA? {Choices: teacher, ta} ")
    if user_type != "teacher" and user_type != "ta":
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)
    canvas_type = input("Would you like to upload to Live Canvas or Canvas Beta? {Choices: Live, Beta} ")
    if canvas_type == "Live" or canvas_type == "live":
        canvas_util = CanvasUtil(PRODUCTION_URL,DOT_ENV_PATH,PRODUCTION_TOKEN_TYPE, user_type)
        print("Starting CSV Uploader With Parameters -> API_URL:",PRODUCTION_URL,"-> DOT_ENV: ",DOT_ENV_PATH,"-> TOKEN_TYPE:",PRODUCTION_TOKEN_TYPE)
    elif canvas_type == "Beta" or canvas_type == "beta":
        canvas_util = CanvasUtil(BETA_URL,DOT_ENV_PATH,BETA_TOKEN_TYPE, user_type)
        print("Starting CSV Uploader With Parameters -> API_URL:",BETA_URL,"-> DOT_ENV:",DOT_ENV_PATH,"-> TOKEN_TYPE:",BETA_TOKEN_TYPE)
    else:
        print("| InputError: Your input does not match one of the chosen types.")
        print("└─> exiting with error")
        exit(-1)

    # try to retrieve courses from canvas API, will gracefully fail if API key not present or invalid
    try:
        courses = canvas_util.get_courses_this_semester()
    except:
        print("| Canvas Util Object failed to be created. Is your API key valid?")
        print("| Hint: try using --setupenv to set up your environment variables.")
        print("└─> exiting with error")
        exit(-1)
    # gets list of all courses
    course_names = list(courses.keys())
    print(course_names)
    # You *must* be of role teacher to see your courses, this can be changed if different roles needed
    print("-=- Listing all courses for which you have role: Teacher in current enrollment period -=-")
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
    section_ids = canvas_util.get_section_ids(course_id)
    print(f"└─> {len(section_ids)} section(s) found")

    # enter a portion of all of the assignment name for a class assignment
    print("-=- Type some part of the title of your assignment - if it's \"Python Pitches\", type \"Pitches\" -=-")
    try:
        assignment_name = input()
        assignment_id = canvas_util.get_assignment_id_by_name(course_id, assignment_name)
    except:
        print("| Error: No matching assignment found")
        print("└─> exiting with error")
        exit(-1)
    print(f"└─> Found assignment ID: {assignment_id}")

    # fetch all student ids via sections in a course
    user_ids = {}
    for section in section_ids:
        canvas_util.get_student_ids_by_section(course_id, section, user_ids)

    # input CSV path that you with to upload
    print("-=- Please input path of CSV file: {If on WSL, remember to use mounted drives and linux formatted paths} -=-")
    csv_path = input()
    try:
        students_from_file = canvas_util.populate_students_from_csv(csv_path)
    except FileNotFoundError:
        print("| FileNotFoundError: The file path you specified could not be located")
        print("└─> exiting with error")
        exit(-1)

    # try to create rubric and load rubric formatting
    try:
        rubric_id = canvas_util.get_rubric_id(course_id, assignment_id)
        rubric_format = canvas_util.generate_rubric(course_id, rubric_id)
    except:
        print("| Rubric operation failed")
        print("└─> exiting with error")
        exit(-1)
    
    # try to upload grades via API
    try:
        canvas_util.upload_grades(course_id, user_ids, assignment_id, students_from_file, rubric_format)
    except:
        print("| Rubric Upload operation failed")
        print("└─> exiting with error")
        exit(-1)
    
    print("-=- Rubric Upload Complete. Shutting down -=-")

if __name__ == "__main__":
    main()