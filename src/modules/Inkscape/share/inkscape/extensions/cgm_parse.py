#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (c) 2024 jonathan.neuhauser@outlook.com
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
"""
Parse binary CGM files
"""

from dataclasses import dataclass, fields, is_dataclass
from io import BufferedIOBase, BytesIO
import struct
from typing import (
    ClassVar,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    get_type_hints,
    get_origin,
    get_args,
)
import warnings
import cgm_enums
import inkex


class FunctionRegistry(dict):
    def register(self, key):
        def decorator(func):
            self[key] = func
            return func

        return decorator


class BinaryCGMCommandParser:
    type_registry: Dict[Tuple[int, int], Type] = {}
    unsigned_readers = FunctionRegistry()
    signed_readers = FunctionRegistry()
    real_readers = FunctionRegistry()
    readers = FunctionRegistry()
    sizers = FunctionRegistry()

    def __init__(self, data: Union[bytes, BufferedIOBase]):
        if isinstance(data, bytes):
            data = BytesIO(data)
        # The stream we currently operate on. For long form commands its
        # easier to temporarily exchange this reference
        self.stream = data
        # The main stream of the file
        self.outer_stream = data
        # Reader functions for basic data types, where precision can be changed
        # in the file.
        self.integer_precision = 16
        self.index_precision = 16
        self.real_type = cgm_enums.RealTypeEnum.FIXED_POINT
        self.real_precision = (16, 16)
        self.vdc_integer_precision = 16
        self.vdc_real_type = cgm_enums.RealTypeEnum.FIXED_POINT
        self.vdc_real_precision = (16, 16)
        self.float_precision = (9, 23)
        self.colour_component_precision = 8
        self.colour_index_precision = 8
        self.vdc_type = cgm_enums.VDCTypeEnum.INTEGER
        self.vdc_real_type = cgm_enums.RealTypeEnum.FIXED_POINT
        self.vdc_real_precision = (16, 16)
        self.colour_model = cgm_enums.ColourModelEnum.RGB
        self.colour_selection_mode = cgm_enums.ColourSelectionModeEnum.INDEXED
        self.line_width_specification_mode = cgm_enums.WidthSpecificationModeEnum.SCALED
        self.marker_size_specification_mode = (
            cgm_enums.WidthSpecificationModeEnum.SCALED
        )
        self.edge_width_specification_mode = cgm_enums.WidthSpecificationModeEnum.SCALED
        self.interior_style_specification_mode = (
            cgm_enums.WidthSpecificationModeEnum.ABSOLUTE
        )

    @staticmethod
    def register_target_datatype(cls):
        if cls.id is not None:
            BinaryCGMCommandParser.type_registry[cls.id] = cls

    def read(self, bytes):
        res = self.stream.read(bytes)
        if len(res) != bytes:
            raise ValueError("EOF")
        return res

    def read_padded(self, length):
        # An uneven length of a command is padded with a null byte
        if length % 2 == 1:
            arg_bytes = self.read(length + 1)
            assert arg_bytes[-1] == 0
            return arg_bytes[:-1]
        return self.read(length)

    @unsigned_readers.register(8)
    def read_u8(self) -> int:
        return int.from_bytes(self.read(1), byteorder="big")

    @unsigned_readers.register(16)
    def read_u16(self) -> int:
        return int.from_bytes(self.read(2), byteorder="big")

    @unsigned_readers.register(24)
    def read_u24(self) -> int:
        return int.from_bytes(self.read(3), byteorder="big")

    @unsigned_readers.register(32)
    def read_u32(self) -> int:
        return int.from_bytes(self.read(4), byteorder="big")

    @signed_readers.register(8)
    def read_i8(self) -> int:
        return int.from_bytes(self.read(1), byteorder="big", signed=True)

    @signed_readers.register(16)
    @readers.register("E")
    def read_i16(self) -> int:
        return int.from_bytes(self.read(2), byteorder="big", signed=True)

    @signed_readers.register(24)
    def read_i24(self) -> int:
        return int.from_bytes(self.read(3), byteorder="big", signed=True)

    @signed_readers.register(32)
    def read_i32(self) -> int:
        return int.from_bytes(self.read(4), byteorder="big", signed=True)

    @real_readers.register((cgm_enums.RealTypeEnum.FLOATING_POINT, 9, 23))
    def read_float(self) -> float:
        return struct.unpack(">f", self.read(4))[0]

    @real_readers.register((cgm_enums.RealTypeEnum.FLOATING_POINT, 12, 52))
    def read_double(self) -> float:
        return struct.unpack(">d", self.read(8))[0]

    @real_readers.register((cgm_enums.RealTypeEnum.FIXED_POINT, 16, 16))
    def read_fixed_single(self) -> float:
        # Some sample files appear to not be using
        # two's complement for signed integers if they occur in a flot.
        # IMO that's incorrect according to the specification.
        return self.read_i16() + self.read_u16() / 2**16

    @real_readers.register((cgm_enums.RealTypeEnum.FIXED_POINT, 32, 32))
    def read_fixed_double(self) -> float:
        return self.read_i32() + self.read_u32() / 2**32

    @readers.register("S")
    @readers.register("D")
    @readers.register("SF")
    def read_str(self) -> str:
        """The first byte indicates the size.
        If the size is 255, the first two bytes indicate the size.
        From the new size, the first bit is a continuation flag
        and the remaining 15 bits are the size"""
        data: bytes
        size = self.read_u8()
        if size != 0xFF:
            data = self.read(size)
        else:
            # Long-form string
            self.stream.seek(0)
            _data = bytearray()
            while True:
                cur_size = self.read_u16()
                length = cur_size & 0b0111111111111111
                _data.extend(self.read(length))
                if not cur_size & 0b1000000000000000:
                    break
            data = bytes(_data)
        # TODO implement proper string encoding
        return data.decode("latin-1")

    def get_single_value(self, type_str: Union[str, Tuple[str]]):
        if type_str in self.readers:
            return BinaryCGMCommandParser.readers[type_str](self)
        else:
            raise ValueError(f"Unknown data type {type_str}")

    def get_value(
        self,
        type_str: Union[str, Tuple[str, ...]],
        target_types: Union[type, Tuple[type]],
        length: Optional[int] = None,
    ):
        """This function reads a value from the stream.
        The result can either be:
         - a primitive type (e.g. "I", <type int> -> int)
         - a tuple of primitive types
           (e.g. ("I", "P"), (<type int>, <type Point>) -> (int, Point))
         - a dataclass
           (e.g. ("P", "E"), <type PolygonLineSetEntry> -> PolygonLineSetEntry)
           in this case the type_str applies to the fields of the dataclass,
           and the target types of those fields are inferred from the
           type hint of the dataclass field
         - a list of any of the previous
           (e.g. ("I", "R"), typing.List[<type int>, <type float>]
           -> List[Tuple[int, float]])
           length must be defined for lists
           This just calls get_value with the argument of the List typehint,
           and collects the result until we've read length bytes
        """
        res = None
        initial_pos = self.stream.tell()

        if isinstance(type_str, str) and isinstance(target_types, type):
            if target_types == str and length == 0:
                return ""
            res = self.get_single_value(type_str)
            if type_str not in ("P", "CO", "CD", "CI"):
                res = target_types(res)

        elif isinstance(type_str, tuple):
            if get_origin(target_types) == tuple:
                target_types = get_args(target_types)
            if isinstance(target_types, tuple):
                assert len(target_types) == len(type_str)
                res = tuple(
                    self.get_value(i, t) for t, i in zip(target_types, type_str)
                )

            elif is_dataclass(target_types):
                res = target_types(
                    *self.get_value(
                        type_str,
                        tuple(
                            get_type_hints(target_types)[t.name]
                            for t in fields(target_types)
                        ),
                    )
                )
        if res is None and get_origin(target_types) == list:
            assert length is not None
            target_type = get_args(target_types)[0]
            try:
                field_size = self.get_size(type_str)
                # Assert that the remaining bytes fit into the list without residue
                assert length % field_size == 0
            except ValueError:
                # just an assertion here, continue
                pass
            res = []
            while True:
                if (self.stream.tell() - initial_pos) >= length:
                    break
                res.append(self.get_value(type_str, target_type))

        assert res is not None, "invalid specification for get_value"
        # assert isinstance(res, target_types), "bad return type"
        return res

    @readers.register("IX")
    def read_index(self):
        return BinaryCGMCommandParser.signed_readers[self.index_precision](self)

    @readers.register("SI")
    @readers.register("I")
    def read_signed(self):
        return BinaryCGMCommandParser.signed_readers[self.integer_precision](self)

    @readers.register("VDC")
    def read_vdc(self):
        return (
            BinaryCGMCommandParser.signed_readers[self.vdc_integer_precision](self)
            if self.vdc_type == cgm_enums.VDCTypeEnum.INTEGER
            else BinaryCGMCommandParser.real_readers[
                (self.vdc_real_type, *self.vdc_real_precision)
            ](self)
        )

    @readers.register("R")
    def read_real(self):
        return BinaryCGMCommandParser.real_readers[
            (self.real_type, *self.real_precision)
        ](self)

    @readers.register("F")
    def read_floating(self):
        return BinaryCGMCommandParser.real_readers[
            (cgm_enums.RealTypeEnum.FLOATING_POINT, *self.float_precision)
        ](self)

    @readers.register("CI")
    def read_indexed_colour(self):
        return cgm_enums.IndexColour(
            self.signed_readers[self.colour_index_precision](self)
        )

    @readers.register("CCO")
    def read_colour_component(self):
        return BinaryCGMCommandParser.unsigned_readers[self.colour_component_precision](
            self
        )

    @readers.register("CD")
    def read_direct_colour(self):
        result = cgm_enums.DirectColour(
            *(
                self.read_colour_component()
                for _ in range(
                    4 if self.colour_model == cgm_enums.ColourModelEnum.CMYK else 3
                )
            )
        )
        result.colour_model = self.colour_model
        return result

    @readers.register("CO")
    def read_colour(self):
        if self.colour_selection_mode == cgm_enums.ColourSelectionModeEnum.DIRECT:
            return self.read_direct_colour()
        else:
            return self.read_indexed_colour()

    @readers.register("P")
    def read_point(self):
        return cgm_enums.Point(self.read_vdc(), self.read_vdc())

    def read_size(self, mode: cgm_enums.WidthSpecificationModeEnum):
        if mode == cgm_enums.WidthSpecificationModeEnum.ABSOLUTE:
            return self.read_vdc()
        return self.read_real()

    @readers.register("LSS")
    def read_line_size(self):
        return self.read_size(self.line_width_specification_mode)

    @readers.register("MSS")
    def read_marker_size(self):
        return self.read_size(self.marker_size_specification_mode)

    @readers.register("ESS")
    def read_edge_size(self):
        return self.read_size(self.edge_width_specification_mode)

    @readers.register("ISS")
    def read_interior_style_size(self):
        return self.read_size(self.interior_style_specification_mode)

    # SIZING FUNCTIONS

    def get_size(self, type_str: Union[str, Tuple[str, ...]]):
        if type_str in BinaryCGMCommandParser.sizers:
            return BinaryCGMCommandParser.sizers[type_str](self)
        if isinstance(type_str, tuple):
            return sum(self.get_size(i) for i in type_str)
        else:
            raise ValueError(f"No size know for type {type_str}")

    @sizers.register("CI")
    def ci_size(self):
        return self.colour_index_precision // 8

    @sizers.register("CCO")
    def cco_size(self):
        return self.colour_component_precision // 8

    @sizers.register("CD")
    def cd_size(self):
        return self.cco_size() * (
            4 if self.colour_model == cgm_enums.ColourModelEnum.CMYK else 3
        )

    @sizers.register("IX")
    def ix_size(self):
        return self.index_precision // 8

    @sizers.register("E")
    def e_size(self):
        return 2

    @sizers.register("I")
    def i_size(self):
        return self.integer_precision // 8

    @sizers.register("R")
    def r_size(self):
        return (self.real_precision[0] + self.real_precision[1]) // 8

    @sizers.register("VDC")
    def vdc_size(self):
        return (
            self.vdc_integer_precision // 8
            if self.vdc_type == cgm_enums.VDCTypeEnum.INTEGER
            else (self.vdc_real_precision[0] + self.vdc_real_precision[1]) // 8
        )

    @sizers.register("P")
    def p_size(self):
        return 2 * self.vdc_size()

    @sizers.register("CO")
    def co_size(self):
        if self.colour_selection_mode == cgm_enums.ColourSelectionModeEnum.DIRECT:
            return self.cd_size()
        else:
            return self.ci_size()

    def ss_size(self, mode: cgm_enums.WidthSpecificationModeEnum):
        if mode == cgm_enums.WidthSpecificationModeEnum.ABSOLUTE:
            return self.vdc_size()
        return self.r_size()

    @sizers.register("LSS")
    def lss_size(self):
        return self.ss_size(self.line_width_specification_mode)

    @sizers.register("MSS")
    def marker_size(self):
        return self.ss_size(self.marker_size_specification_mode)

    @sizers.register("ESS")
    def edge_size(self):
        return self.ss_size(self.edge_width_specification_mode)

    @sizers.register("ISS")
    def interior_style_size(self):
        return self.ss_size(self.interior_style_specification_mode)

    def parse(self):
        while True:
            try:
                header = self.read_u16()
            except ValueError:
                return
            clss = header >> 12
            obj_id = (header & 0b0000111111100000) >> 5
            total_length = header & 0x1F

            if total_length == 31:
                # Long-form header
                args = bytearray()
                total_length = 0
                while True:
                    data = self.read_u16()
                    length = data & 0b0111111111111111
                    total_length += length
                    args.extend(self.read_padded(length))
                    if not data & 0b1000000000000000:
                        break
                self.stream = BytesIO(bytes(args))

            old_pos = self.stream.tell()
            interpreted = self.command_factory(clss, obj_id, total_length)
            new_pos = self.stream.tell()
            if (
                new_pos - old_pos not in [total_length] + [total_length - 1]
                if total_length % 2 == 0
                else []
            ):
                warnings.warn(
                    f"{interpreted.__class__.__name__}: Expected to read {total_length} bytes, but read {new_pos - old_pos}"
                )
            new_pos = old_pos + total_length
            self.stream.seek(new_pos)
            if isinstance(interpreted, ParserModifierCommand):
                self.update_readers(interpreted)

            # Prepare the stream for the next entry
            if self.stream == self.outer_stream:
                if new_pos % 2 != 0:
                    # Fields are always aligned with 2-byte words
                    self.read(1)
            else:
                self.stream = self.outer_stream

            yield interpreted

            if isinstance(interpreted, EndMetafile):
                # Sometimes there are trailing characters afterwards, return
                return

    def parse_data(self, data: BytesIO):
        """Temporarily exchanges the stream by data to read primitives from it,
        using the same settings as the current stream"""
        outer_stream = self.outer_stream
        stream = self.stream

        self.outer_stream = data
        self.stream = data
        result = tuple(self.parse())

        self.outer_stream = outer_stream
        self.stream = stream

        return result

    def update_readers(self, interpreted):
        if isinstance(interpreted, VdcType):
            self.vdc_type = interpreted.vdc_type
        elif isinstance(interpreted, IntegerPrecision):
            self.integer_precision = interpreted.integer_precision
        elif isinstance(interpreted, RealPrecision):
            self.real_type = interpreted.representation
            self.real_precision = (
                interpreted.exponent_whole_size,
                interpreted.fraction_size,
            )
            if interpreted.representation == cgm_enums.RealTypeEnum.FLOATING_POINT:
                self.float_precision = (
                    interpreted.exponent_whole_size,
                    interpreted.fraction_size,
                )
        elif isinstance(interpreted, IndexPrecision):
            self.index_precision = interpreted.index_precision
        elif isinstance(interpreted, ColourIndexPrecision):
            self.colour_index_precision = interpreted.colour_index_precision
        elif isinstance(interpreted, ColourPrecision):
            self.colour_component_precision = interpreted.colour_precision
        elif isinstance(interpreted, ColourSelectionMode):
            self.colour_selection_mode = interpreted.colour_selection_mode
        elif isinstance(interpreted, ColourModel):
            self.colour_model = interpreted.colour_model
        elif isinstance(interpreted, VDCIntegerPrecision):
            self.vdc_integer_precision = interpreted.integer_precision
        elif isinstance(interpreted, VDCRealPrecision):
            self.vdc_real_type = interpreted.representation
            self.vdc_real_precision = (
                interpreted.exponent_whole_size,
                interpreted.fraction_size,
            )
        elif isinstance(interpreted, LineWidthSpecificationMode):
            self.line_width_specification_mode = interpreted.size_specification
        elif isinstance(interpreted, EdgeWidthSpecificationMode):
            self.edge_width_specification_mode = interpreted.size_specification
        elif isinstance(interpreted, MarkerSizeSpecificationMode):
            self.marker_size_specification_mode = interpreted.size_specification
        elif isinstance(interpreted, InteriorStyleSpecificationMode):
            self.interior_style_specification_mode = interpreted.size_specification
        else:
            inkex.errormsg(
                f"Parser modifier command {interpreted} without associated action"
            )

    def command_factory(self, group, command, length):
        cls = self.type_registry.get((group, command), UnknownCommand)
        result = cls.parse_binary(self, length)
        if isinstance(result, UnknownCommand):
            result.id = (group, command)
        return result


