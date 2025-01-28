#!/usr/bin/env python3
"""List all colors used in an svg document"""

from collections import defaultdict
from typing import Dict
import inkex


class ListColours(inkex.ColorExtension):
    """Make the colours darker"""

    _counts: Dict = defaultdict(int)

    def effect(self):
        self._counts = defaultdict(int)
        super().effect()
        items = sorted(self._counts.items(), key=lambda v: -v[1])
        for color, count in items:
            self.msg("{count}: {color}".format(color=color, count=count))

    def modify_color(self, name, color):
        self._counts[color] += 1
        return color


if __name__ == "__main__":
    ListColours().run()
