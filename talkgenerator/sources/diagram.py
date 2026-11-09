"""Diagrams about a slide's seed, the classic way: Venn diagrams and 2×2 matrices, from the words that ConceptNet (or
Datamuse, when ConceptNet is down) relates to the seed. The diagrams are drawn as shapes (see
`talkgenerator.render.diagrams`), so they need no image source.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, Final

from talkgenerator.models.deck import MatrixDiagram, MatrixDot, VennDiagram
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


# The most dots a quadrant holds (the punchline's included): one in its upper half, one in its lower half
DOTS_IN_A_QUADRANT: Final = 2
# The most dots a matrix has besides the punchline's
MOST_DOTS: Final = 4


def dot_positions(quadrants: Sequence[str]) -> list[tuple[float, float]]:
    """Where dots go, one for each quadrant named (a quadrant named twice has two), in a matrix without labels in its
    quadrants: a dot alone in its quadrant anywhere in it but near its edges, with room for its name beside it; two
    in a quadrant, one in its upper half and one in its lower half (each one's name stays in its half: see
    talkgenerator.render.diagrams.dot_bounds), the first nearer the outer side, so never one above the other. (A
    quadrant holds DOTS_IN_A_QUADRANT at most: the caller leaves the others out.)"""
    found: list[tuple[float, float]] = []
    for index, quadrant in enumerate(quadrants):
        sharing = [other for other in quadrants if other == quadrant]
        place = quadrants[:index].count(quadrant)  # (the first or the second dot of its quadrant)
        right, top = quadrant.endswith("right"), quadrant.startswith("top")
        if len(sharing) < 2:
            inner = random_util.uniform(0.08, 0.38)  # (from the quadrant's outer side, as a share of the matrix)
            up = random_util.uniform(0.1, 0.36)  # (from the middle)
        else:
            # (the first nearer the outer side, the second nearer the middle: never one above the other)
            inner = random_util.uniform(0.08, 0.2) if place == 0 else random_util.uniform(0.28, 0.4)
            up = random_util.uniform(0.33, 0.41) if place == 0 else random_util.uniform(0.09, 0.17)
        x = 1 - inner if right else inner
        y = 0.5 + up if top else 0.5 - up
        found.append((round(x, 3), round(y, 3)))
    return found


def matrix(
    x_left: str,
    x_right: str,
    y_bottom: str,
    y_top: str,
    labels: Sequence[str],
    dot: str,
    dot_quadrant: str | None,
    things: Sequence[tuple[str, str]] = (),
) -> MatrixDiagram:
    """A matrix of these texts, whose punchline appears on a click: its axes' ends, its quadrants' labels (four, in
    QUADRANTS' order, "" for none), its punchline's dot in its quadrant (a random one, for one that's none of
    QUADRANTS), and other things as dots where they belong ((name, quadrant) each). There are at most MOST_DOTS things,
    and DOTS_IN_A_QUADRANT in a quadrant (the punchline's included), or one in a quadrant of a matrix with labels
    (where its name stays clear of the label: see dot_position): those that don't fit, repeats and things in no
    quadrant are left out."""
    quadrant = dot_quadrant if dot_quadrant in QUADRANTS else random_util.choice(QUADRANTS)
    labelled = any(label.strip() for label in labels)
    most = 1 if labelled else DOTS_IN_A_QUADRANT
    counts = Counter({quadrant: 1})
    kept: list[tuple[str, str]] = []
    seen = {dot.strip().casefold()}
    for name, where in things:
        if len(kept) == MOST_DOTS:
            break
        if where not in QUADRANTS or counts[where] >= most or not name.strip() or name.strip().casefold() in seen:
            continue
        counts[where] += 1
        seen.add(name.strip().casefold())
        kept.append((name.strip(), where))
    if labelled:
        positions = [dot_position(where) for where in (*(where for _, where in kept), quadrant)]
    else:
        positions = dot_positions([*(where for _, where in kept), quadrant])
    *others, (dot_x, dot_y) = positions
    top_left, top_right, bottom_left, bottom_right = (*labels, "", "", "", "")[:4]
    return MatrixDiagram(
        x_left=x_left,
        x_right=x_right,
        y_bottom=y_bottom,
        y_top=y_top,
        top_left=top_left,
        top_right=top_right,
        bottom_left=bottom_left,
        bottom_right=bottom_right,
        dot=dot,
        dot_x=dot_x,
        dot_y=dot_y,
        reveal="punchline",
        dots=tuple(MatrixDot(name=name, x=x, y=y) for (name, _), (x, y) in zip(kept, others, strict=True)),
    )


def quadrant_with_dots(matrix: MatrixDiagram) -> set[str]:
    """The quadrants that have a dot (any of the matrix's), by their names in QUADRANTS."""
    points = [(matrix.dot_x, matrix.dot_y), *((dot.x, dot.y) for dot in matrix.dots)]
    return {QUADRANTS[(0 if y > 0.5 else 2) + (1 if x > 0.5 else 0)] for x, y in points}


def pictured_quadrants(matrix: MatrixDiagram, pictures: Mapping[str, Any]) -> dict[str, Any]:
    """The pictures of the matrix's quadrants (by their corners: "top_left", ...) that it keeps: those of quadrants
    without a dot, where they have room (a picture of a quadrant with a dot is left out)."""
    taken = quadrant_with_dots(matrix)
    return {
        corner: picture
        for corner, picture in pictures.items()
        if picture is not None and corner.replace("_", " ") in QUADRANTS and corner.replace("_", " ") not in taken
    }


def venn_boxes(generated: tuple[Any, ...]) -> dict[str, str]:
    """A classic Venn diagram's boxes that can have a picture (after its title, the diagram): its first two circles,
    each with its label."""
    venn = generated[1]
    return {f"circle_{number}": label for number, label in enumerate(venn.circles[:2], 1)}


def matrix_boxes(generated: tuple[Any, ...]) -> dict[str, str]:
    """A classic matrix's boxes that can have a picture (after its title, the diagram): its quadrants that have a
    label and no dot, each with its label."""
    shown = generated[1]
    taken = quadrant_with_dots(shown)
    labels = (shown.top_left, shown.top_right, shown.bottom_left, shown.bottom_right)
    return {
        quadrant.replace(" ", "_"): label
        for quadrant, label in zip(QUADRANTS, labels, strict=True)
        if label and quadrant not in taken
    }


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


# How a classic matrix comes out (as a planned one does: see talkgenerator.plan.kinds.MATRIX_VARIANTS): words related
# to its seed as its quadrants' labels, or as dots where its quadrants have no labels, or bare, with only its axes and
# its dot
_CLASSIC_MATRICES: Final = (("labels", 2.0), ("dots", 2.0), ("bare", 1.0))
# A classic matrix's words as dots: this few to this many
_FEWEST_DOTS: Final = 2


def generate_matrix(presentation_context: dict[str, Any]) -> tuple[str, MatrixDiagram] | None:
    """A classic 2×2 matrix: two ways the slide's seed can be (from their opposite, or from not at all, to very)
    along its axes, things related to the seed in its quadrants (as their labels, or as dots: two to four of them,
    in random quadrants, two in a quadrant at most; or none, in a bare matrix), and the seed itself as its dot,
    appearing on a click."""
    seed = presentation_context["seed"]
    properties = _properties(seed)
    # (things in its quadrants: not "eruptive" or "glacial", D67)
    related = [word for word in _words(conceptnet.related_things(seed, 30), seed, 20) if word not in properties]
    if len(properties) < 2 or len(related) < 4:
        return None
    title = matrix_title_generator(presentation_context)
    if not title:
        return None
    across, up = random_util.sample(properties, 2)
    x_left, x_right = _axis(across)
    y_bottom, y_top = _axis(up)
    shape = random_util.weighted_random([(weight, name) for name, weight in _CLASSIC_MATRICES])
    words = [_capitalised(word) for word in random_util.sample(related, 4)]
    if shape == "labels":
        return title, matrix(x_left, x_right, y_bottom, y_top, words, _capitalised(seed), None)
    quadrant = random_util.choice(QUADRANTS)
    things: list[tuple[str, str]] = []
    if shape == "dots":  # (in random quadrants, as many as there's room for: two a quadrant, the punchline's counted)
        room = [where for where in QUADRANTS for _ in range(DOTS_IN_A_QUADRANT - (where == quadrant))]
        places = random_util.sample(room, random_util.randint(_FEWEST_DOTS, MOST_DOTS))
        things = list(zip(words, places, strict=False))
    return title, matrix(x_left, x_right, y_bottom, y_top, ("", "", "", ""), _capitalised(seed), quadrant, things)


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
