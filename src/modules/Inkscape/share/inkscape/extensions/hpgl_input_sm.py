#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2022 Jonathan Neuhauser (jonathan.neuhauser@outlook.com)
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


"""HPGL Input state machine"""

import math
from typing import List, Optional, Tuple, Dict, Union
from pyparsing import ParseResults
import inkex


class ListWithCallback(list):
    """A list that modifies elements with a callback before appending them"""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def append(self, item):
        super().append(self.callback(item))


PathData = ListWithCallback


class HPGLStateMachine:
    """This a HPGL plotter"""

    def __init__(self, root: inkex.Layer, options):
        self.options = options
        self.x: float
        self.y: float
        self.pendown: bool
        self.current_path: PathData
        self.current_parent: inkex.Layer
        self.absolute_mode: bool
        self.root = root
        self.polygon_mode = False
        self.polygon_buffer: List[PathData] = []
        # Start positions of polygon modes
        self.startx = 0
        self.starty = 0
        self.transform_manager = TransformManager(options)
        self.style_manager = StyleManager(options)
        self.initialize()

    def create_group(self):
        """Manage group"""
        # We'll set transforms; if the current layer is empty, don't create a new one
        self.finalize_path()
        if hasattr(self, "current_parent") and len(self.current_parent) == 0:
            group = self.current_parent
        else:
            group = inkex.Group()
            self.root.add(group)
            self.current_parent = group

        group.transform, clip = self.transform_manager.get_transform_and_clip(
            self.root.transform
        )
        if clip is not None:
            self.root.root.defs.append(clip)
            group.clip = clip
        self.initialize_current_path()
        self.current_path.append(inkex.paths.Move(self.x, self.y))

    def df_command(self):
        """default values"""
        self.style_manager.default_values()
        self.transform_manager.default_values()
        self.polygon_buffer = []
        self.initialize_current_path()
        self.create_group()  # in case scaling was turned off

    def initialize(self):
        """Reset state to default"""
        self.transform_manager.initialize()
        self.style_manager.initialize()
        self.x = 0
        self.y = 0
        self.pendown = False
        self.absolute_mode = True
        self.df_command()
        self.create_group()

    def initialize_current_path(self):
        """Initialize the current path with a custom append method"""

        def callback(new_elem):
            # we store the start position additionally to the path element itself
            result = [new_elem, self.pendown, self.x, self.y]
            if new_elem.is_absolute:
                self.x, self.y = new_elem.args[-2:]
            else:
                self.x, self.y = self.x + new_elem.args[-2], self.y + new_elem.args[-1]
            return result

        self.current_path = ListWithCallback(callback)

    def append_path_data(self, cmd, x, y):
        """Given lists of coordinates x, y, adds those to the path with command cmd,
        and sets the pen's position as the last of those"""

    def _line_command(self, key, xvals=None, yvals=None):
        if key in ["PA", "PR"]:
            self.absolute_mode = key == "PA"
        if key in ["PD", "PU"]:
            self.pendown = key == "PD"
        cmd = inkex.paths.Line if self.absolute_mode else inkex.paths.line
        if xvals is not None and yvals is not None:
            for xi, yi in zip(xvals, yvals):
                self.current_path.append(cmd(xi, yi))

    def line_command(self, vals: ParseResults):
        """Handle pu, pd, pa, pr"""
        vals_dict = vals.as_dict()
        if "X" in vals_dict and "Y" in vals_dict:
            self._line_command(vals_dict["key"], vals_dict["X"], vals_dict["Y"])
        else:
            self._line_command(vals_dict["key"])

    @staticmethod
    def create_path(data: List[PathData], fill=False, pmode=False) -> inkex.Path:
        """Create a path out of the stored points"""
        result = inkex.Path()

        for subpath in data:
            for j, (cmd, pendown, xstart, ystart) in enumerate(subpath):
                # For simplicity, commands are converted to absolute in polygon mode
                drawn_before = any(subpath[k][1] for k in range(j))
                if pmode:
                    cmd = cmd.to_absolute(inkex.Vector2d(xstart, ystart))
                    if not fill and pendown and not subpath[j - 1][1] and drawn_before:
                        # When edging a polygon, a line is drawn to "skip" (possibly
                        # subsequent) pen-up commands (but
                        # only if there already was a drawn command in this subpolygon)
                        result.append(inkex.paths.Line(xstart, ystart))
                # Don't draw commands when pen was up
                if not (not pendown and pmode and not fill and drawn_before):
                    # Also the first command of each subpath in polygon mode is
                    # converted: "When you use (PM1), the point after (PM1) becomes the
                    # first point of the next subpolygon. This move is not used as a
                    # boundary when filling a polygon with FP."
                    if (j == 0 and pmode) or (not pmode and not pendown):
                        repl = inkex.paths.move if cmd.is_relative else inkex.paths.Move
                        result.append(repl(*cmd.args[-2:]))
                    else:
                        result.append(cmd)
                if pmode and j == len(subpath) - 1:
                    result.append(inkex.paths.ZoneClose())
        # Ensure that the first path command is a moveto
        if result and result[0].letter.lower() != "m":
            result.insert(0, inkex.paths.move(0, 0))
        # Remove unnecessary moveto in the beginning of a path
        for i, cmd in enumerate(result.proxy_iterator()):
            if cmd.command.letter.lower() != "m":
                result = inkex.Path([inkex.paths.Move(*cmd.first_point)] + result[i:])
                break
        return result

    def finalize_path(self) -> None:
        """Append the current path to the parent if it's effectively non-empty"""
        result = self.create_path([self.current_path], False, False)
        if self.options.break_apart:
            result_list = result.break_apart()
        else:
            result_list = [result]
        for res in result_list:
            if any(i.letter not in "mM" for i in res):
                if self.current_path not in self.polygon_buffer:
                    pel = inkex.PathElement()
                    pel.path = res
                    self.current_parent.add(pel)
                    self.style_manager.set_stroke(
                        pel, p1=self.transform_manager.p1, p2=self.transform_manager.p2
                    )

        self.initialize_current_path()
        self.current_path.append(inkex.paths.Move(self.x, self.y))

    def ci_command(self, vals: ParseResults):
        """Draws a circle using radius. Chord_angle is ignored.
        Includes an automatic PD; restores the old pen state and returns
        to the center position afterwards."""
        vals_dict = vals.as_dict()
        r = vals_dict["Radius"]
        pendown = self.pendown
        # Circles are implicit subpolygons in polygon mode
        self._pm_command(1)

        self.pendown = False
        self.current_path.append(inkex.paths.move(-r, 0))
        self.pendown = True
        # sweep flag = 1 for counterclockwise rotation when y axis points upwards,
        # but this is honestly a best guess from an ambiguous specification
        self.current_path.append(inkex.paths.arc(r, r, 0, 1, 1, 2 * r, 0))
        self.current_path.append(inkex.paths.arc(r, r, 0, 1, 1, -2 * r, 0))
        self.pendown = False
        self.current_path.append(inkex.paths.move(r, 0))
        # Restore pendown
        self.pendown = pendown
        # and terminate subpolygon
        self._pm_command(1)

    def arc_command(self, vals: ParseResults):
        """Draws an absolute/ relative arc"""
        vals_dict = vals.as_dict()

        absolute = vals_dict["key"] == "AA"
        c_x, c_y = vals_dict["X"][0], vals_dict["Y"][0]
        sweep = vals_dict["sweep"] * math.pi / 180
        # Transform start point about center by sweep radius
        if not absolute:
            c_x, c_y = c_x + self.x, c_y + self.y
        dx, dy = (self.x - c_x), (self.y - c_y)
        endpoint = (
            dx * math.cos(sweep) - dy * math.sin(sweep) + c_x,
            dx * math.sin(sweep) + dy * math.cos(sweep) + c_y,
        )
        radius = math.sqrt(dx**2 + dy**2)
        # Determine SVG arc flags
        sweep_flag = 1 if sweep > 0 else 0
        large_arc = 1 if abs(sweep) > math.pi else 0
        res: inkex.paths.PathCommand = inkex.paths.Arc(
            radius, radius, 0, large_arc, sweep_flag, *endpoint
        )
        if not absolute:
            res = res.to_relative(inkex.Vector2d(self.x, self.y))
        self.current_path.append(res)

    def at_command(self, vals: ParseResults):
        """Draws an Absolute Three Point arc"""

        valsd = vals.as_dict()
        x, y, z = [
            i + 1j * j for i, j in zip([self.x] + valsd["X"], [self.y] + valsd["Y"])
        ]
        pel = inkex.PathElement.arc_from_3_points(x, y, z, "arc")
        path = pel.path
        path = path.to_absolute()
        if not list(path.end_points)[-1].is_close(z):
            path = path.reverse()
        assert list(path.end_points)[-1].is_close(z), list(path.end_points)

        for com in path[1:]:  # skip initial move command
            self.current_path.append(com)

    def bezier_command(self, vals: ParseResults):
        """Draws an absolute/relative bezier, possibly multiple"""
        absolute = vals["key"] == "BZ"
        vals = vals.as_dict()["B"]

        cmd = inkex.paths.Curve if absolute else inkex.paths.curve
        for group in vals:
            self.current_path.append(cmd(*group))

    def polyline_encoded(self, vals: ParseResults):
        """Parse Polyline Encoded"""
        data = vals["data"].encode("latin-1")
        absolute_mode = self.absolute_mode
        self.absolute_mode = False
        PolylineEncodedParser(self).polyline_encoded(data)

        self.absolute_mode = absolute_mode

    def pm_command(self, vals: ParseResults):
        """Entering / exiting polygon mode"""
        val = vals["value"]
        self._pm_command(int(val))

    def _pm_command(self, val: int):
        """Entering / exiting polygon mode"""
        if val == 0:
            self.polygon_mode = True
            self.finalize_path()
            # Link polygon buffer and current path.
            self.polygon_buffer = [self.current_path]
        if val > 0 and self.polygon_mode:
            # Move to the end point of the current polygon buffer
            if val == 2:
                self.polygon_mode = False

            if len(self.current_path) < 2:
                return

            self.initialize_current_path()
            if val == 1:
                self.polygon_buffer += [self.current_path]

    def ft_command(self, vals: ParseResults):
        """Fill type"""
        self.style_manager.ft_command(vals.as_dict())

    def _get_function(self, vals: ParseResults, obj):
        return getattr(obj, f"{vals[0][0].lower()}_command")

    def style_command(self, vals: ParseResults):
        """Handle all commands in the style groups, they are deferred to the
        StyleManager"""
        func = self._get_function(vals, self.style_manager)

        # For commands that take effect immediately, finalize the path. This is
        # managed by a decorator to keep all information in one place
        if hasattr(func, "clear_path"):
            self.finalize_path()

        func(vals[0].as_dict())

    def transform_command(self, vals: ParseResults):
        """Handle all commands that potentially create a new parent group"""
        self.finalize_path()
        func = self._get_function(vals, self.transform_manager)
        func(vals[0].as_dict())
        self.create_group()

    def edge_fill_polygon(self, vals: ParseResults):
        """Fill or edge polygon"""
        if self.polygon_mode:
            return  # command illegal in polygon mode
        pel = inkex.PathElement()
        pel.path = self.create_path(self.polygon_buffer, vals["key"] == "FP", True)
        self.current_parent.add(pel)
        if vals["key"] == "FP":
            self.style_manager.set_fill(pel)
            if vals["fillmode"] == "0":
                pel.style["fill-rule"] = "evenodd"
            else:
                pel.style["fill-rule"] = "nonzero"
        else:
            # Draw polygon edges
            pel.style["fill"] = "none"
            self.style_manager.set_stroke(
                pel, p1=self.transform_manager.p1, p2=self.transform_manager.p2
            )

    def rectangle_wedge(self, element, stroke, fill):
        """Common functionality of rectangles and wedges"""
        # Finish the current path
        self.finalize_path()
        self.current_parent.append(element)
        if stroke:
            element.style["fill"] = "none"
            self.style_manager.set_stroke(
                element, p1=self.transform_manager.p1, p2=self.transform_manager.p2
            )
        if fill:
            self.style_manager.set_fill(element)
        # This command does not change the current pen position and up/down state,
        # but it uses the polygon buffer internally. In case the buffer will be reused,
        # push the path to the polygon buffer
        pdata = inkex.Path(element.get_path()).to_absolute()
        # Omit closing Z since polygon buffer does this automatically
        self.polygon_buffer = [
            [  # type: ignore
                [i.command, i.command.letter != "M"] + list(i.first_point)
                for i in pdata.proxy_iterator()
                if i.command.letter.lower() != "z"
            ]
        ]

    def rectangle_command(self, vals: ParseResults):
        """Handle ER, EA, RA, RR"""
        command = vals["key"]
        x = vals["X"][0]
        y = vals["Y"][0]
        if command[1] == "R":
            x += self.x
            y += self.y
        rect = inkex.Rectangle.new(
            min(self.x, x), min(self.y, y), abs(self.x - x), abs(self.y - y)
        ).to_path_element()
        self.rectangle_wedge(rect, command[0] == "E", command[0] == "R")

    def wedge_command(self, vals: ParseResults):
        """Handle EW and WG commands"""
        command = vals["key"]
        radius = vals["radius"]
        start_angle = vals["start_angle"] + (0 if radius > 0 else 180)

        arc = inkex.PathElement.arc(
            [self.x, self.y],
            abs(vals["radius"]),
            arctype="slice",
            start=(start_angle % 360) * math.pi / 180,
            end=((start_angle + vals["sweep"]) % 360) * math.pi / 180,
        )

        self.rectangle_wedge(arc, command[0] == "E", command[0] == "W")


