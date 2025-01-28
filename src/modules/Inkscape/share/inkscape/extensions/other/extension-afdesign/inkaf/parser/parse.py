#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Parses the extracted contents of an afdesign file
Based on https://github.com/VMDevCpp/afread, MIT-licensed
"""

from __future__ import annotations
from io import BufferedIOBase
from typing import Optional, List, Dict, Union

from .enhance import process
from .utils import BinaryParser, BitReader
from .consts import content_magic
from .types import (
    Document,
    ObjectStatus,
    AFObjectMetadata,
    EmbeddedData,
    MetadataStatus,
    AFObject,
    EnumT,
    AFListObject,
    AFDictObject,
    FlagsT,
    Field,
    Curve12,
    Curve16,
    Curve18,
    Curve18Type,
    UnknownStruct,
)


class AFParser(BinaryParser):
    data: BitReader

    def __init__(self, data: BufferedIOBase):
        super().__init__(BitReader(data))
        self.document = Document(0, [], ObjectStatus.ROOT, {}, {})

        self.reader_map = {
            0x01: self.read_u8,  # uint8_t
            0x02: self.read_u16,  # uint16_t
            0x03: self.read_u32,  # uint32_t
            0x04: lambda: int.from_bytes(
                self.read(8), byteorder="little", signed=False
            ),  # uint64_t
            0x05: lambda: int.from_bytes(
                self.read(1), byteorder="little", signed=True
            ),  # int8_t
            0x06: lambda: int.from_bytes(
                self.read(2), byteorder="little", signed=True
            ),  # int16_t
            0x07: self.read_i32,  # int32_t
            0x08: lambda: int.from_bytes(
                self.read(8), byteorder="little", signed=True
            ),  # int64_t
            0x09: self.read_float,  # float
            0x0A: self.read_double,  # double
            0x15: lambda: [self.read_i32() for _ in range(2)],
            0x16: lambda: [self.read_i32() for _ in range(3)],
            0x17: lambda: [self.read_i32() for _ in range(4)],
            0x18: lambda: [self.read_i32() for _ in range(5)],
            0x19: lambda: [self.read_i32() for _ in range(6)],
            0x1F: lambda: [self.read_float() for _ in range(2)],
            0x20: lambda: [self.read_float() for _ in range(3)],
            0x21: lambda: [self.read_float() for _ in range(4)],
            0x22: lambda: [self.read_float() for _ in range(5)],
            0x23: lambda: [self.read_float() for _ in range(6)],
            0x24: lambda: [self.read_double() for _ in range(2)],
            0x25: lambda: [self.read_double() for _ in range(3)],
            0x26: lambda: [self.read_double() for _ in range(4)],
            0x27: lambda: [self.read_double() for _ in range(5)],
            0x28: lambda: [self.read_double() for _ in range(6)],
            0x29: self.data.read_bit,
            0x2B: self.read_string,
            0x2D: self.read_binary_data,
            0x2E: self.read_string,
            0x2F: self.read_u32,
            0x30: self.load_object_30,
            0x31: self.load_object_31,
            0x33: self.read_embedded_data,
            0x34: self.read_u32,
            0x75: self.read_flagsT,
        }
        # These are only for debugging the parser.
        self.tags: List[Dict[str, Union[int, str]]] = []

    def add_tag(self, caption: str, start: int, end: int, color: Optional[str] = None):
        self.tags.append({"start": start, "end": end, "caption": caption})

    def set_end_tag(self, start: int, end: int):
        [i for i in self.tags if i["start"] == start][0]["end"] = end

    def parse(self) -> Document:
        df = self.document.doc_format

        df["file_tag"] = self.read_u32()
        assert df["file_tag"] == content_magic

        df["file_ver"] = self.read_u16()
        df["type_tag"] = self.read_tag()
        df["type_ver"] = self.read_u16()

        if df["file_ver"] > 2:
            raise Exception("Unknown file format")
        elif df["file_ver"] < 2:
            df["version"] = 0
        else:
            df["version"] = self.read_u32()

        self.document.id = 0
        self.document.types = [AFObjectMetadata(0, df["file_tag"], MetadataStatus.TAG)]

        self.load_fields(self.document, True)
        # Postprocessing step
        return process(self.document)

    def format_position(self):
        return f"{self.get_pos()} (line {hex(self.get_pos() // 16 * 16)}, col {hex(self.get_pos() % 16)})"

    def load_fields(self, parent: AFObject, with_tag: bool = True):
        """Load all following fields into parent"""
        while True:
            pos = self.get_pos()
            type_ = self.read_u8()
            array = type_ >= 128
            type_ &= 0x7F

            if type_ == 0x00:
                return
            if type_ > 0x77:
                raise ValueError(f"invalid type at {pos}")

            tag = self.read_tag() if with_tag else None

            need_tag = type_ in (0x30, 0x31, 0x32, 0x33, 0x75, 0x76, 0x77)
            if need_tag and tag is None:
                raise ValueError("missing tag")

            result = Field(type_, self.load_field(type_, array), parent=parent)

            parent.append(tag, result)

    def load_field(self, type_: int, array: bool):
        count = 1
        if array:
            if type_ in (0x2B, 0x2E):
                _ = self.read_u32()  # total_size comes before count
            if type_ in (0x2D, 0x33, 0x75):
                raise ValueError(
                    "Don't know how arrays for embedded/binary/flagsT data work"
                )
            count = self.read_u32()

        if type_ == 0x29:
            self.data.clear_bits()

        # Get loader function
        load_func = None
        if type_ in self.reader_map:
            load_func = self.reader_map[type_]
        elif type_ == 0x2A:
            version = self.read_u16() if array else None

            def load_func():
                return self.read_enumT(version)
        elif type_ == 0x2C:
            size = self.read_u16()

            def load_func():
                return self.read_curve_struct(size)
        elif type_ == 0x32:
            h32 = None
            if array:
                tag2 = self.read_tag()
                h32 = AFObjectMetadata(self.read_u16(), tag2, MetadataStatus.TAG_ID)

            def load_func():
                return self.load_object_32(h32)

        elif 0x35 <= type_ <= 0x74:

            def load_func():
                return self.read_struct(type_)

        if load_func is not None:
            tmp = [load_func() for _ in range(count)]
            return tmp[0] if not array else tmp
        else:
            raise ValueError(
                f"Unknown type {hex(type_)} at position {self.format_position()}."
            )

    def read_string(self):
        length = self.read_u32()
        return self.read(length).decode("utf-8")

    def read_enumT(self, version=None):
        return EnumT(self.read_u16(), self.read_u16() if version is None else version)

    def read_curve_struct(self, size: int):
        if size == 12:
            return Curve12(
                self.read_double(),
                (self.read_u8(), self.read_u8(), self.read_u8(), self.read_u8()),
            )

        elif size == 16:
            return Curve16(self.read_double(), (self.read_u32(), self.read_u32()))
        elif size == 18:
            return Curve18(
                (self.read_double(), self.read_double()),
                Curve18Type(self.read_u8()),
                self.read_u8(),
            )

        elif size in [24, 32]:
            return UnknownStruct(self.read(size))

        else:
            raise ValueError("Bad size for curve struct")

    def read_struct(self, type_: int):
        # We only read the data here since would otherwise need parent properties
        # to discriminate further. This is done in a later step, in enhance.py
        size = type_ - 0x34
        return UnknownStruct(self.read(size))

    def read_embedded_data(self):
        tag = self.read_tag()
        size = self.read_u32()
        data = self.read(size)
        for char in data:
            if not (chr(char).isalnum() or chr(char) == "/"):
                raise ValueError(
                    f"Invalid embedded data, encountered character {chr(char)}"
                )
        return EmbeddedData(tag, size, data.decode("latin-1"))

    def read_binary_data(self):
        size = self.read_u32()
        return self.read(size)

    def read_flagsT(self):
        version = self.read_u16()
        count = self.read_u8()
        flags = self.read(count)
        return FlagsT(version, flags)

    def load_object_30(self) -> AFListObject:
        """Object of type 30"""
        dest = AFListObject(0, [], ObjectStatus.NON_SHARED, [])
        self.load_fields(dest, False)
        return dest

    def load_object_31(self) -> AFDictObject:
        """Object of type 31"""
        dest = AFDictObject(0, [], ObjectStatus(self.read_u8()), {})
        if dest.status == ObjectStatus.SHARED:
            dest.id = self.read_u32()
            # TODO this ID needs to be unique

            while True:
                status = AFObjectMetadata(0, "", MetadataStatus.TAG)
                dest.types.append(status)
                type_flag = self.read_u8()
                if type_flag == 0:
                    status.tag = self.read_tag()
                    status.id = self.read_u16()
                    self.load_fields(dest)
                    status.status = MetadataStatus.TAG_ID
                elif type_flag == 1:
                    status.tag = self.read_tag()
                    break
                elif type_flag == 2:
                    dest.types.remove(status)
                    break
                else:
                    raise ValueError(
                        f"Unknown status type flag at {self.format_position()}"
                    )

            self.load_fields(dest)
        elif dest.status == ObjectStatus.LINK:
            dest.id = self.read_u32()
            # TODO this ID needs to be unique

        elif dest.status == ObjectStatus.NULL:
            pass
        else:
            raise ValueError(
                f"Unknown status flag {dest.status} at {self.format_position()}"
            )
        return dest

    def load_object_32(self, status: Optional[AFObjectMetadata] = None) -> AFDictObject:
        flag = self.read_u8()
        dest = AFDictObject(
            0, [], ObjectStatus.NULL if flag == 0 else ObjectStatus.NON_SHARED, {}
        )
        if dest.status == ObjectStatus.NON_SHARED:
            dest.id = 0
            if status is None:
                tag = self.read_tag()
                status = AFObjectMetadata(self.read_u16(), tag, MetadataStatus.TAG_ID)
            dest.types.append(status)

            self.load_fields(dest)
        return dest
