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
from talkgenerator.models import classic
from talkgenerator.models.deck import (
    DECORATION,
    Box,
    ChartElement,
    ChartSpec,
    Content,
    Credit,
    CreditPart,
    Deck,
    DeckSlide,
    DiagramElement,
    DiagramStyle,
    ImageAsset,
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
from talkgenerator.render import charts, diagrams  # (where a diagram's labels go, and a trend's points)
from talkgenerator.sources import memes
from talkgenerator.util import random_util

WIDTH: Final = 1920
HEIGHT: Final = 1080
MARGIN: Final = 96
# The credit line: small, along the bottom (clear of what a theme's decoration puts under it, such as a status line),
# aligned right, and quiet: in the colour nearest what's behind it that reads there at CREDITS_CONTRAST (the muted
# colour, mixed into the background, as if see-through), with no band behind it. For people who want to know where
# the pictures came from, and for their licenses, without drawing the eye from the slide (D51).
CREDITS_BOX: Final = Box(x=MARGIN, y=996, w=WIDTH - 2 * MARGIN, h=36)
CREDITS_SIZE: Final = 14  # (7 points)
CREDITS_CONTRAST: Final = 2.5
CREDITS_PREFIX: Final = "Image sources: "
SOURCES_PREFIX: Final = "Sources: "  # (for a credit line that credits a text too: see credits_prefix)
# Where a picture is under them (it could be any colour, mid-grey too, where no one colour reads), the credits are
# light, with a dark halo around their letters (a glow, which renderers draw this opaque)
CREDITS_ON_PICTURES: Final = "#e0e0e0"
CREDITS_HALO: Final = TextEffect(glow="#000000", glow_radius=3)
HALO_OPACITY: Final = 0.6
ANY_PICTURE: Final = ("#000000", "#777777", "#ffffff")
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
# A wall of text is unreadable on purpose (docs/v5-plan.md, section 8): its points are fine print, at the largest of
# these sizes at which they fill its slide, and the design checks hold its fine print to a floor of its own
FINE_PRINT_SIZES: Final = tuple(range(18, 36, 2))
FINE_PRINT: Final[dict[str, frozenset[str]]] = {
    "wall_of_text": frozenset({*(f"point_{number}" for number in range(1, 17)), "highlight", "continued"})
}


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
    # (a big number's and KPI tiles' texts over their picture, shaded, or on a band across it: D63)
    "photo title": TextSpec("heading", 88, 44, color="light", heading=True, on_photo=True),
    "photo number": TextSpec("heading", 300, 120, color="light", align="center", heading=True, on_photo=True),
    "photo label": TextSpec("body", 72, 32, color="light", align="center", anchor="top", on_photo=True),
    "photo source": TextSpec("body", 36, 24, color="light", align="center", italic=True, on_photo=True),
    "band number": TextSpec("heading", 260, 96, align="center", heading=True, on_photo=True),
    "band label": TextSpec("body", 64, 30, align="center", anchor="top", on_photo=True),
    "side number": TextSpec("heading", 240, 96, color="accent", align="left", anchor="bottom", heading=True),
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
    # (an academic talk's references: a work's number as cited, the work, and a caption under a picture of one)
    "citation": TextSpec("body", 52, 28, color="accent", align="right", bold=True),
    "reference": TextSpec("body", 52, 28, align="left"),
    "figure caption": TextSpec("body", 40, 24, color="muted", align="center", anchor="top", italic=True),
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
    # (slide types from PowerPoint karaoke decks: a fun fact's heading on a sticker, and the fact)
    "sticker": TextSpec("heading", 64, 28, align="center", heading=True, on_fill=True, effect=False),
    "fact": TextSpec("body", 96, 36, align="center", bold=True),
    "side fact": TextSpec("body", 88, 36, align="left", bold=True),
    "card fact": TextSpec("body", 88, 34, align="left", bold=True, on_fill=True),
    "card source": TextSpec("body", 36, 24, align="left", italic=True, on_fill=True),
    # (an acronym's letters on tiles and its words; a dare; a flowchart's labels and its end; a tier list's rows)
    "tile letter": TextSpec("heading", 120, 40, align="center", heading=True, on_fill=True, effect=False),
    "acronym word": TextSpec("heading", 96, 32, align="left", heading=True),
    "column word": TextSpec("heading", 64, 26, align="center", anchor="top", heading=True),
    "dare": TextSpec("heading", 104, 40, align="center", heading=True, on_fill=True),
    "dare kicker": TextSpec("heading", 120, 48, color="accent", align="center", heading=True),
    "open dare": TextSpec("heading", 104, 40, align="center", heading=True),
    "flow question": TextSpec("body", 64, 28, align="center", on_fill=True, bold=True),
    "flow step": TextSpec("body", 56, 26, align="center", on_fill=True),
    "flow label": TextSpec("body", 40, 24, align="left", bold=True),
    "flow label right": TextSpec("body", 40, 24, align="right", bold=True),
    "tier item": TextSpec("body", 52, 26, align="center", on_fill=True),
    # (the next ones from the karaoke catalogue: a wall of text's fine print, at the one size that fills its slide, and
    # its title on a page; an alignment chart's axes and cells; red flags; reviews; a fake error message's dialog)
    **{f"fine print {size}": TextSpec("body", size, size, align="left", anchor="top") for size in FINE_PRINT_SIZES},
    "fine print note": TextSpec("body", 24, 18, color="muted", align="right", italic=True),
    "page title": TextSpec("heading", 64, 36, align="left", heading=True, on_fill=True),
    "axis": TextSpec("heading", 44, 26, align="center", anchor="bottom", heading=True, effect=False),
    "side axis": TextSpec("heading", 36, 24, align="right", heading=True, effect=False),
    "cell": TextSpec("body", 44, 24, align="center", on_fill=True),
    "flag": TextSpec("body", 60, 28, align="left"),
    "card flag": TextSpec("body", 52, 26, align="center", anchor="top", on_fill=True),
    "review": TextSpec("body", 48, 26, align="left", anchor="top", italic=True, on_fill=True),
    "reviewer": TextSpec("body", 36, 24, align="left", on_fill=True, bold=True),
    "rating": TextSpec("body", 40, 24, align="left", on_fill=True, bold=True),
    "window title": TextSpec("body", 36, 24, align="left", on_fill=True, bold=True),
    "error icon": TextSpec("heading", 140, 60, align="center", heading=True, on_fill=True, effect=False),
    "error message": TextSpec("body", 60, 30, align="left", on_fill=True),
    "centred error message": TextSpec("body", 60, 30, align="center", on_fill=True),
    "error code": TextSpec("body", 32, 24, align="left", italic=True, on_fill=True),
    "centred error code": TextSpec("body", 32, 24, align="center", italic=True, on_fill=True),
    "button": TextSpec("body", 40, 24, align="center", on_fill=True, bold=True),
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
    photo: bool = False  # a photo fills the slide (behind its texts' bands)
    colors: dict[str, str] = field(default_factory=dict)  # role: the colour of a text on a shape (that reads on it)
    # The roles of pictures shown as they are, without the theme's treatment (a meme's template, captioned in place)
    untreated: set[str] = field(default_factory=set)
    # The theme's own decoration (see talkgenerator.design.motifs): shapes behind everything (scenery, a frame around
    # the slide), shapes over the layout's own (a sticker, a title's underline), and texts (a terminal's prompt, a
    # slide's number), each with its box, text spec and colour, and the role of the element it belongs to, if any (the
    # name on a picture's window, which appears with the picture: an element's part_of)
    under: list[ShapeElement] = field(default_factory=list)
    decor: list[ShapeElement] = field(default_factory=list)
    texts: list[tuple[str, Box, str | TextSpec, str, str | None]] = field(default_factory=list)
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


def lay_out(
    deck: Deck,
    theme: Theme,
    style_chaos: float = 0.0,
    extremes: bool = True,
    families: Sequence[str] | None = None,
) -> Deck:
    """The deck with its elements placed and styled in the theme; with style_chaos, some slides (that share of
    them, picked by the seed) in themes of their own, of the families the talk allows (see
    talkgenerator.design.themes.allowed; None, all of them). Every slide knows how many the deck has, for its number
    ("7/12")."""
    layout = DeckLayout(deck.seed, theme, style_chaos, extremes, families, total=len(deck.slides))
    slides = tuple(layout.next(slide) for slide in deck.slides)
    return deck.model_copy(update={"theme": theme.name, "style": theme, "slides": slides})


class DeckLayout:
    """Lays a deck's slides out one at a time, in order, as lay_out does all at once: a slide's layout depends on the
    deck's seed, the slide's place, and the layouts of the slides before it, so slides can be laid out as they come
    in (talkgenerator.generator.stream_talk). The total is how many slides the deck has, which a talk knows from its
    start (for a slide's number, "7/12"; None: the number alone)."""

    def __init__(
        self,
        seed: int | None,
        theme: Theme,
        style_chaos: float = 0.0,
        extremes: bool = True,
        families: Sequence[str] | None = None,
        total: int | None = None,
    ) -> None:
        self.theme, self.style_chaos, self.extremes = theme, style_chaos, extremes
        self.total = total
        # (the families a slide's own theme can be of, in a chaos deck: None, all of them)
        self.families = tuple(families) if families is not None else None
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

    def spare(self, number: int, slide: DeckSlide) -> DeckSlide:
        """A spare slide (the number-th, from 0: see talkgenerator.generator.stream_talk's spares) laid out in the
        deck's theme, as its slides are, but from a random stream of its own and without a slide number ("7/12"): it's
        none of the deck's slides, which are laid out the same, with spares or without. (It can be laid out while the
        deck's slides are, on another thread: this changes nothing of the deck's layout so far.)"""
        return self._lay_out(slide, number, None, Counter(), spare=True)

    def _lay_out(
        self, slide: DeckSlide, number: int, previous: str | None, used: Counter[str], spare: bool = False
    ) -> DeckSlide:
        slide_rng = self._rng.child("spare" if spare else "slide", number)
        own = None
        if self.style_chaos > 0:
            with random_util.use(slide_rng.child("chaos")):
                chaotic = random_util.random() < self.style_chaos
            if chaotic:
                own = themes.pick(themes.RANDOM, slide_rng.child("theme"), self.extremes, among=self.families)
        return lay_out_slide(
            slide,
            own or self.theme,
            slide_rng,
            own_style=own is not None,
            previous=previous,
            used=used,
            number=number,
            total=self.total,
            numbered=not spare,
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
    total: int | None = None,
    numbered: bool = True,
) -> DeckSlide:
    """The slide (the number-th of its deck, from 0, of total slides, if that's known) in one of the layouts that fit
    it and its theme, picked with its random generator: not the previous slide's layout if another one fits, and less
    likely the more often the deck has had it already (used); with its theme's own decoration (see
    talkgenerator.design.motifs), which numbers it ("7/12"), unless it's not to be numbered (a spare slide, which is
    none of the deck's)."""
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
                total=total,
                numbered=numbered,
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
            under = layers.behind(slide_background, backdrop, box)
            content.append(
                element.model_copy(update={"box": box, "chart": cluster_colours(element.chart, theme, under)})
            )
        elif isinstance(element, DiagramElement):
            under = layers.behind(slide_background, backdrop, box)  # (the background, and decoration reaching under it)
            diagram_look = diagram_style(element.diagram, theme, box, under)
            content.append(element.model_copy(update={"box": box, "style": diagram_look}))
    for text, place, text_spec, colour, part_of in placement.texts:  # (the decoration's own: a prompt, a number)
        own = SPECS[text_spec] if isinstance(text_spec, str) else text_spec
        style = _style(text, place, own, theme, colour, True)
        texts.append(TextElement(role=DECORATION, text=text, box=place, style=style, part_of=part_of))
    elements = _in_turn([*backdrop, *content, *placement.overlays, *texts])
    # (a picture the layout had no room for, such as a diagram's box's, stays out, and its credit with it)
    left_out = [
        element.image
        for element in slide.elements
        if isinstance(element, ImageElement) and element is not background and element.role not in placement.boxes
    ]
    credits = _without_credits_of(slide.credits, left_out)
    return slide.model_copy(
        update={
            "layout": placement.layout,
            "elements": tuple(elements),
            "credits": credits,
            "background": slide_background,
            "style": theme if own_style else None,
            "credits_box": CREDITS_BOX,
            "credits_style": credits_style(
                credit_line(credits, credits_prefix(slide)), theme, slide_background, elements
            ),
        }
    )


def _without_credits_of(credits: tuple[Credit, ...], images: Sequence[ImageAsset]) -> tuple[Credit, ...]:
    """The credits, without one for each of the images (those that are left out of a slide)."""
    kept = list(credits)
    for image in images:
        own = image.credit or ((CreditPart(text=image.source, url=image.source_url),) if image.source else ())
        if own in kept:
            kept.remove(own)
    return tuple(kept)


def _in_turn(elements: list[Content]) -> list[Content]:
    """The elements, with the clicks they appear on numbered 1, 2, 3... in turn: a click whose elements the layout
    left out (a meme's caption without a box, say) shows nothing, so it goes, in every renderer alike. On a slide
    whose chart or diagram takes clicks of its own first (a trend's second line, a matrix's punchline), the elements'
    clicks come after those (a picture by a trend's named point, after the second line)."""
    own = max((_own_clicks(element) for element in elements), default=0)
    used = sorted({click for element in elements if (click := getattr(element, "appears_on_click", None))})
    if used == list(range(own + 1, own + len(used) + 1)):
        return elements
    turn = {click: number for number, click in enumerate(used, own + 1)}
    return [
        element.model_copy(update={"appears_on_click": turn[click]})
        if (click := getattr(element, "appears_on_click", None))
        else element
        for element in elements
    ]


def cluster_colours(spec: ChartSpec, theme: Theme, backgrounds: Sequence[str]) -> ChartSpec:
    """A scatter chart's clusters (its named clouds: see talkgenerator.render.charts.clusters, of two or more), and a
    trend's lines (two or more: its second, the punchline), in colours of their own that tell them apart and show on
    what's behind the chart: the theme's accent, then its second accent or its text colour, or the accent's hue
    turned, whichever is far enough from the colours before it, in hue or in lightness (in a theme whose two accents
    are alike, as nearly half of them are). Other charts stay as they are, in their renderers' colours."""
    if spec.chart_type == "scatter":
        shown = charts.clusters([(series.name, len(series.points)) for series in spec.series])
    elif spec.chart_type == "line":
        shown = list(range(len(spec.series)))
    else:
        return spec
    if len(shown) < 2:
        return spec
    palette = theme.palette
    hue, saturation, lightness = color.to_hsl(palette.accent)
    # (a hue turned round from the accent's, in colour and neither dark nor light, even for a black or a grey accent)
    turned = [
        color.hsl(hue + turn, max(saturation, 0.55), min(max(lightness, 0.35), 0.6)) for turn in (150, 240, 60, 300)
    ]
    candidates = [palette.accent, palette.accent_2, *turned, palette.text, palette.muted]
    chosen: list[str] = []
    for candidate in candidates:
        shade = color.readable_on(candidate, backgrounds or _backgrounds(theme), LINE_CONTRAST)
        if all(_far_apart(shade, other) for other in chosen):
            chosen.append(shade)
        if len(chosen) == len(shown):
            break
    chosen += [palette.muted] * (len(shown) - len(chosen))  # (no more far enough apart: the legend names them)
    series = list(spec.series)
    for index, colour in zip(shown, chosen, strict=True):
        series[index] = series[index].model_copy(update={"color": colour})
    return spec.model_copy(update={"series": tuple(series)})


def _far_apart(colour: str, other: str) -> bool:
    """Whether two colours tell apart at a glance: by their hues, when both have one; by one having a hue and the
    other none (a red and a black); or by their lightness."""
    hue, saturation, lightness = color.to_hsl(colour)
    other_hue, other_saturation, other_lightness = color.to_hsl(other)
    turn = min(abs(hue - other_hue), 360 - abs(hue - other_hue))
    if min(saturation, other_saturation) >= 0.25:
        return turn >= 50 or abs(lightness - other_lightness) >= 0.3
    if max(saturation, other_saturation) >= 0.4:  # (one in colour, the other grey)
        return True
    return abs(lightness - other_lightness) >= 0.3


def _own_clicks(element: Content) -> int:
    """The clicks a chart or a diagram takes for itself: a chart's series after the first, one each, when they appear
    on clicks; a diagram's punchline, when it does."""
    if isinstance(element, ChartElement) and element.chart.reveal == "series":
        return max(0, len(element.chart.series) - 1)
    if isinstance(element, DiagramElement) and element.diagram.reveal == "punchline":
        return 1
    return 0


def credit_line(credits: Sequence[Credit], prefix: str = CREDITS_PREFIX) -> str:
    """The credit line of a slide's credits, as it reads on the slide (after credits_prefix's words)."""
    return prefix + ", ".join("".join(part.text for part in credit) for credit in credits)


def credits_prefix(slide: DeckSlide) -> str:
    """How a slide's credit line starts: "Image sources: " when it credits its pictures alone, as it has since 2019,
    and "Sources: " when it credits a text too (a real fact: see DeckSlide.credits_a_text)."""
    return SOURCES_PREFIX if slide.credits_a_text() else CREDITS_PREFIX


def credits_style(line: str, theme: Theme, background: SlideBackground, elements: Sequence[Content]) -> TextStyle:
    """How the credit line looks on a slide (see CREDITS_BOX): small, aligned right, in the colour nearest what's
    behind it (the slide's background, or a shape across the bottom of the slide: the muted colour, mixed into it)
    that reads at CREDITS_CONTRAST on what's behind its letters, or else the nearest shade of the muted colour that
    does; and where a picture is under its letters, or no colour reads (across a panel and the background, say), light
    with a dark halo."""
    palette = theme.palette
    style = TextStyle(font=theme.fonts.body, size=CREDITS_SIZE, color=palette.muted, align="right", anchor="middle")
    behind = credits_behind(line, style, background, elements)
    under = behind[0] if behind else palette.background
    candidates = [color.mix(under, palette.muted, step / 20) for step in range(1, 21)]
    candidates.append(color.readable_on(palette.muted, behind, CREDITS_CONTRAST))
    quiet = next((colour for colour in candidates if color.worst_contrast(colour, behind) >= CREDITS_CONTRAST), None)
    if quiet is not None and not credits_over_picture(line, style, elements):
        return style.model_copy(update={"color": quiet})
    return style.model_copy(update={"color": CREDITS_ON_PICTURES, "effect": CREDITS_HALO})


def credits_behind(
    line: str, style: TextStyle, background: SlideBackground | None, elements: Sequence[Content]
) -> list[str]:
    """The colours that may be behind the credit line's letters (a picture under them could be any colour)."""
    lines = line_boxes(line, CREDITS_BOX, style)
    return layers.behind_letters(background, elements, lines, style.size, anything=ANY_PICTURE)


def credits_over_picture(line: str, style: TextStyle, elements: Sequence[Content]) -> bool:
    """Whether a picture is under any of the credit line's letters."""
    places = layers.letters(line_boxes(line, CREDITS_BOX, style), style.size)
    return any(
        isinstance(element, ImageElement) and element.box is not None and _overlap(element.box, place)
        for element in elements
        for place in places
    )


def credits_legibility(style: TextStyle, behind: Sequence[str]) -> float:
    """How well the credit line reads on what's behind its letters: by its colour, or with a halo, by its colour on
    the halo over what's behind it."""
    worst = color.worst_contrast(style.color, behind)
    effect = style.effect
    if effect is not None and effect.glow and effect.glow_radius > 0:
        haloed = [color.mix(colour, effect.glow, HALO_OPACITY) for colour in behind]
        worst = max(worst, color.worst_contrast(style.color, haloed))
    return worst


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
    """The slide split in two halves, each with its picture (or text) and its caption, a thin rule between them that
    comes in with the second, and the title across the top, centred (with the theme's decoration). (No panel behind
    one half: on a slide whose second half comes on a click, it looked like a stray background.)"""
    half = WIDTH / 2
    placement = Placement("v5/columns-2-split")
    top = MARGIN
    if "title" in roles:
        placement.boxes["title"] = (_TITLE, "centred title")
        placement.shapes += _decoration(theme.model_copy(update={"title_align": "center"}), _TITLE, gap=16)
        top = _CONTENT_TOP
    rule = color.readable_on(theme.palette.muted, _backgrounds(theme), LINE_CONTRAST)
    divider = Box(x=half - 1, y=top, w=2, h=_CONTENT_BOTTOM - top)
    placement.shapes.append(ShapeElement(role="divider", box=divider, color=rule, part_of="content_2"))
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
    box = Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top)
    placement.boxes["chart"] = (box, "caption")
    _pin_picture(placement, roles, box, theme)
    return placement


