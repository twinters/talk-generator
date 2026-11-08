"""Diagrams about a slide's seed, the classic way: Venn diagrams and 2×2 matrices, from the words that ConceptNet (or
Datamuse, when ConceptNet is down) relates to the seed. The diagrams are drawn as shapes (see
`talkgenerator.render.diagrams`), so they need no image source.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

from talkgenerator.models.deck import MatrixDiagram, VennDiagram
from talkgenerator.sources import conceptnet, packs
from talkgenerator.util import language_util, random_util

venn_title_generator = packs.pack(packs.TED).tracery("diagrams.venn_title")
matrix_title_generator = packs.pack(packs.TED).tracery("diagrams.matrix_title")

# The quadrants of a 2×2 matrix, as a plan names the one its dot is in
QUADRANTS: Final = ("top left", "top right", "bottom left", "bottom right")

# How a classic Venn diagram's circles read, for a word that describes the seed (the first ones only fit single words)
_CIRCLE_FORMS: Final = ("{} things", "Everything {}", "Things that are {}")
_LONGEST_WORD: Final = 20  # longer "words" are phrases that don't read well in a circle or a quadrant
# Adjectives of quantity, which say nothing about what they describe ("Things that are much")
_VAGUE: Final = frozenset(
    ("much", "more", "most", "less", "least", "many", "few", "fewer", "other", "such", "same", "own", "several")
    + ("certain", "enough", "whole", "entire", "only", "various")
)


def dot_position(quadrant: str | None) -> tuple[float, float]:
    """Where a matrix's dot goes in its quadrant (in a random one, for a quadrant that's none of QUADRANTS): towards
    the quadrant's outer side, so that its name fits beside it, and in the half nearer the middle, away from the
    quadrant's label (which is at its outer edge)."""
    if quadrant is None or quadrant not in QUADRANTS:
        quadrant = random_util.choice(QUADRANTS)
    x = random_util.uniform(0.8, 0.9) if quadrant.endswith("right") else random_util.uniform(0.1, 0.2)
    y = random_util.uniform(0.61, 0.66) if quadrant.startswith("top") else random_util.uniform(0.34, 0.39)
    return round(x, 3), round(y, 3)


def generate_venn(presentation_context: dict[str, Any]) -> tuple[str, VennDiagram] | None:
    """A classic Venn diagram: things that are like the slide's seed in two (or, a third of the time, three) ways, and
    the seed where they overlap, appearing on a click."""
    seed = presentation_context["seed"]
    properties = _properties(seed)
    if len(properties) < 2:
        return None
    title = venn_title_generator(presentation_context)
    if not title:
        return None
    count = 3 if len(properties) >= 3 and random_util.random() < 1 / 3 else 2
    chosen = random_util.sample(properties, count)
    form = random_util.choice(_CIRCLE_FORMS) if all(" " not in word for word in chosen) else _CIRCLE_FORMS[-1]
    circles = tuple(_capitalised(form.format(word)) for word in chosen)
    return title, VennDiagram(circles=circles, overlap=_capitalised(seed), reveal="punchline")


def generate_matrix(presentation_context: dict[str, Any]) -> tuple[str, MatrixDiagram] | None:
    """A classic 2×2 matrix: two ways the slide's seed can be (from their opposite, or from not at all, to very)
    along its axes, things related to the seed in its quadrants, and the seed itself as its dot, appearing on a
    click."""
    seed = presentation_context["seed"]
    properties = _properties(seed)
    related = [
        word for word in _words(conceptnet.get_weighted_related_words(seed, 30), seed, 20) if word not in properties
    ]
    if len(properties) < 2 or len(related) < 4:
        return None
    title = matrix_title_generator(presentation_context)
    if not title:
        return None
    across, up = random_util.sample(properties, 2)
    x_left, x_right = _axis(across)
    y_bottom, y_top = _axis(up)
    top_left, top_right, bottom_left, bottom_right = (_capitalised(word) for word in random_util.sample(related, 4))
    dot_x, dot_y = dot_position(None)
    return title, MatrixDiagram(
        x_left=x_left,
        x_right=x_right,
        y_bottom=y_bottom,
        y_top=y_top,
        top_left=top_left,
        top_right=top_right,
        bottom_left=bottom_left,
        bottom_right=bottom_right,
        dot=_capitalised(seed),
        dot_x=dot_x,
        dot_y=dot_y,
        reveal="punchline",
    )


def _properties(seed: str) -> list[str]:
    """Words that describe the seed (or, for a seed of more words that none describe, its last word, usually the main
    one): phrases, and the words that WordNet knows as adjectives (the fallback, Datamuse, also gives nouns, such as
    "day" for "running")."""
    words = [word for word in _words(conceptnet.get_weighted_properties(seed), seed) if _describes(word)]
    if not words and " " in seed.strip():
        return _properties(seed.strip().rsplit(" ", 1)[-1])
    return words


def _describes(word: str) -> bool:
    return " " in word or (word.lower() not in _VAGUE and language_util.is_adjective(word))


def _axis(word: str) -> tuple[str, str]:
    """The titles of an axis that goes from the word's opposite (or from "Not <word>") to the word (or "Very
    <word>")."""
    opposites = _words(conceptnet.get_weighted_antonyms(word), word)
    if opposites:
        return _capitalised(opposites[0]), _capitalised(word)
    return f"Not {word}", f"Very {word}"


def _words(entries: Sequence[tuple[float, str]] | None, seed: str, limit: int = 12) -> list[str]:
    """The words of weighted (weight, word) entries, the weightiest first: at most the limit, without repeats, short
    enough for a label, and without the seed (or words holding it)."""
    kept = conceptnet.remove_duplicates(conceptnet.remove_containing(list(entries or ()), seed.lower()) or []) or []
    words = [str(word).strip() for _, word in sorted(kept, key=lambda entry: -entry[0])]
    return [word for word in words if word and len(word) <= _LONGEST_WORD][:limit]


def _capitalised(text: str) -> str:
    return text[:1].upper() + text[1:]
