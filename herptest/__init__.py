import inspect
import os.path
from types import SimpleNamespace
from easydict import EasyDict

# Test Suite Configuration
class Config(EasyDict):
    def __init__(self, runtime=None, test_sets=None, **keywords):
        super().__init__()
        self["runtime"] = runtime
        self["sets"] = test_sets

        # Log locations
        self.general = EasyDict({"result_path":  "Results",
                        "result_file":  "result.csv",
                        "error_log":    "error.log",
                        "summary_file": "summary.csv"})

        # Paths to base files, target source destination, and resources
        self.build = EasyDict({"base":          None,
                               "destination":   None,
                               "resources":     None,

        # Build parameters: source folder (src), build destination (bin)
                               "subject_src":   "Source/Subject",
                               "subject_bin":   "Build/Subject",
                               "framework_src": "Source/Subject",
                               "framework_bin": "Build/Subject",

        # Build commands: preparing & compiling (additional keys: $source_dir, $build_dir)
        # Command format: list[] is single command's elements (command and arguments); tuple() is list of commands.
                               "prep_cmd": None,
                               "compile_cmd": None,
                               "post_cmd": None})

        # Process keywords to make additional assignments.
        for key, value in keywords:
             self[key] = value

#            parent = self
            # If this is a top-level assignment, it's easy-peasy. :)
#            if not "." in key:
#                if not key.isidentifier():
#                    raise Exception("Tried to use invalid string in easydict")
#                parent[key] = value
#                continue
            # If the key is nested, split off the "final" key from the parent key so we can iterate.
#            parent_key, final_key = key.rsplit(".", 1)
#            if not final_key.isidentifier():
#                raise Exception("Tried to use invalid string in easydict")
            # For each parent key section, traverse, adding dictionaries as needed.
#            for section in parent_key.split("."):
#                if not section.isidentifier():
#                    raise Exception("Tried to use invalid string in easydict")
                # If the section doesn't exist, add it. Then traverse into that section.
#                if not hasattr(parent, section):
#                    parent.section = EasyDict()
#                parent = parent[section]
#            parent[final_key] = value


    # Make configuration paths absolute
    def make_paths_absolute(self):
        self.general.result_path = os.path.abspath(self.general.result_path) if self.general.result_path else None

        self.build.base = os.path.abspath(self.build.base) if self.build.base else None
        self.build.destination = os.path.abspath(self.build.destination) if self.build.destination else None
        self.build.resources = os.path.abspath(self.build.resources) if self.build.resources else None

        self.build.subject_src = os.path.abspath(self.build.subject_src) if self.build.subject_src else None
        self.build.subject_bin = os.path.abspath(self.build.subject_bin) if self.build.subject_bin else None
        self.build.framework_src = os.path.abspath(self.build.framework_src) if self.build.framework_src else None
        self.build.framework_bin = os.path.abspath(self.build.framework_bin) if self.build.framework_bin else None


    ######################################################
    # Initialization and shutdown of components

    # Returns framework context
    def initialize_framework(self):
        return None


    def shutdown_framework(self, framework_context):
        return framework_context


    # Returns subject context
    def initialize_subject(self, submission, framework_context):
        return submission


    def shutdown_subject(self, subject_context):
        return subject_context


    # Returns test set context
    def initialize_test_set(self, test_set, subject_context, framework_context):
        return test_set


    def shutdown_test_set(self, test_set_context):
        return test_set_context



# Test Set (Subsection of Test Suite)
class TestSet:
    def __init__(self, name, id, num_tests, test_function, **keywords):
        self._name = name
        self._id = id

        # Assign the test count function. If it isn't valid, throw an exception.
        if isinstance(num_tests, int):
            self.get_num_tests = lambda *args, **kwargs: num_tests
        elif callable(num_tests):
            if len(inspect.getfullargspec(num_tests).args) == len(inspect.getfullargspec(TestSet.__num_tests_template).args):
               self.get_num_tests = num_tests
            else:
                raise Exception("Test count function has wrong number of paramters")
        else:
            raise Exception("Test count is invalid type (must be callable or integer)")

        # Assign the test run function. If it isn't valid, throw an exception.
        if callable(test_function):
            if len(inspect.getfullargspec(test_function).args) == len(inspect.getfullargspec(TestSet.__run_test_template).args):
                self.run_case_test = test_function
            else:
                raise Exception("Test run function has wrong number of paramters")
        else:
            raise Exception("Test run function is not callable")

        # Grab optional keyword argument values
        self._max_score = keywords.pop("max_score", 100.0)
        self._max_penalty = keywords.pop("max_penalty", 0.0)
        self.get_test_desc = keywords.pop("test_desc", TestSet.__get_test_description)

        # Initialize penalty lists
        self._case_penalties = []
        self._set_penalties = []
        #self.project_penalties = [ ("Time", 0.3) ]
        #self.test_case_penalties = [ ("Leaks", 0.3), ("Memory", 0.3) ]
        #self.max_penalty = 0.3
        #self._max_penalty = keywords.pop("max_penalty", 0.0)
        #self._set_penalties = keywords.pop("set_penalties", [])
        #self._case_penalties = keywords.pop("case_penalties", [])


    @property
    def name(self):
        return self._name


    @property
    def id(self):
        return self._id


    @property
    def num_tests(self):
        return self._num_tests


    @property
    def max_score(self):
        return self._max_score


    @property
    def case_penalties(self):
        return self._case_penalties


    @property
    def set_penalties(self):
        return self._set_penalties


    @property
    def max_penalty(self):
        return self._max_penalty


    @staticmethod
    def __num_tests_template(set_context, subject, framework, cfg):
        raise Exception("Template function should never be called!")


    @staticmethod
    def __run_test_template(test_num, set_context, subject, framework, cfg):
        raise Exception("Template function should never be called!")
        pass


    @staticmethod
    def __get_test_description(test_num, *arg_list, **keywords):
        return "Test #%d" % test_num


        #self.project_penalties = [ ("Time", 0.3) ]
        #self.test_case_penalties = [ ("Leaks", 0.3), ("Memory", 0.3) ]
    def add_case_penalty(self, name, fraction, function):
        if fraction and function:
            self._case_penalties.append((name, fraction, function))


    def add_set_penalty(self, name, fraction, function):
        if fraction and function:
            self._set_penalties.append((name, fraction, function))
