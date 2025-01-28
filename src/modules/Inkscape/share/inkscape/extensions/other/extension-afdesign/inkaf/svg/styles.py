#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import itertools
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Union

import inkex

from ..parser.types import AFObject
from .curve import AFCurve
from .fill import AFColor, AFColorSpace, AFGradient, parse_bfil, parse_fdsc


class AFBlendModeV0(Enum):
    NORMAL = 0
    DARKEN = 1
    MULTIPLY = 2
    COLOR_BURN = 3
    LIGHTEN = 4
    SCREEN = 5
    COLOR_DODGE = 6
    ADD = 7
    OVERLAY = 8
    SOFT_LIGHT = 9
    HARD_LIGHT = 10
    VIVID_LIGHT = 11
    PIN_LIGHT = 12
    HARD_MIX = 13
    DIFFERENCE = 14
    EXCLUSION = 15
    SUBTRACT = 16
    HUE = 17
    SATURATION = 18
    LUMINOSITY = 19
    COLOR = 20
    AVERAGE = 21
    NEGATION = 22
    REFLECT = 23
    GLOW = 24
    ERASE = 25


class AFBlendModeV1(Enum):
    DARKER_COLOR = 2
    LIGHTER_COLOR = 6
    LINEAR_LIGHT = 15


class AFBlendModeV2(Enum):
    CONTRAST_NEGATE = 28


class AFBlendModeV3(Enum):
    LINEAR_BURN = 5


class AFBlendModeV4(Enum):
    DIVIDE = 21


AF_BLEND_MODES = {
    0: AFBlendModeV0,
    1: AFBlendModeV1,
    2: AFBlendModeV2,
    3: AFBlendModeV3,
    4: AFBlendModeV4,
}

SVG_BLEND_MODES = {
    "normal",
    "multiply",
    "screen",
    "overlay",
    "darken",
    "lighten",
    "color-dodge",
    "color-burn",
    "hard-light",
    "soft-light",
    "difference",
    "exclusion",
    "hue",
    "saturation",
    "color",
    "luminosity",
    "plus-darker",
    "plus-lighter",
}


class AFStrokeType(Enum):
    NONE = 0
    SOLID = 1
    DASHED = 2
    TEXTURED = 3


class AFStrokeCap(Enum):
    BUTT = 0
    SQUARE = 1
    ROUND = 2


class AFStrokeJoin(Enum):
    NONE = 0  # Unknown
    MITER = 1
    ROUND = 2
    BEVEL = 3


class AFStrokeAlign(Enum):
    CENTER = 0
    INSIDE = 1
    OUTSIDE = 2


class AFStrokeOrder(Enum):
    FRONT = False
    BEHIND = True


