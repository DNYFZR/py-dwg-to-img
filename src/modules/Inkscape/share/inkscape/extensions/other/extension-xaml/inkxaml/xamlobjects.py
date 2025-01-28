#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2020-2022 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
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

"""XAML Object structure and XAML (LXML) parsing utilities"""


from __future__ import annotations
from typing import Optional, Union, List, Dict, Callable
import random
import re

Number = Union[int, float]

from lxml import etree
import inkex
from inkex.elements._utils import removeNS as inkexRemoveNS

from .export.config import GLOBAL_SETTINGS


class NodeBasedXAMLLookup(etree.PythonElementClassLookup):
    """Lookup for etree custom element classes"""

    def lookup(self, doc, element):  # pylint: disable=unused-argument
        """Lookup called by lxml when assigning elements their object class"""
        try:
            result = globals()[removeNS(element.tag)[-1]]
        except TypeError:
            result = None
        except KeyError:
            result = BaseElement
        return result


XAML_PARSER = etree.XMLParser(huge_tree=True)
XAML_PARSER.set_element_class_lookup(NodeBasedXAMLLookup())


def addNS(tag, ns=None):  # pylint: disable=invalid-name
    """Add a known namespace to a name for use with lxml"""
    return inkex.addNS(tag, ns, GLOBAL_SETTINGS.xaml_namespaces)


def removeNS(name):  # pylint: disable=invalid-name
    """The reverse of addNS, finds any namespace and returns tuple (ns, tag)"""
    return inkexRemoveNS(name, GLOBAL_SETTINGS.xaml_namespaces_reversed, default="xaml")


KEY_ATTR = "x:Key"


