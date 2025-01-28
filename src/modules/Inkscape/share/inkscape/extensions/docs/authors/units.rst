.. _units:

Units
=================

If you are reading this page, you are probably confused about how units work in Inkscape, inkex and
SVG in general. This is understandable, since there's quite a bit of conflicting information online.

Units in SVG
------------

SVG means "scalable vector graphics". This introduces an inherent difficulty with how to map units
to the real world. Should units be pixels? Millimeters? Something else? The answer to this depends
on the output format you're targeting.

The authors of the SVG specification solved this problem by introducing an abstract "dimensionless"
unit called **user units**. The SVG1.1 specification [1]_ is quite clear about their definition: 

    *One px unit is defined to be equal to one user unit.
    Thus, a length of "5px" is the same as a length of "5".*

So whenever you read "user unit", think "pixel". And when you encounter a coordinate without unit,
it's specified in user units, i.e. pixels. You might have heard or read something like "I can choose
the unit of a document, so that one user unit equals one millimeter". This statement is misleading, 
although not entirely wrong. It will be explained below.  

An `<svg>` tag has two different properties that influence its size and the mapping of coordinates. 
These are called *viewport coordinate system* and *user coordinate system*. 

And as the name indicates, **user units always refer to the user coordinate system**. So for 
the next section which explains the **viewport coordinate system**, forget user units. 

Viewport coordinate system 
^^^^^^^^^^^^^^^^^^^^^^^^^^

The viewport coordinate system is [2]_

    *[...] a top-level SVG viewport that establishes a mapping between the coordinate system used by the 
    containing environment (for example, CSS pixels in web browsers) and user units.*

The viewport coordinate system is established by the ``width`` and ``height`` attributes of the SVG tag. 
To reformulate the quote above: The viewport tells the SVG viewer how big the visible part of the 
canvas should be *rendered*. It may be ``200px x 100px`` on your screen (``width="200px" height="100px"``)
or ``210mm x 297mm`` (``width="210mm" height="297mm"``), i.e. one A4 page. 

    *If the width or height presentation attributes on the outermost svg element are in user units 
    (i.e., no unit identifier has been provided), then the value is assumed to be equivalent to the 
    same number of "px" units.* [3]_

Expressed in simple terms: if no unit has been specified in the ``width`` or ``height`` attributes,
assume the user means pixels. Otherwise, the unit is converted by the SVG viewer. Inkscape uses a 
DPI of 96 px/in, and corresponding conversions for mm, yd etc. are used. 

Consider the following SVG file:

.. code-block:: XML

    <svg xmlns='http://www.w3.org/2000/svg' width="200" height="100">
        <rect x="0" y="0" width="200" height="100" fill="#aaa"/>
    </svg>

which renders as follows:

.. image:: samples/units1.svg

If your browser zoom is set to 100%, this image should have a size of 100 times 200 pixels, 
and is filled with a grey rectangle. You can verify this by taking a screenshot. 

Likewise, in ``mm`` based documents, you might see code such as
``width="210mm" height="297mm"`` which tells an standard-compliant program that if printed or
exported to PDF, the document should span an entire A4 page. 

User coordinate system 
^^^^^^^^^^^^^^^^^^^^^^^^^^

You may have noticed that we didn't explicitly specify in the above svg that we want to draw 
everything within the area with the coordinates ``0 ≤ x ≤ 200`` and ``0 ≤ y ≤ 100``. This was 
done for us automatically since we specified ``width`` and ``height``. The ``viewBox`` attribute 
allows to change this.

Again from the specification [4]_:

    *The effect of the viewBox attribute is that the user agent automatically supplies the 
    appropriate transformation matrix to map the specified rectangle in user coordinate system 
    to the bounds of a designated region (often, the SVG viewport).*

Let's break this down. Imagine the ``viewBox`` attribute as a camera that moves over the infinite 
canvas. It can zoom in or out and move around - but whatever image the camera outputs, it is 
rendered in the rectangle defined by ``width`` and ``height``, i.e. the viewport. Initially, the 
camera is located such that the region ``viewBox="0 0 width height"`` is pictured. We may
however modify the viewBox as we wish. 

In a ``mm`` based documents, where we specified ``width="210mm" height="297mm"``, the viewbox is
initially ``viewBox="0 0 793.7 1122.5"`` due to the conversion from mm to px. This means that the 
bottom right corner is at ``(210, 297) mm * 1/25.4 in/mm * 96 px/in ≈ (793.7, 1122.5) px``.

As already mentioned: no units means user unit means pixels. So a rectangle with 
``x="793.7" y="1122.5"`` (no units specified) is at the bottom right corner of the page. It would be
nicer if unitless values would be implicitly in millimeters, so we could specify such a rectangle 
with ``x="210" y="297"``. This can be done with the ``viewBox`` attribute and will be explained with
an example SVG.

