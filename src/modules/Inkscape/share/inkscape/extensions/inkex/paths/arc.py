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
"""Arc path commands"""

from __future__ import annotations
from math import atan2, pi, sqrt, sin, cos, tan, acos, radians, degrees
from cmath import exp
from typing import overload, Tuple, List, Union, TYPE_CHECKING

import numpy as np

from ..transforms import Transform, Vector2d, ComplexLike

from .interfaces import (
    AbsolutePathCommand,
    RelativePathCommand,
    LengthSettings,
    ILengthSettings,
    BezierArcComputationMixin,
)

if TYPE_CHECKING:
    from .curves import Curve


class Arc(BezierArcComputationMixin, AbsolutePathCommand):
    """Special Arc segment"""

    letter = "A"

    nargs = 7

    radius: complex
    """Radius of the Arc"""
    x_axis_rotation: float

    large_arc: bool
    sweep: bool

    endpoint: complex
    """Endpoint (absolute) of the Arc"""

    @property
    def rx(self) -> float:
        """x radius of the Arc"""
        return self.radius.real

    @property
    def ry(self) -> float:
        """y radius of the Arc"""
        return self.radius.imag

    @property
    def x(self) -> float:
        """x coordinate of the (absolute) endpoint of the Arc"""
        return self.endpoint.real

    @property
    def y(self) -> float:
        """x coordinate of the (relative) endpoint of the Arc"""
        return self.endpoint.imag

    @property
    def args(self):
        return (
            self.rx,
            self.ry,
            self.x_axis_rotation,
            self.large_arc,
            self.sweep,
            self.x,
            self.y,
        )

    @property
    def cargs(self):
        """Set of arguments in complex form"""
        return (
            self.radius,
            self.x_axis_rotation,
            self.large_arc,
            self.sweep,
            self.endpoint,
        )

    @overload
    def __init__(
        self,
        radius: ComplexLike,
        x_axis_rotation: float,
        large_arc: bool | int,
        sweep: bool | int,
        endpoint: ComplexLike,
    ) -> None: ...

    @overload
    def __init__(
        self,
        rx: float,
        ry: float,
        x_axis_rotation: float,
        large_arc: bool | int,
        sweep: bool | int,
        x: float,
        y: float,
    ) -> None: ...  # pylint: disable=too-many-arguments

    def __init__(self, *args):
        if len(args) == 5:
            (
                self.radius,
                self.x_axis_rotation,
                self.large_arc,
                self.sweep,
                self.endpoint,
            ) = args
            self.radius = complex(self.radius)
            self.endpoint = complex(self.endpoint)
        elif len(args) == 7:
            self.radius = args[0] + args[1] * 1j
            self.x_axis_rotation, self.large_arc, self.sweep = args[2:5]
            self.endpoint = args[5] + args[6] * 1j

    def parametrize(self, prev):
        """Return the parametrisation of the arc:
            (radius, phi, rot_matrix, center, theta1, deltatheta)
        See http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes

        .. versionadded:: 1.4"""
        # my notation roughly follows theirs
        phi = radians(self.x_axis_rotation)
        rot_matrix = exp(1j * phi)

        radius = self.radius
        rx = self.radius.real
        ry = self.radius.imag
        rx_sqd = rx * rx
        ry_sqd = ry * ry

        # Transform z-> z' = x' + 1j*y'
        # = self.rot_matrix**(-1)*(z - (end+start)/2)
        # coordinates.  This translates the ellipse so that the midpoint
        # between self.end and self.start lies on the origin and rotates
        # the ellipse so that the its axes align with the xy-coordinate axes.
        # Note:  This sends self.end to -self.start
        zp1 = (1 / rot_matrix) * (prev - self.cend_point(0j, prev)) / 2
        x1p, y1p = zp1.real, zp1.imag
        x1p_sqd = x1p * x1p
        y1p_sqd = y1p * y1p

        # Correct out of range radii
        radius_check = (x1p_sqd / rx_sqd) + (y1p_sqd / ry_sqd)
        if radius_check > 1:
            rx *= sqrt(radius_check)
            ry *= sqrt(radius_check)
            radius = rx + 1j * ry
            rx_sqd = rx * rx
            ry_sqd = ry * ry

        # Compute c'=(c_x', c_y'), the center of the ellipse in (x', y') coords
        # Noting that, in our new coord system, (x_2', y_2') = (-x_1', -x_2')
        # and our ellipse is cut out by of the plane by the algebraic equation
        # (x'-c_x')**2 / r_x**2 + (y'-c_y')**2 / r_y**2 = 1,
        # we can find c' by solving the system of two quadratics given by
        # plugging our transformed endpoints (x_1', y_1') and (x_2', y_2')
        tmp = rx_sqd * y1p_sqd + ry_sqd * x1p_sqd
        radicand = (rx_sqd * ry_sqd - tmp) / tmp
        radical = 0 if np.isclose(radicand, 0) else sqrt(radicand)

        if self.large_arc == self.sweep:
            cp = -radical * (rx * y1p / ry - 1j * ry * x1p / rx)
        else:
            cp = radical * (rx * y1p / ry - 1j * ry * x1p / rx)

        # The center in (x,y) coordinates is easy to find knowing c'
        center = exp(1j * phi) * cp + (prev + self.cend_point(0j, prev)) / 2

        # Now we do a second transformation, from (x', y') to (u_x, u_y)
        # coordinates, which is a translation moving the center of the
        # ellipse to the origin and a dilation stretching the ellipse to be
        # the unit circle
        u1 = (x1p - cp.real) / rx + 1j * (y1p - cp.imag) / ry  # transformed start
        u2 = (-x1p - cp.real) / rx + 1j * (-y1p - cp.imag) / ry  # transformed end

        # clip in case of floating point error
        u1 = np.clip(u1.real, -1, 1) + 1j * np.clip(u1.imag, -1, 1)
        u2 = np.clip(u2.real, -1, 1) + 1j * np.clip(u2.imag, -1, 1)

        # Now compute theta and delta (we'll define them as we go)
        # delta is the angular distance of the arc (w.r.t the circle)
        # theta is the angle between the positive x'-axis and the start point
        # on the circle
        if u1.imag > 0:
            theta1 = degrees(acos(u1.real))
        elif u1.imag < 0:
            theta1 = -degrees(acos(u1.real))
        else:
            if u1.real > 0:  # start is on pos u_x axis
                theta1 = 0
            else:  # start is on neg u_x axis
                # Note: This behavior disagrees with behavior documented in
                # http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes
                # where theta is set to 0 in this case.
                theta1 = 180

        det_uv = u1.real * u2.imag - u1.imag * u2.real

        acosand = u1.real * u2.real + u1.imag * u2.imag
        acosand = np.clip(acosand.real, -1, 1) + np.clip(acosand.imag, -1, 1)

        if det_uv > 0:
            deltatheta = degrees(acos(acosand))
        elif det_uv < 0:
            deltatheta = -degrees(acos(acosand))
        else:
            if u1.real * u2.real + u1.imag * u2.imag > 0:
                # u1 == u2
                deltatheta = 0
            else:
                # u1 == -u2
                # Note: This behavior disagrees with behavior documented in
                # http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes
                # where deltatheta is set to 0 in this case.
                deltatheta = 180

        if not self.sweep and deltatheta >= 0:
            deltatheta -= 360
        elif self.large_arc and deltatheta <= 0:
            deltatheta += 360

        return radius, phi, rot_matrix, center, theta1, deltatheta

    def update_bounding_box(self, first, last_two_points, bbox):
        prev = last_two_points[-1]
        for seg in self.to_curves(prev=prev):
            seg.update_bounding_box(first, [None, prev], bbox)
            prev = seg.cend_point(first, prev)

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.endpoint,)

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return NotImplemented

    def to_curves(self, prev: ComplexLike, prev_prev: ComplexLike = 0j) -> List[Curve]:
        """Convert this arc into bezier curves"""
        # TODO Refactor out CubicSuperPath
        from .path import CubicSuperPath

        path = CubicSuperPath(
            [arc_to_path(Vector2d.c2t(complex(prev)), self.args)]
        ).to_path(curves_only=True)
        # Ignore the first move command from to_path()
        return list(path)[1:]

    def transform(self, transform: Transform) -> Arc:
        # pylint: disable=invalid-name, too-many-locals
        newend = transform.capply_to_point(self.endpoint)

        T: Transform = transform
        if self.x_axis_rotation != 0:
            T = T @ Transform(rotate=self.x_axis_rotation)
        a, c, b, d, _, _ = list(T.to_hexad())
        # T = | a b |
        #     | c d |

        detT = a * d - b * c
        detT2 = detT**2

        rx = float(self.rx)
        ry = float(self.ry)

        def get_degen():
            return Arc(
                self.radius,
                self.x_axis_rotation,
                self.large_arc,
                self.sweep,
                newend,
            )

        if rx == 0.0 or ry == 0.0 or detT2 == 0.0:
            # degenerate arc
            # transform only last point
            return get_degen()
        A = (d**2 / rx**2 + c**2 / ry**2) / detT2
        B = -(d * b / rx**2 + c * a / ry**2) / detT2
        D = (b**2 / rx**2 + a**2 / ry**2) / detT2

        theta = atan2(-2 * B, D - A) / 2
        theta_deg = theta * 180.0 / pi
        DA = D - A
        l2 = 4 * B**2 + DA**2

        if l2 == 0:
            delta = 0.0
        else:
            delta = 0.5 * (-(DA**2) - 4 * B**2) / sqrt(l2)

        half = (A + D) / 2

        try:
            rx_ = 1.0 / sqrt(half + delta)
            ry_ = 1.0 / sqrt(half - delta)

            if detT > 0:
                sweep = self.sweep
            else:
                sweep = not self.sweep > 0
            return Arc(rx_ + 1j * ry_, theta_deg, self.large_arc, sweep, newend)
        except ZeroDivisionError:
            return get_degen()

    def to_relative(self, prev: ComplexLike) -> RelativePathCommand:
        return arc(
            self.radius,
            self.x_axis_rotation,
            self.large_arc,
            self.sweep,
            self.endpoint - prev,
        )

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.endpoint

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> Arc:
        return Arc(
            self.radius, self.x_axis_rotation, self.large_arc, not self.sweep, prev
        )

    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        # TODO surely this can be expressed in a shorter way using complex geometry?
        radius, _, rot_matrix, center, theta1, deltatheta = self.parametrize(prev)
        angle = (theta1 + t * deltatheta) * pi / 180
        cosphi = rot_matrix.real
        sinphi = rot_matrix.imag
        rx = radius.real
        ry = radius.imag

        x = rx * cosphi * cos(angle) - ry * sinphi * sin(angle) + center.real
        y = rx * sinphi * cos(angle) + ry * cosphi * sin(angle) + center.imag
        return x + y * 1j

    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex:
        """returns the nth derivative of the segment at t."""
        radius, phi, _, _, theta1, deltatheta = self.parametrize(prev)
        angle = radians(theta1 + t * deltatheta)
        rx = radius.real
        ry = radius.imag
        k = (deltatheta * pi / 180) ** n  # ((d/dt)angle)**n

        if n % 4 == 0 and n > 0:
            return (
                rx * cos(phi) * cos(angle)
                - ry * sin(phi) * sin(angle)
                + 1j * (rx * sin(phi) * cos(angle) + ry * cos(phi) * sin(angle))
            )
        elif n % 4 == 1:
            return k * (
                -rx * cos(phi) * sin(angle)
                - ry * sin(phi) * cos(angle)
                + 1j * (-rx * sin(phi) * sin(angle) + ry * cos(phi) * cos(angle))
            )
        elif n % 4 == 2:
            return k * (
                -rx * cos(phi) * cos(angle)
                + ry * sin(phi) * sin(angle)
                + 1j * (-rx * sin(phi) * cos(angle) - ry * cos(phi) * sin(angle))
            )
        elif n % 4 == 3:
            return k * (
                rx * cos(phi) * sin(angle)
                + ry * sin(phi) * cos(angle)
                + 1j * (rx * sin(phi) * sin(angle) - ry * cos(phi) * cos(angle))
            )
        else:
            raise ValueError("n should be a positive integer.")

    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[Arc, Arc]:
        """returns two segments, whose union is this segment and which join
        at self.point(t)."""
        radius, _, _, _, _, deltatheta = self.parametrize(prev)

        def crop(t0, t1):
            return Arc(
                radius,
                self.x_axis_rotation,
                not abs(deltatheta * (t1 - t0)) <= 180,
                self.sweep,
                self.cpoint(0j, prev, 0j, t1),
            )

        return crop(0, t), crop(t, 1)

    def _ilength(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        length: float,
        settings: ILengthSettings = ILengthSettings(),
    ):
        # ilength calls self.parametrize very often, so we cache the result
        param = self.parametrize
        params = param(prev)

        def cached(prev):  # pylint: disable=unused-argument
            return params

        self.parametrize = cached  # type: ignore
        try:
            return super()._ilength(first, prev, prev_control, length, settings)
        finally:
            self.parametrize = param  # type: ignore


