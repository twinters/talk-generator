"""A talk format's arc: the parts its talks go through, in order, and how many slides each part has in a talk of any
length (docs/v5-plan.md, section 7; D56).

A startup pitch goes from the problem to the solution, the market, the business model, its traction, the competition
and the team to the ask; an academic talk from its outline through related work, the method, the results, the
limitations, future work, the acknowledgements and the references to the questions. A part has the fewest and the
most slides it takes, and a rank: a talk too short for all of its parts keeps the parts of the lowest ranks (a pitch of
five slides has its problem, its solution, its traction and the ask), and a longer talk gives the parts it keeps more
slides, by rank too, up to their most. Free slides go between the parts, for the format's other slides (memes, gifs,
full-screen pictures...): an arc keeps a share of a talk's slides free first (its free share: two of a ten-slide
pitch's, D63), and a long talk has the slides that are left after its parts have their most free too.

The arc decides every slide's part from the talk's length alone, so it's the same in every run, and the slide
generators' weights come from it: a part's generators weigh in on their part's slides only (in_part), so a persona's
multipliers move a part's slides between the part's own kinds (a startup founder's traction is KPI tiles more often
than a chart) but never out of their part, and the format's other generators fill the free slides (free), standing in,
rarely, for a part's slide that none of the part's generators can make.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import Final

# How much more a slide generator weighs in the slides it's for (its part's, or the free ones) than a generator of the
# format's other slides that stands in there: a part's slide is a free slide's kind only when none of the part's own
# generators can make it, or once in tens of thousands of slides
PART_WEIGHT: Final = 1000.0
STAND_IN: Final = 0.01


@dataclass(frozen=True)
class Part:
    """A part of an arc: its name ("problem"), the fewest and the most slides it has in a talk that keeps it, and its
    rank (a short talk keeps the parts of the lowest ranks, and a long one gives them more slides first)."""

    name: str
    fewest: int = 1
    most: int = 1
    rank: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.fewest <= self.most:
            raise ValueError(f"part {self.name!r} needs at least one slide, and at most as many as it needs")


@dataclass(frozen=True)
class Arc:
    parts: tuple[Part, ...]
    # The share of a talk's slides (but its first and its last) that are free slides whatever its parts: the format's
    # memes, gifs and pictures, before its parts get theirs (decision D63: with every slide in a part, a ten-slide pitch
    # or academic talk had none, and the user found them text-heavy and dull). Rounded down: none in a short talk
    free: float = 0.0

    def __post_init__(self) -> None:
        names = [part.name for part in self.parts]
        if not names or len(set(names)) < len(names):
            raise ValueError(f"an arc needs parts, each with a name of its own: not {names}")
        if not 0 <= self.free < 1:
            raise ValueError(f"an arc's free share is less than all of a talk's slides: not {self.free}")

    def reserved(self, num_slides: int) -> int:
        """How many of a talk's slides its free share keeps free, whatever its parts."""
        return int(self.free * max(0, num_slides - 2))

    def names(self) -> tuple[str, ...]:
        return tuple(part.name for part in self.parts)

    def layout(self, num_slides: int) -> tuple[str | None, ...]:
        """Every slide's part, by its number (from 0): None for the title slide (the first) and for free slides."""
        return _layout(self, num_slides)

    def part_of(self, slide_nr: int, num_slides: int) -> str | None:
        """The part a slide is in (None for the title slide, a free slide, or a slide the talk hasn't)."""
        layout = self.layout(num_slides)
        return layout[slide_nr] if 0 <= slide_nr < len(layout) else None

    def kept(self, num_slides: int) -> tuple[str, ...]:
        """The parts a talk of this many slides has, in order."""
        return tuple(dict.fromkeys(part for part in self.layout(num_slides) if part is not None))

    def free_slides(self, num_slides: int) -> int:
        """How many slides of a talk of this many slides are in no part (the title slide not counted)."""
        return sum(1 for part in self.layout(num_slides)[1:] if part is None)


@cache
def _layout(arc: Arc, num_slides: int) -> tuple[str | None, ...]:
    room = max(0, num_slides - 1)  # (the slides after the title slide)
    reserved = arc.reserved(num_slides)  # (free slides, whatever the parts: see Arc.free)
    room -= reserved
    by_rank = sorted(range(len(arc.parts)), key=lambda index: (arc.parts[index].rank, index))
    # The parts the talk has room for, the lowest ranks first, each with its fewest slides
    counts: dict[int, int] = {}
    for index in by_rank:
        if arc.parts[index].fewest <= room:
            counts[index] = arc.parts[index].fewest
            room -= arc.parts[index].fewest
    # More slides for the parts that take more, a slide each in turn, the lowest ranks first
    growing = [index for index in by_rank if index in counts]
    while room > 0:
        grown = [index for index in growing if counts[index] < arc.parts[index].most]
        if not grown:
            break
        for index in grown[:room]:
            counts[index] += 1
            room -= 1
    # And the free slides, the reserved ones and those left, spread over the gaps between the parts (before the only
    # part, if it's one)
    room += reserved
    order = sorted(counts)
    gaps = [0] * max(1, len(order) - 1)
    for free in range(room):
        gaps[min(len(gaps) - 1, int((free + 0.5) * len(gaps) / room))] += 1
    slides: list[str | None] = [None]
    if len(order) == 1:
        slides += [None] * room
    for position, index in enumerate(order):
        slides += [arc.parts[index].name] * counts[index]
        if len(order) > 1 and position < len(order) - 1:
            slides += [None] * gaps[position]
    return tuple(slides[: max(0, num_slides)])


class InPart:
    """The weight of a part's slide generator for a slide: its own (times PART_WEIGHT) in its part's slides, and none
    in the others."""

    def __init__(self, arc: Arc, part: str, weight: float = 1.0):
        if part not in arc.names():
            raise ValueError(f"the arc has no part {part!r}; it has {', '.join(arc.names())}")
        self.arc, self.part, self.weight = arc, part, weight

    def __call__(self, slide_nr: int, num_slides: int) -> float:
        return PART_WEIGHT * self.weight if self.arc.part_of(slide_nr, num_slides) == self.part else 0.0


class Free:
    """The weight of one of the format's other slide generators (a meme, a gif, a quote...) for a slide: its own
    (times PART_WEIGHT) in the free slides, a sliver of it in the parts' slides (where it stands in for a part's slide
    that none of the part's generators can make), and none on the title slide."""

    def __init__(self, arc: Arc, weight: float = 1.0):
        self.arc, self.weight = arc, weight

    def __call__(self, slide_nr: int, num_slides: int) -> float:
        if slide_nr <= 0 or slide_nr >= num_slides:
            return 0.0
        return PART_WEIGHT * self.weight if self.arc.part_of(slide_nr, num_slides) is None else STAND_IN * self.weight
