"""Every slide's seed: the word it starts from (a classic slide's templates speak of it, and a language model gets it
as the word its slide riffs on). A talk's seeds wander away from its topic and come back to it.

The seeds that wander are things (docs/v5-plan.md, D68): the related words that read as nouns, familiar ones, not
names (conceptnet.related_things), each of a family of its own (not "eruptive" and "erupted" on a volcano talk,
where a slide said "Volcanoes vs. eruptive" and another "Do you want glacial?"), at most MAX_WANDER steps away from
the topic: a related word of the topic, then maybe one of that word's, and then back.

The related words are English (Datamuse's, and ConceptNet's English ones), so in a talk in another language (see
wandering_in), seeds wander from what its topic is in English (english_name), and a slide knows when its seed is an
English word (SlideSeedGenerator.in_english), for the language model to say it in the talk's language (D74): Datamuse
took Dutch "regen" (rain) for the English "regen", and wandered to "renovation" and "redevelopment", Dutch "kaas"
(cheese) to "faas" and "aviation", and "frietjes" nowhere at all.
"""

import concurrent.futures
import contextlib
import logging
import re
from collections.abc import Iterator, Sequence
from contextvars import ContextVar
from functools import lru_cache
from typing import Final

from talkgenerator.plan import languages
from talkgenerator.sources import conceptnet, slide_texts, wikipedia, word_frequency
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
# How long looking up what a topic is in English may take, at most (in seconds): the talk's seeds wait for it, and
# Wikipedia answers within a second, mostly
ENGLISH_LOOKUP_SECONDS: Final = 3.0
_BRACKETS: Final = re.compile(r"\s*\([^)]*\)")

# The language of the talk whose seeds are being made (see wandering_in)
_LANGUAGE: ContextVar[str] = ContextVar("talkgenerator_seed_language", default=languages.ENGLISH.code)


@contextlib.contextmanager
def wandering_in(language: str) -> Iterator[None]:
    """The seed generators made in this block make the seeds of a talk in this language: those that wander, from what
    the talk's topics are in English (see english_name)."""
    token = _LANGUAGE.set(language)
    try:
        yield
    finally:
        _LANGUAGE.reset(token)


class SlideSeedGenerator:
    def get_seed(self, slide_nr: int) -> str:
        raise NotImplementedError("")

    def alternatives(self, slide_nr: int) -> tuple[str, ...]:
        """Other words that would have done as the slide's seed (none, but for seeds that wander)."""
        return ()

    def in_english(self, slide_nr: int) -> bool:
        """Whether the slide's seed is an English word in a talk in another language (never, but for seeds that
        wander)."""
        return False

    def english_name(self, topic: str) -> str:
        """What a topic is in English, as far as the generator looked it up (or else the topic as typed)."""
        return topic


