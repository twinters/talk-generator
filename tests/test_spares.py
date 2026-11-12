"""Offline tests of spare slides (talkgenerator.generator.stream_talk's spares, docs/v5-plan.md D66): slides a streamed
talk sends early, to show while its next slide isn't in yet. They come as slide.spare events, laid out in the talk's
theme without a slide number, about its topic; they stay out of its deck; and as they're made from random streams of
their own, the talk's slides come out the same with spares or without.

The talks are the fake ones of test_llm_talks (a fake schema with recipes, a fake model and fake images), with fake
spare generators; the real spare generators are tried on their own, with a fake ConceptNet.
"""

import threading

import pytest
from pydantic import TypeAdapter

from talkgenerator import generator
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
from talkgenerator.design import engine, themes
from talkgenerator.models.deck import DECORATION, ImageElement, TextElement
from talkgenerator.models.events import SlideReady, SlideSpare, TalkEvent, TalkFinished, TalkStarted
from talkgenerator.schema.presentation_schema import SPARE_TRIES, PresentationSchema, _DeckState
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.schema.slide_schemas import SPARE_GENERATORS
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import conceptnet
from talkgenerator.util import http_util, random_util
from tests.test_livelier_slides import _numbers
from tests.test_llm_talks import NUM_SLIDES, _classic_chart, fake_schema
from tests.test_slide_types import _theme
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)
from tests.test_streaming import SlowModel
from tests.test_streaming import images as images  # every image at example.com exists (a fixture)

TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3}
SPARES = 2


def _spare_generator(name, made=None):
    """A fake spare generator: a chart titled after it and the slide's seed (or what `made` makes of the context)."""

    def chart(context):
        if made is not None:
            return made(context)
        return (f"{name} about {context['seed']}", *_classic_chart(context)[1:])

    return SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(chart),
        weight_function=ConstantWeightFunction(1),
        allowed_repeated_elements=10,
        tags=[name.lower()],
        name=name,
    )


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    schema = fake_schema()
    schema.spare_generators = tuple((_spare_generator(name), 1.0) for name in ("Spare A", "Spare B", "Spare C"))
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _texts(slide, decoration=False):
    return [
        element.text
        for element in slide.elements
        if isinstance(element, TextElement) and (element.role == DECORATION) == decoration
    ]


def _while_the_model_writes(model, spares=SPARES, **options):
    """A streamed talk's events, of which the spares come while the model still writes (it waits for them)."""
    stream = generator.stream_talk("fake", NUM_SLIDES, llm=model, spares=spares, **{**TALK, **options})
    events = []
    while sum(isinstance(event, SlideSpare) for event in events) < spares:
        events.append(next(stream))
    assert not model.done.is_set()  # (they came while the model was still writing)
    model.go_on.set()
    return events + list(stream)


# SPARES IN A STREAMED TALK


def test_spares_come_while_the_talk_is_made_and_stay_out_of_its_deck():
    events = _while_the_model_writes(SlowModel(), theme="clean keynote")

    started, *between, finished = events
    assert isinstance(started, TalkStarted) and isinstance(finished, TalkFinished)
    spares = [event for event in between if isinstance(event, SlideSpare)]
    ready = [event for event in between if isinstance(event, SlideReady)]
    assert len(spares) + len(ready) == len(between)
    assert [event.index for event in spares] == list(range(SPARES))  # (numbered in the order they come)
    assert [event.index for event in ready] == list(range(NUM_SLIDES + 1))  # (and the closer after them)
    # About the talk's topic, each of another spare generator, laid out in the talk's theme
    titles = [_texts(event.slide)[0] for event in spares]
    assert all(title.endswith("about cats") for title in titles) and len(set(titles)) == SPARES
    assert all(event.slide.layout.startswith("v5/") for event in spares)
    # The deck is the talk's alone: its slides are the ones handed over, without the spares, and the same as a talk
    # made without spares (from the same seed)
    deck = finished.deck
    assert list(deck.slides) == [event.slide for event in ready]
    assert not any(title in text for slide in deck.slides for text in _texts(slide) for title in titles)
    model = SlowModel()
    model.go_on.set()
    without = list(generator.stream_talk("fake", NUM_SLIDES, llm=model, theme="clean keynote", **TALK))
    assert not any(isinstance(event, SlideSpare) for event in without)
    assert deck.to_json() == without[-1].deck.to_json()


