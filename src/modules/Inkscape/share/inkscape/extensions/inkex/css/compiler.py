# coding=utf-8
#
# Copyright (C) 2023 - Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
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

"""CSS evaluation logic, forked from cssselect2 (rewritten without eval, targeted to
our data structure). CSS selectors are compiled into boolean evaluator functions.
All HTML-specific code has been removed, and we don't duplicate the tree data structure
but work on the normal tree."""

import re
from lxml import etree
from typing import Union, List
from tinycss2.nth import parse_nth

from . import parser
from .parser import SelectorError

# http://dev.w3.org/csswg/selectors/#whitespace
split_whitespace = re.compile("[^ \t\r\n\f]+").findall


def ascii_lower(string):  # from webencodings
    r"""Transform (only) ASCII letters to lower case: A-Z is mapped to a-z."""
    return string.encode("utf8").lower().decode("utf8")


# pylint: disable=protected-access,comparison-with-callable,invalid-name,bad-super-call
# pylint: disable=unnecessary-lambda-assignment


## Iterators without comments.
def iterancestors(element):
    """Iterate over ancestors but ignore comments."""
    for e in element.iterancestors():
        if isinstance(e, etree._Comment):
            continue
        yield e


def iterdescendants(element):
    """Iterate over descendants but ignore comments"""
    for e in element.iterdescendants():
        if isinstance(e, etree._Comment):
            continue
        yield e


def itersiblings(element, preceding=False):
    """Iterate over descendants but ignore comments"""
    for e in element.itersiblings(preceding=preceding):
        if isinstance(e, etree._Comment):
            continue
        yield e


def iterchildren(element):
    """Iterate over children but ignore comments"""
    for e in element.iterchildren():
        if isinstance(e, etree._Comment):
            continue
        yield e


def getprevious(element):
    """Get the previous non-comment element"""
    for e in itersiblings(element, preceding=True):
        return e
    return None


def getnext(element):
    """Get the next non-comment element"""
    for e in itersiblings(element, preceding=False):
        return e
    return None


def FALSE(_el):
    """Always returns 0"""
    return 0


def TRUE(_el):
    """Always returns 1"""
    return 1


