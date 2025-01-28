# coding=utf-8
#
# Copyright (C) 2006 Jean-Francois Barraud, barraud@math.univ-lille1.fr
# Copyright (C) 2010 Alvin Penner, penner@vaxxine.com
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
# barraud@math.univ-lille1.fr
#
# This code defines several functions to make handling of transform
# attribute easier.
#
"""
Provide transformation parsing to extensions
"""

from __future__ import annotations
import re
from decimal import Decimal
from math import cos, radians, sin, sqrt, tan, fabs, atan2, hypot, pi, isfinite
from typing import (
    overload,
    cast,
    Callable,
    Generator,
    Iterator,
    Tuple,
    Union,
    Optional,
    List,
)
import cmath


from .utils import strargs, KeyDict


VectorLike = Union["ImmutableVector2d", Tuple[float, float], complex]  # pylint: disable=invalid-name
ComplexLike = Union[complex, "Vector2d"]  # pylint: disable=invalid-name
MatrixLike = Union[
    str,
    Tuple[Tuple[float, float, float], Tuple[float, float, float]],
    Tuple[float, float, float, float, float, float],
    "Transform",
]
BoundingIntervalArgs = Union["BoundingInterval", Tuple[float, float], float]  # pylint: disable=invalid-name

# All the names that get added to the inkex API itself.
__all__ = (
    "BoundingBox",
    "DirectedLineSegment",
    "ImmutableVector2d",
    "Transform",
    "Vector2d",
)


# Old settings, supported because users click 'ok' without looking.
XAN = KeyDict({"l": "left", "r": "right", "m": "center_x"})
YAN = KeyDict({"t": "top", "b": "bottom", "m": "center_y"})
# Anchoring objects with given directions (see inx options)
CUSTOM_DIRECTION = {270: "tb", 90: "bt", 0: "lr", 360: "lr", 180: "rl"}
DIRECTION = ["tb", "bt", "lr", "rl", "ro", "ri"]


class ImmutableVector2d:
    """Represents an immutable element of 2-dimensional Euclidean space"""

    _x = 0.0
    _y = 0.0

    x = property(lambda self: self._x)
    y = property(lambda self: self._y)

    @overload
    def __init__(self):
        pass

    @overload
    def __init__(
        self,
        v: Union[VectorLike, str],
        fallback: Optional[Union[VectorLike, str]] = None,
    ):
        pass

    @overload
    def __init__(self, x: float, y: float):
        pass

    def __init__(self, *args, fallback=None):
        try:
            x, y = self.c2t(complex(*args))
        except (ValueError, TypeError):
            try:
                if len(args) == 0:
                    x, y = 0.0, 0.0
                elif len(args) == 1:
                    x, y = self._parse(args[0])
                elif len(args) == 2:
                    x, y = map(float, args)
                else:
                    raise ValueError("too many arguments")
            except (ValueError, TypeError) as error:
                if fallback is None:
                    raise ValueError(
                        "Cannot parse vector and no fallback given"
                    ) from error
                x, y = ImmutableVector2d(fallback)
        self._x, self._y = float(x), float(y)

    @staticmethod
    def _parse(point: Union[VectorLike, float, str]) -> Tuple[float, float]:
        if isinstance(point, complex):
            x, y = point.real, point.imag
        elif isinstance(point, ImmutableVector2d):
            x, y = point._x, point._y
        elif isinstance(point, (tuple, list)) and len(point) == 2:
            x, y = map(float, point)
        elif isinstance(point, str) and point.count(",") == 1:
            x, y = map(float, point.split(","))
        else:
            raise ValueError(f"Can't parse {repr(point)}")
        return x, y

    def __complex__(self) -> complex:
        return complex(self._x, self._y)

    def __eq__(self, other) -> bool:
        if isinstance(other, (ImmutableVector2d, tuple, complex)):
            other = Vector2d(other)
            return self._x == other._x and self._y == other._y
        return False

    def __add__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        return Vector2d(self._x + other._x, self._y + other._y)

    def __radd__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        return Vector2d(self._x + other._x, self._y + other._y)

    def __sub__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        return Vector2d(self._x - other._x, self._y - other._y)

    def __rsub__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        return Vector2d(other._x - self._x, other._y - self._y)

    def __neg__(self) -> Vector2d:
        return Vector2d(-self._x, -self._y)

    def __pos__(self) -> Vector2d:
        return Vector2d(self._x, self._y)

    def __floordiv__(self, factor: float) -> Vector2d:
        return Vector2d(self._x / float(factor), self._y / float(factor))

    def __truediv__(self, factor: float) -> Vector2d:
        return Vector2d(self._x / float(factor), self._y / float(factor))

    def __div__(self, factor: float) -> Vector2d:
        return Vector2d(self._x / float(factor), self._y / float(factor))

    def __mul__(self, factor: float) -> Vector2d:
        return Vector2d(self._x * factor, self._y * factor)

    def __abs__(self) -> float:
        return self.length

    def __rmul__(self, factor: float) -> Vector2d:
        return Vector2d(self._x * factor, self._y * factor)

    def __repr__(self) -> str:
        return f"Vector2d({self._x:.6g}, {self._y:.6g})"

    def __str__(self) -> str:
        return f"{self._x:.6g}, {self._y:.6g}"

    def __iter__(self) -> Generator[float, None, None]:
        yield self._x
        yield self._y

    def __len__(self) -> int:
        return 2

    def __getitem__(self, item: int) -> float:
        return (self._x, self._y)[item]

    def to_tuple(self) -> Tuple[float, float]:
        """A tuple of the vector's components"""
        return cast(Tuple[float, float], tuple(self))

    def to_polar_tuple(self) -> Tuple[float, Optional[float]]:
        """A tuple of the vector's magnitude and direction

        .. versionadded:: 1.1"""
        return self.length, self.angle

    def dot(self, other: VectorLike) -> float:
        """Multiply Vectors component-wise"""
        other = Vector2d(other)
        return self._x * other._x + self._y * other._y

    def cross(self, other: VectorLike) -> float:
        """Z component of the cross product of the vectors extended into 3D

        .. versionadded:: 1.1"""
        other = Vector2d(other)
        return self._x * other._y - self._y * other._x

    def is_close(
        self,
        other: Union[VectorLike, str, Tuple[float, float]],
        rtol: float = 1e-5,
        atol: float = 1e-8,
    ) -> float:
        """Checks if two vectors are (almost) identical, up to both absolute and
        relative tolerance."""
        return cmath.isclose(self, Vector2d(other), rel_tol=rtol, abs_tol=atol)

    @property
    def length(self) -> float:
        """Returns the length of the vector"""
        return abs(complex(self))

    @property
    def angle(self) -> Optional[float]:
        """The angle of the vector when represented in polar coordinates

        .. versionadded:: 1.1"""
        if self._x == 0 and self._y == 0:
            return None
        return atan2(self._y, self._x)

    @staticmethod
    def from_polar(radius: float, theta: Optional[float] = None) -> Optional[Vector2d]:
        """Creates a Vector2d from polar coordinates

        None is returned when theta is None and radius is not zero.

        .. versionadded:: 1.1
        """
        if radius == 0.0:
            return Vector2d(0.0, 0.0)
        if theta is not None:
            return Vector2d(cmath.rect(radius, theta))
        return None

    @staticmethod
    def c2t(c: complex) -> List[float]:
        """Complex to tuple"""
        return [c.real, c.imag]

    @staticmethod
    def t2c(tup: Tuple[float, float]) -> complex:
        """Tuple to complex"""
        return tup[0] + 1j * tup[1]


