.. _unittests:

Writing unit tests
==================

All Inkscape extensions should come with tests. This package provides you with
the tools needed to create tests and thus ensure that your extension continues
to work with future versions of Inkscape, the "inkex" python modules, and other
python and non-python tools you may use.

Make sure your extension is a python extension and is using the 
:py:mod:`inkex.extensions` base classes. These provide the greatest amount of 
functionality for testing.

You should start by creating a folder in your repository called ``tests`` with
an empty file inside called ``__init__.py`` to turn it into a module folder.

For each of your extensions, you should create a file called
``test_{extension_name}.py`` where the name reflects the name of your extension.

There are three types of tests:

1. Full-process Comparison tests - These are tests which invoke your
    extension with various arguments and attempt to compare the
    output to a known good reference. These are useful for testing
    that your extension would work if it was used in Inkscape.

    Good example of writing comparison tests can be found in the
    Inkscape core repository, each test which inherits from
    the ComparisonMixin class is running comparison tests.

2. Full-process tests that compare only some data in the output - These also invoke
    your extension, but you manually need to write comparisons for the output.
    
    This is useful if the output file contains a lot of data (that could potentially 
    change) and you only want to check correctness of a very specific datum with a 
    particular test.

3. Unit tests - These are individual test functions which call out to
    specific functions within your extension. These are typical
    python unit tests and many good python documents exist
    to describe how to write them well. For examples here you
    can find the tests that test the inkex modules themselves
    to be the most instructive.

When running a test, it will cause a certain fraction of the code within the
extension to execute. This fraction called it's **coverage** and a higher
coverage score indicates that your test is better at exercising the various
options, features, and branches within your code.

.. versionadded:: 1.2
    ``EXPORT_COMPARE`` environment variable

Generating comparison output can be done using the EXPORT_COMPARE environment
variable when calling pytest and comes in 3 modes, the first of which is the
CHECK comparisons mode::

    EXPORT_COMPARE=1 pytest tests/test_my_specific_test.py

This will create files in ``tests/data/refs/*.{ext}`` and these files
should be manually checked to make sure they are correct. Once you are happy
with the output you can re-run the test with the WRITE comparisons mode::

    EXPORT_COMPARE=2 pytest tests/test_my_specific_test.py

Which will create an output file of the right name and then run the test suite
against it. But only if the file doesn't already exist. The final mode is the
OVERWRITE comparisons mode::

    EXPORT_COMPARE=3 pytest tests/test_my_specific_test.py

This is like mode 2, but will over-write any existing files too. This allows
you to update the test compare files.

.. versionadded:: 1.2
    ``NO_MOCK_COMMANDS`` environment variable

If external programs are called, the tester tries to find the call data in the mock
files, located in tests/data/cmd/executable_name. As long as the parameters and input 
files to such a call doesn't change, the mock call filename is stable across operating 
systems. If mock files are missing, they can be generated with the NO_MOCK_COMMANDS 
variable.

    NO_MOCK_COMMANDS=1 pytest tests/test_my_specific_test.py

If mock files are requested but not found, regenerate them and print the generated 
filename to stderr (so you know which file was generated). Typically, the test then 
fails due to "Extra print statements detected". Rename the file and re-run the test.
This is mode you should be using to generate mock files.

    NO_MOCK_COMMANDS=2 pytest tests/test_my_specific_test.py

Ignore existing mock data and actually call commands, and save all resulting mock files
as``*.msg.output`` files. The comparison mechanism governed 
by EXPORT_COMPARE stays in place. This is useful to check e.g. if a different 
version of the executable changes the correctness of the extension output.

