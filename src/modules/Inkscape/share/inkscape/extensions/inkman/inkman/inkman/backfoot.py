#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2021 Martin Owens <doctormo@gmail.com>
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
When the extension manager fails, this allows us to upgrade automatically.
"""

import os
import sys
import traceback

# Note: All imports are being done as late as possible in this module.
# If any of the imports caused the error, then we'll still message the user.


def update_pip_package(package):
    """
    Update the package using the pip update.
    """
    from inkex.utils import get_user_directory
    from inkex.command import ProgramRunError, call

    try:
        pip = os.path.join(get_user_directory(), "bin", "pip")
        log = call(pip, "install", "--upgrade", package).decode("utf8")
        logs = [line for line in log.split("\n") if "skip" not in line]
        return "\n".join(logs)
    except ProgramRunError:
        raise IOError(f"Failed to update the package {package}")


def attempt_to_recover():
    """
    Messages the user, provides a traceback and attepts a self-update
    """
    info = sys.exc_info()
    sys.stderr.write("An error occured with the extensions manager!\n")
    sys.stderr.write("Trying to self-update the package... ")
    sys.stderr.flush()

    from inkman import __pkgname__, __version__, __file__, __issues__

    location = os.path.dirname(__file__)
    update_log = "Not done"

    try:
        update_log = update_pip_package(__pkgname__)
        sys.stderr.write(
            "Updated!\n\nPlease try and reload the program again.\n\n"
        )
    except Exception:
        sys.stderr.write(
            "Failed to update!\n\nPlease delete the package manually! (see location below)\n\n"
        )

    sys.stderr.write(
        f"""
Please report this error
------------------------

Report URL: {__issues__}
Location: {location}
{__pkgname__}: {__version__}

{update_log}
"""
    )

    traceback.print_exception(*info)
    del info
    sys.exit(2)