@dataclass
class CGMCommand:
    id: ClassVar[Tuple[int, int]] = (0, 0)
    binary_params: ClassVar[Tuple[Union[str, Tuple[str, ...]], ...]] = tuple()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BinaryCGMCommandParser.register_target_datatype(cls)

    @classmethod
    def get_binary_args(
        cls,
        stream: BinaryCGMCommandParser,
        length: int,
    ):
        initial_pos = stream.stream.tell()
        for i, (field, types) in enumerate(zip(fields(cls), cls.binary_params)):
            outer_type = get_type_hints(cls)[field.name]
            yield stream.get_value(
                types, outer_type, length - (stream.stream.tell() - initial_pos)
            )

    @classmethod
    def parse_binary(cls, stream: BinaryCGMCommandParser, length):
        args = list(cls.get_binary_args(stream, length))
        return cls(*args)


6


@dataclass
class NoOp(CGMCommand):
    id = (0, 0)
    data: bytes

    @classmethod
    def parse_binary(cls, stream: BinaryCGMCommandParser, length):
        return cls(stream.read(length))


@dataclass
class UnknownCommand(CGMCommand):
    data: bytes

    @classmethod
    def parse_binary(cls, stream: BinaryCGMCommandParser, length):
        return cls(stream.read(length))


@dataclass
class BeginMetafile(CGMCommand):
    id = (0, 1)
    binary_params = ("SF",)
    name: str