class SideTrackingTopicGenerator(SlideSeedGenerator):
    """This generator will make small side tracks around topics, but keeps returning every X slides"""

    def __init__(self, topics: list[str], num_slides: int, topic_return_period_range=range(3, 6)):
        self._topics = topics
        self._num_slides = num_slides
        self._language = _LANGUAGE.get()
        self._english: dict[str, str | None] = {}  # (what each topic is in English, once looked up: see _start)

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
        # (in a talk in another language, the words it wandered to are English, and so is a topic typed in English)
        other = self._language != languages.ENGLISH.code
        self._in_english = [
            other and (step > 0 or reads_as_english(seed, self._language))
            for seed, step in zip(self._seeds, steps, strict=True)
        ]

    def _wander(
        self, seeds: Sequence[str | None], steps: Sequence[int], index: int
    ) -> tuple[str, int, tuple[str, ...]]:
        """The seed of a blank slide, how many steps away from the topic it is, and the words that would have done
        too: a related thing of the seed before it, while that's less than MAX_WANDER steps away, or else of the
        topic (the one before it, in a talk of several); of the topic, too, when the seed before it has none left.
        The topic itself when not even the topic has one. In a talk in another language, a topic's related things are
        those of what it is in English (none, when that isn't known: see english_name)."""
        topics = [seed for seed, step in zip(seeds[:index], steps[:index], strict=True) if step == 0 and seed]
        topic = topics[-1] if topics else self._topics[0]
        before = seeds[index - 1] if index > 0 else None
        starts = [(before, steps[index - 1] + 1)] if before and steps[index - 1] < MAX_WANDER else []
        words = [(self._start(start), step) for start, step in [*starts, (topic, 1)]]
        english = [name for name in self._english.values() if name]
        taken = [*self._topics, *english, *(seed for seed in seeds if seed)]
        for word, step in words:
            things = _things(word, taken) if word else []
            if things:
                seed = normalise_seed(random_util.weighted_random(things) or things[0][1])
                others = dict.fromkeys(normalise_seed(word) for _, word in things if normalise_seed(word) != seed)
                return seed, step, tuple(others)[:ALTERNATIVES]
        return self._topics[0], 0, ()

    def _start(self, word: str) -> str | None:
        """The word to wander from, for a seed or a topic: the seed itself, or in a talk in another language, what a
        topic is in English (looked up once; None when it isn't known)."""
        if self._language == languages.ENGLISH.code or word not in self._topics:
            return word
        if word not in self._english:
            self._english[word] = english_name(word, self._language)
        return self._english[word]

    def get_seed(self, slide_nr: int) -> str:
        return self._seeds[slide_nr]

    def alternatives(self, slide_nr: int) -> tuple[str, ...]:
        return self._alternatives[slide_nr]

    def in_english(self, slide_nr: int) -> bool:
        return self._in_english[slide_nr]

    def english_name(self, topic: str) -> str:
        return self._english.get(topic) or topic

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


def english_name(topic: str, language: str) -> str | None:
    """What a topic typed for a talk in another language is in English, for its seeds to wander from (the related
    words are English: see the module's documentation): the topic as typed when it reads as English (a talk in Dutch
    on "penguins"), or else the title of the English Wikipedia's article about it (see wikipedia.english_title: "Rain"
    for "regen", "Cheese" for "kaas"), for the topic without the article it starts with first ("les vacances":
    "Vacation"; as typed, "l'escargot" is Matisse's "The Snail"), without what it says in brackets ("Fika (Sweden)":
    "Fika"). None when it has neither, or it takes longer than ENGLISH_LOOKUP_SECONDS to find: then the seeds don't
    wander from it, which beats wandering off the topic."""
    if language == languages.ENGLISH.code or reads_as_english(topic, language):
        return topic
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="topic in English")
    try:
        english = executor.submit(_looked_up, topic, language).result(timeout=ENGLISH_LOOKUP_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.info("What %r is in English took too long to look up: the seeds don't wander from it", topic)
        return None
    except Exception:  # (a source that fails is no reason for the talk to)
        logger.exception("Looking up what %r is in English failed: the seeds don't wander from it", topic)
        return None
    finally:
        executor.shutdown(wait=False)
    if english is None:
        logger.info("%r has no English name to wander from: the seeds don't wander from it", topic)
    else:
        logger.info("The seeds wander from %r, what %r is in English", english, topic)
    return english


def _looked_up(topic: str, language: str) -> str | None:
    """What a topic is in English by Wikipedia (see english_name)."""
    attempts = [topic]
    lowered = topic.lower()
    # ("l'" before "le": an elided article has no space after it)
    for article in sorted(languages.language(language).articles, key=len, reverse=True):
        joined = article.endswith(("'", "’"))
        if lowered.startswith(article if joined else article + " ") and len(topic) > len(article) + 1:
            attempts.insert(0, topic[len(article) :].strip())
            break
    for attempt in attempts:
        title = wikipedia.english_title(attempt, language)
        if title:
            return _BRACKETS.sub("", title).strip() or None
    return None


def reads_as_english(topic: str, language: str) -> bool:
    """Whether a topic typed for a talk in another language is English: each of its words is one English knows, and
    knows at least as well as the language does ("penguins" in a Dutch talk; not "la siesta", nor "regen", Dutch for
    rain, which English knows as a word of gamers)."""
    words = re.findall(r"[^\W\d_]+", topic.lower())
    return bool(words) and all(
        word_frequency.get_frequency(word) > 0
        and word_frequency.get_frequency(word) >= word_frequency.get_frequency(word, language)
        for word in words
    )
