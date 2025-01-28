#!/usr/bin/env python3
"""
Convert PNG to Tiff using Raster Output extension.
"""

import io
import inkex


class TiffOutput(inkex.RasterOutputExtension):
    def add_arguments(self, pars):
        pars.add_argument("--tab")
        pars.add_argument("--compression", default=None)
        pars.add_argument("--quality", type=int, default=90)

    def save(self, stream):
        tempstream = io.BytesIO()
        self.img.save(
            tempstream,
            format="tiff",
            compression=(self.options.compression or None),
            dpi=self.img.info["dpi"],
        )
        stream.write(tempstream.getvalue())
        # TODO: Add other fields such as copyright etc.


if __name__ == "__main__":
    TiffOutput().run()
