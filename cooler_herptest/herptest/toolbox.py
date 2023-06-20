import csv
import ctypes
import _ctypes
import difflib
import hashlib
import re
import tempfile
import shutil
import os
import sys
import string
import logging
import collections
import itertools
import pexpect
import time
import pyte
import traceback

import importlib
import importlib.util
from ctypes import util
from os import path
from numbers import Number
from subprocess import Popen, PIPE, TimeoutExpired

DEFAULT_MAX_READ = 1024 * 1024

__ansiterm = None


class PipeSet:
    """Class wrapping python pipes as a set to make it easier to read / write them"""
    def __init__(self):
        self.pipe_in, self.pipe_out = os.pipe()


    def write(self, bytes):
        os.write(self.pipe_out, bytes)


    def read(self, maxbytes = DEFAULT_MAX_READ):
        return os.read(self.pipe_in, maxbytes)


    def print(self, *argv, **kwargs):
        message = ''
        for index, arg in enumerate(argv):
            if not isinstance(arg, str):
                arg = str(arg)

            # Add separators before argument elements except for the first element
            message = message + ((kwargs['sep'] if 'sep' in kwargs else ' ') if index > 0 else '') + arg

        message = message + (kwargs['end'] if 'end' in kwargs else '')
        self.write(message.encode('utf-8'))


    def println(self, *argv, **kwargs):
        kwargs['end'] = '\n'
        self.print(*argv, **kwargs)


class SelectiveFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=0, add_level=True, **keywords):
        LOG_ALL = keywords.pop("LOG_ALL", False)
        self._CRITICAL = keywords.pop("CRITICAL", False or LOG_ALL)
        self._ERROR = keywords.pop("ERROR", False or LOG_ALL)
        self._WARNING = keywords.pop("WARNING", False or LOG_ALL)
        self._INFO = keywords.pop("INFO", False or LOG_ALL)
        self._DEBUG = keywords.pop("DEBUG", False or LOG_ALL)
        self._add_level = add_level
        logging.FileHandler.__init__(self, filename, mode, encoding, delay)


    def emit(self, record):
        if record.levelno == logging.CRITICAL and self._CRITICAL or \
          record.levelno == logging.ERROR and self._ERROR or \
          record.levelno == logging.WARNING and self._WARNING or \
          record.levelno == logging.INFO and self._INFO or \
          record.levelno == logging.DEBUG and self._DEBUG:
            if self._add_level:
                record.msg = "[%s] %s" % (record.levelname, record.msg)
            logging.FileHandler.emit(self, record)


class SelectiveStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None, add_level=False, **keywords):
        LOG_ALL = keywords.pop("LOG_ALL", False)
        self._CRITICAL = keywords.pop("CRITICAL", False or LOG_ALL)
        self._ERROR = keywords.pop("ERROR", False or LOG_ALL)
        self._WARNING = keywords.pop("WARNING", False or LOG_ALL)
        self._INFO = keywords.pop("INFO", False or LOG_ALL)
        self._DEBUG = keywords.pop("DEBUG", False or LOG_ALL)
        self._add_level = add_level
        logging.StreamHandler.__init__(self, stream)


    def emit(self, record):
        if record.levelno == logging.CRITICAL and self._CRITICAL or \
          record.levelno == logging.ERROR and self._ERROR or \
          record.levelno == logging.WARNING and self._WARNING or \
          record.levelno == logging.INFO and self._INFO or \
          record.levelno == logging.DEBUG and self._DEBUG:
            if self._add_level:
                record.msg = "[%s] %s" % (record.levelname, record.msg)
            logging.StreamHandler.emit(self, record)


def data_to_file(data, filename):
    with open(filename, 'wb+') as my_file:
        my_file.write(data)
        my_file.close()


def text_to_file(lines, filename):
    with open(filename, 'w+') as my_file:
        for line in lines:
            my_file.write(line + "\n")
        my_file.close()


