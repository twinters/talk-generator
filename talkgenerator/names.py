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

A talk that doesn't say which styles it may have gets the default ones, nudged by its persona (see Nudge and
talkgenerator.personas): the dice pick its style by the persona's weights (a medieval historian's name is a famous-name
pun more often), and the model hears how the presenter goes by (a professor with "Prof." before the name). A talk that
says which styles it may have goes by those alone.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import logging
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
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
            "a made-up name for the presenter: the name of one famous person who is no longer alive (long ago or lately), that "
            "everyone knows, with a part of it changed into a word about the talk's topic, so that both still show; "
            "never the real name as it is, and never the name of anyone alive today (however old or famous), a "
            "dictator or a criminal",
            "the famous person, no longer alive, whose name the presenter's name will bend, and the word "
            "about the talk's topic that goes into it",
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


@dataclass(frozen=True)
class Nudge:
    """How a talk's persona would have its presenter named (see talkgenerator.personas), for a talk that doesn't say
    which styles it may have: weights over the styles (1 for those it doesn't name), by which the talk's dice pick
    among the switched-on ones, and how the presenter goes by, for the language model that writes the name ("with Prof.
    before the name"), in place of "with a title such as Dr. or Prof. if it suits"."""

    weights: Mapping[str, float] = field(default_factory=dict)
    manner: str = ""

    def weight(self, style: str) -> float:
        return self.weights.get(style, 1.0)


def _pick_style(options: Sequence[str], nudge: Nudge | None) -> str:
    """One of the styles, as the current random stream picks it: by the nudge's weights, if there's a nudge, and
    else each as likely (as before there were personas)."""
    if nudge is None or not nudge.weights:
        return random_util.choice(options)
    picked = random_util.weighted_random([(nudge.weight(style), style) for style in options])
    return picked if picked is not None else options[-1]


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