def _chart_side(roles: dict[str, Content], theme: Theme) -> Placement:
    """The title on the left, the chart beside it."""
    title = Box(x=MARGIN, y=MARGIN, w=_SIDE_TITLE_WIDTH, h=HEIGHT - 2 * MARGIN - 100)
    placement = Placement("v5/chart-side")
    placement.boxes["title"] = (title, "side title")
    x = MARGIN + _SIDE_TITLE_WIDTH + _SIDE_GAP
    box = Box(x=x, y=MARGIN, w=WIDTH - MARGIN - x, h=_CONTENT_BOTTOM - MARGIN)
    placement.boxes["chart"] = (box, "caption")
    placement.shapes += _decoration(theme.model_copy(update={"title_align": "left"}), title, gap=12)
    _pin_picture(placement, roles, box, theme)
    return placement


# A picture by a trend's named point (docs/v5-plan.md, D64): how far from the point, and how much of the plot's height
# it takes at most (and how tall it is at most, in canvas pixels)
_PIN_GAP: Final = 28.0
_PIN_SHARE: Final = 0.46
_PIN_WIDTH: Final = 0.3  # (of the plot's width, at most)
_PIN_SIZES: Final = (1.0, 0.8, 0.62)  # (as large as it may be, or smaller where that keeps it clear of the lines)
_PIN_LARGEST: Final = 320.0
POINT_PICTURE: Final = "point_picture"  # (its role: see talkgenerator.slide.slides.POINT_PICTURE)


def _pin_picture(placement: Placement, roles: dict[str, Content], box: Box, theme: Theme) -> None:
    """The picture by the chart's named point, if the slide has one, by the point, with a line from the point to
    it, in the colour of the point's dot (which comes in with it)."""
    chart = roles.get("chart")
    if not isinstance(roles.get(POINT_PICTURE), ImageElement) or not isinstance(chart, ChartElement):
        return
    pinned = point_picture(chart.chart, box, theme.fonts.body)
    if pinned is None:
        return
    picture, line = pinned
    placement.boxes[POINT_PICTURE] = (picture, "caption")
    if line is not None:
        placement.overlays.append(line.model_copy(update={"color": theme.palette.accent_2}))


def point_picture(spec: ChartSpec, box: Box, font: str) -> tuple[Box, ShapeElement | None] | None:
    """Where the picture by a trend's named point goes, in a chart in the box (on the canvas), whose texts are in
    the font: by the point (see talkgenerator.render.charts.trend_plot, where every renderer has it), on whichever
    side keeps it clearest of the chart's lines and of the point's name, within the plot; and a line from the point
    to the picture, where it's away from it (none, where it's close). None for a chart without a named point."""
    pinned = charts.named_point(spec)
    if pinned is None:
        return None
    plot = charts.trend_plot(spec, box.w, box.h)
    lines = charts.trend_points(spec, plot)
    series, index = pinned
    x, y = lines[series][index]
    name = spec.series[series].labels[index]
    name_width = fonts.text_width(name, font, 2 * charts.LABEL_SIZE, True)
    side = charts.free_side(spec.series[series].values, index)
    middle = min(max(x + side * (12 + name_width / 2), plot.left + name_width / 2), plot.right - name_width / 2)
    label = Box(
        x=middle - name_width / 2,
        y=y - charts.NAMED_DOT / 2 - 6 - 2.4 * charts.LABEL_SIZE,
        w=name_width,
        h=2.4 * charts.LABEL_SIZE,
    )
    largest = min(_PIN_LARGEST * _PICTURE_SHAPE, _PIN_SHARE * (plot.bottom - plot.top) * _PICTURE_SHAPE)
    largest = min(largest, _PIN_WIDTH * (plot.right - plot.left))
    samples = [point for line in lines for point in _along(line)]
    # (the places it can go, as large as it is or a little smaller: by the point on every side, and anywhere in the
    # plot, on a grid; the best keeps clear of the point and its name, crosses the fewest of the lines' points, is the
    # nearest to the point, and the largest)
    best: tuple[float, Box] | None = None
    for size in _PIN_SIZES:
        width = largest * size
        height = width / _PICTURE_SHAPE
        places = [
            (
                x + _PIN_GAP if dx > 0 else x - _PIN_GAP - width if dx < 0 else x - width / 2,
                y + _PIN_GAP if dy > 0 else y - _PIN_GAP - height if dy < 0 else y - height / 2,
            )
            for dx, dy in ((1, -1), (-1, -1), (1, 1), (-1, 1), (1, 0), (-1, 0), (0, -1), (0, 1))
        ]
        places += [
            (
                plot.left + (plot.right - plot.left - width) * across / 11,
                plot.top + (plot.bottom - plot.top - height) * down / 7,
            )
            for across in range(12)
            for down in range(8)
        ]
        for left, top in places:
            left = min(max(left, plot.left), plot.right - width)  # (within the plot)
            top = min(max(top, plot.top - charts.NAMED_DOT), plot.bottom - height)
            candidate = Box(x=left, y=top, w=width, h=height)
            crossing = sum(1 for point in samples if _holds(_inset(candidate, -8), point))
            covering = _shared_area(_inset(candidate, -8), label) > 0 or _holds(
                _inset(candidate, -charts.NAMED_DOT / 2 - 8), (x, y)
            )
            smaller = (1 - size) * 400  # (a smaller picture only where it crosses fewer of the lines)
            score = (10000 if covering else 0) + crossing * 10 + _distance(candidate, (x, y)) + smaller
            if best is None or score < best[0]:
                best = (score, candidate)
    assert best is not None
    picture = best[1].model_copy(update={"x": box.x + best[1].x, "y": box.y + best[1].y})
    return picture, _line_to(picture, (box.x + x, box.y + y))