@dataclass
class EndMetafile(CGMCommand):
    id = (0, 2)


@dataclass
class BeginPicture(CGMCommand):
    id = (0, 3)
    binary_params = ("SF",)
    name: str


@dataclass
class BeginPictureBody(CGMCommand):
    id = (0, 4)


@dataclass
class EndPicture(CGMCommand):
    id = (0, 5)


# Metafile descriptor elements


@dataclass
class MetafileVersion(CGMCommand):
    id = (1, 1)
    binary_params = ("I",)
    version: int


@dataclass
class MetafileDescription(CGMCommand):
    id = (1, 2)
    binary_params = ("SF",)
    description: str


class ParserModifierCommand(CGMCommand):
    pass


@dataclass
class VdcType(ParserModifierCommand):
    id = (1, 3)
    binary_params = ("E",)
    vdc_type: cgm_enums.VDCTypeEnum


@dataclass
class IntegerPrecision(ParserModifierCommand):
    id = (1, 4)
    binary_params = ("I",)
    integer_precision: int


@dataclass
class RealPrecision(ParserModifierCommand):
    id = (1, 5)
    binary_params = "E", "I", "I"
    representation: cgm_enums.RealTypeEnum
    exponent_whole_size: int
    fraction_size: int


@dataclass
class IndexPrecision(ParserModifierCommand):
    id = (1, 6)
    binary_params = ("I",)
    index_precision: int


