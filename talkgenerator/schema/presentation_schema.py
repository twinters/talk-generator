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
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from multiprocessing.pool import ThreadPool
from typing import Any

from pptx.presentation import Presentation

from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData, _filter_generated_elements
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from talkgenerator.slide import slide_generator_types
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
    ) -> tuple[Presentation | None, SlideDeck]:
        """Generate a presentation about a certain topic with a certain number of slides.

        The same seed (int_seed, or the talk's random generator rng) gives the same talk, in parallel or not, as long
        as the sources give the same answers. Without a seed, a random one is picked: the deck tells which."""
        if rng is None:
            rng = random_util.Rng(int_seed)

        logger.info("Made it to presentation_schema...")
        # Generate random talk title
        if not title:
            with random_util.use(rng.child("title")):
                if self._title_generator is not None:
                    title = self._title_generator({"seed": topics[0]})
                else:
                    title = "About " + topics[0]
        logger.info("Generate talk title: {}".format(title))

        # Create new presentation
        slide_deck = SlideDeck(num_slides, title=title, topics=topics, presenter=presenter, seed=rng.root_seed)
        logger.info("Slide deck: {}".format(slide_deck))

        # Create the topic-for-each-slide generator
        with random_util.use(rng.child("topics")):
            seed_generator = self._seed_generator(topics, num_slides)
        logger.info("Seed generator: {}".format(seed_generator))

        # Create main presentation_context
        main_presentation_context = {
            "topic": topics[0],
            "topics": topics,
            "presenter": presenter,
            "title": title,
        }

        self._generate_slides(slide_deck, num_slides, main_presentation_context, seed_generator, rng, parallel)

        if save_ppt:
            presentation = self._powerpoint_creator()
            slide_deck.save_to_powerpoint(presentation, debug_notes=debug_notes)
            return presentation, slide_deck

        return None, slide_deck

    def _generate_slides(
        self,
        slide_deck: SlideDeck,
        num_slides: int,
        main_presentation_context: dict,
        seed_generator: SlideSeedGenerator,
        rng: random_util.Rng,
        parallel: bool,
    ) -> None:
        """Work out every slide and add it to the deck (see the module's docstring for how parallel works)."""
        slide_rngs = [rng.child("slide", slide_nr) for slide_nr in range(num_slides)]
        contexts = []
        for slide_nr in range(num_slides):
            with random_util.use(slide_rngs[slide_nr].child("topic")):
                seed = seed_generator.get_seed(slide_nr)
            contexts.append(create_slide_presentation_context(main_presentation_context, seed))
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
