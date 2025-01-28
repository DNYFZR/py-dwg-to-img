# coding=utf-8
#
# Copyright (C) 2005 Aaron Spike, aaron@ekips.org
#               2019-2020 Martin Owens
#               2021 Jonathan Neuhauser, jonathan.neuhauser@outlook.com
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
Functions for handling styles and embedded css
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Generator, TYPE_CHECKING, Tuple
from lxml import etree
import tinycss2
import tinycss2.ast

from .interfaces.IElement import IBaseElement

from .colors import Color
from .properties import (
    _get_tokens_from_value,
    _is_inherit,
    all_properties,
    shorthand_from_value,
    shorthand_properties,
    TokenList,
    _strip_whitespace_nodes,
)
from .css import CSSCompiler, parser

from .utils import FragmentError, NotifyList, NotifyOrderedDict
from .elements._utils import NSS

if TYPE_CHECKING:
    from .elements._base import BaseElement


class Classes(NotifyList):
    """A list of classes applied to an element (used in css and js)"""

    def __init__(self, classes=None, callback=None, element=None):
        if isinstance(classes, str):
            classes = classes.split()
        super().__init__(classes or (), callback=callback)

    def __str__(self):
        return " ".join(self)


@dataclass
class StyleValue:
    """Encapsulates a single parsed style value + its importance state"""

    value: TokenList
    important: bool = False

    def __str__(self):
        return tinycss2.serialize(self.value) + ("!important" if self.important else "")

    def __eq__(self, other):
        return (
            tinycss2.serialize(self.value) == tinycss2.serialize(other.value)
            and self.important == other.important
        )

    def is_inherit(self):
        """Checks if the value is "inherit" """
        return _is_inherit(self.value)


