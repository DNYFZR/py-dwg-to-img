#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Takes the parsed object tree, and applies certain enhancements
to it to make it easier to convert.
"""

from __future__ import annotations

from typing import Any, Optional

from .sharedaf import (
    SharedAFDictObject,
    SharedAFListObject,
    SharedAFObject,
    SharedDocument,
)
from .types import AFDictObject, AFListObject, Document, Field, UnknownStruct
from .utils import BinaryParser


def process_obj(
    value: Any, field: Field, doc_id: Optional[int] = None, tag: Optional[str] = None
) -> Any:
    if isinstance(value, list):
        # this was an array
        return [process_obj(o, field, doc_id, tag) for o in value]

    if isinstance(value, AFDictObject):
        return process_dictobj(value, doc_id, tag)
    if isinstance(value, AFListObject):
        return process_listobj(value, doc_id, tag)
    if isinstance(value, UnknownStruct):
        assert field.parent is not None
        return process_struct(value, tag, field.parent.get_type())
    return value


def process_dictobj(
    obj: AFDictObject, doc_id: Optional[int] = None, tag: Optional[str] = None
) -> SharedAFDictObject:
    doc_id = SharedAFObject.new_doc() if doc_id is None else doc_id

    shared = (
        SharedDocument(
            id=obj.id,
            types=obj.types,
            status=obj.status,
            fields=obj.fields,
            doc_format=obj.doc_format,
            docid=doc_id,
        )
        if isinstance(obj, Document)
        else SharedAFDictObject(
            id=obj.id,
            types=obj.types,
            status=obj.status,
            fields=obj.fields,
            docid=doc_id,
        )
    )

    for tag, field in shared.fields.items():
        if isinstance(field, list):
            # Duplicate keys, process them one by one
            field[:] = [
                Field(o.type, process_obj(o.value, o, doc_id, tag), shared)
                for o in field
            ]
            continue
        field.value = process_obj(field.value, field, doc_id, tag)
        field.parent = shared

    return shared


def process_listobj(
    obj: AFListObject, doc_id: Optional[int] = None, tag: Optional[str] = None
) -> SharedAFListObject:
    doc_id = SharedAFObject.new_doc() if doc_id is None else doc_id

    shared = SharedAFListObject(
        id=obj.id, types=obj.types, status=obj.status, fields=obj.fields, docid=doc_id
    )
    for field in shared.fields:
        field.value = process_obj(field.value, field, doc_id)
        field.parent = shared
    return shared


def process_struct(
    value: UnknownStruct,
    field_tag: Optional[str] = None,
    parent_tag: Optional[str] = None,
) -> Any:
    size = len(value.data)
    parser = BinaryParser(value.data)
    if size == 4 and parent_tag == "BGrd" and field_tag == "Colr":
        return tuple(parser.read_u8() for _ in range(4))
    elif field_tag == "_col":
        if size == 8:
            if parent_tag == "LABA":
                return tuple(parser.read_u16() for _ in range(4))
            if parent_tag == "GRAY":
                return (parser.read_float(), parser.read_float())
        if size == 16:
            if parent_tag in ["HSLA", "RGBA"]:
                return tuple(parser.read_float() for _ in range(4))
        if size == 20:
            if parent_tag == "CMYK":
                return tuple(parser.read_float() for _ in range(5))
        raise ValueError("Unknown color format")
    return value


def process(doc: Document) -> SharedDocument:
    return process_dictobj(doc, SharedAFObject.new_doc(), None)  # type: ignore
