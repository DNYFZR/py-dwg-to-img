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

"""SVG -> XAML Converter classes for Shapes:
<path>, <ellipse>, <circle>, <rect>, <line>, <polygon>, <polyline>"""


import abc
from typing import Union, Optional, Tuple, List, Dict
import math
import copy

import inkex
from inkex.transforms import Transform
from inkex.bezier import bezierslopeatt

from ..xamlobjects import (
    KEY_ATTR,
    XAMLObject,
    Brush,
    SolidColorBrush,
    LinearGradientBrush,
    RadialGradientBrush,
    GradientStop,
    DrawingBrush,
    Number,
    Shape,
    BaseElement,
    DashStyle,
    Pen,
    Canvas,
    GeometryGroup,
    Geometry,
    GeometryDrawing,
    DrawingGroup,
    Drawing,
    Path,
    PathGeometry,
    Rectangle,
    RectangleGeometry,
    Line,
    LineGeometry,
    Ellipse,
    EllipseGeometry,
)
from .utils import convert_attributes
from .config import GLOBAL_SETTINGS
from .base import BaseParser


class ShapeElementParser(BaseParser, abc.ABC):
    """Parse shapes such as rect, circle ect."""

    def __init__(self, svgelement: inkex.ShapeElement):
        super().__init__(svgelement)
        self.effective_style = self.element.specified_style()

    @staticmethod
    def color_to_xaml_color(color: inkex.Color, premultiply_opacity: Number = 1) -> str:
        """Convert a string to an XAML color"""
        xamlcolor = color.to_rgba()
        xamlcolor[3] = int(xamlcolor[3] * 255 * 1 * premultiply_opacity)
        return "#{3:02x}{0:02x}{1:02x}{2:02x}".format(*xamlcolor)

    def fill_gradient(self, svggrad: inkex.Gradient, brush: Brush, opacity: Number = 1):
        """Fills the properties of a gradient"""
        largest = 0
        for stop in svggrad.stops:
            effective_style = stop.specified_style()
            gdstop = GradientStop()
            gdstop_opacity = (
                1
                if effective_style("stop-opacity") is None
                else float(effective_style("stop-opacity"))
            )
            gdstop_color = effective_style("stop-color")
            gdstop.add_property(
                "Color",
                self.color_to_xaml_color(gdstop_color, gdstop_opacity * opacity),
            )
            # fix https://www.w3.org/TR/SVG2/pservers.html#GradientStops
            stop.offset = min(max(stop.offset, largest, 0), 1)
            gdstop.add_property("Offset", stop.offset)
            largest = stop.offset
            brush.add_child(gdstop)
        convert_attributes(
            svggrad,
            brush,
            [["spreadMethod", "SpreadMethod", ["pad", "reflect", "repeat"]]],
        )
        if not GLOBAL_SETTINGS.avalonia:
            convert_attributes(
                svggrad,
                brush,
                [
                    [
                        "gradientUnits",
                        "MappingMode",
                        {
                            "userSpaceOnUse": "Absolute",
                            "objectBoundingBox": "RelativeToBoundingBox",
                        },
                        "RelativeToBoundingBox",
                        "objectBoundingBox",
                    ]
                ],
            )

        def transformer(number):
            # Relative gradient units are not really well transformed in Avalonia,
            # we try what we can do. See also some back and forth in
            # https://github.com/AvaloniaUI/Avalonia/pull/6522
            if (
                GLOBAL_SETTINGS.avalonia
                and svggrad.get("gradientUnits", "objectBoundingBox")
                == "objectBoundingBox"
            ):
                return str(number * 100) + "%"
            return number

        if isinstance(svggrad, inkex.LinearGradient):
            brush.add_properties(
                {
                    "StartPoint": [
                        transformer(svggrad.x1(self.element.root)),
                        transformer(svggrad.y1(self.element.root)),
                    ],
                    "EndPoint": [
                        transformer(svggrad.x2(self.element.root)),
                        transformer(svggrad.y2(self.element.root)),
                    ],
                }
            )
        elif isinstance(svggrad, inkex.RadialGradient):
            self.fill_radial_gradient(svggrad, brush)
        if GLOBAL_SETTINGS.wpf:
            # Fix this once https://github.com/AvaloniaUI/Avalonia/issues/6343 is
            # released
            brush.set_transform(svggrad.gradientTransform)

    def fill_radial_gradient(self, svggrad, brush):
        """Add the equivalent properties of a radial gradient"""
        r = svggrad.r(self.element.root)
        c = [svggrad.cx(self.element.root), svggrad.cy(self.element.root)]
        focus = [svggrad.fx(self.element.root), svggrad.fy(self.element.root)]
        # check if focal point lies outside of circle
        # (https://www.w3.org/TR/SVG11/pservers.html#RadialGradients)
        dist = math.sqrt((c[0] - focus[0]) ** 2 + (c[1] - focus[1]) ** 2)
        if dist > r:
            # in this case place it on the intersection of the circle and the line
            focus = [
                (focus[0] - c[0]) * r * 1 / dist + c[0],
                (focus[1] - c[1]) * r * 1 / dist + c[1],
            ]
        if GLOBAL_SETTINGS.wpf:
            brush.add_properties({"RadiusX": r, "RadiusY": r})
        else:
            if svggrad.get("gradientUnits", "objectBoundingBox") == "userSpaceOnUse":
                # workaround for https://github.com/AvaloniaUI/Avalonia/issues/3995
                # The smaller side of the bounding box of the untransformed element
                # seems to be the basis for the computation of the drawn radius.
                # So first untransform the element
                temp_transform = self.element.transform
                self.element.transform @= -self.element.transform
                # now read the bounding box
                bbox = self.element.bounding_box()
                self.element.transform = temp_transform
                r /= min(bbox.width, bbox.height)
            brush.add_properties({"Radius": r})
        brush.add_properties({"Center": c, "GradientOrigin": focus})

    def get_swatch(self, value, opacity):
        """Convert a gradient to a swatch; and return the property value
        to be set"""
        stop_style = value.href.stops[0].specified_style()
        color = self.color_to_xaml_color(
            stop_style("stop-color"),
            opacity * stop_style("stop-opacity", 1),
        )
        if GLOBAL_SETTINGS.swatches == "color":
            return color
        key = value.href.get_id()
        if GLOBAL_SETTINGS.TOPLEVEL_DICT.get_child(key) is None:
            res = SolidColorBrush()
            res.add_property("Color", color)
            res.add_property(KEY_ATTR, key)
            GLOBAL_SETTINGS.TOPLEVEL_DICT.insert(0, res)
        if GLOBAL_SETTINGS.TOPLEVEL_DICT.get_child(key) is not None:
            return f"{{{GLOBAL_SETTINGS.swatches} {key}}}"
        # mostly for safety reason in case there was an ID collision
        return color

    def postprocess_1d_gradient(
        self, xaml_parent: XAMLObject, value: inkex.Gradient, parsed: XAMLObject
    ) -> Optional[Union[Brush, str]]:
        """Some gradient postprocessing:
        1) Angle between gradient axis and gradient direction
        2) GradientTransform for Canvas"""
        if (  # Avalonia doesn't support DrawingBrush
            GLOBAL_SETTINGS.wpf
            and isinstance(value, inkex.LinearGradient)
            and value.get("gradientUnits", "objectBoundingBox") == "objectBoundingBox"
            # In this case no workaround is needed.
            and (value.x1() != value.x2() and value.y1() != value.y2())
        ):
            # https://www.w3.org/TR/SVG/pservers.html#LinearGradientElementGradientUnitsAttribute
            drwb = DrawingBrush()
            gmd = GeometryDrawing()
            drwb.add_properties(
                {"Viewbox": "0,0,1,1", "Stretch": "Fill", "Drawing": gmd}
            )
            rectgeom = RectangleGeometry()
            rectgeom.add_property("Rect", "0,0,1,1")
            gmd.add_properties({"Brush": parsed, "Geometry": rectgeom})
            return drwb
        if (
            isinstance(value, (inkex.RadialGradient, inkex.LinearGradient))
            and isinstance(xaml_parent, Shape)
            and xaml_parent is not None
            and value.get("gradientUnits") == "userSpaceOnUse"
            # Remove when https://github.com/AvaloniaUI/Avalonia/issues/6343
            # is released
            and not GLOBAL_SETTINGS.avalonia
        ):
            left = xaml_parent.get("Canvas.Left", None)
            top = xaml_parent.get("Canvas.Top", None)
            if left is not None and top is not None:
                # in a canvas, we have to apply a transform to the gradient
                parsed.set_transform(
                    Transform(translate=(-float(left), -float(top)))
                    @ value.gradientTransform
                )
        return parsed

    def get_brush(
        self, xaml_parent: BaseElement, value=None, opacity=1
    ) -> Optional[Union[Brush, str]]:
        """Adds a brush to xaml_parent. Returns true if the brush can be used, else
        false"""
        if value is None:
            try:
                value = self.effective_style("fill")
            except inkex.ColorError:
                value = inkex.Color("black")
            opacity = self.effective_style("fill-opacity")
        parsed: Brush
        if isinstance(value, (inkex.LinearGradient, inkex.RadialGradient)):
            if isinstance(value, inkex.LinearGradient):
                # We can express the swatch as a Resource if the following properties
                # are fulfilled: the inkscape:swatch attribute is set to solid,
                # the element doesn't have an extra fill-opacity (Inkscape doesn't do
                # that, the opacity slider affects the swatch), and there is exactly
                # one stop (i.e. a solid color)
                if (
                    value.href is not None
                    and value.href.get("inkscape:swatch", "None") == "solid"
                    and len(value.href.stops) == 1
                    and opacity == 1
                ):
                    return self.get_swatch(value, opacity)

                parsed = LinearGradientBrush()
            elif isinstance(value, inkex.RadialGradient):
                parsed = RadialGradientBrush()
            self.fill_gradient(value, parsed, opacity)
            return self.postprocess_1d_gradient(xaml_parent, value, parsed)
        if value is None or value == "none":
            return None
        if isinstance(value, inkex.Pattern):
            parsed = self.get_mask_pattern(xaml_parent, value, opacity)

        else:  # probably a color
            # verbose version, probably won't use
            # parsed = SolidColorBrush()
            # xaml_parent.add_property("Brush", parsed)
            # parsed.add_property("Color", '#{3:02x}{0:02x}{1:02x}{2:02x}'
            # .format(*xamlcolor))
            try:
                return self.color_to_xaml_color(inkex.Color(value), opacity)
            except inkex.colors.ColorError:
                print(f"Invalid color value: {self.effective_style['fill']}")
                return None  # resvg-test a-fill-023
        return parsed

    def dashstyle_from_dasharray(
        self, stroke_dasharray: List[float], append=True
    ) -> Optional[Union[DashStyle, str]]:
        """Generates a dashstyle from a given dasharray. In XAML, the dashstyle is given
        as multiples of the stroke thickness, whereas in SVG it's given in user
        units."""
        width = self.effective_style("stroke-width")
        width = inkex.units.convert_unit(width, "px")
        dsty = DashStyle()
        result = ",".join([str(i / width) for i in stroke_dasharray])
        if append:
            dsty.add_property("Dashes", result)
            return dsty
        return result

    def add_pen(self, xaml_parent: BaseElement) -> Optional[Pen]:
        """Add a pen to xaml_parent based on self.element's style"""
        lowlevel = not isinstance(xaml_parent, Shape)
        parsed: BaseElement = xaml_parent
        if lowlevel:
            parsed = Pen()
        stroke = self.effective_style("stroke")
        stroke_opacity = self.effective_style("stroke-opacity")
        result = self.get_brush(parsed, stroke, stroke_opacity)
        if stroke is None:
            return None
        parsed.add_property("Brush" if lowlevel else "Stroke", result)
        linecap_dict = {"butt": "Flat", "round": "Round", "square": "Square"}
        attribute_converter: List[List]
        attribute_converter = [
            [
                "stroke-linejoin",
                "Join"
                if GLOBAL_SETTINGS.avalonia and GLOBAL_SETTINGS.mode == "canvas"
                else "LineJoin",
                {
                    "miter": "Miter",
                    "miter-clip": "Miter",
                    "bevel": "Bevel",
                    "round": "Round",
                },
                "Miter" if GLOBAL_SETTINGS.wpf else "Bevel",
            ],
            ["stroke-width", "Thickness", lambda s: inkex.units.convert_unit(s, "px")],
        ]
        if GLOBAL_SETTINGS.wpf:
            attribute_converter += [
                ["stroke-linecap", "DashCap", linecap_dict, "Square"],
                ["stroke-linecap", "EndLineCap", linecap_dict, "Flat"],
                ["stroke-linecap", "StartLineCap", linecap_dict, "Flat"],
            ]
        else:
            attribute_converter += [["stroke-linecap", "LineCap", linecap_dict, "Flat"]]
        if not lowlevel:
            for lst in attribute_converter:
                lst[1] = "Stroke" + lst[1]
            attribute_converter += [
                [
                    "stroke-dasharray",
                    "StrokeDashArray",
                    lambda s: self.dashstyle_from_dasharray(s, False),
                ]
            ]
        else:
            attribute_converter += [
                ["stroke-dasharray", "DashStyle", self.dashstyle_from_dasharray]
            ]
        # pylint: enable=line-too-long
        convert_attributes(self.effective_style, parsed, attribute_converter)
        if result is not None and lowlevel and isinstance(parsed, Pen):
            return parsed
        return None