class Style(NotifyOrderedDict):
    """A list of style directives

    .. versionchanged:: 1.2
        The Style API now allows for access to parsed / processed styles via the
        :func:`call` method.

    .. automethod:: __call__
    .. automethod:: __getitem__
    .. automethod:: __setitem__
    """

    color_props = ("stroke", "fill", "stop-color", "flood-color", "lighting-color")
    opacity_props = ("stroke-opacity", "fill-opacity", "opacity", "stop-opacity")
    unit_props = "stroke-width"
    """Dictionary of attributes with units.

    ..versionadded:: 1.2
    """
    associated_props = {
        "fill": "fill-opacity",
        "stroke": "stroke-opacity",
        "stop-color": "stop-opacity",
    }
    """Dictionary of association between color and opacity attributes.

    .. versionadded:: 1.2
    """

    def __init__(self, style=None, callback=None, element=None, **kw):
        self.callback = None
        self.element = element

        # if style is passed as kwargs, replace underscores by dashes
        style = style or [(k.replace("_", "-"), v) for k, v in kw.items()]

        self.update(style)

        # Should accept dict, Style, parsed string, list etc.
        super().__init__(callback=callback)

    def _add(self, key: str, value: StyleValue):
        # Works with both regular dictionaries and Styles
        if key in shorthand_properties:
            chg = shorthand_properties[key].converter.get_shorthand_changes(value.value)  # type: ignore
            for k, v in chg.items():
                self._add(k, StyleValue(v, value.important))
        else:
            if key not in self or (
                not self.get_store(key).important or value.important
            ):
                # Only overwrite if importance of existing value is higher
                super().__setitem__(key, value)

    def _get_val(self, key: str, value):
        if key in all_properties and not isinstance(value, str):
            return StyleValue(
                all_properties[key].converter.convert_back(value, self.element)
            )
        return StyleValue(_get_tokens_from_value(value))

    def _attr_callback(self, key):
        def inner(value):
            self[key] = value

        return inner

    def _parse_str(self, style: str) -> Generator[Tuple[str, StyleValue], None, None]:
        """Create a dictionary from the value of a CSS rule (such as an inline style or
        from an embedded style sheet), including its !important state, in a tokenized
        form. Whitespace tokens from the start and end of the value are stripped.

        Args:
            style: the content of a CSS rule to parse. Can also be a List of
                ComponentValues

        Yields:
            Tuple[str, class:`~inkex.style.StyleValue`]: the parsed attribute
        """
        result = tinycss2.parse_declaration_list(
            style, skip_comments=True, skip_whitespace=True
        )
        for declaration in result:
            if isinstance(declaration, tinycss2.ast.Declaration):
                yield (
                    declaration.name,
                    StyleValue(
                        _strip_whitespace_nodes(declaration.value),
                        declaration.important,
                    ),
                )

    @staticmethod
    def parse_str(style: str, element=None):
        """Parse a style passed as string"""
        return Style(style, element=element)

    def __str__(self):
        """Format an inline style attribute from a dictionary"""
        return self.to_str()

    def to_str(self, sep=";"):
        """Convert to string using a custom delimiter"""
        return sep.join([f"{key}:{value}" for key, value in self.items()])

    def __add__(self, other):
        """Add two styles together to get a third, composing them"""
        ret = self.copy()
        ret.update(Style(other))
        return ret

    def __iadd__(self, other):
        """Add style to this style, the same as ``style.update(dict)``"""
        self.update(other)
        return self

    def __sub__(self, other):
        """Remove keys and return copy"""
        ret = self.copy()
        ret.__isub__(other)
        return ret

    def __isub__(self, other):
        """Remove keys from this style, list of keys or other style dictionary"""
        for key in other:
            self.pop(key, None)
        return self

    def __ne__(self, other):
        return not self.__eq__(other)

    def copy(self):
        """Create a copy of the style.

        .. versionadded:: 1.2"""
        ret = Style({}, element=self.element)
        for key, value in super().items():
            ret[key] = value
        return ret

    def update(self, other):
        """Update, while respecting ``!important`` declarations, and simplifying
        shorthands"""
        if isinstance(other, Style):
            for k, v in super(NotifyOrderedDict, other).items():
                self._add(k, v)
        # Order raw dictionaries so tests can be made reliable
        elif isinstance(other, dict):
            for k, v in sorted(other.items()):
                self._add(k, self._get_val(k, v))

        elif isinstance(other, list) and all(isinstance(i, tuple) for i in other):
            for k, v in other:
                self._add(k, self._get_val(k, v))

        elif isinstance(other, str) or (isinstance(other, list)):
            for k, v in self._parse_str(other):
                self._add(k, v)

    def add_inherited(self, parent):
        """Creates a new Style containing all parent styles with importance "!important"
        and current styles with importance "!important"

        .. versionadded:: 1.2

        Args:
            parent: the parent style that will be merged into this one (will not be
                altered)

        Returns:
            Style: the merged Style object
        """
        ret = self.copy()

        if not (isinstance(parent, Style)):
            return ret

        for item in parent.keys():
            apply = False
            if item in all_properties and all_properties[item].inherited:
                # only set parent value if value is not set or parent importance is
                # higher
                if item not in ret or (
                    not self.get_importance(item) and parent.get_importance(item)
                ):
                    apply = True
            if item in ret and ret.get_store(item).is_inherit():
                apply = True
            if apply:
                super(NotifyOrderedDict, ret).__setitem__(item, parent.get_store(item))
        return ret

    def __setitem__(self, key, value):
        """Sets a style value.

        .. versionchanged:: 1.2
            ``value`` can now also be non-string objects such as a Gradient.

        Args:
            key (str): the attribute name
            value (Any):

                - a :class:`StyleValue`
                - a TokenList (tokenized CSS value),
                - a string with the value
                - any other object. The converter associated with the provided key will
                  attempt to create a string out of the passed value.
        Raises:
            ValueError: when passing something else than string, StyleValue or TokenList
                and key is not a known style attribute
            Error: Other exceptions may be raised when converting non-string objects."""

        if isinstance(value, StyleValue):
            super().__setitem__(key, value)
            return
        if isinstance(value, str):
            value = value.strip()
            tokenized = _get_tokens_from_value(value)

            if key in all_properties:
                all_properties[key].converter.raise_invalid_value(
                    tokenized, self.element
                )
            value = tokenized
        elif (
            isinstance(value, list)
            and len(value) > 0
            and all(isinstance(i, tinycss2.ast.Node) for i in value)
        ):
            pass
        elif key in all_properties:
            value = all_properties[key].converter.convert_back(value, self.element)
        else:
            raise TypeError()
        # Convert value to StyleValue
        super().__setitem__(key, StyleValue(value, False))

    def __getitem__(self, key):
        """Returns the unparsed value of the element (minus a possible ``!important``)

        .. versionchanged:: 1.2
            ``!important`` is removed from the value.
        """
        return tinycss2.serialize(super().__getitem__(key).value)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def get_store(self, key):
        """Gets the :class:`~inkex.properties.BaseStyleValue` of this key, since the
        other interfaces - :func:`__getitem__` and :func:`__call__` - return the
        original and parsed value, respectively.

        .. versionadded:: 1.2

        Args:
            key (str): the attribute name

        Returns:
            BaseStyleValue: the BaseStyleValue struct of this attribute
        """
        return super().__getitem__(key)

    def __call__(self, key: str, element: Optional[BaseElement] = None, default=None):
        """Return the parsed value of a style. Optionally, an element can be passed
        that will be used to find gradient definitions etc.

        .. versionadded:: 1.2"""
        tmp = super().get(key, None)
        v: None | TokenList = None if tmp is None else tmp.value
        if (v is None and (key in all_properties or default is not None)) or (
            v is not None and _is_inherit(v)
        ):  # if the value is still inherit here, return the default
            v = (
                _get_tokens_from_value(default)
                if default is not None
                else (
                    all_properties[key].default_value if key in all_properties else None
                )
            )
            if v is None:
                return v
        if v is not None:
            if key in shorthand_properties:
                return tinycss2.serialize(v)
            if key in all_properties:
                result = all_properties[key].converter.convert(
                    v, element or self.element
                )
            else:
                result = tinycss2.serialize(v)
            if isinstance(result, list) and not isinstance(result, Color):
                result = NotifyList(result, callback=self._attr_callback(key))
            return result
        raise KeyError("Unknown attribute")

    def __eq__(self, other):
        if not isinstance(other, Style):
            other = Style(other)
        if self.keys() != other.keys():
            return False
        for arg in set(self) | set(other):
            if self.get_store(arg) != other.get_store(arg):
                return False
        return True

    def items(self):
        """The styles's items as string

        .. versionadded:: 1.2"""
        for key, value in super().items():
            yield key, tinycss2.serialize(value.value)

    def get_importance(self, key, default=False):
        """Returns whether the declaration with ``key`` is marked as ``!important``

        .. versionadded:: 1.2"""
        if key in self:
            return self.get_store(key).important
        return default

    def set_importance(self, key, importance):
        """Sets the ``!important`` state of a declaration with key ``key``

        .. versionadded:: 1.2"""
        if key in self:
            super().__getitem__(key).important = importance
        else:
            raise KeyError()
        self._callback()

    def get_color(self, name="fill"):
        """Get the color AND opacity as one Color object"""
        color = Color(self.get(name, "none"))
        return color.to_rgba(self.get(name + "-opacity", 1.0))

    def set_color(self, color, name="fill"):
        """Sets the given color AND opacity as rgba to the fill or stroke style
        properties."""
        color = Color(color)
        if color.space == "rgba" and name in Style.associated_props:
            self[Style.associated_props[name]] = color.alpha
            self[name] = color.to_rgb()
        else:
            self[name] = color

    def update_urls(self, old_id, new_id):
        """Find urls in this style and replace them with the new id"""
        for _, elem in super().items():
            for token in elem.value:
                if (
                    isinstance(token, tinycss2.ast.URLToken)
                    and token.value == f"#{old_id}"
                ):
                    token.value = f"#{new_id}"
                    token.representation = f"url(#{new_id})"
                    self._callback()

    def interpolate(self, other, fraction):
        # type: (Style, Style, float) -> Style
        """Interpolate all properties.

        .. versionadded:: 1.1"""
        from .tween import StyleInterpolator
        from inkex.elements import PathElement

        if self.element is None:
            self.element = PathElement(style=str(self))
        if other.element is None:
            other.element = PathElement(style=str(other))
        return StyleInterpolator(self.element, other.element).interpolate(fraction)

    @classmethod
    def cascaded_style(cls, element: BaseElement):
        """Returns the cascaded style of an element (all rules that apply the element
        itself), based on the stylesheets, the presentation attributes and the inline
        style using the respective specificity of the style

        see https://www.w3.org/TR/CSS22/cascade.html#cascading-order

        .. versionadded:: 1.2

        Args:
            element (BaseElement): the element that the cascaded style will be
                computed for

        Returns:
            Style: the cascaded style
        """
        try:
            styles = list(element.root.stylesheets.lookup_specificity(element))
        except FragmentError:
            styles = []

        # presentation attributes have specificity 0,
        # see https://www.w3.org/TR/SVG/styling.html#PresentationAttributes
        styles.append([element.presentation_style(), (0, 0, 0)])

        # would be (1, 0, 0, 0), but then we'd have to extend every entry
        styles.append([element.style, (float("inf"), 0, 0)])

        # sort styles by specificity (ascending, so when overwriting it's correct)
        styles = sorted(styles, key=lambda item: item[1])

        result = styles[0][0].copy()
        for style, _ in styles[1:]:
            result.update(style)
        result.element = element
        return result

    @classmethod
    def specified_style(cls, element):
        """Returns the specified style of an element, i.e. the cascaded style +
        inheritance, see https://www.w3.org/TR/CSS22/cascade.html#specified-value

        .. versionadded:: 1.2

        Args:
            element (BaseElement): the element that the specified style will be computed
                for

        Returns:
            Style: the specified style
        """

        # We currently dont treat the case where parent=absolute value and
        # element=relative value, i.e. specified = relative * absolute.
        cascaded = Style.cascaded_style(element)

        parent = element.getparent()

        if parent is not None and isinstance(parent, IBaseElement):
            cascaded = Style.add_inherited(cascaded, parent.specified_style())
        cascaded.element = element
        return cascaded  # doesn't have a parent

    @classmethod
    def _get_cascade(cls, attribute: str, element: BaseElement) -> Optional[TokenList]:
        if attribute in shorthand_from_value:

            def relevant(style):
                return attribute in style or shorthand_from_value[attribute] in style

        else:

            def relevant(style):
                return attribute in style

        try:
            values = []
            for sheet in element.root.stylesheets:
                for style in sheet:
                    if relevant(style):
                        value = style.get_store(attribute)
                        values += [
                            (value, spec) for spec in style.get_specificities(element)
                        ]
        except FragmentError:
            values = []

        # presentation attributes have specificity 0,
        # see https://www.w3.org/TR/SVG/styling.html#PresentationAttributes
        # they also cannot be shorthands and are always important=False
        if attribute in element.attrib:
            values.append(
                (
                    StyleValue(
                        _get_tokens_from_value(element.attrib[attribute]),
                        False,
                    ),
                    (0, 0, 0),
                )
            )

        if relevant(element.style):
            values.append((element.style.get_store(attribute), (float("inf"), 0, 0)))
        if len(values) == 0:
            return None
        # Sort according to importance, then specificity
        values.sort(key=lambda item: (item[0].important, item[1]))
        return values[-1][0].value

    @classmethod
    def _get_style(cls, attribute: str, element: BaseElement):
        """Specified style for :param:`attribute`"""
        # The resolution order is:
        # - cascade -> then resolve the value, except if the value is "inherit"
        # - parent's computed value
        # - initial (default) value -> then resolve

        result = None
        current = element
        inherited = (
            all_properties[attribute].inherited
            if attribute in all_properties
            else False
        )
        while True:
            result = cls._get_cascade(attribute, current)
            if result is not None and not _is_inherit(result):
                break
            current = current.getparent()
            if current is None or (not inherited and not _is_inherit(result)):
                break
        # Compute value based on current
        if result is None or _is_inherit(result):  # Fallback to default value
            if attribute in all_properties:
                result = all_properties[attribute].default_value
            else:
                return None
        return (
            all_properties[attribute].converter.convert(result, current)
            if attribute in all_properties
            else tinycss2.serialize(result)
        )


