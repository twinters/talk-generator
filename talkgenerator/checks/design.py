"""Design checks of themed decks (docs/v5-plan.md, sections 9 and 14).

Every text has to read on what's behind it (WCAG contrast: 4.5 for body text, 3 for large text), fit its box at its
size, be big enough to read from the back of the room, and stay within the slide's safe area. What's behind a text
is the slide's background (both ends of a gradient), and the shapes and images drawn before it: an image could be
anything, so for one the check takes the worst of black and white, as shaded by what's drawn over it.
"""

from __future__ import annotations

from typing import Final

from talkgenerator.checks.deck import Finding
from talkgenerator.design import color, fit
from talkgenerator.models.deck import Box, Deck, DeckSlide, ImageElement, ShapeElement, TextElement, TextStyle

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
        if slide.credits and slide.credits_box is not None and slide.credits_style is not None:
            behind = _behind(slide, len(slide.elements), slide.credits_box)
            worst = color.worst_contrast(slide.credits_style.color, behind)
            if worst < color.BODY_CONTRAST:
                findings.append(Finding("contrast", "error", f"the credits read badly (contrast {worst:.1f})", number))
            if slide.credits_style.size < SMALLEST_CREDITS:
                findings.append(Finding("text size", "warning", "the credits are too small to read", number))
    return findings


def _text_findings(
    slide: DeckSlide, index: int, box: Box, style: TextStyle, text: str, number: int, role: str
) -> list[Finding]:
    findings = []
    large = style.size >= LARGE_TEXT or (style.bold and style.size >= LARGE_BOLD_TEXT)
    needed = color.LARGE_TEXT_CONTRAST if large else color.BODY_CONTRAST
    worst = color.worst_contrast(style.color, _behind(slide, index, box))
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
    return findings


def _behind(slide: DeckSlide, index: int, box: Box) -> list[str]:
    """The colours that may be behind a box: the slide's background, as the elements drawn before it change it."""
    backgrounds = [slide.background.color] if slide.background is not None else ["#ffffff"]
    if slide.background is not None and slide.background.color_2:
        backgrounds.append(slide.background.color_2)
    center_x, center_y = box.x + box.w / 2, box.y + box.h / 2
    for element in slide.elements[:index]:
        area = element.box
        if area is None or not (area.x <= center_x <= area.x + area.w and area.y <= center_y <= area.y + area.h):
            continue
        if isinstance(element, ImageElement):
            backgrounds = ["#000000", "#ffffff"]  # an image could be anything
        elif isinstance(element, ShapeElement):
            backgrounds = [color.mix(background, element.color, element.opacity) for background in backgrounds]
    return backgrounds


def _inside(box: Box, area: Box) -> bool:
    return box.x >= area.x and box.y >= area.y and box.x + box.w <= area.x + area.w and box.y + box.h <= area.y + area.h
