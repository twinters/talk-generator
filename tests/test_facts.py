"""Offline tests of real facts in talks (talkgenerator.facts, docs/v5-plan.md D60), with fakes of their sources:
Wikipedia (an article's lead, the living people's category, the day's events) and Open Trivia DB.

A talk a language model writes gives up to three of its slides that build on a fact (history, a fun fact, a quiz, a
big number) a real one each, in its one request, and its deck records them; a slide that builds on its fact credits
it. No fact about a living person, nor one of death, war, disasters, crime, politics or race, goes on a slide. Facts
that come too late stay out, and a talk made again in a check gets the same facts. Classic talks get a real fun fact
(with a twist) or a real quiz half the time, credited.
"""

import datetime
import html
import json
import re
import threading
import time
from urllib.parse import urlsplit

import pytest

from talkgenerator import facts, generator
from talkgenerator.datastructures.slide_generator_data import (
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.llm.base import Capabilities, TextProvider, TextResponse
from talkgenerator.llm.replay import ReplayProvider
from talkgenerator.models.deck import Deck, Fact
from talkgenerator.plan import prompt
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types, slides
from talkgenerator.sources import flavour, opentdb, packs, slide_texts, wikipedia
from talkgenerator.util import http_util, random_util
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)

# A FAKE WIKIPEDIA AND OPEN TRIVIA DB

# English Wikipedia's articles: their short descriptions, leads and the articles their leads link to
LEADS = {
    "Penguin": (
        "Family of aquatic flightless birds",
        "Penguins are a group of flightless semi-aquatic sea birds which live almost exclusively in the Southern "
        "Hemisphere. Only one species, the Galapagos penguin, lives at, and slightly north of, the equator. Most "
        "penguins feed on krill, fish and squid, which they swallow whole while swimming.\nOf the 18 species, the "
        "emperor penguin is the tallest and heaviest. Leopard seals and killer whales hunt penguins. Penguins can dive "
        "to 500 metres. Penguins spend about half of their lives on land and the other half in the sea. They are "
        "countershaded.",
        ("Southern Hemisphere", "Galapagos penguin", "Krill", "Emperor penguin", "Leopard seal", "Orca"),
    ),
    "Tesla, Inc.": (
        "American electric vehicle company",
        "Tesla, Inc. is an American automotive and clean energy company. The company was incorporated in July 2003 by "
        "Martin Eberhard and Marc Tarpenning. Tesla, Inc. is named after the inventor Nikola Tesla. In 2004, Musk led "
        "its first funding round.",
        ("Automotive", "Martin Eberhard", "Marc Tarpenning", "Nikola Tesla", "Elon Musk"),
    ),
    "Elon Musk": ("Businessman (born 1971)", "Elon Reeve Musk is a businessman. He leads two companies.", ()),
    "Cat": (
        "Small domesticated carnivorous mammal",
        "The cat is a small domesticated carnivorous mammal. Cats sleep for 12 to 16 hours a day.",
        (),
    ),
    "Mercury (planet)": (
        "Planet closest to the Sun",
        "Mercury is the first planet from the Sun. A year on Mercury lasts 88 days.",
        ("Sun",),
    ),
}
PEOPLE = {"Martin Eberhard", "Marc Tarpenning", "Nikola Tesla", "Wilhelm Röntgen", "Emmanuel Macron", "Edward Brooke"}
LIVING = {"Elon Musk", "Martin Eberhard", "Marc Tarpenning", "Emmanuel Macron"}
DISAMBIGUATION = {"Mercury"}
REDIRECTS = {"Penguins": "Penguin", "Musk": "Elon Musk", "Cats": "Cat"}
SEARCHES = {
    "Cats are liquid": ("TCP (antiseptic)", "Cat"),
    "a plant that won't die": ("Geranium", "Die Hard"),
    "Mercury": ("Mercury (planet)", "Freddie Mercury"),
}
# The Dutch Wikipedia's articles, by their English ones
DUTCH = {"Pinguïns": "Penguin"}
# The day's events, as Wikipedia's main page has them: a year, what happened and the articles it links to
EVENTS = (
    (1895, "Wilhelm Röntgen (pictured) discovered X-rays.", ("Wilhelm Röntgen", "X-ray")),
    (1291, "A law was passed that confined most of Venice's glassmaking industry to nearby Murano.", ("Murano",)),
    (1966, "Edward Brooke was elected to the United States Senate.", ("Edward Brooke",)),
    (2017, "The Louvre Abu Dhabi was opened by Emmanuel Macron.", ("Louvre Abu Dhabi", "Emmanuel Macron")),
    (1932, "The Australian military withdrew from its war against emus.", ("Emu War",)),
)
# Open Trivia DB's questions of a category, as it gives them (with HTML entities)
TRIVIA = {
    27: [
        ("What is the fastest land animal?", "Cheetah", ("Lion", "Pronghorn", "Greyhound")),
        ("Which bird can&#039;t fly but swims very well?", "Penguin", ("Ostrich", "Kiwi", "Emu")),
        ("What is a group of crows called?", "A murder", ("A flock", "A parliament", "A crowd")),  # (grim)
        (
            "How many hearts does an octopus have? Count them all, every single one, in this very long question.",
            "3",
            ("1", "2", "8"),
        ),  # (too long)
    ],
}
# The flavour texts' APIs: a useless fact by its number in the pool (the API answers at random; talkgenerator's cache
# keys it by the number), dad jokes by search term or page, advice slips by their number
USELESS = (
    "25% of a human's bones are in its feet.",
    "Elon Musk once ate a whole pineapple in one go.",  # (a living person)
    "A snail can sleep for three years.",
    "The beer in the fridge was always cold.",  # (drink)
)
JOKES = {
    "penguin": (
        ("p1", "What do you call a penguin in the desert? Lost."),
        ("p2", "Why don't penguins like stupid jokes? They're too cool."),  # (an insult)
    ),
    "cat": (
        ("c1", "What do you call a pile of cats? A meowntain."),
        ("c2", "Did you hear about the wandering nun? She was a roman catholic."),  # ("cat" as no whole word)
    ),
}
PAGE_JOKES = (
    ("a1", "I'm reading a book about anti-gravity. It's impossible to put down."),
    ("a2", "Why did the scarecrow win an award? He was outstanding in his field."),
)
# (every number from 1 to 224 has one, as on the real API: these three, in turn)
ADVICE_SLIPS = ("Smile at strangers.", "Remember to stretch now and then.", "Don't drink bleach.")


