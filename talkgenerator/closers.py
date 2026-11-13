"""The closer (docs/v5-plan.md, D76): the slide after a talk's last, which says that the talk is over, in its language,
its look and its format's kind, outside the slides it asked for.

The user found the end of a talk on talkgenerator.com unclear (2026-11-12): only the corner of the presentation said
"8 / 8", and going on did nothing. And academic talks and all-hands spent one of their slides on "Questions?" (pitches
too, and a TED-like talk now and then), which their closer says now, so that every slide a talk asks for is one of its
content. A talk's deck marks its closer (DeckSlide.closer), and its slides' numbers ("7/12") don't count it:
talkgenerator.com shows "The end" where its number would be, and lowers its curtain once the presenter goes on from it.

A format's closer is a Closer, which its Format names (closer=...); a format without one gets the TED-like talk's
(DEFAULT). The formats' closers:

- a TED-like talk's (DEFAULT): "Thank you!", with the presenter's name under it and a small "Questions?";
- an academic talk's: "Questions?", with "Thank you for your attention" under it, the presenter's name, and a huge
  question mark beside them;
- a pitch's: "Let's talk", with a made-up contact line under it (the presenter's first name at a domain made of the
  startup's name that reads as made up: "anna@penguinly-is-a-real-company.biz", D80) and the presenter's name;
- an all-hands': "Questions?", with "Back to work" under it, the presenter's name, and the question mark;
- a keynote's: "Available today", with the product's name under it, and the presenter's name.

HOW A FORMAT GETS ITS CLOSER. A Closer has its big words (title), a line under them (line) and a small note under that
(note), each a Said: a function of the talk's end (Ending: its language's words, its presenter's name, its title and
its topic) that gives a text, or None for none; and mark, for big words that ask a question, which a huge question mark
then goes beside. Its texts come from these, or from any function of the Ending:

- said("thanks"): talkgenerator's own words, which talkgenerator.plan.languages has in every talk language (the
  Language's fields: thanks, questions, attention, lets_talk, back_to_work, available, and any a format adds there);
- in_every_language({"en": "Call now!", "nl": "Bel nu!", ...}): a format's own words, given in every talk language (a
  ValueError, as soon as the format is defined, for one it leaves out);
- presenter: the presenter's name; contact_line: a pitch's made-up e-mail address; product_line: a keynote's product,
  as the title names it.

So a new format gets its closer in its Format, in one line, as an infomercial's could:

    INFOMERCIAL: Final = Format(..., closer=Closer(in_every_language(CALL_NOW), presenter, in_every_language(LINES)))

and tests/test_closers.py checks that every format's closer says something in every talk language, and that it fits
and reads in every theme family.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator import names
from talkgenerator.plan import languages
from talkgenerator.plan.languages import Language
from talkgenerator.slide.slides import CloserSlide

# What a title names before its colon, when that's a name ("Penguinly: Uber for Penguins"): a few words, short
_NAME_WORDS: Final = 3
_NAME_LENGTH: Final = 24
# A domain that a startup's name has already ("Penguin.ai"), else it gets one
# A made-up e-mail address's domain, which reads as made up (the user, 2026-11-13: "when we show an e-mail address,
# better see that the domain isn't real; maybe an over-the-top silly website name"; D80): the startup's name with words
# that no real company's domain has, in the talk's language, one picked by the name's letters
_SILLY_DOMAINS: Final[dict[str, tuple[str, ...]]] = {
    "en": (
        "{company}-is-a-real-company.biz",
        "totally-legit-{company}.biz",
        "{company}-official-website-trust-us.info",
        "real-{company}-not-a-scam.net",
    ),
    "nl": (
        "{company}-is-echt-een-bedrijf.biz",
        "zeker-geen-oplichting-{company}.biz",
        "{company}-officiele-website-echt-waar.info",
        "betrouwbaar-{company}-geloof-ons.net",
    ),
    "fr": (
        "{company}-vraie-entreprise.biz",
        "pas-une-arnaque-{company}.biz",
        "{company}-site-officiel-promis.info",
    ),
    "de": (
        "{company}-echte-firma.biz",
        "kein-betrug-{company}.biz",
        "{company}-offizielle-seite-wirklich.info",
    ),
    "es": (
        "{company}-empresa-de-verdad.biz",
        "no-es-estafa-{company}.biz",
        "{company}-web-oficial-lo-juro.info",
    ),
    "it": (
        "{company}-azienda-vera.biz",
        "non-e-una-truffa-{company}.biz",
        "{company}-sito-ufficiale-davvero.info",
    ),
    "pt": (
        "{company}-empresa-de-verdade.biz",
        "nao-e-golpe-{company}.biz",
        "{company}-site-oficial-juro.info",
    ),
    "sv": (
        "{company}-riktigt-foretag.biz",
        "inget-bedrageri-{company}.biz",
        "{company}-officiell-sida-lovar.info",
    ),
}
# The little words a surname starts with, in the talks' languages ("Van Wielen", "de la Cruz"): a name that starts
# with one, after its title, has no first name
_PARTICLES: Final = frozenset(
    {"van", "von", "de", "der", "den", "het", "ter", "ten", "la", "le", "di", "da", "du", "del", "della", "dos", "af"}
)


@dataclass(frozen=True)
class Ending:
    """A talk's end, as its closer sees it: its language's words (talkgenerator's own, in the talk's language), its
    presenter's name (on one line, or None), its title and its topic."""

    words: Language = languages.ENGLISH
    presenter: str | None = None
    title: str | None = None
    topic: str = ""

    @classmethod
    def of(
        cls, language: str = "en", presenter: str | None = None, title: str | None = None, topic: str = ""
    ) -> Ending:
        """The end of a talk in this language (its code: a ValueError for one talkgenerator doesn't know)."""
        name = " ".join(presenter.split()) if presenter and presenter.strip() else None
        return cls(languages.language(language), name, title, topic)


