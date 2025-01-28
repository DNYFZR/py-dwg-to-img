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

"""SVG -> XAML Converter classes for Text"""

from typing import List, Union, Optional
import copy
import re
import math

from lxml import etree
import inkex
from inkex.transforms import Transform
from inkex.utils import parse_percent

from .shapes import ShapeElementParser
from ..xamlobjects import (
    TextBlock,
    Span,
    Union,
    TextDecoration,
    TextDecorationCollection,
    Pen,
    BaseElement,
    DrawingGroup,
    LineBreak,
    removeNS,
    XAMLObject,
)
from .utils import convert_attributes
from .config import GLOBAL_SETTINGS


class TextElementParser(ShapeElementParser):
    """Base class for parsing text elements. This is only supported for highlevel
    representation.

    Stroke and different writing modes are not supported."""

    def __init__(self, svgelement: inkex.elements._text.TextElement):
        super().__init__(svgelement)

    def to_xaml_objects(self):
        """We'd need dx information to use <GlyphRun>, which is not available (yet)"""

    def create_obj(self):
        """Instantiate the right text type"""
        return TextBlock()

    @staticmethod
    def get_font_size(element, value=None):
        """Get the current font size"""
        if value is None:
            value = element.specified_style()("font-size")
        if not (isinstance(value, (float, int))) or value <= 0:
            return 12
        return value

    @staticmethod
    def separate_text(text: inkex.TextElement):
        """Separate the text into digestible elements"""
        # If the text already has x/y set, we don't need to do anything.
        # Also if the text has zero length, don't split and hope for the best.
        if (
            text.get("x", None) is not None
            and text.get("y", None) is not None
            or len(text) == 0
        ):
            return []
        # Create a wrapper that will be duplicated later.
        templ = copy.deepcopy(text)
        templ.text = ""
        templ.tail = ""
        for child in list(templ):
            templ.remove(child)
        y = initial_y = text.get("y", None)
        initial_x = text.get("x", None)
        result: List[inkex.TextElement] = []
        current_copy = copy.deepcopy(templ)
        dont_append = TextElementParser.get_width(text) == 0

        def finalize(result, current_copy):
            result += [current_copy]
            current_copy.set("x", initial_x)
            current_copy.set("y", initial_y)

        for tspan in text:
            style = tspan.specified_style()
            cur_y = tspan.get("y", 0)
            cur_x = tspan.get("x", 0)
            if initial_x is None or initial_y is None:
                initial_x = cur_x
                initial_y = cur_y
                append = True
            else:
                # We only support normal oriented text here.
                line_height = (
                    TextElementParser.get_line_height(tspan, style("line-height")) or 0
                )
                append = False
                # By default Inkscape only stores 6 digits
                if math.isclose(line_height, float(cur_y) - float(y), abs_tol=1e-5):
                    # This is a continuation of the previous text
                    append = True

            y = cur_y

            if not append or dont_append:
                finalize(result, current_copy)
                current_copy = copy.deepcopy(templ)
                initial_x, initial_y = cur_x, cur_y
            current_copy.add(tspan)
        if len(current_copy) > 0:
            finalize(result, current_copy)
        return result

    @staticmethod
    def convert_font_weight(value):
        """Get the equivalent font weight"""
        if value.isdigit():
            # Numeric font weight, see
            # https://learn.microsoft.com/dotnet/api/system.windows.fontweights
            return [
                "Thin",
                "ExtraLight",
                "Light",
                "Normal",
                "Medium",
                "DemiBold",
                "Bold",
                "ExtraBold",
                "Heavy",
                "UltraBlack",
            ][min((int(value) - 1) // 100, 9)]
        return {
            "lighter": "Thin",
            "normal": "Normal",
            "bold": "Bold",
            "bolder": "ExtraBlack",
        }.get(value, "Normal")

    @staticmethod
    def convert_font_family(value):
        """Get the equivalent font family"""
        # Font fallbacks are allowed, however we need to replace the generic families.
        # This is not necessarily the same result as Inkscape (which is
        # platform-dependent), but these fonts should exist on every Windows system
        # (WPF only exists on Windows). It might make sense to make this setting
        # available in the UI when this feature is available for Avalonia too.
        return ", ".join(
            [
                {
                    "sans-serif": "Arial",
                    "serif": "Times New Roman",
                    "monospace": "Courier New",
                    "fantasy": "Papyrus",
                    "cursive": "Brush Script MT",
                }
                .get(value, value)
                .replace("'", "")
                for value in map(lambda s: s.strip(), value.split(","))
            ]
        )

    @staticmethod
    def convert_font_stretch(value: str):
        """Get the equivalent font stretch"""
        dct = {
            "ultra-condensed": "UltraCondensed",
            "extra-condensed": "ExtraCondensed",
            "condensed": "Condensed",
            "semi-condensed": "SemiCondensed",
            "normal": "Medium",
            "semi-expanded": "SemiExpanded",
            "expanded": "Expanded",
            "extra-expanded": "ExtraExpanded",
            "ultra-expanded": "UltraExpanded",
        }
        if value[-1] == "%":
            # See https://learn.microsoft.com/dotnet/api/system.windows.fontstretch
            clss = max(0, int((float(value[:-1]) - 0.00001) / 12.5) - 3)
            index = 7 if clss in [7, 8] else 8 if clss > 8 else clss
            return list(dct.values())[index]
        return dct.get(value, None)

    def set_text_decoration(self, primitive: Union[Span, TextBlock]):
        """Creates a visually conforming representation of the TextDecoration.
        Does not support style: blink (deprecated). Multiple styles are supported."""
        # Get shorthand and TextDecorationLocation (decide later)
        line = self.effective_style("text-decoration-line")
        if line == "none" or line is None:
            return
        linetype = {
            "underline": "Underline",
            "overline": "Overline",
            "line-through": "Strikethrough",
        }
        style = self.effective_style("text-decoration-style")
        color = self.effective_style("text-decoration-color")
        if style == "solid" and color == "currentcolor" and line in linetype:
            # Use the predefined shorthands.
            primitive.add_property("TextDecorations", linetype[line])
            return
        collection = TextDecorationCollection()
        for line_item in line.split():
            if line_item not in linetype:
                continue
            ltype = linetype[line_item]
            # Otherwise we need to define one or more TextDecoration objects.
            result = TextDecoration()
            result.add_property("Location", ltype)
            pen = Pen()

            brush = (
                self.get_brush(primitive)
                if color == "currentcolor" or color is None
                else self.color_to_xaml_color(inkex.Color(color))
            )
            pen.add_property("Brush", brush)
            pen.add_property("Thickness", 1)  # UA choice
            result.add_property("Pen", pen)

            dashstyle_map = {
                "dashed": ("Flat", [1.5, 1.5]),
                "dotted": ("Round", [0.0, 0.75]),
            }
            if style in dashstyle_map:
                pen.add_property("DashCap", dashstyle_map[style][0])
                pen.add_property(
                    "DashStyle", self.dashstyle_from_dasharray(dashstyle_map[style][1])
                )
            collection.add_child(result)
            if style == "double":
                cpy = copy.deepcopy(result)
                cpy.add_properties(
                    {
                        "PenOffset": 0.1 if line_item == "underline" else -0.1,
                        "PenOffsetUnit": "FontRenderingEmSize",
                    }
                )
                collection.add_child(cpy)
        primitive.add_property("TextDecorations", collection)

    @staticmethod
    def get_width(element: BaseElement) -> float:
        """Figure out the width of a flowed text
        (shape-inside, inline-size, flowroot)"""
        style = element.specified_style()

        inline_size = element.to_dimensionless(style("inline-size"))
        if inline_size > 0:
            return inline_size
        # FlowRegion and shape-inside work the same way
        shape_inside = style("shape-inside")
        if shape_inside is not None and isinstance(shape_inside, inkex.Rectangle):
            if shape_inside.composed_transform() == inkex.Transform():
                return shape_inside.width

        frs = [e for e in element if isinstance(e, inkex.FlowRegion)]
        if len(frs) > 0 and len(frs[0]) == 1 and isinstance(frs[0][0], inkex.Rectangle):
            if frs[0][0].transform == inkex.Transform():
                return frs[0][0].width
        return 0

    @staticmethod
    def get_line_height(element, value=None) -> Optional[float]:
        """Compute the absolute line height"""
        if value is None:
            value = element.specified_style()("line-height")
        try:
            value = parse_percent(value) * TextElementParser.get_font_size(element)
        except ValueError:
            value = element.to_dimensionless(value)
        if value <= 0.0034 or value >= 160000:  # bounds of TextBlock.LineHeight
            return None
        return value

    def set_position_and_style(self, primitive: BaseElement):
        """Set all attributes that only exist for TextBlocks, but not Spans."""
        fontsize = self.get_font_size(self.element) or 12
        line_height = (
            self.get_line_height(self.element, self.effective_style("line-height"))
            or fontsize
        )
        top = (
            float(self.element.get("y", "0").split(" ")[0])
            - (
                3 / 2
                if isinstance(self.element, (inkex.TextElement, inkex.Tspan))
                else (1 / 2)
            )
            * fontsize
            + 1 / 2 * line_height
        )
        left = float(self.element.get("x", "0").split(" ")[0])

        primitive.add_properties({"Canvas.Top": top, "Canvas.Left": left})
        effective_transform = (
            Transform(translate=(-left, -top))
            @ self.element.transform
            @ Transform(translate=(left, top))
        )
        primitive.set_transform(effective_transform)

        if self.effective_style("display") == "none":
            primitive.set_invisible()
        primitive.add_property(
            "ClipGeometry" if isinstance(primitive, DrawingGroup) else "Clip",
            self.get_clip(primitive),
        )
        primitive.add_property("OpacityMask", self.get_mask(primitive))
        primitive.add_property("Opacity", self.effective_style("opacity"), 1)
        width = self.get_width(self.element)
        if width > 0:
            primitive.add_property("TextWrapping", "Wrap")
            primitive.add_property("Width", width)
        blur = self.get_blur()
        # Bitmap effects are supposed to be added in Avalonia 11 or 12
        if GLOBAL_SETTINGS.wpf and blur is not None:
            primitive.add_property("Effect", blur)

    def set_text_style(self, primitive: BaseElement):
        """Set all text style attributes that we know how to convert."""
        convert_attributes(
            self.effective_style,
            primitive,
            [
                [
                    "font-weight",
                    "FontWeight",
                    self.convert_font_weight,
                    "Normal",
                ],
                [
                    "font-size",
                    "FontSize",
                    lambda f: self.get_font_size(self.element, f),
                ],
                ["font-style", "FontStyle", ["normal", "italic", "oblique"], "Normal"],
                ["font-family", "FontFamily", self.convert_font_family],
                ["fill", "Foreground", self.get_brush],
                [
                    "line-height",
                    "LineHeight",
                    lambda f: self.get_line_height(self.element, f),
                ],
                # This could take unicode-bidi into account.
                [
                    "direction",
                    "FlowDirection",
                    {"ltr": "LeftToRight", "rtl": "RightToLeft"},
                    "LeftToRight",
                    "ltr",
                ],
                ["font-stretch", "FontStretch", self.convert_font_stretch, "Medium"],
                [
                    "text-align",
                    "TextAlignment",
                    {"start": "Left", "middle": "Center", "end": "Right"},
                    "Left",
                    "start",
                ],
            ],
        )
        self.set_text_decoration(primitive)

    def xmlspace(self) -> str:
        """get this element's xml:space attribute which, might be inherited"""

        def ancestors_with_self():
            yield self.element
            yield from self.element.iterancestors()

        for ancestor in ancestors_with_self():
            if "{http://www.w3.org/XML/1998/namespace}space" in ancestor.attrib:
                return ancestor.get("xml:space")
        return "default"

    def process_xmlspace(self, text):
        """Process the xml:space attribute"""
        if text is None:
            return None
        preserve = self.xmlspace() == "preserve"
        if not preserve:
            # Flatten spaces as described here:
            # https://svgwg.org/svg2-draft/text.html#LegacyXMLSpace
            return re.sub(
                r"\s+",
                " ",
                text.replace("\t", " ").replace("\r", "").replace("\n", "").strip(),
            )
        return text

    def add_spaced(self, primitive, text: str, tail: bool = False, parent=None):
        """Process text, which already has been processed according to xml:space
        For tail, the parent is needed."""
        # We need to process line breaks individually
        if text is None or primitive is None:
            return
        lines = text.split("\n")
        linebreaks = [LineBreak() for i in lines]
        setattr(primitive, "tail" if tail else "text", lines[0])
        if len(lines) == 1:
            return
        effective_parent = primitive if not tail else parent
        for line, brk in zip(lines[1:], linebreaks[1:]):
            effective_parent.add_child(brk)
            brk.tail = line

    def to_canvas_objects(self):
        if self.get_font_size(self.element) == 0:
            return None
        result = self.create_obj()
        self.add_spaced(result, self.process_xmlspace(self.element.text), False)

        self.set_position_and_style(result)
        self.set_text_style(result)
        if GLOBAL_SETTINGS.wpf:
            # This will be supported in Avalonia 11.0,
            # see https://github.com/AvaloniaUI/Avalonia/issues/2619
            for child in self.element:
                # Text element and tspans can contain other tspans
                if isinstance(child, (inkex.Tspan, inkex.FlowPara, inkex.FlowSpan)):
                    child_parsed = TspanParser(child).to_canvas_objects()
                    result.add_child(child_parsed)
                    if child.get("sodipodi:role", None) == "line":
                        result.add_child(LineBreak())
                    if isinstance(child, inkex.FlowPara):
                        result.add_child(LineBreak())
                    self.add_spaced(
                        child_parsed,
                        self.process_xmlspace(child.tail),
                        True,
                        result,
                    )
            self.simplify(result)

        return result

    def simplify(self, element: TextBlock):
        """Simplify a text recursively"""
        for child in list(element):
            if not isinstance(child, (TextBlock, Span)):
                continue  # no need to process line breaks
            # Simplify all children first.
            self.simplify(child)

            # Remove all attributes on the child that are also on the parent.
            for attr in child.attrib:
                if element.get(attr, None) == child.get(attr, None):
                    child.remove_property(attr)

            # If there are property elements, we can't integrate the element
            # into the parent.
            if any(
                "." in removeNS(super(etree.ElementBase, elem).tag)[1] for elem in child  # type: ignore
            ):
                continue

            # If the span now has no other attributes, append it to the
            # previous element's tail. If there is no previous element, append
            # it to the parent's text.
            if len(child.attrib) == 0:
                prev = child.getprevious()
                added = child.text or ""
                if prev is not None:
                    prev.tail = (prev.tail or "") + added
                else:
                    element.text = (element.text or "") + added
                # Add the remaining children (such as line breaks) one level up
                for child2 in child:
                    if isinstance(prev, XAMLObject):
                        # This unfortunately moves the tail, so we need to preserve it
                        tail = prev.tail or ""
                        prev.tail = None
                        res = prev.addnext(child2)
                        prev.tail = tail
                        prev = res
                    else:
                        prev = element.insert(0, child2)
                if prev is not None:
                    prev.tail = (prev.tail or "") + (child.tail or "")
                else:
                    element.text = (element.text or "") + (child.tail or "")

                element.remove(child)


class TspanParser(TextElementParser):
    """Convert tspans to Spans"""

    def __init__(self, svgelement: inkex.elements._text.Tspan):
        super().__init__(svgelement)

    def create_obj(self):
        return Span()

    def set_position_and_style(self, primitive: BaseElement):
        """The position (and position-related style attributes)
        are already set on the parent TextBlock, so we return immediately."""

    def set_text_style(self, primitive: BaseElement):
        super().set_text_style(primitive)
        convert_attributes(
            self.effective_style,
            primitive,
            [
                [
                    "baseline-shift",
                    "BaselineAlignment",
                    {"baseline": "Normal", "super": "Superscript", "sub": "Subscript"},
                    "Normal",
                    "baseline",
                ]
            ],
        )
        primitive.remove_property("TextAlignment")
        primitive.remove_property("LineHeight")