class BooleanCompiler:
    def __init__(self) -> None:
        self._func_map = {
            parser.CombinedSelector: self._compile_combined,
            parser.CompoundSelector: self._compile_compound,
            parser.NegationSelector: self._compile_negation,
            parser.RelationalSelector: self._compile_relational,
            parser.MatchesAnySelector: self._compile_any,
            parser.SpecificityAdjustmentSelector: self._compile_any,
            parser.LocalNameSelector: self._compile_local_name,
            parser.NamespaceSelector: self._compile_namespace,
            parser.ClassSelector: self._compile_class,
            parser.IDSelector: self._compile_id,
            parser.AttributeSelector: self._compile_attribute,
            parser.PseudoClassSelector: self._compile_pseudoclass,
            parser.FunctionalPseudoClassSelector: self._compile_functional_pseudoclass,
        }

    def _compile_combined(self, selector: parser.CombinedSelector):
        left_inside = self.compile_node(selector.left)
        if left_inside == FALSE:
            return FALSE  # 0 and x == 0
        if left_inside == TRUE:
            # 1 and x == x, but the element matching 1 still needs to exist.
            if selector.combinator in (" ", ">"):
                left = lambda el: el.getparent() is not None

            elif selector.combinator in ("~", "+"):
                left = lambda el: getprevious(el) is not None

            else:
                raise SelectorError("Unknown combinator", selector.combinator)
        elif selector.combinator == " ":
            left = lambda el: any((left_inside(e)) for e in el.ancestors())

        elif selector.combinator == ">":
            left = lambda el: el.getparent() is not None and left_inside(el.getparent())

        elif selector.combinator == "+":
            left = lambda el: getprevious(el) is not None and left_inside(
                getprevious(el)
            )

        elif selector.combinator == "~":
            left = lambda el: any(
                (left_inside(e)) for e in itersiblings(el, preceding=True)
            )

        else:
            raise SelectorError("Unknown combinator", selector.combinator)

        right = self.compile_node(selector.right)
        if right == FALSE:
            return FALSE  # 0 and x == 0
        if right == TRUE:
            return left  # 1 and x == x
        # Evaluate combinators right to left
        return lambda el: right(el) and left(el)

    def _compile_compound(self, selector: parser.CompoundSelector):
        sub_expressions = [
            expr
            for expr in map(self.compile_node, selector.simple_selectors)
            if expr != TRUE
        ]
        if len(sub_expressions) == 1:
            return sub_expressions[0]
        if FALSE in sub_expressions:
            return FALSE
        if sub_expressions:
            return lambda e: all(expr(e) for expr in sub_expressions)
        return TRUE  # all([]) == True

    def _compile_negation(self, selector: parser.NegationSelector):
        sub_expressions = [
            expr
            for expr in [
                self.compile_node(selector.parsed_tree)
                for selector in selector.selector_list
            ]
            if expr != TRUE
        ]
        if not sub_expressions:
            return FALSE
        return lambda el: not any(expr(el) for expr in sub_expressions)

    @staticmethod
    def _get_subexpr(expression, relative_selector):
        """Helper function for RelationalSelector"""
        if relative_selector.combinator == " ":
            return lambda el: any(expression(e) for e in iterdescendants(el))
        if relative_selector.combinator == ">":
            return lambda el: any(expression(e) for e in iterchildren(el))
        if relative_selector.combinator == "+":
            return lambda el: expression(next(itersiblings(el)))
        if relative_selector.combinator == "~":
            return lambda el: any(expression(e) for e in itersiblings(el))
        raise SelectorError(
            f"Unknown relational selector '{relative_selector.combinator}'"
        )

    def _compile_relational(self, selector: parser.RelationalSelector):
        sub_expr = []

        for relative_selector in selector.selector_list:
            expression = self.compile_node(relative_selector.selector.parsed_tree)
            if expression == FALSE:
                continue
            sub_expr.append(self._get_subexpr(expression, relative_selector))
        return lambda el: any(expr(el) for expr in sub_expr)

    def _compile_any(
        self,
        selector: Union[
            parser.MatchesAnySelector, parser.SpecificityAdjustmentSelector
        ],
    ):
        sub_expressions = [
            expr
            for expr in [
                self.compile_node(selector.parsed_tree)
                for selector in selector.selector_list
            ]
            if expr != FALSE
        ]
        if not sub_expressions:
            return FALSE
        return lambda el: any(expr(el) for expr in sub_expressions)

    def _compile_local_name(self, selector: parser.LocalNameSelector):
        return lambda el: el.TAG == selector.local_name

    def _compile_namespace(self, selector: parser.NamespaceSelector):
        return lambda el: el.NAMESPACE == selector.namespace

    def _compile_class(self, selector: parser.ClassSelector):
        return lambda el: selector.class_name in el.classes

    def _compile_id(self, selector: parser.IDSelector):
        return lambda el: super(etree.ElementBase, el).get("id", None) == selector.ident  # type: ignore

    def _compile_attribute(self, selector: parser.AttributeSelector):
        if selector.namespace is not None:
            if selector.namespace:
                key_func = lambda el: (
                    f"{{{selector.namespace}}}{selector.name}"
                    if el.NAMESPACE != selector.namespace
                    else selector.name
                )

            else:
                key_func = lambda el: selector.name

            value = selector.value
            if selector.case_sensitive is False:
                value = value.lower()

                attribute_value = (
                    lambda el: super(etree.ElementBase, el)
                    .get(key_func(el), "")  # type: ignore
                    .lower()
                )

            else:
                attribute_value = lambda el: super(etree.ElementBase, el).get(  # type: ignore
                    key_func(el), ""
                )

            if selector.operator is None:
                return lambda el: key_func(el) in el.attrib
            if selector.operator == "=":
                return lambda el: (
                    key_func(el) in el.attrib and attribute_value(el) == value
                )
            if selector.operator == "~=":
                return (
                    FALSE
                    if len(value.split()) != 1 or value.strip() != value
                    else lambda el: value in split_whitespace(attribute_value(el))
                )
            if selector.operator == "|=":
                return lambda el: (
                    key_func(el) in el.attrib
                    and (
                        attribute_value(el) == value
                        or attribute_value(el).startswith(value + "-")
                    )
                )
            if selector.operator == "^=":
                if value:
                    return lambda el: attribute_value(el).startswith(value)
                return FALSE
            if selector.operator == "$=":
                return (
                    (lambda el: attribute_value(el).endswith(value)) if value else FALSE
                )
            if selector.operator == "*=":
                return (lambda el: value in attribute_value(el)) if value else FALSE
            raise SelectorError("Unknown attribute operator", selector.operator)
        # In any namespace
        raise NotImplementedError  # TODO

    def _compile_pseudoclass(self, selector: parser.PseudoClassSelector):
        if selector.name in ("link", "any-link", "local-link"):

            def ancestors_or_self(el):
                yield el
                yield from iterancestors(el)

            return lambda el: any(
                e.TAG == "a" and super(etree.ElementBase, e).get("href", "") != ""  # type: ignore
                for e in ancestors_or_self(el)
            )
        if selector.name in (
            "visited",
            "hover",
            "active",
            "focus",
            "focus-within",
            "focus-visible",
            "target",
            "target-within",
            "current",
            "past",
            "future",
            "playing",
            "paused",
            "seeking",
            "buffering",
            "stalled",
            "muted",
            "volume-locked",
            "user-valid",
            "user-invalid",
        ):
            # Not applicable in a static context: never match.
            return FALSE
        if selector.name in ("enabled", "disabled", "checked"):
            # Not applicable to SVG
            return FALSE
        if selector.name in ("root", "scope"):
            return lambda el: el.getparent() is None
        if selector.name == "first-child":
            return lambda el: getprevious(el) is None
        if selector.name == "last-child":
            return lambda el: getnext(el) is None
        if selector.name == "first-of-type":
            return lambda el: all(
                s.tag != el.tag for s in itersiblings(el, preceding=True)
            )
        if selector.name == "last-of-type":
            return lambda el: all(s.tag != el.tag for s in itersiblings(el))
        if selector.name == "only-child":
            return lambda el: getnext(el) is None and getprevious(el) is None
        if selector.name == "only-of-type":
            return lambda el: all(s.tag != el.tag for s in itersiblings(el)) and all(
                s.tag != el.tag for s in itersiblings(el, preceding=True)
            )
        if selector.name == "empty":
            return lambda el: not list(el) and el.text is None
        raise SelectorError("Unknown pseudo-class", selector.name)

    def _compile_lang(self, selector: parser.FunctionalPseudoClassSelector):
        langs = []
        tokens = [
            token
            for token in selector.arguments
            if token.type not in ("whitespace", "comment")
        ]
        while tokens:
            token = tokens.pop(0)
            if token.type == "ident":
                langs.append(token.lower_value)
            elif token.type == "string":
                langs.append(ascii_lower(token.value))
            else:
                raise SelectorError("Invalid arguments for :lang()")
            if tokens:
                token = tokens.pop(0)
                if token.type != "ident" and token.value != ",":
                    raise SelectorError("Invalid arguments for :lang()")

        def haslang(el, lang):
            print(
                el.get("lang"),
                lang,
                el.get("lang", "") == lang or el.get("lang", "").startswith(lang + "-"),
            )
            return el.get("lang", "").lower() == lang or el.get(
                "lang", ""
            ).lower().startswith(lang + "-")

        return lambda el: any(
            haslang(el, lang) or any(haslang(el2, lang) for el2 in iterancestors(el))
            for lang in langs
        )

    def _compile_functional_pseudoclass(
        self, selector: parser.FunctionalPseudoClassSelector
    ):
        if selector.name == "lang":
            return self._compile_lang(selector)
        nth: List[str] = []
        selector_list: List[str] = []
        current_list = nth
        for argument in selector.arguments:
            if argument.type == "ident" and argument.value == "of":
                if current_list is nth:
                    current_list = selector_list
                    continue
            current_list.append(argument)

        if selector_list:
            compiled = tuple(
                self.compile_node(selector.parsed_tree)
                for selector in parser.parse(selector_list)
            )
            test = lambda el: all(expr(el) for expr in compiled)

        else:
            test = TRUE

        if selector.name == "nth-child":
            count = lambda el: sum(
                1 for e in itersiblings(el, preceding=True) if test(e)
            )

        elif selector.name == "nth-last-child":
            count = lambda el: sum(1 for e in itersiblings(el) if test(e))
        elif selector.name == "nth-of-type":
            count = lambda el: sum(
                1
                for s in (e for e in itersiblings(el, preceding=True) if test(e))
                if s.tag == el.tag
            )

        elif selector.name == "nth-last-of-type":
            count = lambda el: sum(
                1 for s in (e for e in itersiblings(el) if test(e)) if s.tag == el.tag
            )

        else:
            raise SelectorError("Unknown pseudo-class", selector.name)

        count_func = lambda el: count(el) if test(el) else float("nan")

        result = parse_nth(nth)
        if result is None:
            raise SelectorError(f"Invalid arguments for :{selector.name}()")
        a, b = result
        # x is the number of siblings before/after the element
        # Matches if a positive or zero integer n exists so that:
        # x = a*n + b-1
        # x = a*n + B
        B = b - 1
        if a == 0:
            # x = B
            return lambda el: count_func(el) == B

        # n = (x - B) / a
        def evaluator(el):
            n, r = divmod(count_func(el) - B, a)
            return r == 0 and n >= 0

        return evaluator

    def compile_node(self, selector):
        """Return a boolean expression, as a callable.

        When evaluated in a context where the `el` variable is an
        :class:`cssselect2.tree.Element` object, tells whether the element is a
        subject of `selector`.

        """
        try:
            return self._func_map[selector.__class__](selector)
        except KeyError as e:
            raise TypeError(type(selector), selector) from e


CSSCompiler = BooleanCompiler()
