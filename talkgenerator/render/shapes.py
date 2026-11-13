"""Draw a themed deck as a PowerPoint presentation: shapes on blank 16:9 slides (docs/v5-plan.md, section 9).

Every element of a themed deck has its box on the 1920×1080 canvas (see `talkgenerator.design.engine`), and every
text its style, so this renderer only draws them: a canvas pixel is 6350 EMU, and half a point. PowerPoint breaks
the texts into lines itself, with the same fonts as the engine measured them with; shrink-on-overflow stays on as a
safety net. The open fonts that texts are in travel inside the file (`talkgenerator.render.embedding`). Slides
animate as classic ones do (`talkgenerator.render.animation`): two or three columns appear click by click, the one
before dimming, a chart's second line draws itself in and a diagram's punchline fades in on a click, and videos play
by themselves. Classic decks go to `talkgenerator.render.powerpoint`, which fills the 2019 template.
"""

from __future__ import annotations

import io
import logging
import math
from functools import cache
from typing import Any, Final

import pptx
from lxml import etree
from PIL import Image as PILImage
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.presentation import Presentation
from pptx.slide import Slide
from pptx.util import Emu, Pt

from talkgenerator.design import color, engine, treatments
from talkgenerator.design.engine import HEIGHT, WIDTH
from talkgenerator.models.deck import (
    Box,
    ChartElement,
    Deck,
    DeckSlide,
    DiagramElement,
    Entrance,
    ImageElement,
    ImageTreatment,
    ShapeElement,
    SlideBackground,
    TextElement,
    TextStyle,
)
from talkgenerator.models.theme import TextEffect, Theme
from talkgenerator.render import animation, backgrounds, charts, diagrams, embedding, reveal
from talkgenerator.render.powerpoint import ImageStore, image_data
from talkgenerator.slide import powerpoint_slide_creator as creator
from talkgenerator.util import emoji_util, http_util, image_util

logger = logging.getLogger("talkgenerator")

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
    embedding.embed_fonts(presentation)  # (the open fonts its texts are in, so PowerPoint shows them)
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
    draw_elements(ppt_slide, slide, theme, images=images)
    if slide.credits and slide.credits_box is not None and slide.credits_style is not None:
        parts: list[tuple[str, str | None]] = [(engine.credits_prefix(slide), None)]
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


