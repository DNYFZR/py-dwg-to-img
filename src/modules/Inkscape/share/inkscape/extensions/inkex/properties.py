# coding=utf-8
#
# Copyright (C) 2021 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
Property management and parsing, CSS cascading, default value storage

.. versionadded:: 1.2

.. data:: all_properties

    A list of all properties, their parser class, and additional information
    such as whether they are inheritable or can be given as presentation attributes
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing import (
    Dict,
    List,
    Optional,
    TYPE_CHECKING,
    cast,
)
import tinycss2
import tinycss2.ast

from .interfaces.IElement import IBaseElement

from .units import convert_unit
from .utils import FragmentError

from .colors import Color

if TYPE_CHECKING:
    from .elements import BaseElement

TokenList = List[tinycss2.ast.Node]


def _make_number_token_dimless(token):
    if isinstance(token, (tinycss2.ast.NumberToken, tinycss2.ast.PercentageToken)):
        return token.value
    if isinstance(token, tinycss2.ast.DimensionToken):
        return convert_unit(token.serialize(), "px")
    raise ValueError("Not a number")


def _get_tokens_from_value(value: str) -> TokenList:
    return tinycss2.parse_one_declaration(f"a:{value}").value


def _is_ws(token: tinycss2.ast.Node) -> bool:
    return isinstance(token, tinycss2.ast.WhitespaceToken)


def _strip_whitespace_nodes(value: TokenList) -> TokenList:
    try:
        while _is_ws(value[0]):
            del value[0]
        while _is_ws(value[-1]):
            del value[-1]
        return value
    except IndexError:
        return []


def _is_inherit(value: TokenList | None) -> bool:
    return (
        value is not None
        and len(value) == 1
        and isinstance(value[0], tinycss2.ast.IdentToken)
        and value[0].value == "inherit"
    )