#TODO: Deprecated; repllace with "text_to_file"
def write_to_file(lines, filename):
    text_to_file(lines, filename)


    start_dir = os.getcwd()
    os.chdir(working_dir)

def load_relative_module(target, neighbor, package_name=None):
    if not os.path.isabs(target):
        target = os.path.join(path.abspath(os.path.dirname(neighbor)), target)
    return load_module(target, package_name)


def load_module(filename, package_name=None):
    start_dir = os.getcwd()
    mod_dir, mod_file = path.split(filename)
    sys.path.append('./')
    module = None

    try:
        if mod_dir:
            os.chdir(mod_dir)

        module_name = (package_name if package_name else '') + path.splitext(mod_file)[0]
        spec = importlib.util.spec_from_file_location(module_name, mod_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except FileNotFoundError as e:
        logging.error(type(e).__name__ + ": " + str(e))
        return None
    except Exception as e:
        logging.error(type(e).__name__ + ": " + str(e))
        return None
    finally:
        os.chdir(start_dir)
        sys.path.remove('./')

    return module


def is_file(filename):
    if path.isfile(filename):
        return filename
    else:
        return None


def find_library(directory, name):
    result = (util.find_library(path.join(directory, name)) or
              util.find_library(path.join(directory, name, name)) or
              util.find_library(path.join(directory, "lib" + name)) or
              util.find_library(path.join(directory, name, "lib" + name)) or
              util.find_library(path.join(directory, "lib" + name + '.so')) or
              util.find_library(path.join(directory, name, "lib" + name + '.so')))

    return (result or
        is_file(path.join(directory, name)) or
        is_file(path.join(directory, name, name)) or
        is_file(path.join(directory, "lib" + name)) or
        is_file(path.join(directory, name, "lib" + name)) or
        is_file(path.join(directory, "lib" + name + '.so')) or
        is_file(path.join(directory, name, "lib" + name + '.so')))


# Hack: To get Python to load a DLL temporarily - so that it can be replaced later - we need to load a different name.
# To do this, we'll make a copy of the library, load it, then dispense with it when we're done.
def loadTempLibrary(directory, name):
    libPath = find_library(directory, name) or path.join(directory, name, "lib" + name + '.so')
    hexHash = hashlib.md5(open(libPath,'rb').read()).hexdigest()

    # Create a temporary file, based on the MD5 hash, that is a copy of the target library, and load it.
    libTemp = path.join(tempfile.mkdtemp(), hexHash + "-" + shutil._basename(libPath))
    shutil.copyfile(libPath, libTemp)
    return ctypes.cdll.LoadLibrary(libTemp)


def load_library(directory, name):
    libPath = find_library(directory, name) or path.join(directory, "lib" + name + '.so')
    return ctypes.CDLL(libPath, mode=ctypes.RTLD_GLOBAL)


def unload_library(library):
    if "FreeLibrary" in dir(_ctypes):
        _ctypes.FreeLibrary(library._handle)
    else:
        _ctypes.dlclose(library._handle)


'''
Perform the pure-Python equivalent of in-place `sed` substitution: e.g.,
`sed -i -e 's/'${pattern}'/'${repl}' "${filename}"`.

by Cecil Curry (https://stackoverflow.com/questions/4427542/how-to-do-sed-like-text-replace-with-python)
'''
def sed(filename, pattern, repl):
    # For efficiency, precompile the passed regular expression.
    pattern_compiled = re.compile(pattern)

    # For portability, NamedTemporaryFile() defaults to mode "w+b" (i.e., binary writing with updating).
    # This is usually a good thing. In this case, however, binary writing imposes non-trivial encoding
    # constraints trivially resolved by switching to text writing. Let's do that.
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
        with open(filename) as src_file:
            for line in src_file:
                tmp_file.write(pattern_compiled.sub(repl, line))

    # Overwrite the original file with the munged temporary file in a manner preserving file attributes.
    shutil.copystat(filename, tmp_file.name)
    shutil.move(tmp_file.name, filename)


# NOTE: If avoid_collisions is True, returns non-CP437 box characters to avoid collisions with 8-bit encodings.
def convert_curses_capture(capture, text_only=False, box_only=False, avoid_collisions=False):
    converted = []
    box_chars = "┍┑┕┙━┃" if avoid_collisions else "┌┐└┘─│"
    pattern = re.compile("((lq+k)|(mqq+j)|(qqqqq+))") # Matches strings that are likely boxes (don't occur in language)
    curses_to_box = str.maketrans("lkmjqx", box_chars) # These are stand-in chars and cannot occur in CP437.
#    box_to_cp437 = str.maketrans(box_chars, "┌┐└┘─│") # Convert non-CP437 variant to CP437 variant. (Needed?)
#    box_to_space = str.maketrans(box_chars,"      ") # Convert boxes to spaces (Needed?)

    # Find matches to known box sequences.
    matches = [(line, [match.span() for match in pattern.finditer(line)]) for line in capture]

    for line, match_set in matches:
        next = 0
        line_set = []
        for start, end in match_set:
            # If there are any characters before the match that we haven't added yet to our string set, add them now.
            if start != next:
                line_set.append(line[next:start])

            # Convert to analogous (but not identical) box characters; these variants do not occur in CP437.
            line_set.append(line[start:end].translate(curses_to_box))
            next = end

        if next != len(line):
            line_set.append(line[next:])
        converted.append("".join(line_set))

    # Next, find characters that might be matches, and triangulate using already converted characters.
    pattern = re.compile("[lkmjqx]")
    matches = [[match.span() for match in pattern.finditer(line)] for line in converted]
    for line_no, match_set in enumerate(matches):
        line = converted[line_no]
        next = 0
        line_set = []
        for index, _ in match_set:
        # If there are any characters before the match that we haven't added yet to our string set, add them now.
            if index != next:
                line_set.append(line[next:index])

            if line[index] == "l":
                if len(line) > index+1 and line[index+1] == "━":
                    line_set.append("┍")
                elif len(converted) < line_no+1 and len(converted[line_no+1]) > index and converted[line_no+1][index] == "┃":
                    line_set.append("┍")
                else:
                    line_set.append("l")

            elif line[index] == "k":
                if index > 0 and line[index-1] == "━":
                    line_set.append("┑")
                elif len(converted) < line_no+1 and len(converted[line_no+1]) > index and converted[line_no+1][index] == "┃":
                    line_set.append("┑")
                else:
                    line_set.append("k")

            elif line[index] == "m":
                if len(line) > index+1 and line[index+1] == "━":
                    line_set.append("┕")
                elif line_no > 0 and len(converted[line_no-1]) > index and converted[line_no-1][index] == "┃":
                    line_set.append("┕")
                else:
                    line_set.append("m")

            elif line[index] == "j":
                if index > 0 and line[index-1] == "━":
                    line_set.append("┙")
                elif line_no > 0 and len(converted[line_no-1]) > index and converted[line_no-1][index] == "┃":
                    line_set.append("┙")
                else:
                    line_set.append("j")

            elif line[index] == "q":
                if index > 0 and (line[index-1] == "━" or line[index-1] == "┕" or line[index-1] == "┍"):
                    line_set.append("━")
                elif len(line) > index+1 and (line[index+1] == "━" or line[index+1] == "┙" or line[index+1] == "┑"):
                    line_set.append("━")
                else:
                    line_set.append("q")

            elif line[index] == "x":
                if line_no > 0 and len(converted[line_no-1]) > index and (converted[line_no-1][index] == "┃" or converted[line_no-1][index] == "┍" or converted[line_no-1][index] == "┑"):
                    line_set.append("┃")
                elif len(converted) > line_no+1 and len(converted[line_no+1]) > index and (converted[line_no+1][index] == "┃" or converted[line_no+1][index] == "┕" or converted[line_no+1][index] == "┙"):
                    line_set.append("┃")
                else:
                    line_set.append("x")

            next = index + 1

        # Finish construction of final line (if necessary) and merge lines into single string again.
        if next != len(line):
            line_set.append(line[next:])
        converted[line_no] = "".join(line_set)

        # If flags set, grab either only the text or only the box characters.
        if text_only:
            converted = "".join([" " if character in box_chars else character for character in converted])
        elif box_only:
            converted = "".join([character if character in box_chars else " " for character in converted])
    return converted


def causes_exception(test_me):
    try:
        test_me()
    except Exception as e:
        return True
    return False


# TODO: Deprecate - replace with 'is_writable_attribute'
def can_write_property(target, property_name, test_value):
#    return causes_exception(lambda: exec("target." + property_name + " = test_value"))
    return not causes_exception(lambda t=target, v=test_value: exec("t." + property_name + " = v"))


def is_writable_attribute(target, attr_name, test_value):
#    return causes_exception(lambda t=target, v=test_value: exec("t." + attr_name + " = v"))
    return hasattr(target, attr_name) and not causes_exception(lambda t=target, v=test_value: exec("t." + attr_name + " = v"))


def is_readonly_attribute(target, attr_name, test_value):
    return hasattr(target, attr_name) and causes_exception(lambda t=target, v=test_value: exec("t." + attr_name + " = v"))


def get_public_attr(classtype, exclusions=[], filter_callable=True):
    key_list = [key for key in classtype.__dict__.keys() if not key.startswith("_")] # Not protected/private
    key_list = [key for key in key_list if not type(classtype.__dict__[key]).__name__ in exclusions] # Not excluded
    if filter_callable:
        key_list = [key for key in key_list if not callable(classtype.__dict__[key])] # Keep non-callable
    return key_list


def get_public_vars(target, filter_callable=True):
    var_list = [entry for entry in vars(target).keys() if not entry.startswith("_")]
    if filter_callable:
        var_list = [key for key in var_list if not callable(vars(target)[key])]
    return var_list


def save_csv(filename, row_data, insert_key = False, dialect = 'excel'):
    # Open file for writing
    with open(filename, 'w', newline = '') as csvFile:
        writer = csv.writer(csvFile, dialect, quotechar='"', delimiter=',')

        # Write the data
        if insert_key:
            for key, row in row_data.iteritems():
                writer.writerow('{:f}'.format(val) if isinstance(val, Number) else val for val in [ key ] + row)
        else:
            for row in row_data:
                writer.writerow('{:f}'.format(val) if isinstance(val, Number) else val for val in row)

        csvFile.close()


def append_csv(filename, row_data, insert_key = False, dialect = 'excel'):
    # Open file for appending
    with open(filename, 'a', newline = '') as csvFile:
        writer = csv.writer(csvFile, dialect, quotechar='"', delimiter=',')

        # Write the data
        if insert_key:
            for key, row in row_data.iteritems():
                writer.writerow('{:f}'.format(val) if isinstance(val, Number) else val for val in [ key ] + row)
        else:
            for row in row_data:
                writer.writerow('{:f}'.format(val) if isinstance(val, Number) else val for val in row)

        csvFile.close()


# Formats input as list of (delay, string) pairs
def _prep_input(input):
    # If the input is just a string, return a simple string
    if type(input) == str:
        return [(0, input)]
    # If it isn't iterable, try to convert it to a string and pass as input.
    elif not hasattr(input, '__iter__'):
       return [(0, str(input))]

    # DEPRECATED CASE: If the list is solely and only a list of strings, concatenate them using new line chars.
    all_strings = True
    for entry in input:
        if type(entry) != str:
            all_strings = False
            break
    if all_strings:
        return [(0, "\n".join(input))]

    # Finally, if it is iterable (and not the special case), go through each element.
    result = []
    for entry in input:
        # If this is a (int, object) tuple, get the delay and object serving as input.
        if type(entry) == tuple and len(entry) == 2 and type(entry[0]) == int:
            delay = entry[0]
            value = entry[1]
        # Otherwise, add a delay of zero and make the entry the value.
        else:
            delay = 0
            value = entry
        # Try to convert the value into a string; if that fails, use a placeholder.
        try:
            value = str(value)
        except:
            value = "Unconvertible-%s" % value.__class__.__name__
        # Finally, append to the result list.
        result.append((delay, value))

    # Return the result list.
    return result


def _convert_type(targetType, value):
    try:
        return targetType(value)
    except ValueError:
        return None


def parse_tokens(input, is_case_sensitive=False, number_string_match=False):
    lines = input.splitlines()
    output = []
    tokens = []

    for line in lines:
        # Get a list of punctuation marks except radix and hyphen/minus so we can remove them.
        punctuation = string.punctuation.translate(str.maketrans('', '', '.-'))
        punc_to_space = str.maketrans(punctuation, " " * len(punctuation))
        radix_dash_to_space = str.maketrans('.-', '  ')

        if not is_case_sensitive:
            line = line.lower()

        for token in line.strip().translate(punc_to_space).split():
            token = token.strip()
            # If this isn't a float, replace periods with space.
            if _convert_type(float, token) == None:
                tokens += [entry.strip() for entry in token.translate(radix_dash_to_space).split()]
            else:
                if number_string_match:
                  tokens += [token]
                else:
                  if round(float(token)) == float(token):
                    tokens += [str(round(float(token)))]
                  else:
                    tokens += [str(float(token))]

        if tokens:
            output.append(tokens)
            tokens = []

    return output


def get_value_or_error_msg(target_function, params):
    try:
        return target_function(*params)
    except Exception as e:
        logging.debug(traceback.format_exc())
        try:
            return "%s: %s" % (e.__class__.__name__, str(e))
        except:
            return e.__class__.__name__


def get_type_and_value_string(target):
    return type(target).__name__ + ": " + str(target)


def ansi_to_text(text, lines=30, columns=80):
#, convert_glyphs=True):
    screen = pyte.Screen(columns, lines)
    stream = pyte.Stream(screen)
    stream.use_utf8 = False
    stream.feed(text)
    return "\n".join(screen.display)


def get_vt_output(working_dir, command, proc_input, timeout, tokenize=True, keep_lines=False, sleep=False, raw=False, lines=30, columns=80, readsize=1000000):
    # Process the input on the front end.
    proc_input = _prep_input(proc_input)

    # Ugly hack to make sure the window size is big enough (ugh).
    old_rows = os.environ['LINES'] if 'LINES' in os.environ else "25"
    old_cols = os.environ['COLUMNS'] if 'COLUMNS' in os.environ else "80"
    os.environ['LINES'] = str(lines)
    os.environ['COLUMNS'] = str(columns)

    # Grab the current working directory, then change to the target directory.
    start_dir = os.getcwd()
    os.chdir(working_dir)

    try:
        # Start the process, get the output, and return to the original directory.
        process = pexpect.spawn(command[0], command[1:], timeout=timeout)

        for delay, entry in proc_input:
            time.sleep(delay)
            process.write(entry)

        # Give the program enough time to update, then pull the data
        if sleep:
            time.sleep(timeout)
        process.flush()

        results = process.read_nonblocking(readsize, timeout=timeout).decode()
        process.terminate(True)

        if not raw:
            results = ansi_to_text(results, lines, columns)
    except Exception as e:
        stack_trace = traceback.format_exc()
        logging.error("%s: %s\n%s" % (type(e).__name__, e, stack_trace))

    finally:
        os.chdir(start_dir)

        # Restore the terminal size variables.
        os.environ['LINES'] = old_rows
        os.environ['COLUMNS'] = old_cols

    if not raw and tokenize:
        results = parse_tokens(results)
        if not keep_lines:
            results = list(itertools.chain(*results))

    return results


##### CONSOLE OUTPUT COMMAND PROCESSING #####
def get_py_output(working_dir, command, input, timeout, tokenize=True, keep_lines=False):
    command = [command] if isinstance(command, str) else command if hasattr(command, '__iter__') else [str(command)]
    return get_cmd_output(working_dir, [sys.executable] + command, input, timeout, tokenize, keep_lines)


def get_cmd_output(working_dir, command, proc_input, timeout, tokenize=True, keep_lines=False):
    # Format the input, grab the current working directory, then change to the target directory.
    proc_input = _prep_input(proc_input)
    start_dir = os.getcwd()
    os.chdir(working_dir)

    # Start the process, send input, and gather output.
    try:
        # First, start the process; then, after the designated delay, send the data.
        process = Popen(command, stdout=PIPE, stdin=PIPE, stderr=PIPE, text=True)

        for delay, entry in proc_input:
            time.sleep(delay)
            process.stdin.write(entry + "\n")
            process.stdin.flush()

        # After all input has been sent, if the process has not quit, wait - and kill if necessary.
        if process.poll() == None:
            try:
                process.wait(timeout=timeout)
            except TimeoutExpired as e:
                process.kill()

        # Gather the output of the process.
        results = process.communicate(timeout=timeout)[0]
    except Exception as e:
        print(e)

    # Return to the original directory.
    finally:
        os.chdir(start_dir)

    # Format the return data, as appropriate.
    if tokenize:
        results = parse_tokens(results)
        if not keep_lines:
            results = list(itertools.chain(*results))

    return results


##### MATCHING FUNCTIONS #######
def match_sets(left_set, right_set):
    matched = [None] * max(len(left_set), len(right_set))

    seq = difflib.SequenceMatcher(None, left_set, right_set, False)
    for a, b, size in seq.get_matching_blocks():
        for index in range(0, size):
            matched[a + index] = b + index

    return matched


def match_subset(superset, candidate):
    matched = [None] * len(candidate)

    seq = difflib.SequenceMatcher(None, candidate, superset, False)
    for a, b, size in seq.get_matching_blocks():
        for index in range(0, size):
            matched[a + index] = b + index

    return matched


##### RESULT COMPARATORS #####
def compare_element(lhs, rhs):
    if lhs == rhs:
        return 1
    else:
        return 0


def compare_iterable_exact(lhs, rhs):
    return compare_iterable_custom(match_sets, lhs, rhs)


def compare_iterable_subset(lhs, rhs):
    return compare_iterable_custom(match_subset, lhs, rhs)


def compare_iterable_custom(match_function, lhs, rhs):
    # Get match results and do a basic comparison. We'll need 100% match.
    for entry in match_function(lhs, rhs):
        if entry == None:
            return 0

    return 1


# Get screen dimensions
def __get_screen_dimensions(text):
    return (len(text), len(text[0]) if len(text) > 0 else 0)


# Returns true i the position is in the range, and false otherwise.
def __pos_in_range(pos_x, pos_y, start_x, start_y, width, height):
    if pos_x >= start_x and pos_x < start_x + width:
        if pos_y >= start_y and pos_y < start_y + height:
            return True
    return False


# Changes dimensions, if necessary, to fit within the bounds of a screen.
def __adjust_dimensions(text, x, y, width, height):
    screen_height, screen_width = __get_screen_dimensions(text)

    # Make sure the x/y positions are within the range of the screen
    if x < 0:
        width += x
        x = 0
    elif x >= screen_width:
        x = screen_width - 1
        width = 0
    if y < 0:
        height += y
        y = 0
    elif y >= screen_height:
        y = screen_height - 1
        height = 0

    # Ensure that the ending x/y positions are within the range of the screen
    if x + width > screen_width:
        width = screen_width - x
    if y + height > screen_height:
        height = screen_height - y

    width = max(0, width)
    height = max(0, height)

    return x, y, width, height


# Get a subscreen of a larger screen
def get_subscreen(text, x, y, width, height):
    # Get the screen in row, col format if it isn't already.
    if isinstance(text, str) or not hasattr(text, '__iter__'):
        text = str(text).splitlines()
    for index in range(len(text)):
        text[index] = str(text[index])

    # Fix the dimensions if any of them are out of bounds.
    x, y, width, height = __adjust_dimensions(text, x, y, width, height)

    # Grab the subscreen and return it.
    text = [''.join([text[y_pos][x_pos] for x_pos in range(x, x + width)]) for y_pos in range(y, y + height)]
    return text


# Get a subscreen of a larger screen with an area cut out (filled with spaces)
def get_cutout(text, x, y, width, height, hollow_x, hollow_y, hollow_width, hollow_height):
    # Adjust the hollow coordinates to be based on the subscreen, which we will grab presently.
    if x >= 0:
        hollow_x -= x
    if y >= 0:
        hollow_y -= y

    # If the hollow coordinates are negative, zero them and reduce the hollow size accordingly.
    if hollow_x < 0:
        hollow_width += hollow_x
        hollow_x = 0

    if hollow_y < 0:
        hollow_height += hollow_y
        hollow_y = 0

    # Get the subscreen
    text = get_subscreen(text, x, y, width, height)
    height, width = __get_screen_dimensions(text)

    # If the hollow starts outside of the subscreen, just return the subscreen.
    if hollow_x >= width or hollow_y >= height:
        return text

    # Adjust the hollow dimensions to fit within the subscreen.
    hollow_x, hollow_y, hollow_width, hollow_height = __adjust_dimensions(text, hollow_x, hollow_y, hollow_width, hollow_height)

    # With the subscreen grabbed and the hollow within the subscreen, it's time to get the values.
    cutout_screen = [[" " for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if not __pos_in_range(x, y, hollow_x, hollow_y, hollow_width, hollow_height):
                cutout_screen[y][x] = text[y][x]

    return ["".join(row) for row in cutout_screen]


# Compare two screens to see if they are identical.
def compare_screen(lhs, rhs, case_sensitive=False):
    # Get the screens in row, col format if they aren't already.
    if isinstance(lhs, str) or not hasattr(lhs, '__iter__'):
        lhs = str(lhs).splitlines()
    if isinstance(rhs, str) or not hasattr(rhs, '__iter__'):
        rhs = str(rhs).splitlines()
    for index in range(len(lhs)):
        lhs[index] = str(lhs[index])
    for index in range(len(rhs)):
        rhs[index] = str(rhs[index])

    # If the screens are not the same size, this comparison automatically fails. (Error here?)
    height, width = __get_screen_dimensions(lhs)
    if __get_screen_dimensions(rhs) != (height, width):
        return 0

    # Check every cell; if any do not match, the comparison fails.
    for y in range(height):
        lhs[y] = lhs[y] if case_sensitive else lhs[y].lower()
        rhs[y] = rhs[y] if case_sensitive else rhs[y].lower()
        for x in range(width):
            if lhs[y][x] != rhs[y][x]:
                return 0
    return 1


# Compare subscreens of two screens to see if they are identical.
def compare_subscreen(lhs, rhs, x, y, width, height, case_sensitive=False):
    lhs = get_subscreen(lhs, x, y, width, height)
    rhs = get_subscreen(rhs, x, y, width, height)
    return compare_screen(lhs, rhs, case_sensitive)


# Compare cutout subscreens of two screens to see if they are equal.
def compare_cutout(lhs, rhs, x, y, width, height, hollow_x, hollow_y, hollow_width, hollow_height, case_sensitive=False):
    lhs = get_cutout(lhs, x, y, width, height, hollow_x, hollow_y, hollow_width, hollow_height)
    rhs = get_cutout(rhs, x, y, width, height, hollow_x, hollow_y, hollow_width, hollow_height)
    return compare_screen(lhs, rhs, case_sensitive)
