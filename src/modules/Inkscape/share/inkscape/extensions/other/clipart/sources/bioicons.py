#
# Copyright 2022 Simon Duerr dev@simonduerr.eu
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
Access Bioicons.

Downloads the database to cache and uses it locally for searching.
"""

import json
import requests
from datetime import datetime
import os


from cachecontrol import CacheControl, CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter

from import_sources import RemoteSource


def local_search(query, db):
    for item in db:
        if query.lower() in item["name"].lower():
            yield item
    return


class Bioicons(RemoteSource):
    name = "Bioicons"
    icon = "sources/bioicons.svg"
    db_url = "https://bioicons.com/icons/icons.json"
    icon_url = "https://bioicons.com/icons/"

    def __init__(self, cache_dir):
        self.session = requests.session()
        self.cache_dir = cache_dir
        self.session.mount(
            "https://",
            CacheControlAdapter(
                cache=FileCache(cache_dir),
                heuristic=ExpiresAfter(days=5),
            ),
        )
        # check if local db is up to date with Last Modified header
        try:
            response = requests.head(self.db_url)
        except Exception:
            response = None

        self._json = os.path.join(self.cache_dir, "icons.json")
        if not os.path.isfile(self._json):
            last_modified = 0
        else:
            last_modified = os.path.getmtime(self._json)

        if response is not None:
            last_update = datetime.strptime(
                response.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT"
            ).timestamp()
            # if icon db was modified download new database
            if last_modified < last_update:
                self.to_local_file(self.db_url)

    def search(self, query):
        results = []
        if os.path.isfile(self._json):
            with open(self._json, "r") as f:
                db = json.load(f)
            results = local_search(query, db)

        for item in results:
            yield {
                "id": item["name"],
                "name": item["name"],
                "summary": item["category"],
                "created": None,
                "popularity": 0,
                "author": item["author"],
                "thumbnail": f"{self.icon_url}{item['license']}/{item['category']}/{item['author']}/{item['name']}.svg",
                "file": f"{self.icon_url}{item['license']}/{item['category']}/{item['author']}/{item['name']}.svg",
                "license": item["license"],
            }