def clear_path(fun):
    """A decorator that tells the parent state machine that the path should be cleared
    before executing this method"""

    def wrapped(*args, **kwargs):
        return fun(*args, **kwargs)

    wrapped.clear_path = True  # type: ignore
    return wrapped


class StyleManager:
    """Abstraction layer to store the state from all commands affecting style (stroke
    and fill)
    Currently not implemented:
    - Fill types (patterns) except solid fill
    - fill anchor (AC)
    - raster fill (RF)
    - screened vectors (SV)
    - Symbol mode (SM)
    - carrying over residue of dasharray
    - adaptive line patterns (negative line indices)
    - triangle line cap
    - no-join (overlap) line join
    """

    def __init__(self, options) -> None:
        self.current_style = inkex.Style()
        self.fill_type = "solid"
        self.options = options
        self.width_units_relative: bool
        self.pen_width: float
        self.linetype_manager: LineTypeManager
        self.transparency: bool

    def initialize(self):
        """IN commands that affect the StyleManager"""
        self.width_units_relative = False
        self._reset_pen_width()
        self.sp_command({"pen": 0})

    def default_values(self):
        """DF commands that affect the StyleManager"""
        self.current_style["stroke-linecap"] = "butt"
        self.current_style["stroke-linejoin"] = "miter"
        self.current_style["stroke-miterlimit"] = 5
        self.fill_type = "solid"
        self.linetype_manager = LineTypeManager(None, True, 0.04)
        self.transparency = True

    @clear_path
    def sp_command(self, vals: Dict):
        """Select pen"""
        penmap = {
            0: "White",
            1: "Black",
            2: "Red",
            3: "Green",
            4: "Yellow",
            5: "Blue",
            6: "Magenta",
            7: "Cyan",
        }
        self.current_style["stroke"] = inkex.Color(penmap[vals.get("pen", 0)].lower())

    def ft_command(self, vals: Dict):
        """Fill type"""
        typ = int(vals.get("type", 1))
        if typ < 3:
            self.fill_type = "solid"

    @clear_path
    def la_command(self, vals: Dict):
        """Set line attributes (line ends, line joins)"""
        for k, value in zip(vals["kind"], vals["value"]):
            kind = int(k)
            # Triangle line ends / line joins are not supported
            if kind == 1:
                dct = {1: "butt", 2: "square", 3: "round", 4: "round"}
                self.current_style["stroke-linecap"] = dct[value]
            if kind == 2:
                #  6: no join is not supported; would require splitting the paths
                # could be done by inserting "m 0,0" after every command
                dct = {1: "miter", 2: "miter", 3: "round", 4: "round", 5: "bevel"}
                self.current_style["stroke-linejoin"] = dct.get(value, "miter")
            if kind == 3:
                self.current_style["stroke-miterlimit"] = value

    @clear_path
    def lt_command(self, vals: Dict):
        """Set line type"""
        self.linetype_manager.lt_command(vals)

    def _reset_pen_width(self):
        self.pen_width = 0.35 if not self.width_units_relative else 0.001

    @clear_path
    def pw_command(self, vals: Dict):
        """Set pen width"""
        if "width" not in vals:
            self._reset_pen_width()
        else:
            self.pen_width = vals["width"]

    def tr_command(self, vals: Dict):
        """Set transparency mode"""
        self.transparency = vals.get("transparency", "1") == "1"

    @clear_path
    def ul_command(self, vals: Dict):
        """Set user defined line type"""
        self.linetype_manager.ul_command(vals)

    def wu_command(self, vals: Dict):
        """Set pen width units"""
        self.width_units_relative = vals.get("units", "0") == "1"
        self._reset_pen_width()

    def p1_p2_mm(
        self,
        pt1: Union[Tuple[float, float], inkex.Vector2d],
        pt2: Union[Tuple[float, float], inkex.Vector2d],
    ):
        """Compute distance between p1 and p2 (provided in kwargs), and convert to mm"""
        return (
            math.sqrt((pt1[1] - pt2[1]) ** 2 + (pt1[0] - pt2[0]) ** 2)
            / 40
            * 1016
            / self.options.resolution
        )

    def set_stroke(
        self,
        element: inkex.PathElement,
        p1: Union[Tuple[float, float], inkex.Vector2d],
        p2: Union[Tuple[float, float], inkex.Vector2d],
    ):
        """Set stroke on an element based on the current stroke settings"""
        element.style["fill"] = None
        for i in ["dasharray", "linejoin", "miterlimit", "linecap"]:
            element.style[f"stroke-{i}"] = self.current_style(f"stroke-{i}")
        element.style["stroke"] = self.current_style("stroke")
        if self.transparency and self.current_style("stroke") == inkex.Color("white"):
            element.style["stroke-opacity"] = 0
        # Stroke width
        width = self.pen_width * (
            self.p1_p2_mm(p1, p2) if self.width_units_relative else 1
        )
        element.style["stroke-width"] = width
        # Apply stroke pattern
        self.linetype_manager.apply_to_path(element, self.p1_p2_mm(p1, p2))

    def set_fill(self, element):
        """Set stroke on an element based on the current fill settings.
        Currently, only solid fill is supported"""
        # Fill polygon
        if self.fill_type == "solid":
            element.style["fill"] = self.current_style("stroke")
            if self.transparency and self.current_style("stroke") == inkex.Color(
                "white"
            ):
                element.style["fill-opacity"] = 0