class Vector2d(ImmutableVector2d):
    """Represents an element of 2-dimensional Euclidean space"""

    @ImmutableVector2d.x.setter
    def x(self, value: Union[float, int, str]) -> None:
        self._x = float(value)

    @ImmutableVector2d.y.setter
    def y(self, value: Union[float, int, str]) -> None:
        self._y = float(value)

    def __iadd__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        self._x, self._y = self._x + other._x, self._y + other._y
        return self

    def __isub__(self, other: VectorLike) -> Vector2d:
        other = Vector2d(other)
        self._x, self._y = self._x - other._x, self._y - other._y
        return self

    def __imul__(self, factor: float) -> Vector2d:
        self._x, self._y = self._x * factor, self._y * factor
        return self

    def __idiv__(self, factor: float) -> Vector2d:
        self._x, self._y = self._x / float(factor), self._y / float(factor)
        return self

    def __itruediv__(self, factor: float) -> Vector2d:
        self._x, self._y = self._x / float(factor), self._y / float(factor)
        return self

    def __ifloordiv__(self, factor: float) -> Vector2d:
        self._x, self._y = self._x / float(factor), self._y / float(factor)
        return self

    @overload
    def assign(self, x: float, y: float) -> VectorLike:
        pass

    @overload
    def assign(self, other: Union[VectorLike, str]) -> VectorLike:
        pass

    def assign(self, *args):
        """Assigns a different vector in place"""
        self._x, self._y = Vector2d(*args)
        return self


