#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2018 Martin Owens <doctormo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>
#
"""
Inkscape Extensions Manager, Graphical User Interface (Gtk3)
"""

import sys
import logging
import warnings

from argparse import ArgumentParser

warnings.filterwarnings("ignore")


def run(args):
    # Late imports to catch import errors.
    from inkman.targets import TARGETS
    from inkman.gui import ManagerApp
    from inkman.utils import get_inkscape_version

    arg_parser = ArgumentParser(description=__doc__)
    arg_parser.add_argument("input_file", nargs="?")
    arg_parser.add_argument(
        "--target",
        default=TARGETS[0].category,
        choices=[t.category for t in TARGETS],
    )
    arg_parser.add_argument("--for-version", default=None)
    options = arg_parser.parse_args(args)
    version = options.for_version or get_inkscape_version()
    try:
        ManagerApp(
            start_loop=True,
            version=version,
            target=[t for t in TARGETS if t.category == options.target][0],
        )
    except KeyboardInterrupt:
        logging.error("User Interputed")
    logging.debug("Exiting Application")


def recovery_run(args):
    try:
        run(args)
    except Exception:
        from inkman.backfoot import attempt_to_recover

        attempt_to_recover()


if __name__ == "__main__":
    recovery_run(sys.argv[1:])