class LineTypeManager:
    """Wrapper for the information contained in the LT and UL command"""

    default_linetypes: List[List[Union[float, int]]] = [
        [0, 100],
        [50, 50],
        [70, 30],
        [80, 10, 0, 10],
        [70, 10, 10, 10],
        [50, 10, 10, 10, 10, 10],
        [70, 10, 0, 10, 0, 10],
        [50, 10, 0, 10, 10, 10, 0, 10],
    ]

    def __init__(
        self, index: Optional[int], unit_relative: bool, pattern_length: float
    ) -> None:
        # type, relative length, pattern length
        self.index = index
        self.unit_relative = unit_relative
        self.pattern_length = pattern_length

        self.linetypes = self.default_linetypes.copy()

    def lt_command(self, vals: Dict):
        """Set line type"""
        if len(vals) == 0:
            # no parameters, reset to solid lines
            self.index = None
        if "linetype" in vals:
            ltp = max(min(vals["linetype"], 8), 0)
            self.index = ltp
        if "mode" in vals:
            self.unit_relative = vals["mode"] == 0
        if "pattern_length" in vals:
            self.pattern_length = max(0, vals["pattern_length"])

    def ul_command(self, vals: Dict):
        """Set user defined line type"""
        if "index" not in vals:
            # Reset all line types:
            self.linetypes = self.default_linetypes.copy()
            return
        i = int(vals["index"])
        if i < 1 or i > 8:
            return
        if "gap" not in vals:
            # Reset current line type
            self.linetypes[i - 1] = self.default_linetypes[i - 1]
            return
        gaps: List[float] = vals["gap"]
        if any(gap < 0 for gap in gaps) or sum(gaps) <= 0:
            return  # invalid
        self.linetypes[i - 1] = [gap / sum(gaps) * 100 for gap in gaps]

    def apply_to_path(self, element: inkex.PathElement, p1p2_dist):
        """Apply the line style to a path element."""
        if self.index is not None:  # None -> solid line
            pattern_length = self.pattern_length * (
                p1p2_dist / 100 if self.unit_relative else 1
            )
            if self.index > 0:
                element.style["stroke-dasharray"] = " ".join(
                    [
                        str(dashdot / 100.0 * pattern_length)
                        for dashdot in self.linetypes[self.index - 1]
                    ]
                )
            elif self.index == 0:
                # Only keep the end points of the path.
                new_path = inkex.Path()
                path_data = list(element.path.proxy_iterator())
                for i, item in enumerate(path_data):
                    if item.command.letter.lower() == "m":
                        if path_data[i + 1].command.letter.lower() != "m":
                            new_path.append(inkex.paths.Move(*(item.end_point)))
                            new_path.append(inkex.paths.line(0.0001, 0))
                    else:
                        # Workaround https://gitlab.com/inkscape/inkscape/-/issues/894
                        new_path.append(inkex.paths.Move(*(item.end_point)))
                        new_path.append(inkex.paths.line(0.0001, 0))
                element.path = new_path
                # Negative line types would have to be implemented in a similar way


