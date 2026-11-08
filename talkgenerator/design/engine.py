"""The layout engine: a deck's elements in their layout's boxes, in a theme's style (docs/v5-plan.md, section 9).

Every slide type has layouts, which are geometry only: boxes on the 1920×1080 canvas for the roles of its elements
(the title, the image, the captions...). The engine picks a layout for every slide (with the deck's seed), puts the
elements in its boxes, gives every text its theme's font and colour at the largest size at which it fits, and adds
the theme's background and decoration. With style_chaos, slides get themes of their own: none (0) to all (1).
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from talkgenerator.design import color, fit, fonts, geometry, layers, themes, treatments
from talkgenerator.models.deck import (
    DECORATION,
    Box,
    ChartElement,
    Content,
    Deck,
    DeckSlide,
    DiagramElement,
    DiagramStyle,
    ImageElement,
    MatrixDiagram,
    ShapeElement,
    SlideBackground,
    TextAnchor,
    TextElement,
    TextStyle,
    VennDiagram,
)
from talkgenerator.models.theme import TextEffect, Theme
from talkgenerator.render import diagrams  # (where a diagram's labels go: in its shapes, or beside them)
from talkgenerator.sources import memes
from talkgenerator.util import random_util

WIDTH: Final = 1920
HEIGHT: Final = 1080
MARGIN: Final = 96
CREDITS_BOX: Final = Box(x=MARGIN, y=996, w=WIDTH - 2 * MARGIN, h=36)
CREDITS_SIZE: Final = 18
# A band behind the credits, where they need one (over a photo, or across a panel): as wide as the slide, and just
# taller than the credit line (clear of what a theme's decoration puts under it, such as a status line)
CREDITS_BAND: Final = Box(x=0, y=CREDITS_BOX.y - 6, w=WIDTH, h=CREDITS_BOX.h + 8)
FULL: Final = Box(x=0, y=0, w=WIDTH, h=HEIGHT)
# Over a photo, texts are light on a dark shade
SHADE: Final = "#000000"
SHADE_OPACITY: Final = 0.55
BAND_OPACITY: Final = 0.85  # of the bands behind texts on a full-screen picture
LIGHT_TEXT: Final = "#ffffff"
# How opaque a diagram's circles are (where they overlap, their colours mix), and its quadrants (as in the template)
DIAGRAM_OPACITY: Final = {"venn": 0.45, "matrix": 0.2}
# Lines, such as a matrix's axes, need less contrast than texts to be seen (WCAG's 3 for graphics)
LINE_CONTRAST: Final = 3.0


@dataclass(frozen=True)
class TextSpec:
    """How a role's text looks: its font (the theme's heading or body font) and sizes, colour and place."""

    font: Literal["heading", "body"]
    largest: float
    smallest: float
    color: Literal["text", "muted", "light", "accent"] = "text"
    align: Literal["title", "left", "center", "right"] = "title"  # title: as the theme aligns its titles
    anchor: TextAnchor = "middle"
    heading: bool = False  # bold and in capitals as the theme's headings are
    italic: bool = False
    on_photo: bool = False  # on a shade or band over a photo, which could be anything
    # On a shape of its layout's (a tile, a badge, a card), in a colour the layout picks to read on it: a heading
    # effect's gradient leaves it be
    on_fill: bool = False
    bold: bool = False  # bold, whatever the theme's headings are (a name on a post)
    effect: bool = True  # with the theme's heading effect, for a heading (not a letter on a badge, say)
    # A look of its own, whatever the theme's (a meme's captions): a font, capitals, and an outline in this colour
    font_name: str | None = None
    uppercase: bool = False
    outline: str | None = None


SPECS: Final[dict[str, TextSpec]] = {
    "talk title": TextSpec("heading", 140, 64, anchor="bottom", heading=True),
    "subtitle": TextSpec("body", 52, 30, color="muted", anchor="top"),
    "title": TextSpec("heading", 88, 44, heading=True),
    "side title": TextSpec("heading", 96, 48, align="left", heading=True),
    "band title": TextSpec("heading", 80, 40, align="center", heading=True, on_photo=True),
    "centred title": TextSpec("heading", 80, 40, align="center", heading=True),
    "panel title": TextSpec("heading", 80, 40, align="left", heading=True, on_photo=True),
    "statement": TextSpec("heading", 120, 52, color="light", align="center", heading=True, on_photo=True),
    "statement title": TextSpec("heading", 56, 32, color="light", align="center", heading=True, on_photo=True),
    "left statement": TextSpec("heading", 112, 52, color="light", align="left", heading=True, on_photo=True),
    "left statement title": TextSpec("heading", 56, 32, color="light", align="left", heading=True, on_photo=True),
    "band statement": TextSpec("heading", 96, 44, align="center", heading=True, on_photo=True),
    "caption": TextSpec("body", 52, 28, align="center", anchor="top"),
    "small caption": TextSpec("body", 44, 26, align="center", anchor="top"),
    "heading caption": TextSpec("body", 52, 28, align="center", anchor="bottom"),  # above its picture
    "small heading caption": TextSpec("body", 44, 26, align="center", anchor="bottom"),
    "side caption": TextSpec("body", 52, 28, align="left"),  # beside its picture, on the right
    "side caption right": TextSpec("body", 52, 28, align="right"),  # beside its picture, on the left
    "quote": TextSpec("body", 64, 30, align="left", italic=True),
    # Milestone 6's slide types: figures, quizzes, mockups of posts and news, and the talk's structure
    "big number": TextSpec("heading", 300, 120, color="accent", align="center", heading=True),
    "panel number": TextSpec("heading", 260, 96, align="center", heading=True, on_fill=True),
    "number label": TextSpec("body", 72, 32, align="center", anchor="top"),
    "side label": TextSpec("body", 72, 32, align="left"),
    "source": TextSpec("body", 36, 24, color="muted", align="center", italic=True),
    "side source": TextSpec("body", 36, 24, color="muted", align="left", italic=True),
    "tile number": TextSpec(
        "heading", 150, 44, align="center", anchor="bottom", heading=True, on_fill=True, effect=False
    ),
    "tile label": TextSpec("body", 56, 26, align="center", anchor="top", on_fill=True),
    "row number": TextSpec("heading", 120, 44, align="left", heading=True, on_fill=True, effect=False),
    "row label": TextSpec("body", 64, 28, align="left", on_fill=True),
    # (a letter or a number on a disc)
    "badge": TextSpec("heading", 64, 28, align="center", heading=True, on_fill=True, effect=False),
    "option": TextSpec("body", 64, 28, align="left"),
    "tile option": TextSpec("body", 60, 28, align="left", on_fill=True),
    "stamp": TextSpec("heading", 160, 56, align="center", heading=True, on_fill=True, effect=False),
    "explanation": TextSpec("body", 52, 26, align="center"),
    "post author": TextSpec("body", 52, 28, align="left", anchor="bottom", on_fill=True, bold=True),
    "post handle": TextSpec("body", 40, 24, align="left", anchor="top", on_fill=True),
    "post text": TextSpec("body", 64, 28, align="left", anchor="top", on_fill=True),
    "big post text": TextSpec("body", 88, 36, align="left", anchor="top", on_fill=True),
    "post stats": TextSpec("body", 36, 24, align="left", on_fill=True),
    "masthead": TextSpec("heading", 120, 56, align="center", heading=True, on_fill=True),
    "headline": TextSpec("heading", 100, 48, align="center", heading=True, on_fill=True),
    "subheadline": TextSpec("body", 48, 26, align="left", anchor="top", on_fill=True),
    "kicker": TextSpec("heading", 40, 24, align="left", heading=True, on_fill=True, effect=False),
    "tv headline": TextSpec("heading", 84, 40, align="left", heading=True, on_fill=True, effect=False),
    "ticker": TextSpec("body", 36, 24, align="left", on_fill=True),
    "outlet": TextSpec("heading", 44, 24, align="center", heading=True, on_fill=True, effect=False),
    "item": TextSpec("body", 68, 30, align="left"),
    "step": TextSpec("body", 56, 26, align="center", anchor="top"),
    "section number": TextSpec("heading", 240, 100, color="accent", anchor="bottom", heading=True),
    "section title": TextSpec("heading", 128, 56, anchor="top", heading=True),
    "section side title": TextSpec("heading", 112, 52, align="left", anchor="bottom", heading=True),
    "questions": TextSpec("heading", 200, 80, align="center", heading=True),
    "centred subtitle": TextSpec("body", 52, 30, color="muted", align="center", anchor="top"),
    "left title": TextSpec("heading", 140, 60, align="left", anchor="bottom", heading=True),
    "left subtitle": TextSpec("body", 52, 30, color="muted", align="left", anchor="top"),
    "mark": TextSpec("heading", 900, 320, color="accent", align="center", heading=True),
    # (a meme's captions: white Impact in capitals with a black outline, over anything; or plain black text, on the
    # template's own even area)
    "meme": TextSpec(
        "body", 96, 28, color="light", align="center", font_name="Impact", uppercase=True, outline="#000000"
    ),
    "plain meme": TextSpec("body", 80, 26, align="center", on_fill=True, font_name="Arial"),
    # (native diagrams)
    "date": TextSpec("body", 72, 28, align="center", anchor="bottom", bold=True),  # (not in capitals: too wide)
    "row date": TextSpec("body", 64, 28, align="right", bold=True),
    "level": TextSpec("body", 56, 28, align="center", on_fill=True, bold=True),
    "disc": TextSpec("body", 44, 26, align="center", on_fill=True, bold=True),
    "box": TextSpec("body", 48, 26, align="center", on_fill=True),
    "boss": TextSpec("heading", 64, 30, align="center", heading=True, on_fill=True, effect=False),
    # (a theme's decoration's own: a slide's number, a terminal window's name, a prompt, a sticker's word)
    "decoration": TextSpec("body", 28, 24, align="left", on_fill=True),
    "decoration right": TextSpec("body", 28, 24, align="right", on_fill=True),
    "decoration centre": TextSpec("body", 28, 24, align="center", on_fill=True),
    "decoration heading": TextSpec("heading", 44, 24, align="center", heading=True, on_fill=True, effect=False),
    "decoration figure": TextSpec("heading", 72, 24, align="right", heading=True, on_fill=True, effect=False),
    # (the families' own layouts: a kindergarten's title, a Swiss poster's, a front page's masthead, a lecture's)
    "kids title": TextSpec("heading", 130, 56, align="center", heading=True),
    "swiss title": TextSpec("heading", 210, 56, align="left", anchor="bottom", heading=True),
    "swiss number": TextSpec("heading", 640, 200, align="left", anchor="bottom", heading=True, effect=False),
    "masthead title": TextSpec("heading", 150, 64, align="center", heading=True),
    "byline": TextSpec("body", 40, 26, color="muted", align="center", italic=True),
    "beamer title": TextSpec("heading", 110, 52, align="center", heading=True, on_fill=True),
}


@dataclass
class Placement:
    layout: str
    boxes: dict[str, tuple[Box, str]] = field(default_factory=dict)  # role: (box, text spec)
    shapes: list[ShapeElement] = field(default_factory=list)  # drawn behind the content
    overlays: list[ShapeElement] = field(default_factory=list)  # drawn over the content, under the texts
    photo: bool = False  # a photo fills the slide: credits go on a band
    colors: dict[str, str] = field(default_factory=dict)  # role: the colour of a text on a shape (that reads on it)
    # The roles of pictures shown as they are, without the theme's treatment (a meme's template, captioned in place)
    untreated: set[str] = field(default_factory=set)
    # The theme's own decoration (see talkgenerator.design.motifs): shapes behind everything (scenery, a frame around
    # the slide), shapes over the layout's own (a sticker, a title's underline), and texts (a terminal's prompt, a
    # slide's number), each with its box, text spec and colour
    under: list[ShapeElement] = field(default_factory=list)
    decor: list[ShapeElement] = field(default_factory=list)
    texts: list[tuple[str, Box, str | TextSpec, str]] = field(default_factory=list)
    # The roles of pictures that fill their box, cropped (where the decoration drew a frame around the box)
    cover: set[str] = field(default_factory=set)
    # The roles of texts the decoration put on a fill of its own (a title on a band): a heading effect's gradient
    # leaves them be, as it does a text on a shape of the layout's
    on_fill: set[str] = field(default_factory=set)
    # The roles of texts that get no heading effect at all (a title on a decoration's block or in its balloon)
    plain: set[str] = field(default_factory=set)
    # The roles of pictures the decoration framed itself (a terminal window's, a sticker's border): they get no frame
    # of the theme's
    framed: set[str] = field(default_factory=set)


def lay_out(deck: Deck, theme: Theme, style_chaos: float = 0.0, extremes: bool = True) -> Deck:
    """The deck with its elements placed and styled in the theme; with style_chaos, some slides (that share of
    them, picked by the seed) in themes of their own."""
    layout = DeckLayout(deck.seed, theme, style_chaos, extremes)
    slides = tuple(layout.next(slide) for slide in deck.slides)
    return deck.model_copy(update={"theme": theme.name, "style": theme, "slides": slides})


class DeckLayout:
    """Lays a deck's slides out one at a time, in order, as lay_out does all at once: a slide's layout depends on the
    deck's seed, the slide's place, and the layouts of the slides before it, so slides can be laid out as they come
    in (talkgenerator.generator.stream_talk)."""

    def __init__(self, seed: int | None, theme: Theme, style_chaos: float = 0.0, extremes: bool = True) -> None:
        self.theme, self.style_chaos, self.extremes = theme, style_chaos, extremes
        self._rng = random_util.Rng(seed if seed is not None else 0).child("layout")
        self._used: Counter[str] = Counter()  # how often the deck has had each layout so far
        self._previous: str | None = None
        self._number = 0
        # What the deck had laid out before each slide (the layout before it, and how often each came up), for a slide
        # that's laid out again
        self._before: list[tuple[str | None, Counter[str]]] = []

    def next(self, slide: DeckSlide) -> DeckSlide:
        """The deck's next slide, laid out."""
        self._before.append((self._previous, Counter(self._used)))
        placed = self._lay_out(slide, self._number, self._previous, self._used)
        self._used[placed.layout] += 1
        self._previous = placed.layout
        self._number += 1
        return placed

    def again(self, number: int, slide: DeckSlide) -> DeckSlide:
        """A slide laid out before (the number-th, from 0) laid out again, as it was: for a slide that got a picture
        later (see talkgenerator.images.generation), which has the same elements, so it gets the same layout, as the
        deck laid out at once gives it."""
        previous, used = self._before[number]
        return self._lay_out(slide, number, previous, used)

    def _lay_out(self, slide: DeckSlide, number: int, previous: str | None, used: Counter[str]) -> DeckSlide:
        slide_rng = self._rng.child("slide", number)
        own = None
        if self.style_chaos > 0:
            with random_util.use(slide_rng.child("chaos")):
                chaotic = random_util.random() < self.style_chaos
            if chaotic:
                own = themes.pick(themes.RANDOM, slide_rng.child("theme"), self.extremes)
        return lay_out_slide(
            slide, own or self.theme, slide_rng, own_style=own is not None, previous=previous, used=used, number=number
        )