def _along(line: Sequence[tuple[float, float]], step: float = 10.0) -> list[tuple[float, float]]:
    """Points along a line through the points, about a step apart."""
    found = list(line[:1])
    for (x0, y0), (x1, y1) in itertools.pairwise(line):
        parts = max(1, math.ceil(math.hypot(x1 - x0, y1 - y0) / step))
        found += [(x0 + (x1 - x0) * part / parts, y0 + (y1 - y0) * part / parts) for part in range(1, parts + 1)]
    return found


def _holds(box: Box, point: tuple[float, float]) -> bool:
    return box.x <= point[0] <= box.x + box.w and box.y <= point[1] <= box.y + box.h


def _shared_area(box: Box, other: Box) -> float:
    across = min(box.x + box.w, other.x + other.w) - max(box.x, other.x)
    down = min(box.y + box.h, other.y + other.h) - max(box.y, other.y)
    return max(0.0, across) * max(0.0, down)


def _nearest(box: Box, point: tuple[float, float]) -> tuple[float, float]:
    """The point of the box nearest the point."""
    return min(max(point[0], box.x), box.x + box.w), min(max(point[1], box.y), box.y + box.h)


def _distance(box: Box, point: tuple[float, float]) -> float:
    return math.dist(_nearest(box, point), point)


def _line_to(picture: Box, point: tuple[float, float], width: float = 6.0) -> ShapeElement | None:
    """A line from the point (a named point's dot) to the nearest point of the picture, which belongs to the picture
    (a thin, turned rectangle: the deck has no lines), if the picture is far enough from it to need one."""
    end = _nearest(picture, point)
    length = math.dist(end, point) - charts.NAMED_DOT / 2  # (from the dot's edge)
    if length < 12:
        return None
    angle = math.atan2(end[1] - point[1], end[0] - point[0])
    start = (point[0] + math.cos(angle) * charts.NAMED_DOT / 2, point[1] + math.sin(angle) * charts.NAMED_DOT / 2)
    middle = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    box = Box(x=middle[0] - length / 2, y=middle[1] - width / 2, w=length, h=width)
    return ShapeElement(role="pin", box=box, color="#000000", rotation=math.degrees(angle), part_of=POINT_PICTURE)


def _diagram(roles: dict[str, Content], theme: Theme) -> Placement:
    placement = Placement("v5/diagram")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    box = Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=_CONTENT_BOTTOM - top)
    placement.boxes["diagram"] = (box, "caption")
    element = roles.get("diagram")
    if isinstance(element, DiagramElement):
        for role, area in diagram_pictures(element.diagram, box, theme.fonts.body, roles).items():
            placement.boxes[role] = (area, "caption")
    return placement


# How tall a picture by a Venn diagram's circle, or in a matrix's quadrant, is at most (in canvas pixels)
_DIAGRAM_PICTURE: Final = 300.0
MATRIX_CORNERS: Final = ("top_left", "top_right", "bottom_left", "bottom_right")  # (its quadrants, by role)


def diagram_pictures(
    diagram: VennDiagram | MatrixDiagram, box: Box, font: str | None, roles: Mapping[str, Content]
) -> dict[str, Box]:
    """Where the pictures of a Venn diagram's circles or a matrix's quadrants go, by their roles, for those the slide
    has (docs/v5-plan.md, D64), when the diagram is in the box (with its labels in the font): a circle's beside it,
    on its outer side (none when the labels are beside the circles: their place); a quadrant's in the part of it that
    its label leaves (none in a quadrant with a dot). The diagram draws its own labels, so a picture keeps clear of
    them; one that has no room stays out."""
    frame = diagrams.Box.on_canvas(box)
    pixel = diagrams.EMU_PER_PIXEL
    found: dict[str, Box] = {}
    if isinstance(diagram, VennDiagram):
        layout = diagrams.venn_layout_for(frame, diagram, font)
        if layout.beside:
            return found
        for number, ((x, y), side) in enumerate(zip(layout.centres[:2], (-1, 1), strict=False), 1):
            if not isinstance(roles.get(f"circle_{number}_picture"), ImageElement):
                continue
            x, y, radius = x / pixel, y / pixel, layout.radius / pixel
            height = min(_DIAGRAM_PICTURE, 0.9 * radius)
            edge = x + side * (radius + _PICTURE_GAP)  # (the circle's outer side, and a gap)
            room = edge - box.x if side < 0 else box.x + box.w - edge
            width = min(room, height * _PICTURE_SHAPE)
            area = Box(x=edge - width if side < 0 else edge, y=y - height / 2, w=width, h=height)
            picture = _picture_box(area)
            if picture is not None:
                found[f"circle_{number}_picture"] = picture.model_copy(
                    update={"x": edge - picture.w if side < 0 else edge}
                )
        return found
    matrix = diagrams.matrix_layout(frame)
    taken = {diagrams.quadrant_of(dot.x, dot.y) for dot in diagrams.matrix_dots(diagram)}
    # (a quadrant's label, as it's drawn: its lines at its size, at the top of its box in a top quadrant, at the
    # bottom of it in a bottom one)
    named = {
        label.name.split(" quadrant: ")[0]: label
        for label in diagrams.labels(frame, diagram, font)
        if " quadrant: " in label.name
    }
    for index, (corner, name) in enumerate(zip(MATRIX_CORNERS, diagrams.QUADRANT_NAMES, strict=True)):
        if not isinstance(roles.get(f"{corner}_picture"), ImageElement) or index in taken:
            continue
        quadrant = matrix.quadrants[index]
        top, bottom = quadrant.top / pixel, quadrant.bottom / pixel
        label = named.get(name)
        if label is not None:  # (the part its label leaves: under it in a top quadrant, above it in a bottom one)
            area = diagrams.text_area(label.box)
            lines = fit.wrap(label.text, area.w, font or diagrams.TEMPLATE_FONT, 2 * label.size, label.bold)
            tall = fit.text_height(len(lines), 2 * label.size)
            top, bottom = (area.y + tall, bottom) if index < 2 else (top, area.y + area.h - tall)
        area = Box(x=quadrant.left / pixel, y=top, w=quadrant.width / pixel, h=bottom - top)
        area = _inset(area, _PICTURE_GAP)
        picture = _picture_box(area.model_copy(update={"h": min(area.h, _DIAGRAM_PICTURE)}))
        if picture is not None:  # (in the middle of the part, across and down)
            found[f"{corner}_picture"] = picture.model_copy(update={"y": area.y + (area.h - picture.h) / 2})
    return found


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