@dataclass
class ColourPrecision(ParserModifierCommand):
    id = (1, 7)
    binary_params = ("I",)
    colour_precision: int


@dataclass
class ColourIndexPrecision(ParserModifierCommand):
    id = (1, 8)
    binary_params = ("I",)
    colour_index_precision: int


@dataclass
class MaximumColourIndex(CGMCommand):
    id = (1, 9)
    binary_params = ("CI",)
    maximum_colour_index: cgm_enums.IndexColour


@dataclass
class ColourValueExtent(CGMCommand):
    id = (1, 10)

    minimum: Optional[int]
    maximum: Optional[int]

    first_component: Optional[Tuple[float, float]]
    second_component: Optional[Tuple[float, float]]
    third_component: Optional[Tuple[float, float]]

    @classmethod
    def get_binary_args(cls, stream: BinaryCGMCommandParser, length):
        if stream.colour_model in (
            cgm_enums.ColourModelEnum.CMYK,
            cgm_enums.ColourModelEnum.RGB,
        ):
            return stream.read_direct_colour(), stream.read_direct_colour(), 0, 0, 0
        else:
            return 0, 0, stream.read_real(), stream.read_real(), stream.read_real()


@dataclass
class MetafileElementList(CGMCommand):
    id = (1, 11)
    elements: List[Tuple[int, int]]

    @classmethod
    def get_binary_args(cls, stream: BinaryCGMCommandParser, length: int):
        num = stream.read_signed()
        yield [(stream.read_index(), stream.read_index()) for _ in range(num)]


