"""Real facts in talks (docs/v5-plan.md, section 11, D60): a few true things for the nonsense to build on.

In a talk a language model writes, up to three of its slides that can build on a fact get one each, in the talk's one
request: a slide of history (a made-up historical figure's quote, two old photos of moments in history, a timeline), a
fun fact ("Did you know?"), a quiz or a big number. The facts are sentences of the lead of the topic's English
Wikipedia article, and events of the day the talk is made on, from Wikipedia's main page ("On this day"), which the
slides of history get first. The model keeps what a fact says true where its slide states it, and twists it: "Only one
species, the Galapagos penguin, lives at the equator" becomes a fun fact about why. A slide that builds on its fact
credits its article (CC BY-SA 4.0).

No fact about a living person goes on a slide: none for a topic that is one (English Wikipedia's "Category:Living
people"), and none that names one (an article its sentence names, of the articles the lead links to, or that an event
links to); nor one with a word a slide shouldn't make light of (see slide_texts.sensitive) or of death, war, disasters,
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

A problem slide (D66) that's on a real problem's angle may start from a real how-to about the topic that people look
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
    # (D66: a real how-to that people look up, for a problem slide on a real problem's angle)
    "problem": "Start from this real how-to, which people look up on wikiHow: the problem is what it's for, or that "
    "people need it at all, in your own words",
}
# The uses of flavour texts, which a talk has besides its facts (MOST counts the facts alone)
_FLAVOUR_USES: Final = frozenset({"dare", "questions", "problem"})
# The uses that would rather have an event of the day than a sentence of the topic's article
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
    slide's (a piece of advice) and a problem slide's (a how-to, D66)."""
    if kind in _ASKS and kind != "history":
        return kind
    return "history" if "history" in tags else None


@dataclass(frozen=True)
class Candidate:
    """A fact that a slide could get: its text, its page, where it's from (an article's lead, the day's events, or a
    flavour text's source), whether it's the article's first sentence (what the topic is), the articles it names (by
    title), and its source as credited, with its license."""

    text: str
    url: str
    day: bool = False  # an event of the day's (with its date), not a sentence of the topic's article
    first: bool = False
    names: tuple[str, ...] = ()
    flavour: str = ""  # a flavour text's kind: "useless" (a useless fact), "joke" or "advice"; none for Wikipedia's
    source: str = "Wikipedia"
    license: str | None = wikipedia.LICENSE
    license_url: str | None = wikipedia.LICENSE_URL

    @property
    def dated(self) -> bool:
        return self.day or bool(_YEAR.search(self.text))

    @property
    def figure(self) -> bool:
        return bool(_FIGURE.search(self.text))

    @property
    def surprising(self) -> bool:
        """Whether it says how special something is (a sentence of the article's lead, but its first)."""
        return not self.first and not self.day and not self.flavour and bool(_SURPRISING.search(self.text))

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
    """The facts found for a talk: its topic's article's (if any), and the day's events', none about living people,
    in the order they came."""

    candidates: tuple[Candidate, ...] = ()


EMPTY: Final = Sheet()


@dataclass(frozen=True)
class Given:
    """A fact a planned slide gets, with what the slide does with it (see use_of)."""

    use: str
    fact: Fact

    def line(self) -> str:
        """What the request says about it, after the slide's brief: for a timeline, an event of the day with its year
        alone ("1291: A law was passed..."), as models copied its whole date into a date's short field."""
        text = self.fact.text.replace('"', "'")
        day = _DAY.match(text) if self.use == "timeline" else None
        return f'{_ASKS[self.use]}: "{text[day.end() :] if day else text}"'


# THE FACTS OF A TALK A LANGUAGE MODEL WRITES


