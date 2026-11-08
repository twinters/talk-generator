"""What talkgenerator asks WordNet: whether a noun's most common meaning is a place (or a container), and whether a
word is an adjective. The answers are NLTK's (wordnet.synsets with its morphy), from the same WordNet files.

NLTK's WordNet reader keeps an index of all 147,000 lemmas in memory, as Python objects (about 130 MB), and the data
files it reads, whole (20 MB more): more than half of what talkgenerator.com's server used at rest, for two questions.
So this reads WordNet's files once, as they're found in NLTK's data (the corpus's zip, or its folder), line by line,
and keeps only what the two questions need: the noun and adjective lemmas and the nouns whose most common meaning is a
place, as sorted arrays of their hashes (about 1 MB), and the irregular forms (noun.exc and adj.exc). Reading them
takes a second or two, once per process (a server's warm-up can do it: see load).
"""

from __future__ import annotations

import io
import threading
import zipfile
from array import array
from bisect import bisect_left
from collections.abc import Collection, Container, Iterable, Iterator
from dataclasses import dataclass
from typing import Final

# The WordNet categories (synsets, by their names) whose members make sense as an answer to "where can you find X?".
# Countries and regions are left out on purpose: they're rarely related to the topic.
PLACE_CATEGORIES: Final = frozenset(
    {
        "structure.n.01",  # buildings, bridges, pens, ...
        "room.n.01",
        "container.n.01",  # boxes, bags, bottles, tins, ...
        "furniture.n.01",
        "body_of_water.n.01",
        "geological_formation.n.01",
        "establishment.n.04",  # shops, hotels, ...
        "facility.n.01",
        "tract.n.01",  # fields, gardens, parks, forests, ...
        "way.n.06",  # roads, paths, streets, ...
    }
)