class _Response:
    def __init__(self, status: int, data: object = None):
        self.status_code = status
        self.ok = status < 400
        self.headers: dict[str, str] = {}
        self._data = data

    def json(self):
        return self._data


def _normalized(title: str) -> str:
    return (title[:1].upper() + title[1:]).replace("_", " ")


class FakeWeb:
    """Wikipedia's, Open Trivia DB's and the flavour texts' APIs, as far as talkgenerator asks them (every thread's
    session): down, slow, or answering from the data above; it keeps the requests it got."""

    def __init__(self, down: bool = False, slow: float = 0.0):
        self.down = down
        self.slow = slow
        self.requests: list[tuple[str, dict]] = []

    def __call__(self):  # (as http_util.get_session)
        return self

    def request(self, method, url, timeout, params=None, headers=None, **kwargs):
        parts = urlsplit(url)
        params = dict(params or {})
        self.requests.append((parts.netloc + parts.path, params))
        if self.slow:
            time.sleep(self.slow)
        if self.down:
            return _Response(503)
        if parts.netloc == "opentdb.com":
            return self._trivia(params)
        if parts.netloc == "uselessfacts.jsph.pl":
            text = USELESS[int(params["i"]) % len(USELESS)]
            return _Response(200, {"id": f"u{params['i']}", "text": text, "language": "en", "permalink": url})
        if parts.netloc == "icanhazdadjoke.com":
            assert headers == {"Accept": "application/json"}  # (else it answers in text)
            found = JOKES.get(params.get("term", ""), ()) if "term" in params else PAGE_JOKES
            return _Response(200, {"results": [{"id": key, "joke": joke} for key, joke in found], "status": 200})
        if parts.netloc == "api.adviceslip.com":
            number = int(parts.path.rsplit("/", 1)[-1])
            if not 1 <= number <= 224:
                return _Response(200, {"message": {"type": "error", "text": "Advice slip not found."}})
            return _Response(200, {"slip": {"id": number, "advice": ADVICE_SLIPS[number % len(ADVICE_SLIPS)]}})
        if "/feed/onthisday/selected/" in parts.path:
            return self._day()
        if params.get("action") == "parse":
            return self._parse(params)
        if parts.netloc.startswith("nl."):
            return self._dutch(params)
        if "generator" in params:
            return self._search(params)
        return self._query(params)

    def asked(self, host: str = "") -> list[dict]:
        return [params for where, params in self.requests if where.startswith(host)]

    @staticmethod
    def _page(title: str, params: dict) -> dict:
        page: dict = {"ns": 0, "title": title}
        if title in DISAMBIGUATION:
            return {**page, "extract": f"{title} may refer to:", "pageprops": {"disambiguation": ""}}
        if title not in LEADS and title not in PEOPLE:
            return {**page, "missing": True}
        wanted = params.get("prop", "")
        if "extracts" in wanted and title in LEADS:
            page["extract"] = LEADS[title][1]
        if "description" in wanted and title in LEADS:
            page["description"] = LEADS[title][0]
        if "categories" in wanted and title in LIVING:
            page["categories"] = [{"ns": 14, "title": wikipedia.LIVING_PEOPLE}]
        return page

    def _query(self, params: dict) -> _Response:
        normalized, redirects, pages = [], [], []
        for title in params["titles"].split("|"):
            final = _normalized(title)
            if final != title:
                normalized.append({"from": title, "to": final})
            if params.get("redirects") and final in REDIRECTS:
                redirects.append({"from": final, "to": REDIRECTS[final]})
                final = REDIRECTS[final]
            pages.append(self._page(final, params))
        return _Response(200, {"query": {"normalized": normalized, "redirects": redirects, "pages": pages}})

    def _search(self, params: dict) -> _Response:
        hits = SEARCHES.get(params["gsrsearch"], ())
        pages = [{**self._page(title, params), "index": index} for index, title in enumerate(hits, 1)]
        return _Response(200, {"query": {"pages": [page for page in pages if not page.get("missing")]}})

    @staticmethod
    def _parse(params: dict) -> _Response:
        title = REDIRECTS.get(_normalized(params["page"]), _normalized(params["page"]))
        if title not in LEADS:
            return _Response(200, {"error": {"code": "missingtitle"}})
        links = [{"ns": 0, "title": link, "exists": True} for link in LEADS[title][2]]
        return _Response(200, {"parse": {"title": title, "links": links}})

    @staticmethod
    def _dutch(params: dict) -> _Response:
        title = params.get("titles", "")
        if title not in DUTCH:
            return _Response(200, {"query": {"pages": [{"ns": 0, "title": title, "missing": True}]}})
        page = {"ns": 0, "title": title, "langlinks": [{"lang": "en", "title": DUTCH[title]}]}
        return _Response(200, {"query": {"pages": [page]}})

    @staticmethod
    def _day() -> _Response:
        selected = [
            {
                "year": year,
                "text": text,
                "pages": [{"title": page.replace(" ", "_"), "titles": {"normalized": page}} for page in pages],
            }
            for year, text, pages in EVENTS
        ]
        return _Response(200, {"selected": selected})

    @staticmethod
    def _trivia(params: dict) -> _Response:
        questions = TRIVIA.get(int(params["category"]), [])
        results = [
            {
                "type": "multiple",
                "difficulty": "easy",
                "category": "Animals",
                "question": question,
                "correct_answer": html.escape(answer, quote=False),
                "incorrect_answers": [html.escape(wrong, quote=False) for wrong in wrongs],
            }
            for question, answer, wrongs in questions
        ]
        return _Response(200, {"response_code": 0 if results else 1, "results": results})


