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
Canvas module for ink2canvas extension
"""

from textwrap import dedent

from inkex import Color, Style

# pylint: disable=too-many-public-methods, disable=missing-function-docstring


class Canvas:
    """Canvas API helper class"""

    def __init__(self, parent, width, height, context="ctx"):
        self.obj = context
        self.code = []  # stores the code
        self.style = Style()
        self.style_cache = Style()  # stores the previous style applied
        self.parent = parent
        self.width = width
        self.height = height

    def write(self, text):
        self.code.append("\t" + text.replace("ctx", self.obj) + "\n")

    def output(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Inkscape Output</title>
        </head>
        <body>
            <canvas id='canvas' width='%d' height='%d'></canvas>
            <script>
            var %s = document.getElementById("canvas").getContext("2d");
            %s
            </script>
        </body>
        </html>
        """
        return dedent(html) % (self.width, self.height, self.obj, "".join(self.code))

    def equal_style(self, style, key):
        """Checks if the last style used is the same or there's no style yet"""
        if key in self.style_cache:
            return True
        if key not in style:
            return True
        return style[key] == self.style_cache[key]

    def begin_path(self):
        self.write("ctx.beginPath();")

    def create_linear_gradient(self, href, x1, y1, x2, y2):
        data = (href, x1, y1, x2, y2)
        self.write(
            "var %s = \
                   ctx.createLinearGradient(%f,%f,%f,%f);"
            % data
        )

    def create_radial_gradient(self, href, cx1, cy1, rx, cx2, cy2, ry):
        data = (href, cx1, cy1, rx, cx2, cy2, ry)
        self.write(
            "var %s = ctx.createRadialGradient\
                   (%f,%f,%f,%f,%f,%f);"
            % data
        )

    def add_color_stop(self, href, pos, color):
        self.write("%s.addColorStop(%f, %s);" % (href, pos, color))

    @staticmethod
    def get_color(rgb, alpha):
        return "'{}'".format(str(Color(rgb).to_rgba(alpha)))

    def set_gradient(self, href):
        """
        for stop in gstops:
            style = simplestyle.parseStyle(stop.get("style"))
            stop_color = style["stop-color"]
            opacity = style["stop-opacity"]
            color = self.get_color(stop_color, opacity)
            pos = float(stop.get("offset"))
            self.add_color_stop(href, pos, color)
        """
        return None  # href

    def set_opacity(self, value):
        self.write("ctx.globalAlpha = %.1f;" % float(value))

    def set_fill(self, value):
        alpha = self.style("fill-opacity")
        if not value.startswith("url("):
            fill = self.get_color(value, alpha)
            self.write("ctx.fillStyle = %s;" % fill)

    def set_stroke(self, value):
        alpha = self.style("stroke-opacity")
        self.write("ctx.strokeStyle = %s;" % self.get_color(value, alpha))

    def set_stroke_width(self, value):
        self.write("ctx.lineWidth = %f;" % self.parent.svg.unittouu(value))

    def set_stroke_linecap(self, value):
        self.write("ctx.lineCap = '%s';" % value)

    def set_stroke_linejoin(self, value):
        self.write("ctx.lineJoin = '%s';" % value)

    def set_stroke_miterlimit(self, value):
        self.write("ctx.miterLimit = %s;" % value)

    def set_font(self, value):
        self.write('ctx.font = "%s";' % value)

    def move_to(self, x, y):
        self.write("ctx.moveTo(%f, %f);" % (x, y))

    def line_to(self, x, y):
        self.write("ctx.lineTo(%f, %f);" % (x, y))

    def close_path(self):
        self.write("ctx.closePath();")

    def quadratic_curve_to(self, cpx, cpy, x, y):
        data = (cpx, cpy, x, y)
        self.write("ctx.quadraticCurveTo(%f, %f, %f, %f);" % data)

    def bezier_curve_to(self, x1, y1, x2, y2, x, y):
        data = (x1, y1, x2, y2, x, y)
        self.write("ctx.bezierCurveTo(%f, %f, %f, %f, %f, %f);" % data)

    def rect(self, x, y, width, height, rx=0, ry=0):
        if rx or ry:
            # rounded rectangle, starts top-left anticlockwise
            self.move_to(x, y + ry)
            self.line_to(x, y + height - ry)
            self.quadratic_curve_to(x, y + height, x + rx, y + height)
            self.line_to(x + width - rx, y + height)
            self.quadratic_curve_to(x + width, y + height, x + width, y + height - ry)
            self.line_to(x + width, y + ry)
            self.quadratic_curve_to(x + width, y, x + width - rx, y)
            self.line_to(x + rx, y)
            self.quadratic_curve_to(x, y, x, y + ry)
        else:
            self.write("ctx.rect(%f, %f, %f, %f);" % (x, y, width, height))

    def arc(self, x, y, r, a1, a2, flag):
        data = (x, y, r, a1, a2, flag)
        self.write("ctx.arc(%f, %f, %f, %f, %.8f, %d);" % data)

    def fill_text(self, text, x, y):
        self.write('ctx.fillText("%s", %f, %f);' % (text, x, y))

    def translate(self, cx, cy):
        self.write("ctx.translate(%f, %f);" % (cx, cy))

    def rotate(self, angle):
        self.write("ctx.rotate(%f);" % angle)

    def scale(self, rx, ry):
        self.write("ctx.scale(%f, %f);" % (rx, ry))

    def transform(self, m11, m12, m21, m22, dx, dy):
        data = (m11, m12, m21, m22, dx, dy)
        self.write("ctx.transform(%f, %f, %f, %f, %f, %f);" % data)

    def save(self):
        self.write("ctx.save();")

    def restore(self):
        self.write("ctx.restore();")

    def finish_path(self):
        if self.style("fill") is not None:
            self.write("ctx.fill();")
        if self.style("stroke") is not None:
            self.write("ctx.stroke();")
