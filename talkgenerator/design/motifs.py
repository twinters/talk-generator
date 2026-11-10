"""A family's own decoration (docs/v5-plan.md, section 9): what makes its slides more than a layout in its colours and
fonts.

Every family has a motif, which its slides are drawn with besides their layout: a terminal's window, prompts and
status line; a blueprint's border, title block and dimension lines; a chalkboard's wooden frame, chalk and tape; a
newspaper's masthead and rules; a Swiss poster's grid, rule and one red block; a kindergarten's crayon squiggles,
confetti and sticker pictures. Strong themes put a fixture on every slide and save their big motif for the title and
section slides; they ration their accent and count their decoration (a few pieces a slide, never behind a text); and
handmade families tilt things a little, where grid families keep everything square. Every family numbers its slides
of the deck's ("7/12", D65), small and in its own style (in a status line, on a sticker, on a tape), so that presenter
and audience see how far the talk is.

A motif draws with the deck's own elements (rectangles, ellipses and polygons, turned or not, with or without an
outline, and texts), so every renderer draws it. It decorates a slide's placement (talkgenerator.design.engine) before
the engine styles its texts: it adds shapes behind everything, over the layout's own shapes, or over the content
(under the texts), texts of its own (role "decoration"), and it may move a text (to make room for a prompt) or a
picture (to fit a frame around it). Its texts read on what's behind them, as every text does (the design checks
check them), and are language-neutral: numbers, symbols and code, as a talk can be in any language.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator.design import color, fonts, geometry, layers
from talkgenerator.design.engine import (
    CREDITS_BOX,
    FULL,
    HEIGHT,
    MARGIN,
    SPECS,
    WIDTH,
    Placement,
    TextSpec,
    text_lines,
)
from talkgenerator.models.deck import Box, Content, ImageAsset, ImageElement, ShapeElement, SlideBackground, TextElement
from talkgenerator.models.theme import Palette, Theme
from talkgenerator.util import random_util

# The text specs of the titles that sit across the top of a slide, and of those that sit beside its content
_TOP_TITLES: Final = frozenset({"title", "centred title"})
_LEFT_TITLES: Final = frozenset({"title", "talk title", "side title", "section side title", "left title"})
# Slide types whose pictures a motif may frame (pictures in their own boxes; not a post's, a page's or a meme's): and
# the closing slide's picture to end on, and the picture of one of an academic talk's references (D65)
_FRAMED_TYPES: Final = frozenset({"image", "two_column_image", "three_column_image", "questions", "references"})
# The slides a motif saves its big pieces for
_BIG_TYPES: Final = frozenset({"title", "section", "questions"})
# Crayon colours (the kindergarten's): red, yellow, teal, blue, green, purple, orange
CRAYONS: Final = ("#ff5d73", "#ffbf00", "#2ec4b6", "#3a86ff", "#8ac926", "#9b5de5", "#ff8c42")
# A synthwave sun's bands, from its top down: yellow, orange, pink
SUNSET: Final = ("#ffd319", "#ff901f", "#ff2975")
# A photo over the whole slide, which could be anything (for what's behind a decoration's text)
_ANYTHING: Final = ImageElement(role="background", image=ImageAsset(url="photo"), box=FULL)


@dataclass
class Scene:
    """A slide being laid out, as a motif decorates it: its placement, its elements by role, its type and theme, its
    place in the deck (from 0), whether it has a credit line and a photo behind everything, and how many slides its
    deck has (None when that isn't known: a slide laid out by itself). A slide that's not numbered (a spare, which is
    none of the deck's slides) gets no slide number, nor what a number is on (a pill, a sticker, a tag), nor what
    counts the deck's slides (a lecture's dots): the rest of its decoration is as a numbered slide's."""

    placement: Placement
    roles: dict[str, Content]
    slide_type: str
    theme: Theme
    number: int
    credits: bool
    backdrop: bool
    total: int | None = None
    numbered: bool = True
    # Where the decoration put a piece that its later pieces keep clear of (a slide's number, which confetti avoids)
    kept: list[Box] = dataclasses.field(default_factory=list)

    @property
    def palette(self) -> Palette:
        return self.theme.palette

    @property
    def big(self) -> bool:
        """Whether it's one of the slides a motif saves its big pieces for: a title, a section, "Questions?"."""
        return self.slide_type in _BIG_TYPES

    @property
    def photo(self) -> bool:
        """Whether a photo fills the slide (behind its texts, or as its content)."""
        return self.placement.photo or self.backdrop

    def present(self, role: str) -> bool:
        return role in self.roles and role in self.placement.boxes

    def box(self, role: str) -> Box:
        return self.placement.boxes[role][0]

    def spec(self, role: str) -> str:
        return self.placement.boxes[role][1]

    def texts(self) -> list[str]:
        return [role for role in self.placement.boxes if isinstance(self.roles.get(role), TextElement)]

    def pictures(self) -> list[str]:
        """The roles of its pictures in boxes of their own (not over the whole slide, nor a meme's template)."""
        return [
            role
            for role in self.placement.boxes
            if isinstance(self.roles.get(role), ImageElement)
            and self.box(role) != FULL
            and role not in self.placement.untreated
            and not self.placement.photo
        ]

    def text(self, role: str) -> str:
        element = self.roles[role]
        return element.text if isinstance(element, TextElement) else ""

    def lines(self, role: str) -> list[Box]:
        """Where a text's lines go, each as wide as it is."""
        _, lines = text_lines(self.text(role), self.box(role), self.spec(role), self.theme)
        return lines

    def ink(self, role: str) -> Box:
        """The box around a text's lines."""
        lines = self.lines(role)
        x0, y0 = min(line.x for line in lines), lines[0].y
        x1 = max(line.x + line.w for line in lines)
        return Box(x=x0, y=y0, w=x1 - x0, h=lines[-1].y + lines[-1].h - y0)

    def title(self) -> str | None:
        """The role of its title across the top of the slide, if it has one."""
        if self.present("title") and self.spec("title") in _TOP_TITLES and self.box("title").y < 120:
            return "title"
        return None

    def occupied(self, letters: bool = False) -> list[Box]:
        """Where its elements and its layout's shapes are (but those over the whole slide, and its thin decoration,
        such as a title's underline): its texts' boxes, or (with letters) only where their lines' letters are."""
        boxes = []
        for role in self.placement.boxes:
            element = self.roles.get(role)
            if element is None:
                continue
            if letters and isinstance(element, TextElement):
                boxes += [_grown(line, 12) for line in self.lines(role)]
            else:
                boxes.append(self.box(role))
        for shape in [*self.placement.shapes, *self.placement.overlays]:
            if shape.box != FULL and shape.role != "decoration":
                boxes.append(geometry.bounds(shape))
        return boxes

    def free(self, box: Box, pad: float = 16, letters: bool = False) -> bool:
        """Whether a decoration in the box would keep clear of the slide's texts (their boxes, or with letters only
        their letters), pictures and panels (by the pad), and of its credit line, and stay on the slide."""
        if box.x < 0 or box.y < 0 or box.x + box.w > WIDTH or box.y + box.h > HEIGHT:
            return False
        if self.credits and _overlaps(_grown(CREDITS_BOX, 2), box):
            return False
        if any(_overlaps(_grown(other, pad), box) for other in self.kept):
            return False
        return not any(_overlaps(_grown(other, pad), box) for other in self.occupied(letters))

    def backgrounds(self) -> list[str]:
        """The colours of the slide's background where nothing's on it: both ends of a gradient, and its pattern's."""
        theme = self.theme
        colours = [self.palette.background]
        if theme.background == "gradient" and theme.gradient_to:
            colours.append(theme.gradient_to)
        if theme.pattern is not None:
            colours += [color.mix(colour, theme.pattern.color, theme.pattern.opacity) for colour in colours]
        return colours

    # Adding decoration (of the slide, or belonging to one of its elements, part_of: a frame around a picture, which
    # appears with the picture)

    def under(self, *shapes: ShapeElement, part_of: str | None = None) -> None:
        """Shapes behind everything: scenery, a frame around the slide, a grid."""
        self.placement.under.extend(_belonging(shapes, part_of))

    def add(self, *shapes: ShapeElement, part_of: str | None = None) -> None:
        """Shapes over the layout's own (its panels and bands), behind the content."""
        self.placement.decor.extend(_belonging(shapes, part_of))

    def over(self, *shapes: ShapeElement, part_of: str | None = None) -> None:
        """Shapes over the content (pictures), under the texts: tape on a photo, a frame's edge."""
        self.placement.overlays.extend(_belonging(shapes, part_of))

    def write(self, text: str, box: Box, spec: str | TextSpec, colour: str, part_of: str | None = None) -> None:
        self.placement.texts.append((text, box, spec, colour, part_of))

    def write_on(
        self, text: str, box: Box, spec: str | TextSpec, preferred: str | None = None, part_of: str | None = None
    ) -> None:
        """A text of the decoration's, in the preferred colour (or the theme's text or background colour), made
        lighter or darker until it reads on what's behind its letters (see behind): so it's written after what it's
        on."""
        style, lines = text_lines(text, box, spec, self.theme)
        background, elements = self._drawn()
        colour = self.on(layers.behind_letters(background, elements, lines, style.size), preferred)
        self.write(text, box, spec, colour, part_of)

    def reading(self, text: str, box: Box, spec: str | TextSpec, preferred: str | None = None) -> str | None:
        """The colour a text of the decoration's gets there, as write_on gives it, if that reads on what's behind its
        letters; None where no colour does (across a theme's frame and its background, say)."""
        style, lines = text_lines(text, box, spec, self.theme)
        background, elements = self._drawn()
        fills = layers.behind_letters(background, elements, lines, style.size)
        colour = self.on(fills, preferred)
        return colour if color.worst_contrast(colour, fills) >= color.BODY_CONTRAST else None

    def behind(self, box: Box) -> list[str]:
        """The colours that may be behind a box, as the slide is drawn so far: its background (and pattern), a photo
        behind everything under its shade, the layout's shapes and the decoration's, pictures (which could be
        anything) and what's over them."""
        background, elements = self._drawn()
        return layers.behind(background, elements, box)

    def _drawn(self) -> tuple[SlideBackground, list[Content]]:
        """The slide's background, and what's drawn on it so far, in order (but the texts)."""
        theme = self.theme
        background = SlideBackground(
            color=self.palette.background,
            color_2=theme.gradient_to if theme.background == "gradient" else None,
            pattern=theme.pattern,
        )
        elements: list[Content] = [_ANYTHING] if self.backdrop else []
        elements += [*self.placement.under, *self.placement.shapes, *self.placement.decor]
        for role, (place, _) in self.placement.boxes.items():
            element = self.roles.get(role)
            if isinstance(element, ImageElement):
                elements.append(element.model_copy(update={"box": place}))
        elements += self.placement.overlays
        return background, elements

    def on(self, fills: Sequence[str], preferred: str | None = None, minimum: float = color.BODY_CONTRAST) -> str:
        """The colour of a text of the decoration's on the fills: the preferred one (or the theme's text or
        background colour, whichever reads better) made lighter or darker until it reads."""
        palette = self.palette
        if preferred is None:
            preferred = max((palette.text, palette.background), key=lambda option: color.worst_contrast(option, fills))
        return color.readable_on(preferred, fills, minimum)

    def shown(self, role: str, inside: Box | None = None) -> Box:
        """Where a picture shows, in its box (or inside another): as large as it fits whole, by its own size, in the
        middle; or (its size unknown) filling the box, cropped. The picture is placed there, so that a frame drawn
        around it fits."""
        element = self.roles[role]
        box = inside or self.box(role)
        spec = self.spec(role)
        width = element.image.width if isinstance(element, ImageElement) else None
        height = element.image.height if isinstance(element, ImageElement) else None
        if not width or not height:
            self.placement.cover.add(role)
            self.placement.boxes[role] = (box, spec)
            return box
        scale = min(box.w / width, box.h / height)
        shown = Box(
            x=box.x + (box.w - width * scale) / 2,
            y=box.y + (box.h - height * scale) / 2,
            w=width * scale,
            h=height * scale,
        )
        self.placement.boxes[role] = (shown, spec)
        return shown


def decorate(scene: Scene) -> None:
    """Draw the theme's motif on the slide (nothing for a theme without one, such as the classic look)."""
    motif = _MOTIFS.get(scene.theme.motif)
    if motif is not None:
        motif(scene)


# BUILDING BLOCKS


def _rect(
    x: float,
    y: float,
    w: float,
    h: float,
    colour: str,
    opacity: float = 1.0,
    corner: float = 0.0,
    rotation: float = 0.0,
    role: str = "decoration",
) -> ShapeElement:
    return ShapeElement(
        role=role,
        box=Box(x=x, y=y, w=w, h=h),
        color=colour,
        opacity=opacity,
        corner=corner,
        rotation=rotation,
    )


def _ellipse(cx: float, cy: float, w: float, h: float, colour: str, opacity: float = 1.0) -> ShapeElement:
    return ShapeElement(shape="ellipse", box=Box(x=cx - w / 2, y=cy - h / 2, w=w, h=h), color=colour, opacity=opacity)


def _ring(cx: float, cy: float, w: float, h: float, colour: str, width: float, opacity: float = 1.0) -> ShapeElement:
    return ShapeElement(
        shape="ellipse",
        box=Box(x=cx - w / 2, y=cy - h / 2, w=w, h=h),
        color=colour,
        filled=False,
        outline=colour,
        outline_width=width,
        opacity=opacity,
    )


def _frame(box: Box, colour: str, width: float, opacity: float = 1.0, corner: float = 0.0) -> ShapeElement:
    """A box's outline, inside it."""
    return ShapeElement(
        box=box, color=colour, filled=False, outline=colour, outline_width=width, opacity=opacity, corner=corner
    )


def _polygon(
    points: geometry.Points,
    x: float,
    y: float,
    w: float,
    h: float,
    colour: str,
    opacity: float = 1.0,
    rotation: float = 0.0,
) -> ShapeElement:
    return ShapeElement(
        shape="polygon",
        points=points,
        box=Box(x=x, y=y, w=w, h=h),
        color=colour,
        opacity=opacity,
        rotation=rotation,
    )


def _line(points: Sequence[geometry.Point], width: float, colour: str, opacity: float = 1.0) -> ShapeElement:
    """A line through the points (a squiggle, a stroke), as a polygon."""
    box, outline = geometry.stroke(points, width)
    return ShapeElement(shape="polygon", points=outline, box=box, color=colour, opacity=opacity)


def _grown(box: Box, by: float) -> Box:
    return Box(x=box.x - by, y=box.y - by, w=box.w + 2 * by, h=box.h + 2 * by)


def _moved(shape: ShapeElement, down: float) -> ShapeElement:
    return shape.model_copy(update={"box": shape.box.model_copy(update={"y": shape.box.y + down})})


def _belonging(shapes: Sequence[ShapeElement], part_of: str | None) -> list[ShapeElement]:
    """The shapes, as part of the element of that role (if any)."""
    if part_of is None:
        return list(shapes)
    return [shape.model_copy(update={"part_of": part_of}) for shape in shapes]


def _overlaps(box: Box, other: Box) -> bool:
    return (
        box.x < other.x + other.w and other.x < box.x + box.w and box.y < other.y + other.h and other.y < box.y + box.h
    )


def _star(cx: float, cy: float, size: float, colour: str, rotation: float = 0.0, opacity: float = 1.0) -> ShapeElement:
    return _polygon(geometry.star(), cx - size / 2, cy - size / 2, size, size, colour, opacity, rotation)


def _number(scene: Scene) -> str:
    return f"{scene.number + 1:02d}"


def _count(scene: Scene, padded: bool = False, gap: str = "") -> str:
    """The slide's number of its deck's slides, as "7/12" (padded, as "07/12", the total too: "03/08", never "03/8",
    which the user found odd on 2026-11-10; with a gap, as "7 / 12"), so that presenter and audience see how far the
    talk is; or its number alone ("07"), when the deck's size isn't known."""
    if scene.total is None:
        return _number(scene)
    digits = max(2, len(str(scene.total))) if padded else 1
    return f"{scene.number + 1:0{digits}d}{gap}/{gap}{scene.total:0{digits}d}"


def _roman(number: int) -> str:
    """A number in Roman numerals (a newspaper's volume)."""
    numerals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL")]
    numerals += [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    written = ""
    for value, numeral in numerals:
        while number >= value:
            written += numeral
            number -= value
    return written


def _sized(spec: str, largest: float, smallest: float | None = None, **changes: Any) -> TextSpec:
    """A decoration's text spec, from largest down to smallest (at exactly largest, without one): a prompt as big as
    its title, say, or a sticker's word as big as fits it."""
    return dataclasses.replace(
        SPECS[spec],
        largest=largest,
        smallest=largest if smallest is None else smallest,
        on_fill=True,
        effect=False,
        **changes,
    )


def _corner_spots(scene: Scene, size: float, inset: float = 40, letters: bool = False) -> list[Box]:
    """Free spots for a piece of decoration this big, in the slide's corners and along its edges, in a fixed order
    (clear of its texts' boxes, or with letters, of their letters only)."""
    spots = []
    for x, y in (
        (WIDTH - inset - size, inset),
        (inset, inset),
        (WIDTH - inset - size, HEIGHT - inset - size),
        (inset, HEIGHT - inset - size),
        (WIDTH / 2 - size / 2, inset),
        (WIDTH - inset - size, HEIGHT / 2 - size / 2),
        (inset, HEIGHT / 2 - size / 2),
    ):
        spot = Box(x=x, y=y, w=size, h=size)
        if scene.free(spot, letters=letters):
            spots.append(spot)
    return spots


def _confetti(
    scene: Scene, colours: Sequence[str], count: int, sizes: tuple[float, float] = (22, 44), top: bool = True
) -> None:
    """A few pieces of confetti (dots, stars, triangles, rings) in free spots along the slide's edges (and along its
    top, if top), each turned a little: never behind a text."""
    candidates: list[tuple[float, float]] = []
    for edge in (30.0, 62.0, WIDTH - 62.0, WIDTH - 30.0):
        candidates += [(edge, float(down)) for down in range(90, HEIGHT - 80, 80)]
    for across in range(200, WIDTH - 200, 160):
        candidates.append((float(across), HEIGHT - 40.0))
        if top:
            candidates.append((float(across), 22.0))
    random_util.shuffle(candidates)
    placed: list[Box] = []
    for x, y in candidates:
        if len(placed) >= count:
            break
        size = random_util.uniform(*sizes)
        spot = Box(x=x - size / 2, y=y - size / 2, w=size, h=size)
        if not scene.free(spot, pad=12) or any(_overlaps(_grown(other, 40), spot) for other in placed):
            continue
        placed.append(spot)
        colour = random_util.choice(colours)
        kind = random_util.choice(("dot", "star", "triangle", "ring"))
        turn = random_util.uniform(-25, 25)
        if kind == "dot":
            scene.under(_ellipse(x, y, size * 0.7, size * 0.7, colour))
        elif kind == "star":
            scene.under(_star(x, y, size, colour, turn))
        elif kind == "triangle":
            scene.under(_polygon(geometry.triangle(), spot.x, spot.y, size, size * 0.9, colour, rotation=turn))
        else:
            scene.under(_ring(x, y, size * 0.8, size * 0.8, colour, max(4.0, size / 7)))


def _slide_number(
    scene: Scene,
    *boxes: Box,
    spec: str | TextSpec = "decoration right",
    colour: str | None = None,
    padded: bool = False,
) -> bool:
    """The slide's number of the deck's ("7/12") in the first of the boxes (corners, in the family's order) that's
    free and where it reads on what's behind its letters (not across a theme's frame, say), small, in the muted colour
    (or the colour), made lighter or darker as it needs; the decoration put after it keeps clear of it. Whether it
    found a place (never, on a slide that's not numbered)."""
    if not scene.numbered:
        return False
    text = _count(scene, padded)
    for box in boxes:
        if not scene.free(box, pad=4):
            continue
        reading = scene.reading(text, box, spec, colour or scene.palette.muted)
        if reading is not None:
            scene.write(text, box, spec, reading)
            scene.kept.append(box)
            return True
    return False


# Where a slide's number goes when its family has no fixture for it: in the bottom right corner, under the credit
# line (or in the top right corner, along the top); and the band along the bottom that a number (and what it's on)
# has, between the credit line and the slide's safe area (the design checks', which ends 16 pixels from its edge)
_BOTTOM_RIGHT: Final = Box(x=WIDTH - MARGIN - 120, y=1034, w=120, h=30)
_TOP_RIGHT: Final = Box(x=WIDTH - MARGIN - 120, y=16, w=120, h=32)
_FOOT: Final = (1034.0, 30.0)


def _plate(x: float, width: float) -> tuple[Box, Box]:
    """Where a slide's number goes in the band along the bottom, and what it's on there (a pill, a sticker, a tape),
    a little taller than the number's box, below the credit line's letters: as large a box for both."""
    top, height = _FOOT
    return Box(x=x, y=top - 2, w=width, h=height + 4), Box(x=x, y=top, w=width, h=height)


# THE MOTIFS


def _keynote(scene: Scene) -> None:
    """Calm: a short accent bar over the title, and the slide's number ("7/12"), small, in the bottom right corner."""
    palette = scene.palette
    title = scene.title()
    if title is not None:
        ink = scene.ink(title)
        x = ink.x if scene.theme.title_align == "left" else ink.x + ink.w / 2 - 36
        scene.add(_rect(x, 28, 72, 10, palette.accent, corner=5))
    if scene.big and not scene.photo:  # (a big soft circle in a corner, on the slides that are about the talk)
        corner = scene.theme.motif_variant % 2
        x = WIDTH - 280 if corner else -420
        opacity = _faint(scene, palette.accent, 0.07)
        if opacity >= 0.03:
            scene.under(_ellipse(x + 350, -60, 700, 700, palette.accent, opacity))
    if not scene.placement.photo:
        _slide_number(scene, _BOTTOM_RIGHT, _TOP_RIGHT)


def _minimal(scene: Scene) -> None:
    """Almost nothing: a thin accent line along the left edge by the title, and the slide's number ("7/12") at the
    top right."""
    palette = scene.palette
    title = scene.title()
    if title is not None:
        ink = scene.ink(title)
        scene.add(_rect(40, ink.y + 8, 4, max(40.0, ink.h - 16), palette.accent))
    if not scene.placement.photo:
        _slide_number(scene, _TOP_RIGHT, _BOTTOM_RIGHT)


def _corporate(scene: Scene) -> None:
    """A band in the accent along the top, a thin one in the second accent under it, and the slide's number ("7/12")
    on a small tile in the bottom right corner."""
    palette = scene.palette
    if not scene.placement.photo:
        scene.add(_rect(0, 0, WIDTH, 12, palette.accent), _rect(0, 12, WIDTH, 4, palette.accent_2))
        width = 72 if scene.total is None else 112
        tile = Box(x=WIDTH - 16 - width, y=1034, w=width, h=30)
        if scene.numbered and scene.free(tile, pad=2):
            scene.add(_rect(tile.x, tile.y, tile.w, tile.h, palette.accent))
            scene.write_on(_count(scene), tile, "decoration centre")


def _lecture(scene: Scene) -> None:
    """A lecture's slides, after LaTeX's Beamer: the title on a band in the accent across the top; a row of dots, one
    a slide of the deck, the slide's own filled (the ones after it fainter: or, when they don't all fit, the slides so
    far); a thin band along the bottom with the slide's number ("7 / 12")."""
    palette = scene.palette
    title = scene.title()
    if title is not None:
        box = scene.box(title)
        band = _rect(0, box.y - 16, WIDTH, box.h + 32, palette.accent)
        scene.add(band)
        scene.placement.colors[title] = scene.on([palette.accent], minimum=color.LARGE_TEXT_CONTRAST)
        scene.placement.on_fill.add(title)
    if not scene.placement.photo:
        fitting = int((WIDTH / 2 - MARGIN) // 26) + 1  # (as many dots as fit in the slide's left half)
        dots = scene.total if scene.total is not None and scene.total <= fitting else scene.number + 1
        for index in range(min(dots, fitting) if scene.numbered else 0):
            x = MARGIN + index * 26
            if index == scene.number:
                scene.add(_ellipse(x + 7, 22, 14, 14, palette.accent))
            else:
                scene.add(_ring(x + 7, 22, 14, 14, palette.accent, 2, 1.0 if index < scene.number else 0.45))
        scene.add(_rect(0, 1036, WIDTH, 44, palette.surface))
        number = Box(x=WIDTH - MARGIN - 160, y=1034, w=160, h=30)
        if scene.numbered:
            scene.write_on(_count(scene, gap=" "), number, "decoration right", palette.muted)


def _blobs(scene: Scene) -> None:
    """A startup's soft blobs: two big circles of its accents, see-through, in opposite corners, off the slide's
    edges (bigger on its title and section slides); and the slide's number ("7/12"), small, in the bottom right
    corner, on a pill of its accent, see-through as the blobs are."""
    palette = scene.palette
    size = 900 if scene.big else 640
    flip = scene.theme.motif_variant % 2
    first = (WIDTH - size * 0.45, -size * 0.45) if flip else (-size * 0.55, -size * 0.4)
    second = (-size * 0.5, HEIGHT - size * 0.5) if flip else (WIDTH - size * 0.5, HEIGHT - size * 0.55)
    for (x, y), width, colour in ((first, size, palette.accent), (second, size * 0.8, palette.accent_2)):
        opacity = _faint(scene, colour, 0.12)
        if opacity >= 0.04:
            scene.under(_ellipse(x + size / 2, y + size / 2, width, width, colour, opacity))
    pill, number = _plate(WIDTH - MARGIN - 112, 112)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        opacity = _faint(scene, palette.accent, 0.16)
        if opacity >= 0.04:
            scene.add(_rect(pill.x, pill.y, pill.w, pill.h, palette.accent, opacity, corner=pill.h / 2))
        _slide_number(scene, number, spec="decoration centre")


def _faint(scene: Scene, colour: str, most: float, stacked: int = 1) -> float:
    """How opaque a see-through shape of the colour can be (at most most), so that the theme's texts and accents,
    which may be over it, still read there (as they read on its background): over that many of them on top of each
    other, as the design checks take several such shapes under one text to be."""
    palette = scene.palette
    needs = [(palette.text, color.BODY_CONTRAST), (palette.muted, color.BODY_CONTRAST)]
    needs += [(palette.accent, color.LARGE_TEXT_CONTRAST), (palette.accent_2, color.LARGE_TEXT_CONTRAST)]
    opacity = most
    while opacity > 0:
        tinted = scene.backgrounds()
        for _ in range(stacked):
            tinted = [color.mix(background, colour, opacity) for background in tinted]
        if all(color.worst_contrast(text, tinted) >= needed for text, needed in needs):
            return opacity
        opacity = round(opacity - 0.01, 2)
    return 0.0


def _ornate(scene: Scene) -> None:
    """Vintage paper's double frame, with a diamond in each corner, a rule with a diamond in its middle under the
    title (a fleuron's place), and the slide's number ("7/12") on a cartouche in the middle of the frame's foot."""
    palette = scene.palette
    ink = palette.accent
    scene.over(
        _frame(Box(x=22, y=22, w=WIDTH - 44, h=HEIGHT - 44), ink, 3),
        _frame(Box(x=32, y=32, w=WIDTH - 64, h=HEIGHT - 64), ink, 1.5),
    )
    for cx, cy in ((27, 27), (WIDTH - 27, 27), (27, HEIGHT - 27), (WIDTH - 27, HEIGHT - 27)):
        scene.over(_polygon(geometry.diamond(), cx - 14, cy - 14, 28, 28, ink))
    cartouche, number = _plate(WIDTH / 2 - 80, 160)
    # (the paper over the frame's lines there, edged in the ink, a diamond each side)
    if scene.numbered and scene.free(number, pad=2):
        middle = cartouche.y + cartouche.h / 2
        scene.over(
            _rect(cartouche.x, cartouche.y, cartouche.w, cartouche.h, palette.background, corner=cartouche.h / 2),
            _frame(cartouche, ink, 1.5, corner=cartouche.h / 2),
            _polygon(geometry.diamond(), cartouche.x - 16, middle - 9, 18, 18, ink),
            _polygon(geometry.diamond(), cartouche.x + cartouche.w - 2, middle - 9, 18, 18, ink),
        )
        _slide_number(scene, number, spec="decoration centre", colour=ink)
    title = scene.title()
    if title is not None:
        ink_box = scene.ink(title)
        y = scene.box(title).y + scene.box(title).h + 14
        middle = ink_box.x + ink_box.w / 2 if scene.theme.title_align == "center" else ink_box.x + 160
        scene.add(
            _rect(middle - 170, y, 140, 3, ink),
            _polygon(geometry.diamond(), middle - 13, y - 11, 26, 26, ink),
            _rect(middle + 30, y, 140, 3, ink),
        )


def _crayon(scene: Scene) -> None:
    """A kindergarten's: a crayon squiggle under the title, confetti along the edges (never behind a text),
    pictures as stickers (a white border, an ink outline and a hard shadow), on its big slides, scenery; and the
    slide's number ("7/12") on a little sticker of its own in the bottom right corner."""
    palette = scene.palette
    crayons = [colour for colour in CRAYONS if color.contrast(colour, palette.background) > 1.4]
    title = scene.title()
    if title is not None:
        ink = scene.ink(title)
        width = min(ink.w, 520.0)
        x = ink.x if scene.theme.title_align == "left" else ink.x + (ink.w - width) / 2
        y = min(scene.box(title).y + scene.box(title).h + 12, ink.y + ink.h + 10)
        squiggle = geometry.squiggle(x, y, width, 7, max(2.0, width / 130))
        scene.add(_line(squiggle, 10, crayons[scene.number % len(crayons)]))
    if not scene.photo:
        if scene.placement.layout == "v5/kids-title":
            _scenery(scene, crayons)
        else:
            _bunting(scene, crayons, -10, WIDTH + 10, 2, 16, 34, 42)
    elif (span := _beside_side_photo(scene)) is not None:  # (a picture filling one side: bunting across the other)
        _bunting(scene, crayons, *span, 2, 12, 34, 42)
    sticker, number = _plate(WIDTH - 44 - 116, 116)
    # (before the confetti, which keeps clear of it)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        corner = sticker.h / 2
        scene.add(
            _rect(sticker.x + 4, sticker.y + 4, sticker.w, sticker.h, palette.text, corner=corner),
            _rect(sticker.x, sticker.y, sticker.w, sticker.h, "#ffffff", corner=corner),
            _frame(sticker, palette.text, 2.5, corner=corner),
        )
        _slide_number(scene, number, spec="decoration centre", colour=palette.text)
        scene.kept.append(sticker)
    _confetti(scene, crayons, 6 if scene.big else 4, (30, 56), top=scene.photo)
    for role in scene.pictures() if scene.slide_type in _FRAMED_TYPES else []:
        shown = scene.shown(role, _grown(scene.box(role), -14))
        corner = 0.08 * min(shown.w, shown.h) + 14
        border = _grown(shown, 14)
        scene.add(
            _rect(border.x + 8, border.y + 8, border.w, border.h, palette.text, corner=corner),
            _rect(border.x, border.y, border.w, border.h, "#ffffff", corner=corner),
            _frame(border, palette.text, 3, corner=corner),
            part_of=role,
        )
    if scene.slide_type == "section" or scene.slide_type == "questions":
        _sun(scene, Box(x=WIDTH - 330, y=40, w=280, h=280))


def _beside_side_photo(scene: Scene) -> tuple[float, float] | None:
    """Across the top of a slide whose picture fills one side of it, from its top to its bottom (a big number's, D63:
    a photo slide, whose picture no frame goes around), the span beside the picture, from left to right; None for
    every other slide."""
    if not scene.placement.photo or scene.backdrop:
        return None
    for role, (box, _) in scene.placement.boxes.items():
        if not isinstance(scene.roles.get(role), ImageElement) or box.y > 0 or box.h < HEIGHT or box.w > WIDTH * 0.6:
            continue
        if box.x + box.w >= WIDTH:
            return -10, box.x - 24
        if box.x <= 0:
            return box.x + box.w + 24, WIDTH + 10
    return None


def _sun(scene: Scene, box: Box) -> None:
    """A crayon sun: a yellow disc with a burst of rays behind it, if there's room."""
    if not scene.free(box, pad=8):
        return
    scene.under(
        _polygon(geometry.burst(12, 0.62), box.x, box.y, box.w, box.h, "#ffd23f", rotation=8),
        _ellipse(box.x + box.w / 2, box.y + box.h / 2, box.w * 0.62, box.h * 0.62, "#ffbf00"),
    )


def _bunting(
    scene: Scene,
    colours: Sequence[str],
    left: float,
    right: float,
    top: float,
    sag: float,
    width: float,
    height: float,
) -> None:
    """A string of little flags hanging across the slide, from left to right at top, sagging in the middle, each flag
    turned along the string, in turn in the colours."""
    ink = scene.palette.text

    def at(share: float) -> tuple[float, float]:
        return left + (right - left) * share, top + sag * 4 * share * (1 - share)

    string = [at(step / 40) for step in range(41)]
    scene.under(_line(string, 3, ink, 0.8))
    count = max(3, int((right - left) / (width * 1.9)))
    for index in range(count):
        share = (index + 0.5) / count
        x, y = at(share)
        slope = math.degrees(math.atan2(sag * 4 * (1 - 2 * share), right - left))
        colour = colours[index % len(colours)]
        scene.under(_polygon(geometry.pennant(), x - width / 2, y, width, height, colour, rotation=slope))


def _cloud(scene: Scene, x: float, y: float, width: float) -> None:
    """A cloud: white puffs with an outline in ink (each puff drawn a little bigger in ink first)."""
    ink = scene.palette.text
    puffs = (
        (0.0, 0.25, 0.45, 0.55),
        (0.28, 0.0, 0.42, 0.7),
        (0.55, 0.18, 0.45, 0.6),
        (0.15, 0.45, 0.75, 0.45),
    )
    fill = color.mix(scene.palette.background, "#8fd3ff", 0.45)
    for grow, colour in ((5.0, ink), (0.0, fill)):
        for px, py, pw, ph in puffs:
            box = Box(
                x=x + px * width - grow,
                y=y + py * width * 0.5 - grow,
                w=pw * width + 2 * grow,
                h=ph * width * 0.5 + 2 * grow,
            )
            scene.under(ShapeElement(shape="ellipse", box=box, color=colour))


def _flower(scene: Scene, x: float, y: float, size: float, colour: str) -> None:
    """A flower: five round petals around a yellow middle."""
    for index in range(5):
        angle = 2 * math.pi * index / 5 - math.pi / 2
        scene.under(
            _ellipse(
                x + math.cos(angle) * size * 0.32, y + math.sin(angle) * size * 0.32, size * 0.42, size * 0.42, colour
            )
        )
    scene.under(_ellipse(x, y, size * 0.36, size * 0.36, "#ffbf00"))


def _scenery(scene: Scene, crayons: Sequence[str]) -> None:
    """A kindergarten's title slide: bunting across the top, a sun and a cloud, rolling hills with flowers along the
    bottom, and the title and subtitle on a white card with a thick crayon outline."""
    palette = scene.palette
    _bunting(scene, crayons, -30, WIDTH + 30, 0, 70, 66, 84)
    _sun(scene, Box(x=WIDTH - 250, y=118, w=220, h=220))
    _cloud(scene, 70, 150, 230)
    scene.under(
        _ellipse(330, 1110, 1300, 560, "#8ac926"),
        _ellipse(1480, 1150, 1500, 600, "#5fb53c"),
        _ellipse(900, 1220, 1500, 520, "#7cc242"),
    )
    for x, y, colour in (
        (200, 925, crayons[0]),
        (420, 880, crayons[3 % len(crayons)]),
        (1580, 935, crayons[5 % len(crayons)]),
    ):
        _flower(scene, x, y, 52, colour)
    if scene.present("title"):
        title = scene.box("title")
        card = Box(x=title.x - 50, y=title.y - 40, w=title.w + 100, h=480)
        scene.add(
            _rect(card.x + 12, card.y + 12, card.w, card.h, palette.text, corner=44),
            _rect(card.x, card.y, card.w, card.h, "#ffffff", corner=44),
            _frame(card, crayons[scene.theme.motif_variant % len(crayons)], 10, corner=44),
        )


def _brutal(scene: Scene) -> None:
    """Brutalist: the title on a solid block of the accent, hard shadows behind pictures, and the slide's number
    ("07/12") on a black tag in the top left corner."""
    palette = scene.palette
    title = scene.title()
    if title is not None and len(scene.lines(title)) <= 2:
        ink = scene.ink(title)
        block = Box(x=ink.x - 18, y=ink.y - 6, w=ink.w + 36, h=ink.h + 12)
        scene.add(
            _rect(block.x + 10, block.y + 10, block.w, block.h, palette.text),
            _rect(block.x, block.y, block.w, block.h, palette.accent),
        )
        scene.placement.colors[title] = scene.on([palette.accent], minimum=color.LARGE_TEXT_CONTRAST)
        scene.placement.on_fill.add(title)
        scene.placement.plain.add(title)
    for role in scene.pictures() if scene.slide_type in _FRAMED_TYPES else []:
        shown = scene.shown(role, _grown(scene.box(role), -16))
        scene.add(_rect(shown.x + 16, shown.y + 16, shown.w, shown.h, palette.text), part_of=role)
    if scene.numbered and not scene.placement.photo:
        width = 136 if scene.total is None else 176
        tag = Box(x=0, y=0, w=width, h=52)
        scene.add(_rect(tag.x, tag.y, tag.w, tag.h, palette.text))
        scene.write_on(_count(scene, padded=True), Box(x=16, y=16, w=width - 32, h=32), "decoration centre")


def _synthwave(scene: Scene) -> None:
    """Neon's: a thin line of its accent along the bottom, with the slide's number ("7/12") over its right end; on
    its big slides, a striped sun sinking behind a grid floor, where there's room."""
    palette = scene.palette
    if scene.big and not scene.photo:
        _retro_sun(scene)
    elif not scene.placement.photo:
        scene.add(_rect(0, HEIGHT - 6, WIDTH, 6, palette.accent))
    if not scene.placement.photo:
        _slide_number(scene, _BOTTOM_RIGHT, _TOP_RIGHT, spec=_sized("decoration heading", 26, 24, align="right"))


def _retro_sun(scene: Scene) -> None:
    """A sun of stripes, half under the horizon, over a floor of grid lines running to it: below the slide's texts,
    as far down as there's room."""
    palette = scene.palette
    texts = [scene.box(role) for role in scene.texts()]
    lowest = max((box.y + box.h for box in texts), default=0.0)
    horizon = max(lowest + 150, 860.0)
    if horizon > HEIGHT - 80:
        return
    radius = min(230.0, horizon - lowest - 30)
    if radius < 90:
        return
    middle = WIDTH / 2
    sun = SUNSET
    for index, colour in enumerate(sun):  # (bands of colour, from the top down)
        scene.under(
            ShapeElement(
                shape="polygon",
                points=_disc_band(index / 3, (index + 1) / 3),
                box=Box(x=middle - radius, y=horizon - radius, w=2 * radius, h=2 * radius),
                color=colour,
            )
        )
    for index in range(5):  # (stripes across its lower half, in the background's colour)
        y = horizon - radius * 0.62 + index * radius * 0.13
        scene.under(_rect(middle - radius, y, 2 * radius, 4 + index * 2.5, palette.background))
    floor = _rect(0, horizon, WIDTH, HEIGHT - horizon, palette.background)
    scene.under(floor, _rect(0, horizon - 2, WIDTH, 4, palette.accent))
    depth = HEIGHT - horizon
    for index in range(1, 6):  # (lines across the floor, closer together towards the horizon)
        y = horizon + depth * (index / 5) ** 1.8
        scene.under(_rect(0, y, WIDTH, 2 + index * 0.6, palette.accent, 0.7))
    for index in range(-6, 7):  # (and lines running to the middle of the horizon)
        end = middle + index * 360
        scene.under(_line([(middle + index * 8, horizon), (end, HEIGHT + 40)], 3, palette.accent, 0.6))


def _disc_band(top: float, bottom: float, steps: int = 24) -> geometry.Points:
    """The part of a disc (in its box, from 0 to 1) between two heights, as a polygon."""

    def half_width(y: float) -> float:
        return math.sqrt(max(0.0, 0.25 - (y - 0.5) ** 2))

    heights = [top + (bottom - top) * step / steps for step in range(steps + 1)]
    left = [(0.5 - half_width(y), y) for y in heights]
    right = [(1 - x, y) for x, y in reversed(left)]
    return tuple((round(x, 4), round(y, 4)) for x, y in [*left, *right])


def _starburst(scene: Scene) -> None:
    """1997 WordArt's: a starburst sticker, turned, with three exclamation marks on it, in a free corner; a row of
    little stars along the top; and the slide's number ("7/12"), in bold italics on a little yellow sticker edged in
    red, in the bottom right corner (over the frame some of its members draw around the slide; the big sticker then
    leaves that corner be)."""
    palette = scene.palette
    sticker, number = _plate(WIDTH - MARGIN - 112, 112)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        corner = sticker.h / 2
        scene.add(
            _rect(sticker.x, sticker.y, sticker.w, sticker.h, "#ffe600", corner=corner),
            _frame(sticker, "#e3001b", 2.5, corner=corner),
        )
        _slide_number(scene, number, spec=_sized("decoration centre", 25, 24, italic=True, bold=True), colour="#e3001b")
        scene.kept.append(sticker)
    spots = _corner_spots(scene, 210, 30, letters=True)
    if spots:
        spot = spots[scene.number % len(spots)]
        turn = random_util.uniform(-18, 18)
        scene.add(
            _polygon(geometry.burst(16, 0.7), spot.x, spot.y, spot.w, spot.h, "#e3001b", rotation=turn),
            _polygon(geometry.burst(16, 0.7), spot.x + 14, spot.y + 14, spot.w - 28, spot.h - 28, "#ffe600", 1, turn),
        )
        word = Box(x=spot.x + 55, y=spot.y + 68, w=spot.w - 110, h=spot.h - 136)
        scene.write_on("!!!", word, _sized("decoration heading", 64, 28), "#e3001b")
    if not scene.placement.photo:
        for index in range(12):
            x = MARGIN + 40 + index * (WIDTH - 2 * MARGIN - 80) / 11
            spot = Box(x=x - 13, y=12, w=26, h=26)
            if scene.free(spot, pad=4):
                scene.under(_star(x, 25, 26, "#ffe600" if index % 2 else palette.accent_2))


def _comic(scene: Scene) -> None:
    """A comic's: every slide a panel (a thick ink border), the title in a speech balloon (white, outlined in ink,
    with a tail), on its big slides a POW burst in a free corner, and the slide's number ("7/12") in a caption box
    on the panel's border, in its bottom right corner."""
    scene.over(_frame(Box(x=14, y=14, w=WIDTH - 28, h=HEIGHT - 28), "#111111", 9))
    caption, number = _plate(WIDTH - 60 - 124, 124)
    # (yellow, edged in ink, over the border: as a comic's narration box)
    if scene.numbered and scene.free(number, pad=2):
        scene.over(_rect(caption.x, caption.y, caption.w, caption.h, "#ffe14d"), _frame(caption, "#111111", 3))
        _slide_number(scene, number, spec=_sized("decoration centre", 25, 24, bold=True), colour="#111111")
    title = scene.title()
    if title is not None:
        ink = scene.ink(title)
        top = scene.box(title).y - 12
        balloon = Box(x=ink.x - 56, y=max(top, ink.y - 26), w=ink.w + 112, h=ink.h + 2 * min(26.0, ink.y - top))
        tail_x = balloon.x + balloon.w * 0.2
        room = scene.box(title).y + scene.box(title).h + 26 - (balloon.y + balloon.h - 8)  # (above the content)
        tail = min(52.0, room)
        if tail >= 20:
            scene.add(_polygon(geometry.tail(), tail_x - 4, balloon.y + balloon.h - 8, tail * 1.08, tail, "#111111"))
        scene.add(
            _rect(balloon.x, balloon.y, balloon.w, balloon.h, "#ffffff", corner=balloon.h / 2),
            _frame(balloon, "#111111", 5, corner=balloon.h / 2),
        )
        if tail >= 20:
            inner = tail * 0.73
            tip = _polygon(geometry.tail(), tail_x + 4, balloon.y + balloon.h - 12, inner * 1.05, inner, "#ffffff")
            scene.add(tip)
        scene.placement.colors[title] = scene.on(["#ffffff"], "#111111")
        scene.placement.on_fill.add(title)
        scene.placement.plain.add(title)
    if scene.big:
        spots = _corner_spots(scene, 240, 30, letters=True)
        if spots:
            spot = spots[0]
            turn = random_util.uniform(-15, 15)
            scene.add(
                _polygon(geometry.burst(14, 0.66), spot.x, spot.y, spot.w, spot.h, "#111111", rotation=turn),
                _polygon(
                    geometry.burst(14, 0.66), spot.x + 10, spot.y + 10, spot.w - 20, spot.h - 20, "#ffd400", 1, turn
                ),
            )
            word = Box(x=spot.x + 60, y=spot.y + 80, w=spot.w - 120, h=spot.h - 160)
            scene.write_on("POW!", word, _sized("decoration heading", 60, 28), "#d7261e")


def _swoosh(scene: Scene) -> None:
    """A 1990s office deck's swoosh along the bottom: two waves in its accents (below the credit line, on slides
    with one); and the slide's number ("7/12") in bold in the top right corner, clear of the swoosh."""
    palette = scene.palette
    if scene.placement.photo:
        return
    lowest = max((box.y + box.h for box in scene.occupied()), default=0.0)
    top = max(lowest + 12, 1036.0 if scene.credits else 900.0)
    height = HEIGHT - top
    if height >= 30:
        scene.under(
            _polygon(geometry.wave(1.2, 0.5), 0, top, WIDTH, height, palette.accent_2, 0.55),
            _polygon(geometry.wave(1.6, 0.45), 0, top + height * 0.25, WIDTH, height * 0.75, palette.accent, 0.8),
        )
    _slide_number(scene, _TOP_RIGHT, _BOTTOM_RIGHT, spec=_sized("decoration right", 26, 24, bold=True))


def _terminal(scene: Scene) -> None:
    """A terminal's: the window's title bar across the top, a prompt before the titles (a ">" or a "$"), a block
    cursor after the talk's title, pictures in windows of their own, and a status line along the bottom with the
    slide's number."""
    palette = scene.palette
    bar = palette.surface
    if not scene.placement.photo:
        scene.add(_rect(0, 0, WIDTH, 48, bar), _rect(0, 48, WIDTH, 2, palette.muted, 0.35))
        for index in range(3):
            scene.add(_ellipse(36 + index * 28, 26, 16, 16, palette.muted, 1.0 - 0.3 * index))
        scene.write_on("~/talk", Box(x=WIDTH / 2 - 200, y=16, w=400, h=32), "decoration centre", palette.muted)
    prompt = "$" if scene.theme.motif_variant % 3 == 0 else ">"
    for role in ("title",):
        if scene.present(role) and scene.spec(role) in _LEFT_TITLES and scene.theme.title_align == "left":
            _prompt(scene, role, prompt)
    if scene.slide_type == "title" and scene.present("title"):
        lines = scene.lines("title")
        last = lines[-1]
        size = last.h / 1.2
        cursor = Box(x=last.x + last.w + size * 0.2, y=last.y + size * 0.15, w=size * 0.55, h=size * 0.95)
        if cursor.x + cursor.w < WIDTH - 40:
            scene.add(_rect(cursor.x, cursor.y, cursor.w, cursor.h, palette.text))
    for index, role in enumerate(scene.pictures() if scene.slide_type in _FRAMED_TYPES else [], 1):
        box = scene.box(role)
        shown = scene.shown(role, Box(x=box.x, y=box.y + 40, w=box.w, h=box.h - 40))
        window = Box(x=shown.x, y=shown.y - 40, w=shown.w, h=shown.h + 40)
        scene.add(_rect(window.x, window.y, window.w, 40, bar), part_of=role)
        scene.over(_frame(window, palette.muted, 2, 0.8), part_of=role)
        name = Box(x=window.x + 14, y=window.y + 4, w=window.w - 28, h=32)
        if window.w > 300:
            evidence = f"./evidence_{scene.number + 1:02d}{index}.jpg"
            scene.write_on(evidence, name, "decoration", palette.muted, part_of=role)
    if not scene.placement.photo:  # (the status line, with the slide's number, "[07/12]", on a tag at its start)
        width = 112 if scene.total is None else 168
        scene.add(_rect(0, 1032, WIDTH, 48, bar))
        if scene.numbered:
            scene.add(_rect(0, 1032, width, 48, palette.accent))
            number = Box(x=16, y=1034, w=width - 32, h=30)
            scene.write_on(f"[{_count(scene, padded=True)}]", number, "decoration centre")


def _prompt(scene: Scene, role: str, prompt: str) -> None:
    """A prompt before a text that's aligned left: the text moves right to make room for it, and the prompt is as
    big as the text's first line, in the accent, where that line is."""
    box, spec = scene.box(role), scene.spec(role)
    lines = scene.lines(role)
    size = lines[0].h / 1.2
    style, _ = text_lines(scene.text(role), box, spec, scene.theme)
    width = fonts.text_width(f"{prompt} ", style.font, size, style.bold)
    moved = Box(x=box.x + width, y=box.y, w=box.w - width, h=box.h)
    scene.placement.boxes[role] = (moved, spec)
    lines = scene.lines(role)  # (as it fits now: maybe smaller)
    size = lines[0].h / 1.2
    prompt_box = Box(x=box.x, y=lines[0].y, w=width, h=lines[0].h)
    colour = scene.on(scene.behind(prompt_box), scene.palette.accent, color.LARGE_TEXT_CONTRAST)
    scene.write(
        prompt, prompt_box, _sized("decoration heading", size, align="left", anchor="top", bold=style.bold), colour
    )


def _blueprint(scene: Scene) -> None:
    """A blueprint's: a border with registration marks in its corners, a dimension line under the title (arrows at
    both ends), figure plates around pictures (an outline just outside them, with ticks at its corners), and a
    title block in the bottom right corner with the slide's number."""
    palette = scene.palette
    line = palette.muted
    if not scene.placement.photo:
        scene.under(_frame(Box(x=20, y=20, w=WIDTH - 40, h=HEIGHT - 40), line, 2, 0.6))
        for cx, cy in ((20, 20), (WIDTH - 20, 20), (20, HEIGHT - 20), (WIDTH - 20, HEIGHT - 20)):
            scene.under(_rect(cx - 16, cy - 1, 32, 2, palette.text), _rect(cx - 1, cy - 16, 2, 32, palette.text))
    title = scene.title()
    if title is not None:
        ink = scene.ink(title)
        y = scene.box(title).y + scene.box(title).h + 12
        x0, x1 = ink.x, ink.x + ink.w
        if x1 - x0 > 80:
            scene.add(
                _rect(x0, y - 1, x1 - x0, 2, line),
                _rect(x0 - 1, y - 12, 2, 24, line),
                _rect(x1 - 1, y - 12, 2, 24, line),
                _polygon(((0.0, 0.5), (1.0, 0.0), (1.0, 1.0)), x0, y - 7, 18, 14, line),
                _polygon(((0.0, 0.0), (1.0, 0.5), (0.0, 1.0)), x1 - 18, y - 7, 18, 14, line),
            )
    for role in scene.pictures() if scene.slide_type in _FRAMED_TYPES else []:
        shown = scene.shown(role, _grown(scene.box(role), -12))
        plate = _grown(shown, 8)
        scene.add(_frame(plate, line, 1.5), part_of=role)
        for x, y in (
            (plate.x, plate.y),
            (plate.x + plate.w, plate.y),
            (plate.x, plate.y + plate.h),
            (plate.x + plate.w, plate.y + plate.h),
        ):
            tick = (_rect(x - 10, y - 1, 20, 2, palette.text), _rect(x - 1, y - 10, 2, 20, palette.text))
            scene.add(*tick, part_of=role)
    block = Box(x=WIDTH - 440, y=1034, w=400, h=30)
    if scene.numbered and not scene.placement.photo and scene.free(block, pad=2):
        scene.add(_rect(block.x, block.y, block.w, block.h, palette.background), _frame(block, palette.text, 2))
        scene.add(_rect(block.x + 150, block.y, 2, block.h, palette.text))
        scene.write_on("1:1", Box(x=block.x + 10, y=block.y, w=130, h=30), "decoration centre", palette.text)
        number = Box(x=block.x + 162, y=block.y, w=226, h=30)  # (the sheet's number of the set's: "# 07/12")
        scene.write_on(f"# {_count(scene, padded=True)}", number, "decoration centre", palette.text)


def _chalkboard(scene: Scene) -> None:
    """A chalkboard's: a wooden frame with a ledge along the bottom (chalk and an eraser on it, and the slide's
    number, "7/12", on a strip of tape at its left end), eraser smudges, a dashed chalk underline under the title,
    doodles on the big slides, and tape holding pictures up."""
    palette = scene.palette
    wood, dark = "#8b6b4a", "#5e4630"
    for _ in range(3):  # (smudges, where the board was wiped: long, thin strokes of an eraser)
        x = random_util.uniform(150, WIDTH - 650)
        y = random_util.uniform(120, HEIGHT - 160)
        width, height = random_util.uniform(500, 900), random_util.uniform(70, 130)
        turn = random_util.uniform(-7, 7)
        scene.under(_rect(x, y, width, height, "#ffffff", _faint(scene, "#ffffff", 0.03), height / 2, turn))
    scene.over(
        _rect(0, 0, WIDTH, 22, wood),
        _rect(0, 0, 22, HEIGHT, wood),
        _rect(WIDTH - 22, 0, 22, HEIGHT, wood),
        _rect(0, HEIGHT - 32, WIDTH, 32, wood),
        _rect(22, 22, WIDTH - 44, 3, dark),
        _rect(22, 22, 3, HEIGHT - 54, dark),
        _rect(WIDTH - 25, 22, 3, HEIGHT - 54, dark),
        _rect(22, HEIGHT - 35, WIDTH - 44, 3, dark),
    )
    chalk = [palette.text, palette.accent, palette.accent_2]
    for index, colour in enumerate(chalk[:2]):
        scene.over(_rect(WIDTH - 360 + index * 110, HEIGHT - 26, 84, 14, colour, corner=6, rotation=-2 + index * 3))
    label, number = _plate(64, 120)
    if scene.numbered and scene.free(number, pad=2):  # (a strip of masking tape on the ledge, the number in pencil)
        scene.over(_rect(label.x, label.y, label.w, label.h, "#e8dcc0", 0.92, corner=3))
        _slide_number(scene, number, spec="decoration centre", colour="#3d3d3d")
    scene.over(
        _rect(WIDTH - 600, HEIGHT - 30, 150, 20, "#c7a27a", corner=3),
        _rect(WIDTH - 600, HEIGHT - 16, 150, 10, "#3d3d3d", corner=2),
    )
    title = scene.title() or (
        "title"
        if scene.present("title") and scene.spec("title") in ("talk title", "section title", "section side title")
        else None
    )
    if title is not None:
        ink = scene.ink(title)
        y = min(ink.y + ink.h + 8, scene.box(title).y + scene.box(title).h + 10)
        width = min(ink.w, 420.0)
        x = ink.x if scene.theme.title_align == "left" else ink.x + (ink.w - width) / 2
        dashes = max(3, int(width // 70))
        for dash in range(dashes):
            start = x + dash * width / dashes
            wobble = random_util.uniform(-2, 2)
            scene.add(_line([(start, y + wobble), (start + width / dashes * 0.7, y - wobble)], 7, palette.accent, 0.9))
    if scene.big:
        for spot, kind in zip(_corner_spots(scene, 120, 70), ("star", "arrow", "ring"), strict=False):
            colour = random_util.choice(chalk[1:])
            if kind == "star":
                scene.under(_star(spot.x + 60, spot.y + 60, 110, colour, random_util.uniform(-20, 20), 0.85))
            elif kind == "arrow":
                scene.under(_polygon(geometry.arrow(), spot.x, spot.y + 30, 120, 60, colour, 0.85, -20))
            else:
                scene.under(_ring(spot.x + 60, spot.y + 60, 110, 90, colour, 6, 0.85))
    letters = [_grown(line, 8) for role in scene.texts() for line in scene.lines(role)]
    floor = CREDITS_BOX.y - 4 if scene.credits else HEIGHT  # (tape stays off the credit line)
    for role in scene.pictures() if scene.slide_type in _FRAMED_TYPES else []:
        shown = scene.shown(role, _grown(scene.box(role), -10))
        # (tape across its top corners, or else its bottom ones, a little higher up them if they'd reach the credit
        # line: where it's clear of the texts' letters)
        for y, turns in ((shown.y, (-35.0, 35.0)), (shown.y + shown.h, (35.0, -35.0))):
            tapes = [
                _rect(corner - 55, y - 17, 110, 34, "#e8dcc0", 0.75, rotation=turn)
                for corner, turn in zip((shown.x, shown.x + shown.w), turns, strict=True)
            ]
            lift = max(geometry.bounds(tape).y + geometry.bounds(tape).h for tape in tapes) - floor
            if lift > 40:
                continue
            if lift > 0:
                tapes = [_moved(tape, -lift) for tape in tapes]
            if not any(_overlaps(geometry.bounds(tape), area) for tape in tapes for area in letters):
                scene.over(*tapes, part_of=role)
                break


def _newsprint(scene: Scene) -> None:
    """A newspaper's: a masthead's rules across the top, with the edition's numbers over them (the volume in Roman
    numerals, three stars, the page of the paper's pages: "7/12"); a thin rule under the title; rules between
    columns; thin outlines around its (grayscale) photos."""
    palette = scene.palette
    ink = palette.text
    if not scene.placement.photo:
        scene.add(_rect(MARGIN, 47, WIDTH - 2 * MARGIN, 3, ink), _rect(MARGIN, 53, WIDTH - 2 * MARGIN, 1, ink))
        if scene.numbered:
            scene.write_on(_roman(scene.number + 1), Box(x=MARGIN, y=16, w=300, h=30), "decoration", palette.muted)
            page = Box(x=WIDTH - MARGIN - 300, y=16, w=300, h=30)
            folio = _count(scene) if scene.total is not None else f"A{scene.number + 1}"
            scene.write_on(folio, page, "decoration right", palette.muted)
        for index in range(3):
            scene.add(_star(WIDTH / 2 - 30 + index * 30, 30, 20, ink))
    title = scene.title()
    if title is not None:
        box = scene.box(title)
        scene.add(_rect(MARGIN, box.y + box.h + 14, WIDTH - 2 * MARGIN, 1, ink))
    columns = sorted(
        (role for role in scene.placement.boxes if role.startswith("content_") and role in scene.roles),
        key=lambda role: scene.box(role).x,
    )
    divided = any(shape.role == "divider" for shape in scene.placement.shapes)  # (a layout's own rule between them)
    for left, right in zip(columns, columns[1:], strict=False):
        first, second = scene.box(left), scene.box(right)
        if second.x > first.x + first.w and abs(second.y - first.y) < 40 and not divided:
            middle = (first.x + first.w + second.x) / 2  # (a rule between them, which comes in with the second)
            scene.add(_rect(middle - 0.5, first.y, 1, 980 - first.y, ink), part_of=right)
    for role in scene.pictures() if scene.slide_type in _FRAMED_TYPES else []:
        shown = scene.shown(role)
        scene.add(_frame(_grown(shown, 2), ink, 2), part_of=role)


def _swiss(scene: Scene) -> None:
    """A Swiss poster's: a three-column grid of thin lines behind everything, a heavy black rule across the top with
    the slide's number ("07/12") over its right end, and one red block per slide (a square at the rule's left end; on
    its big slides, a big circle where there's room)."""
    palette = scene.palette
    ink, red = palette.text, palette.accent_2
    grid = _faint(scene, ink, 0.12, stacked=2)  # (as strong as the texts over its lines allow: on red, none)
    if not scene.placement.photo:
        for column in range(1, 3) if grid >= 0.04 else ():
            x = MARGIN + column * (WIDTH - 2 * MARGIN) / 3
            scene.under(_rect(x, 48, 1.5, HEIGHT - 96, ink, grid))
        scene.add(_rect(MARGIN, 48, WIDTH - 2 * MARGIN, 4, ink))
        _slide_number(scene, Box(x=WIDTH - MARGIN - 160, y=16, w=160, h=30), colour=ink, padded=True)
        if not scene.big:
            scene.add(_rect(MARGIN, 18, 26, 26, red))
    if scene.big and not scene.photo:
        for size in (720.0, 560.0, 420.0):
            spot = Box(x=WIDTH - size + size * 0.18, y=-size * 0.18, w=size, h=size)
            if scene.free(spot, pad=24):
                scene.under(_ellipse(spot.x + size / 2, spot.y + size / 2, size, size, red))
                break


_MOTIFS: Final[dict[str, Callable[[Scene], None]]] = {
    "keynote": _keynote,
    "minimal": _minimal,
    "corporate": _corporate,
    "lecture": _lecture,
    "blobs": _blobs,
    "ornate": _ornate,
    "crayon": _crayon,
    "brutal": _brutal,
    "synthwave": _synthwave,
    "starburst": _starburst,
    "comic": _comic,
    "swoosh": _swoosh,
    "terminal": _terminal,
    "blueprint": _blueprint,
    "chalkboard": _chalkboard,
    "newsprint": _newsprint,
    "swiss": _swiss,
}