def draw_elements(ppt_slide: Slide, slide: DeckSlide, theme: Theme, *, images: ImageStore | None = None) -> None:
    """Draw the slide's elements on the PowerPoint slide, each in its box, and animate them: the columns of a column
    slide click by click, and the elements that appear on a click on theirs; what belongs to an element (a frame
    around a picture: part_of) with it. (A classic deck draws the slide types that the 2019 template has no layouts
    for with this too, on the template's blank slide.)"""
    drawn: dict[str, list[Any]] = {}  # the shapes each element is drawn with (and what belongs to it), by its role
    clicks: dict[int, list[Any]] = {}  # the shapes that appear on each click
    entrances: dict[int, Entrance] = {}  # how shapes come in, by their ids, where they have an entrance effect (D82)
    entering: list[tuple[Any, Entrance]] = []  # the shapes that come in so as the slide comes up
    for element in slide.elements:
        before = {shape.shape_id for shape in ppt_slide.shapes}
        try:
            if isinstance(element, ShapeElement):
                _shape(ppt_slide, element)
            elif isinstance(element, ImageElement) and element.box is not None:
                _picture(ppt_slide, element, images)
            elif isinstance(element, ChartElement) and element.box is not None:
                _chart(ppt_slide, element, theme, slide)
            elif isinstance(element, DiagramElement) and element.box is not None:
                diagrams.draw_diagram(ppt_slide, diagrams.Box.on_canvas(element.box), element.diagram, element.style)
            elif isinstance(element, TextElement) and element.box is not None and element.style is not None:
                _text_box(ppt_slide, element.box, element.style, [(element.text, None)], name=element.role)
        except (ValueError, KeyError, AttributeError, OSError) as error:  # one element that won't draw stays out
            logger.error("Could not draw a %s on a %s slide: %s", element.kind, slide.type, error)
        shapes = [shape for shape in ppt_slide.shapes if shape.shape_id not in before]
        drawn.setdefault(getattr(element, "part_of", None) or element.role, []).extend(shapes)
        click = reveal.click_of(slide, element)
        if click:
            clicks.setdefault(click, []).extend(shapes)
        entrance = getattr(element, "entrance", None)
        if entrance is not None:
            entrances.update(dict.fromkeys((shape.shape_id for shape in shapes), entrance))
            column = reveal.column_of(slide, element)
            if not click and (column is None or not reveal.column_click(slide, column)):
                entering += [(shape, entrance) for shape in shapes]
    columns = reveal.COLUMNS.get(slide.type, 0)  # (click by click, as in the 2019 template: animation.reveal_columns)
    if columns:  # (each its picture or text, with what the picture's treatment lays on it, and its caption)
        animation.reveal_columns(
            ppt_slide,
            [drawn.get(f"content_{index}", []) + drawn.get(f"caption_{index}", []) for index in range(1, columns + 1)],
            entrances,
        )
    if clicks:
        # (a chart's or a diagram's own clicks come first, as its own steps: what appears on one of those, such as a
        # build dot, goes with it; the rest each on a click of its own, after them: D80)
        own = max((_own_clicks(element) for element in slide.elements), default=0)
        later = []
        for number in sorted(clicks):
            if number > own or not animation.join_click(ppt_slide, number, clicks[number], entrances):
                later.append(clicks[number])
        if later:
            animation.reveal_clicks(ppt_slide, later, entrances)
    animation.enter(ppt_slide, entering)  # (what comes in as the slide comes up, before its first click: D82)


def _own_clicks(element: Any) -> int:
    """The clicks a chart or a diagram plays as its own steps (its series or categories, its punchline)."""
    if isinstance(element, ChartElement):
        return element.chart.clicks()
    if isinstance(element, DiagramElement):
        return 1 if element.diagram.reveal == "punchline" else 0
    return 0


# DRAWING


def _emu(value: float) -> Emu:
    return Emu(round(value * EMU_PER_PIXEL))


def _rgb(value: str) -> RGBColor:
    return RGBColor(*color.rgb(value))


def _background(ppt_slide: Slide, slide: DeckSlide, theme: Theme) -> None:
    fill = ppt_slide.background.fill
    background = slide.background
    if background is not None and background.pattern is not None:  # (a picture of it, the same on every slide)
        _picture_background(ppt_slide, background)
        return
    top = background.color if background is not None else theme.palette.background
    bottom = background.color_2 if background is not None else None
    if bottom is None:
        fill.solid()
        fill.fore_color.rgb = _rgb(top)
        return
    fill.gradient()
    fill.gradient_angle = 270  # from the top down (python-pptx counts counter-clockwise: this is DrawingML's 90)
    stops = fill.gradient_stops
    stops[0].color.rgb = _rgb(top)
    stops[0].position = 0
    stops[-1].color.rgb = _rgb(bottom)
    stops[-1].position = 1.0


def _picture_background(ppt_slide: Slide, background: SlideBackground) -> None:
    """The slide's background as a picture of its colours and pattern, stretched over the slide (a .pptx keeps one
    copy of a picture that slides share)."""
    _, relationship = ppt_slide.part.get_or_add_image_part(io.BytesIO(backgrounds.picture(background)))
    properties = ppt_slide._element.cSld.get_or_add_bgPr()
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill", "a:pattFill", "a:grpFill"):
        for old in properties.findall(qn(tag)):
            properties.remove(old)
    properties.insert(
        0,
        parse_xml(
            f'<a:blipFill {nsdecls("a", "r")} dpi="0" rotWithShape="1"><a:blip r:embed="{relationship}"/>'
            "<a:srcRect/><a:stretch><a:fillRect/></a:stretch></a:blipFill>"
        ),
    )


