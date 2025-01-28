Updating your extension for Inkscape 1.0
========================================

.. warning:: This information is partially outdated.

This is a preliminary and incomplete list of actions to take for
updating Python extensions for Inkscape 1.0:

.. _adjusting_folder_structure:

Adjusting folder structure
--------------------------

For easier extension 'installation' by users and for having a better
overview about the installed extensions, you can now put extensions into
their own subfolders of the ``extensions`` directory. This is optional.

When specifying the command in the .inx file, you can use the new
parameter 'location'.

-  If you set ``location="extensions"`` (de-facto default in 0.92.x), it
   will assume the path is relative to either user or system extensions
   folder.
-  If it's ``location="inx"`` (new and recommended in 1.0), it will
   assume the path is relative to the .inx file location.

An extension that uses the following snippet:

.. code:: xml

   <script>
       <command location="inx" interpreter="python">hello.py</command>
   </script>

can be put into any subfolder in ``extensions`` or into the
``extensions`` folder itself, as long as the file ``hello.py`` is in
that same folder, at the same hierarchy level.

The old parameter ``reldir`` is deprecated. It is recommended to use
Unix style path separators (i.e. ``/``), if your script file is located
in a nested subdirectory (should be a very rare case).

.. _updating_.inx_files:

Updating \*.inx files
---------------------

.. _remove_dependency_listings:

Remove dependency listings
~~~~~~~~~~~~~~~~~~~~~~~~~~

Remove the dependency listings for the following modules:

-  bezmisc.py
-  coloreffect.py
-  cspsubdiv.py
-  cubicsuperpath.py
-  ffgeom.py
-  inkex.py (removal not strictly required)
-  pathmodifier.py
-  simplepath.py
-  simplestyle.py
-  simpletransform.py
-  more?

This change is backwards compatible (as long as the user has a fully
functioning Inkscape installation). Not removing these will result in
the extension not being selectable (disabled and greyed out) in Inkscape
1.0 or higher.

.. _changes_to_parameter_definitions:

Changes to parameter definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are also some updates to the parameter definitions in .inx files.
While these are intended to be backwards compatible to 0.92, you may
wish to review the changes below:

-  **Underscores** in inx parameter tags and attributes for translation
   **can be dropped** entirely. Use ``translatable="no"`` to make an
   item (e.g. a unit name) untranslatable.
-  ``boolean`` can be renamed to ``bool``
-  ``<param type="enum" />`` is deprecated, instead use optiongroups. 
   Remember to rename ``item`` to ``option`` when replacing.
-  In optiongroups ``appearance="minimal"`` is deprecated.

   -  In optiongroups you can now define dropdown selections
      (comboboxes) and radio buttons.
   -  i.e. ``<param type="optiongroup" appearance="combo" />``, or 
      ``<param type="optiongroup" appearance="radio" />``.

-  Choosing files / folders with ``<param type="path" />`` 
   (these return the path as a string to the Python script)
-  Color choosers: make them more compact with
   ``appearance="colorbutton"`` for parameters of type ``color``
-  Multiline text entry fields are available with
   ``appearance="multiline"`` for parameters of type ``string``
