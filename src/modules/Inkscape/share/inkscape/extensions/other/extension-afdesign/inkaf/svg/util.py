#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations
from dataclasses import dataclass

import inkex

MAX_CLIP_PATH_RECURSION = 50


@dataclass
class AFBoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def x(self) -> float:
        return self.x1

    @property
    def y(self) -> float:
        return self.y1

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1


class ClipPathRecursionError(Exception):
    pass


def interpolate_float(num1: float, num2: float, factor: float) -> float:
    return num1 + (num2 - num1) * factor


def safe_div(num1: float, num2: float, on_fail: float) -> float:
    return num1 / num2 if num2 != 0 else on_fail


def get_transformed_bbox(bbox: AFBoundingBox, tfm: inkex.Transform) -> AFBoundingBox:
    """Get the bounding box of the transformed rectangle defined by `bbox` and `tfm`"""
    pts = [
        inkex.Vector2d(bbox.x1, bbox.y1),
        inkex.Vector2d(bbox.x1, bbox.y2),
        inkex.Vector2d(bbox.x2, bbox.y1),
        inkex.Vector2d(bbox.x2, bbox.y2),
    ]
    pts[:] = map(tfm.apply_to_point, pts)

    return AFBoundingBox(
        min(pts, key=lambda p: p.x).x,
        min(pts, key=lambda p: p.y).y,
        max(pts, key=lambda p: p.x).x,
        max(pts, key=lambda p: p.y).y,
    )