def _shape(ppt_slide: Slide, element: ShapeElement) -> None:
    """A shape: a rectangle (rounded, if it has corners), an ellipse or a polygon (as a freeform of its corners, in
    its box), filled or not, with its outline inside its box (PowerPoint draws a line along the middle of a shape's
    edge, so the shape is drawn half a line's width smaller), turned and as see-through as it is."""
    box = element.box
    line = element.outline if element.outline and element.outline_width > 0 else None
    inset = element.outline_width / 2 if line else 0.0
    x, y, w, h = box.x + inset, box.y + inset, max(1.0, box.w - 2 * inset), max(1.0, box.h - 2 * inset)
    kind = MSO_SHAPE.RECTANGLE
    if element.shape == "ellipse":
        kind = MSO_SHAPE.OVAL
    elif element.shape == "rectangle" and element.corner > 0:
        kind = MSO_SHAPE.ROUNDED_RECTANGLE
    shape = ppt_slide.shapes.add_shape(kind, _emu(x), _emu(y), _emu(w), _emu(h))
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:  # (its corners' radius, as a share of its shorter side)
        shape.adjustments[0] = min(0.5, max(0.0, element.corner - inset) / min(w, h))
    elif element.shape == "polygon" and element.points:
        _freeform(shape, element.points, w, h)
    if element.filled:
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(element.color)
        if element.opacity < 1:
            _alpha(shape.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr")), element.opacity)
    else:
        shape.fill.background()
    if line:
        shape.line.color.rgb = _rgb(line)
        shape.line.width = _emu(element.outline_width)
        if element.opacity < 1:
            _alpha(shape.line._ln.find(qn("a:solidFill")).find(qn("a:srgbClr")), element.opacity)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    if element.rotation:
        shape.rotation = element.rotation
    shape.name = element.role


def _alpha(color_element: Any, opacity: float) -> None:
    alpha = etree.SubElement(color_element, qn("a:alpha"))
    alpha.set("val", str(round(opacity * 100000)))


def _freeform(shape: Any, points: tuple[tuple[float, float], ...], width: float, height: float) -> None:
    """Give the shape the polygon's geometry: its corners, as shares of the shape's box, in a path as large as it."""
    path_w, path_h = round(width * EMU_PER_PIXEL), round(height * EMU_PER_PIXEL)

    def point(x: float, y: float) -> str:
        return f'<a:pt x="{round(x * path_w)}" y="{round(y * path_h)}"/>'

    (first_x, first_y), *rest = points
    lines = "".join(f"<a:lnTo>{point(x, y)}</a:lnTo>" for x, y in rest)
    geometry = parse_xml(
        f'<a:custGeom {nsdecls("a")}><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/>'
        f'<a:pathLst><a:path w="{path_w}" h="{path_h}"><a:moveTo>{point(first_x, first_y)}</a:moveTo>{lines}'
        "<a:close/></a:path></a:pathLst></a:custGeom>"
    )
    preset = shape._element.spPr.find(qn("a:prstGeom"))
    preset.addprevious(geometry)
    shape._element.spPr.remove(preset)


def _text_box(
    ppt_slide: Slide,
    box: Box,
    style: TextStyle,
    runs: list[tuple[str, str | None]],
    shrink: bool = True,
    name: str | None = None,
) -> None:
    shape = ppt_slide.shapes.add_textbox(_emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
    if name:  # (its role, as the selection pane shows it, as a shape's is)
        shape.name = name
    frame = shape.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = _ANCHOR[style.anchor]
    if shrink:  # (the engine picked a size that fits; this is PowerPoint's safety net)
        frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    paragraph = frame.paragraphs[0]
    paragraph.alignment = _ALIGN[style.align]
    for whole, url in runs:
        # (emoji in runs of their own, in an emoji font: no theme font has them, and an emoji font draws them in colour;
        # and a line of its own where the text breaks it, as a line break in the paragraph: a presenter's job under
        # their name, D80)
        pieces: list[tuple[str, bool] | None] = []
        for number, line in enumerate(whole.split("\n")):
            pieces += [None] * (number > 0) + list(emoji_util.runs(line))
        for piece in pieces:
            if piece is None:
                paragraph.add_line_break()
                continue
            text, emoji = piece
            run = paragraph.add_run()
            run.text = text
            font = run.font
            font.name = emoji_util.EMOJI_FONT if emoji else style.font
            font.size = Pt(style.size / 2)
            font.bold = style.bold
            font.italic = style.italic
            font.color.rgb = _rgb(style.color)
            if emoji:  # (for every script PowerPoint might take them for)
                properties = run._r.get_or_add_rPr()
                for slot in ("a:ea", "a:cs", "a:sym"):
                    etree.SubElement(properties, qn(slot)).set("typeface", emoji_util.EMOJI_FONT)
            if style.uppercase:
                run._r.get_or_add_rPr().set("cap", "all")  # shown in capitals, written as it is
            if style.effect is not None and not emoji:
                _text_effect(run, style.effect)
            if url:  # (in the text's colour, as the rest of a credit line)
                creator.link(run, url)
    if style.effect is not None and style.effect.warp:
        frame._bodyPr.insert(
            0, parse_xml(f'<a:prstTxWarp {nsdecls("a")} prst="{_WARPS[style.effect.warp]}"><a:avLst/></a:prstTxWarp>')
        )


# WordArt's shapes, as PowerPoint names them
_WARPS: Final = {"wave": "textWave1", "arch": "textArchUp", "inflate": "textInflate", "slant": "textSlantUp"}


def _text_effect(run: Any, effect: TextEffect) -> None:
    """A heading's WordArt-style effects on a run of it: its outline, its gradient (instead of its colour), and its
    glow and shadow, in the order a run's properties have them (before its font)."""
    properties = run._r.get_or_add_rPr()
    if effect.outline and effect.outline_width > 0:
        outline = effect.outline.lstrip("#")
        properties.insert(
            0,
            parse_xml(
                f'<a:ln {nsdecls("a")} w="{_emu(effect.outline_width)}"><a:solidFill>'
                f'<a:srgbClr val="{outline}"/></a:solidFill></a:ln>'
            ),
        )
    solid = properties.find(qn("a:solidFill"))
    if effect.fill and solid is not None:
        last = max(1, len(effect.fill) - 1)
        stops = "".join(
            f'<a:gs pos="{round(100000 * index / last)}"><a:srgbClr val="{stop.lstrip("#")}"/></a:gs>'
            for index, stop in enumerate(effect.fill)
        )
        gradient = parse_xml(
            f'<a:gradFill {nsdecls("a")} rotWithShape="1"><a:gsLst>{stops}</a:gsLst>'
            '<a:lin ang="5400000" scaled="0"/></a:gradFill>'  # (from the top down)
        )
        solid.addprevious(gradient)
        properties.remove(solid)
        solid = gradient
    effects = ""
    if effect.glow and effect.glow_radius > 0:
        glow = effect.glow.lstrip("#")
        effects += f'<a:glow rad="{_emu(effect.glow_radius)}"><a:srgbClr val="{glow}"><a:alpha val="60000"/></a:srgbClr></a:glow>'
    if effect.shadow:
        right, down = effect.shadow_offset
        direction = round(math.degrees(math.atan2(down, right)) % 360 * 60000)
        alpha = round(effect.shadow_opacity * 100000)
        effects += (
            f'<a:outerShdw blurRad="{_emu(effect.shadow_blur)}" dist="{_emu(math.hypot(right, down))}" '
            f'dir="{direction}" algn="tl" rotWithShape="0"><a:srgbClr val="{effect.shadow.lstrip("#")}">'
            f'<a:alpha val="{alpha}"/></a:srgbClr></a:outerShdw>'
        )
    if effects and solid is not None:
        solid.addnext(parse_xml(f"<a:effectLst {nsdecls('a')}>{effects}</a:effectLst>"))


def draw_picture(ppt_slide: Slide, element: ImageElement, images: ImageStore | None = None) -> None:
    """A picture in its box, as a themed deck draws it (a classic slide's that the template has no place for: a
    diagram's box's, a picture by a trend's named point)."""
    _picture(ppt_slide, element, images)


def draw_shape(ppt_slide: Slide, element: ShapeElement) -> None:
    """A shape in its box, as a themed deck draws it (a classic slide's: the line to a picture by a trend's point)."""
    _shape(ppt_slide, element)


def _picture(ppt_slide: Slide, element: ImageElement, images: ImageStore | None) -> None:
    assert element.box is not None
    image = image_data(element.image, images)
    data = image_util.fetch_image_data(image)
    if data is None:
        logger.warning("Leaving out image %s: it could not be downloaded", http_util.describe_url(element.image.url))
        return
    width, height = image_util.get_image_size(data)
    look = element.treatment or ImageTreatment()
    box, frame = element.box, None
    if look.frame == "polaroid":  # a white frame around the picture, both tilted a little
        frame, box = treatments.polaroid(element.box, width, height, cover=element.fit == "cover")
        _polaroid_frame(ppt_slide, frame, look.tilt)
    picture = _placed(ppt_slide, data, box, width, height, element.fit)
    if image.video_data is not None:  # a gif too large to embed: its video plays, with this picture as its poster
        picture = creator.play_video(ppt_slide, picture, image.video_data, data, element.fit != "cover")
    if frame is not None and look.tilt:
        _turn(picture, frame, look.tilt)
    _treat(ppt_slide, picture, look, data)
    if element.border and look.frame != "polaroid":
        picture.line.color.rgb = _rgb(element.border)
        picture.line.width = _emu(6)
    image.mark_used()


def _placed(ppt_slide: Slide, data: bytes, box: Box, width: int, height: int, fit: str) -> Any:
    """The picture in the box: filling it, cropped (cover), or whole, in its middle (contain)."""
    if fit == "cover":
        picture = ppt_slide.shapes.add_picture(io.BytesIO(data), _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h))
        box_ratio, image_ratio = box.w / box.h, width / height
        if image_ratio > box_ratio:  # wider than its box: crop the sides
            crop = (1 - box_ratio / image_ratio) / 2
            picture.crop_left = picture.crop_right = crop
        else:
            crop = (1 - image_ratio / box_ratio) / 2
            picture.crop_top = picture.crop_bottom = crop
        return picture
    ratio = min(box.w / width, box.h / height)
    shown_width, shown_height = width * ratio, height * ratio
    x, y = box.x + (box.w - shown_width) / 2, box.y + (box.h - shown_height) / 2
    return ppt_slide.shapes.add_picture(io.BytesIO(data), _emu(x), _emu(y), _emu(shown_width), _emu(shown_height))


# A polaroid's shadow, soft and below it
_SHADOW: Final = (
    f'<a:effectLst {nsdecls("a")}><a:outerShdw blurRad="76200" dist="19050" dir="5400000" algn="t" '
    'rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="30000"/></a:srgbClr></a:outerShdw></a:effectLst>'
)


def _polaroid_frame(ppt_slide: Slide, frame: Box, degrees: float) -> None:
    shape = ppt_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _emu(frame.x), _emu(frame.y), _emu(frame.w), _emu(frame.h))
    shape.name = "Polaroid frame"
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(treatments.POLAROID_WHITE)
    shape.line.fill.background()
    shape._element.spPr.append(parse_xml(_SHADOW))
    shape.rotation = degrees