# How NLTK's morphy finds a word's lemmas: (ending, what it becomes), tried on a form that isn't an irregular one
_NOUN_RULES: Final = (
    ("s", ""),
    ("ses", "s"),
    ("ves", "f"),
    ("xes", "x"),
    ("zes", "z"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("men", "man"),
    ("ies", "y"),
)
_ADJECTIVE_RULES: Final = (("er", ""), ("est", ""), ("er", "e"), ("est", "e"))
_HYPERNYMS: Final = frozenset({"@", "@i"})  # (hypernym_paths follows instance hypernyms too)


class Hashes:
    """A set of words, as a sorted array of their hashes: 8 bytes a word (a frozenset of strings takes ten times as
    much). The hashes are this process's own; two words that share one (a chance of one in billions) count as one."""

    def __init__(self, words: Iterable[str]) -> None:
        self._hashes = array("q", sorted({hash(word) for word in words}))

    def __contains__(self, word: object) -> bool:
        key = hash(word)
        index = bisect_left(self._hashes, key)
        return index < len(self._hashes) and self._hashes[index] == key

    def __len__(self) -> int:
        return len(self._hashes)


@dataclass(frozen=True)
class _Lexicon:
    nouns: Hashes
    places: Hashes  # (the nouns whose first meaning is a place)
    adjectives: Hashes
    noun_exceptions: dict[str, tuple[str, ...]]
    adjective_exceptions: dict[str, tuple[str, ...]]


_lexicon: _Lexicon | None = None
_lock = threading.Lock()


def is_place(word: str) -> bool:
    """Whether the most common meaning of a noun is a place or a container, as NLTK's wordnet.synsets(word, NOUN)[0]
    has one of PLACE_CATEGORIES among its hypernym paths. A LookupError without WordNet."""
    lexicon = load()
    forms = _morphy(_lemma(word), lexicon.nouns, lexicon.noun_exceptions, _NOUN_RULES)
    return bool(forms) and forms[0] in lexicon.places


def is_adjective(word: str) -> bool:
    """Whether WordNet knows the word (or phrase) as an adjective, as NLTK's wordnet.synsets(word, ADJ) does. A
    LookupError without WordNet."""
    lexicon = load()
    return bool(_morphy(_lemma(word), lexicon.adjectives, lexicon.adjective_exceptions, _ADJECTIVE_RULES))


def load() -> _Lexicon:
    """Read what the questions need from WordNet's files, once (a LookupError if NLTK's data has no WordNet)."""
    global _lexicon
    with _lock:
        if _lexicon is None:
            _lexicon = _read()
        return _lexicon


def _lemma(word: str) -> str:
    return word.strip().replace(" ", "_").lower()


def _morphy(
    form: str, lemmas: Container[str], exceptions: dict[str, tuple[str, ...]], rules: tuple[tuple[str, str], ...]
) -> list[str]:
    """The lemmas the form can be of, as NLTK's morphy finds them (NLTK 3.9 and later): the form itself, then its
    irregular lemmas if it's an irregular form, or else what each rule makes of it; those WordNet has, without
    repeats."""
    if form in exceptions:
        candidates = [form, *exceptions[form]]
    else:
        candidates = [form] + [form[: -len(old)] + new for old, new in rules if form.endswith(old)]
    found: list[str] = []
    for candidate in candidates:
        if candidate not in found and candidate in lemmas:
            found.append(candidate)
    return found


def _read() -> _Lexicon:
    # (what's kept is read first, so that it isn't scattered among what's read only to work the places out, which
    # then goes back to the system as a whole)
    noun_exceptions, adjective_exceptions = _exceptions("noun.exc"), _exceptions("adj.exc")
    noun_offsets = _index("index.noun")
    adjectives = Hashes(_index("index.adj"))
    # The place categories' synsets: their lemma's sense, if that's the synset's first lemma (as NLTK names a synset)
    categories: dict[int, str] = {}
    for name in PLACE_CATEGORIES:
        lemma, _, sense = name.rsplit(".", 2)
        offsets = noun_offsets.get(lemma, ())
        if 0 < int(sense) <= len(offsets):
            categories[offsets[int(sense) - 1]] = lemma
    parents, first_lemmas = _hypernyms(categories)
    category_offsets = {offset for offset, lemma in categories.items() if first_lemmas.get(offset) == lemma}
    places: dict[int, bool] = {}

    def is_a_place(offset: int) -> bool:
        if offset not in places:
            places[offset] = False  # (while it's worked out: WordNet's noun hypernyms have no cycles anyway)
            places[offset] = offset in category_offsets or any(is_a_place(parent) for parent in parents.get(offset, ()))
        return places[offset]

    return _Lexicon(
        nouns=Hashes(noun_offsets),
        places=Hashes(lemma for lemma, offsets in noun_offsets.items() if is_a_place(offsets[0])),
        adjectives=adjectives,
        noun_exceptions=noun_exceptions,
        adjective_exceptions=adjective_exceptions,
    )


def _index(name: str) -> dict[str, tuple[int, ...]]:
    """An index file's lemmas, with their synsets' offsets (the most common meaning first)."""
    lemmas: dict[str, tuple[int, ...]] = {}
    for line in _lines(name):
        if line.startswith(" "):  # (the license)
            continue
        fields = line.split()
        count, pointers = int(fields[2]), int(fields[3])
        start = 4 + pointers + 2
        lemmas[fields[0]] = tuple(int(offset) for offset in fields[start : start + count])
    return lemmas


def _hypernyms(wanted: Collection[int]) -> tuple[dict[int, tuple[int, ...]], dict[int, str]]:
    """Every noun synset's hypernyms (and instance hypernyms), by offset; and the first lemma of the wanted ones."""
    parents: dict[int, tuple[int, ...]] = {}
    first_lemmas: dict[int, str] = {}
    for line in _lines("data.noun"):
        if line.startswith(" "):
            continue
        fields = line.split(" | ", 1)[0].split()
        offset, words = int(fields[0]), int(fields[3], 16)
        if offset in wanted:
            first_lemmas[offset] = fields[4].lower()
        # (the pointers' count, then each pointer: its symbol, offset, part of speech, source/target)
        at = 4 + 2 * words
        pointers = range(at + 1, at + 1 + 4 * int(fields[at]), 4)
        found = [int(fields[pointer + 1]) for pointer in pointers if fields[pointer] in _HYPERNYMS]
        if found:
            parents[offset] = tuple(found)
    return parents, first_lemmas


def _exceptions(name: str) -> dict[str, tuple[str, ...]]:
    """An exception list's irregular forms, with their lemmas ("geese": ("goose",))."""
    exceptions: dict[str, tuple[str, ...]] = {}
    for line in _lines(name):
        fields = line.split()
        if fields:
            exceptions[fields[0]] = tuple(fields[1:])
    return exceptions


def _lines(name: str) -> Iterator[str]:
    """The lines of one of WordNet's files in NLTK's data, from its folder or from its zip (unpacked as it's read)."""
    import nltk  # noqa: PLC0415 (only to find the files, where NLTK looks for them)

    pointer = nltk.data.find(f"corpora/wordnet/{name}")
    if isinstance(pointer, nltk.data.ZipFilePathPointer):
        with zipfile.ZipFile(pointer.zipfile.filename) as archive, archive.open(pointer.entry) as member:
            yield from io.TextIOWrapper(member, encoding="utf-8")
    else:
        with open(pointer.path, encoding="utf-8") as file:
            yield from file
