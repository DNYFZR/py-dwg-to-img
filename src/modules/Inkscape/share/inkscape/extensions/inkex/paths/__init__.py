# coding=utf-8
#
# Copyright (C) 2018 Martin Owens <doctormo@gmail.com>
# Copyright (C) 2023 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""Paths module.

Most of the functions derivative, unit_tangent, curvature, point, split, length, ilength
for the individual path commands are ported from
https://github.com/mathandy/svgpathtools/ (MIT licensed)
"""

from typing import Union

from ..transforms import ComplexLike
from .interfaces import (
    PathCommand,
    AbsolutePathCommand,
    RelativePathCommand,
    LengthSettings,
    ILengthSettings,
)
from .lines import Line, line, Move, move, ZoneClose, zoneClose, Horz, horz, Vert, vert
from .curves import curve, Curve, smooth, Smooth
from .quadratic import quadratic, Quadratic, tepidQuadratic, TepidQuadratic
from .arc import Arc, arc, arc_to_path, matprod, rotmat, applymat, norm
from .path import CubicSuperPath, Path, InvalidPath

import numpy as np

np.seterr(invalid="raise")


# definitions that can't be inside the class due to circular dependencies
def to_curve(self, prev: ComplexLike, prev_prev: ComplexLike = 0) -> Curve:
    """Convert command to :py:class:`Curve`

    Curve().to_curve() returns a copy
    """
    return Curve(*self.ccurve_points(0 + 0j, complex(prev), complex(prev_prev)))


def to_line(self, prev: ComplexLike) -> Line:
    """Converts this segment to a line (copies if already a line)"""
    return Line(self.cend_point(0, complex(prev)))


PathCommand.to_curve = to_curve  # type: ignore
PathCommand.to_line = to_line  # type: ignore

PathCommand._letter_to_class = {  # pylint: disable=protected-access
    "M": Move,
    "L": Line,
    "V": Vert,
    "H": Horz,
    "A": Arc,
    "C": Curve,
    "S": Smooth,
    "Z": ZoneClose,
    "Q": Quadratic,
    "T": TepidQuadratic,
    "m": move,
    "l": line,
    "v": vert,
    "h": horz,
    "a": arc,
    "c": curve,
    "s": smooth,
    "z": zoneClose,
    "q": quadratic,
    "t": tepidQuadratic,
}


# All the names that get added to the inkex API itself.
__all__ = (
    "Path",
    "CubicSuperPath",
    "PathCommand",
    "AbsolutePathCommand",
    "RelativePathCommand",
    # Path commands:
    "Line",
    "line",
    "Move",
    "move",
    "ZoneClose",
    "zoneClose",
    "Horz",
    "horz",
    "Vert",
    "vert",
    "Curve",
    "curve",
    "Smooth",
    "smooth",
    "Quadratic",
    "quadratic",
    "TepidQuadratic",
    "tepidQuadratic",
    "Arc",
    "arc",
    # errors
    "InvalidPath",
    # structs
    "LengthSettings",
    "ILengthSettings",
)
