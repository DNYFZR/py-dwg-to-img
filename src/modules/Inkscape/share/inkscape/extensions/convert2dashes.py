#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2005,2007 Aaron Spike, aaron@ekips.org
# Copyright (C) 2009 Alvin Penner, penner@vaxxine.com
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
This extension converts a path into a dashed line using 'stroke-dasharray'
It is a modification of the file addnodes.py
"""

import inkex
from inkex import bezier, CubicSuperPath, Group, PathElement
from inkex.localization import inkex_gettext as _
from inkex.paths.interfaces import ILengthSettings


class Dashit(inkex.EffectExtension):
    """Extension to convert paths into dash-array line"""

    def __init__(self):
        super(Dashit, self).__init__()
        self.not_converted = []

    def effect(self):
        for node in self.svg.selection:
            self.convert2dash(node)
        if self.not_converted:
            inkex.errormsg(
                _("Total number of objects not converted: {}\n").format(
                    len(self.not_converted)
                )
            )
            # return list of IDs in case the user needs to find a specific object
            inkex.utils.debug(self.not_converted)

    def convert2dash(self, node):
        """Convert each selected node's dash array"""
        if isinstance(node, Group):
            for child in node:
                self.convert2dash(child)
        elif isinstance(node, PathElement):
            self._convert(node)
        else:
            self.not_converted.append(node.get("id"))

    @staticmethod
    def _convert(node):
        dashes = []
        offset = 0
        overlap = 0
        dashes = node.get_computed_style("stroke-dasharray")
        offset = float(node.get_computed_style("stroke-dashoffset"))
        # Correct negative offsets
        while offset < 0:
            offset += sum(dashes)
        if not dashes:
            return
        new = inkex.Path()
        segment: inkex.Path.PathCommandProxy
        for segment in node.path.to_absolute().proxy_iterator():
            ismove = segment.letter == "M"
            if ismove:
                # Start a new subpath, reset dash counter.
                idash = 0
                dash = dashes[0]
                remaining_length = offset
                firstdrawn_index = -1
            else:
                remaining_length = segment.length() + overlap
                current = segment
            while dash < remaining_length:
                if not ismove:
                    first_part, current = current.split(current.ilength(dash - overlap))
                    if idash % 2:  # create a gap
                        new.append(inkex.paths.Move(first_part.cend_point))
                    else:
                        if firstdrawn_index == -1:
                            firstdrawn_index = len(new)
                        new.append(first_part.command)
                remaining_length = remaining_length - dash
                idash = (idash + 1) % len(dashes)
                dash = dashes[idash]
                overlap = 0
                # We have already drawn a gap
                if firstdrawn_index == -1:
                    firstdrawn_index = None
            if ismove:
                new.append(segment.command)
            else:
                if idash % 2:  # Process the final part of the segment
                    new.append(inkex.paths.Move(current.cend_point))
                else:
                    if current.letter == "Z":
                        # In case of ZoneClose:
                        # Replace the firstdrawn index with a moveto, and append the
                        # command to the end to fix linejoins
                        new.append(inkex.paths.Line(current.cend_point))
                        if firstdrawn_index is not None and firstdrawn_index > -1:
                            index = firstdrawn_index
                            while new[index].letter != "M":
                                element = new[index]
                                new[index] = inkex.paths.Move(
                                    element.cend_point(0j, 0j)
                                )
                                new.append(element)
                                index += 1
                    else:
                        if firstdrawn_index == -1:
                            firstdrawn_index = len(new)
                        new.append(current.to_non_shorthand())

            overlap = remaining_length
        node.style.pop("stroke-dasharray")
        node.pop("sodipodi:type")
        node.path = new


if __name__ == "__main__":
    Dashit().run()
