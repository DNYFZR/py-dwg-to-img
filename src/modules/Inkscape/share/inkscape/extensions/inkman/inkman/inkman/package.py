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
Support for constructing and understanding installed extensions
as python packages.

Start by using 'PackageLists' and iterate over to get 'PackageList' objects
iterate over those to get 'Package' objects and use those to know more
information about the installed packages.
"""

import os
import sys
import json
from fnmatch import fnmatch
from typing import List

from .factory import PackageInxFile
from .utils import (
    DATA_DIR,
    parse_metadata,
    clean_author,
)

# The ORDER of these places is important, when installing packages it will
# choose the FIRST writable directory in the lsit, so make sure that the
# more preferable locations appear at the top.
EXTENSION_PLACES = []

for path in sys.path:
    if "extensions" in path:
        if "/bin" in path:
            path = path.replace("/bin", "")
        EXTENSION_PLACES.append(path)

CORE_ICON = os.path.join(DATA_DIR, "pixmaps", "core_icon.svg")
ORPHAN_ICON = os.path.join(DATA_DIR, "pixmaps", "orphan_icon.svg")
DEFAULT_ICON = os.path.join(DATA_DIR, "pixmaps", "default_icon.svg")
MODULE_ICON = os.path.join(DATA_DIR, "pixmaps", "module_icon.svg")


class PackageItem(object):
    """
    Gets information about the package using requests.

    Can be remote, or local json file.
    """

    default_icon = DEFAULT_ICON

    @classmethod
    def is_pkg(cls, info):
        """Returns true if this info package is considered a managed package"""
        for field in ("name", "author", "verified", "links", "summary"):
            if field not in info:
                return False
        return True

    def __init__(self, info, remote=None):
        if not self.is_pkg(info):
            raise ValueError("Not a valid package, refusing to create it.")

        self.info = info
        self.remote = remote
        self.installed = None
        self._installer = None
        self._uninstaller = None
        self._missing = []
        self._icon = None

    ident = property(lambda self: self.info.get("id"))
    url = property(lambda self: self.info["links"]["file"])
    link = property(lambda self: self.info["links"]["html"])
    name = property(lambda self: self.info["name"] or "Unnamed")
    license = property(lambda self: self.info.get("license") or "")
    author = property(lambda self: self.info["author"])
    tags = property(lambda self: self.info.get("tags", []))

    stars = property(lambda self: self.info["stats"]["liked"])
    downloads = property(lambda self: self.info["stats"]["downloaded"])
    verified = property(lambda self: self.info["verified"])
    recommended = property(
        lambda self: self.info["stats"].get("extra", 0) == 7
    )

    targets = property(lambda self: self.info.get("Inkscape Version", []))
    target = property(lambda self: ", ".join(self.targets))

    @property
    def summary(self):
        ret = self.info["summary"] or "No summary"
        if len(ret) > 110:
            ret = ret.split(". ", 1)[0]
        if len(ret) > 110:
            ret = ret[:110].rsplit(" ", 1)[0] + "..."
        return ret

    @property
    def version(self):
        if "version" in self.info:
            return str(self.info["version"])
        if "stats" in self.info and "revisions" in self.info["stats"]:
            return str(int(self.info["stats"]["revisions"]) + 1)
        return "?"

    def set_installer(self, fn):
        self._installer = fn

    def set_uninstaller(self, fn, *args):
        def _inner(info):
            return fn(info, *args)

        self._uninstaller = _inner

    def set_installed(self, installed=True):
        self.installed = installed

    def is_installable(self, version):
        if version not in self.targets or not self.verified:
            return False
        return bool(not self.installed and self._installer)

    def is_uninstallable(self):
        return bool(self._uninstaller)

    def install(self):
        """Install the remote package"""
        if not self.remote:
            raise IOError("Can not install without a defined remote")
        url = self.remote(self.info["links"]["file"])
        msg = self._installer(url.as_local_file(), self.info)
        self.set_installed(True)
        return msg

    def uninstall(self):
        """Remove the pakage if possible"""
        if self._uninstaller(self.info):
            self.set_installed(False)
            return True
        return False

    def get_icon(self):
        if self._icon:
            return self._icon
        if self.info.get("icon"):
            if not self.remote:
                raise IOError("Can get icon without a defined remote")
            icon = self.remote(self.info["icon"])
            self._icon = icon.as_local_file() or self.default_icon
            return self._icon
        for filename in self.get_files():
            name = os.path.basename(filename)
            if name in ("icon.svg", "icon.png"):
                self._icon = os.path.abspath(filename)
                return filename
        return self.default_icon

    def get_files(self, missing=False):
        """List files"""
        return [
            name
            for name in self.info.get("files", [])
            if missing or name not in self._missing
        ]

    def get_inx_files(self) -> List[PackageInxFile]:
        return [
            PackageInxFile(self.remote(f"../{name}").normpath())
            for name in self.get_files()
            if name.endswith(".inx")
        ]


class OrphanedItem(PackageItem):
    """
    A special kind of item to collect all orphaned files
    """

    default_icon = ORPHAN_ICON

    def __init__(self, parent):
        super().__init__(
            {
                "name": "Orphan Extensions",
                "author": "Various",
                "verified": False,
                "summary": "Old and manually installed extensions",
                "license": "Unknown",
                "links": {},
                "version": "-",
                "stats": {"liked": -1, "downloaded": -1},
            }
        )

        self._icon = self.default_icon
        self._parent = os.path.abspath(parent)
        self._files = set()
        self._removed = set()
        self._items = {}

    def _get_target_file(self, filename):
        if not os.path.isabs(filename):
            filename = os.path.join(self._parent, filename)
        path = os.path.abspath(filename)
        return path.replace(self._parent, "").lstrip("/")

    def add_file(self, filename):
        """Add a file to the 'this file exists' list"""
        self._files.add(self._get_target_file(filename))

    def remove_file(self, filename, item=None):
        """Add a file to the 'this file is said to exist' list"""
        fn = self._get_target_file(filename)
        self._removed.add(fn)
        if item is not None:
            self._items[fn] = item

    def get_files(self, filters=()):
        """Returns a filtered set of files which exist, minus ones said to exist"""
        if not filters:
            filters = ("*",)
        items = []
        for item in self._files - self._removed:
            if any([fnmatch(item, filt) for filt in filters]):
                items.append(item)
        return items

    def get_missing(self):
        """Returns a set of files which don't exist, even though they were said to"""
        return [
            (fn, self._items.get(fn, None))
            for fn in self._removed - self._files
        ]


