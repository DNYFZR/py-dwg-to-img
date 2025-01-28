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

import sys
import json
import logging

from import_sources import RemoteSource, RemoteFile
from urllib.parse import urljoin, parse_qs

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class OpenClipartFile(RemoteFile):
    def get_file(self):
        """Extract search result from html"""
        response = self.remote.session.get(self.info["file"])
        soup = BeautifulSoup(response.text, features="lxml")
        for script in soup.find_all("script"):
            content = script.contents
            if content and "image" in content[0]:
                try:
                    data = json.loads(content[0])
                    return self.remote.to_local_file(data["image"]["url"])
                except Exception:
                    continue
        logging.error("Couldn't load svg from %s", self.info["file"])


class OpenClipart(RemoteSource):
    name = "Open Clipart Library"
    icon = "sources/ocal.svg"
    base_url = "https://openclipart.org/search/"
    is_enabled = BeautifulSoup is not None
    file_cls = OpenClipartFile

    def html_search(self, response):
        """Extract search results from html"""
        soup = BeautifulSoup(response.text, features="lxml")
        for div in soup.find_all("div", {"class": "artwork"}):
            if div.a and div.a.img:
                link = urljoin(self.base_url, div.a.get("href"))
                img = urljoin(self.base_url, div.a.img.get("src"))

                yield {
                    "file": link,  # Not the actual file yet (see above)
                    "name": div.a.img.get("alt"),
                    "thumbnail": img,
                    "author": "OpenClipart",
                    "license": "cc-0",
                }

        for page in soup.find_all("a", {"class": "page-link", "aria-label": "Next"}):
            if "=" in page.get("href", ""):
                yield lambda: self._search(**parse_qs(page.get("href").split("?")[-1]))

    def search(self, query):
        """HTML searching for now"""
        return self._search(query=query)

    def _search(self, **params):
        try:
            response = self.session.get(self.base_url, params=params)
        except Exception:
            return []

        items = []
        next_page = None
        for item in self.html_search(response):
            if callable(item):
                next_page = item
            else:
                items.append(item)
        # Often ocal will have empty pages, weirdly.
        if not items and next_page:
            return next_page()
        # None empty page, return all
        if next_page:
            items.append(next_page)
        return items
