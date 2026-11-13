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
import itertools
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator.design import color, fonts, geometry, layers
from talkgenerator.design.engine import (
    CREDITS_BOX,
    FULL,
    HEIGHT,
    KIDS_BADGE,
    KIDS_BADGE_MIDDLE,
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
# The slides a motif saves its big pieces for (and the closer, after a talk's last slide, D76, as its title slide
# has them)
_BIG_TYPES: Final = frozenset({"title", "section", "questions", "closer"})
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
        """Whether it's one of the slides a motif saves its big pieces for: a title, a section, "Questions?", the
        closer."""
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

    def occupied(self, letters: bool = False, ignoring: Sequence[str] = (), shapes: bool = True) -> list[Box]:
        """Where its elements (but those ignored) and its layout's shapes are (unless not shapes; but those over the
        whole slide, and its thin decoration, such as a title's underline): its texts' boxes, or (with letters) only
        where their lines' letters are."""
        boxes = []
        for role in self.placement.boxes:
            element = self.roles.get(role)
            if element is None or role in ignoring:
                continue
            if letters and isinstance(element, TextElement):
                boxes += [_grown(line, 12) for line in self.lines(role)]
            else:
                boxes.append(self.box(role))
        for shape in [*self.placement.shapes, *self.placement.overlays] if shapes else ():
            if shape.box != FULL and shape.role != "decoration":
                boxes.append(geometry.bounds(shape))
        return boxes

    def free(
        self, box: Box, pad: float = 16, letters: bool = False, ignoring: Sequence[str] = (), shapes: bool = True
    ) -> bool:
        """Whether a decoration in the box would keep clear of the slide's texts (their boxes, or with letters only
        their letters), pictures and panels (by the pad; but the elements ignored, such as a title its label goes
        behind, and the layout's shapes, unless shapes: a band a text is on), and of its credit line, and stay on the
        slide."""
        if box.x < 0 or box.y < 0 or box.x + box.w > WIDTH or box.y + box.h > HEIGHT:
            return False
        if self.credits and _overlaps(_grown(CREDITS_BOX, 2), box):
            return False
        if any(_overlaps(_grown(other, pad), box) for other in self.kept):
            return False
        return not any(_overlaps(_grown(other, pad), box) for other in self.occupied(letters, ignoring, shapes))

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


# THE KINDERGARTEN'S (D77): four sets of decoration, of which a kids member has one (crayon drawings, a sticker book, a
# school notebook, paper cut-outs), each in its member's palette's colours (see _paints), so that its palettes show:
# only a sun stays yellow, and a crayon drawing's hills green

_SUN_RAYS: Final = "#ffd23f"
_SUN_DISC: Final = "#ffbf00"
_HILLS: Final = ("#8ac926", "#5fb53c", "#7cc242")
_WHITE: Final = "#ffffff"
_PEEL: Final = "#e9e4dc"  # the back of a sticker, where it peels off
_CARD: Final = "#fffdf8"  # a card of white paper
# A rectangle and a circle as polygons, whose corners scissors can move a little (see _snipped)
_RECTANGLE: Final = ((0.0, 0.0), (0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0), (0.0, 1.0), (0.0, 0.5))
_CIRCLE: Final = tuple(
    (round(0.5 + 0.5 * math.cos(2 * math.pi * index / 32), 4), round(0.5 + 0.5 * math.sin(2 * math.pi * index / 32), 4))
    for index in range(32)
)


def _paints(palette: Palette) -> list[str]:
    """The colours a kindergarten's decoration is in, from its member's palette, so that its palettes show: its two
    accents (one darker than a crayon, as an accent made darker to read as a text is, as light as a crayon again, or
    as near that as it gets while it still shows on the paper), and its paper's own hue as a paint, as light as it
    gets while it shows well."""
    paper = palette.background
    paints = []
    for colour in (palette.accent, palette.accent_2):
        hue, saturation, lightness = color.to_hsl(colour)
        paint = colour
        for step in range(round((0.5 - lightness) / 0.02) + 1) if lightness < 0.5 else ():
            lighter = color.hsl(hue, saturation, 0.5 - 0.02 * step)
            if color.contrast(lighter, paper) >= _SHOWS:
                paint = lighter
                break
        paints.append(paint)
    hue = color.to_hsl(paper)[0]
    for lightness in (0.6, 0.57, 0.54, 0.51, 0.48, 0.45, 0.42, 0.39, 0.36):
        own = color.hsl(hue, 0.8, lightness)
        if color.contrast(own, paper) >= _SHOWS + 0.3:
            break
    return [*paints, own]


# How much contrast a kindergarten's paint has with its paper at least, so that it shows (as a shape, not a text)
_SHOWS: Final = 1.5


def _under_title(scene: Scene, title: str, most: float = 520.0) -> tuple[float, float, float]:
    """Where a line under a title goes: its left end, its height and its width (as wide as the title's letters, at
    most most), under their middle (or from their left end, for a title aligned left)."""
    ink = scene.ink(title)
    width = min(ink.w, most)
    x = ink.x if scene.theme.title_align == "left" else ink.x + (ink.w - width) / 2
    y = min(scene.box(title).y + scene.box(title).h + 12, ink.y + ink.h + 10)
    return x, y, width


def _framed(scene: Scene) -> list[str]:
    """The roles of the slide's pictures that its decoration frames (in boxes of their own, on the slide types whose
    pictures a motif may frame)."""
    return scene.pictures() if scene.slide_type in _FRAMED_TYPES else []


def _shadowed(
    shape: ShapeElement, ink: str, right: float = 5, down: float = 7, opacity: float = 0.2
) -> tuple[ShapeElement, ShapeElement]:
    """A shape with a hard shadow under it (paper's, a sticker's): the shape again in ink, see-through, moved right
    and down."""
    box = shape.box
    moved = Box(x=box.x + right, y=box.y + down, w=box.w, h=box.h)
    return shape.model_copy(update={"box": moved, "color": ink, "opacity": opacity}), shape


def _snipped(points: geometry.Points, amount: float = 0.012) -> geometry.Points:
    """A shape's corners each moved a little (by up to amount of its box, staying in it), as scissors cut it."""
    return tuple(
        (
            round(min(1.0, max(0.0, x + random_util.uniform(-amount, amount))), 4),
            round(min(1.0, max(0.0, y + random_util.uniform(-amount, amount))), 4),
        )
        for x, y in points
    )


def _wobbly(
    start: geometry.Point, end: geometry.Point, overshoot: float = 0.0, wobble: float = 2.0, steps: int = 6
) -> list[geometry.Point]:
    """A line drawn by hand from start to end (and a little past both, by overshoot), wobbling a little on its way."""
    (x0, y0), (x1, y1) = start, end
    length = math.hypot(x1 - x0, y1 - y0) or 1.0
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    points = []
    for index in range(steps + 1):
        along = -overshoot + (length + 2 * overshoot) * index / steps
        off = random_util.uniform(-wobble, wobble) if 0 < index < steps else 0.0
        points.append((x0 + dx * along - dy * off, y0 + dy * along + dx * off))
    return points


def _scatter(
    scene: Scene,
    count: int,
    sizes: tuple[float, float],
    draw: Callable[[float, float, float], None],
    top: bool = True,
    letters: bool = False,
    edges: tuple[float, float] = (30.0, 62.0),
    rows: tuple[float, float] = (22.0, 40.0),
) -> None:
    """Up to count pieces of decoration (confetti, stickers, doodles, paper shapes) in free spots along the slide's
    sides (as far in from its left and right edges as edges says), and along its bottom (and its top, if top: as far
    in as rows says), each of a size the seed picks between sizes, drawn by draw from its middle and its size: never
    behind a text (its box, or with letters only its letters)."""
    candidates: list[tuple[float, float]] = []
    for edge in (*edges, *(WIDTH - edge for edge in reversed(edges))):
        candidates += [(edge, float(down)) for down in range(90, HEIGHT - 80, 80)]
    for across in range(200, WIDTH - 200, 160):
        candidates.append((float(across), HEIGHT - rows[1]))
        if top:
            candidates.append((float(across), rows[0]))
    random_util.shuffle(candidates)
    placed: list[Box] = []
    for x, y in candidates:
        if len(placed) >= count:
            break
        size = random_util.uniform(*sizes)
        spot = Box(x=x - size / 2, y=y - size / 2, w=size, h=size)
        if not scene.free(spot, pad=12, letters=letters) or any(_overlaps(_grown(other, 40), spot) for other in placed):
            continue
        placed.append(spot)
        draw(x, y, size)


def _confetti(
    scene: Scene, colours: Sequence[str], count: int, sizes: tuple[float, float] = (22, 44), top: bool = True
) -> None:
    """A few pieces of confetti (dots, stars, triangles, rings) in free spots along the slide's edges (and along its
    top, if top), each turned a little: never behind a text."""

    def piece(x: float, y: float, size: float) -> None:
        colour = random_util.choice(colours)
        kind = random_util.choice(("dot", "star", "triangle", "ring"))
        turn = random_util.uniform(-25, 25)
        if kind == "dot":
            scene.under(_ellipse(x, y, size * 0.7, size * 0.7, colour))
        elif kind == "star":
            scene.under(_star(x, y, size, colour, turn))
        elif kind == "triangle":
            scene.under(
                _polygon(geometry.triangle(), x - size / 2, y - size / 2, size, size * 0.9, colour, rotation=turn)
            )
        else:
            scene.under(_ring(x, y, size * 0.8, size * 0.8, colour, max(4.0, size / 7)))

    _scatter(scene, count, sizes, piece, top)


# Crayon drawings


def _crayon(scene: Scene) -> None:
    """Crayon drawings: a crayon squiggle under the title, bunting across the top, confetti along the edges (never
    behind a text), pictures in a box a crayon drew around them; on the title slide a sun, a cloud and hills with
    flowers around a white card; a big sun with a section's number; and the slide's number ("7/12") in a crayon
    circle in the bottom right corner."""
    palette = scene.palette
    paints = _paints(palette)
    title = scene.title()
    if title is not None:
        x, y, width = _under_title(scene, title)
        squiggle = geometry.squiggle(x, y, width, 7, max(2.0, width / 130))
        scene.add(_line(squiggle, 10, paints[scene.number % len(paints)]))
    if not scene.photo:
        if scene.placement.layout == "v5/kids-title":
            _scenery(scene, paints)
        else:
            _bunting(scene, paints, -10, WIDTH + 10, 2, 16, 34, 42)
    elif (span := _beside_side_photo(scene)) is not None:  # (a picture filling one side: bunting across the other)
        _bunting(scene, paints, *span, 2, 12, 34, 42)
    if scene.placement.layout == "v5/kids-section":
        _sun(scene, KIDS_BADGE, badge=True)
    _, number = _plate(WIDTH - 44 - 116, 116)
    # (before the confetti, which keeps clear of it)
    if (
        not scene.placement.photo
        and scene.free(number, pad=4)
        and _slide_number(scene, number, spec="decoration centre", colour=palette.text)
    ):
        circle = Box(x=number.x - 18, y=number.y - 2, w=number.w + 36, h=number.h + 4)
        _crayon_circle(scene, circle, paints[(scene.number + 1) % len(paints)])
        scene.kept.append(circle)
    _confetti(scene, paints, 6 if scene.big else 4, (30, 56), top=scene.photo)
    for index, role in enumerate(_framed(scene)):
        _crayon_frame(scene, role, paints[(scene.number + index + 2) % len(paints)])
    if scene.slide_type in ("section", "questions", "closer"):
        _sun(scene, Box(x=WIDTH - 330, y=40, w=280, h=280))


def _crayon_frame(scene: Scene, role: str, colour: str) -> None:
    """A box a crayon drew around a picture: a stroke along each of its sides, each a little past its corners."""
    shown = scene.shown(role, _grown(scene.box(role), -18))
    frame = _grown(shown, 9)
    corners = [
        (frame.x, frame.y),
        (frame.x + frame.w, frame.y),
        (frame.x + frame.w, frame.y + frame.h),
        (frame.x, frame.y + frame.h),
    ]
    for start, end in zip(corners, [*corners[1:], corners[0]], strict=True):
        scene.add(_line(_wobbly(start, end, 9, 2.0), 8, colour), part_of=role)


def _crayon_circle(scene: Scene, around: Box, colour: str, width: float = 5) -> None:
    """A circle drawn by hand around a box: two strokes, the second going on a little past where the first began."""
    cx, cy = around.x + around.w / 2, around.y + around.h / 2
    start = random_util.uniform(150, 210)
    scene.add(
        _line(geometry.arc(cx, cy, around.w / 2, around.h / 2, start, start + 200), width, colour),
        _line(geometry.arc(cx, cy, around.w / 2 * 1.03, around.h / 2 * 1.06, start + 180, start + 380), width, colour),
    )


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


def _sun(scene: Scene, box: Box, badge: bool = False) -> None:
    """A crayon sun: a yellow disc with a burst of rays behind it, if there's room; or a section's badge, with its
    number on the disc."""
    disc = _grown(box, -box.w * 0.19)
    if badge:
        scene.add(
            _polygon(geometry.burst(12, 0.62), box.x, box.y, box.w, box.h, _SUN_RAYS),
            _ellipse(disc.x + disc.w / 2, disc.y + disc.h / 2, disc.w, disc.h, _SUN_DISC),
        )
        scene.placement.colors["kicker"] = scene.on([_SUN_DISC], minimum=color.LARGE_TEXT_CONTRAST)
        scene.kept.append(box)
    elif scene.free(box, pad=8):
        scene.under(
            _polygon(geometry.burst(12, 0.62), box.x, box.y, box.w, box.h, _SUN_RAYS, rotation=8),
            _ellipse(box.x + box.w / 2, box.y + box.h / 2, box.w * 0.62, box.h * 0.62, _SUN_DISC),
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
    scene.under(_ellipse(x, y, size * 0.36, size * 0.36, _SUN_DISC))


def _scenery(scene: Scene, paints: Sequence[str]) -> None:
    """Crayon drawings' title slide: bunting across the top, a sun and a cloud, rolling hills with flowers along the
    bottom, and the title and subtitle on a white card with a thick crayon outline."""
    palette = scene.palette
    _bunting(scene, paints, -30, WIDTH + 30, 0, 70, 66, 84)
    _sun(scene, Box(x=WIDTH - 250, y=118, w=220, h=220))
    _cloud(scene, 70, 150, 230)
    scene.under(
        _ellipse(330, 1110, 1300, 560, _HILLS[0]),
        _ellipse(1480, 1150, 1500, 600, _HILLS[1]),
        _ellipse(900, 1220, 1500, 520, _HILLS[2]),
    )
    for x, y, colour in ((200, 925, paints[0]), (420, 880, paints[1]), (1580, 935, paints[2])):
        _flower(scene, x, y, 52, colour)
    if scene.present("title"):
        title = scene.box("title")
        card = Box(x=title.x - 50, y=title.y - 40, w=title.w + 100, h=480)
        scene.add(
            _rect(card.x + 12, card.y + 12, card.w, card.h, palette.text, corner=44),
            _rect(card.x, card.y, card.w, card.h, _WHITE, corner=44),
            _frame(card, paints[scene.theme.motif_variant % len(paints)], 10, corner=44),
        )


# A sticker book


def _stickers(scene: Scene) -> None:
    """A sticker book's: titles on white labels, stickers (stars, hearts, dots, smileys, flowers) along the edges,
    pictures as stickers with a white edge and a corner peeling off; on the title slide, a big label, a rainbow and
    stickers around it; a prize rosette with a section's number; and the slide's number ("7/12") on a sticker of its
    own in the bottom right corner."""
    palette = scene.palette
    paints = _paints(palette)
    title = scene.title()
    if title is not None:
        _label(scene, title, paints[scene.number % len(paints)])
    if scene.placement.layout == "v5/kids-title":
        _sticker_card(scene, paints)
    elif scene.placement.layout == "v5/kids-section":
        _rosette(scene, paints)
    pill, number = _plate(WIDTH - 44 - 124, 124)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        paint = paints[(scene.theme.motif_variant + 1) % len(paints)]
        corner = pill.h / 2
        shadow, rim = _shadowed(
            _rect(pill.x - 5, pill.y - 5, pill.w + 10, pill.h + 10, _WHITE, corner=corner + 5), palette.text, 3, 4, 0.18
        )
        scene.add(shadow, rim, _rect(pill.x, pill.y, pill.w, pill.h, paint, corner=corner))
        _slide_number(scene, number, spec="decoration centre", colour=scene.on([paint]))
        scene.kept.append(_grown(pill, 5))
    kinds = ("star", "heart", "dot", "smiley", "flower")

    def stick(x: float, y: float, size: float) -> None:  # (its white edge, turned, inside the spot)
        kind = random_util.choice(kinds)
        _sticker(scene, kind, x, y, size * 0.78, random_util.choice(paints), random_util.uniform(-18, 18))

    count = 6 if scene.placement.layout == "v5/kids-title" else 4 if scene.big else 2
    sizes = (120.0, 180.0) if scene.big else (80.0, 116.0)
    _scatter(scene, count, sizes, stick, letters=True, edges=(70.0, 120.0), rows=(76.0, 90.0))
    for role in _framed(scene):
        _sticker_picture(scene, role)


def _sticker(scene: Scene, kind: str, x: float, y: float, size: float, colour: str, turn: float) -> None:
    """A sticker, its middle at (x, y): a star, a heart, a dot with a shine, a smiley or a flower, in the colour, on a
    white edge, with a soft shadow under it (over the layout's shapes, such as a photo's shade: a sticker is stuck on
    top)."""
    ink = scene.palette.text
    rim = max(6.0, size * 0.09)
    box = Box(x=x - size / 2, y=y - size / 2, w=size, h=size)
    edge = _grown(box, rim)
    shapes = {"star": geometry.star(5, 0.5), "heart": geometry.heart(), "flower": geometry.scallop(6, 0.32)}
    if kind in shapes:
        backing = _polygon(shapes[kind], edge.x, edge.y, edge.w, edge.h, _WHITE, rotation=turn)
        face = _polygon(shapes[kind], box.x, box.y, box.w, box.h, colour, rotation=turn)
    else:
        backing = _ellipse(x, y, edge.w, edge.h, _WHITE)
        face = _ellipse(x, y, size, size, colour)
    scene.add(*_shadowed(backing, ink, 3, 5, 0.18), face)
    if kind == "dot":  # (a shine on it)
        scene.add(_ellipse(x - size * 0.17, y - size * 0.19, size * 0.3, size * 0.17, _WHITE, 0.7))
    elif kind == "flower":  # (its middle)
        scene.add(_ellipse(x, y, size * 0.34, size * 0.34, _SUN_DISC))
    elif kind == "smiley":  # (eyes and a smile, in ink)
        eye = size * 0.1
        scene.add(
            _ellipse(x - size * 0.16, y - size * 0.1, eye, eye * 1.4, ink),
            _ellipse(x + size * 0.16, y - size * 0.1, eye, eye * 1.4, ink),
            _line(geometry.arc(x, y + size * 0.02, size * 0.24, size * 0.2, 25, 155, 12), max(3.0, size * 0.05), ink),
        )


def _label(scene: Scene, title: str, paint: str) -> None:
    """A title on a white label (a sticker with round ends, edged in a paint): if it has two lines at most, and the
    label keeps clear of the slide's other elements."""
    if len(scene.lines(title)) > 2:
        return
    ink = scene.ink(title)
    label = Box(x=ink.x - 36, y=ink.y - 14, w=ink.w + 72, h=ink.h + 28)
    if not scene.free(label, pad=8, ignoring=(title,)):
        return
    corner = min(label.h / 2, 40.0)
    shadow, card = _shadowed(
        _rect(label.x, label.y, label.w, label.h, _WHITE, corner=corner), scene.palette.text, 4, 6, 0.16
    )
    scene.add(shadow, card, _frame(_grown(label, -7), paint, 3, corner=max(0.0, corner - 7)))
    scene.placement.colors[title] = scene.on([_WHITE], scene.palette.text, color.LARGE_TEXT_CONTRAST)
    scene.placement.on_fill.add(title)
    scene.kept.append(label)


def _sticker_picture(scene: Scene, role: str) -> None:
    """A picture as a sticker: a white edge with round corners and a soft shadow, its bottom right corner peeling off
    (where that keeps off the credit line)."""
    palette = scene.palette
    shown = scene.shown(role, _grown(scene.box(role), -16))
    edge = _grown(shown, 12)
    corner = 0.06 * min(shown.w, shown.h) + 12
    backing = _rect(edge.x, edge.y, edge.w, edge.h, _WHITE, corner=corner)
    scene.add(*_shadowed(backing, palette.text, 6, 8, 0.18), part_of=role)
    fold = min(56.0, 0.16 * min(edge.w, edge.h))
    peel = Box(x=edge.x + edge.w - fold, y=edge.y + edge.h - fold, w=fold, h=fold)
    if scene.credits and _overlaps(_grown(CREDITS_BOX, 2), peel):
        return
    # (where its corner was, the paper under it; over that, the sticker's back, folded over along the diagonal)
    cut = _polygon(((1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), peel.x, peel.y, fold, fold, palette.background)
    flap = _polygon(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), peel.x, peel.y, fold, fold, _PEEL)
    scene.over(cut, *_shadowed(flap, palette.text, 3, 3, 0.18), part_of=role)


def _sticker_card(scene: Scene, paints: Sequence[str]) -> None:
    """A sticker book's title slide: the title and subtitle on a big white label edged in a paint, with a rainbow
    sticker in a free corner (and stickers around it, which _stickers scatters)."""
    palette = scene.palette
    if scene.present("title"):
        title = scene.box("title")
        card = Box(x=title.x - 50, y=title.y - 40, w=title.w + 100, h=480)
        shadow, label = _shadowed(_rect(card.x, card.y, card.w, card.h, _WHITE, corner=48), palette.text, 8, 12, 0.16)
        paint = paints[scene.theme.motif_variant % len(paints)]
        scene.add(shadow, label, _frame(_grown(card, -14), paint, 6, corner=36))
        scene.kept.append(card)
    spots = _corner_spots(scene, 260, 40, letters=True)
    if spots:
        spot = spots[scene.theme.motif_variant % len(spots)]
        _rainbow(scene, spot.x, spot.y + 60, 260, paints)
        scene.kept.append(spot)


def _rainbow(scene: Scene, x: float, y: float, width: float, paints: Sequence[str]) -> None:
    """A rainbow sticker from (x, y), this wide: three bands of the paints, a shadow under them, and a white cloud at
    each end."""
    ink = scene.palette.text
    band = width / 2 * 0.2
    middle, base = x + width / 2, y + width / 2
    for index, colour in enumerate(paints[:3]):
        radius = width / 2 - index * band
        inner = (radius - band) / radius
        shape = _polygon(geometry.arch(inner), middle - radius, base - radius, 2 * radius, radius, colour)
        if index == 0:
            scene.under(_shadowed(shape, ink, 3, 5, 0.18)[0])
        scene.under(shape)
    for end in (x + band * 1.5, x + width - band * 1.5):
        for dx, dy, size in ((-0.9, 0.1, 1.5), (0.7, 0.15, 1.3), (0.0, -0.35, 1.6)):
            scene.under(_ellipse(end + dx * band, base + dy * band, size * band, size * band * 0.85, _WHITE))


def _rosette(scene: Scene, paints: Sequence[str]) -> None:
    """A section's prize rosette: two ribbon tails hanging under a scalloped badge of a paint, with a white middle,
    where the section's number goes."""
    palette = scene.palette
    badge = _grown(KIDS_BADGE, -40)
    middle = KIDS_BADGE_MIDDLE
    across = badge.x + badge.w / 2
    for side, turn in ((-1, 14.0), (1, -14.0)):
        tail = _polygon(
            geometry.ribbon(), across - 60 + side * 72, badge.y + badge.h - 190, 120, 280, paints[1], rotation=turn
        )
        scene.add(*_shadowed(tail, palette.text, 4, 6, 0.16))
    rosette = _polygon(geometry.scallop(16, 0.1), badge.x, badge.y, badge.w, badge.h, paints[0])
    ring = _grown(middle, 22)
    scene.add(
        *_shadowed(rosette, palette.text, 6, 8, 0.18),
        _ring(ring.x + ring.w / 2, ring.y + ring.h / 2, ring.w, ring.h, _WHITE, 8, 0.85),
        _ellipse(middle.x + middle.w / 2, middle.y + middle.h / 2, middle.w, middle.h, _WHITE),
    )
    scene.placement.colors["kicker"] = scene.on([_WHITE], palette.accent, color.LARGE_TEXT_CONTRAST)
    scene.kept.append(Box(x=KIDS_BADGE.x, y=KIDS_BADGE.y, w=KIDS_BADGE.w, h=KIDS_BADGE.h + 90))


# A school notebook


def _notebook(scene: Scene) -> None:
    """A school notebook's: ruled or squared paper (its pattern), a margin line down its left side, holes punched for
    a ring binder (or a spiral binding) along its left edge, a ballpoint underline (or a highlighter's stroke) under
    the title, ballpoint doodles in free spots (stars, spirals, hearts, smileys, flowers, suns, arrows), pictures
    printed and taped in; on the title slide, an exercise book's cover with a label; a circled number for a section;
    and the slide's number ("7/12") at the foot of the page, underlined twice. In its palette's pens: its accents and
    its muted colour."""
    palette = scene.palette
    paints = _paints(palette)
    pens = [palette.accent, palette.accent_2, palette.muted]
    cover = scene.placement.layout == "v5/kids-title"
    if cover:
        _exercise_book(scene, paints)
    elif not scene.photo:
        _margin(scene, palette.accent_2)
        _binding(scene)
    title = scene.title()
    if title is not None:
        if scene.theme.motif_variant % 3 == 0:
            _highlight(scene, title, paints[2])
        else:
            x, y, width = _under_title(scene, title, 560)
            scene.add(
                _line(_wobbly((x, y), (x + width, y - 3), 0, 1.5), 5, pens[0]),
                _line(_wobbly((x + width * 0.08, y + 11), (x + width * 0.88, y + 9), 0, 1.5), 4, pens[0]),
            )
    if scene.placement.layout == "v5/kids-section":
        _circled(scene, pens)
    _, number = _plate(WIDTH - 60 - 120, 120)
    if (
        not cover
        and not scene.placement.photo
        and scene.free(number, pad=4)
        and _slide_number(scene, number, spec="decoration centre", colour=pens[0])
    ):
        middle = number.x + number.w / 2
        scene.add(
            _line(
                _wobbly((middle - 40, number.y + number.h + 3), (middle + 40, number.y + number.h + 2), 0, 1),
                3,
                pens[1],
            ),
            _line(
                _wobbly((middle - 32, number.y + number.h + 9), (middle + 36, number.y + number.h + 8), 0, 1),
                3,
                pens[1],
            ),
        )
        scene.kept.append(Box(x=number.x, y=number.y, w=number.w, h=HEIGHT - number.y))
    elif cover and scene.numbered:  # (on the cover, in white)
        _slide_number(scene, number, spec="decoration centre", colour=_WHITE)
    if not scene.photo:
        doodles = ("star", "spiral", "heart", "smiley", "flower", "sun", "arrow")
        inks = [_WHITE] if cover else pens

        def doodle(x: float, y: float, size: float) -> None:
            _doodle(scene, random_util.choice(doodles), x, y, size, random_util.choice(inks))

        count = 5 if cover else 4 if scene.big else 2
        _scatter(scene, count, (64.0, 104.0), doodle, letters=True, edges=(140.0, 100.0), rows=(70.0, 90.0))
    for index, role in enumerate(_framed(scene)):
        _taped_in(scene, role, paints[(scene.number + index) % len(paints)])


def _margin(scene: Scene, colour: str) -> None:
    """A notebook's margin line down its left side, but where something's in the way there (a text's letters, a
    picture): it goes behind no text."""
    x = 74.0
    blocked = sorted(
        (box for box in scene.occupied(letters=True) if box.x < x + 6 and box.x + box.w > x - 4),
        key=lambda box: box.y,
    )
    top = 0.0
    for box in [*blocked, Box(x=x, y=HEIGHT, w=1, h=1)]:
        if box.y - top > 24:
            scene.under(_rect(x - 1.5, top, 3, box.y - top, colour, 0.7))
        top = max(top, box.y + box.h)


def _binding(scene: Scene) -> None:
    """Along a notebook's left edge, three holes punched for a ring binder, or a spiral binding's coils (one or the
    other, the same on all of a member's slides), where nothing else is."""
    palette = scene.palette
    hole = color.mix(palette.background, palette.text, 0.22)
    if scene.theme.motif_variant % 2:
        for y in (HEIGHT / 2 - 330, HEIGHT / 2, HEIGHT / 2 + 330):
            if scene.free(Box(x=22, y=y - 17, w=34, h=34), pad=4, letters=True):
                scene.under(_ellipse(39, y, 34, 34, hole))
        return
    metal = color.mix(palette.text, _WHITE, 0.5)
    for y in range(46, HEIGHT - 30, 50):
        if scene.free(Box(x=0, y=y - 14, w=56, h=28), pad=4, letters=True):
            scene.under(_ellipse(40, y, 14, 14, hole), _rect(-12, y - 6, 56, 12, metal, corner=6, rotation=-12))


def _highlight(scene: Scene, title: str, colour: str) -> None:
    """A highlighter's stroke across the lower part of each of a title's lines (two at most), as see-through as the
    title over it allows."""
    lines = scene.lines(title)[:2]
    behind = scene.backgrounds()
    opacity = 0.4
    title_colour = scene.palette.text
    while opacity > 0.1 and any(
        color.contrast(title_colour, color.mix(background, colour, opacity)) < color.BODY_CONTRAST
        for background in behind
    ):
        opacity = round(opacity - 0.05, 2)
    if opacity <= 0.1:
        return
    for line in lines:
        size = line.h / 1.2
        scene.add(
            _polygon(
                geometry.slanted(0.02),
                line.x - 12,
                line.y + size * 0.55,
                line.w + 24,
                size * 0.55,
                colour,
                opacity,
                -0.6,
            )
        )


def _doodle(scene: Scene, kind: str, x: float, y: float, size: float, colour: str) -> None:
    """A ballpoint doodle, its middle at (x, y), about size big: a star (five strokes, as children draw one), a
    spiral, a heart, a smiley, a flower, a sun, or a wavy arrow."""
    width = max(3.5, size * 0.05)
    half = size / 2
    if kind == "star":
        corners = [
            (
                x + half * math.sin(math.radians(144 * index)),
                y - half * math.cos(math.radians(144 * index)) + size * 0.05,
            )
            for index in range(6)
        ]
        scene.under(*(_line([start, end], width, colour) for start, end in itertools.pairwise(corners)))
    elif kind == "spiral":
        scene.under(_line(geometry.spiral(x, y, half, 2.6), width, colour))
    elif kind == "heart":
        outline = [(x - half + px * size, y - half + py * size * 0.9) for px, py in geometry.heart()]
        scene.under(_line(outline[:21], width, colour), _line([*outline[20:], outline[0]], width, colour))
    elif kind == "smiley":
        scene.under(
            _ring(x, y, size, size, colour, width),
            _ellipse(x - size * 0.16, y - size * 0.12, size * 0.08, size * 0.12, colour),
            _ellipse(x + size * 0.16, y - size * 0.12, size * 0.08, size * 0.12, colour),
            _line(geometry.arc(x, y + size * 0.04, size * 0.24, size * 0.18, 25, 155, 12), width, colour),
        )
    elif kind == "flower":
        for index in range(5):
            angle = 2 * math.pi * index / 5 - math.pi / 2
            px, py = x + math.cos(angle) * size * 0.3, y + math.sin(angle) * size * 0.3
            scene.under(_ring(px, py, size * 0.36, size * 0.36, colour, width))
        scene.under(_ellipse(x, y, size * 0.2, size * 0.2, colour))
    elif kind == "sun":
        scene.under(_ring(x, y, size * 0.5, size * 0.5, colour, width))
        for index in range(8):
            angle = 2 * math.pi * index / 8
            start = (x + math.cos(angle) * size * 0.34, y + math.sin(angle) * size * 0.34)
            scene.under(_line([start, (x + math.cos(angle) * half, y + math.sin(angle) * half)], width, colour))
    else:  # (a wavy arrow, pointing right)
        shaft = geometry.squiggle(x - half, y, size * 0.92, size * 0.08, 1.2, 16)
        tip = shaft[-1]
        scene.under(
            _line(shaft, width, colour),
            _line([(tip[0] - size * 0.2, tip[1] - size * 0.16), tip], width, colour),
            _line([(tip[0] - size * 0.2, tip[1] + size * 0.16), tip], width, colour),
        )


def _taped_in(scene: Scene, role: str, tape: str) -> None:
    """A picture printed with a white edge and a thin shadow, taped in with two strips of washi tape across its top
    corners (or its bottom ones)."""
    shown = scene.shown(role, _grown(scene.box(role), -14))
    edge = _grown(shown, 10)
    scene.add(*_shadowed(_rect(edge.x, edge.y, edge.w, edge.h, _WHITE), scene.palette.text, 3, 4, 0.16), part_of=role)
    _tape(scene, role, shown, tape, 0.8)


def _tape(scene: Scene, role: str, shown: Box, colour: str, opacity: float) -> None:
    """Two strips of tape holding a picture up: across its top corners, or else its bottom ones (a little higher up
    them if they'd reach the credit line), where they're clear of the texts' letters."""
    letters = [_grown(line, 8) for text in scene.texts() for line in scene.lines(text)]
    floor = CREDITS_BOX.y - 4 if scene.credits else HEIGHT  # (tape stays off the credit line)
    for y, turns in ((shown.y, (-35.0, 35.0)), (shown.y + shown.h, (35.0, -35.0))):
        tapes = [
            _rect(corner - 55, y - 17, 110, 34, colour, opacity, rotation=turn)
            for corner, turn in zip((shown.x, shown.x + shown.w), turns, strict=True)
        ]
        lift = max(geometry.bounds(tape).y + geometry.bounds(tape).h for tape in tapes) - floor
        if lift > 40:
            continue
        if lift > 0:
            tapes = [_moved(tape, -lift) for tape in tapes]
        if not any(_overlaps(geometry.bounds(tape), area) for tape in tapes for area in letters):
            scene.over(*tapes, part_of=role)
            return


def _exercise_book(scene: Scene, paints: Sequence[str]) -> None:
    """A notebook's title slide, its cover: a cover of a paint over the whole slide, a cloth spine along its left edge
    with a seam, and the title and subtitle on a white label with a double edge (doodles on the cover in white come
    later)."""
    palette = scene.palette
    cover = paints[scene.theme.motif_variant % len(paints)]
    scene.under(_rect(0, 0, WIDTH, HEIGHT, cover), _rect(0, 0, 110, HEIGHT, color.mix(cover, palette.text, 0.35)))
    for y in range(28, HEIGHT - 20, 46):  # (the seam's stitches)
        scene.under(_rect(124, y, 4, 22, _WHITE, 0.7))
    if scene.present("title"):
        title = scene.box("title")
        # (down to where the other kids' cards end: its double edge kept clear of the subtitle's second line, the
        # presenter's job, D81)
        label = Box(x=title.x - 60, y=title.y - 50, w=title.w + 120, h=490)
        scene.add(
            *_shadowed(_rect(label.x, label.y, label.w, label.h, _WHITE, corner=28), palette.text, 6, 9, 0.22),
            _frame(_grown(label, -12), cover, 4, corner=18),
            _frame(_grown(label, -22), cover, 1.5, corner=10),
        )
        scene.kept.append(label)


def _circled(scene: Scene, pens: Sequence[str]) -> None:
    """A section's number circled in ballpoint, with rays doodled around the circle (a sun)."""
    middle = KIDS_BADGE_MIDDLE
    cx, cy, radius = middle.x + middle.w / 2, middle.y + middle.h / 2, middle.w / 2
    start = random_util.uniform(200, 250)
    scene.add(
        _line(geometry.arc(cx, cy, radius, radius * 0.96, start, start + 210, 40), 9, pens[0]),
        _line(geometry.arc(cx, cy, radius * 1.04, radius, start + 190, start + 390, 40), 9, pens[0]),
    )
    for index in range(12):
        angle = 2 * math.pi * (index + 0.5) / 12
        inner, outer = radius + 36, radius + (96 if index % 2 == 0 else 68)
        ray = [(cx + inner * math.cos(angle), cy + inner * math.sin(angle))]
        ray.append((cx + outer * math.cos(angle), cy + outer * math.sin(angle)))
        scene.add(_line(ray, 8, pens[1]))
    scene.placement.colors["kicker"] = scene.on(scene.backgrounds(), scene.palette.accent, color.LARGE_TEXT_CONTRAST)
    scene.kept.append(KIDS_BADGE)


# Paper cut-outs


def _cutouts(scene: Scene) -> None:
    """Paper cut-outs': shapes cut from construction paper in its palette's colours, a little uneven as scissors cut
    them, each with a small shadow: a strip with a pinked edge under the title, layered paper in two of the slide's
    corners, shapes (hearts, stars, circles, leaves, triangles) along its edges, pictures on paper mats turned a
    little; on the title slide, paper hills, a sun and clouds around a paper card; a paper flower with a section's
    number; and the slide's number ("7/12") on a paper tag in the bottom right corner."""
    palette = scene.palette
    paints = _paints(palette)
    ink = palette.text
    title = scene.title()
    if title is not None:
        x, y, width = _under_title(scene, title, 460)
        strip = _polygon(geometry.pinked(max(6, int(width // 36)), 0.4), x, y - 6, width, 22, paints[scene.number % 3])
        scene.add(*_shadowed(strip, ink, 3, 4, 0.2))
    if scene.placement.layout == "v5/kids-title":
        _paper_landscape(scene, paints)
    elif scene.placement.layout == "v5/kids-section":
        _paper_flower(scene, paints)
    tag, number = _plate(WIDTH - 44 - 124, 124)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        paint = paints[(scene.theme.motif_variant + 1) % len(paints)]
        shape = _polygon(_snipped(_RECTANGLE, 0.03), tag.x, tag.y, tag.w, tag.h, paint, rotation=-2)
        scene.add(*_shadowed(shape, ink, 3, 4, 0.2))
        _slide_number(scene, number, spec="decoration centre", colour=scene.on([paint]))
        scene.kept.append(_grown(tag, 4))
    if not scene.photo and scene.placement.layout not in ("v5/kids-title", "v5/kids-section"):
        for corner in _CORNER_PAIRS[scene.theme.motif_variant % len(_CORNER_PAIRS)]:
            _paper_corner(scene, corner, paints)
    kinds = {"heart": geometry.heart(), "star": geometry.star(5, 0.5), "circle": _CIRCLE, "leaf": geometry.leaf()}

    def cut(x: float, y: float, size: float) -> None:
        kind = random_util.choice(tuple(kinds))
        height = size * (0.5 if kind == "leaf" else 1.0)
        shape = _polygon(
            _snipped(kinds[kind], 0.02),
            x - size / 2,
            y - height / 2,
            size,
            height,
            random_util.choice(paints),
            rotation=random_util.uniform(-30, 30),
        )
        scene.under(*_shadowed(shape, ink, 3, 5, 0.2))

    count = 5 if scene.big else 3
    _scatter(scene, count, (46.0, 74.0), cut, letters=True, edges=(60.0, 110.0), rows=(60.0, 80.0))
    for index, role in enumerate(_framed(scene)):
        turn = 1.6 if (index + scene.theme.motif_variant) % 2 else -1.6
        _matted(scene, role, paints[(scene.number + index) % len(paints)], turn)
    if scene.slide_type in ("questions", "closer"):  # (and the closer, as its other big pieces: D76)
        spots = _corner_spots(scene, 200, 50, letters=True)
        if spots:
            spot = spots[0]
            star = _polygon(
                _snipped(geometry.star(5, 0.48), 0.015), spot.x, spot.y, spot.w, spot.h, paints[0], rotation=-12
            )
            scene.under(*_shadowed(star, ink, 5, 7, 0.2))


# Which corners of a slide cut-outs layer paper in (0: the top left, 1: the top right, 2: the bottom left; the bottom
# right is the slide's number's)
_CORNER_PAIRS: Final = ((0, 1), (0, 2), (1, 2))


def _paper_corner(scene: Scene, corner: int, paints: Sequence[str]) -> None:
    """Layered paper in a corner of the slide: quarter circles, each smaller and of another paint, with a hole of the
    paper's own colour in their middle, as large as there's room for."""
    palette = scene.palette
    for radius in (220.0, 170.0, 130.0):
        spot = Box(
            x=WIDTH - radius if corner == 1 else 0.0, y=HEIGHT - radius if corner == 2 else 0.0, w=radius, h=radius
        )
        if scene.free(spot, pad=16, letters=True):
            break
    else:
        return
    cx, cy = (WIDTH if corner == 1 else 0.0), (HEIGHT if corner == 2 else 0.0)
    layers = ((1.0, paints[0]), (0.76, paints[1]), (0.54, paints[2]), (0.32, palette.background))
    for share, colour in layers:
        size = radius * share
        disc = _polygon(_snipped(_CIRCLE, 0.008), cx - size, cy - size, 2 * size, 2 * size, colour)
        scene.under(*_shadowed(disc, palette.text, 5, 7, 0.18))
    scene.kept.append(spot)


def _matted(scene: Scene, role: str, paint: str, turn: float) -> None:
    """A picture on a mat of construction paper a little bigger than it, turned a little, with a shadow."""
    shown = scene.shown(role, _grown(scene.box(role), -26))
    mat = _grown(shown, 15)
    shape = _polygon(_snipped(_RECTANGLE, 0.006), mat.x, mat.y, mat.w, mat.h, paint, rotation=turn)
    scene.add(*_shadowed(shape, scene.palette.text, 6, 8, 0.2), part_of=role)


def _paper_landscape(scene: Scene, paints: Sequence[str]) -> None:
    """Paper cut-outs' title slide: layered paper hills along the bottom, a paper sun and a cloud, and the title and
    subtitle on a card of white paper with a strip of tape across its top."""
    palette = scene.palette
    ink = palette.text
    hills = (
        (330, 1130, 1300, 560, color.mix(paints[2], _WHITE, 0.25)),
        (1480, 1160, 1500, 600, paints[1]),
        (900, 1235, 1500, 520, paints[0]),
    )
    for cx, cy, width, height, colour in hills:
        hill = _polygon(_snipped(_CIRCLE, 0.004), cx - width / 2, cy - height / 2, width, height, colour)
        scene.under(*_shadowed(hill, ink, 0, -9, 0.18))
    sun = Box(x=WIDTH - 300, y=70, w=230, h=230)
    rays = _polygon(_snipped(geometry.burst(12, 0.6), 0.01), sun.x, sun.y, sun.w, sun.h, _SUN_RAYS, rotation=8)
    disc = _polygon(_snipped(_CIRCLE, 0.01), sun.x + 44, sun.y + 44, sun.w - 88, sun.h - 88, _SUN_DISC)
    scene.under(*_shadowed(rays, ink, 4, 6, 0.18), *_shadowed(disc, ink, 3, 4, 0.18))
    for px, py, size in ((70, 170, 120), (150, 130, 150), (240, 175, 110)):
        puff = _polygon(_snipped(_CIRCLE, 0.01), px, py, size, size * 0.8, _WHITE)
        scene.under(*_shadowed(puff, ink, 3, 5, 0.12))
    if scene.present("title"):
        title = scene.box("title")
        card = Box(x=title.x - 50, y=title.y - 40, w=title.w + 100, h=480)
        paper = _polygon(_snipped(_RECTANGLE, 0.004), card.x, card.y, card.w, card.h, _CARD)
        tape = _rect(card.x + card.w / 2 - 90, card.y - 22, 180, 44, paints[0], 0.8, rotation=-3)
        scene.add(*_shadowed(paper, ink, 8, 12, 0.18), tape)
        scene.kept.append(card)


def _paper_flower(scene: Scene, paints: Sequence[str]) -> None:
    """A section's paper flower: petals cut from one paint, its middle a circle of another, where the section's number
    goes; a stem and a leaf under it."""
    palette = scene.palette
    ink = palette.text
    badge = _grown(KIDS_BADGE, -20)
    middle = KIDS_BADGE_MIDDLE
    across = middle.x + middle.w / 2
    stem = _rect(across - 14, badge.y + badge.h - 60, 28, HEIGHT - badge.y - badge.h + 80, paints[2])
    leaf = _polygon(_snipped(geometry.leaf(), 0.01), across + 4, HEIGHT - 170, 170, 76, paints[2], rotation=-28)
    petals = _polygon(_snipped(geometry.scallop(8, 0.42), 0.006), badge.x, badge.y, badge.w, badge.h, paints[0])
    heart = _polygon(_snipped(_CIRCLE, 0.008), middle.x, middle.y, middle.w, middle.h, paints[1])
    for shape in (stem, leaf, petals, heart):
        scene.add(*_shadowed(shape, ink, 5, 7, 0.18))
    scene.placement.colors["kicker"] = scene.on([paints[1]], minimum=color.LARGE_TEXT_CONTRAST)
    scene.kept.append(Box(x=KIDS_BADGE.x, y=KIDS_BADGE.y, w=KIDS_BADGE.w, h=HEIGHT - KIDS_BADGE.y))


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
    if scene.slide_type in ("title", "closer") and scene.present("title"):  # (a cursor after the last words too)
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
    for role in _framed(scene):  # (masking tape holding them up)
        _tape(scene, role, scene.shown(role, _grown(scene.box(role), -10)), "#e8dcc0", 0.75)


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


# A WORKSHOP ON A WHITEBOARD (D77)

# Sticky notes' colours (Open Color's second shades): yellow, pink, blue, green, orange, violet
STICKIES: Final = ("#ffec99", "#fcc2d7", "#a5d8ff", "#b2f2bb", "#ffd8a8", "#d0bfff")
# A whiteboard's aluminium frame, and its edge
_ALUMINIUM: Final = ("#c3c9cf", "#8b939b")


def _workshop(scene: Scene) -> None:
    """A workshop on a whiteboard: the board's aluminium frame, with a marker tray along its bottom and two markers on
    it, a marker's stroke under the title, sticky notes with ideas scribbled on them (lines, no words) in a free
    corner, and on the big slides a cluster of them with dot-vote stickers, pictures held up by magnets, and the
    slide's number ("7/12") on a sticky flag in the bottom right corner."""
    palette = scene.palette
    ink = palette.text
    turn = scene.theme.motif_variant % len(STICKIES)
    notes = [*STICKIES[turn:], *STICKIES[:turn]]
    scene.over(
        _frame(Box(x=0, y=0, w=WIDTH, h=HEIGHT), _ALUMINIUM[0], 14),
        _rect(14, 14, WIDTH - 28, 2, _ALUMINIUM[1]),
        _rect(0, HEIGHT - 18, WIDTH, 18, _ALUMINIUM[0]),
        _rect(0, HEIGHT - 18, WIDTH, 2, _ALUMINIUM[1]),
    )
    if not scene.placement.photo:  # (two markers resting on the tray, their caps on)
        for index, (x, colour) in enumerate(((150.0, ink), (360.0, palette.accent))):
            scene.over(
                _rect(x, HEIGHT - 36, 170, 18, colour, corner=6, rotation=-1.5 + 3 * index),
                _rect(
                    x + 128,
                    HEIGHT - 38,
                    52,
                    22,
                    color.mix(colour, "#ffffff", 0.25),
                    corner=6,
                    rotation=-1.5 + 3 * index,
                ),
            )
    title = scene.title()
    if title is not None:  # (a marker's quick stroke, bowing a little, rising to its end)
        x, y, width = _under_title(scene, title, 600)
        stroke = [(x + width * step / 12, y + 5 * math.sin(math.pi * step / 12) - 0.6 * step) for step in range(13)]
        scene.add(_line(stroke, 9, palette.accent))
    flag, number = _plate(WIDTH - 60 - 136, 136)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        scene.add(
            _rect(flag.x, flag.y, flag.w, flag.h, notes[0], 0.92),
            _rect(flag.x, flag.y, 22, flag.h, color.mix(notes[0], ink, 0.25)),
        )
        _slide_number(
            scene, Box(x=number.x + 22, y=number.y, w=number.w - 22, h=number.h), spec="decoration centre", colour=ink
        )
        scene.kept.append(flag)
    for role in _framed(scene):
        _held_by_magnets(scene, role, palette.accent_2 if role.endswith("2") else palette.accent)
    if scene.photo:
        return
    if scene.big:
        _sticky_cluster(scene, notes)
    else:
        size = random_util.uniform(130, 170)
        spots = _corner_spots(scene, size, 54, letters=True)
        if spots:
            spot = spots[scene.number % len(spots)]
            _sticky(scene, spot, notes[scene.number % len(notes)], random_util.uniform(-6, 6))


def _sticky(scene: Scene, box: Box, colour: str, turn: float, votes: Sequence[str] = ()) -> None:
    """A sticky note: a square of the colour, turned a little, a shade darker along its glued top edge, a shadow under
    its curling bottom edge, ideas scribbled on it in marker (wavy lines, no words), and dot-vote stickers on it."""
    ink = scene.palette.text
    middle = (box.x + box.w / 2, box.y + box.h / 2)

    scene.add(
        _rect(box.x + 3, box.y + 12, box.w - 4, box.h - 6, ink, 0.16, rotation=turn),
        _rect(box.x, box.y, box.w, box.h, colour, rotation=turn),
        _turned_with(_rect(box.x, box.y, box.w, box.h * 0.18, color.mix(colour, ink, 0.06)), middle, turn),
    )
    for line in range(3):  # (three lines of scribbled idea, the last one shorter)
        y = box.y + box.h * (0.36 + 0.2 * line)
        width = box.w * (0.7 if line < 2 else 0.45) * random_util.uniform(0.85, 1.0)
        scribble = geometry.squiggle(box.x + box.w * 0.14, y, width, box.h * 0.025, width / 22, 24)
        scene.add(_line([geometry.turn(point, middle, turn) for point in scribble], max(3.0, box.w / 50), ink, 0.85))
    for index, vote in enumerate(votes):  # (dot-vote stickers along its bottom)
        x, y = geometry.turn((box.x + box.w * (0.22 + 0.19 * index), box.y + box.h * 0.86), middle, turn)
        scene.add(_ellipse(x, y, box.w * 0.13, box.w * 0.13, vote))


def _sticky_cluster(scene: Scene, notes: Sequence[str]) -> None:
    """A cluster of sticky notes in a free corner of a big slide (an idea per note, as a workshop sorts them), two of
    them dot-voted on."""
    palette = scene.palette
    for size in (170.0, 140.0, 120.0):
        spots = _corner_spots(scene, 2 * size + 24, 50, letters=True)
        if spots:
            break
    else:
        return
    spot = spots[0]
    for index in range(4):
        x = spot.x + (index % 2) * (size + 24) + random_util.uniform(-6, 6)
        y = spot.y + (index // 2) * (size + 24) + random_util.uniform(-6, 6)
        votes = [palette.accent, palette.accent_2, palette.accent][: (3, 0, 2, 0)[index]]
        _sticky(scene, Box(x=x, y=y, w=size, h=size), notes[index % len(notes)], random_util.uniform(-5, 5), votes)
    scene.kept.append(spot)


def _held_by_magnets(scene: Scene, role: str, colour: str) -> None:
    """A picture held up on the board by two round magnets at its top corners, with a soft shadow under it."""
    ink = scene.palette.text
    shown = scene.shown(role, _grown(scene.box(role), -12))
    scene.add(_rect(shown.x + 6, shown.y + 8, shown.w, shown.h, ink, 0.16), part_of=role)
    for x in (shown.x + 34, shown.x + shown.w - 34):
        scene.over(
            _ellipse(x + 2, shown.y + 6, 40, 40, ink, 0.25),
            _ellipse(x, shown.y + 2, 40, 40, colour),
            _ellipse(x - 7, shown.y - 6, 14, 9, "#ffffff", 0.6),
            part_of=role,
        )


# A 1990s DESKTOP (D77)

# A bevel's light edge, its shade and its dark edge; where the taskbar's top is (the slide's number in its tray goes
# where every slide's number goes, under the credit line); a folder's yellow
_BEVEL: Final = ("#ffffff", "#808080", "#202020")
_TASKBAR: Final = 1030.0
_FOLDER: Final = "#f2cf4a"
# The mouse's pointer, an arrow pointing up and left
_POINTER: Final = ((0.0, 0.0), (0.0, 0.78), (0.21, 0.6), (0.36, 0.94), (0.5, 0.88), (0.35, 0.56), (0.62, 0.56))


def _desktop(scene: Scene) -> None:
    """A 1990s computer's: the slide a window, with a title bar in the accent across its top (a document's name and
    its three buttons) and bevelled edges, and a taskbar along its bottom with the slide's number ("7/12") in its
    tray; pictures in windows of their own; on a big slide with nothing but texts, the desktop around a dialog box
    with the texts in it, a few icons and the mouse's pointer."""
    palette = scene.palette
    bar = palette.accent
    dialog = scene.big and not scene.photo and _dialog(scene)
    if not scene.placement.photo:
        if not dialog:  # (the window's title bar, with a document's icon, its name and its buttons, and its edges)
            scene.add(_rect(0, 0, WIDTH, 50, bar))
            scene.add(_rect(18, 12, 22, 27, "#ffffff"), _rect(22, 19, 14, 2, bar), _rect(22, 25, 14, 2, bar))
            scene.write_on("TALK.PPT", Box(x=54, y=17, w=400, h=30), _sized("decoration", 24, bold=True), "#ffffff")
            _window_buttons(scene, WIDTH - 10, 10, 30)
            scene.over(_rect(0, 50, 3, _TASKBAR - 50, _BEVEL[0]), _rect(WIDTH - 3, 50, 3, _TASKBAR - 50, _BEVEL[1]))
        scene.add(
            _rect(0, _TASKBAR, WIDTH, HEIGHT - _TASKBAR, palette.background), _rect(0, _TASKBAR, WIDTH, 2, "#ffffff")
        )
        scene.add(*_bevelled(Box(x=8, y=_TASKBAR + 6, w=130, h=36), palette.background))
        for index, colour in enumerate(("#d03b3b", "#3b9b3b", "#3b5bd0", "#e0b020")):  # (a button with an icon)
            scene.add(_rect(20 + (index % 2) * 13, _TASKBAR + 12 + (index // 2) * 12, 11, 10, colour))
        if scene.numbered:  # (the slide's number, in the tray at its right end)
            tray = Box(x=WIDTH - 8 - 200, y=_TASKBAR + 6, w=200, h=36)
            scene.add(*_bevelled(tray, palette.background, raised=False))
            _slide_number(
                scene, Box(x=tray.x + 10, y=1034, w=tray.w - 20, h=30), spec="decoration centre", colour=palette.text
            )
    for index, role in enumerate(_framed(scene), 1):
        _picture_window(scene, role, index)


def _bevelled(box: Box, face: str, raised: bool = True) -> list[ShapeElement]:
    """A box with a bevelled edge, raised (light along its top and left, dark along its bottom and right) or sunken
    (the other way around)."""
    light, shade = (_BEVEL[0], _BEVEL[2]) if raised else (_BEVEL[1], _BEVEL[0])
    return [
        _rect(box.x, box.y, box.w, box.h, face),
        _rect(box.x, box.y, box.w, 2, light),
        _rect(box.x, box.y, 2, box.h, light),
        _rect(box.x, box.y + box.h - 2, box.w, 2, shade),
        _rect(box.x + box.w - 2, box.y, 2, box.h, shade),
    ]


def _window_buttons(scene: Scene, right: float, top: float, size: float, part_of: str | None = None) -> None:
    """A window's three buttons, ending at right on its title bar: minimise, maximise and close, bevelled grey, their
    signs drawn as shapes."""
    face, ink = scene.palette.background, _BEVEL[2]
    for index in range(3):
        x = right - (3 - index) * (size + 4) + (4 if index == 2 else 0)
        scene.add(*_bevelled(Box(x=x, y=top, w=size, h=size - 2), face), part_of=part_of)
        if index == 0:
            sign = [_rect(x + size * 0.25, top + size * 0.62, size * 0.42, size * 0.1, ink)]
        elif index == 1:
            sign = [_frame(Box(x=x + size * 0.22, y=top + size * 0.18, w=size * 0.54, h=size * 0.5), ink, 2)]
            sign.append(_rect(x + size * 0.22, top + size * 0.18, size * 0.54, size * 0.12, ink))
        else:
            sign = [
                _rect(x + size * 0.2, top + size * 0.42, size * 0.58, size * 0.11, ink, rotation=angle)
                for angle in (45.0, -45.0)
            ]
        scene.add(*sign, part_of=part_of)


def _picture_window(scene: Scene, role: str, index: int) -> None:
    """A picture in a window of its own: a bevelled grey edge, and a title bar with its file's name and a close
    button."""
    palette = scene.palette
    box = scene.box(role)
    shown = scene.shown(role, Box(x=box.x + 6, y=box.y + 40, w=box.w - 12, h=box.h - 46))
    window = Box(x=shown.x - 6, y=shown.y - 40, w=shown.w + 12, h=shown.h + 46)
    scene.add(
        *_bevelled(window, palette.background),
        _rect(window.x + 4, window.y + 4, window.w - 8, 32, palette.accent),
        part_of=role,
    )
    close = window.x + window.w - 8
    scene.add(*_bevelled(Box(x=close - 26, y=window.y + 8, w=26, h=24), palette.background), part_of=role)
    scene.add(
        *(_rect(close - 21, window.y + 18, 16, 3, _BEVEL[2], rotation=angle) for angle in (45.0, -45.0)), part_of=role
    )
    if window.w > 300:
        name = f"PIC{scene.number + 1:02d}{index}.BMP"
        place = Box(x=window.x + 12, y=window.y + 5, w=window.w - 60, h=30)
        scene.write_on(name, place, _sized("decoration", 24, bold=True), "#ffffff", part_of=role)


def _dialog(scene: Scene) -> bool:
    """A big slide as the desktop: its colour (the second accent) over the whole slide, a dialog box around the slide's
    texts (a bevelled window with a title bar and a close button), a few icons down its left edge (a computer, a
    folder, a document) and the mouse's pointer by the dialog's corner. Only on a slide of nothing but texts, whose
    texts all fit in the dialog; whether it drew one."""
    palette = scene.palette
    elements = [scene.roles.get(role) for role in scene.placement.boxes]
    if any(element is not None and not isinstance(element, TextElement) for element in elements):
        return False
    if scene.placement.shapes or scene.placement.texts or not scene.texts():
        return False
    inks = [scene.ink(role) for role in scene.texts()]
    left, top = min(ink.x for ink in inks) - 70, min(ink.y for ink in inks) - 100
    right, bottom = max(ink.x + ink.w for ink in inks) + 70, max(ink.y + ink.h for ink in inks) + 60
    dialog = Box(x=max(left, 24.0), y=max(top, 24.0), w=0, h=0)
    dialog = dialog.model_copy(update={"w": min(right, WIDTH - 40) - dialog.x, "h": min(bottom, 1000.0) - dialog.y})
    if dialog.x > left or dialog.y > top or dialog.x + dialog.w < right or dialog.y + dialog.h < bottom:
        return False
    desktop = palette.accent_2
    scene.under(_rect(0, 0, WIDTH, HEIGHT, desktop))
    scene.under(*_bevelled(dialog, palette.background))
    scene.under(_rect(dialog.x + 4, dialog.y + 4, dialog.w - 8, 40, palette.accent))
    _window_buttons(scene, dialog.x + dialog.w - 10, dialog.y + 9, 28)
    scene.kept.append(dialog)
    for number, y in enumerate((70.0, 220.0, 370.0)):  # (icons, on the desktop beside the dialog)
        if scene.free(Box(x=40, y=y, w=90, h=90), pad=8, letters=True) and dialog.x > 150:
            _icon(scene, number, 40, y)
    tip = (dialog.x + dialog.w - 90, dialog.y + dialog.h - 70)
    pointer = Box(x=tip[0], y=tip[1], w=36, h=56)
    if scene.free(pointer, pad=6, letters=True):
        scene.add(
            _polygon(_POINTER, pointer.x - 3, pointer.y - 4, pointer.w + 7, pointer.h + 8, _BEVEL[2]),
            _polygon(_POINTER, pointer.x + 1, pointer.y + 3, pointer.w - 2, pointer.h - 4, "#ffffff"),
        )
    return True


def _icon(scene: Scene, kind: int, x: float, y: float) -> None:
    """A desktop's icon, 90 pixels square, from its top left corner: a computer (0), a folder (1) or a document (2)."""
    ink = _BEVEL[2]
    if kind == 0:  # (a monitor on its stand)
        scene.under(*_bevelled(Box(x=x + 8, y=y + 6, w=74, h=56), "#c0c0c0"))
        scene.under(_rect(x + 16, y + 14, 58, 40, "#000080"), _rect(x + 30, y + 62, 30, 8, "#808080"))
        scene.under(*_bevelled(Box(x=x + 14, y=y + 70, w=62, h=12), "#c0c0c0"))
    elif kind == 1:  # (a folder: its tab, and its body)
        scene.under(_rect(x + 8, y + 16, 34, 14, _FOLDER, corner=3), _rect(x + 8, y + 24, 74, 52, _FOLDER, corner=3))
        scene.under(_rect(x + 8, y + 74, 74, 3, color.mix(_FOLDER, ink, 0.4)))
    else:  # (a page, its corner folded, with lines of text)
        scene.under(
            _polygon(((0.0, 0.0), (0.7, 0.0), (1.0, 0.24), (1.0, 1.0), (0.0, 1.0)), x + 18, y + 6, 56, 76, "#ffffff")
        )
        scene.under(_polygon(((0.0, 0.0), (1.0, 1.0), (0.0, 1.0)), x + 57, y + 6, 17, 18, "#c0c0c0"))
        for line in range(4):
            scene.under(_rect(x + 26, y + 32 + line * 11, 36 if line < 3 else 22, 3, "#808080"))


# A CORKBOARD (D77)

_WOOD: Final = ("#9c6b3c", "#6e4826")  # a corkboard's wooden frame, and its inner edge
_PAPER: Final = "#fffdf6"  # an index card's paper, a polaroid's
_PINS: Final = ("#e03131", "#1c7ed6", "#2f9e44", "#f08c00", "#ae3ec9")  # push pins' heads (Open Color's)
_STRING: Final = "#c92a2a"  # a detective's red string
_CARD_LINES: Final = ("#e8590c", "#74c0fc")  # an index card's line along its top, and its ruled lines


def _corkboard(scene: Scene) -> None:
    """A corkboard: the board in a wooden frame, the title on an index card pinned to it, pictures as polaroids, pinned
    or taped up, index cards pinned in free spots (and on its big slides, pins with a red string between them), and
    the slide's number ("7/12") on a pinned tag."""
    palette = scene.palette
    start = scene.theme.motif_variant % len(_PINS)
    pins = [*_PINS[start:], *_PINS[:start]]
    scene.over(
        _rect(0, 0, WIDTH, 18, _WOOD[0]),
        _rect(0, 0, 18, HEIGHT, _WOOD[0]),
        _rect(WIDTH - 18, 0, 18, HEIGHT, _WOOD[0]),
        _rect(0, HEIGHT - 18, WIDTH, 18, _WOOD[0]),
        _frame(Box(x=18, y=18, w=WIDTH - 36, h=HEIGHT - 36), _WOOD[1], 3),
    )
    title = scene.title()
    if title is not None:
        _index_card(scene, title, pins[0])
    for index, role in enumerate(_framed(scene)):
        _polaroid(scene, role, pins[(index + 1) % len(pins)], taped=(index + scene.number) % 3 == 2)
    words = fonts.text_width(_count(scene), scene.theme.fonts.body, 28) + 20  # (as wide as its number needs)
    tag, number = _plate(WIDTH - 60 - 44 - words, 44 + words)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        scene.over(*_shadowed(_rect(tag.x, tag.y, tag.w, tag.h, _PAPER, rotation=-1.5), palette.text, 3, 4, 0.25))
        _pin(scene, tag.x + 20, tag.y + tag.h / 2, pins[2])
        text = Box(x=number.x + 40, y=number.y, w=number.w - 44, h=number.h)
        _slide_number(scene, text, spec="decoration centre", colour=palette.text)
        scene.kept.append(_grown(tag, 4))
    if scene.photo:
        return
    cards = 2 if scene.big else 1
    for size in (170.0, 140.0):
        spots = _corner_spots(scene, size, 60, letters=True)
        for spot in spots[scene.number % max(1, len(spots)) :][:cards]:
            if scene.free(spot, pad=8, letters=True):
                _pinned_card(scene, spot, pins[(scene.number + cards) % len(pins)], random_util.uniform(-5, 5))
                cards -= 1
        if cards <= 0:
            break
    if scene.big:
        _red_string(scene, pins)


def _pin(scene: Scene, x: float, y: float, colour: str, part_of: str | None = None) -> None:
    """A push pin's head, seen from above, its middle at (x, y): round, of the colour, with a shine and a shadow."""
    scene.over(
        _ellipse(x + 4, y + 6, 30, 30, scene.palette.text, 0.3),
        _ellipse(x, y, 30, 30, colour),
        _ellipse(x - 6, y - 7, 10, 7, "#ffffff", 0.7),
        part_of=part_of,
    )


def _index_card(scene: Scene, title: str, pin: str) -> None:
    """A title on an index card pinned to the board (a line along its top, the title on its white): if it has two lines
    at most, and the card keeps clear of the slide's other elements."""
    if len(scene.lines(title)) > 2:
        return
    ink = scene.ink(title)
    card = Box(x=ink.x - 44, y=ink.y - 26, w=ink.w + 88, h=ink.h + 44)
    if card.y < 22 or not scene.free(card, pad=8, ignoring=(title,)):
        return
    paper = _rect(card.x, card.y, card.w, card.h, _PAPER, corner=3)
    scene.add(
        *_shadowed(paper, scene.palette.text, 5, 7, 0.25),
        _rect(card.x + 14, card.y + 12, card.w - 28, 2, _CARD_LINES[0]),
    )
    _pin(scene, card.x + card.w / 2, card.y + 4, pin)
    scene.placement.colors[title] = scene.on([_PAPER], scene.palette.text, color.LARGE_TEXT_CONTRAST)
    scene.placement.on_fill.add(title)
    scene.kept.append(card)


def _polaroid(scene: Scene, role: str, pin: str, taped: bool) -> None:
    """A picture as a polaroid: on white with a wide bottom edge and a shadow, pinned at its top (or taped at two of
    its corners)."""
    box = scene.box(role)
    margin, bottom = 14.0, max(30.0, round(box.h * 0.14))
    inside = Box(x=box.x + margin, y=box.y + margin, w=box.w - 2 * margin, h=box.h - margin - bottom)
    shown = scene.shown(role, inside)
    paper = Box(x=shown.x - margin, y=shown.y - margin, w=shown.w + 2 * margin, h=shown.h + margin + bottom)
    shapes = _shadowed(_rect(paper.x, paper.y, paper.w, paper.h, _PAPER), scene.palette.text, 6, 9, 0.28)
    scene.add(*shapes, part_of=role)
    if taped:
        _tape(scene, role, paper, "#e8dcc0", 0.8)
    else:
        _pin(scene, paper.x + paper.w / 2, paper.y + 8, pin, part_of=role)


def _turned_with(shape: ShapeElement, middle: geometry.Point, turn: float) -> ShapeElement:
    """A shape on another (a line on a card), turned with it: moved where turning the other around its middle takes it,
    and turned as much."""
    x, y = geometry.turn((shape.box.x + shape.box.w / 2, shape.box.y + shape.box.h / 2), middle, turn)
    moved = Box(x=x - shape.box.w / 2, y=y - shape.box.h / 2, w=shape.box.w, h=shape.box.h)
    return shape.model_copy(update={"box": moved, "rotation": turn})


def _pinned_card(scene: Scene, spot: Box, pin: str, turn: float) -> None:
    """An index card pinned in a free spot, turned a little: a line along its top, ruled lines, a pin."""
    ink = scene.palette.text
    card = Box(x=spot.x, y=spot.y + spot.h * 0.18, w=spot.w, h=spot.h * 0.64)
    middle = (card.x + card.w / 2, card.y + card.h / 2)
    scene.add(
        _rect(card.x + 4, card.y + 6, card.w, card.h, ink, 0.25, rotation=turn),
        _rect(card.x, card.y, card.w, card.h, _PAPER, rotation=turn),
        _turned_with(_rect(card.x + 10, card.y + card.h * 0.2, card.w - 20, 2, _CARD_LINES[0]), middle, turn),
    )
    for line in range(1, 4):
        ruled = _rect(card.x + 10, card.y + card.h * (0.2 + 0.2 * line), card.w - 20, 1.5, _CARD_LINES[1])
        scene.add(_turned_with(ruled, middle, turn))
    _pin(scene, *geometry.turn((card.x + card.w / 2, card.y + 10), middle, turn), pin)
    scene.kept.append(spot)


def _red_string(scene: Scene, pins: Sequence[str]) -> None:
    """Pins in free spots near each other, with a detective's red string between them, where the string keeps clear of
    the slide's texts and pictures."""
    spots = _corner_spots(scene, 60, 80, letters=True)
    points = [(spot.x + 30, spot.y + 30) for spot in spots]
    strung: list[tuple[geometry.Point, geometry.Point]] = []
    for (x0, y0), (x1, y1) in itertools.combinations(points, 2):
        length = math.hypot(x1 - x0, y1 - y0)
        if length > 760 or len(strung) >= 3:
            continue
        steps = max(1, int(length // 36))
        along = [(x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps) for step in range(steps + 1)]
        if all(scene.free(Box(x=x - 7, y=y - 7, w=14, h=14), pad=4, letters=True) for x, y in along[1:-1]):
            strung.append(((x0, y0), (x1, y1)))
    for start, end in strung:
        scene.add(_line([start, end], 3, _STRING, 0.9))
    for index, point in enumerate(sorted({point for pair in strung for point in pair})):
        _pin(scene, *point, pins[index % len(pins)])


# A SPREADSHEET (D77)

_COLUMN: Final = 192.0  # a column's width
_ROW: Final = 54.0  # a row's height (its pattern's lines)
_HEADERS: Final = (56.0, 48.0)  # the rows' numbers' column's width, and the columns' letters' row's height
_SHEET_TABS: Final = 1032.0  # where the sheet's tabs start (under the credit line)


def _spreadsheet(scene: Scene) -> None:
    """A spreadsheet: its grid (its rows' lines are its pattern, its columns' lines shapes), a header row with its
    columns' letters and a header column with its rows' numbers (where nothing else is), the title a selected cell
    (outlined, with a handle in its corner), pictures with selection handles, and along the bottom the sheet's tabs,
    the slide's number ("7/12") on the open one."""
    palette = scene.palette
    header = palette.surface
    rule = color.mix(palette.background, palette.text, 0.13)  # (as its rows' lines, its pattern, are)
    left, top = _HEADERS
    if not scene.placement.photo:
        for column in range(1, 10):
            scene.under(_rect(left + column * _COLUMN, top, 1.5, _SHEET_TABS - top, rule))
        if scene.free(Box(x=0, y=0, w=WIDTH, h=top - 14), pad=0, letters=True):  # (letters count 12 pixels bigger)
            scene.add(_rect(0, 0, WIDTH, top, header), _rect(0, top - 1.5, WIDTH, 1.5, rule))
            for column in range(int((WIDTH - 16 - left) // _COLUMN)):  # (its columns' letters, of those that fit)
                place = Box(x=left + column * _COLUMN, y=16, w=_COLUMN, h=30)
                scene.write_on(chr(ord("A") + column), place, "decoration centre", palette.muted)
        if scene.free(Box(x=0, y=top, w=left, h=_SHEET_TABS - top), pad=2, letters=True):
            scene.add(
                _rect(0, top, left, _SHEET_TABS - top, header), _rect(left - 1.5, top, 1.5, _SHEET_TABS - top, rule)
            )
            for row in range(int((_SHEET_TABS - top) // _ROW)):  # (its rows' numbers)
                place = Box(x=16, y=top + row * _ROW + (_ROW - 30) / 2, w=left - 22, h=30)
                scene.write_on(str(row + 1), place, "decoration right", palette.muted)
        scene.add(_rect(0, _SHEET_TABS, WIDTH, HEIGHT - _SHEET_TABS, header), _rect(0, _SHEET_TABS, WIDTH, 1.5, rule))
        scene.write_on("+", Box(x=16, y=1034, w=40, h=30), "decoration centre", palette.muted)
        tab = Box(x=72, y=_SHEET_TABS, w=196, h=HEIGHT - _SHEET_TABS)
        for index in (1, 2):  # (the other sheets' tabs, closed)
            other = Box(x=tab.x + index * (tab.w + 8), y=tab.y + 6, w=tab.w * 0.7, h=tab.h - 12)
            scene.add(_frame(other, rule, 1.5, corner=4))
        if scene.numbered:  # (the open sheet's tab, the slide's number on it)
            scene.add(
                _rect(tab.x, tab.y, tab.w, tab.h, palette.background),
                _rect(tab.x, HEIGHT - 6, tab.w, 6, palette.accent),
            )
            _slide_number(
                scene, Box(x=tab.x + 8, y=1034, w=tab.w - 16, h=30), spec="decoration centre", colour=palette.accent
            )
    title = scene.title()
    if title is not None and len(scene.lines(title)) <= 2:  # (the selected cell)
        ink = scene.ink(title)
        cell_top = max(ink.y - 10, top + 3)
        cell = Box(x=ink.x - 22, y=cell_top, w=ink.w + 44, h=ink.y + ink.h + 10 - cell_top)
        if scene.free(cell, pad=4, ignoring=(title,)):
            handle = _rect(cell.x + cell.w - 7, cell.y + cell.h - 7, 14, 14, palette.accent)
            scene.add(_frame(cell, palette.accent, 4), handle)
    for role in _framed(scene):
        _selected_picture(scene, role)


def _selected_picture(scene: Scene, role: str) -> None:
    """A picture as a spreadsheet shows one that's selected: an outline, square handles at its corners and the middles
    of its sides, and a round handle above it to turn it by."""
    accent = scene.palette.accent_2
    shown = scene.shown(role, _grown(scene.box(role), -14))
    scene.over(_frame(_grown(shown, 2), accent, 2), part_of=role)
    xs, ys = (shown.x, shown.x + shown.w / 2, shown.x + shown.w), (shown.y, shown.y + shown.h / 2, shown.y + shown.h)
    for x, y in itertools.product(xs, ys):
        if (x, y) == (xs[1], ys[1]):
            continue
        square = Box(x=x - 7, y=y - 7, w=14, h=14)
        scene.over(_rect(square.x, square.y, square.w, square.h, "#ffffff"), _frame(square, accent, 2), part_of=role)
    if shown.y > 40:
        middle = shown.x + shown.w / 2
        scene.over(
            _rect(middle - 1, shown.y - 24, 2, 17, accent),
            _ellipse(middle, shown.y - 30, 16, 16, "#ffffff"),
            _ring(middle, shown.y - 30, 16, 16, accent, 2),
            part_of=role,
        )


# THE YEAR 2000 (D77)

_SHEEN: Final = ("#ffb3e6", "#99e9f2", "#fff3a3")  # a disc's rainbow sheen: pink, cyan, yellow


def _y2k(scene: Scene) -> None:
    """The year 2000's: sparkles and glossy bubbles in free spots, a sparkle by the title, pictures in white rounded
    frames with a pastel shadow, on its big slides a CD where there's room, and the slide's number ("7/12") on a
    glossy pill (its headings are chrome: see talkgenerator.design.themes)."""
    palette = scene.palette
    pill, number = _plate(WIDTH - 44 - 136, 136)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        scene.add(
            _rect(pill.x, pill.y, pill.w, pill.h, palette.accent, corner=pill.h / 2),
            _rect(pill.x + 14, pill.y + 2, pill.w - 28, 3, "#ffffff", 0.6, corner=1.5),
        )
        _slide_number(scene, number, spec="decoration centre", colour=scene.on([palette.accent]))
        scene.kept.append(pill)
    title = scene.title()
    if title is not None:  # (a sparkle by its end)
        ink = scene.ink(title)
        spot = Box(x=ink.x + ink.w + 18, y=ink.y - 14, w=58, h=58)
        if scene.free(spot, pad=6, letters=True):
            _sparkle(scene, spot.x + 29, spot.y + 29, 58, palette.accent_2)
    for role in _framed(scene):
        shown = scene.shown(role, _grown(scene.box(role), -22))
        frame = _grown(shown, 12)
        corner = 0.08 * min(frame.w, frame.h) + 12
        scene.add(
            _rect(frame.x + 10, frame.y + 10, frame.w, frame.h, palette.accent_2, 0.4, corner=corner),
            _rect(frame.x, frame.y, frame.w, frame.h, "#ffffff", corner=corner),
            part_of=role,
        )
    if scene.photo and not scene.backdrop:
        return
    if scene.big:
        spots = _corner_spots(scene, 280, 50, letters=True)
        if spots:
            _cd(scene, spots[0])

    def piece(x: float, y: float, size: float) -> None:
        if random_util.random() < 0.7:
            _sparkle(scene, x, y, size, random_util.choice((palette.accent, palette.accent_2)))
        else:  # (a glossy bubble)
            scene.add(
                _ring(x, y, size, size, "#ffffff", max(3.0, size / 14), 0.9),
                _ellipse(x - size * 0.18, y - size * 0.2, size * 0.24, size * 0.15, "#ffffff", 0.85),
            )

    _scatter(scene, 6 if scene.big else 4, (34.0, 72.0), piece, letters=True, edges=(60.0, 110.0), rows=(60.0, 80.0))


def _sparkle(scene: Scene, x: float, y: float, size: float, colour: str) -> None:
    """A sparkle, its middle at (x, y): a four-pointed star of the colour, with a white one in its middle."""
    scene.add(
        _polygon(geometry.star(4, 0.22), x - size / 2, y - size / 2, size, size, colour),
        _polygon(geometry.star(4, 0.22), x - size / 4, y - size / 4, size / 2, size / 2, "#ffffff", 0.9),
    )


def _cd(scene: Scene, box: Box) -> None:
    """A CD in the box: a silver disc with a rainbow's sheen, its clear middle and its hole."""
    cx, cy, radius = box.x + box.w / 2, box.y + box.h / 2, box.w / 2
    scene.under(
        _ellipse(cx + 6, cy + 8, 2 * radius, 2 * radius, scene.palette.text, 0.18),
        _ellipse(cx, cy, 2 * radius, 2 * radius, "#e4e9f0"),
    )
    for colour, start in zip(_SHEEN, (200.0, 310.0, 60.0), strict=True):
        sheen = geometry.arc(cx, cy, radius * 0.7, radius * 0.7, start, start + 80, 16)
        scene.under(_line(sheen, radius * 0.3, colour, 0.6))
    scene.under(
        _ring(cx, cy, 2 * radius, 2 * radius, "#b4c0d0", 3),
        _ellipse(cx, cy, 0.8 * radius, 0.8 * radius, "#d3dae4"),
        _ellipse(cx, cy, 0.3 * radius, 0.3 * radius, scene.palette.background),
    )


# THE 1970s (D77)


def _seventies(scene: Scene) -> None:
    """The 1970s': four rounded stripes in its browns, oranges and mustard along the slide's top and left edges, turning
    its top left corner in a curve, two rounded stripes under the title, pictures as prints with round corners in a
    cream border, on its big slides a sunset of stripes where there's room, and the slide's number ("7/12") on a
    rounded tag."""
    palette = scene.palette
    stripes = [palette.text, palette.accent, color.mix(palette.accent, palette.accent_2, 0.5), palette.accent_2]
    for index, colour in enumerate(stripes):  # (over a picture at the slide's edge too)
        scene.over(_area(_corner_stripe(4 + 13 * index, 9, 210), colour))
    tag, number = _plate(WIDTH - 44 - 136, 136)
    if scene.numbered and not scene.placement.photo and scene.free(number, pad=4):
        scene.add(_rect(tag.x, tag.y, tag.w, tag.h, palette.text, corner=tag.h / 2))
        _slide_number(scene, number, spec="decoration centre", colour=palette.background)
        scene.kept.append(tag)
    title = scene.title()
    if title is not None:
        x, y, width = _under_title(scene, title, 300)
        scene.add(
            _rect(x, y - 4, width, 8, palette.accent, corner=4),
            _rect(x + width * 0.12, y + 10, width * 0.76, 8, palette.accent_2, corner=4),
        )
    for role in _framed(scene):
        shown = scene.shown(role, _grown(scene.box(role), -18))
        print_ = _grown(shown, 14)
        cream = color.mix(palette.background, "#ffffff", 0.6) if not color.is_dark(palette.background) else "#f6e7c8"
        scene.add(
            _rect(print_.x, print_.y, print_.w, print_.h, cream, corner=30),
            _frame(print_, palette.text if not color.is_dark(palette.background) else palette.accent, 4, corner=30),
            part_of=role,
        )
    if scene.big and not scene.photo:
        _sunset(scene, stripes)


def _corner_stripe(inset: float, width: float, turn: float) -> list[geometry.Point]:
    """A stripe this far in from the slide's top and left edges, this wide, along both, turning the top left corner in
    a quarter circle around (turn, turn): its outline, on the canvas."""
    outer: list[geometry.Point] = [(WIDTH + 4.0, inset), (turn, inset)]
    outer += geometry.arc(turn, turn, turn - inset, turn - inset, 270, 180, 12)
    outer += [(inset, HEIGHT + 4.0)]
    inner: list[geometry.Point] = [(inset + width, HEIGHT + 4.0)]
    inner += geometry.arc(turn, turn, turn - inset - width, turn - inset - width, 180, 270, 12)
    inner += [(WIDTH + 4.0, inset + width)]
    return [*outer, *inner]


def _area(points: Sequence[geometry.Point], colour: str, opacity: float = 1.0) -> ShapeElement:
    """A polygon of these corners on the canvas (as shares of the box around them)."""
    x0, y0 = min(x for x, _ in points), min(y for _, y in points)
    w, h = max(x for x, _ in points) - x0, max(y for _, y in points) - y0
    shares = tuple((round((x - x0) / w, 4), round((y - y0) / h, 4)) for x, y in points)
    return _polygon(shares, x0, y0, w, h, colour, opacity)


def _sunset(scene: Scene, stripes: Sequence[str]) -> None:
    """A 1970s sunset: four arches of stripes rising from the slide's bottom edge, where there's room for them (not
    behind a text)."""
    for middle in (WIDTH - 420.0, WIDTH / 2, 420.0):
        spot = Box(x=middle - 330, y=HEIGHT - 330, w=660, h=330)
        if scene.free(spot, pad=16, letters=True):
            break
    else:
        return
    for index, colour in enumerate(reversed(stripes)):
        radius = 330 - index * 62
        scene.under(
            _polygon(
                geometry.arch((radius - 44) / radius), middle - radius, HEIGHT - radius, 2 * radius, radius, colour
            )
        )
    scene.kept.append(spot)


# A GLOSSY MAGAZINE (D77)

# The specs of the texts a magazine puts giant quotation marks by (a statement's, a quote's)
_QUOTES: Final = frozenset({"statement", "left statement", "band statement", "quote"})
# How many issues a magazine has had (its roundel's number, N°1 to N°60)
_ISSUES: Final = 60


def _magazine(scene: Scene) -> None:
    """A glossy magazine's: a hairline rule across the top, with a square of its accent at its start; a short thick rule
    under the title; giant quotation marks by a quote; pictures on a block of its accent's tint, offset; the slide's
    number ("07 / 12") as the page's folio in the bottom right corner, after a hairline; and on its big slides a roundel
    with the issue's number."""
    palette = scene.palette
    ink = palette.text
    if not scene.placement.photo:
        scene.add(_rect(MARGIN, 40, WIDTH - 2 * MARGIN, 1.5, ink), _rect(MARGIN, 30, 20, 20, palette.accent))
        folio = Box(x=WIDTH - MARGIN - 180, y=1034, w=180, h=30)
        if _slide_number(
            scene, folio, spec=_sized("decoration heading", 28, 24, align="right"), colour=ink, padded=True
        ):
            scene.add(_rect(MARGIN, 1048, WIDTH - 2 * MARGIN - 200, 1.5, ink))
    title = scene.title()
    if title is not None:
        x, y, width = _under_title(scene, title, 96)
        if scene.theme.title_align == "left":
            x = scene.ink(title).x
        scene.add(_rect(x, y - 2, min(96.0, width), 7, palette.accent))
    tint = color.mix(palette.accent, palette.background, 0.78)
    for role in _framed(scene):
        box = scene.box(role)
        shown = scene.shown(role, Box(x=box.x, y=box.y, w=box.w - 24, h=box.h - 24))
        scene.add(_rect(shown.x + 24, shown.y + 24, shown.w, shown.h, tint), part_of=role)
    for role in scene.texts():
        if scene.spec(role) in _QUOTES:
            _quote_marks(scene, role)
    if scene.big and not scene.photo:
        spots = _corner_spots(scene, 200, 60, letters=True)
        if spots:
            _roundel(scene, spots[0])


def _quote_marks(scene: Scene, role: str) -> None:
    """Giant quotation marks in the accent before a quote's first line (or smaller, over it), where they keep clear of
    the slide's texts, its other lines included, and pictures (on a band the quote is on, say), and read: in a box as
    tall as their line, of which their glyph fills the top."""
    lines = scene.lines(role)
    first = lines[0]
    big = min(260.0, max(140.0, first.h * 2.4))
    others = [_grown(line, 8) for line in lines[1:]]
    for size, x, y, align in (
        (big, first.x - big * 0.6 - 8, first.y - big * 0.2, "right"),
        (140.0, first.x, first.y - 140 * 0.62, "left"),
    ):
        place, glyph = Box(x=x, y=y, w=size * 0.6, h=size * 1.25), Box(x=x, y=y, w=size * 0.6, h=size * 0.62)
        clear = scene.free(glyph, pad=4, letters=True, ignoring=(role,), shapes=False)  # (the quote's first line aside)
        if x < MARGIN / 2 or y < 16 or not clear or any(_overlaps(other, glyph) for other in others):
            continue
        spec = _sized("decoration heading", size, size * 0.8, align=align, anchor="top")
        colour = scene.reading("“", place, spec, scene.palette.accent)
        if colour is not None:
            scene.write("“", place, spec, colour)
            return


def _roundel(scene: Scene, spot: Box) -> None:
    """A magazine's roundel in the spot: a circle of its accent with the issue's number ("N°7"): the member's, the
    same on each of its big slides, the closer's too (which has no slide number: D76)."""
    palette = scene.palette
    cx, cy = spot.x + spot.w / 2, spot.y + spot.h / 2
    scene.under(
        _ellipse(cx, cy, spot.w, spot.h, palette.accent), _ring(cx, cy, spot.w - 18, spot.h - 18, "#ffffff", 2, 0.8)
    )
    words = Box(x=spot.x + 30, y=spot.y + spot.h * 0.3, w=spot.w - 60, h=spot.h * 0.4)
    issue = scene.theme.motif_variant % _ISSUES + 1
    scene.write_on(f"N°{issue}", words, _sized("decoration heading", 64, 28), "#ffffff")
    scene.kept.append(spot)


_MOTIFS: Final[dict[str, Callable[[Scene], None]]] = {
    "keynote": _keynote,
    "minimal": _minimal,
    "corporate": _corporate,
    "lecture": _lecture,
    "blobs": _blobs,
    "ornate": _ornate,
    "crayon": _crayon,
    "stickers": _stickers,
    "notebook": _notebook,
    "cutouts": _cutouts,
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
    "workshop": _workshop,
    "desktop": _desktop,
    "corkboard": _corkboard,
    "spreadsheet": _spreadsheet,
    "y2k": _y2k,
    "seventies": _seventies,
    "magazine": _magazine,
}