class PythonItem(PackageItem):
    """
    A python package that has an inx file, but was never installed properly.
    """

    def __init__(self, pip):
        self.pip = pip
        info = self.pip.get_metadata()
        super().__init__(
            {
                "pip": True,
                "name": info["name"],
                "summary": info["summary"],
                "author": info["author"] or "Unknown",
                "version": info["version"],
                "license": info["license"],
                "verified": False,
                "links": {},
                "stats": {"liked": -1, "downloaded": -1},
            }
        )

    def get_files(self):
        return self.pip.package_files()


class PythonPackage(object):
    """
    A reprisentation of the python package, NOT the json based packages.
    """

    name = property(lambda self: self.get_metadata()["name"])
    version = property(lambda self: self.get_metadata()["version"])

    def __init__(self, path, parent):
        self._metadata = None
        self.path = path
        self.parent = parent

    def get_inx(self):
        """Yields all of the inx files in this package"""
        for filename in self.package_files():
            if filename.endswith(".inx"):
                yield filename

    def package_files(self):
        """Return a generator of all files in this installed package"""
        parent = os.path.abspath(os.path.dirname(self.path))
        record = self.get_file("RECORD")
        if not record:
            return
        for line in record.split("\n"):
            if line and "," in line:
                (filename, checksum, size) = line.rsplit(",", 2)
                # XXX Check filesize or checksum?
                if not os.path.isabs(filename):
                    filename = os.path.join(parent, filename)
                yield filename

    def get_metadata(self):
        """Returns the metadata from an array of known types"""
        if self._metadata is None:
            for name in ("METADATA", "PKG-INFO"):
                md_mail = self.get_file(name)
                if md_mail:
                    self._metadata = parse_metadata(md_mail)

        if self._metadata is None:
            md_json = self.get_file("metadata.json")
            if md_json:
                self._metadata = clean_author(json.loads(md_json))

        if self._metadata is None:
            raise KeyError(f"Can't find package meta data: {self.path}")
        return self._metadata

    def get_file(self, name):
        """Get filename if it exists"""
        if not self.path or not os.path.isdir(self.path):
            return None
        path = os.path.join(self.path, name)
        if os.path.isfile(path):
            with open(path, "r") as fhl:
                return fhl.read()
        return None

    def get_depedencies(self):
        """Return a list of other pip packages this packages needs"""
        return self.get_metadata()["requires"]