class MarkerMixin(ShapeElementParser):
    """Mixin to handle marker conversion logic. Markers don't exist in XAML, so they
    have to be converted into regular objects"""

    @staticmethod
    def get_angle(prev, cspsegment, nxt) -> float:
        """Get the orientation of a marker based on the previous, current and next
        superpath segment"""
        incoming_angle = None
        outgoing_angle = None
        if prev is not None:
            # for lines, the derivative of the bezier parametric curve is not defined at
            # the end points, so we take the derivative very close to the end points
            # Replace this after oo-paths is done
            incoming_angle = inkex.Vector2d(
                bezierslopeatt(prev[1:] + cspsegment[0:2], 1 - 1e-7)
            )
            incoming_angle /= incoming_angle.length + 1e-15
        if nxt is not None:
            outgoing_angle = inkex.Vector2d(
                bezierslopeatt(cspsegment[1:] + nxt[0:2], 0 + 1e-7)
            )
            outgoing_angle /= outgoing_angle.length + 1e-15
        if incoming_angle is not None and outgoing_angle is not None:
            mean_angle = (incoming_angle + outgoing_angle) / 2
        else:
            mean_angle = incoming_angle or outgoing_angle or inkex.Vector2d(1, 0)
        return math.atan2(mean_angle.y, mean_angle.x) * 180 / math.pi

    def find_markers(self):
        """Compile a list of markers (position, angle, Marker reference)
        from the objects' style and nodes"""
        mst = self.effective_style("marker-start")
        mmid = self.effective_style("marker-mid")
        mend = self.effective_style("marker-end")
        path = self.element.get_path().to_superpath()
        nodelist: List[Tuple[Tuple[float, float], float, inkex.Marker]] = []
        # superpaths are stored as Subpath[Segment[Bezier_in, Point, Bezier_out]]
        for subpath in path:
            for segct, segment in enumerate(subpath):
                point = segment[1]
                prev = None if segct == 0 else subpath[segct - 1]
                nxt = None if segct == len(subpath) - 1 else subpath[segct + 1]
                angle = self.get_angle(prev, segment, nxt)
                nodelist.append((point, angle, mmid))
        if nodelist[0]:
            nodelist[0] = tuple(nodelist[0][0:2] + (mst,))  # type: ignore
            if mst is None:
                nodelist = nodelist[1:]
        if nodelist[-1]:
            nodelist[-1] = tuple(nodelist[-1][0:2] + (mend,))  # type: ignore
            if mend is None:
                nodelist = nodelist[:-1]
        return nodelist

    def get_markers(self, lowlevel=True) -> List[Union[DrawingGroup, Canvas]]:
        """Get the markers of an object"""
        # pylint: disable=too-many-locals
        markers = self.find_markers()
        results = []
        for point, angle, marker in markers:
            if marker is None:
                continue
            orient = marker.get("orient", 0)
            if orient != "auto":
                angle = self.element.unittouu(orient)
            # Construct the equivalent transform of the marker (before the clip)
            trs = inkex.Transform(translate=point)
            trs @= inkex.Transform(rotate=angle)

            if marker.get("markerUnits", "strokeWidth") == "strokeWidth":
                trs @= inkex.Transform(
                    scale=self.element.to_dimensionless(
                        self.effective_style("stroke-width")
                    )
                )
            # compute marker scaling, needed for shifting
            vbx = marker.get_viewbox()
            # 3, really (https://www.w3.org/TR/SVG2/painting.html#MarkerWidthAttribute)
            marker_width = self.element.unittouu(marker.get("markerWidth", 3))
            marker_height = self.element.unittouu(marker.get("markerHeight", 3))
            x_scale = marker_width / vbx[2] if vbx[2] > 0 else 1
            y_scale = marker_height / vbx[3] if vbx[3] > 0 else 1
            # check if aspect ratio is preserved
            par = marker.get("preserveAspectRatio", "xMidYMid")
            alignment = par.split()
            if alignment[0] != "none":
                slc = alignment[1] if len(alignment) > 1 else "meet"
                aspect_scale = (
                    min(x_scale, y_scale) if slc == "meet" else max(x_scale, y_scale)
                )
                x_scale = y_scale = aspect_scale
            trs @= inkex.Transform(
                translate=(
                    -self.element.unittouu(marker.get("refX", 0)) * x_scale,
                    -self.element.unittouu(marker.get("refY", 0)) * y_scale,
                )
            )

            trs @= Transform(scale=(x_scale, y_scale))
            from .structural import GroupParser

            parser = GroupParser(marker)
            result: BaseElement = parser.to_xaml_objects() if lowlevel else parser.to_canvas_objects()  # type: ignore # pylint: disable=line-too-long
            results += [result]

            if marker.specified_style()("overflow", default="hidden") in [
                "hidden",
                "scroll",
            ]:  # Construct a clipping path
                mk_width = vbx[2] * x_scale
                mk_height = vbx[3] * y_scale
                x_offset = 0
                y_offset = 0
                if "xMid" in alignment[0]:
                    x_offset -= (marker_width - mk_width) / 2
                elif "xMax" in alignment[0]:
                    x_offset -= marker_width - mk_width
                if "YMid" in alignment[0]:
                    y_offset -= (marker_height - mk_height) / 2
                elif "YMax" in alignment[0]:
                    y_offset -= marker_height - mk_height
                # specify a clipping rectangle on the marker parent
                clip_geometry = RectangleGeometry()
                clip_geometry.add_property(
                    "Rect",
                    ",".join(
                        map(
                            str,
                            [
                                vbx[0],
                                vbx[1],
                                (x_offset + marker_width) / x_scale,
                                (y_offset + marker_height) / x_scale,
                            ],
                        )
                    ),
                )
                result.add_property(
                    "ClipGeometry" if lowlevel else "Clip", clip_geometry
                )

            result.set_transform(trs)

        return results


