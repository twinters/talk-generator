"""The layout engine: a deck's elements in their layout's boxes, in a theme's style (docs/v5-plan.md, section 9).

Every slide type has layouts, which are geometry only: boxes on the 1920×1080 canvas for the roles of its elements
(the title, the image, the captions...). The engine picks a layout for every slide (with the deck's seed), puts the
elements in its boxes, gives every text its theme's font and colour at the largest size at which it fits, and adds
the theme's background and decoration. With style_chaos, slides get themes of their own: none (0) to all (1).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal

from talkgenerator.design import color, fit, themes
from talkgenerator.models.deck import (
    Box,
    ChartElement,
    Content,
    Deck,
    DeckSlide,
    ImageElement,
    ShapeElement,
    SlideBackground,
    TextAnchor,
    TextElement,
    TextStyle,
)
from talkgenerator.models.theme import Theme
from talkgenerator.util import random_util

WIDTH: Final = 1920
HEIGHT: Final = 1080
MARGIN: Final = 96
CREDITS_BOX: Final = Box(x=MARGIN, y=996, w=WIDTH - 2 * MARGIN, h=36)
CREDITS_SIZE: Final = 18
FULL: Final = Box(x=0, y=0, w=WIDTH, h=HEIGHT)
# Over a photo, texts are light on a dark shade
SHADE: Final = "#000000"
SHADE_OPACITY: Final = 0.55
BAND_OPACITY: Final = 0.85  # of the bands behind texts on a full-screen picture
LIGHT_TEXT: Final = "#ffffff"


@dataclass(frozen=True)
class TextSpec:
    """How a role's text looks: its font (the theme's heading or body font) and sizes, colour and place."""

    font: Literal["heading", "body"]
    largest: float
    smallest: float
    color: Literal["text", "muted", "light"] = "text"
    align: Literal["title", "left", "center"] = "title"  # title: as the theme aligns its titles
    anchor: TextAnchor = "middle"
    heading: bool = False  # bold and in capitals as the theme's headings are
    italic: bool = False


SPECS: Final[dict[str, TextSpec]] = {
    "talk title": TextSpec("heading", 140, 64, anchor="bottom", heading=True),
    "subtitle": TextSpec("body", 52, 30, color="muted", anchor="top"),
    "title": TextSpec("heading", 88, 44, heading=True),
    "side title": TextSpec("heading", 96, 48, align="left", heading=True),
    "band title": TextSpec("heading", 80, 40, align="center", heading=True),
    "statement": TextSpec("heading", 120, 52, color="light", align="center", heading=True),
    "statement title": TextSpec("heading", 56, 32, color="light", align="center", heading=True),
    "caption": TextSpec("body", 52, 28, align="center", anchor="top"),
    "small caption": TextSpec("body", 44, 26, align="center", anchor="top"),
    "quote": TextSpec("body", 64, 30, align="left", italic=True),
}


@dataclass
class _Placement:
    layout: str
    boxes: dict[str, tuple[Box, str]] = field(default_factory=dict)  # role: (box, text spec)
    shapes: list[ShapeElement] = field(default_factory=list)  # drawn behind the content
    photo: bool = False  # a photo fills the slide: credits go on a band


def lay_out(deck: Deck, theme: Theme, style_chaos: float = 0.0, extremes: bool = True) -> Deck:
    """The deck with its elements placed and styled in the theme; with style_chaos, some slides (that share of
    them, picked by the seed) in themes of their own."""
    rng = random_util.Rng(deck.seed if deck.seed is not None else 0).child("layout")
    laid_out = []
    for number, slide in enumerate(deck.slides):
        slide_rng = rng.child("slide", number)
        own = None
        if style_chaos > 0:
            with random_util.use(slide_rng.child("chaos")):
                chaotic = random_util.random() < style_chaos
            if chaotic:
                own = themes.pick(themes.RANDOM, slide_rng.child("theme"), extremes)
        laid_out.append(lay_out_slide(slide, own or theme, slide_rng, own_style=own is not None))
    return deck.model_copy(update={"theme": theme.name, "style": theme, "slides": tuple(laid_out)})


def lay_out_slide(slide: DeckSlide, theme: Theme, rng: random_util.Rng, own_style: bool = False) -> DeckSlide:
    builder = _LAYOUTS.get(slide.type)
    if builder is None:
        raise ValueError(f"There's no layout for {slide.type!r} slides")
    roles = {element.role: element for element in slide.elements}
    with random_util.use(rng):
        placement = builder(roles, theme)
    palette = theme.palette
    elements: list[Content] = []
    background = roles.get("background")
    if isinstance(background, ImageElement):  # a photo behind everything
        elements.append(background.model_copy(update={"box": FULL, "fit": "cover"}))
    elements += placement.shapes
    for element in slide.elements:
        if element is background or element.role not in placement.boxes:
            continue
        box, spec = placement.boxes[element.role]
        if isinstance(element, TextElement):
            elements.append(
                element.model_copy(update={"box": box, "style": _style(element.text, box, SPECS[spec], theme)})
            )
        elif isinstance(element, ImageElement):
            border = palette.text if theme.image_border and box != FULL else None
            elements.append(element.model_copy(update={"box": box, "border": border}))
        elif isinstance(element, ChartElement):
            elements.append(element.model_copy(update={"box": box}))
    # The credits read on what's behind them: the background, or a photo (which could be anything) under a shade
    behind = [
        palette.background,
        *([theme.gradient_to] if theme.background == "gradient" and theme.gradient_to else []),
    ]
    if isinstance(background, ImageElement):
        behind = [color.mix(extreme, SHADE, SHADE_OPACITY) for extreme in ("#000000", "#ffffff")]
    elif placement.photo and slide.credits:  # on a band over the picture, solid if no colour reads on it otherwise
        opacity = BAND_OPACITY
        behind = [color.mix(extreme, palette.surface, opacity) for extreme in ("#000000", "#ffffff")]
        if color.worst_contrast(color.readable_on(palette.muted, behind), behind) < color.BODY_CONTRAST:
            opacity, behind = 1.0, [palette.surface]
        band = Box(x=0, y=CREDITS_BOX.y - 8, w=WIDTH, h=CREDITS_BOX.h + 16)
        elements.append(ShapeElement(role="credits band", box=band, color=palette.surface, opacity=opacity))
    credits_color = color.readable_on(palette.muted, behind, color.BODY_CONTRAST)
    return slide.model_copy(
        update={
            "layout": placement.layout,
            "elements": tuple(elements),
            "background": SlideBackground(
                color=palette.background, color_2=theme.gradient_to if theme.background == "gradient" else None
            ),
            "style": theme if own_style else None,
            "credits_box": CREDITS_BOX,
            "credits_style": TextStyle(font=theme.fonts.body, size=CREDITS_SIZE, color=credits_color, anchor="middle"),
        }
    )


def _style(text: str, box: Box, spec: TextSpec, theme: Theme) -> TextStyle:
    font = theme.fonts.heading if spec.font == "heading" else theme.fonts.body
    bold = theme.fonts.heading_bold if spec.heading else False
    uppercase = theme.fonts.heading_uppercase if spec.heading else False
    largest = max(spec.smallest, round(spec.largest * theme.text_scale / fit.STEP) * fit.STEP)
    fitted = fit.fit(text.upper() if uppercase else text, box.w, box.h, font, largest, spec.smallest, bold)
    colors = {"text": theme.palette.text, "muted": theme.palette.muted, "light": LIGHT_TEXT}
    return TextStyle(
        font=font,
        size=fitted.size,
        color=colors[spec.color],
        bold=bold,
        italic=spec.italic,
        uppercase=uppercase,
        align=theme.title_align if spec.align == "title" else spec.align,
        anchor=spec.anchor,
    )


# THE LAYOUTS (each a function of the slide's elements by role, and the theme)

_TITLE: Final = Box(x=MARGIN, y=56, w=WIDTH - 2 * MARGIN, h=150)
_CONTENT_TOP: Final = 236
_CONTENT_BOTTOM: Final = 980


def _title_slide(roles: dict[str, Content], theme: Theme) -> _Placement:
    title = Box(x=160, y=230, w=1600, h=420)
    placement = _Placement(f"v5/title-{theme.title_align}")
    placement.boxes["title"] = (title, "talk title")
    placement.boxes["subtitle"] = (Box(x=160, y=700, w=1600, h=170), "subtitle")
    placement.shapes += _decoration(theme, title, gap=22)
    return placement


def _statement(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement(
        "v5/statement", shapes=[ShapeElement(role="shade", box=FULL, color=SHADE, opacity=SHADE_OPACITY)]
    )
    placement.boxes["text"] = (Box(x=200, y=200, w=1520, h=700), "statement")
    placement.boxes["title"] = (Box(x=200, y=72, w=1520, h=110), "statement title")
    return placement


def _image(roles: dict[str, Content], theme: Theme) -> _Placement:
    content_spec = "quote" if isinstance(roles.get("content"), TextElement) else "caption"
    if "title" in roles and random_util.random() < 0.35:  # the title beside the image
        title = Box(x=MARGIN, y=MARGIN, w=600, h=HEIGHT - 2 * MARGIN - 100)
        placement = _Placement("v5/image-side")
        placement.boxes["title"] = (title, "side title")
        placement.boxes["content"] = (
            Box(x=744, y=MARGIN, w=WIDTH - 744 - MARGIN, h=_CONTENT_BOTTOM - MARGIN),
            content_spec,
        )
        placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
        return placement
    placement = _Placement("v5/image-top")
    top = _with_title(placement, roles, theme)
    placement.boxes["content"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), content_spec)
    return placement


def _full_image(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/full-image", photo=True)
    placement.boxes["content"] = (FULL, "quote")
    if "title" in roles:
        band = Box(x=0, y=0, w=WIDTH, h=170)
        placement.shapes.append(
            ShapeElement(role="title band", box=band, color=theme.palette.surface, opacity=BAND_OPACITY)
        )
        placement.boxes["title"] = (Box(x=MARGIN, y=16, w=WIDTH - 2 * MARGIN, h=138), "band title")
    return placement


def _columns(count: int) -> Callable[[dict[str, Content], Theme], _Placement]:
    gap = 48
    width = (WIDTH - 2 * MARGIN - (count - 1) * gap) / count
    caption_height = 128 if count == 2 else 168
    caption_spec = "caption" if count == 2 else "small caption"

    def columns(roles: dict[str, Content], theme: Theme) -> _Placement:
        placement = _Placement(f"v5/columns-{count}")
        top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
        caption_top = _CONTENT_BOTTOM - caption_height
        for index in range(1, count + 1):
            x = MARGIN + (index - 1) * (width + gap)
            content = roles.get(f"content_{index}")
            spec = "quote" if isinstance(content, TextElement) else caption_spec
            placement.boxes[f"content_{index}"] = (Box(x=x, y=top, w=width, h=caption_top - top - 16), spec)
            placement.boxes[f"caption_{index}"] = (Box(x=x, y=caption_top, w=width, h=caption_height), caption_spec)
        return placement

    return columns


def _chart(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/chart")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    placement.boxes["chart"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), "caption")
    return placement


def _with_title(placement: _Placement, roles: dict[str, Content], theme: Theme) -> float:
    """Put the title on top, with the theme's decoration; where the content can start below it."""
    placement.boxes["title"] = (_TITLE, "title")
    placement.shapes += _decoration(theme, _TITLE, gap=16)
    return _CONTENT_TOP


