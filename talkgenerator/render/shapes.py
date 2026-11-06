"""Draw a themed deck as a PowerPoint presentation: shapes on blank 16:9 slides (docs/v5-plan.md, section 9).

Every element of a themed deck has its box on the 1920×1080 canvas (see `talkgenerator.design.engine`), and every
text its style, so this renderer only draws them: a canvas pixel is 6350 EMU, and half a point. PowerPoint breaks
the texts into lines itself, with the same fonts as the engine measured them with; shrink-on-overflow stays on as a
safety net. Classic decks go to `talkgenerator.render.powerpoint`, which fills the 2019 template.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Mapping
from typing import Any, Final

import pptx
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.presentation import Presentation
from pptx.slide import Slide
from pptx.util import Emu, Pt

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import color
from talkgenerator.design.engine import HEIGHT, WIDTH
from talkgenerator.models.deck import (
    Box,
    ChartElement,
    Deck,
    DeckSlide,
    ImageAsset,
    ImageElement,
    ShapeElement,
    TextElement,
    TextStyle,
)
from talkgenerator.models.theme import Theme
from talkgenerator.render import animation, charts
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

ImageStore = Mapping[str, ImageData]
EMU_PER_PIXEL: Final = 6350  # 12192000 EMU (13.333 inches) across 1920 pixels
_BLANK_LAYOUT: Final = 6  # in python-pptx's default template
_ALIGN: Final = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
_ANCHOR: Final = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


def new_presentation() -> Presentation:
    """An empty 16:9 presentation, the size of the classic template (13.333 by 7.5 inches)."""
    presentation = pptx.Presentation()
    presentation.slide_width = Emu(WIDTH * EMU_PER_PIXEL)
    presentation.slide_height = Emu(HEIGHT * EMU_PER_PIXEL)
    return presentation


def render_themed(
    deck: Deck, presentation: Presentation | None = None, *, debug_notes: bool = False, images: ImageStore | None = None
) -> Presentation:
    if deck.style is None:
        raise ValueError("A classic deck goes to the classic renderer (talkgenerator.render.powerpoint)")
    if presentation is None:
        presentation = new_presentation()
    for slide in deck.slides:
        draw_slide(presentation, slide, slide.style or deck.style, debug_notes=debug_notes, images=images)
    return presentation


def draw_slide(
    presentation: Presentation,
    slide: DeckSlide,
    theme: Theme,
    *,
    debug_notes: bool = False,
    images: ImageStore | None = None,
) -> Slide:
    ppt_slide = presentation.slides.add_slide(presentation.slide_layouts[_BLANK_LAYOUT])
    _background(ppt_slide, slide, theme)
    for element in slide.elements:
        try:
            if isinstance(element, ShapeElement):
                _shape(ppt_slide, element)
            elif isinstance(element, ImageElement) and element.box is not None:
                _picture(ppt_slide, element, images)
            elif isinstance(element, ChartElement) and element.box is not None:
                _chart(ppt_slide, element, theme)
            elif isinstance(element, TextElement) and element.box is not None and element.style is not None:
                _text_box(ppt_slide, element.box, element.style, [(element.text, None)])
        except (ValueError, KeyError, AttributeError, OSError) as error:  # one element that won't draw stays out
            logger.error("Could not draw a %s on a %s slide: %s", element.kind, slide.type, error)
    if slide.credits and slide.credits_box is not None and slide.credits_style is not None:
        parts: list[tuple[str, str | None]] = [("Image sources: ", None)]
        for index, credit in enumerate(slide.credits):
            if index:
                parts.append((", ", None))
            parts += [(part.text, part.url) for part in credit]
        _text_box(ppt_slide, slide.credits_box, slide.credits_style, parts, shrink=False)
    if debug_notes and slide.notes:
        notes = ppt_slide.notes_slide.notes_text_frame
        if notes is not None:
            notes.text = slide.notes
    return ppt_slide


# DRAWING


def _emu(value: float) -> Emu:
    return Emu(round(value * EMU_PER_PIXEL))


def _rgb(value: str) -> RGBColor:
    return RGBColor(*color.rgb(value))


def _background(ppt_slide: Slide, slide: DeckSlide, theme: Theme) -> None:
    fill = ppt_slide.background.fill
    background = slide.background
    top = background.color if background is not None else theme.palette.background
    bottom = background.color_2 if background is not None else None
    if bottom is None:
        fill.solid()
        fill.fore_color.rgb = _rgb(top)
        return
    fill.gradient()
    fill.gradient_angle = 90  # from the top down
    stops = fill.gradient_stops
    stops[0].color.rgb = _rgb(top)
    stops[0].position = 0
    stops[-1].color.rgb = _rgb(bottom)
    stops[-1].position = 1.0


def _shape(ppt_slide: Slide, element: ShapeElement) -> None:
    box = element.box
    kind = MSO_SHAPE.OVAL if element.shape == "ellipse" else MSO_SHAPE.RECTANGLE
    shape = ppt_slide.shapes.add_shape(kind, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(element.color)
    if element.opacity < 1:
        color_element = shape.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
        alpha = etree.SubElement(color_element, qn("a:alpha"))
        alpha.set("val", str(round(element.opacity * 100000)))
    shape.line.fill.background()
    shape.shadow.inherit = False
    shape.name = element.role


def _text_box(
    ppt_slide: Slide, box: Box, style: TextStyle, runs: list[tuple[str, str | None]], shrink: bool = True
) -> None:
    shape = ppt_slide.shapes.add_textbox(_emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = _ANCHOR[style.anchor]
    if shrink:  # (the engine picked a size that fits; this is PowerPoint's safety net)
        frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = _ALIGN[style.align]
    for text, url in runs:
        run = paragraph.add_run()
        run.text = text
        font = run.font
        font.name = style.font
        font.size = Pt(style.size / 2)
        font.bold = style.bold
        font.italic = style.italic
        font.color.rgb = _rgb(style.color)
        if style.uppercase:
            run._r.get_or_add_rPr().set("cap", "all")  # shown in capitals, written as it is
        if url:
            run.hyperlink.address = url


def _picture(ppt_slide: Slide, element: ImageElement, images: ImageStore | None) -> None:
    assert element.box is not None
    image = _image_data(element.image, images)
    data = image_util.fetch_image_data(image)
    if data is None:
        logger.warning("Leaving out image %s: it could not be downloaded", http_util.describe_url(element.image.url))
        return
    width, height = image_util.get_image_size(data)
    box = element.box
    if element.fit == "cover":
        picture = ppt_slide.shapes.add_picture(io.BytesIO(data), _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
        box_ratio, image_ratio = box.w / box.h, width / height
        if image_ratio > box_ratio:  # wider than its box: crop the sides
            crop = (1 - box_ratio / image_ratio) / 2
            picture.crop_left = picture.crop_right = crop
        else:
            crop = (1 - image_ratio / box_ratio) / 2
            picture.crop_top = picture.crop_bottom = crop
    else:
        ratio = min(box.w / width, box.h / height)
        shown_width, shown_height = width * ratio, height * ratio
        x, y = box.x + (box.w - shown_width) / 2, box.y + (box.h - shown_height) / 2
        picture = ppt_slide.shapes.add_picture(
            io.BytesIO(data), _emu(x), _emu(y), _emu(shown_width), _emu(shown_height)
        )
    if element.border:
        picture.line.color.rgb = _rgb(element.border)
        picture.line.width = _emu(6)
    image.mark_used()


def _image_data(image: ImageAsset, images: ImageStore | None) -> ImageData:
    known = images.get(image.url) if images is not None else None
    if known is not None:
        return known
    credit = [(part.text, part.url) for part in image.credit]
    return ImageData(image_url=image.url, source=image.source, source_url=image.source_url, credit=credit or None)


def _chart(ppt_slide: Slide, element: ChartElement, theme: Theme) -> None:
    assert element.box is not None
    spec, box, palette = element.chart, element.box, theme.palette
    chart_type, data = charts.pptx_chart_data(spec)
    chart_data: Any = data
    frame: Any = ppt_slide.shapes.add_chart(chart_type, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h), chart_data)
    chart = frame.chart
    charts.CHART_STYLES[spec.chart_type](chart, chart_data)
    charts.set_axis_titles(chart, spec)
    chart.font.name = theme.fonts.body
    chart.font.size = Pt(16)
    chart.font.color.rgb = _rgb(palette.text)
    _theme_colors(chart, spec, theme)
    charts.label_points(chart, spec, _rgb(palette.accent_2))
    if spec.reveal == "series":
        animation.reveal_chart_series(ppt_slide, frame, len(spec.series))


def _theme_colors(chart: Any, spec: Any, theme: Theme) -> None:
    """The chart in the theme's colours: slices and series in its accents, and labels that read on the slide."""
    palette = theme.palette
    series_colors = [palette.accent, palette.accent_2, palette.muted, color.mix(palette.accent, palette.text, 0.5)]
    plot = chart.plots[0]
    if spec.chart_type in ("pie", "doughnut"):
        slice_colors = [palette.accent, palette.accent_2, color.mix(palette.accent, palette.background, 0.45)]
        slice_colors += [color.mix(palette.accent_2, palette.background, 0.45), palette.muted]
        for index, point in enumerate(plot.series[0].points if plot.series else []):
            if index >= len(spec.categories):
                break
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = _rgb(slice_colors[index % len(slice_colors)])
            if plot.has_data_labels:
                label = point.data_label
                label.font.color.rgb = _rgb(palette.text)
                label.font.size = Pt(18)
                if spec.chart_type == "pie":
                    label.position = XL_LABEL_POSITION.OUTSIDE_END  # on the slide's background, where it reads
        if spec.chart_type == "doughnut":  # (a doughnut's labels can't go outside it: a legend names its slices)
            plot.has_data_labels = False
            chart.has_legend = True
            chart.legend.position = XL_LEGEND_POSITION.RIGHT
            chart.legend.include_in_layout = False
            chart.legend.font.size = Pt(18)
        return
    for index, series in enumerate(plot.series):
        hue = _rgb(series_colors[index % len(series_colors)])
        if spec.chart_type == "line":
            series.format.line.color.rgb = hue
        elif spec.chart_type == "scatter":
            series.marker.format.fill.solid()
            series.marker.format.fill.fore_color.rgb = hue
            series.marker.format.line.color.rgb = hue
        else:
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = hue
    if spec.chart_type == "bar" and plot.series and spec.categories:  # the punchline in the theme's second accent
        punchline = plot.series[0].points[len(spec.categories) - 1].format.fill
        punchline.solid()
        punchline.fore_color.rgb = _rgb(palette.accent_2)
