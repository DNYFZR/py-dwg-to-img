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
"""
Path and CubicSuperPath classes
"""

from __future__ import annotations

import re
import copy
import warnings
from cmath import isclose

from typing import Optional, Tuple, List, TypeVar, Iterator, Callable, Union
from ..transforms import (
    Transform,
    BoundingBox,
    Vector2d,
    ComplexLike,
)
from ..utils import strargs

from .lines import Line, Move, move, ZoneClose
from .curves import Curve
from .interfaces import (
    ILengthSettings,
    LengthSettings,
    PathCommand,
    AbsolutePathCommand,
)

Pathlike = TypeVar("Pathlike", bound="PathCommand")
AbsolutePathlike = TypeVar("AbsolutePathlike", bound="AbsolutePathCommand")

LEX_REX = re.compile(r"([MLHVCSQTAZmlhvcsqtaz])([^MLHVCSQTAZmlhvcsqtaz]*)")


class InvalidPath(ValueError):
    """Raised when given an invalid path string"""


class Path(list):
    """A list of segment commands which combine to draw a shape"""

    callback: Optional[Callable] = None

    class PathCommandProxy:
        """
        A handy class for Path traverse and coordinate access

        Reduces number of arguments in user code compared to bare
        :class:`PathCommand` methods
        """

        def __init__(
            self,
            command: PathCommand,
            first_point: ComplexLike,
            previous_end_point: ComplexLike,
            prev2_control_point: ComplexLike,
        ):
            self.command = command
            self.cfirst_point = complex(first_point)
            self.cprevious_end_point = complex(previous_end_point)
            self.cprev2_control_point = complex(prev2_control_point)

        @property
        def first_point(self) -> Vector2d:
            """First point of the current subpath"""
            return Vector2d(self.cfirst_point)

        @property
        def previous_end_point(self) -> Vector2d:
            """End point of the previous command"""
            return Vector2d(self.cprevious_end_point)

        @property
        def prev2_control_point(self) -> Vector2d:
            """Last control point of the previous command"""
            return Vector2d(self.cprev2_control_point)

        @property
        def name(self) -> str:
            """The full name of the segment (i.e. Line, Arc, etc)"""
            return self.command.name

        @property
        def letter(self) -> str:
            """The single letter representation of this command (i.e. L, A, etc)"""
            return self.command.letter

        @property
        def next_command(self):
            """The implicit next command."""
            return self.command.next_command

        @property
        def is_relative(self) -> bool:
            """Whether the command is defined in relative coordinates, i.e. relative to
            the previous endpoint (lower case path command letter)"""
            return self.command.is_relative

        @property
        def is_absolute(self) -> bool:
            """Whether the command is defined in absolute coordinates (upper case path
            command letter)"""
            return self.command.is_absolute

        @property
        def args(self) -> List[float]:
            """Returns path command arguments as tuple of floats"""
            return self.command.args

        @property
        def control_points(self) -> List[Vector2d]:
            """Returns list of path command control points"""
            return list(
                self.command.control_points(
                    self.cfirst_point,
                    self.cprevious_end_point,
                    self.cprev2_control_point,
                )
            )

        @property
        def end_point(self) -> Vector2d:
            """Returns last control point of path command"""
            return Vector2d(self.cend_point)

        @property
        def cend_point(self) -> complex:
            """Returns last control point of path command (in complex form)"""
            return self.command.cend_point(self.cfirst_point, self.cprevious_end_point)

        def reverse(self) -> PathCommand:
            """Reverse path command"""
            return self.command.reverse(self.cend_point, self.cprevious_end_point)

        def to_curve(self) -> Curve:
            """Convert command to :py:class:`Curve`
            Curve().to_curve() returns a copy
            """
            return self.command.to_curve(
                self.cprevious_end_point, self.cprev2_control_point
            )

        def to_curves(self) -> List[Curve]:
            """Convert command to list of :py:class:`Curve` commands"""
            return self.command.to_curves(
                self.cprevious_end_point, self.cprev2_control_point
            )

        def to_absolute(self) -> AbsolutePathCommand:
            """Return relative counterpart for relative commands or copy for absolute"""
            return self.command.to_absolute(self.cprevious_end_point)

        def to_non_shorthand(self) -> AbsolutePathCommand:
            """Returns an absolute non-shorthand command

            .. versionadded:: 1.4"""
            return self.command.to_non_shorthand(
                self.cprevious_end_point, self.cprev2_control_point
            )

        def split(self, time) -> Tuple[Path.PathCommandProxy, Path.PathCommandProxy]:
            """Split this path command into two PathCommandProxy segments.
            Raises ValueError for Move commands.

            .. versionadded:: 1.4"""
            result = self.command.split(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                time,
            )
            p1 = Path.PathCommandProxy(
                result[0],
                self.cfirst_point,
                self.previous_end_point,
                self.prev2_control_point,
            )
            prev2: ComplexLike = (
                0j if len(p1.control_points) < 2 else p1.control_points[-2]
            )
            p2 = Path.PathCommandProxy(
                result[1], self.cfirst_point, p1.end_point, prev2
            )
            return (p1, p2)

        def cpoint(self, time) -> complex:
            """Returns the coordinates of the Bezier curve evaluated at t as complex number.

            .. versionadded:: 1.4"""
            return self.command.cpoint(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                time,
            )

        def point(self, time) -> Vector2d:
            """Returns the coordinates of the Bezier curve evaluated at t as :class:`Vector2d`.

            .. versionadded:: 1.4"""
            return self.command.point(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                time,
            )

        def length(self, t0=0, t1=1, settings=LengthSettings()) -> float:
            """Get the length of the command between t0 and t1 in user units

            .. versionadded:: 1.4"""
            return self.command.length(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                t0,
                t1,
                settings,
            )

        def ilength(self, length, settings=ILengthSettings()) -> float:
            """Tries to compute the time t at which the path segment has the given
            length along its trajectory

            .. versionadded:: 1.4"""
            return self.command.ilength(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                length,
                settings,
            )

        def cunit_tangent(self, t) -> complex:
            """Returns the unit tangent at t as complex number

            .. versionadded:: 1.4"""
            return self.command.cunit_tangent(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                t,
            )

        def unit_tangent(self, t) -> Vector2d:
            """Returns the unit tangent at t as :class:`inkex.Vector2D`

            .. versionadded::  1.4"""
            return self.command.unit_tangent(
                self.cfirst_point,
                self.cprevious_end_point,
                self.cprev2_control_point,
                t,
            )

        def __str__(self):
            return str(self.command)

        def __repr__(self):
            return "<" + self.__class__.__name__ + ">" + repr(self.command)

    def __init__(self, path_d=None) -> None:
        super().__init__()
        if isinstance(path_d, str):
            # Returns a generator returning PathCommand objects
            path_d = self.parse_string(path_d)
        elif isinstance(path_d, CubicSuperPath):
            path_d = path_d.to_path()

        for item in path_d or ():
            if isinstance(item, PathCommand):
                self.append(item)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                if isinstance(item[1], (list, tuple)):
                    self.append(PathCommand.letter_to_class(item[0])(*item[1]))
                else:
                    if len(self) == 0:
                        self.append(Move(*item))
                    else:
                        self.append(Line(*item))
            else:
                raise TypeError(
                    f"Bad path type: {type(path_d).__name__}"
                    f"({type(item).__name__}, ...): {item}"
                )

    @classmethod
    def parse_string(cls, path_d):
        """Parse a path string and generate segment objects"""
        for cmd, numbers in LEX_REX.findall(path_d):
            args = list(strargs(numbers))
            cmd = PathCommand.letter_to_class(cmd)
            i = 0
            while i < len(args) or cmd.nargs == 0:
                if len(args[i : i + cmd.nargs]) != cmd.nargs:
                    return
                seg = cmd(*args[i : i + cmd.nargs])
                i += cmd.nargs
                cmd = seg.next_command
                yield seg

    def bounding_box(self) -> Optional[BoundingBox]:
        """Return bounding box of the Path"""
        if not self:
            return None
        iterator = self.proxy_iterator()
        proxy = next(iterator)
        bbox = BoundingBox(proxy.first_point.x, proxy.first_point.y)
        try:
            while True:
                proxy = next(iterator)
                proxy.command.update_bounding_box(
                    complex(proxy.first_point),
                    [
                        proxy.cprev2_control_point,
                        proxy.cprevious_end_point,
                    ],
                    bbox,
                )
        except StopIteration:
            return bbox

    def append(self, cmd):
        """Append a command to this path."""
        try:
            cmd.letter  # pylint: disable=pointless-statement
            super().append(cmd)
        except AttributeError:
            self.extend(cmd)
            warnings.warn(
                "Passing a list to Path.add is deprecated, please use Path.extend",
                category=DeprecationWarning,
            )

    def translate(self, x, y, inplace=False):  # pylint: disable=invalid-name
        """Move all coords in this path by the given amount"""
        return self.transform(Transform(translate=(x, y)), inplace=inplace)

    def scale(self, x, y, inplace=False):  # pylint: disable=invalid-name
        """Scale all coords in this path by the given amounts"""
        return self.transform(Transform(scale=(x, y)), inplace=inplace)

    def rotate(self, deg, center=None, inplace=False):
        """Rotate the path around the given point"""
        if center is None:
            # Default center is center of bbox
            bbox = self.bounding_box()
            if bbox:
                center = bbox.center
            else:
                center = Vector2d()
        center = Vector2d(center)
        return self.transform(
            Transform(rotate=(deg, center.x, center.y)), inplace=inplace
        )

    @property
    def control_points(self) -> Iterator[Vector2d]:
        """Returns all control points of the Path"""
        prev: complex = 0
        prev_prev: complex = 0
        first: complex = 0

        seg: PathCommand
        for seg in self:
            cpts = seg.ccontrol_points(first, prev, prev_prev)
            if seg.letter in "zZmM":
                first = cpts[-1]
            for cpt in cpts:
                prev_prev = prev
                prev = cpt
                yield Vector2d(cpt)

    @property
    def cend_points(self) -> Iterator[complex]:
        """Complex version of end_points"""
        prev = 0j
        first = 0j

        seg: PathCommand
        for seg in self:
            end_point = seg.cend_point(first, prev)
            if seg.letter in "zZmM":
                first = end_point
            prev = end_point
            yield end_point

    @property
    def end_points(self) -> Iterator[Vector2d]:
        """Returns all endpoints of all path commands (i.e. the nodes)"""
        for i in self.cend_points:
            yield Vector2d(i)

    def transform(self, transform, inplace=False):
        """Convert to new path"""
        result = Path()
        previous = 0j
        previous_new = 0j
        start_zone = True
        first = 0j
        first_new = 0j

        seg: PathCommand
        for i, seg in enumerate(self):
            if start_zone:
                first = seg.cend_point(first, previous)

            if seg.letter in "hHVv":
                seg = seg.to_line(previous)

            if seg.is_relative:
                new_seg = (
                    seg.to_absolute(previous)
                    .transform(transform)
                    .to_relative(previous_new)
                )
            else:
                new_seg = seg.transform(transform)

            if start_zone:
                first_new = new_seg.cend_point(first_new, previous_new)

            if inplace:
                self[i] = new_seg
            else:
                result.append(new_seg)
            previous = seg.cend_point(first, previous)
            previous_new = new_seg.cend_point(first_new, previous_new)
            start_zone = seg.letter in "zZ"
        if inplace:
            return self
        return result

    def reverse(self):
        """Returns a reversed path"""
        result = Path()
        *_, first = self.cend_points
        closer = None

        # Go through the path in reverse order
        for index, prcom in reversed(list(enumerate(self.proxy_iterator()))):
            if prcom.letter in "MmZz":
                if closer is not None:
                    if len(result) > 0 and result[-1].letter in "LlVvHh":
                        result.pop()  # We can replace simple lines with Z
                    result.append(closer)  # replace with same type (rel or abs)
                if prcom.letter in "Zz":
                    closer = prcom.command
                else:
                    closer = None

            if index == 0:
                if prcom.letter == "M":
                    result.insert(0, Move(first))
                elif prcom.letter == "m":
                    result.insert(0, move(first))
            else:
                result.append(prcom.reverse())

        return result

    def break_apart(self) -> List[Path]:
        """Breaks apart a path into its subpaths

        .. versionadded:: 1.3"""
        result = [Path()]
        current = result[0]

        for cmnd in self.proxy_iterator():
            if cmnd.letter.lower() == "m":
                current = Path()
                result.append(current)
                current.append(Move(cmnd.cend_point))
            else:
                current.append(cmnd.command)
        # Remove all subpaths that are empty or only contain move commands
        return [
            i
            for i in result
            if len(i) != 0 and not all(j.letter.lower() == "m" for j in i)
        ]

    def close(self):
        """Attempt to close the last path segment"""
        if self and not self[-1].letter in "zZ":
            self.append(ZoneClose())

    def proxy_iterator(self) -> Iterator[PathCommandProxy]:
        """
        Yields :py:class:`AugmentedPathIterator`

        :rtype: Iterator[ Path.PathCommandProxy ]
        """

        previous = 0j
        prev_prev = 0j
        first = 0j
        seg: PathCommand
        for seg in self:
            if seg.letter in "zZmM":
                first = seg.cend_point(first, previous)
            yield Path.PathCommandProxy(seg, first, previous, prev_prev)
            if seg.letter in "ctqsCTQS":
                prev_prev = seg.ccontrol_points(first, previous, prev_prev)[-2]
            previous = seg.cend_point(first, previous)

    def to_absolute(self):
        """Convert this path to use only absolute coordinates"""
        return self._to_absolute(True)

    def to_non_shorthand(self) -> Path:
        """Convert this path to use only absolute non-shorthand coordinates

        .. versionadded:: 1.1"""
        return self._to_absolute(False)

    def _to_absolute(self, shorthand: bool) -> Path:
        """Make entire Path absolute.

        Args:
            shorthand (bool): If false, then convert all shorthand commands to
                non-shorthand.

        Returns:
            Path: the input path, converted to absolute coordinates.
        """

        abspath = Path()

        previous = 0j
        first = 0j
        seg: PathCommand
        for seg in self:
            if seg.letter in "mM":
                first = seg.cend_point(first, previous)

            if shorthand:
                abspath.append(seg.to_absolute(previous))
            else:
                if abspath and abspath[-1].letter in "QC":
                    prev_control = list(abspath[-1].control_points(0, 0, 0))[-2]
                else:
                    prev_control = previous

                abspath.append(seg.to_non_shorthand(previous, prev_control))

            previous = seg.cend_point(first, previous)

        return abspath

    def to_relative(self):
        """Convert this path to use only relative coordinates"""
        abspath = Path()

        previous = 0j
        first = 0j
        seg: PathCommand
        for seg in self:
            if seg.letter in "mM":
                first = seg.cend_point(first, previous)

            abspath.append(seg.to_relative(previous))
            previous = seg.cend_point(first, previous)

        return abspath

    def __str__(self):
        return " ".join([str(seg) for seg in self])

    def __add__(self, other):
        acopy = copy.deepcopy(self)
        if isinstance(other, str):
            other = Path(other)
        if isinstance(other, list):
            acopy.extend(other)
        return acopy

    def to_arrays(self):
        """Returns path in format of parsePath output, returning arrays of absolute
        command data

        .. deprecated:: 1.0
            This is compatibility function for older API. Should not be used in new code

        """
        return [[seg.letter, list(seg.args)] for seg in self.to_non_shorthand()]

    def to_superpath(self):
        """Convert this path into a cubic super path"""
        return CubicSuperPath(self)

    def copy(self):
        """Make a copy"""
        return copy.deepcopy(self)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.callback is not None:
            self.callback(self)  # pylint: disable=not-callable


