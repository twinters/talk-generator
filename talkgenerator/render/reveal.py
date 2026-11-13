"""When a slide's elements appear as it's presented, click by click (docs/v5-plan.md, D37, D52 and D53), as every
renderer that plays clicks shows them: PowerPoint's animations (talkgenerator.render.shapes), talk-generator-web's
presenter view, and the previewer's steps (talkgenerator.render.preview).

An element is there from the start, or appears on a click of its own (`appears_on_click`); a shape or text that
belongs to an element (`part_of`: a frame around a picture, the tape on it) appears with it; and a column slide's
columns appear click by click, as the 2019 template's do: of two, the first is there from the start and the second
comes on the first click, of three, each comes on a click; the one before dims as the next comes in. (A chart's
series after the first, or a ranking's bars, and a diagram's punchline, come on clicks of their own too: their
renderers draw them so.)
"""

from __future__ import annotations

import re
from typing import Final

from talkgenerator.models.deck import ChartElement, Content, DeckSlide, DiagramElement

# The slide types whose columns appear click by click, and how many columns they have
COLUMNS: Final = {"two_column_image": 2, "three_column_image": 3}
# How opaque a column is once the next one has come in
DIMMED: Final = 0.5
_IN_A_COLUMN: Final = re.compile(r"(?:content|caption)_(\d)")


def column_of(slide: DeckSlide, element: Content) -> int | None:
    """The column (from 1) of a column slide that the element is in: its picture or text, its caption, or what
    belongs to them (a frame around the picture); none for anything else."""
    if slide.type not in COLUMNS:
        return None
    match = _IN_A_COLUMN.fullmatch(_owner(element))
    return int(match.group(1)) if match else None


def click_of(slide: DeckSlide, element: Content) -> int | None:
    """The click on which the element appears (the first is 1): its own, or that of the element it belongs to; none
    if it's there from the start (or comes in with its column)."""
    own = getattr(element, "appears_on_click", None)
    if own:
        return int(own)
    part_of = getattr(element, "part_of", None)
    if part_of:
        target = slide.element(part_of)
        return getattr(target, "appears_on_click", None) if target is not None else None
    return None


def column_click(slide: DeckSlide, column: int) -> int:
    """The click on which a column of a column slide comes in: 0 for the first of two, which is there from the
    start."""
    return column - 1 if COLUMNS[slide.type] == 2 else column


def clicks(slide: DeckSlide) -> int:
    """How many clicks the slide takes, as it's presented, before the next slide comes."""
    if slide.type in COLUMNS:
        return column_click(slide, COLUMNS[slide.type])
    count = 0
    for element in slide.elements:
        if isinstance(element, ChartElement):
            count = max(count, element.chart.clicks())
        elif isinstance(element, DiagramElement):
            count = max(count, 1 if element.diagram.reveal == "punchline" else 0)
        else:
            count = max(count, click_of(slide, element) or 0)
    return count


def opacity(slide: DeckSlide, element: Content, step: int) -> float:
    """How the element shows once the slide's first step clicks have happened (0: none yet): not yet (0), as it is
    (1), or dimmed (a column once the next one has come in)."""
    click = click_of(slide, element)
    if click is not None:
        return 0.0 if step < click else 1.0
    column = column_of(slide, element)
    if column is None:
        return 1.0
    comes = column_click(slide, column)
    return 0.0 if step < comes else 1.0 if step == comes else DIMMED


def _owner(element: Content) -> str:
    """The role of the element that the element is, or belongs to."""
    return getattr(element, "part_of", None) or element.role
