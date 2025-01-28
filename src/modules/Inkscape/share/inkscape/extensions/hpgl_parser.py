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

"""Grammar for parsing HPGL input files"""

import pyparsing as pp
from hpgl_input_sm import HPGLStateMachine

pp.ParserElement.enablePackrat()
pp.enable_all_warnings()

integer = pp.pyparsing_common.integer
sinteger = pp.pyparsing_common.signed_integer
flt = pp.pyparsing_common.number
comma = pp.Optional(pp.Suppress(","))

cpair = flt("X*") + comma + flt("Y*")


def build_vector_parsers(stm: HPGLStateMachine):
    """Parsers of the vector group"""
    # Lines
    line_command = pp.Group(
        (
            (pp.Literal("PA") | "PR" | "PD" | "PU")("key")
            + pp.Opt(
                cpair
                + pp.ZeroOrMore(comma + cpair)
                + pp.Opt(comma + sinteger("leftover*"))
            )
        ).add_parse_action(stm.line_command)
    )
    # Circles and arcs
    ci_command = pp.Group(
        (
            "CI" + sinteger("Radius") + pp.Opt(comma + flt("Chord_angle"))
        ).add_parse_action(stm.ci_command)
    )

    arc_command = pp.Group(
        (
            (pp.Literal("AA") | "AR")("key")
            + cpair
            + comma
            + sinteger("sweep")
            + pp.Opt(comma + flt("Chord_angle*"))
        ).add_parse_action(stm.arc_command)
    )
    at_command = pp.Group(
        (
            "AT" + cpair + comma + cpair + pp.Opt(comma + flt("Chord_angle*"))
        ).add_parse_action(stm.at_command)
    )

    # Beziers
    bezier = cpair + comma + cpair + comma + cpair
    bezier_command = pp.Group(
        (
            (pp.Literal("BR") | "BZ")("key")
            + bezier("B*")
            + pp.ZeroOrMore(comma + bezier("B*"))
        ).add_parse_action(stm.bezier_command)
    )
    # Polyline encoded
    pe_command = pp.Group(
        (
            "PE" + pp.Regex("[^;]*").setWhitespaceChars("")("data") + pp.Suppress(";")
        ).add_parse_action(stm.polyline_encoded)
    )

    return (
        line_command
        | ci_command
        | arc_command
        | bezier_command
        | at_command
        | pe_command
    )


def build_polygon_parsers(stm: HPGLStateMachine):
    """Build parser object from the polygon group"""
    pm_command = pp.Group(
        ("PM" + pp.Opt(pp.Word("012", exact=1), default="0")("value")).add_parse_action(
            stm.pm_command
        )
    )
    rectangle_command = pp.Group(
        ((pp.Literal("EA") | "ER" | "RA" | "RR")("key") + cpair).add_parse_action(
            stm.rectangle_command
        )
    )
    polygon_command = pp.Group(
        (
            (
                pp.Literal("FP")("key")
                + pp.Opt(pp.Word("01", exact=1), default="0")("fillmode")
            )
            | pp.Literal("EP")("key")
        ).add_parse_action(stm.edge_fill_polygon)
    )
    wedge_command = pp.Group(
        (
            (pp.Literal("EW") | "WG")("key")
            + sinteger("radius")
            + comma
            + flt("start_angle")
            + comma
            + flt("sweep")
            + pp.Opt(comma + flt("Chord_angle*"))
        ).add_parse_action(stm.wedge_command)
    )
    return pm_command | rectangle_command | polygon_command | wedge_command


def build_linefill_parsers(stm: HPGLStateMachine):
    """Build parsers from the Line and Fill Attributes Group"""

    kind = pp.Word("123", exact=1)("kind*")
    la_command = pp.Group(
        "LA"
        + pp.Opt(kind + comma + integer("value*"))
        + (comma + kind + comma + integer("value*")) * (0, 2)
    )
    lt_command = pp.Group(
        "LT"
        + pp.Opt(
            integer("linetype")
            + pp.Opt(comma + flt("pattern_length") + pp.Opt(comma + flt("mode")))
        )
    )
    pw_command = pp.Group("PW" + pp.Opt(flt("width") + pp.Opt(comma + integer("pen"))))
    # maybe we can combine those two?
    ft_command = pp.Group(
        "FT"
        + pp.Opt(
            (pp.Literal("1") | "2" | "3" | "4" | "10" | "11" | "21" | "22")("type")
            + pp.Opt(comma + flt("option1") + pp.Opt(comma + flt("option2")))
        )
    )
    tr_command = pp.Group("TR" + pp.Opt(pp.Literal("0") | "1", "1")("transparency"))
    ul_command = pp.Group(
        "UL" + pp.Opt(integer("index") + (comma + flt("gap*")) * (0, 20))
    )
    wu_command = pp.Group("WU" + pp.Opt(pp.Word("01", exact=1)("units")))
    sp_command = pp.Group("SP" + pp.Opt(integer("pen"), 0))
    return (
        sp_command
        | la_command
        | lt_command
        | pw_command
        | ft_command
        | tr_command
        | ul_command
        | wu_command
    ).add_parse_action(stm.style_command)


def build_configuration_parser(stm: HPGLStateMachine):
    """Commands of the configurtion group"""
    co_command = pp.Literal("CO") + pp.Suppress('"') + ... + pp.Suppress('"')
    in_command = pp.Literal("IN").add_parse_action(stm.initialize)
    ip_command = pp.Group(
        (pp.Literal("IP") | "IR")("key") + pp.Opt(cpair + pp.Opt(comma + cpair))
    )
    ro_command = pp.Group(
        "RO" + pp.Optional(pp.Literal("0") | "90" | "180" | "270", "0")("angle")
    )
    iw_command = pp.Group("IW" + pp.Opt(cpair + comma + cpair))
    sc_command = pp.Group(
        pp.Literal("SC")
        + (
            pp.Optional(
                flt("Xmin")
                + comma
                + flt("Xmax")
                + comma
                + flt("Ymin")
                + comma
                + flt("Ymax")
                + pp.Optional(
                    (comma + (pp.Literal("0") | "2")("type"))
                    | (
                        comma
                        + pp.Literal("1")("type")
                        + pp.Optional(comma + flt("left") + comma + flt("bottom"))
                    )
                )
            )
        )
    )

    return (in_command | co_command) | (
        ip_command | sc_command | ro_command | iw_command
    ).add_parse_action(stm.transform_command)


def build_parser(stm: HPGLStateMachine):
    """Assemble the command groups"""

    command = (
        build_configuration_parser(stm)
        | build_vector_parsers(stm)
        | build_polygon_parsers(stm)
        | build_linefill_parsers(stm)
        # Commands we don't understand
        | pp.Group(pp.Word(pp.alphas, exact=2) + pp.Opt(pp.Word(pp.nums + ",. ")))("u*")
    )
    # The parse actions of the documents are final cleanup
    document = pp.ZeroOrMore(command + pp.Opt(pp.Suppress(";"))).add_parse_action(
        stm.finalize_path
    )
    pp.autoname_elements()
    return document