@pytest.fixture
def web(monkeypatch):
    """Real facts on, from the fake Wikipedia, Open Trivia DB and flavour texts, with their cooldowns and turns as
    new."""
    monkeypatch.delenv("DISABLE_FACTS", raising=False)
    fake = FakeWeb()
    monkeypatch.setattr(http_util, "get_session", fake)
    monkeypatch.setattr(wikipedia, "_cooldown", http_util.Cooldown("Wikipedia"))
    monkeypatch.setattr(opentdb, "_cooldown", http_util.Cooldown("Open Trivia DB"))
    monkeypatch.setattr(opentdb, "_last_asked", float("-inf"))
    monkeypatch.setattr(opentdb, "SPACING", 0.0)  # (but in test_open_trivia_db_is_asked_five_seconds_apart)
    for cooldown in ("_useless", "_jokes", "_advice"):
        monkeypatch.setattr(flavour, cooldown, http_util.Cooldown(cooldown))
    return fake


DAY = datetime.date(2026, 11, 8)


# WIKIPEDIA


def test_an_article_is_the_one_its_topic_leads_to(web):
    article = wikipedia.article("penguins")
    assert article is not None
    assert (article.title, article.description, article.living) == (
        "Penguin",
        "Family of aquatic flightless birds",
        False,
    )
    assert article.url == "https://en.wikipedia.org/wiki/Penguin"
    assert article.extract.startswith("Penguins are a group")
    assert "Galapagos penguin" in article.links


def test_a_topic_without_an_article_of_its_own_gets_the_search_hit_titled_after_it(web):
    assert wikipedia.article("Cats are liquid").title == "Cat"  # (not "TCP (antiseptic)")
    assert wikipedia.article("Mercury").title == "Mercury (planet)"  # (not its disambiguation page)
    assert wikipedia.article("a plant that won't die") is None  # (neither "Geranium" nor "Die Hard")
    assert wikipedia.titled_after("Plant", "office plants")
    assert not wikipedia.titled_after("Community Plant Variety Office", "office plants")


def test_a_topic_in_another_language_leads_to_its_english_article(web):
    article = wikipedia.article("Pinguïns", "nl")
    assert article is not None and article.title == "Penguin"
    assert web.asked("nl.wikipedia.org")[0]["lllang"] == "en"


def test_living_people_are_the_ones_in_their_category(web):
    assert wikipedia.living(["Elon Musk", "Musk", "Wilhelm Röntgen", "Nobody at all"]) == {"Elon Musk", "Musk"}
    assert wikipedia.article("Elon Musk").living


def test_living_people_are_unknown_when_wikipedia_cant_tell(web):
    web.down = True
    assert wikipedia.living(["Elon Musk"]) is None


def test_the_days_events_come_oldest_first(web):
    events = wikipedia.on_this_day(11, 8)
    assert [event.year for event in events] == sorted(year for year, _, _ in EVENTS)
    assert events[0].pages == ("Murano",)


def test_a_wikipedia_that_is_down_gives_nothing_and_is_skipped_for_a_while(web):
    web.down = True
    assert wikipedia.article("penguins") is None
    asked = len(web.requests)
    assert wikipedia.article("penguins") is None and wikipedia.on_this_day(11, 8) == []
    assert len(web.requests) == asked  # (its cooldown: nothing more is asked)


def test_wikipedia_can_be_switched_off(web, monkeypatch):
    monkeypatch.setenv("DISABLE_WIKIPEDIA", "1")
    assert wikipedia.article("penguins") is None and wikipedia.on_this_day(11, 8) == []
    assert web.requests == []


# OPEN TRIVIA DB


def test_open_trivia_db_gives_a_categorys_questions_without_html(web):
    questions = opentdb.questions(27)
    assert questions[1].question == "Which bird can't fly but swims very well?"
    assert (questions[1].answer, len(questions[1].wrong)) == ("Penguin", 3)
    assert web.asked("opentdb.com")[0] == {"amount": 50, "category": 27, "type": "multiple"}


def test_a_topics_category_follows_its_description():
    assert opentdb.category_for("Family of aquatic flightless birds") == 27
    assert opentdb.category_for("British passenger liner that sank in 1912") == 28
    assert opentdb.category_for("Country in Northwestern Europe") == 22
    assert opentdb.category_for("Computer program for working with tabular data") == 18
    assert opentdb.category_for("Earthy smell when rain falls on dry soil") == 17
    assert opentdb.category_for("Brewed beverage") == opentdb.GENERAL_KNOWLEDGE
    # (whole words: "communication" is no cat, "training" no train)
    assert opentdb.category_for("A means of communication") == opentdb.GENERAL_KNOWLEDGE
    assert opentdb.category_for("Training for a job") == opentdb.GENERAL_KNOWLEDGE
    assert opentdb.questions(24) == []  # (politics: not a category talks use)


def test_open_trivia_db_is_asked_five_seconds_apart(web, monkeypatch):
    waits = []
    monkeypatch.setattr(opentdb, "SPACING", 5.0)
    monkeypatch.setattr(opentdb.time, "sleep", waits.append)
    opentdb.questions(27)
    opentdb.questions(9)
    assert len(waits) == 1 and 4 < waits[0] <= opentdb.SPACING


def test_a_rate_limited_open_trivia_db_gives_no_questions(web, monkeypatch):
    monkeypatch.setattr(web, "_trivia", lambda params: _Response(429, {"response_code": 5, "results": []}))
    assert opentdb.questions(27) == []
    monkeypatch.setenv("DISABLE_OPENTDB", "1")
    assert opentdb.questions(27) == []


# THE CHECKS


def test_a_lead_is_split_into_sentences_without_breaking_names_or_abbreviations():
    lead = (
        "The idea was popularized by H. G. Wells's 1895 novel The Time Machine (pictured). It sold c. 6,000 copies in "
        "the U.S. in a year.\nMachine-knit socks were first produced in the late 16th century [1]."
    )
    assert facts.sentences(lead) == [
        "The idea was popularized by H. G. Wells's 1895 novel The Time Machine.",
        "It sold c. 6,000 copies in the U.S. in a year.",
        "Machine-knit socks were first produced in the late 16th century.",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Of the 2,208 passengers aboard, approximately 1,500 died.",
        "Lord Lucan disappeared a day after allegedly murdering the nanny.",
        "Edward Brooke became the first African American to be elected to the Senate.",
        "The Australian military withdrew from its war against emus.",
        "The pope blessed the bridge.",
    ],
)
def test_facts_of_death_war_crime_politics_race_or_faith_stay_out(text):
    assert not facts.fit(text)