def _turn(shape: Any, frame: Box, degrees: float) -> None:
    """Turn the shape the degrees (clockwise) around the middle of the frame, as if it were stuck on it."""
    at = Box(
        x=shape.left / EMU_PER_PIXEL,
        y=shape.top / EMU_PER_PIXEL,
        w=shape.width / EMU_PER_PIXEL,
        h=shape.height / EMU_PER_PIXEL,
    )
    moved = treatments.turned(at, (frame.x + frame.w / 2, frame.y + frame.h / 2), degrees)
    shape.left, shape.top = _emu(moved.x), _emu(moved.y)
    shape.rotation = degrees


def _treat(ppt_slide: Slide, picture: Any, look: ImageTreatment, data: bytes) -> None:
    """The treatment's filter, as a picture effect that PowerPoint applies (the picture itself stays as it is), its
    rounded corners, and its vignette and grain, laid over the picture."""
    effect = _effect(look, data)
    if effect is not None:
        blip = picture._element.blipFill.blip
        extensions = blip.find(qn("a:extLst"))
        if extensions is not None:
            extensions.addprevious(effect)
        else:
            blip.append(effect)
    if look.frame == "rounded":
        _round(picture)
    if look.tint and look.tint_opacity > 0:  # a colour laid over it, see-through
        tint = ppt_slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, picture.left, picture.top, picture.width, picture.height)
        tint.name = "Tint"
        tint.fill.solid()
        tint.fill.fore_color.rgb = _rgb(look.tint)
        _alpha(tint.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr")), look.tint_opacity)
        tint.line.fill.background()
        tint.shadow.inherit = False
        _like(tint, picture, look)
    if look.vignette:
        vignette = ppt_slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, picture.left, picture.top, picture.width, picture.height
        )
        vignette.name = "Vignette"
        _vignette(vignette, look.vignette)
        _like(vignette, picture, look)
    if look.grain:
        grain = ppt_slide.shapes.add_picture(
            io.BytesIO(_grain(look.grain)), picture.left, picture.top, picture.width, picture.height
        )
        grain.name = "Grain"
        _like(grain, picture, look)


