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
"""Interfaces for path commands"""

from __future__ import annotations

import abc
import math
from typing import (
    List,
    Any,
    Tuple,
    Dict,
    Type,
    Generator,
    Union,
    TYPE_CHECKING,
    Optional,
    Callable,
)
from dataclasses import dataclass

import numpy as np
from ..utils import classproperty, rational_limit
from ..transforms import Vector2d, BoundingBox, Transform, ComplexLike

if TYPE_CHECKING:
    from .curves import Curve
    from .lines import Line


@dataclass
class LengthSettings:
    """Settings for :func:`PathCommand.length`

    .. versionadded::  1.4"""

    min_depth: int = 5
    error: float = 1e-5


@dataclass
class ILengthSettings:
    """Settings for :func:`PathCommand.ilength`

    .. versionadded:: 1.4"""

    min_depth: int = 5

    error: float = 1e-5
    """
    Error tolerance for the computations of the test segment that is performed 
    for each iteration.

    The defaults from svgpathtools are ILENGTH_ERROR=ILENGTH_LENGTH_TOL=1e-12.
    This is rather slow, particularly _length (which then subdivides the path into
    2^12 or more segments and adds up the length). For visual editing, this is rather
    irrelevant (and a lot more accurate than the previous methods)."""

    length_tol: float = 1e-5
    """Total (absolute) tolerance of the resulting s value."""

    maxits: int = 10000