def _decoration(theme: Theme, title: Box, gap: float) -> list[ShapeElement]:
    """The theme's decoration around a title: a bar, an underline, or a frame around the slide."""
    accent = theme.palette.accent
    below = title.y + title.h + gap
    if theme.decoration == "frame":
        inset, thickness = 24, 8
        return [
            ShapeElement(box=Box(x=inset, y=inset, w=WIDTH - 2 * inset, h=thickness), color=accent),
            ShapeElement(
                box=Box(x=inset, y=HEIGHT - inset - thickness, w=WIDTH - 2 * inset, h=thickness), color=accent
            ),
            ShapeElement(box=Box(x=inset, y=inset, w=thickness, h=HEIGHT - 2 * inset), color=accent),
            ShapeElement(
                box=Box(x=WIDTH - inset - thickness, y=inset, w=thickness, h=HEIGHT - 2 * inset), color=accent
            ),
        ]
    centered = theme.title_align == "center"
    if theme.decoration == "bar":
        if centered:
            return [ShapeElement(box=Box(x=WIDTH / 2 - 90, y=below, w=180, h=10), color=accent)]
        return [ShapeElement(box=Box(x=title.x - 40, y=title.y + title.h * 0.2, w=14, h=title.h * 0.6), color=accent)]
    if theme.decoration == "underline":
        if centered:
            return [ShapeElement(box=Box(x=WIDTH / 2 - 320, y=below, w=640, h=4), color=accent)]
        return [ShapeElement(box=Box(x=title.x, y=below, w=min(title.w, 560), h=4), color=accent)]
    return []


_LAYOUTS: Final[dict[str, Callable[[dict[str, Content], Theme], _Placement]]] = {
    "title": _title_slide,
    "large_quote": _statement,
    "image": _image,
    "full_image": _full_image,
    "two_column_image": _columns(2),
    "three_column_image": _columns(3),
    "chart": _chart,
}
