"""Design checks of themed decks (docs/v5-plan.md, sections 9 and 14).

Every text has to read on what's behind it (WCAG contrast: 4.5 for body text, 3 for large text), fit its box at its
size, be big enough to read from the back of the room, stay within the slide's safe area, and not be covered by
what's drawn after it. What's behind a text is the slide's background (both ends of a gradient), and the shapes and
images drawn before it: an image could be anything, so for one the check takes the worst of black and white, as
shaded by what's drawn over it. And a slide doesn't repeat the layout of the slide before it, if another one fits.
"""

from __future__ import annotations

import itertools
from typing import Final

from talkgenerator.checks.deck import Finding
from talkgenerator.design import color, engine, fit, geometry, layers
from talkgenerator.models.deck import (
    Box,
    ChartElement,
    Deck,
    DeckSlide,
    DiagramElement,
    ImageElement,
    ShapeElement,
    TextElement,
    TextStyle,
)
from talkgenerator.render import diagrams

# A shape at least this opaque hides what's under it
COVERING_OPACITY: Final = 0.5

# WCAG's large text: 18 points, or 14 points in bold (a canvas pixel is half a point)
LARGE_TEXT: Final = 36
LARGE_BOLD_TEXT: Final = 28
SMALLEST_TEXT: Final = 24  # 12 points, for anything but the credits
SMALLEST_CREDITS: Final = 16
SAFE_AREA: Final = Box(x=16, y=16, w=1888, h=1048)


def check_design(deck: Deck) -> list[Finding]:
    """The design checks of a themed deck (a classic deck has none: the 2019 template places its texts)."""
    if deck.style is None:
        return []
    findings: list[Finding] = []
    for number, slide in enumerate(deck.slides, 1):
        for index, element in enumerate(slide.elements):
            if isinstance(element, TextElement) and element.box is not None and element.style is not None:
                findings += _text_findings(slide, index, element.box, element.style, element.text, number, element.role)
            elif isinstance(element, DiagramElement) and element.box is not None and element.style is not None:
                findings += _diagram_findings(slide, index, element, number)
        if slide.credits and slide.credits_box is not None and slide.credits_style is not None:
            behind = _behind(slide, len(slide.elements), slide.credits_box)
            worst = color.worst_contrast(slide.credits_style.color, behind)
            if worst < color.BODY_CONTRAST:
                findings.append(Finding("contrast", "error", f"the credits read badly (contrast {worst:.1f})", number))
            if slide.credits_style.size < SMALLEST_CREDITS:
                findings.append(Finding("text size", "warning", "the credits are too small to read", number))
    return [*findings, *check_variety(deck)]


def check_variety(deck: Deck) -> list[Finding]:
    """A themed deck's slides don't have the layout of the slide before them, where another layout fits them."""
    if deck.style is None:
        return []
    return [
        Finding("variety", "warning", f"the same layout as the slide before ({slide.layout})", number)
        for number, (before, slide) in enumerate(itertools.pairwise(deck.slides), 2)
        if slide.layout == before.layout and len(engine.layouts_for(slide, slide.style or deck.style)) > 1
    ]


def _text_findings(
    slide: DeckSlide, index: int, box: Box, style: TextStyle, text: str, number: int, role: str
) -> list[Finding]:
    findings = []
    large = style.size >= LARGE_TEXT or (style.bold and style.size >= LARGE_BOLD_TEXT)
    needed = color.LARGE_TEXT_CONTRAST if large else color.BODY_CONTRAST
    lines = engine.line_boxes(text, box, style)  # (what's behind its letters: a cursor after them doesn't count)
    behind = layers.behind_letters(slide.background, slide.elements[:index], lines, style.size)
    worst = _legibility(style, behind, needed)
    if worst < needed:
        findings.append(
            Finding("contrast", "error", f"the {role} reads badly (contrast {worst:.1f}, needs {needed:g})", number)
        )
    shown = text.upper() if style.uppercase else text
    if not fit.fit(shown, box.w, box.h, style.font, style.size, style.size, style.bold).fits:
        findings.append(
            Finding("overflow", "error", f"the {role} doesn't fit its box at {style.size / 2:g} points", number)
        )
    if style.size < SMALLEST_TEXT:
        findings.append(Finding("text size", "warning", f"the {role} is small ({style.size / 2:g} points)", number))
    if not _inside(box, SAFE_AREA):
        findings.append(Finding("margins", "warning", f"the {role} is outside the slide's safe area", number))
    covering = _covering(slide, index, box)
    if covering is not None:
        findings.append(Finding("covered", "error", f"the {role} is under a {covering} drawn over it", number))
    return findings


