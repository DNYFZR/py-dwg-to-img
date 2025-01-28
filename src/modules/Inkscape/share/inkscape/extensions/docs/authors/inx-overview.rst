INX extension descriptor format
===============================


.. highlight:: xml

Introduction
------------

In order for Inkscape to make use of an external script or program, you
must describe that script to inkscape using an INX file. The INX file is
an XML file with Inkscape-specific content that can be edited in a
plain-text editor.

The INX file allows the author to:

-  Specify what type of extension it is, for example input, output, or
   effect
-  Identify :ref:`which interpreter <supported_interpreters>` should be used to run the extension
-  List dependencies; files or other extensions required for operation
-  Define parameters that can be set in the extension
-  Create :ref:`a GUI with control widgets <inx-widgets>` for those parameters
-  Add a submenu to the Extensions menu for the extension to reside in
-  Label strings for translation

Nothing beats a working example, and Inkscape includes a great number of
extensions with INX files that you can read. To find the location of
your Inkscape extensions directory, where included extensions and their
INX files are located, look in the System pane of Inkscape Preferences,
under "Inkscape extensions".

.. _translation_of_extensions:



Extension types
---------------

``<effect>`` extensions
^^^^^^^^^^^^^^^^^^^^^^^

**Corresponding inkex class:** :class:`~inkex.extensions.EffectExtension`

Effect extensions are given an SVG file on stdin and are expected to return a
modified SVG file on stdout. Any additional messages to be displayed to the user
can be passed on stderr. 

XML Attributes
``````````````

+---------------------------+-------------------------+
| Attribute name            | Allowed values          |
+===========================+=========================+
| ``implements-custom-gui`` | ``"true"`` |            |
|                           | ``"false"`` (default)   |
| .. versionadded:: 1.0     |                         |
+---------------------------+-------------------------+
| If set to ``true`` **requires** an effect           |
| extension to implement custom GUI.                  |
|                                                     |
| .. hint::                                           |
|    *Implementation detail:* The "extension is       |
|    working" window is not shown for this kind of    |
|    extensions. This means user interaction with the |
|    Inkscape interface is blocked until the          |
|    extension returns, with no way for the user to   |
|    abort the running extension! It is therefore     |
|    **absolutely essential** that your extension     |
|    provides the necessary visual feedback for the   |
|    user and has proper error handling, to rule out  |
|    any dead-locking behavior. It is also assumed    |
|    that the extension displays any content written  |
|    to stderr on its own (see ``show-stderr`` to     |
|    change this behavior).                           |
+---------------------------+-------------------------+
| ``show-stderr``           | ``"true"`` |            |
|                           | ``"false"`` (default)   |
| .. versionadded:: 1.4     |                         |
+---------------------------+-------------------------+
| Only evaluated for extensions which implement a     |
| custom gui. If set to ``true`` Inkscape will        |
| display any content written to stderr in a dialog   |
| after the extension is closed or has crashed.       |
+---------------------------+-------------------------+
| ``needs-document``        | ``"true"`` (default) |  |
|                           | ``"false"``             |
| .. versionadded:: 1.0     |                         |
+---------------------------+-------------------------+
| If set to ``false`` the extension will not be       |
| passed a document nor will a document be read back  |
| ("no-op" effect). This is currently a hack to make  |
| extension manager work and will likely be           |
| removed/replaced in future, so use at your          |
| **own risk**!                                       |
+---------------------------+-------------------------+
| ``needs-live-preview``    | ``"true"`` (default) |  |
|                           | ``"false"``             |
| .. versionadded:: 1.0     |                         |
+---------------------------+-------------------------+
| If set to ``true`` in an effect extension, it will  |
| offer a "Live preview" checkbox in its GUI. When    |
| the user checks that box, it will run the extension |
| in a "preview mode", visually showing the effect of |
| the extension, but not making any changes to the    |
| SVG document, unless the user clicks the Apply      |
| button. While "Live preview" is checked in the GUI, |
| any changes that the user makes to parameters       |
| accessible in the GUI will generate an updated      |
| preview.                                            |
+---------------------------+-------------------------+
| ``refresh-extensions``    | ``"true"``  |           |
|                           | ``"false"`` (default)   |
+---------------------------+-------------------------+
| Reloads the extension list after the current        |
| extension finishes. Useful for bootstrapping        |
| extensions, currently used only by the extensions   |
| manager.                                            |
+---------------------------+-------------------------+