class TransformManager:
    """Abstraction layer to handle all commands that affect transform of the current
    layer, in particular IP, IR, SC, IW, RO"""

    def __init__(self, options) -> None:
        self.scale_manager = ScaleManager()
        self.clip_manager = ClipManager()
        self.p1: inkex.Vector2d
        self.p2: inkex.Vector2d
        self.ro_angle: int = 0
        self.options = options
        self.ir_command = self.ip_command  # Alias
        self.initialize()

    def initialize(self):
        """IN commands that affect the TransformManager"""
        self.default_values()
        self.p1 = inkex.Vector2d((0, 0))
        self.p2 = inkex.Vector2d(
            (
                self.options.width * self.options.resolution,
                self.options.height * self.options.resolution,
            )
        )
        self.ro_angle = 0

    def default_values(self):
        """DF commands that affect the TransformManager"""
        self.scale_manager = ScaleManager(None)

    def get_transform_and_clip(
        self, root_transform: inkex.Transform
    ) -> Tuple[inkex.Transform, Optional[inkex.ClipPath]]:
        """Return the current effective transform and clip"""
        transform = self.get_rotation_transform() @ self.scale_manager.get_transform(
            self.p1, self.p2
        )
        clip = self.clip_manager.get_current_clip(
            root_transform,
            transform,
            scaled=self.scale_manager.enabled,
            bake=self.options.bake_transforms,
        )
        return transform, clip

    def ip_command(self, vals: Dict):
        """Set the scaling points p1 and p2"""
        key = vals["key"]
        x = [float(i) for i in vals["X"]]
        y = [float(i) for i in vals["Y"]]

        if key == "IR":
            x = [i * self.options.width * self.options.resolution / 100 for i in x]
            y = [i * self.options.height * self.options.resolution / 100 for i in y]
        if len(x) == 1:
            # P2 tracks P1
            x = [x[0], self.p2[0] - self.p1[0] + x[0]]
            y = [y[0], self.p2[1] - self.p1[1] + y[0]]
        for i in x, y:
            if i[0] == i[1]:  # avoid scaling into infinity
                i[1] += 1

        self.p1 = inkex.Vector2d(x[0], y[0])
        self.p2 = inkex.Vector2d(x[1], y[1])

    def sc_command(self, vals: Dict):
        """Scale command"""
        self.clip_manager.pin_to_plu()
        self.scale_manager = ScaleManager(vals)

    def get_rotation_transform(self) -> inkex.Transform:
        """Compute the effective transform caused by the RO command.
        Does not currently handle a following IP/IR without arguments."""
        rotation = inkex.Transform().add_rotate(self.ro_angle, self.p1)
        translation = inkex.Transform()
        if self.ro_angle == 90:
            # Shift P1 into the bottom right corner
            translation.add_translate(self.p2[0] - self.p1[0], 0)
        elif self.ro_angle == 180:
            # Shift P1 into the top right corner
            translation.add_translate(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])
        elif self.ro_angle == 270:
            # Shift P1 into the top left corner
            translation.add_translate(0, self.p2[1] - self.p1[1])
        return translation @ rotation

    def ro_command(self, vals: Dict):
        """Handle canvas rotation"""
        self.ro_angle = int(vals.get("angle", 0))

    def iw_command(self, vals: Dict):
        """Handle Soft Clipping"""
        self.clip_manager = ClipManager(vals.get("X", None), vals.get("Y", None))


