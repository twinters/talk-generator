"""The languages talks can be in (docs/v5-plan.md, section 5.9).

A language model (or an agent's plan) writes a talk in its language, and talkgenerator adds a few words of its own:
the title slide's "By ...", a chart's "Yes" and "No", a social media post's likes and shares, a news story's
breaking news, the "Did you know?" over a fun fact and the "Challenge" over a dare, which this module has in every
language. The classic generator only speaks English, so in a talk in another language, a slide that doesn't come out
as planned becomes a picture without text instead of a classic slide. The language check reads texts with NLTK's
stopword lists (and a language's words that look like English ones, which they leave out), and the spelling fixes of
what's typed for a talk leave the compounds alone of a language that writes them as one word.
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
    fun_facts: tuple[str, ...] = ("Did you know?", "Fun fact")  # over a fun fact (one of them)
    dare: str = "Challenge"  # over a dare for the presenter
    # Whether it writes compounds as one word ("pinguïnsekte", "Pinguinsekte", "pingvinsekt"), which the spelling
    # fixes of what's typed for a talk then leave alone (see talkgenerator.sources.word_frequency)
    compounds: bool = False
    # Its words that are English stopwords too but missing from its own NLTK list, which the language check then
    # doesn't count as English (Swedish "in", "all" and "just", and "is", ice)
    english_lookalikes: frozenset[str] = frozenset()


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
            fun_facts=("Wist je dat?", "Weetje"),
            dare="Uitdaging",
            compounds=True,
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
            fun_facts=("Le saviez-vous ?", "Anecdote"),
            dare="Défi",
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
            fun_facts=("Schon gewusst?", "Fun Fact"),
            dare="Aufgabe",
            compounds=True,
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
            fun_facts=("¿Sabías que...?", "Dato curioso"),
            dare="Reto",
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
            fun_facts=("Lo sapevi?", "Curiosità"),
            dare="Sfida",
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
            fun_facts=("Você sabia?", "Curiosidade"),
            dare="Desafio",
        ),
        Language(
            "sv",
            "Swedish",
            ("Av", "En presentation av", "Presenterad av"),
            "Ja",
            "Nej",
            "swedish",
            likes="gilla-markeringar",  # (as Facebook and Instagram say it in Swedish)
            shares="delningar",
            breaking="JUST NU",  # (as Swedish news sites and SVT flag breaking news)
            fun_facts=("Visste du?", "Kul fakta"),
            dare="Utmaning",
            compounds=True,
            # (into, all, just, to ask, a village and ice)
            english_lookalikes=frozenset({"in", "all", "just", "be", "by", "is"}),
        ),
    )
}


def language(code: str) -> Language:
    """The language with this code, such as "nl" (ValueError for one talkgenerator doesn't know)."""
    found = LANGUAGES.get(code)
    if found is None:
        raise ValueError(f"talkgenerator doesn't know the language {code!r}; it knows {', '.join(LANGUAGES)}")
    return found
