"""Offline tests: talks in other languages than English read as their speakers write (docs/v5-plan.md, D74).

Talks a language model wrote in Dutch had English words on their slides ("de geheime goaltender", "hier comes de
netwerk"), sentences in English's word order ("Over duizend soorten kaas bestaan"), look-alikes ("graf", a grave, for a
graph) and English Title Case. The requests were in English, and so were the words the slides riffed on, which wandered
off a Dutch topic read as an English word ("regen", rain, to "renovation" and "redevelopment").
"""

import concurrent.futures
import threading
import time

import pytest

from talkgenerator import facts, generator, titles
from talkgenerator.models.deck import Deck, Fact
from talkgenerator.plan import languages, outline, prompt
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import SideTrackingTopicGenerator, wandering_in
from talkgenerator.slide import powerpoint_slide_creator
from talkgenerator.sources import conceptnet, wikipedia
from talkgenerator.util import random_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, fake_schema
from tests.test_llm_talks import images as images  # (the fake pictures: a fixture)

# The English names of the topics, as Wikipedia gives them (wikipedia.english_title), and their related words
ENGLISH = {("regen", "nl"): "Rain", ("vacances", "fr"): "Vacation", ("fika", "sv"): "Fika (Sweden)"}
RELATED = {"rain": ["umbrella", "puddle", "cloud", "drizzle", "gutter"], "vacation": ["beach", "suitcase", "resort"]}


@pytest.fixture
def lookups(monkeypatch):
    """Fake Wikipedia (what a topic is in English) and ConceptNet (related things): the lookups, as they're made."""
    asked: list[tuple[str, str]] = []

    def english_title(topic, language):
        asked.append((topic, language))
        return ENGLISH.get((topic.lower(), language))

    def related_things(word, limit=50, avoid=()):
        return [(5.0 - index, thing) for index, thing in enumerate(RELATED.get(word.lower(), []))]

    monkeypatch.setattr(wikipedia, "english_title", english_title)
    monkeypatch.setattr(conceptnet, "related_things", related_things)
    return asked


def _seeds(topic, language, seed=1):
    with random_util.use(random_util.Rng(seed)), wandering_in(language):
        return SideTrackingTopicGenerator([topic], 10)


# SEED WORDS


def test_a_topic_in_another_language_wanders_from_what_it_is_in_english(lookups):
    seeds = _seeds("regen", "nl")
    wandered = [seed for seed in seeds.all_seeds() if seed != "regen"]
    assert wandered and set(wandered) <= set(RELATED["rain"])  # (not "renovation": rain's own related things)
    assert "regen" in seeds.all_seeds()  # (its slides on the topic have it as typed)
    assert [seeds.in_english(index) for index in range(10)] == [seed != "regen" for seed in seeds.all_seeds()]
    assert seeds.english_name("regen") == "Rain"
    assert lookups == [("regen", "nl")]  # (looked up once a talk)


def test_a_topic_without_an_english_name_doesnt_wander(lookups):
    seeds = _seeds("Feierabend", "de")
    assert seeds.all_seeds() == ["Feierabend"] * 10
    assert not any(seeds.in_english(index) for index in range(10))


def test_a_topic_typed_in_english_wanders_from_itself_and_all_its_words_are_english(lookups):
    RELATED["penguins"] = ["krill", "iceberg"]
    try:
        seeds = _seeds("penguins", "nl")
    finally:
        del RELATED["penguins"]
    assert set(seeds.all_seeds()) <= {"penguins", "krill", "iceberg"} and "krill" in seeds.all_seeds()
    assert all(seeds.in_english(index) for index in range(10))
    assert lookups == []  # (it reads as English: nothing to look up)


def test_an_english_talk_looks_nothing_up(lookups):
    seeds = _seeds("rain", "en")
    assert set(seeds.all_seeds()) <= {"rain", *RELATED["rain"]}
    assert not any(seeds.in_english(index) for index in range(10))
    assert lookups == []


def test_the_english_name_is_looked_up_without_the_article_first(lookups):
    assert slide_topic_generators.english_name("les vacances", "fr") == "Vacation"
    assert lookups == [("vacances", "fr")]
    assert slide_topic_generators.english_name("fika", "sv") == "Fika"  # (what it says in brackets left off)
    assert slide_topic_generators.english_name("penguins", "nl") == "penguins"
    assert slide_topic_generators.english_name("Zorblaxia", "nl") is None


