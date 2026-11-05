"""Automated checks of a deck (docs/v5-plan.md, section 14): a deck in, findings out.

An error is a broken talk: a slide without what it needs, or template code on a slide. A warning is worth a look,
such as an image without a credit, or one that comes back on another slide. Checks of contrast and overflowing text
follow with the themes (docs/v5-plan.md, milestone 3).
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from talkgenerator.models import classic
from talkgenerator.models.deck import ChartElement, Deck, ImageElement, TextElement

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    message: str
    slide: int | None = None  # counted from 1, the way presenters count

    def __str__(self) -> str:
        where = f"slide {self.slide}: " if self.slide is not None else ""
        return f"{self.severity}: {where}{self.message} [{self.check}]"


# Bits of generator machinery that should never make it onto a slide
_LEFTOVERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\{[A-Za-z_]\w*(?:\.\w+)*\}"), "an unfilled template variable"),
    (re.compile(r"#[A-Za-z_]\w*(?:\.\w+)*#"), "an unexpanded tracery symbol"),
    (re.compile(r"\(\([A-Za-z_]\w*\)\)"), "a missing tracery symbol"),
    (re.compile(r"<(?:built-in method|bound method|function|lambda)\b"), "Python code"),
    (re.compile(r"\b(?:ImageData|ChartData|XyChartData|DeckSlide)\("), "a Python object"),
)
# A word followed by None, as in "About None": a template variable that was None. (Not "None of us were ready")
_NONE = re.compile(r"\S\s+None\b|^None$")


def check_deck(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """Every check of a deck."""
    return [*check_completeness(deck, expected_slides), *check_leftovers(deck), *check_images(deck)]


def check_completeness(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """Every slide is there, and has what its type needs."""
    findings = []
    if expected_slides is not None and len(deck.slides) != expected_slides:
        findings.append(Finding("completeness", "error", f"{len(deck.slides)} of the {expected_slides} slides"))
    if deck.slides and deck.slides[0].type != "title":
        findings.append(
            Finding(
                "completeness",
                "warning",
                f"the first slide isn't the title but a slide of type {deck.slides[0].type}",
                1,
            )
        )
    for number, slide in enumerate(deck.slides, 1):
        required = classic.REQUIRED_ROLES.get(slide.type)
        if required is None:
            findings.append(Finding("completeness", "error", f"an unknown type of slide: {slide.type!r}", number))
            continue
        for role in required:
            if slide.element(role) is None:
                findings.append(Finding("completeness", "error", f"no {role} on this {slide.type} slide", number))
        for element in slide.elements:
            if isinstance(element, TextElement) and not element.text.strip():
                findings.append(Finding("completeness", "error", f"an empty {element.role}", number))
            elif isinstance(element, ImageElement) and not element.image.url.strip():
                findings.append(
                    Finding("completeness", "error", f"an image without an address as {element.role}", number)
                )
            elif isinstance(element, ChartElement) and not any(
                series.values or series.points for series in element.chart.series
            ):
                findings.append(Finding("completeness", "error", "a chart without data", number))
    return findings


def check_leftovers(deck: Deck) -> list[Finding]:
    """No template variables, tracery symbols or Python objects in the texts (chart labels included)."""
    findings = []
    for number, slide in enumerate(deck.slides, 1):
        for role, text in _texts(slide.elements):
            for pattern, what in _LEFTOVERS:
                found = pattern.search(text)
                if found:
                    findings.append(Finding("leftovers", "error", f"{what} in its {role}: {found.group(0)!r}", number))
            if _NONE.search(text):
                findings.append(Finding("leftovers", "warning", f"'None' in its {role}: {text!r}", number))
    return findings


def check_images(deck: Deck) -> list[Finding]:
    """Images from the web are credited, and no image comes back on another slide."""
    findings = []
    first_slide_of: dict[str, int] = {}
    for number, slide in enumerate(deck.slides, 1):
        for element in slide.elements:
            if not isinstance(element, ImageElement):
                continue
            url = element.image.url
            if url.startswith("http") and not element.image.credit:
                findings.append(Finding("images", "warning", f"an image without a credit: {url}", number))
            if url in first_slide_of and first_slide_of[url] != number:
                findings.append(Finding("images", "warning", f"the same image as slide {first_slide_of[url]}", number))
            first_slide_of.setdefault(url, number)
    return findings


def deck_metrics(deck: Deck) -> dict[str, Any]:
    """Numbers to follow from one milestone to the next, which aren't right or wrong on their own."""
    types = [slide.type for slide in deck.slides]
    return {
        "slides": len(deck.slides),
        "slide_types": dict(sorted(Counter(types).items())),
        "same_type_in_a_row": sum(1 for before, after in itertools.pairwise(types) if before == after),
        "images": sum(1 for slide in deck.slides for element in slide.elements if isinstance(element, ImageElement)),
        "usage": deck.usage.model_dump(),
    }


def _texts(elements: tuple[TextElement | ImageElement | ChartElement, ...]) -> list[tuple[str, str]]:
    texts = []
    for element in elements:
        if isinstance(element, TextElement):
            texts.append((element.role, element.text))
        elif isinstance(element, ChartElement):
            texts.extend((f"{element.role} label", category) for category in element.chart.categories)
    return texts