def layouts_for(slide: DeckSlide, theme: Theme | None = None) -> list[str]:
    """The layouts that fit the slide: those of its type that fit its elements (a full-screen picture's title goes on
    a band or a panel, and one without a title can be framed instead, say), and its theme (some families have
    layouts of their own: a terminal's title slide, say)."""
    roles = {element.role: element for element in slide.elements}
    family = theme.family if theme is not None else None
    return [layout.name for layout in _LAYOUTS.get(slide.type, ()) if layout.fits(roles) and layout.for_family(family)]


def layout_names(theme: Theme | None = None) -> list[str]:
    """Every layout's name, slide type by slide type (a title slide's is named for its theme's alignment, as
    v5/title-left or v5/title-center): those a theme's slides can have, or (with no theme) every one there is, the
    families' own included."""
    family = theme.family if theme is not None else None
    return [
        layout.name for layouts in _LAYOUTS.values() for layout in layouts if theme is None or layout.for_family(family)
    ]


def lay_out_slide(
    slide: DeckSlide,
    theme: Theme,
    rng: random_util.Rng,
    own_style: bool = False,
    previous: str | None = None,
    used: Mapping[str, int] | None = None,
    number: int = 0,
) -> DeckSlide:
    """The slide (the number-th of its deck, from 0) in one of the layouts that fit it and its theme, picked with its
    random generator: not the previous slide's layout if another one fits, and less likely the more often the deck
    has had it already (used); with its theme's own decoration (see talkgenerator.design.motifs)."""
    from talkgenerator.design import motifs  # (here: motifs draw with this module's layouts and specs)

    layouts = [layout for layout in _LAYOUTS.get(slide.type, ()) if layout.for_family(theme.family)]
    if not layouts:
        raise ValueError(f"There's no layout for {slide.type!r} slides")
    roles = {element.role: element for element in slide.elements}
    fitting = [layout for layout in layouts if layout.fits(roles)] or [layouts[0]]
    fresh = [layout for layout in fitting if layout.name != previous] or fitting
    counts = used or {}
    with random_util.use(rng.child("variant")):
        chosen = random_util.weighted_random(
            [(layout.weight * 0.5 ** counts.get(layout.name, 0), layout) for layout in fresh]
        )
    with random_util.use(rng):
        placement = (chosen or fresh[0]).build(roles, theme)
    background = roles.get("background")
    if "background" in placement.boxes:  # (a layout that puts the photo in a box of its own, not behind everything)
        background = None
    with random_util.use(rng.child("motif")):
        motifs.decorate(
            motifs.Scene(
                placement=placement,
                roles=roles,
                slide_type=slide.type,
                theme=theme,
                number=number,
                credits=bool(slide.credits),
                backdrop=isinstance(background, ImageElement),
            )
        )
    palette = theme.palette
    slide_background = SlideBackground(
        color=palette.background,
        color_2=theme.gradient_to if theme.background == "gradient" else None,
        pattern=theme.pattern,
    )
    backdrop: list[Content] = []  # a photo behind everything, and the shapes behind the content
    if isinstance(background, ImageElement):
        with random_util.use(rng.child("treatment", background.role)):
            look = treatments.for_look(treatments.treatment(theme, framed=False), background.image, theme)
        backdrop.append(background.model_copy(update={"box": FULL, "fit": "cover", "treatment": look}))
    backdrop += [*placement.under, *placement.shapes, *placement.decor]
    content: list[Content] = []  # pictures, charts and diagrams; the bands over them; then the texts, on top
    texts: list[Content] = []
    for element in slide.elements:
        if (background is not None and element is background) or element.role not in placement.boxes:
            continue
        box, spec = placement.boxes[element.role]
        if isinstance(element, TextElement):
            on_fill = element.role in placement.on_fill
            colour = placement.colors.get(element.role)
            style = _style(element.text, box, SPECS[spec], theme, colour, on_fill, element.role in placement.plain)
            texts.append(element.model_copy(update={"box": box, "style": style}))
        elif isinstance(element, ImageElement):
            framed = box != FULL and not placement.photo  # (a picture over the whole slide gets no frame)
            own_frame = element.role in placement.framed  # (one the decoration drew around it)
            with random_util.use(rng.child("treatment", element.role)):
                look = treatments.for_look(treatments.treatment(theme, framed and not own_frame), element.image, theme)
            if own_frame and look is not None and not framed:  # (filtered as a picture in a box is)
                look = treatments.for_look(treatments.treatment(theme, framed=True), element.image, theme)
            if element.role in placement.untreated:
                look = None
            polaroid = look is not None and look.frame == "polaroid"  # (its own white frame instead of a border)
            border = palette.text if theme.image_border and framed and not polaroid and not own_frame else None
            update: dict[str, object] = {"box": box, "border": border, "treatment": look}
            if element.role in placement.cover:
                update["fit"] = "cover"
            content.append(element.model_copy(update=update))
        elif isinstance(element, ChartElement):
            content.append(element.model_copy(update={"box": box}))
        elif isinstance(element, DiagramElement):
            under = layers.behind(slide_background, backdrop, box)  # (the background, and decoration reaching under it)
            diagram_look = diagram_style(element.diagram, theme, box, under)
            content.append(element.model_copy(update={"box": box, "style": diagram_look}))
    for text, place, text_spec, colour in placement.texts:  # (the decoration's own: a prompt, a slide's number)
        own = SPECS[text_spec] if isinstance(text_spec, str) else text_spec
        texts.append(
            TextElement(role=DECORATION, text=text, box=place, style=_style(text, place, own, theme, colour, True))
        )
    elements = [*backdrop, *content, *placement.overlays, *texts]
    # The credits read on what's behind them: the background (and the shapes on it, such as a panel or a band of the
    # theme's decoration), or a photo (which could be anything) under a shade
    behind = layers.behind(slide_background, elements, CREDITS_BOX)
    if placement.photo and slide.credits:  # on a band over the picture, solid if no colour reads on it otherwise
        opacity = BAND_OPACITY
        over = [color.mix(colour, palette.surface, opacity) for colour in behind]
        if color.worst_contrast(color.readable_on(palette.muted, over), over) < color.BODY_CONTRAST:
            opacity, over = 1.0, [palette.surface]
        band = CREDITS_BAND
        elements.append(ShapeElement(role="credits band", box=band, color=palette.surface, opacity=opacity))
        behind = over
    credits_color = color.readable_on(palette.muted, behind, color.BODY_CONTRAST)
    if slide.credits and color.worst_contrast(credits_color, behind) < color.BODY_CONTRAST:
        # (across a panel that no colour reads on as well as on the background: on a band of their own)
        band = CREDITS_BAND
        elements.append(ShapeElement(role="credits band", box=band, color=palette.surface))
        credits_color = color.readable_on(palette.muted, [palette.surface], color.BODY_CONTRAST)
    return slide.model_copy(
        update={
            "layout": placement.layout,
            "elements": tuple(elements),
            "background": slide_background,
            "style": theme if own_style else None,
            "credits_box": CREDITS_BOX,
            "credits_style": TextStyle(font=theme.fonts.body, size=CREDITS_SIZE, color=credits_color, anchor="middle"),
        }
    )


def _style(
    text: str,
    box: Box,
    spec: TextSpec,
    theme: Theme,
    colour: str | None = None,
    on_fill: bool = False,
    plain: bool = False,
) -> TextStyle:
    """A text's style in the theme, at the largest size at which it fits its box: in the spec's colour, or in the
    colour its layout picked (one that reads on the shape it's on: on_fill, a shape of the decoration's), with the
    theme's heading effect for a heading (unless it's plain)."""
    font = spec.font_name or (theme.fonts.heading if spec.font == "heading" else theme.fonts.body)
    bold = (theme.fonts.heading_bold if spec.heading else False) or spec.bold
    uppercase = spec.uppercase or (theme.fonts.heading_uppercase if spec.heading else False)
    largest = max(spec.smallest, round(spec.largest * theme.text_scale / fit.STEP) * fit.STEP)
    fitted = fit.fit(text.upper() if uppercase else text, box.w, box.h, font, largest, spec.smallest, bold)
    colors = {
        "text": theme.palette.text,
        "muted": theme.palette.muted,
        "light": LIGHT_TEXT,
        "accent": theme.palette.accent,
    }
    effect = theme.heading_effect if spec.heading and spec.effect and not plain else None
    if effect is not None and (
        spec.on_photo or spec.on_fill or on_fill
    ):  # (its colour reads there; a gradient may not)
        effect = effect.model_copy(update={"fill": ()})
    if spec.outline:  # (an outline a twelfth of the text's size, as memes have it)
        effect = TextEffect(outline=spec.outline, outline_width=max(2.0, round(fitted.size / 12, 1)))
    return TextStyle(
        font=font,
        size=fitted.size,
        color=colour or colors[spec.color],
        bold=bold,
        italic=spec.italic,
        uppercase=uppercase,
        align=theme.title_align if spec.align == "title" else spec.align,
        anchor=spec.anchor,
        effect=effect,
    )


def text_lines(text: str, box: Box, spec: str | TextSpec, theme: Theme) -> tuple[TextStyle, list[Box]]:
    """A text's style in its box (as the engine fits it), and where its lines go: a box as wide as each line, where
    the text's alignment and anchor put it (as renderers break and place it). For a decoration that goes with a
    text's words rather than its box: an underline as long as a title, a cursor after its last word."""
    style = _style(text, box, SPECS[spec] if isinstance(spec, str) else spec, theme)
    return style, line_boxes(text, box, style)


def line_boxes(text: str, box: Box, style: TextStyle) -> list[Box]:
    """Where a text in a style breaks into lines in its box, and where each line goes (as wide as it is), by the
    style's alignment and anchor."""
    shown = text.upper() if style.uppercase else text
    lines = fit.wrap(shown, box.w, style.font, style.size, style.bold)
    height = style.size * fit.LINE_HEIGHT
    total = height * len(lines)
    top = {"top": box.y, "middle": box.y + (box.h - total) / 2, "bottom": box.y + box.h - total}[style.anchor]
    placed = []
    for index, line in enumerate(lines):
        width = min(box.w, fonts.text_width(line, style.font, style.size, style.bold))
        x = {"left": box.x, "center": box.x + (box.w - width) / 2, "right": box.x + box.w - width}[style.align]
        placed.append(Box(x=x, y=top + index * height, w=width, h=height))
    return placed