def test_a_slow_lookup_leaves_the_seeds_on_the_topic(monkeypatch):
    released = threading.Event()

    def slow(topic, language):
        released.wait(5)
        return "Rain"

    monkeypatch.setattr(wikipedia, "english_title", slow)
    monkeypatch.setattr(slide_topic_generators, "ENGLISH_LOOKUP_SECONDS", 0.05)
    started = time.monotonic()
    try:
        assert slide_topic_generators.english_name("regen", "nl") is None
    finally:
        released.set()
    assert time.monotonic() - started < 2


def test_what_reads_as_english():
    assert slide_topic_generators.reads_as_english("penguins", "nl")
    assert slide_topic_generators.reads_as_english("the moon", "fr")
    assert not slide_topic_generators.reads_as_english("regen", "nl")  # (English knows it as a gamer's word)
    assert not slide_topic_generators.reads_as_english("la siesta", "es")
    assert not slide_topic_generators.reads_as_english("Zorblaxia", "nl")


def test_wikipedias_english_article_is_never_a_disambiguation_page(monkeypatch):
    # (Dutch Wikipedia's "Regen" links to "Regen (disambiguation)"; its search finds "Regen (neerslag)", rain)
    def query(language="en", **params):
        regen = {"title": "Regen", "index": 1, "langlinks": [{"lang": "en", "title": "Regen (disambiguation)"}]}
        if params.get("generator") == "search":
            rain = {"title": "Regen (neerslag)", "index": 2, "langlinks": [{"lang": "en", "title": "Rain"}]}
            return {"query": {"pages": [rain, regen]}}
        return {"query": {"pages": [regen]}}

    monkeypatch.setattr(wikipedia, "_query", query)
    assert wikipedia.english_title("regen", "nl") == "Rain"
    monkeypatch.setenv("DISABLE_WIKIPEDIA", "1")
    assert wikipedia.english_title("regen", "nl") is None


def test_an_article_doesnt_make_a_topic_a_title():
    # (French says its topics with their articles: "le Tour de France" is no title, nor four words for one)
    assert not titles.clearly_a_title("le Tour de France", "fr")
    assert titles.topics_from("la cabane à sucre", "fr") == ["la cabane à sucre"]
    assert not titles.clearly_a_title("the office coffee machine")
    assert titles.clearly_a_title("the last slice of pizza")  # (four words besides its article)
    assert titles.clearly_a_title("Why I Joined a Penguin Cult")
    assert titles.clearly_a_title("de kat van de buren is", "nl")


# THE REQUESTS


def _slides(english=True):
    return [
        prompt.PlannedSlide(2, "Fake", Recipe("two_columns"), "umbrella", english=english),
        prompt.PlannedSlide(3, "Fake", Recipe("fun_fact"), "regen"),
    ]


def test_a_request_in_another_language_asks_for_it_as_a_native_speaker_writes_it():
    request = prompt.talk_request(["regen"], _slides(), random_util.Rng(1), "nl").messages[0].content
    (native,) = [line for line in request.splitlines() if line.startswith("Write as a native Dutch speaker")]
    assert "never word for word from English" in native and "no English words left in" in native
    assert "a graph is a 'grafiek', never a 'graf'" in native  # (the language's look-alike)
    assert "capitals as in Dutch: on only its first word and names, not on every word" in native
    assert "A word to riff on: umbrella (English)" in request
    assert "A word to riff on: regen\n" in request + "\n"  # (the topic, as typed: not English)
    assert "two to five English words" in request  # (the concept is searched for pictures)
    german = prompt.talk_request(["Regen"], _slides(), random_util.Rng(1), "de").messages[0].content
    assert "on its first word, names and every noun" in german
    assert "'eventually' is 'schließlich'" in german


def test_an_english_request_is_as_it_was():
    request = prompt.talk_request(["rain"], _slides(english=False), random_util.Rng(1)).messages[0].content
    assert "native" not in request and "(English)" not in request
    assert f"its concept: {prompt.CONCEPT}." in request
    assert prompt.native_line("en") is None and prompt.concept("en") == prompt.CONCEPT


def test_every_language_has_a_look_alike_and_articles():
    for language in languages.LANGUAGES.values():
        if language != languages.ENGLISH:
            assert language.false_friend and "never" in language.false_friend, language.code
        assert language.articles, language.code


