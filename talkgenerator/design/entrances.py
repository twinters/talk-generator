"""Entrances (D82): which of a slide's elements come in with one of PowerPoint's entrance effects as the slide is
presented, with which effect, and when.

A theme moves as much as its family has it (`Theme.motion`, see talkgenerator.design.themes): a calm one not at all
(its elements are there from the start, and those that appear on a click fade in, as before), one with some motion now
and then (every other slide, one of its things comes in with one of the theme's effects, or two), and one for laughs,
with lots of it, everything on every slide, one after the other: the title first, then the pictures and the texts. The
user's idea (2026-11-13): "exaggerated animations often get a laugh too".

What comes in is a slide's thing: a text, or a picture with what belongs to it (a frame, a tint, the name on its
window, which come in with it, as one); or a click's worth of things, which come in together on it (a quiz's answer on
its tile, the next column of a column slide). A photo behind the whole slide, the theme's decoration, the build dots,
charts and diagrams (whose own clicks reveal them) stay as they are. Every element of a thing gets its entrance, so
renderers have nothing to work out: PowerPoint plays them (talkgenerator.render.animation), talk-generator-web too.
"""

from __future__ import annotations

from typing import Final

from talkgenerator.models.deck import (
    DECORATION,
    ChartElement,
    Content,
    DeckSlide,
    DiagramElement,
    Entrance,
    ImageElement,
    TextElement,
)
from talkgenerator.models.theme import EntranceEffect, Theme
from talkgenerator.render import reveal
from talkgenerator.util import random_util

# How often a slide of a theme with some motion has something that comes in, and how often two things do
SOME_CHANCE: Final = 0.5
TWO_CHANCE: Final = 0.25
# How long after each other the things of a slide come in (with lots of motion), in milliseconds: the last at most
# MOST_STAGGER after the slide comes up, however many there are
STAGGER: Final = 400
MOST_STAGGER: Final = 1600
_BUILD: Final = "build "  # (the build dots' roles: see talkgenerator.design.engine.build_dots)
_FIRST: Final = ("title", "statement", "number")  # (the roles that come in first, where everything does)


def assign(slide: DeckSlide, theme: Theme, rng: random_util.Rng) -> DeckSlide:
    """The laid-out slide with its elements' entrances, as its theme's motion has them (none: the slide as it is)."""
    if theme.motion == "none" or not theme.entrances:
        return slide
    from_the_start, on_clicks = _things(slide)
    if not from_the_start and not on_clicks:
        return slide
    with random_util.use(rng):
        if theme.motion == "some":
            if random_util.random() >= SOME_CHANCE:
                return slide
            count = 2 if random_util.random() < TWO_CHANCE else 1
            starting = len(from_the_start)
            everything = [*from_the_start, *on_clicks]
            picked = set(random_util.sample(range(len(everything)), min(count, len(everything))))
            from_the_start = [everything[index] for index in sorted(picked) if index < starting]
            on_clicks = [everything[index] for index in sorted(picked) if index >= starting]
        entrances: dict[int, Entrance] = {}
        stagger = min(STAGGER, MOST_STAGGER // max(1, len(from_the_start) - 1))
        for place, thing in enumerate(from_the_start):
            entrance = Entrance(effect=random_util.choice(theme.entrances), delay=place * stagger)
            entrances.update(dict.fromkeys(thing, entrance))
        for thing in on_clicks:
            entrances.update(dict.fromkeys(thing, Entrance(effect=random_util.choice(theme.entrances))))
    elements = tuple(
        element.model_copy(update={"entrance": entrances[index]}) if index in entrances else element
        for index, element in enumerate(slide.elements)
    )
    return slide.model_copy(update={"elements": elements})


def effects(slide: DeckSlide) -> list[EntranceEffect]:
    """The entrance effects the slide's elements come in with, one for each thing (as they're in its elements)."""
    seen: list[Entrance] = []
    for element in slide.elements:
        entrance = getattr(element, "entrance", None)
        if entrance is not None and entrance not in seen:
            seen.append(entrance)
    return [entrance.effect for entrance in seen]


def _things(slide: DeckSlide) -> tuple[list[list[int]], list[list[int]]]:
    """The slide's things that can come in (each the places of its elements, in the slide's elements): those there from
    the start, the first ones first, and those that appear on clicks, a click's worth at a time, in order."""
    elements = slide.elements
    leads: list[int] = []
    clicks: dict[int, list[int]] = {}
    for index, element in enumerate(elements):
        if not _moves(element):
            continue
        click = reveal.click_of(slide, element)
        if click is None:
            column = reveal.column_of(slide, element)
            click = reveal.column_click(slide, column) if column is not None else None
        if click:
            clicks.setdefault(click, []).append(index)
        elif _leads(element):
            leads.append(index)
    from_the_start = []
    for lead in sorted(leads, key=lambda index: (not _first(elements[index]), index)):
        role = elements[lead].role
        followers = [
            index
            for index, element in enumerate(elements)
            if index != lead and _moves(element) and getattr(element, "part_of", None) == role
        ]
        from_the_start.append([lead, *followers])
    return from_the_start, [clicks[click] for click in sorted(clicks)]


def _moves(element: Content) -> bool:
    """Whether the element can come in with an effect: not a chart or a diagram (their clicks are their own), nor a
    build dot."""
    return not isinstance(element, ChartElement | DiagramElement) and not element.role.startswith(_BUILD)


def _leads(element: Content) -> bool:
    """Whether the element is a thing of its own, there from the start, that can come in: a text of the talk's (not the
    theme's: a slide's number, a terminal's prompt) or a picture that isn't behind the whole slide."""
    if isinstance(element, TextElement):
        return element.role != DECORATION
    return isinstance(element, ImageElement) and element.role != "background"


def _first(element: Content) -> bool:
    return any(element.role.startswith(role) for role in _FIRST)