def _legibility(style: TextStyle, behind: list[str], needed: float) -> float:
    """How well a text reads on what's behind it: its colour's contrast (each of its gradient's colours, if it has
    one) with the worst of what's behind it. An outlined text (WordArt's, a meme's) reads by its colour or by its
    outline, whichever reads better on each colour behind it: white with a black outline reads on black by its
    white, and on white by its black (when the outline reads on the text's colours too)."""
    effect = style.effect
    fills = effect.fill if effect is not None and effect.fill else (style.color,)
    worst = min(color.worst_contrast(fill, behind) for fill in fills)
    if worst < needed and effect is not None and effect.outline and effect.outline_width > 0:
        outline = effect.outline
        against_fills = min(color.contrast(fill, outline) for fill in fills)
        outlined = min(
            max(
                min(color.contrast(fill, background) for fill in fills),
                min(color.contrast(outline, background), against_fills),
            )
            for background in behind
        )
        worst = max(worst, outlined)
    return worst


def _covering(slide: DeckSlide, index: int, box: Box) -> str | None:
    """What's drawn over a box after the element at the index, if anything: a picture, a chart, a diagram, or a
    shape that hides what's under it (where it's drawn: turned, a polygon's corners, its outline if it has no fill)."""
    for element in slide.elements[index + 1 :]:
        area = element.box
        if area is None:
            continue
        if isinstance(element, ImageElement | ChartElement | DiagramElement):
            if _overlap(area, box):
                return "picture" if isinstance(element, ImageElement) else element.kind
        elif isinstance(element, ShapeElement) and element.opacity >= COVERING_OPACITY:
            if _overlap(geometry.bounds(element), box) and layers.drawn_over(element, box):
                return element.role
    return None


def _overlap(box: Box, other: Box) -> bool:
    """Whether the boxes share some area (not just an edge)."""
    return (
        box.x < other.x + other.w and other.x < box.x + box.w and box.y < other.y + other.h and other.y < box.y + box.h
    )


def _diagram_findings(slide: DeckSlide, index: int, element: DiagramElement, number: int) -> list[Finding]:
    """A diagram's labels, punchline and axes read on what's behind them (its circles or quadrants over the slide's
    background, or the background beside them), and its labels fit their boxes, in its font."""
    assert element.box is not None and element.style is not None
    style, findings = element.style, []
    frame = diagrams.Box.on_canvas(element.box)
    beside = diagrams.labels_beside(frame, element.diagram, style.font)
    backgrounds = _behind(slide, index, element.box)
    behind = engine.diagram_behind(element.diagram, style.fills, style.opacity, backgrounds, beside)
    parts = (
        ("the diagram's labels read badly", style.text, color.BODY_CONTRAST),
        ("the diagram's punchline reads badly", style.punchline, color.BODY_CONTRAST),
        ("the diagram's axes are hard to see", style.lines, engine.LINE_CONTRAST),
    )
    for (problem, colour, needed), backgrounds in zip(parts, behind, strict=True):
        worst = color.worst_contrast(colour, backgrounds) if backgrounds else needed
        if worst < needed:
            findings.append(Finding("contrast", "error", f"{problem} (contrast {worst:.1f}, needs {needed:g})", number))
    for label in diagrams.labels(frame, element.diagram, style.font):
        area = diagrams.text_area(label.box)
        if not fit.fit(label.text, area.w, area.h, style.font, 2 * label.size, 2 * label.size, label.bold).fits:
            part = label.name.split(":")[0].lower()
            message = f"the diagram's {part} doesn't fit its box at {label.size} points"
            findings.append(Finding("overflow", "error", message, number))
    if not _inside(element.box, SAFE_AREA):
        findings.append(Finding("margins", "warning", "the diagram is outside the slide's safe area", number))
    return findings


def _behind(slide: DeckSlide, index: int, box: Box) -> list[str]:
    """The colours that may be behind a box: the slide's background, as the elements drawn before it change it (see
    talkgenerator.design.layers)."""
    return layers.behind(slide.background, slide.elements[:index], box)


def _inside(box: Box, area: Box) -> bool:
    return box.x >= area.x and box.y >= area.y and box.x + box.w <= area.x + area.w and box.y + box.h <= area.y + area.h
