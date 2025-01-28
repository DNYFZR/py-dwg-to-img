#!/usr/bin/env python3

# Copyright (C) 2024 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Decode parsed object structure to JSON, which
requires special handling of dataclasses and enums
"""

from dataclasses import is_dataclass, fields
import copy
from enum import Enum
import json


def asdict(o):
    """Modified version of dataclasses.asdict that doesn't trip
    over infinite recursion"""
    if is_dataclass(o):
        result = {}
        for f in fields(o):
            if f.name in ["parent", "_doc_id"]:
                continue
            if f.name == "fields":
                # Expand into the parent
                if isinstance(getattr(o, f.name), dict):
                    for k, v in getattr(o, f.name).items():
                        assert k not in result
                        result[k] = v
                else:
                    result[f.name] = asdict(getattr(o, f.name))
            else:
                result[f.name] = asdict(getattr(o, f.name))
        return result
    if isinstance(o, Enum):
        return str(o.name.lower().title().replace("_", ""))
    if isinstance(o, (list, tuple)):
        return type(o)(asdict(v) for v in o)
    if isinstance(o, dict):
        return type(o)((asdict(k), asdict(v)) for k, v in o.items())
    else:
        return copy.deepcopy(o)


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)

        if isinstance(o, bytes):
            return o.decode("latin-1")[:10] + "..."
        return super().default(o)
