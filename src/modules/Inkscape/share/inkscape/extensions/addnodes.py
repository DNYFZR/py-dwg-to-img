#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2005, 2007 Aaron Spike, aaron@ekips.org
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
"""
This extension either adds nodes to a path so that

  No segment is longer than a maximum value OR that each segment is divided
  into a given number of equal segments.

"""

import math
from typing import cast
import inkex

from inkex import PathElement


class AddNodes(inkex.EffectExtension):
    """Extension to split a path by adding nodes to it"""

    def add_arguments(self, pars):
        pars.add_argument(
            "--segments",
            type=int,
            default=2,
            help="Number of segments to divide the path into",
        )
        pars.add_argument(
            "--max",
            type=float,
            default=10.0,
            help="Number of segments to divide the path into",
        )
        pars.add_argument(
            "--method", default="bymax", help="The kind of division to perform"
        )
        pars.add_argument(
            "--unit", default="px", help="Unit for maximum segment length"
        )

    def effect(self):
        maxlen = self.svg.viewport_to_unit(f"{self.options.max}{self.options.unit}")
        for node in self.svg.selection.filter(PathElement):
            new = inkex.Path()
            path = cast(inkex.Path, node.path)
            for sub in path.proxy_iterator():
                if sub.letter in "mM":
                    # Add unchanged.
                    new.append(sub.command)
                    continue
                length = sub.length()
                if length < 1e-12:
                    # Zero-length subpaths
                    new.append(sub.command)
                    continue
                # compute number of splits
                if self.options.method == "bynum":
                    splits = self.options.segments
                else:
                    splits = math.ceil(length / maxlen)
                to_split = sub
                # We first split the command at len * 1/splits.
                # The first part is appended, the second part is split
                # again at then len * 1/splits and so on.

                for _ in range(splits - 1):
                    result = to_split.split(to_split.ilength(length / splits))
                    new.append(result[0].command)
                    to_split = result[1]
                new.append(to_split.command)

            node.path = new


if __name__ == "__main__":
    AddNodes().run()
