"""
This module represents the abstractions of a presentation schema
(responsible for specifying how to generate a presentation),
and slide generators, that have functions for generating slides
along with some other metadata.

Generating a talk is a series of random choices, drawn from the talk's random generator (see random_util): every
slide has its own streams for its topic, for every pick of a slide generator, and for every generator's content. So
the same seed gives the same talk, and generating the slides in parallel gives the same talk as one by one:

- One by one, every slide is worked out knowing what the slides before it used (their elements and tags).
- In parallel, the remaining slides are first worked out all at once, each knowing only what was settled before
  that round. Then they're settled in order, keeping a slide's result when working it out one by one would have
  given the same: when the generator picks come out the same, and its content doesn't repeat what the slides before
  it used. That test is exact, because a generator's content never depends on what's used, only whether it's
  accepted, and what's rejected for repeating used elements stays rejected when more is used. A slide whose picks
  lead to a generator it hasn't run yet starts a new round, in which the remaining slides are worked out again in
  parallel, reusing what they found so far.

A talk can be followed while it's made (Progress: talkgenerator.generator.stream_talk does): its slides are settled in
order as soon as they can be, a planned talk's while the language model is still writing the rest of it, and the
Progress hears of each. A Progress can want spare slides too, to show while the next slide isn't in yet: they're made
early, on a thread of their own and from random streams of their own, so the talk's slides come out the same with
spares or without (see _Spares). And it can give a slide a time limit (see _Clock): a slide that runs out of time
settles at once with what's quick, as planned without looking its pictures up, or else as a stand-in of a kind that
takes a hundredth of a second; the same seed then gives the same talk as long as no slide runs out of time. What the
slide waited for goes on by itself, and once it's done, the real slide takes the place of what stood in for it (see
_LateSlides).

A talk's persona (see talkgenerator.personas) weighs in on every pick of a slide generator, classic or planned: a
generator's weight for a slide is its own, times the persona's multiplier for its tags. The tag caps hold as before.
"""

import dataclasses
import functools
import itertools
import logging
import multiprocessing
import re
import threading
import time
from collections.abc import Callable, Collection, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

from pptx.presentation import Presentation

from talkgenerator import closers, facts, names, title_pictures, titles
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData, _filter_generated_elements
from talkgenerator.images import context as image_context
from talkgenerator.images import finder, licenses, profiles
from talkgenerator.images.slots import ImageSlot
from talkgenerator.llm.base import AnswerStopped, ProviderError, TextProvider
from talkgenerator.llm.ledger import MeteredProvider
from talkgenerator.llm.providers import NoneProvider
from talkgenerator.models.deck import Fact
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.models.theme import Theme
from talkgenerator.personas import Persona
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import (
    KINDS,
    PICTURE,
    PRESENTER_JOB,
    TALK_TITLE,
    Recipe,
    picture_version,
    pictures_first,
)
from talkgenerator.plan.outline import (
    ADVANCED,
    BASIC,
    RUNNING_GAG,
    WRITERS,
    Outline,
    SlideIdea,
    batch_size,
    outline_request,
    read_idea,
    writing_request,
)
from talkgenerator.plan.prompt import SPINE, PlannedSlide, slide_plan, talk_request
from talkgenerator.plan.realize import ATTEMPTS, clean_text, realize
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import generator_util, image_util, random_util

if TYPE_CHECKING:
    from talkgenerator.images.generation import ImageGeneration
    from talkgenerator.schema.formats import Format

logger = logging.getLogger("talkgenerator")

# What a slide generator produced for a slide: the slide and its generated elements, or None if it failed
_Result = tuple[Any, list] | None
# A slide's results so far, by the index of the slide generator
_Results = dict[int, _Result]


@dataclass
class _DeckState:
    """What the settled slides used: their elements, and how often each tag came up."""

    used_elements: set = field(default_factory=set)
    used_tags: dict[str, int] = field(default_factory=dict)

    def copy(self) -> "_DeckState":
        return _DeckState(set(self.used_elements), dict(self.used_tags))


@dataclass
class _WorkedOutSlide:
    slide_nr: int
    generator: SlideGeneratorData
    slide: Any
    generated_elements: list


class _NeedsWork:
    """A slide that needs a slide generator to run (to work out what generating it one by one would give)."""


_NEEDS_WORK = _NeedsWork()


def slides_at_once(parallel: bool | int, slides: int, most: int | None = None) -> int:
    """How many of the slides are made at the same time: one by one without parallel (False, or a number below 2), all
    of them with True (or at most `most` of them), and else at most the number parallel is. (A small server makes a
    few at once: each slide being made holds what it found until it's settled.)"""
    if parallel is True:
        at_once = slides if most is None else min(slides, most)
    else:
        at_once = min(slides, int(parallel))
    return max(1, at_once)


def _time_limit(progress: "Progress | None") -> float | None:
    """The seconds a slide may take, as the talk's progress asks (its slide_seconds: see _Clock); None for no limit."""
    seconds = getattr(progress, "slide_seconds", None) if progress is not None else None
    if isinstance(seconds, bool) or not isinstance(seconds, int | float) or seconds <= 0:
        return None
    return float(seconds)


class _Clock:
    """How long a slide may still take, in a talk with a time limit per slide (seconds; None: no limit), from when it
    could settle: once the slide before it was settled, and (for a slide a language model writes) its text came in.
    A slide that runs out of time settles at once with what's quick (see PresentationSchema._in_time and _stand_in),
    and what it waited for goes on by itself: once it's done, the real slide takes the place of what stood in for it
    (see _LateSlides). The title slide has no limit."""

    def __init__(self, seconds: float | None) -> None:
        self.seconds = seconds
        self._start = time.monotonic()

    def remaining(self) -> float | None:
        """The seconds the slide has left (0 once it's out of time), or None without a limit."""
        if self.seconds is None:
            return None
        return max(0.0, self.seconds - (time.monotonic() - self._start))

    @property
    def over(self) -> bool:
        return self.remaining() == 0.0


class _Outcome:
    """What a piece of a slide's work gives once it's done (or the error it raised), whoever runs it: a pool's thread,
    which delivers it here also once the pool is terminated (a pool's own AsyncResult isn't, then), or a thread of its
    own (see _Running). Waited for as a pool's AsyncResult is (wait, ready, get)."""

    def __init__(self) -> None:
        self._given: dict[str, Any] = {}
        self._done = threading.Event()

    def deliver(self, function: Callable[..., Any], *args: Any) -> None:
        """Run the function (with the arguments), and keep what it gives."""
        try:
            self._given["result"] = function(*args)
        except BaseException as error:  # (for whoever waits for it)
            self._given["error"] = error
        finally:
            self._done.set()

    def wait(self, seconds: float | None = None) -> bool:
        """Whether it's done, within the seconds (or ever, without them)."""
        return self._done.wait(seconds)

    def ready(self) -> bool:
        return self._done.is_set()

    def result(self) -> Any:
        """What it gave (once it's done), or the error it raised."""
        if "error" in self._given:
            raise self._given["error"]
        return self._given.get("result")

    def get(self, timeout: float | None = None) -> Any:
        """What it gave, once it's done within the timeout (as a pool's AsyncResult gives it): else
        multiprocessing.TimeoutError."""
        if not self._done.wait(timeout):
            raise multiprocessing.TimeoutError
        return self.result()


class _Running(_Outcome):
    """A function running on a thread of its own (finding images as the talk does), for a slide with a time limit:
    waited for as long as the slide may still take, and then left to finish by itself (for the slide to come after
    all: see _LateSlides), or waited for after all. It should work on copies of what the talk changes meanwhile (its
    _DeckState)."""

    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        threading.Thread(
            target=image_util.carry(self.deliver), args=(function,), name="slide in time", daemon=True
        ).start()


def _deliver(outcomes: dict[int, _Outcome], work: Callable[[int], Any], slide_nr: int) -> None:
    """A pool's work for a slide, delivered to the slide's outcome (see _Outcome)."""
    outcomes[slide_nr].deliver(work, slide_nr)


# How long a talk waits, once its slides are all in, for the slides that ran out of time to come after all (see
# _LateSlides): a slide's work that isn't done by then is dropped, and what stood in for it stays
LATE_SECONDS: Final = 20.0


def _worked_out(made: Any) -> "_WorkedOutSlide | None":
    """What a slide's work made, as a worked-out slide (the work of a slide that ran out of time: see _LateSlides)."""
    return made if isinstance(made, _WorkedOutSlide) else None


def _planned_worked_out(
    slide_nr: int, generator: SlideGeneratorData, made: tuple[Any, list] | None
) -> "_WorkedOutSlide | None":
    """What an attempt at a planned slide made (its slide and generated elements), as a worked-out slide."""
    return _WorkedOutSlide(slide_nr, generator, *made) if made is not None else None


def _planned_picture(
    slide_nr: int, generator: SlideGeneratorData, made: tuple[Any, list] | None
) -> "_WorkedOutSlide | None":
    """What an attempt at a planned slide that tries a picture first made (see talkgenerator.plan.kinds.PictureFirst),
    as a worked-out slide, if it's the picture: its text version stands in for it already (see
    PresentationSchema._in_time), and comes again when no picture was found (None, then)."""
    if made is None or not isinstance(made[0], slides.FullImageSlide):
        return None
    return _WorkedOutSlide(slide_nr, generator, *made)


@dataclass
class _LateSlide:
    """A slide that ran out of time, whose work goes on by itself (work: see _Outcome): what it gives, as a worked-out
    slide (as_worked_out; None for none), takes the place of what stood in for it."""

    slide_nr: int
    work: "_Outcome"
    as_worked_out: Callable[[Any], "_WorkedOutSlide | None"]
    since: float = field(default_factory=time.monotonic)


class _LateSlides:
    """The slides of a talk settled so far (settled, by number, and what they use: state), and those of them that ran
    out of time and settled with what was quick (see _Clock), whose own work goes on by itself (pending): once it's
    done, the real slide takes the place of what stood in for it, in the deck and for whoever follows the talk
    (replace: see PresentationSchema._replace_late), unless it repeats another slide, or the talk has as many slides of
    its kind as its caps allow. They're looked at whenever a slide settles (a slide whose work is done meanwhile waits
    for that, as long as the slide being waited for may take at most), and four times a second once the slides are all
    in, for LATE_SECONDS at most."""

    def __init__(
        self,
        slide_deck: SlideDeck,
        state: _DeckState,
        replace: Callable[[SlideDeck, int, Any], None] | None = None,
    ) -> None:
        self.slide_deck = slide_deck
        self.state = state
        self.replace = replace if replace is not None else _replace_slide
        self.settled: dict[int, _WorkedOutSlide] = {}
        self.pending: dict[int, _LateSlide] = {}

    def settle(
        self,
        worked_out: _WorkedOutSlide,
        work: "_Outcome | None" = None,
        as_worked_out: Callable[[Any], "_WorkedOutSlide | None"] = _worked_out,
    ) -> None:
        """A slide settled in the deck; for one that ran out of time, with its work, which goes on by itself, and
        what that gives as a worked-out slide (as_worked_out)."""
        self.settled[worked_out.slide_nr] = worked_out
        if work is not None:
            self.pending[worked_out.slide_nr] = _LateSlide(worked_out.slide_nr, work, as_worked_out)

    def done(self) -> list[_LateSlide]:
        """The late slides whose work is done (which aren't pending anymore)."""
        ready = [late for late in self.pending.values() if late.work.ready()]
        for late in ready:
            del self.pending[late.slide_nr]
        return ready


def _first_attempt(realize_it: Callable[[int, int], Any], slide_nr: int) -> Any:
    """A planned slide's first attempt, realized (realize_it takes the slide's number and the attempt's)."""
    return realize_it(slide_nr, 0)


class _Started:
    """Which slides' work has started, in a pool's threads or apart from them (each starts once): for a slide that's
    due before a pool's thread got to it, whose work then starts apart from the pool (see _Clock)."""

    def __init__(self) -> None:
        self._started: set[int] = set()
        self._lock = threading.Lock()

    def claim(self, slide_nr: int) -> bool:
        """Whether the slide's work starts now (it hadn't: it's this caller's to run, and the pool's thread skips it)."""
        with self._lock:
            if slide_nr in self._started:
                return False
            self._started.add(slide_nr)
            return True

    def then(self, work: Callable[[int], Any]) -> Callable[[int], Any]:
        """The pool's work for a slide, which a thread skips when the slide's work has started apart from the pool."""

        def run(slide_nr: int) -> Any:
            return work(slide_nr) if self.claim(slide_nr) else None

        return run


@dataclass
class PlanOutcome:
    """How a slide of a plan that was written outside talkgenerator came out (see PresentationSchema.realize_plan)."""

    number: int  # its place in the deck, counted from 1 (slide 1 is the title slide)
    # Or "classic" (its recipe's classic generator made it), "picture" (a picture of its concept without text, in
    # a talk in another language than English, which classic slides aren't in), or "left out"
    outcome: str = "as planned"
    problems: list[str] = field(default_factory=list)  # what went wrong on the way, even when a later try worked


# Titles before a name, which a model may write in a presenter's job before the name it gave them ("Dr. ...")
_HONORIFICS = re.compile(r"^(?:(?:dr|prof|mr|mrs|ms|mx|sir|dame)\.?\s+)+", re.IGNORECASE)


def _numbers(batch: Sequence[int]) -> str:
    """Slides' numbers (counted from 1), as the logs say them: "3", "4 and 5", "6, 7 and 8"."""
    numbers = [str(slide_nr + 1) for slide_nr in batch]
    return numbers[0] if len(numbers) == 1 else f"{', '.join(numbers[:-1])} and {numbers[-1]}"


def _title_slide(
    title: str,
    presenter: str | None,
    job: str | None,
    thesis: str | None,
    rng: random_util.Rng,
    language: str = "en",
) -> tuple[slides.Slide, list[str]]:
    """The title slide of a planned talk ("By <presenter>" and their job on the line under it, in the talk's
    language), with its texts."""
    with random_util.use(rng.child("subtitle")):
        by = random_util.choice(languages.language(language).by)
    if presenter and job:
        # (a free model wrote the presenter's name into their job: "By Dr. Chronos Vance, Dr. Chronos Vance, Founder",
        # and Claude Haiku with a title before it, "By Harold Beanmore, Dr. Harold Beanmore, Chief Chrono-Roaster";
        # but Ann's job may be "Annual Report Analyst")
        named = job if job.casefold().startswith(presenter.casefold()) else _HONORIFICS.sub("", job)
        if (
            named.casefold().startswith(presenter.casefold())
            and not named[len(presenter) : len(presenter) + 1].isalnum()
        ):
            job = named[len(presenter) :].lstrip(" ,;:-–—") or None
    # (the job on a line of its own, under the name: more readable than after a comma, the user found, D80)
    subtitle = "\n".join(part for part in (f"{by} {presenter}" if presenter else "", job or "") if part) or None
    slide = slides.TitleSlide(title, subtitle)
    slide.set_note(f"Planned: the title slide\nThesis: {thesis!r}")
    return slide, [text for text in (title, subtitle) if text]


def _fact_use(pick: SlideGeneratorData | None, recipe: Recipe | None = None) -> str | None:
    """What a slide that the language model writes does with a real fact, if it builds on one (see
    talkgenerator.facts.use_of): none for a variant of its recipe that builds on none (a dare for the audience)."""
    if pick is None or pick.llm is None or pick.llm.kind == "title":
        return None
    if recipe is not None and not recipe.facts:
        return None
    return facts.use_of(pick.llm.kind, pick.get_tags())


def _add_used(state: _DeckState, generated_elements: list) -> None:
    elements = set(generated_elements)
    _filter_generated_elements(elements)
    state.used_elements.update(elements)


