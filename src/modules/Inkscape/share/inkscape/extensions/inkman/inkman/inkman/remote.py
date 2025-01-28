#
# Copyright (C) 2019-2021 Martin Owens
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
Searching for external packages and getting meta data about them.
"""

import os
import requests

try:
    from cachecontrol import CacheControl, CacheControlAdapter
    from cachecontrol.caches.file_cache import FileCache
    from cachecontrol.heuristics import ExpiresAfter
except (ImportError, ModuleNotFoundError):
    CacheControl = None

from .utils import INKSCAPE_VERSION, CACHE_DIR
from .package import PackageItem

PYTHON_VERSION = "py3"


class SearchError(IOError):
    pass


class LocalFile(object):
    """Same API as RemoteFile, but for locals"""

    def __init__(self, basedir, url):
        self.basedir = basedir
        self.url = url

    def __str__(self):
        return self.url

    def filename(self):
        return self.url.split("/")[-1]

    def filepath(self):
        return os.path.join(self.basedir, self.url)

    def normpath(self):
        return os.path.normpath(self.filepath())

    def as_local_file(self):
        filename = self.filepath()
        if os.path.isfile(filename):
            return filename
        raise IOError(f"Can't find file: {filename}")


class RemoteFile(object):
    """A remote file, icon, zip etc"""

    def __init__(self, session, url):
        self.session = session
        self.url = url

    def __str__(self):
        return self.url

    def get(self):
        return self.session.get(self.url)

    def filename(self):
        return self.url.split("/")[-1]

    def filepath(self):
        return os.path.join(CACHE_DIR, self.filename())

    def as_local_file(self):
        if self.url:
            remote = self.get()
            if remote and remote.status_code == 200:
                with open(self.filepath(), "wb") as fhl:
                    fhl.write(remote.content)
                return self.filepath()
        return None


class RemoteArchive(object):
    """The remote archive used to be PyPI but is now inkscape's own website."""

    URL = "https://inkscape.org/gallery/={category}/json/"

    def __init__(self, category, version=INKSCAPE_VERSION):
        self.version = version
        self.url = self.URL.format(category=category)
        self.session = requests.session()
        if CacheControl is not None:
            try:
                self.session.mount(
                    "https://",
                    CacheControlAdapter(
                        cache=FileCache(CACHE_DIR),
                        heuristic=ExpiresAfter(days=1),
                    ),
                )
            except ImportError:
                # This happens when python-lockfile is missing
                pass

    def _remote_file(self, url):
        return RemoteFile(self.session, url)

    def search(self, query, filtered=True):
        """Search for extension packages"""
        for info in self._search(query):
            item = PackageItem(info, remote=self._remote_file)
            if (
                not filtered
                or not self.version
                or self.version in item.targets
            ):
                yield item

    def _search(self, query, tags=[]):
        """Search for the given query and yield each item, will raise if any other response"""
        response = None

        if query is None:
            try:
                response = self.session.get(
                    self.url,
                    params={
                        "tags": tags,
                        "checked": 1,
                        "limit": 10,
                        "order": "extra_status",
                    },
                )
            except requests.exceptions.RequestException as err:
                raise SearchError(str(err))
            except ConnectionError as err:
                raise SearchError(str(err))
            except requests.exceptions.RequestsWarning:
                pass
        else:
            response = self.session.get(
                self.url, params={"q": query, "tags": tags, "checked": 1}
            )
        if response is not None:
            for item in response.json()["items"]:
                yield item