# A text a closer says: what it gives for the talk's end, or None for none
Said = Callable[[Ending], str | None]


@dataclass(frozen=True)
class Closer:
    """A format's closer: its big words, the line under them and the small note under that (see the module's
    documentation), and whether its big words ask a question (mark: a huge question mark goes beside them)."""

    title: Said
    line: Said | None = None
    note: Said | None = None
    mark: bool = False

    def slide(self, ending: Ending) -> CloserSlide:
        """The closer of a talk that ends so: its texts for the talk, in its language."""
        title, line, note = (said(ending) if said is not None else None for said in (self.title, self.line, self.note))
        return CloserSlide(title, line, note, mark=self.mark)


def said(word: str) -> Said:
    """talkgenerator's own word for the closer, in the talk's language: one of the Language's fields ("thanks"; a
    ValueError for one it doesn't have)."""
    if not isinstance(getattr(languages.ENGLISH, word, None), str):
        raise ValueError(f"talkgenerator has no word {word!r} in its languages (see talkgenerator.plan.languages)")
    return lambda ending: getattr(ending.words, word)


def in_every_language(texts: Mapping[str, str]) -> Said:
    """A format's own words for its closer, by the codes of the talk languages: all of them (a ValueError for one it
    leaves out, or one talkgenerator doesn't know)."""
    missing = sorted(set(languages.LANGUAGES) - set(texts))
    unknown = sorted(set(texts) - set(languages.LANGUAGES))
    if missing or unknown or not all(isinstance(text, str) and text.strip() for text in texts.values()):
        raise ValueError(f"A closer's words need every talk language: missing {missing}, unknown {unknown}")
    kept = dict(texts)
    return lambda ending: kept[ending.words.code]


def presenter(ending: Ending) -> str | None:
    """The presenter's name, as the title slide has it."""
    return ending.presenter


def contact_line(ending: Ending) -> str:
    """A pitch's made-up contact line (see contact), in the talk's language."""
    return contact(ending.presenter, ending.title, ending.topic, ending.words.code)


def product_line(ending: Ending) -> str:
    """A keynote's product, as its title names it (see product_name)."""
    return product_name(ending.title, ending.topic)


# The TED-like talk's closer, which every format without one of its own gets
DEFAULT: Final = Closer(said("thanks"), presenter, said("questions"))


def of(talk_format: Any) -> Closer:
    """The closer of a talk format (talkgenerator.schema.formats.Format): its own, or else DEFAULT (and for no format,
    a TED-like talk's, DEFAULT too)."""
    own = getattr(talk_format, "closer", None)
    return own if isinstance(own, Closer) else DEFAULT


def contact(presenter: str | None, title: str | None, topic: str, language: str = "en") -> str:
    """A pitch's made-up contact line: the presenter's first name (without a title such as "Dr.") at a domain made of
    the name of the startup that the title names ("Penguinly: Uber for Penguins"), or else of the startup a classic
    pitch names after its topic (talkgenerator.schema.formats.startup), with words in the talk's language that make it
    read as made up (D80): "anna@penguinly-is-a-real-company.biz"."""
    from talkgenerator.schema.formats import startup  # (here: the formats need much that a closer doesn't)

    company = re.sub(r"[^a-z0-9]+", "", _ascii(named(title) or startup(topic or "startup"))) or "startup"
    domains = _SILLY_DOMAINS.get(language, _SILLY_DOMAINS["en"])
    domain = domains[sum(map(ord, company)) % len(domains)].format(company=company)
    return f"{first_name(presenter) or 'hello'}@{domain}"


def product_name(title: str | None, topic: str) -> str:
    """The name of a keynote's product: as its title names it ("Penguin Pro: Flight, Reimagined"), or else as a classic
    keynote names it after its topic (talkgenerator.schema.formats.product)."""
    from talkgenerator.schema.formats import product  # (here, as in contact)

    return named(title) or product(topic or "product")


def named(title: str | None) -> str | None:
    """What a title names before its colon, when that's a name, as a pitch's and a keynote's titles name their startup
    and their product ("Penguinly: Uber for Penguins"): a few words, short. None for a title without one."""
    if not title or ":" not in title:
        return None
    name = title.split(":", 1)[0].strip()
    return name if 1 <= len(name.split()) <= _NAME_WORDS and len(name) <= _NAME_LENGTH else None


def first_name(presenter: str | None) -> str | None:
    """The presenter's first name, in lowercase letters without accents, as an e-mail address has it: their name's
    first word that's no title ("Prof. Anna Tomy": "anna"); or for a name without one, its surname, whole ("Juf Van
    Wielen": "vanwielen"). None for none."""
    words = [re.sub(r"[^a-z]+", "", _ascii(word)) for word in (presenter or "").replace(".", " ").split()]
    words = [word for word in words if word and word not in names.TITLES]
    if not words:
        return None
    return "".join(words) if words[0] in _PARTICLES else words[0]


def _ascii(text: str) -> str:
    """The text in lowercase, without accents ("Pingüino": "pinguino"), and without what has no ASCII form."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return decomposed.encode("ascii", "ignore").decode("ascii")