class ScaleManager:
    """Helper class for the SC command"""

    def __init__(self, vals: Optional[Dict] = None):
        if vals is None:
            vals = {}
        self.vals = vals

    @property
    def enabled(self):
        """Determine if scaling is switched on"""
        return "Xmin" in self.vals

    def get_transform(self, p1, p2) -> inkex.Transform:
        """Return the transform from plotter units to user units, using the scaling
        points p1 and p2"""
        if not self.enabled:
            return inkex.Transform()
        xmin = self.vals["Xmin"]
        xmax = self.vals["Xmax"]
        ymin = self.vals["Ymin"]
        ymax = self.vals["Ymax"]
        # default not clear from spec? prob anisotropic
        type_id = self.vals.get("type", "0")

        if type_id != "2":
            if type_id == "0":
                pmin = [xmin, ymin]
                pmax = [xmax, ymax]
            elif type_id == "1":
                scale_y = abs(p2[1] - p1[1]) / abs(ymax - ymin)
                scale_x = abs(p2[0] - p1[0]) / abs(xmax - xmin)
                scale = min(scale_x, scale_y)
                if scale == scale_y:
                    # Space left / right
                    space = abs(p2[0] - p1[0]) - scale * abs(xmax - xmin)
                    left = (self.vals.get("left", 50) / 100 * space) / scale
                    right = ((100 - self.vals.get("left", 50)) / 100 * space) / scale
                    pmin = [xmin - left, ymin]
                    pmax = [xmax + right, ymax]
                if scale == scale_x:
                    # Space left / right
                    space = abs(p2[1] - p1[1]) - scale * abs(ymax - ymin)
                    bottom = (self.vals.get("bottom", 50) / 100 * space) / scale
                    top = ((100 - self.vals.get("bottom", 50)) / 100 * space) / scale
                    pmin = [xmin, ymin - bottom]
                    pmax = [xmax, ymax + top]
            # We need to map the points (xmin, ymin), (xmax, ymax))
            # in the layer coordinate system to  (P1), (P2) in plotter units,
            scale = [(p1[i] - p2[i]) / (pmin[i] - pmax[i]) for i in range(2)]
            offset = [p1[i] - scale[i] * pmin[i] for i in range(2)]
        elif type_id == "2":
            pmin = [xmin, ymin]
            scale = [xmax, ymax]
            offset = [p1[0] - scale[0] * xmin, p1[1] - scale[1] * ymin]
        return inkex.Transform(scale=tuple(scale), translate=tuple(offset))


