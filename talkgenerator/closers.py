"""The closer (docs/v5-plan.md, D76): the slide after a talk's last, which says that the talk is over, in its language,
its look and its format's kind, outside the slides it asked for.

The user found the end of a talk on talkgenerator.com unclear (2026-11-12): only the corner of the presentation said
"8 / 8", and going on did nothing. And academic talks and all-hands spent one of their slides on "Questions?" (pitches
too, and a TED-like talk now and then), which their closer says now, so that every slide a talk asks for is one of its
content. Its words are talkgenerator's own, in every talk language (talkgenerator.plan.languages); what else it says
comes from the talk: its presenter's name, and a pitch's startup or a keynote's product, as its title names them.

- A TED-like talk: "Thank you!", with the presenter's name under it and a small "Questions?".
- An academic talk: "Questions?", with "Thank you for your attention" under it, the presenter's name, and a huge
  question mark beside them.
- A pitch: "Let's talk", with a made-up contact line under it (the presenter's first name at the startup's domain:
  "anna@penguinly.com") and the presenter's name.
- An all-hands: "Questions?", with "Back to work" under it, the presenter's name, and the question mark.
- A keynote: "Available today", with the product's name under it, and the presenter's name.

A talk's deck marks it (DeckSlide.closer), and its slides' numbers ("7/12") don't count it: talkgenerator.com shows
"The end" where its number would be, and lowers its curtain once the presenter goes on from it.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from talkgenerator import names
from talkgenerator.plan import languages
from talkgenerator.slide.slides import CloserSlide

# The kinds of closers, a format's each: the TED-like talk's (also every format without a closer of its own), the
# academic talk's, the pitch's, the all-hands' (corporate) and the keynote's
TED: Final = "ted"
KINDS: Final = (TED, "academic", "pitch", "corporate", "keynote")

# What a title names before its colon, when that's a name ("Penguinly: Uber for Penguins"): a few words, short
_NAME_WORDS: Final = 3
_NAME_LENGTH: Final = 24
# A domain that a startup's name has already ("Penguin.ai"), else it gets one
_DOMAIN: Final = re.compile(r"^[a-z0-9-]+\.[a-z]{2,6}$")
_TLD: Final = ".com"
# The little words a surname starts with, in the talks' languages ("Van Wielen", "de la Cruz"): a name that starts
# with one, after its title, has no first name
_PARTICLES: Final = frozenset(
    {"van", "von", "de", "der", "den", "het", "ter", "ten", "la", "le", "di", "da", "du", "del", "della", "dos", "af"}
)


def closer(
    kind: str = TED,
    *,
    presenter: str | None = None,
    title: str | None = None,
    topic: str = "",
    language: str = "en",
) -> CloserSlide:
    """The closer of a talk of a format with this kind of closer (one of KINDS: a format without one of its own has
    the TED-like talk's), in the talk's language: from its presenter's name, its title and its topic."""
    if kind not in KINDS:
        raise ValueError(f"There's no closer of kind {kind!r}; there are {', '.join(KINDS)}")
    words = languages.language(language)
    name = " ".join(presenter.split()) if presenter and presenter.strip() else None
    if kind == "academic":
        return CloserSlide(words.questions, words.attention, name, mark=True)
    if kind == "corporate":
        return CloserSlide(words.questions, words.back_to_work, name, mark=True)
    if kind == "pitch":
        return CloserSlide(words.lets_talk, contact(name, title, topic), name)
    if kind == "keynote":
        return CloserSlide(words.available, product_name(title, topic), name)
    return CloserSlide(words.thanks, name, words.questions)


def contact(presenter: str | None, title: str | None, topic: str) -> str:
    """A pitch's made-up contact line: the presenter's first name (without a title such as "Dr.") at the domain of
    the startup that the title names ("Penguinly: Uber for Penguins"), or else of the startup a classic pitch names
    after its topic (talkgenerator.schema.formats.startup): "anna@penguinly.com"."""
    from talkgenerator.schema.formats import startup  # (here: the formats need much that a closer doesn't)

    company = _ascii(named(title) or startup(topic or "startup"))
    domain = company if _DOMAIN.match(company.replace(" ", "")) else re.sub(r"[^a-z0-9]+", "", company) + _TLD
    return f"{first_name(presenter) or 'hello'}@{domain.replace(' ', '')}"


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
