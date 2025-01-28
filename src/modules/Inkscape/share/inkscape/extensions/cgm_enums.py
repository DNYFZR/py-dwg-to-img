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
Enums and data structures for CGM files
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

Enum.__repr__ = lambda self: self.__class__.__name__ + "." + self.name  # type: ignore


class RealTypeEnum(Enum):
    FLOATING_POINT = 0
    FIXED_POINT = 1


class ScalingModeEnum(Enum):
    ABSTRACT = 0
    METRIC = 1


class VDCTypeEnum(Enum):
    INTEGER = 0
    REAL = 1


class ColourSelectionModeEnum(Enum):
    INDEXED = 0
    DIRECT = 1


class WidthSpecificationModeEnum(Enum):
    ABSOLUTE = 0
    SCALED = 1
    FRACTIONAL = 2
    MM = 3


class InteriorStyleEnum(Enum):
    HOLLOW = 0
    SOLID = 1
    PATTERN = 2
    HATCH = 3
    EMPTY = 4
    GEOMETRIC_PATTERN = 5
    INTERPOLATED = 6


class ColourModelEnum(Enum):
    RGB = 1
    CIELAB = 2
    CIELUV = 3
    CMYK = 4
    RGB_RELATED = 5


@dataclass
class Point:
    x: Union[float, int]
    y: Union[float, int]

    def __complex__(self):
        return self.x + self.y * 1j


class Colour:
    pass


@dataclass
class DirectColour(Colour):
    v1: int
    v2: int
    v3: int
    v4: Optional[int] = field(default=0)
    colour_model: ColourModelEnum = field(default=ColourModelEnum.RGB, init=False)


@dataclass
class IndexColour(Colour):
    index: int


class PolygonSetLineTypeEnum(Enum):
    INVISIBLE = 0
    VISIBLE = 1
    CLOSE_INVISIBLE = 2
    CLOSE_VISIBLE = 3


@dataclass
class PolygonSetEntry:
    pt: Point
    linetype: PolygonSetLineTypeEnum


class ClipIndicatorEnum(Enum):
    OFF = 0
    ON = 1


class TextPrecisionEnum(Enum):
    STRING = 0
    CHARACTER = 1
    STROKE = 2


class TextFinalFlag(Enum):
    NOT_FINAL = 0
    FINAL = 1


class TextHorizontalAlignmentEnum(Enum):
    NORMAL_HORIZONTAL = 0
    LEFT = 1
    CENTER = 2
    RIGHT = 3
    CONTINUOUS_HORIZONTAL = 4


class TextVerticalAlignmentEnum(Enum):
    NORMAL_VERTICAL = 0
    TOP = 1
    CAP = 2
    HALF = 3
    BASE = 4
    BOTTOM = 5
    CONTINUOUS_VERTICAL = 6


class TextPathEnum(Enum):
    RIGHT = 0
    LEFT = 1
    UP = 2
    DOWN = 3


class LineTypeEnum(Enum):
    SOLID = 1
    DASH = 2
    DOT = 3
    DASH_DOT = 4
    DASH_DOT_DOT = 5
    PRIVATE = -1

    @classmethod
    def _missing_(cls, value):
        return cls.PRIVATE


class EdgeVisibilityEnum(Enum):
    OFF = 0
    ON = 1


class CharacterSetTypeEnum(Enum):
    G_SET_94 = 0
    G_SET_96 = 1
    MULTIBYTE_G_SET_94 = 2
    MULTIBYTE_G_SET_96 = 3
    COMPLETE = 4


class CharacterCodingEnum(Enum):
    BASIC_7BIT = 0
    BASIC_8BIT = 1
    EXTENDED_7BIT = 2
    EXTENDED_8BIT = 3


class ArcClosureEnum(Enum):
    PIE = 0
    CHORD = 1


class TransparencyEnum(Enum):
    OFF = 0
    ON = 1


class ASFTypeEnum(Enum):
    LINE_TYPE_ASF = 0
    LINE_WIDTH_ASF = 1
    LINE_COLOUR_ASF = 2
    MARKER_TYPE_ASF = 3
    MARKER_SIZE_ASF = 4
    MARKER_COLOUR_ASF = 5
    TEXT_FONT_INDEX_ASF = 6
    TEXT_PRECISION_ASF = 7
    CHARACTER_EXPANSION_FACTOR_ASF = 8
    CHARACTER_SPACING_ASF = 9
    TEXT_COLOUR_ASF = 10
    INTERIOR_STYLE_ASF = 11
    FILL_COLOUR_ASF = 12
    HATCH_INDEX_ASF = 13
    PATTERN_INDEX_ASF = 14
    EDGE_TYPE_ASF = 15
    EDGE_WIDTH_ASF = 16
    EDGE_COLOUR_ASF = 17


class ASFValue(Enum):
    INDIVIDUAL = 0
    BUNDLED = 1


class MarkerTypeEnum(Enum):
    DOT = 1
    PLUS = 2
    ASTERISK = 3
    CIRCLE = 4
    CROSS = 5
    PRIVATE = -1

    @classmethod
    def _missing_(cls, value):
        return cls.PRIVATE


class PolybezierContinuityEnum(Enum):
    DISCONTINUOUS = 1
    CONTINUOUS = 2


class CapIndicatorEnum(Enum):
    UNSPECIFIED = 1
    BUTT = 2
    ROUND = 3
    PROJECTING_SQUARE = 4
    TRIANGLE = 5


class DashCapIndicatorEnum(Enum):
    UNSPECIFIED = 1
    BUTT = 2
    MATCH = 3


class RestrictionTypeEnum(Enum):
    BASIC = 1
    BOXED_CAP = 2
    BOXED_ALL = 3
    ISOTROPIC_CAP = 4
    ISOTROPIC_ALL = 5
    JUSTIFIED = 6