class CubicSuperPath(list):
    """
    A conversion of a path into a predictable list of cubic curves which
    can be operated on as a list of simplified instructions.

    When converting back into a path, all lines, arcs etc will be converted
    to curve instructions.

    Structure is held as [SubPath[(point_a, bezier, point_b), ...], ...]
    """

    def __init__(self, items):
        super().__init__()
        self._closed = True
        self._prev = 0j
        self._prev_prev = 0j

        if isinstance(items, str):
            items = Path(items)

        if isinstance(items, Path):
            for item in items:
                self.append_path_command(item)
            return

        for item in items:
            self.append(item)

    def __str__(self):
        return str(self.to_path())

    def append_node_with_handles(self, command: List[Tuple[float, float]]):
        """First item: left handle, second item: node coords,
        third item: right handle"""
        if self._closed:
            # Closed means that the previous segment is closed so we need a new one
            # We always append to the last open segment. CSP starts out closed.
            self._closed = False
            super().append([])

        self[-1].append(command)
        self._prev_prev = command[0][0] + command[0][1] * 1j
        self._prev = command[1][0] + command[1][1] * 1j

    def append_path_command(self, command: PathCommand):
        """Append a path command.

        For ordinary commands:

        ..code ::

            old last entry -> [[.., ..], [.., ..], [x1, y1]]
            new last entry -> [[x2, y2], [x3, y3], [x3, y3]]

        The last tuple is duplicated (retracted handle): either it's the last command
        of the subpath, then the handle will stay retracted, or it will be replaced
        with the next path command.
        """
        if command.letter in "mM":
            carg = command.cend_point(self._first, self._prev)
            arg = Vector2d.c2t(carg)
            super().append([[arg[:], arg[:], arg[:]]])
            self._prev = self._prev_prev = carg
            self._closed = False
            return
        if command.letter in "zZ" and self:
            # This duplicates the first segment to 'close' the path
            self[-1].append([self[-1][0][0][:], self[-1][0][1][:], self[-1][0][2][:]])
            # Then adds a new subpath for the next shape (if any)
            # self._closed = True
            self._prev = self._first
            return
        if command.letter in "aA":
            # Arcs are made up of (possibly) more than one curve, depending on their
            # angle (approximated)
            for arc_curve in command.to_curves(self._prev, self._prev_prev):
                self.append_path_command(arc_curve)
            return
        # Handle regular curves.

        if self._closed:
            # Previous segment is closed. Append a new segment first.
            self._closed = False
            super().append([])

        cp1, cp2, cp3 = command.ccurve_points(0j, self._prev, self._prev_prev)

        item = [Vector2d.c2t(cp1), Vector2d.c2t(cp2), Vector2d.c2t(cp3)]
        self._prev = cp3
        if not command.letter in "QT":
            self._prev_prev = cp2
        else:
            self._prev_prev = command.ccontrol_points(0j, self._prev, self._prev_prev)[
                0
            ]

        if self[-1]:  # There exists a previous segment, replace its outgoing handle.
            self[-1][-1][-1] = item[0]
        # Append the segment with the last coordinate (node pos) repeated.
        self[-1].append(item[1:] + [item[-1][:]])

    def append(self, item):
        """Append a segment/node to the superpath and update the internal state.

        item may be specified in any of the following formats:

        - PathCommand
        - [str, List[float]] - A path command letter and its arguments
        - [[float, float], [float, float], [float, float]] - Incoming handle, node,
           outgoing handle.
        - List[[float, float], [float, float], [float, float]] - An entire subpath.


        """
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
            item = PathCommand.letter_to_class(item[0])(*item[1])
        if isinstance(item, PathCommand):
            self.append_path_command(item)
            return

        if isinstance(item, list):
            # Item is a subpath: List[Handle, node, Handle]. Just append the
            # subpath, and update the prev/ prev_prev positions.
            if (
                (len(item) != 3 or not all(len(bit) == 2 for bit in item))
                and len(item[0]) == 3
                and all(len(bit) == 2 for bit in item[0])
            ):
                super().append(self._clean(item))

            elif len(item) == 3 and all(len(bit) == 2 for bit in item):
                # Item is already a csp segment [Handle, node, Handle].
                if self._closed:
                    # Closed means that the previous segment is closed so we need a new
                    # one.
                    # We always append to the last open segment. CSP starts out closed.
                    self._closed = False
                    super().append([])

                # Item is already a csp segment and has already been shifted.
                self[-1].append([i.copy() for i in item])
            else:
                raise ValueError(f"Unknown super curve list format: {item}")

            self._prev_prev = Vector2d.t2c(self[-1][-1][0])
            self._prev = Vector2d.t2c(self[-1][-1][1])
        else:
            raise ValueError(f"Unknown super curve list format: {item}")

    def _clean(self, lst):
        """Recursively clean lists so they have the same type"""
        if isinstance(lst, (tuple, list)):
            return [self._clean(child) for child in lst]
        return lst

    @property
    def _first(self):
        try:
            return self[-1][0][0][0] + self[-1][0][0][1] * 1j
        except IndexError:
            return 0 + 0j

    def to_path(self, curves_only=False, rtol=1e-5, atol=1e-8):
        """Convert the super path back to an svg path

        Arguments: see :func:`to_segments` for parameters"""
        return Path(list(self.to_segments(curves_only, rtol, atol)))

    def to_segments(self, curves_only=False, rtol=1e-5, atol=1e-8):
        """Generate a set of segments for this cubic super path

        Arguments:
            curves_only (bool, optional): If False, curves that can be represented
                by Lineto / ZoneClose commands, will be. Defaults to False.
            rtol (float, optional): relative tolerance, passed to :func:`is_line` and
                :func:`inkex.transforms.ImmutableVector2d.is_close` for checking if a
                line can be replaced by a ZoneClose command. Defaults to 1e-5.

                .. versionadded:: 1.2
            atol: absolute tolerance, passed to :func:`is_line` and
                :func:`inkex.transforms.ImmutableVector2d.is_close`. Defaults to 1e-8.

                .. versionadded:: 1.2"""
        for subpath in self:
            previous = []
            for segment in subpath:
                if not previous:
                    yield Move(Vector2d(segment[1]))
                elif self.is_line(previous, segment, rtol, atol) and not curves_only:
                    if segment is subpath[-1] and Vector2d(segment[1]).is_close(
                        Vector2d(subpath[0][1]), rtol, atol
                    ):
                        yield ZoneClose()
                    else:
                        yield Line(Vector2d(segment[1]))
                else:
                    yield Curve(
                        Vector2d(previous[2]),
                        Vector2d(segment[0]),
                        Vector2d(segment[1]),
                    )
                previous = segment

    def transform(self, transform):
        """Apply a transformation matrix to this super path"""
        return self.to_path().transform(transform).to_superpath()

    @staticmethod
    def is_on(pt_a, pt_b, pt_c, tol=1e-8):
        """Checks if point pt_a is on the line between points pt_b and pt_c

        .. versionadded:: 1.2"""
        return CubicSuperPath.collinear(pt_a, pt_b, pt_c, tol) and (
            CubicSuperPath.within(pt_a[0], pt_b[0], pt_c[0])
            if abs(pt_a[0] - pt_b[0]) > 1e-13
            else CubicSuperPath.within(pt_a[1], pt_b[1], pt_c[1])
        )

    @staticmethod
    def collinear(pt_a, pt_b, pt_c, tol=1e-8):
        """Checks if points pt_a, pt_b, pt_c lie on the same line,
        i.e. that the cross product (b-a) x (c-a) < tol

        .. versionadded:: 1.2"""
        return (
            abs(
                (pt_b[0] - pt_a[0]) * (pt_c[1] - pt_a[1])
                - (pt_c[0] - pt_a[0]) * (pt_b[1] - pt_a[1])
            )
            < tol
        )

    @staticmethod
    def within(val_b, val_a, val_c):
        """Checks if float val_b is between val_a and val_c

        .. versionadded:: 1.2"""
        return val_a <= val_b <= val_c or val_c <= val_b <= val_a

    @staticmethod
    def is_line(previous, segment, rtol=1e-5, atol=1e-8):
        """Check whether csp segment (two points) can be expressed as a line has
        retracted handles or the handles can be retracted without loss of information
        (i.e. both handles lie on the line)

        .. versionchanged:: 1.2
            Previously, it was only checked if both control points have retracted
            handles. Now it is also checked if the handles can be retracted without
            (visible) loss of information (i.e. both handles lie on the line connecting
            the nodes).

        Arguments:
            previous: first node in superpath notation
            segment: second node in superpath notation
            rtol (float, optional): relative tolerance, passed to
                :func:`inkex.transforms.ImmutableVector2d.is_close` for checking handle
                retraction. Defaults to 1e-5.

                .. versionadded:: 1.2
            atol (float, optional): absolute tolerance, passed to
                :func:`inkex.transforms.ImmutableVector2d.is_close` for checking handle
                retraction and
                :func:`inkex.paths.CubicSuperPath.is_on` for checking if all points
                (nodes + handles) lie on a line. Defaults to 1e-8.

                .. versionadded:: 1.2
        """

        retracted = isclose(
            Vector2d(previous[1]), Vector2d(previous[2]), rel_tol=rtol, abs_tol=atol
        ) and isclose(
            Vector2d(segment[0]), Vector2d(segment[1]), rel_tol=rtol, abs_tol=atol
        )

        if retracted:
            return True

        # Can both handles be retracted without loss of information?
        # Definitely the case if the handles lie on the same line as the two nodes and
        # in the correct order
        # E.g. cspbezsplitatlength outputs non-retracted handles when splitting a
        # straight line
        return CubicSuperPath.is_on(
            segment[0], segment[1], previous[2], atol
        ) and CubicSuperPath.is_on(previous[2], previous[1], segment[0], atol)
