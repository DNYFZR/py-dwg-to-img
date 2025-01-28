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
"""Quadratic and TepidQuadratic path commands"""

from __future__ import annotations

from typing import overload, Tuple, Callable, Union
from math import sqrt

import numpy as np

from ..transforms import quadratic_extrema, Transform, ComplexLike

from .interfaces import (
    AbsolutePathCommand,
    RelativePathCommand,
    BezierComputationMixin,
    BezierArcComputationMixin,
    LengthSettings,
)


class QuadraticMixin(BezierComputationMixin, BezierArcComputationMixin):
    # pylint: disable=unused-argument
    ccontrol_points: Callable[[complex, complex, complex], Tuple[complex, ...]]

    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex:
        points = self.ccontrol_points(first, prev, prev_control)
        if n == 1:
            return 2 * ((points[0] - prev) * (1 - t) + (points[1] - points[0]) * t)
        if n == 2:
            return 2 * (prev - 2 * points[0] + points[1])
        if n > 2:
            return 0j
        raise ValueError("n should be a positive integer.")

    def _cunit_tangent(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        return self.bezier_unit_tangent(prev, prev_control, t)

    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        control, end = self.ccontrol_points(first, prev, prev_control)
        return (1 - t) ** 2 * prev + 2 * t * (1 - t) * control + t**2 * end

    # TODO maybe better treatment of degenerate beziers from
    # https://github.com/linebender/kurbo/blob/c229a914d303c5989c9e6b1d766def2df27a8185/src/quadbez.rs#L239
    # Ported from https://github.com/mathandy/svgpathtools/blob/19df25b99b405ec4fc7616b58384eca7879b6fd4/svgpathtools/path.py#L919
    # (MIT licensed)
    def _length(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t0: float = 0,
        t1: float = 1,
        settings=LengthSettings(),
    ) -> float:
        control, end = self.ccontrol_points(first, prev, prev_control)
        a = prev - 2 * control + end
        b = 2 * (control - prev)

        if abs(a) < 1e-12:
            s = abs(b) * (t1 - t0)
        else:
            c2 = 4 * (a.real**2 + a.imag**2)
            c1 = 4 * (a.real * b.real + a.imag * b.imag)
            c0 = b.real**2 + b.imag**2

            beta = c1 / (2 * c2)
            gamma = c0 / c2 - beta**2

            dq1_mag = sqrt(c2 * t1**2 + c1 * t1 + c0)
            dq0_mag = sqrt(c2 * t0**2 + c1 * t0 + c0)
            # this implicitly handles division by zero
            try:
                logarand = (sqrt(c2) * (t1 + beta) + dq1_mag) / (
                    sqrt(c2) * (t0 + beta) + dq0_mag
                )

                s = (
                    (t1 + beta) * dq1_mag
                    - (t0 + beta) * dq0_mag
                    + gamma * sqrt(c2) * np.log(logarand)
                ) / 2
            except ZeroDivisionError:
                s = np.NaN
            if np.isnan(s):
                tstar = abs(b) / (2 * abs(a))
                if t1 < tstar:
                    return abs(a) * (t0**2 - t1**2) - abs(b) * (t0 - t1)
                elif tstar < t0:
                    return abs(a) * (t1**2 - t0**2) - abs(b) * (t1 - t0)
                else:
                    return (
                        abs(a) * (t1**2 + t0**2)
                        - abs(b) * (t1 + t0)
                        + abs(b) ** 2 / (2 * abs(a))
                    )
        return s

    def _abssplit(
        self, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Quadratic, Quadratic]:
        """Split this Quadratic and return two Quadratics using DeCasteljau's algorithm"""
        p1, p2 = self.ccontrol_points(0j, prev, prev_control)
        p1_1 = (1 - t) * prev + t * p1
        p1_2 = (1 - t) * p1 + t * p2
        p2_1 = (1 - t) * p1_1 + t * p1_2
        return Quadratic(p1_1, p2_1), Quadratic(p1_2, p2)

    def _relsplit(self, prev: complex, prev_control: complex, t: float):
        """Split this curve and return two curves"""
        c1abs, c2abs = self._abssplit(prev, prev_control, t)
        return c1abs.to_relative(prev), c2abs.to_relative(c1abs.arg2)


class Quadratic(QuadraticMixin, AbsolutePathCommand):
    """Absolute Quadratic Curved Line segment"""

    letter = "Q"
    nargs = 4

    arg1: complex
    """The (absolute) control point"""

    arg2: complex
    """The (absolute) end point"""

    @property
    def x2(self) -> float:
        """x coordinate of the (absolute) control point"""
        return self.arg1.real

    @property
    def y2(self) -> float:
        """y coordinate of the (absolute) control point"""
        return self.arg1.imag

    @property
    def x3(self) -> float:
        """x coordinate of the (absolute) end point"""
        return self.arg2.real

    @property
    def y3(self) -> float:
        """y coordinate of the (absolute) end point"""
        return self.arg2.imag

    @property
    def args(self):
        return self.x2, self.y2, self.x3, self.y3

    @overload
    def __init__(self, x2: ComplexLike, x3: ComplexLike): ...

    @overload
    def __init__(self, x2: float, y2: float, x3: float, y3: float): ...

    def __init__(self, x2, y2, x3=None, y3=None):
        if x3 is not None:
            self.arg1 = x2 + y2 * 1j
            self.arg2 = x3 + y3 * 1j
        else:
            self.arg1, self.arg2 = complex(x2), complex(y2)

    def update_bounding_box(self, first, last_two_points, bbox):
        x1, x2, x3 = last_two_points[-1].real, self.x2, self.x3
        y1, y2, y3 = last_two_points[-1].imag, self.y2, self.y3

        if not (x1 in bbox.x and x2 in bbox.x and x3 in bbox.x):
            bbox.x += quadratic_extrema(x1, x2, x3)

        if not (y1 in bbox.y and y2 in bbox.y and y3 in bbox.y):
            bbox.y += quadratic_extrema(y1, y2, y3)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.arg1, self.arg2)

    def to_relative(self, prev: ComplexLike) -> quadratic:
        return quadratic(self.arg1 - prev, self.arg2 - prev)

    def transform(self, transform: Transform) -> Quadratic:
        return Quadratic(
            transform.capply_to_point(self.arg1), transform.capply_to_point(self.arg2)
        )

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg2

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        pt1 = 1.0 / 3 * prev + 2.0 / 3 * self.arg1
        pt2 = 2.0 / 3 * self.arg1 + 1.0 / 3 * self.arg2
        return pt1, pt2, self.arg2

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Quadratic:
        prev = complex(prev)
        return Quadratic(self.x2, self.y2, prev.real, prev.imag)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Quadratic, Quadratic]:
        return self._abssplit(prev, prev_control, t)


