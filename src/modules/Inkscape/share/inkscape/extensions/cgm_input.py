#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (c) 2024 jonathan.neuhauser@outlook.com
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Convert CGM files to SVG
"""

from dataclasses import dataclass
import inspect
from inkex.utils import pairwise
import math
from typing import Callable, Dict, List, Optional, Tuple, get_type_hints, Union

import inkex
import cgm_parse
import cgm_enums


class CGMConverterMeta(type):
    """Metaclass so that we can automatically call the methods based
    on their type hint"""

    def __new__(cls, name, bases, class_dict):
        new_class = super().__new__(cls, name, bases, class_dict)

        call_mapping = {}
        for name, method in inspect.getmembers(new_class, predicate=inspect.isfunction):
            hints = get_type_hints(method)
            if name.startswith("on_") and len(hints) == 1:
                type_ = list(hints.values())[0]

                call_mapping[type_] = method

        new_class.call_mapping = call_mapping
        return new_class


@dataclass
class FillAttributes:
    fill: cgm_enums.Colour
    interior_style: cgm_enums.InteriorStyleEnum


@dataclass
class LineAttributes:
    specification_mode: cgm_enums.WidthSpecificationModeEnum
    width: float
    colour: cgm_enums.Colour
    type: cgm_enums.LineTypeEnum
    visibility: cgm_enums.EdgeVisibilityEnum


@dataclass
class TextAttributes:
    colour: cgm_enums.Colour
    character_height: Optional[float]
    fallback_character_height: Optional[float]
    horizontal_alignment: cgm_enums.TextHorizontalAlignmentEnum
    vertical_alignment: cgm_enums.TextVerticalAlignmentEnum
    x_character_up: Optional[float]
    y_character_up: Optional[float]
    x_character_base: Optional[float]
    y_character_base: Optional[float]
    precision: cgm_enums.TextPrecisionEnum
    expansion_ratio: float
    character_spacing: float
    path: cgm_enums.TextPathEnum
    font_index: int


class CGMConverter(metaclass=CGMConverterMeta):
    call_mapping: Dict[type, Callable]

    def __init__(self) -> None:
        self.current_page = None
        self.document = inkex.InputExtension.get_template(width="0", height="0")
        self.svg = self.document.getroot()
        self.color_table: Dict[int, cgm_enums.DirectColour] = {}
        self.vdc_height = 100
        self.font_list: List[str] = ["sans-serif"]
        self.default_replacement: List[cgm_parse.CGMCommand] = []
        self.first_page_origin: Optional[Tuple[float, float]] = None

        pass

    def set_defaults(self) -> None:
        self.edge_attributes = LineAttributes(
            cgm_enums.WidthSpecificationModeEnum.SCALED,
            1.0,
            cgm_enums.DirectColour(0, 0, 0),  # device-dependent fg color
            cgm_enums.LineTypeEnum.SOLID,
            cgm_enums.EdgeVisibilityEnum.OFF,
        )
        self.line_attributes = LineAttributes(
            cgm_enums.WidthSpecificationModeEnum.SCALED,
            1.0,
            cgm_enums.DirectColour(0, 0, 0),  # device-dependent fg color
            cgm_enums.LineTypeEnum.SOLID,
            cgm_enums.EdgeVisibilityEnum.ON,
        )
        self.fill_attributes = FillAttributes(
            cgm_enums.DirectColour(0, 0, 0),  # device-dependent fg color
            interior_style=cgm_enums.InteriorStyleEnum.HOLLOW,
        )
        self.text_attributes = TextAttributes(
            cgm_enums.DirectColour(0, 0, 0),  # device-dependent fg color
            None,
            None,
            cgm_enums.TextHorizontalAlignmentEnum.NORMAL_HORIZONTAL,
            cgm_enums.TextVerticalAlignmentEnum.NORMAL_VERTICAL,
            0,
            None,
            None,
            0,
            cgm_enums.TextPrecisionEnum.STRING,
            1.0,
            0,
            cgm_enums.TextPathEnum.RIGHT,
            1,
        )
        self.current_text: Optional[inkex.TextElement] = None
        first = self.first_page_origin == None
        for cmd in self.default_replacement:
            self.stream(cmd)
        if first:
            # Restore this information if it was overwritten by the default replacement
            self.first_page_origin = None

    def apply_edge(self, elem):
        if self.edge_attributes.visibility == cgm_enums.EdgeVisibilityEnum.ON:
            elem.style.update(
                {
                    "stroke": self.get_colour(self.edge_attributes.colour),
                    "stroke-width": self.edge_attributes.width,
                }
            )
            self.apply_stroke_dasharray(elem, self.edge_attributes.type)

    def apply_line(self, elem):
        elem.style.update(
            {
                "fill": None,
                "stroke": self.get_colour(self.line_attributes.colour),
                "stroke-width": self.line_attributes.width,
            }
        )
        self.apply_stroke_dasharray(elem, self.line_attributes.type)

    def apply_stroke_dasharray(self, elem, stroke_type: cgm_enums.LineTypeEnum):
        if stroke_type == cgm_enums.LineTypeEnum.SOLID:
            return
        elif stroke_type == cgm_enums.LineTypeEnum.DASH:
            array = [3, 3]
        elif stroke_type == cgm_enums.LineTypeEnum.DOT:
            array = [1, 1]
        elif stroke_type == cgm_enums.LineTypeEnum.DASH_DOT:
            array = [4, 2, 1, 2]
        elif stroke_type == cgm_enums.LineTypeEnum.DASH_DOT_DOT:
            array = [4, 2, 1, 2, 1, 2]
        else:
            return  # private value
        elem.style["stroke-dasharray"] = [
            i * float(elem.style["stroke-width"]) for i in array
        ]

    def get_colour(self, colour: cgm_enums.Colour):
        if isinstance(colour, cgm_enums.IndexColour):
            colour = self.color_table.get(
                colour.index,
                cgm_enums.DirectColour(255, 255, 255)
                if colour.index == 0
                else cgm_enums.DirectColour(0, 0, 0),
            )
        if isinstance(colour, cgm_enums.DirectColour):
            if colour.colour_model == cgm_enums.ColourModelEnum.RGB:
                return inkex.Color([colour.v1, colour.v2, colour.v3])
            else:
                inkex.errormsg(f"Color model {colour.colour_model} not implemented")

    def apply_fill(self, elem):
        fill = None
        if self.fill_attributes.interior_style == cgm_enums.InteriorStyleEnum.HOLLOW:
            fill = None
        elif self.fill_attributes.interior_style == cgm_enums.InteriorStyleEnum.SOLID:
            fill = self.get_colour(self.fill_attributes.fill)
        elem.style.update({"fill-rule": "evenodd", "fill": fill})

    def on_begin_picture(self, arg: cgm_parse.BeginPicture):
        self.current_page = self.svg.namedview.add(inkex.Page())
        assert self.current_page is not None
        self.current_page.set("inkscape:label", str(arg.name))
        self.current_layer: inkex.Layer = self.svg.add(inkex.Layer())

        self.set_defaults()

    def on_vdc_extent(self, arg: cgm_parse.VDCExtent):
        first_page = False
        if self.first_page_origin is None:
            self.first_page_origin = arg.first_corner.x, arg.first_corner.y
            first_page = True

        x, y, width, height = (
            arg.first_corner.x - self.first_page_origin[0],
            arg.first_corner.y - self.first_page_origin[1],
            abs(arg.second_corner.x - arg.first_corner.x),
            abs(arg.second_corner.y - arg.first_corner.y),
        )
        assert self.current_page is not None

        self.current_page.set("x", x)
        self.current_page.set("y", y)
        self.current_page.set("width", width)
        self.current_page.set("height", height)
        self.svg.set("width", width)
        self.svg.set("height", height)
        # x1 = x * matrix.a + y * matrix.b + matrix.e,
        # y1 = x * matrix.c + y * matrix.d + matrix.f;

        # We need a transform so that VDC Extent  p1 is the bottom left of the page
        # and VDC Extent p2 is the bottom right of the page

        a = (width) / (arg.second_corner.x - arg.first_corner.x)
        d = (height) / (arg.first_corner.y - arg.second_corner.y)
        e = x - arg.first_corner.x * a
        f = y - arg.second_corner.y * d

        trans = inkex.Transform((a, 0, 0, d, e, f))
        assert (
            trans.apply_to_point(arg.first_corner.x + arg.first_corner.y * 1j)
            == x + (y + height) * 1j
        )
        assert (
            trans.apply_to_point(arg.second_corner.x + arg.second_corner.y * 1j)
            == (x + width) + (y) * 1j
        )

        self.current_layer.transform = trans
        if first_page:
            # only for first page
            self.svg.set("viewBox", f"0 0 {width} {height}")
        self.vdc_height = height
        pass

    def on_rectangle(self, arg: cgm_parse.Rectangle):
        rect = self.current_layer.add(
            inkex.Rectangle.new(
                arg.p1.x, arg.p1.y, arg.p2.x - arg.p1.x, arg.p2.y - arg.p1.y
            )
        )
        self.apply_fill(rect)
        self.apply_edge(rect)

    def on_circle(self, arg: cgm_parse.Circle):
        circle = self.current_layer.add(
            inkex.Circle.new((arg.center.x, arg.center.y), arg.radius)
        )
        self.apply_fill(circle)
        self.apply_edge(circle)

    def on_ellipse(self, arg: cgm_parse.Ellipse):
        ellipse = inkex.Ellipse.new((0, 0), (1, 1))

        ellipse.transform = inkex.Transform(
            (
                arg.point_1.x - arg.center.x,
                arg.point_1.y - arg.center.y,
                arg.point_2.x - arg.center.x,
                arg.point_2.y - arg.center.y,
                arg.center.x,
                arg.center.y,
            )
        )
        assert (
            ellipse.transform.apply_to_point(1) == arg.point_1.x + (arg.point_1.y) * 1j
        )
        assert (
            ellipse.transform.apply_to_point(1j) == arg.point_2.x + (arg.point_2.y) * 1j
        )
        pel: inkex.PathElement = self.current_layer.add(ellipse.to_path_element())
        pel.apply_transform()
        self.apply_fill(pel)
        self.apply_edge(pel)

    def on_polygon(self, arg: cgm_parse.Polygon):
        poly = inkex.Polygon.new(" ".join([f"{i.x},{i.y}" for i in arg.points]))

        path = self.current_layer.add(poly.to_path_element())
        self.apply_fill(path)
        self.apply_edge(path)

    def on_polyline(self, arg: cgm_parse.Polyline):
        poly = inkex.Polyline.new(" ".join([f"{i.x},{i.y}" for i in arg.points]))

        path = self.current_layer.add(poly.to_path_element())
        self.apply_line(path)

    def on_disjoint_polyline(self, arg: cgm_parse.DisjointPolyline):
        path = inkex.PathElement.new(
            inkex.Path(
                [
                    inkex.paths.Move(pt.x, pt.y)
                    if i % 2 == 0
                    else inkex.paths.Line(pt.x, pt.y)
                    for i, pt in enumerate(arg.points)
                ]
            )
        )
        self.current_layer.add(path)
        self.apply_line(path)

    def on_polygon_set(self, arg: cgm_parse.PolygonSet):
        current_close_point = cgm_enums.Point(0, 0)
        if len(arg.points) == 0:
            return

        polygons: List[List[Tuple[bool, cgm_enums.Point]]] = []

        # First construct a list of polygons in the set.
        def iterator(pts):
            yield from pairwise(pts)
            yield [pts[-1], None]

        for e1, e2 in iterator(arg.points):
            if e1 is None:
                polygons.append([])
                current_close_point = e2.pt
            else:
                if e2 is not None and e1.linetype in (
                    cgm_enums.PolygonSetLineTypeEnum.INVISIBLE,
                    cgm_enums.PolygonSetLineTypeEnum.VISIBLE,
                ):
                    polygons[-1].append(
                        (e1.linetype == cgm_enums.PolygonSetLineTypeEnum.VISIBLE, e2.pt)
                    )
                else:
                    draw = e1.linetype in (
                        cgm_enums.PolygonSetLineTypeEnum.CLOSE_VISIBLE,
                        cgm_enums.PolygonSetLineTypeEnum.VISIBLE,
                    )
                    polygons[-1].append((draw, current_close_point))
                    if e2 is not None:
                        current_close_point = e2.pt
                        polygons.append([])

        # Now re-shuffle each polygon so we start with an invisible
        # line if it exists. Coordinates are absolute so this should be fine
        shuffled = []
        single_element = True
        for poly in polygons:
            has_invisible = any([not j[0] for j in poly])
            if has_invisible:
                inv_index = ([p[0] for p in poly]).index(False)
                shuffled.append(poly[inv_index:] + poly[:inv_index])
            else:
                shuffled.append(poly)
            if has_invisible:
                single_element = False

        # Draw the fill, then the stroke.
        fill_path = inkex.Path()
        for poly in shuffled:
            fill_path.append(inkex.paths.Move(poly[-1][1].x, poly[-1][1].y))
            for point in poly[:-1]:  # The last line is drawn via ZoneClose
                fill_path.append(inkex.paths.Line(point[1].x, point[1].y))
            fill_path.append(inkex.paths.ZoneClose())
        fill_elem = self.current_layer.add(inkex.PathElement.new(fill_path))
        self.apply_fill(fill_elem)

        if single_element:
            self.apply_edge(fill_elem)

        else:
            # Draw the stroke separately
            stroke_path = inkex.Path()

            for poly in shuffled:
                stroke_path.append(inkex.paths.Move(poly[-1][1].x, poly[-1][1].y))
                for point in poly:
                    if point[0]:
                        stroke_path.append(inkex.paths.Line(point[1].x, point[1].y))
                    else:
                        stroke_path.append(inkex.paths.Move(point[1].x, point[1].y))
                if all(i[0] for i in poly):
                    stroke_path.append(inkex.paths.ZoneClose())
            stroke_elem = self.current_layer.add(inkex.PathElement.new(stroke_path))
            self.apply_edge(stroke_elem)
            stroke_elem.style["fill"] = None

    def on_polybezier(self, arg: cgm_parse.Polybezier):
        if len(arg.points) == 0:
            return

        path = inkex.Path()
        if arg.continuous == cgm_enums.PolybezierContinuityEnum.CONTINUOUS:
            assert len(arg.points) % 3 == 1, "Bad Polybezier specification"
            path.append(inkex.paths.Move(complex(arg.points[0])))
            for i in range((len(arg.points) - 1) // 3):
                path.append(
                    inkex.paths.Curve(
                        complex(arg.points[3 * i + 1]),
                        complex(arg.points[3 * i + 2]),
                        complex(arg.points[3 * i + 3]),
                    )
                )
        else:
            assert len(arg.points) % 4 == 0, "Bad Polybezier specification"
            for i in range(len(arg.points) // 4):
                if i == 0 or path[-1].cend_point(0, 0) != complex(arg.points[4 * i]):
                    path.append(inkex.paths.Move(complex(arg.points[4 * i])))
                path.append(
                    inkex.paths.Curve(
                        complex(arg.points[4 * i + 1]),
                        complex(arg.points[4 * i + 2]),
                        complex(arg.points[4 * i + 3]),
                    )
                )
        pel = self.current_layer.add(inkex.PathElement.new(path))
        self.apply_line(pel)
        pel.style["stroke"] = "red"

    def on_circular_arc_3pt(self, arg: cgm_parse.CircularArc3Point):
        path = inkex.PathElement.arc_from_3_points(
            complex(arg.p1), complex(arg.p2), complex(arg.p3), "arc"
        )
        self.current_layer.append(path)
        self.apply_line(path)

    def on_circular_arc_3pt_close(self, arg: cgm_parse.CircularArc3PointClose):
        path = inkex.PathElement.arc_from_3_points(
            complex(arg.p1),
            complex(arg.p2),
            complex(arg.p3),
            "chord" if arg.closure == cgm_enums.ArcClosureEnum.CHORD else "slice",
        )
        self.current_layer.append(path)
        self.apply_fill(path)
        self.apply_edge(path)

    def circular_arc_helper(
        self, arg: Union[cgm_parse.CircularArcCentre, cgm_parse.CircularArcCentreClose]
    ):
        c = complex(arg.centre)
        start_ray = arg.delta_x_start + arg.delta_y_start * 1j
        end_ray = arg.delta_x_end + arg.delta_y_end * 1j
        start_angle = inkex.Vector2d(start_ray).angle
        end_angle = inkex.Vector2d(end_ray).angle
        arctype = "arc"
        if isinstance(arg, cgm_parse.CircularArcCentreClose):
            arctype = (
                "chord" if arg.closure == cgm_enums.ArcClosureEnum.CHORD else "slice"
            )
        path = inkex.PathElement.arc(
            inkex.Vector2d(c),
            arg.radius,
            arg.radius,
            arctype,
            start=start_angle,
            end=end_angle,
        )
        return path

    def on_circular_arc_centre(self, arg: cgm_parse.CircularArcCentre):
        path = self.circular_arc_helper(arg)
        self.current_layer.append(path)
        self.apply_line(path)

    def on_circular_arc_centre_close(self, arg: cgm_parse.CircularArcCentreClose):
        path = self.circular_arc_helper(arg)
        self.current_layer.append(path)
        self.apply_fill(path)
        self.apply_edge(path)

    def on_interior_style(self, arg: cgm_parse.InteriorStyle):
        self.fill_attributes.interior_style = arg.interior_style

    def on_fill_colour(self, arg: cgm_parse.FillColour):
        self.fill_attributes.fill = arg.fill

    def on_color_table(self, arg: cgm_parse.ColourTable):
        for i, col in enumerate(arg.colours):
            self.color_table[i + arg.colour_index.index] = col

    def on_line_width(self, arg: cgm_parse.LineWidth):
        if arg.width > 0:
            self.line_attributes.width = arg.width

    def on_line_width_specification_mode(
        self, arg: cgm_parse.LineWidthSpecificationMode
    ):
        self.line_attributes.specification_mode = arg.size_specification

    def on_line_colour(self, arg: cgm_parse.LineColour):
        self.line_attributes.colour = arg.colour

    def on_line_type(self, arg: cgm_parse.LineType):
        self.line_attributes.type = arg.type

    def on_edge_width(self, arg: cgm_parse.EdgeWidth):
        if arg.width > 0:
            self.edge_attributes.width = arg.width

    def on_edge_colour(self, arg: cgm_parse.EdgeColour):
        self.edge_attributes.colour = arg.colour

    def on_edge_type(self, arg: cgm_parse.EdgeType):
        self.edge_attributes.type = arg.type

    def on_edge_visibility(self, arg: cgm_parse.EdgeVisibility):
        self.edge_attributes.visibility = arg.visibility

    def on_background(self, arg: cgm_parse.BackgroundColour):
        self.svg.namedview.set("pagecolor", str(self.get_colour(arg.colour)))

    # Text-related

    def on_font_list(self, arg: cgm_parse.FontList):
        self.font_list = arg.fonts

    def on_text_font_index(self, arg: cgm_parse.TextFontIndex):
        self.text_attributes.font_index = arg.index

    def on_text_alignment(self, arg: cgm_parse.TextAlignment):
        self.text_attributes.horizontal_alignment = arg.horizontal_alignment
        self.text_attributes.vertical_alignment = arg.vertical_alignment

    def on_character_height(self, arg: cgm_parse.CharacterHeight):
        self.text_attributes.character_height = arg.height

    def on_character_orientation(self, arg: cgm_parse.CharacterOrientation):
        self.text_attributes.x_character_base = arg.x_character_base
        self.text_attributes.x_character_up = arg.x_character_up
        self.text_attributes.y_character_base = arg.y_character_base
        self.text_attributes.y_character_up = arg.y_character_up
        self.text_attributes.fallback_character_height = math.sqrt(
            arg.x_character_up**2 + arg.y_character_up**2
        )

    def on_text_precision(self, arg: cgm_parse.TextPrecision):
        self.text_attributes.precision = arg.text_precision

    def on_character_spacing(self, arg: cgm_parse.CharacterSpacing):
        self.text_attributes.character_spacing = arg.spacing

    def on_text_path(self, arg: cgm_parse.TextPath):
        self.text_attributes.path = arg.path

    def on_character_expansion(self, arg: cgm_parse.CharacterExpansionFactor):
        self.text_attributes.expansion_ratio = arg.factor

    def on_text_colour(self, arg: cgm_parse.TextColour):
        self.text_attributes.colour = arg.colour

    def add_tspan(self, text: str):
        assert self.current_text is not None
        tspan = self.current_text.add(inkex.Tspan())
        tspan.text = text
        ch = (
            self.text_attributes.character_height
            or self.text_attributes.fallback_character_height
        )
        tspan.style.update(
            {
                "font-size": 1 / 100 * self.vdc_height if ch is None else ch,
                "font-stretch": f"{self.text_attributes.expansion_ratio * 100}%",
                "letter-spacing": self.text_attributes.character_spacing,
                "fill": self.get_colour(self.text_attributes.colour),
                # 1-based indices
                "font-family": self.font_list[self.text_attributes.font_index - 1],
            }
        )

    def on_text(self, arg: cgm_parse.Text):
        self.current_text = inkex.TextElement()
        # Apply transform
        # get baseline unit vector
        cuv = inkex.Vector2d(
            0
            if self.text_attributes.x_character_up is None
            else self.text_attributes.x_character_up,
            self.vdc_height
            if self.text_attributes.y_character_up is None
            else self.text_attributes.y_character_up,
        )
        cbv = inkex.Vector2d(
            self.vdc_height
            if self.text_attributes.x_character_base is None
            else self.text_attributes.x_character_base,
            0
            if self.text_attributes.y_character_base is None
            else self.text_attributes.y_character_base,
        )
        cuv = 1 / cuv.length * cuv
        cbv = 1 / cbv.length * cbv

        self.current_text.transform = inkex.Transform(
            (cbv.x, cbv.y, cuv.x, cuv.y, 0, 0)
        ) @ inkex.Transform((1, 0, 0, -1, 0, 0))
        origin = arg.point.x + arg.point.y * 1j
        # Apply reverse transform to origin
        origin = (-self.current_text.transform).apply_to_point(origin)
        self.current_text.set("x", origin.x)
        self.current_text.set("y", origin.y)

        if (
            self.text_attributes.horizontal_alignment
            == cgm_enums.TextHorizontalAlignmentEnum.CENTER
        ):
            self.current_text.style["text-anchor"] = "middle"
        elif (
            self.text_attributes.horizontal_alignment
            == cgm_enums.TextHorizontalAlignmentEnum.RIGHT
        ):
            self.current_text.style["text-anchor"] = "end"

        if (
            self.text_attributes.vertical_alignment
            == cgm_enums.TextVerticalAlignmentEnum.HALF
        ):
            self.current_text.set("dy", "0.4em")
        if (
            self.text_attributes.vertical_alignment
            == cgm_enums.TextVerticalAlignmentEnum.TOP
        ):
            self.current_text.set("dy", "1em")

        # TODO: character direction, vertical alignment

        self.add_tspan(arg.string)
        if arg.flag == cgm_enums.TextFinalFlag.FINAL:
            self.finalize_text()

    def finalize_text(self):
        max_font_size = max([i.style["font-size"] for i in self.current_text])
        # This is for vertical alignment, which is specified in em of the largest
        # text of the box
        self.current_text.style["font-size"] = max_font_size

        self.current_layer.append(self.current_text)

    def on_default_replacement(self, arg: cgm_parse.MetafileDefaultsReplacement):
        self.default_replacement = arg.data

    def stream(self, arg: cgm_parse.CGMCommand):
        handler = self.call_mapping.get(type(arg))
        if handler:  # otherwise we ignore the command
            handler(self, arg)


class CgmInput(inkex.InputExtension):
    def __init__(self) -> None:
        super().__init__()

        self.converter = CGMConverter()

    def load(self, stream):
        self.parser = cgm_parse.BinaryCGMCommandParser(stream)
        for command in self.parser.parse():
            self.converter.stream(command)

        return self.converter.document


if __name__ == "__main__":
    CgmInput().run()
