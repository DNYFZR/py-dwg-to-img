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

"""Global export settings / object storage"""


from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..xamlobjects import ResourceDictionary


class XAMLExportGlobalSettings:
    """Storage for XAML export converter settings"""

    def __init__(self) -> None:
        self.target = "wpf"
        self.mode = "lowlevel"
        self.indent = 4
        self.swatches = "color"
        self.referencing_type = "DrawingImage"
        self.xaml_namespaces: Dict[Optional[str], str] = {}
        self.xaml_namespaces_reversed: Dict[str, Optional[str]] = {}
        self.layers_as_resources = True
        self.TOPLEVEL_DICT: "ResourceDictionary"

    @property
    def avalonia(self):
        """Returns if the settings target Avalonia"""
        return self.target != "wpf"

    @property
    def wpf(self):
        """Returns if the settings target WPF"""
        return self.target == "wpf"


GLOBAL_SETTINGS = XAMLExportGlobalSettings()