class NonTextShapeElementParser(ShapeElementParser):
    """Parser for Shapes which are not text elements"""

    @abc.abstractmethod
    def add_attributes(self, geom: Geometry) -> bool:
        """Add functional attributes such as width, height, pathdata... for Geometry
        representation"""

    @abc.abstractmethod
    def add_canvas_attributes(self, geom: Shape) -> bool:
        """Add functional attributes such as width, height, pathdata... for Shape
        (Canvas) representation"""

    @abc.abstractmethod
    def create_geometry(self):
        """Create the geometry child"""

    @abc.abstractmethod
    def get_canvas_object(self):
        """Create the Canvas object child"""

    def needs_wrapper(self, ignore_clip=False) -> bool:
        """Returns true if the shape requires to be wrapped in a DrawingGroup"""
        if (
            (not ignore_clip and self.element.clip is not None)
            or self.effective_style("opacity") != 1
            or self.effective_style("mask") is not None
            or not self.element.transform == inkex.transforms.Transform()
        ):
            return True
        if any(
            self.effective_style(f"marker-{i}") is not None
            for i in ["start", "mid", "end"]
        ):
            return True
        pto = self.paint_order()
        if pto.index("stroke") < pto.index("fill"):
            return True
        return False

    def paint_order(self) -> List[str]:
        """Get sanitized fill order as list"""
        pto: str = self.effective_style("paint-order")
        split = pto.split()
        if "fill" not in split or "markers" not in split or "stroke" not in split:
            split = ["fill", "stroke", "markers"]
        return split

    def to_xaml_objects(self) -> Optional[Drawing]:
        gdr = GeometryDrawing()
        result = gdr
        geometry = self.create_geometry()
        gdr.add_property("Geometry", geometry)
        res = self.add_attributes(geometry)

        gdr.add_property("Brush", self.get_brush(gdr))
        gdr.add_property("Pen", self.add_pen(gdr))
        if self.needs_wrapper():
            parent = DrawingGroup()
            result = parent
            parent.add_name(self.element.get_id())
            parent.set_transform(self.element.transform)
            parent.add_property("ClipGeometry", self.get_clip(parent))
            parent.add_property(
                "OpacityMask", self.get_mask(parent, self.effective_style("mask"))
            )
            parent.add_property("Opacity", self.effective_style("opacity"), 1)
            pto = self.paint_order()
            constituents: Dict[str, List[XAMLObject]] = {"markers": []}
            if isinstance(self, MarkerMixin):
                constituents[
                    "markers"
                ] = self.get_markers()  # pylint: disable=no-member
            if pto.index("fill") == pto.index("stroke") - 1 or (
                pto.index("fill") < pto.index("stroke") and not constituents["markers"]
            ):  #
                # Either fill stroke markers (default), markers fill stroke, or
                # fill markers stroke, but no markers
                constituents["stroke"] = []
                constituents["fill"] = [gdr]
            else:
                strokechild = copy.deepcopy(gdr)
                strokechild.remove_property("Brush")
                fillchild = copy.deepcopy(gdr)
                fillchild.remove_property("Pen")
                constituents.update({"stroke": [strokechild], "fill": [fillchild]})
            for i in pto:
                parent.add_children(constituents[i])

        else:
            gdr.add_name(self.element.get_id())

        if res is not False:
            return result
        return None

    def to_canvas_objects(self) -> Optional[Shape]:
        this = result = fillobj = paintobj = self.get_canvas_object()
        res = self.add_canvas_attributes(this)
        pto = self.paint_order()
        if (
            any(
                self.effective_style(f"marker-{i}") is not None
                for i in ["start", "mid", "end"]
            )
            and isinstance(self, MarkerMixin)
        ) or pto.index("stroke") < pto.index("fill"):
            constituents: Dict[str, List[XAMLObject]] = {"markers": []}
            if isinstance(self, MarkerMixin):
                # pylint: disable=no-member
                constituents["markers"] = self.get_markers(False)
            if pto.index("fill") == pto.index("stroke") - 1 or (
                pto.index("fill") < pto.index("stroke") and not constituents["markers"]
            ):
                # Either fill stroke markers (default), markers fill stroke, or
                # fill markers stroke, but no markers
                constituents["stroke"] = []
                constituents["fill"] = [fillobj]
            else:
                fillobj = copy.deepcopy(paintobj)
                if isinstance(self, TopLeftObjectParser):
                    # In this case, we need to recompute the paint object without stroke
                    # (coordinates change)
                    fillobj = self.get_canvas_object()
                    stroke = self.effective_style.get("stroke-width", None)
                    self.effective_style["stroke-width"] = 0
                    self.add_canvas_attributes(fillobj)
                    self.effective_style["stroke-width"] = stroke
                constituents.update({"stroke": [paintobj], "fill": [fillobj]})
            if sum(1 if len(i) > 0 else 0 for i in constituents.values()) > 1:
                parent = Canvas()
                for i in pto:
                    parent.add_children(constituents[i])
                result = parent
            # we copy the transform up. This is legal because transforms take the
            # stroke width into account only for rects and ellipses, for which
            # markers are invalid
            result.add_property("RenderTransform", this.get("RenderTransform", None))
            this.remove_property("RenderTransform")
        blur = self.get_blur()
        if GLOBAL_SETTINGS.wpf and blur is not None:
            result.add_property("Effect", blur)
        result.add_property("Clip", self.get_clip(this))
        result.add_property(
            "OpacityMask", self.get_mask(this, self.effective_style("mask"))
        )
        result.add_property("Opacity", self.effective_style("opacity"), 1)
        fillobj.add_property("Fill", self.get_brush(fillobj))
        paintobj.add_property("Pen", self.add_pen(paintobj))
        result.add_name(self.element.get_id())

        if res is not False:
            return result
        return None

    def to_clippath(self) -> Optional[Geometry]:
        """Parse the object into a clippath"""
        gdr = self.create_geometry()
        result = gdr
        if self.needs_wrapper(ignore_clip=True):  # no nested clippaths
            parent = GeometryGroup()
            result = parent
            parent.set_transform(self.element.transform)
            parent.add_name(self.element.get_id())
            parent.add_child(gdr)
        else:
            gdr.add_name(self.element.get_id())
        res = self.add_attributes(gdr)
        if (
            self.effective_style("visibility") == "hidden"
            or self.effective_style("display") == "none"
        ):  # https://www.w3.org/TR/SVG11/masking.html#EstablishingANewClippingPath
            return None
        if res is not False:
            return result
        return None


