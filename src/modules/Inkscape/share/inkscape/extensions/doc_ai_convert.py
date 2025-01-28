#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2021 Windell H. Oskay, www.evilmadscientist.com
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
An Inkscape extension to assist with importing AI SVG files.
"""

import inkex
from inkex import units


class DocAiConvert(inkex.EffectExtension):
    """
    Main class of the doc_ai_convert extension

    This extension performs the following two actions:
    1) Recognize intended dimensions of original document.
        - If the AI document was set up with a size given in picas, cm, mm, or in,
          and then exported to SVG, no conversion is needed.
        - If the AI document was set up with any other dimensions,
          (point, yard, px, ft/in, ft, or m), then the exported SVG
          will be in units of 72 DPI pixels. This causes an issue,
          as Inkscape uses CSS pixels (px) which are at 96 DPI.
          In this case, we re-interpret the size as 72 DPI points (pt),
          which will convert the artwork to appear at the correct size.
    2) Recognize Adobe Illustrator layers.
        - Group (<g>) elements with non-empty data-name attributes are
          groups in an Illustrator SVG document.
        - We re-label these as layers such that Inkscape will recognize them.

    """

    def effect(self):
        """
        Main entry point of the doc_ai_convert extension
        """
        # 1) Recognize intended dimensions of original document, if given
        width_string = self.svg.get("width")
        height_string = self.svg.get("height")

        if width_string and height_string:
            width_num, width_units = units.parse_unit(width_string)
            height_num, height_units = units.parse_unit(height_string)

            # Note that units.parse_unit will return units of 'px'
            #    for unitless values, and not None.

            if width_num:
                if width_units == "px":
                    self.svg.set("width", units.render_unit(width_num, "pt"))
            if height_num:
                if height_units == "px":
                    self.svg.set("height", units.render_unit(height_num, "pt"))

        # 2) Recognize Adobe Illustrator layers.
        for node in self.svg.xpath("//svg:g[@data-name]"):
            node.set("inkscape:groupmode", "layer")
            node.set("inkscape:label", node.pop("data-name"))


if __name__ == "__main__":
    DocAiConvert().run()
