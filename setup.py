from distutils.core import setup

setup(
    name='instructor_testsuite',
    version='0.9.0',
    packages=['instructor_testsuite',],
    url='https://github.com/cacticouncil/testingsuite',
    license='GPL 3',
    author='Jeremiah Blanchard',
    author_email='jjb@eng.ufl.edu',
    description='Test suite tools for instructors',
    install_requires=['zipfile','tempfile', 'glob', 'os', 'shutil', 'argparse', 'sys', 'ctypes']
)
