#
# Copyright 2021 Martin Owens <doctormo@gmail.com>
# Copyright 2022 Simon Duerr <dev@simonduerr.eu>
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
Base module for all import web search source modules.
"""

import re
import os
import sys
import logging
import requests
import importlib

from cachecontrol import CacheControl, CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter

from inkex.command import CommandNotFound, ProgramRunError, call
from collections import defaultdict

LICENSE_ICONS = os.path.join(os.path.dirname(__file__), "licenses")

LICENSES = {
    "cc-0": {
        "name": "CC0",
        "modules": ["nocopyright"],
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "overlay": "cc0.svg",
    },
    "cc-by-3.0": {
        "name": "CC-BY 3.0 Unported",
        "modules": ["by"],
        "url": "https://creativecommons.org/licenses/by/3.0/",
        "overlay": "cc-by.svg",
    },
    "cc-by-4.0": {
        "name": "CC-BY 4.0 Unported",
        "modules": ["by"],
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "overlay": "cc-by.svg",
    },
    "cc-by-sa-4.0": {
        "name": "CC-BY SA 4.0",
        "modules": ["by", "sa"],
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "overlay": "cc-by-sa.svg",
    },
    "cc-by-sa-3.0": {
        "name": "CC-BY SA 3.0",
        "modules": ["by", "sa"],
        "url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "overlay": "cc-by-sa.svg",
    },
    "cc-by-nc-sa-4.0": {
        "name": "CC-BY NC SA 4.0",
        "modules": ["by", "sa", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "overlay": "cc-by-nc-sa.svg",
    },
    "cc-by-nc-sa-3.0": {
        "name": "CC-BY NC SA 3.0",
        "modules": ["by", "sa", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "overlay": "cc-by-nc-sa.svg",
    },
    "cc-by-nc-3.0": {
        "name": "CC-BY NC 3.0",
        "modules": ["by", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc/3.0/",
        "overlay": "cc-by-nc.svg",
    },
    "cc-by-nd-3.0": {
        "name": "CC-BY ND 3.0",
        "modules": ["by", "nd"],
        "url": "https://creativecommons.org/licenses/by-nd/3.0/",
        "overlay": "cc-by-nd.svg",
    },
    "gpl-2": {
        "name": "GPLv2",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt",
        "overlay": "gpl.svg",
    },
    "gpl-3": {
        "name": "GPLv3",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/gpl-3.0.txt",
        "overlay": "gpl.svg",
    },
    "agpl-3": {
        "name": "AGPLv3",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/agpl-3.0.txt",
        "overlay": "gpl.svg",
    },
    "mit": {
        "name": "MIT",
        "modules": ["retaincopyrightnotice"],
        "url": "https://mit-license.org/",
        "overlay": "mit.svg",
    },
    "asl": {
        "name": "Apache License",
        "modules": ["retaincopyrightnotice"],
        "url": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "overlay": "asl.svg",
    },
    "bsd": {
        "name": "BSD",
        "modules": ["retaincopyrightnotice", "noendorsement"],
        "url": "https://opensource.org/licenses/BSD-3-Clause",
        "overlay": "bsd.svg",
    },
}


class RemotePage:
    """Lazy access to paging systems"""

    icon = "sources/next_page.svg"
    string = property(lambda self: "Next Page")

    def __init__(self, remote, func):
        self.func = func
        self.remote = remote

    def get_next_page(self):
        for info in self.func():
            yield self.remote.result_to_cls(info)


class RemoteFile:
    """Lazy access to remote files"""

    icon = property(lambda self: self.remote.to_local_file(self.info["thumbnail"]))
    get_file = lambda self: self.remote.to_local_file(self.info["file"])

    def __init__(self, remote, info):
        for field in ("name", "thumbnail", "license", "file"):
            if field not in info:
                raise ValueError(f"Field {field} not provided in RemoteFile package")
        self.info = info
        self.remote = remote

    @property
    def string(self):
        return self.info["name"]

    @property
    def license(self):
        return self.info["license"]

    def get_overlay(self):
        return self.license_info["overlay"]

    @property
    def license_info(self):
        return LICENSES.get(
            self.license,
            {
                "name": "Unknown",
                "url": self.info.get("descriptionurl", ""),
                "modules": [],
                "overlay": "unknown.svg",
            },
        )

    @property
    def author(self):
        return self.info["author"]


class RemoteSource:
    """A remote source of svg images which can be searched and downloaded"""

    # These are the properties that should be overridden in your class
    name = None
    icon = None
    file_cls = RemoteFile
    page_cls = RemotePage
    is_default = False
    is_enabled = True

    @classmethod
    def load(cls, name):
        """Load the file or directory of remote sources"""
        if os.path.isfile(name):
            sys.path, sys_path = [os.path.dirname(name)] + sys.path, sys.path
            try:
                importlib.import_module(os.path.basename(name).rsplit(".", 1)[0])
            except ImportError:
                logging.error(f"Failed to load module: {name}")
            sys.path = sys_path
        elif os.path.isdir(name):
            for child in os.listdir(name):
                if not child.startswith("_") and child.endswith(".py"):
                    cls.load(os.path.join(name, child))

    def search(self, query, tags=[]):
        """
        Search for the given query and yield basic informational blocks t hand to file_cls.

        Required fields per yielded object are: name, license, thumbnail and file.
        Optional fields are: id, summary, author, created, popularity
        """
        raise NotImplementedError(
            "You must implement a search function for this remote source!"
        )

    sources = {}

    def __init_subclass__(cls):
        if cls != RemoteSource:
            cls.sources[cls.__name__] = cls

    def __init__(self, cache_dir):
        self.session = requests.session()
        self.cache_dir = cache_dir
        try:
            self.session.mount(
                "https://",
                CacheControlAdapter(
                    cache=FileCache(cache_dir),
                    heuristic=ExpiresAfter(days=5),
                ),
            )
        except ImportError:
            # This happens when python-lockfile is missing, disable cachecontrol
            pass

    def __del__(self):
        self.session.close()

    def file_search(self, query):
        """Search for extension packages"""
        for info in self.search(query):
            yield self.result_to_cls(info)

    def result_to_cls(self, info):
        if callable(info):
            return self.page_cls(self, info)
        return self.file_cls(self, info)

    def to_local_file(self, url):
        """Get a remote url and turn it into a local file"""
        filepath = os.path.join(self.cache_dir, url.split("/")[-1])
        headers = {"User-Agent": "Inkscape"}
        try:
            remote = self.session.get(
                url, headers=headers
            )  # needs UserAgent otherwise many 403 or 429 for wiki commons
        except requests.exceptions.RequestException as err:
            return None
        except ConnectionError as err:
            return None
        except requests.exceptions.RequestsWarning:
            pass

        if remote and remote.status_code == 200:
            with open(filepath, "wb") as fhl:
                # If we don't have data, return None (instead of empty file)
                if fhl.write(remote.content):
                    return filepath
        return None
