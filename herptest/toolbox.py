import ctypes
import _ctypes
import hashlib
import re
import tempfile
import shutil
import os
import sys
import logging

import importlib
import importlib.util
from ctypes import util
from os import path

DEFAULT_MAX_READ = 1024 * 1024


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


def write_to_file(lines, filename):
    with open(filename, 'w+') as my_file:
        for line in lines:
            my_file.write(line + "\n")
        my_file.close()


def load_module(filename, package_name=None):
    module_name = (package_name if package_name else '') + path.basename(path.splitext(filename)[0])
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except FileNotFoundError as e:
        print(type(e).__name__ + ": " + str(e))
        return None

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
    #print("Loading", name, "from", directory)
    libPath = find_library(directory, name) or path.join(directory, name, "lib" + name + '.so')
    hexHash = hashlib.md5(open(libPath,'rb').read()).hexdigest()
    #print("Loading", name, "from", directory, ":", libPath)

    # Create a temporary file, based on the MD5 hash, that is a copy of the target library, and load it.
    libTemp = path.join(tempfile.mkdtemp(), hexHash + "-" + shutil._basename(libPath))
    shutil.copyfile(libPath, libTemp)
    #print("Loaded as", libTemp)
    return ctypes.cdll.LoadLibrary(libTemp)


def load_library(directory, name):
    libPath = find_library(directory, name) or path.join(directory, "lib" + name + '.so')
    return ctypes.CDLL(libPath, mode=ctypes.RTLD_GLOBAL)


def unload_library(library):
    if "FreeLibrary" in dir(_ctypes):
        _ctypes.FreeLibrary(library)
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