def test_a_fact_says_its_english_in_a_talk_in_another_language():
    given = facts.Given("history_quote", Fact(text="Over a thousand types of cheese exist", source="Wikipedia"))
    lines = prompt.slide_lines(_slides()[1], "nl", given)
    assert lines[0].endswith('exist" (in English: tell it in Dutch)')
    assert "never in English and never word for word" in facts.request_line("nl")
    assert "(in English" not in prompt.slide_lines(_slides(english=False)[1], "en", given)[0]
    assert facts.request_line("en").endswith("pin nothing made up on a real person.")


def test_an_outline_in_another_language_asks_for_its_riffs_in_it():
    planned = _slides()
    offers = {2: ("umbrella", "puddle"), 3: ("regen",)}
    request = outline.outline_request(["regen"], planned, offers, random_util.Rng(1), "nl")
    content = request.messages[0].content
    assert "every slide's riff in Dutch too, and its idea in English" in content
    assert "Its words (English): umbrella, puddle" in content
    assert "slide_3: " in content and "Its words: regen" in content  # (the topic, as typed: not English)
    riff = request.json_schema["properties"]["slide_2"]["properties"]["riff"]["description"]
    assert riff.startswith("the word the slide riffs on, in Dutch")
    english = outline.outline_request(["rain"], _slides(english=False), offers, random_util.Rng(1))
    assert "(English)" not in english.messages[0].content
    assert english.json_schema["properties"]["slide_2"]["properties"]["riff"]["description"] == outline._RIFF


def test_a_batch_of_an_advanced_talk_in_another_language_asks_for_it_as_a_native_speaker_writes_it():
    planned = _slides()
    request = outline.writing_request(["regen"], planned[1:], planned, {"title": "Regen"}, random_util.Rng(1), "nl")
    assert "Write as a native Dutch speaker" in request.system
    assert (
        "- slide_2: " in request.messages[0].content and "Its word: umbrella (English)" in request.messages[0].content
    )
    assert "two to five English words" in request.messages[0].content


# A WHOLE TALK


@pytest.fixture
def wandering_schema(monkeypatch):
    """The fake schema of the LLM talk tests, with seeds that wander."""
    fake = fake_schema()
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=SideTrackingTopicGenerator,
        title_generator=lambda context: "A classic title about " + context["seed"],
        slide_generators=fake.slide_generators,
        max_allowed_tags={"title": 1, "three_columns": 1},
    )
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _talk(model, topic, language) -> Deck:
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=NUM_SLIDES,
        topic=topic,
        presenter="Ann Example",
        int_seed=3,
        save_ppt=False,
        llm=model,
        language=language,
    )
    return slide_deck.to_deck()


def test_a_dutch_talk_on_a_dutch_topic(wandering_schema, lookups):
    model = FakeModel()
    deck = _talk(model, "regen", "nl")
    request = model.requests[0].messages[0].content
    riffs = [line.split("A word to riff on: ")[1] for line in request.splitlines() if "A word to riff on: " in line]
    assert riffs
    assert all(riff == "regen" or riff.removesuffix(" (English)") in RELATED["rain"] for riff in riffs)
    assert all(riff.endswith(" (English)") for riff in riffs if riff != "regen")
    assert "Write as a native Dutch speaker" in request
    notes = [slide.notes for slide in deck.slides if "Seed: " in slide.notes]
    assert any("Seed: regen" in note for note in notes)
    assert not any("renovation" in note for note in notes)


def test_an_english_talk_is_as_it_was(wandering_schema, lookups):
    model = FakeModel()
    _talk(model, "rain", "en")
    request = model.requests[0].messages[0].content
    assert "(English)" not in request and "native" not in request
    assert lookups == []


def test_the_lookup_runs_in_a_thread_of_its_own_with_a_deadline(monkeypatch):
    # (a lookup that fails is no reason for the talk to: the seeds stay on the topic)
    monkeypatch.setattr(wikipedia, "english_title", lambda topic, language: 1 / 0)
    assert slide_topic_generators.english_name("regen", "nl") is None
    with concurrent.futures.ThreadPoolExecutor(1) as pool:  # (and from a talk's own thread, too)
        assert pool.submit(slide_topic_generators.english_name, "regen", "nl").result() is None