def _add_slide(slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
    """Add a settled slide to the deck, and in a talk that generates pictures, start generating the ones it wishes for
    (see talkgenerator.images.generation): each takes its stock photo's place once it's in, and updates the slide. In
    a talk with a vision pick, its pictures' candidates are noted (see talkgenerator.images.vision)."""
    slide_deck.add_slide(slide_nr, slide)
    talk = image_context.current()
    if talk.generation is not None and getattr(slide, "wishes", None):
        talk.generation.settled(slide, functools.partial(slide_deck.slide_updated, slide_nr))
    if talk.vision is not None:
        talk.vision.settled(slide_nr, slide)


def _replace_slide(slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
    """A slide that ran out of time, come after all, in place of what stood in for it (see _LateSlides): in the deck,
    for whoever follows the talk to hear (replaced), with the pictures it wishes for to generate, if any, and noted for
    the vision pick instead of what stood in for it."""
    talk = image_context.current()
    if talk.vision is not None:
        talk.vision.forget(slide_nr)
    slide_deck.replace_slide(slide_nr, slide)
    if talk.generation is not None and getattr(slide, "wishes", None):
        talk.generation.settled(slide, functools.partial(slide_deck.slide_updated, slide_nr))
    if talk.vision is not None:
        talk.vision.settled(slide_nr, slide)


def _finish_picking(slide_deck: SlideDeck, cancelled: threading.Event | None = None) -> None:
    """In a talk with a vision pick, once its slides are settled: have the vision model pick among their pictures'
    candidates, which take their places (see talkgenerator.images.vision). TalkCancelled, if the talk is cancelled
    meanwhile."""
    vision = image_context.current().vision
    if vision is not None and not vision.finish(slide_deck, cancelled):
        raise TalkCancelled()


def _finish_generating(slide_deck: SlideDeck, cancelled: threading.Event | None = None) -> None:
    """Wait for the pictures being generated for the deck's slides (so it has them all), and then stop hearing of
    changes to its slides. TalkCancelled, if the talk is cancelled meanwhile."""
    generation = image_context.current().generation
    if generation is not None and not generation.finish(cancelled):
        raise TalkCancelled()
    slide_deck.update_listener = None


class TalkCancelled(Exception):
    """Whoever followed the talk stopped wanting it (see Progress): it's left unfinished."""


class _InEnglish(AnswerStopped):
    """The answer's spine reads as English, in a talk in another language: the rest of it isn't read."""


class _NotPlanned(AnswerStopped):
    """An Advanced talk's outline found the topic unsafe, or its spine reads as English in a talk in another language:
    the rest of it isn't read, and the talk is written as a Basic one (whose request asks again)."""


class Progress(Protocol):
    """Who follows a talk while it's made: told once its title and language are known (with the deck, still without
    slides), of every slide once it's settled, in order, and of a slide settled before that got a generated picture
    in its stock photo's place (see talkgenerator.images.generation), whenever that comes in. Raising TalkCancelled
    from started or settled stops the talk, and so does setting cancelled, also while the talk waits for the language
    model (whose answer then isn't read further).

    A Progress may also want spare slides (spares, how many: 0 for none, as one without the attribute), which it's
    told of (spare, with the spare's number, from 0) as each is made, from the talk's start until its slides are all
    settled, on a thread of the spares' own: see _Spares. And it may give every slide but the title slide a time limit
    (slide_seconds; None, as one without the attribute, for none): a slide that runs out of time settles with what's
    quick instead (see _Clock), and when the real slide comes after all, in place of what stood in for it, the
    Progress is told (replaced, as updated is, with the slide that takes the other's place: see _LateSlides). It may
    want early versions of the talk's last slides too (early, how many: 0 for none, as one without the attribute),
    which it's told of (early_version, with the slide's number) as each is made, on a thread of their own: see _Early.

    And a Progress may want to know how far the language model that writes the talk is (planning: one without it, or
    with None, isn't told): it's told whenever that changes, from when the model is asked until its answers are all in
    (see Planning), on whichever thread the change came on. And it may want the talk's closer (closed: one without it
    isn't told), as soon as its slides are all settled: the slide after its last (D76: see talkgenerator.closers)."""

    cancelled: threading.Event

    def started(self, slide_deck: SlideDeck) -> None: ...

    def settled(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None: ...

    def updated(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None: ...


@dataclass(frozen=True)
class Planning:
    """How far the language model that writes a talk is (see Progress's planning): the slides it writes (by number,
    from 0: all but the title slide, mostly), whether its answer has started coming in (heard), how many parts of its
    plan came in (the fields of the talk's spine, and at the Advanced level the slides' ideas), the slides whose idea is
    in (planned, at the Advanced level) and the slides it wrote, whether its plan is all in (the spine, and at the
    Advanced level the outline: every slide's idea, or the outline's end), and whether its answers are all in
    (answered: or there won't be any, as when it failed). When it's asked again, it starts over."""

    writes: tuple[int, ...]
    heard: bool = False
    parts: int = 0
    planned: frozenset[int] = frozenset()
    written: frozenset[int] = frozenset()
    plan_in: bool = False
    answered: bool = False


def _shape(key: str, value: Any) -> str:
    """A part of a model's answer, by its key and the kind of its value, without its texts: "slide_02 (an object of
    concept, title, ...)", "slides (a list of 9)", "slide_03 (a text)"."""
    if isinstance(value, dict):
        keys = [str(name) for name in value]
        shown = ", ".join(keys[:4]) + (", ..." if len(keys) > 4 else "")
        return f"{key} (an object of {shown})" if keys else f"{key} (an empty object)"
    if isinstance(value, list):
        return f"{key} (a list of {len(value)})"
    kinds = {str: "a text", int: "a number", float: "a number", bool: "true or false"}
    return f"{key} ({kinds.get(type(value), 'null' if value is None else 'something else')})"


@dataclass(eq=False)
class _PlannedTalk:
    """A talk as the language model plans it: every slide's generator, the model's answer so far, and the first
    attempts at realizing its slides (in parallel, while the rest of the answer comes in).

    While a talk streams, the answer comes in on a thread of its own (answering), and the slides are settled as their
    parts of it come in: wait_for_spine and wait_for wait for what they need, or for the end of the answer."""

    picks: list[SlideGeneratorData | None]
    planned: dict[int, PlannedSlide]  # the slides the model writes, by slide number (from 0)
    contexts: list[dict[str, Any]]
    rngs: list[random_util.Rng]
    spine_fields: frozenset[str]  # what the spine has (a model that doesn't nest the spine writes them one by one)
    spine: dict[str, Any] = field(default_factory=dict)
    plans: dict[int, SlidePlan] = field(default_factory=dict)
    first_attempts: dict[int, _Outcome] = field(default_factory=dict)
    pool: ThreadPool | None = None
    language: str = "en"
    facts: tuple[Fact, ...] = ()  # the real facts its request gave its slides (see talkgenerator.facts)
    answering: threading.Thread | None = None  # (the answer coming in, while the talk streams)
    cancelled: threading.Event = field(default_factory=threading.Event)  # (then the answer isn't read any further)
    # Whether the answer's spine is to be in the talk's language: a first answer's is (the model is asked again when
    # it's English, see languages.reads_as_english), the second one is kept whatever it's in
    check_language: bool = False
    # Whether a slide ran out of time (a talk with a time limit per slide): its realizing goes on by itself, and the
    # talk doesn't wait for it when it closes
    abandoned: bool = False
    # The attempts that slides ran out of time waiting for, by slide number, which go on by themselves: for a slide to
    # come after all, in place of what stood in for it (see _LateSlides)
    late_work: dict[int, _Outcome] = field(default_factory=dict)
    # The slides whose first attempt has started, in the pool or apart from it (see attempt)
    _started: "_Started" = field(default_factory=lambda: _Started())
    # The model's plan of the talk, at the Advanced level (see talkgenerator.plan.outline)
    outline: Outline | None = None
    # Whether the slides come in order, in one answer (a Basic talk's): or else in any order, each from a request of
    # its own (an Advanced talk's), and a slide whose request ended without it is given up (see give_up)
    in_order: bool = True
    # The level its slides are written at: Advanced once its outline's spine is in (see _write_planned)
    level: str = BASIC
    # Who wants to know how far the model is, whenever that changes (see Progress's planning)
    listener: Callable[[Planning], None] | None = None

    def __post_init__(self) -> None:
        self._slide_numbers = {slide.key: slide_nr for slide_nr, slide in self.planned.items()}
        self._changed = threading.Condition()
        self._spine_in = False  # whether all of the spine came in
        self._in_english = False  # whether the spine reads as English, in a talk in another language
        self._reached = -1  # the last slide whose part of the answer came in
        self._finished = False
        self._shapes: list[str] = []  # what came in, by its keys and kinds (see answer_shape)
        self._given_up: set[int] = set()  # (the slides whose own requests ended without them, out of order)
        self._heard = False  # whether the model's answer has started coming in (for the listener)
        self._outlined = False  # whether the outline is all in, at the Advanced level (for the listener)
        self._partial = 0  # the spine's fields in so far, while it comes in as one object (for the listener)

    def tell(self) -> None:
        """Tell the listener, if any, how far the model is (see Planning). One that fails is told no more: how far a
        talk is never stops it (this runs inside the model's answer as it comes in)."""
        listener = self.listener
        if listener is None:
            return
        with self._changed:
            ideas = frozenset(slide_nr for slide_nr, slide in self.planned.items() if slide.idea)
            planning = Planning(
                writes=tuple(sorted(self.planned)),
                heard=self._heard,
                parts=max(len(self.spine), self._partial) + len(ideas),
                planned=ideas,
                written=frozenset(self.plans),
                # (a Basic answer's slides come after its spine; an Advanced talk's plan is its outline: every slide's
                # idea, or else all of it)
                plan_in=(self._spine_in or bool(self.plans))
                if self.in_order
                else self._outlined or ideas.issuperset(self.planned),
                answered=self._finished,
            )
            try:
                listener(planning)
            except Exception:
                logger.exception("Telling how far the language model is crashed: it's told no more")
                self.listener = None

    def heard(self) -> None:
        """The model's answer has started coming in."""
        if not self._heard:
            with self._changed:
                self._heard = True
            self.tell()

    def reading(self, key: str | None, parts: int) -> None:
        """What of the answer is being read (see ObjectReader.reading): the spine, as one object, with that many of its
        fields in so far, or another part."""
        partial = parts if key == SPINE else 0
        if partial != self._partial:
            with self._changed:
                self._partial = partial
            self.tell()

    def outlined(self) -> None:
        """The outline is all in (or there won't be more of it), at the Advanced level."""
        with self._changed:
            self._outlined = True
        self.tell()

    def answer_shape(self) -> str:
        """What the model's answer brought, in order, by its parts' keys and the kinds of their values (never their
        texts): "about (an object of unsafe_topic, thesis, title, ...), slides (an object of slide_02, ...)", say."""
        with self._changed:
            return ", ".join(self._shapes) or "nothing"

    @property
    def title(self) -> str | None:
        return clean_text(self.spine.get("title"), TALK_TITLE, self.language)

    @property
    def in_english(self) -> bool:
        """Whether the answer's spine reads as English, in a talk in another language (when it's checked): then its
        slides aren't looked for, and the model is asked again."""
        with self._changed:
            return self._in_english

    @property
    def presenter_name(self) -> tuple[Any, Any]:
        """The presenter's name the model wrote, if it was asked for one, and what it plays on (both as written: see
        talkgenerator.names)."""
        return self.spine.get("presenter_name"), self.spine.get("name_plays_on")

    def take(self, key: str, value: Any) -> None:
        """A part of the model's answer: the spine (one object, or else one of its fields), or a slide (whose first
        attempt then starts, in parallel). Slides inside another object of the answer count too, after it: Claude
        Haiku, given the schema as text, wrote every slide into the spine's object."""
        with self._changed:
            self._shapes.append(_shape(key, value))
            slide_nr = self._slide_numbers.get(key)
            inside: dict[str, Any] = {}
            if slide_nr is None and isinstance(value, dict):
                inside = {name: part for name, part in value.items() if name in self._slide_numbers}
                value = {name: part for name, part in value.items() if name not in inside}
            if key == SPINE:
                if isinstance(value, dict):
                    self.spine.update(value)
                    self._spine_in = True
            elif slide_nr is None:
                if value or not inside:  # (not an object that only held slides, such as "slides")
                    self.spine[key] = value
                self._spine_in = self._spine_in or self.spine_fields <= self.spine.keys()
            else:
                self._take_slide(slide_nr, value)
            if self._spine_in and self.check_language and not self._in_english:
                # (its texts, but the presenter's name, which may pun in any language, and what it plays on)
                texts = [
                    text
                    for name, text in self.spine.items()
                    if isinstance(text, str) and name not in ("presenter_name", "name_plays_on")
                ]
                self._in_english = languages.reads_as_english(texts, self.language)
            for name, part in inside.items():
                self._take_slide(self._slide_numbers[name], part)
            self._changed.notify_all()
            self.tell()

    def _take_slide(self, slide_nr: int, value: Any) -> None:
        """A slide's part of the answer (with the lock held): its plan, and its first attempt, started in parallel."""
        if self.spine.get("unsafe_topic") is True or self._in_english:  # (they come first: then no slide is looked for)
            return
        self._reached = max(self._reached, slide_nr)
        plan = slide_plan(self.planned[slide_nr], value)
        if plan is not None:
            self.plans[slide_nr] = plan
            if self.pool is not None:
                realize_it = image_util.carry(self._realize)  # (checking images as the talk does)
                # (unless the slide is due before a thread of the pool gets to it, in a talk with a time limit: then
                # its first attempt starts apart from the pool, see attempt)
                first = self._started.then(functools.partial(_first_attempt, realize_it))
                outcome = self.first_attempts[slide_nr] = _Outcome()
                self.pool.apply_async(outcome.deliver, (first, slide_nr))

    def wait_for_spine(self) -> None:
        """Wait for the spine of the answer (its title, the presenter's job and name, its thesis), all of it, or the
        end of the answer: then a talk that streams gets the spine a talk made at once gets. It comes before the
        slides, also from models that write the answer in alphabetical order. A spine that finds the topic unsafe, or
        reads as English in a talk in another language, doesn't count, as the model is then asked again."""
        self._wait(
            lambda: (
                (self._spine_in and self.spine.get("unsafe_topic") is not True and not self._in_english)
                or self._finished
            )
        )

    def wait_for_a_plan(self) -> bool:
        """Wait for the first slide the model wrote, or the end of the answer: whether it wrote any slide."""
        self._wait(lambda: bool(self.plans) or self._finished)
        return bool(self.plans)

    def wait_for(self, slide_nr: int) -> None:
        """Wait for the slide's part of the answer (or a later slide's, as when its part didn't parse, or the end); for
        slides that come in any order, for the slide's own request to end."""
        self._wait(
            lambda: (
                slide_nr in self.plans
                or (self._reached > slide_nr if self.in_order else slide_nr in self._given_up)
                or self._finished
            )
        )

    @property
    def spine_in(self) -> bool:
        """Whether all of the spine came in."""
        with self._changed:
            return self._spine_in

    def has_plan(self, slide_nr: int) -> bool:
        with self._changed:
            return slide_nr in self.plans

    def give_up(self, slide_nr: int) -> None:
        """The slide's own request ended without it (in a talk whose slides come in any order): it's classic."""
        with self._changed:
            self._given_up.add(slide_nr)
            self._changed.notify_all()
            self.tell()

    def _wait(self, ready: Callable[[], bool]) -> None:
        """Wait until it's ready; TalkCancelled once the talk is cancelled (which is looked at four times a second)."""
        with self._changed:
            while not self._changed.wait_for(lambda: ready() or self.cancelled.is_set(), timeout=0.25):
                pass
        if self.cancelled.is_set():
            raise TalkCancelled()

    def finish(self) -> None:
        """The answer is in (or there won't be one)."""
        with self._changed:
            self._finished = True
            self._changed.notify_all()
            self.tell()

    def attempt(
        self, slide_nr: int, attempt: int, seconds: float | None = None
    ) -> tuple[tuple[Any, list] | None, bool]:
        """The slide's attempt, realized (or None), and whether it came within the seconds (always, without them):
        one that doesn't goes on by itself (late_work, for the slide to come after all), and the talk doesn't wait for
        it when it closes (abandoned). With seconds, a first attempt that hasn't started yet (the pool's threads are
        busy) starts now, apart from the pool."""
        with self._changed:
            under_way = self.first_attempts.get(slide_nr) if attempt == 0 else None
            if under_way is not None and seconds is not None and self._started.claim(slide_nr):
                # (it starts now, apart from the pool, whose thread skips it; and it's what's waited for from now on)
                under_way = self.first_attempts[slide_nr] = _Running(functools.partial(self._realize, slide_nr, 0))
        if under_way is None:
            if seconds is None:
                return self._realize(slide_nr, attempt), True
            under_way = _Running(functools.partial(self._realize, slide_nr, attempt))
        if not under_way.wait(seconds):
            self.abandoned = True
            self.late_work[slide_nr] = under_way
            return None, False
        result: tuple[Any, list] | None = under_way.result()
        return result, True

    def _realize(self, slide_nr: int, attempt: int) -> tuple[Any, list] | None:
        recipe = self.planned[slide_nr].recipe
        with self._changed:
            plan = self.plans.get(slide_nr)
        if plan is None:
            return None  # (dropped: by a model that declined halfway, say)
        problems: list[str] = []
        try:
            # (a chart or a diagram that tries a picture first, in its place: its text version if none is found, D73)
            picture = picture_version(plan, recipe)
            if picture is not None:
                found = realize(*picture, self.contexts[slide_nr], self.rngs[slide_nr].child(PICTURE), attempt)
                if found is not None:
                    found[0].add_note(f"Picture first: in place of its {recipe.kind}, under its title")
                    return found
                logger.info(
                    "Planned slide %s, try %s: no picture found first: its text version", slide_nr + 1, attempt + 1
                )
            result = realize(plan, recipe, self.contexts[slide_nr], self.rngs[slide_nr], attempt, problems=problems)
        except Exception:  # one misbehaving source shouldn't sink the talk: the slide goes classic
            logger.exception("Realizing planned slide %s crashed", slide_nr + 1)
            return None
        if result is None:  # (why, for whoever reads the logs: a field the model left empty, an image not found)
            logger.info("Planned slide %s, try %s: %s", slide_nr + 1, attempt + 1, "; ".join(problems) or "no reason")
        return result

    def drop(self) -> None:
        """Forget what the model wrote."""
        with self._changed:
            self.plans.clear()
            self.first_attempts.clear()
            self._started = _Started()
            for written in ("title", "own_title", "presenter_name", "name_plays_on"):
                self.spine.pop(written, None)
            self._changed.notify_all()
            self.tell()

    def restart(self) -> None:
        """Forget the answer, for the model to be asked again."""
        with self._changed:
            self.plans.clear()
            self.first_attempts.clear()
            self._started = _Started()  # (the first answer's attempts that are under way go on apart, unwanted)
            self.spine.clear()
            self._spine_in = False
            self._in_english = False
            self._reached = -1
            self._shapes.clear()
            self._given_up.clear()
            self.in_order = True
            self.level = BASIC
            self._heard = self._outlined = False  # (the model is asked again)
            self._partial = 0
            self._changed.notify_all()
            self.tell()

    def close(self) -> None:
        """Wait for the rest of the answer and for the slides being realized, unless the talk was cancelled, or a
        slide ran out of time (abandoned): then they finish by themselves (on daemon threads, which nothing waits for)."""
        if self.answering is not None and not self.cancelled.is_set():
            self.answering.join()
        self.answering = None
        if self.pool is not None:
            self.pool.close()
            if not self.cancelled.is_set() and not self.abandoned:
                self.pool.join()
            self.pool = None


# The spare generators a spare slide tries, at most, before it's left out (each another kind)
SPARE_TRIES: Final = 3


class _Spares:
    """A talk's spare slides, which its Progress wants (spares) to show while the talk's next slide isn't in yet: made
    one after another on a thread of their own from the talk's start, each handed over (Progress.spare) as soon as it's
    made, until the talk's slides are all settled (stop), after which a spare is of no use, and none is handed over.

    A spare comes from one of the schema's spare generators (see PresentationSchema's spare_generators), which its
    dice pick by their weights times the persona's, another one for every spare, about the talk's topic: slides that
    take a fraction of a second and hardly ever fail. In a talk in another language than English, whose classic slides
    would be English, it's a picture of the topic without text instead (as a planned slide that didn't come out
    becomes: see PresentationSchema._picture_slide). A spare that fails tries another generator (SPARE_TRIES in all),
    and is left out if none works.

    Its random streams are its own (the talk's "spare" stream, by the spare's number), so the talk's slides come out
    the same with spares or without, as long as the sources give the same answers. The spares avoid repeating each
    other's texts and pictures (not the talk's, which are being made at the same time)."""

    def __init__(
        self,
        schema: "PresentationSchema",
        count: int,
        slide_deck: SlideDeck,
        context: dict[str, Any],
        rng: random_util.Rng,
        progress: Progress,
        persona: Persona | None = None,
    ) -> None:
        self.schema = schema
        self.count = count
        self.slide_deck = slide_deck
        self.context = context
        self.rng = rng
        self.progress = progress
        self.persona = persona
        self.handed_over = 0
        self._stopped = False
        self._lock = threading.Lock()  # (held while one is handed over: none comes after stop)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # (finding pictures as the talk does, by its license policy and theme, and probing them while it streams)
        self._thread = threading.Thread(target=image_util.carry(self._make), name="spares", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """No spare is handed over anymore (one being made is left to finish by itself, and dropped)."""
        with self._lock:
            self._stopped = True

    @property
    def stopped(self) -> bool:
        with self._lock:
            return self._stopped or self.progress.cancelled.is_set()

    def _make(self) -> None:
        state = _DeckState()
        used: set[SlideGeneratorData] = set()
        try:
            for number in range(self.count):
                if self.stopped:
                    return
                worked_out = self._spare(number, state, used)
                if worked_out is None:
                    continue
                _add_used(state, worked_out.generated_elements)
                with self._lock:
                    if self._stopped or self.progress.cancelled.is_set():
                        return
                    self.progress.spare(self.slide_deck, self.handed_over, worked_out.slide)  # type: ignore[attr-defined]
                    self.handed_over += 1
        except TalkCancelled:
            pass
        except Exception:  # (a spare must never stop the talk)
            logger.exception("Making the talk's spare slides crashed: it has no more of them")

    def _spare(self, number: int, state: _DeckState, used: set[SlideGeneratorData]) -> _WorkedOutSlide | None:
        """The number-th spare (from 0), worked out: from a spare generator the spare's dice pick among those not used
        yet (and another one if it fails), or in a talk in another language than English, a picture of the topic."""
        rng = self.rng.child(number)
        topic = str(self.context["seed"])
        label = f"spare {number + 1}"
        if self.slide_deck.language != "en":
            picture = self.schema._picture_slide(number, topic, self.context, rng.child("picture"), state)
            if picture is None:
                logger.info("No picture of %r for %s: it's left out", topic, label)
            return picture
        for attempt in range(SPARE_TRIES):
            generator = self.schema._pick_spare_generator(rng.child("pick", attempt), self.persona, used)
            if generator is None:
                break
            used.add(generator)
            quick = {**self.context, slides.STANDING_IN: True}  # (looking nothing up: D73)
            result = self.schema._run_generator(generator, number, quick, rng.child("content", attempt), state, label)
            if result is not None and self.schema._is_new_enough(result, generator, state):
                return _WorkedOutSlide(number, generator, *result)
        logger.info("No spare generator made %s about %r: it's left out", label, topic)
        return None


class _Early:
    """Early versions of a talk's last slides (slides: their numbers), which its Progress wants (early) for a
    presentation to show when it reaches one of them before it's made. Each is that slide's stand-in (see
    PresentationSchema._quick_version: about the slide's own seed, of the spare kinds, mostly in well under a second,
    though a kind that looks a word or a question up can take a few; in a talk in another language, a picture of that
    seed without text, which is looked for), made early: one after another,
    in the slides' order, on a thread of their own from the talk's start, each handed over (Progress.early_version,
    with the slide's number) as soon as it's made, until the talk's slides are all settled (stop).

    A slide that runs out of time (see _Clock), or can't be made, has its early version take its place (take), as long
    as it doesn't repeat a slide before it and the talk's caps allow its kind: so what a presentation showed stays,
    until the real slide comes after all (see _LateSlides). The early versions come from the slides' own stand-in
    streams, so the talk's slides come out the same with them or without, as long as none runs out of time or fails.
    They avoid repeating each other (not the talk's slides, which are being made at the same time)."""

    def __init__(
        self,
        schema: "PresentationSchema",
        slides: Sequence[int],
        slide_deck: SlideDeck,
        contexts: list[dict[str, Any]],
        rng: random_util.Rng,
        progress: Progress,
        persona: Persona | None = None,
    ) -> None:
        self.schema = schema
        self.slides = tuple(slides)
        self.slide_deck = slide_deck
        self.contexts = contexts
        self.rng = rng
        self.progress = progress
        self.persona = persona
        self._made: dict[int, _WorkedOutSlide] = {}
        self._stopped = False
        self._lock = threading.Lock()  # (held while one is handed over: none comes after stop)
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        # (finding pictures as the talk does, by its license policy and theme, and probing them while it streams)
        self._thread = threading.Thread(target=image_util.carry(self._make), name="early versions", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """No early version is handed over anymore (one being made is left to finish by itself, and dropped)."""
        with self._lock:
            self._stopped = True

    def take(self, slide_nr: int) -> _WorkedOutSlide | None:
        """The slide's early version, if it's made by now (once: then it's the deck's)."""
        with self._lock:
            return self._made.pop(slide_nr, None)

    def _make(self) -> None:
        state = _DeckState()  # (what the early versions use, for them not to repeat each other)
        try:
            for slide_nr in self.slides:
                with self._lock:
                    if self._stopped or self.progress.cancelled.is_set():
                        return
                if self.slide_deck.has_slide_nr(slide_nr):
                    continue  # (it's in already: its early version would be of no use)
                context = self.contexts[slide_nr]
                made = self.schema._quick_version(
                    slide_nr,
                    self.slide_deck.size,
                    context,
                    self.rng,
                    state,
                    self.persona,
                    self.slide_deck.language,
                    label=f"an early version of slide {slide_nr + 1}",
                )
                if made is None:
                    logger.info("Slide %s has no early version (about %r)", slide_nr + 1, context["seed"])
                    continue
                self.schema._update_used_elements(
                    state.used_elements, state.used_tags, made.generated_elements, made.generator
                )
                with self._lock:
                    if self._stopped or self.progress.cancelled.is_set():
                        return
                    self._made[slide_nr] = made
                    self.progress.early_version(self.slide_deck, slide_nr, made.slide)  # type: ignore[attr-defined]
        except TalkCancelled:
            pass
        except Exception:  # (an early version must never stop the talk)
            logger.exception("Making early versions of the talk's slides crashed: it has no more of them")


# How many pictures of its topic a talk with a time limit per slide finds early, for the slides that run out of time
# to find their own (a slide has three at most), and the looks whose pictures are of a kind of their own, which a
# picture of the topic can't stand in for: a meme's template, a poster, a chart, a book's cover
SPARE_PICTURES: Final = 3
_OWN_KIND_LOOKS: Final = frozenset({"meme-templates", "inspirobot", "bad-charts", "book-covers"})


class _SparePictures:
    """Pictures of a talk's topic, found early (one after another on a thread of their own, as the talk finds its
    images), for the slides a language model writes that run out of time to look for their own (see
    PresentationSchema._in_time): each takes one, once, for an image it can't do without. A picture of the topic goes
    in any image slot but those of a kind of their own (_OWN_KIND_LOOKS), as long as its orientation and size fit.
    Its random stream is its own (the talk's "spare pictures" stream), so the talk's slides come out the same with it
    or without, as long as the sources give the same answers."""

    def __init__(self, topic: str, count: int, rng: random_util.Rng) -> None:
        self.topic = topic
        self.count = count
        self.rng = rng
        self._found: list[ImageData] = []
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def start(self) -> None:
        threading.Thread(target=image_util.carry(self._find), name="spare pictures", daemon=True).start()

    def stop(self) -> None:
        """No more of them are looked for (one being looked for is left to finish by itself)."""
        self._stopped.set()

    def _find(self) -> None:
        slot = ImageSlot(intent="a picture of the talk's topic", aesthetic="neutral")
        try:
            with random_util.use(self.rng):
                for _ in range(self.count):
                    if self._stopped.is_set():
                        return
                    with self._lock:
                        found_so_far = list(self._found)
                    picture = slot.find(self.topic, avoid=found_so_far)
                    if picture is None:
                        return
                    with self._lock:
                        self._found.append(picture.found_with(self.topic))
        except Exception:  # (a spare picture must never stop the talk)
            logger.exception("Finding spare pictures of %r crashed", self.topic)

    def take(self, source: Any, avoid: Collection[Any] = ()) -> ImageData | None:
        """A spare picture for the source of a slide's image (see _photo_slots: None for a source that takes none),
        not one of those to avoid (by its address), and that no other slide gets."""
        slots = _photo_slots(source)
        if not slots:
            return None
        shown = {image.get_image_url() for image in avoid if isinstance(image, ImageData)}
        with self._lock:
            for picture in self._found:
                if picture.get_image_url() not in shown and all(finder.fits(picture, slot) for slot in slots):
                    self._found.remove(picture)
                    return picture
        return None

    def give_back(self, pictures: Collection[ImageData]) -> None:
        """Pictures taken for a slide that didn't come out after all: for another one, then, before the others (the
        first ones found are the finder's best)."""
        with self._lock:
            self._found[:0] = [picture for picture in pictures if picture not in self._found]

    def lending(self, avoid: Collection[Any]) -> "_Lending":
        """What a slide out of time takes its spare pictures from (not one of those to avoid): see _Lending."""
        return _Lending(self, list(avoid))


class _Lending:
    """The spare pictures one slide out of time takes (see _SparePictures.take), as realize asks for them, which go
    back to the others when the slide doesn't come out after all (give_back)."""

    def __init__(self, pictures: _SparePictures, avoid: list[Any]) -> None:
        self._pictures = pictures
        self._avoid = avoid
        self.taken: list[ImageData] = []

    def __call__(self, source: Any, others: list[ImageData]) -> ImageData | None:
        picture = self._pictures.take(source, [*others, *self._avoid])
        if picture is not None:
            self.taken.append(picture)
        return picture

    def give_back(self) -> None:
        self._pictures.give_back(self.taken)
        self.taken = []


def _photo_slots(source: Any) -> list[ImageSlot] | None:
    """The image slots that a source of a slide's image finds its picture with, when a spare picture of the talk's
    topic can stand in for theirs: the slot itself, or a CombinedGenerator's, when they're all image slots (a photo or
    a weird picture, say). None for any other source, or for slots whose pictures are of a kind of their own (a meme's
    template, a chart: _OWN_KIND_LOOKS)."""
    if isinstance(source, ImageSlot):
        slots = [source]
    elif isinstance(source, generator_util.CombinedGenerator) and source.choices:
        if not all(isinstance(choice, ImageSlot) for choice in source.choices):
            return None
        slots = [choice for choice in source.choices if isinstance(choice, ImageSlot)]
    else:
        return None
    return None if any(slot.aesthetic in _OWN_KIND_LOOKS for slot in slots) else slots


def _picture_first(generator: SlideGeneratorData) -> SlideGeneratorData:
    """The slide generator, or for a chart or a diagram (a kind that tries a picture first: see
    talkgenerator.plan.kinds.PictureFirst), a copy of it whose classic slides try a picture first, now and then, in their
    place (see slide_generator_types.PictureFirstSlideGenerator), with the generator itself as its text version."""
    kind = KINDS.get(generator.llm.kind) if generator.llm is not None else None
    first = kind.picture_first if kind is not None else None
    if first is None or generator.text_version is not None:
        return generator
    picture = slide_generator_types.PictureFirstSlideGenerator(generator.slide_generator, first.slot(), first.odds)
    made = generator.wrapped(picture)
    made.text_version = generator
    return made


class PresentationSchema:
    """Class responsible for determining which slide generators to use in a presentation,
    and how the (topic) seed for each slide is generated."""

    def __init__(
        self,
        powerpoint_creator,
        seed_generator: Callable[[list[str], int], SlideSeedGenerator],
        title_generator,
        slide_generators: list[SlideGeneratorData],
        max_allowed_tags=None,
        ignore_weights=False,
        title_candidates: Sequence[titles.TitleGenerator] = (),
        license_policy: str = licenses.DEFAULT,
        looks: Mapping[str, str] | None = None,
        format: "Format | None" = None,
        spare_generators: Sequence[tuple[SlideGeneratorData, float]] = (),
    ):
        """title_generator makes a classic talk's title, and title_candidates are more classic title generators (such
        as wikiHow's "How to ..." titles), whose titles, with the title generator's, a language model may pick for a
        talk on what was typed when it reads that as a topic (see talkgenerator.titles).

        format is what a talk format beyond the TED-like talks is besides its slides (see
        talkgenerator.schema.formats): its brief for the language model, what its titles and its presenter's job are
        like, how likely each persona is to present it, its talks' theme families and its arc. Without one, a talk is
        a TED-like talk, and its requests to a language model say nothing of a format.

        spare_generators make a streamed talk's spare slides, which it shows while its next slide isn't in yet (see
        _Spares), each with its weight: slide generators that are quick and hardly ever fail (see
        talkgenerator.schema.slide_schemas.SPARE_GENERATORS). Without them, a talk in English has no spares."""
        self.format = format
        self.spare_generators: tuple[tuple[SlideGeneratorData, float], ...] = tuple(spare_generators)
        self._powerpoint_creator = powerpoint_creator
        # The license classes its talks' images may have, unless a talk says otherwise (see talkgenerator.images.licenses)
        self.license_policy = licenses.policy(license_policy).name
        # Its own looks for the looks its slides ask for, such as "corporate-stock" for "photo" (see
        # talkgenerator.images.profiles)
        self.looks: Mapping[str, str] = dict(looks or {})
        for look in (*self.looks, *self.looks.values()):
            profiles.profile(look)
        self._unservable: dict[tuple[str, bool], frozenset[SlideGeneratorData]] = {}
        self._seed_generator = seed_generator
        # (a classic chart or diagram that tries a picture first, now and then, in its place: D73)
        slide_generators = [_picture_first(generator) for generator in slide_generators]
        self._slide_generators = slide_generators
        self._generator_indices = {id(generator): index for index, generator in enumerate(slide_generators)}
        if max_allowed_tags is None:
            max_allowed_tags = {}
        self._max_allowed_tags = max_allowed_tags
        self._ignore_weights = ignore_weights
        self._title_generator = title_generator
        self._title_candidates = tuple(title_candidates)

    @property
    def slide_generators(self) -> list[SlideGeneratorData]:
        return list(self._slide_generators)

    def generate_presentation(
        self,
        topics: list[str],
        num_slides: int,
        presenter=None,
        title: str | None = None,
        parallel: bool | int = False,
        int_seed: int | None = None,
        save_ppt: bool = True,
        debug_notes: bool = False,
        rng: random_util.Rng | None = None,
        llm: TextProvider | None = None,
        language: str = "en",
        theme: Theme | None = None,
        style_chaos: float = 0.0,
        extreme_themes: bool = True,
        progress: Progress | None = None,
        name_styles: Sequence[str] | None = None,
        topic_or_title: str | None = None,
        persona: Persona | None = None,
        theme_families: Sequence[str] | None = None,
        llm_level: str = BASIC,
    ) -> tuple[Presentation | None, SlideDeck]:
        """Generate a presentation about a certain topic with a certain number of slides.

        With topic_or_title, what was typed for the talk, which could be its topic or its title: the topics come
        from it (see talkgenerator.titles.topics_from), and the language model that writes the talk tells which it is,
        in the same request, or else talkgenerator guesses (see talkgenerator.titles). The deck tells how it was read.

        The same seed (int_seed, or the talk's random generator rng) gives the same talk, in parallel or not, as long
        as the sources give the same answers. Without a seed, a random one is picked: the deck tells which. parallel
        is True (the slides all at once, a planned talk's eight at a time), False (one by one), or how many slides are
        made at the same time at most (see slides_at_once).

        With a language model (llm), the model writes what goes on the slides, in the given language (see
        _plan_talk); the slides it doesn't write, or that come out missing something, are classic. At llm_level
        ADVANCED, it plans the talk first, in a request of its own (see talkgenerator.plan.outline): every slide's word
        to riff on, among those the dice offer, and its idea. The deck says which level its slides were written at.

        With a persona (see talkgenerator.personas), the talk is theirs: they weigh in on its kinds of slides, its
        title and the style of its presenter's name, and the language model writes in their voice. The deck tells
        which persona it had.

        Without a presenter, the presenter's name is made up in one of the name styles (see talkgenerator.names): by
        the language model, in the same request, or else by talkgenerator. Without name_styles, in one of the default
        styles, nudged by the persona; with them, in one of those alone.

        With a progress, the talk streams (see Progress): its slides are settled as soon as they can be, a planned
        talk's while the model writes the rest. The one difference with a talk that doesn't stream: when the model
        declines halfway, the slides settled by then stay (only those that come after are classic)."""
        if rng is None:
            rng = random_util.Rng(int_seed)

        logger.info("Made it to presentation_schema...")
        # A talk the language model writes picks its slides' generators first (they don't depend on the slides'
        # seeds), so that the real facts for those that build on one can be looked up while the seeds are (see
        # talkgenerator.facts)
        writes = llm is not None and self.writes_with(llm)
        picks = self._pick_generators(num_slides, rng, language, persona) if writes else None
        gathering = None
        uses = {use for pick in picks or () if (use := _fact_use(pick)) is not None}
        if uses and facts.on():
            # (only what its slides use: a talk without a fun fact asks for no useless fact, and so on)
            gathering = facts.gather(topics[0], language, uses=uses, rng=rng.child("facts"))
        # The photo of the talk's world beside its title, looked up from now on, as it needs nothing the model writes
        # (D80: see talkgenerator.title_pictures)
        title_picture = title_pictures.lookup(topics[0], self.format, persona, rng.child("title picture"))
        # Create the topic-for-each-slide generator, and every slide's topic: in a talk in another language, seeds wander
        # from what its topic is in English, as the related words are English (D74: Dutch "regen", rain, wandered to
        # "renovation"), and its slides on the topic have it as typed
        with random_util.use(rng.child("topics")), slide_topic_generators.wandering_in(language):
            seed_generator = self._seed_generator(topics, num_slides)
        logger.info("Seed generator: {}".format(seed_generator))
        seeds = []
        for slide_nr in range(num_slides):
            with random_util.use(rng.child("slide", slide_nr, "topic")):
                seeds.append(seed_generator.get_seed(slide_nr))
        # (the words a model that plans the talk is offered for each slide: its seed first, by slide number from 1)
        offers = {slide_nr + 1: (seed, *seed_generator.alternatives(slide_nr)) for slide_nr, seed in enumerate(seeds)}
        # (the slides whose words are English, in a talk in another language, which the language model then says in
        # the talk's language: see PlannedSlide.english)
        english = frozenset(slide_nr for slide_nr in range(num_slides) if seed_generator.in_english(slide_nr))

        # The presenter's name, unless it's given: made up in a style the talk's dice pick, by the language model
        # that writes the talk (in the same request), or else by talkgenerator (see talkgenerator.names); in one of
        # the default styles, nudged by the persona, unless the talk says which styles it may have
        nudge = persona.nudge if persona is not None and name_styles is None else None
        styles = names.DEFAULT_STYLES if name_styles is None else name_styles
        naming = names.Naming.of(styles, topics, rng, written=writes, nudge=nudge) if not presenter else None
        # What was typed, when it could be the topic or the title: the language model that writes the talk tells which
        # (and weighs classic titles for a topic), or else talkgenerator guesses (see talkgenerator.titles)
        titling = None
        if topic_or_title:
            # The classic talk's title first (the persona's or the title generator's), and then another one of the
            # title generator's, from a stream of its own
            classic = self._classic_title_generator(persona)
            generators = (*([classic] if classic is not None else []), *self._title_candidates)
            if self._title_generator is not None:
                generators = (*generators, self._title_generator)
            titling = titles.Titling.of(topic_or_title, language, writes, generators, topics[0], rng)

        talk = None
        spares: _Spares | None = None
        early: _Early | None = None
        pictures: _SparePictures | None = None
        if llm is not None and writes:
            cancelled = progress.cancelled if progress is not None else None
            name = naming.request if naming is not None else None
            typed = titling.request if titling is not None else None
            talk = self._plan_talk(
                topics,
                seeds,
                rng,
                llm,
                language,
                title,
                parallel,
                cancelled,
                name,
                typed,
                persona=persona,
                picks=picks,
                gathering=gathering,
                level=llm_level,
                offers=offers,
                listener=getattr(progress, "planning", None),  # (how far the model is, for a Progress that asks)
                english=english,
            )
        # The time a slide may take, if its progress gives one (see _Clock), and for a talk a language model writes,
        # the pictures of its topic that its slides can have when they run out of time to find their own: looked for
        # from now on, while the model writes
        seconds = _time_limit(progress)
        if seconds is not None and talk is not None:
            # (of the topic as it is in English, in a talk in another language: the picture sources search English best)
            pictured = seed_generator.english_name(topics[0])
            pictures = _SparePictures(pictured, SPARE_PICTURES, rng.child("spare pictures"))
            pictures.start()
        try:
            if talk is not None:
                talk.wait_for_spine()
            if naming is not None:
                presenter = naming.name(*(talk.presenter_name if talk is not None else ()))
                logger.info("Presenter: {}".format(presenter))
            # The title: what was typed when it reads as one, or else the model's, or else a classic one
            reading = None
            if titling is not None:
                title, reading = titling.settle(
                    talk.spine if talk is not None else {}, lambda: self._title(topics, rng, persona)
                )
            if not title and talk is not None:
                title = talk.title
            if not title:
                title = self._title(topics, rng, persona)
            logger.info("Generate talk title: {}".format(title))

            # A talk in another language needs the language model's slides: the classic ones are English
            planned = talk is not None and talk.wait_for_a_plan()
            talk_language = language if planned else "en"
            if language != talk_language:
                logger.warning("Without the language model's slides, this talk is classic, and so in English")

            # Create new presentation
            slide_deck = SlideDeck(
                num_slides,
                title=title,
                topics=topics,
                presenter=presenter,
                seed=rng.root_seed,
                language=talk_language,
            )
            slide_deck.theme, slide_deck.style_chaos, slide_deck.extreme_themes = theme, style_chaos, extreme_themes
            slide_deck.title_picture = title_picture  # (its world's photo beside its title, when it's in: D80)
            # (the families a chaos deck's slides get their own themes of: see talkgenerator.design.themes.allowed)
            slide_deck.theme_families = tuple(theme_families) if theme_families is not None else None
            slide_deck.language_model = llm.id if planned and llm is not None else None
            if planned and talk is not None:  # (Advanced once the model's outline came in)
                slide_deck.llm_level = talk.level
            slide_deck.facts = talk.facts if planned and talk is not None else ()
            slide_deck.topic_or_title = reading
            if persona is not None:  # (with the angle the language model was given, for a talk it writes)
                slide_deck.persona = persona.record(persona.angle(rng) if planned else None)
            logger.info("Slide deck: {}".format(slide_deck))
            if progress is not None:
                progress.started(slide_deck)
                slide_deck.listener = progress.settled
                slide_deck.update_listener = getattr(progress, "updated", None)
                slide_deck.replace_listener = getattr(progress, "replaced", None)

            # Create main presentation_context
            main_presentation_context = {
                "topic": topics[0],
                "topics": topics,
                "presenter": presenter,
                "title": title,
                "language": talk_language,
            }
            # (each with the seeds of the slides after it but the last, which a classic agenda announces: D80)
            contexts = [
                {
                    **create_slide_presentation_context(main_presentation_context, seed),
                    "later": tuple(seeds[index + 1 : -1]),
                }
                for index, seed in enumerate(seeds)
            ]
            # The spare slides its progress wants, if any, made from now on while the slides are (see _Spares)
            spares = self._spares(progress, slide_deck, main_presentation_context, rng, persona)
            # And the early versions of its last slides it wants, if any (see _Early)
            early = self._early(progress, slide_deck, contexts, rng, persona)
            if talk is not None and planned:
                lates = self._settle_planned_talk(
                    slide_deck, talk, contexts, rng, presenter, persona, seconds, pictures, early
                )
            else:
                lates = self._generate_slides(slide_deck, contexts, rng, parallel, persona, seconds, early)
            if spares is not None:
                spares.stop()  # (with every slide in, a spare is of no use anymore)
            if early is not None:
                early.stop()  # (nor an early version)
            if pictures is not None:
                pictures.stop()
            # Its closer, after its last slide (D76): right away, before the slides that ran out of time come after all,
            # so a presenter at the last slide goes on to it
            slide_deck.closer_listener = getattr(progress, "closed", None)
            slide_deck.close(self._closer(slide_deck, topics[0]))
            slide_deck.closer_listener = None
            # The slides that ran out of time, whose own work goes on: each comes after all, in place of what stood in
            # for it, if it does so within LATE_SECONDS (see _LateSlides)
            self._replace_late(lates, LATE_SECONDS, progress.cancelled if progress is not None else None)
            slide_deck.listener = None
            slide_deck.replace_listener = None
            _finish_picking(slide_deck, progress.cancelled if progress is not None else None)
            _finish_generating(slide_deck, progress.cancelled if progress is not None else None)
        except BaseException:
            if spares is not None:
                spares.stop()
            if early is not None:
                early.stop()
            if pictures is not None:
                pictures.stop()
            if talk is not None:
                talk.cancelled.set()  # (what's still coming in isn't wanted anymore)
            images = image_context.current()
            if images.generation is not None:
                images.generation.close()  # (and no generated picture either)
            if images.vision is not None:
                images.vision.close()  # (nor a vision pick)
            raise
        finally:
            if talk is not None:
                talk.close()

        if save_ppt:
            return self.render(slide_deck, debug_notes), slide_deck

        return None, slide_deck

    def _closer(self, slide_deck: SlideDeck, topic: str) -> slides.Slide:
        """The talk's closer (D76: see talkgenerator.closers): its format's (or the TED-like talk's), in its
        language, from its presenter's name, its title and its topic."""
        ending = closers.Ending.of(slide_deck.language, slide_deck.presenter, slide_deck.title, topic)
        slide = closers.of(self.format).slide(ending)
        slide.set_note("The closer, after the talk's last slide (D76)")
        return slide

    def _title(self, topics: list[str], rng: random_util.Rng, persona: Persona | None = None) -> str:
        """A classic talk's title, from the talk's "title" stream: its persona's or the title generator's."""
        with random_util.use(rng.child("title")):
            generator = self._classic_title_generator(persona)
            if generator is not None:
                title = generator({"seed": topics[0]})
                if title:
                    return str(title)
            return "About " + topics[0]

    def _classic_title_generator(self, persona: Persona | None) -> titles.TitleGenerator | None:
        """What makes a classic talk's title: the title generator, or with a persona, theirs (which half the time
        makes one of their own titles, and else the title generator's)."""
        if persona is None or not persona.titles:
            return self._title_generator
        return persona.title_generator(self._title_generator)

    def render(self, slide_deck: SlideDeck, debug_notes: bool = False) -> Presentation:
        """The deck as a PowerPoint presentation: in the classic template, or (with a theme) drawn as shapes."""
        if slide_deck.theme is not None:
            return render_pptx(slide_deck.to_deck(), debug_notes=debug_notes, images=slide_deck.image_store())
        presentation = self._powerpoint_creator()
        slide_deck.save_to_powerpoint(presentation, debug_notes=debug_notes)
        return presentation

    def _spares(
        self,
        progress: Progress | None,
        slide_deck: SlideDeck,
        context: dict[str, Any],
        rng: random_util.Rng,
        persona: Persona | None = None,
    ) -> "_Spares | None":
        """The spare slides the talk's progress wants (its spares), under way about the talk's topic; None when it
        wants none, or when there's nothing to make them with (a talk in English, without spare generators)."""
        count = getattr(progress, "spares", 0) if progress is not None else 0
        if progress is None or not isinstance(count, int) or count <= 0 or not hasattr(progress, "spare"):
            return None
        if slide_deck.language == "en" and not self.spare_generators:
            return None
        spares = _Spares(
            self, count, slide_deck, {**context, "seed": context["topic"]}, rng.child("spare"), progress, persona
        )
        spares.start()
        return spares

    def _early(
        self,
        progress: Progress | None,
        slide_deck: SlideDeck,
        contexts: list[dict[str, Any]],
        rng: random_util.Rng,
        persona: Persona | None = None,
    ) -> "_Early | None":
        """Early versions of the talk's last slides, as many as its progress wants (its early, never the title slide),
        under way; None when it wants none, or when there's nothing to make them with (a talk in English, without
        spare generators)."""
        count = getattr(progress, "early", 0) if progress is not None else 0
        if progress is None or isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            return None
        if not hasattr(progress, "early_version") or (slide_deck.language == "en" and not self.spare_generators):
            return None
        slides = range(max(1, len(contexts) - count), len(contexts))
        if not slides:
            return None
        early = _Early(self, slides, slide_deck, contexts, rng, progress, persona)
        early.start()
        return early

    def writes_with(self, llm: TextProvider | None) -> bool:
        """Whether a language model writes this schema's talks: there is one, and slide generators with recipes."""
        if llm is None or isinstance(getattr(llm, "provider", llm), NoneProvider):
            return False
        return any(generator.llm is not None for generator in self._slide_generators)

    # TALKS A LANGUAGE MODEL WRITES

    def _plan_talk(
        self,
        topics: list[str],
        seeds: list[str],
        rng: random_util.Rng,
        llm: TextProvider,
        language: str,
        title: str | None,
        parallel: bool | int,
        cancelled: threading.Event | None = None,
        name: names.NameRequest | None = None,
        typed: titles.TitleRequest | None = None,
        persona: Persona | None = None,
        picks: list[SlideGeneratorData | None] | None = None,
        gathering: facts.Gathering | None = None,
        level: str = BASIC,
        offers: Mapping[int, Sequence[str]] | None = None,
        listener: Callable[[Planning], None] | None = None,
        english: Collection[int] = (),
    ) -> "_PlannedTalk":
        """Pick every slide's generator (as the persona weighs them, unless they're picked already), and ask the
        language model, in one request, what goes on the slides whose generators have recipes (and the presenter's
        name, with a name request, and for what was typed, whether it's the topic or the title, with a title request:
        see talkgenerator.titles), in the persona's voice; with the real facts being gathered (see talkgenerator.facts),
        the slides that build on one get one, once they're in. The model's answer is read while it's written, and in
        parallel, every slide's first attempt starts as soon as its part of the answer is in. For a talk that streams
        (that can be cancelled), the answer comes in on a thread of its own, and this returns at once, for the slides to
        be settled while it does.

        At level ADVANCED, the model plans the talk first, and its slides are written in parallel as their plans come in
        (see _write_planned); the talk is a Basic one when that can't be done. A listener hears how far the model is
        (see Planning), from now on. In a talk in another language, the slides whose seeds are English (english, by
        slide number from 0) have the model say them in the talk's language (see PlannedSlide.english)."""
        num_slides = len(seeds)
        if picks is None:
            picks = self._pick_generators(num_slides, rng, language, persona)
        planned: dict[int, PlannedSlide] = {}
        queried: frozenset[str] = frozenset()  # (what the variants so far search for: a meme's template comes once)
        for slide_nr, pick in enumerate(picks):
            if pick is None or pick.llm is None or pick.llm.kind == "title":
                continue
            # (a recipe with variants comes out as one of them, such as a chart with labels or without)
            recipe = pick.llm.varied(rng.child("slide", slide_nr, "variant"), avoid=queried)
            queried |= frozenset(recipe.queries.values())
            planned[slide_nr] = PlannedSlide(
                slide_nr + 1,
                pick.name or str(pick),
                recipe,
                seeds[slide_nr],
                digits=len(str(num_slides)),
                english=slide_nr in english,
            )
        # (an agenda announces some of the slides after it, which pick its items up: D80)
        planned = prompt.agenda_cues(planned)
        talk = _PlannedTalk(
            picks,
            planned,
            # What realizing a slide may know: its topic and language (not the title, which arrives with the answer)
            [{"topic": topics[0], "topics": topics, "seed": seed, "language": language} for seed in seeds],
            [rng.child("slide", slide_nr, "planned") for slide_nr in range(num_slides)],
            frozenset(prompt.spine(language, name, typed)),
            language=language,
            cancelled=cancelled or threading.Event(),
            listener=listener,
        )
        if not planned:
            talk.finish()
            return talk
        talk.tell()  # (it's asked)
        at_once = slides_at_once(parallel, len(planned), most=8)
        if at_once > 1:
            talk.pool = ThreadPool(processes=at_once)

        def answer() -> None:
            try:
                generation = image_context.current().generation  # (its images' prompts, if it generates pictures)
                if level == ADVANCED and self._write_planned(
                    llm, talk, topics, offers or {}, rng, language, title, name, typed, persona, generation, gathering
                ):
                    logger.info("The language model wrote %s of the %s slides", len(talk.plans), num_slides)
                    return
                given = self._facts_for(talk, gathering, rng)
                # The model is asked once more for a topic it found unsafe, or for a talk it started in English
                why_again: str | None = None
                for asked_again in (False, True):
                    if talk.cancelled.is_set():  # (while its facts came in, say)
                        break
                    talk.check_language = not asked_again
                    request = talk_request(
                        topics,
                        list(planned.values()),
                        rng,
                        language,
                        title,
                        why_again == "unsafe",
                        name,
                        typed,
                        generation,
                        persona=persona,
                        talk_format=self.format,
                        facts=given,
                        answered_in_english=why_again == "english",
                    )
                    self._ask(llm, request, talk)
                    if talk.cancelled.is_set():
                        break
                    if talk.spine.get("unsafe_topic") is True:  # (first: such a spine may well be in English too)
                        why_again = "unsafe"
                        if asked_again:
                            logger.warning("The language model wouldn't write about this topic: the talk is classic")
                        else:  # (some of the free models get the flag wrong: one turned down "penguins")
                            logger.info("The language model found the topic unsafe: asking once more")
                    elif talk.in_english:  # (a free model wrote a Swedish talk in English, 2026-11-08)
                        why_again = "english"
                        logger.info(
                            "The language model started the talk in English, not %s: asking once more",
                            languages.language(language).name,
                        )
                    else:
                        break
                    talk.restart()
                logger.info("The language model wrote %s of the %s slides", len(talk.plans), num_slides)
            finally:
                talk.finish()

        if cancelled is not None:
            talk.answering = threading.Thread(target=image_util.carry(answer), name="talk plan", daemon=True)
            talk.answering.start()
        else:
            answer()
        return talk

    def _write_planned(
        self,
        llm: TextProvider,
        talk: "_PlannedTalk",
        topics: list[str],
        offers: Mapping[int, Sequence[str]],
        rng: random_util.Rng,
        language: str,
        title: str | None,
        name: names.NameRequest | None,
        typed: titles.TitleRequest | None,
        persona: Persona | None,
        generation: "ImageGeneration | None",
        gathering: facts.Gathering | None,
    ) -> bool:
        """Write the talk at the Advanced level (see talkgenerator.plan.outline): the model plans it, in an outline that's
        read while it's written (its spine first, then every slide's word and idea), and its slides are written as their
        ideas come in, in batches (BATCHES: the second slide alone, then two, then three at a time), each in a request of
        its own, at most WRITERS at a time, from the plan so far; the slides the outline didn't plan, from the dice's
        words, once it's in. The slides come in any order, and each is realized as soon as it's in. With the real facts
        being gathered, they're waited for before the first batch's request (they're in by then, mostly).

        Whether the talk was written so (or cancelled): False when it's to be a Basic talk, as the outline brought no
        spine (an error, a refusal), found the topic unsafe, or started in English in a talk in another language (the
        Basic talk's request then asks again), or as the talk's budget can't afford the outline and a request per slide."""
        if talk.cancelled.is_set():
            return True
        planned = [talk.planned[slide_nr] for slide_nr in sorted(talk.planned)]
        request = outline_request(topics, planned, offers, rng, language, title, name, typed, persona, self.format)
        if isinstance(llm, MeteredProvider):
            estimates, left, number = [], list(planned), 0
            while left:  # (the batches, as the dice's words make them)
                batch, left = left[: batch_size(number)], left[batch_size(number) :]
                estimates.append(
                    writing_request(topics, batch, planned, {}, rng, language, persona, self.format, None, generation)
                )
                number += 1
            if not llm.affords(request, *estimates):
                logger.info("The talk's budget doesn't allow its outline and its slides' requests: it's a Basic talk")
                return False
        slide_numbers = {slide.key: slide_nr for slide_nr, slide in talk.planned.items()}
        # (what a Basic talk starts from, should the outline come to nothing: the dice's words)
        dice = (dict(talk.planned), [context.get("seed") for context in talk.contexts])
        ideas: dict[int, SlideIdea] = {}
        writing: list[Future[None]] = []
        submitted: set[int] = set()
        pending: list[int] = []  # (the slides whose ideas are in, for the next batch)
        planning = threading.Lock()  # (the plan as far as it goes, which the batches' requests read)
        dropped = threading.Event()  # (the outline was declined: what its slides' requests write isn't used)
        given: dict[int, facts.Given] | None = None
        talk.in_order = False
        talk.check_language = True
        writers = ThreadPoolExecutor(max_workers=min(WRITERS, len(planned)), thread_name_prefix="slide writer")

        def write(batch: list[int]) -> None:
            with planning:
                slides = [talk.planned[slide_nr] for slide_nr in batch]
                plan = [talk.planned[number] for number in sorted(talk.planned)]
            request = writing_request(
                topics, slides, plan, dict(talk.spine), rng, language, persona, self.format, given, generation
            )
            taken = self._ask_slides(llm, request, talk, batch, dropped)
            for slide_nr in batch:
                if slide_nr not in taken:
                    talk.give_up(slide_nr)

        def submit(batch: list[int]) -> None:
            nonlocal given
            batch = [slide_nr for slide_nr in batch if slide_nr not in submitted]
            if not batch or talk.cancelled.is_set():
                return
            if given is None:
                given = self._facts_for(talk, gathering, rng)
            submitted.update(batch)
            writing.append(writers.submit(image_util.carry(write), batch))

        reader = ObjectReader()
        read_anything = False

        def plan(slide_nr: int, value: Any) -> None:
            """A slide's part of the outline: its word and idea (if they're in), and its batch, once that's full."""
            if not talk.spine_in or slide_nr in submitted or slide_nr in pending:
                return
            idea = read_idea(value)
            if idea is not None:
                with planning:
                    # (a riff is in the talk's language, as the outline asks for it: see outline_request)
                    slide = talk.planned[slide_nr] = dataclasses.replace(
                        talk.planned[slide_nr], seed=idea.riff, idea=idea.idea, english=False
                    )
                    talk.contexts[slide_nr]["seed"] = idea.riff  # (for its notes)
                ideas[slide.number] = idea
                talk.tell()
            pending.append(slide_nr)
            if len(pending) >= batch_size(len(writing)):
                submit(pending[:])
                pending.clear()

        def read(text: str) -> None:
            nonlocal read_anything
            if talk.cancelled.is_set():
                raise TalkCancelled()  # (out of the provider's stream, which then stops)
            read_anything = True
            talk.heard()
            for key, value in reader.feed(text):
                slide_nr = slide_numbers.get(key)
                if slide_nr is not None:
                    plan(slide_nr, value)
                    continue
                # (the spine, with its running gag, which the batches' requests tell; slides' ideas that a model put
                # inside it, or in an object of their own, are ideas, not slides)
                inside = (
                    {name: part for name, part in value.items() if name in slide_numbers}
                    if isinstance(value, dict)
                    else {}
                )
                talk.take(key, {name: part for name, part in value.items() if name not in inside} if inside else value)
                if talk.spine.get("unsafe_topic") is True or talk.in_english:
                    raise _NotPlanned()
                if talk.spine_in:
                    talk.level = ADVANCED  # (before the first slide: the deck says so)
                for name, part in inside.items():
                    plan(slide_numbers[name], part)
            talk.reading(*reader.reading)

        try:
            response = llm.stream(request, read)
            if not read_anything:
                read(response.text)
            if response.finish == "refused":
                # (what a model wrote before it declined isn't to be used, as in a Basic talk: the spine, the slides)
                logger.warning("The language model declined to plan the talk: it's a Basic talk")
                dropped.set()
            elif response.finish != "complete":
                logger.warning(
                    "The language model's outline was %s: slides it didn't plan keep the dice's words", response.finish
                )
        except TalkCancelled:
            pass
        except _NotPlanned:
            logger.info("The talk's outline found the topic unsafe, or started in English: it's a Basic talk")
        except ProviderError as error:
            logger.warning("The language model didn't plan the talk (%s)", error)
        except Exception:  # a misbehaving provider shouldn't sink the talk either
            logger.exception("Asking the language model for the talk's outline crashed")
        talk.outlined()
        if not talk.cancelled.is_set() and (
            dropped.is_set() or not talk.spine_in or talk.spine.get("unsafe_topic") is True or talk.in_english
        ):
            dropped.set()
            writers.shutdown(cancel_futures=True)  # (the slides' requests under way stop at once)
            talk.planned.update(dice[0])
            for context, seed in zip(talk.contexts, dice[1], strict=True):
                context["seed"] = seed
            talk.restart()  # (and it's a Basic talk, from the dice's words)
            return False
        # (the slides still waiting for their batch, and those the outline didn't plan, from the dice's words)
        rest = sorted({*pending, *(slide_nr for slide_nr in talk.planned if slide_nr not in submitted)})
        while rest:
            size = batch_size(len(writing))
            submit(rest[:size])
            rest = rest[size:]
        for future in writing:
            while not talk.cancelled.is_set():
                try:
                    future.result(timeout=0.25)
                    break
                except TimeoutError:
                    continue
                except Exception:  # (write gives a slide up itself; this is what it didn't foresee)
                    logger.exception("Writing a planned slide crashed")
                    break
        writers.shutdown(wait=not talk.cancelled.is_set(), cancel_futures=talk.cancelled.is_set())
        if ideas:
            talk.outline = Outline(str(talk.spine.get("thesis") or ""), str(talk.spine.get(RUNNING_GAG) or ""), ideas)
            logger.info("The language model planned %s of the %s slides it writes", len(ideas), len(planned))
        return True

    @staticmethod
    def _ask_slides(
        llm: TextProvider, request: Any, talk: "_PlannedTalk", batch: list[int], dropped: threading.Event
    ) -> set[int]:
        """Ask for a batch of an Advanced talk's slides, and hand them to the talk while they come in: the ones that came
        (a slide the model doesn't write, or gets wrong, is classic, as in a Basic talk). A slide alone that a model
        wrote without its key around it (its fields at the answer's top) is taken as written. Once the outline is
        dropped, nothing more is taken."""
        keys = {talk.planned[slide_nr].key for slide_nr in batch}
        reader = ObjectReader()
        loose: dict[str, Any] = {}
        read_anything = False

        def read(text: str) -> None:
            nonlocal read_anything
            if talk.cancelled.is_set() or dropped.is_set():
                raise TalkCancelled()
            read_anything = True
            for name, value in reader.feed(text):
                if name in keys or (isinstance(value, dict) and keys & value.keys()):
                    talk.take(name, value)  # (a slide, or an object around some, which take looks into)
                else:
                    loose[name] = value

        try:
            response = llm.stream(request, read)
            if not read_anything:
                read(response.text)
            if response.finish == "refused":
                logger.warning("The language model declined to write slides %s: they're classic", _numbers(batch))
                return set()
        except TalkCancelled:
            return set()
        except ProviderError as error:
            logger.warning("The language model didn't write slides %s (%s): they're classic", _numbers(batch), error)
            return set()
        except Exception:  # a misbehaving provider shouldn't sink the talk either
            logger.exception("Asking the language model for slides %s crashed: they're classic", _numbers(batch))
            return set()
        if len(batch) == 1 and not talk.has_plan(batch[0]) and loose and not dropped.is_set():
            talk.take(talk.planned[batch[0]].key, loose)
        return {slide_nr for slide_nr in batch if talk.has_plan(slide_nr)}

    @staticmethod
    def _facts_for(
        talk: "_PlannedTalk", gathering: facts.Gathering | None, rng: random_util.Rng
    ) -> dict[int, facts.Given]:
        """The real facts that the talk's planned slides get (see talkgenerator.facts), by slide number (from 1), once
        they're in: for the slides that build on one, in order. Each goes in its slide's context too (for its credit),
        and all of them in the talk (for the deck)."""
        if gathering is None:
            return {}
        uses = [
            (slide.number, use)
            for slide_nr, slide in sorted(talk.planned.items())
            if (use := _fact_use(talk.picks[slide_nr], slide.recipe)) is not None
        ]
        if not uses:
            return {}
        try:
            given = facts.assign(gathering.result(), uses, rng.child("facts"))
        except Exception:  # (the talk goes without them)
            logger.exception("Giving the talk's slides their real facts crashed: the talk goes without them")
            return {}
        for number, fact in given.items():
            talk.contexts[number - 1]["fact"] = fact.fact
            if fact.also is not None:  # (a coincidence's other real thing: D73)
                talk.contexts[number - 1]["also_fact"] = fact.also
        talk.facts = tuple(each for fact in given.values() for each in fact.facts)
        if given:
            logger.info("Real facts for slides %s", ", ".join(str(number) for number in given))
        return given

    @staticmethod
    def _ask(llm: TextProvider, request: Any, talk: "_PlannedTalk") -> None:
        """Ask the language model for the talk, and hand its answer to the talk while it comes in."""
        reader = ObjectReader()
        read_anything = False

        def read(text: str) -> None:
            nonlocal read_anything
            if talk.cancelled.is_set():
                raise TalkCancelled()  # (out of the provider's stream, which then stops)
            read_anything = True
            talk.heard()
            for key, value in reader.feed(text):
                talk.take(key, value)
                if talk.in_english:
                    raise _InEnglish()  # (out of the provider's stream, which then stops: the model is asked again)
            talk.reading(*reader.reading)

        try:
            response = llm.stream(request, read)
            if not read_anything:
                read(response.text)
            if response.finish == "refused":
                # What a model wrote before it declined isn't to be used
                logger.warning("The language model declined to write the talk: it's classic")
                talk.drop()
            elif response.finish != "complete":
                logger.warning(
                    "The language model's answer was %s: slides it didn't write are classic", response.finish
                )
            elif not talk.plans and talk.spine.get("unsafe_topic") is not True:
                # (Claude Haiku's answer to one talk of 2026-11-08 brought its title and no slide that could be read,
                # and the talk came out classic without a word of why: this says what came in instead)
                logger.warning(
                    "The language model's answer had no slide that could be read, so the talk is classic (from %s, "
                    "its answer brought %s)",
                    response.model or llm.id,
                    talk.answer_shape(),
                )
        except (TalkCancelled, _InEnglish):
            return
        except ProviderError as error:
            logger.warning("The language model didn't write the talk (%s): its slides are classic", error)
        except Exception:  # a misbehaving provider shouldn't sink the talk either
            logger.exception("Asking the language model for the talk crashed: its slides are classic")

    def _pick_generators(
        self, num_slides: int, rng: random_util.Rng, language: str = "en", persona: Persona | None = None
    ) -> list[SlideGeneratorData | None]:
        """Every slide's generator, before there's any content: by weight for the slide's position (as the persona
        weighs it), among the ones the tags of the slides before it still allow (as generating the slides one by one
        picks them). A talk in another language than English gets none whose recipes find English texts (such as real
        quotes)."""
        english_only = {
            generator for generator in self._slide_generators if generator.llm is not None and generator.llm.texts_from
        }
        used_tags: dict[str, int] = {}
        picks: list[SlideGeneratorData | None] = []
        for slide_nr in range(num_slides):
            prohibited = set(self._calculate_prohibited_generators(used_tags, num_slides))
            if language != "en":
                prohibited |= english_only
            with random_util.use(rng.child("slide", slide_nr, "plan")):
                try:
                    generator = self._select_generator(slide_nr, num_slides, prohibited, persona)
                except ValueError:
                    generator = None
            picks.append(generator)
            if generator is not None:
                add_tags(used_tags, generator.get_tags())
        return picks

    def _settle_planned_talk(
        self,
        slide_deck: SlideDeck,
        talk: "_PlannedTalk",
        contexts: list[dict],
        rng: random_util.Rng,
        presenter: str | None,
        persona: Persona | None = None,
        seconds: float | None = None,
        pictures: "_SparePictures | None" = None,
        early: "_Early | None" = None,
    ) -> _LateSlides:
        """Settle the slides in order: the title slide from the plan's title, a planned slide in up to ATTEMPTS
        tries (each must not repeat what the slides before it used), and a classic slide wherever that fails (picked as
        the persona weighs them). In a talk in another language than English, where classic slides would be English,
        that's a picture of what the slide was about, without text (or no slide, without pictures in the schema).

        With seconds, a time limit per slide (see _Clock), a slide that runs out of time settles at once instead: as
        planned, without looking anything up (see _in_time: its pictures from pictures, spare ones of the talk's
        topic), or else as a stand-in (see _stand_in: its early version, if it has one). What it waited for goes on by
        itself, and once it's done, the real slide takes the place of what stood in for it (see _LateSlides: the ones
        that aren't done once the slides are all in come back, to be waited for); with nothing to stand in, it's waited
        for after all. A slide that can't be made at all is left out, unless it has an early version (see _Early)."""
        num_slides = len(contexts)
        state = _DeckState()
        lates = _LateSlides(slide_deck, state)
        for slide_nr in range(num_slides):
            pick = talk.picks[slide_nr]
            worked_out: _WorkedOutSlide | None = None
            late: _Outcome | None = None  # (the work it ran out of time waiting for, which goes on by itself)
            as_worked_out: Callable[[Any], _WorkedOutSlide | None] = _worked_out
            if slide_nr in talk.planned:
                talk.wait_for(slide_nr)
            clock = _Clock(seconds if slide_nr > 0 else None)  # (from now: the slide before it is in, its text too)

            def stand_in(slide_nr: int = slide_nr) -> _WorkedOutSlide | None:
                context = contexts[slide_nr]
                language = talk.language
                return self._stand_in(slide_nr, num_slides, context, rng, state, persona, language, pictures, early)

            if pick is not None and pick.llm is not None and pick.llm.kind == "title":
                worked_out = self._planned_title_slide(slide_nr, pick, talk, contexts[slide_nr]["title"], presenter)
            elif pick is not None and slide_nr in talk.plans:
                worked_out, out_of_time = self._planned_attempts(talk, slide_nr, pick, state, clock)
                if out_of_time:
                    in_time = self._in_time(slide_nr, pick, talk, state, pictures, clock)
                    worked_out = in_time or stand_in()
                    if worked_out is None:  # (nothing to stand in: it's waited for after all)
                        worked_out, _ = self._planned_attempts(talk, slide_nr, pick, state, _Clock(None))
                    else:
                        late = talk.late_work.pop(slide_nr, None)
                        # (a slide that tries a picture first stands in as its text version: only its picture takes
                        # its place, D73)
                        text_version = in_time is not None and talk.planned[slide_nr].recipe.picture_first
                        late_slide = _planned_picture if text_version else _planned_worked_out
                        as_worked_out = functools.partial(late_slide, slide_nr, pick)
            # (the work below gets a copy of what the slides before it used: with a time limit, it may go on by itself
            # while the talk settles more)
            if worked_out is None and talk.language != "en":
                plan = talk.plans.get(slide_nr)
                concept = (plan.concept.strip() if plan else "") or contexts[slide_nr]["seed"]
                picture = functools.partial(
                    self._picture_slide,
                    slide_nr,
                    concept,
                    contexts[slide_nr],
                    rng.child("slide", slide_nr, "picture"),
                    state.copy(),
                )
                worked_out, late = self._bounded(clock, picture, stand_in)
            elif worked_out is None:
                classic_slide = functools.partial(
                    self._work_out_slide,
                    slide_nr,
                    num_slides,
                    contexts[slide_nr],
                    rng.child("slide", slide_nr),
                    state.copy(),
                    {},
                    generate=True,
                    persona=persona,
                )
                classic, late = self._bounded(clock, classic_slide, stand_in)
                worked_out = _worked_out(classic)
            if worked_out is None:
                worked_out = self._instead_of_none(slide_nr, early, state, num_slides)
            if worked_out is None:
                logger.error("Gave up on generating slide %s", slide_nr + 1)
            else:
                _add_slide(slide_deck, slide_nr, worked_out.slide)
                self._update_used_elements(
                    state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
                )
                lates.settle(worked_out, late, as_worked_out)
            self._replace_late(lates)  # (the slides that ran out of time before, come after all by now)
        return lates

    @staticmethod
    def _planned_title_slide(
        slide_nr: int, generator: SlideGeneratorData, talk: "_PlannedTalk", title: str, presenter: str | None
    ) -> _WorkedOutSlide:
        job = clean_text(talk.spine.get("presenter_job"), PRESENTER_JOB, talk.language)
        thesis = talk.spine.get("thesis")
        slide, texts = _title_slide(title, presenter, job, thesis, talk.rngs[slide_nr], talk.language)
        return _WorkedOutSlide(slide_nr, generator, slide, texts)

    def _planned_attempts(
        self, talk: "_PlannedTalk", slide_nr: int, pick: SlideGeneratorData, state: _DeckState, clock: _Clock
    ) -> tuple[_WorkedOutSlide | None, bool]:
        """The planned slide, in up to ATTEMPTS tries (each must not repeat what the slides before it used), and
        whether it ran out of time first (see _Clock): then there's none."""
        for attempt in range(ATTEMPTS):
            if attempt > 0 and clock.over:  # (no time for another try)
                return None, True
            result, in_time = talk.attempt(slide_nr, attempt, clock.remaining())
            if not in_time:
                return None, True
            if result is not None and self._is_new_enough(result, pick, state):
                return _WorkedOutSlide(slide_nr, pick, *result), False
        logger.info("Planned slide %s didn't come out: it's classic", slide_nr + 1)
        return None, False

    def _in_time(
        self,
        slide_nr: int,
        pick: SlideGeneratorData,
        talk: "_PlannedTalk",
        state: _DeckState,
        pictures: "_SparePictures | None",
        clock: _Clock,
    ) -> _WorkedOutSlide | None:
        """A planned slide that ran out of time, made at once, as the model wrote it: without the pictures it can do
        without, and for the ones it can't, spare pictures of the talk's topic, found early (pictures), so that nothing
        is looked up (see realize). None if it needs a picture there's no spare one for, or it repeats what the slides
        before it used."""
        plan = talk.plans.get(slide_nr)
        if plan is None:
            return None
        used = [element for element in state.used_elements if isinstance(element, ImageData)]
        spare = pictures.lending(used) if pictures is not None else None

        def lent(source: Any, others: list[ImageData]) -> ImageData | None:
            return spare(source, others) if spare is not None else None

        recipe = talk.planned[slide_nr].recipe
        problems: list[str] = []
        try:
            context, stream = talk.contexts[slide_nr], talk.rngs[slide_nr]
            result = realize(plan, recipe, context, stream, 0, problems=problems, spare_pictures=lent)
        except Exception:  # (one misbehaving source shouldn't sink the talk: a stand-in, then)
            logger.exception("Realizing planned slide %s at once crashed", slide_nr + 1)
            result = None
        if result is None or not self._is_new_enough(result, pick, state):
            if spare is not None:
                spare.give_back()
            why = "; ".join(problems) or "it repeats what a slide before it used"
            logger.info("Slide %s ran out of time, and can't come as planned at once (%s)", slide_nr + 1, why)
            return None
        slide, generated = result
        spared = spare.taken if spare is not None else []
        logger.info(
            "Slide %s ran out of time (%g s): it comes as the model wrote it, without looking for its pictures%s",
            slide_nr + 1,
            clock.seconds,
            f" ({len(spared)} spare picture{'s' if len(spared) != 1 else ''} of the talk's topic)" if spared else "",
        )
        if recipe.picture_first:  # (D73)
            slide.add_note(f"Out of time ({clock.seconds:g} s): its text version, while its picture is looked for")
        else:
            slide.add_note(f"Out of time ({clock.seconds:g} s): as planned, without looking for its pictures")
        return _WorkedOutSlide(slide_nr, pick, slide, generated)

    def _stand_in(
        self,
        slide_nr: int,
        num_slides: int,
        context: dict,
        rng: random_util.Rng,
        state: _DeckState,
        persona: Persona | None,
        language: str,
        pictures: "_SparePictures | None" = None,
        early: "_Early | None" = None,
    ) -> _WorkedOutSlide | None:
        """What takes the place of a slide that ran out of time, made at once (see _Clock): its early version, if it
        has one (see _Early) that the deck allows; else a quick slide about its own seed (see _quick_version), without
        looking anything up, which in a talk in another language than English is a spare picture of the talk's topic
        (pictures). None if none comes out (on a seed the spare kinds won't make light of, say)."""
        made = self._early_version(slide_nr, early, state, num_slides)
        if made is not None:
            logger.info(
                "Slide %s ran out of time: its early version (%s) stands in for it", slide_nr + 1, made.generator
            )
        else:
            if language == "en" or pictures is not None:  # (in another language, only a spare picture is quick)
                made = self._quick_version(slide_nr, num_slides, context, rng, state, persona, language, pictures)
            if made is None:
                logger.info(
                    "Slide %s ran out of time, and nothing could stand in for it: it's waited for", slide_nr + 1
                )
                return None
            logger.info("Slide %s ran out of time: %s stands in for it", slide_nr + 1, made.generator)
        made.slide.add_note(f"Out of time: a stand-in for a slide about {context['seed']!r}")
        return made

    def _quick_version(
        self,
        slide_nr: int,
        num_slides: int,
        context: dict,
        rng: random_util.Rng,
        state: _DeckState,
        persona: Persona | None,
        language: str,
        pictures: "_SparePictures | None" = None,
        label: str | None = None,
    ) -> _WorkedOutSlide | None:
        """A quick slide about a slide's own seed, from that slide's "stand-in" stream: what stands in for it once it
        runs out of time (see _stand_in), or its early version, made ahead (see _Early). A slide of one of the spare
        generators' kinds, as the persona weighs them, among those the talk's tag caps still allow by state (another
        kind if one fails, SPARE_TRIES in all: mostly well under a second each), that doesn't repeat what state used;
        or in a talk in another language than English, whose classic slides would be English, a picture of the seed,
        without text: a spare one of the talk's topic, with pictures, else one that's looked for. None if none comes out
        (on a seed the spare kinds won't make light of, say). label says what it is, in the logs."""
        stream = rng.child("slide", slide_nr, "stand-in")
        if language != "en":
            return self._picture_slide(slide_nr, str(context["seed"]), context, stream, state, pictures)
        # (not one of a kind the talk's tag caps don't allow anymore: by their tags, as a format has its own copies)
        capped = {
            tag
            for tag, cap in self._max_allowed_tags.items()
            if state.used_tags.get(tag, 0) >= most_slides(cap, num_slides)
        }
        excluded = {generator for generator, _ in self.spare_generators if set(generator.get_tags()) & capped}
        for attempt in range(SPARE_TRIES):
            generator = self._pick_spare_generator(stream.child("pick", attempt), persona, excluded)
            if generator is None:
                break
            excluded.add(generator)
            what = label or f"a stand-in for slide {slide_nr + 1}"
            quick = {**context, slides.STANDING_IN: True}  # (looking nothing up, nor breaking a pattern: D73)
            result = self._run_generator(generator, slide_nr, quick, stream.child("content", attempt), state, what)
            if result is not None and self._is_new_enough(result, generator, state):
                return _WorkedOutSlide(slide_nr, generator, *result)
        return None

    def _early_version(
        self, slide_nr: int, early: "_Early | None", state: _DeckState, num_slides: int
    ) -> _WorkedOutSlide | None:
        """The slide's early version (see _Early), if it has one by now that doesn't repeat what the slides before it
        used (state), of a kind the talk's caps still allow: for a slide that ran out of time, or can't be made."""
        made = early.take(slide_nr) if early is not None else None
        if made is None:
            return None
        capped = self._capped_tag(made.generator, state.used_tags, num_slides)
        if capped is not None or not self._is_new_enough((made.slide, made.generated_elements), made.generator, state):
            why = f"the talk has its {capped} slides already" if capped else "it repeats a slide before it"
            logger.info("Slide %s's early version can't take its place: %s", slide_nr + 1, why)
            return None
        return made

    def _instead_of_none(
        self, slide_nr: int, early: "_Early | None", state: _DeckState, num_slides: int
    ) -> _WorkedOutSlide | None:
        """What takes the place of a slide that can't be made at all: its early version, if it has one the deck allows
        (see _early_version); else nothing, and the slide is left out."""
        made = self._early_version(slide_nr, early, state, num_slides)
        if made is not None:
            logger.info(
                "Slide %s couldn't be made: its early version (%s) takes its place", slide_nr + 1, made.generator
            )
            made.slide.add_note(f"Couldn't be made: its early version, {made.generator}")
        return made

    def _capped_tag(self, generator: SlideGeneratorData, used_tags: Mapping[str, int], num_slides: int) -> str | None:
        """A tag of the generator's whose cap the slides that used used_tags have reached (see most_slides), if any:
        another slide of its kind would go over it."""
        for tag in generator.get_tags():
            cap = self._max_allowed_tags.get(tag)
            if cap is not None and used_tags.get(tag, 0) >= most_slides(cap, num_slides):
                return str(tag)
        return None

    def _text_version(
        self,
        slide_nr: int,
        generator: SlideGeneratorData | None,
        context: dict,
        rng: random_util.Rng,
        state: _DeckState,
    ) -> _WorkedOutSlide | None:
        """What stands in for a classic chart or diagram that tries a picture first (see _picture_first) and ran out of
        time: its text version, at once (without pictures in its boxes, which it would look up), from the stream its work
        has, so it's the text that the work has too; None for another slide, or when that doesn't come out."""
        text = generator.text_version if generator is not None else None
        if generator is None or text is None or not pictures_first():
            return None
        stream = rng.child("content", self._generator_indices[id(generator)])
        label = f"slide {slide_nr + 1}'s text version"
        result = self._run_generator(text, slide_nr, {**context, slides.STANDING_IN: True}, stream, state, label)
        if result is None or not self._is_new_enough(result, generator, state):
            return None
        logger.info(
            "Slide %s ran out of time: its text version stands in for it, while its picture is looked for", slide_nr + 1
        )
        result[0].add_note("Out of time: its text version, while its picture is looked for")
        return _WorkedOutSlide(slide_nr, generator, *result)

    def _replace_late(
        self, lates: _LateSlides, wait: float | None = None, cancelled: threading.Event | None = None
    ) -> None:
        """The slides that ran out of time and came after all (see _LateSlides), each in place of what stood in for
        it: those whose work is done now, or with wait (seconds), each as it comes, for that long at most.
        TalkCancelled, once the talk is cancelled meanwhile."""
        until = time.monotonic() + wait if wait is not None else None
        while lates.pending:
            for late in lates.done():
                self._take_late(lates, late)
            if until is None or not lates.pending or time.monotonic() >= until:
                break
            if cancelled is not None and cancelled.is_set():
                raise TalkCancelled()
            first = next(iter(lates.pending.values()))
            first.work.wait(min(0.25, max(0.0, until - time.monotonic())))
        if until is not None and lates.pending:
            numbers = ", ".join(str(slide_nr + 1) for slide_nr in sorted(lates.pending))
            logger.info(
                "Slides that ran out of time and didn't come after all within %g s (%s): what stood in for them stays",
                wait,
                numbers,
            )

    def _take_late(self, lates: _LateSlides, late: _LateSlide) -> None:
        """A slide that ran out of time, come after all: in place of what stood in for it, unless it repeats another
        slide of the deck (more than its generator allows, or a picture), or the deck has as many slides of its kind as
        the talk's caps allow without it."""
        seconds = time.monotonic() - late.since
        try:
            real = late.as_worked_out(late.work.get(0))
        except Exception:  # (one misbehaving source shouldn't sink the talk: what stood in for it stays)
            logger.exception("Slide %s, come after all, crashed: what stood in for it stays", late.slide_nr + 1)
            return
        if real is None:
            logger.info("Slide %s didn't come out after all: what stood in for it stays", late.slide_nr + 1)
            return
        standing = lates.settled.get(late.slide_nr)
        if (
            standing is not None
            and real.generator.text_version is not None
            and not isinstance(real.slide, slides.FullImageSlide)
            and real.slide.to_deck_slide().elements == standing.slide.to_deck_slide().elements
        ):  # (a chart or a diagram that tried a picture first, come as the text version that stands in for it: D73)
            logger.info("Slide %s came after all, without its picture: its text version stays", late.slide_nr + 1)
            return
        others = _DeckState()
        for slide_nr, worked_out in lates.settled.items():
            if slide_nr != late.slide_nr:
                self._update_used_elements(
                    others.used_elements, others.used_tags, worked_out.generated_elements, worked_out.generator
                )
        capped = self._capped_tag(real.generator, others.used_tags, lates.slide_deck.size)
        if capped is not None or not self._is_new_enough((real.slide, real.generated_elements), real.generator, others):
            why = f"the talk has its {capped} slides already" if capped else "it repeats another slide"
            logger.info(
                "Slide %s came after all, %.1f s after its time ran out, but %s: what stood in for it stays",
                late.slide_nr + 1,
                seconds,
                why,
            )
            return
        real.slide.add_note(f"Came after all, {seconds:.1f} s after its time ran out, in place of what stood in for it")
        lates.settled[late.slide_nr] = real
        lates.state.used_elements.clear()  # (what the slides in the deck use now)
        lates.state.used_tags.clear()
        for worked_out in lates.settled.values():
            self._update_used_elements(
                lates.state.used_elements, lates.state.used_tags, worked_out.generated_elements, worked_out.generator
            )
        lates.replace(lates.slide_deck, late.slide_nr, real.slide)
        logger.info(
            "Slide %s came after all, %.1f s after its time ran out: it takes the place of what stood in for it",
            late.slide_nr + 1,
            seconds,
        )

    def _pick_spare_generator(
        self, rng: random_util.Rng, persona: Persona | None, excluded: Collection[SlideGeneratorData] = ()
    ) -> SlideGeneratorData | None:
        """One of the spare generators (but the excluded), picked with the random stream by their weights times the
        persona's (see spare_generators); None when there's none left."""
        weighted = [
            (weight * (persona.weight(generator.get_tags()) if persona is not None else 1), generator)
            for generator, weight in self.spare_generators
            if generator not in excluded
        ]
        with random_util.use(rng):
            picked: SlideGeneratorData | None = random_util.weighted_random(weighted) if weighted else None
        return picked

    @staticmethod
    def _bounded(clock: _Clock, work: Callable[[], Any], stand_in: Callable[[], Any]) -> tuple[Any, _Running | None]:
        """What the work makes, if it does so within the slide's time (see _Clock); else what stand_in makes at once,
        with the work, which goes on by itself (for what it makes to come after all: see _LateSlides); or with nothing
        to stand in, the work's after all. Without a time limit, the work's, however long it takes. The work should
        work on copies of what the talk changes meanwhile (its _DeckState): see _Running."""
        remaining = clock.remaining()
        if remaining is None:
            return work(), None
        running = _Running(work)  # (also when it's out of time already: for the slide to come after all)
        if running.wait(remaining):
            return running.result(), None
        made = stand_in()
        if made is not None:
            return made, running
        running.wait(None)
        return running.result(), None

    def _picture_slide(
        self,
        slide_nr: int,
        concept: str,
        context: dict,
        rng: random_util.Rng,
        state: _DeckState,
        pictures: "_SparePictures | None" = None,
    ) -> _WorkedOutSlide | None:
        """A picture of the concept, filling the slide, without text: what a slide of a talk in another language
        than English becomes when it doesn't come out as planned. None if this schema has no such pictures, or none
        is found. With pictures, a spare picture of the talk's topic instead, found early (for a slide out of time:
        nothing is looked up)."""
        candidates = [
            generator
            for generator in self._slide_generators
            if generator.llm is not None and generator.llm.kind == "full_image" and not generator.llm.texts_from
        ]
        neutral = [generator for generator in candidates if "neutral" in generator.get_tags()]
        if not candidates:
            return None
        generator = (neutral or candidates)[0]
        recipe = generator.llm
        assert recipe is not None
        picture = SlidePlan(kind="full_image", recipe=generator.name, concept=concept, images={"image": concept})
        if pictures is not None:
            lending = pictures.lending([element for element in state.used_elements if isinstance(element, ImageData)])
            spare = realize(picture, recipe, context, rng, 0, spare_pictures=lending)
            if spare is not None and self._is_new_enough(spare, generator, state):
                return _WorkedOutSlide(slide_nr, generator, *spare)
            lending.give_back()
            return None
        for attempt in range(ATTEMPTS):
            result = realize(picture, recipe, context, rng, attempt)
            if result is not None and self._is_new_enough(result, generator, state):
                return _WorkedOutSlide(slide_nr, generator, *result)
        return None

    # TALKS PLANNED OUTSIDE TALKGENERATOR (BY AN AGENT, SAY)

    def realize_plan(
        self,
        plan: TalkPlan,
        recipes: Sequence[tuple[SlideGeneratorData, Recipe] | None],
        presenter: str | None,
        rng: random_util.Rng,
        local_images: Path | None = None,
        parallel: bool | int = True,
    ) -> tuple[SlideDeck, list["PlanOutcome"]]:
        """A plan written outside talkgenerator (see talkgenerator.plan.external) as a deck: the title slide from the
        plan's title, then every planned slide as planned (in up to ATTEMPTS tries, each of which must not repeat what
        the slides before it used), or else made by its recipe's classic generator, or else left out. In a plan in
        another language than English, where classic slides would be English, a slide that doesn't come out becomes a
        picture of its concept, without text, instead.

        recipes holds every planned slide's slide generator and recipe, or None for a slide that can't be made (a
        kind this schema has no slides of). Like the other talks, the same seed gives the same deck, in parallel or
        not, as long as the sources give the same answers."""
        num_slides = 1 + len(plan.slides)
        title = clean_text(plan.title, TALK_TITLE, plan.language) or plan.topic
        slide_deck = SlideDeck(
            num_slides,
            title=title,
            topics=[plan.topic],
            presenter=presenter,
            seed=rng.root_seed,
            language=plan.language,
        )
        state = _DeckState()
        job = clean_text(plan.presenter_job, PRESENTER_JOB, plan.language)
        title_slide, title_texts = _title_slide(
            title, presenter, job, plan.thesis, rng.child("slide", 0, "planned"), plan.language
        )
        slide_deck.add_slide(0, title_slide)
        _add_used(state, title_texts)

        contexts = [
            {
                "topic": plan.topic,
                "topics": [plan.topic],
                "seed": planned.concept.strip() or plan.topic,
                "presenter": presenter,
                "title": plan.title,
                "language": plan.language,
            }
            for planned in plan.slides
        ]

        def attempt(index: int, attempt_nr: int) -> tuple[_Result, list[str]]:
            entry = recipes[index]
            assert entry is not None
            problems: list[str] = []
            rng_of_slide = rng.child("slide", index + 1, "planned")
            try:
                result = realize(
                    plan.slides[index],
                    entry[1],
                    contexts[index],
                    rng_of_slide,
                    attempt_nr,
                    problems=problems,
                    local_images=local_images,
                )
            except Exception as error:  # one misbehaving source shouldn't sink the talk
                logger.exception("Realizing slide %s of the plan crashed", index + 2)
                problems.append(f"realizing it crashed: {error!r}")
                result = None
            return result, problems

        # Every slide's first try at once: searching images takes most of the time
        makeable = [index for index, entry in enumerate(recipes) if entry is not None]
        first_tries: dict[int, tuple[_Result, list[str]]] = {}
        at_once = slides_at_once(parallel, len(makeable), most=8)
        if at_once > 1:
            with ThreadPool(processes=at_once) as pool:
                first_try = image_util.carry(lambda index: attempt(index, 0))
                first_tries = dict(zip(makeable, pool.map(first_try, makeable), strict=True))

        outcomes = []
        for index, planned in enumerate(plan.slides):
            outcome = PlanOutcome(number=index + 2)
            outcomes.append(outcome)
            entry = recipes[index]
            if entry is None:
                outcome.outcome = "left out"
                outcome.problems.append(f"this format has no {planned.kind!r} slides")
                continue
            generator, recipe = entry
            worked_out: tuple[Any, list] | None = None
            for attempt_nr in range(ATTEMPTS):
                result, problems = first_tries.pop(index) if index in first_tries else attempt(index, attempt_nr)
                outcome.problems += [problem for problem in problems if problem not in outcome.problems]
                if result is not None and self._is_new_enough(result, generator, state):
                    worked_out = result
                    break
                if result is not None:
                    outcome.problems.append("it repeats an image or a text of a slide before it")
            if worked_out is None and plan.language != "en":
                concept = planned.concept.strip() or plan.topic
                picture = self._picture_slide(
                    index + 1, concept, contexts[index], rng.child("slide", index + 1, "picture"), state
                )
                if picture is None:
                    outcome.outcome = "left out"
                    continue
                worked_out = (picture.slide, picture.generated_elements)
                outcome.outcome = "picture"
            elif worked_out is None:
                classic = self._run_generator(
                    generator, index + 1, contexts[index], rng.child("slide", index + 1, "classic"), state
                )
                if classic is not None and self._is_new_enough(classic, generator, state):
                    worked_out = classic
                    outcome.outcome = "classic"
                else:
                    outcome.outcome = "left out"
                    continue
            _add_slide(slide_deck, index + 1, worked_out[0])
            _add_used(state, worked_out[1])
        # Its closer after its last slide, as every talk has one (D76), as the title slide before its first
        slide_deck.close(self._closer(slide_deck, plan.topic))
        _finish_picking(slide_deck)
        _finish_generating(slide_deck)
        return slide_deck, outcomes

    # TALKS THE CLASSIC GENERATOR MAKES

    def _generate_slides(
        self,
        slide_deck: SlideDeck,
        contexts: list[dict],
        rng: random_util.Rng,
        parallel: bool | int,
        persona: Persona | None = None,
        seconds: float | None = None,
        early: "_Early | None" = None,
    ) -> _LateSlides:
        """Work out every slide and add it to the deck, picking their generators as the persona weighs them (see the
        module's docstring for how parallel works: a round works out the remaining slides, as many at once as
        slides_at_once says).

        With seconds, a time limit per slide (see _Clock), a slide that runs out of time settles at once as a stand-in
        (see _stand_in: its early version, if it has one), while its work goes on by itself: once it's done, the real
        slide takes the stand-in's place (see _LateSlides: the ones that aren't done once the slides are all in come
        back, to be waited for); with nothing to stand in, it's waited for after all. A round then doesn't wait for the
        work under way when it ends either: the next one goes on from what that found so far. A talk none of whose
        slides runs out of time comes out as it does without one. A slide that can't be made at all is left out, unless
        it has an early version (see _Early)."""
        num_slides = len(contexts)
        slide_rngs = [rng.child("slide", slide_nr) for slide_nr in range(num_slides)]
        results: list[_Results] = [{} for _ in range(num_slides)]
        state = _DeckState()
        lates = _LateSlides(slide_deck, state, SlideDeck.replace_slide)  # (a classic slide wishes for no pictures)
        clocks: dict[int, _Clock] = {}  # (each slide's, from when it could settle: in the round it does, or before)
        picked: dict[int, SlideGeneratorData] = {}  # (the generator each slide's work runs, last: for its text version)

        def work_out(slide_nr: int, at_state: _DeckState, generate: bool) -> _WorkedOutSlide | _NeedsWork | None:
            return self._work_out_slide(
                slide_nr,
                num_slides,
                contexts[slide_nr],
                slide_rngs[slide_nr],
                at_state,
                results[slide_nr],
                generate,
                persona=persona,
                picked=picked,
            )

        def stand_in(slide_nr: int) -> _WorkedOutSlide | None:
            # (a chart or a diagram that tries a picture first stands in as its text version, while its picture is
            # looked for, as a planned slide stands in as it's planned: D73; else its early version, or a quick slide)
            context, stream = contexts[slide_nr], slide_rngs[slide_nr]
            text = self._text_version(slide_nr, picked.get(slide_nr), context, stream, state)
            return text or self._stand_in(slide_nr, num_slides, context, rng, state, persona, "en", early=early)

        slide_nr = 0
        while slide_nr < num_slides:
            at_once = slides_at_once(parallel, num_slides - slide_nr)
            in_parallel = at_once > 1
            pool: ThreadPool | None = None
            # (each remaining slide's work in this round, once it's done: delivered by the pool's thread itself, also
            # after the round, when the pool is terminated, for a slide that ran out of time to come after all)
            working: dict[int, _Outcome] = {}
            started = _Started()  # (the slides whose work has started, in the round's pool or apart from it)
            if in_parallel:
                remaining = list(range(slide_nr, num_slides))
                logger.info("Generating slides %s in parallel, %s at once", [nr + 1 for nr in remaining], at_once)
                pool = ThreadPool(processes=at_once)
                work = image_util.carry(functools.partial(work_out, at_state=state.copy(), generate=True))
                working = {nr: _Outcome() for nr in remaining}
                deliver = started.then(functools.partial(_deliver, working, work))
                for nr in remaining:  # (started in order)
                    pool.apply_async(deliver, (nr,))
            try:
                # Settle the slides in order, as generating them one by one would: each once its work is done
                while slide_nr < num_slides:
                    clock = clocks.setdefault(slide_nr, _Clock(seconds if slide_nr > 0 else None))
                    # (with a time limit, a slide whose work hasn't started yet when it's due, as the round's threads
                    # are busy, starts it now, apart from them: its time is for its own work, not for theirs)
                    apart = clock.seconds is not None and started.claim(slide_nr)
                    late: _Outcome | None  # (the work it ran out of time waiting for, which goes on by itself)
                    if in_parallel and not apart:
                        settle = functools.partial(work_out, slide_nr, state, False)
                        worked_out, late = self._settle_worked(slide_nr, working[slide_nr], clock, settle, stand_in)
                    else:
                        one_by_one = functools.partial(work_out, slide_nr, state.copy(), True)
                        worked_out, late = self._bounded(clock, one_by_one, functools.partial(stand_in, slide_nr))
                    if isinstance(worked_out, _NeedsWork):
                        break  # the next round works out the remaining slides again, knowing the ones settled so far
                    if worked_out is None:
                        worked_out = self._instead_of_none(slide_nr, early, state, num_slides)
                    if worked_out is None:
                        logger.error("Gave up on generating slide %s", slide_nr + 1)
                    else:
                        slide_deck.add_slide(slide_nr, worked_out.slide)
                        self._update_used_elements(
                            state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
                        )
                        lates.settle(worked_out, late)
                    slide_nr += 1
                    self._replace_late(lates)  # (the slides that ran out of time before, come after all by now)
            except BaseException:
                if pool is not None:
                    # (the slides it hasn't started on are dropped, and its threads finish the others by themselves:
                    # nothing waits for what they find)
                    pool.terminate()
                raise
            if pool is not None:
                # The slides this round hasn't started on are dropped (the next round works them out, knowing more)
                pool.terminate()
                if seconds is None:
                    pool.join()  # (and the ones it's working out are waited for: the next round reuses what they found)
                else:
                    # (with a time limit, nothing waits for them: the next round goes on from what they found so far,
                    # and they go on by themselves, where it doesn't look)
                    for nr, under_way in working.items():
                        if not under_way.ready():
                            results[nr] = dict(results[nr])
        return lates

    @staticmethod
    def _settle_worked(
        slide_nr: int,
        under_way: _Outcome,
        clock: _Clock,
        settle: Callable[[], _WorkedOutSlide | _NeedsWork | None],
        stand_in: Callable[[int], _WorkedOutSlide | None],
    ) -> tuple[_WorkedOutSlide | _NeedsWork | None, _Outcome | None]:
        """A slide of a round worked out in parallel (see _generate_slides), settled (settle) once its work (under_way)
        is done; or once it runs out of time (see _Clock), as a stand-in (stand_in), with its work, which goes on by
        itself (for the slide to come after all: see _LateSlides); with nothing to stand in, once its work is done
        after all."""
        under_way.wait(clock.remaining())
        if not under_way.ready():
            made = stand_in(slide_nr)
            if made is not None:
                return made, under_way
            under_way.wait()
        under_way.get()  # (an error that stopped its work comes out here)
        return settle(), None

    def _work_out_slide(
        self,
        slide_nr: int,
        num_slides: int,
        presentation_context: dict,
        rng: random_util.Rng,
        state: _DeckState,
        results: _Results,
        generate: bool,
        extra_prohibited: Collection[SlideGeneratorData] = (),
        persona: Persona | None = None,
        picked: dict[int, SlideGeneratorData] | None = None,
    ) -> _WorkedOutSlide | _NeedsWork | None:
        """Work out a slide the way generating the slides one by one does: pick a slide generator (with the slide's
        stream for that pick, as the persona weighs them) among the ones the used tags still allow, run it (with its
        own stream for this slide), and pick another one when it fails. With picked, the generator it runs goes in it,
        by the slide's number (for its text version to stand in for it, should it run out of time: see
        _text_version).

        results holds what the generators produced for this slide before, given fewer used elements, and gets what
        they produce now. A failure stays a failure, and a slide still holds as long as it doesn't repeat what's used
        now. Without generate, a slide that needs a generator to run returns _NEEDS_WORK instead. Returns None when
        no slide generator is left to try."""
        prohibited = set(self._calculate_prohibited_generators(state.used_tags, num_slides)) | set(extra_prohibited)
        for pick in itertools.count():
            with random_util.use(rng.child("pick", pick)):
                try:
                    generator = self._select_generator(slide_nr, num_slides, prohibited, persona)
                except ValueError as e:
                    logger.error(
                        "Could not generate slide %s about '%s': %s", slide_nr + 1, presentation_context["seed"], e
                    )
                    return None
            if generator is None:
                logger.warning(
                    "No generator found to generate slide %s about '%s'", slide_nr + 1, presentation_context["seed"]
                )
                return None

            index = self._generator_indices[id(generator)]
            known = index in results
            result = results.get(index)
            if known and result is not None and not self._is_new_enough(result, generator, state):
                known = False  # generating it now, its first tries would be rejected too, and it would carry on
            if not known:
                if not generate:
                    return _NEEDS_WORK
                if picked is not None:
                    picked[slide_nr] = generator
                result = self._run_generator(
                    generator, slide_nr, presentation_context, rng.child("content", index), state
                )
                results[index] = result

            if result is None:
                prohibited.add(generator)
                continue
            slide, generated_elements = result
            return _WorkedOutSlide(slide_nr, generator, slide, generated_elements)
        raise AssertionError("unreachable")

    @staticmethod
    def _is_new_enough(result: tuple[Any, list], generator: SlideGeneratorData, state: _DeckState) -> bool:
        """Whether a slide repeats no more of the slides before it than its generator allows, and none of their
        images: conclusions may repeat texts (as they sum up), but a picture twice is a picture too few (nearly the same
        picture too, such as one photo found at two sources). It's the rule slide generators keep to themselves (see
        slide_generator_types.is_different_enough_for_allowed_repeated): what one generated, it accepts."""
        return slide_generator_types.is_different_enough_for_allowed_repeated(
            result[1], state.used_elements, generator.get_allowed_repeated_elements()
        )

    @staticmethod
    def _run_generator(
        generator: SlideGeneratorData,
        slide_nr: int,
        presentation_context: dict,
        rng: random_util.Rng,
        state: _DeckState,
        label: str | None = None,
    ) -> _Result:
        """Run the slide generator for a slide (or what label says it's for, in the logs: "spare 1", say)."""
        seed = presentation_context["seed"]
        what = label or "slide {}".format(slide_nr + 1)
        logger.info("* Generating {} about {} using {} *".format(what, seed, generator))
        start_time = time.time()
        with random_util.use(rng):
            try:
                # A copy of the context: some generators write their findings into it
                result = generator.generate(dict(presentation_context), state.used_elements)
            except Exception:
                # One misbehaving source (an API that changed, a scraper that broke...) shouldn't sink the talk
                logger.exception("Slide generator %s crashed; trying another one", generator)
                result = None
        seconds = round(time.time() - start_time, 2)
        if result:
            logger.info(
                "* Finished generating {} about {} using {} in {} seconds *".format(what, seed, generator, seconds)
            )
            return result
        logger.info("Failed to generate after {} seconds using: {}".format(seconds, generator))
        return None

    @classmethod
    def _update_used_elements(cls, used_elements, used_tags, generated_elements, slide_generator_data):
        # Add generated items to used_elements list
        generated_elements = set(generated_elements)
        _filter_generated_elements(generated_elements)
        used_elements.update(generated_elements)

        # Add generator tags to used_tags list
        add_tags(used_tags, slide_generator_data.get_tags())

    def generate_slide(
        self,
        presentation_context,
        slide_nr,
        num_slides,
        used_elements=None,
        prohibited_generators=None,
        int_seed=None,
    ):
        """Generate one slide on its own, given the elements used so far, the way generating a talk does.
        Returns (slide, generated_elements, slide_generator, slide_nr), or None if no slide generator succeeded."""
        logger.debug("presentation_schema.generate_slide: {}".format(slide_nr))
        worked_out = self._work_out_slide(
            slide_nr,
            num_slides,
            presentation_context,
            random_util.Rng(int_seed).child("slide", slide_nr),
            _DeckState(set(used_elements or ())),
            {},
            generate=True,
            extra_prohibited=prohibited_generators or (),
        )
        if not isinstance(worked_out, _WorkedOutSlide):
            return None
        return worked_out.slide, worked_out.generated_elements, worked_out.generator, slide_nr

    def _select_generator(self, slide_nr, total_slides, prohibited_generators, persona: Persona | None = None):
        """Select a generator for a certain slide number (by weight, as the persona weighs them)"""
        if self._ignore_weights:
            return random_util.choice_optional(
                [generator for generator in self._slide_generators if generator not in prohibited_generators]
            )
        _selected_generator = random_util.weighted_random(
            self._get_weighted_generators_for_slide_nr(slide_nr, total_slides, prohibited_generators, persona)
        )
        logger.debug("_selected_generator: {}".format(_selected_generator))
        return _selected_generator

    def _get_weighted_generators_for_slide_nr(
        self, slide_nr, total_slides, prohibited_generators, persona: Persona | None = None
    ):
        """Every generator that's allowed, with its weight for the slide: its own, times the persona's multiplier for
        its tags (see talkgenerator.personas.Persona.weight)."""
        weighted_generators = []
        for i in range(len(self._slide_generators)):
            generator = self._slide_generators[i]
            if generator in prohibited_generators:
                continue
            weight = generator.get_weight_for(slide_nr, total_slides)
            if persona is not None:
                weight *= persona.weight(generator.get_tags())
            weighted_generators.append((weight, generator))

        if len(weighted_generators) == 0:
            raise ValueError("No generators left to generate slides with!")

        return weighted_generators

    def _calculate_prohibited_generators(self, used_tags: dict[str, int], num_slides: int):
        """The slide generators that the next slide can't have: those with a tag that the slides so far used as often
        as its cap allows (see most_slides), from the talk's first slide on, so that a cap of none holds too, and
        those whose images the talk's license policy allows no source for."""
        prohibited_tags = {
            tag for tag, cap in self._max_allowed_tags.items() if used_tags.get(tag, 0) >= most_slides(cap, num_slides)
        }
        prohibited_generators = set(self.unservable())
        for generator in self._slide_generators:
            if set(generator.get_tags()) & prohibited_tags:
                prohibited_generators.add(generator)

        return prohibited_generators

    def unservable(self) -> frozenset[SlideGeneratorData]:
        """The slide generators whose images the talk's license policy allows no source for (a meme slide in a talk
        without fair use, say), by the image slots of their recipes, which their classic slides use too (but the slots
        a slide can do without: a picture behind a big number)."""
        talk = image_context.current()
        policy = talk.policy
        # (a talk that generates pictures can serve the slots that prefer generated ones, whatever their sources)
        key = (policy.name, talk.generation is not None and talk.generation.active)
        known = self._unservable.get(key)
        if known is None:
            known = frozenset(
                generator
                for generator in self._slide_generators
                if generator.llm is not None
                and any(
                    isinstance(source, ImageSlot)
                    and slot not in KINDS[generator.llm.kind].optional_images
                    and not finder.servable(source, policy)
                    for slot, source in generator.llm.slots()
                )
            )
            self._unservable[key] = known
        return known


# Helper functions
def most_slides(cap: float, num_slides: int) -> float:
    """How many slides with a tag a talk of num_slides slides may have, by the tag's cap: an absolute cap is a number of
    slides (0: none at all, as the interview format's about-me slides), and a relative one (between 0 and 1) a share
    of the talk's slides, rounded down, but at least one, so that short talks keep every kind of slide (D50). (A kind
    of slide that only longer talks have says so by its weight, as the section divider does.)"""
    if 0 < cap < 1:
        return max(1, int(cap * num_slides))
    return cap


def create_slide_presentation_context(main_presentation_context, seed):
    presentation_context = dict(main_presentation_context)
    presentation_context["seed"] = seed
    return presentation_context


def add_tags(used_tags, tags):
    for tag in tags:
        if tag not in used_tags:
            used_tags[tag] = 1
        else:
            used_tags[tag] += 1
