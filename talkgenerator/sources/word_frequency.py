"""Word frequencies, used to find the most specific word in a sentence.

Backed by the offline `wordfreq` package. This replaces the PhraseFinder API (api.phrasefinder.io),
whose domain no longer exists.
"""

from functools import lru_cache

from wordfreq import zipf_frequency

from talkgenerator.util import language_util


@lru_cache(maxsize=4096)
def get_frequency(word: str) -> float:
    """Frequency of a word in English on the Zipf scale: about 7 for "the", 3 for rare words, 0 if unknown."""
    return zipf_frequency(word, "en")


def get_rarest_word(sentence: str | None) -> str | None:
    """The least common word of a sentence (unknown words count as the rarest), or None if it has no words."""
    if not sentence:
        return None
    words = [language_util.replace_non_alphabetical_characters(word).strip() for word in sentence.split(" ")]
    words = [word for word in words if any(character.isalpha() for character in word)]
    if not words:
        return None
    return min(words, key=get_frequency)