def request_line(language: str = "en") -> str:
    """What the request says about the facts, once, when some of its slides get one."""
    english = (
        " The facts are in English; write the slides in the talk's language, as asked." if language != "en" else ""
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
    uses), its topic's English Wikipedia article's and the day's events (of today, unless another day is given), and the
    flavour texts they want, drawn by the talk's random stream (see Draws)."""
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
    """A talk's facts (see the module's documentation), for the uses its slides have: the article's sentences, and the
    day's events, that pass the checks, and the flavour texts that do (useless facts for a fun fact, dad jokes for a
    dare, advice for the closing slide), none about a living person."""
    if not on():
        return EMPTY
    if language != languages.ENGLISH.code:
        uses = uses - _FLAVOUR_USES  # (no dad jokes or advice, which a slide says word for word, in English)
    started = time.monotonic()
    asking = _asking()
    wiki = wikipedia.available() and bool(uses & _WIKIPEDIA_USES)
    found = asking.submit(wikipedia.article, topic, language) if wiki else None
    happened = asking.submit(wikipedia.on_this_day, day.month, day.day) if wiki else None
    useless = [asking.submit(flavour.useless_fact, number) for number in draws.useless] if "fun_fact" in uses else []
    joking = asking.submit(_jokes_about, topic, draws.joke_page) if "dare" in uses else None
    advising = [asking.submit(flavour.advice, number) for number in draws.advice] if "questions" in uses else []
    fixing = asking.submit(howtos, topic) if "problem" in uses else None
    article = found.result() if found is not None else None
    events = happened.result() if happened is not None else []
    flavours = [
        *((future.result(), "useless") for future in useless),
        *((joke, "joke") for joke in (joking.result() if joking is not None else [])),
        *((future.result(), "advice") for future in advising),
        *((howto, "howto") for howto in (fixing.result() if fixing is not None else [])),
    ]
    looked_up = time.monotonic()
    candidates = [
        *article_candidates(article, topic),
        *day_candidates(events, day, topic),
        *(candidate for candidate in (flavour_candidate(text, kind, topic) for text, kind in flavours) if candidate),
    ]
    checked = time.monotonic()
    kept = asking.submit(without_living, candidates).result()
    logger.info(
        "Real facts: %s of %s (%s), %s of the day's %s events, %s flavour texts, in %.1f s (%.1f s to look up, %.1f s "
        "to check, %.1f s for who's living)",
        sum(not candidate.day and not candidate.flavour for candidate in kept),
        "the article" if article is not None else "no article",
        article.title if article is not None else topic,
        sum(candidate.day for candidate in kept),
        len(events),
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


def day_candidates(events: Sequence[wikipedia.Event], day: datetime.date, topic: str = "") -> list[Candidate]:
    """The events of the day that could be facts, with their dates: "8 November 1895: Wilhelm Röntgen discovers
    X-rays...", passing the checks."""
    url = wikipedia.anniversaries_url(day.month, day.day)
    candidates = []
    for event in events:
        text = f"{day.day} {wikipedia.MONTHS[day.month - 1]} {event.year}: {_without_brackets(event.text)}"
        if len(text) <= LONGEST and fit(event.text, topic):
            candidates.append(Candidate(text, url, day=True, names=event.pages))
    return candidates


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


# What a how-to says that makes its problem plain: what it stops, fixes or gets rid of (D66)
_FIXING: Final = re.compile(
    r"^(?:stop|fix|repair|deal with|cope with|get rid of|prevent|avoid|escape|overcome|quit|fight|handle|repel|"
    r"unclog|untangle|remove|calm|survive|clean|unstick|rescue|recover|tell if|know if)\b"
    r"|^keep\b.*\b(?:away|from|off|out)\b",
    re.IGNORECASE,
)


def howtos(topic: str) -> list[flavour.Flavour]:
    """wikiHow's how-tos about the topic, as flavour texts for a problem slide (D66): "How to Stop a Goose Attack",
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
    when it can't tell)."""
    named = {title for candidate in candidates for title in candidate.names}
    people = wikipedia.living(named) if named else frozenset()
    if people is None:
        logger.info("Wikipedia couldn't tell who's living: the facts that name someone stay out")
        return [candidate for candidate in candidates if not candidate.names]
    return [candidate for candidate in candidates if not people & set(candidate.names)]


def assign(sheet: Sheet, slides: Sequence[tuple[int, str]], rng: random_util.Rng) -> dict[int, Given]:
    """The facts that the slides get, by slide number (as given): up to MOST slides, in order, one each, never one
    fact twice, and a flavour text for a dare and the closing slide besides. A slide of history gets an event of the
    day first, then a sentence with a date; a big number one with a number; a fun fact one that says how special
    something is (not what the topic is: the first sentence) or a useless fact; a quiz any of the article's; a dare a
    dad joke, and the closing slide a piece of advice. Among the ones a slide likes as much, its pick is the random
    stream's."""
    taken: set[Candidate] = set()
    given: dict[int, Given] = {}
    facts = 0
    shuffled = list(sheet.candidates)
    rng.shuffle(shuffled)
    for number, use in slides:
        if use not in _FLAVOUR_USES and facts == MOST:
            continue
        ranked = [(rank, candidate) for candidate in shuffled if (rank := _rank(candidate, use)) is not None]
        fresh = [(rank, candidate) for rank, candidate in ranked if candidate not in taken]
        if not fresh:
            continue
        best = min(fresh, key=lambda ranked_candidate: ranked_candidate[0])[1]
        taken.add(best)
        given[number] = Given(use, best.fact(number))
        facts += use not in _FLAVOUR_USES
    return given


def _rank(candidate: Candidate, use: str) -> int | None:
    """How well a fact suits a slide's use: the lower, the better; None for one it can't use."""
    if use in _FLAVOUR_USES or candidate.flavour:
        wanted = {"dare": "joke", "questions": "advice", "fun_fact": "useless", "problem": "howto"}.get(use)
        if not candidate.flavour or candidate.flavour != wanted:
            return None
        # (a how-to that says what it fixes makes a plainer problem: D66)
        return 1 if wanted == "howto" and not _FIXING.match(candidate.text.removeprefix("How to ")) else 0
    if use in _HISTORY:
        return 0 if candidate.day else 1 if candidate.dated else 2 if not candidate.first else 3
    if use == "big_number":  # (an event's date is no figure to count)
        return 2 if candidate.day else 0 if candidate.figure else 1
    if use == "fun_fact":
        return 0 if candidate.surprising else 1 if not candidate.first and not candidate.day else 2
    return 0 if not candidate.day else 1  # (a quiz)


def used_in(fact: Fact, texts: Iterable[str | None]) -> bool:
    """Whether a slide's texts build on a fact: two of its telling words (of four letters or more, and its years, but
    not an event's day and month) are in them, or its only one ("A bean untaxed is a vassal unchecked, as the emperor
    knew in 1278", of the emperor who retired on 8 November 1278), or one of its figures, which counts for two (a big
    number of "383/km2", of Belgium's population density of 383/km2)."""
    found = _DAY.match(fact.text)
    told = fact.text[found.end() :] if found else fact.text
    words = set(_telling(told)) | set(_YEARS.findall(fact.text))
    figures = _figures(told) - words
    written = " ".join(text for text in texts if text)
    shared = len(words & (set(_telling(written)) | set(_YEARS.findall(written)))) + 2 * len(figures & _figures(written))
    return bool(words or figures) and shared >= min(2, len(words) + 2 * len(figures))


_DAY: Final = re.compile(r"\d{1,2} [A-Z][a-z]+ (?=\d{1,4}: )")  # (an event's day and month, before its year)
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
    title = title.replace("Wikipedia:Selected anniversaries/", "On this day, ")
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
