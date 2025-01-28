Creating objects
================

Introduction
------------

In this tutorial, we will number the nodes of a path - effectively recreate a simpler
version of the the "Number Nodes" extension. We will create objects (in this case,
circles) and text on the canvas, at a programmatically determined location. 

INX File
--------

We will use two parameters, the font size and whether the circle should be filled or not.
The inx file looks as follows:

.. code:: xml

    <?xml version="1.0" encoding="UTF-8"?>
    <inkscape-extension xmlns="http://www.inkscape.org/namespace/inkscape/extension">
        <name>My Number Nodes</name>
        <id>org.inkscape.tutorial.my_number_nodes</id>
        <param name="fontsize" type="string" gui-text="Font size:">20px</param>
        <param name="filled" type="bool" gui-text="Fill dot">True</param>
        <effect>
            <effects-menu>
                <submenu name="Visualize Path"/>
            </effects-menu>
        </effect>
        <script>
            <command location="inx" interpreter="python">my_number_nodes.py</command>
        </script>
    </inkscape-extension>

Boilerplate code
----------------

Create a python file with the following contents:


.. code:: python

    import inkex

    class MyNumberNodes(inkex.EffectExtension):

        def add_arguments(self, pars):
            pars.add_argument("--filled", default=True, type=inkex.Boolean)
            pars.add_argument("--fontsize", default="20px", help="Size of node labels")
        
        def effect(self):
            filtered = self.svg.selection.filter_nonzero(inkex.PathElement)

            for element in filtered:
                self.process(element)

        def process(self, element: inkex.PathElement):
            """Draw the node markers and number for each node"""

Processing a path
-----------------

There are three steps we have to perform:

  - Figure out the locations of the path's nodes.
  - Draw a circle at each node's location.
  - Draw a text next to the circle.

For the first step, we'll use the :attr:`~inkex.Path.end_points` attribute of the 
:class:`inkex.PathElement`'s :attr:`inkex.PathElement.path`. This attribute contains
the end point of all path commands, which are the nodes of the path. (Note that this 
means that the start point of a closed subpath will be marked twice).  
However, before doing this, we have to apply the path's transform - otherwise, we would
get the node coordinates of the untransformed path. Our function therefore starts with:

.. code:: python

    def process(self, element: inkex.PathElement):
        """Draw the node markers and number for each node"""

        # element.transform contains an object-oriented representation of the
        # "transform" SVG attribute
        transformed_path = element.path.transform(element.transform)
        nodes = transformed_path.end_points

Second, we'll create a group and append it after the path. In this group, all newly
created objects will go. We can also use the ``enumerate`` function to loop over the 
nodes - this gives us both the index and the coordinates as looping variables.

.. code:: python

        ...
        g = inkex.Group()
        element.addnext(g)

        for index, node in enumerate(transformed_path.end_points):
        
        ...

Third, onto creating the circles: 

