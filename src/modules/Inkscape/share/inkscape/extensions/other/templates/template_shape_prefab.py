#!/usr/bin/env python3
# coding=utf-8

import os
from inkex import load_svg, TemplateExtension


class ShapeBuilderTemplate(TemplateExtension):
    """Generate shape builder pattern"""

    def add_arguments(self, pars):
        pars.add_argument("--svg", help="Template to load")

    def get_size(self):
        return (900, "px", 900, "px")

    def get_template(self, **kwargs):
        path = os.path.dirname(os.path.realpath(__file__))
        return load_svg(os.path.join(path, self.options.svg))

    def set_namedview(self, width_px, height_px, unit):
        pass


if __name__ == "__main__":
    ShapeBuilderTemplate().run()
