#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2021 Martin Owens <doctormo@gmail.com>
# Copyright 2022 Simon Duerr <dev@simonduerr.eu>
#
# This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>
#
"""
Import images from the internet, inkscape extension (GUI)
"""

__version__ = "1.0"
__pkgname__ = "inkscape-import-web-image"

import os
import sys
import logging
import warnings

warnings.filterwarnings("ignore")

from collections import defaultdict
from base64 import encodebytes
from appdirs import user_cache_dir

import inkex
from inkex import Style
from inkex.gui import GtkApp, Window, IconView, asyncme
from inkex.gui.pixmap import PixmapManager, SizeFilter, PadFilter, OverlayFilter
from inkex.elements import (
    load_svg,
    Image,
    Defs,
    NamedView,
    Metadata,
    SvgDocumentElement,
    StyleElement,
)
from gi.repository import Gtk

from import_sources import RemoteSource, RemoteFile, RemotePage

SOURCES = os.path.join(os.path.dirname(__file__), "sources")
LICENSES = os.path.join(os.path.dirname(__file__), "licenses")
CACHE_DIR = user_cache_dir("inkscape-import-web-image", "Inkscape")


class LicenseOverlay(OverlayFilter):
    pixmaps = PixmapManager(LICENSES)

    def get_overlay(self, item=None, manager=None):
        if item is None:  # Default image
            return None
        return self.pixmaps.get(item.get_overlay())


class ResultsIconView(IconView):
    """The search results shown as icons"""

    def get_markup(self, item):
        return item.string

    def get_icon(self, item):
        return item.icon

    def setup(self):
        self._list.set_markup_column(1)
        self._list.set_pixbuf_column(2)
        crt, crp = self._list.get_cells()
        self.crt_notify = crt.connect("notify", self.keep_size)
        super().setup()

    def keep_size(self, crt, *args):
        """Hack Gtk to keep cells smaller"""
        crt.handler_block(self.crt_notify)
        crt.set_property("width", 150)
        crt.handler_unblock(self.crt_notify)


class ImporterWindow(Window):
    """The window that is in the glade file"""

    name = "import_web_image"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.widget("dl-searching").hide()

        # Add each of the source services from their plug-in modules
        self.source = self.widget("service_list")
        self.source_model = self.source.get_model()
        self.source_model.clear()

        RemoteSource.load(SOURCES)
        pix = PixmapManager(SOURCES, size=150)
        for x, (key, source) in enumerate(RemoteSource.sources.items()):
            if not source.is_enabled:
                continue
            # We add them in GdkPixbuf, string, string format (see glade file)
            self.source_model.append([pix.get(source.icon), source.name, key])
            if source.is_default:
                self.source.set_active(x)

        pixmaps = PixmapManager(
            CACHE_DIR,
            filters=[
                SizeFilter(size=150),
                PadFilter(size=(0, 150)),
                LicenseOverlay(position=(0.5, 1)),
            ],
        )
        self.select_func = self.gapp.kwargs["select"]
        self.results = ResultsIconView(self.widget("results"), pixmaps)
        self.pool = ResultsIconView(self.widget("pool"), pixmaps)
        self.multiple = False

        self.widget("perm-nocopyright").set_message_type(Gtk.MessageType.WARNING)

    def select_image(self, widget):
        """Callback when clicking on an image in the result list"""
        for item_path in self.widget("results").get_selected_items():
            item_iter = self.results._model.get_iter(item_path)
            item = self.results._model[item_iter][0]
            self.show_license(item)
        self.update_btn_import()

    def show_license(self, item):
        """Display the current item's license information"""
        self.widget("perms").foreach(lambda w: w.hide())
        info = item.license_info
        for mod in info["modules"]:
            self.widget("perm-" + mod).show()

    def get_selected_source(self):
        """Return the selected source class"""
        _iter = self.source.get_active_iter()
        key = self.source_model[_iter][2]
        return RemoteSource.sources[key](CACHE_DIR)

    def img_multiple(self, widget):
        """Enable multi-selection"""
        widget.hide()
        self.widget("btn-single").show()
        self.widget("multiple-box").show()
        self.widget("multiple-buttons").show()
        self.multiple = True
        self.update_btn_import()

    def img_single(self, widget):
        """Enable single-selection"""
        widget.hide()
        self.widget("btn-multiple").show()
        self.widget("multiple-box").hide()
        self.widget("multiple-buttons").hide()
        is_selected = bool(list(self.results.get_selected_items()))
        self.pool.clear()
        self.multiple = False
        self.update_btn_import()

    def img_add(self, widget=None):
        """Add an item from the search to the multi-pool"""
        self.pool.add(self.results.get_selected_items())
        self.update_btn_import()

    def img_remove(self, widget=None):
        """Remove any selected items from the multi-pool"""
        for item in self.pool.get_selected_items():
            self.pool.remove_item(item)
        self.update_btn_import()

    def update_btn_import(self):
        """Set the import button to enabled or disabled"""
        enabled = False
        if self.multiple:
            enabled = bool(list(self.pool))
        else:
            enabled = bool(list(self.results.get_selected_items()))
        self.widget("btn-import").set_sensitive(enabled)

    def result_activate(self, widget=None):
        """Search results double click"""
        if self.multiple:
            self.img_add()
        else:
            self.img_import()

    def img_import(self, widget=None):
        """Apply the selected image and quit"""
        items = []
        if not self.multiple:
            items.extend(self.results.get_selected_items())
        else:
            items.extend([item for item, *_ in self.pool])

        to_exit = True
        for item in items:
            self.select_func(item.get_file())
            # XXX This pagination control is not good. Replace it with normal controls.
            # elif isinstance(item, RemotePage):
        if to_exit:
            self.exit()

    def search(self, widget):
        """Remote search activation"""
        query = widget.get_text()
        if len(query) > 2:
            self.search_clear()
            self.search_started()
            self.async_search(query)

    @asyncme.run_or_none
    def async_search(self, query):
        """Asyncronous searching in PyPI"""
        for resource in self.get_selected_source().file_search(query):
            self.add_search_result(resource)
        self.search_finished()

    @asyncme.mainloop_only
    def add_search_result(self, resource):
        """Adding things to Gtk must be done in mainloop"""
        if isinstance(resource, RemotePage):
            return self.set_next_page(resource)

        self.results.add_item(resource)

    def search_clear(self, widget=None):
        """Remove previous search"""
        self.results.clear()
        self.update_btn_import()
        self.next_page_item = None
        self.widget("btn-next-page").hide()

    def search_started(self):
        """Set widgets to stun"""
        self.widget("dl-search").set_sensitive(False)
        self.widget("dl-searching").start()
        self.widget("dl-searching").show()

    @asyncme.mainloop_only
    def search_finished(self):
        """After everything, finish the search"""
        self.widget("dl-search").set_sensitive(True)
        self.widget("dl-searching").hide()
        self.widget("dl-searching").stop()

    def set_next_page(self, item):
        self.next_page_item = item
        self.widget("btn-next-page").show()

    def show_next_page(self, widget=None):
        item = self.next_page_item
        if item:
            self.search_clear()
            self.search_started()
            self.async_next_page(item)

    @asyncme.run_or_none
    def async_next_page(self, item):
        for resource in item.get_next_page():
            self.add_search_result(resource)
        self.search_finished()


