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
    for submission in submissions:
        student, _, _, filename = os.path.basename(submission).split("_", 3)
        header, ext = os.path.splitext(filename)
        student_path = os.path.join(args.destination, student)
        if not os.path.isdir(student_path):
            os.mkdir(student_path)

        if ext.lower() == ".zip":
            with zipfile.ZipFile(submission) as zf:
                zf.extractall(path=student_path)
        else:
            shutil.copyfile(submission, os.path.join(student_path, filename))

if __name__ == "__main__":
    main()