class StyleSheets(list):
    """
    Special mechanism which contains all the stylesheets for an svg document
    while also caching lookups for specific elements.

    This caching is needed because data can't be attached to elements as they are
    re-created on the fly by lxml so lookups have to be centralised.
    """

    def lookup(self, element):
        """
        Find all styles for this element.
        """
        for sheet in self:
            for style in sheet.lookup(element):
                yield style

    def lookup_specificity(self, element):
        """
        Find all styles for this element and return the specificity of the match.

        .. versionadded:: 1.2
        """
        for sheet in self:
            for style in sheet.lookup_specificity(element):
                yield style


class StyleSheet(list):
    """
    A style sheet, usually the CDATA contents of a style tag, but also
    a css file used with a css. Will yield multiple Style() classes.
    """

    def __init__(self, content=None, callback=None):
        super().__init__()
        self.callback = None
        # Remove comments
        if content is None:
            parsed = []
        else:
            parsed = tinycss2.parse_stylesheet(
                content, skip_comments=True, skip_whitespace=True
            )
        # Parse rules
        for block in parsed:
            if isinstance(block, tinycss2.ast.QualifiedRule):
                self.append(block)
        self.callback = callback

    def __str__(self):
        return "\n" + "\n".join([str(style) for style in self]) + "\n"

    def _callback(self, style=None):  # pylint: disable=unused-argument
        if self.callback is not None:
            self.callback(self)

    def add(self, rule, style):
        """Append a rule and style combo to this stylesheet"""
        self.append(
            ConditionalStyle(rules=rule, style=str(style), callback=self._callback)
        )

    def append(self, other: str | tinycss2.ast.QualifiedRule):
        """Make sure callback is called when updating"""
        if isinstance(other, str):
            other = tinycss2.parse_one_rule(other)
        if isinstance(other, tinycss2.ast.QualifiedRule):
            other = ConditionalStyle(
                other.prelude, other.content, callback=self._callback
            )
        super().append(other)
        self._callback()

    def lookup(self, element):
        """Lookup the element against all the styles in this sheet"""
        for style in self:
            if any(style.checks(element)):
                yield style

    def lookup_specificity(self, element):
        """Lookup the element_id against all the styles in this sheet
        and return the specificity of the match

        Args:
            element: the element of the element that styles are being queried for

        Yields:
            Tuple[ConditionalStyle, Tuple[int, int, int]]: all matched styles and the
            specificity of the match
        """
        for style in self:
            for specificity in style.get_specificities(element):
                yield (style, specificity)


