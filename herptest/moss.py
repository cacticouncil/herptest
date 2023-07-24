import mosspy
import os
from dotenv import load_dotenv

# MossUtil class to encapsulate the moss functionality in objects
class MossUtil:
    def __init__(self, dotenv_path):
        load_dotenv(dotenv_path)  # load token from .env file
        self.userid = os.getenv("USERID")
        if self.userid == None:
            raise ValueError("Non-existant Moss Token, try running --setupenv")


    # Returns mosspy object bound to userid and language

    # Language choices:
    # language_list = ["c", "cc", "java", "ml", "pascal", "ada",
    # "lisp", "scheme", "haskell", "fortran",
    # "ascii", "vhdl", "perl", "matlab", "python",
    # "mips", "prolog", "spice", "vb", "csharp",
    # "modula2", "a8086", "javascript", "plsql", "verilog"]

    
    def init_moss(self, language):
        language_list = ["c", "cc", "java", "ml", "pascal", "ada",
        "lisp", "scheme", "haskell", "fortran",
        "ascii", "vhdl", "perl", "matlab", "python",
        "mips", "prolog", "spice", "vb", "csharp",
        "modula2", "a8086", "javascript", "plsql", "verilog"]
        for lang in language_list:
            if lang == language.lower():
                self.moss_obj = mosspy.Moss(self.userid, language)
                return
        raise ValueError("Language not valid choice of language from MOSS.")
            


    # Adds files to be sent with submission
    def add_files(self, file_name_base, file_name_submissions):
        
        if(os.path.isdir(file_name_base)):
            base_files = os.listdir(file_name_base)
        else:
            # error if not directory (can't read in base files)
            raise ValueError("Base file is not a directory",file_name_base)
        
        for base in base_files:
            self.moss_obj.addBaseFile(os.path.join(file_name_base,base))
            # print(base)

        if(os.path.isdir(file_name_submissions)):
            student_files = os.listdir(file_name_submissions)
        else:
            # error if not directory (can't read in base files)
            raise ValueError("Student submissions file is not a directory",file_name_submissions)

        for student in student_files:
            # self.moss_obj.addFile(student)
            submission_files = os.listdir(os.path.join(file_name_submissions, student))
            for submission in submission_files:
                self.moss_obj.addFile(os.path.join(file_name_submissions,student,submission))
                # print(os.path.join(student, submission))
            # self.moss_obj.addFilesByWildcard("submission/a01-*.py")



    # Sends files via url created with moss_obj
    def send_files(self):
        self.url = self.moss_obj.send() # Submission Report URL
        # self.url = self.moss_obj.send(lambda: print('*', end='', flush=True))

        print ("Report Url: " + self.url)



    def save_files(self):
        # Save report file
        self.moss_obj.saveWebPage(self.url, "report.html")

        # Download whole report locally including code diff links
        mosspy.download_report(self.url, "report/", connections=8)