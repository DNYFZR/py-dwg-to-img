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

"""Conversion of SVG to XAML"""

import sys
from pathlib import Path

from xml.dom import minidom
from lxml import etree

import inkex
from inkex.localization import inkex_gettext as _


# This bit of import fiddling is taken from
# https://stackoverflow.com/a/28154841/3298143, and it is necessary
# so the script can run both with -m (needed for pypi) as well as
# directly (needed for being an extensions submodule)
if __name__ == "__main__" and __package__ is None:
    file = Path(__file__).resolve()
    parent, top = file.parent, file.parents[1]

    sys.path.append(str(top))
    try:
        sys.path.remove(str(parent))
    except ValueError:  # Already removed
        pass

    __package__ = "inkxaml"

from inkxaml.export.config import GLOBAL_SETTINGS
from inkxaml.xamlobjects import (
    ResourceDictionary,
    DrawingImage,
    KEY_ATTR,
    DrawingBrush,
    Grid,
    BaseElement,
)
from inkxaml.export.structural import SvgElementParser, typemap


def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = etree.tostring(elem, method="xml").decode("utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent=" " * GLOBAL_SETTINGS.indent)


def setup_document():
    """Setup the root element + the root dictionary for swatch resources.
    This setup differs depending on mode and layers-as-resources."""
    # We can reuse the namespace dict, but have to rename the "xaml" item
    nsmap = GLOBAL_SETTINGS.xaml_namespaces.copy()
    nsmap[None] = nsmap.pop("xaml")
    if GLOBAL_SETTINGS.mode == "canvas" and GLOBAL_SETTINGS.layers_as_resources:
        parent = Grid(nsmap=nsmap)
        # We'll use the Grid's ResourceDict for Swatch resources
        rdict = ResourceDictionary(nsmap=nsmap)
        parent.add_property("Resources", rdict)
        GLOBAL_SETTINGS.TOPLEVEL_DICT = rdict
    else:
        # For lowlevel export, this grid will be used directly.
        # For non-layered canvas export, we'll copy the resources out later.
        GLOBAL_SETTINGS.TOPLEVEL_DICT = ResourceDictionary(nsmap=nsmap)
        parent = GLOBAL_SETTINGS.TOPLEVEL_DICT
    return parent


def convert_to_xaml(effect: inkex.OutputExtension, **kwargs):
    """Main conversion method"""
    etree.register_namespace("x", "http://schemas.microsoft.com/winfx/2006/xaml")
    etree.register_namespace("svg", "http://www.w3.org/2000/svg")

    document: inkex.SvgDocumentElement = effect.svg
    GLOBAL_SETTINGS.target = kwargs.get("target", "wpf")
    GLOBAL_SETTINGS.indent = kwargs.get("indent", 4)
    GLOBAL_SETTINGS.mode = kwargs.get("mode", "lowlevel")
    GLOBAL_SETTINGS.swatches = kwargs.get("swatch_treatment", "color")
    GLOBAL_SETTINGS.layers_as_resources = kwargs.get("layers_as_resources", True)
    GLOBAL_SETTINGS.referencing_type = kwargs.get("referencing_type", "DrawingImage")
    xaml_types = {
        "wpf": "http://schemas.microsoft.com/winfx/2006/xaml/presentation",
        "avaloniaui": "https://github.com/avaloniaui",
    }

    GLOBAL_SETTINGS.xaml_namespaces = {
        "x": "http://schemas.microsoft.com/winfx/2006/xaml",
        "d": "http://schemas.microsoft.com/expression/blend/2008",
        "xaml": xaml_types.get(GLOBAL_SETTINGS.target, ""),
        "xml": "http://www.w3.org/XML/1998/namespace",
    }
    GLOBAL_SETTINGS.xaml_namespaces_reversed = dict(
        (b, a) for (a, b) in GLOBAL_SETTINGS.xaml_namespaces.items()
    )

    root_element = setup_document()

    layers = (
        document.xpath("/svg:svg/svg:g[@inkscape:groupmode='layer']")
        if GLOBAL_SETTINGS.layers_as_resources
        else [None]
    )
    for layer in layers:
        layername = layer.get("inkscape:label") if layer is not None else None
        layer_id = layer.get_id() if layer is not None else None
        parser = SvgElementParser(document, layer_id)
        if not GLOBAL_SETTINGS.layers_as_resources:
            # We can fall back to the document name, but we need to strip the .svg
            layername = document.get("sodipodi:docname")
            if layername is not None:
                layername = layername.split(".svg")[0]
        if GLOBAL_SETTINGS.mode == "canvas":
            result = parser.to_canvas_objects()
            if layername is not None:
                result.add_property("Name", BaseElement.sanitize_name(layername))
            if not GLOBAL_SETTINGS.layers_as_resources:
                if len(GLOBAL_SETTINGS.TOPLEVEL_DICT) > 0:
                    result.add_property("Resources", GLOBAL_SETTINGS.TOPLEVEL_DICT)
                root_element = result
            else:
                root_element.add_child(result)
        else:
            result = parser.to_xaml_objects()
            if layername is not None:
                result.add_property(KEY_ATTR, layername)
            root_element.add_child(result)
            key_result = result.get(KEY_ATTR)
            if GLOBAL_SETTINGS.referencing_type == "DrawingImage":
                dwi = DrawingImage()
                dwi.set(KEY_ATTR, "di_" + key_result)
            else:
                dwi = DrawingBrush()
                dwi.set(KEY_ATTR, "db_" + key_result)
                dwi.add_property("Stretch", "Uniform")
            dwi.add_property("Drawing", f"{{StaticResource {key_result}}}")
            root_element.add_child(dwi)
    return prettify(root_element)


class XamlOutput(inkex.OutputExtension):
    """Save as XAML Output"""

    def add_arguments(self, pars):
        pars.add_argument("--mode", choices=["canvas", "lowlevel"], default="lowlevel")
        pars.add_argument("--target", choices=["wpf", "avaloniaui"], default="wpf")
        pars.add_argument(
            "--swatch-treatment",
            choices=["DynamicResource", "StaticResource", "color"],
            default="DynamicResource",
        )
        pars.add_argument("--indent", type=int, default=4)
        pars.add_argument("--layers-as-resources", type=inkex.Boolean, default=False)
        pars.add_argument("--text-to-path", type=inkex.Boolean, default=False)
        pars.add_argument(
            "--referencing-type",
            type=str,
            default="DrawingImage",
            choices=["DrawingImage", "DrawingBrush"],
        )

    def save(self, stream):
        if (
            self.options.mode == "lowlevel"
            or self.options.target == "avaloniaui"
            or (self.options.mode == "canvas" and self.options.text_to_path)
        ):
            # Check if there are any texts that need converting.
            if len(self.svg.xpath("//svg:flowRoot|//svg:text")) > 0:
                self.preprocess(["flowRoot", "text"], unlink_clones=False)

        # Check if the user might accidentally create an empty file.
        warn_toplevel_objects = False
        if self.options.layers_as_resources:
            for elem in self.svg:
                if elem.__class__ in typemap and not isinstance(elem, inkex.Layer):
                    warn_toplevel_objects = True
        if warn_toplevel_objects:
            inkex.errormsg(
                _(
                    'You enabled "Layers as resources", but there are visual '
                    "elements that are not part of a layer and instead contained in the root "
                    "element directly. These elements will be missing in the export. \n\n"
                    "Consider moving them to a layer or disabling this option."
                )
            )
        output = convert_to_xaml(self, **vars(self.options))
        stream.write(output.encode("utf-8"))


def run():
    XamlOutput().run()


if __name__ == "__main__":
    run()
