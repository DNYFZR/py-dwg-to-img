#!/usr/bin/env python3
"""
Testing tool for running queries.
"""

import sys
import json

from import_sources import RemoteSource


def run():
    RemoteSource.load("sources")
    source = RemoteSource.sources[sys.argv[1]]("/tmp")

    for item in source.search(sys.argv[2]):
        if callable(item):
            print(f"Next Page {item}")
        else:
            print(json.dumps(item, indent=2))


if __name__ == "__main__":
    run()