XML Children
````````````

- ``<effects-menu>``: Place of the extension in the menu. Example:

  .. code-block:: xml

    <effects-menu>
      <submenu name="Render">
          <submenu name="Grids"/>
      </submenu>
    </effects-menu>

- ``<menu-tip>Tooltip</menu-tip>``: Tooltip of the extension.
- ``<object-type>type|all</object-type>``: Specify for which selection of SVG
  elements the extension is enabled and can be triggered from within Inkscape.
  
  .. warning::

    This setting currently has no effect, see `inbox#723 <https://gitlab.com/inkscape/inbox/-/issues/723>`_.

  

``<input>`` extensions
^^^^^^^^^^^^^^^^^^^^^^

Input extensions are given an arbitrary file on stdin and are expected to return the 
contents of the file, converted to SVG, on stdout. 
Any additional messages to be displayed to the user can be passed on stderr. 

**Corresponding inkex class:** :class:`~inkex.extensions.InputExtension`

XML Attributes
``````````````

+---------------------------+-------------------------+
| Attribute name            | Allowed values          |
+===========================+=========================+
| ``priority``              | ``<int>`` |             |
|                           | not specified (default) |
| .. versionadded:: 1.3     |                         |
+---------------------------+-------------------------+
| In the Open dialog, the ``priority`` parameter      |
| determines the order of extensions.                 |
| When multiple extensions are registered as          |
| import for a given file extension, the extension    |
| with the lowest priority wins.                      |
| If no priority is specified, sort order is          |
| determined alphabetically.                          |
+---------------------------+-------------------------+
| ``savecopyonly``          | ``"true"`` |            |
|                           | ``"false"`` (default)   |
| .. versionadded:: 1.2     |                         |
+---------------------------+-------------------------+

XML Children
````````````

- ``<extension>.svg</extension>``: the file extension
- ``<mimetype>text/xml+svg</mimetype>``: mime type. Needs to be specified if the 
  extension should be called on clipboard data.
- ``<filetypename>Scalable Vector Graphics (*.svg)</filetypename>``: 
  this string is displayed in the filter of the Open dialog
- ``<filetypetooltip>Additional details</filetypetooltip>``


``<output>`` extensions
^^^^^^^^^^^^^^^^^^^^^^^

Output extensions are given an SVG file on stdin and are expected to return the 
exported representation of the file contents on stdout. 
Any additional messages to be displayed to the user can be passed on stderr. 

**Corresponding inkex class:** :class:`~inkex.extensions.OutputExtension`

XML Attributes
``````````````

+---------------------------+-------------------------+
| Attribute name            | Allowed values          |
+===========================+=========================+
| ``is_exported``           | ``"true"`` |            |
|                           | ``"false"`` (default)   |
| .. versionadded:: 1.2     |                         |
+---------------------------+-------------------------+
| If set to ``true`` in an **output** extensions, the |
| the extension will be available in the export       |
| dialog.                                             |
+---------------------------+-------------------------+
| ``priority``              | ``<int>`` |             |
|                           | not specified (default) |
| .. versionadded:: 1.3     |                         |
+---------------------------+-------------------------+
| In the Save / Save As dialog, the ``priority``      |
| parameter determines the order of extensions.       |
| If no priority is specified, sort order is          |
| determined alphabetically.                          |
+---------------------------+-------------------------+
| ``savecopyonly``          | ``"true"`` |            |
|                           | ``"false"`` (default)   |
| .. versionadded:: 1.2     |                         |
+---------------------------+-------------------------+
| If set to ``true`` in an **output** extension, it   |
| will limit the extension to being available only    |
| in the "Save a Copy" menu.                          |
+---------------------------+-------------------------+

