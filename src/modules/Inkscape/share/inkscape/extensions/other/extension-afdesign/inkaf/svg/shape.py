#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import Dict, List, Tuple, Type

from inkex import (
    PathEffect,
)

from ..parser.types import AFObject
from .util import AFBoundingBox, safe_div

# TODO: For shapes, the stroke's start point should be at the top right corner of the shape


class AFShape:
    _id: int = 0

    def __init__(self, b_box: AFBoundingBox):
        self.b_box = b_box

        self.id = self.__class__._id
        self.__class__._id += 1

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFShape:
        stype = shpe.get_type()
        assert stype is not None, "Undefined Shape type"
        return cls(b_box)


class AFPointsShapeBase(AFShape):
    def __init__(self, b_box: AFBoundingBox):
        super().__init__(b_box)

    @property
    @abstractmethod
    def points(self) -> List[Tuple[float, float]]: ...


class AFCornerPos(Enum):
    TL = 0
    TR = 1
    BR = 2
    BL = 3


class AFCornerType(Enum):
    ROUNDED = 0
    STRAIGHT = 1
    CONCAVE = 2
    CUTOUT = 3
    NONE = 4


corner_map = {
    AFCornerType.NONE: "F",  # radius will be set to 0
    AFCornerType.ROUNDED: "F",
    AFCornerType.CONCAVE: "IF",
    AFCornerType.STRAIGHT: "C",
}


class AFRectangle(AFShape):
    def __init__(
        self,
        b_box: AFBoundingBox,
        radii: List[float] = [0.25] * 4,
        corner_types: List[AFCornerType] = [AFCornerType.NONE] * 4,
        lock: bool = True,
        absolute_size: bool = False,
    ):
        super().__init__(b_box)
        self.lock = lock
        self.absolute_size = absolute_size
        self.corner_types = corner_types
        self.radii = radii

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFRectangle:
        sup = super().from_af(shpe, b_box)
        assert shpe.get_type() == "ShNR", "Not a rectangle"
        assert isinstance(sup, AFRectangle)

        if "Lock" in shpe:
            sup.lock = shpe["Lock"]
        if "AbSz" in shpe:
            sup.absolute_size = shpe["AbSz"]
        if "CTyp" in shpe:
            sup.corner_types = [AFCornerType(ct.id) for ct in shpe["CTyp"]]
        if "ShCR" in shpe:
            sup.radii = shpe["ShCR"]
        return sup

    @property
    def radii(self) -> List[float]:
        radii = self._radii
        if not self.absolute_size:
            radii = [r * min(self.b_box.width, self.b_box.height) for r in radii]
        if self.lock:
            radii = [radii[0]] * 4

        radii = [
            r if c != AFCornerType.NONE else 0.0
            for r, c in zip(radii, self.corner_types)
        ]

        if (
            radii[0] + radii[1] > self.b_box.width
            or radii[2] + radii[3] > self.b_box.width
            or radii[3] + radii[0] > self.b_box.height
            or radii[1] + radii[2] > self.b_box.height
        ):
            ratio = min(
                safe_div(self.b_box.width, (radii[0] + radii[1]), float("inf")),
                safe_div(self.b_box.width, (radii[2] + radii[3]), float("inf")),
                safe_div(self.b_box.height, (radii[3] + radii[0]), float("inf")),
                safe_div(self.b_box.height, (radii[1] + radii[2]), float("inf")),
            )
            if ratio != float("inf"):
                radii = [r * ratio for r in radii]
        return radii

    @radii.setter
    def radii(self, value: List[float]):
        assert len(value) == 4
        self._radii = value

    @property
    def corner_types(self) -> List[AFCornerType]:
        if self.lock:
            return [AFCornerType(self._corner_types[0])] * 4
        return [ct for ct in self._corner_types]

    @corner_types.setter
    def corner_types(self, value: List[AFCornerType]):
        assert len(value) == 4 and all(isinstance(ct, AFCornerType) for ct in value)
        self._corner_types = value

    def _corner_path(self, pos: AFCornerPos) -> List[Tuple[str, List[float]]]:
        corner_type = self.corner_types[pos.value]
        radius = self.radii[pos.value]

        if radius <= 0:
            return []

        dx = radius if pos in [AFCornerPos.TL, AFCornerPos.TR] else -radius
        dy = radius if pos in [AFCornerPos.TR, AFCornerPos.BR] else -radius

        if corner_type == AFCornerType.STRAIGHT:
            return [("l", [dx, dy])]

        if corner_type in [AFCornerType.ROUNDED, AFCornerType.CONCAVE]:
            # arc: a rx ry x-axis-rotation large-arc-flag sweep-flag dx dy
            is_round = corner_type == AFCornerType.ROUNDED
            return [("a", [radius, radius, 0, 0, int(is_round), dx, dy])]

        if corner_type == AFCornerType.CUTOUT:
            return (
                [("h", [dx]), ("v", [dy])]
                if pos in [AFCornerPos.TL, AFCornerPos.BR]
                else [("v", [dy]), ("h", [dx])]
            )

        return (
            [("h", [dx]), ("v", [dy])]
            if pos not in [AFCornerPos.TL, AFCornerPos.BR]
            else [("v", [dy]), ("h", [dx])]
        )

    def _corner_path_effect(self) -> PathEffect:
        assert all(
            ct in corner_map for ct in self.corner_types
        ), f"Invalid corner types {[ct for ct in self.corner_types if ct not in corner_map]}"

        params = " @ ".join(
            f"{corner_map[c]},1,0,1,0,{r/fn(self.b_box.width, self.b_box.height)},0,1"
            for c, r, fn in zip(self.corner_types, self.radii, [max, min] * 2)
        )
        return PathEffect.new(
            effect="fillet_chamfer",
            lpeversion="1",
            method="arc",
            flexible="true",  # radius in %
            satellites_param=params,  # Inkscape 1.2
            nodesatellites_param=params,  # Inkscape 1.3
        )