class PathParser(NonTextShapeElementParser, MarkerMixin):
    """Parser for <path> elements"""

    def __init__(self, svgelement: inkex.PathElement):
        super().__init__(svgelement)

    def create_geometry(self) -> PathGeometry:
        return PathGeometry()

    def get_canvas_object(self):
        return Path()

    def add_attributes(self, geom: Geometry):
        geom.add_property("Figures", str(self.element.path))
        convert_attributes(
            self.effective_style,
            geom,
            [
                [
                    "fill-rule",
                    "FillRule",
                    {
                        "evenodd": "EvenOdd",
                        "nonzero": "Nonzero" if GLOBAL_SETTINGS.wpf else "NonZero",
                    },
                    "EvenOdd",
                ]
            ],
        )
        return geom

    def add_canvas_attributes(self, geom: Shape):
        data = PathGeometry()
        geom.add_property("Data", data)
        geom.set_transform(self.element.transform)
        self.add_attributes(data)

    def to_clippath(self) -> Optional[Geometry]:
        result = super().to_clippath()
        if result is not None:
            convert_attributes(
                self.effective_style,
                result,
                [
                    [
                        "clip-rule",
                        "FillRule",
                        {
                            "evenodd": "EvenOdd",
                            "nonzero": "Nonzero" if GLOBAL_SETTINGS.wpf else "NonZero",
                        },
                        "EvenOdd",
                    ]
                ],
            )
        return result


