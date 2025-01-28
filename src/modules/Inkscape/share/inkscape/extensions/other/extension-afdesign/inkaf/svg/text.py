#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>

# SPDX-License-Identifier: GPL-2.0-or-later


from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from ..parser.types import AFObject
from .curve import AFCurve
from .fill import AFColor, AFGradient, parse_fdsc
from .shape import AFRectangle, AFShape, parse_shape
from .styles import AFStroke
from .util import AFBoundingBox


class AFTextStretch(Enum):
    ULTRA_CONDENSED = 1
    EXTRA_CONDENSED = 2
    CONDENSED = 3
    SEMI_CONDENSED = 4
    NORMAL = 5
    SEMI_EXPANDED = 6
    EXPANDED = 7
    EXTRA_EXPANDED = 8
    ULTRA_EXPANDED = 9


@dataclass
class AFFont:
    family: str
    italic: bool
    pano: list[int]
    post: str  # post: "family-NarroBoldItalic"
    weight: int
    stretch: AFTextStretch

    @classmethod
    def from_af(cls, font: AFObject) -> AFFont:
        assert font.get_type() == "Font"
        return cls(
            post=font["Post"],
            family=font["Famy"],
            weight=font["Wegt"],
            italic=font["Ital"],
            stretch=AFTextStretch(font["Widh"]),
            pano=font["Pano"]["byte"],
        )


