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
        attributes = os.path.basename(submission).rsplit("_", 3)
        if len(attributes) < 4:
            print("Warning: [" + submission + "] cannot be reformatted. Skipping.")
            continue

        # Extract submission information from the Canvas formatted filename.
        student, canvas_id, sub_id, filename = attributes
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

        student_path = os.path.join(args.destination, student + "_" + canvas_id)
        if not os.path.isdir(student_path):
            os.mkdir(student_path)

        if ext.lower() == ".zip":
            with zipfile.ZipFile(submission) as zf:
                zf.extractall(path=student_path)
        else:
            shutil.copyfile(submission, os.path.join(student_path, filename))

if __name__ == "__main__":
    main()

