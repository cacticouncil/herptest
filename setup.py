from setuptools import setup


from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='herptest',
    version='0.9.9.5',
    packages=['herptest',],
    url='https://github.com/RobertKilkenny/herptest_UFSA23',
    license='GPL 3',
    author='Jeremiah Blanchard, Renee Kaynor, Lunafreya Trung Nguyen, Jack, Robert Kilkenny, Tyler Maiello, Emma Andrews, Matthew Baumaister, Matthew McDermott, Gerard Avecilla',
    author_email='jjb@eng.ufl.edu',
    description='Test suite tools for instructors',
    install_requires=[
        'numpy',
        'certifi',
        'chardet',
        'idna',
        'python-dotenv',
        'requests',
        'urllib3',
        'paramiko',
        'vix',
        'virtualbox',
        'pyside2',
        'canvasapi',
        'mosspy',
        'dill',
        'pathos',
        'pexpect',
        'pyte',
	'monkeydict'
    ],
    package_data={'herptest': ['herptest/*.png', 'test_suite_templates/*.py']},

    include_package_data=True,

    entry_points =
    { 'console_scripts':
        [
            'elma = herptest.extract_lms_archive:main',
            'herp = herptest.run_test_suite:main',
            'herp_gui = herptest.gui:main',
            'csv-upload = herptest.grade_csv_uploader:main',
            'herp-canvas = herptest.canvas:main',
            'moss = herptest.run_moss:main'
        ]
    }
)
