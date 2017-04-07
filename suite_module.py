import ctypes
import _ctypes
import hashlib
import tempfile
import shutil

from ctypes import util
from os import path


# Hack: To get Python to load a DLL temporarily - so that it can be replaced later - we need to load a different name.
# To do this, we'll make a copy of the library, load it, then dispense with it when we're done.
def loadTempLibrary(directory, name):
    #print("Loading", name, "from", directory)
    libPath = findLibrary(directory, name) or path.join(directory, name, "lib" + name + '.so')
    hexHash = hashlib.md5(open(libPath,'rb').read()).hexdigest()
    #print("Loading", name, "from", directory, ":", libPath)

    # Create a temporary file, based on the MD5 hash, that is a copy of the target library, and load it.
    libTemp = path.join(tempfile.mkdtemp(), hexHash + "-" + shutil._basename(libPath))
    shutil.copyfile(libPath, libTemp)
    #print("Loaded as", libTemp)
    return ctypes.cdll.LoadLibrary(libTemp)

#def unloadTempLibrary(library):
#    ctypes.cdll.FreeLibrary(library._handle)
#    ctypes.cdll.FreeLibrary(library)
#    del library

def isFile(filename):
    if path.isfile(filename):
        return filename
    else:
        return None


def loadLibrary(directory, name):
    libPath = findLibrary(directory, name) or path.join(directory, "lib" + name + '.so')
    return ctypes.CDLL(libPath, mode=ctypes.RTLD_GLOBAL)


def unloadLibrary(library):
    if "FreeLibrary" in dir(_ctypes):
        _ctypes.FreeLibrary(library)
    else:
        _ctypes.dlclose(library._handle)


def findLibrary(directory, name):
    result = (util.find_library(path.join(directory, name)) or
              util.find_library(path.join(directory, name, name)) or
              util.find_library(path.join(directory, "lib" + name)) or
              util.find_library(path.join(directory, name, "lib" + name)) or
              util.find_library(path.join(directory, "lib" + name + '.so')) or
              util.find_library(path.join(directory, name, "lib" + name + '.so')))

    return (result or
        isFile(path.join(directory, name)) or
        isFile(path.join(directory, name, name)) or
        isFile(path.join(directory, "lib" + name)) or
        isFile(path.join(directory, name, "lib" + name)) or
        isFile(path.join(directory, "lib" + name + '.so')) or
        isFile(path.join(directory, name, "lib" + name + '.so')))
