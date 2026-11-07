"""The layout engine: a deck's elements in their layout's boxes, in a theme's style (docs/v5-plan.md, section 9).

Every slide type has layouts, which are geometry only: boxes on the 1920×1080 canvas for the roles of its elements
(the title, the image, the captions...). The engine picks a layout for every slide (with the deck's seed), puts the
elements in its boxes, gives every text its theme's font and colour at the largest size at which it fits, and adds
the theme's background and decoration. With style_chaos, slides get themes of their own: none (0) to all (1).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from talkgenerator.design import color, fit, themes, treatments
from talkgenerator.models.deck import (
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
    color: Literal["text", "muted", "light"] = "text"
    align: Literal["title", "left", "center", "right"] = "title"  # title: as the theme aligns its titles
    anchor: TextAnchor = "middle"
    heading: bool = False  # bold and in capitals as the theme's headings are
    italic: bool = False
    on_photo: bool = False  # on a shade or band over a photo, which could be anything


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
}


@dataclass
class _Placement:
    layout: str
    boxes: dict[str, tuple[Box, str]] = field(default_factory=dict)  # role: (box, text spec)
    shapes: list[ShapeElement] = field(default_factory=list)  # drawn behind the content
    overlays: list[ShapeElement] = field(default_factory=list)  # drawn over the content, under the texts
    photo: bool = False  # a photo fills the slide: credits go on a band


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

    def next(self, slide: DeckSlide) -> DeckSlide:
        """The deck's next slide, laid out."""
        slide_rng = self._rng.child("slide", self._number)
        own = None
        if self.style_chaos > 0:
            with random_util.use(slide_rng.child("chaos")):
                chaotic = random_util.random() < self.style_chaos
            if chaotic:
                own = themes.pick(themes.RANDOM, slide_rng.child("theme"), self.extremes)
        placed = lay_out_slide(
            slide, own or self.theme, slide_rng, own_style=own is not None, previous=self._previous, used=self._used
        )
        self._used[placed.layout] += 1
        self._previous = placed.layout
        self._number += 1
        return placed


def layouts_for(slide: DeckSlide) -> list[str]:
    """The layouts that fit the slide: those of its type that fit its elements (a full-screen picture's title goes on
    a band or a panel, and one without a title can be framed instead, say)."""
    roles = {element.role: element for element in slide.elements}
    return [layout.name for layout in _LAYOUTS.get(slide.type, ()) if layout.fits(roles)]


def layout_names() -> list[str]:
    """Every layout's name, slide type by slide type (a title slide's is named for its theme's alignment, as
    v5/title-left or v5/title-center)."""
    return [layout.name for layouts in _LAYOUTS.values() for layout in layouts]