@dataclass
class MetafileDefaultsReplacement(CGMCommand):
    id = (1, 12)
    data: List[CGMCommand]

    @classmethod
    def get_binary_args(cls, stream: BinaryCGMCommandParser, length: int):
        data = stream.read(length)

        yield stream.parse_data(BytesIO(data))


@dataclass
class FontList(CGMCommand):
    id = (1, 13)
    binary_params = ("SF",)

    fonts: List[str]


@dataclass
class CharacterSetList(CGMCommand):
    id = (1, 14)
    binary_params = (("E", "SF"),)

    specification: List[Tuple[cgm_enums.CharacterSetTypeEnum, str]]


@dataclass
class CharacterCodingAnnouncer(CGMCommand):
    id = (1, 15)
    binary_params = ("E",)

    encoding: cgm_enums.CharacterCodingEnum


@dataclass
class MaximumVDCExtent(CGMCommand):
    id = (1, 17)
    binary_params = "P", "P"

    first_corner: cgm_enums.Point
    second_corner: cgm_enums.Point


@dataclass
class ColourModel(ParserModifierCommand):
    id = (1, 19)
    binary_params = ("IX",)

    colour_model: cgm_enums.ColourModelEnum


@dataclass
class ScalingMode(CGMCommand):
    id = (2, 1)
    binary_params = "E", "F"

    scaling_mode: cgm_enums.ScalingModeEnum
    metric_scaling_factor: float


