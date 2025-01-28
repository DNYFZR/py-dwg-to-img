#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Constants for the parser module
"""

file_magic = 0x414BFF00
content_magic = 0x534BFF00

expected_file_classes = [
    "Prsn",
    "Pref",
    "Adjm",
    "AstP",
    "CroP",
    "DevP",
    "Dcts",
    "DocP",
    "ExpP",
    "Fils",
    "GrdP",
    "Macs",
    "Objs",
    "OSty",
    "RBru",
    "Shps",
    "TonP",
    "TlSt",
    "VBru",
]

expected_documents = [
    "doc.dat",
    "newdoccontroller",
    "previews.dat",
    "preferences",
    "newdocstate",
    "session.dat",
    "structure",
    "content.dat",
    "templates.dat",
]