def _effect(look: ImageTreatment, data: bytes) -> Any:
    """The picture effect (DrawingML) of the treatment's filter, if it has one."""
    if look.filter == "grayscale":
        return parse_xml(f"<a:grayscl {nsdecls('a')}/>")
    if look.filter == "black and white":  # split at the picture's own median lightness
        with PILImage.open(io.BytesIO(data)) as opened:
            cut = treatments.threshold(opened.convert("RGB"))
        return parse_xml(f'<a:biLevel {nsdecls("a")} thresh="{round(cut * 100000)}"/>')
    if look.filter in ("sepia", "duotone") and look.dark and look.light:
        dark, light = look.dark.lstrip("#"), look.light.lstrip("#")
        return parse_xml(f'<a:duotone {nsdecls("a")}><a:srgbClr val="{dark}"/><a:srgbClr val="{light}"/></a:duotone>')
    return None


def _round(shape: Any) -> None:
    """Give the shape (a picture, say) rounded corners."""
    geometry = shape._element.spPr.find(qn("a:prstGeom"))
    if geometry is None:
        return
    geometry.set("prst", "roundRect")
    for child in list(geometry):
        geometry.remove(child)
    radius = round(treatments.ROUNDED * 100000)  # (of the shorter side)
    geometry.append(parse_xml(f'<a:avLst {nsdecls("a")}><a:gd name="adj" fmla="val {radius}"/></a:avLst>'))


