"""A talk's title and topic from what's typed for it, which can be either (docs/v5-plan.md, section 5.11).

What someone types for a talk (generate_presentation's topic_or_title) can be its topic ("penguins"), a premise ("Cats
are liquid") or its title ("Why I Joined a Penguin Cult"). In a talk a language model writes:

- What's typed in quote marks is the title, word for word (talkgenerator.com has no other way to say so).
- What's clearly a title (see clearly_a_title: four words or more, or a question or exclamation) stays the talk's
  title, with only its obvious slips fixed (spelling, grammar, capitals) by the model, in the same request: its wording
  and its joke stay (see recognisable), or else it stays as typed, with the slips fixed that talkgenerator can fix
  itself (see polished).
- Anything shorter is the talk's topic, or a premise, on which the model builds a title of its own, funnier and more
  specific than what was typed ("The French Revolution" deserves better than itself; a premise keeps its words). (The
  user's call, 2026-11-07, after the free models proved unreliable at telling a topic from a title themselves.) The
  talk's dice pick how the classic titles go with it (see CLASSIC_TITLE_WAYS).

A talk without a language model, or whose model writes no title, goes by talkgenerator's guess (see guess): what reads
as a title stays as typed (polished), and a topic gets the classic title.

The talk's topic is settled before the model is asked, since the slides' words to riff on come from it: a clear
title's rarest word (as for a title given as such), or else what was typed (topics, separated by commas), either with
its misspellings fixed.

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

from talkgenerator.models.deck import Reading, TopicOrTitle
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import TALK_TITLE
from talkgenerator.plan.realize import clean_text
from talkgenerator.sources import word_frequency
from talkgenerator.util import random_util

logger = logging.getLogger("talkgenerator")

TOPIC: Final = "topic"
TITLE: Final = "title"
READINGS: Final = (TOPIC, TITLE)
# The ways a talk's classic titles go to the language model, for a short input, which the talk's dice pick by weight:
# as titles to pick ("options"), as inspiration for its own ("inspiration"), or not at all ("none", which saves the
# wikiHow search before the request too). The user liked the titles of all three, in a live comparison (2026-11-07)
CLASSIC_TITLE_WAYS: Final[tuple[tuple[str, float], ...]] = (("options", 1.0), ("inspiration", 1.0), ("none", 1.0))

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
# Verbs that make a few words a claim ("Cats are liquid", "Breakfast is overrated"), which a topic hardly has: forms of
# "to be" and modal verbs, in English and in the other languages talks can be in
_CLAIM_VERBS: Final[dict[str, frozenset[str]]] = {
    "en": frozenset(
        {"is", "are", "was", "were", "am", "isn't", "aren't", "wasn't", "can", "can't", "will", "won't", "should"}
    ),
    "nl": frozenset({"is", "zijn", "was", "waren", "ben", "bent", "kan", "kunnen", "moet", "moeten", "wil", "zal"}),
    "fr": frozenset({"est", "sont", "était", "suis", "peut", "peuvent", "doit", "va"}),
    "de": frozenset({"ist", "sind", "war", "waren", "bin", "kann", "können", "muss", "will", "wird"}),
    "es": frozenset({"es", "son", "está", "están", "era", "soy", "puede", "pueden", "debe", "va"}),
    "it": frozenset({"è", "sono", "era", "può", "possono", "deve", "va"}),
    "pt": frozenset({"é", "são", "está", "estão", "era", "sou", "pode", "podem", "deve", "vai"}),
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


def quoted(text: str) -> bool:
    """Whether what was typed is in quote marks ('"Cats are liquid"'), which makes it a title to keep word for word."""
    text = " ".join(text.split())
    return len(text) > 2 and text[0] in _QUOTE_MARKS and text[-1] in _QUOTE_MARKS and bool(normalised(text))


def clearly_a_title(text: str) -> bool:
    """Whether what was typed is a title whatever a language model says: a part of it (between commas) has four
    words or more, or it ends in "?" or "!". (The free models took "10 reasons your toaster hates you" and "Is cheese
    the future of money?" for topics, and the talks lost their titles.)"""
    text = normalised(text)
    return text.endswith(_TITLE_ENDS) or any(len(_words(part)) > _MOST_TOPIC_WORDS for part in text.split(","))


def guess(text: str, language: str = "en") -> str:
    """How talkgenerator reads what was typed, without a language model to tell: TITLE when it's clearly a title (a
    part of it, between commas, has four words or more, or it ends in "?" or "!"), when it starts like a title ("How
    to", "Why", "The", "A", "My", ..., in English or in the talk's language), or when it's a claim ("Cats are liquid":
    a form of "to be", or a modal verb); TOPIC otherwise (one or a few words, or a few such topics separated by
    commas)."""
    if quoted(text):
        return TITLE
    text = normalised(text)
    if clearly_a_title(text):
        return TITLE
    words = _words(text)
    for start in {*_TITLE_STARTS["en"], *_TITLE_STARTS.get(language, ())}:
        start_words = start.split()
        if words[: len(start_words)] == start_words:
            return TITLE
    if len(words) > 1 and set(words[1:]) & (_CLAIM_VERBS["en"] | _CLAIM_VERBS.get(language, frozenset())):
        return TITLE
    return TOPIC


def topics_from(text: str, language: str = "en") -> list[str]:
    """The topics of a talk on what was typed, as settled before its language model is asked: a clear title's rarest
    word in its language (as for a title given as such; also a title in quote marks), or else the topics it names,
    separated by commas (a premise,
    such as "Cats are liquid", as it is). Either with its misspellings fixed ("pengiuns": "penguins"), as what's
    typed often has them: the topics give the slides their words to riff on, and a misspelled word would be a
    title's rarest, as no language knows it."""
    title = quoted(text)
    text = normalised(text)
    if title or clearly_a_title(text):
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
_LEAST_WORD_LIKENESS: Final = (
    0.6  # (a misspelled word and its fix: "joind" and "joined" are 0.91, "waht" and "what" 0.75)
)
_LITTLE_WORD: Final = 3  # a word of this many letters or fewer may be added or left out ("a", "the", "of")


def _alike(word: str, other: str) -> bool:
    return word == other or difflib.SequenceMatcher(None, word, other).ratio() >= _LEAST_WORD_LIKENESS


def _unmatched(words: Sequence[str], others: Sequence[str]) -> list[str]:
    """The words that are like none of the others."""
    return [word for word in words if not any(_alike(word, other) for other in others)]


def recognisable(typed: str, written: str) -> bool:
    """Whether a title the language model wrote for a typed title is still that title, with no more than its slips
    fixed (spelling, grammar, capitals): about as many words (one more or fewer, or a quarter of a long title's), none
    added or left out but little ones ("a", "the"), and mostly the same letters. A title rewritten, extended, cut or
    translated isn't, nor one with a word put before it ("Typed: ...")."""
    typed_words, written_words = _plain_words(typed), _plain_words(written)
    if not typed_words or not written_words:
        return False
    if abs(len(typed_words) - len(written_words)) > max(1, len(typed_words) // _MOST_WORDS_CHANGED):
        return False
    changed = _unmatched(written_words, typed_words) + _unmatched(typed_words, written_words)
    if any(len(word) > _LITTLE_WORD for word in changed):
        return False
    likeness = difflib.SequenceMatcher(None, " ".join(typed_words), " ".join(written_words)).ratio()
    return likeness >= _LEAST_LIKENESS


def polished(typed: str, language: str = "en") -> str:
    """A typed title with the slips fixed that talkgenerator can fix itself, for when no language model fixed them: its
    misspellings (see word_frequency.fix_spelling), and when it's all in lower case, a capital at the start (and "I"
    for "i", in English)."""
    title = word_frequency.fix_spelling(typed, language)
    if title == title.lower():
        if language == "en":
            title = re.sub(r"\bi\b", "I", title)
        title = title[:1].upper() + title[1:]
    return title


def part_of(typed: str, written: str) -> str | None:
    """The part of a longer title the language model wrote that is what was typed, as the model wrote it ("Cats Are
    Liquid" in "Cats Are Liquid: A Medieval Scientific Breakthrough", for "cats are liquid"), or None."""
    typed_words = _plain_words(typed)
    spans = [(match.start(), match.end(), _plain_words(match.group())) for match in re.finditer(r"[^\W_]+", written)]
    words = [(start, end, plain[0]) for start, end, plain in spans if plain]
    for first in range(len(words) - len(typed_words) + 1):
        run = words[first : first + len(typed_words)]
        if typed_words and all(
            _alike(word, typed_word) for (_, _, word), typed_word in zip(run, typed_words, strict=True)
        ):
            return written[run[0][0] : run[-1][1]]
    return None


# CLASSIC TITLES A LANGUAGE MODEL MAY PICK

# A classic title generator: a presentation context (with the "seed" to make a title about) in, a title (or None) out
TitleGenerator = Callable[[dict[str, Any]], Any]
_MOST_CANDIDATES: Final = 3


def candidates(generators: Sequence[TitleGenerator], topic: str, rng: random_util.Rng) -> tuple[str, ...]:
    """Up to three classic titles about the topic, for the language model to weigh against its own, as the talk's
    dice draw how many (one to three): the generators' titles in order (such as the schema's title generator, a
    wikiHow "How to ..." title, and the schema's title generator again), each from a stream of its own, leaving out
    what fails, repeats, or doesn't mention the topic (none at all, when no title does). The first generator's title
    comes from the talk's "title" stream, as a classic talk's title does."""
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
        if text and text.casefold() not in {other.casefold() for other in found} and _about(text, topic):
            found.append(text)
    return tuple(found)


def _about(title: str, topic: str) -> bool:
    """Whether a classic title mentions the topic (one of its words that aren't little, in any form: "cats" for
    "cat"), as one from an odd wikiHow page doesn't ("Never, Ever Be A Secret Agent", for penguins), and which the
    free models still pick."""
    topic_words = [word for word in _plain_words(topic) if len(word) > _LITTLE_WORD] or _plain_words(topic)
    return any(_alike(word, topic_word) for word in _plain_words(title) for topic_word in topic_words)


# WHAT THE LANGUAGE MODEL IS ASKED


@dataclass(frozen=True)
class TitleRequest:
    """What the language model that writes a talk is told about what was typed for it, and asked: to keep it as the
    talk's title, fixing its slips (keep, for what's clearly a title), or else to build a title of its own on it, as
    the talk's topic or premise, funnier and more specific; with the classic titles that may go with that (in English
    talks: the classic titles are English), as titles to pick or as inspiration."""

    typed: str
    keep: bool = False
    candidates: tuple[str, ...] = ()
    inspiration: bool = False  # (the classic titles are examples of their humour, not titles to pick)
    exact: bool = False  # (a title typed in quote marks: word for word, not even its slips fixed)
    meaning: str | None = None  # (what a short input means, with its misspellings fixed, when that's different)

    def lines(self, topic: str) -> list[str]:
        """The request's lines about it, instead of its topic and title (topic: the talk's, for a title to keep)."""
        if self.exact:
            return [f"Topic: {topic}", f'Title: "{self.typed}" (as the user typed it, in quotes: word for word)']
        if self.keep:
            return [
                f"Topic: {topic}",
                f'Title: "{self.typed}" (as the user typed it: keep its words, fixing only its spelling, grammar and '
                "capitals)",
            ]
        meaning = f', meaning "{self.meaning}"' if self.meaning else ""
        lines = [
            f'Topic: "{self.typed}" (as the user typed it{meaning}: the talk\'s topic, or a premise for it)',
            "Title: come up with one, funnier and more specific than what the user typed",
        ]
        if self.candidates:
            listed = "; ".join(f'"{candidate}"' for candidate in self.candidates)
            if self.inspiration:
                lines.append(f"Classic talkgenerator titles, for inspiration only (write your own): {listed}")
            else:
                lines.append(f"Classic titles from talkgenerator, to pick from: {listed}")
        return lines

    def fields(self, language: str = "en") -> dict[str, str]:
        """The spine's fields about the title, in order (instead of its title)."""
        name = languages.language(language).name
        limit = f"at most {TALK_TITLE.max_length} characters"
        if self.exact:
            return {"title": f"the title the user typed, word for word, exactly as it is ({limit})"}
        if self.keep:
            return {
                "title": "the title the user typed, word for word, with only its spelling, grammar and capitals "
                f"fixed (not translated) ({limit})"
            }
        own = (
            f"a title of your own for the talk, in {name}: funnier and more specific than what the user typed, "
            f"building on it, spelled right (a premise such as 'Cats are liquid' keeps its words) ({limit})"
        )
        if self.candidates and not self.inspiration:
            return {
                "own_title": own,
                "title": "own_title, or one of the classic titles instead if it's about the topic and funnier, fixed "
                f"where it's off ({limit})",
            }
        return {"title": own}


# A TALK'S TITLE


@dataclass(frozen=True, eq=False)
class Titling:
    """How a talk on what was typed gets its title, as decided before its language model is asked (if a model writes
    it): what was typed, how talkgenerator guesses it reads, and for a talk a model writes, what the model is asked
    (with the classic titles that go with a topic)."""

    typed: str
    language: str = "en"
    guessed: str = TOPIC
    request: TitleRequest | None = None
    exact: bool = False  # (typed in quote marks: the title, word for word)

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
        """How a talk on what was typed gets its title: a title in quote marks is kept word for word, and for a talk a
        language model writes (written), what's clearly a title is kept, and anything shorter gets the model's title,
        with in an English talk classic titles that the generators make about the topic, in a way the talk's dice
        (rng) pick (see CLASSIC_TITLE_WAYS)."""
        exact = quoted(typed)
        titling = cls(normalised(typed), language, guess(typed, language), exact=exact)
        typed = titling.typed
        if not written:
            return titling
        keep = exact or clearly_a_title(typed)
        way = "none"
        drawn: tuple[str, ...] = ()
        if not keep and language == "en" and rng is not None:
            way = _way(rng)
            if way != "none" and generators and topic:
                drawn = candidates(generators, topic, rng)
            logger.info("Classic titles for the language model (%s): %s", way, drawn)
        fixed = word_frequency.fix_spelling(typed, language)
        request = TitleRequest(
            typed,
            keep,
            drawn,
            inspiration=way == "inspiration",
            exact=exact,
            meaning=fixed if not keep and fixed != typed else None,
        )
        return dataclasses.replace(titling, request=request)

    def settle(self, spine: Mapping[str, Any], classic: Callable[[], str]) -> tuple[str, TopicOrTitle]:
        """The talk's title, and how what was typed was read.

        A title in quote marks is the talk's title, word for word. What's clearly a title is the talk's title, in the model's words when they're recognisably what was typed (see
        recognisable) or part of its title ("Cats Are Liquid", out of "Cats Are Liquid: A Medieval Breakthrough"), and
        else as typed, with the slips fixed that talkgenerator can fix itself (see polished). Anything shorter is the
        topic, and the talk gets the model's title: its own, rather than just what was typed when it wrote both. Without
        a title from the model (or without a model), talkgenerator's guess goes: what reads as a title stays as typed
        (polished), and a topic gets the classic title (classic(), the one a classic talk with this seed gets)."""
        written = self._written(spine, "title")
        own = self._written(spine, "own_title")
        reading: Reading
        if self.exact:
            reading, title = "title", self.typed
        elif self.request is not None and self.request.keep:
            kept = written if written is not None and recognisable(self.typed, written) else None
            part = part_of(self.typed, written) if written is not None and kept is None else None
            reading, title = "title", kept or part or polished(self.typed, self.language)
            if title == self.typed:  # (the model gave it back as typed, slips and all)
                title = polished(self.typed, self.language)
        elif self.request is not None and (written or own):
            reading = "topic"
            echoed = written is None or recognisable(self.typed, written)
            title = own if echoed and own and not recognisable(self.typed, own) else (written or own or "")
        else:
            if self.request is not None:
                logger.info("The language model wrote no title for %r: talkgenerator guesses", self.typed)
            reading = "title" if self.guessed == TITLE else "topic"
            title = polished(self.typed, self.language) if reading == "title" else classic()
        logger.info("Read %r as a %s: the title is %r", self.typed, reading, title)
        return title, TopicOrTitle(text=self.typed, read_as=reading)

    def _written(self, spine: Mapping[str, Any], field: str) -> str | None:
        """A title the language model wrote (its title or own_title), if it will do, without a label the request has
        put before it ("Title: ...", which a free model copied)."""
        if self.request is None:
            return None
        title = clean_text(spine.get(field), TALK_TITLE, self.language)
        if title is not None:
            title = _LABEL.sub("", title).strip() or None
        return title


def _way(rng: random_util.Rng) -> str:
    """How the talk's classic titles go to the language model, as its dice pick (see CLASSIC_TITLE_WAYS)."""
    with random_util.use(rng.child("title", "classic titles")):
        way = random_util.weighted_random([(weight, way) for way, weight in CLASSIC_TITLE_WAYS])
    return way or "none"


# A label of the request, which a free model put before the title it copied
_LABEL: Final = re.compile(r"^(?:what the user typed|typed|title|topic)\s*:\s*", re.IGNORECASE)