@dataclass
class ColourSelectionMode(ParserModifierCommand):
    id = (2, 2)
    binary_params = ("E",)

    colour_selection_mode: cgm_enums.ColourSelectionModeEnum


@dataclass
class LineWidthSpecificationMode(ParserModifierCommand):
    id = (2, 3)
    binary_params = ("E",)

    size_specification: cgm_enums.WidthSpecificationModeEnum


@dataclass
class MarkerSizeSpecificationMode(ParserModifierCommand):
    id = (2, 4)

    binary_params = ("E",)
    size_specification: cgm_enums.WidthSpecificationModeEnum


@dataclass
class EdgeWidthSpecificationMode(ParserModifierCommand):
    id = (2, 5)

    binary_params = ("E",)
    size_specification: cgm_enums.WidthSpecificationModeEnum


@dataclass
class VDCExtent(CGMCommand):
    id = (2, 6)
    binary_params = "P", "P"

    first_corner: cgm_enums.Point
    second_corner: cgm_enums.Point


@dataclass
class BackgroundColour(CGMCommand):
    id = (2, 7)
    binary_params = ("CD",)

    colour: cgm_enums.DirectColour


@dataclass
class InteriorStyleSpecificationMode(ParserModifierCommand):
    id = (2, 16)

    binary_params = ("E",)
    size_specification: cgm_enums.WidthSpecificationModeEnum


@dataclass
class VDCIntegerPrecision(ParserModifierCommand):
    id = (3, 1)
    binary_params = ("I",)
    integer_precision: int


@dataclass
class VDCRealPrecision(ParserModifierCommand):
    id = (3, 2)
    binary_params = "E", "I", "I"
    representation: cgm_enums.RealTypeEnum
    exponent_whole_size: int
    fraction_size: int


@dataclass
class Transparency(CGMCommand):
    id = (3, 4)
    binary_params = ("E",)
    indicator: cgm_enums.TransparencyEnum


@dataclass
class ClipRectangle(CGMCommand):
    id = (3, 5)
    binary_params = ("P", "P")
    p1: cgm_enums.Point
    p2: cgm_enums.Point


@dataclass
class ClipIndicator(CGMCommand):
    id = (3, 6)
    binary_params = ("E",)
    clip: cgm_enums.ClipIndicatorEnum


@dataclass
class Polyline(CGMCommand):
    id = (4, 1)
    binary_params = ("P",)
    points: List[cgm_enums.Point]


@dataclass
class DisjointPolyline(CGMCommand):
    id = (4, 2)
    binary_params = ("P",)
    points: List[cgm_enums.Point]


@dataclass
class Polymarker(CGMCommand):
    id = (4, 3)
    binary_params = ("P",)
    points: List[cgm_enums.Point]