class AFEllipse(AFShape):
    def __init__(self, b_box: AFBoundingBox):
        super().__init__(b_box)

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFEllipse:
        sup = super().from_af(shpe, b_box)
        assert shpe.get_type() == "ShpE", "Not an ellipse"
        assert isinstance(sup, AFEllipse)
        return sup

    @property
    def centre(self) -> Tuple[float, float]:
        b_box = self.b_box
        return (b_box.x + b_box.width / 2, b_box.y + b_box.height / 2)

    @property
    def radii(self) -> Tuple[float, float]:
        b_box = self.b_box
        return (b_box.width / 2, b_box.height / 2)


class AFTriangle(AFPointsShapeBase):
    def __init__(self, b_box: AFBoundingBox, pos: float = 0.5):
        super().__init__(b_box)
        self.pos = pos

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFTriangle:
        sup = super().from_af(shpe, b_box)
        assert shpe.get_type() == "ShpT", "Not a triangle"
        assert isinstance(sup, AFTriangle)

        if "Pos " in shpe:
            sup.pos = shpe["Pos "]

        return sup

    @property
    def points(self) -> List[Tuple[float, float]]:
        b_box = self.b_box
        return [
            (b_box.x + (b_box.width * self.pos), b_box.y),
            (b_box.x2, b_box.y2),
            (b_box.x, b_box.y2),
        ]


class AFDiamond(AFPointsShapeBase):
    def __init__(self, b_box: AFBoundingBox, pos: float = 0.5):
        super().__init__(b_box)
        self.pos = pos

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFDiamond:
        sup = super().from_af(shpe, b_box)
        assert shpe.get_type() == "ShpD", "Not a diamond"
        assert isinstance(sup, AFDiamond)

        if "Pos " in shpe:
            sup.pos = shpe["Pos "]

        return sup

    @property
    def points(self) -> List[Tuple[float, float]]:
        b_box = self.b_box
        hpos, vpos = 0.5, 1 - self.pos
        return [
            (b_box.x + (b_box.width * hpos), b_box.y),
            (b_box.x2, b_box.y + (b_box.height * vpos)),
            (b_box.x + (b_box.width * hpos), b_box.y2),
            (b_box.x, b_box.y + (b_box.height * vpos)),
        ]


class AFTrapezoid(AFPointsShapeBase):
    def __init__(self, b_box: AFBoundingBox, posl: float = 0.25, posr: float = 0.75):
        super().__init__(b_box)
        self.posl = posl
        self.posr = posr

    @classmethod
    def from_af(cls, shpe: AFObject, b_box: AFBoundingBox) -> AFTrapezoid:
        sup = super().from_af(shpe, b_box)
        assert shpe.get_type() == "ShTz", "Not a trapezoid"
        assert isinstance(sup, AFTrapezoid)

        if "PosL" in shpe:
            sup.posl = shpe["PosL"]
        if "PosR" in shpe:
            sup.posr = shpe["PosR"]

        return sup

    @property
    def points(self) -> List[Tuple[float, float]]:
        b_box = self.b_box
        posl, posr = self.posl, self.posr
        return [
            (b_box.x2, b_box.y2),
            (b_box.x, b_box.y2),
            (b_box.x + (b_box.width * posl), b_box.y),
            (b_box.x + (b_box.width * posr), b_box.y),
        ]


shape_map: Dict[str, Type[AFShape]] = {
    "ShNR": AFRectangle,
    "ShpE": AFEllipse,
    "ShpT": AFTriangle,
    "ShpD": AFDiamond,
    "ShTz": AFTrapezoid,
}


def parse_shape(shpe: AFObject, b_box: List[float]) -> AFShape:
    shape_type = shpe.get_type()
    if shape_type in shape_map:
        return shape_map[shape_type].from_af(shpe, AFBoundingBox(*b_box))

    raise NotImplementedError(f"Shape type {shape_type} not implemented")
