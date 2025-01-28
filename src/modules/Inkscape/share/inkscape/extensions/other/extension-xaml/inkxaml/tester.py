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

"""Test utilities for the XAML exporter"""

from io import BytesIO
import re

from lxml import etree

from inkex.tester import TestCase

from .svg2xaml import XamlOutput


class Svg2XamlTester(TestCase):
    """Base class for SVG->XAML conversion tests"""

    KEY_ATTR = "{http://schemas.microsoft.com/winfx/2006/xaml}Key"

    @staticmethod
    def cleanup_tree(subtree: etree.Element) -> etree.Element:
        """
        Sanitize the XAML tree for better comparability.
        - Put child-properties (i.e. Canvas.Clip or similar) last and alphabetically
        ordered
        """
        properties = []
        for child in list(subtree):
            # after namespace, there's a dot in the tag
            if "." in child.tag.split("}")[1]:
                properties += [child]
                subtree.remove(child)
        properties.sort(key=lambda x: x.tag)
        for prop in properties:
            subtree.append(prop)
        for child in subtree:
            Svg2XamlTester.cleanup_tree(child)
        return subtree

    @staticmethod
    def run_to_tree(svg, args):
        exporter = XamlOutput()
        out = BytesIO()
        exporter.run(args + [svg], output=out)
        out.seek(0)
        decoded = out.read().decode("utf-8")
        return Svg2XamlTester.cleanup_tree(etree.fromstring(decoded))

    xamlns = "http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    namespaces = {
        "x": "http://schemas.microsoft.com/winfx/2006/xaml",
        "d": "http://schemas.microsoft.com/expression/blend/2008",
        "xaml": xamlns,
    }

    def run_to_dg(self, svg, args=None) -> etree.Element:
        """Runs the extensions, and fetches the toplevel DrawingGroup."""
        elements = Svg2XamlTester.run_to_tree(
            self.data_file("svg", svg), args or ["--target=wpf", "--mode=lowlevel"]
        ).xpath("//xaml:DrawingGroup", namespaces=self.namespaces)
        return elements[0]

    def run_to_canvas(self, svg, args=None) -> etree.Element:
        """Runs the extensions, and fetches the toplevel Canvas."""
        elements = Svg2XamlTester.run_to_tree(
            self.data_file("svg", svg), args or ["--target=wpf", "--mode=canvas"]
        ).xpath("//xaml:Canvas", namespaces=self.namespaces)
        return elements[0]

    def assertTagEqual(self, item, tag):
        """Check if the tag of item is "tag" """
        self.assertEqual(item.tag, f"{{{self.xamlns}}}{tag}")

    def assertPropertyEqual(
        self, item, prop, expected_value, default=None, places=10, separator=",| "
    ):
        """Datatype-aware comparison of properties"""

        value = item.get(prop, default)
        if expected_value is None:
            self.assertIsNone(value)
            return
        # Numbers
        if prop in [
            "Canvas.Left",
            "Canvas.Top",
            "FontSize",
            "Height",
            "LineHeight",
            "Offset",
            "PenOffset",
            "RadiusX",
            "RadiusY",
            "Radius",
            "StrokeThickness",
            "Thickness",
            "Width",
            "X1",
            "X2",
            "Y1",
            "Y2",
        ]:
            self.assertAlmostEqual(float(value), expected_value, places=places)

        # Lists of numbers
        elif prop in [
            "Center",
            "Dashes",
            "DestinationRect",
            "EndPoint",
            "GradientOrigin",
            "Matrix",
            "Rect",
            "RenderTransform",
            "RenderTransformOrigin",
            "SourceRect",
            "StartPoint",
            "StrokeDashArray",
            "Transform",
            "Viewbox",
            "Viewport",
        ]:
            self.assertAlmostTuple(
                [float(i) for i in re.split(separator, value) if i != ""],
                expected_value,
                precision=places,
            )

        # For other data types, compare literally
        else:
            self.assertEqual(value, expected_value)
