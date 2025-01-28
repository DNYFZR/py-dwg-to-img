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

import hashlib
from import_sources import RemoteSource


class Wikimedia(RemoteSource):
    name = "Wikimedia"
    icon = "sources/wikimedia.svg"
    base_url = "https://commons.wikimedia.org/w/api.php"

    def search(self, query):
        params = {
            "action": "query",
            "format": "json",
            "uselang": "en",
            "generator": "search",
            "gsrsearch": "filetype:bitmap|drawing filemime:svg " + query,
            "gsrlimit": 40,
            "gsroffset": 0,
            "gsrinfo": "totalhits|suggestion",
            "gsrprop": "size|wordcount",
            "gsrnamespace": 6,
            "prop": "info|imageinfo|entityterms",
            "inprop": "url",
            "iiprop": "url|size|mime|user|extmetadata",
            "iiurlheight": 180,
            "wbetterms": "label",
        }
        pages = []
        try:
            response = self.session.get(self.base_url, params=params).json()
            if "error" in response:
                raise IOError(response["error"]["info"])
            pages = response["query"]["pages"].values()
        except:
            pass

        for item in pages:
            img = item["imageinfo"][0]
            # get standard licenses
            # for non standard licenses we have to get the ShortName and provide the url to the resource
            try:
                license = img["extmetadata"]["License"]["value"]
                if license in ["cc0", "pd"]:
                    license = "cc-0"
            except KeyError:
                license = img["extmetadata"]["LicenseShortName"]["value"]
            yield {
                "id": item.get("pageid", None),
                "name": item["title"].split(":", 1)[-1],
                "author": img["user"],
                "license": license,
                "summary": "",  # No data
                "thumbnail": img["thumburl"],
                "created": item["touched"],
                "descriptionurl": item["canonicalurl"],
                "popularity": 0,  # No data
                "file": img["url"],
            }