def _vignette(shape: Any, strength: float) -> None:
    """Fill the shape with a vignette: clear in the middle, darker towards the edges (a gradient along a circle)."""
    shape.line.fill.background()
    shape.shadow.inherit = False
    properties = shape._element.spPr
    for tag in ("a:solidFill", "a:noFill", "a:gradFill"):
        for old in properties.findall(qn(tag)):
            properties.remove(old)
    start = round(treatments.VIGNETTE_START * 100000)
    darkest = round(treatments.VIGNETTE_DARKEST * strength * 100000)
    stop = '<a:gs pos="{pos}"><a:srgbClr val="000000"><a:alpha val="{alpha}"/></a:srgbClr></a:gs>'
    fill = parse_xml(
        f'<a:gradFill {nsdecls("a")} rotWithShape="1"><a:gsLst>'
        + stop.format(pos=0, alpha=0)
        + stop.format(pos=start, alpha=0)
        + stop.format(pos=100000, alpha=darkest)
        + '</a:gsLst><a:path path="circle"><a:fillToRect l="50000" t="50000" r="50000" b="50000"/></a:path>'
        "</a:gradFill>"
    )
    properties.find(qn("a:prstGeom")).addnext(fill)


def _like(overlay: Any, picture: Any, look: ImageTreatment) -> None:
    """Turn and shape an overlay like the picture it lies on."""
    overlay.rotation = picture.rotation
    if look.frame == "rounded":
        _round(overlay)


