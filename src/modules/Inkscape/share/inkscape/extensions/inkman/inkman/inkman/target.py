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
Target a directory to install resources into.
"""

import os
import sys
import json
import logging
from shutil import which

from inkex.command import call

from .archive import Archive, UnrecognizedArchiveFormat
from .remote import RemoteArchive, LocalFile
from .utils import INKSCAPE_PROFILE, CACHE_DIR, ExtensionInx
from .package import PackageItem, OrphanedItem, PythonItem, PythonPackage


class BasicTarget(object):
    """
    A location where to install something, plus how to search for it.
    """

    version_specific = False

    def __init__(self, category, label, path, is_search=False, filters=()):
        self.category = category
        self.label = label
        self.path = os.path.join(INKSCAPE_PROFILE, path)
        self.is_search = is_search
        self.archive = RemoteArchive(category)
        self.filters = filters
        self._installed = None

    def search(self, query, filtered=False):
        """Search the online archive for things"""
        for pkg in self.archive.search(query, filtered):
            pkg.set_installer(self._install)
            yield pkg

    def is_writable(self):
        """Can the folder be written to (for installation)"""
        try:
            return os.access(self.path, os.W_OK)
        except IOError:
            return False

    def _install(self, filename, info):
        if not info.get("id"):
            info["id"] = self.generate_id(filename)

        if not info.get("id"):
            raise ValueError("Id is a required field for packages")

        if filename.endswith(".zip"):
            location = info["id"]
            fname = "info.json"
            info["files"] = list(self.install_zip_files(filename, location))
        else:
            location = "pkg"
            fname = info["id"] + ".json"
            info["files"] = [
                self.write_file(filename, os.path.basename(filename))
            ]

        self.write_file(json.dumps(info).encode("utf8"), fname, extra=location)

        return "Package installed! Remember to restart inkscape to use it!"

    def _uninstall(self, info, json_file):
        self._installed = None
        for fname in info.get("files"):
            self.remove_file(fname)
        if json_file and os.path.isfile(json_file):
            self.remove_file(json_file)
        return True

    def install_zip_files(self, filename, location):
        """Install the files in the zip filename as non-pip files"""
        with Archive(filename) as archive:
            for filename in archive.filenames():
                yield self.write_file(
                    archive.read(filename), filename, extra=location
                )

    def generate_id(self, filename):
        """User submitted zip file, generate an id as best we can"""
        return filename.replace(".zip", "")

    def list_installed(self, cached=True):
        """
        Loops through all the files in the target path and finds all the installed items.
        """
        if cached and self._installed:
            yield from self._installed
            return

        self._installed = []
        for item in self._list_installed():
            self._installed.append(item)
            yield item

    def _list_installed(self):
        orphans = OrphanedItem(self.path)
        for root, subs, files in os.walk(self.path):
            for fname in files:
                fpath = os.path.join(root, fname)
                name = self.unprefix_path(fpath)
                if fname.endswith(".json"):
                    if os.path.basename(fpath) == "package.json":
                        continue
                    with open(fpath, "rb") as fhl:
                        data = fhl.read()
                        info = json.loads(data)
                        if not PackageItem.is_pkg(info):
                            continue

                        item = PackageItem(
                            info, remote=self._remote_or_local_file(root)
                        )
                        item.set_uninstaller(self._uninstall, fpath)
                        yield item

                        for pkg_file in item.get_files(missing=True):
                            orphans.remove_file(pkg_file, item)
                            orphans.remove_file(
                                os.path.join(root, pkg_file), item
                            )
                else:
                    orphans.add_file(name)

        for fname, item in orphans.get_missing():
            if item is not None:
                item._missing.append(fname)

        if orphans.get_files(filters=self.filters):
            yield orphans

    def _remote_or_local_file(self, basedir):
        # If a json file specifies something that's local, it's "ALWAYS" local to the
        # json file as a basedir.
        def _inner(url):
            if "://" not in url:
                return LocalFile(basedir, url)
            return self.archive._remote_file(url)

        return _inner

    def write_file(self, source, source_name=None, extra=None):
        target = os.path.join(self.path, extra) if extra else self.path

        if isinstance(source, str):
            if not source_name:
                source_name = source
            with open(source, "rb") as fhl:
                source = fhl.read()

        path = os.path.join(target, source_name)
        filedir = os.path.dirname(path)
        if not os.path.isdir(filedir):
            os.makedirs(filedir)

        # Ignore paths
        if not os.path.isdir(path):
            with open(path, "wb") as whl:
                whl.write(source)

        return self.unprefix_path(path)

    def remove_file(self, filename):
        """
        Remove the given file and clean up
        """
        if not filename.startswith(self.path):
            filename = os.path.join(self.path, filename)
        if os.path.isfile(filename):
            os.unlink(filename)

        # Recursively clean up directories (if empty)
        path = os.path.dirname(filename)
        while path.lstrip("/") != self.path.lstrip("/"):
            if os.listdir(path):
                break
            os.rmdir(path)
            path = os.path.dirname(path)

    def unprefix_path(self, path):
        """
        Removes the prefix of the given path, if it's based in self.path
        """
        # Strip just the OS seperator, but what if the files were moved from another OS?
        return path.replace(self.path, "").lstrip("/").lstrip("\\")


class ExtensionsTarget(BasicTarget):
    """
    Extra functional target for extensions (pip based)
    """

    version_specific = True

    def get_pip(self):
        path = os.path.abspath(os.path.join(self.path, "bin"))
        return which("pip", path=path + ":" + os.environ["PATH"])

    def _install(self, filename, info):
        if self.is_pip_package(filename):
            results = self.pip_install(filename)
            if results:
                info["pip"] = True
                info["id"] = results.strip().split()[-1]
                fname = info["id"] + ".json"
                self.write_file(
                    json.dumps(info).encode("utf8"), fname, extra="lib"
                )
                return (
                    "Python Package installed! "
                    "Remember to restart inkscape to use it!"
                )
            return "Failed to install, something is wrong with your setup."

        return super()._install(filename, info)

    def _uninstall(self, info, json_file):
        self._installed = None
        if not info.get("pip"):
            return super()._uninstall(info, json_file)
        self.pip_uninstall(info["name"])
        if json_file and os.path.isfile(json_file):
            self.remove_file(json_file)
        return True

    def is_pip_package(self, filename):
        """Return true if this is a detectable pip package"""
        if filename.endswith(".whl"):
            return True
        try:
            with Archive(filename) as archive:
                for filename in archive.filenames():
                    if filename.endswith("setup.py"):
                        return True
        except UnrecognizedArchiveFormat:
            return False
        return False

    def pip_install(self, filename):
        """Install the filename as a pip package"""
        pip = self.get_pip()
        if pip is None:
            logging.error(
                "This package requires python VirtualEnv which is not available on your system."
            )
            return None
        results = call(
            pip,
            "install",
            ("isolated", True),
            ("disable-pip-version-check", True),
            ("cache-dir", CACHE_DIR),
            filename,
        ).decode("utf8")
        return results

    def pip_uninstall(self, name):
        """Uninstall the given pip package name"""
        results = call(
            self.get_pip(),
            "uninstall",
            ("disable-pip-version-check", True),
            name,
        ).decode("utf8")
        return results

    def generate_id(self, filename):
        """Extensions have an id internally, try and use it"""
        try:
            with Archive(filename) as archive:
                inxes = [
                    item
                    for item in archive.filenames()
                    if item.endswith(".inx")
                ]
                if not inxes:
                    raise IOError(
                        "Refusing to install extension without inx file!"
                    )
                inx = ExtensionInx(archive.read(inxes[0]).decode("utf-8"))
            return inx.ident
        except UnrecognizedArchiveFormat:
            raise IOError(
                "Refusing the install extension without inx file (unknown archive)"
            )
        except:  # noqa: E722
            raise IOError("Refusing the install extension with bad inx file!")

    def _list_installed(self):
        """
        Add pip packages to file lists.
        """
        orphans = None
        packages = {}
        all_deps = set()
        all_files = set()

        # First collect a list of python packages installed
        for node in self.get_python_paths():
            if node.endswith(".dist-info") or node.endswith(".egg-info"):
                package = PythonPackage(node, self.path)
                packages[package.name] = package
                all_files |= set(package.package_files())
                for dep, _ in package.get_depedencies():
                    all_deps.add(dep)

        # Now return all non pip packaged extensions (from super)
        for item in super()._list_installed():
            if item.info.get("pip", False):
                if self.info.ident not in packages:
                    print(f"Can't find python package: {item.ient}")
                    continue

                pip_pkg = packages[item.ident]
                item.info["version"] = pip_pkg.version

            if isinstance(item, OrphanedItem):
                orphans = item
            else:
                yield item

        # Remove all orphaned files that were installed by pip packages
        if orphans is not None:
            for fn in all_files:
                orphans.remove_file(fn)
            if orphans.get_files(filters=self.filters):
                # Yield if we still have orphans
                yield orphans

        # Now what to do with all these remaining packages, pretend their installed?
        for name, package in packages.items():
            for inx in package.get_inx():
                item = PythonItem(package)
                item.set_uninstaller(self._uninstall, None)
                yield item
                break

        for dep in all_deps:
            if dep not in packages:
                # These packages are often just installed into the system, nothing to say.
                # XXX But, there is a future where pip could be interigated.
                # logging.error(f"Missing python depedency: {dep}")
                continue
            packages.pop(dep)

    def get_python_paths(self):
        """Returns paths related to the python packages"""
        pyver = "python" + sys.version[:3]
        for varient in [
            os.path.join(self.path, "lib", pyver, "site-packages"),
        ]:
            if os.path.isdir(varient):
                for subpath in os.listdir(varient):
                    yield os.path.join(varient, subpath)

    def get_package(self, name, version=None):
        """Test every package in this list if it matches the name and version"""
        for package in self.iter():
            found = package.is_package(name, version=version)
            if found:
                return package
        return None
