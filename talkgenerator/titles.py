"""A talk's title and topic from what's typed for it, which can be either (docs/v5-plan.md, section 5.11).

What someone types for a talk (generate_presentation's topic_or_title) can be its topic ("penguins") or its title
("Why I Joined a Penguin Cult"). In a talk a language model writes, the model tells which, in the same request: in the
talk's spine, before the rest. Read as a title, it stays the talk's title, with only its obvious slips fixed (spelling,
grammar, capitals): its wording and its joke stay (see recognisable). Read as a topic, it gets a title from the model,
which picks the best of its own and a few classic titles that the talk's dice draw (see candidates), fixing the one
it picks where it's off. A talk without a language model, or whose model doesn't say how it read what was typed,
goes by talkgenerator's guess (see guess).

The talk's topic is settled before the model is asked, since the slides' words to riff on come from it: by the guess,
the rarest word of a title (as for a title given as such), or else what was typed (topics, separated by commas).

A topic or a title given as such (generate_presentation's topic and title) is taken as it is: nothing second-guesses
the user.
"""

from __future__ import annotations

import dataclasses
import difflib
import logging
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator.models.deck import ReadBy, Reading, TopicOrTitle
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import TALK_TITLE
from talkgenerator.plan.realize import clean_text
from talkgenerator.sources import word_frequency
from talkgenerator.util import random_util

logger = logging.getLogger("talkgenerator")

TOPIC: Final = "topic"
TITLE: Final = "title"
READINGS: Final = (TOPIC, TITLE)
# The field of the talk's spine in which the language model says which it read: one that sorts before the others, so
# that a model that writes the fields in alphabetical order says it before it writes the title too
INPUT_IS: Final = "input_is"

# How titles start, as words in lower case: in English, and in the other languages talks can be in (what's typed for
# a talk in another language may be in either). "How to", "Why", "The", "A", "My", ...
_TITLE_STARTS: Final[dict[str, tuple[str, ...]]] = {
    "en": ("how", "why", "what", "when", "where", "who", "the", "a", "an", "my", "your", "i", "we", "you"),
    "nl": ("hoe", "waarom", "wat", "wanneer", "waar", "wie", "de", "het", "een", "mijn", "jouw", "ik", "wij", "we"),
    "fr": ("comment", "pourquoi", "quand", "où", "qui", "le", "la", "les", "un", "une", "mon", "ma", "mes", "je"),
    "de": ("wie", "warum", "was", "wann", "wo", "wer", "der", "die", "das", "ein", "eine", "mein", "meine", "ich"),
    "es": ("cómo", "como", "por qué", "porque", "qué", "cuándo", "el", "la", "los", "las", "un", "una", "mi", "yo"),
    "it": ("come", "perché", "cosa", "quando", "il", "lo", "la", "gli", "le", "un", "una", "uno", "mio", "mia", "io"),
    "pt": ("como", "por que", "porque", "o que", "quando", "o", "os", "as", "um", "uma", "meu", "minha", "eu"),
}
_MOST_TOPIC_WORDS: Final = 3  # a part of what's typed (between commas) with more words than this is a title's
_TITLE_ENDS: Final = ("?", "!")
_QUOTE_MARKS: Final = "\"'“”‘’«»„"


def _words(text: str) -> list[str]:
    """The words of a text, in lower case (an apostrophe or hyphen inside a word keeps it whole)."""
    return [word.casefold() for word in re.findall(r"[^\W_]+(?:['’-][^\W_]+)*", text)]


def normalised(text: str) -> str:
    """What was typed on one line, without quote marks around it."""
    return " ".join(text.split()).strip(_QUOTE_MARKS + " ")


def guess(text: str, language: str = "en") -> str:
    """How talkgenerator reads what was typed, without a language model to tell: TITLE when a part of it (between
    commas) has four words or more, when it starts like a title ("How to", "Why", "The", "A", "My", ..., in English
    or in the talk's language), or when it ends in "?" or "!"; TOPIC otherwise (one or a few words, or a few such
    topics separated by commas)."""
    text = normalised(text)
    if text.endswith(_TITLE_ENDS):
        return TITLE
    if any(len(_words(part)) > _MOST_TOPIC_WORDS for part in text.split(",")):
        return TITLE
    words = _words(text)
    for start in {*_TITLE_STARTS["en"], *_TITLE_STARTS.get(language, ())}:
        start_words = start.split()
        if words[: len(start_words)] == start_words:
            return TITLE
    return TOPIC


