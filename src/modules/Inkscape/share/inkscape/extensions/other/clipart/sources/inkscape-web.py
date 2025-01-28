#
# Copyright 2021 Martin Owens <doctormo@gmail.com>
# Copyright 2022 Simon Duerr <dev@simonduerr.eu>
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

from import_sources import RemoteSource


license_mapping = {
    "PD": "cc-0",
    "CC-0": "cc-0",
    "CC-BY 3.0": "cc-by-3.0",
    "CC-BY 4.0": "cc-by-4.0",
    "CC-BY-SA 4.0": "cc-by-sa-4.0",
    "CC-BY-NC 3.0": "cc-by-nc-3.0",
    "CC-BY-NC-SA 3.0": "cc-by-nc-sa-3.0",
    "CC-BY-NC-SA 4.0": "cc-by-nc-sa-4.0",
    "CC-BY-SA 3.0": "cc-by-sa-3.0",
    "CC-BY-ND 3.0": "cc-by-nd-3.0",
    "ASL": "asl",
    "nbsd": "bsd",
    "GPLv2": "gpl-2",
    "GPLv3": "gpl-3",
    "AGPLv3": "agpl-3",
    "MIT": "mit",
}


class InkscapeWebsite(RemoteSource):
    name = "Inkscape Community"
    icon = "sources/inkscape-web.svg"
    is_default = True

    base_url = "https://inkscape.org/gallery/=artwork/json/"

    def search(self, query):
        """Ask the inkscape website for some artwork"""
        items = []
        try:
            response = self.session.get(self.base_url, params={"q": query})
            items = response.json()["items"]
        except Exception:
            pass

        for item in items:
            if "svg" not in item["type"]:
                continue
            if (
                item["license"] == "(C)"
            ):  # ignore copyrighted items because they cannot be reused
                continue
            yield {
                "id": item["id"],
                "name": item["name"],
                "author": item["author"],
                "license": license_mapping.get(
                    item["license"], item["license"].lower()
                ),
                "summary": item["summary"],
                "thumbnail": item["icon"] or item["links"]["file"],
                "created": item["dates"]["created"],
                "popularity": item["stats"]["liked"],
                "file": item["links"]["file"],
            }
