#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
# SPDX-FileCopyrightText: 2024 Software Freedom Conservancy <info@sfconservancy.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Union

import inkex

from ..parser.types import AFObject
from .util import interpolate_float


class AFColorSpace(Enum):
    UNKNOWN = 0
    RGB = 1
    HSL = 2
    CMYK = 3
    LAB = 4
    GRAY = 5

    @classmethod
    def from_string(cls, space: str) -> AFColorSpace:
        if space.upper() in ["RGB", "RGBA"]:
            return AFColorSpace.RGB
        if space.upper() in ["HSL", "HSLA"]:
            return AFColorSpace.HSL
        if space.upper() == "CMYK":
            return AFColorSpace.CMYK
        if space.upper() in ["LAB", "LABA"]:
            return AFColorSpace.LAB
        if space.upper() == "GRAY":
            return AFColorSpace.GRAY
        return AFColorSpace.UNKNOWN


class AFGradientType(Enum):
    LINEAR = 0
    ELLIPTICAL = 1
    RADIAL = 2
    CONICAL = 3


def gray_to_rgb(color: AFColor) -> AFColor:
    assert color.space == AFColorSpace.GRAY
    return AFColor([color.color[0]] * 3, alpha=color.alpha, _space=AFColorSpace.RGB)


def hsl_to_rgb(color: AFColor) -> AFColor:
    assert color.space == AFColorSpace.HSL
    return AFColor(
        inkex.colors.hsl_to_rgb(*color.color),
        alpha=color.alpha,
        _space=AFColorSpace.RGB,
    )


def cmyk_to_rgb(color: AFColor) -> AFColor:
    assert color.space == AFColorSpace.CMYK
    c, m, y, k = color.color
    if k == 1:
        return AFColor([0, 0, 0], alpha=color.alpha, _space=AFColorSpace.RGB)
    return AFColor(
        [
            0.0 if c >= 1 else 1.0 * (1 - c) * (1 - k),
            0.0 if m >= 1 else 1.0 * (1 - m) * (1 - k),
            0.0 if y >= 1 else 1.0 * (1 - y) * (1 - k),
        ],
        alpha=color.alpha,
        _space=AFColorSpace.RGB,
    )


def lab_to_rgb(color: AFColor) -> AFColor:
    raise NotImplementedError("LAB to RGB not implemented")


map_to_rgb: Dict[AFColorSpace, Callable[[AFColor], AFColor]] = {
    AFColorSpace.RGB: lambda color: color,
    AFColorSpace.HSL: hsl_to_rgb,
    AFColorSpace.CMYK: cmyk_to_rgb,
    AFColorSpace.LAB: lab_to_rgb,
    AFColorSpace.GRAY: gray_to_rgb,
}

map_from_rgb: Dict[AFColorSpace, Callable[[AFColor], AFColor]] = {
    AFColorSpace.RGB: lambda color: color,
    # AFColorSpace.HSL: lambda color: color,
    # AFColorSpace.CMYK: lambda color: color,
    # AFColorSpace.LAB: lambda color: color,
    # AFColorSpace.GRAY: lambda color: color,
}


@dataclass
class AFColor:
    color: list[int | float]
    alpha: float
    _space: InitVar[AFColorSpace | str]
    space: AFColorSpace = field(init=False)

    def __post_init__(self, _space: AFColorSpace | str):
        self.space = (
            _space
            if isinstance(_space, AFColorSpace)
            else AFColorSpace.from_string(_space)
        )
        assert self.space != AFColorSpace.UNKNOWN, f"Unknown color space: {_space}"

        assert 0 <= self.alpha <= 1, f"Bad alpha: {self.alpha}"
        assert (
            len(self.color) == 1 or self.space != AFColorSpace.GRAY
        ), f"Bad {self.space.name} color list: {self.color}"
        assert len(self.color) == 3 or self.space not in [
            AFColorSpace.RGB,
            AFColorSpace.HSL,
            AFColorSpace.LAB,
        ], f"Bad {self.space.name} color list: {self.color}"
        assert (
            len(self.color) == 4 or self.space != AFColorSpace.CMYK
        ), f"Bad {self.space.name} color list: {self.color}"

    @classmethod
    def from_af(cls, color: AFObject) -> AFColor:
        color_values = color["_col"]
        color_space = color.get_type()

        if color_space == "RGBA":
            return AFColor(
                color_values[:3], alpha=color_values[3], _space=AFColorSpace.RGB
            )
        if color_space == "HSLA":
            return AFColor(
                color_values[:3], alpha=color_values[3], _space=AFColorSpace.HSL
            )
        if color_space == "CMYK":
            return AFColor(
                color_values[:4], alpha=color_values[4], _space=AFColorSpace.CMYK
            )
        if color_space == "LABA":
            return AFColor(
                color_values[:3],
                alpha=color_values[3] / 0xFFFF,
                _space=AFColorSpace.LAB,
            )
        if color_space == "GRAY":
            return AFColor(
                [color_values[0]], alpha=color_values[1], _space=AFColorSpace.GRAY
            )

        raise NotImplementedError(f"Unknown color space: {color_space}")

    def to_rgb(self) -> AFColor:
        fn = map_to_rgb.get(self.space)
        if fn is None:
            raise NotImplementedError(f"Can't convert {self.space.name} to RGB")
        return fn(self)

    def to_space(self, space: AFColorSpace) -> AFColor:
        if self.space != AFColorSpace.RGB:
            return AFColor(
                self.to_rgb().to_space(space).color, alpha=self.alpha, _space=space
            )
        fn = map_from_rgb.get(space)
        if fn is None:
            raise NotImplementedError(
                f"Can't convert {self.space.name} to {space.name}"
            )
        return fn(self)

    def interpolate(self, other: AFColor, t: float, space=AFColorSpace.RGB) -> AFColor:
        inter = inkex.Color(
            self.to_space(space).color, space=space.name.lower()
        ).interpolate(
            inkex.Color(other.to_space(space).color, space=space.name.lower()), t
        )
        return AFColor(
            [c / 255 for c in inter],
            alpha=interpolate_float(self.alpha, other.alpha, t),
            _space=inter.space,
        )


