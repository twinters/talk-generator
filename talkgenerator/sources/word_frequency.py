"""Word frequencies, used to find the most specific word in a sentence.

Backed by the offline `wordfreq` package. This replaces the PhraseFinder API (api.phrasefinder.io),
whose domain no longer exists.
"""

import difflib
import re
import unicodedata
from functools import cache, lru_cache
from typing import Final

from wordfreq import top_n_list, zipf_frequency

from talkgenerator.plan.languages import LANGUAGES
from talkgenerator.util import language_util

_KNOWN_WORDS = 50_000  # how many of a language's most frequent words a misspelling is matched against
_LEAST_LIKENESS = 0.85  # (difflib's ratio: "pengiun" is 0.86 like "penguin", "zorblax" 0.83 like "zorba")
# A word rarer than this on the Zipf scale (0.3 in a million words) may be a misspelling of a word one edit away that's
# this much more frequent (a hundred times): misspellings that are common enough have frequencies of their own ("teh")
_RARE = 2.5
_MORE_FREQUENT = 2.0


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


_WORD: Final = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")


def fix_spelling(text: str, language: str = "en") -> str:
    """The text with its misspelled words fixed: every word the language doesn't know (nor English) taken as the
    known word it's most likely a misspelling of, if there's one that close, in the same case ("Pengiuns":
    "Penguins"). Made-up words, such as "Zorblaxia", stay."""
    return _WORD.sub(lambda match: _in_case_of(match.group(), _spelled(match.group(), language)), text)


def _in_case_of(original: str, word: str) -> str:
    if word.casefold() == original.casefold():
        return original
    if original.isupper() and len(original) > 1:
        return word.upper()
    return word[:1].upper() + word[1:] if original[:1].isupper() else word


def _spelled(word: str, language: str) -> str:
    """The word, or the known word it's most likely a misspelling of: for a rare word (or one the language doesn't
    know, nor English), the most frequent word one edit away (a letter left out, two swapped, one changed or one
    added) that's at least a hundred times more frequent ("waht" is "what", "teh" "the", "pengiun" "penguin"); or
    else, for a word no language knows, one of the language's most frequent words that starts with the same letter,
    is about as long and is mostly the same letters ("airplain": "airplane").

    In another language than English, a word of that language (one it knows at least as well as English does) is
    only taken as the same word with its accents put right ("faglar": "fåglar"), never as another word of it, nor as
    an English one: it's a rare word, but a word ("matare", Swedish for a feeder, isn't "mature"; and D74: "polvos",
    Portuguese octopuses, isn't "povos", peoples, Swedish "lämlar", lemmings, isn't "lämnar", leaves, nor Dutch
    "verkeerskegels", traffic cones, "verkeersregels", the rules of the road). In a language that writes compounds as
    one word (Dutch, German and Swedish), a word no language knows that's two of its words put together is a compound,
    and no near match ("tomatbok", a book of tomatoes, isn't "tomato", nor is "robotarmé" "robotar"); one a single
    edit away from a known word is still taken as it ("kvallens": "kvällens")."""
    frequency = _frequency(word, language)
    if len(word) < 3 or frequency >= _RARE:
        return word
    lowered = word.casefold()
    own = language != "en" and _own(lowered, language)
    languages = (language, "en") if language != "en" else ("en",)
    known = frozenset().union(*(_known_set(each) for each in languages))
    edited = [
        candidate
        for candidate in sorted(_edits(lowered) & known)
        if _frequency(candidate, language) >= frequency + _MORE_FREQUENT
        and (not own or (_own(candidate, language) and _unaccented(candidate) == _unaccented(lowered)))
    ]
    if edited:  # (the likest first, "joined" before "join" for "joind"; then the most frequent, "what" for "waht")
        return max(
            edited,
            key=lambda candidate: (
                round(difflib.SequenceMatcher(None, lowered, candidate).ratio(), 2),
                _frequency(candidate, language),
            ),
        )
    if frequency > 0:
        return word  # (a rare word, but a word)
    if _compounding(language) and _compound(lowered, language):
        return word
    pool = [
        candidate
        for each in languages
        for candidate in _known_words(each)
        if candidate[:1] == lowered[:1] and abs(len(candidate) - len(lowered)) <= 2
    ]
    matches = difflib.get_close_matches(lowered, pool, n=1, cutoff=_LEAST_LIKENESS)
    return matches[0] if matches else word


def _own(word: str, language: str) -> bool:
    """Whether a word is one of the language's own: one it knows at least as well as English does."""
    frequency = get_frequency(word, language)
    return frequency > 0 and frequency >= get_frequency(word)


def _unaccented(word: str) -> str:
    """The word without its accents ("fåglar": "faglar")."""
    return "".join(
        character for character in unicodedata.normalize("NFKD", word) if not unicodedata.combining(character)
    )


def _compounding(language: str) -> bool:
    """Whether the language writes compounds as one word, as Dutch, German and Swedish do."""
    found = LANGUAGES.get(language)
    return found is not None and found.compounds


_LEAST_HEAD: Final = 2  # the shortest words a compound is taken to start with ("is" in "isrobot", an ice robot)
_LEAST_TAIL: Final = 3  # and to end with ("bok" in "tomatbok")


@lru_cache(maxsize=4096)
def _compound(word: str, language: str) -> bool:
    """Whether a word (in lower case) is two or more of the language's words put together, as Dutch, German and
    Swedish make them ("pingvinsekt", "tomatbok"): words among its most frequent, at least one of them more its own
    than English's (its lists hold English words too, and two of those make no compound of it). The first may be
    joined to the rest with an "s" ("kärnkraftsolycka"), or lose its last "e" or "a" ("spökarmé", of "spöke" and
    "armé")."""
    for split in range(_LEAST_HEAD, len(word) - _LEAST_TAIL + 1):
        head, tail = word[:split], word[split:]
        if not _part(tail, language):
            continue
        heads = [head, head + "e", head + "a"]
        if head.endswith("s") and split > _LEAST_HEAD:
            heads.append(head[:-1])
        if any(_part(each, language) and (_own_part(each, language) or _own_part(tail, language)) for each in heads):
            return True
    return False


def _part(word: str, language: str) -> bool:
    """Whether a word can be a part of a compound in the language: one of its most frequent words, or a compound."""
    return word in _known_set(language) or _compound(word, language)


def _own_part(word: str, language: str) -> bool:
    """Whether a part of a compound is the language's own: its own word, or a compound (of which one word is)."""
    return _own(word, language) or (word not in _known_set(language) and _compound(word, language))


_LETTERS: Final = "abcdefghijklmnopqrstuvwxyzàáâäåçèéêëìíîïñòóôöùúûü"


def _edits(word: str) -> set[str]:
    """The strings one edit away from the word: a letter left out, two letters swapped, one changed or one added."""
    splits = [(word[:index], word[index:]) for index in range(len(word) + 1)]
    return {
        *(left + right[1:] for left, right in splits if right),
        *(left + right[1] + right[0] + right[2:] for left, right in splits if len(right) > 1),
        *(left + letter + right[1:] for left, right in splits if right for letter in _LETTERS),
        *(left + letter + right for left, right in splits for letter in _LETTERS),
    }


@cache
def _known_words(language: str) -> tuple[str, ...]:
    return tuple(word for word in top_n_list(language, _KNOWN_WORDS) if word.isalpha())


@cache
def _known_set(language: str) -> frozenset[str]:
    return frozenset(_known_words(language))
