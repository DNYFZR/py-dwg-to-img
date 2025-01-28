# coding=utf-8
#
# Copyright (C) 2011 Karlisson Bezerra <contact@hacktoon.com>
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
Element parsing and context for ink2canvas extensions
"""

from __future__ import unicode_literals
import math

import inkex
from inkex.localization import inkex_gettext as _


# pylint: disable=missing-function-docstring, missing-class-docstring
# pylint: disable=too-few-public-methods


class Element:
    """Base Element"""

    def __init__(self, node):
        self.node = node

    def attr(self, val):
        """Get attribute"""
        try:
            attr = float(self.node.get(val))
        except (ValueError, TypeError, AttributeError):
            attr = self.node.get(val)
        return attr


class GradientDef(Element):
    def __init__(self, node, stops):
        super().__init__(node)
        self.stops = stops


class LinearGradientDef(GradientDef):
    def get_data(self):
        # pylint: disable=unused-variable
        x1 = self.attr("x1")
        y1 = self.attr("y1")
        x2 = self.attr("x2")
        y2 = self.attr("y2")
        # self.create_linear_gradient(href, x1, y1, x2, y2)

    def draw(self):
        pass


class RadialGradientDef(GradientDef):
    def get_data(self):
        # pylint: disable=unused-variable
        cx = self.attr("cx")
        cy = self.attr("cy")
        r = self.attr("r")
        # self.create_radial_gradient(href, cx, cy, r, cx, cy, r)

    def draw(self):
        pass


class AbstractShape(Element):
    def __init__(self, command, node, ctx):
        super().__init__(node)
        self.command = command
        self.ctx = ctx
        self.gradient = None

    def get_data(self):  # pylint: disable=no-self-use
        return None

    def get_style(self):
        return self.node.specified_style()

    def set_style(self, style):
        """Translates style properties names into method calls"""
        self.ctx.style = style
        for key in style:
            method = "set_" + "_".join(key.split("-"))
            if hasattr(self.ctx, method) and style[key] != "none":
                getattr(self.ctx, method)(style[key])
        # saves style to compare in next iteration
        if (
            hasattr(self.ctx, "style_cache")
            and "opacity" not in style
            and self.ctx.style_cache("opacity") != style("opacity")
        ):
            self.ctx.set_opacity(
                style("opacity")
            )  # opacity is kept in memory, need to reset
        self.ctx.style_cache = style

    def has_transform(self):
        return bool(self.attr("transform"))

    def get_transform(self):
        return self.node.transform.to_hexad()

    def has_gradient(self):
        style = self.get_style()
        fill = style("fill")
        return fill is not None and isinstance(fill, inkex.Gradient)

    def get_gradient_href(self):
        style = self.get_style()
        return style("fill").get_id()

    def has_clip(self):
        return bool(self.attr("clip-path"))

    def start(self, gradient):
        self.gradient = gradient
        self.ctx.write("\n// #%s" % self.node.get_id())
        if self.has_transform() or self.has_clip():
            self.ctx.save()

    def draw(self):
        data = self.get_data()  # pylint: disable=assignment-from-none
        style = self.get_style()
        self.ctx.begin_path()
        if self.has_transform():
            trans_matrix = self.get_transform()
            self.ctx.transform(*trans_matrix)  # unpacks argument list
        if self.has_gradient():
            self.gradient.draw()
        self.set_style(style)
        # unpacks "data" in parameters to given method
        getattr(self.ctx, self.command)(*data)
        self.ctx.finish_path()

    def end(self):
        if self.has_transform() or self.has_clip():
            self.ctx.restore()


class G(AbstractShape):  # pylint: disable=invalid-name
    def draw(self):
        # get layer label, if exists
        if self.has_transform():
            trans_matrix = self.get_transform()
            self.ctx.transform(*trans_matrix)


class Rect(AbstractShape):
    def get_data(self):
        x = self.attr("x")
        y = self.attr("y")
        width = self.attr("width")
        height = self.attr("height")
        rx = self.attr("rx") or 0
        ry = self.attr("ry") or 0
        return x, y, width, height, rx, ry


class Circle(AbstractShape):
    def __init__(self, command, node, ctx):
        AbstractShape.__init__(self, command, node, ctx)
        self.command = "arc"

    def get_data(self):
        cx = self.attr("cx")
        cy = self.attr("cy")
        r = self.attr("r")
        return cx, cy, r, 0, math.pi * 2, True


class Ellipse(AbstractShape):
    def get_data(self):
        cx = self.attr("cx")
        cy = self.attr("cy")
        rx = self.attr("rx")
        ry = self.attr("ry")
        return cx, cy, rx, ry

    def draw(self):
        cx, cy, rx, ry = self.get_data()
        style = self.get_style()
        self.ctx.begin_path()
        if self.has_transform():
            trans_matrix = self.get_transform()
            self.ctx.transform(*trans_matrix)  # unpacks argument list
        self.set_style(style)

        kappa = 4 * ((math.sqrt(2) - 1) / 3)
        self.ctx.move_to(cx, cy - ry)
        self.ctx.bezier_curve_to(
            cx + (kappa * rx), cy - ry, cx + rx, cy - (kappa * ry), cx + rx, cy
        )
        self.ctx.bezier_curve_to(
            cx + rx, cy + (kappa * ry), cx + (kappa * rx), cy + ry, cx, cy + ry
        )
        self.ctx.bezier_curve_to(
            cx - (kappa * rx), cy + ry, cx - rx, cy + (kappa * ry), cx - rx, cy
        )
        self.ctx.bezier_curve_to(
            cx - rx, cy - (kappa * ry), cx - (kappa * rx), cy - ry, cx, cy - ry
        )
        self.ctx.finish_path()


class Path(AbstractShape):
    def __init__(self, command, node, ctx):
        AbstractShape.__init__(self, command, node, ctx)
        self.current_position = 0, 0

    def path_move_to(self, data):
        self.ctx.move_to(data[0], data[1])
        self.current_position = data[0], data[1]

    def path_line_to(self, data):
        self.ctx.line_to(data[0], data[1])
        self.current_position = data[0], data[1]

    def path_curve_to(self, data):
        x1, y1, x2, y2 = data[0], data[1], data[2], data[3]
        x, y = data[4], data[5]
        self.ctx.bezier_curve_to(x1, y1, x2, y2, x, y)
        self.current_position = x, y

    def path_close(self, data):  # pylint: disable=unused-argument
        self.ctx.close_path()

    def draw(self):
        """Gets the node type and calls the given method"""
        style = self.get_style()
        self.ctx.begin_path()
        if self.has_transform():
            trans_matrix = self.get_transform()
            self.ctx.transform(*trans_matrix)  # unpacks argument list
        self.set_style(style)

        # Draws path commands
        path_command = {
            "M": self.path_move_to,
            "L": self.path_line_to,
            "C": self.path_curve_to,
            "Z": self.path_close,
        }
        # Make sure we only have Lines and curves (no arcs etc)
        for comm, data in self.node.path.to_superpath().to_path().to_arrays():
            if comm in path_command:
                path_command[comm](data)

        self.ctx.finish_path()


class Line(Path):
    def get_data(self):
        x1 = self.attr("x1")
        y1 = self.attr("y1")
        x2 = self.attr("x2")
        y2 = self.attr("y2")
        return ("M", (x1, y1)), ("L", (x2, y2))


class Polygon(Path):
    def get_data(self):
        points = self.attr("points").strip().split(" ")
        points = map(lambda x: x.split(","), points)
        comm = []
        for point in points:  # creating path command similar
            point = list(map(float, point))
            comm.append(["L", point])
        comm[0][0] = "M"  # first command must be a 'M' => moveTo
        return comm


class Polyline(Polygon):
    pass


class Text(AbstractShape):
    def text_helper(self, tspan):
        if tspan is not None:
            return tspan.text
        for ts_cur in tspan:
            return ts_cur.text + self.text_helper(ts_cur) + ts_cur.tail

    def set_text_style(self, style):
        keys = ("font-style", "font-weight", "font-size", "font-family")
        text = []
        for key in keys:
            if key in style:
                text.append(style[key])
        self.ctx.set_font(" ".join(text))

    def get_data(self):
        x = self.attr("x")
        y = self.attr("y")
        return x, y

    def draw(self):
        for tspan in self.node:
            if isinstance(tspan, inkex.TextPath):
                raise ValueError(_("TextPath elements are not supported"))
        style = self.get_style()
        if self.has_transform():
            trans_matrix = self.get_transform()
            self.ctx.transform(*trans_matrix)  # unpacks argument list
        self.set_style(style)
        self.set_text_style(style)

        for tspan in self.node:
            text = self.text_helper(tspan)
            cur_x = float(tspan.get("x").split()[0])
            cur_y = float(tspan.get("y").split()[0])
            self.ctx.fill_text(text, cur_x, cur_y)
