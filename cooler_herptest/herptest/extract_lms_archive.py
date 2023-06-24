#!/usr/bin/python

import gzip
import tarfile
import zipfile

import tempfile
import glob
import os
import os.path
import shutil
import argparse
import re
from enum import Enum

Lms = Enum('LMS', ['Canvas', 'ZyBooks'])
CANVAS_PATTERN = r"(?P<name>[^_]*)(?P<late>_LATE)?_(?P<lms_id>[0-9]*)_(?P<sub_id>[0-9]*)_(?P<filename>.*)"


def main():
    parser = argparse.ArgumentParser(description="Unzips submissions from LMS. Defaults to Canvas format.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_help = True
    parser.add_argument('filename', help='submissions zip file')
    parser.add_argument('destination', help='where to extract submissions to')
    parser.add_argument('-z', '--zybooks', help='process ZyBooks archive', action='store_true')

    args = parser.parse_args()
    filetype = (Lms.ZyBooks if args.zybooks else Lms.Canvas) # Default to Canvas file type

    # Set up a temporary working directory for submission data and extract the archive.
    tmp_path = tempfile.mkdtemp()
    with zipfile.ZipFile(args.filename) as zf:
        zf.extractall(path=tmp_path)

    # Go through the raw submission files one at a time.
    submissions = glob.glob(os.path.join(tmp_path, "*"))
    success_count = 0
    warning_count = 0

    for rawfile in submissions:
        success_count += 1

        # separate the submission name from the file type (for later use)
        submission, ext = os.path.splitext(rawfile)

        # Handle the special case of gzip files (which by default contain another extension)
        while ext and ext.lower().split('.')[1] == "gz":
           submission, ext2 = os.path.splitext(submission)
           ext = ext2 + ext

        # Based in the LMS type, extract submission information from the submission string.
        if filetype == Lms.Canvas:
            attributes = re.match(CANVAS_PATTERN, os.path.basename(submission))

            # Deal with Canvas appending "LATE" to student names with an underscore (add to name with a dash)
            student = attributes.group('name')
            lms_id = attributes.group('lms_id')
            submission_id = attributes.group('sub_id')
            header = attributes.group('filename')
            late = (True if attributes.group('late') else False)

            # Give a warning if there was trouble parsing the name.
            if not (student or lms_id or submission_id or header):
                print("Warning: missing elements in [%s]. Rebuilt files may be malformed." % submission)

            # Account for Canvas's submission count suffix (gross, Canvas).
            count_info = header.rsplit("-", 1)
            if len(count_info) > 1:
                try:
                    int(count_info[1])
                    header = count_info[0]
                except ValueError:
                    pass # Right side of "-" was not a number, so this is not a Canvas submission count suffix.

        # Handler for ZyBooks submissions - TODO: Redo with regex (as above)
        elif filetype == Lms.ZyBooks:
            attributes = os.path.basename(submission).rsplit("_", 3)

            # Handle missing elements in filenames as best we can (limited to weird Canvas output configurations)
            if len(attributes) < 4:
                print("Warning: [%s] cannot be reformatted. Assuming generic values." % submission)
                attributes[1:1] = [""] * 4 - len(attributes)

            student, lms_id, submission_date, submission_time = attributes
            submission_id = submission_date + "." + submission_time
            header = "submission"

        # We shouldn't reach this. If we do, something is wrong; it should catch invalid LMS types.
        else:
            print("Uh-oh, invalid LMS type... we should never get here!")
            exit(1)

        # If the submission was late, mark it as such.
        if attributes.group('late'):
            student += "-LATE"

        # Now that we've processed submission information, reconstruct the files.
        ext = ext.lower()
        filename = header + ext

        student_path = os.path.join(args.destination, student + "_" + lms_id)

        if not os.path.isdir(student_path):
            os.makedirs(student_path)

        if ext == ".zip":
            try:
                with zipfile.ZipFile(rawfile) as zf:
                    zf.extractall(path=student_path)
            except zipfile.BadZipFile:
                print("Warning: [%s] is not a zipfile; treating like normal file." % os.path.basename(rawfile))
                shutil.copyfile(rawfile, os.path.join(student_path, filename))
                warning_count += 1
        elif ext == ".tgz" or ext == ".tar.gz" or ext.endswith(".tar"):
            try:
                with tarfile.open(rawfile, ("r" if ext.endswith(".tar") else "r:gz")) as tf:
                    tf.extractall(path=student_path)
            except tarfile.TarError:
                print("Warning: [%s] could not be read / extracted; treating like normal file." % os.path.basename(rawfile))
                shutil.copyfile(rawfile, os.path.join(student_path, filename))
                warning_count += 1
        elif ext.lower().endswith(".gz"):
            try:
                with gzip.open(rawfile, "rb") as gzf:
                    with open(os.path.join(student_path, filename.rsplit(".", 1)[0]), "wb") as outfile:
                        outfile.write(gzf.read())
            except gzip.BadGzipFile:
                print("Warning: [%s] could not be read / extracted; treating like normal file." % os.path.basename(rawfile))
                shutil.copyfile(rawfile, os.path.join(student_path, filename))
                warning_count += 1
            except:
                print("Warning: could not write extracted file; copying [%s] as normal file." % os.path.basename(rawfile))
                shutil.copyfile(rawfile, os.path.join(student_path, filename))
                warning_count += 1
        else:
            shutil.copyfile(rawfile, os.path.join(student_path, filename))

    print("Successfuly extracted %d submissions with %d warnings." % (success_count, warning_count))

if __name__ == "__main__":
    main()
