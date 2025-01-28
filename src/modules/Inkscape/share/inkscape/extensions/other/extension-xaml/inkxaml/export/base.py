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

"""SVG -> XAML Base converter class, handling most styles"""
from typing import Optional, Union

import inkex
from inkex.transforms import Transform

from .config import GLOBAL_SETTINGS
from ..xamlobjects import (
    XAMLObject,
    BaseElement,
    Shape,
    GeometryGroup,
    Geometry,
    BlurEffect,
    Brush,
    VisualBrush,
    DrawingBrush,
)
from .utils import convert_attributes


class BaseParser:
    """Base class for parsers from SVG objects to XAML"""

    def __init__(self, svgelement: inkex.BaseElement):
        self.element = svgelement

    def to_xaml_objects(self):
        """Base method to convert self.element to an XAML object for a Drawing"""

    def to_canvas_objects(self):
        """Base method to convert self.element to an XAML object for a Canvas"""

    def get_clip(
        self, xaml_parent: BaseElement, value=None
    ) -> Optional[Union[GeometryGroup, Geometry, str]]:
        """Converts a Clip to XAML (Geometry) representation. If value is not given,
        it is pulled from self.element. xaml_parent is used to evaluate transforms
        correctly"""
        if isinstance(xaml_parent, GeometryGroup):
            return None  # XAML doesn't support nested clips
        if value is None:
            if isinstance(self.element, inkex.ShapeElement):
                value = self.element.clip
        # Construct the child parser
        if isinstance(value, inkex.ClipPath):
            # ClipPaths in XAML are specified in the coordinate system of the clip
            # definition, while in SVG they are specified in userSpaceOnUse. So we have
            # to apply the inverse transform of the self.element to a copy of the
            # clippath. Most probably, the clippath is only referenced by one element.
            # If it is referenced multiple times, the clippath will be duplicated.
            transformcopy = value.transform
            # For elements which specify a Canvas coordinate,
            # the clip is relative to that coordinate
            left = xaml_parent.get("Canvas.Left", 0)
            top = xaml_parent.get("Canvas.Top", 0)
            additional_transform = inkex.Transform(translate=(left, top))
            # do we need to consider parent transforms?
            value.transform = value.transform @ (-additional_transform)
            from .structural import ClipPathParser

            parser = ClipPathParser(value)
            result: Union[GeometryGroup, Geometry, str, None] = parser.to_clippath()
            if result is not None and isinstance(result, GeometryGroup):
                result = parser.simplify_clip(result)
            value.transform = transformcopy
            return result
        return None

    def get_mask(self, xaml_parent, value=None):
        """Converts a Mask to XAML (Geometry) representation. If value is not given,
        it is pulled from self.element. xaml_parent is used to evaluate transforms
        correctly"""
        if value is None:
            if isinstance(self.element, inkex.ShapeElement):
                value = self.element.specified_style()("mask")
        if value is None:
            return None
        return self.get_mask_pattern(xaml_parent, value)

    def get_blur(self) -> Optional[BlurEffect]:
        """Checks if an object has a Blur filter applied, and in that case returns the
        equivalent XAML object"""
        value = self.element.specified_style()("filter")
        if value is None or len(value) != 1 or value[0].TAG != "feGaussianBlur":
            return None
        result = BlurEffect()
        std_dev = value[0].get("stdDeviation")
        std_dev = float(std_dev.split()[0]) * 3.1  # empirical factor
        if std_dev < 0.5:
            # Ignore
            return None
        if 0.5 <= std_dev < 1:
            std_dev = 1
        result.add_property("Radius", std_dev)
        return result

    def set_mask_pattern_viewbox(self, value, pattern, parsed):
        """Set the viewbox of a mask or pattern."""
        mask = isinstance(value, inkex.Mask)

        viewboxprops = [value.x, value.y, value.width, value.height]
        units = value.patternUnits if not mask else value.maskUnits
        if all(x == 0 for x in viewboxprops) and mask:
            # Fall back to absolute units.
            bbx = value.shape_box()
            if bbx is not None:
                viewboxprops = [
                    bbx.x.minimum * 0.9,
                    bbx.y.minimum * 0.9,
                    bbx.width * 1.2,
                    bbx.height * 1.2,
                ]
            units = "userSpaceOnUse"

        if GLOBAL_SETTINGS.avalonia:
            viewboxprops = [float(i) for i in viewboxprops]
            pattern.add_properties(
                {
                    "Width": viewboxprops[0] + float(viewboxprops[2]),
                    "Height": viewboxprops[1] + float(viewboxprops[3]),
                }
            )
            parsed.add_properties(
                {
                    "SourceRect": " ".join(map(str, viewboxprops)),
                    "DestinationRect": " ".join(
                        map(
                            str, [-viewboxprops[0], -viewboxprops[1]] + viewboxprops[2:]
                        )
                    ),
                }
            )
        else:
            # ideally properly inherit this attribute, see pservers-pattern-04
            convert_attributes(
                None,
                parsed,
                [
                    [
                        "patternUnits",
                        "ViewportUnits",
                        {
                            "objectBoundingBox": "RelativeToBoundingBox",
                            "userSpaceOnUse": "Absolute",
                        },
                        "RelativeToBoundingBox",
                        units,
                    ],
                    [
                        "patternUnits",
                        "ViewboxUnits",
                        {
                            "objectBoundingBox": "RelativeToBoundingBox",
                            "userSpaceOnUse": "Absolute",
                        },
                        "RelativeToBoundingBox",
                        units,
                    ],
                ],
            )
            if not mask:
                parsed.add_properties(
                    {
                        "ViewboxUnits": "Absolute",
                    }
                )
            parsed.add_properties(
                {
                    "Viewbox": " ".join(map(str, viewboxprops)),
                    "Viewport": " ".join(map(str, viewboxprops)),
                }
            )
        return viewboxprops

    def set_pattern_transform(self, pattern, parsed, value, viewboxprops):
        """Set the transform on a pattern"""
        parsed.add_properties({"TileMode": "Tile"})
        if (value.get_viewbox() is not None) or not all(
            map(lambda x: x == "0", viewboxprops)
        ):
            # in this case, viewport and viewbox both have to be set together with
            # an initial transform of the pattern group
            vbox = value.get_viewbox()
            # pylint: disable=line-too-long
            if vbox is not None:
                # both are specified, apply viewbox as additional transform
                trans = inkex.Transform(
                    (
                        float(viewboxprops[2]) / vbox[2],
                        0,
                        0,
                        float(viewboxprops[2]) / vbox[3],
                        viewboxprops[0],
                        viewboxprops[1],
                    )
                )
            else:
                trans = inkex.Transform((1, 0, 0, 1, viewboxprops[0], viewboxprops[1]))

            if trans is not None:
                pattern.set_transform(trans)
        if not GLOBAL_SETTINGS.avalonia:
            parsed.set_transform(value.patternTransform)

    def get_mask_pattern(
        self, xaml_parent, value: Union[inkex.Mask, inkex.Pattern], opacity=1
    ):
        """Routine to convert Masks and Patterns to XAML"""
        lowlevel = True
        if GLOBAL_SETTINGS.avalonia:
            # Avalonia doesn't support DrawingBrush, so we have to
            # use a VisualBrush. Currently, pattern-transform is not supported.
            # In Avalonia 0.11, we'll also have a Transform attribute
            # (https://github.com/AvaloniaUI/Avalonia/pull/6344)
            lowlevel = False
        # in WPF, the ViewBox indicates which part of the VisualBrush we use
        # the ViewPort indicates the position of the first tile

        parsed: Brush = VisualBrush()
        if lowlevel:
            parsed = DrawingBrush()
        mask = isinstance(value, inkex.Mask)
        from .structural import GroupParser

        pps = GroupParser(value if mask else value.get_effective_parent())

        pattern: XAMLObject
        if lowlevel:
            pattern = pps.to_xaml_objects()
        else:
            pattern = pps.to_canvas_objects()

        viewboxprops = self.set_mask_pattern_viewbox(value, pattern, parsed)
        parsed.add_property("Drawing" if lowlevel else "Visual", pattern)
        if not mask:
            self.set_pattern_transform(pattern, parsed, value, viewboxprops)
        if isinstance(xaml_parent, Shape) and xaml_parent is not None:
            left = xaml_parent.get("Canvas.Left", None)
            top = xaml_parent.get("Canvas.Top", None)
            if left is not None and top is not None:
                # in a canvas, we have to apply a transform to the pattern
                pattern_transform = Transform(translate=(-float(left), -float(top))) @ (
                    inkex.Transform() if mask else value.patternTransform
                )
                parsed.set_transform(pattern_transform)
        pattern.add_property("Opacity", value.specified_style()("opacity") * opacity, 1)
        return parsed
