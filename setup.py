from setuptools import setup

setup(
    name='herptest',
    version='0.9.9.7',
    packages=['herptest',],
    url='https://github.com/cacticouncil/herptest',
    license='GPL 3',
    author='Jeremiah Blanchard',
    author_email='jjb@eng.ufl.edu',
    description='Test suite tools for instructors',
    install_requires=['pexpect>=4.8.0', 'pyte>=0.8.0', 'pathos>=0.2.7', 'easydict>=1.10'],

    entry_points =
    { 'console_scripts':
        [
            'elma = herptest.extract_lms_archive:main',
            'herp = herptest.run_test_suite:main'
        ]
    }
)