@dataclass
class AFGradientStop:
    pos: float
    mid: float
    color: AFColor


@dataclass
class AFGradient:
    grad_type: AFGradientType
    tfm: inkex.Transform
    stops: List[AFGradientStop]
    fdsc: bool = True

    @classmethod
    def from_af(
        cls, fdef: AFObject, fdex: List[float], fdsc: Optional[bool]
    ) -> AFGradient:
        assert fdef.get_type() == "FilG", "Not a gradient"
        grad_type = AFGradientType(fdef["Type"].id)

        fdsc = True if fdsc is None else fdsc
        assert len(fdex) == 6, "Invalid gradient transform"
        assert isinstance(fdsc, bool)
        if not fdsc:
            raise NotImplementedError(f"FDSc {fdsc} not implemented")  # TODO

        grad = fdef["Grad"]
        stops = [
            AFGradientStop(s[0], s[1], AFColor.from_af(c))
            for s, c in zip(grad["Posn"], grad["Cols"])
        ]

        tfm = inkex.Transform((fdex[:3], fdex[3:]))  # type: ignore
        return cls(grad_type, tfm, stops, fdsc)


def parse_pant(fill: AFObject) -> AFColor:
    # TODO: fields: ispt, name, base, srgb
    return AFColor.from_af(fill["srgb"])


def parse_solid(fill: AFObject) -> AFColor:
    # TODO: type: RegC
    if fill["Colr"].get_type() == "Pant":
        return parse_pant(fill["Colr"])
    return AFColor.from_af(fill["Colr"])


def parse_no_fill(_: Optional[AFObject] = None) -> AFColor:
    return AFColor([0, 0, 0], alpha=0, _space=AFColorSpace.RGB)


def parse_gradient(
    fill: AFObject, tfm: List[float], fdsc: Optional[bool] = None
) -> AFGradient:
    return AFGradient.from_af(fill, tfm, fdsc)


fdsc_map: Dict[str, Callable[[AFObject], Union[AFColor, AFGradient]]] = {
    "FilN": lambda _: parse_no_fill(),
    "FilS": lambda fdsc: parse_solid(fdsc["FDeF"]),
    "FilG": lambda fdsc: parse_gradient(fdsc["FDeF"], fdsc["FDeX"], fdsc.get("FDSc")),
    # "FilB": # TODO,
}


def parse_fdsc(fdsc: AFObject) -> Union[AFColor, AFGradient]:
    assert fdsc.get_type() == "FDsc", f"Not a fill desc: {fdsc}"
    fill_type = fdsc["FDeF"].get_type()
    assert fill_type in [
        "FilN",
        "FilS",
        "FilG",
        "FilB",
    ], f"Invalid fill type: {fill_type}"

    fn = fdsc_map.get(fill_type)
    if fn is None:
        raise NotImplementedError(f"Fill type '{fill_type}' not implemented")

    return fn(fdsc)


def parse_bfil(bfil: AFObject) -> Union[AFColor, AFGradient]:
    if bfil.get_type() == "FDsc":
        return parse_fdsc(bfil)
    if bfil.get_type() == "FilS":
        return parse_solid(bfil)
    raise NotImplementedError(f"Fill type '{bfil.get_type()}' not implemented")