class _StyleConverter:
    """Converter between str and computed value of a style, with context element"""

    # pylint: disable=unused-argument
    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        """Get parsed property value with resolved urls, color, etc.

        Args:
            element (BaseElement): the SVG element to which this style is applied to
                currently used for resolving gradients / masks, could be used for
                computing percentage attributes or calc() attributes [optional]

        Returns:
            object: parsed property value
        """
        return tinycss2.serialize(value)

    def raise_invalid_value(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> None:
        """Checks if the value str is valid in the context of element.

        Args:
            value (str): attribute value
            element (Optional[BaseElement], optional): Context element. Defaults to
                None.

        Raises:
            various exceptions if the property has a bad value
        """
        self.convert(value, element)

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        """Converts value back to string in the context of element.

        Args:
            value (object): parsed value of attribute
            element (_type_, optional): Context element. Defaults to None.

        Returns:
            str: _description_
        """
        return _get_tokens_from_value(str(value))


class _AlphaValueConverter(_StyleConverter):
    """Stores an alpha value (such as opacity), which may be specified as
    as percentage or absolute value.

    Reference: https://www.w3.org/TR/css-color/#typedef-alpha-value"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        if isinstance(value[0], tinycss2.ast.NumberToken):
            parsed_value = value[0].value
        elif isinstance(value[0], tinycss2.ast.PercentageToken):
            parsed_value = value[0].value / 100
        else:
            raise ValueError()
        return min(max(parsed_value, 0), 1)

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        if isinstance(value, (float, int)):
            value = min(max(value, 0), 1)
            return [tinycss2.ast.NumberToken(0, 0, value, value, f"{value}")]
        raise ValueError("Value must be number")


class _ColorValueConverter(_StyleConverter):
    """Converts a color value

    Reference: https://drafts.csswg.org/css-color-3/#valuea-def-color"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        # Process this as string
        vstr = _StyleConverter.convert(self, value, element)
        if vstr == "currentColor":
            if element is not None:
                return element.get_computed_style("color")
            return None
        return Color(vstr)


class _URLNoneValueConverter(_StyleConverter):
    """Converts a value that is either none or an url, such as markers or masks.

    Reference: https://www.w3.org/TR/SVG2/painting.html#VertexMarkerProperties"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        if len(value) == 0:
            return None
        value = value[0]
        if isinstance(value, tinycss2.ast.URLToken):
            if element is not None and self.element_has_root(element):
                return element.root.getElementById(value.value)
            return value.serialize()
        if isinstance(value, tinycss2.ast.IdentToken):
            return None

        raise ValueError("Invalid property value")

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        if isinstance(value, IBaseElement):
            if element is not None:
                value = _URLNoneValueConverter._insert_if_necessary(element, value)
            return [tinycss2.ast.URLToken(0, 0, value.get_id(), value.get_id(as_url=2))]
        return [tinycss2.ast.IdentToken(0, 0, "none")]

    @staticmethod
    def element_has_root(element) -> bool:
        "Checks if an element has a root"
        try:
            _ = element.root
            return True
        except FragmentError:
            return False

    @staticmethod
    def _insert_if_necessary(element: BaseElement, value: BaseElement) -> BaseElement:
        """Ensures that the return (value or a deep copy of it) is inside the same
        document as element.

        if element is unrooted, don't do anything (just return value)
        If element is attached to the same document as value, return value.
        If value is not attached to a document, attach it to the defs of element's
        document and return value.
        If value is already attached to another document, create a copy and return the
        copy.

        .. versionadded:: 1.4"""
        # Check if the element is rooted and has the same root as self.element.
        try:
            _ = element.root
            try:
                if value.root != element.root:
                    # Create a copy and attach it to the tree.
                    copy = value.copy()
                    element.root.defs.append(copy)
                    return copy
            except FragmentError:
                element.root.defs.append(value)
                return value

        except FragmentError:
            pass
        return value


class _PaintValueConverter(_ColorValueConverter, _URLNoneValueConverter):
    """Stores a paint value (such as fill and stroke), which may be specified
    as color, or url.

    Reference: https://www.w3.org/TR/SVG2/painting.html#SpecifyingPaint"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        v0 = value[0]
        if isinstance(v0, tinycss2.ast.IdentToken):
            if v0.value == "none":
                return None
            if v0.value == "currentColor":
                return _ColorValueConverter.convert(self, value, element)
            if v0.value in ["context-fill", "context-stroke"]:
                return v0.value
            else:
                return Color(v0.value)

        if isinstance(v0, tinycss2.ast.HashToken):
            return Color("#" + v0.value)
        if isinstance(v0, tinycss2.ast.URLToken):
            if element is not None and self.element_has_root(element):
                paint_server = element.root.getElementById(v0.value[1:])
            else:
                return None
            if paint_server is not None:
                return paint_server
            for i in value[1:]:
                if isinstance(i, tinycss2.ast.IdentToken):
                    return Color(i.value)
            raise ValueError("Paint server not found")
        if isinstance(v0, tinycss2.ast.FunctionBlock) and v0.name in [
            "rgb",
            "rgba",
            "hsl",
            "hsla",
        ]:
            arguments = [str(argument.value) for argument in v0.arguments]
            return Color(f"{v0.name}({''.join(arguments)})")
        raise ValueError("Unknown color specification")

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        if value is None:
            return [tinycss2.ast.IdentToken(0, 0, "none")]
        if isinstance(value, IBaseElement):
            return _URLNoneValueConverter.convert_back(self, value, element=element)
        return _ColorValueConverter.convert_back(self, value, element=element)


class _EnumValueConverter(_StyleConverter):
    """Stores a value that can only have a finite set of options"""

    def __init__(self, options):
        self.options = options

    def raise_invalid_value(
        self, value: TokenList, element: BaseElement | None = None
    ) -> None:
        if tinycss2.serialize(value) not in self.options:
            raise ValueError(
                f"Value '{tinycss2.serialize(value)}' is invalid for the property"
            )


class _ShorthandValueConverter(_StyleConverter):
    """Stores a value that sets other values (e.g. the font shorthand)"""

    def __init__(self, keys) -> None:
        super().__init__()

        self.keys = keys

    @abstractmethod
    def get_shorthand_changes(self, value) -> Dict[str, str]:
        """calculates the value of affected attributes for this shorthand

        Returns:
            Dict[str, str]: a dictionary containing the new values of the
            affected attributes
        """


class _FontValueShorthandConverter(_ShorthandValueConverter):
    """Logic for the shorthand font property"""

    def __init__(self) -> None:
        super().__init__(
            [
                "font-style",
                "font-variant",
                "font-weight",
                "font-stretch",
                "font-size",
                "line-height",
                "font-family",
            ]
        )
        self.options = {
            key: all_properties[key].converter.options  # type: ignore
            for key in self.keys
            if isinstance(all_properties[key].converter, _EnumValueConverter)
        }
        # Font stretch can be specified in percent, but for the
        # shorthand, only a keyword value is allowed
        self.options["font-stretch"] = (
            "normal",
            "ultra-condensed",
            "extra-condensed",
            "condensed",
            "semi-condensed",
            "semi-expanded",
            "expanded",
            "extra-expanded",
            "ultra-expanded",
        )

    def get_shorthand_changes(self, value):
        result = {key: all_properties[key].default_value for key in self.keys}

        if len(value) == 0:
            return result  # shorthand not set, nothing to do
        i = 0
        while i < len(value):
            cur = value[i]
            matched = False
            if isinstance(cur, tinycss2.ast.IdentToken):
                matched = True
                if cur.value in self.options["font-style"]:
                    result["font-style"] = [cur]
                elif cur.value in self.options["font-variant"]:
                    result["font-variant"] = [cur]
                elif cur.value in self.options["font-weight"]:
                    result["font-weight"] = [cur]
                elif cur.value in self.options["font-stretch"]:
                    result["font-stretch"] = [cur]
                else:
                    matched = False
            if not matched and not isinstance(cur, tinycss2.ast.WhitespaceToken):
                result["font-size"] = [cur]
                if (
                    len(value) > i + 1
                    and isinstance(value[i + 1], tinycss2.ast.LiteralToken)
                    and value[i + 1].value == "/"
                ):
                    result["line-height"] = [value[i + 2]]
                    i += 2
                if len(value[i + 1 :]) > 0:
                    result["font-family"] = _strip_whitespace_nodes(value[i + 1 :])
                break
            i += 1
        return result


class _TextDecorationValueConverter(_ShorthandValueConverter):
    """Logic for the shorthand font property

    .. versionadded:: 1.3"""

    def __init__(self):
        super().__init__(
            ["text-decoration-style", "text-decoration-color", "text-decoration-line"]
        )
        self.options = {
            "text-decoration-" + key: all_properties[
                "text-decoration-" + key
            ].converter.options
            for key in ("line", "style", "color")
            if isinstance(
                all_properties["text-decoration-" + key].converter, _EnumValueConverter
            )
        }

    def get_shorthand_changes(self, value):
        result = {
            "text-decoration-style": all_properties[
                "text-decoration-style"
            ].default_value,
            "text-decoration-color": "currentcolor",
            "text-decoration-line": [],
        }

        for cur in (i.serialize() for i in value):
            if cur in ["underline", "overline", "line-through", "blink"]:
                result["text-decoration-line"] += [cur]
            elif cur in self.options["text-decoration-style"]:
                result["text-decoration-style"] = cur
            else:
                result["text-decoration-color"] = cur

        if len(result["text-decoration-line"]) == 0:
            result["text-decoration-line"] = all_properties[
                "text-decoration-line"
            ].default_value
        else:
            # Text-decoration-line can have multiple values.
            result["text-decoration-line"] = " ".join(result["text-decoration-line"])

        return result


class _MarkerShorthandValueConverter(_ShorthandValueConverter, _URLNoneValueConverter):
    """Logic for the marker shorthand property"""

    def __init__(self) -> None:
        super().__init__(["marker-start", "marker-end", "marker-mid"])

    def get_shorthand_changes(self, value):
        if value == "":
            return {}  # shorthand not set, nothing to do
        return {k: value for k in self.keys}

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        """Convert value back to a tokenlist"""
        return _URLNoneValueConverter.convert_back(self, value, element)


class _FontSizeValueConverter(_StyleConverter):
    """Logic for the font-size property"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        v0 = value[0].serialize()
        if element is None:
            return v0  # no additional logic in this case
        if isinstance(
            value[0],
            (
                tinycss2.ast.NumberToken,
                tinycss2.ast.PercentageToken,
                tinycss2.ast.DimensionToken,
            ),
        ):
            return element.to_dimensionless(v0)
        # unable to parse font size, e.g. font-size:normal
        return v0


class _StrokeDasharrayValueConverter(_StyleConverter):
    """Logic for the stroke-dasharray property"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        dashes = []
        i = 0
        for i, el in enumerate(value):
            if (
                i == 0
                and isinstance(el, tinycss2.ast.IdentToken)
                and el.value == "none"
            ):
                return []
            # whitespace or comma separated list
            if isinstance(el, (tinycss2.ast.WhitespaceToken)) or (
                isinstance(el, tinycss2.ast.LiteralToken) and el.value == ","
            ):
                continue
            if isinstance(el, (tinycss2.ast.DimensionToken, tinycss2.ast.NumberToken)):
                dashes.append(_make_number_token_dimless(el))
            else:
                return []
        if any(i < 0 for i in dashes):
            # one negative value makes the dasharray invalid
            return []
        if len(dashes) % 2 == 1:
            dashes = 2 * dashes
        return dashes

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        if value is None or not value:
            value = "none"
        if isinstance(value, list):
            if len(value) == 0:
                value = "none"
            else:
                value = " ".join(map(str, value))
        return _get_tokens_from_value(str(value))


class _FilterListConverter(_URLNoneValueConverter):
    """Stores a list of Filters

    .. versionadded:: 1.4"""

    def convert(
        self, value: TokenList, element: Optional[BaseElement] = None
    ) -> object:
        if element is None or value == "none":
            return []

        try:
            result = [
                element.root.getElementById(item.value)
                for item in value
                if isinstance(item, tinycss2.ast.URLToken)
            ]
            return [i for i in result if i is not None]
        except FragmentError:
            return [
                item.serialize()
                for item in value
                if isinstance(item, tinycss2.ast.URLToken)
            ]
        except ValueError:  # broken link
            return []

    def convert_back(
        self, value: object, element: Optional[BaseElement] = None
    ) -> TokenList:
        if isinstance(value, IBaseElement) or not isinstance(value, (list, tuple)):
            value = [value]
        if all((isinstance(i, str) for i in value)):
            return _get_tokens_from_value(" ".join(value))  # type: ignore
        assert element is not None
        value = cast("List[BaseElement]", value)
        try:
            _ = element.root
            for i in value:
                if i is None:
                    continue
                # insert the element
                inserted = self._insert_if_necessary(element, cast("BaseElement", i))
                # if a copy was created, replace the original in the list with the copy
                if inserted is not i:
                    for index, item in enumerate(value):
                        if item is i:
                            value[index] = inserted
        except FragmentError:
            # Element is unrooted, we skip this step.
            pass
        return _get_tokens_from_value(
            " ".join(f"url(#{i.get_id()})" for i in value if i is not None)
        )


@dataclass
class PropertyDescription:
    """Describes a CSS / presentation attribute"""

    name: str
    converter: _StyleConverter
    default_value: TokenList
    presentation: bool
    inherited: bool

    def __init__(
        self,
        name: str,
        converter: _StyleConverter,
        default_value: str,
        presentation: bool = False,
        inherited: bool = False,
    ):
        self.presentation = presentation
        self.inherited = inherited
        self.default_value = _get_tokens_from_value(default_value)
        self.name = name
        self.converter = converter


# Source for this list: https://www.w3.org/TR/SVG2/styling.html#PresentationAttributes
properties_list: List[PropertyDescription] = [
    PropertyDescription(
        "alignment-baseline",
        _EnumValueConverter(
            [
                "baseline",
                "text-bottom",
                "alphabetic",
                "ideographic",
                "middle",
                "central",
                "mathematical",
                "text-top",
            ]
        ),
        "baseline",
        True,
        False,
    ),
    PropertyDescription("baseline-shift", _StyleConverter(), "0", True, False),
    PropertyDescription("clip", _StyleConverter(), "auto", True, False),
    PropertyDescription("clip-path", _URLNoneValueConverter(), "none", True, False),
    PropertyDescription(
        "clip-rule", _EnumValueConverter(["nonzero", "evenodd"]), "nonzero", True, True
    ),
    PropertyDescription("color", _PaintValueConverter(), "black", True, True),
    PropertyDescription(
        "color-interpolation",
        _EnumValueConverter(["sRGB", "auto", "linearRGB"]),
        "sRGB",
        True,
        True,
    ),
    PropertyDescription(
        "color-interpolation-filters",
        _EnumValueConverter(["auto", "sRGB", "linearRGB"]),
        "linearRGB",
        True,
        True,
    ),
    PropertyDescription(
        "color-rendering",
        _EnumValueConverter(
            ["auto", "optimizeSpeed", "optimizeQuality", "pixelated", "crisp-edges"]
        ),
        "auto",
        True,
        True,
    ),
    PropertyDescription("cursor", _StyleConverter(), "auto", True, True),
    PropertyDescription(
        "direction", _EnumValueConverter(["ltr", "rtl"]), "ltr", True, True
    ),
    PropertyDescription(
        "display",
        _EnumValueConverter(
            [
                "inline",
                "block",
                "list-item",
                "inline-block",
                "table",
                "inline-table",
                "table-row-group",
                "table-header-group",
                "table-footer-group",
                "table-row",
                "table-column-group",
                "table-column",
                "table-cell",
                "table-caption",
                "none",
            ]
        ),
        "inline",
        True,
        False,
    ),
    PropertyDescription(
        "dominant-baseline",
        _EnumValueConverter(
            [
                "auto",
                "text-bottom",
                "alphabetic",
                "ideographic",
                "middle",
                "central",
                "mathematical",
                "hanging",
                "text-top",
            ]
        ),
        "auto",
        True,
        True,
    ),
    PropertyDescription("fill", _PaintValueConverter(), "black", True, True),
    PropertyDescription("fill-opacity", _AlphaValueConverter(), "1", True, True),
    PropertyDescription(
        "fill-rule", _EnumValueConverter(["nonzero", "evenodd"]), "nonzero", True, True
    ),
    PropertyDescription("filter", _FilterListConverter(), "none", True, False),
    PropertyDescription("flood-color", _PaintValueConverter(), "black", True, False),
    PropertyDescription("flood-opacity", _AlphaValueConverter(), "1", True, False),
    PropertyDescription("font-family", _StyleConverter(), "sans-serif", True, True),
    PropertyDescription("font-size", _FontSizeValueConverter(), "medium", True, True),
    PropertyDescription("font-size-adjust", _StyleConverter(), "none", True, True),
    PropertyDescription("font-stretch", _StyleConverter(), "normal", True, True),
    PropertyDescription(
        "font-style",
        _EnumValueConverter(["normal", "italic", "oblique"]),
        "normal",
        True,
        True,
    ),
    PropertyDescription(
        "font-variant",
        _EnumValueConverter(["normal", "small-caps"]),
        "normal",
        True,
        True,
    ),
    PropertyDescription(
        "font-weight",
        _EnumValueConverter(
            ["normal", "bold"] + [str(i) for i in range(100, 901, 100)]
        ),
        "normal",
        True,
        True,
    ),
    PropertyDescription(
        "glyph-orientation-horizontal", _StyleConverter(), "0deg", True, True
    ),
    PropertyDescription(
        "glyph-orientation-vertical", _StyleConverter(), "auto", True, True
    ),
    PropertyDescription("inline-size", _StyleConverter(), "0", False, False),
    PropertyDescription(
        "image-rendering",
        _EnumValueConverter(["auto", "optimizeQuality", "optimizeSpeed"]),
        "auto",
        True,
        True,
    ),
    PropertyDescription("letter-spacing", _StyleConverter(), "normal", True, True),
    PropertyDescription(
        "lighting-color", _ColorValueConverter(), "normal", True, False
    ),
    PropertyDescription("line-height", _StyleConverter(), "normal", False, True),
    PropertyDescription("marker", _MarkerShorthandValueConverter(), ""),
    PropertyDescription("marker-end", _URLNoneValueConverter(), "none", True, True),
    PropertyDescription("marker-mid", _URLNoneValueConverter(), "none", True, True),
    PropertyDescription("marker-start", _URLNoneValueConverter(), "none", True, True),
    PropertyDescription("mask", _URLNoneValueConverter(), "none", True, False),
    PropertyDescription("opacity", _AlphaValueConverter(), "1", True, False),
    PropertyDescription(
        "overflow",
        _EnumValueConverter(["visible", "hidden", "scroll", "auto"]),
        "visible",
        True,
        False,
    ),
    PropertyDescription("paint-order", _StyleConverter(), "normal", True, False),
    PropertyDescription(
        "pointer-events",
        _EnumValueConverter(
            [
                "bounding-box",
                "visiblePainted",
                "visibleFill",
                "visibleStroke",
                "visible",
                "painted",
                "fill",
                "stroke",
                "all",
                "none",
            ]
        ),
        "visiblePainted",
        True,
        True,
    ),
    PropertyDescription("shape-inside", _URLNoneValueConverter(), "none", False, False),
    PropertyDescription(
        "shape-rendering",
        _EnumValueConverter(
            ["auto", "optimizeSpeed", "crispEdges", "geometricPrecision"]
        ),
        "visiblePainted",
        True,
        True,
    ),
    PropertyDescription("stop-color", _ColorValueConverter(), "black", True, False),
    PropertyDescription("stop-opacity", _AlphaValueConverter(), "1", True, False),
    PropertyDescription("stroke", _PaintValueConverter(), "none", True, True),
    PropertyDescription(
        "stroke-dasharray", _StrokeDasharrayValueConverter(), "none", True, True
    ),
    PropertyDescription("stroke-dashoffset", _StyleConverter(), "0", True, True),
    PropertyDescription(
        "stroke-linecap",
        _EnumValueConverter(["butt", "round", "square"]),
        "butt",
        True,
        True,
    ),
    PropertyDescription(
        "stroke-linejoin",
        _EnumValueConverter(["miter", "miter-clip", "round", "bevel", "arcs"]),
        "miter",
        True,
        True,
    ),
    PropertyDescription("stroke-miterlimit", _StyleConverter(), "4", True, True),
    PropertyDescription("stroke-opacity", _AlphaValueConverter(), "1", True, True),
    PropertyDescription("stroke-width", _StyleConverter(), "1", True, True),
    PropertyDescription("text-align", _StyleConverter(), "start", True, True),
    PropertyDescription(
        "text-anchor",
        _EnumValueConverter(["start", "middle", "end"]),
        "start",
        True,
        True,
    ),
    PropertyDescription(
        "text-decoration-line", _StyleConverter(), "none", False, False
    ),
    PropertyDescription(
        "text-decoration-style",
        _EnumValueConverter(["solid", "double", "dotted", "dashed", "wavy"]),
        "solid",
        False,
        False,
    ),
    PropertyDescription(
        "text-decoration-color", _StyleConverter(), "currentcolor", False, False
    ),
    PropertyDescription(
        "text-overflow", _EnumValueConverter(["clip", "ellipsis"]), "clip", True, False
    ),
    PropertyDescription(
        "text-rendering",
        _EnumValueConverter(
            ["auto", "optimizeSpeed", "optimizeLegibility", "geometricPrecision"]
        ),
        "auto",
        True,
        True,
    ),
    PropertyDescription(
        "unicode-bidi",
        _EnumValueConverter(
            [
                "normal",
                "embed",
                "isolate",
                "bidi-override",
                "isolate-override",
                "plaintext",
            ]
        ),
        "normal",
        True,
        False,
    ),
    PropertyDescription("vector-effect", _StyleConverter(), "none", True, False),
    PropertyDescription("vertical-align", _StyleConverter(), "baseline", False, False),
    PropertyDescription(
        "visibility",
        _EnumValueConverter(["visible", "hidden", "collapse"]),
        "visible",
        True,
        True,
    ),
    PropertyDescription(
        "white-space",
        _EnumValueConverter(
            ["normal", "pre", "nowrap", "pre-wrap", "break-spaces", "pre-line"]
        ),
        "normal",
        True,
        True,
    ),
    PropertyDescription("word-spacing", _StyleConverter(), "normal", True, True),
    PropertyDescription(
        "writing-mode",
        _EnumValueConverter(
            [
                "horizontal-tb",
                "vertical-rl",
                "vertical-lr",
                "lr",
                "lr-tb",
                "rl",
                "rl-tb",
                "tb",
                "tb-rl",
            ]
        ),
        "horizontal-tb",
        True,
        True,
    ),
    PropertyDescription(
        "-inkscape-font-specification", _StyleConverter(), "sans-serif", False, True
    ),
]
all_properties = {v.name: v for v in properties_list}

properties_list += [
    PropertyDescription("font", _FontValueShorthandConverter(), ""),
    PropertyDescription("text-decoration", _TextDecorationValueConverter(), ""),
]

all_properties["font"] = properties_list[-2]
all_properties["text-decoration"] = properties_list[-1]

shorthand_from_value = {
    item: prop.name
    for prop in properties_list
    if isinstance(prop.converter, _ShorthandValueConverter)
    for item in prop.converter.keys
}

shorthand_properties = {
    i.name: i
    for i in properties_list
    if isinstance(i.converter, _ShorthandValueConverter)
}
