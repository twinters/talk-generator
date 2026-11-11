"""Real facts in talks (docs/v5-plan.md, section 11, D60): a few true things for the nonsense to build on.

In a talk a language model writes, up to three of its slides that can build on a fact get one each, in the talk's one
request: a slide of history (a made-up historical figure's quote, two old photos of moments in history, a timeline), a
fun fact ("Did you know?"), a quiz or a big number. The facts are sentences of the lead of the topic's English
Wikipedia article. The model keeps what a fact says true where its slide states it, and twists it: "Only one species,
the Galapagos penguin, lives at the equator" becomes a fun fact about why. A slide that builds on its fact credits its
article (CC BY-SA 4.0).

Slides of history, and fun facts now and then, get a coincidence first (D73, in place of D60's events of the day the
talk is made on, which the user found confusing, and the same in talk after talk): a moment of the topic's history (a
sentence of its article with its year, the lead's or else the rest's) and something else that happened the same year,
from the year's article ("1886"), which the slide puts side by side as if one caused the other: "In 1886, Karl Benz
patented the motor car" and "1886: Coca-Cola is first sold in Atlanta". Its slide credits both articles.

No fact about a living person goes on a slide: none for a topic that is one (English Wikipedia's "Category:Living
people"), and none that names one (an article its sentence names, of the articles the lead links to, or a name a
year's event spells out, from 1910 on); nor one with a word a slide shouldn't make light of (see slide_texts.sensitive) or of death, war, disasters,
crime and accusations, politics or race (_GRIM_WORDS), nor one about real-world politics (see
talkgenerator.checks.deck.real_politics). When Wikipedia can't tell who's living, the facts that name someone stay out.

The facts are looked up once a talk, while its slides' seeds are (before the request, which waits for them), from the
cache of API responses (a week) or within a few seconds (DEADLINE, from the talk's start): a talk whose sources are
down goes without them, and so does one whose facts don't come in time (the next talk asks again, and gets the answers
that came too late from the cache). The deck records every fact it was given (Deck.facts): its text, its page and its
license, and its slide. With the same answers, the same seed gives the same deck, also when facts came too late: in a
block of http_util.same_answers (`talkgenerator check`), a talk made again gets the facts the first one got.

Flavour texts too (talkgenerator.sources.flavour), from three small free APIs that the user allowed on 2026-11-08: a
fun fact may build on a random useless fact instead ("25% of a human's bones are in its feet"), a dare dares the
presenter to tell a real dad joke (about the topic, if there's one: a groan they have to deliver), and the closing
slide's line under its title can be a real piece of advice. They pass the facts' checks and some of their own (no
insults, drink or faiths), and name no living person (the articles their capitalised words would be). A talk in another
language than English gets no dad jokes or advice, which its slides would say word for word, in English: a free model
put "Sing in the shower." on a German talk's closing slide (2026-11-09), also when asked for it translated.

A problem slide (D69) that's on a real problem's angle may start from a real how-to about the topic that people look
up on wikiHow ("How to Stop a Goose Attack"): a flavour text too, which an English talk gets, the problem-like ones
(stop, fix, deal with...) first.

Classic talks (English) have them where they fit: half of their fun facts are a real one, a sentence about the slide's
seed from Wikipedia or a useless fact, with an absurd twist of the content pack's, half of their quizzes a real one
from Open Trivia DB (talkgenerator.sources.opentdb), of the topic's kind (animals for penguins), half of their dares a
real dad joke to tell, and some of their closing lines a real piece of advice, each credited on the slide.
DISABLE_FACTS=1 turns all of it off, and DISABLE_WIKIPEDIA=1, DISABLE_OPENTDB=1, DISABLE_USELESS_FACTS=1,
DISABLE_DAD_JOKES=1 and DISABLE_ADVICE_SLIPS=1 a source.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Final
from urllib.parse import unquote

from talkgenerator import settings
from talkgenerator.datastructures.image_data import CreditPart
from talkgenerator.models.deck import Fact
from talkgenerator.plan import languages
from talkgenerator.sources import flavour, opentdb, wikipedia
from talkgenerator.util import http_util, language_util, random_util

logger = logging.getLogger("talkgenerator")

MOST: Final = 3  # facts in a talk's request, at most: one a slide
LONGEST: Final = 240  # characters in a fact for the request, at most
DEADLINE: Final = 8.0  # seconds from the start of a talk for its facts to come in (its seeds take 3 to 5)
REAL_SHARE: Final = 0.5  # of the classic fun facts and quizzes that are real ones, when they can be (dares: D65)
ADVICE_SHARE: Final = 0.4  # of the classic closing slides whose line under their title is a real piece of advice
JOKE_LONGEST: Final = 85  # characters in a dad joke, at most (a dare has 130, with what it asks)
ADVICE_LONGEST: Final = 60  # characters in a piece of advice, at most (the line under the closing title has 80)
HOWTO_LONGEST: Final = 90  # characters in a wikiHow how-to's title, at most ("How to ...", for a problem slide)

# What a slide of each kind does with its fact, as the request says it on the slide's line
_ASKS: Final = {
    "fun_fact": "Build it on this real fact: keep what it says true, and add an absurd twist of your own, so that the "
    "slide says more than the fact",
    "quiz": "Ask about this real fact: what it says is the right option's, and the other options are made up",
    "big_number": "Start from this real fact: its number can be the big one, with an absurd twist in what it counts",
    "timeline": "Put this real moment among the made-up ones, in its place by year (oldest first), with its year "
    "and a few words of your own",
    "history_quote": "The made-up figure lived through this real moment, or speaks of it",
    "history": "One of the moments is this real one, in a few words of your own",
    # (flavour texts: see talkgenerator.sources.flavour)
    "dare": "Dare the presenter to tell this real dad joke, word for word, and say how (a voice, a pause, a pose)",
    "questions": "Make the line under the title this real piece of advice, word for word or nearly",
    # (D69: a real how-to that people look up, for a problem slide on a real problem's angle)
    "problem": "Start from this real how-to, which people look up on wikiHow: the problem is what it's for, or that "
    "people need it at all, in your own words",
}
# What a slide does with a coincidence (D73): two real things of the same year, the topic's and another, side by side
# as if one caused the other
_COINCIDENCE_ASKS: Final = {
    "fun_fact": "Build it on these two real things that happened in the same year: keep both true, and state as "
    "certain that the first caused the second",
    "timeline": "Put these two real moments of the same year among the made-up ones, next to each other, as if the "
    "first caused the second, each with its year and a few words of your own",
    "history_quote": "The made-up figure lived through these two real moments of the same year, and is sure that the "
    "first caused the second",
    "history": "Its two moments are these two real ones of the same year, in a few words of your own each, the second "
    "as if the first caused it",
}
COINCIDENCE_YEARS: Final = 2  # years of the topic's history whose events a talk looks up, at most (a request each)
LIVING_SINCE: Final = 1910  # (the year from which a year's events may name someone alive today: none before it can)
# The uses of flavour texts, which a talk has besides its facts (MOST counts the facts alone)
_FLAVOUR_USES: Final = frozenset({"dare", "questions", "problem"})
# The uses that would rather have a coincidence (or else a moment of history, with its year) than another sentence of
# the topic's article
_HISTORY: Final = frozenset({"timeline", "history_quote", "history"})
# Words of facts a talk shouldn't make light of, besides the slides' (slide_texts.sensitive), which history is full
# of: death, war, disasters, crime and accusations, politics and race (a word ending in "*" stands for every word it
# starts). A word of the talk's topic is no reason (a talk on the Dead Sea may say "dead").
_GRIM_WORDS: Final = (
    "die dies died dead dying death* deadl* fatal* casualt* victim* kill* murder* massacr* slaughter* assassin* "
    "executed execution* suicid* drown* war wars warfare wartime warship* battle* army armies soldier* troop* "
    "militar* attack* bomb bombs bombed bombing* bomber* shooting* gunfire gunman gunmen weapon* missile* nuclear "
    "invad* invasion* genocid* terror* hostage* kidnap* hijack* riot riots coup coups rebel* uprising* earthquake* "
    "tsunami* disaster* catastroph* crash* explosion* exploded famine* epidemic* pandemic* plague* cancer* disease* "
    "injur* wounded wounds slave* slavery enslav* prison* imprison* arrest* convict* sentenced crime* criminal* "
    "alleged allegedly accus* scandal* abus* elected election* electoral vote voted votes voting voter* senat* "
    "parliament* congress* president* minister* politic* government* referendum* treaty treaties protest* regime* "
    "dictator* communis* fascis* sanction* annex* racial* racism* racist* segregat* apartheid ethnic* indigenous "
    "tribe tribes tribal"
)
_GRIM: Final = re.compile(
    r"\b(?:"
    + "|".join(re.escape(word[:-1]) + r"\w*" if word.endswith("*") else re.escape(word) for word in _GRIM_WORDS.split())
    + r"|african[- ]americans?|civil rights)\b",
    re.IGNORECASE,
)
# What makes a sentence a fun fact rather than what the topic is: a number, or a word that says how special it is
_SURPRISING: Final = re.compile(
    r"\d|\b(?:only|first|most|least|largest|smallest|biggest|oldest|youngest|longest|shortest|fastest|slowest|"
    r"highest|lowest|never|every|unique|rare|rarely|record|unlike|despite|surprisingly)\b",
    re.IGNORECASE,
)
_YEAR: Final = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b|\b\d{1,2}(?:st|nd|rd|th) century\b|\bBC\b|\bBCE\b")
_FIGURE: Final = re.compile(r"\d")
# Where a sentence ends: before a space and a capital, quote or digit, unless what ends there is an initial ("H. G.
# Wells") or an abbreviation
_SENTENCE_END: Final = re.compile(r"(?<=[.!?])\s+(?=[\"“'‘(\[A-Z0-9])")
_ABBREVIATIONS: Final = frozenset(
    "mr mrs ms dr prof st jr sr mt ft no nos vs etc al approx ca c e.g i.e u.s u.k inc ltd co corp gen lt col sgt rev "
    "fig jan feb mar apr jun jul aug sep sept oct nov dec".split()
)
_BRACKETS: Final = re.compile(r"\s*\([^()]*\)|\s*\[[^\[\]]*\]")
# A sentence that starts with a word for what the one before it said ("He also appears in all of the Peanuts films",
# of Snoopy) says nothing on its own
_BACK_REFERENCE: Final = re.compile(r"(?:he|she|it|they|his|her|its|their|this|these|those|such)\b", re.IGNORECASE)
# Words of flavour texts that a talk doesn't need, besides the facts' (fit): insults, drink and faiths, which jokes and
# advice have more than encyclopedias do
_UNFIT_FLAVOUR: Final = frozenset(
    "stupid idiot idiots dumb moron morons fat fatty obese ugly crazy insane psycho lunatic retard retarded lame "
    "cripple midget freak freaks weirdo loser losers damn hell crap shit piss ass arse bitch bastard drunk drunken "
    "alcohol alcoholic beer beers wine vodka whisky whiskey booze hangover cocktail catholic catholics nun nuns priest "
    "priests monk monks vicar pastor heaven sin sins pray prayer prayers bleach toilet".split()
)
# A word or name a flavour text capitalises: whose article might be a living person's
_CAPITALISED: Final = re.compile(r"\b[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,3}")


def on() -> bool:
    """Whether talks get real facts: unless DISABLE_FACTS says they don't."""
    return not settings.is_source_disabled("FACTS")