class App(GtkApp):
    """Load the inkscape extensions glade file and attach to window"""

    glade_dir = os.path.join(os.path.dirname(__file__))
    app_name = "inkscape-import-web-image"
    windows = [ImporterWindow]


class ImportWebImage(inkex.EffectExtension):
    """Import an svg from the internet"""

    selected_filename = None

    def merge_defs(self, defs):
        """Add all the items in defs to the self.svg.defs"""
        target = self.svg.defs
        for child in defs:
            if isinstance(child, StyleElement):
                continue  # Already appled in merge_stylesheets()
            target.append(child)

    def merge_stylesheets(self, svg):
        """Because we don't want conflicting style-sheets (classes, ids, etc) we scrub them"""
        elems = defaultdict(list)
        # 1. Find all styles, and all elements that apply to them
        for sheet in svg.getroot().stylesheets:
            for style in sheet:
                xpath = style.to_xpath()
                for elem in svg.xpath(xpath):
                    elems[elem].append(style)
                    # 1b. Clear possibly conflicting attributes
                    if "@id" in xpath:
                        elem.set_random_id()
                    if "@class" in xpath:
                        elem.set("class", None)
        # 2. Apply each style cascade sequentially
        for elem, styles in elems.items():
            output = Style()
            for style in styles:
                output += style
            elem.style = output + elem.style

    def import_svg(self, new_svg):
        """Import an svg file into the current document"""
        self.merge_stylesheets(new_svg)
        for child in new_svg.getroot():
            if isinstance(child, SvgDocumentElement):
                yield from self.import_svg(child)
            elif isinstance(child, StyleElement):
                continue  # Already applied in merge_stylesheets()
            elif isinstance(child, Defs):
                self.merge_defs(child)
            elif isinstance(child, (NamedView, Metadata)):
                pass
            else:
                yield child

    def import_from_file(self, filename):
        if not filename or not os.path.isfile(filename):
            return
        with open(filename, "rb") as fhl:
            head = fhl.read(100)
            if b"<?xml" in head or b"<svg" in head:
                new_svg = load_svg(head + fhl.read())
                # Add each object to the container
                objs = list(self.import_svg(new_svg))

                if len(objs) == 1 and isinstance(objs[0], inkex.Group):
                    # Prevent too many groups, if item aready has one.
                    container = objs[0]
                else:
                    # Make a new group to contain everything
                    container = inkex.Group()
                    for child in objs:
                        container.append(child)

                # Retain the original filename as a group label
                container.label = os.path.basename(filename)
                # Apply unit transformation to keep things the same sizes.
                container.transform.add_scale(
                    self.svg.unittouu(1.0) / new_svg.getroot().unittouu(1.0)
                )

            else:
                container = self.import_raster(filename, fhl)

            self.svg.get_current_layer().append(container)

            # Make sure that none of the new content is a layer.
            for child in container.descendants():
                if isinstance(child, inkex.Group):
                    child.set("inkscape:groupmode", None)

    def effect(self):
        def select_func(filename):
            self.import_from_file(filename)

        App(start_loop=True, select=select_func)

    def import_raster(self, filename, handle):
        """Import a raster image"""
        # Don't read the whole file to check the header
        handle.seek(0)
        file_type = self.get_type(filename, handle.read(10))
        handle.seek(0)

        if file_type:
            # Future: Change encodestring to encodebytes when python3 only
            node = Image()
            node.label = os.path.basename(filename)
            node.set(
                "xlink:href",
                "data:{};base64,{}".format(
                    file_type, encodebytes(handle.read()).decode("ascii")
                ),
            )
            return node

    @staticmethod
    def get_type(path, header):
        """Basic magic header checker, returns mime type"""
        # Taken from embedimage.py
        for head, mime in (
            (b"\x89PNG", "image/png"),
            (b"\xff\xd8", "image/jpeg"),
            (b"BM", "image/bmp"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"MM\x00\x2a", "image/tiff"),
            (b"II\x2a\x00", "image/tiff"),
        ):
            if header.startswith(head):
                return mime
        return None


if __name__ == "__main__":
    ImportWebImage().run()
