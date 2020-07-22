#!/usr/bin/python

import zipfile
import tempfile
import glob
import os
import os.path
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description="Unzips submissions", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_help = True
    parser.add_argument('filename', help='submissions zip file')
    parser.add_argument('destination', help='where to extract submissions to')
    args = parser.parse_args()

    tmp_path = tempfile.mkdtemp()
    with zipfile.ZipFile(args.filename) as zf:
        zf.extractall(path=tmp_path)

    submissions = glob.glob(os.path.join(tmp_path, "*"))
    success_count = 0
    warning_count = 0
    for submission in submissions:
        success_count += 1
        attributes = os.path.basename(submission).split("_", 3)

        # Deal with Canvas appending "LATE" to student names with an underscore (add to name with a dash)
        if len(attributes) > 1 and attributes[1] == "LATE":
            attributes[0:2] = [attributes[0] + "-LATE"]
            if len(attributes) == 3:
                attributes[2:] = attributes[2].split("_", 1)

        # Handle missing elements in filenames as best we can (limited to weird Canvas output configurations)
        if len(attributes) == 1:
            print("Warning: [%s] cannot be reformatted. Assuming generic filename." % submission)
            attributes[1:1] = ["", "", "submission.file"]
            warning_count += 1
        elif len(attributes) == 2:
            attributes[1:1] = ["", ""]
        elif len(attributes) == 3:
            attributes[2:2] = [""]

        student, lms_id, submission_id, filename = attributes

        # Extract submission information from the Canvas formatted filename.
        header, ext = os.path.splitext(filename)

        # Handle the special case of gzip files (which by default contain another extension)
        if ext.lower() == ".gz":
            header, ext = os.path.splitext(header)
            ext = ext + ".gz"

        # Account for Canvas's submission count suffix.
        count_info = header.rsplit("-", 1)
        if len(count_info) > 1:
            try:
                int(count_info[1])
                filename = count_info[0] + ext
            except ValueError:
                pass # Right side of "-" was not a number, so this is not a Canvas submission count suffix.

        student_path = os.path.join(args.destination, student + "_" + lms_id)
        if not os.path.isdir(student_path):
            os.mkdir(student_path)

        if ext.lower() == ".zip":
            with zipfile.ZipFile(submission) as zf:
                zf.extractall(path=student_path)
        else:
            shutil.copyfile(submission, os.path.join(student_path, filename))
    print("Successfuly extracted %d submissions with %d warnings." % (success_count, warning_count))

if __name__ == "__main__":
    main()

