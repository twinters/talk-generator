"""Word frequencies, used to find the most specific word in a sentence.

Backed by the offline `wordfreq` package. This replaces the PhraseFinder API (api.phrasefinder.io),
whose domain no longer exists.
"""

import difflib
import re
from functools import cache, lru_cache

from wordfreq import top_n_list, zipf_frequency

from talkgenerator.util import language_util

_KNOWN_WORDS = 50_000  # how many of a language's most frequent words a misspelling is matched against
_LEAST_LIKENESS = 0.85  # (difflib's ratio: "pengiun" is 0.86 like "penguin", "zorblax" 0.83 like "zorba")


@lru_cache(maxsize=4096)
def get_frequency(word: str, language: str = "en") -> float:
    """Frequency of a word in the language (English by default) on the Zipf scale: about 7 for "the", 3 for rare
    words, 0 if unknown."""
    return zipf_frequency(word, language)


def _frequency(word: str, language: str) -> float:
    """How frequent a word is in a sentence in the language: in another language than English, a word may be
    English, too (as words of a title often are)."""
    if language == "en":
        return get_frequency(word)
    return max(get_frequency(word, language), get_frequency(word))


def get_rarest_word(sentence: str | None, language: str = "en", fix_spelling: bool = False) -> str | None:
    """The least common word of a sentence in its language (unknown words count as the rarest), or None if it has no
    words. In another language than English, words keep their accents ("pinguïns"). With fix_spelling, a word the
    language doesn't know is taken as the known word it's most likely a misspelling of, if there's one that close
    ("pengiun": "penguin"; a made-up word such as "Zorblaxia" stays)."""
    if not sentence:
        return None
    clean = language_util.replace_non_alphabetical_characters if language == "en" else _letters
    words = [clean(word).strip() for word in sentence.split(" ")]
    words = [word for word in words if any(character.isalpha() for character in word)]
    if fix_spelling:
        words = [_spelled(word, language) for word in words]
    if not words:
        return None
    return min(words, key=lambda word: _frequency(word, language))


def _letters(word: str) -> str:
    """The word without what isn't a letter, a hyphen or an apostrophe (in any alphabet)."""
    return re.sub(r"[^\w'’-]|[\d_]", "", word)


def _spelled(word: str, language: str) -> str:
    """The word, or the known word it's most likely a misspelling of, when the language doesn't know it: one of the
    language's most frequent words (or English's) that starts with the same letter and is about as long."""
    if _frequency(word, language) > 0:
        return word
    lowered = word.casefold()
    pool = [
        known
        for known in _known_words(language) + (_known_words("en") if language != "en" else ())
        if known[:1] == lowered[:1] and abs(len(known) - len(lowered)) <= 2
    ]
    matches = difflib.get_close_matches(lowered, pool, n=1, cutoff=_LEAST_LIKENESS)
    return matches[0] if matches else word


@cache
def _known_words(language: str) -> tuple[str, ...]:
    return tuple(word for word in top_n_list(language, _KNOWN_WORDS) if word.isalpha())