@dataclass
class AFStroke:
    width: float
    style: AFStrokeType
    cap: AFStrokeCap
    join: AFStrokeJoin
    order: AFStrokeOrder
    align: AFStrokeAlign
    miter_clip: float
    dash_pattern: List[float]
    width_curve: Optional[AFCurve] = None

    def __post_init__(self):
        if self.width_curve and not self.width_curve.curves:
            self.width_curve = None

        # Width remains constant for DASHED strokes
        if self.width_curve and self.style not in [
            AFStrokeType.SOLID,
            AFStrokeType.TEXTURED,
        ]:
            multiplier = max(
                self.width_curve.curves[1], key=lambda node: node.point[1]
            ).point[1]
            self.width *= multiplier
            self.width_curve = None

    @classmethod
    def from_af(cls, liln: AFObject):
        assert liln.get_type() == "LDsc"
        return cls(
            width=float(liln["LDeL"]["Wght"]),
            cap=AFStrokeCap(liln["LDeL"]["Data"].unsigned_ints[0]),
            join=AFStrokeJoin(liln["LDeL"]["Data"].unsigned_ints[1]),
            style=AFStrokeType(liln["LDeL"]["Data"].unsigned_ints[2]),
            miter_clip=float(liln["LDeL"]["Data"].doubles),
            dash_pattern=liln["LDeL"].get("Patn", [1, 1, 0, 0, 0, 0]),
            order=AFStrokeOrder(liln["LDBe"]),
            align=AFStrokeAlign(liln["LDSa"]),
            width_curve=(
                AFCurve.from_af(liln["LDeP"]) if "Data" in liln["LDeP"] else None
            ),
            # TODO
            # liln["LIAh"],
            # liln["LDSc"],
            # liln["LDeL"]["Brus"],
            # liln["LDeL"]["DBal"],
        )

    def get_power_stroke(self, svg: inkex.ShapeElement) -> Optional[inkex.PathEffect]:
        if self.width_curve is None:
            return None
        path = svg.path
        locations = [i.point[0] for i in self.width_curve.curves[0]]
        # Get local lengths
        subpaths = path.break_apart()
        start_indices = [0] + list(itertools.accumulate(len(s) for s in subpaths))
        moves = 0
        resulting_offsets: List[Tuple[float, float]] = []
        for start_index, subpath in zip(start_indices, subpaths):
            # the same width curve is applied to all subpaths
            lengths = [
                command.length() if command.letter not in "Mm" else 0
                for command in subpath.proxy_iterator()
            ]
            cumulative_lengths = list(itertools.accumulate(lengths))
            total_length = cumulative_lengths[-1]
            result = {}
            moves += 1
            for (_, l1), ((i, p2), l2) in inkex.utils.pairwise(
                zip(enumerate(subpath.proxy_iterator()), cumulative_lengths),
                start=False,
            ):
                if l2 - l1 == 0:
                    moves += 1
                for location in locations:
                    if l1 <= location * total_length <= l2 and location not in result:
                        # On the current segment and not processed yet
                        # Coordinates are specified as
                        # no. visible segment + local path coordinate
                        result[location] = (start_index + i - moves) + p2.ilength(
                            location * total_length - l1
                        )
            resulting_offsets.extend(
                (result[point.point[0]], abs(point.point[1]))
                for point in self.width_curve.curves[0]
                if point.index == 0
            )
        width = float(svg.style("stroke-width"))

        offset_pts = " | ".join(
            f"{location:.6f},{offset * width / 2:.6f}"
            for location, offset in resulting_offsets
        )

        assert len(self.width_curve.curves) == 1, "Invalid width curve"

        svg.set("inkscape:original-d", str(svg.path))
        return inkex.PathEffect.new(
            effect="powerstroke",
            is_visible="true",
            lpeversion="1.3",
            scale_width="1",
            interpolator_type="CubicBezierSmooth",
            interpolator_beta="0.22",
            start_linecap_type=stroke_cap_map[self.cap],
            end_linecap_type=stroke_cap_map[self.cap],
            linejoin_type=stroke_join_map[self.join],
            miter_limit=self.miter_clip,
            sort_points="true",
            not_jump="false",
            offset_points=offset_pts,
        )


stroke_cap_map = {e: e.name.lower() for e in AFStrokeCap}
stroke_join_map = {
    **{e: e.name.lower() for e in AFStrokeJoin},
    AFStrokeJoin.NONE: "miter",
}
stroke_order_map = {
    AFStrokeOrder.FRONT: "fill stroke markers",
    AFStrokeOrder.BEHIND: "stroke markers fill",
}


def parse_transform(xfrm: List[float]) -> inkex.Transform:
    return inkex.Transform((xfrm[:3], xfrm[3:]))


def parse_fill(child: AFObject) -> Union[AFColor, AFGradient]:
    if "BFil" in child:
        return parse_bfil(child["BFil"])
    elif "BFCr" in child and "BFFl" in child:
        fill_idx = child["BFCr"]
        return parse_fdsc(child["BFFl"][fill_idx])
    else:
        return AFColor([255, 39, 255], 0, AFColorSpace.RGB)


def parse_stroke_color(child: AFObject) -> Union[AFColor, AFGradient]:
    if "LICr" in child and "LIFl" in child:
        stroke_idx = child["LICr"]
        return parse_fdsc(child["LIFl"][stroke_idx])
    else:
        return AFColor([255, 39, 255], 0, AFColorSpace.RGB)


def parse_stroke(child) -> AFStroke:
    # Stroke
    # TODO: Align, Textured style, Start-End markers
    if "LSty" in child:
        return AFStroke.from_af(child["LSty"])
    elif "LILn" in child and "LICr" in child:
        stroke_idx = child["LICr"]
        return AFStroke.from_af(child["LILn"][stroke_idx])
    else:
        return AFStroke(
            1,
            AFStrokeType.NONE,
            AFStrokeCap.ROUND,
            AFStrokeJoin.ROUND,
            AFStrokeOrder.FRONT,
            AFStrokeAlign.CENTER,
            1.5,
            [1, 1, 0, 0, 0, 0],
        )
