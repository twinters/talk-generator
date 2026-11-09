"""Actions ("how to ...") from WikiHow's public search, for the texts about a slide's seed.

WikiHow's search pads what it knows little about with its most popular how-tos ("Kiss", "Tie a Tie", "Make Sex
Better") and with loose matches (penguins: "Be a Secret Agent"; stations: "Have a Baby in The Sims 4"). So a seed gets
only the actions about it (`about`): those with one of its telling words in any form ("Clean a Microwave" for
cleaning), or with a telling word of one of the words related to it ("Draw a Bird" for birdwatching). And none of the
worst (`unfit`): none with a word that a slide shouldn't make light of (a faith, violence, hate, death or hard drugs:
see talkgenerator.sources.slide_texts.sensitive). Crude and edgy ones stay, as much of a classic talk's humour is:
"Clean Your Penis" for cleaning, "Hide the Smell of Marijuana Plants" for office plants.
"""

import logging
import re
from functools import cache, lru_cache
from itertools import chain
from typing import Final
from urllib.parse import quote

import inflect
from bs4 import BeautifulSoup
from nltk.stem.snowball import SnowballStemmer

from talkgenerator import settings
from talkgenerator.sources import conceptnet, word_frequency
from talkgenerator.util import http_util, language_util

logger = logging.getLogger("talkgenerator")

_SEARCH_URL = "https://www.wikihow.com/wikiHowTo"

# A how-to's title: "How to Draw a Penguin", or "4 Easy Ways to Draw Cute Cats". WikiHow's search finds other pages
# too, which teach no action: lists ("330 Cool & Unique Names for Penguins"), quizzes, questions ("How Do You Store
# Cheese?") and categories
_HOW_TO: Final = re.compile(r"(?:how to|(?:\d+\s+)?(?:[^\W\d_]+\s+)?ways to)\s+(?P<action>.+)", re.IGNORECASE)

# The words a slide shouldn't make light of (talkgenerator.sources.slide_texts.sensitive) that a how-to may have
# nevertheless: the crude ones, on sex and the body (the second line is the TED content pack's, and "Cook Chicken
# Breasts" with it)
_CRUDE: Final = frozenset(
    ("sex", "sexual", "sexy", "porn", "nude", "naked", "penis", "vagina")
    + ("breast", "breasts", "boob", "boobs", "nipple", "nipples", "genitals")
)
# What tells what a seed is about: its rarest word, and its other words rarer than this on the Zipf scale, so that
# "rainy days" isn't about every day (days: 5.6), nor "school reunions" about school (5.7)
_TELLING: Final = 5.5
# The words related to a seed tell of it too: so many of them (as many as a slide's seed wanders among, see
# talkgenerator.schema.slide_topic_generators), and of their words those rarer than this ("bird", related to
# birdwatching, is 4.6; "clear" and "set", which Datamuse relates to the night bus and office plants, 5.3 and 5.6)
_RELATED_WORDS: Final = 25
_RELATED_TELLING: Final = 5.0
_STEMMER: Final = SnowballStemmer("english")
_WORDS: Final = re.compile(r"[^\W\d_]+")


def action_of(wikihow_title: str) -> str | None:
    """The action a wikiHow page's title teaches ("How to Draw a Penguin": "Draw a Penguin"), without what's in
    brackets or after a colon ("...: 8 Simple Tricks"), or None for a page that isn't a how-to."""
    match = _HOW_TO.fullmatch(" ".join(wikihow_title.split()))
    if match is None:
        return None
    return clean_wikihow_action(match.group("action").split(": ")[0]) or None


def page_of(action: str) -> str:
    """The page of a wikiHow how-to, by its action ("Stop a Goose Attack": https://www.wikihow.com/Stop-a-Goose-Attack),
    as wikiHow names its pages."""
    return "https://www.wikihow.com/" + quote("-".join(action.split()), safe="-")


def clean_wikihow_action(action: str) -> str:
    action = _remove_between_brackets(action)
    action = _remove_trademarks(action)
    action = re.sub(r"\s+", " ", action).strip()
    return action


def _remove_between_brackets(sentence: str) -> str:
    while True:
        s_new = re.sub(r"\([^(]*?\)", r"", sentence)
        if s_new == sentence:
            break
        sentence = s_new
    return sentence