def _overlap(box: Box, other: Box) -> bool:
    """Whether the boxes share some area (not just an edge)."""
    return (
        box.x < other.x + other.w and other.x < box.x + box.w and box.y < other.y + other.h and other.y < box.y + box.h
    )


def _backgrounds(theme: Theme) -> list[str]:
    """The colours of a slide's background in the theme: one, or both ends of a gradient."""
    palette = theme.palette
    return [palette.background, *([theme.gradient_to] if theme.background == "gradient" and theme.gradient_to else [])]


def diagram_style(
    diagram: VennDiagram | MatrixDiagram, theme: Theme, box: Box, backgrounds: Sequence[str] | None = None
) -> DiagramStyle:
    """A diagram's look in the theme, in its box: its labels in the theme's body font and text colour, its circles or
    quadrants in the theme's accents (and two hues a third of the way round from them), and its punchline in the
    colour that stands out. Circles and quadrants get lighter or darker (keeping their hue) until the text reads on
    them, and where they overlap: the theme's text reads on its background, so on a lighter or darker shade of it
    too. (A Venn diagram's labels beside its circles read on the background, and the text colour is picked so.) The
    backgrounds are what's behind its box: the theme's background, and its decoration's colours where it reaches
    under the box (a grid's lines, a blob)."""
    palette = theme.palette
    backgrounds = list(backgrounds) if backgrounds else _backgrounds(theme)
    opacity = DIAGRAM_OPACITY[diagram.diagram_type]
    turned = [color.to_hsl(accent) for accent in (palette.accent, palette.accent_2)]
    accents = (
        palette.accent,
        palette.accent_2,
        *(color.hsl(hue + 120, saturation, lightness) for hue, saturation, lightness in turned),
    )
    overlapping = len(diagram.circles) if isinstance(diagram, VennDiagram) else 0
    beside = diagrams.labels_beside(diagrams.Box.on_canvas(box), diagram, theme.fonts.body)
    fills = _readable_fills(accents, palette.text, backgrounds, opacity, overlapping, pairs=beside)
    labels, punchline, lines = diagram_behind(diagram, fills, opacity, backgrounds, beside)
    return DiagramStyle(
        font=theme.fonts.body,
        fills=fills,
        opacity=opacity,
        text=color.readable_on(palette.text, labels),
        lines=color.readable_on(palette.text, lines, LINE_CONTRAST) if lines else palette.text,
        punchline=color.readable_on(palette.accent_2, punchline) if punchline else palette.accent_2,
        outline=palette.background,
    )


def _readable_fills(
    fills: Sequence[str],
    text: str,
    backgrounds: Sequence[str],
    opacity: float,
    overlapping: int,
    pairs: bool = False,
) -> tuple[str, ...]:
    """The fills, each the nearest shade of it (by its lightness: lighter under dark text, darker under light text)
    on which the text reads, over every background; and with the first ones (as many as overlap) shaded further, if
    the text doesn't read where they all overlap yet (or, with pairs, where any two of them overlap: a Venn diagram's
    overlap with its labels beside the circles may spread over those parts)."""
    lighter = color.luminance(text) < color.luminance(backgrounds[0])

    def shade(fill: str, steps: int) -> str:
        hue, saturation, lightness = color.to_hsl(fill)
        return color.hsl(hue, saturation, lightness + (0.05 if lighter else -0.05) * steps)

    def reads(*layers: str) -> bool:
        return color.worst_contrast(text, _under(backgrounds, layers, opacity)) >= color.BODY_CONTRAST

    def reads_where_they_overlap(circles: Sequence[str]) -> bool:
        together = [tuple(circles), *(itertools.combinations(circles, 2) if pairs else ())]
        return all(reads(*layers) for layers in together)

    steps = [next((step for step in range(21) if reads(shade(fill, step))), 20) for fill in fills]
    shaded = [shade(fill, step) for fill, step in zip(fills, steps, strict=True)]
    for more in range(1, 21):
        if overlapping < 2 or reads_where_they_overlap(shaded[:overlapping]):
            break
        shaded = [shade(fill, step + more) for fill, step in zip(fills, steps, strict=True)]
    return tuple(shaded)


def _under(backgrounds: Sequence[str], layers: Sequence[str], opacity: float) -> list[str]:
    """The backgrounds with the see-through layers over them, one on top of the other."""
    found = []
    for background in backgrounds:
        mixed = background
        for layer in layers:
            mixed = color.mix(mixed, layer, opacity)
        found.append(mixed)
    return found


def diagram_behind(
    diagram: VennDiagram | MatrixDiagram,
    fills: Sequence[str],
    opacity: float,
    backgrounds: Sequence[str],
    beside: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """What may be behind a diagram's labels, its punchline's name and its lines: the backgrounds, under the circles
    or quadrants they're on (where a Venn diagram's circles overlap, under all of them). A Venn diagram's labels
    beside its circles are on the backgrounds themselves, and its overlap's label may then spread over every part of
    the middle (where two circles overlap, too)."""

    def under(*layers: str) -> list[str]:
        return _under(backgrounds, layers, opacity)

    if isinstance(diagram, VennDiagram):
        circles = fills[: len(diagram.circles)]
        labels = [*(mixed for circle in circles for mixed in under(circle)), *under(*circles)]
        if beside:
            labels += [*backgrounds, *(mixed for pair in itertools.combinations(circles, 2) for mixed in under(*pair))]
        return labels, [], []
    tints = [mixed for quadrant in fills[:4] for mixed in under(quadrant)]
    # The axes' titles are outside the matrix, on the background; the axes cross it, and reach beyond it
    return [*tints, *backgrounds], tints, [*tints, *backgrounds]


# THE LAYOUTS (each a function of the slide's elements by role, and the theme; a slide type has one or more)

_TITLE: Final = Box(x=MARGIN, y=56, w=WIDTH - 2 * MARGIN, h=150)
_CONTENT_TOP: Final = 236
_CONTENT_BOTTOM: Final = 980
_SIDE_TITLE_WIDTH: Final = 600  # a title beside the content
_SIDE_GAP: Final = 48
_GAP: Final = 48  # between columns


def _title_slide(roles: dict[str, Content], theme: Theme) -> Placement:
    title = Box(x=160, y=230, w=1600, h=420)
    placement = Placement(f"v5/title-{theme.title_align}")
    placement.boxes["title"] = (title, "talk title")
    placement.boxes["subtitle"] = (Box(x=160, y=700, w=1600, h=170), "subtitle")
    placement.shapes += _decoration(theme, title, gap=22)
    return placement


def _shade() -> ShapeElement:
    return ShapeElement(role="shade", box=FULL, color=SHADE, opacity=SHADE_OPACITY)


def _statement(roles: dict[str, Content], theme: Theme) -> Placement:
    placement = Placement("v5/statement", shapes=[_shade()])
    placement.boxes["text"] = (Box(x=200, y=200, w=1520, h=700), "statement")
    placement.boxes["title"] = (Box(x=200, y=72, w=1520, h=110), "statement title")
    return placement


def _statement_left(roles: dict[str, Content], theme: Theme) -> Placement:
    """The statement over the shaded photo, aligned left beside a bar in the theme's accent (made visible on it)."""
    shaded = [color.mix(extreme, SHADE, SHADE_OPACITY) for extreme in ("#000000", "#ffffff")]
    bar = ShapeElement(
        role="decoration",
        box=Box(x=150, y=250, w=14, h=600),
        color=color.readable_on(theme.palette.accent, shaded, LINE_CONTRAST),
    )
    placement = Placement("v5/statement-left", shapes=[_shade(), bar])
    placement.boxes["text"] = (Box(x=210, y=200, w=1510, h=700), "left statement")
    placement.boxes["title"] = (Box(x=210, y=72, w=1510, h=110), "left statement title")
    return placement


def _statement_band(roles: dict[str, Content], theme: Theme) -> Placement:
    """The statement in the theme's text colour, on a band across the shaded photo."""
    band = ShapeElement(
        role="statement band", box=Box(x=0, y=290, w=WIDTH, h=520), color=theme.palette.surface, opacity=BAND_OPACITY
    )
    placement = Placement("v5/statement-band", shapes=[_shade()], overlays=[band])
    placement.boxes["text"] = (Box(x=200, y=320, w=1520, h=460), "band statement")
    placement.boxes["title"] = (Box(x=200, y=150, w=1520, h=110), "statement title")
    return placement


def _content_spec(element: Content | None, caption: str = "caption") -> str:
    """The text spec of a content: a quote if it's a text (not a picture)."""
    return "quote" if isinstance(element, TextElement) else caption


def _image_top(roles: dict[str, Content], theme: Theme) -> Placement:
    placement = Placement("v5/image-top")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    content = Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top)
    placement.boxes["content"] = (content, _content_spec(roles.get("content")))
    return placement


