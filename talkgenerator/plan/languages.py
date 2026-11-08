"""The languages talks can be in (docs/v5-plan.md, section 5.9).

A language model (or an agent's plan) writes a talk in its language, and talkgenerator adds a few words of its own:
the title slide's "By ...", a chart's "Yes" and "No", a social media post's likes and shares, a news story's
breaking news, the "Did you know?" over a fun fact and the "Challenge" over a dare, an alignment chart's axes (lawful
to chaotic, good to evil) and the "Continued on next slide" under a wall of text, which this module has in every
language. The classic generator only speaks English, so in a talk in another language, a slide that doesn't come out
as planned becomes a picture without text instead of a classic slide. The language check reads texts with NLTK's
stopword lists (and a language's words that look like English ones, which they leave out): a language model whose
answer starts in English, for a talk in another language, is asked again (see reads_as_english), and the check of a
deck finds a talk that reads as English. The spelling fixes of what's typed for a talk leave the compounds alone of a
language that writes them as one word.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
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
    # An alignment chart's axes, as Dungeons & Dragons has them: across, from lawful to chaotic, and down, from good to
    # evil (as the game's editions in the language say them)
    lawful_to_chaotic: tuple[str, str, str] = ("Lawful", "Neutral", "Chaotic")
    good_to_evil: tuple[str, str, str] = ("Good", "Neutral", "Evil")
    continued: str = "Continued on next slide"  # under a wall of text
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
            lawful_to_chaotic=("Wettig", "Neutraal", "Chaotisch"),
            good_to_evil=("Goed", "Neutraal", "Kwaad"),
            continued="Vervolg op de volgende dia",
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
            lawful_to_chaotic=("Loyal", "Neutre", "Chaotique"),
            good_to_evil=("Bon", "Neutre", "Mauvais"),
            continued="Suite à la diapositive suivante",
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
            lawful_to_chaotic=("Rechtschaffen", "Neutral", "Chaotisch"),
            good_to_evil=("Gut", "Neutral", "Böse"),
            continued="Fortsetzung auf der nächsten Folie",
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
            lawful_to_chaotic=("Legal", "Neutral", "Caótico"),
            good_to_evil=("Bueno", "Neutral", "Malvado"),
            continued="Continúa en la siguiente diapositiva",
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
            lawful_to_chaotic=("Legale", "Neutrale", "Caotico"),
            good_to_evil=("Buono", "Neutrale", "Malvagio"),
            continued="Continua nella prossima slide",
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
            lawful_to_chaotic=("Leal", "Neutro", "Caótico"),
            good_to_evil=("Bom", "Neutro", "Mau"),
            continued="Continua no próximo slide",
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
            lawful_to_chaotic=("Laglig", "Neutral", "Kaotisk"),
            good_to_evil=("God", "Neutral", "Ond"),
            continued="Fortsättning på nästa bild",
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


_WORD: Final = re.compile(r"[^\W\d_]+")


@cache
def telling_words(code: str) -> tuple[frozenset[str], frozenset[str]]:
    """The little words that tell a text in the language from one in English, by NLTK's stopword lists: the
    language's own that English doesn't have ("de", "het"), and English ones that it doesn't have ("the", "of"), but
    its words that look like English ones (english_lookalikes: Swedish "is", ice)."""
    from talkgenerator.util import language_util  # (here: the languages themselves need no NLTK)

    spoken = language(code)
    own = language_util.stopwords(spoken.stopwords)
    english = language_util.stopwords(ENGLISH.stopwords)
    return own - english, english - own - spoken.english_lookalikes


def reads_as_english(texts: Iterable[str], code: str) -> bool:
    """Whether texts that are to be in the language read as English instead (never for English): at least three of
    English's telling little words (see telling_words), and more than twice as many as of the language's own. A free
    model wrote a Swedish talk in English (2026-11-08): the talk's spine, its title, thesis and presenter's job, tells
    before its slides come in, and the model is asked again (see talkgenerator.schema.presentation_schema)."""
    if code == ENGLISH.code:
        return False
    own, english = telling_words(code)
    words = [word for text in texts for word in _WORD.findall(text.lower())]
    in_english = sum(word in english for word in words)
    return in_english >= 3 and in_english > 2 * sum(word in own for word in words)
