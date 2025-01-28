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
"""Line-like path commands (Line, Horz, Vert, ZoneClose and their relative siblings)"""

from __future__ import annotations

from typing import overload, Tuple, Optional, TYPE_CHECKING, Callable, Union

from inkex.paths.interfaces import ILengthSettings, LengthSettings

from ..transforms import Transform, BoundingBox, ComplexLike

from .interfaces import AbsolutePathCommand, RelativePathCommand, ILengthSettings

if TYPE_CHECKING:
    from .curves import Curve


class LineMixin:
    """Common Line functions"""

    # pylint: disable=unused-argument

    arg1: complex

    cend_point: Callable[[complex, complex], complex]

    def ccurve_points(self, first: complex, prev: complex, prev_prev: complex):
        """Common implementation of ccurve_points for Lines"""
        arg1 = self.cend_point(first, prev)
        return prev, arg1, arg1

    def ccontrol_points(
        self,
        first: complex,
        prev: complex,
        prev_prev: complex,  # pylint: disable=unused-argument
    ) -> Tuple[complex, ...]:
        """Common implementation of ccontrol_points for Lines"""
        return (self.cend_point(first, prev),)

    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex:
        start = self.cend_point(first, prev)
        if prev == start:
            raise ValueError("Derivative is not defined for zero-length segments")
        if n == 1:
            return start - prev
        return 0j

    def _curvature(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> float:
        return 0

    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        return self.cend_point(first, prev) * t + (1 - t) * prev

    def _length(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t0: float = 0,
        t1: float = 1,
        settings=LengthSettings(),
    ) -> float:
        return abs(self.cend_point(first, prev) - prev) * (t1 - t0)

    def _ilength(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        length: float,
        settings: ILengthSettings = ILengthSettings(),
    ):
        return length / self._length(first, prev, prev_control)


class Line(LineMixin, AbsolutePathCommand):
    """Line segment"""

    letter = "L"
    nargs = 2

    arg1: complex
    """The (absolute) end points of the line."""

    @property
    def x(self):
        """x coordinate of the line's (absolute) end point."""
        return self.arg1.real

    @property
    def y(self):
        """y coordinate of the line's (absolute) end point."""
        return self.arg1.imag

    @property
    def args(self):
        return self.x, self.y

    @overload
    def __init__(self, x: ComplexLike): ...

    @overload
    def __init__(self, x: float, y: float): ...

    def __init__(self, x, y=None):
        if y is not None:
            self.arg1 = x + y * 1j
        else:
            self.arg1 = complex(x)

    def update_bounding_box(self, first, last_two_points, bbox):
        bbox += BoundingBox(
            (last_two_points[-1].real, self.x), (last_two_points[-1].imag, self.y)
        )

    def to_relative(self, prev: ComplexLike) -> line:
        return line(self.arg1 - prev)

    def transform(self, transform) -> Line:
        return Line(transform.capply_to_point(self.arg1))

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return self.arg1

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Line:
        return Line(prev)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Line, Line]:
        return Line(self._cpoint(first, prev, prev_control, t)), Line(self.arg1)


