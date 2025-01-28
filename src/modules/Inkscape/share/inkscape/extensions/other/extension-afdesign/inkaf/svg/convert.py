#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Manpreet Singh <manpreet.singh.dev@proton.me>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import traceback
from typing import List, Optional, Tuple, Union

import inkex
import lxml.etree
from inkex.base import SvgOutputMixin

from inkaf.svg.fill import (
    AFColor,
    AFGradient,
    AFGradientStop,
    AFGradientType,
    parse_fdsc,
)
from inkaf.svg.util import (
    MAX_CLIP_PATH_RECURSION,
    AFBoundingBox,
    ClipPathRecursionError,
    get_transformed_bbox,
    interpolate_float,
)

from ..parser.types import AFObject, Document, EnumT
from .curve import AFCurve
from .shape import (
    AFCornerPos,
    AFCornerType,
    AFEllipse,
    AFPointsShapeBase,
    AFRectangle,
    AFShape,
    corner_map,
    parse_shape,
)
from .styles import (
    AF_BLEND_MODES,
    SVG_BLEND_MODES,
    AFBlendModeV0,
    AFStroke,
    AFStrokeJoin,
    AFStrokeOrder,
    AFStrokeType,
    parse_fill,
    parse_stroke,
    parse_stroke_color,
    parse_transform,
    stroke_cap_map,
    stroke_join_map,
    stroke_order_map,
)
from .text import (
    TEXT_TYPES,
    AFGlyphAtt,
    AFParaAlign,
    AFParaAtt,
    AFText,
    AFTextLineStyle,
    AFTextType,
)


