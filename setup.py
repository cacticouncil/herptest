from setuptools import setup

setup(
    name='herptest',
    version='0.9.0',
    packages=['herptest',],
    url='https://github.com/cacticouncil/herptest',
    license='GPL 3',
    author='Jeremiah Blanchard',
    author_email='jjb@eng.ufl.edu',
    description='Test suite tools for instructors',
    install_requires=['zipfile','tempfile', 'glob', 'os', 'shutil', 'argparse', 'sys', 'ctypes']
)
