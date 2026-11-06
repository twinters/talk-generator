"""
Light, commonly used, non-specific generators that are helpful shortcuts for creating
certain types of (content) generators
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import image_util, random_util

logger = logging.getLogger("talkgenerator")

# While the images of a planned slide are searched (see as_planned), searches go as written: generators that rewrite a
# search (with a prefix, a related word, a walk) pass it on unchanged, random fallbacks step aside, and image lists
# pick among their best results instead of all of them. The classic generator keeps its surprises.
_AS_PLANNED: ContextVar[bool] = ContextVar("talkgenerator_as_planned", default=False)
TOP_RESULTS: Final = 5


@contextmanager
def as_planned() -> Iterator[None]:
    """Search for what a plan asks for, as written (see _AS_PLANNED)."""
    token = _AS_PLANNED.set(True)
    try:
        yield
    finally:
        _AS_PLANNED.reset(token)


def planned() -> bool:
    return _AS_PLANNED.get()


def fullname(o):
    # o.__module__ + "." + o.__class__.__qualname__ is an example in
    # this context of H.L. Mencken's "neat, plausible, and wrong."
    # Python makes no guarantees as to whether the __module__ special
    # attribute is defined, so we take a more circumspect approach.
    # Alas, the module name is explicitly excluded from __qualname__
    # in Python 3.

    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__  # Avoid reporting __builtin__
    else:
        return module + "." + o.__class__.__name__


class Generator:
    def __call__(self, seed: str):
        raise NotImplementedError(str(self) + " has not provided an implementation for the generator")


class PrefixedGenerator(Generator):
    def __init__(self, prefix: str, generator: Generator):
        self._prefix = prefix
        self._generator = generator

    def __call__(self, seed: str):
        return self._generator(seed if planned() else self._prefix + " " + seed)


class PrefixedPresentationContextGenerator(Generator):
    def __init__(self, prefix: str, generator):
        self._prefix = prefix
        self._generator = generator

    def __call__(self, presentation_context):
        if planned():
            return self._generator(presentation_context)
        presentation_context = dict(presentation_context)
        presentation_context["seed"] = self._prefix + " " + presentation_context["seed"]
        return self._generator(presentation_context)


class CombinedGenerator(Generator):
    def __init__(self, *weighted_generators: tuple[float, Callable[[Any], Any]]):
        self._weighted_generators = weighted_generators

    def __call__(self, seed: str | dict[str, str]):
        logger.debug("Calling generator_util.CombinedGenerator")
        current_weighted_generators = list(self._weighted_generators)
        logger.debug("current_weighted_generators: {}".format(current_weighted_generators))
        while len(current_weighted_generators) > 0:
            generator = random_util.weighted_random(current_weighted_generators)
            if generator is None:
                return None
            logger.debug("current generator: {}".format(generator))
            logger.debug("generator seed: {}".format(seed))
            generated = generator(seed)
            logger.debug("generated: {}".format(generated))
            if generated is not None:
                return generated
            _remove_object_from_weighted_list(current_weighted_generators, generator)


def _remove_object_from_weighted_list(current_weighted_generators, generator):
    for i in current_weighted_generators:
        if i and i[1] == generator:
            current_weighted_generators.remove(i)


class MappedGenerator(Generator):
    def __init__(self, generator, *functions):
        self._generator = generator
        self._functions = functions

    def __call__(self, presentation_context):
        # print("MappedGenerator generator using", presentation_context)
        generated = self._generator(presentation_context)
        for func in self._functions:
            generated = func(generated)
        return generated


class TupledGenerator(Generator):
    """Creates a tuple generator that generates every tuple value independent from the others"""

    def __init__(self, *generators):
        self._generators = generators

    def __call__(self, presentation_context):
        # print("TupledGenerator generator using", presentation_context)
        return tuple([generator(presentation_context) for generator in self._generators])


class InspiredTupleGenerator(Generator):
    """The second generator will get the generator 1 as input, outputting the tuple"""

    def __init__(self, generator_1, generator_2):
        self._generator_1 = generator_1
        self._generator_2 = generator_2

    def __call__(self, presentation_context):
        # print("InspiredTupleGenerator generator using", presentation_context)
        gen_1 = self._generator_1(presentation_context)
        gen_2 = self._generator_2(gen_1)
        return gen_1, gen_2


# == TRIVIAL GENERATORS ==


class SeededGenerator(Generator):
    def __init__(self, simple_generator):
        self._simple_generator = simple_generator

    def __call__(self, presentation_context):
        logger.debug("Calling generator_util.SeededGenerator")
        logger.debug("presentation_context: {}".format(presentation_context))
        logger.debug("self._simple_generator: {}".format(self._simple_generator))
        return self._simple_generator(presentation_context["seed"])


class UnseededGenerator(Generator):
    def __init__(self, simple_generator):
        self._simple_generator = simple_generator

    def __call__(self, seed):
        presentation_context = {"seed": seed}
        return self._simple_generator(presentation_context)


class NoneGenerator(Generator):
    def __init__(self):
        pass

    def __call__(self, presentation_context):
        return None


class IdentityGenerator(Generator):
    def __init__(self, input_word):
        self._input_word = input_word

    def __call__(self, presentation_context):
        return self._input_word


class TitledIdentityGenerator(Generator):
    def __init__(self, input_word):
        self._input_word = input_word

    def __call__(self, presentation_context):
        if self._input_word:
            return self._input_word.title()


class StaticGenerator(Generator):
    def __init__(self, always_generate_this):
        self._always_generate_this = always_generate_this

    def __call__(self, presentation_context=None):
        return self._always_generate_this


class FromListGenerator(Generator):
    def __init__(self, list_generator):
        self._list_generator = list_generator

    def __call__(self, presentation_context):
        return random_util.choice_optional(self._list_generator(presentation_context))


seeded_identity_generator = SeededGenerator(IdentityGenerator)
seeded_titled_identity_generator = SeededGenerator(TitledIdentityGenerator)


class ExternalImageListGenerator(Generator):
    """Picks a random image from a list of candidates (optionally weighted by (weight, image) pairs).

    With check_image_validness, candidates are downloaded and checked first, so that dead links
    and "image removed" placeholders are skipped instead of ending up as holes in the deck.
    """

    max_attempts = 8

    def __init__(
        self,
        image_generator,
        check_image_validness=True,
        weighted=False,
    ):
        self._image_generator = image_generator
        self._check_image_validness = check_image_validness
        self._weighted = weighted

    def __call__(self, presentation_context) -> ImageData | None:
        images = self._image_generator(presentation_context)
        if not images:
            return None
        # Work on a copy: the list may come straight out of a cache
        candidates = list(images)

        for _ in range(self.max_attempts):
            if self._weighted:
                candidates = [entry for entry in candidates if entry[0] > 0]
            if not candidates:
                return None
            # For a plan, among the best results (the search's first ones) that are left
            pool = candidates[:TOP_RESULTS] if planned() else candidates
            if self._weighted:
                entry = random_util.choices(pool, weights=[entry[0] for entry in pool])[0]
                chosen = entry[1]
            else:
                entry = chosen = random_util.choice(pool)
            candidates.remove(entry)

            if isinstance(chosen, str):
                chosen_image = ImageData(image_url=chosen)
            elif isinstance(chosen, ImageData):
                chosen_image = chosen
            else:
                logger.warning("Invalid image input for external image generator: %r", chosen)
                continue

            if not self._check_image_validness or image_util.fetch_image_data(chosen_image) is not None:
                return chosen_image
        return None


class BackupGenerator(Generator):
    def __init__(self, *generator_list):
        self._generator_list = generator_list

    def __call__(self, context):
        for generator in self._generator_list:
            generated = generator(context)
            if generated:
                return generated


class WeightedGenerator(Generator):
    def __init__(self, weighted_list_creator):
        self._weighted_list_creator = weighted_list_creator

    def __call__(self, argument):
        weighted_list = self._weighted_list_creator(argument)
        if weighted_list:
            return random_util.weighted_random(weighted_list)


class UnweightedGenerator(Generator):
    def __init__(self, weighted_list_creator):
        self._weighted_list_creator = weighted_list_creator

    def __call__(self, argument):
        weighted_list = self._weighted_list_creator(argument)
        if weighted_list:
            return random_util.choice_optional([element[1] for element in weighted_list])


class WalkingGenerator(Generator):
    """This type of generator uses its output as input for a next step, taking concepts a few steps away"""

    def __init__(self, inner_generator, steps):
        self._inner_generator = inner_generator
        self._steps = steps

    def __call__(self, seed):
        if planned():
            return seed
        history = set()
        history.add(seed)
        current = seed
        for _ in range(self._steps):
            generated = self._inner_generator(current)
            if generated:
                current = generated
                history.add(current)

        return current


class ImageGenerator(Generator):
    def __call__(self, seed: str) -> ImageData:
        raise NotImplementedError("Not implemented image generator")


class UnsourcedImageGenerator(ImageGenerator):
    def __init__(self, image_url_generator: Callable[[str], str]):
        self._image_url_generator = image_url_generator

    def __call__(self, seed: str) -> ImageData:
        return ImageData(image_url=self._image_url_generator(seed))


class RelatedMappingGenerator(Generator):
    def __init__(self, related_word_generator: Callable[[str], str], generator: Generator):
        self._related_word_generator = related_word_generator
        self._generator = generator

    def __call__(self, seed: str) -> str | None:
        mapped_seed = seed if planned() else self._related_word_generator(seed)
        return self._generator(mapped_seed)