def use_of(kind: str, tags: Iterable[str] = ()) -> str | None:
    """What a planned slide of a kind (with its generator's tags) does with a real fact, or None if it has no use for
    one: a fun fact's, a quiz's, a big number's, a timeline's and a historical figure's quote's, and a slide of
    history's (two old photos of moments in history); and with a flavour text, a dare's (a dad joke), the closing
    slide's (a piece of advice) and a problem slide's (a how-to, D69)."""
    if kind in _ASKS and kind != "history":
        return kind
    return "history" if "history" in tags else None


@dataclass(frozen=True)
class Candidate:
    """A fact that a slide could get: its text, its page, where it's from (an article, or a flavour text's source),
    whether it's the article's first sentence (what the topic is), the articles it names (by title), and its source as
    credited, with its license; and for a coincidence (D73), the other real thing of its year (also: an event of the
    year's article, which it goes with)."""

    text: str
    url: str
    first: bool = False
    names: tuple[str, ...] = ()
    flavour: str = ""  # a flavour text's kind: "useless" (a useless fact), "joke" or "advice"; none for Wikipedia's
    source: str = "Wikipedia"
    license: str | None = wikipedia.LICENSE
    license_url: str | None = wikipedia.LICENSE_URL
    also: Candidate | None = None  # (a coincidence's other half: something else that happened the same year)

    @property
    def dated(self) -> bool:
        return bool(_YEAR.search(self.text))

    @property
    def figure(self) -> bool:
        return bool(_FIGURE.search(self.text))

    @property
    def surprising(self) -> bool:
        """Whether it says how special something is (a sentence of the article's lead, but its first)."""
        return not self.first and not self.flavour and self.also is None and bool(_SURPRISING.search(self.text))

    @property
    def coincidence(self) -> bool:
        return self.also is not None

    def fact(self, slide: int | None = None, use: str = "prompt") -> Fact:
        return Fact(
            text=self.text,
            source=self.source,
            url=self.url,
            license=self.license,
            license_url=self.license_url,
            slide=slide,
            use="slide" if use == "slide" else "prompt",
        )