class ConditionalStyle(Style):
    """
    Just like a Style object, but includes one or more
    conditional rules which places this style in a stylesheet
    rather than being an attribute style.
    """

    def __init__(
        self, rules: str | TokenList = "*", style=None, callback=None, **kwargs
    ):
        super().__init__(style=style, callback=callback, **kwargs)
        self._rules: str | TokenList = rules
        self.rules = list(parser.parse(rules, namespaces=NSS))
        self.checks = [
            CSSCompiler.compile_node(selector.parsed_tree) for selector in self.rules
        ]

    def matches(self, element: etree.Element):
        """Checks if an individual element matches this selector.

        .. versionadded:: 1.4"""
        if isinstance(element, etree._Comment):
            return False
        if any(check(element) for check in self.checks):
            return True
        return False

    def all_matches(self, document: etree.Element):
        """Get all matches of this selector in document as iterator.

        .. versionadded:: 1.4"""
        for el in document.iter():
            if self.matches(el):
                yield el

    def __str__(self):
        """Return this style as a css entry with class"""
        content = self.to_str(";\n  ")
        rules = ",\n".join(str(rule) for rule in self.rules)
        if content:
            return f"{rules} {{\n  {content};\n}}"
        return f"{rules} {{}}"

    def get_specificities(self, element: Optional[BaseElement] = None):
        """Gets an iterator of the specificity of all rules in this ConditionalStyle

        .. versionadded:: 1.2"""
        if element is not None:
            for rule, check in zip(self.rules, self.checks):
                if check(element):
                    yield rule.specificity
        else:
            for rule in self.rules:
                yield rule.specificity
