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
"""

import functools
import itertools
import logging
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Any

from pptx.presentation import Presentation

from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData, _filter_generated_elements
from talkgenerator.llm.base import ProviderError, TextProvider
from talkgenerator.llm.providers import NoneProvider
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import Recipe, TextField
from talkgenerator.plan.prompt import PlannedSlide, slide_plan, talk_request
from talkgenerator.plan.realize import ATTEMPTS, clean_text, realize
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util

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

_TALK_TITLE = TextField("title", "the talk's title", 80)
_PRESENTER_JOB = TextField("presenter_job", "the presenter's job", 40)


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
    subtitle = ", ".join(part for part in (f"{by} {presenter}" if presenter else "", job or "") if part) or None
    slide = slides.TitleSlide(title, subtitle)
    slide.set_note(f"Planned: the title slide\nThesis: {thesis!r}")
    return slide, [text for text in (title, subtitle) if text]


def _add_used(state: _DeckState, generated_elements: list) -> None:
    elements = set(generated_elements)
    _filter_generated_elements(elements)
    state.used_elements.update(elements)


@dataclass(eq=False)
class _PlannedTalk:
    """A talk as the language model plans it: every slide's generator, the model's answer so far, and the first
    attempts at realizing its slides (in parallel, while the rest of the answer comes in)."""

    picks: list[SlideGeneratorData | None]
    planned: dict[int, PlannedSlide]  # the slides the model writes, by slide number (from 0)
    contexts: list[dict[str, Any]]
    rngs: list[random_util.Rng]
    spine: dict[str, Any] = field(default_factory=dict)
    plans: dict[int, SlidePlan] = field(default_factory=dict)
    first_attempts: dict[int, Any] = field(default_factory=dict)
    pool: ThreadPool | None = None
    language: str = "en"

    def __post_init__(self) -> None:
        self._slide_numbers = {slide.key: slide_nr for slide_nr, slide in self.planned.items()}

    @property
    def title(self) -> str | None:
        return clean_text(self.spine.get("title"), _TALK_TITLE)

    def take(self, key: str, value: Any) -> None:
        """A part of the model's answer: the spine, or a slide (whose first attempt then starts, in parallel)."""
        slide_nr = self._slide_numbers.get(key)
        if slide_nr is None:
            self.spine[key] = value
            return
        if self.spine.get("safe_topic") is False:  # it comes first: then no slide is looked for
            return
        plan = slide_plan(self.planned[slide_nr], value)
        if plan is None:
            return
        self.plans[slide_nr] = plan
        if self.pool is not None:
            self.first_attempts[slide_nr] = self.pool.apply_async(self._realize, (slide_nr, 0))

    def attempt(self, slide_nr: int, attempt: int) -> tuple[Any, list] | None:
        if attempt == 0 and slide_nr in self.first_attempts:
            result: tuple[Any, list] | None = self.first_attempts[slide_nr].get()
            return result
        return self._realize(slide_nr, attempt)

    def _realize(self, slide_nr: int, attempt: int) -> tuple[Any, list] | None:
        recipe = self.planned[slide_nr].recipe
        try:
            return realize(self.plans[slide_nr], recipe, self.contexts[slide_nr], self.rngs[slide_nr], attempt)
        except Exception:  # one misbehaving source shouldn't sink the talk: the slide goes classic
            logger.exception("Realizing planned slide %s crashed", slide_nr + 1)
            return None

    def drop(self) -> None:
        """Forget what the model wrote."""
        self.plans.clear()
        self.first_attempts.clear()
        self.spine.pop("title", None)

    def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
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
    ):
        self._powerpoint_creator = powerpoint_creator
        self._seed_generator = seed_generator
        self._slide_generators = slide_generators
        self._generator_indices = {id(generator): index for index, generator in enumerate(slide_generators)}
        if max_allowed_tags is None:
            max_allowed_tags = {}
        self._max_allowed_tags = max_allowed_tags
        self._ignore_weights = ignore_weights
        self._title_generator = title_generator

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
    ) -> tuple[Presentation | None, SlideDeck]:
        """Generate a presentation about a certain topic with a certain number of slides.

        The same seed (int_seed, or the talk's random generator rng) gives the same talk, in parallel or not, as long
        as the sources give the same answers. Without a seed, a random one is picked: the deck tells which.

        With a language model (llm), the model writes what goes on the slides, in the given language (see
        _plan_talk); the slides it doesn't write, or that come out missing something, are classic."""
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

        talk = None
        if llm is not None and self.writes_with(llm):
            talk = self._plan_talk(topics, seeds, rng, llm, language, title, parallel)
        try:
            # Generate random talk title
            if not title and talk is not None:
                title = talk.title
            if not title:
                with random_util.use(rng.child("title")):
                    if self._title_generator is not None:
                        title = self._title_generator({"seed": topics[0]})
                    else:
                        title = "About " + topics[0]
            logger.info("Generate talk title: {}".format(title))

            # A talk in another language needs the language model's slides: the classic ones are English
            planned = talk is not None and bool(talk.plans)
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
            logger.info("Slide deck: {}".format(slide_deck))

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
                self._settle_planned_talk(slide_deck, talk, contexts, rng, presenter)
            else:
                self._generate_slides(slide_deck, contexts, rng, parallel)
        finally:
            if talk is not None:
                talk.close()

        if save_ppt:
            presentation = self._powerpoint_creator()
            slide_deck.save_to_powerpoint(presentation, debug_notes=debug_notes)
            return presentation, slide_deck

        return None, slide_deck

    def render(self, slide_deck: SlideDeck, debug_notes: bool = False) -> Presentation:
        """The deck as a PowerPoint presentation."""
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
    ) -> "_PlannedTalk":
        """Pick every slide's generator, and ask the language model, in one request, what goes on the slides whose
        generators have recipes. The model's answer is read while it's written, and in parallel, every slide's first
        attempt starts as soon as its part of the answer is in."""
        num_slides = len(seeds)
        picks = self._pick_generators(num_slides, rng, language)
        planned = {
            slide_nr: PlannedSlide(slide_nr + 1, pick.name or str(pick), pick.llm, seeds[slide_nr])
            for slide_nr, pick in enumerate(picks)
            if pick is not None and pick.llm is not None and pick.llm.kind != "title"
        }
        talk = _PlannedTalk(
            picks,
            planned,
            # What realizing a slide may know: its topic and language (not the title, which arrives with the answer)
            [{"topic": topics[0], "topics": topics, "seed": seed, "language": language} for seed in seeds],
            [rng.child("slide", slide_nr, "planned") for slide_nr in range(num_slides)],
            language=language,
        )
        if not planned:
            return talk
        if parallel:
            talk.pool = ThreadPool(processes=min(8, len(planned)))

        reader = ObjectReader()
        read_anything = False

        def read(text: str) -> None:
            nonlocal read_anything
            read_anything = True
            for key, value in reader.feed(text):
                talk.take(key, value)

        request = talk_request(topics, list(planned.values()), rng, language, title)
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
        except ProviderError as error:
            logger.warning("The language model didn't write the talk (%s): its slides are classic", error)
        except Exception:  # a misbehaving provider shouldn't sink the talk either
            logger.exception("Asking the language model for the talk crashed: its slides are classic")
        if talk.spine.get("safe_topic") is False:
            logger.warning("The language model wouldn't write about this topic: the talk is classic")
            talk.drop()
        logger.info("The language model wrote %s of the %s slides", len(talk.plans), num_slides)
        return talk

    def _pick_generators(
        self, num_slides: int, rng: random_util.Rng, language: str = "en"
    ) -> list[SlideGeneratorData | None]:
        """Every slide's generator, before there's any content: by weight for the slide's position, among the ones
        the tags of the slides before it still allow (as generating the slides one by one picks them). A talk in
        another language than English gets none whose recipes find English texts (such as real quotes)."""
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
                    generator = self._select_generator(slide_nr, num_slides, prohibited)
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
    ) -> None:
        """Settle the slides in order: the title slide from the plan's title, a planned slide in up to ATTEMPTS
        tries (each must not repeat what the slides before it used), and a classic slide wherever that fails. In a
        talk in another language than English, where classic slides would be English, that's a picture of what the
        slide was about, without text (or no slide, without pictures in the schema)."""
        num_slides = len(contexts)
        state = _DeckState()
        for slide_nr in range(num_slides):
            pick = talk.picks[slide_nr]
            worked_out: _WorkedOutSlide | None = None
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
                    slide_nr, num_slides, contexts[slide_nr], rng.child("slide", slide_nr), state, {}, generate=True
                )
                worked_out = classic if isinstance(classic, _WorkedOutSlide) else None
            if worked_out is None:
                logger.error("Gave up on generating slide %s", slide_nr + 1)
                continue
            slide_deck.add_slide(slide_nr, worked_out.slide)
            self._update_used_elements(
                state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
            )

    @staticmethod
    def _planned_title_slide(
        slide_nr: int, generator: SlideGeneratorData, talk: "_PlannedTalk", title: str, presenter: str | None
    ) -> _WorkedOutSlide:
        job = clean_text(talk.spine.get("presenter_job"), _PRESENTER_JOB)
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
        title = clean_text(plan.title, _TALK_TITLE) or plan.topic
        slide_deck = SlideDeck(
            num_slides,
            title=title,
            topics=[plan.topic],
            presenter=presenter,
            seed=rng.root_seed,
            language=plan.language,
        )
        state = _DeckState()
        job = clean_text(plan.presenter_job, _PRESENTER_JOB)
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
                first_tries = dict(zip(makeable, pool.map(lambda index: attempt(index, 0), makeable), strict=True))

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
            slide_deck.add_slide(index + 1, worked_out[0])
            _add_used(state, worked_out[1])
        return slide_deck, outcomes

    # TALKS THE CLASSIC GENERATOR MAKES

    def _generate_slides(
        self,
        slide_deck: SlideDeck,
        contexts: list[dict],
        rng: random_util.Rng,
        parallel: bool,
    ) -> None:
        """Work out every slide and add it to the deck (see the module's docstring for how parallel works)."""
        num_slides = len(contexts)
        slide_rngs = [rng.child("slide", slide_nr) for slide_nr in range(num_slides)]
        results: list[_Results] = [{} for _ in range(num_slides)]
        state = _DeckState()

        def work_out(slide_nr: int, at_state: _DeckState, generate: bool) -> _WorkedOutSlide | _NeedsWork | None:
            return self._work_out_slide(
                slide_nr, num_slides, contexts[slide_nr], slide_rngs[slide_nr], at_state, results[slide_nr], generate
            )

        slide_nr = 0
        while slide_nr < num_slides:
            in_parallel = parallel and num_slides - slide_nr > 1
            if in_parallel:
                remaining = list(range(slide_nr, num_slides))
                logger.info("Generating slides %s in parallel", [nr + 1 for nr in remaining])
                with ThreadPool(processes=len(remaining)) as pool:
                    pool.map(functools.partial(work_out, at_state=state.copy(), generate=True), remaining)
            # Settle the slides in order, as generating them one by one would
            while slide_nr < num_slides:
                worked_out = work_out(slide_nr, state, not in_parallel)
                if isinstance(worked_out, _NeedsWork):
                    break  # the next round works out the remaining slides again, knowing the slides settled so far
                if worked_out is None:
                    logger.error("Gave up on generating slide %s", slide_nr + 1)
                else:
                    slide_deck.add_slide(slide_nr, worked_out.slide)
                    self._update_used_elements(
                        state.used_elements, state.used_tags, worked_out.generated_elements, worked_out.generator
                    )
                slide_nr += 1

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
    ) -> _WorkedOutSlide | _NeedsWork | None:
        """Work out a slide the way generating the slides one by one does: pick a slide generator (with the slide's
        stream for that pick) among the ones the used tags still allow, run it (with its own stream for this slide),
        and pick another one when it fails.

        results holds what the generators produced for this slide before, given fewer used elements, and gets what
        they produce now. A failure stays a failure, and a slide still holds as long as it doesn't repeat what's used
        now. Without generate, a slide that needs a generator to run returns _NEEDS_WORK instead. Returns None when
        no slide generator is left to try."""
        prohibited = set(self._calculate_prohibited_generators(state.used_tags, num_slides)) | set(extra_prohibited)
        for pick in itertools.count():
            with random_util.use(rng.child("pick", pick)):
                try:
                    generator = self._select_generator(slide_nr, num_slides, prohibited)
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

    def _select_generator(self, slide_nr, total_slides, prohibited_generators):
        """Select a generator for a certain slide number"""
        if self._ignore_weights:
            return random_util.choice_optional(
                [generator for generator in self._slide_generators if generator not in prohibited_generators]
            )
        _selected_generator = random_util.weighted_random(
            self._get_weighted_generators_for_slide_nr(slide_nr, total_slides, prohibited_generators)
        )
        logger.debug("_selected_generator: {}".format(_selected_generator))
        return _selected_generator

    def _get_weighted_generators_for_slide_nr(self, slide_nr, total_slides, prohibited_generators):
        weighted_generators = []
        for i in range(len(self._slide_generators)):
            generator = self._slide_generators[i]
            if generator in prohibited_generators:
                continue
            weighted_generator = (
                generator.get_weight_for(slide_nr, total_slides),
                generator,
            )
            weighted_generators.append(weighted_generator)

        if len(weighted_generators) == 0:
            raise ValueError("No generators left to generate slides with!")

        return weighted_generators

    def _calculate_prohibited_generators(self, used_tags: dict[str, int], num_slides: int):
        prohibited_tags = set()
        for key, value in used_tags.items():
            if key in self._max_allowed_tags:
                max_tag = self._max_allowed_tags[key]

                # Assumes integer maximum
                max_number_of_slides = max_tag

                # If Procentua/Double ratio:
                if 0 < max_tag < 1:
                    max_number_of_slides = int(max_tag * num_slides)

                # Check if currently over the max allowed slides of this tag
                if value >= max_number_of_slides:
                    prohibited_tags.add(key)

        prohibited_generators = set()
        for generator in self._slide_generators:
            if set(generator.get_tags()) & prohibited_tags:
                prohibited_generators.add(generator)

        return prohibited_generators


# Helper functions
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
