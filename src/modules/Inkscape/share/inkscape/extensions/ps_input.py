#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2008 Stephen Silver
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
Simple wrapper around ps2pdf
"""

import sys
import os

import inkex
from inkex.command import ProgramRunError, call, which
from inkex.localization import inkex_gettext as _


class PostscriptInput(inkex.CallExtension):
    """Load Postscript/EPS Files by calling ps2pdf program"""

    input_ext = "ps"
    output_ext = "pdf"
    multi_inx = True

    def add_arguments(self, pars):
        pars.add_argument("--crop", type=inkex.Boolean, default=False)
        pars.add_argument(
            "--autorotate", choices=["None", "PageByPage", "All"], default="None"
        )

    def call(self, input_file, output_file):
        crop = "-dEPSCrop" if self.options.crop else None
        if sys.platform == "win32":
            params = [
                "-q",
                "-P-",
                "-dSAFER",
                "-dNOPAUSE",
                "-dBATCH",
                "-sDEVICE#pdfwrite",
                "-dCompatibilityLevel#1.4",
                crop,
                "-sOutputFile#" + output_file,
                "-dAutoRotatePages#/" + self.options.autorotate,
                input_file,
            ]
            gs_execs = ["gswin64c", "gswin32c"]
            gs_exec = None
            for executable in gs_execs:
                try:
                    which(executable)
                    gs_exec = executable
                except:
                    pass
            if gs_exec is None:
                if "PYTEST_CURRENT_TEST" in os.environ:
                    gs_exec = "gswin64c"  # In CI, we have neither available,
                    # but there are mock files for the 64 bit version
                else:
                    raise inkex.AbortExtension(_("No GhostScript executable was found"))
            try:
                call(gs_exec, *params)
            except ProgramRunError as err:
                self.handle_gs_error(err)
        else:
            try:
                call(
                    "ps2pdf",
                    crop,
                    "-dAutoRotatePages=/" + self.options.autorotate,
                    input_file,
                    output_file,
                )
            except ProgramRunError as err:
                self.handle_gs_error(err)

    def handle_gs_error(self, err: ProgramRunError):
        inkex.errormsg(
            _(
                "Ghostscript was unable to read the file. \nThe following error message was returned:"
            )
            + "\n"
        )
        inkex.errormsg(err.stderr.decode("utf8"))
        inkex.errormsg(err.stdout.decode("utf8"))
        raise inkex.AbortExtension()


if __name__ == "__main__":
    PostscriptInput().run()
