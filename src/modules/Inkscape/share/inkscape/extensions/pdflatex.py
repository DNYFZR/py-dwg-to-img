#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2019 Marc Jeanmougin
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
#
"""
Generate Latex via a PDF using pdflatex
"""

import os

import inkex
from inkex.base import TempDirMixin
from inkex.command import ProgramRunError, call, inkscape
from inkex import load_svg, ShapeElement, Defs
from inkex.units import convert_unit
from inkex.localization import inkex_gettext as _


class PdfLatex(TempDirMixin, inkex.GenerateExtension):
    """
    Use pdflatex to generate LaTeX, this whole hack is required because
    we don't want to open a LaTeX document as a document, but as a
    generated fragment (like import, but done manually).
    """

    def add_arguments(self, pars):
        pars.add_argument(
            "--formule",
            type=str,
            default=r"\(\displaystyle\frac{\pi^2}{6}=\lim_{n \to \infty}\sum_{k=1}^n \frac{1}{k^2}\)",
        )
        pars.add_argument(
            "--preamble",
            type=str,
            default="".join(
                f"\\usepackage{{ams{i}}}" for i in ["math", "symb", "fonts"]
            ),
        )
        pars.add_argument("--font_size", type=int, default=10)
        pars.add_argument("--page", choices=["basic", "advanced"])
        pars.add_argument("--standalone", type=inkex.Boolean, default=True)

    def generate(self):
        tex_file = os.path.join(self.tempdir, "input.tex")
        pdf_file = os.path.join(self.tempdir, "input.pdf")  # Auto-generate by pdflatex
        svg_file = os.path.join(self.tempdir, "output.svg")

        with open(tex_file, "w") as fhl:
            self.write_latex(fhl)

        try:
            call(
                "pdflatex",
                tex_file,
                output_directory=self.tempdir,
                halt_on_error=True,
                oldie=True,
            )
        except ProgramRunError as err:
            inkex.errormsg(_("An exception occurred during LaTeX compilation: ") + "\n")
            inkex.errormsg(
                err.stdout.decode("utf8")
                .replace("\r\n", "\n")
                .split("Transcript written on")[0]
            )
            raise inkex.AbortExtension()

        inkscape(
            pdf_file,
            export_filename=svg_file,
            pages=1,
            pdf_poppler=True,
            export_type="svg",
            actions=(
                "select-all;page-fit-to-selection;"
                "clone-unlink-recursively;vacuum-defs"
            ),
        )

        if not os.path.isfile(svg_file):
            fn = os.path.basename(svg_file)
            if os.path.isfile(fn):
                # Inkscape bug detected, file got saved wrong
                svg_file = fn

        with open(svg_file, "r") as fhl:
            svg: inkex.SvgDocumentElement = load_svg(fhl).getroot()

            scale = convert_unit("1pt", "px") / self.svg.scale
            if not self.options.standalone:
                scale *= self.options.font_size / 10

            for child in svg:
                if isinstance(child, ShapeElement):
                    child.transform = inkex.Transform(scale=scale) @ child.transform
                    yield child
                elif isinstance(child, Defs):
                    for def_child in child:
                        # The ids of both the imported and the target document should
                        # be off-limits
                        def_child.set_random_ids(
                            backlinks=True, blacklist=self.svg.get_ids()
                        )
                        self.svg.defs.append(def_child)

    def write_latex(self, stream):
        """Takes a formula and wraps it in latex"""
        if self.options.standalone:
            docclass = (
                f"\\documentclass[fontsize={self.options.font_size}pt, "
                + "class=scrreprt, preview, border=2pt]{standalone}"
            )
        else:
            docclass = r"\documentclass{minimal}"
        stream.write(
            f"""%% processed with pdflatex.py
{docclass}
{self.options.preamble}
\\begin{{document}}
{self.options.formule}
\\end{{document}}
"""
        )
        stream.flush()


if __name__ == "__main__":
    PdfLatex().run()