class XAMLObject(etree.ElementBase):
    """Base class for XAML objects"""

    PARSER = XAML_PARSER
    NAMESPACE = property(lambda self: GLOBAL_SETTINGS.xaml_namespaces["xaml"])
    TAG = property(lambda self: removeNS(self.classtag())[-1])

    text: str

    @classmethod
    def classtag(cls) -> str:
        """Returns the xml tag of this class"""
        return cls.__name__

    @property
    def tag(self) -> str:
        """Returns the xml tag of this element (i.e. the tag of the elements's class)"""
        return self.__class__.classtag()

    @staticmethod
    def sanitize_name(name):
        """Replace all non-alphanumeric characters; more precise validation would be
        https://docs.microsoft.com/en-us/dotnet/desktop/xaml-services/xamlname-grammar
        also ensure that the first character is not a number"""
        result = re.sub("[^0-9a-zA-Z]", "_", name)
        return re.sub(r"^(\d.*)", r"_\1", result)

    @staticmethod
    def make_key_unique(parent, element: BaseElement, key=KEY_ATTR, force=True):
        """Makes sure that an element does not create a key collision. If so, the key is
        changed to the existing key (or the element tag if not set) + underscore
        + random number"""
        current_key = element.get(key, None)
        if current_key is not None:
            current_key = BaseElement.sanitize_name(current_key)
            element.set(key, current_key)
        newkey = False
        if current_key is None:
            if force:
                newkey = True
                current_key = element.tag
            else:
                # No key is set, there is no danger for collision.
                return

        xpath = f"//*[@{key}='{element.get(key)}']"
        elements = parent.xpath(xpath)
        if len(elements) > 2 or (len(elements) == 1 and elements[0] != element):
            newkey = True
        temp_key = current_key
        while newkey or len(parent.xpath(f"//*[@{key}='{temp_key}']")) > 0:
            temp_key = f"{current_key}_{random.randint(0, 1000)}"
            newkey = False
        element.set(addNS(key), temp_key)

    def get_tag_name(self, prop: str) -> str:
        """Get the tag name for a property"""
        prop = ":".join(removeNS(prop))
        if prop.startswith("xaml:"):
            prop = prop[5:]
        if ":" in prop:
            return prop
        return f"{self.tag}.{prop}"

    def set(self, name, val):
        """Check if the attribute is already set, in this case delete it.
        Otherwise set it."""
        self.remove_property(name)
        if isinstance(val, str):
            super().set(addNS(name), val)
        elif isinstance(val, (int, float)):
            super().set(addNS(name), str(val))
        elif isinstance(val, list):
            super().set(addNS(name), ",".join(map(str, val)))
        elif isinstance(val, BaseElement):
            # Order of children:
            # Property Element(s) -> text -> child1 -> child1.tail -> c2 -> c2.tail
            prophandle = etree.Element(self.get_tag_name(name))
            self.insert(0, prophandle)
            if self.text != "":
                prophandle.tail = self.text
                self.text = ""
            prophandle.append(val)

    def remove_property(self, name):
        """Remove a property"""
        for node in self:
            if super(etree.ElementBase, node).tag == self.get_tag_name(name):
                self.remove(node)
        if addNS(name) in self.keys():
            self.attrib.pop(addNS(name))  # pylint: disable=no-member

    def get(self, name, default=None):
        if ":" not in name:
            for node in self.xpath("/" + self.get_tag_name(name)):
                return node
        return super().get(addNS(name), default)

    def add_property(
        self,
        name: str,
        val: Optional[Union[str, Number, XAMLObject, List[Number]]],
        default=None,
    ):
        """Add a property if not None"""
        if val is not None:
            if val == default:
                self.remove_property(name)
            else:
                self.set(name, val)

    def add_properties(
        self, properties: Dict[str, Union[str, XAMLObject, Number, List[Number]]]
    ):
        """Add multiple properties if not None"""
        for key, value in properties.items():
            self.add_property(key, value)

    def add_children(self, children: List[XAMLObject]):
        """Append multiple children"""
        for child in children:
            self.append(child)

    def add_name(self, name: str):
        """Adding names lead to an exception when parsing the XAML if it's wrapped in a
        resource dictionary."""

    @property
    def key(self):
        """Get the objects' x:Key attribute."""
        return self.get(KEY_ATTR, None)

    @property
    def root(self):
        """Get the root ResourceDictionary from any element descendent"""
        if self.getparent() is not None:
            return self.getparent().root
        if not isinstance(self, ResourceDictionary):
            raise ValueError(
                "Element fragment does not have a ResourceDictionary root!"
            )
        return self

    def add_child(self, element: Optional[XAMLObject], front=False):
        """Append/insert a child if not none"""
        if element is None:
            return
        if not front:
            self.append(element)
        else:
            # TODO append after property elements
            self.insert(0, element)

    @staticmethod
    def remove_key(element):
        """remove the x:key attribute if set"""
        if element.get(KEY_ATTR, None) is not None:
            element.attrib.pop(addNS(KEY_ATTR))

    def append(self, element):
        """Append without key (key is only valid inside ResourceDictionary)"""
        BaseElement.remove_key(element)
        self.make_key_unique(self, element, "Name", False)
        super().append(element)

    def insert(self, index, element):
        """Insert without key (key is only valid inside ResourceDictionary)"""
        BaseElement.remove_key(element)
        self.make_key_unique(self, element, "Name", False)
        super().insert(index, element)

    def xpath(self, expr, namespaces=None):
        return super().xpath(
            expr, namespaces=namespaces or GLOBAL_SETTINGS.xaml_namespaces
        )

    def parse_transform(self, attribute="Transform") -> inkex.Transform:
        """Reads the transform attribute and returns an inkex.Transform object.
        This currently does not support TransformGroup"""
        read = self.get(attribute, None)
        if read is None:
            return inkex.Transform()
        return inkex.Transform(f"matrix({read})")

    def __str__(self):
        return f"{self.TAG} element with {len(self.getchildren())} children"

    def set_invisible(self):
        """Makes an element invisible"""
        self.add_property("ClipGeometry", "")

    @staticmethod
    def transform_to_xaml(transform: inkex.Transform):
        """Converts an inkex Transform struct to an XAML object representation"""
        as_string = ",".join(map(str, transform.to_hexad()))
        if GLOBAL_SETTINGS.avalonia:
            result = MatrixTransform()
            result.set("Matrix", as_string)
            return result
        return as_string

    def set_transform(self, transform: inkex.Transform):
        """Sets a transform on an object"""
        if transform != inkex.Transform():  # don't add the identity transform
            self.add_property("Transform", self.transform_to_xaml(transform))


