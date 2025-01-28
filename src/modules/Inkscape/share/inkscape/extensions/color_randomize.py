#!/usr/bin/env python3
"""Randomise the selected item's colours using hsl colorspace"""

from random import randrange, uniform, seed
import inkex
from inkex.localization import inkex_gettext as _


def _rand(
    limit, value, roof=255, method=randrange, circular=False, deterministic=False
):
    """Generates a random number which is less than limit % away from value, using the method
    supplied."""
    if deterministic:
        if isinstance(value, float):
            seed(int(value * 1000))
        else:
            seed(value)
    limit = roof * float(limit) / 100
    limit /= 2
    max_ = type(roof)(value + limit)
    min_ = type(roof)(value - limit)
    if not (circular):
        if max_ > roof:
            min_ -= max_ - roof
            max_ = roof
        if min_ < 0:
            max_ -= min_
            min_ = 0
        return method(min_, max_)
    return method(min_, max_) % roof


class Randomize(inkex.ColorExtension):
    """Randomize the colours of all objects"""

    deterministic_output = False

    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("-y", "--hue_range", type=int, default=0, help="Hue range")
        pars.add_argument(
            "-t", "--saturation_range", type=int, default=0, help="Saturation range"
        )
        pars.add_argument(
            "-m", "--lightness_range", type=int, default=0, help="Lightness range"
        )
        pars.add_argument(
            "-o", "--opacity_range", type=int, default=0, help="Opacity range"
        )

    def _rand(self, limit, value, roof=255, method=randrange, circular=False):
        return _rand(
            limit,
            value,
            roof,
            method,
            circular,
            deterministic=self.deterministic_output,
        )

    def modify_color(self, name, color):
        hsl = color.to_hsl()
        if self.options.hue_range > 0:
            hsl.hue = int(self._rand(self.options.hue_range, hsl.hue, circular=True))
        if self.options.saturation_range > 0:
            hsl.saturation = int(
                self._rand(self.options.saturation_range, hsl.saturation)
            )
        if self.options.lightness_range > 0:
            hsl.lightness = int(self._rand(self.options.lightness_range, hsl.lightness))
        return hsl.to_rgb()

    def modify_opacity(self, name, opacity):
        if name != "opacity":
            return opacity
        try:
            opacity = float(opacity)
        except ValueError:
            self.msg(_("Ignoring unusual opacity value: {}").format(opacity))
            return opacity
        orange = self.options.opacity_range
        if orange > 0:
            return self._rand(orange, opacity, roof=1.0, method=uniform)
        return opacity


if __name__ == "__main__":
    Randomize().run()