def test_a_sentence_that_needs_the_one_before_it_is_no_fact(web):
    texts = [candidate.text for candidate in facts.look_up("penguins", "en", DAY).candidates]
    assert "Penguins spend about half of their lives on land and the other half in the sea." in texts
    assert "They are countershaded." not in texts


def test_a_word_of_the_topic_is_no_reason_to_leave_a_fact_out():
    assert facts.fit("The Dead Sea is the lowest lake on land.", "the Dead Sea")
    assert not facts.fit("The Dead Sea is the lowest lake on land.", "salt")
    assert facts.fit("A law confined most of Venice's glassmaking industry to Murano.")


def test_a_sentence_names_the_articles_its_lead_links_to():
    assert facts.names_article("Musk led its first funding round.", "Elon Musk")  # (by the last word of a name)
    assert facts.names_article("The Galapagos penguin lives at the equator.", "Galapagos penguin")
    assert facts.names_article("It lives on Mercury.", "Mercury (planet)")
    assert not facts.names_article("A bear ate it.", "Isabel Joy Bear")  # (a name is capitalised)


def test_no_fact_names_a_living_person(web):
    sheet = facts.look_up("Tesla, Inc.", "en", DAY)
    texts = [candidate.text for candidate in sheet.candidates]
    assert "Tesla, Inc. is named after the inventor Nikola Tesla." in texts
    assert not [text for text in texts if "Eberhard" in text or "Musk" in text or "Macron" in text]
    assert (
        "8 November 1291: A law was passed that confined most of Venice's glassmaking industry to nearby Murano."
        in texts
    )
    assert "8 November 1895: Wilhelm Röntgen discovered X-rays." in texts  # (without "(pictured)")
    assert not [text for text in texts if "Senate" in text or "emus" in text]  # (politics, war)


def test_a_living_persons_article_gives_no_facts(web):
    candidates = facts.look_up("Elon Musk", "en", DAY).candidates
    assert [candidate for candidate in candidates if not candidate.day and not candidate.flavour] == []


def test_facts_that_name_someone_stay_out_when_wikipedia_cant_tell_whos_living(web, monkeypatch):
    monkeypatch.setattr(wikipedia, "living", lambda titles: None)
    candidates = facts.look_up("penguins", "en", DAY).candidates
    assert candidates and all(not candidate.names for candidate in candidates)


# WHICH SLIDES GET WHICH FACTS


def test_slides_that_build_on_facts_are_the_history_fun_fact_quiz_and_big_number_ones():
    assert [facts.use_of(kind) for kind in ("fun_fact", "quiz", "big_number", "timeline", "history_quote")] == [
        "fun_fact",
        "quiz",
        "big_number",
        "timeline",
        "history_quote",
    ]
    assert facts.use_of("two_columns", {"history", "two_images"}) == "history"
    assert facts.use_of("two_columns", {"two_images"}) is None
    assert facts.use_of("statement") is None


def test_each_slide_gets_a_fact_that_suits_it_and_no_fact_comes_twice(web):
    sheet = facts.look_up("penguins", "en", DAY)
    for seed in range(10):
        given = facts.assign(
            sheet, [(2, "timeline"), (4, "fun_fact"), (6, "big_number"), (8, "quiz")], random_util.Rng(seed)
        )
        assert list(given) == [2, 4, 6]  # (three at most)
        assert given[2].fact.text.startswith("8 November ")  # (a day's event, for history)
        assert not given[4].fact.text.startswith("8 November ") and "Penguins are a group" not in given[4].fact.text
        assert re.search(r"\d", given[6].fact.text) and not given[6].fact.text.startswith("8 November ")
        assert len({fact.fact.text for fact in given.values()}) == 3
        assert [fact.fact.slide for fact in given.values()] == [2, 4, 6]
    picks = {facts.assign(sheet, [(4, "fun_fact")], random_util.Rng(seed))[4].fact.text for seed in range(10)}
    assert len(picks) > 1  # (the random stream picks among those it likes as much)
    assert facts.assign(sheet, [(4, "fun_fact")], random_util.Rng(3)) == facts.assign(
        sheet, [(4, "fun_fact")], random_util.Rng(3)
    )


def test_a_slide_builds_on_its_fact_when_its_texts_say_what_the_fact_does():
    fact = Fact(text="Only one species, the Galapagos penguin, lives at the equator.", source="Wikipedia")
    assert facts.used_in(fact, ["The Galapagos penguin moved to the equator for the tax breaks", None])
    assert not facts.used_in(fact, ["Penguins are secretly dentists"])
    day = Fact(text="8 November 1895: Wilhelm Röntgen discovered X-rays.", source="Wikipedia")
    assert facts.used_in(day, ["1895", "Röntgen discovered X-rays, and my cat"])
    assert not facts.used_in(day, ["8 November 1895", "Nothing happened"])  # (its day and month don't count)
    retired = Fact(
        text="8 November 1278: Trần Thánh Tông, the second emperor of Vietnam, took up the title of retired emperor.",
        source="Wikipedia",
    )
    assert facts.used_in(retired, ["The Bean Tax of 1278", "A bean untaxed is a vassal unchecked, as the emperor knew"])
    density = Fact(
        text="Belgium covers an area of 30,689 km2 and has a population density of 383/km2.", source="Wikipedia"
    )
    assert facts.used_in(density, ["The magic number of closeness", "383/km2", "people sharing one small country"])
    assert not facts.used_in(density, ["The magic number", "1,000", "people"])


def test_a_facts_credit_names_its_article_and_its_license():
    fact = facts.Candidate("A fact.", "https://en.wikipedia.org/wiki/Tesla,_Inc.").fact()
    assert "".join(text for text, _ in facts.credit(fact)) == "Wikipedia: Tesla, Inc. (CC BY-SA 4.0)"
    assert facts.credit(fact)[0][1] == "https://en.wikipedia.org/wiki/Tesla,_Inc."
    day = facts.Candidate("A fact.", wikipedia.anniversaries_url(11, 8), day=True).fact()
    assert "".join(text for text, _ in facts.credit(day)) == "Wikipedia: On this day, November 8 (CC BY-SA 4.0)"


