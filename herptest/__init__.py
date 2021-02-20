import os.path
from types import SimpleNamespace

# Test Suite Configuration
class Config:
    def __init__(self, runtime=None, test_sets=None):
        self.build = SimpleNamespace()
        self.general = SimpleNamespace()
        self.runtime = runtime
        self.sets = test_sets

        # Log locations
        self.general.result_path = "Results"
        self.general.result_file = "result.csv"
        self.general.error_log = "error.log"
        self.general.summary_file = "summary.csv"

        # Paths to base files, target source destination, and resources
        self.build.base = None
        self.build.destination = None
        self.build.resources = None

        # Build parameters: source folder (src), build destination (bin)
        self.build.subject_src = "Source/Subject"
        self.build.subject_bin = "Build/Subject"

        self.build.framework_src = None
        self.build.framework_bin = None

        # Build commands: preparing & compiling (additional keys: $source_dir, $build_dir)
        self.build.prep_cmd = []
        self.build.compile_cmd = []


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
        None


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
        self.run_case_test = test_function
        self.get_num_tests = num_tests if callable(num_tests) else lambda *args, **kwargs: num_tests

        self._max_score = keywords.pop("max_score", 100.0)
        self._max_penalty = keywords.pop("max_penalty", 0.0)
        self.get_test_desc = keywords.pop("test_desc", self.__class__.__get_test_description)

        self._case_penalties = []
        self._set_penalties = []
        #self.project_penalties = [ ("Time", 0.3) ]
        #self.test_case_penalties = [ ("Leaks", 0.3), ("Memory", 0.3) ]
        #self.max_penalty = 0.3
        #self._case_penalties = keywords.pop("case_penalties", [])
        #self._set_penalties = keywords.pop("set_penalties", [])
        #self._max_penalty = keywords.pop("max_penalty", 0.0)


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
