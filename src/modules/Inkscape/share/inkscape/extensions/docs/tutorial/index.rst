.. _authors-tutorial:

Tutorial
========

Introduction
------------

Extensions are small programs that extend Inkscape’s functionality. They
can provide features for specific tasks, experimentation, or art styles.
They can also add support for special hardware or different export
formats. While many extensions are included with Inkscape, you can also
install extensions written by third parties or write your own.

This guide aims to provide you with enough information to write your own
extension using the python programming language and a text editor. You
should have the latest version of Inkscape installed. While Inkscape
extensions generally work across platforms, this guide will use Linux as
its default operating system. Linux is not required for writing
extensions, but you may need to modify the location of files on your
computer as you follow along. You may also need to use other “helper”
programs, for example a different text editor, depending on your
operating system.

When a user selects an extension from the menu within Inkscape, Inkscape
opens a pop-up dialog that presents information to the user and/or
allows the user to enter any parameters that are necessary to use the
extension. An extension can also be configured to run immediately
without an intermediate dialog, for example if it does not have any
adjustable parameters. When the user clicks **Apply** in the dialog, the
parameters are passed to the extension program along with the svg file
and a list of selected objects. The extension program itself then runs,
and the data that it returns will be used to update Inkscape’s svg
canvas or to save data to disk.

We’ve made this process easier for you by creating a set of template
extensions which you can download as the starting point for this
tutorial. If you are a beginner we recommend that you start with the
Effect Extension Template. Input, Output and other types of extensions
will be covered in the more advanced topics later.

.. toctree::
   :maxdepth: 1

   my-first-effect-extension
   simple-path-extension
   my-first-text-extension
   my-first-import-extension
   object-editing