class arc(RelativePathCommand, Arc):  # pylint: disable=invalid-name
    """Relative Arc line segment"""

    letter = "a"

    nargs = 7

    endpoint: complex
    """Endpoint (relative) of the arc"""

    @property
    def rx(self) -> float:
        """x radius of the arc"""
        return self.radius.real

    @property
    def ry(self) -> float:
        """y radius of the arc"""
        return self.radius.imag

    @property
    def dx(self) -> float:
        """x coordinate of the (relative) endpoint of the arc"""
        return self.endpoint.real

    @property
    def dy(self) -> float:
        """x coordinate of the (relative) endpoint of the arc"""
        return self.endpoint.imag

    @property
    def args(self):
        return (
            self.rx,
            self.ry,
            self.x_axis_rotation,
            self.large_arc,
            self.sweep,
            self.dx,
            self.dy,
        )

    @overload
    def __init__(
        self,
        radius: ComplexLike,
        x_axis_rotation: float,
        large_arc: bool,
        sweep: bool,
        endpoint: ComplexLike,
    ) -> None: ...

    @overload
    def __init__(
        self,
        rx: float,
        ry: float,
        x_axis_rotation: float,
        large_arc: bool,
        sweep: bool,
        dx: float,
        dy: float,
    ) -> None: ...  # pylint: disable=too-many-arguments

    def __init__(self, *args):
        if len(args) == 5:
            (
                self.radius,
                self.x_axis_rotation,
                self.large_arc,
                self.sweep,
                self.endpoint,
            ) = args
            self.radius = complex(self.radius)
            self.endpoint = complex(self.endpoint)
        elif len(args) == 7:
            self.radius = args[0] + args[1] * 1j
            self.x_axis_rotation, self.large_arc, self.sweep = args[2:5]
            self.endpoint = args[5] + args[6] * 1j

    def to_absolute(self, prev: ComplexLike) -> Arc:
        return Arc(
            self.radius,
            self.x_axis_rotation,
            self.large_arc,
            self.sweep,
            self.endpoint + prev,
        )

    def cend_point(self, first: complex, prev: complex) -> complex:
        return self.endpoint + prev

    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return (self.endpoint + prev,)

    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        return NotImplemented

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> arc:
        return arc(
            self.radius,
            self.x_axis_rotation,
            self.large_arc,
            not self.sweep,
            -self.endpoint,
        )

    def to_curves(self, prev: ComplexLike, prev_prev: ComplexLike = 0j) -> List[Curve]:
        return self.to_absolute(prev).to_curves(prev, prev_prev)