# TALKS A LANGUAGE MODEL WRITES

TOPIC = "penguins"


def _drawn(kind, content, slide_class, weight, **recipe):
    return SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(content, slide_class),
        weight_function=weight,
        allowed_repeated_elements=10,
        tags=[kind],
        name=f"Fake {kind}",
        llm=Recipe(kind, **recipe),
    )


def fact_schema(with_facts: bool = True) -> PresentationSchema:
    """A talk of a title slide, a fun fact, a timeline, a quiz and a closing slide (or, without facts, a closing slide
    four times)."""
    title = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Fake title",
        llm=Recipe("title"),
    )
    closing = _drawn("questions", lambda c: ("Questions?", None), slides.QuestionsSlide, ConstantWeightFunction(1))
    builders = [
        _drawn(
            "fun_fact",
            lambda c: ("Did you know?", "A classic fact", None, None),
            slides.FunFactSlide,
            ConstantWeightFunction(1),
            images=(lambda c: None,),
            omit=frozenset({"photo"}),
        ),
        _drawn(
            "timeline",
            lambda c: ("A classic timeline", "1900", "One", "1950", "Two", "2000", "Three"),
            slides.TimelineSlide,
            ConstantWeightFunction(1),
        ),
        _drawn(
            "quiz",
            lambda c: ("A classic question?", "One", "Two", "Three", None, "A", None),
            slides.QuizSlide,
            ConstantWeightFunction(1),
        ),
    ]
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "A classic title",
        slide_generators=[title, closing, *(builders if with_facts else [])],
        max_allowed_tags={"title": 1, "questions": 1, "fun_fact": 1, "timeline": 1, "quiz": 1},
    )


def _given_fact(request, key: str) -> str | None:
    """The real fact the request gives a slide, by its key."""
    for line in request.messages[0].content.splitlines():
        if line.startswith(f"{key}:"):
            found = re.search(r': "(.+)"$', line)
            return found.group(1) if found else None
    return None


class FakeModel(TextProvider):
    """Writes every field of a talk's answer (a choice's first option), and a slide's fact field with the real fact
    the request gives it, if any."""

    id = "fake:model"
    capabilities = Capabilities(structured_output=True, streaming=True)

    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        answer = {}
        for key, value in request.json_schema["properties"].items():
            fields = {}
            for name, field in value["properties"].items():
                if field["type"] == "boolean":
                    fields[name] = False
                elif field.get("enum"):
                    fields[name] = field["enum"][0]
                elif name in ("fact", "dare", "subtitle") and _given_fact(request, key):
                    fields[name] = _given_fact(request, key)  # (a fun fact's, a dad joke, a piece of advice)
                elif name.startswith("date_"):
                    fields[name] = str(1900 + 10 * int(name[-1]))
                else:
                    fields[name] = f"The {name.replace('_', ' ')}"
            answer[key] = fields
        return TextResponse(text=json.dumps(answer), model=self.id, input_tokens=100, output_tokens=100)

    def stream(self, request, on_text):
        response = self.complete(request)
        on_text(response.text)
        return response


@pytest.fixture
def schema(monkeypatch):
    made = fact_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    return made


def _talk(model, int_seed=1, parallel=True, slides=5, topic=TOPIC, language="en"):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=slides,
        topic=topic,
        presenter="Ann Example",
        int_seed=int_seed,
        parallel=parallel,
        save_ppt=False,
        llm=model,
        language=language,
    )
    return slide_deck.to_deck()


def test_a_talk_s_request_gives_its_slides_real_facts_and_its_deck_records_them(web, schema):
    model = FakeModel()
    deck = _talk(model)
    request = model.requests[0].messages[0].content
    assert facts.request_line() in request
    kinds = {slide.type: number for number, slide in enumerate(deck.slides, 1)}
    uses = {kinds[kind]: kind for kind in ("fun_fact", "timeline", "quiz", "questions")}
    assert [fact.slide for fact in deck.facts] == sorted(uses)  # (the closing slide's: a piece of advice)
    assert all(fact.use == "prompt" for fact in deck.facts)
    by_slide = {fact.slide: fact for fact in deck.facts}
    assert by_slide[kinds["questions"]].source == "Advice Slip"
    assert {by_slide[kinds[kind]].source for kind in ("timeline", "quiz")} == {"Wikipedia"}
    assert by_slide[kinds["fun_fact"]].source in ("Wikipedia", "Useless Facts")  # (as the seed's shuffle picks)
    for fact in deck.facts:
        assert fact.text.split(": ", 1)[-1] in request  # (a timeline's event with its year alone)
    timeline = by_slide[kinds["timeline"]]
    assert timeline.text.startswith(f"{datetime.date.today().day} ")  # (an event of the day the talk is made on)
    # (small: a line, and three facts and a piece of advice on their slides' lines)
    added = len(facts.request_line()) + sum(
        len(facts.Given(uses[fact.slide], fact).line()) for fact in deck.facts if fact.slide is not None
    )
    assert added < 1200


def test_a_slide_that_builds_on_its_fact_credits_it(web, schema):
    deck = _talk(FakeModel())
    fun_fact = next(slide for slide in deck.slides if slide.type == "fun_fact")
    credited = {"".join(part.text for part in credit) for credit in fun_fact.credits}
    assert credited & {"Wikipedia: Penguin (CC BY-SA 4.0)", "Useless Facts"}, credited
    assert "Real fact (built on)" in fun_fact.notes
    quiz = next(slide for slide in deck.slides if slide.type == "quiz")  # (it wrote "The question": not built on)
    assert quiz.credits == () and "Real fact (left out)" in quiz.notes


def test_the_same_seed_and_answers_give_the_same_talk_with_facts(web, schema, tmp_path):
    talk = _talk(FakeModel(), int_seed=3).to_json()
    assert _talk(FakeModel(), int_seed=3, parallel=False).to_json() == talk
    cassette = tmp_path / "talk.json"
    recorded = _talk(ReplayProvider(cassette, record=FakeModel()), int_seed=4)
    assert _talk(ReplayProvider(cassette), int_seed=4).to_json() == recorded.to_json()