def lay_out_slide(
    slide: DeckSlide,
    theme: Theme,
    rng: random_util.Rng,
    own_style: bool = False,
    previous: str | None = None,
    used: Mapping[str, int] | None = None,
) -> DeckSlide:
    """The slide in one of the layouts that fit it, picked with its random generator: not the previous slide's
    layout if another one fits, and less likely the more often the deck has had it already (used)."""
    layouts = _LAYOUTS.get(slide.type)
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
    palette = theme.palette
    background = roles.get("background")
    backdrop: list[Content] = []  # a photo behind everything, and the shapes behind the content
    if isinstance(background, ImageElement):
        with random_util.use(rng.child("treatment", background.role)):
            look = treatments.for_look(treatments.treatment(theme, framed=False), background.image, theme)
        backdrop.append(background.model_copy(update={"box": FULL, "fit": "cover", "treatment": look}))
    backdrop += placement.shapes
    content: list[Content] = []  # pictures, charts and diagrams; the bands over them; then the texts, on top
    texts: list[Content] = []
    for element in slide.elements:
        if element is background or element.role not in placement.boxes:
            continue
        box, spec = placement.boxes[element.role]
        if isinstance(element, TextElement):
            texts.append(
                element.model_copy(update={"box": box, "style": _style(element.text, box, SPECS[spec], theme)})
            )
        elif isinstance(element, ImageElement):
            framed = box != FULL and not placement.photo  # (a picture over the whole slide gets no frame)
            with random_util.use(rng.child("treatment", element.role)):
                look = treatments.for_look(treatments.treatment(theme, framed), element.image, theme)
            polaroid = look is not None and look.frame == "polaroid"  # (its own white frame instead of a border)
            border = palette.text if theme.image_border and framed and not polaroid else None
            content.append(element.model_copy(update={"box": box, "border": border, "treatment": look}))
        elif isinstance(element, ChartElement):
            content.append(element.model_copy(update={"box": box}))
        elif isinstance(element, DiagramElement):
            content.append(element.model_copy(update={"box": box, "style": diagram_style(element.diagram, theme)}))
    elements = [*backdrop, *content, *placement.overlays, *texts]
    # The credits read on what's behind them: the background (and the shapes on it, such as a panel), or a photo
    # (which could be anything) under a shade
    behind = _backgrounds(theme)
    behind += [
        color.mix(colour, shape.color, shape.opacity)
        for shape in placement.shapes
        if _overlap(shape.box, CREDITS_BOX)
        for colour in _backgrounds(theme)
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
    effect = theme.heading_effect if spec.heading else None
    if effect is not None and spec.on_photo:  # (over a photo, the text colour reads; a gradient may not)
        effect = effect.model_copy(update={"fill": ()})
    return TextStyle(
        font=font,
        size=fitted.size,
        color=colors[spec.color],
        bold=bold,
        italic=spec.italic,
        uppercase=uppercase,
        align=theme.title_align if spec.align == "title" else spec.align,
        anchor=spec.anchor,
        effect=effect,
    )


def _overlap(box: Box, other: Box) -> bool:
    """Whether the boxes share some area (not just an edge)."""
    return (
        box.x < other.x + other.w and other.x < box.x + box.w and box.y < other.y + other.h and other.y < box.y + box.h
    )


def _backgrounds(theme: Theme) -> list[str]:
    """The colours of a slide's background in the theme: one, or both ends of a gradient."""
    palette = theme.palette
    return [palette.background, *([theme.gradient_to] if theme.background == "gradient" and theme.gradient_to else [])]


def diagram_style(diagram: VennDiagram | MatrixDiagram, theme: Theme) -> DiagramStyle:
    """A diagram's look in the theme: its labels in the theme's body font and text colour, its circles or quadrants
    in the theme's accents (and two hues a third of the way round from them), and its punchline in the colour that
    stands out. Circles and quadrants get lighter or darker (keeping their hue) until the text reads on them, and
    where they overlap: the theme's text reads on its background, so on a lighter or darker shade of it too."""
    palette = theme.palette
    backgrounds = _backgrounds(theme)
    opacity = DIAGRAM_OPACITY[diagram.diagram_type]
    turned = [color.to_hsl(accent) for accent in (palette.accent, palette.accent_2)]
    accents = (
        palette.accent,
        palette.accent_2,
        *(color.hsl(hue + 120, saturation, lightness) for hue, saturation, lightness in turned),
    )
    overlapping = len(diagram.circles) if isinstance(diagram, VennDiagram) else 0
    fills = _readable_fills(accents, palette.text, backgrounds, opacity, overlapping)
    labels, punchline, lines = diagram_behind(diagram, fills, opacity, backgrounds)
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
    fills: Sequence[str], text: str, backgrounds: Sequence[str], opacity: float, overlapping: int
) -> tuple[str, ...]:
    """The fills, each the nearest shade of it (by its lightness: lighter under dark text, darker under light text)
    on which the text reads, over every background; and with the first ones (as many as overlap) shaded further, if
    the text doesn't read where they all overlap yet."""
    lighter = color.luminance(text) < color.luminance(backgrounds[0])

    def shade(fill: str, steps: int) -> str:
        hue, saturation, lightness = color.to_hsl(fill)
        return color.hsl(hue, saturation, lightness + (0.05 if lighter else -0.05) * steps)

    def reads(*layers: str) -> bool:
        return color.worst_contrast(text, _under(backgrounds, layers, opacity)) >= color.BODY_CONTRAST

    steps = [next((step for step in range(21) if reads(shade(fill, step))), 20) for fill in fills]
    shaded = [shade(fill, step) for fill, step in zip(fills, steps, strict=True)]
    for more in range(1, 21):
        if overlapping < 2 or reads(*shaded[:overlapping]):
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
    diagram: VennDiagram | MatrixDiagram, fills: Sequence[str], opacity: float, backgrounds: Sequence[str]
) -> tuple[list[str], list[str], list[str]]:
    """What may be behind a diagram's labels, its punchline's name and its lines: the backgrounds, under the circles
    or quadrants they're on (where a Venn diagram's circles overlap, under all of them)."""

    def under(*layers: str) -> list[str]:
        return _under(backgrounds, layers, opacity)

    if isinstance(diagram, VennDiagram):
        circles = fills[: len(diagram.circles)]
        return [*(mixed for circle in circles for mixed in under(circle)), *under(*circles)], [], []
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