def from_pack(topics: Sequence[str], chosen: Sequence[str], rng: random_util.Rng, nudge: Nudge | None = None) -> str:
    """The name of a talk whose presenter no language model names (a classic talk, or one whose model didn't write a
    name that will do): a name of the pack in a chosen style that has names for one of the talk's topics, or else a
    classic name. The talk's dice pick the style among those (and the classic names, when they're chosen), by the
    nudge's weights if there's one, and then one of its names."""
    fitting = [entry for entry in pack() if entry.style in chosen and entry.fits(topics)]
    options = [style for style in STYLES if style in chosen and (style == CLASSIC or _has_names(fitting, style))]
    with random_util.use(rng.child("presenter", "pack")):
        style = _pick_style(options, nudge) if options else CLASSIC
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
    examples it's shown (names of the pack for other topics than the talk's, which aren't to be copied), and how the
    presenter goes by, as their persona has it (manner: see Nudge)."""

    style: str
    examples: tuple[Example, ...] = ()
    manner: str = ""

    def description(self, language: str = "en") -> str:
        """What to write, for the prompt and the response schema: in the talk's language, as long as a name gets."""
        name = languages.language(language).name
        such_as = " or ".join(str(example) for example in self.examples)
        wordplay = f", with wordplay that works in {name}" if language != "en" else ""
        manner = self.manner or "with a title such as Dr. or Prof. if it suits"
        return (
            f"{STYLES[self.style].asked}{', such as ' + such_as if such_as else ''}, for the title slide; in {name}"
            f"{wordplay}, {manner} (at most {PRESENTER_NAME.max_length} characters)"
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
# Names that never go on a title slide, even bent into a pun: dictators and their like (and famous living people: see
# _LIVING_PEOPLE)
_BLOCKED_WORDS: Final = frozenset({"adolf", "mao", "saddam", "osama", "putin", "jinping"})
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
# (Word for word, each word as the start of one: "Pol Potter" too)
_BLOCKED_PHRASES: Final = (
    ("pol", "pot"),
    ("idi", "amin"),
    ("bin", "laden"),
    ("kim", "jong"),
    ("xi", "jinping"),
    ("vladimir", "putin"),
)
# Famous living people, whose names models reach for in puns: a free model named a keynote's presenter "Umbrella
# Chomsky" (2026-11-08), where a famous-name pun bends the name of someone famous who is no longer alive (section 5.10
# of docs/v5-plan.md). A name with an asterisk is theirs alone, and a presenter's name with it goes, whatever its other
# words ("Umbrella Chomsky", "Oprah Windfrey"): no classic name has it (but Trump, as the blocklist had it), nor is it a
# word that a fun surname could be (a gosling is a young goose, "streep" a Dutch stripe, "stallone" an Italian
# stallion). Their other names are ordinary ones ("Swift", "Gates"), which only count together, the first name before
# the surname, as they are or with one of them bent ("Taylor Swiftly", "Gordon Hamsay", "Tailor Swift": see
# _living_person), so "Dr. Emma Swift" stays
_LIVING_PEOPLE: Final = """
    Donald *Trump, Joe *Biden, *Barack *Obama, Michelle *Obama, Hillary Clinton, Bill Clinton, Kamala Harris, Emmanuel
    *Macron, Angela Merkel, Boris Johnson, Keir *Starmer, Justin Trudeau, Volodymyr *Zelensky, Narendra Modi, Benjamin
    *Netanyahu, Recep Tayyip *Erdoğan, Bernie Sanders, Al Gore, Greta *Thunberg, *Malala *Yousafzai, *Dalai Lama,
    Meghan Markle, Mark Rutte,
    *Elon *Musk, Bill Gates, Jeff *Bezos, Mark *Zuckerberg, Tim Cook, Steve Wozniak, Sam Altman, Jensen Huang, Sundar
    *Pichai, Satya *Nadella, Larry Page, Sergey Brin, Linus *Torvalds, Tim Berners-Lee, Warren *Buffett, Richard
    Branson, Martha Stewart,
    Noam *Chomsky, David *Attenborough, Neil *deGrasse Tyson, Bill Nye, Richard Dawkins, Brian Cox, Michio *Kaku, Roger
    Penrose, Steven Pinker, Yuval Noah Harari, Jordan Peterson, Buzz *Aldrin, Chris Hadfield, Malcolm *Gladwell, Marie
    Kondo, Bear *Grylls,
    Gordon Ramsay, Jamie Oliver, Nigella Lawson, Mary Berry, Paul Hollywood, Guy Fieri, Heston Blumenthal, Wolfgang
    Puck,
    *Usain Bolt, Serena Williams, Roger *Federer, Rafael Nadal, Novak *Djoković, Lionel *Messi, Cristiano Ronaldo,
    LeBron James, Michael Jordan, Tiger Woods, Michael Phelps, Simone Biles, Tom Brady, Wayne *Gretzky, Mike Tyson,
    Tony Hawk, Max *Verstappen, Lewis Hamilton, Eddy *Merckx, *Zlatan Ibrahimović, David Beckham, Kylian *Mbappé,
    *Shaquille O'Neal, Tadej *Pogačar, Remco *Evenepoel,
    Taylor Swift, *Beyoncé, *Rihanna, Lady Gaga, Ed Sheeran, Justin Bieber, Billie *Eilish, Dolly Parton, Elton John,
    Paul McCartney, Ringo Starr, Mick Jagger, Bob Dylan, Bruce *Springsteen, Snoop Dogg, *Eminem, *Shakira, Céline
    Dion, *Kanye West, Britney Spears, Katy Perry, Harry Styles, Bruno Mars, Ariana Grande, Miley Cyrus, *Stromae,
    Tom Hanks, Tom Cruise, Brad Pitt, Leonardo *DiCaprio, Meryl Streep, Morgan Freeman, Johnny Depp, *Keanu Reeves,
    Harrison Ford, Steven *Spielberg, George Lucas, Quentin Tarantino, Christopher Nolan, Tim Burton, Danny DeVito, Ryan
    Gosling, Ryan Reynolds, Benedict Cumberbatch, Nicolas Cage, Kevin Bacon, Samuel L. Jackson, Dwayne Johnson,
    Sylvester Stallone, Jackie Chan, Jim Carrey, Bill Murray, *Oprah Winfrey, Ellen *DeGeneres, Simon Cowell, Kim
    *Kardashian, Paris Hilton, Rowan Atkinson, John *Cleese, Ricky Gervais, Jerry *Seinfeld, Emma Watson, Daniel
    Radcliffe, Hugh Jackman, Arnold *Schwarzenegger, Jennifer Aniston, *Zendaya, Timothée *Chalamet, Chris *Hemsworth,
    J. K. *Rowling, Stephen King, George R. R. Martin, Margaret Atwood, Salman *Rushdie, Dan Brown, Neil *Gaiman, Paulo
    Coelho, Haruki Murakami, *Banksy, Yoko Ono, Ai Weiwei, Damien Hirst, David *Hockney, Jeff Koons, *MrBeast,
    *PewDiePie
"""
# The classic names (tracery's full_name), whose first names and surnames are ordinary ones: none of them bends a living
# person's name ("Cookson" isn't Cook bent)
CLASSIC_NAMES_FILE: Final = "data/text-templates/name.json"
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
        for end in range(start + 1, min(start + 3, len(words)) + 1):  # (one word, or a name of two or three)
            if _blocked(words[start:end]):
                return " ".join(words[start:end])
    for famous in _famous_names():
        if _has_words(words, famous):
            return " ".join(famous)
        last = famous[-1]
        if len(famous) > 1 and last not in _COMMON_LAST_NAMES and last in words:
            return last
    return None


def _blocked(words: Sequence[str]) -> bool:
    """Whether a name's words (see _plain_words) name someone a talk doesn't go out under: a dictator or their like,
    or a famous living person (see _living_person)."""
    if _BLOCKED_WORDS & set(words) or any(word.startswith(_BLOCKED_STARTS) for word in words):
        return True
    if any(
        all(words[start + offset].startswith(part) for offset, part in enumerate(phrase))
        for phrase in _BLOCKED_PHRASES
        for start in range(len(words) - len(phrase) + 1)
    ):
        return True
    return _living_person(words)


@dataclass(frozen=True)
class _Living:
    """The famous living people's names (_LIVING_PEOPLE), as words: those that are theirs alone, and their surnames by
    first name and first names by surname."""

    alone: frozenset[str]
    surnames: Mapping[str, frozenset[str]]
    first_names: Mapping[str, frozenset[str]]


@cache
def _living() -> _Living:
    """The names of _LIVING_PEOPLE, as words (see _Living)."""
    alone: set[str] = set()
    surnames: dict[str, set[str]] = {}
    first_names: dict[str, set[str]] = {}
    for person in _LIVING_PEOPLE.split(","):
        parts = person.split()
        alone.update(word for part in parts if part.startswith("*") for word in _plain_words(part))
        names = [word for word in _plain_words(person) if len(word) > 1]  # (no initials)
        surname = next((word for word in _plain_words(parts[-1]) if len(word) > 1), None) if parts else None
        if len(names) > 1 and surname is not None and surname != names[0]:  # (a first name and a surname)
            surnames.setdefault(names[0], set()).add(surname)
            first_names.setdefault(surname, set()).add(names[0])
    return _Living(
        frozenset(alone),
        {first: frozenset(names) for first, names in surnames.items()},
        {surname: frozenset(names) for surname, names in first_names.items()},
    )


@cache
def _ordinary_names() -> tuple[frozenset[str], frozenset[str]]:
    """The first names and the surnames of the classic names (CLASSIC_NAMES_FILE), as words: ordinary names."""
    with open(os_util.to_actual_file(CLASSIC_NAMES_FILE), encoding="utf-8") as file:
        grammar = json.load(file)

    def words(*rules: str) -> frozenset[str]:
        return frozenset(word for rule in rules for name in grammar[rule] for word in _plain_words(str(name)))

    return words("male_name", "female_name"), words("last_name")


def _living_person(words: Sequence[str]) -> bool:
    """Whether a name's words (see _plain_words) name a famous living person (see _LIVING_PEOPLE): a name that's theirs
    alone ("Umbrella Chomsky"), or their first name and their surname in a row (an initial between them aside), as
    they are, or with one of the two bent ("Taylor Q. Swiftly", "Gordon Hamsay", "Tailor Swift": see _bent) into what
    no classic name is: "Tim Cookson" and "Jill Gates" stay, as the classic names have Cookson and Jill."""
    living = _living()
    if living.alone & set(words):
        return True
    first_names, surnames = _ordinary_names()
    names = [word for word in words if len(word) > 1]
    for first, surname in itertools.pairwise(names):
        theirs = living.surnames.get(first, frozenset())
        if surname in theirs or (
            surname not in surnames and any(_bent(surname, their_surname) for their_surname in theirs)
        ):
            return True
        if first not in first_names and first not in surnames:
            if any(_bent(first, their_first) for their_first in living.first_names.get(surname, ())):
                return True
    return False


# How a word bends a name (see _bent): it starts with the name's first letters (all of a shorter name's), or it's a
# letter off the name (one added, left out or changed: "Hamsay" for Ramsay, "Goosling" for Gosling), or two off a
# long one
_BENT_START: Final = 5  # (the name's first letters)
_LEAST_TO_BEND: Final = 4  # (a shorter name is only bent by what starts with it)
_LONG_NAME: Final = 9  # (two letters off)


def _bent(word: str, name: str) -> bool:
    """Whether a word bends a name (see _BENT_START), as a pun does: "Swiftly" bends Swift, "Hamsay" Ramsay,
    "Cucumberbatch" Cumberbatch."""
    if word == name or len(word) < 3:
        return False
    if word.startswith(name[:_BENT_START]):
        return True
    return len(name) >= _LEAST_TO_BEND and _edits_within(word, name, 2 if len(name) >= _LONG_NAME else 1)


def _edits_within(word: str, other: str, most: int) -> bool:
    """Whether a word is at most so many edits (a letter added, left out or changed) from another one."""
    if abs(len(word) - len(other)) > most:
        return False
    previous = list(range(len(other) + 1))
    for index, letter in enumerate(word, 1):
        current = [index]
        for other_index, other_letter in enumerate(other, 1):
            current.append(
                min(previous[other_index] + 1, current[-1] + 1, previous[other_index - 1] + (letter != other_letter))
            )
        if min(current) > most:
            return False
        previous = current
    return previous[-1] <= most


# A TALK'S NAME


@dataclass(frozen=True, eq=False)
class Naming:
    """How a talk gets its presenter's name when nobody gives one, as decided before its language model is asked (if
    a model writes it): the styles it may have (and its persona's nudge, if the talk didn't say which), and for a talk
    a model writes, the style its dice picked and what the model is asked to write (None: nothing, for a classic
    name)."""

    styles: tuple[str, ...]
    topics: tuple[str, ...]
    rng: random_util.Rng  # the talk's
    style: str | None = None
    request: NameRequest | None = None
    nudge: Nudge | None = None

    @classmethod
    def of(
        cls,
        chosen: Sequence[str],
        topics: Sequence[str],
        rng: random_util.Rng,
        written: bool,
        nudge: Nudge | None = None,
    ) -> Naming:
        """How a talk on the topics names its presenter, in one of the chosen styles: for a talk a language model
        writes (written), in a style its dice pick among those (by the nudge's weights, if there's one), which the
        model writes (but the classic names), told how the presenter goes by (the nudge's manner)."""
        naming = cls(tuple(style for style in STYLES if style in chosen), tuple(topics), rng, nudge=nudge)
        if not written or not naming.styles:
            return naming
        with random_util.use(rng.child("presenter", "style")):
            style = _pick_style(naming.styles, nudge)
        if style == CLASSIC:
            return dataclasses.replace(naming, style=style)
        examples = _examples(style, topics, rng.child("presenter", "examples"))
        manner = nudge.manner if nudge is not None else ""
        return dataclasses.replace(naming, style=style, request=NameRequest(style, examples, manner))

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
        return from_pack(self.topics, self.styles, self.rng, self.nudge)