@dataclass(frozen=True)
class Sheet:
    """The facts found for a talk: its topic's article's (if any), its coincidences, and its flavour texts, none about
    living people, in the order they came."""

    candidates: tuple[Candidate, ...] = ()


EMPTY: Final = Sheet()


@dataclass(frozen=True)
class Given:
    """A fact a planned slide gets, with what the slide does with it (see use_of); for a coincidence, with the other
    real thing of its year (also)."""

    use: str
    fact: Fact
    also: Fact | None = None

    def line(self) -> str:
        """What the request says about it, after the slide's brief: for a coincidence, both real things and that one
        caused the other."""
        text = self.fact.text.replace('"', "'")
        if self.also is not None and self.use in _COINCIDENCE_ASKS:
            other = self.also.text.replace('"', "'")
            return f'{_COINCIDENCE_ASKS[self.use]}: "{text}", and the same year, "{other}"'
        return f'{_ASKS[self.use]}: "{text}"'

    @property
    def facts(self) -> tuple[Fact, ...]:
        """The real facts it gives its slide: the one, or a coincidence's two."""
        return (self.fact, self.also) if self.also is not None else (self.fact,)


# THE FACTS OF A TALK A LANGUAGE MODEL WRITES


def request_line(language: str = "en") -> str:
    """What the request says about the facts, once, when some of its slides get one. In a talk in another language,
    that they're English, to be told in the talk's language in words of the model's own: a free model put "Over
    duizend soorten kaas bestaan" on a Dutch slide, word for word in English's order, and an English useless fact on a
    French one, as it was (D74)."""
    name = languages.language(language).name
    english = (
        f" The facts are in English: tell them in {name}, in your own words, as a {name} speaker would, never in English "
        "and never word for word."
        if language != languages.ENGLISH.code
        else ""
    )
    return (
        "Real facts: some slides come with one (from Wikipedia, or a real useless fact, dad joke or piece of advice), to "
        "mix with the nonsense. Keep what a fact says true where the slide states it, put the absurd around it, and pin "
        "nothing made up on a real person." + english
    )


class Gathering:
    """The facts of a talk being looked up in the background, from the start of the talk: result() waits for them
    until DEADLINE seconds after that start, and gives none if they're not in by then (they're kept in the cache for
    the next talk). In a block of http_util.same_answers, a talk made again gets what the first one got."""

    def __init__(self, key: tuple[object, ...], work: Callable[[], Sheet], deadline: float | None = None) -> None:
        self._key = key
        self._until = time.monotonic() + (DEADLINE if deadline is None else deadline)
        self._done = threading.Event()
        self._sheet = EMPTY
        threading.Thread(target=self._run, args=(work,), name="facts", daemon=True).start()

    def _run(self, work: Callable[[], Sheet]) -> None:
        try:
            self._sheet = work()
        except Exception:  # a source that misbehaves shouldn't sink the talk: it goes without facts
            logger.exception("Looking up real facts for the talk crashed: it goes without them")
        finally:
            self._done.set()

    def result(self) -> Sheet:
        return http_util.keep(self._key, self._wait)

    def _wait(self) -> Sheet:
        # (a talk that's late may be a busy computer's rather than Wikipedia's: so the next talk asks as always, and
        # gets the answers that came too late for this one from the cache. Wikipedia's own outages and slow answers
        # keep it out for a while, as every source's do: see http_util.search_json)
        if not self._done.wait(max(0.0, self._until - time.monotonic())):
            logger.warning("Real facts didn't come in %.0f seconds: the talk goes without them", DEADLINE)
            return EMPTY
        return self._sheet


_asked: ThreadPoolExecutor | None = None
_asked_lock = threading.Lock()


