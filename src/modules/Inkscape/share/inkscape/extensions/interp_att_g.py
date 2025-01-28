#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2009 Aurelio A. Heckert, aurium (a) gmail dot com
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
Interpolation of attributes in selected objects or group's children.
"""

import inkex
from inkex.localization import inkex_gettext as _
from inkex.tween import ColorInterpolator, ValueInterpolator, AttributeInterpolator
from inkex.utils import is_number


class InterpAttG(inkex.EffectExtension):
    """
    This effect applies a value for any interpolatable attribute for all
    elements inside the selected group or for all elements in a multiple selection.
    """

    def __init__(self):
        super(InterpAttG, self).__init__()
        self.arg_parser.add_argument(
            "-a",
            "--att",
            type=str,
            dest="att",
            default="width",
            help="Attribute to be interpolated.",
        )
        self.arg_parser.add_argument(
            "-o",
            "--att-other",
            type=str,
            dest="att_other",
            help="Other attribute (for a limited UI).",
        )
        self.arg_parser.add_argument(
            "-t",
            "--att-other-type",
            type=self.arg_class([ColorInterpolator, ValueInterpolator]),
            dest="att_other_type",
            help="The other attribute type.",
        )
        self.arg_parser.add_argument(
            "-w",
            "--att-other-where",
            type=str,
            dest="att_other_where",
            default="tag",
            help="That is a tag attribute or a style attribute?",
        )
        self.arg_parser.add_argument(
            "-s",
            "--start-val",
            type=str,
            dest="start_val",
            default="#F00",
            help="Initial interpolation value.",
        )
        self.arg_parser.add_argument(
            "-e",
            "--end-val",
            type=str,
            dest="end_val",
            default="#00F",
            help="End interpolation value.",
        )
        self.arg_parser.add_argument(
            "-u", "--unit", type=str, dest="unit", default="none", help="Values unit."
        )
        self.arg_parser.add_argument(
            "--zsort",
            type=inkex.Boolean,
            dest="zsort",
            default=False,
            help="use z-order instead of selection order",
        )
        self.arg_parser.add_argument(
            "--tab",
            type=str,
            dest="tab",
            help="The selected UI-tab when OK was pressed",
        )

    def get_elements(self):
        """Returns a list of elements to work on"""
        if not self.svg.selection:
            return []

        if len(self.svg.selection) > 1:
            # multiple selection
            if self.options.zsort:
                return list(self.svg.selection.rendering_order().values())
            return list(self.svg.selection.values())

        # must be a group
        node = self.svg.selection.filter(inkex.Group).first()
        return list(node) or []

    def create_dummy_nodes(self, path):
        """Create dummy nodes to use the interpolation classes defined in inkex.tween"""
        pat1 = inkex.PathElement()
        pat2 = inkex.PathElement()

        start_value = self.options.start_val.replace(",", ".")
        end_value = self.options.end_val.replace(",", ".")
        if self.options.unit != "none":
            start_value += self.options.unit
            end_value += self.options.unit
        self.apply_value(pat1, path, start_value)
        self.apply_value(pat2, path, end_value)
        return pat1, pat2

    @staticmethod
    def apply_value(node, path, value):
        """Applies a value to a given node. If path starts with "transform/" or "style/", the
        value is applied to either transform or style."""
        if path.startswith("style/"):
            att_name = path[6:]
            node.style[att_name] = value
        elif path.startswith("transform/"):
            if not is_number(value):
                raise inkex.AbortExtension(
                    _("Unable to set attribute {} to {}").format(path, value)
                )
            if path == "transform/trans-x":
                node.transform.add_translate(value, 0)
            elif path == "transform/trans-y":
                node.transform.add_translate(0, value)
            elif path == "transform/scale":
                node.transform.add_scale(value)
        elif path == "transform":
            node.transform @= value
        else:
            node.set(path, value)

    def effect(self):
        method = None
        if self.options.att == "other":
            if self.options.att_other is None:
                raise inkex.AbortExtension(
                    _("You selected 'Other'. Please enter an attribute to interpolate.")
                )
            if self.options.att_other_where == "tag":
                path = self.options.att_other
            else:
                path = self.options.att_other_where + "/" + self.options.att_other
            method = self.options.att_other_type
        else:
            path = self.options.att
            if self.options.att == "height" or self.options.att == "width":
                method = inkex.tween.UnitValueInterpolator

        path1, path2 = self.create_dummy_nodes(path)
        if path.startswith("transform"):
            path = "transform"
        try:
            # maybe tween knows what do do with this attribute?
            interpolator = AttributeInterpolator.create_from_attribute(
                path1, path2, path, None
            )
        except:
            # okay, apparently not
            interpolator = AttributeInterpolator.create_from_attribute(
                path1, path2, path, method
            )
        collection = self.get_elements()
        if not collection:
            raise inkex.AbortExtension(_("There is no selection to interpolate"))

        steps = [1.0 / (len(collection) - 1) * i for i in range(len(collection))]

        for time, node in zip(steps, collection):
            new_value = interpolator.interpolate(time)
            InterpAttG.apply_value(node, path, new_value)

        return True


if __name__ == "__main__":
    InterpAttG().run()
