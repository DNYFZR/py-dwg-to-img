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
"""Curve and Smooth Path Commands"""

from __future__ import annotations

from typing import overload, Tuple, Callable, Union, cast

import numpy as np

from ..transforms import cubic_extrema, Transform, Vector2d, ComplexLike

from .interfaces import (
    AbsolutePathCommand,
    RelativePathCommand,
    BezierArcComputationMixin,
    BezierComputationMixin,
)


class CurveMixin(BezierComputationMixin, BezierArcComputationMixin):
    """Common functionality for curves"""

    ccontrol_points: Callable[[complex, complex, complex], Tuple[complex, ...]]

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        """Common implementation of ccurve_points for Curves"""
        return self.ccontrol_points(first, prev, prev_prev)

    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex:
        """Returns the nth derivative of the segment at t.

        .. hint:: Bezier curves can have points where their derivative vanishes.
        If you are interested in the tangent direction, use the :func:`unit_tangent`
        method instead."""

        points = self.ccontrol_points(first, prev, prev_control)

        if n == 1:
            return (
                3 * (points[0] - prev) * ((1 - t) ** 2)
                + 6 * (points[1] - points[0]) * (1 - t) * t
                + 3 * (points[2] - points[1]) * t**2
            )
        elif n == 2:
            return 6 * (
                (1 - t) * (points[1] - 2 * points[0] + prev)
                + t * (points[2] - 2 * points[1] + points[0])
            )
        elif n == 3:
            return 6 * (points[2] - 3 * (points[1] - points[0]) - prev)
        elif n > 3:
            return complex(0, 0)
        else:
            raise ValueError("n should be a positive integer.")

    def poly(self, prev, prev_control, return_coeffs=False):
        """Returns a the cubic as a complex Polynomial object.

        .. versionadded:: 1.4"""
        points = self.ccontrol_points(0j, prev, prev_control)
        coeffs = (
            -prev + 3 * (points[0] - points[1]) + points[2],
            3 * (prev - 2 * points[0] + points[1]),
            3 * (prev + points[0]),
            prev,
        )
        if return_coeffs:
            return coeffs
        return np.poly1d(coeffs)

    def _cunit_tangent(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        return self.bezier_unit_tangent(prev, prev_control, t)

    def _curvature(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ):
        return self.segment_curvature(prev, prev_control, t)

    def _abssplit(
        self, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Curve, Curve]:
        """Split this curve and return two Curves using DeCasteljau's algorithm"""
        p1, p2, p3 = self.ccontrol_points(0j, prev, prev_control)
        p1_1 = (1 - t) * prev + t * p1
        p1_2 = (1 - t) * p1 + t * p2
        p1_3 = (1 - t) * p2 + t * p3
        p2_1 = (1 - t) * p1_1 + t * p1_2
        p2_2 = (1 - t) * p1_2 + t * p1_3
        p3_1 = (1 - t) * p2_1 + t * p2_2

        return Curve(p1_1, p2_1, p3_1), Curve(p2_2, p1_3, p3)

    def _relsplit(self, prev: complex, prev_control: complex, t: float):
        """Split this curve and return two curves"""
        c1abs, c2abs = self._abssplit(prev, prev_control, t)
        return c1abs.to_relative(prev), c2abs.to_relative(c1abs.arg3)

    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        control1, control2, end = self.ccontrol_points(first, prev, prev_control)
        return (
            (1 - t) ** 3 * prev
            + 3 * t * (1 - t) ** 2 * control1
            + 3 * t**2 * (1 - t) * control2
            + t**3 * end
        )


class Curve(CurveMixin, AbsolutePathCommand):
    """Absolute Curved Line segment"""

    letter = "C"
    nargs = 6

    arg1: complex
    """The (absolute) first control point"""

    arg2: complex
    """The (absolute) second control point"""

    arg3: complex
    """The (absolute) end point"""

    @property
    def x2(self) -> float:
        """x coordinate of the (absolute) first control point"""
        return self.arg1.real

    @property
    def y2(self) -> float:
        """y coordinate of the (absolute) first control point"""
        return self.arg1.imag

    @property
    def x3(self) -> float:
        """x coordinate of the (absolute) second control point"""
        return self.arg2.real

    @property
    def y3(self) -> float:
        """y coordinate of the (absolute) second control point"""
        return self.arg2.imag

    @property
    def x4(self) -> float:
        """x coordinate of the (absolute) end point"""
        return self.arg3.real

    @property
    def y4(self) -> float:
        """y coordinate of the (absolute) end point"""
        return self.arg3.imag

    @property
    def args(self):
        return (
            self.arg1.real,
            self.arg1.imag,
            self.arg2.real,
            self.arg2.imag,
            self.arg3.real,
            self.arg3.imag,
        )

    @overload
    def __init__(self, x2: ComplexLike, x3: ComplexLike, x4: ComplexLike): ...

    @overload
    def __init__(
        self, x2: float, y2: float, x3: float, y3: float, x4: float, y4: float
    ): ...  # pylint: disable=too-many-arguments

    def __init__(self, x2, y2, x3, y3=None, x4=None, y4=None):  # pylint: disable=too-many-arguments
        if y3 is not None:
            self.arg1 = x2 + y2 * 1j
            self.arg2 = x3 + y3 * 1j
            self.arg3 = x4 + y4 * 1j
        else:
            self.arg1, self.arg2, self.arg3 = complex(x2), complex(y2), complex(x3)

    def update_bounding_box(self, first, last_two_points, bbox):
        x1, x2, x3, x4 = last_two_points[-1].real, self.x2, self.x3, self.x4
        y1, y2, y3, y4 = last_two_points[-1].imag, self.y2, self.y3, self.y4

        if not (x1 in bbox.x and x2 in bbox.x and x3 in bbox.x and x4 in bbox.x):
            bbox.x += cubic_extrema(x1, x2, x3, x4)

        if not (y1 in bbox.y and y2 in bbox.y and y3 in bbox.y and y4 in bbox.y):
            bbox.y += cubic_extrema(y1, y2, y3, y4)

    def transform(self, transform: Transform) -> Curve:
        return Curve(
            transform.capply_to_point(self.arg1),
            transform.capply_to_point(self.arg2),
            transform.capply_to_point(self.arg3),
        )

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        # pylint: disable=unused-argument
        return (self.arg1, self.arg2, self.arg3)

    def to_relative(self, prev: ComplexLike) -> curve:
        return curve(self.arg1 - prev, self.arg2 - prev, self.arg3 - prev)

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg3

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Curve:
        return Curve(self.arg2, self.arg1, prev)

    def to_bez(self):
        """Convert to [[c1x, c1y], [c2x, c2y], [end_x, end_y]]"""
        return [Vector2d.c2t(i) for i in self.ccontrol_points(0j, 0j, 0j)]

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Curve, Curve]:
        return self._abssplit(prev, prev_control, t)