def _asking() -> ThreadPoolExecutor:
    """The threads that ask the sources for talks' facts: kept from one talk to the next, so that their sessions (and
    connections, until a server closes them: see http_util.close_idle_connections) are too, as http_util's sessions
    are a thread's. A new thread's first request costs a session and a connection (and on a busy computer, measured
    on 2026-11-08 with twenty Python processes at work, six to nine seconds). Its tasks never wait for one another."""
    global _asked
    with _asked_lock:
        if _asked is None:
            _asked = ThreadPoolExecutor(max_workers=8, thread_name_prefix="facts")
        return _asked


@dataclass(frozen=True)
class Draws:
    """A talk's draws for its flavour texts, made before they're looked up (by its random stream: see gather), so that
    the same seed asks for the same ones: two numbers of the week's useless facts, a page of dad jokes (for a topic
    that has none of its own), and two numbers of advice slips (the second for when the first doesn't fit)."""

    useless: tuple[int, ...] = (0, 1)
    joke_page: int = 1
    advice: tuple[int, ...] = (1, 2)

    @classmethod
    def of(cls, rng: random_util.Rng) -> Draws:
        return cls(
            tuple(rng.sample(range(flavour.POOL), 2)),
            rng.randint(1, flavour.JOKE_PAGES),
            tuple(rng.sample(range(1, flavour.ADVICE_SLIPS + 1), 2)),
        )


# The uses that build on Wikipedia's facts (the others on flavour texts)
_WIKIPEDIA_USES: Final = frozenset({"fun_fact", "quiz", "big_number", "timeline", "history_quote", "history"})


def gather(
    topic: str,
    language: str = "en",
    today: datetime.date | None = None,
    uses: Iterable[str] | None = None,
    rng: random_util.Rng | None = None,
) -> Gathering:
    """Start looking up a talk's facts (see Gathering): for the uses its slides have (see use_of; all of them, without
    uses), its topic's English Wikipedia article's, its coincidences (of the years before today's, unless another day
    is given), and the flavour texts they want, drawn by the talk's random stream (see Draws)."""
    day = today or datetime.date.today()
    wanted = frozenset(uses) if uses is not None else frozenset(_ASKS)
    draws = Draws.of(rng.child("flavour")) if rng is not None else Draws()
    key = ("facts", topic, language, day.isoformat(), tuple(sorted(wanted)), draws)
    return Gathering(key, lambda: look_up(topic, language, day, wanted, draws))


def look_up(
    topic: str,
    language: str,
    day: datetime.date,
    uses: frozenset[str] = frozenset(_ASKS),
    draws: Draws = Draws(),
) -> Sheet:
    """A talk's facts (see the module's documentation), for the uses its slides have: the article's sentences that pass
    the checks, its coincidences (for the slides of history and fun facts: see coincidences), and the flavour texts that
    do (useless facts for a fun fact, dad jokes for a dare, advice for the closing slide), none about a living person."""
    if not on():
        return EMPTY
    if language != languages.ENGLISH.code:
        uses = uses - _FLAVOUR_USES  # (no dad jokes or advice, which a slide says word for word, in English)
    started = time.monotonic()
    asking = _asking()
    wiki = wikipedia.available() and bool(uses & _WIKIPEDIA_USES)
    found = asking.submit(wikipedia.article, topic, language) if wiki else None
    useless = [asking.submit(flavour.useless_fact, number) for number in draws.useless] if "fun_fact" in uses else []
    joking = asking.submit(_jokes_about, topic, draws.joke_page) if "dare" in uses else None
    advising = [asking.submit(flavour.advice, number) for number in draws.advice] if "questions" in uses else []
    fixing = asking.submit(howtos, topic) if "problem" in uses else None
    article = found.result() if found is not None else None
    lead = article_candidates(article, topic)
    # (the years of the topic's history, and what else happened in them: for the slides that put the two side by side)
    years: list[int] = []
    coincidences: list[Candidate] = []
    if article is not None and uses & _COINCIDENCE_USES:
        coincidences = coincidence_candidates(article, lead, topic, day.year, asking, years)
    flavours = [
        *((future.result(), "useless") for future in useless),
        *((joke, "joke") for joke in (joking.result() if joking is not None else [])),
        *((future.result(), "advice") for future in advising),
        *((howto, "howto") for howto in (fixing.result() if fixing is not None else [])),
    ]
    looked_up = time.monotonic()
    candidates = [
        *lead,
        *coincidences,
        *(candidate for candidate in (flavour_candidate(text, kind, topic) for text, kind in flavours) if candidate),
    ]
    checked = time.monotonic()
    kept = asking.submit(without_living, candidates).result()
    logger.info(
        "Real facts: %s of %s (%s), %s coincidences (of %s), %s flavour texts, in %.1f s (%.1f s to look up, %.1f s "
        "to check, %.1f s for who's living)",
        sum(not candidate.coincidence and not candidate.flavour for candidate in kept),
        "the article" if article is not None else "no article",
        article.title if article is not None else topic,
        sum(candidate.coincidence for candidate in kept),
        ", ".join(str(year) for year in years) or "no year",
        sum(bool(candidate.flavour) for candidate in kept),
        time.monotonic() - started,
        looked_up - started,
        checked - looked_up,
        time.monotonic() - checked,
    )
    return Sheet(tuple(kept))


def article_candidates(article: wikipedia.Article | None, topic: str = "", longest: int = LONGEST) -> list[Candidate]:
    """The sentences of an article's lead that could be facts: as long as a fact may be, saying something on their own
    (not "He also appears in..."), and passing the checks (none of the lead of an article about a living person), each
    with the articles it names."""
    if article is None or article.living:
        return []
    candidates = []
    for index, sentence in enumerate(sentences(article.extract)):
        alone = not _BACK_REFERENCE.match(sentence)
        if len(sentence) <= longest and alone and fit(sentence, topic or article.title):
            names = tuple(title for title in article.links if names_article(sentence, title))
            candidates.append(Candidate(sentence, article.url, first=index == 0, names=names))
    return candidates