class PathCommand(abc.ABC):
    """
    Base class of all path commands
    """

    letter = ""
    # Number of arguments that follow this path commands letter
    nargs = -1

    @classproperty  # From python 3.9 on, just combine @classmethod and @property
    def name(cls):  # pylint: disable=no-self-argument
        """The full name of the segment (i.e. Line, Arc, etc)"""
        return cls.__name__  # pylint: disable=no-member

    @classproperty
    def next_command(self):
        """The implicit next command. This is for automatic chains where the next
        command isn't given, just a bunch on numbers which we automatically parse."""
        return self

    @property
    def is_relative(self) -> bool:
        """Whether the command is defined in relative coordinates, i.e. relative to
        the previous endpoint (lower case path command letter)"""
        raise NotImplementedError

    @property
    def is_absolute(self) -> bool:
        """Whether the command is defined in absolute coordinates (upper case path
        command letter)"""
        raise NotImplementedError

    def to_relative(self, prev: ComplexLike) -> RelativePathCommand:
        """Return absolute counterpart for absolute commands or copy for relative"""
        raise NotImplementedError

    def to_absolute(self, prev: ComplexLike) -> AbsolutePathCommand:
        """Return relative counterpart for relative commands or copy for absolute"""
        raise NotImplementedError

    def reverse(self, first: ComplexLike, prev: ComplexLike) -> PathCommand:
        """Reverse path command

        .. versionadded:: 1.1"""
        raise NotImplementedError

    def to_non_shorthand(
        self,
        prev: ComplexLike,
        prev_control: ComplexLike,  # pylint: disable=unused-argument
    ) -> AbsolutePathCommand:
        """Return an absolute non-shorthand command

        .. versionadded:: 1.1"""
        return self.to_absolute(prev)

    # The precision of the numbers when converting to string
    number_template = "{:.6g}"

    # Maps single letter path command to corresponding class
    # (filled at the bottom of file, when all classes already defined)
    _letter_to_class: Dict[str, Type[Any]] = {}

    @staticmethod
    def letter_to_class(letter):
        """Returns class for given path command letter"""
        return PathCommand._letter_to_class[letter]

    @property
    @abc.abstractmethod
    def args(self) -> List[float]:
        """Returns path command arguments as tuple of floats"""

    def control_points(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_prev: ComplexLike,
    ) -> Generator[Vector2d, None, None]:
        """Returns list of path command control points"""
        first, prev, prev_prev = complex(first), complex(prev), complex(prev_prev)
        yield from [Vector2d(i) for i in self.ccontrol_points(first, prev, prev_prev)]

    @abc.abstractmethod
    def ccontrol_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        """Returns list of path command control points"""

    @classmethod
    def _argt(cls, sep):
        return sep.join([cls.number_template] * cls.nargs)

    def __str__(self):
        return f"{self.letter} {self._argt(' ').format(*self.args)}".strip()

    def __repr__(self):
        # pylint: disable=consider-using-f-string
        return "{{}}({})".format(self._argt(", ")).format(self.name, *self.args)

    def __eq__(self, other):
        previous = 0j
        if type(self) == type(other):  # pylint: disable=unidiomatic-typecheck
            return self.args == other.args
        if isinstance(other, tuple):
            return self.args == other
        if not isinstance(other, PathCommand):
            raise ValueError("Can't compare types")
        try:
            if self.is_relative == other.is_relative:
                return self.to_curve(previous) == other.to_curve(previous)
        except ValueError:
            pass
        return False

    @abc.abstractmethod
    def cend_point(self, first: complex, prev: complex) -> complex:
        """Complex version of end_point"""

    def end_point(self, first: ComplexLike, prev: ComplexLike) -> Vector2d:
        """Returns last control point of path command"""
        return Vector2d(self.cend_point(complex(first or 0), complex(prev or 0)))

    @abc.abstractmethod
    def update_bounding_box(
        self, first: complex, last_two_points: List[complex], bbox: BoundingBox
    ):
        """Enlarges given bbox to contain path element.

        Args:
            first (complex): first point of path. Required to calculate Z segment
            last_two_points (List[complex]): list with last two control points in abs
                coords.
            bbox (BoundingBox): bounding box to update
        """

    def to_curve(self, prev: ComplexLike, prev_prev: ComplexLike = 0) -> Curve:
        # pylint: disable=unused-argument
        """Convert command to :py:class:`Curve`

        Curve().to_curve() returns a copy
        """
        return NotImplemented

    def to_curves(self, prev: ComplexLike, prev_prev: ComplexLike = 0) -> List[Curve]:
        """Convert command to list of :py:class:`Curve` commands"""
        return [self.to_curve(prev, prev_prev)]

    def to_line(self, prev: ComplexLike) -> Line:
        # pylint: disable=unused-argument
        """Converts this segment to a line (copies if already a line)"""
        return NotImplemented

    @abc.abstractmethod
    def ccurve_points(
        self, first: complex, prev: complex, prev_prev: complex
    ) -> Tuple[complex, ...]:
        # pylint: disable=unused-argument
        """Converts the path element into a single cubic bezier"""

    # Derivation functionality

    def __check_t(self, t: Optional[float], allow_none=True):
        if not allow_none and (t is None and self.letter not in "zZmMlLhHvV"):
            raise ValueError("t=None only supported for Line-like commands")
        if t is not None and not 0 <= t <= 1:
            raise ValueError("t should be between 0 and 1")
        return t if t is not None else 0.0

    def cderivative(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t: Optional[float] = None,
        n: int = 1,
    ) -> complex:
        """Returns the nth derivative of the segment at t as a complex number.

        .. versionadded:: 1.4
        """
        if n < 1:
            raise ValueError("n should be a positive integer")
        # pylint: disable=protected-access
        return self._cderivative(first, prev, prev_control, self.__check_t(t), n)

    def derivative(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        t: Optional[float] = None,
        n: int = 1,
    ) -> Vector2d:
        """Returns the nth derivative of the segment at t as a :class:`Vector2D`.

        .. versionadded:: 1.4
        """
        return Vector2d(
            self.cderivative(
                complex(first or 0),
                complex(prev or 0),
                complex(prev_control or 0),
                t,
                n,
            )
        )

    @abc.abstractmethod
    def _cderivative(
        self, first: complex, prev: complex, prev_control: complex, t: float, n: int = 1
    ) -> complex: ...

    def cunit_tangent(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t: Optional[float] = None,
    ) -> complex:
        """Returns the unit tangent of the segment at t as a complex number.

        ..versionadded:: 1.4
        """
        return self._cunit_tangent(first, prev, prev_control, self.__check_t(t))

    def unit_tangent(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        t: Optional[float] = None,
    ) -> Vector2d:
        """Returns the unit tangent of the segment at t as a :class:`Vector2D`.

        ..versionadded:: 1.4
        """
        return Vector2d(
            self.cunit_tangent(
                complex(first or 0), complex(prev or 0), complex(prev_control or 0), t
            )
        )

    def _cunit_tangent(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        dseg = self._cderivative(first, prev, t, 1)
        return dseg / abs(dseg)

    def cnormal(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t: Optional[float] = None,
    ) -> complex:
        """Returns the (right-hand-rule) normal vector of the segment at t as a complex
        number.

        ..versionadded:: 1.4
        """
        return self.cunit_tangent(first, prev, prev_control, t) * 1j

    def normal(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        t: Optional[float] = None,
    ) -> Vector2d:
        """Returns the (right-hand-rule) normal vector of the segment at t as
        :class:`Vector2D`.

        ..versionadded:: 1.4
        """
        return Vector2d(
            self.cnormal(
                complex(first or 0), complex(prev or 0), complex(prev_control or 0), t
            )
        )

    def curvature(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        t: Optional[float] = None,
    ) -> float:
        """Returns the curvature of the segment at t.

        ..versionadded:: 1.4
        """
        # pylint: disable=protected-access
        return self._curvature(
            complex(first or 0),
            complex(prev or 0),
            complex(prev_control or 0),
            self.__check_t(t),
        )

    @abc.abstractmethod
    def _curvature(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> float: ...

    # Point evaluation, splitting
    def cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex:
        """Returns the coordinates of the Bezier curve evaluated at t as complex number.

        .. versionadded:: 1.4"""
        return self._cpoint(first, prev, prev_control, self.__check_t(t, False))

    def point(
        self, first: ComplexLike, prev: ComplexLike, prev_control: ComplexLike, t: float
    ) -> Vector2d:
        """Returns the coordinates of the Bezier curve evaluated at t as :class:`Vector2d`.

        .. versionadded:: 1.4"""
        return Vector2d(
            self.cpoint(
                complex(first or 0), complex(prev or 0), complex(prev_control or 0), t
            )
        )

    @abc.abstractmethod
    def _cpoint(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> complex: ...

    def split(
        self, first: ComplexLike, prev: ComplexLike, prev_control: ComplexLike, t: float
    ) -> Tuple[PathCommand, PathCommand]:
        """Returns two segments, whose union is this segment and which join at
        self.point(t).

        .. versionadded:: 1.4"""
        # no simplification here, we want to preserve the original type
        return self._split(
            complex(first),
            complex(prev),
            complex(prev_control),
            self.__check_t(t, False),
        )

    @abc.abstractmethod
    def _split(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> Tuple[PathCommand, PathCommand]: ...

    # Line integration

    def length(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        t0: float = 0,
        t1: float = 1,
        settings=LengthSettings(),
    ) -> float:
        """Returns the length of the segment between t0 and t1.

        .. versionadded:: 1.4"""
        # pylint: disable=protected-access
        return self._length(
            complex(first),
            complex(prev),
            complex(prev_control),
            self.__check_t(t0, False),
            self.__check_t(t1, False),
            settings,
        )

    @abc.abstractmethod
    def _length(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t0: float = 0,
        t1: float = 1,
        settings=LengthSettings(),
    ) -> float: ...

    def ilength(
        self,
        first: ComplexLike,
        prev: ComplexLike,
        prev_control: ComplexLike,
        length: float,
        settings: ILengthSettings = ILengthSettings(),
    ):
        """Returns a float ``t``, such that ``self.length(0, t)`` is approximately
        ``length``.

        .. versionadded:: 1.4"""
        # pylint: disable=protected-access
        return self._ilength(
            complex(first), complex(prev), complex(prev_control), length, settings
        )

    @abc.abstractmethod
    def _ilength(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        length: float,
        settings: ILengthSettings = ILengthSettings(),
    ): ...


class RelativePathCommand(PathCommand):
    """
    Abstract base class for relative path commands.

    Implements most of methods of :py:class:`PathCommand` through
    conversion to :py:class:`AbsolutePathCommand`
    """

    @property
    def is_relative(self):
        return True

    @property
    def is_absolute(self):
        return False

    def to_relative(self, prev: ComplexLike) -> RelativePathCommand:
        return self.__class__(*self.args)

    def update_bounding_box(self, first, last_two_points, bbox):
        self.to_absolute(last_two_points[-1]).update_bounding_box(
            first, last_two_points, bbox
        )


class AbsolutePathCommand(PathCommand):
    """Absolute path command. Unlike :py:class:`RelativePathCommand` can be transformed
    directly."""

    @property
    def is_relative(self):
        return False

    @property
    def is_absolute(self):
        return True

    def to_absolute(self, prev: ComplexLike) -> AbsolutePathCommand:
        return self.__class__(*self.args)

    @abc.abstractmethod
    def transform(self, transform: Transform) -> AbsolutePathCommand:
        """Returns new transformed segment

        :param transform: a transformation to apply
        """

    def rotate(self, degrees: float, center: Vector2d) -> AbsolutePathCommand:
        """
        Returns new transformed segment

        :param degrees: rotation angle in degrees
        :param center: invariant point of rotation
        """
        return self.transform(Transform(rotate=(degrees, center[0], center[1])))

    def translate(self, dr: Vector2d) -> AbsolutePathCommand:
        """Translate or scale this path command by dr"""
        return self.transform(Transform(translate=dr))

    def scale(self, factor: Union[float, Tuple[float, float]]) -> AbsolutePathCommand:
        """Returns new transformed segment

        :param factor: scale or (scale_x, scale_y)
        """
        return self.transform(Transform(scale=factor))


class BezierArcComputationMixin:
    """Functionality that works the same way for Arcs, Cubic and Quadratic

    .. versionadded:: 1.4"""

    _cpoint: Callable[[complex, complex, complex, float], complex]
    _cderivative: Callable[..., complex]
    poly: Callable[[complex, complex, complex, Optional[bool]], np.poly1d]

    def inv_arclength(self, prev, prev_control, s, settings=ILengthSettings()):
        """Ported from https://github.com/mathandy/svgpathtools/blob/19df25b99b405ec4fc7616b58384eca7879b6fd4/svgpathtools/path.py#L541
        (MIT Licensed)"""
        t_upper = 1
        t_lower = 0
        iteration = 0
        while iteration < settings.maxits:
            iteration += 1
            t = (t_lower + t_upper) / 2
            s_t = self._length(0j, prev, prev_control, t1=t, settings=settings)
            if abs(s_t - s) < settings.length_tol:
                return t
            elif s_t < s:  # t too small
                t_lower = t
            else:  # s < s_t, t too big
                t_upper = t
            if t_upper == t_lower:
                # warn("t is as close as a float can be to the correct value, "
                #        "but |s(t) - s| = {} > s_tol".format(abs(s_t-s)))
                return t
        raise Exception(f"Maximum iterations reached with s(t) - s = {s_t - s}.")

    def segment_length(
        self,
        start,
        end,
        start_point,
        end_point,
        pos_eval,
        settings=LengthSettings(),
        depth=0,
    ):
        """
        Ported from https://github.com/mathandy/svgpathtools/blob/19df25b99b405ec4fc7616b58384eca7879b6fd4/svgpathtools/path.py#L479
        (MIT licensed)
        # TODO better treatment of degenerate beziers from
        # https://github.com/linebender/kurbo/blob/c229a914d303c5989c9e6b1d766def2df27a8185/src/cubicbez.rs#L431
        """
        mid = (start + end) / 2
        mid_point = pos_eval(mid)
        length = abs(end_point - start_point)
        first_half = abs(mid_point - start_point)
        second_half = abs(end_point - mid_point)

        length2 = first_half + second_half
        if (length2 - length > settings.error) or (depth < settings.min_depth):
            # Calculate the length of each segment:
            depth += 1
            return self.segment_length(
                start, mid, start_point, mid_point, pos_eval, settings, depth
            ) + self.segment_length(
                mid, end, mid_point, end_point, pos_eval, settings, depth
            )
        # This is accurate enough.
        return length2

    def segment_curvature(self, prev: complex, prev_prev: complex, t: float):
        """Returns the curvature of the segment at t.

        Ported from https://github.com/mathandy/svgpathtools/blob/19df25b99b405ec4fc7616b58384eca7879b6fd4/svgpathtools/path.py#L386
        (MIT licensed)
        """

        dz = self._cderivative(0j, prev, prev_prev, t)
        ddz = self._cderivative(0j, prev, prev_prev, t, n=2)
        dx, dy = dz.real, dz.imag
        ddx, ddy = ddz.real, ddz.imag
        try:
            kappa = abs(dx * ddy - dy * ddx) / math.sqrt(dx * dx + dy * dy) ** 3
        except (ZeroDivisionError, FloatingPointError):
            # tangent vector is zero at t, use polytools to find limit
            p = self.poly(0j, prev, prev_prev, False)
            dp = p.deriv()
            ddp = dp.deriv()
            dx2, dy2 = np.real(dp), np.imag(dp)
            ddx2, ddy2 = np.real(ddp), np.imag(ddp)
            f2 = (dx2 * ddy2 - dy2 * ddx2) ** 2
            g2 = (dx2 * dx2 + dy2 * dy2) ** 3
            lim2 = rational_limit(f2, g2, t)
            if lim2 < 0:  # impossible, must be numerical error
                return 0
            kappa = math.sqrt(lim2)
        return kappa

    def _length(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        t0=0,
        t1=1,
        settings=LengthSettings(),
    ) -> float:
        return self.segment_length(
            t0,
            t1,
            self._cpoint(first, prev, prev_control, t0),
            self._cpoint(first, prev, prev_control, t1),
            lambda t: self._cpoint(first, prev, prev_control, t),
            settings,
            0,
        )

    def _ilength(
        self,
        first: complex,
        prev: complex,
        prev_control: complex,
        length,
        settings=ILengthSettings(),
    ):
        return self.inv_arclength(prev, prev_control, length, settings)

    def _curvature(
        self, first: complex, prev: complex, prev_control: complex, t: float
    ) -> float:
        return self.segment_curvature(prev, prev_control, t)


class BezierComputationMixin:
    """Functionality that works the same for all Beziers (Quadratic, Cubic)

    .. versionadded:: 1.4"""

    def _bpoints(self, prev, prev_prev):
        return (prev,) + self.ccontrol_points(0j, prev, prev_prev)

    def bezier_unit_tangent(self, prev, prev_prev, t):
        """Returns the unit tangent of the segment at t.

        Ported from https://github.com/mathandy/svgpathtools/blob/19df25b99b405ec4fc7616b58384eca7879b6fd4/svgpathtools/path.py#L348
        (MIT licensed)"""

        dseg = self._cderivative(0j, prev, prev_prev, t)

        try:
            unit_tangent = dseg / abs(dseg)
        except (ZeroDivisionError, FloatingPointError):
            # This may be a removable singularity, if so we just need to compute
            # the limit.
            # Note: limit{{dseg / abs(dseg)} = sqrt(limit{dseg**2 / abs(dseg)**2})
            dseg_poly = self.poly(prev, prev_prev).deriv()
            dseg_abs_squared_poly = np.real(dseg_poly) ** 2 + np.imag(dseg_poly) ** 2
            try:
                unit_tangent = np.sqrt(
                    rational_limit(dseg_poly**2, dseg_abs_squared_poly, t)
                )
            except ValueError:
                bef = self.poly(prev, prev_prev).deriv()(t - 1e-4)
                aft = self.poly(prev, prev_prev).deriv()(t + 1e-4)
                mes = (
                    "Unit tangent appears to not be well-defined at "
                    f"t = {t}, \n"
                    f"seg.poly().deriv()(t - 1e-4) = {bef}\n"
                    f"seg.poly().deriv()(t + 1e-4) = {aft}"
                )
                raise ValueError(mes)
        return unit_tangent
