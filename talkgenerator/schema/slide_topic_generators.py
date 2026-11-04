import multiprocessing
import random
import logging
from functools import lru_cache
from typing import List, Collection

from talkgenerator.sources import conceptnet
from talkgenerator.util import language_util, random_util

# == TOPIC GENERATORS ==

logger = logging.getLogger("talkgenerator")


class SlideSeedGenerator:
    def get_seed(self, slide_nr: int) -> str:
        raise NotImplementedError("")


class SideTrackingTopicGenerator(SlideSeedGenerator):
    """ This generator will make small side tracks around topics, but keeps returning every X slides"""

    def __init__(
        self, topics: List[str], num_slides: int, topic_return_period_range=range(3, 6)
    ):
        self._topics = topics
        self._num_slides = num_slides

        seeds: List[str] = [None] * num_slides

        # Make it begin and end with the topic
        if num_slides > 0:
            # End with main topic
            seeds[-1] = topics[0]

        if len(topics) == 1:
            # Add the returning topic if only one topic given
            idx = 0
            while idx < num_slides:
                seeds[idx] = topics[0]
                idx += random.choice(topic_return_period_range)
        else:
            # Disperse all topics over the slides if multiple topics given
            _disperse(seeds, topics, 0, num_slides - 1)

        # Fill in the blanks with related topics
        previous = seeds.copy()
        while None in seeds:
            fill_in_blank_topics_with_related(seeds)
            logger.info("SideTrackingTopicGenerator concept seeds: {}".format(seeds))
            if seeds == previous:
                fill_in_blanks_with(seeds, topics[0])
                break
            previous = seeds.copy()

        # Convert None's to literal none's for debugging purposes
        seeds = [seed if seed else "None" for seed in seeds]

        self._seeds = seeds

    def get_seed(self, slide_nr: int) -> str:
        return self._seeds[slide_nr]

    def all_seeds(self):
        return self._seeds


def _disperse(seeds, topics, min_idx, max_idx):
    range_size = max_idx - min_idx + 1
    step_size = range_size / len(topics)
    for i in range(len(topics)):
        seeds_index = int(min_idx + step_size * i)
        seeds[seeds_index] = topics[i]


def fill_in_blank_topics_with_related(seeds, distance=1):
    for i in range(len(seeds)):
        _fill_in(seeds, i)


def fill_in_blanks_with(seeds, topic):
    for i in range(len(seeds)):
        if not seeds[i]:
            seeds[i] = topic


def normalise_weighted_word(weighted_word):
    return weighted_word[0], normalise_seed(weighted_word[1])


def _fill_in(seeds, i, distance=1):
    if seeds[i] is None:

        # Check for neighbours
        if i - distance >= 0 and seeds[i - distance]:
            neighbour = seeds[i - distance]

            try:
                related = conceptnet.get_weighted_related_words(neighbour, 25)
                if len(related) == 0:
                    related = conceptnet.get_weighted_related_words(
                        normalise_seed(neighbour), 25
                    )

            except Exception as e:
                logger.info("Conceptnet related words failing: {}".format(e))
                related = []

            normalised_related = map(normalise_weighted_word, related)
            # pool = multiprocessing.Pool()
            # normalised_related = pool.map(normalise_weighted_word, related)
            # pool.close()

            filtered_related = [
                weighted_word
                for weighted_word in normalised_related
                if not weighted_word[1] in seeds and len(weighted_word[1]) > 2
            ]

            if len(filtered_related) > 0:
                seeds[i] = normalise_seed(random_util.weighted_random(filtered_related))

            # Check if still unassigned
            if seeds[i] is None:
                _fill_in(seeds, i, distance + 1)


@lru_cache(maxsize=300)
def normalise_seed(seed):
    normalised = conceptnet.normalise(seed).lower()
    normalised = language_util.replace_non_alphabetical_characters(normalised)
    logger.debug("Mapping seed '%s' => %s", seed, normalised)
    return normalised


class IdentityTopicGenerator(SlideSeedGenerator):
    """ Generates always the given topic as the seed for each slide """

    def __init__(self, topics: Collection[str], _):
        self._topics = topics

    def get_seed(self, _) -> str:
        return random.choice(self._topics)


# class SynonymTopicGenerator:
#     """ Generates a bunch of related words (e.g. synonyms) of a word to generate topics for a presentation"""
#
#     def __init__(self, topic, number_of_slides):
#         self._topic = topic
#         self._slides_nr = number_of_slides
#         synonyms = language_util.get_synonyms(topic)
#         # seeds.extend(get_relations(topic))
#
#         # Check if enough generated
#         if len(synonyms) < number_of_slides:
#             # If nothing: big problem!
#             if len(synonyms) == 0:
#                 synonyms = [topic]
#
#             # Now fill the seeds up with repeating topics
#             number_of_repeats = int(math.ceil(number_of_slides / len(synonyms)))
#             synonyms = numpy.tile(synonyms, number_of_repeats)
#
#         # Take random `number_of_slides` elements
#         random.shuffle(synonyms)
#         self._seeds = synonyms[0: number_of_slides]
#
#     def generate_seed(self, slide_nr):
#         return self._seeds[slide_nr]
