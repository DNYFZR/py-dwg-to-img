#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Common stream reading functions
"""

from io import BufferedIOBase, BytesIO
import struct
from typing import Union


class ReaderWrapper:
    def __init__(self, stream: BufferedIOBase):
        self.stream = stream

    def read(self, num: int) -> bytes:
        read = self.stream.read(num)
        assert len(read) == num, "Unexpected EOF"
        return read

    def tell(self) -> int:
        return self.stream.tell()


class BitReader(ReaderWrapper):
    def __init__(self, stream: BufferedIOBase):
        super().__init__(stream)
        self.current_byte = 0
        self.bit_shift = 8

    def read_bit(self) -> bool:
        if self.bit_shift == 8:
            byte = self.stream.read(1)
            if not byte:  # End of stream
                raise EOFError("No more bits available")
            self.current_byte = ord(byte)
            self.bit_shift = 0
        result = bool((self.current_byte >> self.bit_shift) & 1)
        self.bit_shift += 1
        return result

    def clear_bits(self):
        self.bit_shift = 8


class BinaryParser:
    def __init__(self, data: Union[ReaderWrapper, bytes, BufferedIOBase]):
        if isinstance(data, bytes):
            data = BytesIO(data)
        if isinstance(data, BufferedIOBase):
            data = ReaderWrapper(data)
        self.data = data
        assert self.data is not None, f"Bad type, {type(data)}"

    def read(self, num_bytes: int) -> bytes:
        return self.data.read(num_bytes)

    def get_pos(self):
        return self.data.tell()

    def read_u8(self) -> int:
        return int.from_bytes(self.read(1), byteorder="little", signed=False)

    def read_u16(self) -> int:
        return int.from_bytes(self.read(2), byteorder="little", signed=False)

    def read_u32(self) -> int:
        return int.from_bytes(self.read(4), byteorder="little", signed=False)

    def read_u64(self) -> int:
        return int.from_bytes(self.read(8), byteorder="little", signed=False)

    def read_i32(self) -> int:
        return int.from_bytes(self.read(4), byteorder="little", signed=True)

    def read_float(self) -> float:
        return struct.unpack("f", self.read(4))[0]

    def read_double(self) -> float:
        return struct.unpack("d", self.read(8))[0]

    def read_tag(self) -> str:
        tag = self.read(4).decode("latin-1")[::-1]
        return tag