XML Children
````````````

- ``<extension>.sif</extension>``: The file extension
- ``<mimetype>image/sif</mimetype>``: Needs to be specified if the 
  extension should be called when this particular clipboard format is requested.
- ``<filetypename>Synfig Animation (*.sif)</filetypename>``:
  this string is displayed in the filter of the Open dialog
- ``<filetypetooltip>Additional details</filetypetooltip>``
- ``<dataloss>true</dataloss>``: If the conversion to the output format is lossy,
  Inkscape will prompt the user to save the file as SVG on close.

Example
-------

.. code-block:: xml

   <?xml version="1.0" encoding="UTF-8"?>
   <inkscape-extension xmlns="http://www.inkscape.org/namespace/inkscape/extension">
     <name>{Friendly Extension Name}</name>
     <id>{org.domain.sub-domain.extension-name}</id>
     <dependency type="executable" location="[extensions|path|plugins|{location}]">program.ext</dependency>
     <param name="tab" type="notebook">
       <page name="controls" gui-text="Controls">
         <param name="{argumentName}" type="[int|float|string|bool]" min="{number}" max="{number}"
           gui-text="{Friendly Argument Name}">{default value}</param>
       </page>
       <page name="help" gui-text="Help">
         <param name="help_text" type="description">{Friendly Extension Help}</param>
       </page>
     </param>
     <effect>
       <object-type>[all|{element type}]</object-type>
         <effects-menu>
           <submenu name="{Extension Group Name}"/>
         </effects-menu>
     </effect>
     <script>
       <command location="[inx|extensions]" interpreter="[python|perl|ruby|bash|{some other}]">program.ext</command>
     </script>
   </inkscape-extension>

More example INX files are available in the Inkscape distribution, which
takes its files from the `Inkscape Extensions Repository`_.

For a full list of currently supported interpreters, please see 
:ref:`supported_interpreters`.

.. _dtd_xml_schema:

Translation of extensions
-------------------------

Inkscape extensions repository
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When extensions are included in the `Inkscape Extensions Repository`_,
various scripts will scan each INX file for translatable text and
prepare `translation files`_ for others to translate.

Use ``translatable="no"`` to make an item (e.g. a unit name) untranslatable.

Third party extensions
~~~~~~~~~~~~~~~~~~~~~~

Third party extensions can set their own translation files by setting up their own unique
translation domain.

Example::

    <inkscape-extension translationdomain="my_extension" xmlns="http://www.inkscape.org/namespace/inkscape/extension">

Use the `inx.its`_ file from the Inkscape main repo and run
``xgettext my_extension.inx --its=inx.its -o my_extension.pot``. This will generate the pot file,
which you can distribute to translators. Use the .mo files generated from those in a special
structure:

::

    locale/
    ├── ar
    │   └── LC_MESSAGES
    │       └── my_extension.mo
    ├── as
    │   └── LC_MESSAGES
    │       └── my_extension.mo
    ├── az
    │   └── LC_MESSAGES
    │       └── my_extension.mo
    ...

If the files are, for instance, in
``.config/inkscape/extensions/my_extension/locale/<lang>/LC_MESSAGES/my_extension.mo``, then an inx
file at ``.config/inkscape/extensions/my_extension/my_extension.inx`` with the translationdomain
``my_extension`` will be translated in the interface.

The following three locations are recursively searched for "${translationdomain}.mo":

-  the 'locale' directory in the .inx file's folder
-  the 'locale' directory in the "extensions" folder containing the .inx file
-  the system location for gettext catalogs, i.e. where Inkscape's own catalog is located


.. _attributes_description:


DTD XML schema
--------------

.. warning:: This section contains slightly outdated information.

The following XML schema may not fully describe the current INX file
structure. The actual XML schema used is described in the :ref:`next
paragraph <relax_ng_xml_schema>`.