def _image_beside(right: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """The title beside the image: on its left, or (right) on its right."""
    content_width = WIDTH - 2 * MARGIN - _SIDE_TITLE_WIDTH - _SIDE_GAP

    def image_beside(roles: dict[str, Content], theme: Theme) -> Placement:
        title_x = WIDTH - MARGIN - _SIDE_TITLE_WIDTH if right else MARGIN
        content_x = MARGIN if right else MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP
        title = Box(x=title_x, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
        placement = Placement("v5/image-side-right" if right else "v5/image-side")
        placement.boxes["title"] = (title, "side title")
        content = Box(x=content_x, y=MARGIN, w=content_width, h=_CONTENT_BOTTOM - MARGIN)
        placement.boxes["content"] = (content, _content_spec(roles.get("content")))
        placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
        return placement

    return image_beside


def _full_image(roles: dict[str, Content], theme: Theme) -> Placement:
    """The picture over the whole slide, and its title on a band across the top."""
    return _full_image_with("v5/full-image", roles, theme, Box(x=0, y=0, w=WIDTH, h=170), "band title")


def _full_image_framed(roles: dict[str, Content], theme: Theme) -> Placement:
    """A picture without a title, inset from the slide's edges (framed, in themes that frame pictures)."""
    placement = Placement("v5/full-image-framed")
    placement.boxes["content"] = (Box(x=MARGIN, y=64, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - 64), "quote")
    return placement


def _full_image_low(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title on a band across the bottom (above the credits)."""
    return _full_image_with("v5/full-image-low", roles, theme, Box(x=0, y=800, w=WIDTH, h=170), "band title")


def _full_image_corner(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title on a panel in the bottom left corner."""
    return _full_image_with("v5/full-image-corner", roles, theme, Box(x=56, y=690, w=1000, h=260), "panel title")


def _full_image_with(name: str, roles: dict[str, Content], theme: Theme, band: Box, spec: str) -> Placement:
    placement = Placement(name, photo=True)
    placement.boxes["content"] = (FULL, "quote")
    if "title" in roles:
        placement.overlays.append(
            ShapeElement(role="title band", box=band, color=theme.palette.surface, opacity=BAND_OPACITY)
        )
        inset = 40 if spec == "panel title" else MARGIN
        title = Box(x=band.x + inset, y=band.y + 16, w=band.w - 2 * inset, h=band.h - 32)
        placement.boxes["title"] = (title, spec)
    return placement


def _columns(count: int) -> Callable[[dict[str, Content], Theme], Placement]:
    """Side by side, with their captions under them."""
    width = (WIDTH - 2 * MARGIN - (count - 1) * _GAP) / count
    caption_height = 128 if count == 2 else 168
    caption_spec = "caption" if count == 2 else "small caption"

    def columns(roles: dict[str, Content], theme: Theme) -> Placement:
        placement = Placement(f"v5/columns-{count}")
        top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
        caption_top = _CONTENT_BOTTOM - caption_height
        for index in range(1, count + 1):
            x = MARGIN + (index - 1) * (width + _GAP)
            spec = _content_spec(roles.get(f"content_{index}"), caption_spec)
            placement.boxes[f"content_{index}"] = (Box(x=x, y=top, w=width, h=caption_top - top - 16), spec)
            placement.boxes[f"caption_{index}"] = (Box(x=x, y=caption_top, w=width, h=caption_height), caption_spec)
        return placement

    return columns


def _headed_columns(count: int) -> Callable[[dict[str, Content], Theme], Placement]:
    """Side by side, with their captions above them, as headings."""
    width = (WIDTH - 2 * MARGIN - (count - 1) * _GAP) / count
    caption_height = 128 if count == 2 else 168
    caption_spec = "heading caption" if count == 2 else "small heading caption"

    def headed(roles: dict[str, Content], theme: Theme) -> Placement:
        placement = Placement(f"v5/columns-{count}-headed")
        top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
        content_top = top + caption_height + 16
        for index in range(1, count + 1):
            x = MARGIN + (index - 1) * (width + _GAP)
            spec = _content_spec(roles.get(f"content_{index}"), caption_spec)
            placement.boxes[f"caption_{index}"] = (Box(x=x, y=top, w=width, h=caption_height), caption_spec)
            placement.boxes[f"content_{index}"] = (
                Box(x=x, y=content_top, w=width, h=_CONTENT_BOTTOM - content_top),
                spec,
            )
        return placement

    return headed


def _rows(roles: dict[str, Content], theme: Theme) -> Placement:
    """The two one above the other, zig-zag: the first on the left with its caption on its right, the second on the
    right with its caption on its left."""
    placement = Placement("v5/columns-2-rows")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    gap = 24
    height = (_CONTENT_BOTTOM - top - gap) / 2
    content_width = 640  # (most pictures are landscape: a narrower box keeps them by their captions)
    caption_width = WIDTH - 2 * MARGIN - content_width - _GAP
    rows = (
        (MARGIN, MARGIN + content_width + _GAP, "side caption"),
        (WIDTH - MARGIN - content_width, MARGIN, "side caption right"),
    )
    for index, (content_x, caption_x, caption_spec) in enumerate(rows, 1):
        y = top + (index - 1) * (height + gap)
        spec = _content_spec(roles.get(f"content_{index}"), caption_spec)
        placement.boxes[f"content_{index}"] = (Box(x=content_x, y=y, w=content_width, h=height), spec)
        placement.boxes[f"caption_{index}"] = (Box(x=caption_x, y=y, w=caption_width, h=height), caption_spec)
    return placement


def _split(roles: dict[str, Content], theme: Theme) -> Placement:
    """The slide split in two halves, the first in the theme's surface colour, each with its picture (or text) and
    its caption, and the title across the top, centred (with the theme's decoration)."""
    half = WIDTH / 2
    panel = ShapeElement(role="panel", box=Box(x=0, y=0, w=half, h=HEIGHT), color=theme.palette.surface)
    placement = Placement("v5/columns-2-split", shapes=[panel])
    top = MARGIN
    if "title" in roles:
        placement.boxes["title"] = (_TITLE, "centred title")
        placement.shapes += _decoration(theme.model_copy(update={"title_align": "center"}), _TITLE, gap=16)
        top = _CONTENT_TOP
    caption_height = 128
    caption_top = _CONTENT_BOTTOM - caption_height
    for index in (1, 2):
        x = (index - 1) * half + 64
        spec = _content_spec(roles.get(f"content_{index}"))
        placement.boxes[f"content_{index}"] = (Box(x=x, y=top, w=half - 128, h=caption_top - top - 16), spec)
        placement.boxes[f"caption_{index}"] = (Box(x=x, y=caption_top, w=half - 128, h=caption_height), "caption")
    return placement


def _chart(roles: dict[str, Content], theme: Theme) -> Placement:
    placement = Placement("v5/chart")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    placement.boxes["chart"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), "caption")
    return placement


def _chart_side(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title on the left, the chart beside it."""
    title = Box(x=MARGIN, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
    placement = Placement("v5/chart-side")
    placement.boxes["title"] = (title, "side title")
    x = MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP
    placement.boxes["chart"] = (Box(x=x, y=MARGIN, w=WIDTH - MARGIN - x, h=_CONTENT_BOTTOM - MARGIN), "caption")
    placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
    return placement


def _diagram(roles: dict[str, Content], theme: Theme) -> Placement:
    placement = Placement("v5/diagram")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    placement.boxes["diagram"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), "caption")
    return placement


def _with_title(placement: Placement, roles: dict[str, Content], theme: Theme) -> float:
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


def _always(roles: dict[str, Content]) -> bool:
    return True


def _titled(roles: dict[str, Content]) -> bool:
    return "title" in roles


def _untitled(roles: dict[str, Content]) -> bool:
    return "title" not in roles


def _beside_title(roles: dict[str, Content]) -> bool:
    """Whether the slide has a title that fits beside its content (a picture, a chart, a diagram): without a word too
    long for the side (a compound, as Dutch and German have them, can be wider than the side is in a wide font)."""
    title = roles.get("title")
    return isinstance(title, TextElement) and all(len(word) <= 15 for word in title.text.split())


def _beside_title_with_room(prefix: str, most: int) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide has a title that fits beside a diagram, and at most so many of the items (an org chart's
    people, a cycle's steps), for whose boxes there's room beside the title."""

    def fits(roles: dict[str, Content]) -> bool:
        return _beside_title(roles) and f"{prefix}_{most + 1}" not in roles

    return fits


def _has(role: str) -> Callable[[dict[str, Content]], bool]:
    def has(roles: dict[str, Content]) -> bool:
        return role in roles

    return has


def _short(role: str, characters: int) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide's text of the role is at most this long (a number that fits on a disc, say)."""

    def short(roles: dict[str, Content]) -> bool:
        element = roles.get(role)
        return isinstance(element, TextElement) and len(element.text) <= characters

    return short


# MILESTONE 6'S SLIDE TYPES (docs/v5-plan.md, section 8): big numbers and KPI tiles, quizzes, a social media post and
# a news headline, an agenda, a section's divider and the closing "Questions?". They're texts on shapes that the
# layouts draw in the theme's colours (tiles, badges, cards, bands), so every renderer draws them as it draws the
# other slides; a text on a shape gets a colour that reads on it.

_PANEL_WIDTH: Final = 760  # a panel along the slide's left side
_STAMP: Final = 260  # the diameter of the disc that a quiz's answer appears on
_EXPLANATION: Final = Box(x=MARGIN, y=864, w=WIDTH - 2 * MARGIN, h=108)  # under a quiz's options
_CARD_PADDING: Final = 44
_AVATAR: Final = 104
_POST_PHOTO_WIDTH: Final = 760


def _on(fills: Sequence[str], theme: Theme, minimum: float = color.BODY_CONTRAST) -> str:
    """The colour of a text on a fill (on each of the fills: a see-through one over what may be behind it): the
    theme's text or background colour, whichever reads better there, made lighter or darker until it reads."""
    palette = theme.palette
    best = max((palette.text, palette.background), key=lambda option: color.worst_contrast(option, fills))
    return color.readable_on(best, fills, minimum)


def _text_height(text: str, width: float, spec_name: str, theme: Theme) -> float:
    """How tall a text is in a box this wide at its spec's largest size in the theme (as _style fits it), with a
    little room to spare."""
    spec = SPECS[spec_name]
    font = theme.fonts.heading if spec.font == "heading" else theme.fonts.body
    bold = (theme.fonts.heading_bold if spec.heading else False) or spec.bold
    size = max(spec.smallest, round(spec.largest * theme.text_scale / fit.STEP) * fit.STEP)
    lines = fit.wrap(text, width, font, size, bold)
    return fit.text_height(len(lines), size) + 8


def _inset(box: Box, by: float) -> Box:
    return Box(x=box.x + by, y=box.y + by, w=box.w - 2 * by, h=box.h - 2 * by)


def _click(roles: dict[str, Content], role: str) -> int | None:
    """The click on which the slide's element of the role appears, if it doesn't from the start."""
    element = roles.get(role)
    return element.appears_on_click if isinstance(element, TextElement | ImageElement | ShapeElement) else None


def _numbered(roles: dict[str, Content], prefix: str, most: int) -> list[int]:
    """The numbers of the slide's elements of a kind that it has, such as its options (option_1, option_2...)."""
    return [number for number in range(1, most + 1) if f"{prefix}_{number}" in roles]


def _spread(top: float, bottom: float, count: int, gap: float, most: float) -> tuple[float, float]:
    """Where the first of a column of rows goes and how tall each is: as tall as fit between top and bottom (at most
    the most), with the gap between them, the column in the middle."""
    height = min(most, (bottom - top - gap * (count - 1)) / count)
    return top + (bottom - top - (height * count + gap * (count - 1))) / 2, height


def _left_aligned(theme: Theme) -> Theme:
    return theme.model_copy(update={"title_align": "left"})


def _big_number(roles: dict[str, Content], theme: Theme) -> Placement:
    """The number big in the middle, in the theme's accent, with what it counts under it and its source below."""
    placement = Placement("v5/big-number")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    bottom = _CONTENT_BOTTOM - (72 if "source" in roles else 0)
    number_height = round((bottom - top) * 0.58)
    width = WIDTH - 2 * MARGIN
    placement.boxes["number"] = (Box(x=MARGIN, y=top, w=width, h=number_height), "big number")
    label_top = top + number_height + 16
    placement.boxes["label"] = (Box(x=MARGIN + 120, y=label_top, w=width - 240, h=bottom - label_top), "number label")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=MARGIN, y=bottom + 16, w=width, h=56), "source")
    return placement


def _beside(placement: Placement, roles: dict[str, Content], theme: Theme, x: float, top: float) -> None:
    """The title (if any), what the number counts and its source, one under the other from x to the slide's right
    margin, the title with the theme's decoration."""
    width = WIDTH - MARGIN - x
    if "title" in roles:
        title = Box(x=x, y=top, w=width, h=260)
        placement.boxes["title"] = (title, "side title")
        placement.shapes += _decoration(_left_aligned(theme), title, gap=12)
        top += 300
    bottom = _CONTENT_BOTTOM - (80 if "source" in roles else 0)
    placement.boxes["label"] = (Box(x=x, y=top, w=width, h=bottom - top), "side label")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=x, y=bottom + 16, w=width, h=56), "side source")


def _big_number_panel(roles: dict[str, Content], theme: Theme) -> Placement:
    """The number on a panel in the theme's accent, along the slide's left side; the title, what the number counts
    and its source beside it."""
    accent = theme.palette.accent
    panel = ShapeElement(role="panel", box=Box(x=0, y=0, w=_PANEL_WIDTH, h=HEIGHT), color=accent)
    placement = Placement("v5/big-number-panel", shapes=[panel])
    placement.boxes["number"] = (Box(x=64, y=MARGIN, w=_PANEL_WIDTH - 128, h=HEIGHT - 2 * MARGIN), "panel number")
    placement.colors["number"] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    _beside(placement, roles, theme, _PANEL_WIDTH + 80, 120)
    return placement


def _big_number_disc(roles: dict[str, Content], theme: Theme) -> Placement:
    """The number on a big disc in the theme's accent, on the left, and what it counts beside it, under the title."""
    accent = theme.palette.accent
    placement = Placement("v5/big-number-disc")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    diameter = min(640.0, _CONTENT_BOTTOM - top - 40)
    disc = Box(x=MARGIN + 40, y=top + (_CONTENT_BOTTOM - top - diameter) / 2, w=diameter, h=diameter)
    placement.shapes.append(ShapeElement(role="disc", shape="ellipse", box=disc, color=accent))
    # (where the disc is widest, inside it)
    number = Box(x=disc.x + 0.08 * diameter, y=disc.y + 0.28 * diameter, w=0.84 * diameter, h=0.44 * diameter)
    placement.boxes["number"] = (number, "panel number")
    placement.colors["number"] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    x = disc.x + diameter + 80
    width = WIDTH - MARGIN - x
    bottom = _CONTENT_BOTTOM - (80 if "source" in roles else 0)
    placement.boxes["label"] = (Box(x=x, y=top + 40, w=width, h=bottom - top - 40), "side label")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=x, y=bottom + 16, w=width, h=56), "side source")
    return placement


def _figure_colours(placement: Placement, theme: Theme, index: int) -> None:
    """A figure's number in the theme's accent and its label in the theme's text colour, as each reads on its tile
    (in the theme's surface colour)."""
    palette = theme.palette
    placement.colors[f"number_{index}"] = color.readable_on(
        palette.accent, [palette.surface], color.LARGE_TEXT_CONTRAST
    )
    placement.colors[f"label_{index}"] = _on([palette.surface], theme)


def _tile(role: str, box: Box, theme: Theme, click: int | None, strip: Literal["top", "left"]) -> list[ShapeElement]:
    """A tile in the theme's surface colour, with a strip in its accent along its top or its left side."""
    palette = theme.palette
    edge = Box(x=box.x, y=box.y, w=box.w, h=14) if strip == "top" else Box(x=box.x, y=box.y, w=14, h=box.h)
    return [
        ShapeElement(role=role, box=box, color=palette.surface, appears_on_click=click),
        ShapeElement(role=f"{role} strip", box=edge, color=palette.accent, appears_on_click=click),
    ]


