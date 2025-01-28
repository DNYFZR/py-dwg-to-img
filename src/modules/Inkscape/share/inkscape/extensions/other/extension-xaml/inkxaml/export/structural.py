#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2020-2022 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""SVG -> XAML Converter classes for structural elements 
(<g>, <svg>, <clipPath>)"""

from typing import Union, List, Optional
import inkex

from .config import GLOBAL_SETTINGS
from ..xamlobjects import (
    DrawingGroup,
    Canvas,
    GeometryGroup,
    BaseElement,
    RectangleGeometry,
    Viewbox,
    Geometry,
    KEY_ATTR,
)
from .text import TextElementParser
from .base import BaseParser
from .shapes import (
    RectangleParser,
    EllipseParser,
    LineParser,
    PolygonPolylineParser,
    PathParser,
    NonTextShapeElementParser,
)


class GroupBaseParser(BaseParser):
    """Base Parser for SVG Groups (also <svg>, <symbol> etc)"""

    def __init__(
        self, svgelement: Union[inkex.SvgDocumentElement, inkex.Group], layer=None
    ):
        super().__init__(svgelement)
        self.layer = layer
        self.child_parsers: List[BaseParser] = []
        for child in list(self.element):
            if layer is not None and (
                not isinstance(child, inkex.Group) or not child.get_id() == layer
            ):
                # ignore everything but the specified layer
                continue
            if isinstance(child, inkex.Use):
                # we unlink all clones since XAML doesn't really have a notion of clones
                # (except putting Geometries in ResourceDictionaries, which would only
                # be a very partial clone, without styles and transforms)
                child.style = child.specified_style()
                if child.href is not None:
                    child.href.style = child.href.specified_style()
                    child = child.unlink()
            if isinstance(child, inkex.TextElement):
                # We need to preprocess the text, mainly separating out tspans that do
                # not share the same line height or not simply square flowtexts
                new_elems = TextElementParser.separate_text(child)
                if new_elems:
                    last_elem = child
                    for elem in new_elems:
                        self.child_parsers.append(TextElementParser(elem))
                        last_elem.addnext(elem)
                        last_elem = elem
                    child.getparent().remove(child)
                    continue
            if isinstance(child, inkex.FlowRoot):
                # Pull the position out of the flowregion
                frs = [e for e in child if isinstance(e, inkex.FlowRegion)]
                if (
                    len(frs) == 1
                    and len(frs[0]) == 1
                    and isinstance(frs[0][0], inkex.Rectangle)
                ):
                    child.set("x", frs[0][0].left)
                    child.set("y", frs[0][0].top)
            if isinstance(child, inkex.Rectangle) and GLOBAL_SETTINGS.avalonia:
                if child.rx > 0 or child.ry > 0:
                    self.child_parsers.append(PathParser(child))
                    continue
            if child.__class__ in typemap:
                self.child_parsers.append(typemap[child.__class__](child))

    def parse_children(self, primitive: Union[DrawingGroup, Canvas, GeometryGroup]):
        """Adds the children of a groupbase to a primitive XAML object"""
        # primitive.add_property(KEY_ATTR, self.element.get_id())
        primitive.add_name(self.element.get_id())
        primitive.set_transform(self.element.transform)

        if self.element.specified_style()("display") == "none":
            primitive.set_invisible()
        if not isinstance(primitive, GeometryGroup):
            primitive.add_property(
                "ClipGeometry" if isinstance(primitive, DrawingGroup) else "Clip",
                self.get_clip(primitive),
            )
            primitive.add_property("OpacityMask", self.get_mask(primitive))
            primitive.add_property(
                "Opacity", self.element.specified_style()("opacity"), 1
            )
        blur = self.get_blur()
        # Bitmap effects are supposed to be added in Avalonia 11 or 12
        if GLOBAL_SETTINGS.wpf and blur is not None and isinstance(primitive, Canvas):
            primitive.add_property("Effect", blur)
        for parser in self.child_parsers:
            result: Optional[BaseElement] = None
            if isinstance(primitive, DrawingGroup):
                result = parser.to_xaml_objects()
            elif isinstance(primitive, Canvas):
                result = parser.to_canvas_objects()
            elif isinstance(primitive, GeometryGroup):
                if isinstance(
                    parser, NonTextShapeElementParser
                ):  # can only parse simple elements
                    result = parser.to_clippath()
            primitive.add_child(result)

    def to_xaml_objects(self) -> DrawingGroup:
        parsed = DrawingGroup()
        self.parse_children(parsed)
        return parsed

    def to_canvas_objects(self) -> Canvas:
        parsed = Canvas()
        parsed.add_property("UseLayoutRounding", "False")
        self.parse_children(parsed)
        return parsed


class SvgElementParser(GroupBaseParser):
    """Parse <svg> elements"""

    def __init__(self, svgelement: inkex.SvgDocumentElement, layer=None):
        super().__init__(svgelement, layer)

    def equivalent_transform(self):
        """Get the equivalent transform of an SVG element"""
        return inkex.Transform(
            translate=(
                self.element.unittouu(self.element.get("x", 0)),
                self.element.unittouu(self.element.get("y", 0)),
            )
        )

    def get_equivalent_clip(self) -> Optional[RectangleGeometry]:
        """Get the equivalent clip, i.e. clipped by the viewbox"""
        vbx = self.element.get_viewbox()
        clip_geometry = RectangleGeometry()
        clip_geometry.add_properties(
            {
                "Rect": ",".join(
                    map(
                        str,
                        [
                            vbx[0],
                            vbx[1],
                            self.element.viewbox_width,
                            self.element.viewbox_height,
                        ],
                    )
                )
            }
        )
        return clip_geometry

    def to_xaml_objects(self):
        self.element.transform = self.equivalent_transform() @ self.element.transform
        this = super().to_xaml_objects()

        if (
            GLOBAL_SETTINGS.layers_as_resources
            and self.element == self.element.root
            # The next two checks should already be true as a consequence of the first
            # two, but the correctness of the next operation depends on them
            and (len(this) == 1 and isinstance(this[0], DrawingGroup))
            and all(i in ["ClipGeometry"] for i in this[0].attrib.keys())
        ):
            # When exporting layers as indidual resources, there are two nested groups
            # (one for the SVG including the viewbox, which has the original layer's
            # name, and one for the layer). Iif the layer had no other relevant
            # attributes, in particular no transform, one group can be ommitted.
            if this[0].get("ClipGeometry", None) in [None, ""]:
                # Invisiblity is mocked by setting an empty ClipGeometry; we ignore
                # visibility of toplevel layers in this case.
                this = this[0]
        this.add_property("ClipGeometry", self.get_equivalent_clip())
        self.element.transform = (-self.equivalent_transform()) @ self.element.transform
        return this

    def to_canvas_objects(self):
        self.element.transform = self.equivalent_transform() @ self.element.transform
        this = super().to_canvas_objects()
        if (
            GLOBAL_SETTINGS.layers_as_resources
            and self.element == self.element.root
            # The next two checks should already be true as a consequence of the first
            # two, but the correctness of the next operation depends on them
            and len(this) == 1
            and isinstance(this[0], Canvas)
            # These attributes can be ignored safely.
            and all(
                i in ["UseLayoutRounding", "Visibility", "IsVisible"]
                for i in this[0].attrib.keys()
            )
        ):
            this = this[0]
        this.add_properties(
            {"Width": self.element.viewbox_width, "Height": self.element.viewbox_height}
        )
        this.add_property("Clip", self.get_equivalent_clip())
        result = Viewbox(nsmap=GLOBAL_SETTINGS.TOPLEVEL_DICT.nsmap)
        result.add_property("Stretch", "Uniform")
        result.add_child(this)
        self.element.transform = (-self.equivalent_transform()) @ self.element.transform
        return result


class GroupParser(GroupBaseParser):
    """Parse <g> elements"""

    def __init__(self, svgelement: Union[inkex.Group, inkex.Pattern]):
        super().__init__(svgelement)


class ClipPathParser(GroupBaseParser):
    """Parse a clippath element"""

    def __init__(self, svgelement: inkex.ClipPath):
        super().__init__(svgelement)

    def to_clippath(self) -> Optional[GeometryGroup]:
        """Convert current clippath to XAML"""
        result = GeometryGroup()
        self.parse_children(result)
        result.add_property("FillRule", "Nonzero" if GLOBAL_SETTINGS.wpf else "NonZero")
        return result

    def simplify_clip(self, clippath: GeometryGroup) -> Union[Geometry, str]:
        """Simplify the clip if possible.
        There are a few cases where we can simplify the clip.
        1. The clippath is an empty group: can be expressed as string
        2. Two nested GeometryGroups: Join the inner transforms and copy the clippath,
           if set, from the inner one one level up
        3. The top level geometrygroup has only one child
        """
        # Case 1
        if isinstance(clippath, GeometryGroup) and len(clippath) == 0:
            return ""
        # Case 2
        while len(clippath.getchildren()) == 1 and isinstance(
            clippath[0], GeometryGroup
        ):
            parent_transform = clippath.parse_transform()
            child_transform = clippath[0].parse_transform()
            clippath.set_transform(parent_transform @ child_transform)
            # clippath.add_property("FillRule", clippath[0].get("FillRule", None))
            for child in clippath[0]:
                clippath.append(child)
            clippath.remove(clippath[0])
        # Casse 3
        if len(clippath.getchildren()) == 1 and isinstance(clippath[0], Geometry):
            clippath[0].set(KEY_ATTR, clippath.get(KEY_ATTR, None))
            clippath[0].set("Transform", clippath.get("Transform", None))
            clippath = clippath[0]
        return clippath


typemap = {
    inkex.Group: GroupParser,
    inkex.Layer: GroupParser,
    inkex.SvgDocumentElement: SvgElementParser,
    inkex.PathElement: PathParser,
    inkex.Rectangle: RectangleParser,
    inkex.Circle: EllipseParser,
    inkex.Ellipse: EllipseParser,
    inkex.Polygon: PolygonPolylineParser,
    inkex.Polyline: PolygonPolylineParser,
    inkex.Line: LineParser,
    inkex.TextElement: TextElementParser,
    inkex.FlowRoot: TextElementParser,
}