@cache
def _grain(opacity: float) -> bytes:
    output = io.BytesIO()
    treatments.grain(opacity).save(output, "PNG")
    return output.getvalue()


def _chart(ppt_slide: Slide, element: ChartElement, theme: Theme, slide: DeckSlide) -> None:
    assert element.box is not None
    spec, box, palette = element.chart, element.box, theme.palette
    chart_type, data = charts.pptx_chart_data(spec)
    chart_data: Any = data
    frame: Any = ppt_slide.shapes.add_chart(chart_type, _emu(box.x), _emu(box.y), _emu(box.w), _emu(box.h), chart_data)
    chart = frame.chart
    charts.CHART_STYLES[spec.chart_type](chart, chart_data)
    charts.set_axis_titles(chart, spec)
    _theme_colors(chart, spec, theme)
    look = charts.ChartLook(
        text=_rgb(palette.text),
        line=_rgb(palette.muted),
        background=_rgb(_colour_behind(box, slide, theme)),
        font=theme.fonts.body,
        punchline=_rgb(palette.accent_2),
    )
    charts.label_points(chart, spec, look, frame.width)
    charts.add_trendlines(chart, spec, _rgb(palette.text))
    charts.name_bars(chart, spec, look)
    if isinstance(slide.element(engine.POINT_PICTURE), ImageElement):  # (where the layout reckons its point is)
        charts.pin_plot(chart, spec, box.w, box.h)
    charts.finish(chart, look)
    animation.reveal_chart(ppt_slide, frame, spec)


def _colour_behind(box: Box, slide: DeckSlide, theme: Theme) -> str:
    """The slide's background in the middle of the box: on a gradient, the colour that far down it."""
    background = slide.background
    top = background.color if background is not None else theme.palette.background
    bottom = background.color_2 if background is not None else None
    if bottom is None:
        return top
    return color.mix(top, bottom, min(1.0, max(0.0, (box.y + box.h / 2) / HEIGHT)))


def _theme_colors(chart: Any, spec: Any, theme: Theme) -> None:
    """The chart in the theme's colours: slices and series in its accents, and labels that read where they are (the
    others get the theme's text colour from charts.finish)."""
    palette = theme.palette
    series_colors = [palette.accent, palette.accent_2, palette.muted, color.mix(palette.accent, palette.text, 0.5)]
    plot = chart.plots[0]
    if spec.chart_type in ("pie", "doughnut"):
        slice_colors = [palette.accent, palette.accent_2, color.mix(palette.accent, palette.background, 0.45)]
        slice_colors += [color.mix(palette.accent_2, palette.background, 0.45), palette.muted]
        for index, point in enumerate(plot.series[0].points if plot.series else []):
            if index >= len(spec.categories):
                break
            fill = slice_colors[index % len(slice_colors)]
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = _rgb(fill)
            if not plot.has_data_labels:
                continue
            if spec.chart_type == "pie":
                point.data_label.position = XL_LABEL_POSITION.OUTSIDE_END  # on the slide's background, where it reads
            else:  # a doughnut's share is on its slice: in whichever of the theme's text and background reads on it
                on_slice = max((palette.text, palette.background), key=lambda option: color.contrast(option, fill))
                for paragraph in point.data_label.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.color.rgb = _rgb(on_slice)
        return
    for index, series in enumerate(plot.series):
        own = spec.series[index].color if index < len(spec.series) else None  # (a cluster's or a line's: the engine's)
        hue = _rgb(own or series_colors[index % len(series_colors)])
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