def _title_slide(roles: dict[str, Content], theme: Theme) -> _Placement:
    title = Box(x=160, y=230, w=1600, h=420)
    placement = _Placement(f"v5/title-{theme.title_align}")
    placement.boxes["title"] = (title, "talk title")
    placement.boxes["subtitle"] = (Box(x=160, y=700, w=1600, h=170), "subtitle")
    placement.shapes += _decoration(theme, title, gap=22)
    return placement


def _shade() -> ShapeElement:
    return ShapeElement(role="shade", box=FULL, color=SHADE, opacity=SHADE_OPACITY)


def _statement(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/statement", shapes=[_shade()])
    placement.boxes["text"] = (Box(x=200, y=200, w=1520, h=700), "statement")
    placement.boxes["title"] = (Box(x=200, y=72, w=1520, h=110), "statement title")
    return placement


def _statement_left(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The statement over the shaded photo, aligned left beside a bar in the theme's accent (made visible on it)."""
    shaded = [color.mix(extreme, SHADE, SHADE_OPACITY) for extreme in ("#000000", "#ffffff")]
    bar = ShapeElement(
        role="decoration",
        box=Box(x=150, y=250, w=14, h=600),
        color=color.readable_on(theme.palette.accent, shaded, LINE_CONTRAST),
    )
    placement = _Placement("v5/statement-left", shapes=[_shade(), bar])
    placement.boxes["text"] = (Box(x=210, y=200, w=1510, h=700), "left statement")
    placement.boxes["title"] = (Box(x=210, y=72, w=1510, h=110), "left statement title")
    return placement


def _statement_band(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The statement in the theme's text colour, on a band across the shaded photo."""
    band = ShapeElement(
        role="statement band", box=Box(x=0, y=290, w=WIDTH, h=520), color=theme.palette.surface, opacity=BAND_OPACITY
    )
    placement = _Placement("v5/statement-band", shapes=[_shade()], overlays=[band])
    placement.boxes["text"] = (Box(x=200, y=320, w=1520, h=460), "band statement")
    placement.boxes["title"] = (Box(x=200, y=150, w=1520, h=110), "statement title")
    return placement


def _content_spec(element: Content | None, caption: str = "caption") -> str:
    """The text spec of a content: a quote if it's a text (not a picture)."""
    return "quote" if isinstance(element, TextElement) else caption


def _image_top(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/image-top")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    content = Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top)
    placement.boxes["content"] = (content, _content_spec(roles.get("content")))
    return placement


def _image_beside(right: bool) -> Callable[[dict[str, Content], Theme], _Placement]:
    """The title beside the image: on its left, or (right) on its right."""
    content_width = WIDTH - 2 * MARGIN - _SIDE_TITLE_WIDTH - _SIDE_GAP

    def image_beside(roles: dict[str, Content], theme: Theme) -> _Placement:
        title_x = WIDTH - MARGIN - _SIDE_TITLE_WIDTH if right else MARGIN
        content_x = MARGIN if right else MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP
        title = Box(x=title_x, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
        placement = _Placement("v5/image-side-right" if right else "v5/image-side")
        placement.boxes["title"] = (title, "side title")
        content = Box(x=content_x, y=MARGIN, w=content_width, h=_CONTENT_BOTTOM - MARGIN)
        placement.boxes["content"] = (content, _content_spec(roles.get("content")))
        placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
        return placement

    return image_beside


def _full_image(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The picture over the whole slide, and its title on a band across the top."""
    return _full_image_with("v5/full-image", roles, theme, Box(x=0, y=0, w=WIDTH, h=170), "band title")


def _full_image_framed(roles: dict[str, Content], theme: Theme) -> _Placement:
    """A picture without a title, inset from the slide's edges (framed, in themes that frame pictures)."""
    placement = _Placement("v5/full-image-framed")
    placement.boxes["content"] = (Box(x=MARGIN, y=64, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - 64), "quote")
    return placement


def _full_image_low(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The title on a band across the bottom (above the credits)."""
    return _full_image_with("v5/full-image-low", roles, theme, Box(x=0, y=800, w=WIDTH, h=170), "band title")


def _full_image_corner(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The title on a panel in the bottom left corner."""
    return _full_image_with("v5/full-image-corner", roles, theme, Box(x=56, y=690, w=1000, h=260), "panel title")


def _full_image_with(name: str, roles: dict[str, Content], theme: Theme, band: Box, spec: str) -> _Placement:
    placement = _Placement(name, photo=True)
    placement.boxes["content"] = (FULL, "quote")
    if "title" in roles:
        placement.overlays.append(
            ShapeElement(role="title band", box=band, color=theme.palette.surface, opacity=BAND_OPACITY)
        )
        inset = 40 if spec == "panel title" else MARGIN
        title = Box(x=band.x + inset, y=band.y + 16, w=band.w - 2 * inset, h=band.h - 32)
        placement.boxes["title"] = (title, spec)
    return placement


def _columns(count: int) -> Callable[[dict[str, Content], Theme], _Placement]:
    """Side by side, with their captions under them."""
    width = (WIDTH - 2 * MARGIN - (count - 1) * _GAP) / count
    caption_height = 128 if count == 2 else 168
    caption_spec = "caption" if count == 2 else "small caption"

    def columns(roles: dict[str, Content], theme: Theme) -> _Placement:
        placement = _Placement(f"v5/columns-{count}")
        top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
        caption_top = _CONTENT_BOTTOM - caption_height
        for index in range(1, count + 1):
            x = MARGIN + (index - 1) * (width + _GAP)
            spec = _content_spec(roles.get(f"content_{index}"), caption_spec)
            placement.boxes[f"content_{index}"] = (Box(x=x, y=top, w=width, h=caption_top - top - 16), spec)
            placement.boxes[f"caption_{index}"] = (Box(x=x, y=caption_top, w=width, h=caption_height), caption_spec)
        return placement

    return columns


def _headed_columns(count: int) -> Callable[[dict[str, Content], Theme], _Placement]:
    """Side by side, with their captions above them, as headings."""
    width = (WIDTH - 2 * MARGIN - (count - 1) * _GAP) / count
    caption_height = 128 if count == 2 else 168
    caption_spec = "heading caption" if count == 2 else "small heading caption"

    def headed(roles: dict[str, Content], theme: Theme) -> _Placement:
        placement = _Placement(f"v5/columns-{count}-headed")
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


def _rows(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The two one above the other, zig-zag: the first on the left with its caption on its right, the second on the
    right with its caption on its left."""
    placement = _Placement("v5/columns-2-rows")
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


def _split(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The slide split in two halves, the first in the theme's surface colour, each with its picture (or text) and
    its caption, and the title across the top, centred (with the theme's decoration)."""
    half = WIDTH / 2
    panel = ShapeElement(role="panel", box=Box(x=0, y=0, w=half, h=HEIGHT), color=theme.palette.surface)
    placement = _Placement("v5/columns-2-split", shapes=[panel])
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


def _chart(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/chart")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    placement.boxes["chart"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), "caption")
    return placement


def _chart_side(roles: dict[str, Content], theme: Theme) -> _Placement:
    """The title on the left, the chart beside it."""
    title = Box(x=MARGIN, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
    placement = _Placement("v5/chart-side")
    placement.boxes["title"] = (title, "side title")
    x = MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP
    placement.boxes["chart"] = (Box(x=x, y=MARGIN, w=WIDTH - MARGIN - x, h=_CONTENT_BOTTOM - MARGIN), "caption")
    placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
    return placement


def _diagram(roles: dict[str, Content], theme: Theme) -> _Placement:
    placement = _Placement("v5/diagram")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    placement.boxes["diagram"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top), "caption")
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


def _always(roles: dict[str, Content]) -> bool:
    return True


def _titled(roles: dict[str, Content]) -> bool:
    return "title" in roles


def _untitled(roles: dict[str, Content]) -> bool:
    return "title" not in roles


@dataclass(frozen=True)
class _Layout:
    """One of a slide type's layouts: its name, what places its elements, how likely it's picked (against the type's
    other layouts), and which slides it fits, by their elements."""

    name: str
    build: Callable[[dict[str, Content], Theme], _Placement]
    weight: float = 1.0
    fits: Callable[[dict[str, Content]], bool] = _always


_LAYOUTS: Final[dict[str, tuple[_Layout, ...]]] = {
    "title": (_Layout("v5/title", _title_slide),),  # (named for the theme's alignment: v5/title-left or -center)
    "large_quote": (
        _Layout("v5/statement", _statement),
        _Layout("v5/statement-left", _statement_left, 0.8),
        _Layout("v5/statement-band", _statement_band, 0.6),
    ),
    "image": (
        _Layout("v5/image-top", _image_top),
        _Layout("v5/image-side", _image_beside(right=False), 0.6, _titled),
        _Layout("v5/image-side-right", _image_beside(right=True), 0.5, _titled),
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
        _Layout("v5/chart-side", _chart_side, 0.6, _titled),
    ),
    "diagram": (_Layout("v5/diagram", _diagram),),
}