class ClipManager:
    """Helper class for the IW command"""

    def __init__(
        self,
        x: Optional[Tuple[float, float]] = None,
        y: Optional[Tuple[float, float]] = None,
    ) -> None:
        self.x = x
        self.y = y
        self.storedx: Optional[Tuple[float, float]] = None
        self.storedy: Optional[Tuple[float, float]] = None
        self.pinned = False

    def get_current_clip(
        self,
        svg_to_plu: inkex.Transform,
        plu_to_uu: inkex.Transform,
        scaled=False,
        bake=False,
    ) -> Optional[inkex.ClipPath]:
        """Get the current clip path based on current transforms and scaling info"""
        if self.x is None or self.y is None:
            return None
        if not (self.x[1] >= self.x[0] and self.y[1] >= self.y[0]):
            inkex.errormsg("Bad clipping specification, will be ignored")
            return None
        if self.pinned:
            transform = svg_to_plu
        else:
            transform = svg_to_plu @ plu_to_uu
        if not bake:
            transform = -(svg_to_plu @ plu_to_uu) @ transform

        rect = inkex.Rectangle.new(
            self.x[0], self.y[0], self.x[1] - self.x[0], self.y[1] - self.y[0]
        )
        aspath = inkex.Path(rect.get_path())

        if scaled:
            # Store positions of the rectangle in plotter units
            bbox = aspath.transform(plu_to_uu).bounding_box()
            self.storedx = (float(bbox.left), float(bbox.right))
            self.storedy = (float(bbox.top), float(bbox.bottom))

        result = inkex.ClipPath()
        result.add(inkex.PathElement.new(path=aspath.transform(transform)))
        return result

    def pin_to_plu(self):
        """Pin position of the clip in plotter units"""
        self.x = self.storedx
        self.y = self.storedy
        self.pinned = True


