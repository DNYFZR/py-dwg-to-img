# SPDX-FileCopyrightText: 2024 Software Freedom Conservancy <info@sfconservancy.org>
# SPDX-FileCopyrightText: 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""Script to extract afdesign data"""

import os
import sys
from io import BytesIO

import inkex


HERE = os.path.dirname(__file__) or "."
# This is suggested by https://docs.python-guide.org/writing/structure/.
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from inkaf.utils import to_pretty_xml  # noqa: E402
from inkaf.parser.extract import AFExtractor  # noqa: E402
from inkaf.parser.parse import AFParser, Document  # noqa: E402
from inkaf.svg.convert import AFConverter  # noqa: E402


def parse(stream) -> Document:
    extractor = AFExtractor(stream)
    doc = extractor.content.files["doc.dat"]  # type: ignore

    result = AFParser(BytesIO(doc))
    return result.parse()


class AFInput(inkex.InputExtension):
    """Input extension to extract afdesign data"""

    def add_arguments(self, pars):
        """Add command line arguments"""
        # optional arguments, see https://stackoverflow.com/a/15008806/1320237
        pars.add_argument(
            "--pretty",
            action="store_true",
            dest="pretty_print",
            default=False,
            help="Create an SVG file that has several lines and looks pretty to read.",
        )

    def load(self, stream) -> bytes:
        """Load the afdesign file"""
        converter = AFConverter(parse(stream))
        converter.convert()
        return self.svg_to_string(converter.doc.getroot())

    def svg_to_string(self, svg: inkex.SvgDocumentElement) -> bytes:
        """Convert the SvgDocumentElement to a string.

        This is mostly copied from inkex.elements._svg.SvgDocumentElement.tostring().
        """
        result = svg.tostring()
        if self.options.pretty_print:
            return to_pretty_xml(result)
        return result


def main():
    """Main entry point for the command line."""
    stdout = sys.stdout.buffer  # type: ignore
    # redirect print statements to stderr
    # see https://stackoverflow.com/a/15860430/1320237
    sys.stdout = sys.stderr
    AFInput().run(output=stdout)
    stdout.write(b"\n")
