#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2011 Nikita Kitaev
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
#
"""
Simplifies SVG files in preparation for sif export.
"""

from inkex.localization import inkex_gettext as _
from inkex.base import TempDirMixin

import inkex
from inkex import (
    Group,
    PathElement,
    ShapeElement,
    Anchor,
    Switch,
    SvgDocumentElement,
    Transform,
)

###### Utility Classes ####################################


class MalformedSVGError(Exception):
    """Raised when the SVG document is invalid or contains unsupported features"""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return _(
            """SVG document is invalid or contains unsupported features

Error message: %s

The SVG to Synfig converter is designed to handle SVG files that were created using Inkscape. Unsupported features are most likely to occur in SVG files written by other programs.
"""
        ) % repr(self.value)


###### Utility Functions ##################################

### Path related


def fuse_subpaths(path: inkex.Path):
    """Fuse subpaths of a path. Should only be used on unstroked paths.
    The idea is to replace every moveto by a lineto, and then walk all the extra lines
    backwards to get the same fill. For unfilled paths, this gives visually good results
    in cases with not-too-complex paths, i.e. no intersections.
    There may be extra zero-length Lineto commands."""

    result = inkex.Path()
    return_stack = []
    for i, seg in enumerate(path.proxy_iterator()):
        if seg.letter not in "zZmM":
            result.append(seg.command)
        elif i == 0:
            result.append(seg.command)
            first = seg.end_point
        else:
            # Add a line instead of the ZoneClose / Move command, and store
            # the initial position.
            return_to = seg.previous_end_point
            if seg.letter in "mM":
                if seg.previous_end_point != first:  # only close if needed
                    # all paths must be closed for this algorithm to work. Since
                    # the path doesn't have a stroke, it's visually irrellevant.
                    result.append(inkex.paths.Line(*first))
                    return_to = first

                return_stack += [return_to]
            result.append(inkex.paths.Line(*seg.end_point))

            first = seg.end_point

    # also close the last subpath
    return_stack += [first]

    # now apply the return stack backwards
    for point in return_stack[::-1]:
        result.append(inkex.paths.Line(*point))

    return result


def split_fill_and_stroke(path_node):
    """Split a path into two paths, one filled and one stroked

    Returns a the list [fill, stroke], where each is the XML element of the
    fill or stroke, or None.
    """
    style = dict(inkex.Style.parse_str(path_node.get("style", "")))

    # If there is only stroke or only fill, don't split anything
    if "fill" in style and style["fill"] == "none":
        if "stroke" not in style or style["stroke"] == "none":
            return [None, None]  # Path has neither stroke nor fill
        else:
            return [None, path_node]
    if "stroke" not in style.keys() or style["stroke"] == "none":
        return [path_node, None]

    group = Group()
    fill = group.add(PathElement())
    stroke = group.add(PathElement())

    d = path_node.pop("d")
    if d is None:
        raise AssertionError("Cannot split stroke and fill of non-path element")

    nodetypes = path_node.pop("sodipodi:nodetypes", None)
    path_id = path_node.pop("id", str(id(path_node)))
    transform = path_node.pop("transform", None)
    path_node.pop("style")

    # Pass along all remaining attributes to the group
    for attrib_name, attrib_value in path_node.attrib.items():
        group.set(attrib_name, attrib_value)

    group.set("id", path_id)

    # Next split apart the style attribute
    style_group = {}
    style_fill = {"stroke": "none", "fill": "#000000"}
    style_stroke = {"fill": "none", "stroke": "none"}

    for key in style.keys():
        if key.startswith("fill"):
            style_fill[key] = style[key]
        elif key.startswith("stroke"):
            style_stroke[key] = style[key]
        elif key.startswith("marker"):
            style_stroke[key] = style[key]
        elif key.startswith("filter"):
            style_group[key] = style[key]
        else:
            style_fill[key] = style[key]
            style_stroke[key] = style[key]

    if len(style_group) != 0:
        group.set("style", str(inkex.Style(style_group)))

    fill.set("style", str(inkex.Style(style_fill)))
    stroke.set("style", str(inkex.Style(style_stroke)))

    # Finalize the two paths
    fill.set("d", d)
    stroke.set("d", d)
    if nodetypes is not None:
        fill.set("sodipodi:nodetypes", nodetypes)
        stroke.set("sodipodi:nodetypes", nodetypes)
    fill.set("id", path_id + "-fill")
    stroke.set("id", path_id + "-stroke")
    if transform is not None:
        fill.set("transform", transform)
        stroke.set("transform", transform)

    # Replace the original node with the group
    path_node.getparent().replace(path_node, group)

    return [fill, stroke]


### Object related


def propagate_attribs(
    node, parent_style={}, parent_transform=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
):
    """Propagate style and transform to remove inheritance"""

    # Don't enter non-graphical portions of the document
    if not isinstance(node, (ShapeElement, SvgDocumentElement)):
        return

    # Compose the transformations
    if isinstance(node, SvgDocumentElement) and node.get("viewBox"):
        vx, vy, vw, vh = [get_dimension(x) for x in node.get_viewbox()]
        dw = get_dimension(node.get("width", vw))
        dh = get_dimension(node.get("height", vh))
        this_transform = Transform(translate=(-vx, -vy), scale=(dw / vw, dh / vh))
        del node.attrib["viewBox"]
    else:
        this_transform = Transform(parent_transform)

    this_transform @= node.transform

    # Compose the style attribs
    this_style = dict(inkex.Style.parse_str(node.get("style", "")))
    remaining_style = {}  # Style attributes that are not propagated

    non_propagated = ["filter"]  # Filters should remain on the topmost ancestor
    for key in non_propagated:
        if key in this_style.keys():
            remaining_style[key] = this_style[key]
            del this_style[key]

    # Create a copy of the parent style, and merge this style into it
    parent_style_copy = parent_style.copy()
    parent_style_copy.update(this_style)
    this_style = parent_style_copy

    # Merge in any attributes outside of the style
    style_attribs = ["fill", "stroke"]
    for attrib in style_attribs:
        if node.get(attrib):
            this_style[attrib] = node.get(attrib)
            del node.attrib[attrib]

    if isinstance(node, (SvgDocumentElement, Group, Anchor, Switch)):
        # Leave only non-propagating style attributes
        if remaining_style:
            node.style = remaining_style
        else:
            if "style" in node.keys():
                del node.attrib["style"]

        # Remove the transform attribute
        if "transform" in node.keys():
            del node.attrib["transform"]

        # Continue propagating on subelements
        for child in node.iterchildren():
            propagate_attribs(child, this_style, this_transform)
    else:
        # This element is not a container

        # Merge remaining_style into this_style
        this_style.update(remaining_style)

        # Set the element's style and transform attribs
        node.style = this_style
        node.transform = this_transform


### Style related


def get_dimension(s="1024"):
    """Convert an SVG length string from arbitrary units to pixels"""
    return inkex.units.convert_unit(s, "px")
