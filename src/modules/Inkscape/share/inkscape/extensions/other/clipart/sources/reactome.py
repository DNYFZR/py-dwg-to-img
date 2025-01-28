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
Access Reactome Content Services.
"""

import re

from import_sources import RemoteSource

TAG_REX = re.compile(r"<[^<]+?>")


class Reactome(RemoteSource):
    name = "Reactome (Bio)"
    icon = "sources/reactome.svg"
    search_url = "https://reactome.org/ContentService/search/query"
    file_url = "https://reactome.org/icon/{stId}.svg"
    icon_url = "https://reactome.org/icon/{stId}.png"
    all_licence = "cc-by-sa-4.0"

    def search(self, query):
        params = {
            "query": query,
            "types": "Icon",
            "cluster": "true",
            "Start row": 0,
            "rows": 100,
        }
        response = {}
        try:
            response = self.session.get(self.search_url, params=params).json()
        except Exception:
            pass

        if "messages" in response and "No entries" in response["messages"][0]:
            return
        for cats in response.get("results", []):
            for entry in cats["entries"]:
                yield {
                    "id": entry["dbId"],
                    "name": TAG_REX.sub("", entry["name"]),
                    "author": "Reactome/" + entry.get("iconDesignerName", "Unknown"),
                    "summary": TAG_REX.sub("", entry.get("summation", "")),
                    "created": None,  # No data
                    "popularity": 0,  # No data
                    "thumbnail": self.icon_url.format(**entry),
                    "file": self.file_url.format(**entry),
                    "license": self.all_licence,
                }