def _beside_title_with_room(prefix: str, most: int, pictures: bool = True) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide has a title that fits beside a diagram, and at most so many of the items (an org chart's
    people, a cycle's steps), for whose boxes there's room beside the title (and, unless pictures, none of them with a
    picture: docs/v5-plan.md, D64)."""

    def fits(roles: dict[str, Content]) -> bool:
        pictured = any(role.startswith(f"{prefix}_") and role.endswith("_picture") for role in roles)
        return _beside_title(roles) and f"{prefix}_{most + 1}" not in roles and (pictures or not pictured)

    return fits


def _photo_beside_title(roles: dict[str, Content]) -> bool:
    """Whether a closing slide has a picture, and a question that fits beside it (without a word too long for the
    side: a closing slide with one has its picture above it)."""
    return "photo" in roles and _beside_title(roles)


def _has(role: str) -> Callable[[dict[str, Content]], bool]:
    def has(roles: dict[str, Content]) -> bool:
        return role in roles

    return has


def _plain(fits: Callable[[dict[str, Content]], bool]) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide has no picture behind it (a big number's: D63), and fits."""

    def plain(roles: dict[str, Content]) -> bool:
        return "background" not in roles and fits(roles)

    return plain


def _pictured(fits: Callable[[dict[str, Content]], bool]) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide has a picture to put behind it or beside it (a big number's: D63), and fits."""

    def pictured(roles: dict[str, Content]) -> bool:
        return "background" in roles and fits(roles)

    return pictured


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


# A big number or KPI tiles over a picture of what they're about (D63: the user found slides of text boring): the
# picture behind everything under a statement's shade, and the texts that aren't on a tile of their own light, as they
# read on it whatever the picture is; or on a band across it; or the picture filling the slide's right side, and the
# texts beside it on the theme's background
_SHADED: Final = tuple(color.mix(extreme, SHADE, SHADE_OPACITY) for extreme in ("#000000", "#ffffff"))
_SIDE_PHOTO: Final = 820  # the width of a picture that fills a slide's right side


def _backdrop(placement: Placement, roles: dict[str, Content]) -> bool:
    """Whether the slide has a picture behind it (its background, which the engine puts behind everything): then the
    shade goes over it, first of the layout's shapes."""
    if not isinstance(roles.get("background"), ImageElement):
        return False
    placement.shapes.insert(0, _shade())
    return True


def _heading(placement: Placement, roles: dict[str, Content], theme: Theme, photo: bool) -> float:
    """The title (if any) across the top, with the theme's decoration, or over a shaded picture in a light colour and
    without it; where the content can start below it."""
    if "title" not in roles:
        return MARGIN
    if not photo:
        return _with_title(placement, roles, theme)
    placement.boxes["title"] = (_TITLE, "photo title")
    return _CONTENT_TOP


def _big_number(roles: dict[str, Content], theme: Theme) -> Placement:
    """The number big in the middle, in the theme's accent, with what it counts under it and its source below; over
    its picture, if it has one, shaded, with the number in the accent made light enough to read on the shade, and the
    rest light."""
    placement = Placement("v5/big-number")
    photo = _backdrop(placement, roles)
    top = _heading(placement, roles, theme, photo)
    bottom = _CONTENT_BOTTOM - (72 if "source" in roles else 0)
    number_height = round((bottom - top) * 0.58)
    width = WIDTH - 2 * MARGIN
    number = Box(x=MARGIN, y=top, w=width, h=number_height)
    placement.boxes["number"] = (number, "photo number" if photo else "big number")
    if photo:
        placement.colors["number"] = color.readable_on(theme.palette.accent, _SHADED, color.LARGE_TEXT_CONTRAST)
    label_top = top + number_height + 16
    label = Box(x=MARGIN + 120, y=label_top, w=width - 240, h=bottom - label_top)
    placement.boxes["label"] = (label, "photo label" if photo else "number label")
    if "source" in roles:
        source = Box(x=MARGIN, y=bottom + 16, w=width, h=56)
        placement.boxes["source"] = (source, "photo source" if photo else "source")
    return placement


def _big_number_band(roles: dict[str, Content], theme: Theme) -> Placement:
    """The picture over the whole slide, shaded, and the number with what it counts on a band across its middle, in
    the theme's colours, as a statement's band has them; the title above it and the source below it, light."""
    surface = theme.palette.surface
    band_box = Box(x=0, y=250, w=WIDTH, h=600)
    band = ShapeElement(role="number band", box=band_box, color=surface, opacity=BAND_OPACITY)
    placement = Placement("v5/big-number-band", shapes=[_shade()], overlays=[band])
    on_band = [color.mix(shaded, surface, BAND_OPACITY) for shaded in _SHADED]
    if "title" in roles:
        placement.boxes["title"] = (Box(x=MARGIN, y=72, w=WIDTH - 2 * MARGIN, h=150), "photo title")
    width = WIDTH - 2 * MARGIN
    placement.boxes["number"] = (Box(x=MARGIN, y=band_box.y + 24, w=width, h=330), "band number")
    placement.colors["number"] = color.readable_on(theme.palette.accent, on_band, color.LARGE_TEXT_CONTRAST)
    label_top = band_box.y + 24 + 330 + 12
    label = Box(x=MARGIN + 120, y=label_top, w=width - 240, h=band_box.y + band_box.h - 24 - label_top)
    placement.boxes["label"] = (label, "band label")
    placement.colors["label"] = _on(on_band, theme)
    if "source" in roles:
        placement.boxes["source"] = (Box(x=MARGIN, y=band_box.y + band_box.h + 24, w=width, h=64), "photo source")
    return placement


def _big_number_side(roles: dict[str, Content], theme: Theme) -> Placement:
    """The picture filling the slide's right side, and the number beside it, aligned left, in the theme's accent,
    with what it counts and its source under it, and the title (if any) above it, on the theme's background."""
    placement = Placement("v5/big-number-side", photo=True)  # (a picture to the slide's edges: none of a box's frame)
    picture_x = WIDTH - _SIDE_PHOTO
    placement.boxes["background"] = (Box(x=picture_x, y=0, w=_SIDE_PHOTO, h=HEIGHT), "quote")
    width = picture_x - MARGIN - 80
    top = 120.0
    if "title" in roles:
        title = Box(x=MARGIN, y=top, w=width, h=220)
        placement.boxes["title"] = (title, "side title")
        placement.shapes += _decoration(_left_aligned(theme), title, gap=12)
        top += 250
    bottom = _CONTENT_BOTTOM - (80 if "source" in roles else 0)
    number_height = round((bottom - top) * 0.5)
    placement.boxes["number"] = (Box(x=MARGIN, y=top, w=width, h=number_height), "side number")
    label_top = top + number_height + 16
    placement.boxes["label"] = (Box(x=MARGIN, y=label_top, w=width, h=bottom - label_top), "side label")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=MARGIN, y=bottom + 16, w=width, h=56), "side source")
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
    measures beside it. (A figure comes with its band, on its click.) Over their picture, if they have one, shaded,
    with the title light (as on every KPI layout: their tiles read on anything)."""
    placement = Placement("v5/kpi-rows")
    top = _heading(placement, roles, theme, _backdrop(placement, roles)) + 8
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
    top = _heading(placement, roles, theme, _backdrop(placement, roles)) + 24
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
    top = _heading(placement, roles, theme, _backdrop(placement, roles)) + 24
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


def _badge(placement: Placement, theme: Theme, role: str, badge: Box, click: int | None = None) -> None:
    """A short text (an option's letter, an item's number) on a badge, a disc in the theme's accent (appearing with
    the text, on its click)."""
    accent = theme.palette.accent
    disc = ShapeElement(role=f"{role} badge", shape="ellipse", box=badge, color=accent, appears_on_click=click)
    placement.shapes.append(disc)
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
        badge = Box(x=MARGIN, y=y + 12, w=diameter, h=diameter)
        _badge(placement, theme, f"letter_{index}", badge, _click(roles, f"letter_{index}"))
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
        appears = _click(roles, f"option_{index}")  # (the option's tile comes with it)
        tile = Box(x=x, y=y, w=width, h=height)
        placement.shapes.append(
            ShapeElement(role=f"tile_{index}", box=tile, color=palette.surface, appears_on_click=appears)
        )
        diameter = min(112.0, height - 56)
        badge = Box(x=x + 28, y=y + (height - diameter) / 2, w=diameter, h=diameter)
        _badge(placement, theme, f"letter_{index}", badge, _click(roles, f"letter_{index}"))
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
        badge = Box(x=x, y=y + 12, w=diameter, h=diameter)
        _badge(placement, theme, f"number_{index}", badge, _click(roles, f"number_{index}"))
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
        badge = Box(x=x + (width - diameter) / 2, y=top, w=diameter, h=diameter)
        _badge(placement, theme, f"number_{index}", badge, _click(roles, f"number_{index}"))
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


def _references(left: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """An academic talk's references: its works one under the other, each after its number as cited ("[1]"), and a
    picture of one of them (a book's cover, a paper's figure), if it has one, beside them (on the right, or left), as
    large as it fits whole, with its caption right under it."""

    def references(roles: dict[str, Content], theme: Theme) -> Placement:
        placement = Placement("v5/references-left" if left else "v5/references")
        top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 8
        figure = roles.get("figure")
        picture_width = 680.0 if isinstance(figure, ImageElement) else 0.0
        x0 = MARGIN + picture_width + 64 if picture_width and left else MARGIN
        x1 = WIDTH - MARGIN - picture_width - 64 if picture_width and not left else WIDTH - MARGIN
        works = _numbered(roles, "item", 5)
        y, height = _spread(top, _CONTENT_BOTTOM, len(works), 16, 130)
        for index in works:
            placement.boxes[f"number_{index}"] = (Box(x=x0, y=y, w=100, h=height), "citation")
            placement.boxes[f"item_{index}"] = (Box(x=x0 + 124, y=y, w=x1 - x0 - 124, h=height), "reference")
            y += height + 16
        if isinstance(figure, ImageElement):
            caption = 64.0 if "caption" in roles else 0.0
            area = Box(
                x=MARGIN if left else WIDTH - MARGIN - picture_width,
                y=top,
                w=picture_width,
                h=_CONTENT_BOTTOM - top - caption,
            )
            shown = _whole(figure, area)
            placement.boxes["figure"] = (shown, "quote")
            if caption:
                below = Box(x=area.x, y=shown.y + shown.h + 12, w=area.w, h=caption - 12)
                placement.boxes["caption"] = (below, "figure caption")
        return placement

    return references


def _whole(picture: ImageElement, area: Box) -> Box:
    """Where a picture shows whole in an area, as large as it fits, in its middle (filling the area when its size
    isn't known)."""
    width, height = picture.image.width, picture.image.height
    if not width or not height:
        return area
    scale = min(area.w / width, area.h / height)
    shown_w, shown_h = width * scale, height * scale
    return Box(x=area.x + (area.w - shown_w) / 2, y=area.y + (area.h - shown_h) / 2, w=shown_w, h=shown_h)


def _questions_photo(roles: dict[str, Content], theme: Theme) -> Placement:
    """The question and its subtitle on the left, and the picture to end on (a funny one, or an earlier slide's,
    called back) large on the right."""
    placement = Placement("v5/questions-photo")
    photo = Box(x=WIDTH - MARGIN - 880, y=110, w=880, h=820)
    placement.boxes["photo"] = (photo, "quote")
    width = photo.x - 64 - MARGIN
    title = Box(x=MARGIN, y=170, w=width, h=440)
    placement.boxes["title"] = (title, "left title")
    placement.shapes += _decoration(_left_aligned(theme), title, gap=16)
    placement.boxes["subtitle"] = (Box(x=MARGIN, y=660, w=width, h=270), "left subtitle")
    return placement


def _questions_banner(roles: dict[str, Content], theme: Theme) -> Placement:
    """The picture to end on across the top, and the question big under it, with the subtitle below."""
    placement = Placement("v5/questions-banner")
    banner = Box(x=MARGIN, y=56, w=WIDTH - 2 * MARGIN, h=520)
    placement.boxes["photo"] = (banner, "quote")
    title = Box(x=160, y=banner.y + banner.h + 40, w=WIDTH - 320, h=230)
    placement.boxes["title"] = (title, "centred title")
    placement.boxes["subtitle"] = (Box(x=160, y=title.y + title.h + 12, w=WIDTH - 320, h=120), "centred subtitle")
    return placement


# Native diagrams: a timeline, a pyramid and a funnel, a cycle, a small org chart and an iceberg; and the pictures some
# of their boxes have now and then (docs/v5-plan.md, D64), cropped to fill a box of their own beside the box's text
# (or in it), which appear with the text

_PICTURE_GAP: Final = 16.0
_PICTURE_SHAPE: Final = 4 / 3  # (a picture's box, as wide as it's tall times this, where it can be)
_SMALLEST_PICTURE: Final = 96.0  # (a picture's box is at least this tall and wide, or the picture stays out)


def _picture_role(box: str) -> str:
    """The role of the picture of a diagram's box (see talkgenerator.slide.slides.picture_role)."""
    return f"{box}_picture"


def _has_picture(roles: dict[str, Content], box: str) -> bool:
    return isinstance(roles.get(_picture_role(box)), ImageElement)


def _picture_box(area: Box, shape: float = _PICTURE_SHAPE) -> Box | None:
    """The largest box of the shape (its width over its height) in the middle of the area, if it's large enough."""
    width = min(area.w, area.h * shape)
    height = width / shape
    if min(width, height) < _SMALLEST_PICTURE:
        return None
    return Box(x=area.x + (area.w - width) / 2, y=area.y + (area.h - height) / 2, w=width, h=height)


def _place_picture(placement: Placement, box: str, area: Box | None) -> bool:
    """Put the picture of the box (if the slide has one, and the area is large enough for it) in the area."""
    if area is None:
        return False
    placement.boxes[_picture_role(box)] = (area, "caption")
    return True


def _picture_inside(placement: Placement, roles: dict[str, Content], box: str, text: Box, side: str) -> Box:
    """The box's picture, if it has one, at one end of its text's box (left or right, in a box as tall as it), and
    where the text goes then: the rest of the box."""
    if not _has_picture(roles, box):
        return text
    picture = _picture_box(Box(x=text.x, y=text.y, w=min(text.w * 0.45, text.h * _PICTURE_SHAPE), h=text.h))
    if picture is None:
        return text
    if side == "right":
        picture = picture.model_copy(update={"x": text.x + text.w - picture.w})
    else:
        picture = picture.model_copy(update={"x": text.x})
    _place_picture(placement, box, picture)
    rest = text.w - picture.w - _PICTURE_GAP
    return Box(x=text.x if side == "right" else text.x + picture.w + _PICTURE_GAP, y=text.y, w=rest, h=text.h)


def _dot(
    role: str, centre: tuple[float, float], diameter: float, colour: str, click: int | None = None
) -> ShapeElement:
    x, y = centre
    box = Box(x=x - diameter / 2, y=y - diameter / 2, w=diameter, h=diameter)
    return ShapeElement(role=role, shape="ellipse", box=box, color=colour, appears_on_click=click)


def _timeline(roles: dict[str, Content], theme: Theme) -> Placement:
    """The moments side by side along a line in the theme's accent, oldest first: a dot on the line for each (the
    last one's, the punchline's, in the second accent), appearing with it, its date above it and what happened under
    it."""
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
        colour = palette.accent_2 if index == moments[-1] else palette.accent
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
        colour = palette.accent_2 if index == moments[-1] else palette.accent
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
    punchline's (a pyramid's top, a funnel's bottom) in its second accent; each appearing with its text."""

    def stack(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement(name)
        left, right, top = _area(placement, roles, theme, side)
        items = _numbered(roles, prefix, most)
        punchline = (items[0] if widening else items[-1]) if items else None
        gap = 12
        y, height = _spread(top + 24, _CONTENT_BOTTOM, len(items), gap, 170)
        widest = min(1500.0, right - left)
        narrowest = 460.0  # (wide enough for a long word at the top of a pyramid, or at the bottom of a funnel)
        for position, index in enumerate(items):
            share = position / max(1, len(items) - 1)  # (from 0 at the top to 1 at the bottom)
            width = narrowest + (widest - narrowest) * (share if widening else 1 - share)
            click = _click(roles, f"{prefix}_{index}")
            shade = color.mix(palette.accent, palette.background, 0.2 * share)
            fill = palette.accent_2 if index == punchline else shade
            band = Box(x=(left + right - width) / 2, y=y, w=width, h=height)
            placement.shapes.append(
                ShapeElement(role=f"{prefix} {index} band", box=band, color=fill, appears_on_click=click)
            )
            text = Box(x=band.x + 24, y=y + 8, w=width - 48, h=height - 16)
            # (a band's picture beside it, where the stack leaves room on its right; else in it, at its right end)
            beside = Box(x=band.x + band.w + _PICTURE_GAP, y=y, w=right - band.x - band.w - _PICTURE_GAP, h=height)
            if _has_picture(roles, f"{prefix}_{index}") and not _place_picture(
                placement, f"{prefix}_{index}", _beside_picture(beside)
            ):
                text = _picture_inside(placement, roles, f"{prefix}_{index}", text, "right")
            placement.boxes[f"{prefix}_{index}"] = (text, "level")
            placement.colors[f"{prefix}_{index}"] = _on([fill], theme)
            y += height + gap
        return placement

    return stack


def _beside_picture(area: Box) -> Box | None:
    """A picture's box at the left end of the area (as tall as it, and as wide as that allows), if it's large
    enough."""
    picture = _picture_box(area.model_copy(update={"w": min(area.w, area.h * _PICTURE_SHAPE)}))
    return picture.model_copy(update={"x": area.x}) if picture is not None else None


def _cycle(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """The steps on ovals in the theme's accent around a ring of dots, clockwise from the top: each leads to the next,
    and the last back to the first; each oval appears with its step. (Ovals, wide enough for a long word, on an oval
    ring as wide as there's room.)"""

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
        ovals = []
        for position, index in enumerate(steps):
            x, y = on_ring(2 * math.pi * position / len(steps))
            oval = Box(x=x - width / 2, y=y - height / 2, w=width, h=height)
            ovals.append(oval)
            click = _click(roles, f"step_{index}")
            placement.shapes.append(
                ShapeElement(role=f"step {index} oval", shape="ellipse", box=oval, color=accent, appears_on_click=click)
            )
            text = Box(x=x - 0.4 * width, y=y - 0.27 * height, w=0.8 * width, h=0.54 * height)
            placement.boxes[f"step_{index}"] = (text, "disc")
            placement.colors[f"step_{index}"] = _on([accent], theme)
        # (a step's picture in the middle of the ring, as large as it is clear of the ovals)
        for index in steps:
            if _has_picture(roles, f"step_{index}"):
                _place_picture(placement, f"step_{index}", _clear_of(middle, ovals))
                break
        return placement

    return cycle


def _clear_of(middle: tuple[float, float], boxes: Sequence[Box], largest: float = 300.0) -> Box | None:
    """The largest picture's box (at most so tall) around the point that keeps clear of the boxes (by a gap), if
    it's large enough."""
    height = largest
    while height >= _SMALLEST_PICTURE:
        width = height * _PICTURE_SHAPE
        picture = Box(x=middle[0] - width / 2, y=middle[1] - height / 2, w=width, h=height)
        if not any(_overlap(_inset(picture, -_PICTURE_GAP), box) for box in boxes):
            return picture
        height *= 0.9
    return None


def _org_chart(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """Who's in charge, on a box in the theme's accent at the top, joined by lines to the people under them, on
    boxes in its surface colour: each box (and a report's line to it) appearing with its text."""

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
            click = _click(roles, f"report_{index}")
            down = Box(x=x + width / 2 - 3, y=joint, w=6, h=drop)
            placement.shapes.append(ShapeElement(role="line", box=down, color=ink, appears_on_click=click))
            report = Box(x=x, y=row, w=width, h=box_height)
            placement.shapes.append(
                ShapeElement(role=f"report {index} box", box=report, color=palette.surface, appears_on_click=click)
            )
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
    through): what everyone sees on its tip, above the water, and what's under it, below (each on a click)."""

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
        tip = Box(x=centre - 240, y=water - 200, w=480, h=160)
        placement.boxes["tip"] = (tip, "box")
        placement.colors["tip"] = _on([palette.surface], theme)
        # (the tip's picture beside it, on its right; a hidden thing's beside it too, on the ice under the water)
        beside = Box(x=tip.x + tip.w + _PICTURE_GAP, y=tip.y, w=right - tip.x - tip.w - _PICTURE_GAP, h=tip.h)
        _place_picture(placement, "tip", _beside_picture(beside) if _has_picture(roles, "tip") else None)
        hidden = _numbered(roles, "hidden", 3)
        y, height = _spread(water + 48, _CONTENT_BOTTOM, len(hidden), 16, 130)
        under = color.mix(palette.surface, palette.accent, opacity)
        label = min(720.0, 0.66 * width)
        for index in hidden:
            text = Box(x=centre - label / 2, y=y, w=label, h=height)
            placement.boxes[f"hidden_{index}"] = (text, "box")
            placement.colors[f"hidden_{index}"] = _on([under], theme)
            if _has_picture(roles, f"hidden_{index}"):
                room = Box(
                    x=text.x + text.w + _PICTURE_GAP,
                    y=y,
                    w=ice.x + ice.w - text.x - text.w - 2 * _PICTURE_GAP,
                    h=height,
                )
                _place_picture(placement, f"hidden_{index}", _beside_picture(room))
            y += height + 16
        return placement

    return iceberg


# The talk formats' (docs/v5-plan.md, section 7): a process, such as an academic talk's method or how a pitch's
# product works

# How long a word of a process's steps may be for them to go side by side, by how many steps there are (a longer one,
# as German and Dutch compounds are, gets the steps one under the other)
_ACROSS_WORDS: Final = {3: 20, 4: 15, 5: 12}


def _arrow(role: str, box: Box, down: bool, colour: str, click: int | None) -> ShapeElement:
    """An arrowhead in the box, pointing down or to the right."""
    points = ((0.0, 0.0), (1.0, 0.0), (0.5, 1.0)) if down else ((0.0, 0.0), (1.0, 0.5), (0.0, 1.0))
    return ShapeElement(role=role, shape="polygon", points=points, box=box, color=colour, appears_on_click=click)


def _process_steps(roles: dict[str, Content], theme: Theme) -> tuple[list[int], str, str, str]:
    """A process's steps, the colour of its arrows, of its steps and of its last step (the punchline)."""
    palette = theme.palette
    ink = color.readable_on(palette.muted, _backgrounds(theme), LINE_CONTRAST)
    return _numbered(roles, "step", 5), ink, palette.accent, palette.accent_2


def _process_down(roles: dict[str, Content], theme: Theme) -> Placement:
    """The steps one under the other, on bands in the theme's accent (the last one, the punchline, in its second
    accent), each led to by an arrow from the one above it; a step's band and its arrow appear with it."""
    placement = Placement("v5/process")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 16
    steps, ink, fill, last = _process_steps(roles, theme)
    gap = 48.0
    y, height = _spread(top, _CONTENT_BOTTOM, len(steps), gap, 150)
    width = min(1300.0, WIDTH - 2 * MARGIN)
    x = (WIDTH - width) / 2
    for position, index in enumerate(steps):
        click = _click(roles, f"step_{index}")
        colour = last if position == len(steps) - 1 else fill
        band = Box(x=x, y=y, w=width, h=height)
        if position:
            head = Box(x=WIDTH / 2 - 32, y=y - gap + 8, w=64, h=gap - 16)
            placement.shapes.append(_arrow(f"step {index} arrow", head, True, ink, click))
        placement.shapes.append(ShapeElement(role=f"step {index} band", box=band, color=colour, appears_on_click=click))
        text = Box(x=band.x + 24, y=y + 8, w=width - 48, h=height - 16)
        # (a step's picture beside its band, on its right, where there's room; else in it, at its right end)
        beside = Box(x=band.x + band.w + _PICTURE_GAP, y=y, w=WIDTH - MARGIN - band.x - band.w - _PICTURE_GAP, h=height)
        if _has_picture(roles, f"step_{index}") and not _place_picture(
            placement, f"step_{index}", _beside_picture(beside)
        ):
            text = _picture_inside(placement, roles, f"step_{index}", text, "right")
        placement.boxes[f"step_{index}"] = (text, "level")
        placement.colors[f"step_{index}"] = _on([colour], theme)
        y += height + gap
    return placement


def _process_across(roles: dict[str, Content], theme: Theme) -> Placement:
    """The steps side by side, from left to right, on boxes in the theme's accent (the last one, the punchline, in its
    second accent), each led to by an arrow from the one on its left; a step's box and its arrow appear with it."""
    placement = Placement("v5/process-across")
    top = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    steps, ink, fill, last = _process_steps(roles, theme)
    gap = 64.0
    width = (WIDTH - 2 * MARGIN - gap * (len(steps) - 1)) / len(steps)
    height = min(340.0, _CONTENT_BOTTOM - top - 48)
    y = top + (_CONTENT_BOTTOM - top - height) / 2
    for position, index in enumerate(steps):
        click = _click(roles, f"step_{index}")
        colour = last if position == len(steps) - 1 else fill
        x = MARGIN + position * (width + gap)
        if position:
            head = Box(x=x - gap + 14, y=y + height / 2 - 28, w=gap - 28, h=56)
            placement.shapes.append(_arrow(f"step {index} arrow", head, False, ink, click))
        box = Box(x=x, y=y, w=width, h=height)
        placement.shapes.append(ShapeElement(role=f"step {index} box", box=box, color=colour, appears_on_click=click))
        text = _inset(box, 18)
        if _has_picture(roles, f"step_{index}"):  # (a step's picture in the top half of its box, its text under it)
            upper = Box(x=text.x, y=text.y, w=text.w, h=(text.h - _PICTURE_GAP) / 2)
            if _place_picture(placement, f"step_{index}", _picture_box(upper)):
                text = Box(x=text.x, y=upper.y + upper.h + _PICTURE_GAP, w=text.w, h=upper.h)
        placement.boxes[f"step_{index}"] = (text, "box")
        placement.colors[f"step_{index}"] = _on([colour], theme)
    return placement


def _short_steps(roles: dict[str, Content]) -> bool:
    """Whether a process's steps can go side by side: three to five, each without a word too long for its box."""
    steps = [roles[f"step_{index}"] for index in _numbered(roles, "step", 5)]
    longest = _ACROSS_WORDS.get(len(steps))
    return longest is not None and all(
        isinstance(step, TextElement) and all(len(word) <= longest for word in step.text.split()) for step in steps
    )


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
        if box.style == "plain":  # (the label comes with its caption)
            fill = box.fill or "#ffffff"
            label = ShapeElement(role=f"{role} label", box=place, color=fill, appears_on_click=_click(roles, role))
            placement.overlays.append(label)
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


# SLIDE TYPES FROM POWERPOINT KARAOKE DECKS (docs/v5-plan.md, section 8): texts on shapes, and a photo
_FACT_PHOTO_WIDTH: Final = 760  # a fun fact's photo beside it


def _sticker(placement: Placement, theme: Theme, box: Box, role: str = "kicker") -> None:
    """A short heading (a fun fact's "Did you know?") on a sticker in the theme's accent, drawn over a picture it may
    overlap."""
    accent = theme.palette.accent
    placement.overlays.append(ShapeElement(role=f"{role} sticker", box=box, color=accent))
    placement.boxes[role] = (_inset(box, 16), "sticker")
    placement.colors[role] = _on([accent], theme, color.LARGE_TEXT_CONTRAST)


def _fun_fact(roles: dict[str, Content], theme: Theme) -> Placement:
    """The fact big in the middle, under its heading on a sticker in the theme's accent, its source under it; with a
    photo, the photo on the right and the rest beside it, aligned left."""
    placement = Placement("v5/fun-fact")
    photo = "photo" in roles
    right = WIDTH - MARGIN - (_FACT_PHOTO_WIDTH + _GAP if photo else 0)
    width = right - MARGIN
    if photo:
        photo_box = Box(x=WIDTH - MARGIN - _FACT_PHOTO_WIDTH, y=MARGIN, w=_FACT_PHOTO_WIDTH, h=_CONTENT_BOTTOM - MARGIN)
        placement.boxes["photo"] = (photo_box, "quote")
    sticker_width = min(640.0, width)
    sticker_x = MARGIN if photo else (WIDTH - sticker_width) / 2
    _sticker(placement, theme, Box(x=sticker_x, y=150, w=sticker_width, h=116))
    top = 150 + 116 + 40
    bottom = _CONTENT_BOTTOM - (96 if "source" in roles else 0)
    placement.boxes["fact"] = (Box(x=MARGIN, y=top, w=width, h=bottom - top), "side fact" if photo else "fact")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=MARGIN, y=bottom + 24, w=width, h=64), "side source" if photo else "source")
    return placement


def _fun_fact_card(roles: dict[str, Content], theme: Theme) -> Placement:
    """The fact on a card in the theme's second accent, as on a sticky note, with a shadow: its heading on a sticker
    over the card's top edge, its source at the card's foot."""
    palette = theme.palette
    card = Box(x=400, y=200, w=1120, h=720)
    shadow = Box(x=card.x + 20, y=card.y + 20, w=card.w, h=card.h)
    fill = palette.accent_2
    placement = Placement(
        "v5/fun-fact-card",
        shapes=[
            ShapeElement(role="card shadow", box=shadow, color=color.mix(palette.background, palette.text, 0.25)),
            ShapeElement(role="card", box=card, color=fill),
        ],
    )
    _sticker(placement, theme, Box(x=card.x - 40, y=card.y - 58, w=600, h=116))
    inner = _inset(card, 64)
    bottom = inner.y + inner.h - (72 if "source" in roles else 0)
    placement.boxes["fact"] = (Box(x=inner.x, y=card.y + 96, w=inner.w, h=bottom - card.y - 96), "card fact")
    ink = _on([fill], theme)
    placement.colors["fact"] = ink
    if "source" in roles:
        placement.boxes["source"] = (Box(x=inner.x, y=bottom + 16, w=inner.w, h=56), "card source")
        placement.colors["source"] = ink
    return placement


def _fun_fact_banner(roles: dict[str, Content], theme: Theme) -> Placement:
    """The photo across the top, its heading on a sticker over its lower edge, and the fact under it, with its
    source below."""
    placement = Placement("v5/fun-fact-banner")
    banner = Box(x=MARGIN, y=56, w=WIDTH - 2 * MARGIN, h=470)
    placement.boxes["photo"] = (banner, "quote")
    _sticker(placement, theme, Box(x=MARGIN + 48, y=banner.y + banner.h - 64, w=600, h=116))
    top = banner.y + banner.h + 52 + 24
    bottom = _CONTENT_BOTTOM - (80 if "source" in roles else 0)
    placement.boxes["fact"] = (Box(x=MARGIN, y=top, w=WIDTH - 2 * MARGIN, h=bottom - top), "side fact")
    if "source" in roles:
        placement.boxes["source"] = (Box(x=MARGIN, y=bottom + 16, w=WIDTH - 2 * MARGIN, h=56), "side source")
    return placement


def _without(role: str) -> Callable[[dict[str, Content]], bool]:
    def without(roles: dict[str, Content]) -> bool:
        return role not in roles

    return without


def _acronym_rows(roles: dict[str, Content], theme: Theme) -> Placement:
    """The acronym down the slide: every letter on a tile in the theme's accent, the word it stands for beside it."""
    accent = theme.palette.accent
    placement = Placement("v5/acronym")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 8
    words = _numbered(roles, "word", 6)
    y, height = _spread(top, _CONTENT_BOTTOM, len(words), 16, 150)
    ink = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    for index in words:
        tile = Box(x=MARGIN + 40, y=y, w=height, h=height)
        placement.shapes.append(ShapeElement(role=f"letter {index} tile", box=tile, color=accent))
        placement.boxes[f"letter_{index}"] = (_inset(tile, height * 0.12), "tile letter")
        placement.colors[f"letter_{index}"] = ink
        word_x = tile.x + tile.w + 48
        placement.boxes[f"word_{index}"] = (Box(x=word_x, y=y, w=WIDTH - MARGIN - word_x, h=height), "acronym word")
        y += height + 16
    return placement


def _acronym_across(roles: dict[str, Content], theme: Theme) -> Placement:
    """The acronym across the slide, its letters big on tiles in the theme's accent, every word under its letter."""
    accent = theme.palette.accent
    placement = Placement("v5/acronym-across")
    start = _with_title(placement, roles, theme) if "title" in roles else MARGIN
    words = _numbered(roles, "word", 6)
    gap = 32
    width = (WIDTH - 2 * MARGIN - gap * (len(words) - 1)) / len(words)
    size = min(260.0, width)
    word_height = 220.0
    top = start + (_CONTENT_BOTTOM - start - (size + 32 + word_height)) / 2
    ink = _on([accent], theme, color.LARGE_TEXT_CONTRAST)
    for position, index in enumerate(words):
        x = MARGIN + position * (width + gap)
        tile = Box(x=x + (width - size) / 2, y=top, w=size, h=size)
        placement.shapes.append(ShapeElement(role=f"letter {index} tile", box=tile, color=accent))
        placement.boxes[f"letter_{index}"] = (_inset(tile, size * 0.12), "tile letter")
        placement.colors[f"letter_{index}"] = ink
        placement.boxes[f"word_{index}"] = (Box(x=x, y=top + size + 32, w=width, h=word_height), "column word")
    return placement


def _few_short_words(roles: dict[str, Content]) -> bool:
    """Whether an acronym has at most five words, none longer than twelve letters (to fit under its letter)."""
    words = [roles[f"word_{index}"] for index in _numbered(roles, "word", 6)]
    return len(words) <= 5 and all(
        isinstance(word, TextElement) and all(len(part) <= 12 for part in word.text.split()) for word in words
    )


def _dare_card(roles: dict[str, Content], theme: Theme) -> Placement:
    """The dare big on a card in the theme's surface colour, edged in its accent, under its heading on a sticker."""
    palette = theme.palette
    card = Box(x=260, y=250, w=1400, h=640)
    placement = Placement(
        "v5/dare",
        shapes=[
            ShapeElement(role="card edge", box=_inset(card, -10), color=palette.accent),
            ShapeElement(role="card", box=card, color=palette.surface),
        ],
    )
    _sticker(placement, theme, Box(x=(WIDTH - 640) / 2, y=card.y - 70, w=640, h=120))
    placement.boxes["dare"] = (Box(x=card.x + 80, y=card.y + 90, w=card.w - 160, h=card.h - 150), "dare")
    placement.colors["dare"] = _on([palette.surface], theme)
    return placement


def _dare_tape(roles: dict[str, Content], theme: Theme) -> Placement:
    """The dare between two bands of warning tape (blocks in the theme's accent and text colour), its heading big in
    the accent above it."""
    palette = theme.palette
    placement = Placement("v5/dare-tape")
    block = 160.0
    for band_y in (72.0, 868.0):
        for number in range(math.ceil(WIDTH / block)):
            fill = palette.accent if number % 2 == 0 else palette.text
            box = Box(x=number * block, y=band_y, w=min(block, WIDTH - number * block), h=56)
            placement.shapes.append(ShapeElement(role="tape", box=box, color=fill))
    placement.boxes["kicker"] = (Box(x=MARGIN, y=176, w=WIDTH - 2 * MARGIN, h=170), "dare kicker")
    placement.boxes["dare"] = (Box(x=200, y=370, w=WIDTH - 400, h=450), "open dare")
    return placement


def _flowchart(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """A yes-or-no question on an oval in the theme's accent at the top; lines down to where each answer leads (Yes
    on the left, No on the right), on boxes in its surface colour; and lines from both down to the same end, on a box
    in its second accent. Each answer's way (its label, line and box) appears with its step, and the lines to the end
    with the end."""

    def flowchart(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/flowchart-side" if side else "v5/flowchart")
        left, right, top = _area(placement, roles, theme, side)
        width, centre = right - left, (left + right) / 2
        ink = color.readable_on(palette.muted, _backgrounds(theme), LINE_CONTRAST)
        oval_height, step_height, end_height = 160.0, 150.0, 150.0
        total = oval_height + 40 + 80 + step_height + 40 + 50 + end_height
        y = top + 16 + max(0.0, (_CONTENT_BOTTOM - top - 16 - total) / 2)
        oval_width = min(900.0, width - 40)
        oval = Box(x=centre - oval_width / 2, y=y, w=oval_width, h=oval_height)
        placement.shapes.append(ShapeElement(role="question oval", shape="ellipse", box=oval, color=palette.accent))
        placement.boxes["question"] = (
            Box(x=oval.x + 0.1 * oval.w, y=oval.y + 0.17 * oval.h, w=0.8 * oval.w, h=0.66 * oval.h),
            "flow question",
        )
        placement.colors["question"] = _on([palette.accent], theme)
        step_width = min(620.0, width / 2 - 40)
        branch = width / 4 + 10
        split = oval.y + oval.h + 40
        steps = split + 80
        joint = steps + step_height + 40
        end_top = joint + 50

        def line(x: float, y: float, w: float, h: float, click: int | None = None) -> None:
            box = Box(x=x, y=y, w=w, h=h)
            placement.shapes.append(ShapeElement(role="line", box=box, color=ink, appears_on_click=click))

        line(centre - 3, oval.y + oval.h, 6, split - oval.y - oval.h + 3)
        line(centre - branch - 3, split - 3, 2 * branch + 6, 6)
        line(centre - branch - 3, joint - 3, 2 * branch + 6, 6, _click(roles, "end"))
        line(centre - 3, joint, 6, end_top - joint, _click(roles, "end"))
        for role, x, label, spec in (
            ("yes_step", centre - branch, "yes", "flow label"),
            ("no_step", centre + branch, "no", "flow label right"),
        ):
            click = _click(roles, role)
            line(x - 3, split, 6, steps - split, click)
            line(x - 3, steps + step_height, 6, joint - steps - step_height, click)
            box = Box(x=x - step_width / 2, y=steps, w=step_width, h=step_height)
            placement.shapes.append(
                ShapeElement(role=f"{role} box", box=box, color=palette.surface, appears_on_click=click)
            )
            # (a step's picture in its box, at its outer end: Yes's on the left, No's on the right)
            outer = "left" if role == "yes_step" else "right"
            placement.boxes[role] = (_picture_inside(placement, roles, role, _inset(box, 16), outer), "flow step")
            placement.colors[role] = _on([palette.surface], theme)
            label_x = x + 20 if spec == "flow label" else x - 20 - 200
            placement.boxes[label] = (Box(x=label_x, y=split + 12, w=200, h=steps - split - 18), spec)
        end_width = min(760.0, width - 80)
        end = Box(x=centre - end_width / 2, y=end_top, w=end_width, h=end_height)
        click = _click(roles, "end")
        placement.shapes.append(ShapeElement(role="end box", box=end, color=palette.accent_2, appears_on_click=click))
        placement.boxes["end"] = (_picture_inside(placement, roles, "end", _inset(end, 18), "right"), "boss")
        placement.colors["end"] = _on([palette.accent_2], theme)  # (a long end is no large text)
        return placement

    return flowchart


# A tier list's tiers' colours, as tier lists have them (red for the best, to blue for the worst)
_TIER_COLOURS: Final = {"s": "#ff7f7f", "a": "#ffbf7f", "b": "#ffdf7f", "c": "#ffff7f", "f": "#7fbfff"}


def _tier_list(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """The tiers one under the other, best first: each tier's letter on a tile in its colour, and its things side by
    side on a band in the theme's surface colour (a tier's things on a click of their own, from the worst tier up to
    the S tier)."""

    def tier_list(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/tier-list-side" if side else "v5/tier-list")
        left, right, top = _area(placement, roles, theme, side)
        tiers = [tier for tier in "sabcf" if f"tier_{tier}" in roles]
        y, height = _spread(top + 16, _CONTENT_BOTTOM, len(tiers), 12, 150)
        on_band = _on([palette.surface], theme)
        for tier in tiers:
            fill = _TIER_COLOURS[tier]
            tile = Box(x=left, y=y, w=height, h=height)
            placement.shapes.append(ShapeElement(role=f"tier {tier} tile", box=tile, color=fill))
            placement.boxes[f"tier_{tier}"] = (_inset(tile, height * 0.14), "tile letter")
            placement.colors[f"tier_{tier}"] = _on([fill], theme, color.LARGE_TEXT_CONTRAST)
            band = Box(x=tile.x + tile.w + 12, y=y, w=right - tile.x - tile.w - 12, h=height)
            placement.shapes.append(ShapeElement(role=f"tier {tier} band", box=band, color=palette.surface))
            items = [index for index in range(1, 4) if f"item_{tier}_{index}" in roles]
            gap = 16
            item_width = (band.w - gap * (len(items) + 1)) / max(1, len(items))
            for position, index in enumerate(items):
                item = Box(x=band.x + gap + position * (item_width + gap), y=y + 8, w=item_width, h=height - 16)
                placement.boxes[f"item_{tier}_{index}"] = (item, "tier item")
                placement.colors[f"item_{tier}_{index}"] = on_band
            y += height + 12
        return placement

    return tier_list


# THE NEXT ONES FROM THE KARAOKE CATALOGUE: a wall of text, an alignment chart, red flags, reviews and a fake error
# message (docs/v5-plan.md, section 8)

_WALL_GAP: Final = 0.4  # the room between a wall's points, as a share of their size
_WALL_INDENT: Final = 1.5  # how far in a point under another goes, as a share of the size
_NOTE_HEIGHT: Final = 44.0  # the line under a wall: "Continued on next slide"
_WALL_COLUMNS_GAP: Final = 96.0  # (wider than other columns': so many lines side by side need it)


def _wall_flow(roles: dict[str, Content]) -> list[str]:
    """A wall of text's points in order, its highlighted one where the slide hid it (classic.highlighted_at)."""
    points = [f"point_{number}" for number in _numbered(roles, "point", 16)]
    if "highlight" not in roles:
        return points
    at = classic.highlighted_at(len(points))
    return [*points[:at], "highlight", *points[at:]]


def _flowed(
    flow: Sequence[str], roles: dict[str, Content], columns: Sequence[Box], font: str, size: float
) -> list[tuple[str, Box]] | None:
    """Where a wall's points go at a size: down its one or two columns (of one width), in order, a point under
    another a little further in, each point's box as tall as its lines, and two columns as even as the points allow;
    None if they don't all fit (or a word is wider than its column)."""
    gap, line = round(size * _WALL_GAP), size * fit.LINE_HEIGHT
    measured: list[tuple[str, float, float]] = []  # (each point's role, indent and height)
    for role in flow:
        element = roles[role]
        text = element.text if isinstance(element, TextElement) else ""
        indent = round(size * _WALL_INDENT) if text.startswith(classic.SUB_BULLET) else 0
        width = columns[0].w - indent
        lines = fit.wrap(text, width, font, size)
        if any(fonts.text_width(part, font, size) > width for part in lines):
            return None
        measured.append((role, indent, len(lines) * line + 2))  # (room to spare: it fits at this size, no larger)

    def height(points: Sequence[tuple[str, float, float]]) -> float:
        return sum(tall for _, _, tall in points) + gap * max(0, len(points) - 1)

    splits = [len(measured)] if len(columns) == 1 else range(len(measured) + 1)
    fitting = [
        split
        for split in splits
        if all(height(part) <= column.h for part, column in zip(_parts(measured, split), columns, strict=False))
    ]
    if not fitting:
        return None
    best = min(fitting, key=lambda split: max(height(part) for part in _parts(measured, split)))
    placed: list[tuple[str, Box]] = []
    for part, column in zip(_parts(measured, best), columns, strict=False):
        y = column.y
        for point, inset, tall in part:
            placed.append((point, Box(x=column.x + inset, y=y, w=column.w - inset, h=tall)))
            y += tall + gap
    return placed


def _parts(points: Sequence[tuple[str, float, float]], split: int) -> list[Sequence[tuple[str, float, float]]]:
    """A wall's points in its first column and in its second (the first split of them, and the rest)."""
    return [points[:split], points[split:]]


def _wall(
    placement: Placement,
    roles: dict[str, Content],
    theme: Theme,
    columns: Sequence[Box],
    under: list[str],
    ink: str,
) -> None:
    """A wall's points in its columns, at the largest fine print size at which they all fit (at the smallest, the
    points that fit, from the first, and the highlighted one always), in the ink's colour (which reads on what's under
    them); and a marker over the highlighted point's lines (as wide as its words), in a colour that it reads on, on
    the slide's one click."""
    flow, font = _wall_flow(roles), theme.fonts.body
    found, size = None, min(FINE_PRINT_SIZES)
    for largest in sorted(FINE_PRINT_SIZES, reverse=True):
        found = _flowed(flow, roles, columns, font, largest)
        if found is not None:
            size = largest
            break
    while found is None and len(flow) > 1:  # (leave points out from the end, but never the highlighted one)
        flow.remove(next(role for role in reversed(flow) if role != "highlight"))
        found = _flowed(flow, roles, columns, font, size)
    spec = f"fine print {size}"
    for role, box in found or []:
        placement.boxes[role] = (box, spec)
        placement.colors[role] = ink
    highlight = roles.get("highlight")
    if "highlight" not in placement.boxes or not isinstance(highlight, TextElement):
        return
    colour, opacity = _marker(theme, under, ink)
    marked = [color.mix(colour_under, colour, opacity) for colour_under in under]
    placement.colors["highlight"] = color.readable_on(ink, [*under, *marked], _FINE_CONTRAST)  # (and after its click)
    _, lines = text_lines(highlight.text, placement.boxes["highlight"][0], spec, theme)
    for line in lines:
        band = Box(x=line.x - 0.3 * size, y=line.y, w=line.w + 0.6 * size, h=line.h)
        placement.shapes.append(
            ShapeElement(role="marker", box=band, color=colour, opacity=opacity, appears_on_click=1)
        )


def _marker(theme: Theme, under: Sequence[str], ink: str) -> tuple[str, float]:
    """The colour and opacity of a marker over a text (a highlighter's): the theme's second accent (or, where that
    would take the text's contrast away, a shade of it that the text reads on), as see-through as it takes for the
    text to read on it over what's under it; else that shade, solid (a background on which a text only just reads
    leaves no room for a see-through colour over it: mixed in, most colours make it darker)."""
    accent = theme.palette.accent_2
    shaded = color.readable_on(accent, [ink], _FINE_CONTRAST)
    for opacity in (0.45, 0.38, 0.3, 0.22, 0.15):
        for fill in (accent, shaded):
            if color.worst_contrast(ink, [color.mix(colour, fill, opacity) for colour in under]) >= _FINE_CONTRAST:
                return fill, opacity
    return shaded, 1.0


# A marked text's contrast, a little over WCAG's 4.5 (its colour is picked for the colours behind it that the theme
# says, and a design check that finds the same ones may round them a hair differently)
_FINE_CONTRAST: Final = color.BODY_CONTRAST + 0.1


def _slide_colours(theme: Theme) -> list[str]:
    """The colours of a slide's background in the theme: its own (or both ends of its gradient), and its pattern's
    lines or dots over it."""
    colours = _backgrounds(theme)
    pattern = theme.pattern
    if pattern is not None:
        colours += [color.mix(colour, pattern.color, pattern.opacity) for colour in colours]
    return colours


def _wall_columns(left: float, right: float, top: float, bottom: float) -> list[Box]:
    width = (right - left - _WALL_COLUMNS_GAP) / 2
    return [Box(x=left + index * (width + _WALL_COLUMNS_GAP), y=top, w=width, h=bottom - top) for index in range(2)]


def _wall_of_text(roles: dict[str, Content], theme: Theme) -> Placement:
    """A wall of text: its title on top and its points under it in two columns of fine print, as large as fills them,
    a marker over the highlighted one on the slide's click, and "Continued on next slide" under it all."""
    placement = Placement("v5/wall-of-text")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 8
    bottom = _CONTENT_BOTTOM - _NOTE_HEIGHT
    columns = _wall_columns(MARGIN, WIDTH - MARGIN, top, bottom)
    _wall(placement, roles, theme, columns, _slide_colours(theme), theme.palette.text)
    placement.boxes["continued"] = (
        Box(x=MARGIN, y=bottom + 4, w=WIDTH - 2 * MARGIN, h=_NOTE_HEIGHT - 4),
        "fine print note",
    )
    return placement


def _wall_of_text_page(roles: dict[str, Content], theme: Theme) -> Placement:
    """The wall as a page of a report on the slide: a sheet in the theme's surface colour, with a shadow, its title
    at the top of the page over a rule in its accent, and its points under it in two columns of fine print."""
    palette = theme.palette
    page = Box(x=250, y=40, w=WIDTH - 500, h=946)
    shadow = Box(x=page.x + 18, y=page.y + 18, w=page.w, h=page.h)
    placement = Placement(
        "v5/wall-of-text-page",
        shapes=[
            ShapeElement(role="page shadow", box=shadow, color=color.mix(palette.background, palette.text, 0.25)),
            ShapeElement(role="page", box=page, color=palette.surface),
        ],
    )
    inner = _inset(page, 64)
    ink = _on([palette.surface], theme)
    top = inner.y
    if "title" in roles:
        placement.boxes["title"] = (Box(x=inner.x, y=inner.y, w=inner.w, h=104), "page title")
        placement.colors["title"] = ink
        rule = color.readable_on(palette.accent, [palette.surface], LINE_CONTRAST)
        placement.shapes.append(
            ShapeElement(role="page rule", box=Box(x=inner.x, y=inner.y + 112, w=inner.w, h=4), color=rule)
        )
        top = inner.y + 140
    bottom = inner.y + inner.h - _NOTE_HEIGHT
    columns = _wall_columns(inner.x, inner.x + inner.w, top, bottom)
    _wall(placement, roles, theme, columns, [palette.surface], ink)
    placement.boxes["continued"] = (Box(x=inner.x, y=bottom + 4, w=inner.w, h=_NOTE_HEIGHT - 4), "fine print note")
    placement.colors["continued"] = color.readable_on(palette.muted, [palette.surface])
    return placement


def _alignment_chart(side: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """An alignment chart: its nine things on tiles in a grid of three by three, the tiles a little deeper in the
    theme's accent row by row (from good down to evil), chaotic evil's in its second accent; the axes' words in the
    accent, lawful to chaotic over the columns and good to evil beside the rows. Each tile appears with its thing."""

    def alignment_chart(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/alignment-chart-side" if side else "v5/alignment-chart")
        left, right, top = _area(placement, roles, theme, side)
        gap, header = 14.0, 64.0
        label = 190.0 if side else 220.0
        grid_x, grid_y = left + label + gap, top + 16 + header + gap
        cell_w = (right - grid_x - 2 * gap) / 3
        cell_h = (_CONTENT_BOTTOM - grid_y - 2 * gap) / 3
        axis = color.readable_on(palette.accent, _slide_colours(theme))
        for index in range(1, 4):
            column = Box(x=grid_x + (index - 1) * (cell_w + gap), y=top + 16, w=cell_w, h=header)
            placement.boxes[f"column_{index}"] = (column, "axis")
            row = Box(x=left, y=grid_y + (index - 1) * (cell_h + gap), w=label, h=cell_h)
            placement.boxes[f"row_{index}"] = (row, "side axis")
            placement.colors[f"column_{index}"] = placement.colors[f"row_{index}"] = axis
        for position, alignment in enumerate(classic.ALIGNMENTS):
            down, across = divmod(position, 3)
            tile = Box(x=grid_x + across * (cell_w + gap), y=grid_y + down * (cell_h + gap), w=cell_w, h=cell_h)
            punchline = alignment == classic.ALIGNMENTS[-1]
            fill = palette.accent_2 if punchline else color.mix(palette.surface, palette.accent, 0.1 * down)
            click = _click(roles, alignment)
            placement.shapes.append(ShapeElement(role=f"{alignment} box", box=tile, color=fill, appears_on_click=click))
            placement.boxes[alignment] = (_inset(tile, 14), "cell")
            placement.colors[alignment] = _on([fill], theme)
        return placement

    return alignment_chart


def _short_cells(most: int) -> Callable[[dict[str, Content]], bool]:
    """Whether an alignment chart's title fits beside it and its things are at most this long (for its narrower
    cells there)."""

    def short(roles: dict[str, Content]) -> bool:
        cells = [roles.get(alignment) for alignment in classic.ALIGNMENTS]
        return _beside_title(roles) and all(
            not isinstance(cell, TextElement) or len(cell.text) <= most for cell in cells
        )

    return short


# A red flag's red, and its shape: a flag with a swallowtail, on a pole
_RED: Final = "#e53935"
_SWALLOWTAIL: Final = ((0.0, 0.0), (1.0, 0.0), (0.78, 0.5), (1.0, 1.0), (0.0, 1.0))


def _flag(placement: Placement, role: str, box: Box, theme: Theme, under: Sequence[str], click: int | None) -> None:
    """A red flag in the box, on its pole (both appearing with its text, on its click), in colours that show on what's
    under them."""
    pole = max(6.0, box.w * 0.09)
    name = role.replace("_", " ")  # ("flag 1")
    placement.shapes += [
        ShapeElement(
            role=f"{name} pole",
            box=Box(x=box.x, y=box.y, w=pole, h=box.h),
            color=color.readable_on(theme.palette.text, under, LINE_CONTRAST),
            appears_on_click=click,
        ),
        ShapeElement(
            role=f"{name} cloth",
            shape="polygon",
            points=_SWALLOWTAIL,
            box=Box(x=box.x + pole, y=box.y, w=box.w - pole, h=box.h * 0.62),
            color=color.readable_on(_RED, under, LINE_CONTRAST),
            appears_on_click=click,
        ),
    ]


def _red_flags(roles: dict[str, Content], theme: Theme) -> Placement:
    """The red flags one under the other, each beside a red flag on its pole."""
    placement = Placement("v5/red-flags")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 16
    flags = _numbered(roles, "flag", 5)
    y, height = _spread(top, _CONTENT_BOTTOM, len(flags), 20, 150)
    icon_h = min(110.0, height - 16)
    for index in flags:
        role = f"flag_{index}"
        icon = Box(x=MARGIN + 24, y=y + (height - icon_h) / 2, w=0.85 * icon_h, h=icon_h)
        _flag(placement, role, icon, theme, _slide_colours(theme), _click(roles, role))
        x = icon.x + icon.w + 48
        placement.boxes[role] = (Box(x=x, y=y, w=WIDTH - MARGIN - x, h=height), "flag")
        y += height + 20
    return placement


def _red_flags_cards(roles: dict[str, Content], theme: Theme) -> Placement:
    """The red flags side by side on cards in the theme's surface colour, each card with its red flag on top."""
    palette = theme.palette
    placement = Placement("v5/red-flags-cards")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 24
    flags = _numbered(roles, "flag", 5)
    gap = 40.0
    width = (WIDTH - 2 * MARGIN - gap * (len(flags) - 1)) / len(flags)
    height = min(600.0, _CONTENT_BOTTOM - top)
    y = top + (_CONTENT_BOTTOM - top - height) / 2
    for position, index in enumerate(flags):
        role, click = f"flag_{index}", _click(roles, f"flag_{index}")
        x = MARGIN + position * (width + gap)
        card = Box(x=x, y=y, w=width, h=height)
        placement.shapes.append(
            ShapeElement(role=f"flag {index} card", box=card, color=palette.surface, appears_on_click=click)
        )
        icon = Box(x=x + (width - 128) / 2, y=y + 40, w=128, h=150)
        _flag(placement, role, icon, theme, [palette.surface], click)
        text_top = icon.y + icon.h + 32
        placement.boxes[role] = (Box(x=x + 28, y=text_top, w=width - 56, h=y + height - 28 - text_top), "card flag")
        placement.colors[role] = _on([palette.surface], theme)
    return placement


def _at_most(prefix: str, most: int) -> Callable[[dict[str, Content]], bool]:
    """Whether the slide has at most so many of its things (red flags on cards side by side, say)."""

    def few(roles: dict[str, Content]) -> bool:
        return f"{prefix}_{most + 1}" not in roles

    return few


# A review's stars: gold, and grey where it falls short of five
_GOLD: Final = "#f5b301"


def _rating(roles: dict[str, Content], index: int) -> int:
    """How many stars a review gives (its stars' text says, as "4/5")."""
    element = roles.get(f"stars_{index}")
    text = element.text if isinstance(element, TextElement) else ""
    return int(text[:1]) if text[:1].isdigit() else 0


def _stars(placement: Placement, roles: dict[str, Content], index: int, at: Box, theme: Theme, under: str) -> None:
    """A review's five stars, in a row along the top of the box (each as wide as it's tall): as many in gold as it
    gives, the rest grey, all appearing with the review, on its click."""
    gold = color.readable_on(_GOLD, [under], 2.0)
    grey = color.mix(under, theme.palette.text, 0.18)
    rating, click, size = _rating(roles, index), _click(roles, f"review_{index}"), at.h
    for number in range(5):
        box = Box(x=at.x + number * 1.12 * size, y=at.y, w=size, h=size)
        placement.shapes.append(
            ShapeElement(
                role=f"review {index} star",
                shape="polygon",
                points=geometry.star(),
                box=box,
                color=gold if number < rating else grey,
                appears_on_click=click,
            )
        )


def _stars_width(size: float) -> float:
    return 5 * 1.12 * size - 0.12 * size


def _review_texts(placement: Placement, index: int, rating: Box, text: Box, reviewer: Box, ink: str) -> None:
    for role, box, spec in (
        (f"stars_{index}", rating, "rating"),
        (f"review_{index}", text, "review"),
        (f"reviewer_{index}", reviewer, "reviewer"),
    ):
        placement.boxes[role] = (box, spec)
        placement.colors[role] = ink


def _reviews(roles: dict[str, Content], theme: Theme) -> Placement:
    """The reviews side by side on cards in the theme's surface colour: each card's stars across its top, with the
    rating beside them ("4/5"), what the reviewer wrote under them, and who they are at the card's foot."""
    palette = theme.palette
    placement = Placement("v5/reviews")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 24
    reviews = _numbered(roles, "review", 3)
    gap, padding = 40.0, 36.0
    width = (WIDTH - 2 * MARGIN - gap * (len(reviews) - 1)) / len(reviews)
    height = min(620.0, _CONTENT_BOTTOM - top)
    y = top + (_CONTENT_BOTTOM - top - height) / 2
    ink = _on([palette.surface], theme)
    for position, index in enumerate(reviews):
        x = MARGIN + position * (width + gap)
        card = Box(x=x, y=y, w=width, h=height)
        click = _click(roles, f"review_{index}")
        placement.shapes.append(
            ShapeElement(role=f"review {index} card", box=card, color=palette.surface, appears_on_click=click)
        )
        size = min(56.0, (width - 2 * padding - 110) / 5.48)
        stars = Box(x=x + padding, y=y + padding + 4, w=_stars_width(size), h=size)
        _stars(placement, roles, index, stars, theme, palette.surface)
        rating = Box(
            x=stars.x + stars.w + 16, y=stars.y - 6, w=x + width - padding - stars.x - stars.w - 16, h=size + 12
        )
        text_top = stars.y + size + 32
        foot = y + height - padding - 64
        text = Box(x=x + padding, y=text_top, w=width - 2 * padding, h=foot - 8 - text_top)
        reviewer = Box(x=x + padding, y=foot, w=width - 2 * padding, h=64)
        _review_texts(placement, index, rating, text, reviewer, ink)
    return placement


def _reviews_rows(roles: dict[str, Content], theme: Theme) -> Placement:
    """The reviews one under the other, on bands in the theme's surface colour: the stars on the left, the rating
    under them, and what the reviewer wrote beside them, over who they are."""
    palette = theme.palette
    placement = Placement("v5/reviews-rows")
    top = (_with_title(placement, roles, theme) if "title" in roles else MARGIN) + 16
    reviews = _numbered(roles, "review", 3)
    y, height = _spread(top, _CONTENT_BOTTOM, len(reviews), 24, 260)
    ink = _on([palette.surface], theme)
    size, padding = 52.0, 32.0
    for index in reviews:
        band = Box(x=MARGIN, y=y, w=WIDTH - 2 * MARGIN, h=height)
        click = _click(roles, f"review_{index}")
        placement.shapes.append(
            ShapeElement(role=f"review {index} card", box=band, color=palette.surface, appears_on_click=click)
        )
        stars = Box(x=band.x + padding, y=y + (height - size - 56) / 2, w=_stars_width(size), h=size)
        _stars(placement, roles, index, stars, theme, palette.surface)
        rating = Box(x=stars.x, y=stars.y + size + 8, w=stars.w, h=48)
        x = stars.x + stars.w + 48
        text = Box(x=x, y=y + 20, w=band.x + band.w - padding - x, h=height - 20 - 64 - 12)
        reviewer = Box(x=x, y=y + height - 64 - 8, w=text.w, h=64)
        _review_texts(placement, index, rating, text, reviewer, ink)
        y += height + 24
    return placement


_BUTTON_HEIGHT: Final = 88.0
_BUTTON_GAP: Final = 28.0
_BUTTON_PADDING: Final = 36.0  # (on either side of a button's label)
_SHORTEST_BUTTON: Final = 180.0


def _button_widths(labels: Sequence[str], theme: Theme, room: float) -> tuple[float, list[float]]:
    """The size of a dialog's buttons' labels, one for them all (the largest at which the buttons, each as wide as its
    label with some room on either side, fit side by side), and every button's width; at the smallest size, buttons
    that still don't fit share the room (and their labels wrap)."""
    spec, font = SPECS["button"], theme.fonts.body
    largest = max(spec.smallest, round(spec.largest * theme.text_scale / fit.STEP) * fit.STEP)

    def widths(size: float) -> list[float]:
        return [
            max(_SHORTEST_BUTTON, fonts.text_width(label, font, size, True) + 2 * _BUTTON_PADDING) for label in labels
        ]

    size = largest
    while size > spec.smallest and sum(widths(size)) + _BUTTON_GAP * (len(labels) - 1) > room:
        size -= fit.STEP
    found = widths(size)
    total = sum(found) + _BUTTON_GAP * (len(labels) - 1)
    if total > room:  # (at the smallest size: each a share of the room)
        found = [width * (room - _BUTTON_GAP * (len(labels) - 1)) / sum(found) for width in found]
    return size, found


def _error_message(stacked: bool) -> Callable[[dict[str, Content], Theme], Placement]:
    """A fake error message: a dialog in the middle of the slide, with a shadow, its title on a bar in the theme's
    accent (and a ×), a warning sign on a disc in its second accent, the message and its code, and its buttons along
    its foot (the last one, the punchline, the dialog's default, in the accent): the sign beside the message, the
    buttons on the right, or (stacked) everything in the middle, one under the other."""

    def error_message(roles: dict[str, Content], theme: Theme) -> Placement:
        palette = theme.palette
        placement = Placement("v5/error-message-stacked" if stacked else "v5/error-message")
        width, height = (1180.0, 760.0) if stacked else (1360.0, 600.0)
        window = Box(x=(WIDTH - width) / 2, y=(HEIGHT - height) / 2 - 10, w=width, h=height)
        bar = Box(x=window.x, y=window.y, w=width, h=80)
        shadow = Box(x=window.x + 20, y=window.y + 24, w=width, h=height)
        placement.shapes += [
            ShapeElement(role="window shadow", box=shadow, color=color.mix(palette.background, palette.text, 0.3)),
            ShapeElement(role="window", box=window, color=palette.surface),
            ShapeElement(role="title bar", box=bar, color=palette.accent),
        ]
        on_bar = _on([palette.accent], theme)
        if "window_title" in roles:
            title = Box(x=bar.x + 32, y=bar.y + 10, w=bar.w - 150, h=bar.h - 20)
            placement.boxes["window_title"] = (title, "window title")
            placement.colors["window_title"] = on_bar
        placement.texts.append(
            ("×", Box(x=bar.x + bar.w - 92, y=bar.y + 8, w=68, h=bar.h - 16), "button", on_bar, None)
        )
        body = bar.y + bar.h
        ink = _on([palette.surface], theme)
        if stacked:
            disc = Box(x=WIDTH / 2 - 80, y=body + 44, w=160, h=160)
            message = Box(x=window.x + 72, y=disc.y + disc.h + 28, w=width - 144, h=200)
        else:
            disc = Box(x=window.x + 72, y=body + 64, w=170, h=170)
            text_x = disc.x + disc.w + 56
            message = Box(x=text_x, y=body + 48, w=window.x + width - 64 - text_x, h=220)
        code = Box(x=message.x, y=message.y + message.h + 8, w=message.w, h=52)
        placement.shapes.append(ShapeElement(role="icon disc", shape="ellipse", box=disc, color=palette.accent_2))
        placement.boxes["icon"] = (_inset(disc, disc.w * 0.15), "error icon")
        placement.colors["icon"] = _on([palette.accent_2], theme, color.LARGE_TEXT_CONTRAST)
        placement.boxes["message"] = (message, "centred error message" if stacked else "error message")
        placement.colors["message"] = ink
        if "code" in roles:
            placement.boxes["code"] = (code, "centred error code" if stacked else "error code")
            placement.colors["code"] = color.readable_on(palette.muted, [palette.surface])
        written = [(index, roles[f"button_{index}"]) for index in _numbered(roles, "button", 3)]
        labelled = [(index, element.text) for index, element in written if isinstance(element, TextElement)]
        buttons, labels = [index for index, _ in labelled], [label for _, label in labelled]
        size, widths = _button_widths(labels, theme, width - 128)
        total = sum(widths) + _BUTTON_GAP * (len(widths) - 1)
        x = window.x + (width - total) / 2 if stacked else window.x + width - 64 - total
        y = window.y + height - 56 - _BUTTON_HEIGHT
        plain = color.mix(palette.surface, palette.text, 0.1)
        edge = color.readable_on(palette.muted, [palette.surface], LINE_CONTRAST)
        for index, label, button_w in zip(buttons, labels, widths, strict=True):
            default = index == buttons[-1]
            fill = palette.accent if default else plain
            box = Box(x=x, y=y, w=button_w, h=_BUTTON_HEIGHT)
            placement.shapes.append(
                ShapeElement(
                    role=f"button_{index} box",
                    box=box,
                    color=fill,
                    corner=12,
                    outline=None if default else edge,
                    outline_width=0 if default else 3,
                )
            )
            # (its label's box just as wide as the label at the buttons' one size, so that it gets that size, and no
            # larger: in a dialog, every button's label is as large as the others')
            inner = _inset(box, 12)
            tight = min(inner.w, fonts.text_width(label, theme.fonts.body, size, True) + 2)
            placement.boxes[f"button_{index}"] = (
                Box(x=inner.x + (inner.w - tight) / 2, y=inner.y, w=tight, h=inner.h),
                "button",
            )
            placement.colors[f"button_{index}"] = _on([fill], theme)
            x += button_w + _BUTTON_GAP
        return placement

    return error_message


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
        _Layout("v5/big-number-panel", _big_number_panel, 0.8, _plain(_short("number", 7))),
        _Layout("v5/big-number-disc", _big_number_disc, 0.7, _plain(_short("number", 5))),
        # (over or beside a picture: D63)
        _Layout("v5/big-number-band", _big_number_band, 0.8, _has("background")),
        _Layout("v5/big-number-side", _big_number_side, 0.9, _pictured(_short("number", 9))),
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
        _Layout("v5/questions", _questions, fits=_without("photo")),
        _Layout("v5/questions-mark", _questions_mark, 0.8, _without("photo")),
        _Layout("v5/questions-photo", _questions_photo, fits=_photo_beside_title),
        _Layout("v5/questions-banner", _questions_banner, 0.7, _has("photo")),
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
        # (beside a title, the ring has no room in its middle for a step's picture)
        _Layout("v5/cycle-side", _cycle(side=True), 0.7, _beside_title_with_room("step", 4, pictures=False)),
    ),
    "org_chart": (
        _Layout("v5/org-chart", _org_chart(side=False)),
        _Layout("v5/org-chart-side", _org_chart(side=True), 0.7, _beside_title_with_room("report", 3)),
    ),
    "iceberg": (
        _Layout("v5/iceberg", _iceberg(side=False)),
        _Layout("v5/iceberg-side", _iceberg(side=True), 0.7, _beside_title),
    ),
    # (the talk formats')
    "process": (
        _Layout("v5/process", _process_down),
        _Layout("v5/process-across", _process_across, 1.5, _short_steps),
    ),
    "references": (
        _Layout("v5/references", _references(left=False)),
        _Layout("v5/references-left", _references(left=True), 0.8, _has("figure")),
    ),
    "meme": (_Layout("v5/meme", _meme),),
    # (slide types from PowerPoint karaoke decks)
    "fun_fact": (
        _Layout("v5/fun-fact", _fun_fact),
        _Layout("v5/fun-fact-card", _fun_fact_card, 0.9, _without("photo")),
        _Layout("v5/fun-fact-banner", _fun_fact_banner, 0.8, _has("photo")),
    ),
    "acronym": (
        _Layout("v5/acronym", _acronym_rows),
        _Layout("v5/acronym-across", _acronym_across, 0.9, _few_short_words),
    ),
    "dare": (
        _Layout("v5/dare", _dare_card),
        _Layout("v5/dare-tape", _dare_tape, 0.9),
    ),
    "flowchart": (
        _Layout("v5/flowchart", _flowchart(side=False)),
        _Layout("v5/flowchart-side", _flowchart(side=True), 0.7, _beside_title),
    ),
    "tier_list": (
        _Layout("v5/tier-list", _tier_list(side=False)),
        _Layout("v5/tier-list-side", _tier_list(side=True), 0.7, _beside_title),
    ),
    "wall_of_text": (
        _Layout("v5/wall-of-text", _wall_of_text),
        _Layout("v5/wall-of-text-page", _wall_of_text_page, 0.8),
    ),
    "alignment_chart": (
        _Layout("v5/alignment-chart", _alignment_chart(side=False)),
        _Layout("v5/alignment-chart-side", _alignment_chart(side=True), 0.6, _short_cells(28)),
    ),
    "red_flags": (
        _Layout("v5/red-flags", _red_flags),
        _Layout("v5/red-flags-cards", _red_flags_cards, 0.9, _at_most("flag", 4)),
    ),
    "reviews": (
        _Layout("v5/reviews", _reviews),
        _Layout("v5/reviews-rows", _reviews_rows, 0.8),
    ),
    "error_message": (
        _Layout("v5/error-message", _error_message(stacked=False)),
        _Layout("v5/error-message-stacked", _error_message(stacked=True), 0.9),
    ),
}