# COINCIDENCES (D73): a moment of the topic's history and something else that happened the same year, which a slide puts
# side by side as if one caused the other

# The uses that put a coincidence on their slide
_COINCIDENCE_USES: Final = frozenset(_COINCIDENCE_ASKS)
# The year a sentence dates something to: four digits after a word that dates ("in 1886", "since 1791", "by 1902"), a
# month ("May 1886") or a day ("8 May 1886"), or at its start ("1886 was..."), but not a figure ("1500 metres")
_DATED: Final = re.compile(
    r"(?:\b(?:in|since|by|from|until|till|after|before|during|around|circa|c\.|early|late|mid|"
    + "|".join(wikipedia.MONTHS)
    + r")(?:\s+\d{1,2},?)?\s+|^)(1[0-9]{3}|20[0-9]{2})(?![\d,.]*\s*(?:metres|meters|km|kilometres|kilometers|miles|"
    r"feet|kg|kilograms|tonnes|tons|people|species|years|m\b))",
    re.IGNORECASE,
)
EVENTS_A_YEAR: Final = 12  # of a year's events that pass the checks, the ones a talk keeps (the lively ones first)
RECENT: Final = 10  # years before this one whose events are mostly the news (politics, crises): none of those
# What makes a year's event the news of its day, which a talk leaves out besides the facts' checks (fit): governments,
# crowns, money and borders, which a year's article lists more than anything (and nobody laughs at a currency's fall)
_NEWS: Final = re.compile(
    r"\b(?:crisis|crises|dispute\w*|agreement\w*|alliance\w*|independence|constitution\w*|reign\w*|throne|crown\w*|"
    r"succeed\w*|monarch\w*|king|kings|queen|queens|emperor\w*|empress\w*|prince\w*|duke\w*|count|countess|pope\w*|"
    r"cardinal\w*|bishop\w*|church\w*|currency|currencies|devalu\w*|bank|banks|recession\w*|strike|strikes|"
    r"revolution\w*|rebel\w*|fleet\w*|siege\w*|surrender\w*|colon\w*|conquest\w*|occupation\w*|BRICS|NATO|"
    r"United Nations|European Union|EU|territor\w*|border\w*|province\w*|navy|naval|armada\w*|tsar\w*|sultan\w*|"
    r"gun|guns|revolver\w*|rifle\w*|pistol\w*|cannon\w*|musket\w*|opium|cocaine|heroin|missionar\w*|mormon\w*|"
    r"religio\w*|temple\w*|mosque\w*|cathedral\w*|monaster\w*|saint\w*|holy)\b",
    re.IGNORECASE,
)
# What makes one lively: a first, an invention, something opening, coming out or going on show
_LIVELY: Final = re.compile(
    r"\b(?:first|invent\w*|discover\w*|patent\w*|found(?:s|ed|ing)?|open(?:s|ed|ing)?|publish\w*|premiere\w*|"
    r"launch\w*|record\w*|introduc\w*|unveil\w*|releas\w*|debut\w*|demonstrat\w*|exhibit\w*|perform\w*|sold|sells?|"
    r"complet\w*|built|builds|arriv\w*)\b",
    re.IGNORECASE,
)


def year_of(text: str, this_year: int) -> int | None:
    """The year a sentence dates something to (see _DATED), when its year's article lists its events: from
    wikipedia.FIRST_YEAR to RECENT years before this one; else None."""
    for found in _DATED.finditer(text):
        year = int(found.group(1))
        if wikipedia.FIRST_YEAR <= year <= this_year - RECENT:
            return year
    return None


def history_candidates(article: wikipedia.Article, topic: str, this_year: int) -> list[Candidate]:
    """The sentences of the rest of an article (beyond its lead) that date a moment of its topic's history (see
    year_of), as facts that pass the checks, each with the names it spells out (from LIVING_SINCE on: for who's
    living)."""
    lead = set(sentences(article.extract))
    found = []
    for sentence in sentences(wikipedia.article_text(article.title)):
        year = year_of(sentence, this_year)
        if sentence in lead or year is None or len(sentence) > LONGEST or _BACK_REFERENCE.match(sentence):
            continue
        if fit(sentence, topic or article.title):
            names = tuple(title for title in article.links if names_article(sentence, title))
            spelled = _names_in(sentence) if year >= LIVING_SINCE else ()
            found.append(Candidate(sentence, article.url, names=tuple(dict.fromkeys((*names, *spelled)))))
    return found


def coincidence_candidates(
    article: wikipedia.Article,
    lead: Sequence[Candidate],
    topic: str,
    this_year: int,
    asking: ThreadPoolExecutor | None = None,
    years: list[int] | None = None,
) -> list[Candidate]:
    """A topic's coincidences: each moment of its history (a sentence of its lead that dates something, or else of the
    rest of its article: see year_of), of its first COINCIDENCE_YEARS years, with each of the events of its year (from
    the year's article, EVENTS_A_YEAR of those that pass the checks, spread over the year) that's about something else
    (none of the topic's telling words, nor two of the moment's). The years looked up go in years, if given."""
    if article.living:
        return []
    dated = [candidate for candidate in lead if year_of(candidate.text, this_year) is not None]
    if not dated:
        dated = history_candidates(article, topic, this_year)
    picked: list[int] = []
    for candidate in dated:
        year = year_of(candidate.text, this_year)
        if year is not None and year not in picked:
            picked.append(year)
    picked = picked[:COINCIDENCE_YEARS]
    if years is not None:
        years[:] = picked
    if not picked:
        return []
    listed = asking.map(wikipedia.year_events, picked) if asking is not None else map(wikipedia.year_events, picked)
    about = set(_telling(f"{topic} {article.title}"))
    events = {year: _year_candidates(year, found, topic, about) for year, found in zip(picked, listed, strict=True)}
    coincidences = []
    for candidate in dated:
        year = year_of(candidate.text, this_year)
        moment = set(_telling(candidate.text))
        for event in events.get(year, ()) if year is not None else ():
            if len(set(_telling(event.text)) & moment) < 2:  # (not the same moment, told twice)
                coincidences.append(dataclasses.replace(candidate, also=event))
    return coincidences


