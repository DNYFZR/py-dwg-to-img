#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2005 Aaron Spike, aaron@ekips.org
#               2022 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
Extract embedded images.
"""

import math
import os
from pathlib import Path
from typing import Iterable
from base64 import decodebytes

import inkex
from inkex.localization import inkex_gettext as _, inkex_ngettext as ngettext


class ExtractImage(inkex.EffectExtension):
    """Extract images and save to filenames"""

    def add_arguments(self, pars):
        pars.add_argument(
            "-s",
            "--selectedonly",
            type=inkex.Boolean,
            help="Extract only selected images",
            default=True,
        )
        pars.add_argument(
            "-l",
            "--linkextracted",
            type=inkex.Boolean,
            help="Replace image data with link to image",
            default=True,
        )
        pars.add_argument(
            "--directory",
            default="./images/",
            help="Location to save the images. "
            "If the directory starts with ./, the filename is interpreted "
            "relative to the location of the opened file.",
        )
        pars.add_argument("--basename", default="", help="Optional file name prefix.")
        pars.add_argument(
            "--filepath",
            default="",
            help="Path to a new file. If given, --basename and --directory "
            "options are ignored.",
        )

    def __init__(self):
        super().__init__()
        self.errcount = 0

    def message(self, elem, message, error=True):
        """Write an error message"""
        inkex.errormsg(elem.get_id() + ": " + message)
        if error:
            self.errcount += 1

    def effect(self):
        self.errcount = 0

        elems: Iterable[inkex.BaseElement] = (
            self.svg.selection.filter(inkex.Image)
            if self.options.selectedonly
            else self.svg.xpath("//svg:image")
        )
        if len(elems) == 0:
            return

        filename, directory = self.process_options()

        counter = 1
        for __, elem in enumerate(elems):
            data, file_ext = self.prepare(elem)
            if data is None:
                continue

            # If no filename is set, use id
            cname = filename
            if cname.strip() == "":
                cname = elem.get_id()
            elif len(elems) > 1:
                # if more than one element is selected and a common filename is used,
                # insert ID
                while True:
                    suffix = "_" + str(counter).rjust(int(math.log10(len(elems))) + 1)
                    if os.path.isfile(
                        os.path.join(directory, cname + suffix + file_ext)
                    ):
                        counter += 1
                    else:
                        cname = cname + suffix
                        break

            pathwext = os.path.join(directory, cname + file_ext)
            if self.save_image(elem, data, pathwext):
                # absolute for making in-mem cycles work
                if self.options.linkextracted:
                    elem.set("xlink:href", Path(os.path.realpath(pathwext)).as_uri())
                counter += 1

        if self.errcount > 0:
            inkex.errormsg(
                ngettext(
                    "{} error occurred", "{} errors occurred.", self.errcount
                ).format(self.errcount)
            )

    def process_options(self):
        """Prepare directory and base filename, independent of particular images"""
        # First case: Extension called from the context menu
        if self.options.filepath.strip() != "":
            directory, filename = os.path.split(self.options.filepath)
            filename, __ = os.path.splitext(filename)
        elif self.options.directory.strip() != "":
            # If the extension is called from the
            # Effects menu, directory is passed and can be absolute or relative
            directory = self.options.directory
            filename = os.path.splitext(self.options.basename)[0]

        # create the directory if it doesn't exist
        directory = self.absolute_href(directory)
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            raise inkex.AbortExtension(
                _("Unable to create directory {}.").format(directory)
            )

        return filename, directory

    @staticmethod
    def mime_to_ext(mime):
        """Return a file extension (incl. leading dot) based on the mime type"""
        # Most extensions are automatic (i.e. extension is same as minor part of mime type)
        part = mime.split("/", 1)[1].split("+")[0]
        return "." + {
            # These are the non-matching ones.
            "svg+xml": "svg",
            "jpeg": "jpg",
            "icon": "ico",
        }.get(part, part)

    def prepare(self, node):
        """Check if we can process the data attribute"""
        xlink = node.get("xlink:href")
        if not xlink.startswith("data:"):
            self.message(
                node, _("Unable to extract image, is it maybe already linked?")
            )
            return None, None  # Not embedded image data

        try:
            data = xlink[5:]
            (mimetype, data) = data.split(";", 1)
            (base, data) = data.split(",", 1)
            file_ext = self.mime_to_ext(mimetype)
        except (ValueError, IndexError):
            self.message(node, _("Invalid image format found."))
            return None, None

        if base != "base64":
            self.message(node, _("Unable to decode encoding {}.").format(base))
            return None, None

        return data, file_ext

    def save_image(self, node, data, pathwext):
        """Save the image contained in the base64-encoded string data to pathwext.

        Returns whether the operation succeded."""

        if os.path.isfile(pathwext):
            self.message(
                node,
                _("Unable to extract image, file {} already exists.").format(pathwext),
            )
            return False

        try:
            with open(pathwext, "wb") as fhl:
                fhl.write(decodebytes(data.encode("utf-8")))
        except (OSError, ValueError):
            self.message(node, _("Unable to write to {}").format(pathwext))
            return False

        self.message(node, _("Image extracted to: {}").format(pathwext), False)

        return True


if __name__ == "__main__":
    ExtractImage().run()
