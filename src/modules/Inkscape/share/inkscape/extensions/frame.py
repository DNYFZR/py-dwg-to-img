#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2016 Richard White, rwhite8282@gmail.com
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
An Inkscape extension that creates a frame around a selected object.
"""

from typing import List

import inkex
from inkex import Group, PathElement, ClipPath
from inkex.localization import inkex_gettext as _


class Frame(inkex.EffectExtension):
    """
    An Inkscape extension that creates a frame around a selected object.
    """

    def add_arguments(self, pars):
        # Parse the options.
        pars.add_argument("--tab", default="stroke")
        pars.add_argument("--clip", type=inkex.Boolean, default=False)
        pars.add_argument("--type", default="rect", choices=["rect", "ellipse"])
        pars.add_argument("--corner_radius", type=int, default=0)
        pars.add_argument("--fill_color", type=inkex.Color, default=inkex.Color(0))
        pars.add_argument("--group", type=inkex.Boolean, default=False)
        pars.add_argument("--stroke_color", type=inkex.Color, default=inkex.Color(0))
        pars.add_argument("--width", type=float, default=2.0)
        pars.add_argument(
            "--offset_absolute",
            type=float,
            default=0,
            help="Offset in user units, positive = outside",
        )
        pars.add_argument(
            "--offset_relative",
            type=float,
            default=0,
            help="Relative offset in percentage of the bounding box size",
        )
        pars.add_argument(
            "--z_position",
            type=str,
            default="bottom",
            choices=["top", "bottom", "split"],
        )
        pars.add_argument("--asgroup", type=inkex.Boolean, default=False)

    def add_clip(self, node: inkex.BaseElement, clip_path: inkex.PathElement):
        """Adds a new clip path node to the defs and sets
            the clip-path on the node.
        node -- The node that will be clipped.
        clip_path -- The clip path object.
        """
        clip = ClipPath()
        # apply the reverse transform to the clip path. no composed_transform here,
        # since the frame will be appended to the object' parent (or an untransformed
        # group within).
        clip.append(PathElement.new(path=clip_path.path, transform=-node.transform))
        self.svg.defs.add(clip)
        node.set("clip-path", clip.get_id(as_url=2))

    @staticmethod
    def generate_frame(name, box: inkex.BoundingBox, rectangle=True, radius=0):
        """
        name -- The name of the new frame object.
        box -- The boundary box of the node.
        style -- The style used to draw the path.
        radius -- The corner radius of the frame.
        returns a new frame node.
        """
        if rectangle:
            r = min([radius, abs(box.x.size / 2), abs(box.y.size / 2)])
            elem = inkex.Rectangle.new(
                left=box.x.minimum,
                top=box.y.minimum,
                width=box.x.size,
                height=box.y.size,
                rx=r,
            )
        else:
            elem = inkex.Ellipse.new(center=box.center, radius=box.size / 2)
        elem.label = name
        return elem

    def create_frame(self, containedelements: List[inkex.BaseElement]):
        """generate the frame for an element or a group of elements"""
        width = self.options.width
        style = inkex.Style({"stroke-width": width})
        style.set_color(self.options.stroke_color, "stroke")
        elem_top = None
        elem_bottom = None

        box = inkex.BoundingBox()
        for node in containedelements:
            if isinstance(node, (inkex.TextElement, inkex.Tspan, inkex.FlowRoot)):
                try:
                    box += node.get_inkscape_bbox()
                except ValueError:
                    continue
            else:
                box += node.bounding_box()
        box = box.resize(
            box.x.size * (self.options.offset_relative / 100),
            box.y.size * (self.options.offset_relative / 100),
        )
        box = box.resize(self.options.offset_absolute)

        frame = self.generate_frame(
            "Frame", box, self.options.type == "rect", self.options.corner_radius
        )
        if self.options.z_position != "split":
            style.set_color(self.options.fill_color, "fill")
            frame.style = style
            if self.options.z_position == "bottom":
                elem_bottom = frame
            else:
                elem_top = frame
        else:
            fill = frame.copy()
            elem_top = frame
            elem_top.style = style
            elem_bottom = fill
            elem_bottom.style.set_color(self.options.fill_color, "fill")
            elem_top.style["fill"] = None
        return elem_bottom, elem_top

    def process_elements(self, containedelements: List[inkex.BaseElement]):
        """Create and append the frame for an object or a set of objects."""
        elem_bottom, elem_top = self.create_frame(containedelements)
        if self.options.clip:
            for node in containedelements:
                element = elem_top if elem_top is not None else elem_bottom
                self.add_clip(node, element)
        if self.options.group:
            group = containedelements[0].getparent().add(Group())
            if elem_bottom is not None:
                group.append(elem_bottom)
            for node in containedelements:
                group.append(node)
            if elem_top is not None:
                group.append(elem_top)
        else:
            if elem_bottom is not None:
                containedelements[0].addprevious(elem_bottom)
            if elem_top is not None:
                containedelements[-1].addnext(elem_top)

    def effect(self):
        """Performs the effect."""
        # Determine common properties.
        if not self.svg.selection:
            raise inkex.AbortExtension(_("Select at least one object."))
        style = inkex.Style({"stroke-width": self.options.width})
        style.set_color(self.options.stroke_color, "stroke")

        if not self.options.asgroup:
            for node in self.svg.selection:
                self.process_elements([node])
        else:
            self.process_elements(self.svg.selection.rendering_order())


if __name__ == "__main__":
    Frame().run()