def _year_candidates(year: int, events: Sequence[wikipedia.Event], topic: str, about: set[str]) -> list[Candidate]:
    """A year's events as the second halves of coincidences ("1886: Coca-Cola is first sold in Atlanta"): those that
    pass the checks, aren't the news of their day (_NEWS), say something on their own (not "French Revolution:", over
    the events it lists) and are about something else than the topic, EVENTS_A_YEAR at most, the lively ones first
    (_LIVELY: firsts, inventions, premieres); with the names they spell out, from LIVING_SINCE on."""
    usable = []
    for event in events:
        text = _without_brackets(event.text).strip()
        if len(text) < _SHORTEST_EVENT or text.endswith(":") or _BACK_REFERENCE.match(text) or _NEWS.search(text):
            continue
        told = f"{year}: {text}"
        if set(_telling(text)) & about or len(told) > LONGEST or not fit(text, topic):
            continue
        names = _names_in(text) if year >= LIVING_SINCE else ()
        usable.append(Candidate(told, wikipedia.year_url(year), names=names))
    lively = [candidate for candidate in usable if _LIVELY.search(candidate.text)]
    return [*lively, *(candidate for candidate in usable if candidate not in lively)][:EVENTS_A_YEAR]


_SHORTEST_EVENT: Final = 30  # (characters of a year's event, at least: a shorter one is a heading, or says little)


def _names_in(text: str) -> tuple[str, ...]:
    """The capitalised words and names a text spells out, as articles that might be a living person's."""
    return tuple(dict.fromkeys(found.group(0).strip(" .'") for found in _CAPITALISED.finditer(text)))[:8]


# What a flavour text of each kind may be at most: a useless fact as a fact, a joke and advice as their slides take
# them, and a how-to as the request gives it
_FLAVOUR_LONGEST: Final = {"useless": LONGEST, "joke": JOKE_LONGEST, "advice": ADVICE_LONGEST, "howto": HOWTO_LONGEST}


def flavour_candidate(text: flavour.Flavour | None, kind: str, topic: str = "") -> Candidate | None:
    """A flavour text as a fact a slide could get (kind "useless", "joke" or "advice"), with its capitalised words and
    names as the articles it may name (for who's living); none for one that's too long or doesn't fit a talk."""
    if text is None or len(text.text) > _FLAVOUR_LONGEST[kind] or not fit_flavour(text.text, topic):
        return None
    names = tuple(dict.fromkeys(found.group(0).strip(" .'") for found in _CAPITALISED.finditer(text.text)))
    return Candidate(
        text.text, text.url, names=names[:8], flavour=kind, source=text.source, license=None, license_url=None
    )


# What a how-to says that makes its problem plain: what it stops, fixes or gets rid of (D69)
_FIXING: Final = re.compile(
    r"^(?:stop|fix|repair|deal with|cope with|get rid of|prevent|avoid|escape|overcome|quit|fight|handle|repel|"
    r"unclog|untangle|remove|calm|survive|clean|unstick|rescue|recover|tell if|know if)\b"
    r"|^keep\b.*\b(?:away|from|off|out)\b",
    re.IGNORECASE,
)


def howtos(topic: str) -> list[flavour.Flavour]:
    """wikiHow's how-tos about the topic, as flavour texts for a problem slide (D69): "How to Stop a Goose Attack",
    with its page, the ones that say what they fix first (each group in wikiHow's order); none when wikiHow is off."""
    from talkgenerator.sources import wikihow  # (here: its search reads related words, which load late)

    try:
        actions = wikihow.get_related_wikihow_actions(topic)
    except Exception:  # (a source that misbehaves leaves the problem slide without one, not the talk without facts)
        logger.exception("Looking up wikiHow's how-tos for a problem slide crashed: it goes without one")
        return []
    ordered = [action for action in actions if _FIXING.match(action)] + [
        action for action in actions if not _FIXING.match(action)
    ]
    return [flavour.Flavour(f"How to {action}", "wikiHow", wikihow.page_of(action)) for action in ordered[:HOWTOS]]


HOWTOS: Final = 6  # how-tos about a topic a talk looks at, at most (the ones that say what they fix first)


def _jokes_about(topic: str, page: int) -> list[flavour.Flavour]:
    """Dad jokes about the topic's longest word, in the singular (whose search finds "penguin" in "penguins", but not
    the other way round) and as a whole word, or else the page's."""
    words = [word for word in re.findall(r"[a-zA-Z]{3,}", topic) if word.lower() not in _STOPWORDS]
    word = language_util.to_singular(max(words, key=len).lower()) if words else ""
    jokes = flavour.dad_jokes(word) if word else []
    return jokes[:12] or flavour.dad_jokes(page=page)[:12]


def without_living(candidates: Sequence[Candidate]) -> list[Candidate]:
    """The candidates that name no living person, as English Wikipedia's articles tell (all those that name nobody,
    when it can't tell), a coincidence in neither of its halves."""
    named = {title for candidate in candidates for title in _named(candidate)}
    people = wikipedia.living(named) if named else frozenset()
    if people is None:
        logger.info("Wikipedia couldn't tell who's living: the facts that name someone stay out")
        return [candidate for candidate in candidates if not _named(candidate)]
    return [candidate for candidate in candidates if not people & _named(candidate)]


def _named(candidate: Candidate) -> set[str]:
    """The articles a candidate names, a coincidence's in both its halves."""
    return set(candidate.names) | (set(candidate.also.names) if candidate.also is not None else set())


