.. _first-effect-extension:

My first effect extension
=========================

Resources
---------

-  :download:`Template Files <resources/template_effect.zip>`
-  :download:`Example solution <resources/make_red_extension.zip>`

Introduction
------------
Effect extensions take the svg from Inkscape, modify it in some way and
pass the modified version back to Inkscape to be rendered onto the
canvas. This can be very powerful, allowing everything from randomising
colours to manipulating path elements in external programs.

We are going to write an effect extension that will simply change the fill
any selected object to red.

Step One
---------

Extract the ``Effect Extension Template`` files into a folder on your
computer. You should have two files, one inx file and one python file.
Move or link these files into your extensions directory as you would
when installing extensions manually. This is the directory listed at
``Edit > Preferences > System: User extensions``.

Edit the inx file in a text editor and change the name of the extension
to ``Make Red Extension`` and the id to
``org.inkscape.tutorial.make_red_extension`` by changing these lines near
the top:

.. code:: xml

   <?xml version="1.0" encoding="UTF-8"?>
   <inkscape-extension xmlns="http://www.inkscape.org/namespace/inkscape/extension">
     <name>Make Red Extension</name>
     <id>org.inkscape.tutorial.make_red_extension</id>
       [...]

Toward the end of the .inx file, change the submenu to ``Color``
specify that this extension will be listed in the ``Color`` submenu
under the ``Extensions`` menu:

.. code:: xml

       [...]
       <effect>
           <!--object-type>path</object-type-->
           <effects-menu>
               <submenu name="Color"/>
           </effects-menu>
       </effect>
       [...]

Step Two
---------

Next, open ``my_effect_extension.py`` in your text editor. You can see
this is an inkex extension because it contains a python class that
inherits from ``inkex.EffectExtension``. Change the class name to
``MakeRedExtension``:

.. code:: python

       [...]
       class MakeRedExtension(inkex.EffectExtension):
       [...]

Reflect this change down in the ``__main__`` section of the code by
changing the class name to ``MakeRedExtension`` there:

.. code:: python

   [...]
   if __name__ == '__main__':
       MakeRedExtension().run()

When a standard inkex-based python effect extension is run, it will call
a method called :func:`~inkex.base.InkscapeExtension.effect` on your extension's class. So, most of the
code you need to write will go there. Edit
``my_effect_extension.py``\ 's ``effect()`` method to look like the
following, **being sure that the indentation is correct so that**
``effect()`` **is recognized as a method of the MakeRedExtension class**:

.. code:: python

   for elem in self.svg.selection:
       elem.style['fill'] = 'red'
       elem.style['fill-opacity'] = 1
       elem.style['opacity'] = 1



Code Explanation
~~~~~~~~~~~~~~~~

We want to change the color of all selected objects to red. For this we need to loop 
through each of the selected paths. The first line of :func:`inkex.base.InkscapeExtension.effect` 
does this. The :attr:`~inkex.elements._svg.SvgDocumentElement.selection` attribute of ``self.svg`` 
contains the currently selected objects. 

.. hint::
   ``self.svg`` contains the SVG document in its current state - passed by Inkscape - and
   is already parsed for us, so we don't have to manipulate the XML manually. Instead, inkex offers 
   an  object-oriented interface to all the SVG element types. 

Each element has a ``style`` attribute: it's one of the 
:attr:`~inkex.elements._base.BaseElement.WRAPPED_ATTRS` of each element, so ``elem.style`` is a 
:class:`~inkex.styles.Style` object (you can think of it as a dictionary). And in this dictionary,
we set the value for ``'fill'`` to ``'red'``. We also set the ``'fill-opacity'`` to ``1``, in case
the object was transparent previously. 


Final Step
------------

That’s it! There’s no need to set, save or do anything else as we’ve
modified the style in place. 

Save your python script, and re-launch Inkscape. If inkscape was already
open, close it first. You should find your new extension available in
the ``Effect`` menu.

Draw some shapes in Inkscape. Select some of the shapes and use the extension. 
The fill of all objects should change to red.

