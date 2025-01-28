#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2005 Aaron Spike, aaron@ekips.org
#               2020 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
"""Interpolate between two paths, respecting their style"""

import copy

import inkex
from inkex.utils import pairwise
from inkex.tween import (
    AttributeInterpolator,
    StyleInterpolator,
    EqualSubsegmentsInterpolator,
    FirstNodesInterpolator,
)

from inkex.localization import inkex_gettext as _


class Interpolate(inkex.EffectExtension):
    """Interpolate extension"""

    def add_arguments(self, pars):
        pars.add_argument(
            "-e",
            "--exponent",
            type=float,
            default=1.0,
            help="values other than zero give non linear interpolation",
        )
        pars.add_argument(
            "-s", "--steps", type=int, default=5, help="number of interpolation steps"
        )
        pars.add_argument(
            "-m",
            "--method",
            type=str,
            default="equalSubsegments",
            help="method of interpolation",
        )
        pars.add_argument(
            "-d", "--dup", type=inkex.Boolean, default=True, help="duplicate endpaths"
        )
        pars.add_argument(
            "--style",
            type=inkex.Boolean,
            default=False,
            help="try interpolation of some style properties",
        )
        pars.add_argument(
            "--zsort",
            type=inkex.Boolean,
            default=False,
            help="use z-order instead of selection order",
        )

    def effect(self):
        steps = self.get_steps()

        objectpairs = self.get_copied_path_pairs()
        if not objectpairs:
            raise inkex.AbortExtension(_("At least two paths need to be selected"))

        for elem1, elem2 in objectpairs:
            method = EqualSubsegmentsInterpolator
            if self.options.method == "firstNodes":
                method = FirstNodesInterpolator

            path_interpolator = AttributeInterpolator.create_from_attribute(
                elem1, elem2, "d", method=method
            )
            if self.options.style:
                style_interpolator = StyleInterpolator(elem1, elem2)

            group = self.svg.get_current_layer().add(inkex.Group())
            for time in steps:
                interpolated_path = path_interpolator.interpolate(time)
                new = group.add(inkex.PathElement())
                new.path = interpolated_path
                if self.options.style:
                    interpolated_style = style_interpolator.interpolate(time)
                    new.style = interpolated_style
                else:
                    new.style = copy.deepcopy(elem1.style)

    def get_steps(self):
        """Returns the interpolation steps as a monotonous array with elements between 0 and 1.
        0 and 1 are added as first and last elements if the source paths should be duplicated
        """
        exponent = self.options.exponent
        # if exponent >= 0:
        #    exponent += 1.0
        # else:
        #    exponent = 1.0 / (1.0 - exponent)
        steps = [
            ((i + 1) / (self.options.steps + 1.0)) ** exponent
            for i in range(self.options.steps)
        ]
        if self.options.dup:
            steps = [0] + steps + [1]
        return steps

    def get_copied_path_pairs(self):
        """Returns deep copies of pairs of subsequent objects of the
        current selection, either in z order or in selection order.
        Objects other than path objects are ignored. Transforms are baked in."""
        if self.options.zsort:
            # work around selection order swapping with Live Preview
            objects = self.svg.selection.rendering_order()
        else:
            # use selection order (default)
            objects = self.svg.selection

        objects = [
            node for node in objects.values() if isinstance(node, inkex.PathElement)
        ]

        for node in objects:
            node.apply_transform()

        objectpairs = pairwise(objects, start=False)
        return objectpairs


if __name__ == "__main__":
    Interpolate().run()
