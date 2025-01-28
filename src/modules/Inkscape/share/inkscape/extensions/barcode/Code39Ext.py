# coding=utf-8
#
# Copyright (C) 2007 Martin Owens
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
Python barcode renderer for Code39 Extended barcodes. Designed for Inkscape.
"""

from .Code39 import Code39

encode = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

charmap = {}

i = 0
for char in encode:
    charmap[char] = i
    i += 1


def get_map(array):
    """Extended encoding maps for full ASCII Code93"""
    result = {}
    for y, x in enumerate(array):
        result[chr(x)] = encode[y]

    return result


# MapA is eclectic, but B, C, D are all ASCII ranges
mapA = get_map(
    [
        27,
        28,
        29,
        30,
        31,
        59,
        60,
        61,
        62,
        63,
        91,
        92,
        93,
        94,
        95,
        123,
        124,
        125,
        126,
        127,
        0,
        64,
        96,
        127,
        127,
        127,
    ]
)  # %
mapB = get_map(range(1, 26))  # $
mapC = get_map(range(33, 58))  # /
mapD = get_map(range(97, 122))  # +


class Code39Ext(Code39):
    """Render Code39 Barcodes"""

    def encode(self, text):
        # We are only going to extend the Code39 barcodes
        result = ""
        for character in text:
            if character in mapA:
                character = "%" + mapA[character]
            elif character in mapB:
                character = "$" + mapB[character]
            elif character in mapC:
                character = "/" + mapC[character]
            elif character in mapD:
                character = "+" + mapD[character]
            result = result + character

        return Code39.encode(self, result)