-  The following new widgets (static, do not need to be read in by the
   .py file's option parser anymore):

   -  ``label``: (``<label>Some text</label>``), replaces parameters of type
      ``description`` (which never really were parameters in the actual
      sense), optionally with ``appearance="header"``.
   -  ``hbox``/``vbox``: for layouting purposes (allow to pack child
      widgets into horizontally/vertically oriented boxes)
   -  ``<spacer/>`` / ``<separator/>``: which add a variable space or separating line between child
      widgets.
   -  ``<image>my_image.svg</image>``: which allows to display an image in the
      extension UI

See :ref:`inx-widgets` for more details.

Example file with many of the new features:

.. code:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <inkscape-extension xmlns="http://www.inkscape.org/namespace/inkscape/extension">
        <name>Layout Demo</name>
        <id>org.inkscape.test.layout_demo</id>
        <dependency type="executable" location="extensions">pathmodifier.py</dependency>

        <hbox>
            <vbox>
                <label appearance="header">Multiple vboxes packed into an hbox</label>
                <hbox>
                    <vbox>
                        <label>Vertical stack</label>
                        <param name="param_bool" type="bool" gui-text="Boolean">true</param>
                        <param name="param_int" type="int" gui-text="Int:" >12345</param>
                        <param name="param_float" type="float" gui-text="Float:">1.2345</param>
                        <param name="param_color" type="color" appearance="colorbutton" gui-text="Color:">0x12345678</param>
                    </vbox>
                    <spacer />
                    <vbox>
                        <label>Vertical stack with separators</label>
                        <param name="param_string" type="string" gui-text="Single line string:">a string value</param>
                        <separator></separator>
                        <param name="param_string_empty" type="string" gui-text="Empty single line:"></param>
                        <separator></separator>
                        <param name="param_string_multiline" type="string" appearance="multiline" gui-text="Multiline string:">a\nmultiline\nstring\nvalue</param>
                    </vbox>
                    <spacer />
                    <vbox>
                        <label>Vertical stack with spacers</label>
                        <param name="param_file_new" type="path" mode="file_new"  filetypes="png" gui-text="A new file:">my/path/to/file.png</param>
                        <spacer />
                        <param name="param_file" type="path" mode="file" filetypes="png,jpg" gui-text="A file:">my/path/to/file.png</param>
                        <spacer />
                        <param name="param_files" type="path" mode="files" gui-text="Multiple files:">my/path/to/file.png</param>
                        <spacer />
                        
                    </vbox>
                    <spacer />
                    <vbox>
                        <label>Vertical stack with expanding spacer</label>
                        <spacer size="expand"/>
                        <param name="param_folder" type="path" mode="folder" gui-text="A folder:">my/path/</param>
                        <param name="param_folders" type="path" mode="folders" gui-text="Folders:">my/path/to/file.png</param>
                        <param name="param_folder_new" type="path" mode="folder_new" gui-text="A new folder:">my/path/</param>
                    </vbox>
                    <spacer />
                    <vbox>
                    <label appearance="header">An image!</label>
                    <image>ink_icon.svg</image>
                    <spacer />
                    <label appearance="header" indent="1">Indented header</label>
                    <spacer />
                    <label>For details please refer to</label>
                    <label appearance="url" indent="1">https://clickable.url</label>
                    </vbox>
                </hbox>
            </vbox>
        </hbox>

        <effect needs-live-preview="false">
            <object-type>all</object-type>
            <effects-menu>
                <submenu _name="Test"/>
            </effects-menu>
        </effect>
        <script>
            <command reldir="extensions" interpreter="python">do_nothing.py</command>
        </script>
    </inkscape-extension>

.. _updating_.py_files:

Updating \*.py files
--------------------

.. _collecting_the_options_of_the_extension:

Collecting the options of the extension
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Instead of ``inkex.Effect.OptionParser.add_option``, your extension
   should now use ``inkex.Effect.arg_parser.add_argument``.
#. The 'type' option now works with variables instead of strings. Use
   ``int`` instead of ``"int"`` (same for float,...).
#. The 'inkbool' type is now ``inkex.Boolean``.
#. ``action="store"`` can be removed.

These changes are not backwards compatible. The old options will still
work, but are deprecated and should no longer be used when you develop
your extension for Inkscape 1.0 or higher.

.. _replace_specific_functions:

Replace specific functions
~~~~~~~~~~~~~~~~~~~~~~~~~~

When the .inx file is valid and not greyed out (meaning: a dependency is
missing), you can start building the .py file up again.

In the Inkscape extensions refactoring process for Inkscape 1.0, many
inkex functions have been removed, or renamed, or moved, or options have
changed. Wherever possible, Inkscape will try to replace the old
function by the new one, and will give you a deprecation warning, with
instructions what to replace them by.

E.g. ``inkex.Effect.selected`` is replaced by
``inkex.Effect.svg.selected`` - however, most replacements do not follow
this naming scheme translation.

These changes are not backwards compatible.

.. _python_3_python_2_compatibility:

Python 3 / Python 2 compatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. warning:: Starting from Inkscape 1.1, only Python 3 is supported.

Test your extension with both Python 2 and Python 3, if you want it to
work for as many users as possible. With the updated extensions,
Inkscape does no longer require Python 2, so some users will probably be
using Python 3, and may no longer have Python 2 installed on their
system. See `Extension_Interpreters <Extension_Interpreters>`__ for how
to set the Python version for your extension in the preferences file
(for testing).

.. _getting_your_extension_added_to_inkscapes_stock_extensions:

Getting your extension added to Inkscape's stock extensions
-----------------------------------------------------------

Inkscape now has a `separate repository for its Python
extensions <https://gitlab.com/inkscape/extensions>`__, which is
included into Inkscape proper by using a Git submodule.

.. _writing_tests:

Writing tests
~~~~~~~~~~~~~

Previously Inkscape didn't require any unit testing for code. You should
now write test code if you expect your module to be included into the
Inkscape extensions repository and included in the shipped Inkscape
release. In this case, a test suite file should be made in the tests
directory for your extension. It should test each aspect of your
extension and exercise all assumptions.

If you are writing a standalone extension that users will install
themselves, there is no strict requirement for tests. But having them
will greatly improve your code and your ability to upgrade the code
later. You can have tests in your own folders and use the extension's
setup.py as a harness to run them (a setup.py file is also useful for
installing your python code as a non-inkscape related python module,
which might be useful too). See Python documentation for creating
packages.

.. _documenting_your_extension:

Documenting your extension
~~~~~~~~~~~~~~~~~~~~~~~~~~

Docstrings
----------

Include docstrings in your extension, so documentation can be built from
them automatically.

.. _submitting_your_extension_for_inclusion:

Submitting your extension for inclusion
---------------------------------------

Visit https://gitlab.com/inkscape/extensions, fork the repository, and
create a merge request on GitLab.

.. _external_links:

External links
--------------

A script to perform some of the conversion steps automatically has been
contributed: https://gitlab.com/inkscape/extensions/-/issues/380

