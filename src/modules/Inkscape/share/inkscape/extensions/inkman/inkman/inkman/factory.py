#
# Copyright 2020 Martin Owens <doctormo@gmail.com>
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
Extract information from an inx file and follow all the files.
"""

import os
import sys

from datetime import datetime
from modulefinder import ModuleFinder
from collections import defaultdict

from inkex.inx import InxFile

from inkman import __pkgname__, __version__
from inkman.utils import DATA_DIR

MODULES = (
    (
        "Depricated",
        "Using depricated modules {names}",
        "Critical",
        (
            "bezmisc",
            "cubicsuperpath",
            "simplestyle",
            "cspsubdiv",
            "ffgeom",
            "simplepath",
            "simpletransform",
        ),
    ),
    (
        "Unusual",
        "Unusual modules being used {names}",
        "Warning",
        ("argparse",),
    ),
    ("Ignored", None, None, ("os", "sys", "lxml")),
)


class PackageInxFile(InxFile):
    def __init__(self, filename):
        super().__init__(filename)
        self.inx_file = filename

    def get_file_root(self):
        return os.path.dirname(self.inx_file)

    def get_script(self):
        """Return the file the INX points to"""
        if self.script.get("location", None) in ("inx", None):
            return os.path.join(self.get_file_root(), self.script["script"])
        raise IOError("Can't find script filename")


class IncludeFile(object):
    """A file to include in the package"""

    def __init__(self, root, filepath, target=None):
        self.root = root
        self.filepath = filepath
        self.name = os.path.basename(filepath)
        self.target = target or os.path.dirname(filepath)

    def __repr__(self):
        return f"<File name='{self.name}'>"

    def file_icon(self):
        """Return a filename type"""
        ext = self.filepath.rsplit(".", 1)[-1]
        if ext in ("inx", "py", "txt", "svg", "png"):
            return ext
        return "default"

    def detect_deps(self, modules=False):
        if not self.filepath.endswith(".py"):
            return [], []
        # We want to find all modules imported by the script directly
        # So we set the location to nowhere and collect the badmodules
        finder = ModuleFinder("never-land")
        finder.run_script(self.filepath)
        # TODO: split out local modules, system modules and genuine deps

        deps, mods = [], []
        for key, locs in finder.badmodules.items():
            if "__main__" not in locs:
                continue
            try:
                mod_path = finder.find_module("inkman", path=sys.path)[1]
                if "/python" in mod_path:
                    if "site-packages" in mod_path:
                        deps.append(key.split(".")[0])
                elif mod_path.startswith(self.root):
                    mods.append(mod_path)
            except ImportError:
                continue
        return mods, deps


class GeneratePackage(object):
    """A generated package based on data"""

    def __init__(
        self, inx_files, template=os.path.join(DATA_DIR, "setup.template")
    ):
        with open(template, "r") as fhl:
            self._template = fhl.read()
        self.files = []
        self.requires = set()
        self.warnings = defaultdict(list)
        self.name = ""
        self.ident = ""

        for x, inx_file in enumerate(inx_files):
            try:
                inx = PackageInxFile(inx_file)
            except Exception as err:
                self.add_warning(f"Can't add file {inx_file}: {err}", 5)
                continue
            self._add_file(inx.get_file_root(), inx.inx_file)
            self._add_file(inx.get_file_root(), inx.get_script())
            if not x:
                self.name = inx.name or ""
                self.ident = inx.ident.replace(".", "-")

    def _add_file(self, root, fname):
        included = IncludeFile(root, fname)
        self.files.append(included)
        (mods, deps) = included.detect_deps()
        for dep in deps:
            self._add_dep(dep)
        for fname in mods:
            self._add_file(root, fname)
        print(f"DEP: {self.requires}")

    def _add_dep(self, name):
        """Try and find the package associated with this name"""
        for list_name, warning, level, mod_list in MODULES:
            if name in mod_list:
                self.warnings[list_name].append(name)
                return
        self.requires.add(name)

    def generate_setup(self, target):
        """Generates a setup.py file contents"""
        args = {
            "__pkgname__": __pkgname__,
            "__version__": __version__,
            "year": datetime.now().year,
            "readme": self.generate_readme(target),
            "ident": self.generate_ident(),
            "version": self.generate_version(),
            "description": self.widget("entry_name").get_text(),
            "author": self.widget("entry_author").get_text(),
            "author_email": self.widget("entry_email").get_text(),
            "url": self.widget("entry_url").get_text(),
            "license": self.widget("licenses").get_active_id(),
            "datafiles": self.generate_datafiles(),
            "requires": self.generate_requires(),
            "classifiers": "",  # TODO
        }
        return self._template.format(**args)

    def generate_ident(self):
        """Generate the ident from the text entry"""
        ident = self.widget("entry_ident").get_text()
        ident = ident.replace(" ", "-").lower()
        self.widget("entry_ident").set_text(ident)
        return "inx-" + ident

    def generate_datafiles(self):
        """Generate a list of datafile and their install location"""
        result = ""
        template = "        ('{target}', ['{file}']),\n"  # noqa: F841
        # 2. Loop through all the file objects in the list
        # 3. Add them to the final result
        return result.strip()

    def generate_requires(self):
        """Generate a list of required modules"""
        # TODO: Version keeping
        result = ""
        # 1. Loop through all the dep objects in the list
        # 2. Append them to the result
        return result


if __name__ == "__main__":
    gen = GeneratePackage(sys.argv[1:])