class curve(CurveMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative curved line segment"""

    letter = "c"
    nargs = 6

    arg1: complex
    """The (relative) first control point"""

    arg2: complex
    """The (relative) second control point"""

    arg3: complex
    """The (relative) end point"""

    @property
    def dx2(self) -> float:
        """x coordinate of the (relative) first control point"""
        return self.arg1.real

    @property
    def dy2(self) -> float:
        """y coordinate of the (relative) first control point"""
        return self.arg1.imag

    @property
    def dx3(self) -> float:
        """x coordinate of the (relative) second control point"""
        return self.arg2.real

    @property
    def dy3(self) -> float:
        """y coordinate of the (relative) second control point"""
        return self.arg2.imag

    @property
    def dx4(self) -> float:
        """x coordinate of the (relative) end point"""
        return self.arg3.real

    @property
    def dy4(self) -> float:
        """y coordinate of the (relative) end point"""
        return self.arg3.imag

    @overload
    def __init__(self, dx2: ComplexLike, dx3: ComplexLike, dx4: ComplexLike): ...

    @overload
    def __init__(
        self, dx2: float, dy2: float, dx3: float, dy3: float, dx4: float, dy4: float
    ): ...  # pylint: disable=too-many-arguments

    def __init__(self, dx2, dy2, dx3, dy3=None, dx4=None, dy4=None):  # pylint: disable=too-many-arguments
        if dy3 is not None:
            self.arg1 = dx2 + dy2 * 1j
            self.arg2 = dx3 + dy3 * 1j
            self.arg3 = dx4 + dy4 * 1j
        else:
            self.arg1, self.arg2, self.arg3 = complex(dx2), complex(dy2), complex(dx3)

    @property
    def args(self):
        return self.dx2, self.dy2, self.dx3, self.dy3, self.dx4, self.dy4

    def to_absolute(self, prev: ComplexLike) -> Curve:
        return Curve(*self.ccurve_points(0j, complex(prev), 0j))

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg3 + prev

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> curve:
        return curve(-self.arg3 + self.arg2, -self.arg3 + self.arg1, -self.arg3)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        # pylint: disable=unused-argument
        return (
            self.arg1 + prev,
            self.arg2 + prev,
            self.arg3 + prev,
        )

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[curve, curve]:
        return self._relsplit(prev, prev_control, t)


class Smooth(CurveMixin, AbsolutePathCommand):
    """Absolute Smoothed Curved Line segment"""

    letter = "S"
    nargs = 4

    arg1: complex
    """The (absolute) control point"""

    arg2: complex
    """The (absolute) end point"""

    @property
    def x3(self) -> float:
        """x coordinate of the (absolute) control point"""
        return self.arg1.real

    @property
    def y3(self) -> float:
        """y coordinate of the (absolute) control point"""
        return self.arg1.imag

    @property
    def x4(self) -> float:
        """x coordinate of the (absolute) end point"""
        return self.arg2.real

    @property
    def y4(self) -> float:
        """y coordinate of the (absolute) end point"""
        return self.arg2.imag

    @property
    def args(self):
        return self.x3, self.y3, self.x4, self.y4

    @overload
    def __init__(self, x3: ComplexLike, x4: ComplexLike): ...

    @overload
    def __init__(self, x3: float, y3: float, x4: float, y4: float): ...

    def __init__(self, x3, y3, x4=None, y4=None):
        if x4 is not None:
            self.arg1 = x3 + y3 * 1j
            self.arg2 = x4 + y4 * 1j
        else:
            self.arg1, self.arg2 = complex(x3), complex(y3)

    def update_bounding_box(self, first, last_two_points, bbox):
        # pylint: disable=no-member
        self.to_curve(last_two_points[-1], last_two_points[-2]).update_bounding_box(
            first, last_two_points, bbox
        )

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        # pylint: disable=unused-argument
        return (2 * prev - prev_prev, self.arg1, self.arg2)

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Curve:
        return self.to_curve(prev, prev_control)

    def to_relative(self, prev: ComplexLike) -> smooth:
        return smooth(self.arg1 - prev, self.arg2 - prev)

    def transform(self, transform: Transform) -> Smooth:
        return Smooth(
            transform.capply_to_point(self.arg1), transform.capply_to_point(self.arg2)
        )

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg2

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Smooth:
        return Smooth(self.arg1, prev)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Curve, Curve]:
        # We can't preserve the smooth type for a split because de Casteljau's
        # algorithm changes the handles (obviously).
        # Only in special cases such as splitting to subsequent smooth segments at
        # t=1/2 such a preservation would be possible
        crv = cast(Curve, self.to_non_shorthand(prev, prev_control))
        return crv._split(  # pylint: disable=protected-access, no-member
            first, prev, prev_control, t
        )


class smooth(CurveMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative smoothed curved line segment"""

    letter = "s"
    nargs = 4

    arg1: complex
    """The (absolute) control point"""

    arg2: complex
    """The (absolute) end point"""

    @property
    def dx3(self) -> float:
        """x coordinate of the (relative) control point"""
        return self.arg1.real

    @property
    def dy3(self) -> float:
        """y coordinate of the (relative) control point"""
        return self.arg1.imag

    @property
    def dx4(self) -> float:
        """x coordinate of the (relative) end point"""
        return self.arg2.real

    @property
    def dy4(self) -> float:
        """y coordinate of the (relative) end point"""
        return self.arg2.imag

    @property
    def args(self):
        return self.dx3, self.dy3, self.dx4, self.dy4

    @overload
    def __init__(self, dx3: ComplexLike, dx4: ComplexLike): ...

    @overload
    def __init__(self, dx3: float, dy3: float, dx4: float, dy4: float): ...

    def __init__(self, dx3, dy3, dx4=None, dy4=None):
        if dx4 is not None:
            self.arg1 = dx3 + dy3 * 1j
            self.arg2 = dx4 + dy4 * 1j
        else:
            self.arg1, self.arg2 = complex(dx3), complex(dy3)

    def to_absolute(self, prev: ComplexLike) -> Smooth:
        return Smooth(self.arg1 + prev, self.arg2 + prev)

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg2 + prev

    def to_non_shorthand(self, prev: ComplexLike, prev_control: ComplexLike) -> Curve:
        return self.to_absolute(prev).to_non_shorthand(prev, prev_control)

    def reverse(self, first: ComplexLike, prev: ComplexLike):
        return smooth(-self.arg2 + self.arg1, -self.arg2)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        # pylint: disable=unused-argument
        return (2 * prev - prev_prev, self.arg1 + prev, self.arg2 + prev)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[curve, curve]:
        return self._relsplit(prev, prev_control, t)