class quadratic(QuadraticMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative quadratic line segment"""

    letter = "q"
    nargs = 4

    arg1: complex
    """The (relative) control point"""

    arg2: complex
    """The (relative) end point"""

    @property
    def dx2(self) -> float:
        """x coordinate of the (relative) control point"""
        return self.arg1.real

    @property
    def dy2(self) -> float:
        """y coordinate of the (relative) control point"""
        return self.arg1.imag

    @property
    def dx3(self) -> float:
        """x coordinate of the (relative) end point"""
        return self.arg2.real

    @property
    def dy3(self) -> float:
        """y coordinate of the (relative) end point"""
        return self.arg2.imag

    @property
    def args(self):
        return self.dx2, self.dy2, self.dx3, self.dy3

    @overload
    def __init__(self, dx2: ComplexLike, dx3: ComplexLike): ...

    @overload
    def __init__(self, dx2: float, dy2: float, dx3: float, dy3: float): ...

    def __init__(self, dx2, dy2, dx3=None, dy3=None):
        if dx3 is not None:
            self.arg1 = dx2 + dy2 * 1j
            self.arg2 = dx3 + dy3 * 1j
        else:
            self.arg1, self.arg2 = complex(dx2), complex(dy2)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.arg1 + prev, self.arg2 + prev)

    def to_absolute(self, prev: ComplexLike) -> Quadratic:
        return Quadratic(self.arg1 + prev, self.arg2 + prev)

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        pt1 = 1.0 / 3 * prev + 2.0 / 3 * (prev + self.arg1)
        pt2 = 2.0 / 3 * (prev + self.arg1) + 1.0 / 3 * (prev + self.arg2)
        return pt1, pt2, prev + self.arg2

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg2 + prev

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> quadratic:
        return quadratic(-self.arg2 + self.arg1, -self.arg2)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[quadratic, quadratic]:
        return self._relsplit(prev, prev_control, t)


class TepidQuadratic(QuadraticMixin, AbsolutePathCommand):
    """Continued Quadratic Line segment"""

    letter = "T"
    nargs = 2

    arg1: complex
    """The (absolute) control point"""

    @property
    def x3(self) -> float:
        """x coordinate of the (absolute) end point"""
        return self.arg1.real

    @property
    def y3(self) -> float:
        """y coordinate of the (absolute) end point"""
        return self.arg1.imag

    @property
    def args(self):
        return self.x3, self.y3

    @overload
    def __init__(self, x3: ComplexLike): ...

    @overload
    def __init__(self, x3: float, y3: float): ...

    def __init__(self, x3, y3=None):
        if y3 is not None:
            self.arg1 = x3 + y3 * 1j
        else:
            self.arg1 = complex(x3)

    def update_bounding_box(self, first, last_two_points, bbox):
        self.to_quadratic(last_two_points[-1], last_two_points[-2]).update_bounding_box(
            first, last_two_points, bbox
        )

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (2 * prev - prev_prev, self.arg1)

    def to_non_shorthand(
        self, prev: ComplexLike, prev_control: ComplexLike
    ) -> Quadratic:
        return self.to_quadratic(prev, prev_control)

    def to_relative(self, prev: ComplexLike) -> tepidQuadratic:
        return tepidQuadratic(self.arg1 - prev)

    def transform(self, transform: Transform) -> TepidQuadratic:
        return TepidQuadratic(transform.capply_to_point(self.arg1))

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        qp1 = 2 * prev - prev_prev
        qp2 = self.arg1
        pt1 = 1.0 / 3 * prev + 2.0 / 3 * qp1
        pt2 = 2.0 / 3 * qp1 + 1.0 / 3 * qp2
        return pt1, pt2, qp2

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg1

    def to_quadratic(self, prev: ComplexLike, prev_prev: ComplexLike) -> Quadratic:
        """Convert this continued quadratic into a full quadratic"""
        return Quadratic(
            *self.ccontrol_points(complex(prev), complex(prev), complex(prev_prev))
        )

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> TepidQuadratic:
        return TepidQuadratic(prev)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Quadratic, Quadratic]:
        return self._abssplit(prev, prev_control, t)


class tepidQuadratic(QuadraticMixin, RelativePathCommand):  # pylint: disable=invalid-name
    """Relative continued quadratic line segment"""

    letter = "t"
    nargs = 2

    arg1: complex
    """The (relative) control point"""

    @property
    def dx3(self) -> float:
        """x coordinate of the (relative) end point"""
        return self.arg1.real

    @property
    def dy3(self) -> float:
        """y coordinate of the (relative) end point"""
        return self.arg1.imag

    @property
    def args(self):
        return self.dx3, self.dy3

    @overload
    def __init__(self, dx3: ComplexLike): ...

    @overload
    def __init__(self, dx3: float, dy3: float): ...

    def __init__(self, dx3, dy3=None):
        if dy3 is not None:
            self.arg1 = dx3 + dy3 * 1j
        else:
            self.arg1 = complex(dx3)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (2 * prev - prev_prev, self.arg1 + prev)

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        qp1 = 2 * prev - prev_prev
        qp2 = self.arg1 + prev
        pt1 = 1.0 / 3 * prev + 2.0 / 3 * qp1
        pt2 = 2.0 / 3 * qp1 + 1.0 / 3 * qp2
        return pt1, pt2, qp2

    def to_absolute(self, prev: ComplexLike) -> TepidQuadratic:
        return TepidQuadratic(self.arg1 + prev)

    def to_non_shorthand(
        self, prev: ComplexLike, prev_control: ComplexLike
    ) -> Quadratic:
        return self.to_absolute(prev).to_non_shorthand(prev, prev_control)

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.arg1 + prev

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> tepidQuadratic:
        return tepidQuadratic(-self.arg1)

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[quadratic, quadratic]:
        return self._relsplit(prev, prev_control, t)