class PolylineEncodedParser:
    """Helper class to parse the PE command"""

    def __init__(self, parent: HPGLStateMachine):
        self.parent = parent

    @staticmethod
    def _decode_value(value, fractional_bits: Optional[int] = None, base32_mode=False):
        """Helper function to decode a HPGL-encoded number"""
        # First remove all irrelevant values
        value = "".join(
            chr(i) for i in value if not (i < 63 or 128 <= i <= 190 or i == 255)
        ).encode("latin-1")
        result = 0
        for i, val in enumerate(value):
            if base32_mode and val > 127:
                val -= 128
            offset = 63
            if i == len(value) - 1:
                if base32_mode:
                    offset = 95
                else:
                    offset = 191

            result += (val - offset) << (5 if base32_mode else 6) * i
        # Only perform these steps if fractional data (i.e. coordinates)
        # are to be encoded
        if fractional_bits is not None:
            # Set sign
            result = result // 2 * (-1 if result % 2 == 1 else 1)
            # Fractional bits
            result = result / (2**fractional_bits)
        return result

    @staticmethod
    def _get_next_value(
        data, start_with, fractional_bits: Optional[int] = None, base32_mode=False
    ):
        """Helper function to find and then decode a HPGL encoded number"""
        i = start_with
        while i < len(data):
            if chr(data[i]) in ":><=7":  # can happen if there is no data
                # (specification is contradictory if this is allowed or not)
                i -= 1
                break
            if base32_mode:
                if data[i] % 128 >= 95:
                    break
            else:
                if data[i] >= 191:
                    break
            i += 1
        return i + 1, PolylineEncodedParser._decode_value(
            data[start_with : i + 1], fractional_bits, base32_mode
        )

    def polyline_encoded(self, data):
        """Parse a binary-encoded polyline"""
        index = 0
        base32_mode = False
        fractional_bits = 0

        while index < len(data):
            flag = chr(data[index])
            if base32_mode:
                flag = chr(ord(flag) % 128)  # remove highest bit
            if flag == "7":
                base32_mode = True
                index += 1
            elif flag in ">:":
                index, result = PolylineEncodedParser._get_next_value(
                    data, index + 1, None, base32_mode
                )
                if flag == ":":
                    # Select pen
                    self.parent.style_manager.sp_command({"pen": result})
                else:
                    # Select the number of fractional bits
                    fractional_bits = result
            else:
                start_index = index + (1 if flag in "<=" else 0)
                index, first = PolylineEncodedParser._get_next_value(
                    data, start_index, fractional_bits, base32_mode
                )
                index, second = PolylineEncodedParser._get_next_value(
                    data, index, fractional_bits, base32_mode
                )
                cmd = "PU" if flag == "<" else ("PA" if flag == "=" else "PR")
                # pylint: disable=protected-access
                if start_index != index:
                    self.parent._line_command(cmd, [first], [second])
                    # If coordinates were found, send a pen-down command if necessary
                    if not self.parent.pendown:
                        self.parent._line_command("PD")
                else:
                    self.parent._line_command(cmd)
