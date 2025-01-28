#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional

import inkex

from ..parser.types import AFObject, Curve18


@dataclass
class AFCurve:
    curves: List[List[Curve18]]
    closed: List[bool]

    @classmethod
    def from_af(cls, crvs: AFObject) -> AFCurve:
        assert crvs.get_type() in ["PCvD", "CrvD"], f"Not a curve {crvs}"
        data = crvs["Data"]

        _byte: int = data[0]
        size: Optional[int] = data[1] if crvs.get_type() == "PCvD" else None
        curv_ptr = 1 if size is None else 2
        if size is None:
            size = (len(data) - curv_ptr) // 2

        if _byte != 0:
            raise NotImplementedError(f"_byte {_byte} is not implemented\n{crvs}")

        curves: List[List[Curve18]] = []
        closeds: List[bool] = []
        for curv_idx in range(size):
            closed = data[curv_idx * 2 + curv_ptr]
            curve = data[curv_idx * 2 + curv_ptr + 1]
            assert isinstance(closed, bool), f"Invalid curve\n{data}"
            assert isinstance(curve, list), f"Invalid curve\n{data}"
            assert not curve or isinstance(
                curve[0], Curve18
            ), f'Invalid curve type "{type(curve[0])}" in \n{data}'

            curves.append(curve)
            closeds.append(closed)

        return cls(curves, closeds)

    @staticmethod
    def _sort_nodes(nodes: List[Curve18], n: int) -> None:
        for i in range(0, len(nodes), n):
            nodes[i : i + n] = sorted(nodes[i : i + n], key=lambda p: p.index)

    def get_svg_path(self) -> inkex.Path:
        path = inkex.Path()
        for curve, closed in zip(self.curves, self.closed):
            # Paths sometimes start with a (symmetric) invisible handle on the first node,
            # we skip that. In that case the outgoing handle also has
            # index: 2 = incoming handle, 0 = node, 1 = outgoing handle
            i = 0
            while curve[i].index != 0:
                i += 1

            path.append(inkex.paths.Move(*curve[i].point))
            i += 1
            while i < len(curve):
                p1 = curve[i]
                if p1.index == 0:
                    path.append(inkex.paths.Line(*p1.point))
                    i += 1
                else:
                    if i + 2 >= len(curve):
                        break  # outgoing (symmetric) handle of the last node
                    last = path[-1].cend_point(0j, 0j)
                    p2 = curve[i + 1]
                    p3 = curve[i + 2]
                    assert p1.index == 1 and p2.index == 2 and p3.index == 0
                    if (
                        math.isclose(last.real, p1.point[0])
                        and math.isclose(last.imag, p1.point[1])
                        and math.isclose(p2.point[0], p3.point[0])
                        and math.isclose(p2.point[1], p3.point[1])
                    ):
                        path.append(inkex.paths.Line(*p3.point))
                    else:
                        path.append(inkex.paths.Curve(*p1.point, *p2.point, *p3.point))

                    i += 3

            if closed:
                path.append(inkex.paths.ZoneClose())

        return path
