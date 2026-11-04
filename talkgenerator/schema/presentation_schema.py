"""
This module represents the abstractions of a presentation schema
(responsible for specifying how to generate a presentation),
and slide generators, that have functions for generating slides
along with some other metadata.
"""

import logging
import random
import time
from collections.abc import Callable, Collection
from multiprocessing.pool import ThreadPool

from pptx import Presentation

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData, _filter_generated_elements
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from talkgenerator.slide import slide_generator_types
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util

logger = logging.getLogger("talkgenerator")

MAX_PARALLEL_GENERATION_ROUNDS = 6


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
        if max_allowed_tags is None:
            max_allowed_tags = {}
        self._max_allowed_tags = max_allowed_tags
        self._ignore_weights = ignore_weights
        self._title_generator = title_generator

    def generate_presentation(
        self,
        topics: list[str],
        num_slides: int,
        presenter=None,
        title: str = None,
        parallel: bool = False,
        int_seed: int = None,
        save_ppt: bool = True,
        debug_notes: bool = False,
    ) -> tuple[Presentation, SlideDeck]:
        """Generate a presentation about a certain topic with a certain number of slides"""

        logger.info("Made it to presentation_schema...")
        # Generate random talk title
        if not title or title is None:
            if self._title_generator is not None:
                title = self._title_generator({"seed": topics[0]})
            else:
                title = "About " + topics[0]
        logger.info("Generate talk title: {}".format(title))

        # Create new presentation
        slide_deck = SlideDeck(num_slides)
        logger.info("Slide deck: {}".format(slide_deck))

        # Create the topic-for-each-slide generator
        seed_generator = self._seed_generator(topics, num_slides)
        logger.info("Seed generator: {}".format(seed_generator))

        # Create main presentation_context
        main_presentation_context = {
            "topic": topics[0],
            "topics": topics,
            "presenter": presenter,
            "title": title,
        }

        used_tags = {}
        used_elements = set()

        # Generate
        if parallel:
            self._generate_slide_deck_parallel(
                slide_deck,
                num_slides,
                main_presentation_context,
                seed_generator,
                used_elements,
                used_tags,
                int_seed,
            )
        else:
            self._generate_slide_deck(
                slide_deck,
                num_slides,
                main_presentation_context,
                seed_generator,
                used_elements,
                used_tags,
                int_seed,
            )

        if save_ppt:
            presentation = self._powerpoint_creator()
            slide_deck.save_to_powerpoint(presentation, debug_notes=debug_notes)
            return presentation, slide_deck

        return None, slide_deck

    def _generate_slide_deck_parallel(
        self,
        slide_deck,
        num_slides: int,
        main_presentation_context,
        seed_generator: SlideSeedGenerator,
        used_elements,
        used_tags: dict[str, int],
        int_seed: int,
    ):
        logger.info("Generating the slide deck in parallel")
        slide_nrs_to_generate = range(num_slides)

        generated_results = [None] * num_slides

        for round_nr in range(MAX_PARALLEL_GENERATION_ROUNDS):
            if len(slide_nrs_to_generate) == 0:
                break
            if round_nr > 0:
                logger.info("Regenerating the following slides: " + str(slide_nrs_to_generate))

            with ThreadPool(processes=num_slides) as pool:
                all_slide_results = pool.map(
                    SlideGeneratorContext(
                        presentation_schema=self,  # reference the enclosing presentation schema
                        presentation_context=main_presentation_context,
                        seed_generator=seed_generator,
                        num_slides=num_slides,
                        used_elements=used_elements,
                        prohibited_generators=self._calculate_prohibited_generators(used_tags, num_slides),
                        int_seed=int_seed,
                    ),
                    slide_nrs_to_generate,
                )
                slide_nrs_to_generate = []
                for slide_result in all_slide_results:
                    if slide_result:
                        (
                            slide,
                            generated_elements,
                            slide_generator_data,
                            slide_nr,
                        ) = slide_result
                        generated_results[slide_nr] = slide_result

            # Check Constraints

            for i in range(num_slides):
                if not slide_deck.has_slide_nr(i):
                    if not generated_results[i]:
                        slide_nrs_to_generate.append(i)
                    else:
                        success = self._update_slide_deck_with_generated_result(
                            slide_deck,
                            generated_results[i],
                            used_elements,
                            used_tags,
                            num_slides,
                        )
                        if not success:
                            generated_results[i] = None
                            slide_nrs_to_generate.append(i)
        else:
            if slide_nrs_to_generate:
                logger.error("Gave up on generating slides %s", [nr + 1 for nr in slide_nrs_to_generate])

        return slide_deck

    def _generate_slide_deck(
        self,
        slide_deck,
        num_slides,
        main_presentation_context,
        seed_generator,
        used_elements,
        used_tags,
        int_seed=None,
    ):
        for slide_nr in range(num_slides):
            logger.debug("Generating slide: {}".format(slide_nr))
            # Generate the slide
            slide_results = self.generate_slide(
                presentation_context=create_slide_presentation_context(
                    main_presentation_context, seed_generator.get_seed(slide_nr)
                ),
                slide_nr=slide_nr,
                num_slides=num_slides,
                used_elements=used_elements,
                prohibited_generators=self._calculate_prohibited_generators(used_tags, num_slides),
                int_seed=int_seed,
            )

            if slide_results:
                success = self._update_slide_deck_with_generated_result(
                    slide_deck, slide_results, used_elements, used_tags, num_slides
                )
                if not success:
                    logger.warning("Slide %s was rejected because it repeats too much", slide_nr + 1)

        return slide_deck

    def _update_slide_deck_with_generated_result(
        self, slide_deck, generated_result, used_elements, used_tags, num_slides
    ):
        slide, generated_elements, slide_generator_data, slide_nr = generated_result
        # Check if allowed according to repeated elements & slide type tags
        if slide_generator_types.is_different_enough_for_allowed_repeated(
            generated_elements,
            used_elements,
            slide_generator_data.get_allowed_repeated_elements(),
        ) and slide_generator_data not in self._calculate_prohibited_generators(used_tags, num_slides):
            slide_deck.add_slide(slide_nr, slide)
            self._update_used_elements(used_elements, used_tags, generated_elements, slide_generator_data)
            return True
        return False

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
        logger.debug("presentation_schema.generate_slide: {}".format(slide_nr))
        if int_seed is not None:
            random.seed(int_seed + slide_nr)

        # Default arguments: avoid mutable defaults
        if prohibited_generators is None:
            prohibited_generators = set()

        # Select the slide generator to generate with
        try:
            generator = self._select_generator(slide_nr, num_slides, prohibited_generators)
        except ValueError as e:
            logger.error("Could not generate slide %s about '%s': %s", slide_nr + 1, presentation_context["seed"], e)
            return None
        logger.debug("Generator: {}".format(generator))

        start_time = time.time()
        if generator:
            logger.info(
                "* Generating slide {} about {} using {} *".format(
                    slide_nr + 1, presentation_context["seed"], generator
                )
            )
            try:
                slide_result = generator.generate(presentation_context, used_elements)
            except Exception:
                # One misbehaving source (an API that changed, a scraper that broke...) shouldn't sink the talk
                logger.exception("Slide generator %s crashed; trying another one", generator)
                slide_result = None
            logger.debug("Slide result: {}".format(slide_result))

            # Try again if slide is None, and prohibit generator for generating for this topic
            if not bool(slide_result):
                end_time = time.time()
                logger.info(
                    "Failed to generate after {} seconds using: {}".format(round(end_time - start_time, 2), generator)
                )
                prohibited_generators.add(generator)

                return self.generate_slide(
                    presentation_context=presentation_context,
                    slide_nr=slide_nr,
                    num_slides=num_slides,
                    used_elements=used_elements,
                    prohibited_generators=prohibited_generators,
                )

            slide, generated_elements = slide_result
            end_time = time.time()
            logger.info(
                "* Finished generating slide {} about {} using {} in {} seconds *".format(
                    slide_nr + 1,
                    presentation_context["seed"],
                    generator,
                    round(end_time - start_time, 2),
                )
            )
            return slide, generated_elements, generator, slide_nr
        else:
            logger.warning(
                "No generator found to generate slide %s about '%s'", slide_nr + 1, presentation_context["seed"]
            )

    def _select_generator(self, slide_nr, total_slides, prohibited_generators):
        """Select a generator for a certain slide number"""
        if self._ignore_weights:
            return random_util.choice_optional(self._slide_generators)
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


class SlideGeneratorContext:
    def __init__(
        self,
        presentation_schema,
        presentation_context,
        seed_generator: SlideSeedGenerator,
        num_slides: int,
        used_elements: Collection[str | ImageData] | None = None,
        prohibited_generators: Collection[SlideGeneratorData] | None = None,
        int_seed: int | None = None,
    ):
        self.presentation_schema = presentation_schema
        self.presentation_context = presentation_context
        self.seed_generator: SlideSeedGenerator = seed_generator
        self.num_slides = num_slides
        self.used_elements = used_elements
        self.prohibited_generators = prohibited_generators
        self.int_seed = int_seed

    def __call__(self, slide_nr):
        if self and self.int_seed and self.int_seed is not None:
            random.seed(self.int_seed + slide_nr)

        return self.presentation_schema.generate_slide(
            # presentation_context=dict(),
            create_slide_presentation_context(
                self.presentation_context,
                self.seed_generator.get_seed(slide_nr),
                # 'cat'
            ),
            slide_nr=slide_nr,
            num_slides=self.num_slides,
            used_elements=self.used_elements,
            prohibited_generators=self.prohibited_generators,
        )


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