def test_a_talk_asks_only_for_what_its_slides_use(web, monkeypatch):
    plain = fact_schema(with_facts=False)  # (a title slide and a closing slide)
    monkeypatch.setattr(generator, "get_schema", lambda name: plain)
    deck = _talk(FakeModel(), slides=2)
    assert [fact.source for fact in deck.facts] == ["Advice Slip"]
    # (no article, no day's events: Wikipedia only tells whether the advice's capitalised words are living people)
    wikipedia_asked = [params for where, params in web.requests if "wikipedia" in where]
    assert wikipedia_asked and all(params.get("prop") == "categories" for params in wikipedia_asked)


def test_a_talk_without_slides_for_facts_asks_nothing_and_its_deck_is_as_before(web, monkeypatch):
    plain = fact_schema(with_facts=False)
    monkeypatch.setattr(generator, "get_schema", lambda name: plain)
    monkeypatch.setenv("DISABLE_ADVICE_SLIPS", "1")  # (its closing slide's only use)
    model = FakeModel()
    deck = _talk(model, slides=2)
    assert deck.facts is None and web.requests == []
    assert facts.request_line() not in model.requests[0].messages[0].content
    assert '"facts"' not in deck.to_json()  # (the deck as before talks had facts)


def test_a_talk_whose_facts_come_too_late_goes_without_them_and_the_next_one_asks_again(web, schema, monkeypatch):
    monkeypatch.setattr(facts, "DEADLINE", 0.2)
    web.slow = 0.5
    model = FakeModel()
    deck = _talk(model)
    assert deck.facts is None and facts.request_line() not in model.requests[0].messages[0].content
    # (a late talk may be a busy computer's: Wikipedia isn't kept out for it, and the next talk gets its facts)
    assert not wikipedia._cooldown.active
    web.slow = 0.0
    assert _talk(FakeModel()).facts is not None


def test_a_talk_made_again_in_a_check_gets_the_facts_the_first_one_got(web, schema, monkeypatch):
    monkeypatch.setattr(facts, "DEADLINE", 0.2)
    with http_util.same_answers():
        web.slow = 0.5
        first = _talk(FakeModel())
        web.slow = 0.0
        monkeypatch.setattr(wikipedia, "_cooldown", http_util.Cooldown("Wikipedia"))
        again = _talk(FakeModel(), parallel=False)
    assert first.facts is None and again.to_json() == first.to_json()
    assert _talk(FakeModel()).facts is not None  # (outside the check, they come in time now)


def test_a_wikipedia_that_is_down_makes_a_talk_without_facts(web, schema):
    web.down = True
    deck = _talk(FakeModel())
    assert deck.facts is None and len(deck.slides) == 5


def test_a_talk_on_a_living_person_gets_no_facts_about_them(web, schema):
    deck = _talk(FakeModel(), topic="Elon Musk")
    of_wikipedia = [fact for fact in deck.facts or () if fact.source == "Wikipedia"]
    assert all(fact.text.startswith(f"{datetime.date.today().day} ") for fact in of_wikipedia)  # (the day's alone)
    assert not [fact for fact in deck.facts or () if "Musk" in fact.text]


def test_a_talk_in_another_language_gets_english_facts_and_says_so(web, schema):
    model = FakeModel()
    deck = _talk(model, topic="Pinguïns", language="nl")
    assert deck.facts and any("penguin" in fact.text.lower() for fact in deck.facts)
    assert "The facts are in English" in model.requests[0].messages[0].content


def test_facts_can_be_switched_off(web, schema, monkeypatch):
    monkeypatch.setenv("DISABLE_FACTS", "1")
    model = FakeModel()
    assert _talk(model).facts is None and web.requests == []
    assert facts.request_line() not in model.requests[0].messages[0].content


def test_the_request_is_as_before_without_facts():
    slide = prompt.PlannedSlide(2, "Fake fun_fact", Recipe("fun_fact", (lambda c: None,)), "krill")
    plain = prompt.talk_request([TOPIC], [slide], random_util.Rng(1))
    fact = Fact(text='Penguins eat "krill".', source="Wikipedia")
    given = facts.Given("fun_fact", fact)
    with_fact = prompt.talk_request([TOPIC], [slide], random_util.Rng(1), facts={2: given})
    assert given.line().endswith(": \"Penguins eat 'krill'.\"")  # (its own quote marks single)
    content = with_fact.messages[0].content
    assert plain.messages[0].content == content.replace(f"\n{facts.request_line()}", "").replace(
        f". {given.line()}", ""
    )
    assert plain.json_schema == with_fact.json_schema


def test_keep_gives_what_the_first_got_in_a_block_of_same_answers():
    values = iter(range(10))
    with http_util.same_answers():
        assert http_util.keep("key", lambda: next(values)) == 0
        assert http_util.keep("key", lambda: next(values)) == 0
        assert http_util.keep("other", lambda: next(values)) == 1
    assert http_util.keep("key", lambda: next(values)) == 2


def test_keep_makes_the_others_wait_for_the_first(web):
    started, results = threading.Event(), []

    def slowly():
        started.set()
        time.sleep(0.2)
        return "first"

    with http_util.same_answers():
        thread = threading.Thread(target=lambda: results.append(http_util.keep("key", slowly)))
        thread.start()
        started.wait()
        results.append(http_util.keep("key", lambda: "second"))
        thread.join()
    assert results == ["first", "first"]


def test_a_deck_s_facts_survive_its_json():
    deck = Deck(generator="test", facts=(Fact(text="A fact.", source="Wikipedia", slide=2),))
    assert Deck.from_json(deck.to_json()) == deck
    assert '"facts"' not in Deck(generator="test").to_json()


# CLASSIC SLIDES


def _photo(context):
    return None


def test_half_of_the_classic_fun_facts_are_real_ones_with_a_twist(web, related):
    twists = packs.pack(packs.TED).rule("karaoke.fun_fact_twist")
    real, made_up = 0, 0
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            kicker, fact, source, _ = slide_texts.fun_fact(_photo)({"seed": "cat", "topic": "cats"})
        if isinstance(fact, facts.CreditedText):
            real += 1
            assert source == fact.fact.source in ("Wikipedia", "Useless Facts") and fact.fact.use == "slide"
            assert fact.startswith(fact.fact.text) and fact[len(fact.fact.text) + 1 :] in twists
            assert len(fact) <= 150 and "The cat is" not in fact  # (not what a cat is)
        else:
            made_up += 1
    assert real > 3 and made_up > 3