Let's say we want to design a business card that should eventually be *printed on 84mm x 56mm*, so
we specifiy ``width="84mm" height="56mm"```. We also want the user units to behave like real-world
millimeters, so we have to zoom the viewbox camera: ``viewBox="0 0 84 56"``. As mentioned above,
no units means px, so these attributes together tell the SVG viewer "move the camera in such a way 
that (84, 56) in user units, i.e. px, is the bottom right corner, and scale the image such that when 
printed or rendered it has a size of 84mm by 56mm".

You can imagine this situation like this [5]_:

.. image:: samples/unit_camera.svg

To illustrate this, we draw a crosshair at ``(14, 21)`` (note: no units in the path specification!), 
i.e. a fourth horizontally and vertically for reference. Then we draw three circles: one at 
``(21, 14)``, one at ``(21px, 14px)`` and one at ``(21mm, 14mm)``.

.. code-block:: XML

    <svg xmlns='http://www.w3.org/2000/svg' width="84mm" height="56mm" viewBox="0 0 84 56" fill="none">
        <rect x="0" y="0" width="84" height="56" stroke="orange" stroke-width="2px"/>
        <path d="M 0, 14 H 84" stroke="black" stroke-width="0.2px"/> 
        <path d="M 21, 0 V 56" stroke="black" stroke-width="0.2px"/> 
        <circle id="c1" r="2" cx="21" cy="14" stroke="red" stroke-width="0.5"/>
        <circle id="c2" r="4px" cx="21px" cy="14px" stroke="green" stroke-width="0.5px"/>
        <circle id="c3" r="0.5mm" cx="21mm" cy="14mm" stroke="blue" stroke-width="0.5mm"/>
    </svg>

.. image:: samples/units2.svg

The rendered image at 100% browser resolution should be approximatly ``85mm`` by ``56mm``, but this 
highly depends on your screen resolution. 

Note that the first two circles specified without unit 
(i.e. user units) and specified in px are at the correct position and identical except for radius 
and stroke color. 

The third circle's coordinates, radius and stroke-width are specified in mm. It should be located 
somewhere near the bottom right corner (where exactly depends on the DPI conversion of your browser,
but most browsers use ``96dpi = 96 px/in`` today, which yields a conversion factor of approx. 
``3.77px/mm``). The stroke is thicker by the same factor and the radius has been reduced to be 
comparable to the first circle. 

This is somewhat unintuitive. Didn't we create a mm based document? Now we can explain the 
statement from the introduction
"I can choose the unit of a document, so that one user unit equals one millimeter".
We didn't change the core statement "no unit = user unit = pixels" by specifying width and
height in mm. But the special choice of the viewbox attribute - the same width and height, but 
without the unit) makes the following statement true: "**One user unit looks like one millimeter on 
the output device** (e.g. screen or paper)". 

Now you understand why appending "mm" to the circle's position moved it. The transformation px->mm 
has been applied twice! Once in the coordinate specification itself, and once by the "camera".


Units in Inkex
-----------------

As an extension autor, you may have four different questions regarding units. 

What is the position of this object [in the user coordinate system]?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a question that typically needs to be answered if you want to position an object relative
to other objects, whose coordinates may be specified in a different unit.

The most convenient way to deal with this is to get rid of the units, and that means converting 
everything to user units. 

Each :class:`BaseElement <inkex.elements._base.BaseElement>` has a method 
:meth:`to_dimensionless <inkex.elements._base.BaseElement.to_dimensionless>`. This method parses a 
``length`` value and returns it, converted to px (user units). 

:meth:`~inkex.elements._base.BaseElement.to_dimensionless` fulfils the following task:
**Convert this string from the XML into a number, while processing the unit.
When using this function on any SVG attribute and replacing the
original value with the result, the output doesn't change visually.**

In these and the following examples, the above "business card" SVG will be used.

>>> svg = inkex.load_svg("docs/samples/units2.svg").getroot()
>>> svg.to_dimensionless(svg.getElementById("c1").get("cx"))
21.0
>>> svg.to_dimensionless(svg.getElementById("c2").get("cx")) 
21.0
>>> svg.to_dimensionless(svg.getElementById("c3").get("cx"))
79.370078

For some classes, e.g. :class:`Rectangle <inkex.elements._polygons.Rectangle>`, convenience
properties are available which do the conversion for you, e.g. 
:attr:`Rectangle.left <inkex.elements._polygons.RectangleBase.left>`. Similarly there are some
properties for circles:

>>> svg.getElementById("c3").center
Vector2d(79.3701, 52.9134)
>>> svg.getElementById("c2").radius
4.0

What is the dimension of an object in a specified unit in the user coordinate system?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also convert from user units to any unit. This is done using 
:meth:`BaseElement.to_dimensional <inkex.elements._base.BaseElement.to_dimensional>`. 

>>> svg.to_dimensional(svg.getElementById("c2").radius, "px")
4.0
>>> svg.to_dimensional(svg.getElementById("c2").radius, "mm") 
1.0583333333333333

What is the dimension of an object on the viewport in arbitrary units?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is useful if you want to draw a property of a shape (for example its area) as text on the
canvas, in a unit specified by the user. The default unit to convert to is px.

The method for this is called :meth:`BaseElement.unit_to_viewport <inkex.elements._base.BaseElement.unit_to_viewport>`.

>>> svg.unit_to_viewport(svg.getElementById("c2").radius)
15.118110236220472
>>> svg.unit_to_viewport(svg.getElementById("c2").radius, "mm") 
4.0
>>> svg.unit_to_viewport("4", "mm")
4.0

In other words, ``unit_to_viewport(value, unit="px")`` answers the following
question: **What does the the width/height widget of the selection
tool (set to** ``unit`` **) show when selecting an element with width**
``value`` **as defined in the SVG?** Consider again 
``<svg width="210mm" viewBox="0 0 105 147.5"><rect width="100" height="100"/></svg>``
, i.e. a "mm-based" document with scale=2. When selecting this rectangle, the rectangle tool 
shows ``viewport_to_unit("100", unit="mm") = 200``, if the rectangle tool is set to mm.

Obviously the element needs to know the viewport of its SVG document for this. This method therefore
does not work if the element is unrooted.


How big does an object have to be to have the specified size on the viewport?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is useful if you want to draw a shape at a given location on the viewport, regardless of
what the user coordinate system is. This is done using
:meth:`BaseElement.viewport_to_unit <inkex.elements._base.BaseElement.viewport_to_unit>`.

>>> svg.viewport_to_unit("4mm", "px")  
4.0
>>> svg.viewport_to_unit("4mm", "mm")  
1.0583333333333333

An example for this would be text elements. In order for text to show up in Inkscape's text
tool as ``9pt``, you have to user

>>> element.style["font-size"] = self.svg.viewport_to_unit("9pt")

Again, this method will raise an error if the element is unrooted.

In other words, ``viewport_to_unit(value, target_unit="px")`` answers the following question: 
**What is the SVG representation of entering** ``value`` **in the width/height widget of the 
selection tool (set to the unit of value)?** Consider 
``<svg width="210mm" viewBox="0 0 105 147.5"><rect width="?" height="?"/></svg>``,
i.e. a "mm-based" SVG with scale=2. When typing ``200`` in the
rectangle tool, set to mm, the XML editor shows ``100`` =
``100px``. That's what ``viewport_to_unit("200mm") = 100`` does.

Note that this is different than
``viewport_to_unit("200", "mm")``, which would be for a rectangle
with a width (in the width/height widget of the rectangle tool) of
200 (px), while writing the width in ``mm`` *in the SVG*:
``<rect width="7.00043mm" height="7.00043mm"/>``.

Document dimensions
^^^^^^^^^^^^^^^^^^^^^^^^

* :attr:`SvgDocumentElement.viewport_width <inkex.elements._svg.SvgDocumentElement.viewport_width>`
  and  
  :attr:`SvgDocumentElement.viewport_height <inkex.elements._svg.SvgDocumentElement.viewport_height>`
  are the width and height of the viewport coordinate system, i.e. the "output screen" of the 
  viewBox camera, in pixels. In above example: ``(317.480314, 211.653543)``

.. code-block: 
    84mm          *   96px/in / (25.4mm/in) = 317.480314
    [output size]     [resolution 96dpi]      [output size in pixels]

* :attr:`SvgDocumentElement.viewbox_width <inkex.elements._svg.SvgDocumentElement.viewbox_height>`
  and  
  :attr:`SvgDocumentElement.viewbox_height <inkex.elements._svg.SvgDocumentElement.viewbox_height>`
  are the width and height of the user coordinate system, i.e. for a viewport without offset, the 
  largest ``x`` and ``y`` values that are visible to the viewport camera.
  In above example: ``(84, 56)``

Conversion between arbitrary units
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The functions listed above are methods of :class:`BaseElement <inkex.elements._base.BaseElement>`
because they use properties of the root SVG. For an unrooted SVG fragment, 
:meth:`BaseElement.to_dimensionless <inkex.elements._base.BaseElement.to_dimensionless>`. 
:meth:`BaseElement.to_dimensional <inkex.elements._base.BaseElement.to_dimensional>` work as well.

If you want to convert between arbitrary units, you can do so using the 
:meth:`convert_unit <inkex.units.convert_units>` method:

>>> inkex.units.convert_unit("4mm", "px")  
15.118110236220472


Note that inkex doesn't support relative units (percentage, `em` and `ex`) yet. You will have to
implement these yourself if you want your extension to support them. 

.. [1] https://www.w3.org/TR/SVG11/coords.html#Units
.. [2] https://www.w3.org/TR/SVG2/coords.html#Introduction
.. [3] https://www.w3.org/TR/SVG2/coords.html#ViewportSpace
.. [4] https://www.w3.org/TR/SVG2/coords.html#ViewBoxAttribute
.. [5] Note that this drawing has ``width="100%" height="" viewBox="0 0 88.540985 36.87265"``. 
       This instructs the viewer that the SVG should span the entire width of the containing 
       element (in this case, an HTML div) and the height should be chosen such that the image
       is scaled proportionally. Inkex doesn't support these relative units and these don't really
       make sense in standalone SVGs anyway.