def _kpi_rows(roles: dict[str, Content], theme: Theme) -> Placement:
    """The figures one under the other, each on a band with an accent strip: the number on the left, what it
    measures beside it. (A figure that appears on a click comes with its band.)"""
    placement = Placement("v5/kpi-rows")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 8
    figures = _numbered(roles, "number", 4)
    y, height = _spread(top, _CONTENT_BOTTOM, len(figures), 20, 220)
    for index in figures:
        band = Box(x=MARGIN, y=y, w=WIDTH - 2 * MARGIN, h=height)
        placement.shapes += _tile(f"figure_{index}", band, theme, _click(roles, f"number_{index}"), "left")
        placement.boxes[f"number_{index}"] = (Box(x=MARGIN + 48, y=y + 12, w=520, h=height - 24), "row number")
        label = Box(x=MARGIN + 600, y=y + 12, w=WIDTH - 2 * MARGIN - 640, h=height - 24)
        placement.boxes[f"label_{index}"] = (label, "row label")
        _figure_colours(placement, theme, index)
        y += height + 20
    return placement


def _longest_number_word(roles: dict[str, Content], most: int) -> bool:
    """Whether every figure's number has no word longer than most characters (to fit a narrow tile)."""
    for index in _numbered(roles, "number", 4):
        element = roles[f"number_{index}"]
        if isinstance(element, TextElement) and any(len(word) > most for word in element.text.split()):
            return False
    return True


def _narrow_tiles_fit(roles: dict[str, Content]) -> bool:
    """Whether the figures' numbers fit tiles side by side: three always do, four if their numbers are short."""
    return len(_numbered(roles, "number", 4)) <= 3 or _longest_number_word(roles, 9)


def _four_short_figures(roles: dict[str, Content]) -> bool:
    return len(_numbered(roles, "number", 4)) == 4 and _longest_number_word(roles, 9)


def _kpi_tiles(roles: dict[str, Content], theme: Theme) -> Placement:
    """The figures side by side, each on a tile with an accent strip on top: the number, and what it measures
    under it."""
    placement = Placement("v5/kpi-tiles")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 24
    figures = _numbered(roles, "number", 4)
    gap = 40
    width = (WIDTH - 2 * MARGIN - gap * (len(figures) - 1)) / len(figures)
    height = min(560.0, _CONTENT_BOTTOM - top)
    y = top + (_CONTENT_BOTTOM - top - height) / 2
    number_height = round(height * 0.45)
    for position, index in enumerate(figures):
        x = MARGIN + position * (width + gap)
        tile = Box(x=x, y=y, w=width, h=height)
        placement.shapes += _tile(f"figure_{index}", tile, theme, _click(roles, f"number_{index}"), "top")
        placement.boxes[f"number_{index}"] = (Box(x=x + 28, y=y + 40, w=width - 56, h=number_height), "tile number")
        label_top = y + 40 + number_height + 20
        label = Box(x=x + 28, y=label_top, w=width - 56, h=y + height - 28 - label_top)
        placement.boxes[f"label_{index}"] = (label, "tile label")
        _figure_colours(placement, theme, index)
    return placement


def _kpi_grid(roles: dict[str, Content], theme: Theme) -> Placement:
    """Four figures on tiles in two rows of two, each with an accent strip on its left: the number on the left of
    its tile, what it measures on its right."""
    placement = Placement("v5/kpi-grid")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 24
    gap = 32
    width = (WIDTH - 2 * MARGIN - gap) / 2
    height = (_CONTENT_BOTTOM - top - gap) / 2
    for position, index in enumerate(_numbered(roles, "number", 4)):
        x = MARGIN + (position % 2) * (width + gap)
        y = top + (position // 2) * (height + gap)
        tile = Box(x=x, y=y, w=width, h=height)
        placement.shapes += _tile(f"figure_{index}", tile, theme, _click(roles, f"number_{index}"), "left")
        placement.boxes[f"number_{index}"] = (Box(x=x + 44, y=y + 24, w=360, h=height - 48), "row number")
        placement.boxes[f"label_{index}"] = (Box(x=x + 432, y=y + 24, w=width - 468, h=height - 48), "row label")
        _figure_colours(placement, theme, index)
    return placement


def _answer(roles: dict[str, Content]) -> int | None:
    """The number of a quiz's right option (1 for A), if its answer names one of its options."""
    answer = roles.get("answer")
    if not isinstance(answer, TextElement):
        return None
    index = "ABCD".find(answer.text.strip()[:1].upper()) + 1
    return index if index and f"option_{index}" in roles else None


def _highlight(theme: Theme) -> tuple[str, float]:
    """The colour and opacity of a band that marks a text, a quiz's right answer: the theme's second accent, as see-
    through as it takes for the theme's text to read on it (over every background), or else its surface colour."""
    palette = theme.palette
    for opacity in (0.4, 0.32, 0.25, 0.18):
        mixed = [color.mix(background, palette.accent_2, opacity) for background in _backgrounds(theme)]
        if color.worst_contrast(palette.text, mixed) >= color.BODY_CONTRAST:
            return palette.accent_2, opacity
    return palette.surface, 1.0


def _badge(placement: Placement, theme: Theme, role: str, badge: Box) -> None:
    """A short text (an option's letter, an item's number) on a badge, a disc in the theme's accent."""
    accent = theme.palette.accent
    placement.shapes.append(ShapeElement(role=f"{role} badge", shape="ellipse", box=badge, color=accent))
    placement.boxes[role] = (_inset(badge, badge.w * 0.16), "badge")
    placement.colors[role] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)


def _stamp(placement: Placement, roles: dict[str, Content], theme: Theme, disc: Box) -> None:
    """A quiz's answer, its letter on a disc in the theme's second accent, appearing with it."""
    accent = theme.palette.accent_2
    placement.shapes.append(
        ShapeElement(role="stamp", shape="ellipse", box=disc, color=accent, appears_on_click=_click(roles, "answer"))
    )
    placement.boxes["answer"] = (_inset(disc, disc.w * 0.2), "stamp")
    placement.colors["answer"] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)


def _quiz_list(roles: dict[str, Content], theme: Theme) -> Placement:
    """The question as the title, and the options one under the other, each with its letter on a badge. With the
    answer (on a click): a band behind the right option, its letter on a stamp beside the options, and the
    explanation under them."""
    placement = Placement("v5/quiz-list")
    top = _with_title(placement, roles, theme) + 16
    bottom = _EXPLANATION.y - 24 if "explanation" in roles else _CONTENT_BOTTOM
    options = _numbered(roles, "option", 4)
    y, height = _spread(top, bottom, len(options), 20, 150)
    right = _answer(roles)
    end = WIDTH - MARGIN - _STAMP - 80  # (where the options end: the stamp goes beside them)
    for index in options:
        if index == right:
            colour, opacity = _highlight(theme)
            band = Box(x=MARGIN - 16, y=y - 6, w=end - MARGIN + 32, h=height + 12)
            placement.shapes.append(
                ShapeElement(
                    role="right answer",
                    box=band,
                    color=colour,
                    opacity=opacity,
                    appears_on_click=_click(roles, "answer"),
                )
            )
        diameter = height - 24
        _badge(placement, theme, f"letter_{index}", Box(x=MARGIN, y=y + 12, w=diameter, h=diameter))
        x = MARGIN + diameter + 36
        placement.boxes[f"option_{index}"] = (Box(x=x, y=y, w=end - x, h=height), "option")
        y += height + 20
    if right is not None:
        middle = (top + bottom) / 2
        _stamp(placement, roles, theme, Box(x=WIDTH - MARGIN - _STAMP, y=middle - _STAMP / 2, w=_STAMP, h=_STAMP))
    if "explanation" in roles:
        placement.boxes["explanation"] = (_EXPLANATION, "explanation")
    return placement


