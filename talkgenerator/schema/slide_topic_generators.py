"""Every slide's seed: the word it starts from (a classic slide's templates speak of it, and a language model gets it
as the word its slide riffs on). A talk's seeds wander away from its topic and come back to it.

The seeds that wander are things (docs/v5-plan.md, D68): the related words that read as nouns, familiar ones, not
names (conceptnet.related_things), each of a family of its own (not "eruptive" and "erupted" on a volcano talk,
where a slide said "Volcanoes vs. eruptive" and another "Do you want glacial?"), at most MAX_WANDER steps away from
the topic: a related word of the topic, then maybe one of that word's, and then back.
"""

import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Final

from talkgenerator.sources import conceptnet, slide_texts
from talkgenerator.util import language_util, random_util

# == TOPIC GENERATORS ==

logger = logging.getLogger("talkgenerator")

# How many steps a seed wanders from the topic at most, each a related word of the one before ("penguins": "seals",
# "walrus"), before the next starts from the topic again: further on, the talk lost its topic ("penguins": "leafs",
# "hockey", "netball", in a talk of 2026-11-09)
MAX_WANDER: Final = 2
# How many related words a seed is picked among (the weightiest first: Datamuse's top words are its oddest)
_CANDIDATES: Final = 50
# How many other words that would have done a seed keeps, besides itself (for a language model to pick from)
ALTERNATIVES: Final = 3


class SlideSeedGenerator:
    def get_seed(self, slide_nr: int) -> str:
        raise NotImplementedError("")

    def alternatives(self, slide_nr: int) -> tuple[str, ...]:
        """Other words that would have done as the slide's seed (none, but for seeds that wander)."""
        return ()


class SideTrackingTopicGenerator(SlideSeedGenerator):
    """This generator will make small side tracks around topics, but keeps returning every X slides"""

    def __init__(self, topics: list[str], num_slides: int, topic_return_period_range=range(3, 6)):
        self._topics = topics
        self._num_slides = num_slides

        seeds: list[str | None] = [None] * num_slides

        # Make it begin and end with the topic
        if num_slides > 0:
            # End with main topic
            seeds[-1] = topics[0]

        if len(topics) == 1:
            # Add the returning topic if only one topic given
            idx = 0
            while idx < num_slides:
                seeds[idx] = topics[0]
                idx += random_util.choice(topic_return_period_range)
        else:
            # Disperse all topics over the slides if multiple topics given
            _disperse(seeds, topics, 0, num_slides - 1)

        # Fill in the blanks with related things, wandering away from the topic and back
        steps = [0 if seed is not None else MAX_WANDER + 1 for seed in seeds]
        alternatives: list[tuple[str, ...]] = [()] * num_slides
        for index in range(num_slides):
            if seeds[index] is None:
                seeds[index], steps[index], alternatives[index] = self._wander(seeds, steps, index)
        logger.info("SideTrackingTopicGenerator concept seeds: {}".format(seeds))

        self._seeds: list[str] = [seed or topics[0] for seed in seeds]
        self._alternatives = alternatives

    def _wander(
        self, seeds: Sequence[str | None], steps: Sequence[int], index: int
    ) -> tuple[str, int, tuple[str, ...]]:
        """The seed of a blank slide, how many steps away from the topic it is, and the words that would have done
        too: a related thing of the seed before it, while that's less than MAX_WANDER steps away, or else of the
        topic (the one before it, in a talk of several); of the topic, too, when the seed before it has none left.
        The topic itself when not even the topic has one."""
        topics = [seed for seed, step in zip(seeds[:index], steps[:index], strict=True) if step == 0 and seed]
        topic = topics[-1] if topics else self._topics[0]
        taken = [*self._topics, *(seed for seed in seeds if seed)]
        before = seeds[index - 1] if index > 0 else None
        starts = [(before, steps[index - 1] + 1)] if before and steps[index - 1] < MAX_WANDER else []
        for start, step in [*starts, (topic, 1)]:
            things = _things(start, taken)
            if things:
                seed = normalise_seed(random_util.weighted_random(things) or things[0][1])
                others = dict.fromkeys(normalise_seed(word) for _, word in things if normalise_seed(word) != seed)
                return seed, step, tuple(others)[:ALTERNATIVES]
        return self._topics[0], 0, ()

    def get_seed(self, slide_nr: int) -> str:
        return self._seeds[slide_nr]

    def alternatives(self, slide_nr: int) -> tuple[str, ...]:
        return self._alternatives[slide_nr]

    def all_seeds(self):
        return self._seeds


def _things(word: str, taken: Sequence[str]) -> list[tuple[float, str]]:
    """The related things a seed can be, after this word, none of the family of a word taken already (see
    conceptnet.related_things), nor a word a slide shouldn't make light of; for a phrase whose related words are all
    of its own family ("quantum physics": "quantum mechanics", "quantum theory"), those of its words, its last one
    (usually the main one) first. None when ConceptNet and Datamuse fail."""
    words = [word, normalise_seed(word), *reversed(word.split())] if " " in word.strip() else [word]
    try:
        for start in dict.fromkeys(words):
            things = [
                (weight, thing)
                for weight, thing in conceptnet.related_things(start, _CANDIDATES, avoid=taken)
                if len(normalise_seed(thing)) > 2 and not slide_texts.sensitive(thing)
            ]
            if things:
                return things
    except Exception as e:
        logger.info("Conceptnet related words failing: {}".format(e))
    return []


def _disperse(seeds, topics, min_idx, max_idx):
    range_size = max_idx - min_idx + 1
    step_size = range_size / len(topics)
    for i in range(len(topics)):
        seeds_index = int(min_idx + step_size * i)
        seeds[seeds_index] = topics[i]


@lru_cache(maxsize=300)
def normalise_seed(seed):
    normalised = conceptnet.normalise(seed).lower()
    normalised = language_util.replace_non_alphabetical_characters(normalised)
    logger.debug("Mapping seed '%s' => %s", seed, normalised)
    return normalised


class IdentityTopicGenerator(SlideSeedGenerator):
    """Generates always the given topic as the seed for each slide"""

    def __init__(self, topics: Sequence[str], _):
        self._topics = topics

    def get_seed(self, _) -> str:
        return random_util.choice(self._topics)
