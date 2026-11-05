"""Related words from the Datamuse API (https://www.datamuse.com/api/).

Datamuse is free and keyless (fair use: up to 100,000 requests per day). talkgenerator uses it
as the stand-in for ConceptNet whenever the ConceptNet API can't be reached, which has been the
case since late 2025. All functions return (weight, word) pairs, with weights scaled to (0, 10]
so they mix well with ConceptNet edge weights.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from talkgenerator.util import http_util, language_util, random_util

API_URL = "https://api.datamuse.com/words"

logger = logging.getLogger("talkgenerator.datamuse")

# Everyday places used to pad "where can you find X?" answers when the data has too few of its own.
_GENERIC_PLACES = (
    "home",
    "the office",
    "the kitchen",
    "the garden",
    "under the bed",
    "the internet",
    "the supermarket",
    "the basement",
    "grandma's attic",
    "the zoo",
    "the beach",
    "the park",
    "the library",
    "outer space",
)


@lru_cache(maxsize=512)
def _query(relation: str, word: str, max_results: int) -> tuple[tuple[str, int], ...]:
    data = http_util.get_json(API_URL, params={relation: word, "max": max_results})
    if not isinstance(data, list):
        return ()
    return tuple((entry["word"], int(entry.get("score", 0))) for entry in data if entry.get("word"))


def query(relation: str, word: str, max_results: int = 50) -> list[tuple[float, str]]:
    """Run a Datamuse query (e.g. relation "rel_trg" for "triggers") and return (weight, word) pairs."""
    word = (word or "").strip().lower()
    if not word:
        return []
    results = _query(relation, word, max_results)
    if not results:
        return []
    top_score = max(score for _, score in results) or 1
    return [(max(0.1, round(10 * score / top_score, 3)), result) for result, score in results]


def _without_word_itself(word: str, weighted_words: list[tuple[float, str]]) -> list[tuple[float, str]]:
    word = word.strip().lower()
    return [(weight, other) for weight, other in weighted_words if word not in other and other not in word]


def related_words(word: str, limit: int = 50) -> list[tuple[float, str]]:
    """Words associated with the given word ("triggers"), topped up with similar-meaning words."""
    results = _without_word_itself(word, query("rel_trg", word, limit))
    if len(results) < 5:
        seen = {other for _, other in results}
        similar = _without_word_itself(word, query("ml", word, limit))
        results += [(weight / 2, other) for weight, other in similar if other not in seen]
    if not results and " " in word.strip():
        # For multi-word topics, fall back on associations with the last (usually main) word
        return related_words(word.strip().split(" ")[-1], limit)
    return results[:limit]


def describing_adjectives(word: str, limit: int = 50) -> list[tuple[float, str]]:
    """Adjectives that are often used to describe the word, e.g. "cat" -> "black", "wild"."""
    return query("rel_jjb", word, limit)


def antonyms(word: str, limit: int = 50) -> list[tuple[float, str]]:
    return query("rel_ant", word, limit)


def parts(word: str, limit: int = 50) -> list[tuple[float, str]]:
    """Things the word consists of (meronyms), e.g. "car" -> "engine"."""
    return query("rel_com", word, limit)


def places(word: str, limit: int = 50) -> list[tuple[float, str]]:
    """Places where you might find the word, padded with generic everyday places.

    Datamuse has no "location" relation, so this keeps the words associated with the topic that
    WordNet considers to be places or containers ("fish" -> "pond", "aquarium", "reef").
    """
    found = []
    seen = set()
    for weight, candidate in related_words(word, 100):
        if candidate not in seen and language_util.is_place(candidate):
            seen.add(candidate)
            found.append((weight, candidate))
    if len(found) < 4:
        padding = [place for place in _GENERIC_PLACES if place not in seen]
        found += [(round(random_util.uniform(1, 4), 3), place) for place in random_util.sample(padding, 4 - len(found))]
    return found[:limit]
