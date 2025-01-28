#!/usr/bin/env python3
"""Replace color extension"""

import inkex


class ReplaceColor(inkex.ColorExtension):
    """Replace color in SVG with another"""

    pass_rgba = True

    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument(
            "-f",
            "--from_color",
            default=inkex.Color("black"),
            type=inkex.Color,
            help="Replace color",
        )
        pars.add_argument(
            "-t",
            "--to_color",
            default=inkex.Color("red"),
            type=inkex.Color,
            help="By color",
        )
        pars.add_argument(
            "-i",
            "--ignore_opacity",
            default=True,
            type=inkex.Boolean,
            help="Whether color should be replaced regardless of opacity match",
        )

    def modify_color(self, name, color):  # color is rgba
        if self.options.from_color.to_rgb() == color.to_rgb() and (
            self.options.ignore_opacity
            or abs(self.options.from_color.to_rgba().alpha - color.alpha) < 0.01
        ):
            return self.options.to_color.to_rgba()
        return color


if __name__ == "__main__":
    ReplaceColor().run()
