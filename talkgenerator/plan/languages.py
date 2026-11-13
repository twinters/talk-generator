"""The languages talks can be in (docs/v5-plan.md, section 5.9).

A language model (or an agent's plan) writes a talk in its language, and talkgenerator adds a few words of its own:
the title slide's "By ...", a chart's "Yes" and "No", a social media post's likes and shares, a news story's
breaking news, the "Did you know?" over a fun fact, the "Challenge" over a dare (and "Audience participation" over a
dare for everyone), "The problem" over a problem slide whose heading a model left empty, an alignment chart's axes
(lawful to chaotic, good to evil), the "Continued on next slide" under a wall of text, the words of the closer, the
slide after a talk's last (D76: "Thank you!", "Questions?", "Let's talk"...), and the words of the slides of a
picture to explain (D78: an exhibit's "Exhibit A" and its case number, "Pick one:" and the "OR" between two
pictures, "What do you see?", and "Before" and "After"), which this module has in every language. The classic
generator only speaks English, so in a talk in another language, a slide that doesn't come out as planned becomes a
picture without text instead of a classic slide. The language check reads texts with
NLTK's stopword lists (and a language's words that look like English ones, which they leave out): a language model
whose answer starts in English, for a talk in another language, is asked again (see reads_as_english), and the check
of a deck finds a talk that reads as English. The spelling fixes of what's typed for a talk leave the compounds alone
of a language that writes them as one word.

A language model is asked for a talk in another language as a native speaker of it writes (D74, see
talkgenerator.plan.prompt.native_line), with one of the language's words that only look like English ones and the
words that have capitals in its titles; and a topic's articles are left off to look up what it is in English (see
talkgenerator.schema.slide_topic_generators.english_name), and don't count toward the words that make what's typed a
title (see talkgenerator.titles.clearly_a_title).
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
    # Before a quiz's question, so the presenter knows at once that it's a quiz (one of them, by the question's letters)
    quizzes: tuple[str, ...] = ("Quiz:", "Pop quiz:", "Quiz time:", "Question for you:", "Test yourself:")
    dare: str = "Challenge"  # over a dare for the presenter
    audience: str = "Audience participation"  # over a dare for the whole audience
    problem: str = "The problem"  # over a problem slide whose heading the model left empty (D69)
    # An alignment chart's axes, as Dungeons & Dragons has them: across, from lawful to chaotic, and down, from good to
    # evil (as the game's editions in the language say them)
    lawful_to_chaotic: tuple[str, str, str] = ("Lawful", "Neutral", "Chaotic")
    good_to_evil: tuple[str, str, str] = ("Good", "Neutral", "Evil")
    continued: str = "Continued on next slide"  # under a wall of text
    # The closer's words (D76: the slide after a talk's last, outside its count, of its format's kind; see
    # talkgenerator.closers): a TED-like talk's thanks, with a small question under it; an academic talk's question,
    # with its thanks under it (and an all-hands' question); a pitch's invitation; the all-hands' way back to work; and
    # the availability of a keynote's product
    thanks: str = "Thank you!"
    questions: str = "Questions?"
    attention: str = "Thank you for your attention"
    lets_talk: str = "Let's talk"
    back_to_work: str = "Back to work"
    available: str = "Available today"
    # (and those of D79's formats: an infomercial's call to order, with its operators under it; a documentary's thanks
    # for watching; a court case's end of session; a museum tour's thanks, with the way to its gift shop under them; a
    # wedding toast's last words; and a book report's end, with the pupil's plea under it)
    call_now: str = "Call now!"
    standing_by: str = "Operators are standing by"
    watching: str = "Thanks for watching"
    adjourned: str = "Court is adjourned"
    visiting: str = "Thank you for visiting"
    gift_shop: str = "The gift shop is on your left"
    happy_couple: str = "To the happy couple!"
    the_end: str = "The End"
    sit_down: str = "Can I sit down now?"
    # The words of the slides of a picture to explain (D78): an exhibit's, before its letter ("Exhibit A"), and its
    # case's number ({number}: "Case No. 4417-23"); the heading over two pictures to pick one of, and the word between
    # them; the question over a picture to see something in; and the words over a before and an after
    exhibit: str = "Exhibit"
    case: str = "Case No. {number}"
    pick_one: str = "Pick one:"
    either_or: str = "OR"
    what_do_you_see: str = "What do you see?"
    before_after: tuple[str, str] = ("Before", "After")
    # Whether it writes compounds as one word ("pinguïnsekte", "Pinguinsekte", "pingvinsekt"), which the spelling
    # fixes of what's typed for a talk then leave alone (see talkgenerator.sources.word_frequency)
    compounds: bool = False
    # Its words that are English stopwords too but missing from its own NLTK list, which the language check then
    # doesn't count as English (Swedish "in", "all" and "just", and "is", ice)
    english_lookalikes: frozenset[str] = frozenset()
    # The articles a topic may start with ("les vacances"), which looking up what it is in English leaves off when the
    # topic as typed finds nothing (see talkgenerator.schema.slide_topic_generators.english_topics)
    articles: tuple[str, ...] = ()
    # An English word that a word of the language only looks like, with the word it is instead (D74: a free model
    # wrote "graf", a grave, for a graph in a Dutch talk), for the request's line on writing as a native speaker would
    false_friend: str = ""
    # Which words of a title have a capital in the language, for that same line (English titles have one on every word)
    capitals: str = "only its first word and names"


ENGLISH: Final = Language(
    "en", "English", ("By", "A presentation by", "Presented by"), "Yes", "No", "english", articles=("the", "a", "an")
)

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
            quizzes=("Quiz:", "Quizvraag:", "Vraag:", "Test voor jullie:", "Even testen:"),
            dare="Uitdaging",
            audience="Publieksparticipatie",
            problem="Het probleem",
            lawful_to_chaotic=("Wettig", "Neutraal", "Chaotisch"),
            good_to_evil=("Goed", "Neutraal", "Kwaad"),
            continued="Vervolg op de volgende dia",
            thanks="Bedankt!",
            questions="Vragen?",
            attention="Bedankt voor jullie aandacht",
            lets_talk="Laten we praten",
            back_to_work="En nu weer aan het werk",
            available="Vanaf vandaag verkrijgbaar",
            call_now="Bel nu!",
            standing_by="Onze medewerkers staan voor u klaar",
            watching="Bedankt voor het kijken",
            adjourned="De zitting is gesloten",
            visiting="Bedankt voor jullie bezoek",
            gift_shop="De museumwinkel is links",
            happy_couple="Op het bruidspaar!",
            the_end="Einde",
            sit_down="Mag ik nu gaan zitten?",
            exhibit="Bewijsstuk",
            case="Zaaknr. {number}",
            pick_one="Kies er één:",
            either_or="OF",
            what_do_you_see="Wat zie je?",
            before_after=("Voor", "Na"),
            compounds=True,
            articles=("de", "het", "een", "'t"),
            false_friend="a graph is a 'grafiek', never a 'graf' (a grave)",
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
            quizzes=("Quiz :", "Question :", "Petit test :", "Question pour vous :"),
            dare="Défi",
            audience="Participation du public",
            problem="Le problème",
            lawful_to_chaotic=("Loyal", "Neutre", "Chaotique"),
            good_to_evil=("Bon", "Neutre", "Mauvais"),
            continued="Suite à la diapositive suivante",
            thanks="Merci !",
            questions="Des questions ?",
            attention="Merci de votre attention",
            lets_talk="Parlons-en",
            back_to_work="Et maintenant, au travail",
            available="Disponible dès aujourd'hui",
            call_now="Appelez vite !",
            standing_by="Nos conseillers attendent votre appel",
            watching="Merci de nous avoir regardés",
            adjourned="L'audience est levée",
            visiting="Merci de votre visite",
            gift_shop="La boutique est sur votre gauche",
            happy_couple="Vive les mariés !",
            the_end="Fin",
            sit_down="Je peux m'asseoir maintenant ?",
            exhibit="Pièce à conviction",
            case="Affaire n° {number}",
            pick_one="Choisissez :",
            either_or="OU",
            what_do_you_see="Que voyez-vous ?",
            before_after=("Avant", "Après"),
            articles=("le", "la", "les", "l'", "l’", "un", "une", "des", "du"),
            false_friend="'actually' is 'en fait', never 'actuellement' (currently)",
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
            quizzes=("Quiz:", "Quizfrage:", "Frage an euch:", "Kleiner Test:"),
            dare="Aufgabe",
            audience="Publikumsbeteiligung",
            problem="Das Problem",
            lawful_to_chaotic=("Rechtschaffen", "Neutral", "Chaotisch"),
            good_to_evil=("Gut", "Neutral", "Böse"),
            continued="Fortsetzung auf der nächsten Folie",
            thanks="Danke!",
            questions="Fragen?",
            attention="Vielen Dank für Ihre Aufmerksamkeit",
            lets_talk="Lassen Sie uns reden",
            back_to_work="Und jetzt zurück an die Arbeit",
            available="Ab heute erhältlich",
            call_now="Jetzt anrufen!",
            standing_by="Unsere Mitarbeiter warten auf Ihren Anruf",
            watching="Danke fürs Zuschauen",
            adjourned="Die Sitzung ist geschlossen",
            visiting="Danke für Ihren Besuch",
            gift_shop="Der Museumsshop ist links",
            happy_couple="Auf das Brautpaar!",
            the_end="Ende",
            sit_down="Darf ich mich jetzt setzen?",
            exhibit="Beweisstück",
            case="Aktenzeichen {number}",
            pick_one="Entscheide dich:",
            either_or="ODER",
            what_do_you_see="Was siehst du?",
            before_after=("Vorher", "Nachher"),
            compounds=True,
            articles=("der", "die", "das", "den", "dem", "ein", "eine"),
            false_friend="'eventually' is 'schließlich', never 'eventuell' (perhaps)",
            capitals="its first word, names and every noun",
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
            quizzes=("Quiz:", "Pregunta:", "Pregunta para ustedes:", "Pequeño test:"),
            dare="Reto",
            audience="Participación del público",
            problem="El problema",
            lawful_to_chaotic=("Legal", "Neutral", "Caótico"),
            good_to_evil=("Bueno", "Neutral", "Malvado"),
            continued="Continúa en la siguiente diapositiva",
            thanks="¡Gracias!",
            questions="¿Preguntas?",
            attention="Gracias por su atención",
            lets_talk="Hablemos",
            back_to_work="Y ahora, a trabajar",
            available="Disponible desde hoy",
            call_now="¡Llame ya!",
            standing_by="Nuestros operadores le esperan",
            watching="Gracias por vernos",
            adjourned="Se levanta la sesión",
            visiting="Gracias por su visita",
            gift_shop="La tienda está a su izquierda",
            happy_couple="¡Vivan los novios!",
            the_end="Fin",
            sit_down="¿Ya me puedo sentar?",
            exhibit="Prueba",
            case="Caso n.º {number}",
            pick_one="Elige uno:",
            either_or="O",
            what_do_you_see="¿Qué ves?",
            before_after=("Antes", "Después"),
            articles=("el", "la", "los", "las", "un", "una", "unos", "unas"),
            false_friend="'embarrassed' is 'avergonzado', never 'embarazada' (pregnant)",
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
            quizzes=("Quiz:", "Domanda:", "Domanda per voi:", "Piccolo test:"),
            dare="Sfida",
            audience="Partecipazione del pubblico",
            problem="Il problema",
            lawful_to_chaotic=("Legale", "Neutrale", "Caotico"),
            good_to_evil=("Buono", "Neutrale", "Malvagio"),
            continued="Continua nella prossima slide",
            thanks="Grazie!",
            questions="Domande?",
            attention="Grazie per l'attenzione",
            lets_talk="Parliamone",
            back_to_work="E ora, tutti al lavoro",
            available="Disponibile da oggi",
            call_now="Chiamate subito!",
            standing_by="I nostri operatori vi aspettano",
            watching="Grazie per la visione",
            adjourned="L'udienza è tolta",
            visiting="Grazie per la visita",
            gift_shop="Il bookshop è sulla sinistra",
            happy_couple="Viva gli sposi!",
            the_end="Fine",
            sit_down="Posso sedermi adesso?",
            exhibit="Reperto",
            case="Fascicolo n. {number}",
            pick_one="Scegline uno:",
            either_or="O",
            what_do_you_see="Cosa vedi?",
            before_after=("Prima", "Dopo"),
            articles=("il", "lo", "la", "i", "gli", "le", "l'", "l’", "un", "uno", "una", "un'", "un’"),
            false_friend="'actually' is 'in realtà', never 'attualmente' (currently)",
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
            quizzes=("Quiz:", "Pergunta:", "Pergunta para vocês:", "Teste rápido:"),
            dare="Desafio",
            audience="Participação do público",
            problem="O problema",
            lawful_to_chaotic=("Leal", "Neutro", "Caótico"),
            good_to_evil=("Bom", "Neutro", "Mau"),
            continued="Continua no próximo slide",
            thanks="Obrigado!",
            questions="Perguntas?",
            attention="Obrigado pela atenção",
            lets_talk="Vamos conversar",
            back_to_work="E agora, de volta ao trabalho",
            available="Disponível a partir de hoje",
            call_now="Ligue já!",
            standing_by="Nossos atendentes estão esperando",
            watching="Obrigado por assistir",
            adjourned="A sessão está encerrada",
            visiting="Obrigado pela visita",
            gift_shop="A loja fica à sua esquerda",
            happy_couple="Vivam os noivos!",
            the_end="Fim",
            sit_down="Já posso me sentar?",
            exhibit="Prova",
            case="Processo n.º {number}",
            pick_one="Escolha um:",
            either_or="OU",
            what_do_you_see="O que você vê?",
            before_after=("Antes", "Depois"),
            articles=("o", "a", "os", "as", "um", "uma"),
            false_friend="'to pretend' is 'fingir', never 'pretender' (to intend)",
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
            quizzes=("Quiz:", "Fråga:", "Fråga till er:", "Litet test:"),
            dare="Utmaning",
            audience="Publikmedverkan",
            problem="Problemet",
            lawful_to_chaotic=("Laglig", "Neutral", "Kaotisk"),
            good_to_evil=("God", "Neutral", "Ond"),
            continued="Fortsättning på nästa bild",
            thanks="Tack!",
            questions="Frågor?",
            attention="Tack för er uppmärksamhet",
            lets_talk="Låt oss prata",
            back_to_work="Och nu tillbaka till jobbet",
            available="Finns i butik i dag",
            call_now="Ring nu!",
            standing_by="Våra operatörer väntar på ditt samtal",
            watching="Tack för att ni tittade",
            adjourned="Förhandlingen är avslutad",
            visiting="Tack för ert besök",
            gift_shop="Museibutiken ligger till vänster",
            happy_couple="Leve brudparet!",
            the_end="Slut",
            sit_down="Får jag sätta mig nu?",
            exhibit="Bevis",
            case="Mål nr {number}",
            pick_one="Välj en:",
            either_or="ELLER",
            what_do_you_see="Vad ser du?",
            before_after=("Före", "Efter"),
            compounds=True,
            # (into, all, just, to ask, a village and ice)
            english_lookalikes=frozenset({"in", "all", "just", "be", "by", "is"}),
            articles=("en", "ett"),
            false_friend="a gift is a 'present', never 'gift' (married, or poison)",
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
