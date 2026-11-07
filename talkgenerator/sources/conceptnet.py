"""Related concepts for a word: ConceptNet when it's reachable, Datamuse + WordNet otherwise.

The public ConceptNet API (api.conceptnet.io) has been answering with HTTP 502 since late 2025
(https://github.com/commonsense/conceptnet5/issues/341). When a request fails, this module
stops calling ConceptNet for a while and answers the same questions with Datamuse instead, so
the functions below always return a (possibly empty) list and never None.

Settings (environment variables or .env):
    CONCEPTNET_API_URL    Base URL of a (self-hosted) ConceptNet API (default: https://api.conceptnet.io)
    DISABLE_CONCEPTNET=1  Skip ConceptNet altogether and always use the fallback
"""

import logging
import time
from functools import lru_cache
from urllib.parse import quote, urlencode

from talkgenerator import settings
from talkgenerator.sources import datamuse
from talkgenerator.util import cache_util, generator_util, http_util

_LOCATION_ARGUMENTS = cache_util.HashableDict(rel="/r/AtLocation", limit=100)
_HASA_ARGUMENTS = cache_util.HashableDict(rel="/r/HasA", limit=200)
_DEFAULT_ARGUMENTS = cache_util.HashableDict(limit=200)

_UNAVAILABLE_COOLDOWN_SECONDS = 15 * 60
_REQUEST_TIMEOUT_SECONDS = 8

# HELPERS
_PROHIBITED_SEARCH_TERMS = (
    "a",
    "your",
    "my",
    "her",
    "his",
    "its",
    "their",
    "be",
    "an",
    "the",
    "you",
    "are",
)

logger = logging.getLogger("talkgenerator.conceptnet")

_cooldown = http_util.Cooldown("ConceptNet API")


class _ConceptNetUnavailable(Exception):
    pass


class _CoolingDown(Exception):
    """A word ConceptNet wasn't asked about before, while it's skipped for a while (see _cooldown)."""


# Helpers
def _remove_prohibited_words(word):
    return [part for part in word.split(" ") if part not in _PROHIBITED_SEARCH_TERMS]


def normalise(word):
    return " ".join(_remove_prohibited_words(word)).lower()


def remove_duplicates(entries):
    if entries:
        checked = set()
        result = []
        for entry in entries:
            if entry:
                key = entry[1]
                if key in checked:
                    continue
                checked.add(key)
                result.append(entry)
        return result


def remove_containing(entries, prohibited_word):
    if entries:
        result = []
        for entry in entries:
            if entry:
                key = entry[1]
                if prohibited_word in key:
                    continue
                result.append(entry)
        return result


def remove_nones(entries):
    if entries:
        return [entry for entry in entries if entry]
    return []


# RETRIEVING DATA


@lru_cache(maxsize=256)
def _fetch_edges(word, arguments):
    """Edges of a ConceptNet node. Failures raise instead of returning, so they aren't cached. While ConceptNet is
    skipped for a while (see _cooldown), only what it answered before will do: from memory, or the on-disk cache."""
    search_term = "_".join(_remove_prohibited_words(word.lower()))
    url = "{}/c/en/{}?{}".format(settings.conceptnet_api_url(), quote(search_term), urlencode(arguments, safe="/"))
    start = time.perf_counter()
    cooling = _cooldown.active
    response = http_util.get(url, timeout=_REQUEST_TIMEOUT_SECONDS, cached_only=cooling)
    logger.debug("Took %.2f seconds to poll ConceptNet for '%s'", time.perf_counter() - start, word)
    if response is None and cooling:
        raise _CoolingDown
    if response is None:
        raise _ConceptNetUnavailable("no response")
    if not response.ok:
        raise _ConceptNetUnavailable(f"HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        raise _ConceptNetUnavailable("invalid JSON response") from None
    if "error" in data:
        logger.info("ConceptNet has no result for '%s': %s", word, data["error"])
        return ()
    return tuple(data.get("edges", ()))


def _get_edges(word, arguments=None):
    """ConceptNet edges for a word, or None if ConceptNet can't be used right now."""
    if not word or not word.strip() or settings.is_source_disabled("CONCEPTNET"):
        return None
    try:
        return _fetch_edges(word, arguments or _DEFAULT_ARGUMENTS)
    except _CoolingDown:
        return None
    except _ConceptNetUnavailable as e:
        _cooldown.trigger(_UNAVAILABLE_COOLDOWN_SECONDS, f"{e}; using Datamuse and WordNet instead")
        return None


def _get_weight_and_word(edge, word):
    end_label = edge["end"]["label"]
    if not end_label == word:
        return edge["weight"], end_label


def _get_relation_label(edge):
    return edge["rel"]["label"]


def _get_from_relation(word, edges, relation_name):
    return remove_nones(
        [_get_weight_and_word(edge, word) for edge in edges if _get_relation_label(edge) == relation_name]
    )


# EXTRACTING INFO


def is_english(node):
    return node and ("language" not in node or node["language"] == "en")


def is_different_enough_label(edge, word):
    label = edge["label"].lower()
    word_lower = word.lower()
    return label not in word_lower and word_lower not in label


def get_weighted_related_words(word, limit=50):
    edges = _get_edges(word, cache_util.HashableDict(limit=limit))
    if edges is None:
        return datamuse.related_words(word, limit)
    starts = [
        (edge["weight"], edge["start"]["label"])
        for edge in edges
        if is_different_enough_label(edge["start"], word) and is_english(edge["start"])
    ]
    ends = [
        (edge["weight"], edge["end"]["label"])
        for edge in edges
        if is_different_enough_label(edge["end"], word) and is_english(edge["end"])
    ]
    return starts + ends


def get_weighted_related_locations(word):
    edges = _get_edges(word, _LOCATION_ARGUMENTS)
    if edges is None:
        return datamuse.places(word)
    return _get_from_relation(word, edges, "AtLocation")


def get_weighted_has(word):
    edges = _get_edges(word, _HASA_ARGUMENTS)
    if edges is None:
        return datamuse.parts(word)
    return _get_from_relation(word, edges, "HasA")


def get_weighted_properties(word):
    edges = _get_edges(word)
    if edges is None:
        return datamuse.describing_adjectives(word)
    return _get_from_relation(word, edges, "HasProperty")


def get_weighted_antonyms(word):
    edges = _get_edges(word)
    if edges is None:
        return datamuse.antonyms(word)
    return _get_from_relation(word, edges, "Antonym")


# Weighted
weighted_location_generator = generator_util.WeightedGenerator(get_weighted_related_locations)
weighted_antonym_generator = generator_util.WeightedGenerator(get_weighted_antonyms)
weighted_related_word_generator = generator_util.WeightedGenerator(get_weighted_related_words)

# Unweighted
unweighted_location_generator = generator_util.UnweightedGenerator(get_weighted_related_locations)
unweighted_antonym_generator = generator_util.UnweightedGenerator(get_weighted_antonyms)
unweighted_related_word_generator = generator_util.UnweightedGenerator(get_weighted_related_words)
