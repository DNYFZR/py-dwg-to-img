# SPDX-FileCopyrightText: 2023 Software Freedom Conservancy <info@sfconservancy.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
"""Commonly used functions."""

from lxml import etree
from io import BytesIO


def to_pretty_xml(xml_string: bytes) -> bytes:
    """Return a pretty xml string with newlines and indentation."""
    # from https://stackoverflow.com/a/3974112/1320237
    # and https://stackoverflow.com/a/9612463/1320237
    parser = etree.XMLParser(remove_blank_text=True)
    file = BytesIO()
    file.write(xml_string)
    file.seek(0)
    element = etree.parse(file, parser)
    return etree.tostring(element, pretty_print=True)


__all__ = ["to_pretty_xml"]