def test_a_spare_has_no_slide_number_where_the_talks_slides_have_theirs():
    events = _while_the_model_writes(SlowModel(), theme="clean keynote")

    for event in events:
        if isinstance(event, SlideSpare):
            assert _numbers(event.slide) == []
        elif isinstance(event, SlideReady) and event.slide.closer:  # (none either: none of the slides, D76)
            assert _numbers(event.slide) == []
        elif isinstance(event, SlideReady) and event.index > 0:  # (a title slide's big title can leave no room)
            assert _numbers(event.slide) == [(event.index + 1, NUM_SLIDES)]


def test_spare_events_are_json_that_reads_back():
    events = _while_the_model_writes(SlowModel(), theme="neon")
    spares = [event for event in events if isinstance(event, SlideSpare)]
    assert spares and all(event.event == "slide.spare" for event in spares)
    adapter = TypeAdapter(TalkEvent)
    assert [adapter.validate_json(event.to_json()) for event in spares] == spares


def test_a_talk_wants_no_spares_unless_it_asks_for_them():
    model = SlowModel()
    model.go_on.set()
    events = list(generator.stream_talk("fake", NUM_SLIDES, llm=model, **TALK))
    # (a slide.ready for every slide, and one more for the closer after them: D76)
    assert [event.event for event in events] == ["talk.started", *["slide.ready"] * (NUM_SLIDES + 1), "talk.finished"]


# MAKING THEM (the spares of a talk's schema, with a Progress that notes what it's told)


class Noting:
    """A talk's progress that wants spares, and notes them."""

    def __init__(self, spares=SPARES):
        self.spares = spares
        self.cancelled = threading.Event()
        self.got = []

    def spare(self, slide_deck, number, slide):
        self.got.append((number, slide))


def _spares(schema, progress, language="en", topic="cats", seed=3, stop=True):
    """The spares the schema makes for a talk on the topic (and its progress), once they're all made."""
    slide_deck = SlideDeck(
        NUM_SLIDES, title="About cats", topics=[topic], presenter="Ann Example", seed=seed, language=language
    )
    context = {
        "topic": topic,
        "topics": [topic],
        "presenter": "Ann Example",
        "title": "About cats",
        "language": language,
    }
    making = schema._spares(progress, slide_deck, context, random_util.Rng(seed), None)
    if making is not None and stop:
        making._thread.join(timeout=10)
        assert not making._thread.is_alive()
    return making


def test_every_spare_is_of_another_kind_and_the_same_seed_makes_the_same_ones(schema):
    first, again = Noting(spares=3), Noting(spares=3)
    _spares(schema, first)
    _spares(schema, again)

    titles = [_texts(slide.to_deck_slide())[0] for _, slide in first.got]
    assert [number for number, _ in first.got] == [0, 1, 2]
    assert sorted(title.split(" about ")[0] for title in titles) == ["Spare A", "Spare B", "Spare C"]
    assert titles == [_texts(slide.to_deck_slide())[0] for _, slide in again.got]
    # (and as many as there are spare generators, at most)
    more = Noting(spares=5)
    _spares(schema, more)
    assert len(more.got) == 3


def test_a_spare_that_fails_tries_another_spare_generator(schema, caplog):
    broken = _spare_generator("Broken", lambda context: None)
    schema.spare_generators = ((broken, 100.0), (_spare_generator("Spare A"), 1.0))
    progress = Noting(spares=2)
    with caplog.at_level("INFO", logger="talkgenerator"):
        _spares(schema, progress)

    # The broken one first (by its weight), for the first spare only; then another one; and none left for the second
    picked = [record.getMessage() for record in caplog.records if record.getMessage().startswith("* Generating")]
    assert picked == [
        "* Generating spare 1 about cats using Broken *",
        "* Generating spare 1 about cats using Spare A *",
    ]
    assert [_texts(slide.to_deck_slide())[0] for _, slide in progress.got] == ["Spare A about cats"]


def test_spares_that_all_fail_are_left_out_and_the_talk_goes_on(schema):
    def crashing(context):
        raise RuntimeError("a source that broke")

    schema.spare_generators = tuple((_spare_generator(f"Broken {n}", crashing), 1.0) for n in range(SPARE_TRIES + 1))
    progress = Noting(spares=2)
    _spares(schema, progress)
    assert progress.got == []


