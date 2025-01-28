.. _supported_interpreters:

Supported Interpreters
======================

Inkscape Script extensions can use one of the following interpreters:

+----------+------------------+----------------------+------------------+
| Language | Name (in INX     | Name (in             | Default value    |
|          | file)            | preferences.xml)     |                  |
+==========+==================+======================+==================+
| Perl     | "perl"           | "perl-interpreter"   | "perl"           |
|          |                  |                      |                  |
|          |                  |                      | "wperl" (Windows;|
|          |                  |                      | since Inkscape   |
|          |                  |                      | 1.0)             |
+----------+------------------+----------------------+------------------+
| Python   | "python"         | "python-interpreter" | "python"         |
|          |                  |                      |                  |
|          |                  |                      | "pythonw"        |
|          |                  |                      | (Windows)        |
+----------+------------------+----------------------+------------------+
| Ruby     | "ruby"           | "ruby-interpreter"   | "ruby"           |
+----------+------------------+----------------------+------------------+
| Shell    | "shell"          | "shell-interpreter"  | "sh"             |
+----------+------------------+----------------------+------------------+

(Code reference: `src/extension/implementation/script.cpp`_)

.. _src/extension/implementation/script.cpp: https://gitlab.com/inkscape/inkscape/-/blob/master/src/extension/implementation/script.cpp

.. _inx_files:

INX files
---------

Within the INX file, you need to indicate the interpreter which will be
used to execute the script, using the name given in the table above:

Example:

::

   <inkscape-extension xmlns="http://www.inkscape.org/namespace/inkscape/extension">
     ...
     <script>
       <command reldir="extensions" interpreter="python">my_extension.py</command>
     </script>
   </inkscape-extension>

.. _selecting_a_specific_interpreter_version_via_preferences_file:

Selecting a specific interpreter version (via preferences file)
---------------------------------------------------------------

In the preferences.xml file, a user can set a specific executable of the
interpreter that Inkscape should use to execute extensions of a specific
type.

This is especially useful, if the system's default version of the
interpreter is incompatible with the one used by Inkscape's extension
subsystem (e.g. Inkscape extensions that rely on inkex.py will only work
with Python 2 (as of Inkscape 0.92.1), while on some recent Linux
distributions, the default Python version used is Python 3, which
results in errors during execution of extensions).

To change the executable that will be used to run script extensions to a
different value than the default value in the above table, you need to
do the following:

#. quit all running Inkscape processes
#. Open your perferences.xml file with a text editor (find the exact
   location of the file by going to Edit -> Preferences -> System: User
   Preferences)
#. search the group which holds settings for the extension system itself
   and options of various extensions:
   ::

        <group
           id="extensions"
           …
           org.ekips.filter.gears.teeth="24"
           org.ekips.filter.gears.pitch="20"
           org.ekips.filter.gears.angle="20" />

#. Insert a key for the interpreter, for example 'python-interpreter'
   for setting the program that should be used to run python extensions,
   and set the string to the absolute path to the python binary which is
   compatible with Inkscape's current extension scripts (in the example
   below, the path is "/usr/bin/python2.7". It will look different on
   Windows systems.):
   ::

        <group
           id="extensions"
           python-interpreter="/usr/bin/python2.7"
           …
           org.ekips.filter.gears.teeth="24"
           org.ekips.filter.gears.pitch="20"
           org.ekips.filter.gears.angle="20" />

#. Save the preferences file, and launch Inkscape to test the
   extensions.

.. _see_also:

See Also
--------

-  `INX Parameters <INX_Parameters>`__
-  `ScriptingHOWTO <ScriptingHOWTO>`__

`Category:Developer Documentation <Category:Developer_Documentation>`__
`Category:Extensions <Category:Extensions>`__
