#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Shared objects for the binary parser.

Shared objects allow accessing fields from a link object with the same id and doc_id
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from typing import Any, ClassVar, List, Optional
from weakref import WeakValueDictionary

from .types import AFDictObject, AFListObject, AFObject, Document, ObjectStatus


class DocIdInvalidError(Exception):
    def __init__(self, doc_id: int) -> None:
        super().__init__(f"Document id:{doc_id} not found")
        self.doc_id = doc_id


class LinkedObjectNotFound(Exception):
    def __init__(self, obj_id: int) -> None:
        super().__init__(f"Shared object id:{obj_id} not found")
        self.obj_id = obj_id


@dataclass
class SharedAFObject(AFObject):
    _shared_items: ClassVar[List[WeakValueDictionary[int, SharedAFObject]]] = []
    docid: InitVar[Optional[int]] = field(default=None, repr=False)
    _doc_id: int = field(init=False, repr=False, compare=False)

    def __post_init__(self, docid: Optional[int] = None):
        self._doc_id = self.new_doc() if docid is None else docid
        self.set_status(self.status)

    @classmethod
    def new_doc(cls) -> int:
        cls._shared_items.append(WeakValueDictionary())
        return len(cls._shared_items) - 1

    @property
    def shared_items(self) -> WeakValueDictionary[int, SharedAFObject]:
        if self._doc_id >= len(self._shared_items) or self._doc_id < 0:
            raise DocIdInvalidError(self._doc_id)

        return self._shared_items[self._doc_id]

    @property
    def doc_id(self) -> int:
        return self._doc_id

    @property
    def shared_self(self) -> SharedAFObject:
        if self.status != ObjectStatus.LINK:
            raise ValueError("Not a link object")
        if self.id not in self.shared_items:
            raise LinkedObjectNotFound(self.id)
        return self.shared_items[self.id]

    def set_status(self, status: ObjectStatus):
        self.status = status
        if status == ObjectStatus.SHARED:
            if self.id in self.shared_items:
                raise ValueError(f"Duplicate shared object id:{self.id}")
            self.shared_items[self.id] = self
            return

        if self.shared_items.get(self.id) is self:
            self.shared_items.pop(self.id, None)

    def get_type(self) -> Optional[str]:
        return (
            self.shared_self.get_type()
            if self.status == ObjectStatus.LINK
            else super().get_type()
        )

    def __getitem__(self, key: str | int) -> Any:
        if self.status == ObjectStatus.LINK:
            return self.shared_self[key]
        return super().__getitem__(key)  # type: ignore

    def __contains__(self, key: str | int) -> bool:
        if self.status == ObjectStatus.LINK:
            return key in self.shared_self
        return super().__contains__(key)  # type: ignore

    def __len__(self) -> int:
        if self.status == ObjectStatus.LINK:
            return len(self.shared_self)
        return super().__len__()  # type: ignore


@dataclass
class SharedAFDictObject(SharedAFObject, AFDictObject):
    pass


@dataclass
class SharedAFListObject(SharedAFObject, AFListObject):
    pass


@dataclass
class SharedDocument(SharedAFDictObject, Document):
    def set_status(self, status: ObjectStatus):
        assert status == ObjectStatus.ROOT, "Document must be root"
        return super().set_status(status)