def assign(sheet: Sheet, slides: Sequence[tuple[int, str]], rng: random_util.Rng) -> dict[int, Given]:
    """The facts that the slides get, by slide number (as given): up to MOST slides, in order, one each, never one
    fact twice (nor a sentence that's half of another slide's coincidence), and a flavour text for a dare and the
    closing slide besides. A slide of history gets a coincidence first (D73), then a sentence with a date; a big number
    one with a number; a fun fact one that says how special something is (not what the topic is: the first sentence),
    a coincidence or a useless fact; a quiz any of the article's; a dare a dad joke, and the closing slide a piece of
    advice. Among the ones a slide likes as much, its pick is the random stream's."""
    taken: set[str] = set()  # (the texts given so far)
    given: dict[int, Given] = {}
    facts = 0
    shuffled = list(sheet.candidates)
    rng.shuffle(shuffled)
    for number, use in slides:
        if use not in _FLAVOUR_USES and facts == MOST:
            continue
        ranked = [(rank, candidate) for candidate in shuffled if (rank := _rank(candidate, use)) is not None]
        fresh = [(rank, candidate) for rank, candidate in ranked if not _texts(candidate) & taken]
        if not fresh:
            continue
        best = min(fresh, key=lambda ranked_candidate: ranked_candidate[0])[1]
        taken |= _texts(best)
        also = best.also.fact(number) if best.also is not None else None
        given[number] = Given(use, best.fact(number), also)
        facts += use not in _FLAVOUR_USES
    return given


def _texts(candidate: Candidate) -> set[str]:
    return {candidate.text} | ({candidate.also.text} if candidate.also is not None else set())


def _rank(candidate: Candidate, use: str) -> int | None:
    """How well a fact suits a slide's use: the lower, the better; None for one it can't use."""
    if use in _FLAVOUR_USES or candidate.flavour:
        wanted = {"dare": "joke", "questions": "advice", "fun_fact": "useless", "problem": "howto"}.get(use)
        if not candidate.flavour or candidate.flavour != wanted:
            return None
        # (a how-to that says what it fixes makes a plainer problem: D69)
        return 1 if wanted == "howto" and not _FIXING.match(candidate.text.removeprefix("How to ")) else 0
    if use in _HISTORY:
        return 0 if candidate.coincidence else 1 if candidate.dated else 2 if not candidate.first else 3
    if candidate.coincidence and use not in _COINCIDENCE_USES:  # (a big number counts something, a quiz asks one thing)
        return None
    if use == "big_number":
        return 0 if candidate.figure else 1
    if use == "fun_fact":
        return 0 if candidate.surprising or candidate.coincidence else 1 if not candidate.first else 2
    return 0  # (a quiz)


def used_in(fact: Fact, texts: Iterable[str | None]) -> bool:
    """Whether a slide's texts build on a fact: two of its telling words (of four letters or more, and its years) are
    in them, or its only one ("A bean untaxed is a vassal unchecked, as the emperor knew in 1278", of "1278: Emperor
    Tran Thanh Tong retires"), or one of its figures, which counts for two (a big number of "383/km2", of Belgium's
    population density of 383/km2)."""
    words = set(_telling(fact.text)) | set(_YEARS.findall(fact.text))
    figures = _figures(fact.text) - words
    written = " ".join(text for text in texts if text)
    shared = len(words & (set(_telling(written)) | set(_YEARS.findall(written)))) + 2 * len(figures & _figures(written))
    return bool(words or figures) and shared >= min(2, len(words) + 2 * len(figures))


_YEARS: Final = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b")
_FIGURE_DIGITS: Final = re.compile(r"\d[\d,.]*\d")  # (of two digits or more, as "30,689" or "11.8")


def _figures(text: str) -> set[str]:
    return {found.group(0).replace(",", "") for found in _FIGURE_DIGITS.finditer(text)}


_STOPWORDS: Final = frozenset(
    "that this with from were have been they their there which when what where while also into than then them these "
    "those such some most many more only over under about after before because being other very much each".split()
)


def _telling(text: str) -> list[str]:
    return [word for word in re.findall(r"[^\W\d_]{4,}", text.lower()) if word not in _STOPWORDS]


def credit(fact: Fact) -> tuple[CreditPart, ...]:
    """A fact's credit, as a slide's credit line has it: "Wikipedia: Penguin (CC BY-SA 4.0)"."""
    page = fact.url or ""
    title = page.rsplit("/wiki/", 1)[-1].replace("_", " ") if "/wiki/" in page else ""
    named = f"{fact.source}: {unquote(title)}" if title else fact.source
    if not fact.license:
        return ((named, fact.url),)
    return ((named, fact.url), (" (", None), (fact.license, fact.license_url), (")", None))


# THE CHECKS


def fit(text: str, topic: str = "") -> bool:
    """Whether a real fact may go on a slide: no word that a slide shouldn't make light of, nor of death, war,
    disasters, crime, politics or race (but those of the topic: see _GRIM_WORDS), and nothing about real-world
    politics (unless the topic is about it)."""
    from talkgenerator.checks.deck import real_politics  # (it reads the deck's models)
    from talkgenerator.sources import slide_texts  # (which has the classic generators that use this module)

    about = set(re.findall(r"[a-z]+", topic.lower()))
    grim = [found.group(0) for found in _GRIM.finditer(text) if found.group(0).lower() not in about]
    return not grim and not slide_texts.sensitive(text) and real_politics(text, topic) is None


def fit_flavour(text: str, topic: str = "") -> bool:
    """Whether a flavour text (a useless fact, a dad joke, a piece of advice) may go on a slide: as a fact may (fit),
    and without an insult, drink or a faith (_UNFIT_FLAVOUR), which jokes have more than encyclopedias."""
    words = set(re.findall(r"[a-z]+", text.lower().replace("’", "'")))
    return fit(text, topic) and not words & _UNFIT_FLAVOUR


