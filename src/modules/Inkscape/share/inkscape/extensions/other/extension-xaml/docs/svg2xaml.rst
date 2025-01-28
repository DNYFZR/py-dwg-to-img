XAML Export
###########

Inkscape 1.3 comes with a new XAML exporter. Why should you use it over other conversion
tools, such as `SharpVectors <https://github.com/ElinamLLC/SharpVectors>`_, 
`SvgToXaml <https://github.com/BerndK/SvgToXaml>`_ (which uses SharpVectors internally)
or AB4D? 

* It supports high-fidelity conversion to both the high-level representation (Canvas) 
  and the low-level DrawingGroup,
* it allows to target the open-source, cross-platform UI toolkit 
  `Avalonia UI <https://avaloniaui.net/>`_,
* it handles Inkscape semantics, such as layers and swatches and thus generally 
  performs better with Inkscape generated SVGs,
* and it works cross-platform and already comes with Inkscape.

Features 
********

* Switch between DrawingGroup and Canvas export.

  DrawingGroup supports less complex SVG features, but generally has better performance,
  making it suitable for icon dictionaries. Primitives cannot be animated.
  Canvas is more suitable for complex drawings where individual elements should be 
  animated, or user controls be added into the resulting XAML.

* Switch between WPF and `Avalonia UI <https://avaloniaui.net/>`_ XAML. Other
  target frameworks can be added relatively easily, so please open an issue with 
  expected differences. Not all features are supported equally. See the 
  :ref:`list below<SVG support>` for details.

* Version-control friendly through consistent, user-specified indentation level.

* Support for Inkscape-specific SVG extensions, such as:

  * Exporting top-level layers as individual resources, so that you can maintain 
    an icon library in a single SVG file. This option is most useful for 
    DrawingGroup export. For Canvas export, the layers will be added as ``<ViewBox>``es
    to a top-level grid, whose resources contain swatches (see next bullet point).
  * Converting solid-color swatches to resources (and referencing them as 
    ``StaticResource`` or ``DynamicResource``). This allows to define swatches such as 
    'Foreground', 'Background', 'Accent', and themeing your application this way!


.. _SVG support:

State of support for various SVG features
*****************************************

Text
====

.. table:: Text as path

    ==========  ================  ===============  =====================
    WPF Canvas  WPF DrawingGroup  Avalonia Canvas  Avalonia DrawingGroup
    ==========  ================  ===============  =====================
    ✓           ✓                 ✓                ✓
    ==========  ================  ===============  =====================

All targets support converting the text to path beforehand. In this case, it should
be rendered correctly as long as it's rendered correctly in Inkscape.

.. table:: Editable text

    ==========  ================  ===============  =====================
    WPF Canvas  WPF DrawingGroup  Avalonia Canvas  Avalonia DrawingGroup
    ==========  ================  ===============  =====================
    ✓           ✗                 ✗                ✗
    ==========  ================  ===============  =====================

For WPF Canvas, it is possible to convert the text into ``TextBlock`` / ``Tspan`` 
elements.
This supports flowed texts (SVG1.2 and SVG2, as long as the flow region is a rectangle, 
or the text is flowed using ``inline-size``) and font styles (font family, font style, 
font weight, all CSS Level 3 decorations except wavy, which is replaced by a solid line). 
Spacing attributes (kerning, character rotation, dx/dy for tspans) are not supported.

In general, Inkscape-created text will render relatively correct, however the position
on the canvas might be wrong in case of right-to-left or justified text.

``<textPath>`` elements are not supported.

Shapes
======

.. table:: Support for basic shapes

    ==========  ================  ===============  =====================
    WPF Canvas  WPF DrawingGroup  Avalonia Canvas  Avalonia DrawingGroup
    ==========  ================  ===============  =====================
    ✓           ✓                 ✓                ✓
    ==========  ================  ===============  =====================

All SVG shapes, such as ``<path>``, ``<line>``, ``<polyline>``, ``<polygon>``,
``<circle>``, ``<ellipse>`` and ``<rectangle>`` are supported in all target frameworks.

For Avalonia export, rectangles with rounded corners are converted to path. 

Fill and Stroke
===============

Solid colors
------------

Solid fills / strokes are supported, including conversion of solid-color swatches to
resources. ``currentColor`` is not supported. Fallback fills are supported.

Gradients
---------

.. table:: Linear and radial gradients

    +-------------+-------------------+------------------+------------------------+
    | WPF Canvas  | WPF DrawingGroup  | Avalonia Canvas  | Avalonia DrawingGroup  |
    +=============+===================+==================+========================+
    | ✓           | ✓                 | partially; Inkscape-generated gradients   |
    |             |                   | should work                               |
    +-------------+-------------------+------------------+------------------------+

Linear and radial gradients are supported for all shapes. Gradients can be arbitrarily
deeply nested. The ``gradientUnits`` and 
``spreadMethod`` attributes are supported;  ``gradientTransform`` is supported for WPF
(support will be added in Avalonia 11.0).

