#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2008-2009 Alvin Penner, penner@vaxxine.com
#               2009, Christian Mayer, inkscape@christianmayer.de
#               2020, MartinOwens, doctormo@geek-2.com
#               2024, Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
Input a DXF file >= (AutoCAD Release 13 == AC1012)
"""

import os
import re
import struct
import sys
import math

from collections import defaultdict
from typing import Tuple
from urllib.parse import quote
from lxml import etree

import inkex
from inkex.localization import inkex_gettext as _

global defs
global block  # 2021.6
global layer
global svg
global scale
global xmin
global ymin
global height
global style_font3
global style_direction

COLORS = [
    "PAD",
    "#FF0000",
    "#FFFF00",
    "#00FF00",
    "#00FFFF",
    "#0000FF",
    "#FF00FF",
    "#000000",
    "#808080",
    "#C0C0C0",
    "#FF0000",
    "#FF7F7F",
    "#CC0000",
    "#CC6666",
    "#990000",
    "#994C4C",
    "#7F0000",
    "#7F3F3F",
    "#4C0000",
    "#4C2626",
    "#FF3F00",
    "#FF9F7F",
    "#CC3300",
    "#CC7F66",
    "#992600",
    "#995F4C",
    "#7F1F00",
    "#7F4F3F",
    "#4C1300",
    "#4C2F26",
    "#FF7F00",
    "#FFBF7F",
    "#CC6600",
    "#CC9966",
    "#994C00",
    "#99724C",
    "#7F3F00",
    "#7F5F3F",
    "#4C2600",
    "#4C3926",
    "#FFBF00",
    "#FFDF7F",
    "#CC9900",
    "#CCB266",
    "#997200",
    "#99854C",
    "#7F5F00",
    "#7F6F3F",
    "#4C3900",
    "#4C4226",
    "#FFFF00",
    "#FFFF7F",
    "#CCCC00",
    "#CCCC66",
    "#989800",
    "#98984C",
    "#7F7F00",
    "#7F7F3F",
    "#4C4C00",
    "#4C4C26",
    "#BFFF00",
    "#DFFF7F",
    "#99CC00",
    "#B2CC66",
    "#729800",
    "#85984C",
    "#5F7F00",
    "#6F7F3F",
    "#394C00",
    "#424C26",
    "#7FFF00",
    "#BFFF7F",
    "#66CC00",
    "#99CC66",
    "#4C9800",
    "#72984C",
    "#3F7F00",
    "#5F7F3F",
    "#264C00",
    "#394C26",
    "#3FFF00",
    "#9FFF7F",
    "#33CC00",
    "#7FCC66",
    "#269800",
    "#5F984C",
    "#1F7F00",
    "#4F7F3F",
    "#134C00",
    "#2F4C26",
    "#00FF00",
    "#7FFF7F",
    "#00CC00",
    "#66CC66",
    "#009800",
    "#4C984C",
    "#007F00",
    "#3F7F3F",
    "#004C00",
    "#264C26",
    "#00FF3F",
    "#7FFF9F",
    "#00CC33",
    "#66CC7F",
    "#009826",
    "#4C985F",
    "#007F1F",
    "#3F7F4F",
    "#004C13",
    "#264C2F",
    "#00FF7F",
    "#7FFFBF",
    "#00CC66",
    "#66CC99",
    "#00984C",
    "#4C9872",
    "#007F3F",
    "#3F7F5F",
    "#004C26",
    "#264C39",
    "#00FFBF",
    "#7FFFDF",
    "#00CC99",
    "#66CCB2",
    "#009872",
    "#4C9885",
    "#007F5F",
    "#3F7F6F",
    "#004C39",
    "#264C42",
    "#00FFFF",
    "#7FFFFF",
    "#00CCCC",
    "#66CCCC",
    "#009898",
    "#4C9898",
    "#007F7F",
    "#3F7F7F",
    "#004C4C",
    "#264C4C",
    "#00BFFF",
    "#7FDFFF",
    "#0099CC",
    "#66B2CC",
    "#007298",
    "#4C8598",
    "#005F7F",
    "#3F6F7F",
    "#00394C",
    "#26424C",
    "#007FFF",
    "#7FBFFF",
    "#0066CC",
    "#6699CC",
    "#004C98",
    "#4C7298",
    "#003F7F",
    "#3F5F7F",
    "#00264C",
    "#26394C",
    "#003FFF",
    "#7F9FFF",
    "#0033CC",
    "#667FCC",
    "#002698",
    "#4C5F98",
    "#001F7F",
    "#3F4F7F",
    "#00134C",
    "#262F4C",
    "#0000FF",
    "#7F7FFF",
    "#0000CC",
    "#6666CC",
    "#000098",
    "#4C4C98",
    "#00007F",
    "#3F3F7F",
    "#00004C",
    "#26264C",
    "#3F00FF",
    "#9F7FFF",
    "#3300CC",
    "#7F66CC",
    "#260098",
    "#5F4C98",
    "#1F007F",
    "#4F3F7F",
    "#13004C",
    "#2F264C",
    "#7F00FF",
    "#BF7FFF",
    "#6600CC",
    "#9966CC",
    "#4C0098",
    "#724C98",
    "#3F007F",
    "#5F3F7F",
    "#26004C",
    "#39264C",
    "#BF00FF",
    "#DF7FFF",
    "#9900CC",
    "#B266CC",
    "#720098",
    "#854C98",
    "#5F007F",
    "#6F3F7F",
    "#39004C",
    "#42264C",
    "#FF00FF",
    "#FF7FFF",
    "#CC00CC",
    "#CC66CC",
    "#980098",
    "#984C98",
    "#7F007F",
    "#7F3F7F",
    "#4C004C",
    "#4C264C",
    "#FF00BF",
    "#FF7FDF",
    "#CC0099",
    "#CC66B2",
    "#980072",
    "#984C85",
    "#7F005F",
    "#7F3F6F",
    "#4C0039",
    "#4C2642",
    "#FF007F",
    "#FF7FBF",
    "#CC0066",
    "#CC6699",
    "#98004C",
    "#984C72",
    "#7F003F",
    "#7F3F5F",
    "#4C0026",
    "#4C2639",
    "#FF003F",
    "#FF7F9F",
    "#CC0033",
    "#CC667F",
    "#980026",
    "#984C5F",
    "#7F001F",
    "#7F3F4F",
    "#4C0013",
    "#4C262F",
    "#333333",
    "#5B5B5B",
    "#848484",
    "#ADADAD",
    "#D6D6D6",
    "#FFFFFF",
]


def get_rgbcolor(dxfcolor, parent_color="#000000"):
    """Returns hex color code corresponding to a color value

    dxfcolor     -- dxf code to convert to hex color code
                    0 (BYBLOCK) and 256 (BYLAYER) use parent_color
                    No more differentiation is currently done
                    Negative values are ignored (specification
                    allows layer to be hidden here)
                    Negative values also use parent_color
    parent_color -- hex color code from parent layer.
                    Use default color '#000000' if
                    parent layer color undefined.
    """
    rgbcolor = None
    if dxfcolor in range(1, len(COLORS)):
        rgbcolor = COLORS[dxfcolor]
    if not rgbcolor:
        rgbcolor = parent_color
    return rgbcolor


class ValueConstruct(defaultdict):
    """Store values from the DXF and provide them as named attributes"""

    values = {
        "1": ("text", "default"),
        "2": ("tag", "block_name"),
        "3": ("mtext",),
        "6": ("line_type",),
        "7": ("text_style",),
        "8": ("layer_name",),
        "10": ("x1",),
        "11": ("x2",),
        "13": ("x3",),
        "14": ("x4",),
        "20": ("y1",),
        "21": ("y2",),
        "23": ("y3",),
        "24": ("y4",),
        "40": ("scale", "knots", "radius", "width_ratio"),
        "41": ("ellipse_a1", "insert_scale_x", "mtext_width"),
        "42": ("ellipse_a2", "bulge", "insert_scale_y"),
        "50": ("angle",),
        "51": ("angle2",),
        "62": ("color",),
        "70": ("fill", "flags"),
        "71": ("attach_pos",),
        "72": ("edge_type",),
        "73": ("sweep",),  # ccw
        "92": ("path_type",),
        "93": ("num_edges",),
        "230": ("extrude",),
        "370": ("line_weight",),
    }
    attrs = dict([(name, a) for a, b in values.items() for name in b])

    def __init__(self):
        super().__init__(list)

    @classmethod
    def is_valid(cls, key):
        return key in cls.values

    def __getattr__(self, attr):
        is_list = attr.endswith("_list")
        key = attr[:-5] if is_list else attr
        if key in self.attrs:
            ret = self[self.attrs[key]]
            if not attr.endswith("_list"):
                return ret[0]
            return ret
        if attr.startswith("has_"):
            key = attr[4:]
            if key in self.attrs:
                return self.attrs[key] in self
        raise AttributeError(f"Can't find dxf attribute '{key}' {attr}")

    def __setattr__(self, attr, value):
        if not attr in self.attrs:
            raise AttributeError(f"Can't set bad dxf attribute '{attr}'")
        if not isinstance(value, list):
            value = [value]
        self[self.attrs[attr]] = value

    def adjust_coords(self, xmin, ymin, scale, extrude, height):
        """Adjust the x,y coordinates to fit on the page"""
        for xgrp in set(["10", "11", "13", "14"]) & set(self):  # scale/reflect x values
            for i in range(len(self[xgrp])):
                self[xgrp][i] = scale * (extrude * self[xgrp][i] - xmin)
        for ygrp in set(["20", "21", "23", "24"]) & set(self):  # scale y values
            for i in range(len(self[ygrp])):
                self[ygrp][i] = height - scale * (self[ygrp][i] - ymin)


export_viewport = False
export_endsec = False


def re_hex2unichar(m):
    # return unichr(int(m.group(1), 16))
    return chr(int(m.group(1), 16))


def formatStyle(style):
    return str(inkex.Style(style))


def export_text(vals):
    # mandatory group codes : (11, 12, 72, 73) (fit_x, fit_y, horizon, vertical)
    # TODO: position to display at by (x2,y2) according to 72(horizon),73(vertical)
    # groupcode 72:0(left),1(center),2(right),3(both side),4(middle),5(fit)
    # grouocode 73:0(standard),1(floor),2(center),3(ceiling)
    vals["71"].append(1)  # attach=pos left in mtext
    vals["70"].append(1)  # text: flags=1
    return export_mtext(vals)


def export_mtext(vals):
    # mandatory group codes : (1 or 3, 10, 20) (text, x, y)
    # TODO: text-format: \Font; \W; \Q; \L..\l etc
    if (vals.has_text or vals.has_mtext) and vals.has_x1 and vals.has_y1:
        x = vals.x1
        y = vals.y1
        # optional group codes : (21, 40, 50) (direction, text height mm, text angle)
        # optional group codes : 2: char style is defined at TABLES Section
        size = 12  # default fontsize in px
        if vals.has_scale:
            size = scale * textscale * vals.scale

        dx = dy = 0
        if not vals.has_flags:  # as mtext, putting in the box
            dy = size

        anchor = "start"
        if vals.has_attach_pos:
            if vals.attach_pos in (2, 5, 8):
                anchor = "middle"
            elif vals.attach_pos in (3, 6, 9):
                anchor = "end"
            if vals.attach_pos in (4, 5, 6):
                dy = size / 2
        # if vals.has_text_style and vals.text_style in style_font3 :
        #    attribs = {'x': '%f' % x, 'y': '%f' % y, 'style': 'font-size: %.3fpx; fill: %s; font-family: %s' \
        #            % (size, color, style_font3[vals.text_style])}
        # else :
        #    attribs = {'x': '%f' % x, 'y': '%f' % y, 'style': 'font-size: %.3fpx; fill: %s; font-family: %s' % (size, color, options.font)}
        attribs = {
            "x": "%f" % x,
            "y": "%f" % y,
            "style": "font-size: %.3fpx; fill: %s; font-family: %s; text-anchor: %s"
            % (size, color, options.font, anchor),
        }

        angle = 0  # default angle in degrees
        bVertical = False
        if vals.has_angle:  # TEXT only
            if vals.angle != 0:
                angle = vals.angle
            # attribs.update({'transform': 'rotate (%f %f %f)' % (-angle, x, y)})
        elif vals.has_y2 and vals.has_x2:
            # MTEXT
            # recover original data
            # (x,y)=(scale*(x-xmin), height-scale*(y-ymin)
            orgx = vals.x2 / scale + xmin
            orgy = -(vals.y2 - height) / scale + ymin
            unit = math.sqrt(orgy * orgy + orgx * orgx)
            if (unit < 1.01) and (unit > 0.99):
                ang1 = math.atan2(orgy, orgx)
                angle = 180 * ang1 / math.pi
            # attribs.update({'transform': 'rotate (%f %f %f)' % (-angle, x, y)})

        if vals.has_text_style and vals.text_style in style_direction:
            if style_direction[vals.text_style] & 4:
                # angle = -90
                # attribs.update({'transform': 'rotate (%f %f %f)' % (-angle, x, y)})
                bVertical = True
                angle = 0
                dx = size
                attribs = {
                    "x": "%f" % x,
                    "y": "%f" % y,
                    "style": "font-size: %.3fpx; fill: %s; font-family: %s; text-anchor: %s; writing-mode: tb"
                    % (size, color, options.font, anchor),
                }
        if angle != 0:
            attribs.update({"transform": "rotate (%f %f %f)" % (-angle, x, y)})

        node = layer.add(inkex.TextElement(**attribs))
        node.set("sodipodi:linespacing", "125%")
        text = ""
        if vals.has_mtext:
            text = "".join(vals.mtext_list)
        if vals.has_text:
            text += vals.text
        # folding long text
        if vals.has_mtext_width and vals.has_scale:
            if vals.mtext_width > 10.0 and vals.scale > 1.0:
                charsperline = vals.mtext_width * 2 / vals.scale  # or 1.6?
                nochars = int(charsperline)
                if len(text) > charsperline:
                    # plain text only no \P,{} better divide by space
                    if (text.find(r"\P") < 0) and (text.find(r"{") < 0):
                        pos = 0
                        while len(text) > pos:
                            text = text[:pos] + r"\P" + text[pos:]
                            pos += nochars + 2

        text = mtext_normalize(text)
        lines = 0
        found = text.find(r"\P")  # new line
        while found > -1:
            tspan = node.add(inkex.Tspan())
            if bVertical:
                tspan.set("y", "%f" % y)
                if lines > 0:
                    tspan.set("dx", "%f" % size)
            else:
                tspan.set("sodipodi:role", "line")
                if lines > 0:
                    tspan.set("x", x + dx)
                else:
                    tspan.set("dx", "%f" % dx)
                tspan.set("dy", "%f" % dy)
            # tspan.text = text[:found]
            text1 = text[:found]
            mtext_separate(node, tspan, text1)
            text = text[(found + 2) :]
            found = text.find(r"\P")
            lines += 1

        tspan = node.add(inkex.Tspan())
        if bVertical:
            tspan.set("y", "%f" % y)
            if lines > 0:
                tspan.set("dx", "%f" % dx)
        else:
            tspan.set("sodipodi:role", "line")
            if lines > 0:
                tspan.set("x", x + dx)
            else:
                tspan.set("dx", "%f" % dx)
            tspan.set("dy", "%f" % dy)
        # tspan.text = text
        text1 = text
        mtext_separate(node, tspan, text1)


def mtext_normalize(text):
    # {  \P  } -> {  }\P{  }
    found = text.find(r"\P")
    while found > -1:
        nest = False
        posL = text.rfind(r"{", 0, found)
        posR = text.rfind(r"}", 0, found)
        if posL > -1:
            if posR == -1:
                nest = True
            else:
                if posL > posR:
                    nest = True
        if nest:
            # paste }\P{
            control = ""
            if text[posL + 1] == "\\":
                posC = text.find(r";", posL)
                if posC != -1 and (posC - posL) < 20:
                    control = text[posL + 1 : posC + 1]
            text = text[:found] + r"}\P{" + control + text[found + 2 :]
        found = text.find(r"\P", found + 2)
    return text


def mtext_separate(node, tspan, text):
    # sparate aaa{bbb}(ccc) -> aaa,bbb.ccc
    tspanAdd = True
    found = text.find(r"{")
    while found > -1:
        if found == 0:
            found1 = text.find(r"}")
            if found1 < 1:
                break
            text1 = text[:found1]  # tspan
            text1 = text1[found + 1 :]
            if tspanAdd == False:
                tspan = node.add(inkex.Tspan())
            mtext_ctrl(tspan, text1)
            # tspan.text = text1 +'+1'
            tspanAdd = False
            text = text[found1 + 1 :]
            found = text.find(r"{")
        else:
            text1 = text[:found]  # tspan
            if tspanAdd == False:
                tspan = node.add(inkex.Tspan())
            mtext_ctrl(tspan, text1)
            # tspan.text = text1 +'+2'
            tspanAdd = False
            text = text[found:]
            found = 0

    if len(text) > 0:
        text1 = text
        if tspanAdd == False:
            tspan = node.add(inkex.Tspan())
        mtext_ctrl(tspan, text1)
        # tspan.text = text1 +'+3'
        tspanAdd = False


def mtext_ctrl(tspan, phrase):
    if len(phrase) == 0:
        return
    if phrase[0] != "\\":
        tspan.text = phrase
        return
    # if you'll add the function, you should remove the auto re.sub at setting group code:1
    if phrase[1].upper() in ("C", "H", "T", "Q", "W", "A"):
        # get the value
        found = phrase.find(r";")
        if found > 2:
            cvalue = phrase[:found]
            cvalue = cvalue[2:]
            try:
                value = float(cvalue)
            except ValueError:
                done = False
            else:
                done = True
                if phrase[1].upper() == "C":
                    i = int(value)
                    color = get_rgbcolor(i)
                    tspan.set("style", "stroke: %s" % color)
                elif phrase[1].upper() == "H":
                    value *= scale
                    tspan.set("style", "font-size: %.3fpx;" % value)
                elif phrase[1].upper() == "T":
                    tspan.set("style", "letter-spacing: %f;" % value)
                elif phrase[1].upper() == "A":
                    if value == 0:
                        tspan.set("dominant-baseline", "text-bottom")
                    elif value == 1:
                        tspan.set("dominant-baseline", "central")
                    elif value == 2:
                        tspan.set("dominant-baseline", "text-top")
                tspan.text = phrase[found + 1 :]
        else:
            tspan.text = phrase
    else:
        if phrase[1].upper() == "F":
            # get the value font-name & style & cut from text             2022.March
            # \FArial|b0|i0|c0|p0; b:bold,i:italic,c:charset,ppitch
            found = phrase.find(r";")
            if found > 2:
                cvalue = phrase[:found]
                tspan.text = phrase[found + 1 :]
        else:
            tspan.text = phrase


def export_point(vals, w):
    # mandatory group codes : (10, 20) (x, y)
    if vals.has_x1 and vals.has_y1:
        if vals["70"]:
            inkex.errormsg("$PDMODE is ignored. A point is displayed as normal.")
        if options.gcodetoolspoints:
            generate_gcodetools_point(vals.x1, vals.y1)
        else:
            generate_ellipse(vals.x1, vals.y1, w / 2, 0.0, 1.0, 0.0, 0.0)


def export_line(vals):
    """Draw a straight line from the dxf"""
    # mandatory group codes : (10, 11, 20, 21) (x1, x2, y1, y2)
    if vals.has_x1 and vals.has_x2 and vals.has_y1 and vals.has_y2:
        path = inkex.PathElement()
        path.style = style
        path.path = "M %f,%f %f,%f" % (vals.x1, vals.y1, vals.x2, vals.y2)
        layer.add(path)


def export_solid(vals):
    # arrows of dimension
    # mandatory group codes : (10, 11, 12, 20, 21, 22) (x1, x2, x3, y1, y2, y3)
    # TODO: 4th point
    if (
        vals.has_x1
        and vals.has_x2
        and vals.has_x3
        and vals.has_y1
        and vals.has_y2
        and vals.has_y3
    ):
        path = inkex.PathElement()
        path.style = style
        path.path = "M %f,%f %f,%f %f,%f z" % (
            vals.x1,
            vals.y1,
            vals.x2,
            vals.y2,
            vals.x3,
            vals.y3,
        )
        layer.add(path)


def export_spline(vals):
    # see : http://www.mactech.com/articles/develop/issue_25/schneider.html
    # mandatory group codes : (10, 20, 40, 70) (x[], y[], knots[], flags)
    if (
        vals.has_flags
        and vals.has_knots
        and vals.x1_list
        and len(vals.x1_list) == len(vals.y1_list)
    ):
        knots = vals.knots_list
        ctrls = len(vals.x1_list)
        if ctrls > 3 and len(knots) == ctrls + 4:  # cubic
            if ctrls > 4:
                for i in range(len(knots) - 5, 3, -1):
                    if knots[i] != knots[i - 1] and knots[i] != knots[i + 1]:
                        a0 = (knots[i] - knots[i - 2]) / (knots[i + 1] - knots[i - 2])
                        a1 = (knots[i] - knots[i - 1]) / (knots[i + 2] - knots[i - 1])
                        vals.x1_list.insert(
                            i - 1,
                            (1.0 - a1) * vals.x1_list[i - 2] + a1 * vals.x1_list[i - 1],
                        )
                        vals.y1_list.insert(
                            i - 1,
                            (1.0 - a1) * vals.y1_list[i - 2] + a1 * vals.y1_list[i - 1],
                        )
                        vals.x1_list[i - 2] = (1.0 - a0) * vals.x1_list[
                            i - 3
                        ] + a0 * vals.x1_list[i - 2]
                        vals.y1_list[i - 2] = (1.0 - a0) * vals.y1_list[
                            i - 3
                        ] + a0 * vals.y1_list[i - 2]
                        knots.insert(i, knots[i])
                for i in range(len(knots) - 6, 3, -2):
                    if (
                        knots[i] != knots[i + 2]
                        and knots[i - 1] != knots[i + 1]
                        and knots[i - 2] != knots[i]
                    ):
                        a1 = (knots[i] - knots[i - 1]) / (knots[i + 2] - knots[i - 1])
                        vals.x1_list.insert(
                            i - 1,
                            (1.0 - a1) * vals.x1_list[i - 2] + a1 * vals.x1_list[i - 1],
                        )
                        vals.y1_list.insert(
                            i - 1,
                            (1.0 - a1) * vals.y1_list[i - 2] + a1 * vals.y1_list[i - 1],
                        )
            ctrls = len(vals.x1_list)
            path = "M %f,%f" % (vals.x1, vals.y1)
            for i in range(0, (ctrls - 1) // 3):
                path += " C %f,%f %f,%f %f,%f" % (
                    vals.x1_list[3 * i + 1],
                    vals.y1_list[3 * i + 1],
                    vals.x1_list[3 * i + 2],
                    vals.y1_list[3 * i + 2],
                    vals.x1_list[3 * i + 3],
                    vals.y1_list[3 * i + 3],
                )
            if vals.flags & 1:  # closed path
                path += " z"
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)
        if ctrls == 3 and len(knots) == 6:  # quadratic
            path = "M %f,%f Q %f,%f %f,%f" % (
                vals.x1,
                vals.y1,
                vals.x1_list[1],
                vals.y1_list[1],
                vals.x1_list[2],
                vals.y1_list[2],
            )
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)
        if ctrls == 5 and len(knots) == 8:  # spliced quadratic
            path = "M %f,%f Q %f,%f %f,%f Q %f,%f %f,%f" % (
                vals.x1,
                vals.y1,
                vals.x1_list[1],
                vals.y1_list[1],
                vals.x1_list[2],
                vals.y1_list[2],
                vals.x1_list[3],
                vals.y1_list[3],
                vals.x1_list[4],
                vals.y1_list[4],
            )
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)


def export_circle(vals):
    # mandatory group codes : (10, 20, 40) (x, y, radius)
    if vals.has_x1 and vals.has_y1 and vals.has_radius:
        generate_ellipse(vals.x1, vals.y1, scale * vals.radius, 0.0, 1.0, 0.0, 0.0)


def export_arc(vals):
    # mandatory group codes : (10, 20, 40, 50, 51) (x, y, radius, angle1, angle2)
    if (
        vals.has_x1
        and vals.has_y1
        and vals.has_radius
        and vals.has_angle
        and vals.has_angle2
    ):
        generate_ellipse(
            vals.x1,
            vals.y1,
            scale * vals.radius,
            0.0,
            1.0,
            vals.angle * math.pi / 180.0,
            vals.angle2 * math.pi / 180.0,
        )


def export_ellipse(vals):
    # mandatory group codes : (10, 11, 20, 21, 40, 41, 42) (xc, xm, yc, ym, width ratio, angle1, angle2)
    if (
        vals.has_x1
        and vals.has_x2
        and vals.has_y1
        and vals.has_y2
        and vals.has_width_ratio
        and vals.has_ellipse_a1
        and vals.has_ellipse_a2
    ):
        # generate_ellipse(vals.x1, vals.y1, scale*vals.x2, scale*vals.y2, vals.width_ratio, vals.ellipse_a1, vals.ellipse_a2)
        # vals are through adjust_coords : recover proper value
        # (x,y)=(scale*x-xmin, height-scale*y-ymin)
        x2 = vals.x2 + xmin
        y2 = -vals.y2 + ymin + height
        generate_ellipse(
            vals.x1, vals.y1, x2, y2, vals.width_ratio, vals.ellipse_a1, vals.ellipse_a2
        )


def export_leader(vals):
    # mandatory group codes : (10, 20) (x, y)
    if vals.has_x1 and vals.has_y1:
        if len(vals.x1_list) > 1 and len(vals.y1_list) == len(vals.x1_list):
            path = "M %f,%f" % (vals.x1, vals.y1)
            for i in range(1, len(vals.x1_list)):
                path += " %f,%f" % (vals.x1_list[i], vals.y1_list[i])
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)


def export_polyline(vals):
    return export_lwpolyline(vals)


def export_lwpolyline(vals):
    # mandatory group codes : (10, 20, 70) (x, y, flags)
    if vals.has_x1 and vals.has_y1 and vals.has_flags:
        if len(vals.x1_list) > 1 and len(vals.y1_list) == len(vals.x1_list):
            # optional group codes : (42) (bulge)
            iseqs = 0
            ibulge = 0
            if vals.flags & 1:  # closed path
                seqs.append("20")
                vals.x1_list.append(vals.x1)
                vals.y1_list.append(vals.y1)
            while seqs[iseqs] != "20":
                iseqs += 1
            path = "M %f,%f" % (vals.x1, vals.y1)
            xold = vals.x1
            yold = vals.y1
            for i in range(1, len(vals.x1_list)):
                bulge = 0
                iseqs += 1
                while seqs[iseqs] != "20":
                    if seqs[iseqs] == "42":
                        bulge = vals.bulge_list[ibulge]
                        ibulge += 1
                    iseqs += 1
                if bulge:
                    sweep = 0  # sweep CCW
                    if bulge < 0:
                        sweep = 1  # sweep CW
                        bulge = -bulge
                    large = 0  # large-arc-flag
                    if bulge > 1:
                        large = 1
                    r = math.sqrt(
                        (vals.x1_list[i] - xold) ** 2 + (vals.y1_list[i] - yold) ** 2
                    )
                    r = 0.25 * r * (bulge + 1.0 / bulge)
                    path += " A %f,%f 0.0 %d %d %f,%f" % (
                        r,
                        r,
                        large,
                        sweep,
                        vals.x1_list[i],
                        vals.y1_list[i],
                    )
                else:
                    path += " L %f,%f" % (vals.x1_list[i], vals.y1_list[i])
                xold = vals.x1_list[i]
                yold = vals.y1_list[i]
            if vals.flags & 1:  # closed path
                path += " z"
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)


def export_hatch(vals):
    # mandatory group codes : (10, 20, 70, 72, 92, 93) (x, y, fill, Edge Type, Path Type, Number of edges)
    # TODO: Hatching Pattern
    if (
        vals.has_x1
        and vals.has_y1
        and vals.has_fill
        and vals.has_edge_type
        and vals.has_path_type
        and vals.has_num_edges
    ):
        if len(vals.x1_list) > 1 and len(vals.y1_list) == len(vals.x1_list):
            # optional group codes : (11, 21, 40, 50, 51, 73) (x, y, r, angle1, angle2, CCW)
            i10 = 1  # count start points
            i11 = 0  # count line end points
            i40 = 0  # count circles
            i72 = 0  # count edge type flags
            path = ""
            for i in range(0, len(vals.num_edges_list)):
                xc = vals.x1_list[i10]
                yc = vals.y1_list[i10]
                if vals.edge_type_list[i72] == 2:  # arc
                    rm = scale * vals.radius_list[i40]
                    a1 = vals.angle_list[i40]
                    path += "M %f,%f " % (
                        xc + rm * math.cos(a1 * math.pi / 180.0),
                        yc + rm * math.sin(a1 * math.pi / 180.0),
                    )
                else:
                    a1 = 0
                    path += "M %f,%f " % (xc, yc)
                for j in range(0, vals.num_edges_list[i]):
                    if vals.path_type_list[i] & 2:  # polyline
                        if j > 0:
                            path += "L %f,%f " % (vals.x1_list[i10], vals.y1_list[i10])
                        if j == vals.path_type_list[i] - 1:
                            i72 += 1
                    elif vals.edge_type_list[i72] == 2:  # arc
                        xc = vals.x1_list[i10]
                        yc = vals.y1_list[i10]
                        rm = scale * vals.radius_list[i40]
                        a2 = vals.angle2_list[i40]
                        diff = (a2 - a1 + 360) % 360
                        sweep = 1 - vals.sweep_list[i40]  # sweep CCW
                        large = 0  # large-arc-flag
                        if diff:
                            path += "A %f,%f 0.0 %d %d %f,%f " % (
                                rm,
                                rm,
                                large,
                                sweep,
                                xc + rm * math.cos(a2 * math.pi / 180.0),
                                yc + rm * math.sin(a2 * math.pi / 180.0),
                            )
                        else:
                            path += "A %f,%f 0.0 %d %d %f,%f " % (
                                rm,
                                rm,
                                large,
                                sweep,
                                xc + rm * math.cos((a1 + 180.0) * math.pi / 180.0),
                                yc + rm * math.sin((a1 + 180.0) * math.pi / 180.0),
                            )
                            path += "A %f,%f 0.0 %d %d %f,%f " % (
                                rm,
                                rm,
                                large,
                                sweep,
                                xc + rm * math.cos(a1 * math.pi / 180.0),
                                yc + rm * math.sin(a1 * math.pi / 180.0),
                            )
                        i40 += 1
                        i72 += 1
                    elif vals.edge_type_list[i72] == 1:  # line
                        path += "L %f,%f " % (vals.x2_list[i11], vals.y2_list[i11])
                        i11 += 1
                        i72 += 1
                    i10 += 1
                path += "z "
            if vals.has_fill:
                style = formatStyle({"fill": "%s" % color})
            else:
                style = formatStyle({"fill": "url(#Hatch)", "fill-opacity": "1.0"})
            attribs = {"d": path, "style": style}
            etree.SubElement(layer, "path", attribs)


def export_dimension(vals):
    # mandatory group codes : (10, 11, 13, 14, 20, 21, 23, 24) (x1..4, y1..4)
    # block_name: dimension definition for 10mm
    if vals.has_x1 and vals.has_x2 and vals.has_y1 and vals.has_y2:
        if vals.has_block_name:
            attribs = {
                inkex.addNS("href", "xlink"): "#%s" % (vals.block_name)
            }  # not use quote because name *D2 etc. changed to %2AD2
            tform = "translate(0 0)"
            # if vals.has_angle :
            #    tform += ' rotate(%f,%f,%f)' % (vals.angle,vals.x4,vals.y4)
            attribs.update({"transform": tform})
            etree.SubElement(layer, "use", attribs)
        else:
            # TODO: improve logic when INSERT in BLOCK
            dx = abs(vals.x1 - vals.x3)
            dy = abs(vals.y1 - vals.y3)
            if (vals.x1 == vals.x4) and dx > 0.00001:
                d = dx / scale
                dy = 0
                path = "M %f,%f %f,%f" % (vals.x1, vals.y1, vals.x3, vals.y1)
            elif (vals.y1 == vals.y4) and dy > 0.00001:
                d = dy / scale
                dx = 0
                path = "M %f,%f %f,%f" % (vals.x1, vals.y1, vals.x1, vals.y3)
            else:
                return
            attribs = {
                "d": path,
                "style": style
                + "; marker-start: url(#DistanceX); marker-end: url(#DistanceX); stroke-width: 0.25px",
            }
            etree.SubElement(layer, "path", attribs)
            x = vals.x2
            y = vals.y2
            size = 12  # default fontsize in px
            if vals.has_mtext:
                if vals.mtext in DIMTXT:
                    size = scale * textscale * DIMTXT[vals.mtext]
                    if size < 2:
                        size = 2
            attribs = {
                "x": "%f" % x,
                "y": "%f" % y,
                "style": "font-size: %.3fpx; fill: %s; font-family: %s; text-anchor: middle; text-align: center"
                % (size, color, options.font),
            }
            if dx == 0:
                attribs.update({"transform": "rotate (%f %f %f)" % (-90, x, y)})
            node = etree.SubElement(layer, "text", attribs)
            tspan = node.add(inkex.Tspan())
            tspan.set("sodipodi:role", "line")
            tspan.text = str(float("%.2f" % d))


def export_insert(vals):
    # mandatory group codes : (2, 10, 20) (block name, x, y)
    # TODO: repeat by row and column
    # (times,interval)= row(70,44), column(71,45)

    if vals.has_block_name and vals.has_x1 and vals.has_y1:
        # vals are through adjust_coords except block
        # block (x,y)=(0,0) : (scale*x-xmin, height-scale*y-ymin)
        # translate(move x units,move y units)
        # 2021.6  translate..ok  scale..x  rotate X
        # as scale, the line is wider ->same width  -> you should fix
        global height
        cx = scale * xmin  # transorm-origin:
        cy = scale * ymin + height  # center of rotation

        x = vals.x1 + scale * xmin
        y = vals.y1 - scale * ymin - height
        ixscale = iyscale = 1
        if vals.has_insert_scale_y:
            ixscale = vals.insert_scale_x
        if vals.has_insert_scale_y:
            iyscale = vals.insert_scale_y
        x += cx * (iyscale - 1)
        y -= cy * (iyscale - 1)

        elem = layer.add(inkex.Use())
        elem.set(
            inkex.addNS("href", "xlink"),
            "#" + quote(vals.block_name.replace(" ", "_").encode("utf-8")),
        )

        # add style stroke-width=1px for reducing thick line
        fwide = abs(0.5 / ixscale)  # better to use w/ixscale
        elem.style["stroke-width"] = "%.3fpx" % fwide

        elem.transform.add_translate(x, y)
        if vals.has_insert_scale_x and vals.has_insert_scale_y:
            elem.transform.add_scale(ixscale, iyscale)
        if vals.has_angle:
            rotated_angle = vals.angle
            if ixscale * iyscale > 0:
                rotated_angle = 360 - rotated_angle
            elem.transform.add_rotate(rotated_angle, -cx, cy)


def export_block(vals):
    # mandatory group codes : (2) (block name)
    if vals.has_block_name:
        global block
        block = etree.SubElement(
            defs, "symbol", {"id": vals.block_name.replace(" ", "_")}
        )


def export_endblk(vals):
    global block
    block = defs  # initiallize with dummy


def export_attdef(vals):
    # mandatory group codes : (1, 2) (default, tag)
    if vals.has_default and vals.has_tag:
        vals.text_list.append(vals.tag)
        export_mtext(vals)


def generate_ellipse(xc, yc, xm, ym, w, a1, a2):
    rm = math.sqrt(xm * xm + ym * ym)
    a = math.atan2(ym, xm)  # x-axis-rotation
    diff = (a2 - a1 + 2 * math.pi) % (2 * math.pi)
    if abs(diff) > 0.0000001 and abs(diff - 2 * math.pi) > 0.0000001:  # open arc
        large = 0  # large-arc-flag
        if diff > math.pi:
            large = 1
        xt = rm * math.cos(a1)
        yt = w * rm * math.sin(a1)
        x1 = xt * math.cos(a) - yt * math.sin(a)
        y1 = xt * math.sin(a) + yt * math.cos(a)
        xt = rm * math.cos(a2)
        yt = w * rm * math.sin(a2)
        x2 = xt * math.cos(a) - yt * math.sin(a)
        y2 = xt * math.sin(a) + yt * math.cos(a)
        path = "M %f,%f A %f,%f %f %d 0 %f,%f" % (
            xc + x1,
            yc - y1,
            rm,
            w * rm,
            -180.0 * a / math.pi,
            large,
            xc + x2,
            yc - y2,
        )
    else:  # closed arc
        path = "M %f,%f A %f,%f %f 0, 0 %f,%f A %f,%f %f 0, 0 %f,%f z" % (
            xc + xm,
            yc - ym,
            rm,
            w * rm,
            -180.0 * a / math.pi,
            xc - xm,
            yc + ym,
            rm,
            w * rm,
            -180.0 * a / math.pi,
            xc + xm,
            yc - ym,
        )
    attribs = {"d": path, "style": style}
    etree.SubElement(layer, "path", attribs)


def generate_gcodetools_point(xc, yc):
    elem = layer.add(inkex.PathElement())
    elem.style = "stroke:none;fill:#ff0000"
    elem.set("inkscape:dxfpoint", "1")
    elem.path = (
        "m %s,%s 2.9375,-6.34375 0.8125,1.90625 6.84375,-6.84375 0,0 0.6875,0.6875 -6.84375,6.84375 1.90625,0.8125 z"
        % (xc, yc)
    )


#   define DXF Entities and specify which Group Codes to monitor


class DxfInput(inkex.InputExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab", default="options")
        pars.add_argument("--scalemethod", default="manual")
        pars.add_argument("--scale", default="1.0")
        pars.add_argument("--textscale", default="1.0")
        pars.add_argument("--xmin", default="0.0")
        pars.add_argument("--ymin", default="0.0")
        pars.add_argument("--gcodetoolspoints", default=False, type=inkex.Boolean)
        pars.add_argument("--encoding", dest="input_encode", default="latin_1")
        pars.add_argument("--font", default="Arial")

    def load(self, stream):
        return stream

    def effect(self):
        global options
        global defs
        global entity
        global seqs
        global style
        global layer
        global scale
        global textscale
        global color
        global extrude
        global xmin
        global ymin
        global height
        global DIMTXT
        global block
        global svg
        global style_font3
        global style_direction
        global be_extrude

        options = self.options

        doc = self.get_template(width=210 * 96 / 25.4, height=297 * 96 / 25.4)
        svg = doc.getroot()
        defs = svg.defs
        marker = etree.SubElement(
            defs,
            "marker",
            {
                "id": "DistanceX",
                "orient": "auto",
                "refX": "0.0",
                "refY": "0.0",
                "style": "overflow:visible",
            },
        )
        etree.SubElement(
            marker,
            "path",
            {
                "d": "M 3,-3 L -3,3 M 0,-5 L  0,5",
                "style": "stroke:#000000; stroke-width:0.5",
            },
        )
        pattern = etree.SubElement(
            defs,
            "pattern",
            {
                "id": "Hatch",
                "patternUnits": "userSpaceOnUse",
                "width": "8",
                "height": "8",
                "x": "0",
                "y": "0",
            },
        )
        etree.SubElement(
            pattern,
            "path",
            {
                "d": "M8 4 l-4,4",
                "stroke": "#000000",
                "stroke-width": "0.25",
                "linecap": "square",
            },
        )
        etree.SubElement(
            pattern,
            "path",
            {
                "d": "M6 2 l-4,4",
                "stroke": "#000000",
                "stroke-width": "0.25",
                "linecap": "square",
            },
        )
        etree.SubElement(
            pattern,
            "path",
            {
                "d": "M4 0 l-4,4",
                "stroke": "#000000",
                "stroke-width": "0.25",
                "linecap": "square",
            },
        )

        def _get_line(strip=True):
            line = self.document.readline()
            if strip:
                line = line.strip()
            else:
                line = line.rstrip(b"\r\n")
            return line.decode(options.input_encode)

        def get_line():
            l1 = _get_line()
            if l1 in ("1", "2", "3", "6", "7", "8"):  # text value
                # text entity, do not strip
                return l1, _get_line(False)
            return l1, _get_line()

        def get_binary_line() -> Tuple[str, str]:
            stream = self.document
            # Data types inferred from
            # https://help.autodesk.com/view/OARX/2023/ENU/?guid=GUID-2553CF98-44F6-4828-82DD-FE3BC7448113

            try:
                key = struct.unpack("<h", stream.read(2))[0]
                if (
                    key <= 9
                    or 100 <= key <= 109
                    or 300 <= key <= 309
                    or 320 <= key <= 369
                    or 390 <= key <= 399
                    or 410 <= key <= 419
                    or 430 <= key <= 439
                    or 470 <= key <= 481
                    or 999 <= key <= 1009
                ):
                    string_bytes = bytearray()
                    while True:
                        byte = stream.read(1)
                        if byte == b"\x00" or len(byte) == 0:
                            value = string_bytes.decode().replace("\t", "")
                            break
                        string_bytes.extend(byte)
                elif (
                    10 <= key <= 59
                    or 110 <= key <= 149
                    or 210 <= key <= 239
                    or 460 <= key <= 469
                    or 1010 <= key <= 1059
                ):
                    value = struct.unpack("d", stream.read(8))[0]
                elif (
                    60 <= key <= 79
                    or 170 <= key <= 179
                    or 270 <= key <= 289
                    or 370 <= key <= 389
                    or 400 <= key <= 409
                    or 1060 <= key <= 1070
                ):
                    value = struct.unpack("<h", stream.read(2))[0]
                elif (
                    80 <= key <= 99
                    or 420 <= key <= 429
                    or 440 <= key <= 459
                    or key == 1071
                ):
                    value = struct.unpack("<i", stream.read(4))[0]
                elif 160 <= key <= 169:
                    value = struct.unpack("<q", stream.read(8))[0]
                elif 290 <= key <= 299:
                    value = struct.unpack("?", stream.read(1))[0]
                elif 310 <= key <= 319:
                    # binary data
                    length = struct.unpack("<B", stream.read(1))[0]
                    value = stream.read(length)
                else:
                    inkex.errormsg(
                        _(
                            "Encountered key of unknown format, id={0} while parsing DXF. This is probably a bug."
                        ).format(key)
                    )
                return str(key), str(value)
            except struct.error:
                return "", ""
                # EOF

        def get_group(group):
            line = get_line()
            if line[0] == group:
                return float(line[1])
            return 0.0

        xmax = xmin = ymin = 0.0
        ltscale = 1.0  # $LTSCALE:global scale of line-style
        height = 297.0 * 96.0 / 25.4  # default A4 height in pixels
        measurement = 0  # default inches
        flag = 0  # (0, 1, 2, 3, 4) = (none, LAYER, LTYPE, DIMTXT, STYLE)
        layer_colors = {}  # store colors by layer
        layer_nodes = {}  # store nodes by layer
        linetypes = {}  # store linetypes by name
        DIMTXT = {}  # store DIMENSION text sizes
        # style_name = {}     # style name
        style_font3 = {}  # style font 1byte
        style_font4 = {}  # style font 2byte
        style_direction = {}  # style display direction
        be_extrude = False
        first_line = _get_line()

        if first_line == "AutoCAD Binary DXF":
            magic = self.document.read(2)
            if not magic == b"\x1a\x00":
                inkex.AbortExtension(_("Binary DXF file has unexpected header."))
            get_line = get_binary_line
            line = [first_line, ""]
        else:
            line = [first_line, _get_line()]

        inENTITIES = False
        style_name = "*"
        layername = None
        linename = None
        stylename = None
        style_name = None
        errno = 0
        pdmode_err = False
        while line[0] and line[1] != "BLOCKS":
            line = get_line()
            if line[1] == "ENTITIES":  # no BLOCK SECTION
                inENTITIES = True
                break
            if line[1] == "$PDMODE" and not pdmode_err:
                inkex.errormsg("$PDMODE is ignored. A point is displayed as normal.")
                pdmode_err = True
            if options.scalemethod == "file":
                if line[1] == "$MEASUREMENT":
                    measurement = get_group("70")
            elif options.scalemethod == "auto":
                if line[1] == "$EXTMIN":
                    xmin = get_group("10")
                    ymin = get_group("20")
                if line[1] == "$EXTMAX":
                    xmax = get_group("10")
            if line[1] == "$LTSCALE":
                ltscale = get_group("40")
            if flag == 1 and line[0] == "2":
                layername = line[1]
                layer_nodes[layername] = svg.add(inkex.Layer.new(layername))
            if flag == 2 and line[0] == "2":
                linename = line[1]
                linetypes[linename] = []
            if flag == 3 and line[0] == "2":
                stylename = line[1]
            if flag == 4 and line[0] == "2":
                style_name = line[1]
                style_font3[style_name] = []
                style_font4[style_name] = []
                style_direction[style_name] = []
            if line[0] == "2" and line[1] == "LAYER":
                flag = 1
            if line[0] == "2" and line[1] == "LTYPE":
                flag = 2
            if line[0] == "2" and line[1] == "DIMSTYLE":
                flag = 3
            if line[0] == "2" and line[1] == "STYLE":
                flag = 4
            if flag == 1 and line[0] == "62":
                if layername is None:
                    errno = 1
                    break
                layer_colors[layername] = int(line[1])
            if flag == 2 and line[0] == "49":
                if linename is None:
                    errno = 2
                    break
                linetypes[linename].append(float(line[1]))
            if flag == 3 and line[0] == "140":
                if stylename is None:
                    errno = 3
                    break
                DIMTXT[stylename] = float(line[1])
            if flag == 4 and line[0] == "3":
                if style_name is None:
                    errno = 4
                    break
                style_font3[style_name].append(line[1])
            if flag == 4 and line[0] == "4":
                if style_name is None:
                    errno = 4
                    break
                style_font4[style_name].append(line[1])
            if flag == 4 and line[0] == "70":  # not no of STYLE
                if style_name != "*":
                    style_direction[style_name] = int(line[1])
            if line[0] == "0" and line[1] == "ENDTAB":
                flag = 0
        if errno != 0:
            if errno == 1:
                errMsg = "LAYER"
            elif errno == 2:
                errMsg = "LTYPE"
            elif errno == 3:
                errMsg = "DIMSTYLE"
            else:  # errno == 4
                errMsg = "STYLE"
            inkex.errormsg(
                "Import stopped. DXF is incorrect.\ngroup code 2 ("
                + errMsg
                + ") is missing"
            )
            self.document = doc
            return

        if options.scalemethod == "file":
            scale = 25.4  # default inches
            if measurement == 1.0:
                scale = 1.0  # use mm
        elif options.scalemethod == "auto":
            scale = 1.0
            if xmax > xmin:
                scale = 210.0 / (xmax - xmin)  # scale to A4 width
        else:
            scale = float(options.scale)  # manual scale factor
            xmin = float(options.xmin)
            ymin = float(options.ymin)
        svg.desc = "%s - scale = %f, origin = (%f, %f), method = %s" % (
            os.path.basename(options.input_file),
            scale,
            xmin,
            ymin,
            options.scalemethod,
        )
        scale *= 96.0 / 25.4  # convert from mm to pixels
        textscale = float(options.textscale)

        if "0" not in layer_nodes:
            layer_nodes["0"] = svg.add(inkex.Layer.new("0"))

            layer_colors["0"] = 7

        for linename in linetypes.keys():  # scale the dashed lines
            linetype = ""
            for length in linetypes[linename]:
                if length == 0:  # test for dot
                    linetype += " 0.5,"
                else:
                    linetype += "%.4f," % math.fabs(length * scale * ltscale)
            if linetype == "":
                linetypes[linename] = "stroke-linecap: round"
            else:
                linetypes[linename] = "stroke-dasharray:" + linetype

        entity = ""
        block = defs  # initiallize with dummy
        while line[0] and (line[1] != "ENDSEC" or not inENTITIES):
            line = get_line()
            if line[1] == "ENTITIES":
                inENTITIES = True
            if entity and vals.is_valid(line[0]):
                seqs.append(line[0])  # list of group codes
                if line[0] in ("1", "2", "3", "6", "7", "8"):  # text value
                    # TODO: if add funs of export_mtext, delete the line
                    val = line[1].replace(r"\~", " ")
                    # val = re.sub(r"\\A.*;", "", val)
                    # val = re.sub(r'\\H.*;', '', val)
                    val = re.sub(r"\^I", "", val)
                    val = re.sub(r"{\\L", "", val)
                    # val = re.sub(r'}', '', val)  {\\C; '}' in mtext
                    val = re.sub(r"\\S.*;", "", val)
                    val = re.sub(r"\\W.*;", "", val)
                    val = val
                    val = re.sub(r"\\U\+([0-9A-Fa-f]{4})", re_hex2unichar, val)
                elif line[0] in ("62", "70", "92", "93"):
                    val = int(line[1])
                else:  # unscaled float value
                    val = float(line[1])
                vals[line[0]].append(val)
            elif has_export(line[1]):
                if has_export(entity):
                    if block != defs:  # in a BLOCK
                        layer = block
                    elif vals.has_layer_name:  # use Common Layer Name
                        if not vals.layer_name:
                            vals.layer_name = "0"  # use default name
                        if vals.layer_name not in layer_nodes:
                            # attribs = {inkex.addNS('groupmode','inkscape') :
                            #    'layer', inkex.addNS('label','inkscape') : '%s' % vals.layer_name}
                            # layer_nodes[vals.layer_name] = etree.SubElement(doc.getroot(), 'g', attribs)
                            layer_nodes[vals.layer_name] = svg.add(
                                inkex.Layer.new(vals.layer_name)
                            )
                        layer = layer_nodes[vals.layer_name]
                    color = "#000000"  # default color
                    if vals.has_layer_name:
                        if vals.layer_name in layer_colors:
                            color = get_rgbcolor(layer_colors[vals.layer_name], color)
                    if vals.has_color:  # Common Color Number
                        color = get_rgbcolor(vals.color, color)
                    style = formatStyle({"stroke": "%s" % color, "fill": "none"})
                    w = 0.5  # default lineweight for POINT
                    if vals.has_line_weight:  # Common Lineweight
                        if vals.line_weight > 0:
                            w = 96.0 / 25.4 * vals.line_weight / 100.0
                            w *= scale  # real wide : line_weight /144 inch
                            if w < 0.5:
                                w = 0.5
                            if (
                                block == defs
                            ):  # not in a BLOCK for INSERT except stroke-width 2021.july
                                style = formatStyle(
                                    {
                                        "stroke": "%s" % color,
                                        "fill": "none",
                                        "stroke-width": "%.3f" % w,
                                    }
                                )
                    if vals.has_line_type:  # Common Linetype
                        if vals.line_type in linetypes:
                            style += ";" + linetypes[vals.line_type]
                    extrude = 1.0
                    if vals.has_extrude:
                        if (entity != "LINE") and (entity != "POINT"):
                            extrude = float(vals.extrude)
                            if extrude < 1.0:
                                be_extrude = True

                    vals.adjust_coords(xmin, ymin, scale, extrude, height)

                    if extrude == -1.0:  # reflect angles
                        if vals.has_angle and vals.has_angle2:
                            vals.angle2, vals.angle = (
                                180.0 - vals.angle,
                                180.0 - vals.angle2,
                            )
                    exporter = get_export(entity)
                    if exporter:
                        if entity == "POINT":
                            exporter(vals, w)
                        else:
                            exporter(vals)

                if line[1] == "POLYLINE":
                    inVertexs = False
                    entity = "LWPOLYLINE"
                    vals = ValueConstruct()
                    seqs = []
                    flag70 = 0  # default closed-line or not
                    val8 = "0"  # default layer name
                    val10 = 0  # x
                    val20 = 0  # y
                    val42 = 0  # bulge
                    valid = True
                    while line[0] and (line[1] != "SEQEND"):
                        line = get_line()
                        if line[1] == "VERTEX":
                            if inVertexs == True:
                                if valid:
                                    seqs.append("10")
                                    vals["10"].append(val10)
                                    seqs.append("20")
                                    vals["20"].append(val20)
                                    seqs.append("42")
                                    vals["42"].append(val42)
                                    val42 = 0
                            inVertexs = True
                            valid = True
                        if inVertexs == False:
                            if line[0] == "6":  # 6:line style
                                seqs.append(line[0])
                                vals[line[0]].append(line[1])
                            if line[0] == "8":  # 8:layer
                                val8 = line[1]
                            if line[0] == "70":  # flag
                                flag70 = int(line[1])
                        else:
                            if line[0] == "70":
                                if int(line[1]) == 16:  # control point
                                    valid = False
                            if line[0] in ("10", "20", "42"):  # vertexs
                                val = float(line[1])
                                if line[0] == "10":
                                    val10 = val
                                elif line[0] == "20":
                                    val20 = val
                                else:
                                    val42 = val
                    if valid:
                        seqs.append("8")  # layer_name
                        vals["8"].append(val8)
                        seqs.append("10")
                        vals["10"].append(val10)
                        seqs.append("20")
                        vals["20"].append(val20)
                        seqs.append("42")  # bulge
                        vals["42"].append(val42)
                    seqs.append("70")  # closed line?
                    vals["70"].append(flag70)
                    continue

                entity = line[1]
                vals = ValueConstruct()
                seqs = []

        #     for debug
        # tree = etree.ElementTree(svg)
        # tree.write('c:\Python\svgCH2.xml')
        if be_extrude:
            inkex.errormsg(
                _(
                    "An object that has the extrude parameter set was detected. "
                    "The imported figure may be displayed incorrectly."
                )
            )
        self.document = doc


def get_export(opt):
    return globals().get("export_" + opt.lower(), None)


def has_export(opt):
    return get_export(opt) is not None


if __name__ == "__main__":
    DxfInput().run()
