#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2020-2022 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
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

"""Utilities for conversion"""

import inkex

from ..xamlobjects import XAMLObject


def convert_attributes(source, target: XAMLObject, definitions):  # convert with dict
    """Extracts attribute from source and writes it to target by using definition.
    Definition types:
    * lambda(str) -> str
    * Dict map
    * List -> capitalizes entry
    4th entry of definition: default XAML value
    5th entry of definition: default SVG value
    """
    for dfn in definitions:
        val = None
        if isinstance(source, inkex.Style):
            val = source(dfn[0])
        elif source is not None:
            val = source.get(dfn[0], None)
        if val is None and len(dfn) == 5:
            # set to the default SVG value
            val = dfn[4]
        if val is None:
            continue
        result: str = ""
        if isinstance(dfn[2], dict):
            # This should be always true, by the EnumValue construct in properties
            # handling
            if val in dfn[2]:
                result = dfn[2][val]
            elif len(dfn) == 5:
                result = dfn[2][dfn[4]]
        if isinstance(dfn[2], list):
            if val in dfn[2] and isinstance(val, str):
                result = val.capitalize()
        if callable(dfn[2]):
            result = dfn[2](val)
        target.add_property(dfn[1], result, None if len(dfn) < 4 else dfn[3])