::

    <!ELEMENT inkscape-extension (name, id, dependency*, param*,(input|output|effect),(script|plugin))>
    <!ELEMENT input (extension, mimetype, filetype, filetypetooltip, output_extension?)>
    <!ELEMENT output (extension, mimetype, filetype, filetypetooltip, dataloss?)>
    <!ELEMENT effect (object-type|submenu?)>
    <!ELEMENT script (command, helper_extension*, check*)>
    <!ELEMENT plugin (name)>
    <!ELEMENT name (#PCDATA)>
    <!ELEMENT id (#PCDATA)>
    <!ELEMENT item (#PCDATA)>
    <!ELEMENT option (#PCDATA)>
    <!ELEMENT dependency (#PCDATA)>
    <!ELEMENT param (#PCDATA|page|item|option)*>
    <!ELEMENT page (#PCDATA, param*)>
    <!ELEMENT extension (#PCDATA)>
    <!ELEMENT mimetype (#PCDATA)>
    <!ELEMENT filetype (#PCDATA)>
    <!ELEMENT filetooltip (#PCDATA)>
    <!ELEMENT object-type (#PCDATA)>
    <!ELEMENT command (#PCDATA)>
    <!ELEMENT check (#PCDATA)>
    <!ELEMENT dataloss (#PCDATA)>
    <!ELEMENT helper_extension (#PCDATA)>
    <!ELEMENT output_extension (#PCDATA)>
    <!ELEMENT menu-tip (#PCDATA)>
    
    <!ATTLIST check reldir (absolute|path|extensions|plugins) #REQUIRED>
    <!ATTLIST command reldir (absolute|path|extensions|plugins) #REQUIRED>
    <!ATTLIST command interpreter CDATA #REQUIRED>
    <!ATTLIST dependency type (executable|extension) #REQUIRED>
    <!ATTLIST dependency location (absolute|path|extensions|plugins) #IMPLIED>
    <!ATTLIST dependency description CDATA #IMPLIED>
    <!ATTLIST effect needs-live-preview (true|false) #REQUIRED>
    <!ATTLIST effect implements-custom-gui (true|false) #IMPLIED>
    <!ATTLIST effect needs-document (true|false) #IMPLIED>
    <!ATTLIST page name CDATA #REQUIRED>
    <!ATTLIST page gui-text CDATA #IMPLIED>
    <!ATTLIST param name CDATA #REQUIRED>
    <!ATTLIST param type (int|float|string|bool|notebook|path|optiongroup|color) #REQUIRED>
    <!ATTLIST param min CDATA #IMPLIED>
    <!ATTLIST param max CDATA #IMPLIED>
    <!ATTLIST param max_length CDATA #IMPLIED>
    <!ATTLIST param precision CDATA #IMPLIED>
    <!ATTLIST param gui-text CDATA #IMPLIED>
    <!ATTLIST param gui-tip CDATA #IMPLIED>
    <!ATTLIST param gui-description CDATA #IMPLIED>
    <!ATTLIST param scope CDATA #IMPLIED>
    <!ATTLIST param gui-hidden CDATA #IMPLIED>
    <!ATTLIST param appearance (minimal|) "">
    <!ATTLIST submenu name CDATA #REQUIRED>

.. _relax_ng_xml_schema:

RELAX NG XML schema
-------------------

The XML schema for INX files is available in the `Inkscape extensions
Git repository`_. This is a `RELAX NG schema`_.

.. _see_also:

.. _next paragraph: INX_extension_descriptor_format#RELAX_NG_XML_schema
.. _Inkscape extensions Git repository: https://gitlab.com/inkscape/extensions/-/blob/master/inkex/tester/inkscape.extension.rng
.. _RELAX NG schema: http://www.relaxng.org/
.. _INX Parameters: Extensions:_INX_widgets_and_parameters
.. _ScriptingHOWTO: ScriptingHOWTO

.. _Inkscape Extensions Repository: https://gitlab.com/inkscape/extensions
.. _a GUI with control widgets: Extensions:_INX_widgets_and_parameters
.. _translation files: https://gitlab.com/inkscape/inkscape/-/tree/master/po
.. _inx.its: https://gitlab.com/inkscape/inkscape/-/raw/master/po/its/inx.its
