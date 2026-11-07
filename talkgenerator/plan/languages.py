"""The languages talks can be in (docs/v5-plan.md, section 5.9).

A language model (or an agent's plan) writes a talk in its language, and talkgenerator adds a few words of its own:
the title slide's "By ...", a chart's "Yes" and "No", a social media post's likes and shares, and a news story's
breaking news, which this module has in every language. The classic
generator only speaks English, so in a talk in another language, a slide that doesn't come out as planned becomes a
picture without text instead of a classic slide. The language check reads texts with NLTK's stopword lists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Language:
    code: str
    name: str  # in English, for the prompt
    by: tuple[str, ...]  # how the title slide credits the presenter, as in "By Ann Example"
    yes: str
    no: str
    stopwords: str  # the name of NLTK's stopword list for it
    likes: str = "likes"  # under a social media post, as in "12K likes"
    shares: str = "shares"
    breaking: str = "BREAKING NEWS"  # over a news story on television


ENGLISH: Final = Language("en", "English", ("By", "A presentation by", "Presented by"), "Yes", "No", "english")

LANGUAGES: Final[dict[str, Language]] = {
    language.code: language
    for language in (
        ENGLISH,
        Language(
            "nl",
            "Dutch",
            ("Door", "Een presentatie van", "Gepresenteerd door"),
            "Ja",
            "Nee",
            "dutch",
            likes="likes",
            shares="keer gedeeld",
            breaking="NIEUWSFLITS",
        ),
        Language(
            "fr",
            "French",
            ("Par", "Une présentation de", "Présenté par"),
            "Oui",
            "Non",
            "french",
            likes="j'aime",
            shares="partages",
            breaking="DERNIÈRE MINUTE",
        ),
        Language(
            "de",
            "German",
            ("Von", "Ein Vortrag von", "Präsentiert von"),
            "Ja",
            "Nein",
            "german",
            likes="Likes",
            shares="Mal geteilt",
            breaking="EILMELDUNG",
        ),
        Language(
            "es",
            "Spanish",
            ("Por", "Una presentación de", "Presentado por"),
            "Sí",
            "No",
            "spanish",
            likes="me gusta",
            shares="veces compartido",
            breaking="ÚLTIMA HORA",
        ),
        Language(
            "it",
            "Italian",
            ("A cura di", "Una presentazione di", "Presentato da"),
            "Sì",
            "No",
            "italian",
            likes="mi piace",
            shares="condivisioni",
            breaking="ULTIM'ORA",
        ),
        Language(
            "pt",
            "Portuguese",
            ("Por", "Uma apresentação de", "Apresentado por"),
            "Sim",
            "Não",
            "portuguese",
            likes="curtidas",
            shares="compartilhamentos",
            breaking="ÚLTIMA HORA",
        ),
    )
}


def language(code: str) -> Language:
    """The language with this code, such as "nl" (ValueError for one talkgenerator doesn't know)."""
    found = LANGUAGES.get(code)
    if found is None:
        raise ValueError(f"talkgenerator doesn't know the language {code!r}; it knows {', '.join(LANGUAGES)}")
    return found
