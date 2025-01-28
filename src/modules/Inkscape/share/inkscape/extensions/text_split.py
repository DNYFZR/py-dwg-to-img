#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2009 Karlisson Bezerra, contato@nerdson.com
#               2021 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
#
"""Splits a text element into lines, words, chars.
Supports all text elements that Inkscape can create, such as normal text, shape-inside (SVG2),
flowroot (SVG1.2), inline-size, manual kerns, and nested tspans (with possibly different kerns)

The code is structured as followed. For each selected text element:
 - preprocess_text_element duplicates the element, converts flowroots to plain text elements,
   and simplifies manual kerning if requested (only for split_words and split_chars, for all,
   possibly nested, children) using simplify_nested_tspans.
 - if split lines: split_lines copies all top-level tspans from the previous step into their own
   text element, which is otherwise a duplicate of the original text element (thus preserving
   style and transforms), see append_splitted_element
 - if split words or chars: split_words_or_chars: the text is recursively processed. For each tspan,
   the content and tail is split (words: at spaces, chars: after each character) into their own
   tspan, again using append_splitted_element. The method keeps track of the horizontal and vertical
   coordinate, incrementing it with the number of characters and a multiple of font size.
"""

import re as regex
from typing import Union, Callable

import inkex
from inkex import TextElement, FlowRoot, FlowPara, Tspan, Rectangle, ShapeElement
from inkex.units import parse_unit
from inkex.localization import inkex_gettext as _

TextLike = Union[FlowRoot, TextElement]