class line(LineMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative line segment"""

    letter = "l"
    nargs = 2

    arg1: complex
    """The (relative) end points of the line."""

    @property
    def dx(self):
        """x coordinate of the line's (relative) end point."""
        return self.arg1.real

    @property
    def dy(self):
        """y coordinate of the line's (relative) end point."""
        return self.arg1.imag

    @property
    def args(self):
        return self.dx, self.dy

    @overload
    def __init__(self, dx: ComplexLike): ...

    @overload
    def __init__(self, dx: float, dy: float): ...

    def __init__(self, dx, dy=None):
        if dy is not None:
            self.arg1 = dx + dy * 1j
        else:
            self.arg1 = complex(dx)

    def to_absolute(self, prev: ComplexLike) -> Line:
        return Line(prev + self.arg1)

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return self.arg1 + prev

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> line:
        return line(-self.arg1)

    def to_curve(
        self, prev: ComplexLike, prev_prev: Optional[ComplexLike] = 0j
    ) -> Curve:
        raise ValueError("Move segments can not be changed into curves.")

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[line, line]:
        dx1 = self.cpoint(first, prev, prev_control, t) - prev
        return line(dx1), line(self.arg1 - dx1)


class MoveMixin:
    """Disable derivative / length method for Move command."""

    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex:
        raise ValueError("Derivative is not supported for move/Move")

    def _cunit_tangent(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        raise ValueError("Unit Tangent is not supported for move/Move")

    def _curvature(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> float:
        raise ValueError("Curvature is not supported for move/Move")

    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        raise ValueError("Point is not supported for move/Move")

    def _length(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t0: float = 0,
        t1: float = 1,
        settings=LengthSettings(),
    ) -> float:
        raise ValueError("Length is not supported for move/Move")

    def _ilength(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        length: float,
        settings: ILengthSettings = ILengthSettings(),
    ):
        raise ValueError("ILength is not supported for move/Move")

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Move, Move]:
        raise ValueError("Split is not supported for move/Move")


class Move(MoveMixin, AbsolutePathCommand):
    """Move pen segment without a line"""

    letter = "M"
    nargs = 2
    next_command = Line

    arg1: complex
    """The (absolute) end points of the Move command"""

    @property
    def x(self):
        """x coordinate of the Moves's (absolute) end point."""
        return self.arg1.real

    @property
    def y(self):
        """y coordinate of the Move's (absolute) end point."""
        return self.arg1.imag

    @property
    def args(self):
        return self.x, self.y

    @overload
    def __init__(self, x: ComplexLike): ...

    @overload
    def __init__(self, x: float, y: float): ...

    def __init__(self, x, y=None):
        if y is not None:
            self.arg1 = x + y * 1j
        else:
            self.arg1 = complex(x)

    def update_bounding_box(self, first, last_two_points, bbox):
        bbox += BoundingBox(self.x, self.y)

    def ccurve_points(self, first: complex, prev: complex, prev_prev: complex):
        return prev, self.arg1, self.arg1

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.arg1,)

    def to_relative(self, prev: ComplexLike) -> move:
        return move(self.arg1 - prev)

    def transform(self, transform: Transform) -> Move:
        return Move(transform.capply_to_point(self.arg1))

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg1

    def to_curve(
        self, prev: ComplexLike, prev_prev: Optional[ComplexLike] = 0j
    ) -> Curve:
        raise ValueError("Move segments can not be changed into curves.")

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Move:
        return Move(prev)


class move(MoveMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative move segment"""

    letter = "m"
    nargs = 2
    next_command = line

    @property
    def dx(self):
        """x coordinate of the moves's (relative) end point."""
        return self.arg1.real

    @property
    def dy(self):
        """y coordinate of the move's (relative) end point."""
        return self.arg1.imag

    @property
    def args(self):
        return self.dx, self.dy

    @overload
    def __init__(self, dx: ComplexLike): ...

    @overload
    def __init__(self, dx: float, dy: float): ...

    def __init__(self, dx, dy=None):
        if dy is not None:
            self.arg1 = dx + dy * 1j
        else:
            self.arg1 = complex(dx)

    def ccurve_points(self, first: complex, prev: complex, prev_prev: complex):
        return prev, self.arg1 + prev, self.arg1 + prev

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.arg1 + prev,)

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg1 + prev

    def to_absolute(self, prev: ComplexLike) -> Move:
        return Move(prev + self.arg1)

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> move:
        return move(prev - first)

    def to_curve(
        self, prev: ComplexLike, prev_prev: Optional[ComplexLike] = 0j
    ) -> Curve:
        raise ValueError("Move segments can not be changed into curves.")


class ZoneClose(LineMixin, AbsolutePathCommand):
    """Close segment to finish a path"""

    letter = "Z"
    nargs = 0
    next_command = Move

    @property
    def args(self):
        return ()

    def update_bounding_box(self, first, last_two_points, bbox):
        pass

    def transform(self, transform: Transform) -> ZoneClose:
        return ZoneClose()

    def to_relative(self, prev: ComplexLike) -> zoneClose:
        return zoneClose()

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return first

    def to_curve(
        self, prev: ComplexLike, prev_prev: Optional[ComplexLike] = 0j
    ) -> Curve:
        raise ValueError("ZoneClose segments can not be changed into curves.")

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Line:
        return Line(prev)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Line, ZoneClose]:
        return Line(self._cpoint(first, prev, prev_control, t)), ZoneClose()