class Transform:
    r"""A transformation object which will always reduce to a matrix and can
    then be used in combination with other transformations for reducing
    finding a point and printing svg ready output.

    Use with svg transform attribute input:

      tr = Transform("scale(45, 32)")

    Use with triad matrix input (internal representation):

      tr = Transform(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))

    Use with hexad matrix input (i.e. svg matrix(...)):

      tr = Transform((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))

    Once you have a transformation you can operate tr * tr to compose,
    any of the above inputs are also valid operators for composing.

    .. versionchanged:: 1.4
    
        Internally, the values are stored as complex values. For the hexad
        ``(a, c, e), (b, d, f)`` we store:

        .. math::

            a_1 &= \frac{a+d}{2} + j \frac{b-c}{2} \\
            a_2 &= \frac{a-d}{2} + j \frac{b+c}{2} \\
            a_3 &= e + f j
        
        This makes application to another vector a multiplication / addition on 
        primitives: :math:`a_1p + a_2 \bar{p} + a_3`

        As with paths, this performance benefit is best reaped by using the methods
        prefixed with "c", such as :func:`capply_to_point` (which is also what
        :func:`inkex.paths.Path.transform` uses internally).

    """

    arg1: complex = 1 + 0j
    arg2: complex = 0 + 0j
    arg3: complex = 0 + 0j
    callback: Callable = lambda *args: args[0]

    TRM = re.compile(r"(translate|scale|rotate|skewX|skewY|matrix)\s*\(([^)]*)\)\s*,?")
    absolute_tolerance = 1e-5  # type: float

    @property
    def matrix(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Get the matrix of the transform."""
        return (
            (
                (self.arg1 + self.arg2).real,
                (self.arg2 - self.arg1).imag,
                self.arg3.real,
            ),
            (
                (self.arg1 + self.arg2).imag,
                (self.arg1 - self.arg2).real,
                self.arg3.imag,
            ),
        )

    def __init__(self, *args, element=None, **kwargs) -> None:
        if len(args) == 3:
            # Shortcut for complex initializer
            self.arg1, self.arg2, self.arg3 = args
            self.callback = kwargs.get("callback", self.callback)
            return

        matrix = callback = None
        if len(args) > 0:
            matrix = args[0]
        if len(args) > 1:
            callback = args[1]

        matrix = kwargs.pop("matrix", matrix)
        callback = kwargs.pop("callback", callback)

        if matrix is not None:
            self._set_matrix(matrix)

        self.add_kwargs(**kwargs)
        # Set callback last, so it doesn't kick off just setting up the internal value
        if callback is not None:
            self.callback = callback

    def _set_matrix(self, matrix: MatrixLike) -> None:
        """Parse a given string as an svg transformation instruction.

        .. versionadded:: 1.1"""
        if isinstance(matrix, str):
            for func, values in self.TRM.findall(matrix.strip()):
                getattr(self, "add_" + func.lower())(*strargs(values))
        elif isinstance(matrix, Transform):
            self.arg1, self.arg2, self.arg3 = matrix.arg1, matrix.arg2, matrix.arg3
        elif isinstance(matrix, (tuple, list)):
            try:
                a, c, e = map(float, matrix[0])  # type: ignore
                b, d, f = map(float, matrix[1])  # type: ignore
            except TypeError:  # Could be 1x6 matrix instead
                try:
                    a, b, c, d, e, f = map(float, matrix)  # type: ignore
                except TypeError:
                    raise ValueError(
                        f"Matrix '{matrix}' is not a valid transformation matrix"
                    )
            self.arg1 = (a + d) / 2 + 1j * (b - c) / 2
            self.arg2 = (a - d) / 2 + 1j * (b + c) / 2
            self.arg3 = e + f * 1j
        else:
            raise ValueError(f"Invalid transform type: {type(matrix).__name__}")

    # These provide quick access to the svg matrix:
    #
    # [ a, c, e ]
    # [ b, d, f ]
    #
    # pylint: disable=invalid-name
    a = property(lambda self: (self.arg1 + self.arg2).real)
    b = property(lambda self: (self.arg1 + self.arg2).imag)
    c = property(lambda self: (self.arg2 - self.arg1).imag)
    d = property(lambda self: (self.arg1 - self.arg2).real)
    e = property(lambda self: self.arg3.real)
    f = property(lambda self: self.arg3.imag)
    # pylint: enable=invalid-name

    def __bool__(self) -> bool:
        return not self.__eq__(Transform())

    __nonzero__ = __bool__

    @overload
    def add_matrix(self, a: MatrixLike) -> Transform: ...

    @overload
    def add_matrix(  # pylint: disable=too-many-arguments
        self, a: float, b: float, c: float, d: float, e: float, f: float
    ) -> Transform: ...

    @overload
    def add_matrix(
        self, a: Tuple[float, float, float], b: Tuple[float, float, float]
    ) -> Transform: ...

    def add_matrix(self, *args):
        """Add matrix in order they appear in the svg hexad"""
        if len(args) == 1:
            t = Transform(args[0])
        elif len(args) == 2 or len(args) == 6:
            t = Transform(args)
        else:
            raise ValueError(f"Invalid number of arguments {args}")
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(t.arg1, t.arg2, t.arg3)
        self.callback(self)
        return self

    def add_kwargs(self, **kwargs):
        """Add translations, scales, rotations etc using key word arguments"""
        for key, value in reversed(list(kwargs.items())):
            func = getattr(self, "add_" + key)
            if isinstance(value, tuple):
                func(*value)
            elif value is not None:
                func(value)
        return self

    @overload
    def add_translate(self, dr: VectorLike) -> Transform: ...

    @overload
    def add_translate(self, tr_x: float, tr_y: float = 0.0) -> Transform: ...

    def add_translate(self, *args):
        """Add translate to this transformation"""
        tr = Vector2d(*args)
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(1, 0, complex(tr))
        if self.callback is None:
            pass
        self.callback(self)
        return self

    def add_scale(self, sc_x: float, sc_y: Optional[float] = None) -> Transform:
        """Add scale to this transformation"""
        sc_x = float(sc_x)
        sc_y = sc_x if sc_y is None else float(sc_y)
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(
            (sc_x + sc_y) / 2, (sc_x - sc_y) / 2, 0
        )
        self.callback(self)
        return self

    @overload
    def add_rotate(self, deg: float, center: VectorLike): ...

    @overload
    def add_rotate(self, deg: float, center_x: float, center_y: float): ...

    @overload
    def add_rotate(self, deg: float) -> Transform: ...

    @overload
    def add_rotate(self, deg: float, a: Union[VectorLike, str]) -> Transform: ...

    @overload
    def add_rotate(self, deg: float, a: float, b: float) -> Transform: ...

    def add_rotate(self, deg, *args):
        """Add rotation to this transformation"""
        c = complex(Vector2d(*args))
        _cos, _sin = cos(radians(deg)), sin(radians(deg))
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(_cos + 1j * _sin, 0, c)
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(1 + 0j, 0 + 0j, -c)
        self.callback(self)
        return self

    def add_skewx(self, deg: float) -> Transform:
        """Add skew x to this transformation, and return it"""
        ttan = tan(radians(deg)) / 2
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(
            1 - ttan * 1j, 0 + ttan * 1j, 0 + 0j
        )
        self.callback(self)
        return self

    def add_skewy(self, deg: float) -> Transform:
        """Add skew y to this transformation, and return it"""
        ttan = tan(radians(deg)) / 2
        self.arg1, self.arg2, self.arg3 = self.__fastmatmul(
            1 + ttan * 1j, 0 + ttan * 1j, 0 + 0j
        )
        self.callback(self)
        return self

    def to_hexad(self) -> Tuple[float, float, float, float, float, float]:
        """Returns the transform as a hexad matrix (used in svg)"""
        return (self.a, self.b, self.c, self.d, self.e, self.f)

    def is_translate(self, exactly: bool = False) -> bool:
        """Returns True if this transformation is ONLY translate"""
        tol = self.absolute_tolerance if not exactly else 0.0
        return (
            fabs(self.a - 1) <= tol
            and abs(self.d - 1) <= tol
            and fabs(self.b) <= tol
            and fabs(self.c) <= tol
        )

    def is_scale(self, exactly=False):
        # type: (bool) -> bool
        """Returns True if this transformation is ONLY scale"""
        tol = self.absolute_tolerance if not exactly else 0.0
        return (
            fabs(self.e) <= tol
            and fabs(self.f) <= tol
            and fabs(self.b) <= tol
            and fabs(self.c) <= tol
        )

    def is_rotate(self, exactly=False):
        # type: (bool) -> bool
        """Returns True if this transformation is ONLY rotate"""
        tol = self.absolute_tolerance if not exactly else 0.0
        return (
            self._is_URT(exactly=exactly)
            and fabs(self.e) <= tol
            and fabs(self.f) <= tol
            and fabs(self.a**2 + self.b**2 - 1) <= tol
        )

    def rotation_degrees(self):
        # type: () -> float
        """Return the amount of rotation in this transform"""
        if not self._is_URT(exactly=False):
            raise ValueError(
                "Rotation angle is undefined for non-uniformly scaled or skewed "
                "matrices"
            )
        return atan2(self.b, self.a) * 180 / pi

    def __str__(self):
        # type: () -> str
        """Format the given matrix into a string representation for svg"""
        hexad = self.to_hexad()
        if self.is_translate():
            if not self:
                return ""
            return f"translate({self.e:.6g}, {self.f:.6g})"
        if self.is_scale():
            return f"scale({self.a:.6g}, {self.d:.6g})"
        if self.is_rotate():
            return f"rotate({self.rotation_degrees():.6g})"
        return f"matrix({' '.join(f'{var:.6g}' for var in hexad)})"

    def __repr__(self) -> str:
        """String representation of this object"""
        return (
            f"{type(self).__name__}(("
            f"({', '.join(f'{var:.6g}' for var in self.matrix[0])}), "
            f"({', '.join(f'{var:.6g}' for var in self.matrix[1])})))"
        )

    def __eq__(self, matrix) -> bool:
        # typing this requires writing a proof for mypy that matrix is really
        # MatrixLike
        """Test if this transformation is equal to the given matrix"""
        if isinstance(matrix, (str, tuple, list, Transform)):
            o = Transform(matrix)
            val = (
                cmath.isclose(o.arg1, self.arg1, abs_tol=self.absolute_tolerance)
                and cmath.isclose(o.arg2, self.arg2, abs_tol=self.absolute_tolerance)
                and cmath.isclose(o.arg3, self.arg3, abs_tol=self.absolute_tolerance)
            )
        else:
            val = False
        return val

    def __fastmatmul(
        self, oa1: complex, oa2: complex, oa3: complex
    ) -> Tuple[complex, complex, complex]:
        """Matrix multiplication without instance checks or transform istantiation

        .. versionadded:: 1.4"""
        return (
            self.arg1 * oa1 + self.arg2 * oa2.conjugate(),
            self.arg1 * oa2 + self.arg2 * oa1.conjugate(),
            self.arg1 * oa3 + self.arg2 * oa3.conjugate() + self.arg3,
        )

    def __matmul__(self, matrix: MatrixLike) -> Transform:
        """Combine this transform's internal matrix with the given matrix"""
        # Conform the input to a known quantity (and convert if needed)
        # Return a transformation as the combined result
        try:
            oa1, oa2, oa3 = matrix.arg1, matrix.arg2, matrix.arg3  # type: ignore
        except AttributeError:
            matrix = Transform(matrix)
            oa1, oa2, oa3 = matrix.arg1, matrix.arg2, matrix.arg3
        return Transform(*self.__fastmatmul(oa1, oa2, oa3))

    def __imatmul__(self, matrix: MatrixLike) -> Transform:
        """In place multiplication of transform matrices"""
        tmp = self @ matrix
        self.arg1, self.arg2, self.arg3 = tmp.arg1, tmp.arg2, tmp.arg3
        self.callback(self)
        return self

    def __neg__(self) -> Transform:
        """Returns an inverted transformation"""
        det = (self.arg1 * self.arg1.conjugate()) - (self.arg2 * self.arg2.conjugate())

        # invert the rotation/scaling part
        na1 = self.arg1.conjugate() / det
        na2 = -(self.arg2 / det)
        # invert the translational part
        na3 = -na1 * self.arg3 - na2 * self.arg3.conjugate()
        return Transform(na1, na2, na3)

    def capply_to_point(self, point: complex) -> complex:
        """Transform a tuple (X, Y), return a complex

        .. versionadded:: 1.4"""
        return self.arg1 * point + self.arg2 * point.conjugate() + self.arg3

    def apply_to_point(self, point: VectorLike) -> Vector2d:
        """Transform a vector (X, Y)"""
        return Vector2d(self.capply_to_point(complex(Vector2d(point))))

    def _is_URT(self, exactly=False):
        # type: (bool) -> bool
        """
        Checks that transformation can be decomposed into product of
        Uniform scale (U), Rotation around origin (R) and translation (T)

        :return: decomposition as U*R*T is possible
        """
        tol = self.absolute_tolerance if not exactly else 0.0
        return (fabs(self.a - self.d) <= tol) and (fabs(self.b + self.c) <= tol)

    def interpolate(self, other, fraction):
        # type: (Transform, float) -> Transform
        """Interpolate with another Transform.

        .. versionadded:: 1.1
        """
        from .tween import TransformInterpolator

        return TransformInterpolator(self, other).interpolate(fraction)


class BoundingInterval:  # pylint: disable=too-few-public-methods
    """A pair of numbers that represent the minimum and maximum values."""

    @overload
    def __init__(self, x: Optional[BoundingInterval] = None) -> None:
        pass

    @overload
    def __init__(self, x: Tuple[float, float]) -> None:
        pass

    @overload
    def __init__(self, x: float) -> None:
        pass

    @overload
    def __init__(self, x: float, y: float) -> None:
        pass

    def __init__(
        self,
        x: Union[Optional[BoundingInterval], Tuple[float, float], float] = None,
        y: Optional[float] = None,
    ) -> None:
        self.x: Union[int, float, Decimal]
        self.y: Union[int, float, Decimal]
        self.minimum: float
        self.maximum: float
        if y is not None:
            if isinstance(x, (int, float, Decimal)) and isinstance(
                y, (int, float, Decimal)
            ):
                self.minimum = float(x)
                self.maximum = float(y)
            else:
                raise ValueError(
                    f"Not a number for scaling: {str((x, y))} "
                    f"({type(x).__name__},{type(y).__name__})"
                )

        else:
            value = x
            if value is None:
                # identity for addition, zero for intersection
                self.minimum, self.maximum = float("+inf"), float("-inf")
            elif isinstance(value, BoundingInterval):
                self.minimum = value.minimum
                self.maximum = value.maximum
            elif isinstance(value, (tuple, list)) and len(value) == 2:
                self.minimum, self.maximum = min(value), max(value)
            elif isinstance(value, (int, float, Decimal)):
                self.minimum = self.maximum = float(value)
            else:
                raise ValueError(
                    f"Not a number for scaling: {str(value)} ({type(value).__name__})"
                )

    def __bool__(self):
        # type: () -> bool
        return isfinite(self.minimum) and isfinite(self.maximum)

    __nonzero__ = __bool__

    def __neg__(self):
        # type: () -> BoundingInterval
        return BoundingInterval((-1 * self.maximum, -1 * self.minimum))

    def __add__(self, other):
        # type: (BoundingInterval) -> BoundingInterval
        """Calculate the bounding interval that covers both given bounding intervals"""
        new = BoundingInterval(self)
        if other is not None:
            new += other
        return new

    def __iadd__(self, other):
        # type: (BoundingInterval) -> BoundingInterval
        other = BoundingInterval(other)
        self.minimum = min((self.minimum, other.minimum))
        self.maximum = max((self.maximum, other.maximum))
        return self

    def __radd__(self, other):
        # type: (BoundingInterval) -> BoundingInterval
        if other is None:
            return BoundingInterval(self)
        return self + other

    def __and__(self, other: BoundingInterval) -> BoundingInterval:
        """Calculate the bounding interval where both given bounding intervals
        overlap"""
        new = BoundingInterval(self)
        if other is not None:
            new &= other
        return new

    def __iand__(self, other):
        # type: (BoundingInterval) -> BoundingInterval
        other = BoundingInterval(other)
        self.minimum = max((self.minimum, other.minimum))
        self.maximum = min((self.maximum, other.maximum))
        if self.minimum > self.maximum:
            self.minimum, self.maximum = float("+inf"), float("-inf")
        return self

    def __rand__(self, other):
        # type: (BoundingInterval) -> BoundingInterval
        if other is None:
            return BoundingInterval(self)
        return self & other

    def __mul__(self, other: float) -> BoundingInterval:
        new = BoundingInterval(self)
        if other is not None:
            new *= other
        return new

    def __imul__(self, other: float) -> BoundingInterval:
        self.minimum *= other
        self.maximum *= other
        return self

    def __iter__(self) -> Generator[float, None, None]:
        yield self.minimum
        yield self.maximum

    def __eq__(self, other) -> bool:
        return tuple(self) == tuple(BoundingInterval(other))

    def __contains__(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum

    def __repr__(self) -> str:
        return f"BoundingInterval({self.minimum}, {self.maximum})"

    @property
    def center(self):
        # type: () -> float
        """Pick the middle of the line"""
        return self.minimum + ((self.maximum - self.minimum) / 2)

    @property
    def size(self):
        # type: () -> float
        """Return the size difference minimum and maximum"""
        return self.maximum - self.minimum


class BoundingBox:  # pylint: disable=too-few-public-methods
    """
    Some functions to compute a rough bbox of a given list of objects.

    BoundingBox(other)
    BoundingBox(x, y)
    BoundingBox((x1, x2), (y1, y2))
    """

    width = property(lambda self: self.x.size)
    height = property(lambda self: self.y.size)
    top = property(lambda self: self.y.minimum)
    left = property(lambda self: self.x.minimum)
    bottom = property(lambda self: self.y.maximum)
    right = property(lambda self: self.x.maximum)
    center_x = property(lambda self: self.x.center)
    center_y = property(lambda self: self.y.center)
    diagonal_length = property(lambda self: (self.width**2 + self.height**2) ** (0.5))

    @overload
    def __init__(self, other=None):
        # type: (Optional[BoundingBox]) -> None
        pass

    @overload
    def __init__(self, x, y):
        # type: (BoundingIntervalArgs, BoundingIntervalArgs) -> None
        pass

    def __init__(self, x=None, y=None):
        if y is None:
            if x is None:
                # identity for addition, zero for intersection
                pass
            elif isinstance(x, BoundingBox):
                x, y = x.x, x.y
            else:
                raise ValueError(
                    f"Not a number for scaling: {str(x)} ({type(x).__name__})"
                )
        self.x = BoundingInterval(x)
        self.y = BoundingInterval(y)

    @staticmethod
    def new_xywh(x: float, y: float, width: float, height: float) -> BoundingBox:
        """Create a bounding box using x, y, width and height

        .. versionadded:: 1.2"""
        return BoundingBox((x, x + width), (y, y + height))

    def __bool__(self):
        # type: () -> bool
        return bool(self.x) and bool(self.y)

    __nonzero__ = __bool__

    def __neg__(self):
        # type: () -> BoundingBox
        return BoundingBox(-self.x, -self.y)

    def __add__(self, other):
        # type: (Optional[BoundingBox]) -> BoundingBox
        """Calculate the bounding box that covers both given bounding boxes"""
        new = BoundingBox(self)
        new += BoundingBox(other)
        return new

    def __iadd__(self, other):
        # type: (Optional[BoundingBox]) -> BoundingBox
        other = BoundingBox(other)
        self.x += other.x
        self.y += other.y
        return self

    def __radd__(self, other):
        # type: (Optional[BoundingBox]) -> BoundingBox
        return self + other

    def __and__(self, other):
        # type: (Optional[BoundingBox]) -> BoundingBox
        """Calculate the bounding box where both given bounding boxes overlap"""
        new = BoundingBox(self)
        new &= BoundingBox(other)
        return new

    def __iand__(self, other: Optional[BoundingBox]) -> BoundingBox:
        other = BoundingBox(other)
        self.x = self.x & other.x
        self.y = self.y & other.y
        if not self.x or not self.y:
            self.x, self.y = BoundingInterval(), BoundingInterval()
        return self

    def __rand__(self, other):
        # type: (Optional[BoundingBox]) -> BoundingBox
        return self & other

    def __mul__(self, factor):
        # type: (float) -> BoundingBox
        new = BoundingBox(self)
        new *= factor
        return new

    def __imul__(self, factor):
        # type: (float) -> BoundingBox
        self.x *= factor
        self.y *= factor
        return self

    def __eq__(self, other):
        # type (object) -> bool
        if isinstance(other, BoundingBox):
            return tuple(self) == tuple(other)
        return False

    def __iter__(self) -> Generator[BoundingBox, None, None]:
        yield self.x
        yield self.y

    @property
    def area(self):
        """Return area of the bounding box

        .. versionadded:: 1.2"""
        return self.width * self.height

    @property
    def minimum(self):
        # type: () -> Vector2d
        """Return the minimum x,y coords"""
        return Vector2d(self.x.minimum, self.y.minimum)

    @property
    def maximum(self):
        # type: () -> Vector2d
        """Return the maximum x,y coords"""
        return Vector2d(self.x.maximum, self.y.maximum)

    def __repr__(self):
        # type: () -> str
        return f"BoundingBox({tuple(self.x)},{tuple(self.y)})"

    @property
    def center(self):
        # type: () -> Vector2d
        """Returns the middle of the bounding box"""
        return Vector2d(self.x.center, self.y.center)

    @property
    def size(self):
        """Returns a vector containing width and height of the bounding box

        .. versionadded:: 1.2"""
        return Vector2d(self.x.size, self.y.size)

    def get_anchor(self, xanchor, yanchor, direction=0, selbox=None):
        # type: (str, str, Union[int, str], Optional[BoundingBox]) -> float
        """Calls get_distance with the given anchor options"""
        return self.anchor_distance(
            getattr(self, XAN[xanchor]),
            getattr(self, YAN[yanchor]),
            direction=direction,
            selbox=selbox,
        )

    @staticmethod
    def anchor_distance(
        x: float,
        y: float,
        direction: Union[int, str] = 0,
        selbox: Optional[BoundingBox] = None,
    ) -> float:
        """Using the x,y returns a single sortable value based on direction and angle

        Args:
            x (float): input x coordinate
            y (float): input y coordinate
            direction (Union[int, str], optional): int/float (custom angle),
                tb/bt (top/bottom), lr/rl (left/right), ri/ro (radial). Defaults to 0.
            selbox (Optional[BoundingBox], optional): The bounding box of the whole
                selection for radial anchors. Defaults to None.

        Raises:
            ValueError: if radial distance is requested without the optional selbox
                parameter.

        Returns:
            float: the anchor distance with respect to the direction.
        """

        rot = 0.0
        if isinstance(direction, (int, float)):  # Angle
            if direction not in CUSTOM_DIRECTION:
                return hypot(x, y) * (cos(radians(-direction) - atan2(y, x)))
            direction = CUSTOM_DIRECTION[direction]

        if direction in ("ro", "ri"):
            if selbox is None:
                raise ValueError(
                    "Radial distance not available without selection bounding box"
                )
            rot = hypot(selbox.x.center - x, selbox.y.center - y)

        return [y, -y, x, -x, rot, -rot][DIRECTION.index(direction)]

    def resize(self, delta_x: float, delta_y: Optional[float] = None) -> BoundingBox:
        """Enlarges / shrinks a bounding box by a constant value. If only delta_x
        is given, each side is moved by the same amount; if delta_y is given,
        different deltas are applied to horizontal and vertical intervals.

        .. versionadded:: 1.2"""
        delta_y = delta_y or delta_x
        return BoundingBox(
            (self.x.minimum - delta_x, self.x.maximum + delta_x),
            (self.y.minimum - delta_y, self.y.maximum + delta_y),
        )


class DirectedLineSegment:
    """
    A directed line segment

    DirectedLineSegment(((x0, y0), (x1, y1)))
    """

    start = Vector2d()  # start point of segment
    end = Vector2d()  # end point of segment

    x0 = property(lambda self: self.start.x)  # pylint: disable=invalid-name
    y0 = property(lambda self: self.start.y)  # pylint: disable=invalid-name
    x1 = property(lambda self: self.end.x)
    y1 = property(lambda self: self.end.y)
    dx = property(lambda self: self.vector.x)  # pylint: disable=invalid-name
    dy = property(lambda self: self.vector.y)  # pylint: disable=invalid-name

    @overload
    def __init__(self):
        # type: () -> None
        pass

    @overload
    def __init__(self, other):
        # type: (DirectedLineSegment) -> None
        pass

    @overload
    def __init__(self, start, end):
        # type: (VectorLike, VectorLike) -> None
        pass

    def __init__(self, *args):
        if not args:  # overload 0
            start, end = Vector2d(), Vector2d()
        elif len(args) == 1:  # overload 1
            (other,) = args
            start, end = other.start, other.end
        elif len(args) == 2:  # overload 2
            start, end = args
        else:
            raise ValueError(f"DirectedLineSegment() can't be constructed from {args}")

        self.start = Vector2d(start)
        self.end = Vector2d(end)

    def __eq__(self, other):
        # type: (object) -> bool
        if isinstance(other, (tuple, DirectedLineSegment)):
            return tuple(self) == tuple(other)
        return False

    def __iter__(self):
        # type: () -> Generator[DirectedLineSegment, None, None]
        yield self.x0
        yield self.x1
        yield self.y0
        yield self.y1

    @property
    def vector(self):
        # type: () -> Vector2d
        """The vector of the directed line segment.

        The vector of the directed line segment represents the length
        and direction of segment, but not the starting point.

        .. versionadded:: 1.1
        """
        return self.end - self.start

    @property
    def length(self):
        # type: () -> float
        """Get the length of the line segment"""
        return self.vector.length

    @property
    def angle(self):
        # type: () -> float
        """Get the angle of the line created by this segment"""
        return atan2(self.dy, self.dx)

    def distance_to_point(self, x, y):
        # type: (float, float) -> Union[DirectedLineSegment, Optional[float]]
        """Get the distance to the given point (x, y)"""
        segment2 = DirectedLineSegment(self.start, (x, y))
        dot2 = segment2.dot(self)
        if dot2 <= 0:
            return DirectedLineSegment((x, y), self.start).length
        if self.dot(self) <= dot2:
            return DirectedLineSegment((x, y), self.end).length
        return self.perp_distance(x, y)

    def perp_distance(self, x, y):
        # type: (float, float) -> Optional[float]
        """Perpendicular distance to the given point"""
        if self.length == 0:
            return None
        return fabs((self.dx * (self.y0 - y)) - ((self.x0 - x) * self.dy)) / self.length

    def dot(self, other):
        # type: (DirectedLineSegment) -> float
        """Get the dot product with the segment with another"""
        return self.vector.dot(other.vector)

    def point_at_ratio(self, ratio):
        # type: (float) -> Tuple[float, float]
        """Get the point at the given ratio along the line"""
        return self.x0 + ratio * self.dx, self.y0 + ratio * self.dy

    def point_at_length(self, length):
        # type: (float) -> Tuple[float, float]
        """Get the point as the length along the line"""
        return self.point_at_ratio(length / self.length)

    def parallel(self, x, y):
        # type: (float, float) -> DirectedLineSegment
        """Create parallel Segment"""
        return DirectedLineSegment((x + self.dx, y + self.dy), (x, y))

    def intersect(self, other):
        # type: (DirectedLineSegment) -> Optional[Vector2d]
        """Get the intersection between two segments"""
        other = DirectedLineSegment(other)
        denom = self.vector.cross(other.vector)
        num = other.vector.cross(self.start - other.start)

        if denom != 0:
            return Vector2d(self.point_at_ratio(num / denom))
        return None

    def __repr__(self):
        # type: () -> str
        return f"DirectedLineSegment(({self.start}), ({self.end}))"


def cubic_extrema(py0, py1, py2, py3):
    # type: (float, float, float, float) -> Tuple[float, float]
    """Returns the extreme value, given a set of bezier coordinates"""

    atol = 1e-9
    cmin, cmax = min(py0, py3), max(py0, py3)
    pd1 = py1 - py0
    pd2 = py2 - py1
    pd3 = py3 - py2

    def _is_bigger(point):
        if 0 < point < 1:
            pyx = (
                py0 * (1 - point) * (1 - point) * (1 - point)
                + 3 * py1 * point * (1 - point) * (1 - point)
                + 3 * py2 * point * point * (1 - point)
                + py3 * point * point * point
            )
            return min(cmin, pyx), max(cmax, pyx)
        return cmin, cmax

    if fabs(pd1 - 2 * pd2 + pd3) > atol:
        if pd2 * pd2 > pd1 * pd3:
            pds = sqrt(pd2 * pd2 - pd1 * pd3)
            cmin, cmax = _is_bigger((pd1 - pd2 + pds) / (pd1 - 2 * pd2 + pd3))
            cmin, cmax = _is_bigger((pd1 - pd2 - pds) / (pd1 - 2 * pd2 + pd3))

    elif fabs(pd2 - pd1) > atol:
        cmin, cmax = _is_bigger(-pd1 / (2 * (pd2 - pd1)))

    return cmin, cmax


def quadratic_extrema(py0, py1, py2):
    # type: (float, float, float) -> Tuple[float, float]
    """Returns the extreme value, given a set of quadratic bezier coordinates"""
    atol = 1e-9
    cmin, cmax = min(py0, py2), max(py0, py2)

    def _is_bigger(point):
        if 0 < point < 1:
            pyx = (
                py0 * (1 - point) * (1 - point)
                + 2 * py1 * point * (1 - point)
                + py2 * point * point
            )
            return min(cmin, pyx), max(cmax, pyx)
        return cmin, cmax

    if fabs(py0 + py2 - 2 * py1) > atol:
        cmin, cmax = _is_bigger((py0 - py1) / (py0 + py2 - 2 * py1))

    return cmin, cmax