def test_a_classic_slide_credits_the_real_fact_it_shows_and_the_deck_records_it(web, related):
    from talkgenerator.slide.slide_deck import SlideDeck

    generator_data = SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(slide_texts.fun_fact(_photo), slides.FunFactSlide),
        retries=1,
        name="Fun Fact",
    )
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            slide, _ = generator_data.generate({"seed": "cat", "topic": "cats"}, set())
        if slide.facts:
            break
    deck = SlideDeck(2)
    deck.add_slide(1, slide)
    made = deck.to_deck()
    assert [(fact.slide, fact.use, fact.url) for fact in made.facts] == [
        (2, "slide", "https://en.wikipedia.org/wiki/Cat")
    ]
    assert ["".join(part.text for part in credit) for credit in made.slides[0].credits] == [
        "Wikipedia: Cat (CC BY-SA 4.0)"
    ]


def test_half_of_the_classic_quizzes_are_real_ones_of_the_topics_kind(web, related):
    real = 0
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            quiz = slide_texts.generate_quiz({"seed": "cat", "topic": "penguins"})
        question = quiz[0]
        if isinstance(question, facts.CreditedText):
            real += 1
            options, letter = quiz[1:5], quiz[5]
            found = next(entry for entry in TRIVIA[27] if html.unescape(entry[0]) == question)
            assert options["ABCD".index(letter)] == found[1] and sorted(options) == sorted([found[1], *found[2]])
            assert question.fact.source == "Open Trivia DB" and quiz[6] is None
            assert "murder" not in question and "octopus" not in question  # (grim; too long)
    assert 3 < real < 18


def test_classic_facts_can_be_switched_off(web, related, monkeypatch):
    monkeypatch.setenv("DISABLE_FACTS", "1")
    for seed in range(10):
        with random_util.use(random_util.Rng(seed)):
            assert not isinstance(
                slide_texts.generate_quiz({"seed": "cat", "topic": "penguins"})[0], facts.CreditedText
            )
            assert not isinstance(slide_texts.fun_fact(_photo)({"seed": "cat"})[1], facts.CreditedText)
    assert web.requests == []


def test_a_credit_line_that_credits_a_fact_starts_with_sources(web, related):
    from talkgenerator.design import engine, themes
    from talkgenerator.render.powerpoint import render_pptx
    from talkgenerator.slide.slide_deck import SlideDeck

    generator_data = SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(slide_texts.fun_fact(_photo), slides.FunFactSlide),
        retries=1,
        name="Fun Fact",
    )
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            slide, _ = generator_data.generate({"seed": "cat", "topic": "cats"}, set())
        if slide.facts:
            break
    for theme in (None, themes.pick("clean keynote", random_util.Rng(1))):
        deck = SlideDeck(1)
        deck.add_slide(0, slide)
        deck.theme = theme
        made = deck.to_deck()
        assert made.slides[0].credits_a_text() and engine.credits_prefix(made.slides[0]) == "Sources: "
        texts = [shape.text_frame.text for shape in render_pptx(made).slides[0].shapes if shape.has_text_frame]
        line = "Sources: Wikipedia: Cat (CC BY-SA 4.0)"
        assert any(text in (line, f"[{line}]") for text in texts), texts
    # (a slide that credits its pictures alone reads as it has since 2019)
    pictured = made.slides[0].model_copy(update={"text_credits": None})
    assert not pictured.credits_a_text() and engine.credits_prefix(pictured) == "Image sources: "


def test_a_timeline_gets_an_event_of_the_day_with_its_year_alone():
    fact = Fact(text="8 November 1291: A law confined Venice's glassmaking to Murano.", source="Wikipedia")
    assert facts.Given("timeline", fact).line().endswith(': "1291: A law confined Venice\'s glassmaking to Murano."')
    assert (
        facts.Given("history_quote", fact)
        .line()
        .endswith(': "8 November 1291: A law confined Venice\'s glassmaking to Murano."')
    )


# FLAVOUR TEXTS: USELESS FACTS, DAD JOKES AND ADVICE SLIPS


def test_a_useless_fact_comes_by_its_number_in_the_weeks_pool(web):
    found = flavour.useless_fact(14)
    assert web.asked("uselessfacts.jsph.pl")[0] == {"language": "en", "i": 2}  # (14 of a pool of 12)
    assert (found.text, found.source) == (USELESS[2], "Useless Facts")


def test_dad_jokes_are_about_a_whole_word_or_from_a_page(web):
    assert [joke.text for joke in flavour.dad_jokes("cat")] == [JOKES["cat"][0][1]]  # (not the roman catholic)
    assert flavour.dad_jokes("cat")[0].url == "https://icanhazdadjoke.com/j/c1"
    assert [joke.text for joke in flavour.dad_jokes(page=3)] == [joke for _, joke in PAGE_JOKES]
    assert web.asked("icanhazdadjoke.com")[-1] == {"limit": 30, "page": 3}


def test_an_advice_slip_comes_by_its_number(web):
    assert flavour.advice(1).text == ADVICE_SLIPS[1]
    assert flavour.advice(225).text == flavour.advice(1).text  # (the numbers go round the 224 slips)
    assert flavour.advice(1).url == "https://api.adviceslip.com/advice/1"


def test_the_flavour_sources_can_be_switched_off(web, monkeypatch):
    for name in ("USELESS_FACTS", "DAD_JOKES", "ADVICE_SLIPS"):
        monkeypatch.setenv(f"DISABLE_{name}", "1")
    assert flavour.useless_fact(0) is None and flavour.dad_jokes("cat") == [] and flavour.advice(1) is None
    assert web.requests == []


@pytest.mark.parametrize(
    "text",
    [
        "Why don't penguins like stupid jokes? They're too cool.",
        "The beer in the fridge was always cold.",
        "Did you hear about the wandering nun? She was a roman catholic.",
        "Don't drink bleach.",
        "A cat killed the mood.",
    ],
)
def test_flavour_texts_of_insults_drink_faiths_or_death_stay_out(text):
    assert not facts.fit_flavour(text)