class zoneClose(LineMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Same as above (svg says no difference)"""

    letter = "z"
    nargs = 0
    next_command = Move

    @property
    def args(self):
        return ()

    def to_absolute(self, prev: ComplexLike):
        return ZoneClose()

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> line:
        return line(prev - first)

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return first

    def to_curve(
        self, prev: ComplexLike, prev_prev: Optional[ComplexLike] = 0j
    ) -> Curve:
        raise ValueError("ZoneClose segments can not be changed into curves.")

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[line, zoneClose]:
        return line(self.cpoint(first, prev, prev_control, t) - prev), zoneClose()


class Horz(LineMixin, AbsolutePathCommand):
    """Horizontal Line segment"""

    letter = "H"
    nargs = 1

    @property
    def args(self):
        return (self.x,)

    def __init__(self, x):
        self.x = x

    def update_bounding_box(self, first, last_two_points, bbox):
        bbox += BoundingBox(
            (last_two_points[-1].real, self.x), last_two_points[-1].imag
        )

    def to_relative(self, prev: ComplexLike) -> horz:
        return horz(self.x - complex(prev).real)

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Line:
        return self.to_line(prev)

    def transform(self, transform: Transform) -> AbsolutePathCommand:
        raise ValueError("Horizontal lines can't be transformed directly.")

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return self.x + prev.imag * 1j

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Horz:
        return Horz(complex(prev).real)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Horz, Horz]:
        return Horz(self.cpoint(first, prev, prev_control, t).real), Horz(self.x)


class horz(LineMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative horz line segment"""

    letter = "h"
    nargs = 1

    @property
    def args(self):
        return (self.dx,)

    def __init__(self, dx):
        self.dx = dx

    def to_absolute(self, prev: ComplexLike) -> Horz:
        return Horz(complex(prev).real + self.dx)

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Line:
        return self.to_line(prev)

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return (self.dx + prev.real) + prev.imag * 1j

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> horz:
        return horz(-self.dx)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[horz, horz]:
        dx1 = (self.cpoint(first, prev, prev_control, t) - prev).real
        return horz(dx1), horz(self.dx - dx1)


class Vert(LineMixin, AbsolutePathCommand):
    """Vertical Line segment"""

    letter = "V"
    nargs = 1

    @property
    def args(self):
        return (self.y,)

    def __init__(self, y):
        self.y = y

    def update_bounding_box(self, first, last_two_points, bbox):
        bbox += BoundingBox(
            last_two_points[-1].real, (last_two_points[-1].imag, self.y)
        )

    def transform(self, transform: Transform) -> AbsolutePathCommand:
        raise ValueError("Vertical lines can't be transformed directly.")

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Line:
        return self.to_line(prev)

    def to_relative(self, prev: ComplexLike) -> vert:
        return vert(self.y - complex(prev).imag)

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return prev.real + self.y * 1j

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Vert:
        return Vert(complex(prev).imag)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Vert, Vert]:
        return Vert(self.cpoint(first, prev, prev_control, t).imag), Vert(self.y)


class vert(LineMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative vertical line segment"""

    letter = "v"
    nargs = 1

    @property
    def args(self):
        return (self.dy,)

    def __init__(self, dy):
        self.dy = dy

    def to_absolute(self, prev: ComplexLike) -> Vert:
        return Vert(complex(prev).imag + self.dy)

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Line:
        return self.to_line(prev)

    def cend_point(self, first: complex, prev: complex) -> complex:
        # pylint: disable=unused-argument
        return prev.real + (prev.imag + self.dy) * 1j

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> vert:
        return vert(-self.dy)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[vert, vert]:
        dy1 = (self.cpoint(first, prev, prev_control, t) - prev).imag
        return vert(dy1), vert(self.dy - dy1)
