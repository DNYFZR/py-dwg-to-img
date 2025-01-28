#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Object types for the binary parser
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class Field:
    type: int
    value: Any = None
    parent: Optional[AFObject] = None


@dataclass
class AFObjectMetadata:
    id: int
    tag: str
    status: MetadataStatus


class ObjectStatus(Enum):
    NULL = 0
    SHARED = 1
    LINK = 2
    NON_SHARED = 3
    ROOT = 4


class MetadataStatus(Enum):
    TAG = 0
    TAG_ID = 1


@dataclass
class AFObject:
    id: int
    types: List[AFObjectMetadata]
    status: ObjectStatus

    def get_type(self) -> Optional[str]:
        return self.types[0].tag if self.types else None

    def append(self, tag: Optional[str], value: Any) -> None: ...

    def get(self, key: str | int, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    @abstractmethod
    def __getitem__(self, key: Any) -> Any: ...

    @abstractmethod
    def __contains__(self, key: Any) -> bool: ...

    @abstractmethod
    def __len__(self) -> int: ...


@dataclass
class AFDictObject(AFObject):
    fields: Dict[str, Union[Field, List[Field]]]

    def append(self, tag: Optional[str], value: Any) -> None:
        assert tag is not None, "AFDictObject entries need tags"
        if tag in self.fields:
            fld = self.fields[tag]
            if isinstance(fld, list):
                fld.append(value)
            else:
                self.fields[tag] = [fld, value]
        else:
            self.fields[tag] = value

    def __getitem__(self, key: str) -> Any:
        field = self.fields[key]
        return field[-1].value if isinstance(field, list) else field.value

    def __contains__(self, key: str) -> bool:
        return key in self.fields

    def __len__(self) -> int:
        return len(self.fields)


@dataclass
class AFListObject(AFObject):
    fields: List[Field]

    def append(self, tag: Optional[str], value: Any) -> None:
        self.fields.append(value)

    def __getitem__(self, index: int) -> Any:
        if index not in self:
            raise KeyError(index)
        field = self.fields[index]
        return field[-1].value if isinstance(field, list) else field.value

    def __contains__(self, index: int) -> bool:
        return 0 <= index < len(self.fields)

    def __len__(self) -> int:
        return len(self.fields)


@dataclass
class EnumT:  # TODO: What is this?
    id: int
    version: int


@dataclass
class Curve12:
    doubles: float
    unsigned_ints: Tuple[int, int, int, int]


@dataclass
class Curve16:
    doubles: float
    unsigned_ints: Tuple[int, int]


class Curve18Type(Enum):
    CONTROL_POINT = 0
    SHARP = 1
    SMOOTH = 2
    SMART = 3
    SMOOTH_SHARP = 4  # TODO: Sharp with control points?


@dataclass
class Curve18:
    point: Tuple[float, float]
    type: Curve18Type
    index: int


@dataclass
class UnknownStruct:
    data: bytes


@dataclass
class FlagsT:
    version: int
    flags: bytes


@dataclass
class EmbeddedData:
    tag: str
    size: int
    data: str


@dataclass
class Document(AFDictObject):
    doc_format: Dict[str, Any]