@dataclass
class Text(CGMCommand):
    id = (4, 4)
    binary_params = ("P", "E", "S")
    point: cgm_enums.Point
    flag: cgm_enums.TextFinalFlag
    string: str


@dataclass
class RestrictedText(CGMCommand):
    id = (4, 5)
    binary_params = ("VDC", "VDC", "P", "E", "S")
    width: float
    height: float
    point: cgm_enums.Point
    flag: cgm_enums.TextFinalFlag
    string: str


@dataclass
class AppendText(CGMCommand):
    id = (4, 6)
    binary_params = ("E", "S")
    flag: cgm_enums.TextFinalFlag
    string: str


@dataclass
class Polygon(CGMCommand):
    id = (4, 7)
    binary_params = ("P",)
    points: List[cgm_enums.Point]


@dataclass
class PolygonSet(CGMCommand):
    id = (4, 8)
    points: List[cgm_enums.PolygonSetEntry]
    binary_params = (("P", "E"),)


# TODO: Cell array (complicated parsing with sub-byte values)


@dataclass
class GeneralizedDrawingPrimitive(CGMCommand):
    id = (4, 10)
    identifier: int
    points: List[cgm_enums.Point]
    data: bytes

    @classmethod
    def get_binary_args(cls, stream: BinaryCGMCommandParser, length: int):
        yield stream.read_signed()
        num = stream.read_signed()
        points = [stream.read_point() for _ in range(num)]
        yield points
        read = stream.i_size() * 2 + num * stream.p_size()
        yield stream.read(length - read)


@dataclass
class Rectangle(CGMCommand):
    id = (4, 11)
    binary_params = ("P", "P")
    p1: cgm_enums.Point
    p2: cgm_enums.Point


@dataclass
class Circle(CGMCommand):
    id = (4, 12)
    binary_params = ("P", "VDC")
    center: cgm_enums.Point
    radius: float


@dataclass
class CircularArc3Point(CGMCommand):
    id = (4, 13)
    binary_params = ("P", "P", "P")
    p1: cgm_enums.Point
    p2: cgm_enums.Point
    p3: cgm_enums.Point


@dataclass
class CircularArc3PointClose(CircularArc3Point):
    id = (4, 14)
    binary_params = ("P", "P", "P", "E")  # type: ignore
    closure: cgm_enums.ArcClosureEnum


@dataclass
class CircularArcCentre(CGMCommand):
    id = (4, 15)
    binary_params = ("P", "VDC", "VDC", "VDC", "VDC", "VDC")  # type: ignore
    centre: cgm_enums.Point
    delta_x_start: float
    delta_y_start: float
    delta_x_end: float
    delta_y_end: float
    radius: float


@dataclass
class CircularArcCentreClose(CircularArcCentre):
    id = (4, 16)
    binary_params = ("P", "VDC", "VDC", "VDC", "VDC", "VDC", "E")  # type: ignore
    closure: cgm_enums.ArcClosureEnum


@dataclass
class Ellipse(CGMCommand):
    id = (4, 17)
    binary_params = ("P", "P", "P")
    center: cgm_enums.Point
    point_1: cgm_enums.Point
    point_2: cgm_enums.Point


@dataclass
class EllipticalArc(Ellipse):
    id = (4, 18)
    binary_params = ("P", "P", "P", "VDC", "VDC", "VDC", "VDC")  # type: ignore
    delta_x_start: float
    delta_y_start: float
    delta_x_end: float
    delta_y_end: float


@dataclass
class EllipticalArcClose(EllipticalArc):
    id = (4, 19)
    binary_params = ("P", "P", "P", "VDC", "VDC", "VDC", "VDC", "E")  # type: ignore
    closure: cgm_enums.ArcClosureEnum


@dataclass
class Polybezier(CGMCommand):
    id = (4, 26)
    binary_params = ("E", "P")
    continuous: cgm_enums.PolybezierContinuityEnum
    points: List[cgm_enums.Point]


@dataclass
class LineType(CGMCommand):
    id = (5, 2)
    binary_params = ("IX",)
    type: cgm_enums.LineTypeEnum


@dataclass
class LineWidth(CGMCommand):
    id = (5, 3)
    binary_params = ("LSS",)
    width: float


@dataclass
class LineColour(CGMCommand):
    id = (5, 4)
    binary_params = ("CO",)
    colour: cgm_enums.Colour


@dataclass
class MarkerType(CGMCommand):
    id = (5, 6)
    binary_params = ("E",)
    type: cgm_enums.MarkerTypeEnum


