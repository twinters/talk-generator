"""
Light, commonly used, non-specific generators that are helpful shortcuts for creating
certain types of (content) generators
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final

from talkgenerator.util import random_util

logger = logging.getLogger("talkgenerator")

# While the images of a planned slide are searched (see as_planned), searches go as written: generators that rewrite a
# search (with a related word, a walk) pass it on unchanged, random fallbacks step aside, and the image finder picks
# among a source's best results (TOP_RESULTS of them) instead of all of them. The classic generator keeps its
# surprises.
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


class Generator:
    def __call__(self, seed: str):
        raise NotImplementedError(str(self) + " has not provided an implementation for the generator")


class CombinedGenerator(Generator):
    """One of its generators, picked by weight, and when that one gives nothing (a source that failed, say), another
    one of the rest. A NoneGenerator among them gives none on purpose: when it's picked, there's none (a slide
    without a title, say), rather than another generator's."""

    def __init__(self, *weighted_generators: tuple[float, Callable[[Any], Any]]):
        self._weighted_generators = weighted_generators

    @property
    def choices(self) -> tuple[Callable[[Any], Any], ...]:
        """Its generators, without their weights."""
        return tuple(generator for _, generator in self._weighted_generators)

    def __call__(self, seed: str | dict[str, str]):
        logger.debug("Calling generator_util.CombinedGenerator")
        current_weighted_generators = list(self._weighted_generators)
        logger.debug(f"current_weighted_generators: {current_weighted_generators}")
        while len(current_weighted_generators) > 0:
            generator = random_util.weighted_random(current_weighted_generators)
            if generator is None or isinstance(generator, NoneGenerator):
                return None
            logger.debug(f"current generator: {generator}")
            logger.debug(f"generator seed: {seed}")
            generated = generator(seed)
            logger.debug(f"generated: {generated}")
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
        logger.debug(f"presentation_context: {presentation_context}")
        logger.debug(f"self._simple_generator: {self._simple_generator}")
        return self._simple_generator(presentation_context["seed"])


class NoneGenerator(Generator):
    def __init__(self):
        pass

    def __call__(self, presentation_context):
        return None


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


class RelatedMappingGenerator(Generator):
    def __init__(self, related_word_generator: Callable[[str], str], generator: Generator):
        self._related_word_generator = related_word_generator
        self._generator = generator

    def __call__(self, seed: str) -> str | None:
        mapped_seed = seed if planned() else self._related_word_generator(seed)
        return self._generator(mapped_seed)