def sentences(extract: str) -> list[str]:
    """An article's lead as sentences, without what's in brackets (pronunciations, dates of birth, notes)."""
    found: list[str] = []
    for paragraph in extract.splitlines():
        text = " ".join(_without_brackets(paragraph).split())
        start = 0
        for end in _SENTENCE_END.finditer(text):
            before = text[start : end.start()]
            last = before.rsplit(" ", 1)[-1].rstrip(".!?").lower()
            if (len(last) == 1 and last.isalpha()) or last in _ABBREVIATIONS:
                continue  # (an initial, or an abbreviation)
            found.append(before.strip())
            start = end.end()
        if text[start:].strip():
            found.append(text[start:].strip())
    return [sentence for sentence in found if len(sentence) > 20 and sentence[-1:] in ".!?"]


def _without_brackets(text: str) -> str:
    for _ in range(2):  # (brackets in brackets)
        text = _BRACKETS.sub("", text)
    return " ".join(text.split()).replace(" ,", ",").replace(" .", ".")


def names_article(sentence: str, title: str) -> bool:
    """Whether a sentence names an article: its title (without its qualifier in brackets), or, for a name of several
    capitalised words ("Isabel Joy Bear"), the last of them, as a name."""
    plain = re.sub(r"\s*\([^)]*\)", "", title).strip()
    if not plain:
        return False
    if re.search(r"(?<!\w)" + re.escape(plain) + r"(?!\w)", sentence, re.IGNORECASE):
        return True
    words = plain.split()
    if len(words) > 1 and all(word[:1].isupper() for word in words) and len(words[-1]) > 3:
        return re.search(r"(?<!\w)" + re.escape(words[-1]) + r"(?!\w)", sentence) is not None
    return False


# CLASSIC SLIDES


class CreditedText(str):
    """A text from a source that asks for credit (a real fact, a real quiz question): it reads as the text, and
    carries the fact it shows, for the slide's credit line and the deck (see SlideGeneratorData.generate)."""

    fact: Fact

    def __new__(cls, text: str, fact: Fact) -> CreditedText:
        made = super().__new__(cls, text)
        made.fact = fact
        return made


def classic_on() -> bool:
    return on() and wikipedia.available()


def real_sentence(seed: str, longest: int) -> Candidate | None:
    """A real sentence about a classic slide's seed, for a fun fact: of its English Wikipedia article's lead, as long
    as it may be, one that says how special something is (else another, else what the seed is), naming no living
    person; the slide's random stream picks among those it likes as much."""
    article = wikipedia.article(seed)
    candidates = without_living(article_candidates(article, seed, longest))
    if not candidates:
        return None
    ranks = [_rank(candidate, "fun_fact") or 0 for candidate in candidates]  # (an article's: never None)
    return random_util.choice(
        [candidate for candidate, rank in zip(candidates, ranks, strict=True) if rank == min(ranks)]
    )


def trivia_on() -> bool:
    return on() and opentdb.available()


def real_question(topic: str, seed: str, longest: int, longest_option: int) -> tuple[opentdb.Question, Fact] | None:
    """A real quiz question for a classic slide: one of Open Trivia DB's of the topic's kind (by its English Wikipedia
    article's description: animals for penguins), that fits the slide and passes the checks, about the seed or the
    topic if there's one, else any (the slide's random stream picks)."""
    article = wikipedia.article(topic) if wikipedia.available() else None
    category = opentdb.category_for(article.description if article is not None else "")
    usable = [
        question
        for question in opentdb.questions(category)
        if len(question.question) <= longest
        and all(len(option) <= longest_option for option in (question.answer, *question.wrong))
        and fit(" ".join((question.question, question.answer, *question.wrong)), topic)
    ]
    if not usable:
        return None
    about = set(_telling(f"{seed} {topic}"))
    matching = [question for question in usable if about & set(_telling(question.question))]
    question = random_util.choice(matching or usable)
    fact = Fact(
        text=f"{question.question} (Answer: {question.answer})",
        source="Open Trivia DB",
        url=opentdb.SITE,
        license=opentdb.LICENSE,
        license_url=opentdb.LICENSE_URL,
        use="slide",
    )
    return question, fact


def flavour_on(name: str) -> bool:
    """Whether classic slides get a flavour source's texts: with real facts on, and the source ("USELESS_FACTS",
    "DAD_JOKES" or "ADVICE_SLIPS")."""
    return on() and flavour.available(name)


def real_useless_fact(longest: int) -> Candidate | None:
    """A useless fact for a classic fun fact: one of the week's pool, which the slide's random stream picks (or the
    next one, when it doesn't fit), naming no living person."""
    start = random_util.randrange(flavour.POOL)
    for number in (start, (start + 1) % flavour.POOL):
        candidate = flavour_candidate(flavour.useless_fact(number), "useless")
        if candidate is not None and len(candidate.text) <= longest and without_living([candidate]):
            return candidate
    return None


def real_joke(seed: str, longest: int) -> Candidate | None:
    """A dad joke for a classic dare: one about the seed's longest word, if there are any, else one of a page of all
    of them (the slide's random stream picks both), as long as the dare takes, naming no living person."""
    page = random_util.randint(1, flavour.JOKE_PAGES)
    jokes = [flavour_candidate(joke, "joke", seed) for joke in _jokes_about(seed, page)]
    usable = without_living([joke for joke in jokes if joke is not None and len(joke.text) <= longest])
    return random_util.choice(usable) if usable else None


def real_advice(longest: int) -> Candidate | None:
    """A piece of advice for a classic closing slide: the advice slip the slide's random stream picks (or one of the
    next two, when it doesn't fit), naming no living person."""
    start = random_util.randint(1, flavour.ADVICE_SLIPS)
    for number in (start, start + 1, start + 2):
        candidate = flavour_candidate(flavour.advice(number), "advice")
        if candidate is not None and len(candidate.text) <= longest and without_living([candidate]):
            return candidate
    return None
