Submitting and reviewing extensions
===================================

This page details how extensions can be submitted to and moderated on
the Inkscape website.

I want to submit my extension
-----------------------------

Go through each of these actions and check to make sure your extension
is ready to be made available in Inkscape:

#. Check for limitations

   * Your extension must not contact the internet (unless exempted for a good reason)
   * It must not self-update, or edit files in the config directory.
   * It must be readable code, in English. Code in other languages or too obscure may not be accepted.

#. Check the license of your code

   * Your code must be Free and Open Source. Using one of the available licenses such 
     as GPL, AGPL, MIT, Apache2 etc.
   * Every included dependency must be also Free and Open Source.

#. Check all of your dependencies

   * Your extension MUST be python based (except for template extensions)
   * It MUST work with python 3.8 or later
   * Any dependency not shipped with Inkscape MUST be packaged along side your
     extension. For example jinja2 would be included in a folder.

#. Create a zip file of your extension and any external depdencies.

   * Include only one copy in the root of the zip file.
   * No specific versions for windows or linux, macOS.

#. Check which versions of Inkscape it works with (each one, make a note for tagging 
   later)

   * set the variable "INKSCAPE_PROFILE_DIR=/tmp/folder"
   * run the inkscape version
   * open the extensions manager
   * install the zip file you hope to submit (second tab, folder button at the bottom)
   * Your extension MUST work with at least one version of Inkscape.

#. Sign your zip file

   * Use GnuPG to sign your zip file, use the same signature as the public key you 
     uploaded to inkscape.org
   * OR use md5hash to create a less secure md5 signature of the zip file. Make sure 
     you have some text in your inkscape.org gnupg key profile setting so you see the 
     signature field when uploading.

#. Upload the zip file to the extensions category in the website.

   * Include the generated signature
   * Title and description in English with as much detail as possible
   * Add Inkscape versions as you tested above.
   * Include a link to the Git repository.
   * Include an icon and screenshot file.

#. Send a message to the Inkscape extensions team on `RocketChat`_ asking for a review.

.. _RocketChat: https://chat.inkscape.org/channel/inkscape_extensions

I want to review a submission
-----------------------------

Extensions Reviewer Checklist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  ☐ Take next popular extension [#]_ or request to review
-  ☐ Check for existing verification signature
-  ☐ Contact author to inform about review
-  ☐ Unpack zip to extensions folder
-  ☐ Check zip contents for inx and py file
-  ☐ Check for license header and/or file
-  ☐ Run pytest and record test coverage
-  ☐ Run pylint to get code quality score
-  ☐ Visually confirm no mallicious or internet code
-  ☐ If no tests, add simple test upstream [#]_
-  ☐ Install zip using extensions manager
-  If everything is correct …
-  ☐ Add version tags and any other tags
-  ☐ Edit description, title, logos to improve presentation
-  ☐ contact a website administrator to complete

If everything is correct (must be admin):
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-  ☐ Add testing and quality scores to decription
-  ☐ Generate signature key and upload
-  ☐ Generate md5 if package is not self-signed

.. [#] https://inkscape.org/gallery/=extension/

.. [#] Add simple inkex.tester comparision test