#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Reads an afdesign file and extracts the contents, to be used by the
parser.
"""

from __future__ import annotations
from io import BufferedReader
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import warnings
import zlib
import zstandard


from .utils import BinaryParser
from .consts import expected_file_classes, expected_documents, file_magic


@dataclass
class InfHeader:
    """Structure to handle basic data in the Header"""

    fat_offset: int
    thumbnail_offset: int
    creation_date: datetime
    revision: int


@dataclass
class InfHeader2:
    """Structure to handle additional data in the Header"""

    revision: int


@dataclass
class Header:
    """Header of an .afdesign file"""

    version: int
    class_tag: str
    inf_header: InfHeader
    inf_header_2: Optional[InfHeader2]


@dataclass
class AFFileStructure:
    """Struct for an .afdesign file"""

    header: Header
    files: Dict[str, bytes]


@dataclass
class FAT:
    """Struct for the file access table (FAT)"""

    tag: str
    creation_date: datetime
    files: List[FATFile]
    dirs: List[FATDir]

    def get_file(self, file_id: int) -> Optional[FATFile]:
        """Finds the file with the given id, or None"""
        return next((file for file in self.files if file.id == file_id), None)

    def __repr__(self):
        return f"{{Date: {str(self.creation_date)}, Files: {len(self.files)}, Directories: {len(self.dirs)}}}"


class FATFileType(Enum):
    """Type of a FAT file"""

    NORMAL_WITH_NAME = 0
    NORMAL_WITHOUT_NAME = 1
    DELETED = 2


@dataclass
class FATFile:
    """Struct for an individual file. This class is directly
    used only for files with Type == Deleted"""

    id: int
    flag: FATFileType


@dataclass
class NormalFATFile(FATFile):
    """Struct for an individual file"""

    offset: int
    size: int
    compressed_size: int
    crc32: int
    compression: int
    name: Optional[str] = None


@dataclass
class FATDir:
    """Struct for a directory within the FAT"""

    files_num: int
    name: str


def undo_cumulative_sum(data: bytes) -> bytes:
    byte = 0
    result = bytearray()
    for b in data:
        byte = (byte + b) & 0xFF
        result.append(byte)
    return bytes(result)


class AFExtractor(BinaryParser):
    """Extract the contents of the .afdesign archive.
    Afterwards, self.content.files contains the binary
    data for the latest revision of all files in the archive"""

    def __init__(self, data: BufferedReader) -> None:
        super().__init__(data)
        self.content: Optional[AFFileStructure] = None
        self.ids: Dict[str, int] = {}
        self.revisions: List[datetime] = []
        self.fats: List[FAT] = []
        self._read_file()

    def _read_file(self):
        self.data.stream.seek(0)
        header = self._read_header()
        self.content = AFFileStructure(header, {})

        self._load_fat()
        self._load_content()

    def _read_header(self) -> Header:
        assert self.read_u32() == file_magic
        version = self.read_u16()
        flag = self.read_u16()
        class_tag = self.read_tag()
        assert class_tag in expected_file_classes, f"unknown file type {class_tag}"
        assert 7 <= version <= 11, "invalid version"

        # read the header information
        header_tag = self.read_tag()
        assert header_tag == "fnI#", f"Unexpected header tag {header_tag}"
        fat_offset = self.read_u64()
        thmb_offset = self.read_u64()
        self.data.read(16)  # unknown
        timestamp = self.read_u64()
        revision = self.read_u32()
        self.read_u32()  # unknown

        inf2 = None
        if version > 7:
            assert self.read_tag() == "torP"
            revision2 = self.read_u32()
            inf2 = InfHeader2(revision2)

        result = Header(
            version,
            class_tag,
            InfHeader(
                fat_offset, thmb_offset, datetime.fromtimestamp(timestamp), revision
            ),
            inf2,
        )

        if not (flag % 2 == 0 and flag & 2 == 0):
            raise ValueError(f"Unknown format, flag was {flag}")

        return result

    def _load_fat_file(self, fat_tag: str):
        fat_id = self.read_u32()
        flag = FATFileType(self.read_u8())
        if flag != FATFileType.DELETED:
            file_offset = self.read_u64()
            size = self.read_u64()
            compressed_size = self.read_u64()
            crc32 = self.read_u32()
            compression = self.read_u8()
            if not fat_tag == "TAF#":
                self.read(4)  # Unknown u32
            if fat_tag == "4TF#":
                self.read(4)  # Unknown u32
            if fat_tag in ("TAF#", "2TF#"):
                compression = {
                    0x01: 0x01,
                    0x02: 0x41,
                    0x03: 0x81,
                    0x04: 0xC1,
                }.get(compression, 0)
            name = None
            if flag == FATFileType.NORMAL_WITH_NAME:
                name = self.read(self.read_u16()).decode("latin-1")
                if name in self.ids:
                    assert self.ids[name] == fat_id, "Invalid ID"
                self.ids[name] = fat_id
            return NormalFATFile(
                fat_id,
                flag,
                file_offset,
                size,
                compressed_size,
                crc32,
                compression,
                name,
            )
        return FATFile(fat_id, flag)

    def _load_fat(self):
        """Load the file access table"""
        assert self.content is not None
        offset = self.content.header.inf_header.fat_offset
        while offset != 0:
            self.data.stream.seek(offset)
            fat_tag = self.read_tag()
            assert fat_tag in (
                "TAF#",
                "2TF#",
                "3TF#",
                "4TF#",
            ), f"unexpected FAT tag: {fat_tag}"
            next_offset = self.read_u64()
            created = datetime.fromtimestamp(self.read_u64())
            self.read(24)  # Unknown, 3x u64
            files_count = self.read_u32()
            self.read(8)  # Unknown, 2x u32
            dirs_count = self.read_u16()
            self.read(1)  # Unknown, 1x u8

            fat_files = []
            fat_dirs = []

            for _ in range(files_count):
                fat_files.append(self._load_fat_file(fat_tag))

            for _ in range(dirs_count):
                str_len = self.read_u16()
                some_len = self.read_u16()
                assert some_len == 0
                files_num = self.read_u64()
                name = self.read(str_len).decode("latin-1")
                fat_dirs.append(FATDir(files_num, name))

            self.revisions.append(created)
            self.fats.append(FAT(fat_tag, created, fat_files, fat_dirs))
            offset = next_offset

    def get_head_revision(self, name):
        return self._get_revision(name, None)

    def _get_revision(
        self, name, revision_date: Optional[datetime]
    ) -> Optional[FATFile]:
        if name not in self.ids:
            return None
        fat_id = self.ids[name]
        # Find the FAT where the latest revision before revision_date of file sits.
        # by sorting descending by creation date
        desc = sorted(
            (
                (fat.creation_date, fat.get_file(fat_id))
                for fat in self.fats
                if fat.get_file(fat_id) is not None
                and (revision_date is None or fat.creation_date <= revision_date)
            ),
            key=lambda i: i[0],
            reverse=True,
        )
        if not desc:
            return None
        return desc[0][1]

    def _load_content(self):
        for doc in expected_documents:
            revision = self.get_head_revision(doc)
            if revision is None:
                continue
            if not isinstance(revision, NormalFATFile):
                continue
            if revision.compressed_size == 0:
                continue

            file_content = self.extract(revision)

            assert self.content is not None
            self.content.files[doc] = file_content

    def extract(self, file: NormalFATFile) -> bytes:
        """Extract a FAT file"""
        assert file.size != 0, "Empty file"
        assert file.offset != 0, "Invalid offset"

        self.data.stream.seek(file.offset)
        tag = self.read_tag()
        assert tag == "liF#", f"Unexpected tag: {tag}"

        flag = (file.compression >> 5) & 1
        alg = file.compression & 3
        type_ = file.compression & 0xC0
        if type_ == 0x40:
            type_ = 1
            flag = 0
        elif type_ == 0x80:
            type_ = 2
        elif type_ == 0xC0:
            type_ = 3
        else:
            type_ = 0
            flag = 0

        data = self.read(file.compressed_size)
        assert len(data) == file.compressed_size, "Invalid size"
        if alg == 1:
            extracted = zlib.decompress(data, bufsize=file.size)
        elif alg == 2:
            assert (
                data[:4] == b"(\xb5/\xfd"
            ), "Expected zstd, but magic header doesn't match"
            extracted = zstandard.decompress(data, file.size)
        else:
            extracted = data

        if flag == 0 and type_ == 1:
            extracted = undo_cumulative_sum(extracted)

        elif (flag == 0 and type_ in (1, 2)) or (flag == 1 and type_ == 2):
            raise NotImplementedError(
                "Stream transform functions are not implemented yet."
                f"Flag {flag}, Type {type_}"
            )

        # Check checksum
        assert len(extracted) == file.size, "File size doesn't match"
        if zlib.crc32(extracted) != file.crc32:
            warnings.warn("Invalid checksum")

        return extracted

    def close(self):
        """Close the stream."""
        self.data.stream.close()