class TextSplit(inkex.EffectExtension):
    """Split text up."""

    def __init__(self):
        """Initialize State machine"""
        super().__init__()
        self.mode: Callable
        self.separation: float = 1
        self.fs_multiplier: float = 0.25
        self.current_x: float = 0
        self.current_y: float = 0
        self.process_kerns: bool = True
        self.current_root: TextLike
        self.current_fontsize: float = 0

    def add_arguments(self, pars):
        pars.add_argument("--tab", help="The selected UI tab when OK was pressed")
        pars.add_argument(
            "-t",
            "--splittype",
            default="line",
            choices=["letter", "word", "line"],
            help="type of split",
        )
        pars.add_argument(
            "-p",
            "--preserve",
            type=inkex.Boolean,
            default=True,
            help="Preserve original",
        )
        pars.add_argument(
            "-s",
            "--separation",
            type=float,
            default=1,
            help="Threshold for separating text with manual kerns in multiples of"
            "font-size",
        )

    def effect(self):
        """Applies the effect"""

        split_type = self.options.splittype
        preserve = self.options.preserve

        # checks if the selected elements are text nodes
        for elem in self.svg.selection.filter_nonzero(TextElement, FlowRoot):
            try:
                self.separation = self.options.separation
                if split_type == "line":
                    node = self.split_lines(elem)
                elif split_type == "word":
                    self.mode = self.process_plain_words
                    node = self.split_words_or_chars(elem)
                else:
                    self.separation = 0
                    self.mode = self.process_plain_chars
                    node = self.split_words_or_chars(elem)

                node.getparent().remove(node)

                if not preserve and node is not None:
                    elem.getparent().remove(elem)
            except TypeError as err:
                inkex.errormsg(err)  # if an element can not be processed

    @staticmethod
    def get_font_size(element):
        """get the font size of an element"""
        return element.get_computed_style("font-size")

    @staticmethod
    def get_line_height(element: ShapeElement):
        """get the line height of an element"""
        return element.get_line_height_uu()

    def simplify_child_tspans(self, element: TextElement):
        """Checks all child tspans if they have manual kerns.
        If it does, try to find words (characters with a distance > separation * font-size).
        Then concatenate the words with spaces, set this string as a new text and"""
        for child in list(element):
            # process manual kerns
            if not isinstance(child, Tspan):
                continue
            xvals = list(
                map(float, filter(len, regex.split(r"[,\s]", child.get("x") or "")))
            )
            content = child.text
            if content not in [None, ""] and len(xvals) >= 2:
                fsize = self.get_font_size(child)
                separation = self.separation * fsize
                current_word_start = 0
                for i in range(1, max(len(content), len(xvals))):
                    if i >= len(content) - 1 or i >= len(xvals) - 1:
                        # consume the entire remaining string
                        i = len(content)
                    if i == len(content) or abs(xvals[i] - xvals[i - 1]) > separation:
                        wordspan = Tspan(x=str(xvals[current_word_start]))
                        wordspan.text = content[current_word_start:i]
                        child.add(wordspan)
                        current_word_start = i
                child.pop("x")
                child.text = None
            # process child elements
            self.simplify_child_tspans(child)

    def preprocess_text_element(self, element: TextElement):
        """Processes a text element and returns an element containing tspans with x and y coordinate,
        possibly nested (for Inkscape-type kerning), so that the actual splitting can work as if the
        text was a simple text. Manual kerns (one x value per letter) are converted to spaces
        if requested (not necessary for "split characters")"""

        oldelement = element
        if isinstance(element, FlowRoot):
            element = TextElement()
            oldelement.addnext(element)
            element.style = oldelement.style
            element.transform = oldelement.transform
            flowref = oldelement.findone("svg:flowRegion")[0]
            if isinstance(flowref, Rectangle):
                flowx = element.unittouu(flowref.get("x"))
                flowy = element.unittouu(float(flowref.get("y")))
                first = True
            else:
                raise TypeError(
                    _(
                        "Element {} uses a flow region that is not a rectangle. "
                        "First unflow text."
                    ).format(element.get_id())
                )
            for child in oldelement:
                if isinstance(child, FlowPara):
                    # convert the flowpara "line" (note: no automatic wrapping)
                    # to a tspan and set the y coordinate.
                    # future FlowRoot improvements could add a better conversion.
                    newchild = Tspan()
                    element.append(newchild)
                    newchild.text = child.text
                    newchild.style = child.style
                    newchild.transform = child.transform
                    newchild.set("x", flowx)
                    if first:
                        flowy += self.get_font_size(child) * 1.25
                        first = False
                    else:
                        flowy += self.get_line_height(child)
                    newchild.set("y", str(flowy))

        else:
            element = oldelement.duplicate()
            oldelement.getparent().append(element)

        element.style.pop("shape-inside", None)

        # Real support for RTL text is missing, but we can emulate it by just removing the
        # attribute. However, line breaks will be misaligned.
        element.style.pop("direction", None)
        for child in element:
            child.style.pop("direction", None)

        if self.process_kerns:
            self.simplify_child_tspans(element)
        return element

    def append_splitted_element(self, text, prototype=None):
        """Creates a new text element, sibling to self.current_root, at (self.current_x,
        self.current_y) with content text.

        text: either a Tspan that should be moved to a new text element - in this case, text is
            a direct child of element; or a string
        prototype: if text is a string, style and transform will be taken from prototype
        """

        if isinstance(text, Tspan) and text.getparent() == self.current_root:
            # we just move the tspan to a new text element.
            elem = self.current_root.duplicate()
            elem.remove_all(Tspan)
            elem.append(text)
            elem.set("x", text.get("x"))
            elem.set("y", text.get("y"))
        else:
            elem = TextElement(x=str(self.current_x), y=str(self.current_y))
            # transfer the style from all parents, including the text element (if there's a style to
            # the text element's parent applied, it will be duplicated, but that doesn't really
            # matter)
            elem.style = prototype.specified_style()
            # the element will be appended to the parent of element, but there might be nested
            # tspans between the prototype and the element. The next line says
            # "compose transforms until you reach the parent of element"
            elem.transform = (
                -self.current_root.getparent().transform
            ) @ prototype.composed_transform()
            tsp = Tspan(x=str(self.current_x), y=str(self.current_y))
            tsp.text = text
            elem.add(tsp)
        self.current_root.addnext(elem)

    def split_lines(self, element: TextLike) -> TextElement:
        """Splits a text into its lines"""
        self.process_kerns = False
        preprocessed = self.preprocess_text_element(element)
        self.current_root = preprocessed
        # Now we only have to copy each tspan into its own text element.
        for child in list(preprocessed):
            self.append_splitted_element(child)

        return preprocessed

    def process_plain_text(self, element, splitted):
        """Appends new text elements to as sibling root for each element of splitted, starting at
        self.current_x, self.current_y, incrementing those, with prototype element (that
        styles and transforms will be taken from)"""
        if splitted is None:
            return
        for word in splitted:
            if word != "":
                self.append_splitted_element(word, element)
            # +1 since for words, we lost a space
            self.current_x += (
                self.current_fontsize * (len(word) + 1) * self.fs_multiplier
            )

    def process_plain_words(self, element, text):
        """Calls process_plain_text for splitting words"""
        self.fs_multiplier = 0.4
        if text is not None:
            self.process_plain_text(element, text.split(" "))

    def process_plain_chars(self, element, text):
        """Calls process_plain_text for splitting characters"""
        self.fs_multiplier = 0.25
        self.process_plain_text(element, text)

    def split_words_or_chars(self, element: TextLike) -> TextElement:
        """Splits a text into its lines"""
        self.process_kerns = True
        preprocessed = self.preprocess_text_element(element)

        def process_element(element) -> float:
            elem_coords = {
                i: (
                    element.root.unittouu(element.get(i))
                    if element.get(i) is not None
                    else None
                )
                for i in "xy"
            }
            if elem_coords["x"] is not None:
                self.current_x = elem_coords["x"]
            if elem_coords["y"] is not None:
                self.current_y = elem_coords["y"]
            self.current_fontsize = self.get_font_size(element)
            current_x = self.mode(element, element.text)

            for elem in element:
                if isinstance(elem, Tspan):
                    current_x = process_element(elem)
                current_x = self.mode(element, elem.tail)
            return current_x

        self.current_root = preprocessed
        process_element(preprocessed)
        return preprocessed


if __name__ == "__main__":
    TextSplit().run()