class AFParaAlign(Enum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2
    JUSTIFY_LEFT = 3
    JUSTIFY_CENTER = 4
    JUSTIFY_RIGHT = 5
    JUSTIFY_ALL = 6
    TOWARDS_SPLINE = 7
    AWAY_FROM_SPLINE = 8


class AFTextVAlign(Enum):
    TOP = 0
    CENTER = 1
    BOTTOM = 2
    JUSTIFY = 3


class AFTextLineStyle(Enum):
    NONE = 0
    SINGLE = 1
    DOUBLE = 2


class AFParaLeadingType(Enum):
    MULTIPLE = 0
    PERCENT_HEIGHT = 1
    EXACTLY = 2
    AT_LEAST = 3


@dataclass
class AFParaLeading:
    type: AFParaLeadingType
    value: float

    @classmethod
    def from_af(
        cls, type: AFParaLeadingType, multiple: float, exact: float
    ) -> AFParaLeading:
        return cls(
            type=type,
            value=multiple
            if type in [AFParaLeadingType.PERCENT_HEIGHT, AFParaLeadingType.MULTIPLE]
            else exact
            if type in [AFParaLeadingType.EXACTLY, AFParaLeadingType.AT_LEAST]
            else 0.0,
        )

    def get_line_height(self, font_size: float) -> float:
        if self.type in {AFParaLeadingType.PERCENT_HEIGHT, AFParaLeadingType.MULTIPLE}:
            return self.value * font_size
        if self.type == AFParaLeadingType.AT_LEAST:
            return max(self.value, font_size)
        return self.value


@dataclass
class AFParaAtt:
    index: int

    para_leading: AFParaLeading
    align: AFParaAlign

    @classmethod
    def from_af(cls, paar: AFObject) -> AFParaAtt:
        indx = paar["Indx"]
        item = paar["Item"]
        return AFParaAtt(
            index=indx,
            para_leading=AFParaLeading.from_af(
                AFParaLeadingType(item["Ints"][1]), item["Doub"][0], item["Doub"][1]
            ),
            align=AFParaAlign(item["Ints"][0]),
        )


@dataclass
class AFParaAtts:
    runs: List[AFParaAtt]

    @classmethod
    def from_af(cls, glas: AFObject) -> AFParaAtts:
        runs = []
        for run in glas["Runs"]:
            runs.append(AFParaAtt.from_af(run))
        return cls(runs)


@dataclass
class AFGlyphAtt:
    index: int
    font: AFFont
    rfnt: AFFont  # Unknown

    font_size: float
    fill: AFColor | AFGradient
    bg_fill: AFColor | AFGradient
    stroke_fill: AFColor | AFGradient
    stroke: AFStroke

    underline: AFTextLineStyle
    underline_fill: AFColor | AFGradient

    line_through: AFTextLineStyle
    line_through_fill: AFColor | AFGradient

    lang: str

    @classmethod
    def from_af(cls, glar: AFObject) -> AFGlyphAtt:
        indx = glar["Indx"]
        item = glar["Item"]
        return cls(
            index=indx,
            font=AFFont.from_af(item["DFnt"]),
            rfnt=AFFont.from_af(item["RFnt"]),
            font_size=item["Doub"][0],
            fill=parse_fdsc(item["Objs"][0]),
            bg_fill=parse_fdsc(item["Objs"][4]),
            stroke_fill=parse_fdsc(item["Objs"][1]),
            stroke=AFStroke.from_af(item["Objs"][2]),
            underline=AFTextLineStyle(item["Ints"][0]),
            line_through=AFTextLineStyle(item["Ints"][1]),
            underline_fill=parse_fdsc(item["Objs"][5]),
            line_through_fill=parse_fdsc(item["Objs"][6]),
            lang=item["Stri"][1],
            # optical_alignment=item["Objs"][8],
        )


@dataclass
class AFGlyphAtts:
    runs: List[AFGlyphAtt]

    @classmethod
    def from_af(cls, glas: AFObject) -> AFGlyphAtts:
        runs = []
        for run in glas["Runs"]:
            runs.append(AFGlyphAtt.from_af(run))
        return cls(runs)


class AFTextType(Enum):
    ARTISTIC = "TxtA"
    FRAMED = "TxtF"
    FOLLOW_CURVE = "CPTx"
    IN_SHAPE = "TxtS"
    IN_CURVE = "TxtC"


TEXT_TYPES = set(t.value for t in AFTextType)


@dataclass
class AFText:
    type: AFTextType

    glyphs: List[str]
    glyph_atts: List[AFGlyphAtts]
    para_atts: List[AFParaAtts]

    text_path: Optional[AFTextPath]
    shape_inside: AFShape | AFCurve

    # TODO: Unused fields
    colw: Optional[float] = None
    gutw: Optional[float] = None
    valign: AFTextVAlign = AFTextVAlign.TOP

    @classmethod
    def from_af(cls, child: AFObject) -> AFText:
        text_type = AFTextType(child.get_type())
        txth = child.get("TxtH")
        assert txth is not None or text_type == AFTextType.ARTISTIC, "Text info missing"

        b_box = (
            (txth.get("FrmB") if txth else None)
            or child.get("ShpB")
            or child.get("CvsB")
            or child.get("bbox")
        )
        assert b_box is not None, "Text bbox missing"

        shape_inside: AFShape | AFCurve
        if text_type == AFTextType.IN_SHAPE:
            shape_inside = parse_shape(child["Shpe"], child["ShpB"])
        elif text_type == AFTextType.IN_CURVE:
            shape_inside = AFCurve.from_af(child["Crvs"])
        else:
            shape_inside = AFRectangle(AFBoundingBox(*b_box))

        text_path = (
            AFTextPath.from_af(txth) if text_type == AFTextType.FOLLOW_CURVE else None
        )

        blocks = child["StSt"]["Blok"]
        return cls(
            type=text_type,
            glyphs=[block["Glyp"]["Utf8"] for block in blocks],
            glyph_atts=[AFGlyphAtts.from_af(block["GAtt"]) for block in blocks],
            para_atts=[AFParaAtts.from_af(block["PAtt"]) for block in blocks],
            text_path=text_path,
            shape_inside=shape_inside,
            colw=txth.get("ColW") if txth else None,
            gutw=txth.get("GutW") if txth else None,
            valign=AFTextVAlign(txth["Algn"].id)
            if txth and "Algn" in txth
            else AFTextVAlign.TOP,
        )


@dataclass
class AFTextPath:
    path: AFCurve
    starts: List[float]
    ends: List[float]
    reverses: List[bool]

    @classmethod
    def from_af(cls, txth: AFObject) -> AFTextPath:
        return cls(
            path=AFCurve.from_af(txth["PCrv"]),
            starts=txth["Strt"],
            ends=txth["Ends"],
            reverses=txth["Revr"],
        )