class BaseElement(XAMLObject):
    """Superclass for any XAML object"""


class ResourceDictionary(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.resourcedictionary"""

    def insert_wrapper(self, element: BaseElement, insert_function: Callable):
        """Inserting with unique key"""
        self.make_key_unique(self, element)
        key = element.get(KEY_ATTR, None)
        result = insert_function(element)
        element.set(addNS(KEY_ATTR), key)
        return result

    def append(self, element: BaseElement):
        """Appending with unique key"""
        return self.insert_wrapper(element, super().append)

    def insert(self, index: int, element: BaseElement):
        """Inserting with unique key"""
        inserter = super().insert
        return self.insert_wrapper(element, lambda el: inserter(index, el))

    def get_child(self, key):
        """Finds a direct subchild based on key"""
        for i in self.iterdescendants():
            if i.get(KEY_ATTR) == key:
                return i
        return None


class Drawing(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.drawing"""


class DrawingGroup(Drawing):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.drawinggroup"""


class GeometryDrawing(Drawing):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.geometrydrawing"""


class Geometry(Drawing):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.geometry"""


class PathGeometry(Geometry):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.pathgeometry"""


class LineGeometry(Geometry):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.linegeometry"""


class RectangleGeometry(Geometry):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.rectanglegeometry"""


class EllipseGeometry(Geometry):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.ellipsegeometry"""


class Brush(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.brush"""


class SolidColorBrush(Brush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.solidcolorbrush"""


class DrawingBrush(Brush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.drawingbrush"""


class GradientBrush(Brush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.gradientbrush"""


class LinearGradientBrush(GradientBrush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.lineargradientbrush"""


class RadialGradientBrush(GradientBrush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.radialgradientbrush"""


class VisualBrush(Brush):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.visualbrush"""


class Pen(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.pen"""


class DashStyle(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.dashstyle"""


class GradientStop(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.gradientstop"""


class DrawingImage(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.drawingimage"""


class UIElement(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.controls.uielement"""

    def set_invisible(self):
        if GLOBAL_SETTINGS.wpf:
            self.add_property("Visibility", "Hidden")
        else:
            self.add_property("IsVisible", "False")

    def set_transform(self, transform: inkex.Transform):
        if transform != inkex.Transform():
            self.add_property("RenderTransform", self.transform_to_xaml(transform))
            if GLOBAL_SETTINGS.avalonia:
                self.add_property("RenderTransformOrigin", "0,0")


class Canvas(UIElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.controls.canvas"""


class Viewbox(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.controls.viewbox"""


class Shape(UIElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.shape"""


class Path(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.path"""


class Rectangle(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.rectangle"""


class Polygon(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.polygon"""


class Polyline(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.polyline"""


class Line(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.line"""


class Ellipse(Shape):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.shapes.ellipse"""


class GeometryGroup(Geometry):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.geometrygroup"""


class MatrixTransform(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.matrixtransform"""


class BlurEffect(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.media.effects.blureffect"""


class TextBlock(UIElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.controls.textblock"""


class Span(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.documents.span"""


class LineBreak(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.documents.linebreak"""


class TextDecoration(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.textdecoration"""


class TextDecorationCollection(BaseElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.textdecorationcollection"""


class Grid(UIElement):
    """Interface for
    https://docs.microsoft.com/dotnet/api/system.windows.controls.grid"""