@dataclass
class MarkerSize(CGMCommand):
    id = (5, 7)
    binary_params = ("MSS",)
    size: float


@dataclass
class MarkerColour(CGMCommand):
    id = (5, 8)
    binary_params = ("CO",)
    colour: cgm_enums.Colour


@dataclass
class TextFontIndex(CGMCommand):
    id = (5, 10)
    binary_params = ("IX",)
    index: int


@dataclass
class TextPrecision(CGMCommand):
    id = (5, 11)
    binary_params = ("E",)
    text_precision: cgm_enums.TextPrecisionEnum


@dataclass
class CharacterExpansionFactor(CGMCommand):
    id = (5, 12)
    binary_params = ("R",)
    factor: float


@dataclass
class CharacterSpacing(CGMCommand):
    id = (5, 13)
    binary_params = ("R",)
    spacing: float


@dataclass
class TextColour(CGMCommand):
    id = (5, 14)
    binary_params = ("CO",)
    colour: cgm_enums.Colour


@dataclass
class CharacterHeight(CGMCommand):
    id = (5, 15)
    binary_params = ("VDC",)
    height: float


@dataclass
class CharacterOrientation(CGMCommand):
    id = (5, 16)
    binary_params = ("VDC", "VDC", "VDC", "VDC")
    x_character_up: float
    y_character_up: float
    x_character_base: float
    y_character_base: float


@dataclass
class TextPath(CGMCommand):
    id = (5, 17)
    binary_params = ("E",)
    path: cgm_enums.TextPathEnum


@dataclass
class TextAlignment(CGMCommand):
    id = (5, 18)
    binary_params = ("E", "E", "R", "R")

    horizontal_alignment: cgm_enums.TextHorizontalAlignmentEnum
    vertical_alignment: cgm_enums.TextVerticalAlignmentEnum
    continous_horizontal_alignment: float
    continous_vertical_alignment: float


@dataclass
class CharacterSetIndex(CGMCommand):
    id = (5, 19)
    binary_params = ("IX",)

    index: int


@dataclass
class AlternateCharacterSetIndex(CGMCommand):
    id = (5, 20)
    binary_params = ("IX",)

    index: int


@dataclass
class InteriorStyle(CGMCommand):
    id = (5, 22)
    binary_params = ("E",)

    interior_style: cgm_enums.InteriorStyleEnum


@dataclass
class FillColour(CGMCommand):
    id = (5, 23)
    binary_params = ("CO",)

    fill: cgm_enums.Colour


@dataclass
class HatchIndex(CGMCommand):
    id = (5, 24)
    binary_params = ("IX",)
    index: int


@dataclass
class PatternIndex(CGMCommand):
    id = (5, 25)
    binary_params = ("IX",)
    index: int


@dataclass
class EdgeType(CGMCommand):
    id = (5, 27)
    binary_params = ("IX",)
    type: cgm_enums.LineTypeEnum


@dataclass
class EdgeWidth(CGMCommand):
    id = (5, 28)
    binary_params = ("ESS",)
    width: float


@dataclass
class EdgeColour(CGMCommand):
    id = (5, 29)
    binary_params = ("CO",)
    colour: cgm_enums.Colour


@dataclass
class EdgeVisibility(CGMCommand):
    id = (5, 30)
    binary_params = ("E",)
    visibility: cgm_enums.EdgeVisibilityEnum


@dataclass
class ColourTable(CGMCommand):
    id = (5, 34)
    binary_params = ("CI", "CD")

    colour_index: cgm_enums.IndexColour
    colours: List[cgm_enums.DirectColour]


@dataclass
class AspectSourceFlags(CGMCommand):
    id = (5, 35)
    binary_params = (("E", "E"),)
    flags: List[Tuple[cgm_enums.ASFTypeEnum, cgm_enums.ASFValue]]


@dataclass
class LineCap(CGMCommand):
    id = (5, 37)
    binary_params = ("E", "E")
    cap: cgm_enums.CapIndicatorEnum
    dash_cap: cgm_enums.DashCapIndicatorEnum


@dataclass
class RestrictedTextType(CGMCommand):
    id = (5, 42)
    binary_params = ("E",)
    type: cgm_enums.RestrictionTypeEnum


@dataclass
class ApplicationData(CGMCommand):
    id = (7, 2)
    binary_params = ("I", "SF")

    identifier: int
    data: str
