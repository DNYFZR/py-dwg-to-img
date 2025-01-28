#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2022 Jonathan Neuhauser (jonathan.neuhauser@outlook.com)
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

"""Parser for HP/GL2 Documents (includes ordinary HPGL)"""

import pyparsing as pp

from inkex.base import SvgOutputMixin
import inkex
from inkex.localization import inkex_gettext as _


from hpgl_input_sm import HPGLStateMachine
from hpgl_parser import build_parser


class Hpgl2Input(inkex.InputExtension):
    """InputExtension to import HP/GL2 documents."""

    def add_arguments(self, pars):
        pars.add_argument(
            "--width", type=float, default=8, help="Width of the picture frame [in]"
        )
        pars.add_argument(
            "--height", type=float, default=10, help="Height of the picture frame [in]"
        )
        pars.add_argument(
            "--resolution", type=float, default=1016.0, help="Resolution (plu/in)"
        )
        pars.add_argument(
            "--bake-transforms",
            type=inkex.Boolean,
            default=True,
            help=(
                "Bake transforms"
                "(disabling is helpful for debugging IP/IR/SC commands)"
            ),
        )
        pars.add_argument(
            "--break-apart",
            type=inkex.Boolean,
            default=True,
            help="Break apart subpaths",
        )

    def load(self, stream):
        """Load the document, making sure that we operate on a decoded string"""
        res = stream.read()
        if isinstance(res, str):
            return res
        return res.decode()

    def effect(self):
        # interpret HPGL data
        doc: inkex.SvgDocumentElement = SvgOutputMixin.get_template(
            width=self.options.width * 25.4,
            height=self.options.height * 25.4,
            unit="mm",
        )

        layer = doc.getroot().add(inkex.Layer())

        plu_to_svg = inkex.Transform(
            scale=(
                0.025 / self.options.resolution * 1016,
                -0.025 / self.options.resolution * 1016,
            ),
            translate=(0, self.options.height * 25.4),
        )
        layer.transform = plu_to_svg

        document_parser = build_parser(HPGLStateMachine(layer, self.options))
        try:
            result = document_parser.parse_string(self.document, parse_all=True)
            # bake in the transforms
            if self.options.bake_transforms:
                layer.bake_transforms_recursively()
            unknown = result.get("u")
            if unknown:
                inkex.errormsg(
                    _(
                        "Unsupported commands encountered. "
                        "The following commands were ignored:"
                    )
                )
                inkex.errormsg(unknown)

        except pp.ParseException as parse_err:
            inkex.errormsg(parse_err.explain())

        # deliver document to inkscape
        self.document = doc


if __name__ == "__main__":
    Hpgl2Input().run()
