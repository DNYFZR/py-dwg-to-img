#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2012 Alvin Penner, penner@vaxxine.com
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
This extension will generate vector graphics printout, specifically for Windows GDI32.

This is a modified version of the file dxf_outlines.py by Aaron Spike, aaron@ekips.org
It will write only to the default printer.
The printing preferences dialog will be called.
In order to ensure a pure vector output, use a linewidth < 1 printer pixel

- see http://www.lessanvaezi.com/changing-printer-settings-using-the-windows-api/
- get GdiPrintSample.zip at http://archive.msdn.microsoft.com/WindowsPrintSample

"""

import sys
import ctypes
import struct

import inkex
from inkex import (
    PathElement,
    ShapeElement,
    Rectangle,
    Group,
    Use,
    Transform,
    Line,
    Circle,
    Ellipse,
)
from inkex.paths import Path

if sys.platform.startswith("win"):
    # The wintypes module raises a ValueError when imported on non-Windows systems
    # for certain Python versions.
    from ctypes import wintypes

    myspool = ctypes.WinDLL("winspool.drv")
    mygdi = ctypes.WinDLL("gdi32.dll")

    class LOGBRUSH(ctypes.Structure):
        _fields_ = [
            ("lbStyle", wintypes.UINT),
            ("lbColor", wintypes.COLORREF),
            ("lbHatch", wintypes.PULONG),
        ]

    DM_IN_PROMPT = 4  # call printer property sheet
    DM_OUT_BUFFER = 2  # write to DEVMODE structure

    LOGPIXELSX = 88
    LOGPIXELSY = 90

    class DOCINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_int),
            ("lpszDocName", wintypes.LPCSTR),
            ("lpszOutput", wintypes.LPCSTR),
            ("lpszDatatype", wintypes.LPCSTR),
            ("fwType", wintypes.DWORD),
        ]

    StartDocA = mygdi.StartDocA
    StartDocA.argtypes = [wintypes.HDC, ctypes.POINTER(DOCINFO)]
    StartDocA.restype = ctypes.c_int

    EndDoc = mygdi.EndDoc
    EndDoc.argtypes = [wintypes.HDC]
    EndDoc.restype = ctypes.c_int

    CreateDCA = mygdi.CreateDCA
    CreateDCA.argtypes = [
        wintypes.LPCSTR,
        wintypes.LPCSTR,
        wintypes.LPCSTR,
        wintypes.LPCVOID,
    ]
    CreateDCA.restype = wintypes.HDC

    GetDefaultPrinterA = myspool.GetDefaultPrinterA
    GetDefaultPrinterA.argtypes = [wintypes.LPSTR, wintypes.LPDWORD]
    GetDefaultPrinterA.restype = wintypes.BOOL

    OpenPrinterA = myspool.OpenPrinterA
    OpenPrinterA.argtypes = [wintypes.LPSTR, wintypes.LPHANDLE, wintypes.LPCVOID]
    OpenPrinterA.restype = wintypes.BOOL

    ClosePrinter = myspool.ClosePrinter
    ClosePrinter.argtypes = [wintypes.HANDLE]
    ClosePrinter.restype = wintypes.BOOL

    DocumentPropertiesA = myspool.DocumentPropertiesA
    DocumentPropertiesA.argtypes = [
        wintypes.HWND,
        wintypes.HANDLE,
        wintypes.LPSTR,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    DocumentPropertiesA.restype = wintypes.LONG

    SelectObject = mygdi.SelectObject
    SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    SelectObject.restype = wintypes.HGDIOBJ

    MoveToEx = mygdi.MoveToEx
    MoveToEx.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCVOID]
    MoveToEx.restype = wintypes.BOOL

    CreateBrushIndirect = mygdi.CreateBrushIndirect
    CreateBrushIndirect.argtypes = [ctypes.POINTER(LOGBRUSH)]
    CreateBrushIndirect.restype = wintypes.HBRUSH

    CreatePen = mygdi.CreatePen
    CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.COLORREF]
    CreatePen.restype = wintypes.HPEN

    BeginPath = mygdi.BeginPath
    BeginPath.argtypes = [wintypes.HDC]
    BeginPath.restype = wintypes.BOOL

    EndPath = mygdi.EndPath
    EndPath.argtypes = [wintypes.HDC]
    EndPath.restype = wintypes.BOOL

    FillPath = mygdi.FillPath
    FillPath.argtypes = [wintypes.HDC]
    FillPath.restype = wintypes.BOOL

    PolyBezierTo = mygdi.PolyBezierTo
    PolyBezierTo.argtypes = [wintypes.HDC, wintypes.LPCVOID, wintypes.DWORD]

    GetDeviceCaps = mygdi.GetDeviceCaps
    GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    GetDeviceCaps.restype = ctypes.c_int


class PrintWin32Vector(inkex.EffectExtension):
    def __init__(self):
        super(PrintWin32Vector, self).__init__()

    def process_shape(self, node, mat):
        """Process shape"""
        pen_color = 0  # Stroke color
        fill_color = None  # Fill color
        pen_width = 1  # Pen width in printer pixels

        # Win32 API expect colors in 0x00bbggrr format.
        def to_bgr(color):
            color = color.to_rgb()
            return (color[2] << 16) + (color[1] << 8) + color[0]

        if not isinstance(node, (PathElement, Rectangle, Line, Circle, Ellipse)):
            return

        # Very NB : If the pen width is greater than 1 then the output will Not be a vector output !
        style = node.style
        if style:
            attr = style("stroke")
            if attr is not None and isinstance(attr, inkex.Color):
                pen_color = to_bgr(attr)
            attr = style("fill")
            if attr is not None and isinstance(attr, inkex.Color):
                fill_color = to_bgr(attr)
            if "stroke-width" in style:
                pen_width = self.svg.to_dimensionless(style("stroke-width").strip())
                pen_width = int(pen_width * self.scale_xy)

        path = node.path.to_superpath().transform(mat @ node.transform)

        hPen = CreatePen(0, pen_width, pen_color)
        SelectObject(self.hDC, hPen)
        self.emit_path(path)
        if fill_color is not None:
            brush = LOGBRUSH(0, fill_color, None)
            hBrush = CreateBrushIndirect(ctypes.byref(brush))
            SelectObject(self.hDC, hBrush)
            BeginPath(self.hDC)
            self.emit_path(path)
            EndPath(self.hDC)
            FillPath(self.hDC)
        return

    def emit_path(self, p):
        for sub in p:
            MoveToEx(self.hDC, int(sub[0][1][0]), int(sub[0][1][1]), None)
            POINTS = ctypes.c_long * (6 * (len(sub) - 1))
            points = POINTS()
            for i in range(len(sub) - 1):
                points[6 * i] = int(sub[i][2][0])
                points[6 * i + 1] = int(sub[i][2][1])
                points[6 * i + 2] = int(sub[i + 1][0][0])
                points[6 * i + 3] = int(sub[i + 1][0][1])
                points[6 * i + 4] = int(sub[i + 1][1][0])
                points[6 * i + 5] = int(sub[i + 1][1][1])
            PolyBezierTo(self.hDC, ctypes.addressof(points), 3 * (len(sub) - 1))

    def process_clone(self, node):
        trans = node.get("transform")
        x = node.get("x")
        y = node.get("y")
        mat = Transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        if trans:
            mat @= Transform(trans)
        if x:
            mat @= Transform([[1.0, 0.0, float(x)], [0.0, 1.0, 0.0]])
        if y:
            mat @= Transform([[1.0, 0.0, 0.0], [0.0, 1.0, float(y)]])
        # push transform
        if trans or x or y:
            self.groupmat.append(Transform(self.groupmat[-1]) @ mat)
        # get referenced node
        refnode = node.href
        if refnode is not None:
            if isinstance(refnode, inkex.Group):
                self.process_group(refnode)
            elif refnode.tag == "svg:use":
                self.process_clone(refnode)
            else:
                self.process_shape(refnode, self.groupmat[-1])
        # pop transform
        if trans or x or y:
            self.groupmat.pop()

    def process_group(self, group):
        trans = group.get("transform")
        if trans:
            self.groupmat.append(self.groupmat[-1] @ Transform(trans))
        for node in group:
            if not isinstance(node, ShapeElement) or not node.is_visible():
                continue
            if isinstance(node, Group):
                self.process_group(node)
            elif isinstance(node, Use):
                self.process_clone(node)
            else:
                self.process_shape(node, self.groupmat[-1])
        if trans:
            self.groupmat.pop()

    def doc_name(self):
        docname = self.svg.xpath("@sodipodi:docname")
        if not docname:
            docname = ["New document 1"]
        return ctypes.create_string_buffer(
            ("Inkscape " + docname[0].split("\\")[-1]).encode("ascii", "replace")
        )

    def effect(self):
        pcchBuffer = wintypes.DWORD()
        GetDefaultPrinterA(None, ctypes.byref(pcchBuffer))  # get length of printer name
        pname = ctypes.create_string_buffer(pcchBuffer.value)
        GetDefaultPrinterA(pname, ctypes.byref(pcchBuffer))  # get printer name
        hPrinter = wintypes.HANDLE()
        if OpenPrinterA(pname.value, ctypes.byref(hPrinter), None) == 0:
            return inkex.errormsg(_("Failed to open default printer"))

        # get printer properties dialog
        pcchBuffer = DocumentPropertiesA(0, hPrinter, pname, None, None, 0)
        pDevMode = ctypes.create_string_buffer(
            pcchBuffer + 100
        )  # allocate extra just in case
        pcchBuffer = DocumentPropertiesA(
            0,
            hPrinter,
            pname,
            ctypes.byref(pDevMode),
            None,
            DM_IN_PROMPT + DM_OUT_BUFFER,
        )
        ClosePrinter(hPrinter)
        if pcchBuffer != 1:  # user clicked Cancel
            exit()

        # initialize print document
        lpszDocName = self.doc_name()
        docInfo = DOCINFO(
            ctypes.sizeof(DOCINFO), ctypes.addressof(lpszDocName), 0, 0, 0
        )
        self.hDC = CreateDCA(None, pname, None, ctypes.byref(pDevMode))
        if StartDocA(self.hDC, ctypes.byref(docInfo)) < 0:
            exit()  # user clicked Cancel

        # Take the DPI value from the DC instead of extracting it from pDevMode, this
        # method works when print drivers return device-independent quality values (e.g.
        # DMRES_MEDIUM).
        dpi_x = GetDeviceCaps(self.hDC, LOGPIXELSX)
        dpi_y = GetDeviceCaps(self.hDC, LOGPIXELSY)
        # Convert from dots-per-inch (DPI) to user units.
        self.scale_x = dpi_x / self.svg.viewport_to_unit("1in")
        self.scale_y = dpi_y / self.svg.viewport_to_unit("1in")

        doc = self.document.getroot()
        # Process viewBox height attribute to correct page scaling.
        viewBox = self.svg.get_viewbox()
        if viewBox and viewBox[2] and viewBox[3]:
            doc_width = self.svg.viewbox_width
            doc_height = self.svg.viewbox_height
            self.scale_x *= doc_width / self.svg.viewport_to_unit(
                self.svg.add_unit(viewBox[2])
            )
            self.scale_y *= doc_height / self.svg.viewport_to_unit(
                self.svg.add_unit(viewBox[3])
            )

        self.scale_xy = (self.scale_x + self.scale_y) / 2
        self.groupmat = [
            Transform([[self.scale_x, 0.0, 0.0], [0.0, self.scale_y, 0.0]])
        ]
        self.process_group(doc)
        EndDoc(self.hDC)


if __name__ == "__main__":
    PrintWin32Vector().run()
