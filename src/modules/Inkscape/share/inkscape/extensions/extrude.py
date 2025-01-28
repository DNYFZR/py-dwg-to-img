#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2022 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
"""Join paths with lines or polygons"""

import itertools
from typing import List, Union

import inkex
from inkex.localization import inkex_gettext as _
from inkex.paths import ZoneClose, zoneClose, Line, Move, move
from inkex.turtle import PathGroupBuilder, PathBuilder


class Extrude(inkex.EffectExtension):
    """This effect draws lines between each nth node of each selected path.
    It can be chosen whether these regions are filled and whether the fill uses rectangles
    or copies of the path segments.
    The lines will be inserted between the two elements.
    """

    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument(
            "-m",
            "--mode",
            default="lines",
            choices=["lines", "polygons", "snug"],
            help='Join paths with lines, polygons or copies of the segments ("snug")',
        )
        pars.add_argument(
            "-s",
            "--subpaths",
            default=True,
            type=inkex.Boolean,
            help="""If true, connecting lines will be inserted as subpaths of a single path.
                        If false, they will be inserted in newly created group. 
                        Only applies to mode=lines""",
        )

    @staticmethod
    def _handle_lines(manager, com1, com2):
        if not (
            isinstance(com1.command, (ZoneClose, zoneClose))
            or isinstance(com2.command, (ZoneClose, zoneClose))
        ):
            # For a closed subpath, the first line has already been drawn.
            manager.Move_to(*com1.end_point)
            manager.Line_to(*com2.end_point)

    @staticmethod
    def _handle_polygons(manager, com1, com2):
        if not (
            isinstance(com1.command, (Move, move))
            or isinstance(com2.command, (Move, move))
        ):
            # We skip if one of either commands is a "Move" command
            manager.Move_to(*com1.previous_end_point)
            for point in [
                com1.end_point,
                com2.end_point,
                com2.previous_end_point,
                com1.previous_end_point,
            ]:
                manager.Line_to(*point)

    @staticmethod
    def _handle_snug(manager, com1, com2):
        if not (
            isinstance(com1.command, (Move, move))
            or isinstance(com2.command, (Move, move))
        ):
            # We skip if one of either commands is a "Move" command
            manager.Move_to(*com1.previous_end_point)
            com1r = com1.command
            com2r = com2.reverse()
            doflag = True
            if isinstance(com1r, (ZoneClose, zoneClose)):
                # ZoneClose can not be used directly, must be converted to line
                com1r = Line(*com1.first_point)
                if com1.previous_end_point.is_close(com1.end_point):
                    doflag = False
            if doflag:
                manager.add([com1r, Line(*com2.end_point), com2r, ZoneClose()])

    def effect(self):
        paths: List[inkex.PathElement] = []
        for node in self.svg.selection.rendering_order().filter(inkex.ShapeElement):
            if isinstance(node, inkex.PathElement):
                node.apply_transform()
            paths.append(node)
        if len(paths) < 2:
            raise inkex.AbortExtension(_("Need at least 2 paths selected"))
        lines = self.options.mode.lower() == "lines"
        subpaths = self.options.subpaths and lines

        mode = (
            self._handle_lines
            if lines
            else (
                self._handle_polygons
                if self.options.mode.lower() == "polygons"
                else self._handle_snug
            )
        )

        if lines:
            style = {
                "fill": "none",
                "stroke": "#000000",
                "stroke-opacity": 1,
                "stroke-width": "1px",
            }
        else:
            style = {
                "fill": "#000000",
                "fill-opacity": 0.3,
                "stroke": "#000000",
                "stroke-opacity": 0.6,
                "stroke-width": "1px",
                "stroke-linejoin": "round",
            }

        for pa1, pa2 in itertools.combinations(paths, 2):
            manager = PathBuilder(style) if subpaths else PathGroupBuilder(style)
            for com1, com2 in zip(pa1.path.proxy_iterator(), pa2.path.proxy_iterator()):
                mode(manager, com1, com2)
                manager.terminate()
            manager.append_next(pa1)


if __name__ == "__main__":
    Extrude().run()
