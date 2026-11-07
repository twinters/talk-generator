"""The presenter's name on a talk's title slide, when nobody gives one (docs/v5-plan.md, section 5.10).

A name comes in a style, which the talk's dice pick among the styles that are switched on (talk-generator-web offers
them as settings: see catalog):

- pun: a pun on the talk's topic, such as "Prof. Anna Tomy" for a talk on medicine;
- fun_surname: an ordinary first name with a surname that fits the topic a little too well, such as "Linda
  Hivesworth" for a talk on bees;
- famous_pun: a historical figure's name bent to fit the topic, such as "Albert Einstone" for geology (never a real
  name as it is, nor a living person's or a dictator's);
- classic: a first and a last name at random (tracery's full_name), as talkgenerator made them up in 2019.

A name the user gives (generate_presentation's presenter) always goes first, and never goes to a language model.
Otherwise, in a talk a language model writes, the model writes the name too, in the same request: in the talk's
spine, in the talk's language, before the presenter's job, which agrees with it. A talk without a language model, or
whose model doesn't write a name that will do (see clean), gets one of talkgenerator's own: a name of its pack
(PACK_FILE, drafted with a language model, to be curated by hand) in a switched-on style that has names for the
talk's topic, or else a classic one. The pack is English, as classic talks are. The model is shown two of its names
for other topics, with what they play on ("'Anna Tomy' (anatomy) for medicine").
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cache, lru_cache
from typing import Any, Final

from talkgenerator.checks.deck import leftovers_in
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import PRESENTER_NAME
from talkgenerator.plan.realize import length_limit
from talkgenerator.util import language_util, os_util, random_util

logger = logging.getLogger("talkgenerator")

PUN: Final = "pun"
FUN_SURNAME: Final = "fun_surname"
FAMOUS_PUN: Final = "famous_pun"
CLASSIC: Final = "classic"

PACK_FILE: Final = "data/text-templates/presenter_names.json"


@dataclass(frozen=True)
class Style:
    name: str
    label: str  # for a settings menu
    description: str  # what its names are like, for a settings menu
    asked: str  # what a language model is asked to write (before the examples); none for the classic names
    # What the model works out first, in a field of its own before the name (name_plays_on), which helps the free
    # models make a pun instead of a name that only fits
    plays_on: str = ""
    default: bool = True  # whether talks that don't say which styles they may have get it


STYLES: Final[dict[str, Style]] = {
    style.name: style
    for style in (
        Style(
            PUN,
            "Pun names",
            "a pun on the topic, such as Prof. Anna Tomy for a talk on medicine",
            "a made-up name for the presenter that, read aloud, sounds like a word or phrase about the talk's topic "
            "(a pun on the whole name, not just a surname that fits)",
            "the word or phrase about the talk's topic that the presenter's name will sound like",
        ),
        Style(
            FUN_SURNAME,
            "Fun surnames",
            "an ordinary first name with a surname that fits the topic too well, such as Linda Hivesworth for bees",
            "a made-up name for the presenter: an ordinary first name with a surname that fits the talk's topic a "
            "little too well",
            "the word about the talk's topic that the presenter's surname will be made from",
        ),
        Style(
            FAMOUS_PUN,
            "Famous-name puns",
            "a historical figure's name bent to fit the topic, such as Albert Einstone for geology",
            "a made-up name for the presenter: the name of one famous historical figure that everyone knows, with a "
            "part of it changed into a word about the talk's topic, so that both still show; never the real name as "
            "it is, and never the name of a living person, a dictator or a criminal",
            "the famous historical figure whose name the presenter's name will bend, and the word about the talk's "
            "topic that goes into it",
        ),
        Style(CLASSIC, "Random names", "a first and a last name at random, as in 2019", "", default=False),
    )
}
DEFAULT_STYLES: Final = tuple(name for name, style in STYLES.items() if style.default)


def catalog() -> list[dict[str, Any]]:
    """The name styles, for a settings menu (talk-generator-web's, say): each with its name (what styles takes), a
    label, a line on what its names are like, and whether talks that don't say get it. A name the user types is no
    style: it's generate_presentation's presenter, which always goes first."""
    return [
        {"name": style.name, "label": style.label, "description": style.description, "default": style.default}
        for style in STYLES.values()
    ]


def styles(chosen: str | Iterable[str] | None = None) -> tuple[str, ...]:
    """The name styles a talk may have, from their names (in any order), or from one string with their names
    separated by commas ("pun,classic"): in the order of STYLES, so the order they're given in doesn't change a talk.
    None gives the default ones; none at all, classic names only. A ValueError for a style there isn't."""
    if chosen is None:
        return DEFAULT_STYLES
    parts = chosen.split(",") if isinstance(chosen, str) else list(chosen)
    wanted = {part.strip().lower() for part in parts if part.strip()}
    unknown = sorted(wanted - set(STYLES))
    if unknown:
        raise ValueError(f"There's no name style {unknown[0]!r}; there are {', '.join(STYLES)}")
    return tuple(name for name in STYLES if name in wanted)


# TALKGENERATOR'S OWN NAMES


@dataclass(frozen=True)
class PackEntry:
    """Names of the pack in a style, for a topic, with what each plays on (a pun's word, a famous name's owner)."""

    style: str
    topic: str  # what its names are for, as a prompt's examples say it ("medicine")
    words: tuple[tuple[str, ...], ...]  # the words and phrases of the topics it fits, as lists of words
    names: tuple[str, ...]
    plays_on: tuple[str, ...]  # per name ("anatomy" for "Anna Tomy"), or "" (a fun surname is plain to see)

    def fits(self, topics: Sequence[str]) -> bool:
        """Whether a talk on the topics fits it: one of them holds one of its words or phrases (word for word,
        ignoring case: "geese" holds "goose", whose singular it is, but "die" doesn't hold "dice")."""
        return any(_holds(_words(topic), phrase) for topic in topics for phrase in self.words)


@cache
def pack() -> tuple[PackEntry, ...]:
    """talkgenerator's own names (PACK_FILE), by style and topic. In the file, a name is followed by what it plays
    on, if anything, after " = " ("Anna Tomy = anatomy")."""
    with open(os_util.to_actual_file(PACK_FILE), encoding="utf-8") as file:
        data = json.load(file)
    entries = []
    for style in STYLES:
        for entry in data.get(style, ()):
            names, plays_on = zip(*(str(name).partition(" = ")[::2] for name in entry["names"]), strict=True)
            words = tuple(tuple(_words(str(word))) for word in entry["words"])
            entries.append(PackEntry(style, str(entry["topic"]), words, names, plays_on))
    return tuple(entries)


_WORD: Final = re.compile(r"[^\W_]+")


def _words(text: str) -> list[str]:
    return [word.casefold() for word in _WORD.findall(text)]


@lru_cache(maxsize=4096)
def _forms(word: str) -> frozenset[str]:
    """A word, and its singular when it's an English plural ("geese": "goose" too)."""
    return frozenset({word, language_util.to_singular(word)})


def _holds(words: Sequence[str], phrase: Sequence[str]) -> bool:
    """Whether the words hold the phrase, word for word: each as it is, or in the singular (the phrase's words are in
    the singular, as the pack has them)."""
    size = len(phrase)
    return size > 0 and any(
        all(phrase[offset] in _forms(words[start + offset]) for offset in range(size))
        for start in range(len(words) - size + 1)
    )


def classic(rng: random_util.Rng) -> str:
    """A classic name: a first and a last name at random, as talkgenerator made up names in 2019 (tracery's
    full_name), drawn from the talk's "presenter" stream, as before there were styles: a seed keeps its name."""
    from talkgenerator.schema.content_generators import full_name_generator  # (here: it loads every source)

    with random_util.use(rng.child("presenter")):
        return str(full_name_generator())


def from_pack(topics: Sequence[str], chosen: Sequence[str], rng: random_util.Rng) -> str:
    """The name of a talk whose presenter no language model names (a classic talk, or one whose model didn't write a
    name that will do): a name of the pack in a chosen style that has names for one of the talk's topics, or else a
    classic name. The talk's dice pick the style among those (and the classic names, when they're chosen), and then
    one of its names."""
    fitting = [entry for entry in pack() if entry.style in chosen and entry.fits(topics)]
    options = [style for style in STYLES if style in chosen and (style == CLASSIC or _has_names(fitting, style))]
    with random_util.use(rng.child("presenter", "pack")):
        style = random_util.choice(options) if options else CLASSIC
        if style != CLASSIC:
            return random_util.choice([name for entry in fitting if entry.style == style for name in entry.names])
    return classic(rng)


def _has_names(entries: Sequence[PackEntry], style: str) -> bool:
    return any(entry.style == style for entry in entries)


# NAMES A LANGUAGE MODEL WRITES


@dataclass(frozen=True)
class Example:
    """A name of the pack that a language model is shown: for which topic, and what it plays on (if anything)."""

    name: str
    topic: str
    plays_on: str = ""

    def __str__(self) -> str:
        return f"'{self.name}'{f' ({self.plays_on})' if self.plays_on else ''} for {self.topic}"


@dataclass(frozen=True)
class NameRequest:
    """What the language model that writes a talk is asked for its presenter's name: a name in a style, like the
    examples it's shown (names of the pack for other topics than the talk's, which aren't to be copied)."""

    style: str
    examples: tuple[Example, ...] = ()

    def description(self, language: str = "en") -> str:
        """What to write, for the prompt and the response schema: in the talk's language, as long as a name gets."""
        name = languages.language(language).name
        such_as = " or ".join(str(example) for example in self.examples)
        wordplay = f", with wordplay that works in {name}" if language != "en" else ""
        return (
            f"{STYLES[self.style].asked}{', such as ' + such_as if such_as else ''}, for the title slide; in {name}"
            f"{wordplay}, with a title such as Dr. or Prof. if it suits (at most {PRESENTER_NAME.max_length} "
            "characters)"
        )

    def plays_on_description(self) -> str:
        """What the model works out before the name (name_plays_on, which the talk doesn't show)."""
        return f"{STYLES[self.style].plays_on}, worked out before the name (not shown)"


def _examples(style: str, topics: Sequence[str], rng: random_util.Rng, count: int = 2) -> tuple[Example, ...]:
    """Names of the pack in the style, for other topics than the talk's (a model that copies one gets it rejected),
    picked by the talk's dice."""
    others = [entry for entry in pack() if entry.style == style and not entry.fits(topics)]
    with random_util.use(rng):
        picked = random_util.sample(others, min(count, len(others)))
        return tuple(_example(entry, random_util.randrange(len(entry.names))) for entry in picked)


def _example(entry: PackEntry, index: int) -> Example:
    return Example(entry.names[index], entry.topic, entry.plays_on[index])


# What a name has: letters, and spaces, dots, apostrophes and hyphens between them (no digits, brackets, commas, ...)
_NAME: Final = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'’-])*")
_MOST_WORDS: Final = 6
# Words of a placeholder for a name, rather than a name ("Presenter Name", "[Your name]"), in the talks' languages
_PLACEHOLDERS: Final = frozenset(
    {
        "presenter",
        "presenters",
        "speaker",
        "name",
        "names",
        "firstname",
        "lastname",
        "surname",
        "your",
        "anonymous",
        "unknown",
        "placeholder",
        "lorem",
        "ipsum",
        "tbd",
        "todo",
        "naam",
        "spreker",
        "presentator",
        "presentatrice",
        "anoniem",
        "nom",
        "orateur",
        "redner",
        "nombre",
        "nome",
    }
)
# Names that never go on a title slide, even bent into a pun: dictators and their like, and the living people models
# reach for most (a famous-name pun is about a historical figure who died long ago)
_BLOCKED_WORDS: Final = frozenset(
    {
        "adolf",
        "mao",
        "saddam",
        "osama",
        "trump",
        "putin",
        "biden",
        "obama",
        "elon",
        "musk",
        "zuckerberg",
        "bezos",
        "kardashian",
        "beyonce",
        "jinping",
    }
)
_BLOCKED_STARTS: Final = (
    "hitler",
    "stalin",
    "mussolin",
    "himmler",
    "goebbel",
    "pinochet",
    "mengele",
    "eichmann",
    "gaddaf",
    "qaddaf",
    "nazi",
)
# (Word for word, each word as the start of one: "Taylor Swiftly" and "Donald Trumpet" too)
_BLOCKED_PHRASES: Final = (
    ("pol", "pot"),
    ("idi", "amin"),
    ("bin", "laden"),
    ("kim", "jong"),
    ("xi", "jinping"),
    ("donald", "trump"),
    ("vladimir", "putin"),
    ("joe", "biden"),
    ("barack", "obama"),
    ("mark", "zuckerberg"),
    ("jeff", "bezos"),
    ("kim", "kardashian"),
    ("taylor", "swift"),
)
_QUOTE_MARKS: Final = "\"'“”‘’«»"


def clean(value: Any, request: NameRequest | None = None) -> str | None:
    """The name as it goes on the title slide (on one line, without quote marks around it), or None when it won't
    do: when it isn't a text, is longer than a name gets (it isn't cut: half a name is no name), holds template code
    or what no name has (digits, brackets, commas, ...), is a placeholder ("Presenter Name"), names someone a talk
    doesn't go out under (a dictator, a famous living person), is the real name of a famous person whose name the
    pack bends (Marie Curie), or copies an example of the request (for another topic than the talk's)."""
    if not isinstance(value, str):
        return None
    name = " ".join(value.split()).strip(_QUOTE_MARKS + " ")
    if not name or len(name) > length_limit(PRESENTER_NAME) or leftovers_in(name) or not _NAME.fullmatch(name):
        return None
    words = _plain_words(name)
    if not 1 <= len(words) <= _MOST_WORDS or max(len(word) for word in words) < 3:
        return None
    if _PLACEHOLDERS & set(words) or _blocked(words):
        return None
    if any(_has_words(words, famous) for famous in _famous_names()):
        return None
    if request is not None and any(_squashed(example.name) in _squashed(name) for example in request.examples):
        return None
    return name


@cache
def _famous_names() -> tuple[tuple[str, ...], ...]:
    """The real names of the famous people whose names the pack's famous-name puns bend, as words."""
    return tuple(
        sorted(
            {
                tuple(_plain_words(original))
                for entry in pack()
                if entry.style == FAMOUS_PUN
                for original in entry.plays_on
                if original
            }
        )
    )


def _has_words(words: Sequence[str], phrase: Sequence[str]) -> bool:
    """Whether the words hold the phrase's words, in a row."""
    size = len(phrase)
    return size > 0 and any(
        tuple(words[start : start + size]) == tuple(phrase) for start in range(len(words) - size + 1)
    )


def _plain_words(text: str) -> list[str]:
    """The words of a text in lower case, without accents ("Beyoncé": "beyonce")."""
    plain = "".join(
        character for character in unicodedata.normalize("NFKD", text) if not unicodedata.combining(character)
    )
    return [word.casefold() for word in re.findall(r"[^\W\d_]+", plain)]


def _squashed(text: str) -> str:
    return "".join(_plain_words(text))


# Last names of the famous people above that are ordinary words too: they only count with the whole name
_COMMON_LAST_NAMES: Final = frozenset({"arc", "cook", "poe", "polo"})


def real_person(text: str) -> str | None:
    """A real person the text names, of the people talkgenerator knows by name: someone a talk doesn't go out under
    (a dictator, a famous living person), or a famous historical figure whose name the pack bends, by their whole
    name or their last name ("Einstein"). For generated pictures, which mustn't show real people (see
    talkgenerator.images.safety); the name as the text has it, or None."""
    words = _plain_words(text)
    for start in range(len(words)):
        if _blocked(words[start : start + 3]):
            return " ".join(words[start : start + 2])
    for famous in _famous_names():
        if _has_words(words, famous):
            return " ".join(famous)
        last = famous[-1]
        if len(famous) > 1 and last not in _COMMON_LAST_NAMES and last in words:
            return last
    return None


def _blocked(words: Sequence[str]) -> bool:
    """Whether a name's words (see _plain_words) name someone a talk doesn't go out under."""
    if _BLOCKED_WORDS & set(words) or any(word.startswith(_BLOCKED_STARTS) for word in words):
        return True
    return any(
        all(words[start + offset].startswith(part) for offset, part in enumerate(phrase))
        for phrase in _BLOCKED_PHRASES
        for start in range(len(words) - len(phrase) + 1)
    )


# A TALK'S NAME


@dataclass(frozen=True, eq=False)
class Naming:
    """How a talk gets its presenter's name when nobody gives one, as decided before its language model is asked (if
    a model writes it): the styles it may have, and for a talk a model writes, the style its dice picked and what the
    model is asked to write (None: nothing, for a classic name)."""

    styles: tuple[str, ...]
    topics: tuple[str, ...]
    rng: random_util.Rng  # the talk's
    style: str | None = None
    request: NameRequest | None = None

    @classmethod
    def of(cls, chosen: Sequence[str], topics: Sequence[str], rng: random_util.Rng, written: bool) -> Naming:
        """How a talk on the topics names its presenter, in one of the chosen styles: for a talk a language model
        writes (written), in a style its dice pick among those, which the model writes (but the classic names)."""
        naming = cls(tuple(style for style in STYLES if style in chosen), tuple(topics), rng)
        if not written or not naming.styles:
            return naming
        with random_util.use(rng.child("presenter", "style")):
            style = random_util.choice(naming.styles)
        if style == CLASSIC:
            return dataclasses.replace(naming, style=style)
        examples = _examples(style, topics, rng.child("presenter", "examples"))
        return dataclasses.replace(naming, style=style, request=NameRequest(style, examples))

    def name(self, written: Any = None, plays_on: Any = None) -> str:
        """The presenter's name: the one the language model wrote (its answer's presenter_name, and name_plays_on,
        what it worked out first), when it was asked for one and it will do (see clean); or else a classic one, when
        that's the style the talk's dice picked; or else the name a talk without a language model gets (see
        from_pack)."""
        if self.request is not None:
            name = clean(written, self.request)
            if name is not None:
                logger.info(
                    "The language model named the presenter (%s, on %r): %s", self.request.style, plays_on, name
                )
                return name
            if written is None:
                logger.info("The language model didn't name the presenter: talkgenerator makes up a name")
            else:
                logger.info(
                    "The language model's name for the presenter won't do (%r): talkgenerator makes one up", written
                )
        if self.style == CLASSIC:
            return classic(self.rng)
        return from_pack(self.topics, self.styles, self.rng)