class AFConverter:
    def __init__(self, afdoc: Document) -> None:
        self.afdoc = afdoc
        self.doc: lxml.etree._ElementTree
        self.document: inkex.SvgDocumentElement
        self._page_label = ""
        self._has_artboards = False

    def convert(self) -> None:
        self.doc = inkex.SvgDocumentElement = SvgOutputMixin.get_template(
            width=self.afdoc["DocR"].get("DfSz", (100, 100))[0],
            height=self.afdoc["DocR"].get("DfSz", (100, 100))[1],
            unit="px",
        )
        self.document = self.doc.getroot()
        root_chlds = self.afdoc["DocR"].get("Chld", [])
        assert len(root_chlds) <= 1
        if root_chlds:
            self._parse_doc(root_chlds[0])

        if "DCMD" in self.afdoc["DocR"] and "FlNm" in self.afdoc["DocR"]["DCMD"]:
            title = self.afdoc["DocR"]["DCMD"]["FlNm"]
            title = (
                title[: -len(".afdesign")] if title.endswith(".afdesign") else title
            ) + ".svg"
            self.document.add(inkex.Title.new(title))

    def _parse_doc(self, child: AFObject) -> None:
        assert child.get_type() == "Sprd", "Not a document"
        assert not self.document.getchildren()
        self.document.set("width", f"{child['SprB'][2]}")
        self.document.set("height", f"{child['SprB'][3]}")
        self.document.set(
            "viewBox",
            f"{child['SprB'][0]} {child['SprB'][1]} {child['SprB'][2]} {child['SprB'][3]}",
        )

        self._parse_children(child.get("Chld", []))
        self._add_guides(child)

        if self._has_artboards and self._page_label:
            self.document.namedview.get_pages()[0].label = self._page_label

    def _add_guides(
        self, child: AFObject, page_offset: inkex.Vector2d = inkex.Vector2d()
    ) -> None:
        v_guides: list[float] = child.get("GdsV", [])
        h_guides: list[float] = child.get("GdsH", [])

        for pos in v_guides:
            self.document.namedview.add_guide(pos + page_offset.x, orient=False)

        for pos in h_guides:
            self.document.namedview.add_guide(pos + page_offset.y, orient=True)

        # guide color and opacity
        guide_color_af = self.afdoc["DocR"].get("GFil")
        if guide_color_af is None:
            return

        guide_color = parse_fdsc(guide_color_af)
        self.document.namedview.set("guidecolor", self._convert_fill(guide_color))
        self.document.namedview.set(
            "guideopacity",
            (guide_color.alpha if isinstance(guide_color, AFColor) else 1.0),
        )

    def _add_artboard(self, child: AFObject) -> None:
        assert child.get_type() in ["ShpN", "PCrv"], "Invalid artboard type"

        bbox = AFBoundingBox(*child["ShpB" if child.get_type() == "ShpN" else "CvsB"])
        if "Xfrm" in child:
            bbox = get_transformed_bbox(bbox, parse_transform(child["Xfrm"]))

        vx, vy, _, _ = self.document.get_viewbox() or [0, 0, 0, 0]
        self._add_guides(child, inkex.Vector2d(bbox.x - vx, bbox.y - vy))

        if not self._has_artboards:
            self.document.set(
                "viewBox", f"{bbox.x} {bbox.y} {bbox.width} {bbox.height}"
            )
            self.document.set("width", bbox.width)
            self.document.set("height", bbox.height)

            self._page_label = child.get("Desc", "Artboard1")
            self._has_artboards = True
            return

        self.document.namedview.new_page(
            f"{bbox.x - vx}",
            f"{bbox.y - vy}",
            f"{bbox.width}",
            f"{bbox.height}",
            label=child.get(
                "Desc", f"Artboard{len(self.document.namedview._get_pages())}"
            ),
        )

    def _parse_children(
        self,
        children: list[AFObject],
        parent: Optional[inkex.Group] = None,
        parent_af: Optional[AFObject] = None,
    ) -> None:
        if parent is None:
            parent = self.document
        assert parent is not None

        for child in children:
            self._add_child(child, parent, parent_af)

    def _add_path_effect(
        self,
        element: inkex.ShapeElement,
        path_effect: inkex.PathEffect,
    ) -> None:
        self.document.defs.add(path_effect)
        path_effect_str = element.get("inkscape:path-effect", "")
        if path_effect_str:
            element.set(
                "inkscape:path-effect", f"{path_effect_str},{path_effect.get_id(1)}"
            )
        else:
            element.set("inkscape:path-effect", f"{path_effect.get_id(1)}")

    def _add_clip(
        self, child: inkex.ShapeElement, parent: inkex.ShapeElement, href: bool = True
    ) -> None:
        assert not isinstance(
            parent, inkex.elements._groups.GroupBase
        ), f"{parent} of type {type(parent)} is a group"
        assert isinstance(
            parent, inkex.ShapeElement
        ), f"{parent} of type {type(parent)} is not a ShapeElement"

        if href:
            use = inkex.Use()
            use.href = parent
            use.transform = -child.transform
        else:
            use = parent

        clip = inkex.ClipPath()
        self.document.defs.add(clip)
        clip.add(use)

        child_clip = child
        for i in range(MAX_CLIP_PATH_RECURSION):
            if child_clip.clip is None:
                clip.set("id", f"clip-path{i}-{child.get_id()}")
                child_clip.clip = clip
                return
            assert isinstance(child_clip.clip, inkex.ClipPath)
            child_clip = child_clip.clip

        raise ClipPathRecursionError("Too many nested clip paths")

    def _parse_child(self, child: AFObject) -> inkex.ShapeElement:
        # Sprd -> Document
        if child.get_type() == "Sprd":
            raise RuntimeError("Document not at root")

        # TODO: Some shapes (Rectangles, Curves) may be Artboards
        # ShpN -> Shape
        if child.get_type() == "ShpN":
            return self._convert_shape(parse_shape(child["Shpe"], child["ShpB"]))

        # PCrv -> Curve
        elif child.get_type() == "PCrv":
            _bbox = child["CvsB"]
            return inkex.PathElement.new(AFCurve.from_af(child["Crvs"]).get_svg_path())

        # Scop -> Layer
        elif child.get_type() == "Scop":
            return inkex.Layer()  # TODO: Parse layer properties

        # Grup -> Group
        elif child.get_type() == "Grup":
            return inkex.Group()  # TODO: Parse group properties

        # TxtA -> Text
        elif child.get_type() in TEXT_TYPES:
            return self._convert_text(AFText.from_af(child))

        else:
            raise NotImplementedError(
                f'Object type "{child.get_type()}" not implemented'
            )

    def _add_child(
        self, child: AFObject, parent: inkex.Group, parent_af: Optional[AFObject] = None
    ) -> None:
        try:
            if child.get("ABEn", False):
                self._add_artboard(child)

            svg = self._parse_child(child)
        except Exception:
            traceback.print_exc()
            svg = inkex.Layer.new(label=f"-Failed-{child.get_type()}-")

        if isinstance(svg, inkex.Group):
            layer = parent.add(svg)
        else:
            layer = parent.add(inkex.Group())
            layer.add(svg)

        # parent svg object converted from parent_af
        parent_object: Optional[inkex.ShapeElement] = (
            parent
            if parent_af is not None and parent_af.get_type() in ["Scop", "Grup"]
            else (
                parent.getchildren()[0]
                if parent_af is not None and parent.getchildren()
                else None
            )
        )
        try:
            self._add_common_properties(child, svg, parent_object)
            self._add_layer_style(layer, child)
            self._add_style(svg, child)
            self._add_fx(layer, child)
            self._set_blend_mode(layer, child)
        except Exception:
            traceback.print_exc()

        if parent_object is not None and not isinstance(parent_object, inkex.Group):
            self._add_clip(layer, parent_object)

        # Vector Masks
        masks = child.get("AdCh", [])
        for mask in masks:
            try:
                mask_svg = self._parse_child(mask)
                self._add_common_properties(mask, mask_svg)
                self._add_clip(svg, mask_svg, href=False)
            except ClipPathRecursionError:
                print(
                    f"Warning: Max Vector Mask limit '{MAX_CLIP_PATH_RECURSION}' exceeded"
                )
                break
            except Exception:
                traceback.print_exc()

        self._parse_children(child.get("Chld", []), layer, child)

    def _convert_shape(self, child: AFShape) -> inkex.ShapeElement:
        if isinstance(child, AFPointsShapeBase):
            return inkex.Polygon.new(
                points=" ".join([f"{x},{y}" for x, y in child.points])
            )
        if isinstance(child, AFRectangle):
            return self._convert_rectangle(child)
        if isinstance(child, AFEllipse):
            return inkex.Ellipse.new(center=child.centre, radius=child.radii)

    def _convert_rectangle(self, child: AFRectangle) -> inkex.ShapeElement:
        b_box, radii = child.b_box, child.radii

        if any(ct not in corner_map for ct in child.corner_types):
            path_commands = []
            path_commands.append(("M", [b_box.x2, b_box.y + radii[1]]))
            path_commands.append(("L", [b_box.x2, b_box.y2 - radii[2]]))
            path_commands.extend(child._corner_path(AFCornerPos.BR))
            path_commands.append(("L", [b_box.x + radii[3], b_box.y2]))
            path_commands.extend(child._corner_path(AFCornerPos.BL))
            path_commands.append(("L", [b_box.x, b_box.y + radii[0]]))
            path_commands.extend(child._corner_path(AFCornerPos.TL))
            path_commands.append(("L", [b_box.x2 - radii[1], b_box.y]))
            path_commands.extend(child._corner_path(AFCornerPos.TR))
            path_commands.append(("Z", []))
            return inkex.PathElement.new(path_commands)

        rect = inkex.Rectangle.new(b_box.x, b_box.y, b_box.width, b_box.height)
        if all(
            r == radii[0] and ct == AFCornerType.ROUNDED
            for ct, r in zip(radii, child.corner_types)
        ) or all(r == 0 for r in radii):
            rect.set("rx", radii[0])
            return rect

        self._add_path_effect(rect, child._corner_path_effect())
        return rect

    def _convert_text(self, text: AFText) -> inkex.TextElement:
        if text.type == AFTextType.FOLLOW_CURVE:
            text_ele = self._convert_text_on_curve(text, self._convert_tspans(text))
        else:
            text_ele = self._convert_text_in_shape(text, self._convert_tspans(text))

        text_ele.style["white-space"] = "pre"
        text_ele.set("xml:space", "preserve")
        text_ele.style["font-size"] = 0
        text_ele.style["line-height"] = 0
        return text_ele

    def _convert_tspans(self, text: AFText) -> List[inkex.Tspan]:
        para_tspans = []

        for glyph, glyph_atts, para_atts in zip(
            text.glyphs, text.glyph_atts, text.para_atts
        ):
            paras: List[str] = [para + "\n" for para in glyph.split("\u2029")]
            curr_patt_idx = 0
            curr_gatt_idx = 0
            pos_para_offset = 0
            pos_prev_gatt = 0

            for para_str in paras:
                pspan = inkex.Tspan()
                para_tspans.append(pspan)

                max_para_font_size = 0.0
                for glyph_att in glyph_atts.runs[curr_gatt_idx:]:
                    glyph_str = para_str[
                        pos_prev_gatt - pos_para_offset : glyph_att.index
                        - pos_para_offset
                    ]
                    pos_prev_gatt += len(glyph_str)

                    gspan = inkex.Tspan.new(glyph_str.replace("\u0000", ""))
                    pspan.add(gspan)
                    self._add_glyph_style(gspan, glyph_att)

                    max_para_font_size = max(glyph_att.font_size, max_para_font_size)

                    # End of glyph_att
                    if glyph_att.index <= pos_para_offset + len(para_str):
                        curr_gatt_idx += 1

                    # End of current paragraph (reached \u2029)
                    if glyph_att.index >= pos_para_offset + len(para_str):
                        break

                para_att = para_atts.runs[curr_patt_idx]
                self._add_para_style(
                    pspan,
                    para_att,
                    max_para_font_size,
                )

                # Adjust offests
                pos_para_offset += len(para_str)

                # End of current paragraph_att
                if pos_para_offset >= para_att.index:
                    curr_patt_idx += 1

        return para_tspans

    def _convert_text_on_curve(
        self, text: AFText, tspans: List[inkex.Tspan]
    ) -> inkex.TextElement:
        assert text.text_path is not None
        text_ele = inkex.TextElement.new()
        line = text_ele.add(inkex.TextPath.new(*tspans))
        path = inkex.PathElement.new(text.text_path.path.get_svg_path())

        self.document.defs.add(path)
        line.href = path
        line.set("startOffset", f"{text.text_path.starts[0]*100}%")
        line.set("side", "right" if text.text_path.reverses[0] else "left")
        return text_ele

    def _convert_text_in_shape(
        self,
        text: AFText,
        tspans: List[inkex.Tspan],
    ) -> inkex.TextElement:
        def _convert_shape_inside(
            shape: AFShape | AFCurve, offs: Tuple[float, float], text_type: AFTextType
        ) -> inkex.ShapeElement:
            if text_type != AFTextType.ARTISTIC:
                if isinstance(shape, AFCurve):
                    return inkex.PathElement.new(shape.get_svg_path())
                return self._convert_shape(shape)

            assert isinstance(shape, AFRectangle)
            bbox = shape.b_box
            x1, y1, x2, y2 = bbox.x1, bbox.y1, bbox.x2 + offs[0], bbox.y2 + offs[1]
            return self._convert_shape(AFRectangle(AFBoundingBox(x1, y1, x2, y2)))

        text_ele = inkex.TextElement.new()
        line = text_ele.add(inkex.Tspan.new(*tspans))
        line.set("sodipodi:role", "line")

        bottom_offset = 0
        right_offset = 0

        if tspans:
            top_offset_factor = 0.65
            line1_font_size = max(
                [t.style("font-size") for t in list(tspans[0])] or [0]
            )
            line1_height = (
                float(tspans[0].style("line-height")[:-2]) * top_offset_factor
            )
            tspans[0].style["line-height"] = f"{line1_height}pt"

            bottom_offset = max(line1_height, line1_font_size)
            right_offset = line1_font_size

        shape_inside = _convert_shape_inside(
            text.shape_inside, (right_offset, bottom_offset), text.type
        )
        self.document.defs.add(shape_inside)
        text_ele.style["shape-inside"] = shape_inside
        return text_ele

    def _add_glyph_style(self, tspan: inkex.Tspan, glyph_att: AFGlyphAtt) -> None:
        # Fill and stroke
        self._apply_color(tspan, True, glyph_att.fill)
        self._apply_color(tspan, False, glyph_att.stroke_fill)
        self._apply_stroke_style(tspan, glyph_att.stroke)

        # Font
        tspan.style["font-size"] = glyph_att.font_size
        tspan.style["font-family"] = glyph_att.font.family
        tspan.style["font-weight"] = glyph_att.font.weight
        tspan.style["font-style"] = "italic" if glyph_att.font.italic else "normal"
        tspan.style["font-stretch"] = glyph_att.font.stretch.name.lower()

        if glyph_att.lang:
            tspan.style["lang"] = glyph_att.lang

        if glyph_att.underline != AFTextLineStyle.NONE:
            tspan.style["text-decoration-line"] = "underline"
            tspan.style["text-decoration-style"] = (
                "solid" if glyph_att.underline == AFTextLineStyle.SINGLE else "double"
            )
            tspan.style["text-decoration-fill"] = self._convert_fill(
                glyph_att.underline_fill
            )

        if glyph_att.line_through != AFTextLineStyle.NONE:
            tspan.style["text-decoration-line"] = "line-through"
            tspan.style["text-decoration-style"] = (
                "solid"
                if glyph_att.line_through == AFTextLineStyle.SINGLE
                else "double"
            )
            tspan.style["text-decoration-fill"] = self._convert_fill(
                glyph_att.line_through_fill
            )

    def _add_para_style(
        self, tspan: inkex.Tspan, para_att: AFParaAtt, para_font_size: float
    ) -> None:
        tspan.style["line-height"] = (
            f"{para_att.para_leading.get_line_height(para_font_size)}pt"
        )

        # TODO: Doesn't work
        if para_att.align == AFParaAlign.LEFT:
            tspan.style["text-anchor"] = "start"
            tspan.style["text-align"] = "start"
        elif para_att.align == AFParaAlign.CENTER:
            tspan.style["text-anchor"] = "middle"
            tspan.style["text-align"] = "middle"
        elif para_att.align == AFParaAlign.RIGHT:
            tspan.style["text-anchor"] = "end"
            tspan.style["text-align"] = "end"
        elif para_att.align == AFParaAlign.JUSTIFY_LEFT:
            tspan.style["text-align"] = "justify"
            tspan.style["text-anchor"] = "start"
        elif para_att.align == AFParaAlign.JUSTIFY_CENTER:
            tspan.style["text-align"] = "justify"
            tspan.style["text-anchor"] = "middle"
        elif para_att.align == AFParaAlign.JUSTIFY_RIGHT:
            tspan.style["text-align"] = "justify"
            tspan.style["text-anchor"] = "end"
        elif para_att.align == AFParaAlign.JUSTIFY_ALL:
            tspan.style["text-align"] = "justify"
            tspan.style["text-anchor"] = "middle"
        elif para_att.align in [
            AFParaAlign.TOWARDS_SPLINE,
            AFParaAlign.AWAY_FROM_SPLINE,
        ]:
            raise NotImplementedError(f"Alignment {para_att.align} not implemented")
        else:
            raise NotImplementedError(f"Unknown alignment: {para_att.align}")

    def _add_layer_style(self, svg: inkex.ShapeElement, child: AFObject) -> None:
        # Visibility and Opacity
        # Opac -> layer opacity, FOpc -> filter opacity
        if not child.get("Visi", True):
            svg.style["display"] = "none"
        svg.style["opacity"] = child.get("Opac", 1.0) * child.get("FOpc", 1.0)

    def _add_style(self, svg: inkex.ShapeElement, child: AFObject) -> None:
        fill = parse_fill(child)
        self._apply_color(svg, True, fill)

        # Stroke
        stroke_fill = parse_stroke_color(child)
        self._apply_color(svg, False, stroke_fill)

        stroke = parse_stroke(child)
        self._apply_stroke_style(svg, stroke)

        power_stroke = stroke.get_power_stroke(svg)
        if power_stroke is not None:
            if svg.style("fill") is not None:
                # Split fill and stroke
                fillcopy = svg.copy()
                fillcopy.style["stroke"] = None
                fillcopy.pop("stroke-opacity")
                if stroke.order == AFStrokeOrder.FRONT:
                    svg.addprevious(fillcopy)
                else:
                    svg.addnext(fillcopy)
            svg.style["fill"] = svg.style["stroke"]
            svg.style["stroke"] = None
            svg.style["fill-opacity"] = svg.style["stroke-opacity"]
            svg.style.pop("stroke-opacity")
            self._add_path_effect(svg, power_stroke)

    def _set_blend_mode(self, svg: inkex.ShapeElement, child: AFObject) -> None:
        blend_enum = child.get("Blnd")
        if blend_enum is None:
            return
        assert isinstance(blend_enum, EnumT)

        mode = AF_BLEND_MODES[blend_enum.version](blend_enum.id)
        if mode == AFBlendModeV0.NORMAL:
            return

        if mode.name.lower().replace("_", "-") in SVG_BLEND_MODES:
            svg.style["mix-blend-mode"] = mode.name.lower().replace("_", "-")
            return

        raise NotImplementedError(f"Blend mode {mode.name} not supported")

    def _add_filter(self, svg: inkex.ShapeElement, filt: inkex.Filter) -> None:
        filters = svg.style.get("filter", "")
        svg.style["filter"] = " ".join([filters, f"url(#{filt.get_id()})"])

    def _add_fx(self, svg: inkex.ShapeElement, child: AFObject) -> None:
        for fx in child.get("FiEf", []):
            if not fx.get("Enab", False):
                continue

            filt: inkex.Filter = inkex.Filter()
            self.document.defs.add(filt)
            filt.set("color-interpolation-filters", "sRGB")

            if fx.get_type() == "Gaus":
                radius: float = fx["Radi"] / 3.0
                preserve_alpha: bool = fx["PrAl"]

                filt.add(
                    inkex.Filter.GaussianBlur.new(stdDeviation=radius, result="blur")
                )

                if preserve_alpha:
                    cpt = filt.add(
                        inkex.Filter.ColorMatrix.new(
                            values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 100 0",
                            result="blurOpaque",
                        )
                    )
                    cpt.set("in", "blur")

                    composite = filt.add(inkex.Filter.Composite.new(operator="atop"))
                    composite.set("in", "blurOpaque")
                    composite.set("in2", "SourceAlpha")

            else:
                raise NotImplementedError(
                    f"Filter type {fx.get_type()} not implemented"
                )

            self._add_filter(svg, filt)

    def _apply_stroke_style(self, svg: inkex.ShapeElement, stroke: AFStroke):
        if stroke.style == AFStrokeType.NONE:
            svg.style["stroke"] = "none"
            return

        if stroke.style == AFStrokeType.DASHED:
            pattern = list(stroke.dash_pattern)
            while pattern[-1] == 0:
                del pattern[-1]
            svg.style["stroke-dasharray"] = " ".join(
                [str((d if d > 0 else 0.05) * stroke.width) for d in pattern]
            )

        elif stroke.style != AFStrokeType.SOLID:
            raise NotImplementedError(f"Stroke style {stroke.style} not implemented")

        svg.style["stroke-linecap"] = stroke_cap_map[stroke.cap]
        svg.style["paint-order"] = stroke_order_map[stroke.order]
        svg.style["stroke-width"] = stroke.width
        svg.style["stroke-linejoin"] = stroke_join_map[stroke.join]
        if stroke.join == AFStrokeJoin.MITER:
            svg.style["stroke-miterlimit"] = stroke.miter_clip
        svg.set("style", inkex.Style(svg.style))

    def _apply_color(
        self,
        svg: inkex.ShapeElement,
        fill: bool,
        stroke_fill: Union[AFColor, AFGradient],
    ):
        prefix = "fill" if fill else "stroke"
        svg.style[prefix] = self._convert_fill(stroke_fill)
        svg.style[f"{prefix}-opacity"] = (
            stroke_fill.alpha if isinstance(stroke_fill, AFColor) else 1.0
        )

    def _convert_fill(self, fill: AFColor | AFGradient) -> str:
        if isinstance(fill, AFColor):
            return self._convert_color(fill)

        gradient_svg = self._convert_gradient(fill)
        self.document.defs.add(gradient_svg)
        return f"url(#{gradient_svg.get_id()})"

    @staticmethod
    def _convert_gradient(grad: AFGradient) -> inkex.Gradient:
        if grad.grad_type == AFGradientType.LINEAR:
            gradient = inkex.LinearGradient()
            gradient.set("x1", 0)
            gradient.set("y1", 0)
            gradient.set("x2", 1)
            gradient.set("y2", 0)

        elif grad.grad_type in [AFGradientType.RADIAL, AFGradientType.ELLIPTICAL]:
            gradient = inkex.RadialGradient()
            gradient.set("cx", 0)
            gradient.set("cy", 0)
            gradient.set("r", 1)

        else:
            raise NotImplementedError(
                f'Gradient type "{grad.grad_type}" not implemented'
            )

        gradient.set("gradientTransform", grad.tfm)
        gradient.set("gradientUnits", "userSpaceOnUse")

        for stop in AFConverter._convert_stops(grad.stops):
            gradient.add(stop)

        return gradient

    @staticmethod
    def _convert_stops(stops: List[AFGradientStop]) -> List[inkex.Stop]:
        assert len(stops) >= 2, "At least two stops required"
        res = []
        prev_stop = None
        for stop in stops:
            if prev_stop is not None:
                s1, s2 = AFConverter._convert_stop(prev_stop, next_stop=stop)
                res.extend([s1, s2])
            prev_stop = stop
        res.extend(AFConverter._convert_stop(stops[-1]))
        return res

    @staticmethod
    def _convert_stop(
        self, next_stop: AFGradientStop | None = None
    ) -> List[inkex.Stop]:
        def _make_stop(offset: float, color: AFColor) -> inkex.Stop:
            stop = inkex.Stop()
            stop.set("offset", offset)
            stop.style = inkex.Style(
                {
                    "stop-color": AFConverter._convert_color(color),
                    "stop-opacity": color.alpha,
                }
            )
            return stop

        stops = []
        stops.append(_make_stop(self.pos, self.color))
        if next_stop is None:
            return stops

        stops.append(
            _make_stop(
                interpolate_float(self.pos, next_stop.pos, self.mid),
                self.color.interpolate(next_stop.color, 0.5),
            )
        )
        return stops

    @staticmethod
    def _convert_color(color: AFColor) -> str:
        return "#{0:02x}{1:02x}{2:02x}".format(
            *[
                round(c * 255) if isinstance(c, float) else int(c)
                for c in color.to_rgb().color
            ]
        )

    @staticmethod
    def _add_common_properties(
        af: AFObject,
        svg: inkex.ShapeElement,
        parent_svg: Optional[inkex.ShapeElement] = None,
    ) -> None:
        if "Desc" in af and af["Desc"]:
            svg.label = af["Desc"]

        # Xfrm -> Transform
        if "Xfrm" in af:
            tfm = parse_transform(af["Xfrm"])
            if af.get_type() in TEXT_TYPES - {AFTextType.ARTISTIC.value}:
                shape = svg.style("shape-inside")
                if shape is None:
                    shape = svg.getchildren()[0].href

                shape.transform = inkex.Transform((tfm.a, 0, 0, tfm.d, tfm.e, tfm.f))
                tfm @= -shape.transform
            svg.transform @= tfm

        # Child tfm = parent tfm + child tfm
        # For Layer and Group, the transforms are automatically inherited by their children
        if parent_svg is not None and not isinstance(
            parent_svg, inkex.elements._groups.GroupBase
        ):
            svg.transform = parent_svg.transform @ svg.transform
