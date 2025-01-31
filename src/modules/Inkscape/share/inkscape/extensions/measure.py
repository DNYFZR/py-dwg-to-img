#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2015 ~suv <suv-sf@users.sf.net>
# Copyright (C) 2010 Alvin Penner
# Copyright (C) 2006 Georg Wiora
# Copyright (C) 2006 Nathan Hurst
# Copyright (C) 2005 Aaron Spike, aaron@ekips.org
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
"""
This extension module can measure arbitrary path and object length
It adds text to the selected path containing the length in a given unit.
Area and Center of Mass calculated using Green's Theorem:
http://mathworld.wolfram.com/GreensTheorem.html
"""

import inkex

from inkex import TextElement, TextPath, Tspan
from inkex.bezier import csparea, cspcofm
from inkex.localization import inkex_gettext as _
from inkex.paths.interfaces import LengthSettings


class MeasureLength(inkex.EffectExtension):
    """Measure the length of selected paths"""

    def add_arguments(self, pars):
        pars.add_argument(
            "--type", dest="mtype", default="length", help="Type of measurement"
        )
        pars.add_argument(
            "--method",
            type=self.arg_method(),
            default=self.method_textonpath,
            help="Text Orientation method",
        )
        pars.add_argument(
            "--presetFormat", default="default", help="Preset text layout"
        )
        pars.add_argument(
            "--startOffset", default="custom", help="Text Offset along Path"
        )
        pars.add_argument(
            "--startOffsetCustom", type=int, default=50, help="Text Offset along Path"
        )
        pars.add_argument("--anchor", default="start", help="Text Anchor")
        pars.add_argument("--position", default="start", help="Text Position")
        pars.add_argument("--angle", type=float, default=0, help="Angle")
        pars.add_argument(
            "-f",
            "--fontsize",
            type=int,
            default=12,
            help="Size of length label text in px",
        )
        pars.add_argument(
            "-o",
            "--offset",
            type=float,
            default=-6,
            help="The distance above the curve",
        )
        pars.add_argument(
            "-u", "--unit", default="px", help="The unit of the measurement"
        )
        pars.add_argument(
            "-p",
            "--precision",
            type=int,
            default=2,
            help="Number of significant digits after decimal point",
        )
        pars.add_argument(
            "-s",
            "--scale",
            type=float,
            default=1.0,
            help="Scale Factor (Drawing:Real Length)",
        )

    def effect(self):
        # get number of digits
        prec = int(self.options.precision)
        scale = self.svg.viewport_to_unit(
            "1" + self.svg.document_unit
        )  # convert to document units
        self.options.offset *= scale

        factor = self.svg.unit_to_viewport(1, self.options.unit)

        # loop over all selected paths
        filtered = self.svg.selection.filter(inkex.PathElement)
        if not filtered:
            raise inkex.AbortExtension(_("Please select at least one path object."))
        for node in filtered:
            path: inkex.Path = node.path.transform(node.composed_transform())
            if self.options.mtype == "length":
                settings = LengthSettings(error=1e-8)
                stotal = sum(
                    command.length(settings=settings)
                    for command in path.proxy_iterator()
                    if command.letter not in "mM"
                )
                self.group = node.getparent().add(TextElement())
            else:
                csp = path.to_superpath()
                inverse_parent_transform = -node.getparent().composed_transform()
                if self.options.mtype == "area":
                    stotal = abs(csparea(csp) * factor * self.options.scale)
                    self.group = node.getparent().add(TextElement())
                else:
                    try:
                        xc, yc = cspcofm(csp)
                    except ValueError as err:
                        raise inkex.AbortExtension(str(err))
                    self.group = node.getparent().add(inkex.PathElement())
                    self.group.set("id", "MassCenter_" + node.get("id"))
                    self.add_cross(self.group, xc, yc, scale)
                    self.group.transform = inverse_parent_transform
                    continue
            # Format the length as string
            val = round(stotal * factor * self.options.scale, prec)
            # Transform the result back
            self.options.method(node, str(val))

    def method_textonpath(self, node, lenstr):
        startOffset = self.options.startOffset
        if startOffset == "custom":
            startOffset = str(self.options.startOffsetCustom) + "%"
        if self.options.mtype == "length":
            self.add_textonpath(
                self.group,
                0,
                0,
                lenstr + " " + self.options.unit,
                node,
                self.options.anchor,
                startOffset,
                self.options.offset,
            )
        else:
            self.add_textonpath(
                self.group,
                0,
                0,
                lenstr + " " + self.options.unit + "^2",
                node,
                self.options.anchor,
                startOffset,
                self.options.offset,
            )

    def method_fixedtext(self, node, lenstr):
        _id = node.get("id")
        csp = node.path.transform(node.composed_transform()).to_superpath()
        if self.options.position == "mass":
            tx, ty = cspcofm(csp)
            anchor = "middle"
        elif self.options.position == "center":
            bbox = node.bounding_box(True)
            tx, ty = bbox.center
            anchor = "middle"
        else:  # default
            tx = csp[0][0][1][0]
            ty = csp[0][0][1][1]
            anchor = "start"
        if self.options.mtype == "length":
            self.add_fixedtext(
                self.group,
                tx,
                ty,
                lenstr + " " + self.options.unit,
                anchor,
                -int(self.options.angle),
                self.options.offset + self.options.fontsize / 2,
            )
        else:
            self.add_fixedtext(
                self.group,
                tx,
                ty,
                lenstr + " " + self.options.unit + "^2",
                anchor,
                -int(self.options.angle),
                -self.options.offset + self.options.fontsize / 2,
            )

    def method_presets(self, node, lenstr):
        """A preset option for alignments"""
        preset_dict = {
            "default_cofm": [None, None, None, None, None],
            "default_length": [self.method_textonpath, "50%", "start", None, None],
            "TaP_start": [self.method_textonpath, "0%", "start", None, None],
            "TaP_middle": [self.method_textonpath, "50%", "middle", None, None],
            "TaP_end": [self.method_textonpath, "100%", "end", None, None],
            "default_area": [self.method_fixedtext, None, None, "start", 0.0],
            "FT_start": [self.method_fixedtext, None, None, "start", 0.0],
            "FT_bbox": [self.method_fixedtext, None, None, "center", 0.0],
            "FT_mass": [self.method_fixedtext, None, None, "mass", 0.0],
        }

        if self.options.presetFormat == "default":
            current_preset = "default_" + self.options.mtype
        else:
            current_preset = self.options.presetFormat

        self.options.startOffset = preset_dict[current_preset][1]
        self.options.anchor = preset_dict[current_preset][2]
        self.options.position = preset_dict[current_preset][3]
        self.options.angle = preset_dict[current_preset][4]
        method = preset_dict[current_preset][0]
        if method is not None:
            return method(node, lenstr)

    def add_cross(self, node, x, y, scale):
        l = 3 * scale  # 3 pixels in document units
        node.set(
            "d",
            "m %s,%s %s,0 %s,0 m %s,%s 0,%s 0,%s"
            % (str(x - l), str(y), str(l), str(l), str(-l), str(-l), str(l), str(l)),
        )
        node.set("style", "stroke:#000000;fill:none;stroke-width:%s" % str(0.5 * scale))

    def add_textonpath(self, node, x, y, text, _node, anchor, startOffset, dy=0):
        new = node.add(TextPath())
        s = {
            "text-align": "center",
            "vertical-align": "bottom",
            "text-anchor": anchor,
            "font-size": str(self.options.fontsize),
            "fill-opacity": "1.0",
            "stroke": "none",
            "font-weight": "normal",
            "font-style": "normal",
            "fill": "#000000",
        }
        new.style = s
        new.href = _node
        new.set("startOffset", startOffset)
        new.set("dy", str(dy))  # dubious merit
        # new.append(tp)
        if text[-2:] == "^2":
            new.append(Tspan.superscript("2"))
            new.text = str(text)[:-2]
        else:
            new.text = str(text)
        # node.set('transform','rotate(180,'+str(-x)+','+str(-y)+')')
        node.set("x", str(x))
        node.set("y", str(y))

    def add_fixedtext(self, node, x, y, text, anchor, angle, dy=0):
        new = node.add(Tspan())
        new.set("sodipodi:role", "line")
        s = {
            "text-align": "center",
            "vertical-align": "bottom",
            "text-anchor": anchor,
            "font-size": self.svg.viewport_to_unit(self.options.fontsize),
            "fill-opacity": "1.0",
            "stroke": "none",
            "font-weight": "normal",
            "font-style": "normal",
            "fill": "#000000",
        }
        new.style = s
        new.set("dy", str(dy))
        if text[-2:] == "^2":
            new.append(Tspan.superscript("2"))
            new.text = str(text)[:-2]
        else:
            new.text = str(text)
        node.set("x", str(x))
        node.set("y", str(y))
        node.set("transform", "rotate(%s, %s, %s)" % (angle, x, y))
        node.transform = -node.getparent().composed_transform() @ node.transform


if __name__ == "__main__":
    MeasureLength().run()