class PolygonPolylineParser(PathParser):
    """Parser for polygon and polyline elements (not created by Inkscape). They
    are simply converted to paths."""

    def add_attributes(self, geom: Geometry):
        path = str(self.element.get_path())
        geom.add_property("Figures", path)
        return geom


class LineParser(NonTextShapeElementParser, MarkerMixin):
    """Parser for <line> elements"""

    def __init__(self, svgelement: inkex.Line):
        super().__init__(svgelement)

    def create_geometry(self) -> LineGeometry:
        return LineGeometry()

    def get_canvas_object(self):
        return Line()

    def get_xy(self) -> List:
        """Return a list [x1, y1, x2, y2]"""
        return [self.element.x1, self.element.y1, self.element.x2, self.element.y2]

    def add_attributes(self, geom: Geometry):
        x_y = self.get_xy()
        geom.add_properties({"StartPoint": x_y[0:2], "EndPoint": x_y[2:4]})
        return geom

    def add_canvas_attributes(self, geom: Shape):
        geom.add_properties(dict(zip(["X1", "Y1", "X2", "Y2"], self.get_xy())))
        geom.set_transform(self.element.transform)


class TopLeftObjectParser(NonTextShapeElementParser):
    """Parse to elements whose position is defined by Canvas.Left and Canvas.Height"""

    def __init__(self, svgelement: Union[inkex.Rectangle, inkex.Circle]):
        super().__init__(svgelement)

    @abc.abstractmethod
    def topleftwidthheight(self) -> Tuple:
        """Get the top, left, width and height of a shape; taking stroke into account"""

    def add_canvas_attributes(self, geom: Shape):
        stroke = (
            0
            if self.effective_style("stroke") is None
            else self.element.to_dimensionless(self.effective_style("stroke-width"))
        )
        top, left, width, height = self.topleftwidthheight()
        left = left - stroke / 2
        top = top - stroke / 2
        attrs = {
            "Canvas.Left": left,
            "Canvas.Top": top,
            "Width": width + stroke,
            "Height": height + stroke,
        }
        effective_transform = (
            Transform(translate=(-left, -top))
            @ self.element.transform
            @ Transform(translate=(left, top))
        )
        geom.set_transform(effective_transform)
        geom.add_properties(attrs)