def test_a_flavour_text_that_names_a_living_person_stays_out(web):
    candidates = [facts.flavour_candidate(flavour.Flavour(text, "Useless Facts", "u"), "useless") for text in USELESS]
    kept = facts.without_living([candidate for candidate in candidates if candidate is not None])
    assert [candidate.text for candidate in kept] == [USELESS[0], USELESS[2]]  # (not Elon Musk's, nor the beer)


def test_a_dare_gets_a_dad_joke_and_the_closing_slide_a_piece_of_advice(web):
    sheet = facts.look_up("penguins", "en", DAY)
    slides = [(2, "timeline"), (3, "fun_fact"), (4, "quiz"), (5, "big_number"), (6, "dare"), (9, "questions")]
    given = facts.assign(sheet, slides, random_util.Rng(1))
    assert list(given) == [2, 3, 4, 6, 9]  # (three facts at most, and a joke and a piece of advice besides)
    assert (given[6].fact.source, given[6].fact.text) == ("icanhazdadjoke", JOKES["penguin"][0][1])
    assert given[9].fact.source == "Advice Slip" and "bleach" not in given[9].fact.text
    assert given[6].line().startswith("Dare the presenter to tell this real dad joke")
    assert given[9].fact.license is None  # (their sites state none)


def test_a_fun_fact_builds_on_the_topics_facts_or_a_useless_fact(web):
    sheet = facts.look_up("penguins", "en", DAY)
    picks = {facts.assign(sheet, [(3, "fun_fact")], random_util.Rng(seed))[3].fact.source for seed in range(20)}
    assert picks == {"Wikipedia", "Useless Facts"}


def test_each_kind_of_text_goes_to_its_own_slides(web):
    lead = facts.Sheet((facts.Candidate("Penguins are birds that swim very well.", "u"),))
    assert facts.assign(lead, [(2, "dare"), (3, "questions")], random_util.Rng(1)) == {}
    joke = facts.Sheet((facts.Candidate("A joke.", "u", flavour="joke", source="icanhazdadjoke"),))
    uses = [(2, "quiz"), (3, "timeline"), (4, "fun_fact"), (5, "questions")]
    assert facts.assign(joke, uses, random_util.Rng(1)) == {}


def test_a_talk_draws_its_flavour_texts_by_its_seed():
    assert facts.Draws.of(random_util.Rng(3)) == facts.Draws.of(random_util.Rng(3))
    assert facts.Draws.of(random_util.Rng(3)) != facts.Draws.of(random_util.Rng(4))
    draws = facts.Draws.of(random_util.Rng(3))
    assert all(0 <= number < flavour.POOL for number in draws.useless) and 1 <= draws.joke_page <= flavour.JOKE_PAGES


def dare_schema() -> PresentationSchema:
    """A talk of a title slide, a dare and a closing slide."""
    title = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Fake title",
        llm=Recipe("title"),
    )
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "A classic title",
        slide_generators=[
            title,
            _drawn("dare", lambda c: ("Challenge", "A classic dare"), slides.DareSlide, PeakedWeight((1,), 1000, 0)),
            _drawn("questions", lambda c: ("Questions?", None), slides.QuestionsSlide, PeakedWeight((-1,), 1000, 0)),
        ],
        max_allowed_tags={"title": 1, "dare": 1, "questions": 1},
    )


def test_a_talk_s_dare_dares_its_presenter_to_tell_a_real_dad_joke(web, monkeypatch):
    made = dare_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    model = FakeModel()
    deck = _talk(model, slides=3)
    assert [slide.type for slide in deck.slides] == ["title", "dare", "questions"]
    request = model.requests[0].messages[0].content
    joke = JOKES["penguin"][0][1]
    assert f'tell this real dad joke, word for word, and say how (a voice, a pause, a pose): "{joke}"' in request
    assert [(fact.slide, fact.source) for fact in deck.facts] == [(2, "icanhazdadjoke"), (3, "Advice Slip")]
    dare, closing = deck.slides[1], deck.slides[2]
    assert ["".join(part.text for part in credit) for credit in dare.credits] == ["icanhazdadjoke"]
    assert dare.text_credits and closing.text_credits  # (their credit lines say "Sources:")


def test_half_of_the_classic_dares_dare_the_presenter_to_tell_a_real_dad_joke(web, related):
    framings = packs.pack(packs.TED).rule("karaoke.joke_dare")
    jokes = 0
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            _, dare = slide_texts.generate_dare({"seed": "cat", "topic": "cats"})
        if isinstance(dare, facts.CreditedText):
            jokes += 1
            assert (dare.fact.source, dare.fact.text) == ("icanhazdadjoke", JOKES["cat"][0][1])
            assert dare in [framing.replace("{joke}", dare.fact.text) for framing in framings] and len(dare) <= 130
    assert 3 < jokes < 17


def test_some_classic_closing_slides_end_on_a_real_piece_of_advice(web, related):
    framings = packs.pack(packs.TED).rule("structure.advice_line")
    advised = 0
    for seed in range(30):
        with random_util.use(random_util.Rng(seed)):
            _, line = slide_texts.generate_questions({"seed": "cat", "topic": "cats"})
        if isinstance(line, facts.CreditedText):
            advised += 1
            assert line.fact.source == "Advice Slip" and "bleach" not in line
            assert line in [framing.replace("{advice}", line.fact.text) for framing in framings] and len(line) <= 80
    assert 3 < advised < 25


def test_classic_flavour_texts_switched_off_leave_the_slides_as_they_were(web, related, monkeypatch):
    def made(*switched_off: str) -> list[tuple]:
        for name in ("FACTS", "DAD_JOKES", "ADVICE_SLIPS"):
            monkeypatch.delenv(f"DISABLE_{name}", raising=False)
        for name in switched_off:
            monkeypatch.setenv(f"DISABLE_{name}", "1")
        texts = []
        for seed in range(10):
            with random_util.use(random_util.Rng(seed)):
                texts.append(
                    (slide_texts.generate_dare({"seed": "cat"}), slide_texts.generate_questions({"seed": "cat"}))
                )
        return texts

    assert made("DAD_JOKES", "ADVICE_SLIPS") == made("FACTS")  # (no draw of theirs either)