def _quiz_tiles(roles: dict[str, Content], theme: Theme) -> Placement:
    """The question as the title, and four options on tiles in two rows of two, each with its letter on a badge.
    With the answer (on a click): a frame in the theme's second accent around the right option, the answer's letter
    on a stamp at its corner, and the explanation under them."""
    palette = theme.palette
    placement = Placement("v5/quiz-tiles")
    top = _with_title(placement, roles, theme) + 28
    bottom = _EXPLANATION.y - 28 if "explanation" in roles else _CONTENT_BOTTOM
    gap_across, gap_down = 48, 40
    width = (WIDTH - 2 * MARGIN - gap_across) / 2
    height = (bottom - top - gap_down) / 2
    right = _answer(roles)
    click = _click(roles, "answer")
    on_tile = _on([palette.surface], theme)
    stamp = None
    for position, index in enumerate(_numbered(roles, "option", 4)):
        x = MARGIN + (position % 2) * (width + gap_across)
        y = top + (position // 2) * (height + gap_down)
        if index == right:  # (a frame: a bigger tile behind the right one)
            frame = Box(x=x - 12, y=y - 12, w=width + 24, h=height + 24)
            placement.shapes.append(
                ShapeElement(role="right answer", box=frame, color=palette.accent_2, appears_on_click=click)
            )
            stamp = Box(x=x + width - 84, y=y - 44, w=120, h=120)  # (on its top right corner)
        placement.shapes.append(
            ShapeElement(role=f"tile_{index}", box=Box(x=x, y=y, w=width, h=height), color=palette.surface)
        )
        diameter = min(112.0, height - 56)
        badge = Box(x=x + 28, y=y + (height - diameter) / 2, w=diameter, h=diameter)
        _badge(placement, theme, f"letter_{index}", badge)
        option = Box(x=x + diameter + 56, y=y + 16, w=width - diameter - 56 - 96, h=height - 32)
        placement.boxes[f"option_{index}"] = (option, "tile option")
        placement.colors[f"option_{index}"] = on_tile
    if stamp is not None:
        _stamp(placement, roles, theme, stamp)
    if "explanation" in roles:
        placement.boxes["explanation"] = (_EXPLANATION, "explanation")
    return placement


def _post(photo_left: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """A social media post on a card in the theme's surface colour: its author's initials on an avatar, their name
    and handle, the post, and how often it was liked and shared; its photo beside it, on the card's right (or on its
    left), when it has one. Without a photo, the card is narrower and the post bigger."""

    def post(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/post-photo-left" if photo_left else "v5/post")
        top = _with_title(placement, roles, theme) if "title" in roles else 72
        photo = "photo" in roles
        width = WIDTH - 2 * MARGIN if photo else 1240.0
        height = _CONTENT_BOTTOM - top
        if not photo:  # (a card as tall as it takes for its text, at the text's largest size, in the middle)
            post = roles.get("text")
            needed = _text_height(
                post.text if isinstance(post, TextElement) else "", width - 2 * _CARD_PADDING, "big post text", theme
            )
            height = min(height, 2 * _CARD_PADDING + _AVATAR + 32 + needed + 24 + 44)
            top += (_CONTENT_BOTTOM - top - height) / 2
        card = Box(x=(WIDTH - width) / 2, y=top, w=width, h=height)
        edge = color.mix(palette.surface, palette.text, 0.25)
        placement.shapes += [
            ShapeElement(role="card edge", box=_inset(card, -3), color=edge),
            ShapeElement(role="card", box=card, color=palette.surface),
        ]
        padding = _CARD_PADDING
        x, text_width = card.x + padding, card.w - 2 * padding
        if photo:
            photo_x = card.x + padding if photo_left else card.x + card.w - padding - _POST_PHOTO_WIDTH
            placement.boxes["photo"] = (
                Box(x=photo_x, y=card.y + padding, w=_POST_PHOTO_WIDTH, h=card.h - 2 * padding),
                "quote",
            )
            text_width -= _POST_PHOTO_WIDTH + 48
            if photo_left:
                x = photo_x + _POST_PHOTO_WIDTH + 48
        avatar = Box(x=x, y=card.y + padding, w=_AVATAR, h=_AVATAR)
        placement.shapes.append(ShapeElement(role="avatar", shape="ellipse", box=avatar, color=palette.accent))
        placement.boxes["initials"] = (_inset(avatar, 16), "badge")
        placement.colors["initials"] = _on([palette.accent], theme, color.LARGE_TEXT_CONTRAST)
        name_x = x + _AVATAR + 28
        placement.boxes["author"] = (Box(x=name_x, y=avatar.y, w=x + text_width - name_x, h=56), "post author")
        placement.boxes["handle"] = (Box(x=name_x, y=avatar.y + 58, w=x + text_width - name_x, h=46), "post handle")
        stats_top = card.y + card.h - padding - 44
        placement.boxes["stats"] = (Box(x=x, y=stats_top, w=text_width, h=44), "post stats")
        text_top = avatar.y + _AVATAR + 32
        text = Box(x=x, y=text_top, w=text_width, h=stats_top - 24 - text_top)
        placement.boxes["text"] = (text, "post text" if photo else "big post text")
        ink = _on([palette.surface], theme)
        faint = color.readable_on(palette.muted, [palette.surface])
        placement.colors.update(author=ink, text=ink, handle=faint, stats=faint)
        return placement

    return post


def _band(theme: Theme, box: Box, role: str, over_photo: bool) -> tuple[ShapeElement, str]:
    """A band in the theme's surface colour (see-through over a photo, if a colour reads on it that way, else
    solid), and the colour of a text on it."""
    surface = theme.palette.surface
    if over_photo:
        mixed = [color.mix(extreme, surface, BAND_OPACITY) for extreme in ("#000000", "#ffffff")]
        colour = _on(mixed, theme)
        if color.worst_contrast(colour, mixed) >= color.BODY_CONTRAST:
            return ShapeElement(role=role, box=box, color=surface, opacity=BAND_OPACITY), colour
    return ShapeElement(role=role, box=box, color=surface), _on([surface], theme)


def _news_tv(roles: dict[str, Content], theme: Theme) -> Placement:
    """The photo over the whole slide, as on television: the breaking news on a band in the theme's second accent,
    the headline on a band across the lower third, the subheadline on a ticker under it, and the outlet's name in
    the top right corner."""
    palette = theme.palette
    placement = Placement("v5/news-tv", photo=True)
    placement.boxes["photo"] = (FULL, "quote")
    kicker = Box(x=0, y=596, w=640, h=76)
    placement.overlays.append(ShapeElement(role="kicker band", box=kicker, color=palette.accent_2))
    placement.boxes["kicker"] = (Box(x=MARGIN, y=kicker.y + 12, w=kicker.w - MARGIN - 32, h=kicker.h - 24), "kicker")
    placement.colors["kicker"] = _on([palette.accent_2], theme)
    band, ink = _band(theme, Box(x=0, y=672, w=WIDTH, h=180), "headline band", over_photo=True)
    placement.overlays.append(band)
    placement.boxes["headline"] = (
        Box(x=MARGIN, y=band.box.y + 14, w=WIDTH - 2 * MARGIN, h=band.box.h - 28),
        "tv headline",
    )
    placement.colors["headline"] = ink
    if "subheadline" in roles:
        ticker = Box(x=0, y=852, w=WIDTH, h=88)
        placement.overlays.append(ShapeElement(role="ticker", box=ticker, color=palette.text))
        placement.boxes["subheadline"] = (
            Box(x=MARGIN, y=ticker.y + 12, w=WIDTH - 2 * MARGIN, h=ticker.h - 24),
            "ticker",
        )
        placement.colors["subheadline"] = _on([palette.text], theme)
    corner, ink = _band(theme, Box(x=WIDTH - MARGIN - 440, y=56, w=440, h=100), "outlet band", over_photo=True)
    placement.overlays.append(corner)
    placement.boxes["outlet"] = (_inset(corner.box, 12), "outlet")
    placement.colors["outlet"] = ink
    return placement


def _newspaper(roles: dict[str, Content], theme: Theme) -> Placement:
    """A newspaper's front page, on a page in the theme's surface colour: the outlet's name as its masthead over a
    double rule, the headline, and the photo with the subheadline beside it, past a rule."""
    palette = theme.palette
    page = Box(x=MARGIN, y=40, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - 40)
    ink = _on([palette.surface], theme)
    x, width = page.x + 48, page.w - 96
    placement = Placement("v5/newspaper", shapes=[ShapeElement(role="page", box=page, color=palette.surface)])
    placement.boxes["outlet"] = (Box(x=x, y=60, w=width, h=124), "masthead")
    placement.shapes += [
        ShapeElement(role="rule", box=Box(x=x, y=196, w=width, h=6), color=ink),
        ShapeElement(role="rule", box=Box(x=x, y=210, w=width, h=2), color=ink),
    ]
    placement.boxes["headline"] = (Box(x=x, y=228, w=width, h=232), "headline")
    top, bottom = 480, page.y + page.h - 32
    if "subheadline" in roles:
        photo_width = 1000.0
        placement.shapes.append(
            ShapeElement(role="rule", box=Box(x=x + photo_width + 27, y=top, w=2, h=bottom - top), color=ink)
        )
        column = x + photo_width + 56
        placement.boxes["subheadline"] = (Box(x=column, y=top, w=x + width - column, h=bottom - top), "subheadline")
    else:
        photo_width = width
    placement.boxes["photo"] = (Box(x=x, y=top, w=photo_width, h=bottom - top), "quote")
    placement.colors.update(outlet=ink, headline=ink, subheadline=ink)
    return placement


def _agenda(roles: dict[str, Content], theme: Theme) -> Placement:
    """The items one under the other, each numbered on a badge in the theme's accent."""
    placement = Placement("v5/agenda")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 16
    _agenda_rows(placement, roles, theme, MARGIN, top)
    return placement


def _agenda_rows(placement: Placement, roles: dict[str, Content], theme: Theme, x: float, top: float) -> None:
    items = _numbered(roles, "item", 5)
    y, height = _spread(top, _CONTENT_BOTTOM, len(items), 16, 140)
    for index in items:
        diameter = height - 24
        _badge(placement, theme, f"number_{index}", Box(x=x, y=y + 12, w=diameter, h=diameter))
        item_x = x + diameter + 40
        placement.boxes[f"item_{index}"] = (Box(x=item_x, y=y, w=WIDTH - MARGIN - item_x, h=height), "item")
        y += height + 16


def _agenda_steps(roles: dict[str, Content], theme: Theme) -> Placement:
    """The items side by side, as steps along a line in the theme's accent: each numbered on a badge on the line,
    with the item under it."""
    accent = theme.palette.accent
    placement = Placement("v5/agenda-steps")
    items = _numbered(roles, "item", 5)
    gap, diameter, item_height = 24, 120, 320.0
    start = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    top = start + (_CONTENT_BOTTOM - start - (diameter + 40 + item_height)) / 2
    width = (WIDTH - 2 * MARGIN - gap * (len(items) - 1)) / len(items)
    middle = top + diameter / 2
    first, last = MARGIN + width / 2, WIDTH - MARGIN - width / 2
    placement.shapes.append(
        ShapeElement(role="line", box=Box(x=first, y=middle - 3, w=last - first, h=6), color=accent)
    )
    for position, index in enumerate(items):
        x = MARGIN + position * (width + gap)
        _badge(placement, theme, f"number_{index}", Box(x=x + (width - diameter) / 2, y=top, w=diameter, h=diameter))
        placement.boxes[f"item_{index}"] = (Box(x=x, y=top + diameter + 40, w=width, h=item_height), "step")
    return placement


def _agenda_side(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title on the left, with the theme's decoration, and the numbered items beside it."""
    placement = Placement("v5/agenda-side")
    title = Box(x=MARGIN, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
    placement.boxes["title"] = (title, "side title")
    placement.shapes += _decoration(_left_aligned(theme), title, gap=12)
    _agenda_rows(placement, roles, theme, MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP, MARGIN)
    return placement


def _section(roles: dict[str, Content], theme: Theme) -> Placement:
    """The section's number big in the theme's accent, its title under it with the theme's decoration, and its
    subtitle: all aligned as the theme aligns its titles."""
    placement = Placement("v5/section")
    placement.boxes["kicker"] = (Box(x=160, y=120, w=1600, h=300), "section number")
    title = Box(x=160, y=440, w=1600, h=300)
    placement.boxes["title"] = (title, "section title")
    placement.shapes += _decoration(theme, title, gap=14)
    placement.boxes["subtitle"] = (Box(x=160, y=790, w=1600, h=150), "subtitle")
    return placement


def _section_panel(roles: dict[str, Content], theme: Theme) -> Placement:
    """The section's number on a panel in the theme's accent, along the slide's left side; its title and subtitle
    beside it."""
    accent = theme.palette.accent
    panel = ShapeElement(role="panel", box=Box(x=0, y=0, w=_PANEL_WIDTH, h=HEIGHT), color=accent)
    placement = Placement("v5/section-panel", shapes=[panel])
    placement.boxes["kicker"] = (Box(x=64, y=200, w=_PANEL_WIDTH - 128, h=680), "panel number")
    placement.colors["kicker"] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    x = _PANEL_WIDTH + 80
    title = Box(x=x, y=200, w=WIDTH - MARGIN - x, h=460)
    placement.boxes["title"] = (title, "section side title")
    placement.shapes += _decoration(_left_aligned(theme), title, gap=16)
    placement.boxes["subtitle"] = (Box(x=x, y=700, w=WIDTH - MARGIN - x, h=220), "left subtitle")
    return placement


def _questions(roles: dict[str, Content], theme: Theme) -> Placement:
    """The question big in the middle, with the theme's decoration under it, and the subtitle below."""
    placement = Placement("v5/questions")
    title = Box(x=160, y=200, w=1600, h=460)
    placement.boxes["title"] = (title, "questions")
    placement.shapes += _decoration(theme.model_copy(update={"title_align": "center"}), title, gap=16)
    placement.boxes["subtitle"] = (Box(x=160, y=720, w=1600, h=200), "centred subtitle")
    return placement


def _questions_mark(roles: dict[str, Content], theme: Theme) -> Placement:
    """The question and its subtitle on the left, and a huge question mark in the theme's accent on the right."""
    placement = Placement("v5/questions-mark")
    placement.boxes["mark"] = (Box(x=1080, y=40, w=760, h=940), "mark")
    title = Box(x=MARGIN, y=200, w=960, h=440)
    placement.boxes["title"] = (title, "left title")
    placement.shapes += _decoration(_left_aligned(theme), title, gap=16)
    placement.boxes["subtitle"] = (Box(x=MARGIN, y=690, w=960, h=220), "left subtitle")
    return placement


# Native diagrams: a timeline, a pyramid and a funnel, a cycle, a small org chart and an iceberg


def _dot(
    role: str, centre: tuple[float, float], diameter: float, colour: str, click: int | None = None
) -> ShapeElement:
    x, y = centre
    box = Box(x=x - diameter / 2, y=y - diameter / 2, w=diameter, h=diameter)
    return ShapeElement(role=role, shape="ellipse", box=box, color=colour, appears_on_click=click)


def _timeline(roles: dict[str, Content], theme: Theme) -> Placement:
    """The moments side by side along a line in the theme's accent, oldest first: a dot on the line for each (the
    punchline's in the second accent, appearing with it), its date above it and what happened under it."""
    palette = theme.palette
    placement = Placement("v5/timeline")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    moments = _numbered(roles, "event", 5)
    gap = 32
    width = (WIDTH - 2 * MARGIN - gap * (len(moments) - 1)) / len(moments)
    line = top + 260
    first, last = MARGIN + width / 2, WIDTH - MARGIN - width / 2
    placement.shapes.append(
        ShapeElement(role="line", box=Box(x=first, y=line - 4, w=last - first, h=8), color=palette.accent)
    )
    for position, index in enumerate(moments):
        x = MARGIN + position * (width + gap)
        click = _click(roles, f"event_{index}")
        colour = palette.accent_2 if click else palette.accent
        placement.shapes.append(_dot(f"dot_{index}", (x + width / 2, line), 48, colour, click))
        placement.boxes[f"date_{index}"] = (Box(x=x, y=top + 40, w=width, h=line - 48 - top - 40), "date")
        placement.boxes[f"event_{index}"] = (Box(x=x, y=line + 48, w=width, h=_CONTENT_BOTTOM - line - 48), "step")
    return placement


def _timeline_down(roles: dict[str, Content], theme: Theme) -> Placement:
    """The moments one under the other along a line in the theme's accent, oldest first: each date on the line's
    left, a dot on the line, and what happened on its right."""
    palette = theme.palette
    placement = Placement("v5/timeline-down")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 16
    moments = _numbered(roles, "event", 5)
    gap = 12
    y, height = _spread(top, _CONTENT_BOTTOM, len(moments), gap, 150)
    line = MARGIN + 370
    first, last = y + height / 2, y + (len(moments) - 1) * (height + gap) + height / 2
    placement.shapes.append(
        ShapeElement(role="line", box=Box(x=line - 4, y=first, w=8, h=last - first), color=palette.accent)
    )
    for index in moments:
        click = _click(roles, f"event_{index}")
        colour = palette.accent_2 if click else palette.accent
        placement.shapes.append(_dot(f"dot_{index}", (line, y + height / 2), 44, colour, click))
        placement.boxes[f"date_{index}"] = (Box(x=MARGIN, y=y, w=330, h=height), "row date")
        placement.boxes[f"event_{index}"] = (Box(x=line + 56, y=y, w=WIDTH - MARGIN - line - 56, h=height), "item")
        y += height + gap
    return placement


def _area(placement: Placement, roles: dict[str, Content], theme: Theme, side: bool) -> tuple[float, float, float]:
    """Where a diagram goes, from its left to its right and from its top down: under the title (across the slide), or
    beside it (the title on the left, with the theme's decoration)."""
    if side:
        title = Box(x=MARGIN, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
        placement.boxes["title"] = (title, "side title")
        placement.shapes += _decoration(_left_aligned(theme), title, gap=12)
        return MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP, WIDTH - MARGIN, MARGIN
    return MARGIN, WIDTH - MARGIN, _with_title(placement, roles, theme) if "title" in roles else MARGIN


def _stack(
    name: str, prefix: str, most: int, widening: bool, side: bool = False
) -> Callable[[dict[str, Content], Theme], Placement]:
    """Bands one under the other, in the middle, each with its text: wider and wider going down (a pyramid), or
    narrower and narrower (a funnel). In the theme's accent, a little lighter or darker with every band, and the
    punchline's in its second accent, appearing with it."""

    def stack(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement(name)
        left, right, top = _area(placement, roles, theme, side)
        items = _numbered(roles, prefix, most)
        gap = 12
        y, height = _spread(top + 24, _CONTENT_BOTTOM, len(items), gap, 170)
        widest = min(1500.0, right - left)
        narrowest = 460.0  # (wide enough for a long word at the top of a pyramid, or at the bottom of a funnel)
        for position, index in enumerate(items):
            share = position / max(1, len(items) - 1)  # (from 0 at the top to 1 at the bottom)
            width = narrowest + (widest - narrowest) * (share if widening else 1 - share)
            click = _click(roles, f"{prefix}_{index}")
            fill = palette.accent_2 if click else color.mix(palette.accent, palette.background, 0.2 * share)
            band = Box(x=(left + right - width) / 2, y=y, w=width, h=height)
            placement.shapes.append(
                ShapeElement(role=f"{prefix} {index} band", box=band, color=fill, appears_on_click=click)
            )
            placement.boxes[f"{prefix}_{index}"] = (Box(x=band.x + 24, y=y + 8, w=width - 48, h=height - 16), "level")
            placement.colors[f"{prefix}_{index}"] = _on([fill], theme)
            y += height + gap
        return placement

    return stack


def _cycle(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """The steps on ovals in the theme's accent around a ring of dots, clockwise from the top: each leads to the next,
    and the last back to the first. (Ovals, wide enough for a long word, on an oval ring as wide as there's room.)"""

    def cycle(roles: dict[str, Content], theme: Theme) -> Placement:
        accent = theme.palette.accent
        placement = Placement("v5/cycle-side" if side else "v5/cycle")
        left, right, top = _area(placement, roles, theme, side)
        steps = _numbered(roles, "step", 5)
        middle = ((left + right) / 2, (top + _CONTENT_BOTTOM) / 2)
        width, height = 440.0, 200.0
        across = (right - left) / 2 - width / 2 - 8  # (the ring's radii)
        down = (_CONTENT_BOTTOM - top) / 2 - height / 2 - 8

        def on_ring(angle: float) -> tuple[float, float]:  # (from the top, clockwise)
            return middle[0] + across * math.sin(angle), middle[1] - down * math.cos(angle)

        for step in range(48):  # (the ring, under the ovals)
            placement.shapes.append(_dot("ring", on_ring(2 * math.pi * step / 48), 16, accent))
        for position, index in enumerate(steps):
            x, y = on_ring(2 * math.pi * position / len(steps))
            oval = Box(x=x - width / 2, y=y - height / 2, w=width, h=height)
            placement.shapes.append(ShapeElement(role=f"step {index} oval", shape="ellipse", box=oval, color=accent))
            text = Box(x=x - 0.4 * width, y=y - 0.27 * height, w=0.8 * width, h=0.54 * height)
            placement.boxes[f"step_{index}"] = (text, "disc")
            placement.colors[f"step_{index}"] = _on([accent], theme)
        return placement

    return cycle


def _org_chart(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """Who's in charge, on a box in the theme's accent at the top (appearing with them), joined by lines to the
    people under them, on boxes in its surface colour."""

    def org_chart(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/org-chart-side" if side else "v5/org-chart")
        left, right, top = _area(placement, roles, theme, side)
        reports = _numbered(roles, "report", 4)
        box_height, drop = 170.0, 70.0
        y = top + 24 + (_CONTENT_BOTTOM - top - 24 - (2 * box_height + 2 * drop)) / 2
        centre = (left + right) / 2
        boss = Box(x=centre - 300, y=y, w=600, h=box_height)
        gap = 24.0 if side else 48.0  # (beside a title, the boxes need all the room there is)
        inset = 12.0 if side else 20.0
        width = min(420.0, (right - left - gap * (len(reports) - 1)) / len(reports))
        total = width * len(reports) + gap * (len(reports) - 1)
        first = centre - total / 2
        joint, row = boss.y + boss.h + drop, boss.y + boss.h + 2 * drop
        ink = color.readable_on(palette.muted, _backgrounds(theme), LINE_CONTRAST)
        placement.shapes += [
            ShapeElement(role="line", box=Box(x=centre - 3, y=boss.y + boss.h, w=6, h=drop + 3), color=ink),
            ShapeElement(
                role="line", box=Box(x=first + width / 2 - 3, y=joint - 3, w=total - width + 6, h=6), color=ink
            ),
        ]
        for position, index in enumerate(reports):
            x = first + position * (width + gap)
            placement.shapes.append(
                ShapeElement(role="line", box=Box(x=x + width / 2 - 3, y=joint, w=6, h=drop), color=ink)
            )
            report = Box(x=x, y=row, w=width, h=box_height)
            placement.shapes.append(ShapeElement(role=f"report {index} box", box=report, color=palette.surface))
            placement.boxes[f"report_{index}"] = (_inset(report, inset), "box")
            placement.colors[f"report_{index}"] = _on([palette.surface], theme)
        click = _click(roles, "boss")
        placement.shapes.append(ShapeElement(role="boss box", box=boss, color=palette.accent, appears_on_click=click))
        placement.boxes["boss"] = (_inset(boss, 20), "boss")
        placement.colors["boss"] = _on([palette.accent], theme, color.LARGE_TEXT_CONTRAST)
        return placement

    return org_chart


def _iceberg(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """An iceberg in the theme's surface colour, outlined in its accent and mostly under water (the accent, see-
    through): what everyone sees on its tip, above the water, and what's under it, below (appearing on a click)."""

    def iceberg(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/iceberg-side" if side else "v5/iceberg")
        left, right, top = _area(placement, roles, theme, side)
        centre = (left + right) / 2
        water = top + 300
        width = min(1100.0, right - left - 40)
        ice = Box(x=centre - width / 2, y=water - 280, w=width, h=1500)  # (an ellipse, its tip above the water)
        opacity = 0.35
        edge = color.readable_on(palette.accent, _backgrounds(theme), LINE_CONTRAST)
        shore = left - 24 if side else 0.0  # (the water stays clear of a title beside it)
        sea = Box(x=shore, y=water, w=WIDTH - shore, h=HEIGHT - water)
        placement.shapes += [
            ShapeElement(role="ice edge", shape="ellipse", box=_inset(ice, -8), color=edge),
            ShapeElement(role="ice", shape="ellipse", box=ice, color=palette.surface),
            ShapeElement(role="water", box=sea, color=palette.accent, opacity=opacity),
        ]
        placement.boxes["tip"] = (Box(x=centre - 240, y=water - 200, w=480, h=160), "box")
        placement.colors["tip"] = _on([palette.surface], theme)
        hidden = _numbered(roles, "hidden", 3)
        y, height = _spread(water + 48, _CONTENT_BOTTOM, len(hidden), 16, 130)
        under = color.mix(palette.surface, palette.accent, opacity)
        label = min(720.0, 0.66 * width)
        for index in hidden:
            placement.boxes[f"hidden_{index}"] = (Box(x=centre - label / 2, y=y, w=label, h=height), "box")
            placement.colors[f"hidden_{index}"] = _on([under], theme)
            y += height + 16
        return placement

    return iceberg


# A MEME: a template's picture as large as fits, with its captions in its boxes (see talkgenerator.sources.memes)

_MEME_AREA: Final = Box(x=MARGIN, y=_CONTENT_BOTTOM - memes.AREA[1], w=memes.AREA[0], h=memes.AREA[1])
# The boxes of a picture whose boxes talkgenerator doesn't know (one a plan brought): at its top, and at its bottom
_TOP_AND_BOTTOM: Final = (
    memes.CaptionBox(0.03, 0.02, 0.94, 0.2, "impact", ""),
    memes.CaptionBox(0.03, 0.78, 0.94, 0.2, "impact", ""),
)


def _meme(roles: dict[str, Content], theme: Theme) -> Placement:
    """The template's picture as large as fits the slide, shown as it is (no theme treats it: its captions go in
    place on it), each caption in its box: white Impact with a black outline, or plain black text on the template's
    own even area, which a label in its colour keeps even under the text."""
    placement = Placement("v5/meme", untreated={"template"})
    picture = roles.get("template")
    template = (
        memes.of_picture(picture.image.url, picture.image.source_url) if isinstance(picture, ImageElement) else None
    )
    if template is not None:
        width, height, boxes = float(template.width), float(template.height), template.boxes
    else:
        size = (picture.image.width, picture.image.height) if isinstance(picture, ImageElement) else (None, None)
        width, height, boxes = float(size[0] or 4), float(size[1] or 3), _TOP_AND_BOTTOM
    area = _MEME_AREA
    scale = min(area.w / width, area.h / height)
    shown = Box(
        x=area.x + (area.w - width * scale) / 2,
        y=area.y + (area.h - height * scale) / 2,
        w=width * scale,
        h=height * scale,
    )
    placement.boxes["template"] = (shown, "quote")
    for number, box in enumerate(boxes, 1):
        role, caption = f"text_{number}", roles.get(f"text_{number}")
        if not isinstance(caption, TextElement):
            continue
        spec, padding = ("plain meme", 6.0) if box.style == "plain" else ("meme", 4.0)
        place = Box(x=shown.x + box.x * shown.w, y=shown.y + box.y * shown.h, w=box.w * shown.w, h=box.h * shown.h)
        place = _room_for(caption.text, place, spec, padding, shown)
        if box.style == "plain":
            fill = box.fill or "#ffffff"
            placement.overlays.append(ShapeElement(role=f"{role} label", box=place, color=fill))
            placement.colors[role] = color.readable_on("#000000", [fill])
        placement.boxes[role] = (_inset(place, padding), spec)
    return placement


def _room_for(text: str, box: Box, spec_name: str, padding: float, bounds: Box) -> Box:
    """A caption's box, grown around its middle (within the picture) where the caption doesn't fit it at its smallest
    size: as wide as its widest word, and then as tall as its lines (a narrow box, such as a sign's, and a long word)."""
    spec = SPECS[spec_name]
    font = spec.font_name or "Arial"
    shown = text.upper() if spec.uppercase else text
    widest = max((fonts.text_width(word, font, spec.smallest, spec.bold) for word in shown.split()), default=0.0)
    width = min(bounds.w, max(box.w, widest + 2 * padding + 4))
    fitted = fit.fit(shown, width - 2 * padding, box.h - 2 * padding, font, spec.smallest, spec.smallest, spec.bold)
    height = (
        box.h if fitted.fits else min(bounds.h, fit.text_height(len(fitted.lines), spec.smallest) + 2 * padding + 8)
    )
    x = min(max(box.x + (box.w - width) / 2, bounds.x), bounds.x + bounds.w - width)
    y = min(max(box.y + (box.h - height) / 2, bounds.y), bounds.y + bounds.h - height)
    return Box(x=x, y=y, w=width, h=height) if (width, height) != (box.w, box.h) else box


# THE FAMILIES' OWN LAYOUTS: title and section slides that set a family apart (its decoration, which
# talkgenerator.design.motifs draws, goes around them: a kindergarten's bunting and hills, a sunset)

_SUN: Final = ("#ffd23f", "#ffbf00")  # a crayon sun's rays and disc


def _kids_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """The talk's title and subtitle on a white card in the middle (its motif puts bunting over it, a sun and a cloud
    beside it and hills under it)."""
    placement = Placement("v5/kids-title")
    placement.boxes["title"] = (Box(x=330, y=300, w=1260, h=290), "kids title")
    placement.boxes["subtitle"] = (Box(x=330, y=610, w=1260, h=100), "centred subtitle")
    return placement


def _kids_section(roles: dict[str, Content], theme: Theme) -> Placement:
    """The section's number on a big crayon sun on the left, its title and subtitle beside it."""
    placement = Placement("v5/kids-section")
    sun = Box(x=120, y=230, w=620, h=620)
    disc = _inset(sun, sun.w * 0.19)
    placement.shapes += [
        ShapeElement(role="sun rays", shape="polygon", points=geometry.burst(12, 0.62), box=sun, color=_SUN[0]),
        ShapeElement(role="sun", shape="ellipse", box=disc, color=_SUN[1]),
    ]
    placement.boxes["kicker"] = (_inset(disc, disc.w * 0.16), "panel number")
    placement.colors["kicker"] = _on([_SUN[1]], theme, color.LARGE_TEXT_CONTRAST)
    x = sun.x + sun.w + 60
    placement.boxes["title"] = (Box(x=x, y=300, w=WIDTH - MARGIN - x, h=330), "section side title")
    placement.boxes["subtitle"] = (Box(x=x, y=660, w=WIDTH - MARGIN - x, h=180), "left subtitle")
    return placement


def _neon_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title and subtitle high on the slide, leaving its lower part to a sunset over a grid (its motif's)."""
    placement = Placement("v5/neon-title")
    title = Box(x=160, y=100, w=1600, h=330)
    placement.boxes["title"] = (title, "talk title")
    placement.boxes["subtitle"] = (Box(x=160, y=450, w=1600, h=110), "subtitle")
    placement.shapes += _decoration(theme, title, gap=12)
    return placement


def _neon_section(roles: dict[str, Content], theme: Theme) -> Placement:
    """The section's number, title and subtitle high on the slide, with room for the sunset under them."""
    placement = Placement("v5/neon-section")
    placement.boxes["kicker"] = (Box(x=160, y=90, w=1600, h=230), "section number")
    placement.boxes["title"] = (Box(x=160, y=330, w=1600, h=200), "section title")
    placement.boxes["subtitle"] = (Box(x=160, y=540, w=1600, h=90), "subtitle")
    return placement


def _swiss_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """A Swiss poster's: the subtitle small under the rule, a big circle in the second accent at the top right, off
    the slide's edge, and the title huge, flush left, at the bottom left."""
    placement = Placement("v5/swiss-title")
    circle = Box(x=1260, y=-130, w=760, h=760)
    placement.shapes.append(ShapeElement(role="circle", shape="ellipse", box=circle, color=theme.palette.accent_2))
    placement.boxes["subtitle"] = (Box(x=MARGIN, y=84, w=1080, h=110), "left subtitle")
    placement.boxes["title"] = (Box(x=MARGIN, y=560, w=1240, h=420), "swiss title")
    return placement


def _swiss_section(roles: dict[str, Content], theme: Theme) -> Placement:
    """A Swiss poster's divider: the slide in its ink, the section's number giant at the bottom left, one bar in its
    second accent over it, and its title and subtitle at the right, in the paper's colour."""
    palette = theme.palette
    ink = palette.text
    placement = Placement("v5/swiss-section", shapes=[ShapeElement(role="panel", box=FULL, color=ink)])
    placement.shapes.append(ShapeElement(role="bar", box=Box(x=MARGIN, y=200, w=420, h=48), color=palette.accent_2))
    placement.boxes["kicker"] = (Box(x=MARGIN, y=300, w=900, h=680), "swiss number")
    placement.boxes["title"] = (Box(x=1060, y=520, w=764, h=320), "section side title")
    placement.boxes["subtitle"] = (Box(x=1060, y=860, w=764, h=120), "left subtitle")
    on_ink = _on([ink], theme)
    placement.colors.update(kicker=on_ink, title=on_ink, subtitle=on_ink)
    placement.on_fill.update({"kicker", "title"})
    return placement


def _newspaper_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """A front page: the talk's title as the masthead between a heavy rule and a thin one, the subtitle as its
    byline, and three columns of type under them (grey lines, as a page seen from afar) with rules between them."""
    palette = theme.palette
    placement = Placement("v5/newspaper-title")
    placement.boxes["title"] = (Box(x=MARGIN, y=84, w=WIDTH - 2 * MARGIN, h=330), "masthead title")
    width = WIDTH - 2 * MARGIN
    placement.shapes += [
        ShapeElement(role="rule", box=Box(x=MARGIN, y=432, w=width, h=7), color=palette.text),
        ShapeElement(role="rule", box=Box(x=MARGIN, y=446, w=width, h=2), color=palette.text),
    ]
    placement.boxes["subtitle"] = (Box(x=MARGIN, y=466, w=width, h=80), "byline")
    placement.shapes.append(ShapeElement(role="rule", box=Box(x=MARGIN, y=560, w=width, h=2), color=palette.text))
    grey = color.mix(palette.background, palette.text, 0.22)
    gap = 56
    column = (width - 2 * gap) / 3
    for index in range(3):
        x = MARGIN + index * (column + gap)
        if index:
            placement.shapes.append(
                ShapeElement(role="rule", box=Box(x=x - gap / 2, y=596, w=1.5, h=380), color=palette.text)
            )
        for row in range(16):
            length = column if (row + index) % 7 != 6 else column * 0.55
            y = 600 + row * 23
            placement.shapes.append(ShapeElement(role="type", box=Box(x=x, y=y, w=length, h=9), color=grey))
    return placement


def _corporate_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """A company's title slide: a slanted panel in the accent along the right, a slanted stripe in the second accent
    before it, and the title and subtitle on the left."""
    palette = theme.palette
    placement = Placement("v5/corporate-title")
    placement.shapes += [
        ShapeElement(
            role="stripe",
            shape="polygon",
            points=geometry.slanted(0.3),
            box=Box(x=1150, y=0, w=330, h=HEIGHT),
            color=palette.accent_2,
        ),
        ShapeElement(
            role="panel",
            shape="polygon",
            points=geometry.slanted(0.3),
            box=Box(x=1260, y=0, w=760, h=HEIGHT),
            color=palette.accent,
        ),
    ]
    title = Box(x=MARGIN + 40, y=260, w=980, h=400)
    placement.boxes["title"] = (title, "left title")
    placement.boxes["subtitle"] = (Box(x=MARGIN + 40, y=700, w=900, h=170), "left subtitle")
    placement.shapes += _decoration(_left_aligned(theme), title, gap=12)
    return placement


def _beamer_title(roles: dict[str, Content], theme: Theme) -> Placement:
    """A lecture's title slide, as Beamer's: the title on a rounded block of the accent in the middle, the subtitle
    under it."""
    accent = theme.palette.accent
    block = Box(x=160, y=270, w=1600, h=330)
    placement = Placement("v5/beamer-title")
    placement.shapes.append(ShapeElement(role="title block", box=block, color=accent, corner=28))
    placement.boxes["title"] = (_inset(block, 40), "beamer title")
    placement.colors["title"] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    placement.on_fill.add("title")
    placement.boxes["subtitle"] = (Box(x=160, y=640, w=1600, h=150), "centred subtitle")
    return placement


@dataclass(frozen=True)
class _Layout:
    """One of a slide type's layouts: its name, what places its elements, how likely it's picked (against the type's
    other layouts), which slides it fits, by their elements, and which families' themes have it (a family's own
    layout; none named: every family's)."""

    name: str
    build: Callable[[dict[str, Content], Theme], Placement]
    weight: float = 1.0
    fits: Callable[[dict[str, Content]], bool] = _always
    families: frozenset[str] = frozenset()

    def for_family(self, family: str | None) -> bool:
        """Whether a theme of the family has the layout (when the family isn't known: whether every theme has it)."""
        return not self.families or family in self.families


_LAYOUTS: Final[dict[str, tuple[_Layout, ...]]] = {
    # (the generic title's named for the theme's alignment: v5/title-left or -center; a family's own comes first)
    "title": (
        _Layout("v5/title", _title_slide),
        _Layout("v5/kids-title", _kids_title, 50, families=frozenset({"kids"})),
        _Layout("v5/neon-title", _neon_title, 50, families=frozenset({"neon"})),
        _Layout("v5/swiss-title", _swiss_title, 50, families=frozenset({"Swiss poster"})),
        _Layout("v5/newspaper-title", _newspaper_title, 50, families=frozenset({"newspaper"})),
        _Layout("v5/beamer-title", _beamer_title, 50, families=frozenset({"academic"})),
        _Layout("v5/corporate-title", _corporate_title, 50, families=frozenset({"corporate"})),
    ),
    "large_quote": (
        _Layout("v5/statement", _statement),
        _Layout("v5/statement-left", _statement_left, 0.8),
        _Layout("v5/statement-band", _statement_band, 0.6),
    ),
    "image": (
        _Layout("v5/image-top", _image_top),
        _Layout("v5/image-side", _image_beside(right=False), 0.6, _beside_title),
        _Layout("v5/image-side-right", _image_beside(right=True), 0.5, _beside_title),
    ),
    "full_image": (
        _Layout("v5/full-image", _full_image),
        _Layout("v5/full-image-low", _full_image_low, 0.8, _titled),
        _Layout("v5/full-image-corner", _full_image_corner, 0.8, _titled),
        _Layout("v5/full-image-framed", _full_image_framed, 0.8, _untitled),
    ),
    "two_column_image": (
        _Layout("v5/columns-2", _columns(2)),
        _Layout("v5/columns-2-headed", _headed_columns(2), 0.8),
        _Layout("v5/columns-2-rows", _rows, 0.8),
        _Layout("v5/columns-2-split", _split, 0.8),
    ),
    "three_column_image": (
        _Layout("v5/columns-3", _columns(3)),
        _Layout("v5/columns-3-headed", _headed_columns(3), 0.8),
    ),
    "chart": (
        _Layout("v5/chart", _chart),
        _Layout("v5/chart-side", _chart_side, 0.6, _beside_title),
    ),
    "diagram": (_Layout("v5/diagram", _diagram),),
    # (A type's first layout fits every slide of it: the others may need short numbers, or a fourth option)
    "big_number": (
        _Layout("v5/big-number", _big_number),
        _Layout("v5/big-number-panel", _big_number_panel, 0.8, _short("number", 7)),
        _Layout("v5/big-number-disc", _big_number_disc, 0.7, _short("number", 5)),
    ),
    "kpi": (
        _Layout("v5/kpi-rows", _kpi_rows),
        _Layout("v5/kpi-tiles", _kpi_tiles, 1.2, _narrow_tiles_fit),
        _Layout("v5/kpi-grid", _kpi_grid, 0.8, _four_short_figures),
    ),
    "quiz": (
        _Layout("v5/quiz-list", _quiz_list),
        _Layout("v5/quiz-tiles", _quiz_tiles, 0.9, _has("option_4")),
    ),
    "social_post": (
        _Layout("v5/post", _post(photo_left=False)),
        _Layout("v5/post-photo-left", _post(photo_left=True), 0.8, _has("photo")),
    ),
    "news_headline": (
        _Layout("v5/news-tv", _news_tv),
        _Layout("v5/newspaper", _newspaper, 0.9),
    ),
    "agenda": (
        _Layout("v5/agenda", _agenda),
        _Layout("v5/agenda-steps", _agenda_steps, 0.8),
        _Layout("v5/agenda-side", _agenda_side, 0.6, _beside_title),
    ),
    "section": (
        _Layout("v5/section", _section),
        _Layout("v5/section-panel", _section_panel, 0.8),
        _Layout("v5/kids-section", _kids_section, 4, families=frozenset({"kids"})),
        _Layout("v5/neon-section", _neon_section, 4, families=frozenset({"neon"})),
        _Layout("v5/swiss-section", _swiss_section, 4, families=frozenset({"Swiss poster"})),
    ),
    "questions": (
        _Layout("v5/questions", _questions),
        _Layout("v5/questions-mark", _questions_mark, 0.8),
    ),
    "timeline": (
        _Layout("v5/timeline", _timeline),
        _Layout("v5/timeline-down", _timeline_down, 0.8),
    ),
    "pyramid": (
        _Layout("v5/pyramid", _stack("v5/pyramid", "level", 4, widening=True)),
        _Layout("v5/pyramid-side", _stack("v5/pyramid-side", "level", 4, widening=True, side=True), 0.7, _beside_title),
    ),
    "funnel": (
        _Layout("v5/funnel", _stack("v5/funnel", "stage", 5, widening=False)),
        _Layout("v5/funnel-side", _stack("v5/funnel-side", "stage", 5, widening=False, side=True), 0.7, _beside_title),
    ),
    "cycle": (
        _Layout("v5/cycle", _cycle(side=False)),
        _Layout("v5/cycle-side", _cycle(side=True), 0.7, _beside_title_with_room("step", 4)),
    ),
    "org_chart": (
        _Layout("v5/org-chart", _org_chart(side=False)),
        _Layout("v5/org-chart-side", _org_chart(side=True), 0.7, _beside_title_with_room("report", 3)),
    ),
    "iceberg": (
        _Layout("v5/iceberg", _iceberg(side=False)),
        _Layout("v5/iceberg-side", _iceberg(side=True), 0.7, _beside_title),
    ),
    "meme": (_Layout("v5/meme", _meme),),
}