class RectangleParser(TopLeftObjectParser):
    """Parse a <rect> element"""

    def __init__(self, svgelement: inkex.Rectangle):
        super().__init__(svgelement)

    def create_geometry(self) -> RectangleGeometry:
        return RectangleGeometry()

    def get_canvas_object(self):
        return Rectangle()

    def topleftwidthheight(self) -> Tuple:
        return (
            self.element.top,
            self.element.left,
            self.element.width,
            self.element.height,
        )

    def add_attributes(self, geom: Geometry):
        geom.add_property(
            "Rect",
            ",".join(
                map(
                    str,
                    [
                        self.element.left,
                        self.element.top,
                        self.element.width,
                        self.element.height,
                    ],
                )
            ),
        )
        if self.element.rx > 0:
            geom.add_property("RadiusX", self.element.rx)
        if self.element.ry > 0:
            geom.add_property("RadiusY", self.element.ry)
        if self.element.width == 0 or self.element.height == 0:
            # lowlevel attributes don't have visibility property. Ignore element
            return False
        return geom

    def add_canvas_attributes(self, geom: Shape):
        if not GLOBAL_SETTINGS.avalonia:
            # This has been added in https://github.com/AvaloniaUI/Avalonia/pull/7914,
            # and will be part of 0.11
            geom.add_properties(
                {"RadiusX": self.element.rx, "RadiusY": self.element.ry}
            )
        super().add_canvas_attributes(geom)
        if self.element.width == 0 or self.element.height == 0:
            geom.set_invisible()


class EllipseParser(TopLeftObjectParser):
    """Parse an <ellipse> or <circle> element"""

    def __init__(self, svgelement: inkex.elements._polygons.EllipseBase):
        super().__init__(svgelement)

    def create_geometry(self) -> EllipseGeometry:
        return EllipseGeometry()

    def get_canvas_object(self):
        return Ellipse()

    def topleftwidthheight(self) -> Tuple:
        return (
            self.element.center[1] - self.element.rxry()[1],
            self.element.center[0] - self.element.rxry()[0],
            2 * self.element.rxry()[0],
            2 * self.element.rxry()[1],
        )

    def add_attributes(self, geom: Geometry):
        attrs = {
            "RadiusX": self.element.rxry()[0],
            "RadiusY": self.element.rxry()[1],
            "Center": ",".join(map(str, self.element.center)),
        }
        geom.add_properties(attrs)
        if self.element.rxry()[0] == 0 or self.element.rxry()[1] == 0:
            # lowlevel attributes don't have visibility property. Ignore element
            return False
        return geom

    def add_canvas_attributes(self, geom: Shape):
        super().add_canvas_attributes(geom)
        if self.element.rxry()[0] == 0 or self.element.rxry()[1] == 0:
            geom.set_invisible()
        return geom
