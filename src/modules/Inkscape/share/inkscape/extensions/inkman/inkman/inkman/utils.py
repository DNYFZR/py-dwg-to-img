#
# Copyright (C) 2019 Martin Owens
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
Utilities functions for inkscape extension manager.
"""

import os

from collections import defaultdict
from email.parser import FeedParser
from appdirs import user_cache_dir

from inkex.inx import InxFile
from inkex.command import inkscape, ProgramRunError, CommandNotFound

DEFAULT_VERSION = "1.1"
CACHE_DIR = user_cache_dir("inkscape-extension-manager", "Inkscape")
INKSCAPE_VERSION = os.environ.get("INKSCAPE_VERSION", None)
INKSCAPE_PROFILE = os.environ.get("INKSCAPE_PROFILE_DIR", None)

# This directory can be passed and used by inkscape to override it's
# profile directory for extensions
INKSCAPE_EXTENSIONS = os.environ.get("INKSCAPE_EXTENSIONS_DIR", None)

if not INKSCAPE_PROFILE and "VIRTUAL_ENV" in os.environ:
    INKSCAPE_PROFILE = os.path.dirname(os.environ["VIRTUAL_ENV"])

if not INKSCAPE_PROFILE and "APPDATA" in os.environ:
    INKSCAPE_PROFILE = os.path.join(os.environ["APPDATA"], "inkscape")

if not INKSCAPE_PROFILE and not INKSCAPE_EXTENSIONS:
    raise ImportError("The Inkscape profile directory isn't set!")

if not os.path.isdir(CACHE_DIR):
    os.makedirs(CACHE_DIR)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ICON_SEP = ("-" * 12) + "SVGICON" + ("-" * 12)


def _pythonpath():
    for pth in os.environ.get("PYTHONPATH", "").split(":"):
        if os.path.isdir(pth):
            yield pth


def get_user_directory():
    """Return the user directory where extensions are stored."""
    if INKSCAPE_EXTENSIONS:
        return os.path.abspath(INKSCAPE_EXTENSIONS)

    if "INKSCAPE_PROFILE_DIR" in os.environ:
        return os.path.abspath(
            os.path.expanduser(
                os.path.join(os.environ["INKSCAPE_PROFILE_DIR"], "extensions")
            )
        )

    home = os.path.expanduser("~")
    for pth in _pythonpath():
        if pth.startswith(home):
            return pth


def get_inkscape_directory():
    """Return the system directory where inkscape's core is."""
    for pth in _pythonpath():
        if os.path.isdir(os.path.join(pth, "inkex")):
            return pth


def get_inkscape_version():
    """Attempt to detect the inkscape version"""
    try:
        line = inkscape(version=True, svg_file=None)
    except (ProgramRunError, CommandNotFound):
        return DEFAULT_VERSION
    if isinstance(line, bytes):
        line = line.decode("utf8")
    (major, minor) = line.strip().split(" ")[1].split(".")[:2]
    return "{}.{}".format(int(major), int(minor.split("-")[0]))


def format_requires(string):
    """Get a version requires."""
    primary = string.split("; ", 1)[0]
    if "(" in primary:
        primary, version = primary.split("(", 1)
        return (primary.strip(), version.strip(") "))
    return (primary.strip(), None)


def parse_metadata(data):
    """
    Convert older email based meta data into a newer json format,
    See PEP 566 for details.
    """
    feed_parser = FeedParser()
    feed_parser.feed(data)
    metadata = feed_parser.close()

    def getdict():
        """Multi-dimentional dictionary"""
        return defaultdict(getdict)

    ret = defaultdict(getdict)

    ret["description"] = metadata.get_payload()
    ret["requires"] = [
        format_requires(m) for m in metadata.get_all("Requires-Dist", [])
    ]

    for key, value in metadata.items():
        if key == "Home-page":
            ret["extensions"]["python.details"]["project_urls"]["Home"] = value
        elif key == "Classifier":
            ret["classifiers"] = list(ret["classifiers"])
            ret["classifiers"].append(value)
        else:
            ret[key.lower().replace("-", "_")] = value

    return ret


def clean_author(data):
    """Clean the author so it has consistant keys"""
    for contact in (
        data.get("extensions", {})
        .get("python.details", {})
        .get("contacts", [])
    ):
        if contact["role"] == "author":
            data["author"] = contact["name"]
            data["author_email"] = contact.get("email", "")
            if "<" in data["author"]:
                data["author"], other = data["author"].split("<", 1)
                if "@" in other and not data["author_email"]:
                    data["author_email"] = data["author"].split(">")[0]
    return data


class ExtensionInx(InxFile):
    """Information about an extension specifically"""

    ident = property(lambda self: super().ident or f"[no-id] {self.filename}")
    name = property(lambda self: super().name or f"[unnamed] {self.ident}")

    @property
    def menu(self):
        menu = self.xml.find_one("effect/effects-menu")
        if menu is not None and menu.get("hidden", "false") == "true":
            return ["_hidden", self.name]
        return super().menu