def topics_from(text: str, language: str = "en") -> list[str]:
    """The topics of a talk on what was typed, as settled before its language model reads it (by the guess): a
    title's rarest word in its language (as for a title given as such), or else the topics it names, separated by
    commas. Either with its misspellings fixed ("pengiuns": "penguins"), as what's typed often has them: the topics
    give the slides their words to riff on, and a misspelled word would be a title's rarest, as no language knows
    it."""
    text = normalised(text)
    if guess(text, language) == TITLE:
        return [word_frequency.get_rarest_word(text, language, fix_spelling=True) or text]
    fixed = word_frequency.fix_spelling(text, language)
    return [part.strip() for part in fixed.split(",") if part.strip()] or [text]


# A TITLE THAT WAS TYPED


def _plain_words(text: str) -> list[str]:
    """The words of a text in lower case, without accents or punctuation ("Pinguïns!": "pinguins")."""
    plain = "".join(
        character for character in unicodedata.normalize("NFKD", text) if not unicodedata.combining(character)
    )
    return [word.casefold() for word in re.findall(r"[^\W_]+", plain)]


_MOST_WORDS_CHANGED: Final = 4  # (a typed title of n words may gain or lose max(1, n // this) words)
_LEAST_LIKENESS: Final = 0.7


def recognisable(typed: str, written: str) -> bool:
    """Whether a title the language model wrote for a typed title is still that title, with no more than its slips
    fixed (spelling, grammar, capitals): about as many words (one more or fewer, or a quarter of a long title's), and
    mostly the same letters. A title rewritten, extended, cut or translated isn't."""
    typed_words, written_words = _plain_words(typed), _plain_words(written)
    if not typed_words or not written_words:
        return False
    if abs(len(typed_words) - len(written_words)) > max(1, len(typed_words) // _MOST_WORDS_CHANGED):
        return False
    likeness = difflib.SequenceMatcher(None, " ".join(typed_words), " ".join(written_words)).ratio()
    return likeness >= _LEAST_LIKENESS


# CLASSIC TITLES A LANGUAGE MODEL MAY PICK

# A classic title generator: a presentation context (with the "seed" to make a title about) in, a title (or None) out
TitleGenerator = Callable[[dict[str, Any]], Any]
_MOST_CANDIDATES: Final = 3


def candidates(generators: Sequence[TitleGenerator], topic: str, rng: random_util.Rng) -> tuple[str, ...]:
    """One to three classic titles about the topic, for the language model to weigh against its own, as the talk's
    dice draw how many: the generators' titles in order (such as the schema's title generator, a wikiHow "How to
    ..." title, and the schema's title generator again), each from a stream of its own, leaving out what fails or
    repeats. The first generator's title comes from the talk's "title" stream, as a classic talk's title does, so it's
    the title the talk gets when it turns out classic."""
    with random_util.use(rng.child("title", "candidates")):
        wanted = random_util.randint(1, _MOST_CANDIDATES)
    found: list[str] = []
    for index, generator in enumerate(generators):
        if len(found) >= wanted:
            break
        stream = rng.child("title") if index == 0 else rng.child("title", "candidate", index)
        try:
            with random_util.use(stream):
                title = generator({"seed": topic})
        except Exception:  # (a source that misbehaves leaves its title out)
            logger.exception("A classic title for the language model to weigh failed")
            continue
        text = clean_text(title, TALK_TITLE) if isinstance(title, str) else None
        if text and text.casefold() not in {other.casefold() for other in found}:
            found.append(text)
    return tuple(found)


# WHAT THE LANGUAGE MODEL IS ASKED


@dataclass(frozen=True)
class TitleRequest:
    """What the language model that writes a talk is told about what was typed for it, and asked: whether it reads
    as the talk's topic or its title (input_is, in the spine), and the talk's title, for a topic the best of
    its own (own_title) and the classic candidates, when there are any (in English talks: the classic titles are
    English)."""

    typed: str
    candidates: tuple[str, ...] = ()

    def lines(self) -> list[str]:
        """The request's lines about it, instead of its topic and title."""
        lines = [f"Typed: {self.typed} (the user's input: the talk's topic or its title; say which in input_is)"]
        if self.candidates:
            listed = "; ".join(f'"{candidate}"' for candidate in self.candidates)
            lines.append(f"Classic titles, for a topic: {listed}")
        return lines

    def input_is_description(self) -> str:
        return (
            "what the typed input is, decided first: 'title' if it's a talk's title (a phrase that names a talk, a "
            "claim or a question, such as 'Why I Joined a Penguin Cult'), 'topic' if it's what a talk is about (a "
            "thing or a subject, or a few, such as 'penguins' or 'medieval cheese'), however odd"
        )

    def own_title_description(self, language: str = "en") -> str:
        return (
            f"for a topic, your own title for the talk, in {languages.language(language).name}; for a title, empty "
            f"(at most {TALK_TITLE.max_length} characters)"
        )

    def title_description(self, language: str = "en") -> str:
        name = languages.language(language).name
        topic = (
            "the best of own_title and the classic titles, whichever it is, fixed where it's off (a broken plural, an "
            f"odd phrase, words that make no sense), in {name}"
            if self.candidates
            else f"your own title for the talk, in {name}"
        )
        return (
            "the talk's title: for a title, the typed input with only its obvious slips fixed (spelling, grammar, "
            f"capitals), its words and its joke kept, and not translated; for a topic, {topic} (at most "
            f"{TALK_TITLE.max_length} characters)"
        )


# A TALK'S TITLE


@dataclass(frozen=True, eq=False)
class Titling:
    """How a talk on what was typed gets its title, as decided before its language model is asked (if a model writes
    it): what was typed, how talkgenerator guesses it reads, and for a talk a model writes, what the model is asked
    (with the classic titles it may pick)."""

    typed: str
    language: str = "en"
    guessed: str = TOPIC
    request: TitleRequest | None = None

    @classmethod
    def of(
        cls,
        typed: str,
        language: str = "en",
        written: bool = False,
        generators: Sequence[TitleGenerator] = (),
        topic: str | None = None,
        rng: random_util.Rng | None = None,
    ) -> Titling:
        """How a talk on what was typed gets its title: for a talk a language model writes (written), the model is
        asked how it reads, and in an English talk, it gets classic titles to weigh, which the generators make about
        the topic, with the talk's dice (rng)."""
        typed = normalised(typed)
        titling = cls(typed, language, guess(typed, language))
        if not written:
            return titling
        drawn: tuple[str, ...] = ()
        if language == "en" and generators and topic and rng is not None:
            drawn = candidates(generators, topic, rng)
        return dataclasses.replace(titling, request=TitleRequest(typed, drawn))

    def settle(self, spine: Mapping[str, Any], classic: Callable[[], str]) -> tuple[str, TopicOrTitle]:
        """The talk's title, and how what was typed was read: as the language model read it (its answer's spine:
        input_is and title), or else as talkgenerator guesses. A title: the model's, when it's recognisably what was
        typed (see recognisable), or else what was typed. A topic: the model's title, or else the classic title
        (classic(), the one a classic talk with this seed gets)."""
        reading, by = self._reading(spine)
        written = clean_text(spine.get("title"), TALK_TITLE, self.language) if self.request is not None else None
        if reading == "title":
            title = self.typed
            if written is not None and recognisable(self.typed, written):
                title = written
            elif written is not None:
                logger.info("The language model's title strays from what was typed (%r): it stays as typed", written)
        else:
            title = written or classic()
        logger.info("Read %r as a %s (%s): the title is %r", self.typed, reading, by, title)
        return title, TopicOrTitle(text=self.typed, read_as=reading, by=by)

    def _reading(self, spine: Mapping[str, Any]) -> tuple[Reading, ReadBy]:
        """How what was typed was read, and by whom: as the language model's input_is says, or else as guessed."""
        said = spine.get(INPUT_IS) if self.request is not None else None
        if isinstance(said, str) and said.strip().casefold() in READINGS:
            return ("title" if said.strip().casefold() == TITLE else "topic"), "language model"
        if self.request is not None:
            logger.info("The language model didn't say how it read %r (%r): talkgenerator guesses", self.typed, said)
        return ("title" if self.guessed == TITLE else "topic"), "guess"