def _remove_trademarks(action: str) -> str:
    if " - wikihow.com" in action:
        return re.sub(" - wikihow.com", "", action)
    return action


@lru_cache(maxsize=64)
def basic_search_wikihow(search_words: str) -> bytes | None:
    response = http_util.get(_SEARCH_URL, params={"search": search_words}, timeout=8)
    if response is None or not response.ok:
        return None
    return response.content


def get_related_wikihow_actions_basic_search(seed_word: str) -> list[str]:
    if not seed_word or not seed_word.strip():
        return []
    page = basic_search_wikihow(seed_word)
    # Try again but with plural if nothing is found
    if not page:
        page = basic_search_wikihow(inflect.engine().plural(seed_word))
    if not page:
        return []

    soup = BeautifulSoup(page, "html.parser")
    actions_elements = soup.find_all("a", class_="result_link")
    action_titles = list(chain.from_iterable([a.find_all("div", class_="result_title") for a in actions_elements]))
    actions = [action_of(x.get_text()) for x in action_titles if x is not None]
    return [action for action in actions if action]


def get_related_wikihow_actions(seed_word: str) -> list[str]:
    """WikiHow's actions about the seed that a slide may make light of (see the module's documentation), from its
    basic search (the advanced search requires logging in)."""
    if settings.is_source_disabled("WIKIHOW"):
        return []
    return list(_actions_about(seed_word))


@lru_cache(maxsize=256)
def _actions_about(seed: str) -> tuple[str, ...]:
    found = dict.fromkeys(get_related_wikihow_actions_basic_search(seed))  # (without repeats, in their order)
    kept = tuple(action for action in found if not unfit(action) and about(action, seed))
    logger.debug("Kept %d of wikiHow's %d actions for '%s': %s", len(kept), len(found), seed, kept)
    return kept


def unfit(action: str) -> bool:
    """Whether an action has a word that a slide shouldn't make light of (a faith, violence, hate, death or hard drugs),
    but for the crude ones ("Make Sex Better" may stay)."""
    from talkgenerator.sources.slide_texts import sensitive  # (here: slide_texts imports what imports this module)

    return any(sensitive(word) for word in _words(action) if word not in _CRUDE)


def about(action: str, seed: str) -> bool:
    """Whether an action is about the seed: it has one of the seed's telling words in any form (by Snowball's stems:
    "Clean a Microwave" for cleaning, "Charge a Car Battery" for batteries), or a telling word of one of the words
    related to the seed, singular or plural ("Draw a Bird" for birdwatching, which Datamuse relates "bird" to)."""
    words = _words(action)
    if {_STEMMER.stem(word) for word in words} & _seed_stems(seed):
        return True
    return bool({_singular(word) for word in words} & _related_words(seed))


@lru_cache(maxsize=256)
def _seed_stems(seed: str) -> frozenset[str]:
    """The stems of the words that tell what a seed is about: its rarest word, and its others rarer than _TELLING,
    leaving out the little ones ("the", "of")."""
    words = _words(seed)
    content = [word for word in words if word not in _little_words()] or words
    if not content:
        return frozenset()
    rarest = min(content, key=word_frequency.get_frequency)
    return frozenset(
        _STEMMER.stem(word) for word in content if word == rarest or word_frequency.get_frequency(word) < _TELLING
    )


@lru_cache(maxsize=256)
def _related_words(seed: str) -> frozenset[str]:
    """The telling words of the words related to a seed (ConceptNet's, or Datamuse's when ConceptNet is down), singular:
    those rarer than _RELATED_TELLING, leaving out the little ones."""
    related = conceptnet.get_weighted_related_words(seed, _RELATED_WORDS) or []
    return frozenset(
        _singular(word)
        for _, entry in related
        for word in _words(str(entry))
        if word not in _little_words() and word_frequency.get_frequency(word) < _RELATED_TELLING
    )


@lru_cache(maxsize=4096)
def _singular(word: str) -> str:
    return language_util.to_singular(word)


@cache
def _little_words() -> frozenset[str]:
    """English's little words ("the", "of"), which tell nothing, or none if NLTK's list can't be had."""
    try:
        return language_util.stopwords("english")
    except (LookupError, OSError, ValueError):
        return frozenset()


def _words(text: str) -> list[str]:
    return _WORDS.findall(text.lower())