def arc_to_path(point, params):
    """Approximates an arc with cubic bezier segments.

    Arguments:
        point:  Starting point (absolute coords)
        params: Arcs parameters as per
              https://www.w3.org/TR/SVG/paths.html#PathDataEllipticalArcCommands

    Returns a list of triplets of points :
    [control_point_before, node, control_point_after]
    (first and last returned triplets are [p1, p1, *] and [*, p2, p2])
    """

    # pylint: disable=invalid-name, too-many-locals
    A = point[:]
    rx, ry, teta, longflag, sweepflag, x2, y2 = params[:]
    teta = teta * pi / 180.0
    B = [x2, y2]
    # Degenerate ellipse
    if rx == 0 or ry == 0 or A == B:
        return [[A[:], A[:], A[:]], [B[:], B[:], B[:]]]

    # turn coordinates so that the ellipse morph into a *unit circle* (not 0-centered)
    mat = matprod((rotmat(teta), [[1.0 / rx, 0.0], [0.0, 1.0 / ry]], rotmat(-teta)))
    applymat(mat, A)
    applymat(mat, B)

    k = [-(B[1] - A[1]), B[0] - A[0]]
    d = k[0] * k[0] + k[1] * k[1]
    k[0] /= sqrt(d)
    k[1] /= sqrt(d)
    d = sqrt(max(0, 1 - d / 4.0))
    # k is the unit normal to AB vector, pointing to center O
    # d is distance from center to AB segment (distance from O to the midpoint of AB)
    # for the last line, remember this is a unit circle, and kd vector is ortogonal to
    # AB (Pythagorean thm)

    if longflag == sweepflag:
        # top-right ellipse in SVG example
        # https://www.w3.org/TR/SVG/images/paths/arcs02.svg
        d *= -1

    O = [(B[0] + A[0]) / 2.0 + d * k[0], (B[1] + A[1]) / 2.0 + d * k[1]]
    OA = [A[0] - O[0], A[1] - O[1]]
    OB = [B[0] - O[0], B[1] - O[1]]
    start = acos(OA[0] / norm(OA))
    if OA[1] < 0:
        start *= -1
    end = acos(OB[0] / norm(OB))
    if OB[1] < 0:
        end *= -1
    # start and end are the angles from center of the circle to A and to B respectively

    if sweepflag and start > end:
        end += 2 * pi
    if (not sweepflag) and start < end:
        end -= 2 * pi

    NbSectors = int(abs(start - end) * 2 / pi) + 1
    dTeta = (end - start) / NbSectors
    v = 4 * tan(dTeta / 4.0) / 3.0
    # I would use v = tan(dTeta/2)*4*(sqrt(2)-1)/3 ?
    p = []
    for i in range(0, NbSectors + 1, 1):
        angle = start + i * dTeta
        v1 = [
            O[0] + cos(angle) - (-v) * sin(angle),
            O[1] + sin(angle) + (-v) * cos(angle),
        ]
        pt = [O[0] + cos(angle), O[1] + sin(angle)]
        v2 = [O[0] + cos(angle) - v * sin(angle), O[1] + sin(angle) + v * cos(angle)]
        p.append([v1, pt, v2])
    p[0][0] = p[0][1][:]
    p[-1][2] = p[-1][1][:]

    # go back to the original coordinate system
    mat = matprod((rotmat(teta), [[rx, 0], [0, ry]], rotmat(-teta)))
    for pts in p:
        applymat(mat, pts[0])
        applymat(mat, pts[1])
        applymat(mat, pts[2])
    return p


def matprod(mlist):
    """Get the product of the mat"""
    prod = mlist[0]
    for mat in mlist[1:]:
        a00 = prod[0][0] * mat[0][0] + prod[0][1] * mat[1][0]
        a01 = prod[0][0] * mat[0][1] + prod[0][1] * mat[1][1]
        a10 = prod[1][0] * mat[0][0] + prod[1][1] * mat[1][0]
        a11 = prod[1][0] * mat[0][1] + prod[1][1] * mat[1][1]
        prod = [[a00, a01], [a10, a11]]
    return prod


def rotmat(teta):
    """Rotate the mat"""
    return [[cos(teta), -sin(teta)], [sin(teta), cos(teta)]]


def applymat(mat, point):
    """Apply the given mat"""
    x = mat[0][0] * point[0] + mat[0][1] * point[1]
    y = mat[1][0] * point[0] + mat[1][1] * point[1]
    point[0] = x
    point[1] = y


def norm(point):
    """Normalise"""
    return sqrt(point[0] * point[0] + point[1] * point[1])