def test_a_spare_made_once_the_slides_are_in_isnt_handed_over(schema):
    waiting, release = threading.Event(), threading.Event()

    def slow(context):
        waiting.set()
        release.wait(timeout=10)
        return (f"Slow about {context['seed']}", *_classic_chart(context)[1:])

    schema.spare_generators = ((_spare_generator("Slow", slow), 1.0),)
    progress = Noting(spares=1)
    making = _spares(schema, progress, stop=False)
    assert waiting.wait(timeout=10)
    making.stop()  # (the talk's slides are all in)
    release.set()
    making._thread.join(timeout=10)
    assert progress.got == []


def test_spares_stop_once_nobody_wants_the_talk(schema):
    progress = Noting(spares=3)
    progress.cancelled.set()
    _spares(schema, progress)
    assert progress.got == []


def test_a_talk_without_spare_generators_makes_none_in_english(schema):
    schema.spare_generators = ()
    progress = Noting()
    assert _spares(schema, progress) is None
    assert progress.got == []


def test_spares_of_a_talk_in_another_language_are_pictures_of_its_topic_without_text(schema):
    # (in English, the spare generators' slides would be English)
    progress = Noting(spares=2)
    _spares(schema, progress, language="nl", topic="katten")

    assert progress.got and progress.got[0][0] == 0
    shown = []
    for _, slide in progress.got:
        deck_slide = slide.to_deck_slide()
        assert deck_slide.type == "full_image" and _texts(deck_slide) == []
        pictures = [element.image.url for element in deck_slide.elements if isinstance(element, ImageElement)]
        assert len(pictures) == 1 and "katten" in pictures[0]
        shown += pictures
    # Never the same picture twice (the fake photos have one a topic: so one spare, and the second is left out)
    assert len(shown) == len(set(shown)) == 1


# LAID OUT WITHOUT A NUMBER


@pytest.mark.parametrize("family", list(themes.FAMILIES))
def test_every_family_lays_a_spare_out_without_a_slide_number(family):
    made = slides.AgendaSlide("Today", "One", "Two", "Three").to_deck_slide()
    layout = engine.DeckLayout(3, _theme(family), total=12)
    first = layout.next(made)
    spare = layout.spare(0, made)
    second = layout.next(made)

    assert _numbers(spare) == []
    assert _numbers(first) in ([], [(1, 12)]) and _numbers(second) in ([], [(2, 12)])
    # Laying a spare out changes nothing of the deck's: its next slide is laid out as it would be without it
    alone = engine.DeckLayout(3, _theme(family), total=12)
    alone.next(made)
    assert alone.next(made) == second
    # And it's the theme's slide all the same: the same texts as the deck's, and decoration (but its number's)
    assert _texts(spare) == _texts(first)
    assert len(_texts(spare, decoration=True)) <= len(_texts(first, decoration=True))


# THE REAL SPARE GENERATORS


@pytest.fixture
def offline(monkeypatch, related):
    """No answer from anywhere on the web (but the fake ConceptNet's related words): ConceptNet's other relations
    (a pie's antonyms) and Datamuse find nothing, as when they're down; and every request is noted."""
    asked = []

    def nothing(url, *args, **kwargs):
        asked.append(url)

    monkeypatch.setattr(http_util, "get", nothing)
    monkeypatch.setattr(http_util, "get_json", nothing)
    monkeypatch.setattr(conceptnet, "_cooldown", http_util.Cooldown("ConceptNet API (test)"))
    return asked


@pytest.mark.parametrize("name", [generator.name for generator, _ in SPARE_GENERATORS])
def test_the_spare_generators_make_their_slides_about_a_topic_without_pictures(offline, name):
    spare = next(generator for generator, _ in SPARE_GENERATORS if generator.name == name)
    context = {"topic": "cat", "topics": ["cat"], "presenter": "Ann", "title": "About cats", "language": "en"}
    made = [
        PresentationSchema._run_generator(spare, 0, {**context, "seed": "cat"}, random_util.Rng(seed), _DeckState())
        for seed in range(5)
    ]
    assert all(result is not None for result in made), name
    for slide, _ in made:
        assert not slide.image_store(), name  # (no picture to find: a spare takes a fraction of a second)
    # (and on a sensitive topic, the ones that make light of it make none: another kind of slide takes its place)


def test_every_spare_generator_is_a_slide_generator_of_the_talks_of_every_format():
    # (a spare is a kind of slide the talk could have had: the formats beyond the TED-like talks take the same ones)
    names = {generator.name for generator, _ in SPARE_GENERATORS}
    assert names <= {generator.name for generator in get_schema("default").slide_generators}
    for format_name in ("default", "ted", "interview", "pitch", "academic", "corporate", "keynote"):
        assert get_schema(format_name).spare_generators == SPARE_GENERATORS, format_name