For Avalonia, ``gradientUnits="objectBoundingBox"`` is not well supported, but Inkscape
doesn't create such gradients. The radius of spherical gradients might differ slightly.

Mesh gradients are not supported.

Patterns
--------
.. table:: Patterns

    +-------------+-------------------+------------------+------------------------+
    | WPF Canvas  | WPF DrawingGroup  | Avalonia Canvas  | Avalonia DrawingGroup  |
    +=============+===================+==================+========================+
    | ✓           | ✓                 | partially; only work well if no the       |
    |             |                   | ``patternTransform`` attribute is unset   |
    +-------------+-------------------+------------------+------------------------+

Patterns are converted to ``VisualBrush`` / ``DrawingBrush`` for WPF 
Canvas/DrawingGroup, respectively; Avalonia only supports ``VisualBrush``, which leads
to the unfortunate situation of high-level elements embedded in low-level drawings, but
it works. Patterns can also be nested.

``patternTransform`` is supported for WPF, but not for Avalonia (will be added in 11.0).

``viewBox``, ``width`` / ``height`` / ``x`` / ``y`` are supported.

``patternUnits="userSpaceOnUse"`` (as true for Inkscape patterns) generally yields better
results; ``patternUnits="objectBoundingBox"`` is be fully supported for WPF.

Markers
-------

.. table:: Markers and paint order

    ==========  ================  ===============  =====================
    WPF Canvas  WPF DrawingGroup  Avalonia Canvas  Avalonia DrawingGroup
    ==========  ================  ===============  =====================
    ✓           ✓                 ✓                ✓
    ==========  ================  ===============  =====================

Markers are supported for all targets. They are emulated by adding the shape to a 
container, and placing a marker in this group for each node where a marker should be 
placed. Automatic orientation and ``overflow`` is supported.

Paint order
-----------

Paint order is supported for all targets. If required, fill and stroke are split into
two otherwise identical objects, which are added into a container, markers either
before, between or after them.

Stroke attributes
-----------------

``stroke-width``, ``stroke-linejoin``, ``stroke-linecap``, ``stroke-dasharray`` are 
supported. Zero-length subpaths are correctly rendered.

``stroke-dashoffset`` is not supported as there is no equivalent in XAML.

``stroke-miterlimit`` is not supported, as this attribute  works differently in XAML 
than in SVG. In SVG `(SVG documentation) <https://www.w3.org/TR/SVG2/painting.html#StrokeMiterlimitProperty>`_,
when the miter length at a node surpasses miter-limit and ``stroke-linejoin="miter"``, 
the node falls back to ``bevel``. 
In XAML `(WPF documentation) <https://docs.microsoft.com/dotnet/api/system.windows.media.pen.miterlimit>`_,
every node is clipped at miter-length in a somewhat weird angle. One can
fix the rendering of these nodes by setting miter-limit=1, which basically
sets the path back to ``bevel``, but this unfortunately affects every node,
making the node-style ``miter`` useless. All known converters have this
problem. 

Filters
-------

Only spherical ``feGaussianBlur`` is supported.

Clips and masks
===============

.. table:: Clips and masks

  +-------+-----------------+-------------------+------------------+------------------------+
  |       | WPF Canvas      | WPF DrawingGroup  | Avalonia Canvas  | Avalonia DrawingGroup  |
  +=======+=================+===================+==================+========================+
  | clip  |          mostly correct, complex clips might have different rendering           |
  +-------+---------------------------------------------------------------------------------+
  | mask  |             partially, colored masks are not supported                          |
  +-------+-----------------+-------------------+------------------+------------------------+


Clips and masks are supported. 

Clips are set via ``Clip`` resp. ``ClipGeometry``. ``clipPathUnits`` is supported.
For very complex clip-paths that make use of ``clip-rule="even-odd"``, the results can
be incorrect, as there is no equivalent XAML representation. The clip is simplified
as much as possible.

Masks are set via ``OpacityMask`` and a ``VisualBrush`` / ``DrawingBrush`` inside. 
The conversion via the ``feColorMatrix`` filter does not take place; the rendering
are therefore incorrect for colored masks. The results in WPF are generally better due 
to the existence of the transform attribute for Brushes.

Child SVG elements
==================

Child SVG elements are supported, including their equivalent clipping path.

Symbols and clones
==================

Symbols and clones are supported; they are unlinked before processing.

Images
======

Raster images (and in general ``<image>`` elements) are not supported.

Groups and transforms
=====================

Groups are fully supported; the group structure is preserved. If necessary, objects are
wrapped in groups; i.e. for a non-default paint order, blur and markers as well as for 
a lot of other attributes when targeting DrawingGroup (clip, opacity etc.). 

Transforms are supprted, but flattened into matrix representation.

Other
=====

Object IDs and names are lost, except for top-level resources (layer names, swatch names
and ``sodipodi:docname``). IDs are sanitized. 

The em, ex and % units are not supported, and all unit information is converted to px. 

RDF and metadata are not supported.

CSS styles are supported (generally on a CSS2 level).




