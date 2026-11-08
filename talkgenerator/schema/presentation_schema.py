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
Progress hears of each.

A talk's persona (see talkgenerator.personas) weighs in on every pick of a slide generator, classic or planned: a
generator's weight for a slide is its own, times the persona's multiplier for its tags. The tag caps hold as before.
"""

import functools
import itertools
import logging
import threading
import time
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pptx.presentation import Presentation

from talkgenerator import names, titles
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData, _filter_generated_elements
from talkgenerator.images import context as image_context
from talkgenerator.images import finder, licenses, profiles
from talkgenerator.images.slots import ImageSlot
from talkgenerator.llm.base import ProviderError, TextProvider
from talkgenerator.llm.providers import NoneProvider
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.models.theme import Theme
from talkgenerator.personas import Persona
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import PRESENTER_JOB, TALK_TITLE, Recipe
from talkgenerator.plan.prompt import SPINE, PlannedSlide, slide_plan, talk_request
from talkgenerator.plan.realize import ATTEMPTS, clean_text, realize
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import image_util, random_util

if TYPE_CHECKING:
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


@dataclass
class PlanOutcome:
    """How a slide of a plan that was written outside talkgenerator came out (see PresentationSchema.realize_plan)."""

    number: int  # its place in the deck, counted from 1 (slide 1 is the title slide)
    # Or "classic" (its recipe's classic generator made it), "picture" (a picture of its concept without text, in
    # a talk in another language than English, which classic slides aren't in), or "left out"
    outcome: str = "as planned"
    problems: list[str] = field(default_factory=list)  # what went wrong on the way, even when a later try worked


def _title_slide(
    title: str,
    presenter: str | None,
    job: str | None,
    thesis: str | None,
    rng: random_util.Rng,
    language: str = "en",
) -> tuple[slides.Slide, list[str]]:
    """The title slide of a planned talk ("By <presenter>, <job>", in the talk's language), with its texts."""
    with random_util.use(rng.child("subtitle")):
        by = random_util.choice(languages.language(language).by)
    if job and presenter and job.casefold().startswith(presenter.casefold()):
        # (a free model wrote the presenter's name into their job: "By Dr. Chronos Vance, Dr. Chronos Vance, Founder")
        job = job[len(presenter) :].lstrip(" ,;:-–—") or None
    subtitle = ", ".join(part for part in (f"{by} {presenter}" if presenter else "", job or "") if part) or None
    slide = slides.TitleSlide(title, subtitle)
    slide.set_note(f"Planned: the title slide\nThesis: {thesis!r}")
    return slide, [text for text in (title, subtitle) if text]


def _add_used(state: _DeckState, generated_elements: list) -> None:
    elements = set(generated_elements)
    _filter_generated_elements(elements)
    state.used_elements.update(elements)


def _add_slide(slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None:
    """Add a settled slide to the deck, and in a talk that generates pictures, start generating the ones it wishes for
    (see talkgenerator.images.generation): each takes its stock photo's place once it's in, and updates the slide."""
    slide_deck.add_slide(slide_nr, slide)
    generation = image_context.current().generation
    if generation is not None and getattr(slide, "wishes", None):
        generation.settled(slide, functools.partial(slide_deck.slide_updated, slide_nr))


def _finish_generating(slide_deck: SlideDeck, cancelled: threading.Event | None = None) -> None:
    """Wait for the pictures being generated for the deck's slides (so it has them all), and then stop hearing of
    changes to its slides. TalkCancelled, if the talk is cancelled meanwhile."""
    generation = image_context.current().generation
    if generation is not None and not generation.finish(cancelled):
        raise TalkCancelled()
    slide_deck.update_listener = None


class TalkCancelled(Exception):
    """Whoever followed the talk stopped wanting it (see Progress): it's left unfinished."""


class Progress(Protocol):
    """Who follows a talk while it's made: told once its title and language are known (with the deck, still without
    slides), of every slide once it's settled, in order, and of a slide settled before that got a generated picture
    in its stock photo's place (see talkgenerator.images.generation), whenever that comes in. Raising TalkCancelled
    from started or settled stops the talk, and so does setting cancelled, also while the talk waits for the language
    model (whose answer then isn't read further)."""

    cancelled: threading.Event

    def started(self, slide_deck: SlideDeck) -> None: ...

    def settled(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None: ...

    def updated(self, slide_deck: SlideDeck, slide_nr: int, slide: Any) -> None: ...


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
    first_attempts: dict[int, Any] = field(default_factory=dict)
    pool: ThreadPool | None = None
    language: str = "en"
    answering: threading.Thread | None = None  # (the answer coming in, while the talk streams)
    cancelled: threading.Event = field(default_factory=threading.Event)  # (then the answer isn't read any further)

    def __post_init__(self) -> None:
        self._slide_numbers = {slide.key: slide_nr for slide_nr, slide in self.planned.items()}
        self._changed = threading.Condition()
        self._spine_in = False  # whether all of the spine came in
        self._reached = -1  # the last slide whose part of the answer came in
        self._finished = False

    @property
    def title(self) -> str | None:
        return clean_text(self.spine.get("title"), TALK_TITLE, self.language)

    @property
    def presenter_name(self) -> tuple[Any, Any]:
        """The presenter's name the model wrote, if it was asked for one, and what it plays on (both as written: see
        talkgenerator.names)."""
        return self.spine.get("presenter_name"), self.spine.get("name_plays_on")

    def take(self, key: str, value: Any) -> None:
        """A part of the model's answer: the spine (one object, or else one of its fields), or a slide (whose first
        attempt then starts, in parallel)."""
        with self._changed:
            slide_nr = self._slide_numbers.get(key)
            if key == SPINE:
                if isinstance(value, dict):
                    self.spine.update(value)
                    self._spine_in = True
            elif slide_nr is None:
                self.spine[key] = value
                self._spine_in = self._spine_in or self.spine_fields <= self.spine.keys()
            elif self.spine.get("unsafe_topic") is not True:  # it comes first: then no slide is looked for
                self._reached = max(self._reached, slide_nr)
                plan = slide_plan(self.planned[slide_nr], value)
                if plan is not None:
                    self.plans[slide_nr] = plan
                    if self.pool is not None:
                        realize_it = image_util.carry(self._realize)  # (checking images as the talk does)
                        self.first_attempts[slide_nr] = self.pool.apply_async(realize_it, (slide_nr, 0))
            self._changed.notify_all()

    def wait_for_spine(self) -> None:
        """Wait for the spine of the answer (its title, the presenter's job and name, its thesis), all of it, or the
        end of the answer: then a talk that streams gets the spine a talk made at once gets. It comes before the
        slides, also from models that write the answer in alphabetical order. A spine that finds the topic unsafe
        doesn't count, as the model is then asked again."""
        self._wait(lambda: (self._spine_in and self.spine.get("unsafe_topic") is not True) or self._finished)

    def wait_for_a_plan(self) -> bool:
        """Wait for the first slide the model wrote, or the end of the answer: whether it wrote any slide."""
        self._wait(lambda: bool(self.plans) or self._finished)
        return bool(self.plans)

    def wait_for(self, slide_nr: int) -> None:
        """Wait for the slide's part of the answer (or a later slide's, as when its part didn't parse, or the end)."""
        self._wait(lambda: slide_nr in self.plans or self._reached > slide_nr or self._finished)

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

    def attempt(self, slide_nr: int, attempt: int) -> tuple[Any, list] | None:
        with self._changed:
            first = self.first_attempts.get(slide_nr) if attempt == 0 else None
        if first is not None:
            result: tuple[Any, list] | None = first.get()
            return result
        return self._realize(slide_nr, attempt)

    def _realize(self, slide_nr: int, attempt: int) -> tuple[Any, list] | None:
        recipe = self.planned[slide_nr].recipe
        with self._changed:
            plan = self.plans.get(slide_nr)
        if plan is None:
            return None  # (dropped: by a model that declined halfway, say)
        try:
            return realize(plan, recipe, self.contexts[slide_nr], self.rngs[slide_nr], attempt)
        except Exception:  # one misbehaving source shouldn't sink the talk: the slide goes classic
            logger.exception("Realizing planned slide %s crashed", slide_nr + 1)
            return None

    def drop(self) -> None:
        """Forget what the model wrote."""
        with self._changed:
            self.plans.clear()
            self.first_attempts.clear()
            for written in ("title", "own_title", "presenter_name", "name_plays_on"):
                self.spine.pop(written, None)
            self._changed.notify_all()

    def restart(self) -> None:
        """Forget the answer, for the model to be asked again."""
        with self._changed:
            self.plans.clear()
            self.first_attempts.clear()
            self.spine.clear()
            self._spine_in = False
            self._reached = -1
            self._changed.notify_all()

    def close(self) -> None:
        """Wait for the rest of the answer and for the slides being realized, unless the talk was cancelled: then
        they finish by themselves (on daemon threads, which nothing waits for)."""
        if self.answering is not None and not self.cancelled.is_set():
            self.answering.join()
        self.answering = None
        if self.pool is not None:
            self.pool.close()
            if not self.cancelled.is_set():
                self.pool.join()
            self.pool = None


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
    ):
        """title_generator makes a classic talk's title, and title_candidates are more classic title generators (such
        as wikiHow's "How to ..." titles), whose titles, with the title generator's, a language model may pick for a
        talk on what was typed when it reads that as a topic (see talkgenerator.titles).

        format is what a talk format beyond the TED-like talks is besides its slides (see
        talkgenerator.schema.formats): its brief for the language model, what its titles and its presenter's job are
        like, how likely each persona is to present it, its talks' theme families and its arc. Without one, a talk is
        a TED-like talk, and its requests to a language model say nothing of a format."""
        self.format = format
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
        parallel: bool = False,
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
    ) -> tuple[Presentation | None, SlideDeck]:
        """Generate a presentation about a certain topic with a certain number of slides.

        With topic_or_title, what was typed for the talk, which could be its topic or its title: the topics come
        from it (see talkgenerator.titles.topics_from), and the language model that writes the talk tells which it is,
        in the same request, or else talkgenerator guesses (see talkgenerator.titles). The deck tells how it was read.

        The same seed (int_seed, or the talk's random generator rng) gives the same talk, in parallel or not, as long
        as the sources give the same answers. Without a seed, a random one is picked: the deck tells which.

        With a language model (llm), the model writes what goes on the slides, in the given language (see
        _plan_talk); the slides it doesn't write, or that come out missing something, are classic.

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
        # Create the topic-for-each-slide generator, and every slide's topic
        with random_util.use(rng.child("topics")):
            seed_generator = self._seed_generator(topics, num_slides)
        logger.info("Seed generator: {}".format(seed_generator))
        seeds = []
        for slide_nr in range(num_slides):
            with random_util.use(rng.child("slide", slide_nr, "topic")):
                seeds.append(seed_generator.get_seed(slide_nr))

        # The presenter's name, unless it's given: made up in a style the talk's dice pick, by the language model
        # that writes the talk (in the same request), or else by talkgenerator (see talkgenerator.names); in one of
        # the default styles, nudged by the persona, unless the talk says which styles it may have
        writes = llm is not None and self.writes_with(llm)
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
        if llm is not None and writes:
            cancelled = progress.cancelled if progress is not None else None
            name = naming.request if naming is not None else None
            typed = titling.request if titling is not None else None
            talk = self._plan_talk(
                topics, seeds, rng, llm, language, title, parallel, cancelled, name, typed, persona=persona
            )
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
            slide_deck.language_model = llm.id if planned and llm is not None else None
            slide_deck.topic_or_title = reading
            if persona is not None:  # (with the angle the language model was given, for a talk it writes)
                slide_deck.persona = persona.record(persona.angle(rng) if planned else None)
            logger.info("Slide deck: {}".format(slide_deck))
            if progress is not None:
                progress.started(slide_deck)
                slide_deck.listener = progress.settled
                slide_deck.update_listener = getattr(progress, "updated", None)

            # Create main presentation_context
            main_presentation_context = {
                "topic": topics[0],
                "topics": topics,
                "presenter": presenter,
                "title": title,
                "language": talk_language,
            }
            contexts = [create_slide_presentation_context(main_presentation_context, seed) for seed in seeds]
            if talk is not None and planned:
                self._settle_planned_talk(slide_deck, talk, contexts, rng, presenter, persona)
            else:
                self._generate_slides(slide_deck, contexts, rng, parallel, persona)
            slide_deck.listener = None
            _finish_generating(slide_deck, progress.cancelled if progress is not None else None)
        except BaseException:
            if talk is not None:
                talk.cancelled.set()  # (what's still coming in isn't wanted anymore)
            generation = image_context.current().generation
            if generation is not None:
                generation.close()  # (and no generated picture either)
            raise
        finally:
            if talk is not None:
                talk.close()

        if save_ppt:
            return self.render(slide_deck, debug_notes), slide_deck

        return None, slide_deck

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
        parallel: bool,
        cancelled: threading.Event | None = None,
        name: names.NameRequest | None = None,
        typed: titles.TitleRequest | None = None,
        persona: Persona | None = None,
    ) -> "_PlannedTalk":
        """Pick every slide's generator (as the persona weighs them), and ask the language model, in one request, what
        goes on the slides whose generators have recipes (and the presenter's name, with a name request, and for what
        was typed, whether it's the topic or the title, with a title request: see talkgenerator.titles), in the
        persona's voice. The model's answer is read while it's written, and in parallel, every slide's first attempt
        starts as soon as its part of the answer is in. For a talk that streams (that can be cancelled), the answer
        comes in on a thread of its own, and this returns at once, for the slides to be settled while it does."""
        num_slides = len(seeds)
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
                slide_nr + 1, pick.name or str(pick), recipe, seeds[slide_nr], digits=len(str(num_slides))
            )
        talk = _PlannedTalk(
            picks,
            planned,
            # What realizing a slide may know: its topic and language (not the title, which arrives with the answer)
            [{"topic": topics[0], "topics": topics, "seed": seed, "language": language} for seed in seeds],
            [rng.child("slide", slide_nr, "planned") for slide_nr in range(num_slides)],
            frozenset(prompt.spine(language, name, typed)),
            language=language,
            cancelled=cancelled or threading.Event(),
        )
        if not planned:
            talk.finish()
            return talk
        if parallel:
            talk.pool = ThreadPool(processes=min(8, len(planned)))

        def answer() -> None:
            try:
                generation = image_context.current().generation  # (its images' prompts, if it generates pictures)
                for asked_again in (False, True):
                    request = talk_request(
                        topics,
                        list(planned.values()),
                        rng,
                        language,
                        title,
                        asked_again,
                        name,
                        typed,
                        generation,
                        persona=persona,
                        talk_format=self.format,
                    )
                    self._ask(llm, request, talk)
                    if talk.cancelled.is_set() or talk.spine.get("unsafe_topic") is not True:
                        break
                    talk.restart()
                    if asked_again:
                        logger.warning("The language model wouldn't write about this topic: the talk is classic")
                    else:  # (some of the free models get the flag wrong: one turned down "penguins")
                        logger.info("The language model found the topic unsafe: asking once more")
                logger.info("The language model wrote %s of the %s slides", len(talk.plans), num_slides)
            finally:
                talk.finish()

        if cancelled is not None:
            talk.answering = threading.Thread(target=image_util.carry(answer), name="talk plan", daemon=True)
            talk.answering.start()
        else:
            answer()
        return talk

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
            for key, value in reader.feed(text):
                talk.take(key, value)

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
        except TalkCancelled:
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
    ) -> None:
        """Settle the slides in order: the title slide from the plan's title, a planned slide in up to ATTEMPTS
        tries (each must not repeat what the slides before it used), and a classic slide wherever that fails (picked as
        the persona weighs them). In a talk in another language than English, where classic slides would be English,
        that's a picture of what the slide was about, without text (or no slide, without pictures in the schema)."""
        num_slides = len(contexts)
        state = _DeckState()
        for slide_nr in range(num_slides):
            pick = talk.picks[slide_nr]
            worked_out: _WorkedOutSlide | None = None
            if slide_nr in talk.planned:
                talk.wait_for(slide_nr)
            if pick is not None and pick.llm is not None and pick.llm.kind == "title":
                worked_out = self._planned_title_slide(slide_nr, pick, talk, contexts[slide_nr]["title"], presenter)
            elif pick is not None and slide_nr in talk.plans:
                for attempt in range(ATTEMPTS):
                    result = talk.attempt(slide_nr, attempt)
                    if result is not None and self._is_new_enough(result, pick, state):
                        worked_out = _WorkedOutSlide(slide_nr, pick, *result)
                        break
                else:
                    logger.info("Planned slide %s didn't come out: it's classic", slide_nr + 1)
            if worked_out is None and talk.language != "en":
                plan = talk.plans.get(slide_nr)
                concept = (plan.concept.strip() if plan else "") or contexts[slide_nr]["seed"]
                worked_out = self._picture_slide(
                    slide_nr, concept, contexts[slide_nr], rng.child("slide", slide_nr, "picture"), state
                )
            elif worked_out is None:
                classic = self._work_out_slide(
                    slide_nr,
                    num_slides,
                    contexts[slide_nr],
                    rng.child("slide", slide_nr),
                    state,
                    {},
                    generate=True,
                    persona=persona,
                )
                worked_out = classic if isinstance(classic, _WorkedOutSlide) else None
            if worked_out is None:
                logger.error("Gave up on generating slide %s", slide_nr + 1)
                continue
            _add_slide(slide_deck, slide_nr, worked_out.slide)
            self._update_used_elements(
                state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
            )

    @staticmethod
    def _planned_title_slide(
        slide_nr: int, generator: SlideGeneratorData, talk: "_PlannedTalk", title: str, presenter: str | None
    ) -> _WorkedOutSlide:
        job = clean_text(talk.spine.get("presenter_job"), PRESENTER_JOB, talk.language)
        thesis = talk.spine.get("thesis")
        slide, texts = _title_slide(title, presenter, job, thesis, talk.rngs[slide_nr], talk.language)
        return _WorkedOutSlide(slide_nr, generator, slide, texts)

    def _picture_slide(
        self, slide_nr: int, concept: str, context: dict, rng: random_util.Rng, state: _DeckState
    ) -> _WorkedOutSlide | None:
        """A picture of the concept, filling the slide, without text: what a slide of a talk in another language
        than English becomes when it doesn't come out as planned. None if this schema has no such pictures, or none
        is found."""
        pictures = [
            generator
            for generator in self._slide_generators
            if generator.llm is not None and generator.llm.kind == "full_image" and not generator.llm.texts_from
        ]
        neutral = [generator for generator in pictures if "neutral" in generator.get_tags()]
        if not pictures:
            return None
        generator = (neutral or pictures)[0]
        recipe = generator.llm
        assert recipe is not None
        picture = SlidePlan(kind="full_image", recipe=generator.name, concept=concept, images={"image": concept})
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
        parallel: bool = True,
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
        if parallel and len(makeable) > 1:
            with ThreadPool(processes=min(8, len(makeable))) as pool:
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
        _finish_generating(slide_deck)
        return slide_deck, outcomes

    # TALKS THE CLASSIC GENERATOR MAKES

    def _generate_slides(
        self,
        slide_deck: SlideDeck,
        contexts: list[dict],
        rng: random_util.Rng,
        parallel: bool,
        persona: Persona | None = None,
    ) -> None:
        """Work out every slide and add it to the deck, picking their generators as the persona weighs them (see the
        module's docstring for how parallel works)."""
        num_slides = len(contexts)
        slide_rngs = [rng.child("slide", slide_nr) for slide_nr in range(num_slides)]
        results: list[_Results] = [{} for _ in range(num_slides)]
        state = _DeckState()

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
            )

        slide_nr = 0
        while slide_nr < num_slides:
            in_parallel = parallel and num_slides - slide_nr > 1
            pool: ThreadPool | None = None
            worked: Iterator[Any] | None = None
            if in_parallel:
                remaining = list(range(slide_nr, num_slides))
                logger.info("Generating slides %s in parallel", [nr + 1 for nr in remaining])
                pool = ThreadPool(processes=len(remaining))
                work = image_util.carry(functools.partial(work_out, at_state=state.copy(), generate=True))
                worked = pool.imap(work, remaining)
            try:
                # Settle the slides in order, as generating them one by one would: each once its work is done
                while slide_nr < num_slides:
                    if worked is not None:
                        next(worked)
                    worked_out = work_out(slide_nr, state, not in_parallel)
                    if isinstance(worked_out, _NeedsWork):
                        break  # the next round works out the remaining slides again, knowing the ones settled so far
                    if worked_out is None:
                        logger.error("Gave up on generating slide %s", slide_nr + 1)
                    else:
                        slide_deck.add_slide(slide_nr, worked_out.slide)
                        self._update_used_elements(
                            state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
                        )
                    slide_nr += 1
            except BaseException:
                if pool is not None:
                    pool.close()  # (its threads finish by themselves: nothing waits for what they find)
                raise
            if pool is not None:
                pool.close()
                pool.join()  # (the next round reuses what this round's slides found)

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
    ) -> _WorkedOutSlide | _NeedsWork | None:
        """Work out a slide the way generating the slides one by one does: pick a slide generator (with the slide's
        stream for that pick, as the persona weighs them) among the ones the used tags still allow, run it (with its
        own stream for this slide), and pick another one when it fails.

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
    ) -> _Result:
        seed = presentation_context["seed"]
        logger.info("* Generating slide {} about {} using {} *".format(slide_nr + 1, seed, generator))
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
                "* Finished generating slide {} about {} using {} in {} seconds *".format(
                    slide_nr + 1, seed, generator, seconds
                )
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
        without fair use, say), by the image slots of their recipes, which their classic slides use too."""
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
                    isinstance(source, ImageSlot) and not finder.servable(source, policy)
                    for _, source in generator.llm.slots()
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
