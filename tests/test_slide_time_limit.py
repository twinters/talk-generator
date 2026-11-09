"""Offline tests of a streamed talk's time limit per slide (stream_talk's slide_seconds, docs/v5-plan.md D67): a slide
that isn't made in time comes at once with what's quick, and nothing waits for what it was waiting for. A slide a
language model wrote keeps its texts, without the pictures it can do without and with spare pictures of the talk's
topic for those it can't; else a stand-in of the spare slides' kinds takes its place. A talk none of whose slides runs
out of time comes out as it does without a limit.

The talks are made with small fake schemas, fake spare generators, a fake model (test_llm_talks's) and a fake image
finder, whose searches for some queries take as long as a test wants.
"""

import itertools
import re
import threading
import time
import types

import pytest

from talkgenerator import generator
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.images import finder
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.events import SlideReady, TalkFinished
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema import presentation_schema
from talkgenerator.schema.presentation_schema import PresentationSchema, _Clock, _photo_slots, _SparePictures
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util import random_util
from talkgenerator.util.generator_util import CombinedGenerator, NoneGenerator
from tests.test_llm_talks import FakeModel, _classic_chart
from tests.test_streaming import SlowModel
from tests.test_streaming import images as images  # every image at example.com exists (a fixture)

TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3, "theme": "clean keynote"}
SECONDS = 0.6  # the time limit the talks below get
PHOTO = ImageSlot("a photo of the slide's topic", aesthetic="neutral")


def _chart(name, wait=None):
    """A classic chart titled after its generator and the slide's seed: after the wait (an event), if any."""

    def chart(context):
        if wait is not None:
            wait.wait(10)
        return (f"{name} about {context['seed']}", *_classic_chart(context)[1:])

    return slide_generator_types.ChartSlideGenerator(chart)


def _generator(name, weight, classic, kind=None, tags=(), **recipe):
    return SlideGeneratorData(
        classic,
        weight_function=weight,
        allowed_repeated_elements=10,
        tags=[name.lower(), *tags],
        name=name,
        llm=Recipe(kind, **recipe) if kind else None,
    )


def _spare_generators():
    return tuple(
        (_generator(f"Spare {letter}", ConstantWeightFunction(0), _chart(f"Spare {letter}")), 1.0) for letter in "ABC"
    )


def _schema(generators, max_allowed_tags=None):
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "A classic title about " + context["seed"],
        slide_generators=generators,
        max_allowed_tags=max_allowed_tags or {"title": 1},
        spare_generators=_spare_generators(),
    )


def _title():
    return _generator(
        "Title slide",
        PeakedWeight((0,), 100000, 0),
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        "title",
    )


@pytest.fixture
def held():
    """What the slow parts of a talk wait for (ten seconds at most): let go once the test is done."""
    event = threading.Event()
    yield event
    event.set()


@pytest.fixture
def photos(monkeypatch, held):
    """A fake image finder: a photo for every query (another one for each to avoid), declared 1600×900; the queries
    with a part in .slow wait for held first, and those with a part in .none find nothing. Once the test is done, what
    its talk left to finish by itself (a slide that ran out of time) finishes with it, before the real finder is back:
    an offline test never searches for real."""
    before = set(threading.enumerate())
    found = types.SimpleNamespace(slow=set(), none=set(), asked=[])

    def find(slot, query, avoid=()):
        query = query or ""
        found.asked.append(query)
        if any(part in query for part in found.slow):
            held.wait(10)
        if any(part in query for part in found.none):
            return None
        shown = {image.get_image_url() for image in avoid}
        for number in itertools.count():
            url = f"https://example.com/{re.sub(r'[^a-z0-9]+', '-', query.lower())}-{number}.jpg"
            if url not in shown:
                return ImageData(url, source="Fake photos", declared_size=(1600, 900), license_class="public-domain")
        raise AssertionError("unreachable")

    monkeypatch.setattr(finder, "find", find)
    yield found
    held.set()
    deadline = time.monotonic() + 10
    for thread in set(threading.enumerate()) - before:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))


def _use(monkeypatch, schema):
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _timed(slides, **options):
    """The talk's events, and how long it took to make them."""
    start = time.monotonic()
    events = list(generator.stream_talk("fake", slides, **{**TALK, **options}))
    return events, time.monotonic() - start


def _texts(slide):
    return [element.text for element in slide.elements if element.kind == "text" and element.role != "decoration"]


def _pictures(slide):
    return [element.image.url for element in slide.elements if element.kind == "image"]


# CLASSIC TALKS: a stand-in takes a slow slide's place


@pytest.fixture
def classic(monkeypatch, held):
    """A classic talk of 5 slides whose third slide's generator waits for held."""
    slides = [
        _title(),
        _generator("Chart", PeakedWeight((1, 3, 4), 100000, 0), _chart("Chart")),
        _generator("Slow", PeakedWeight((2,), 100000, 0), _chart("Slow", wait=held)),
    ]
    return _use(monkeypatch, _schema(slides))


@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_a_classic_slide_out_of_time_gets_a_stand_in_and_nothing_waits_for_it(classic, held, parallel):
    events, seconds = _timed(5, llm="none", slide_seconds=SECONDS, parallel=parallel)

    *_, finished = events
    assert isinstance(finished, TalkFinished)
    assert seconds < 5  # (not the ten seconds the slow slide's generator would have taken)
    third = finished.deck.slides[2]
    assert _texts(third)[0].startswith("Spare ") and _texts(third)[0].endswith("about cats")  # (its own seed)
    assert "Out of time" in third.notes
    # It's the talk's slide, where the slow one would have been: in the deck, numbered, handed over in order
    ready = [event for event in events if isinstance(event, SlideReady)]
    assert [event.index for event in ready] == list(range(5)) and ready[2].slide == third
    assert [_texts(slide)[0] for slide in finished.deck.slides[3:]] == ["Chart about cats"] * 2


def test_a_slide_due_while_the_threads_are_busy_with_slow_ones_starts_apart_and_comes_in_time(monkeypatch, held):
    # (two threads, both busy with slides that ran out of time: the quick slide after them isn't a stand-in, as its
    # time is for its own work, which starts when it's due rather than when a thread is free)
    slides = [
        _title(),
        _generator("Chart", PeakedWeight((1, 4), 100000, 0), _chart("Chart")),
        _generator("Slow", PeakedWeight((2, 3), 100000, 0), _chart("Slow", wait=held)),
    ]
    _use(monkeypatch, _schema(slides))
    events, seconds = _timed(5, llm="none", slide_seconds=SECONDS, parallel=2)

    assert seconds < 5
    deck = events[-1].deck
    assert ["Out of time" in slide.notes for slide in deck.slides] == [False, False, True, True, False]
    assert _texts(deck.slides[4])[0] == "Chart about cats"


@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_a_time_limit_no_slide_runs_out_of_changes_nothing(classic, held, parallel):
    held.set()  # (the slow slide is quick after all)
    with_limit, _ = _timed(5, llm="none", slide_seconds=30, parallel=parallel)
    without, _ = _timed(5, llm="none", parallel=parallel)
    assert with_limit[-1].deck.to_json() == without[-1].deck.to_json()
    assert not any("Out of time" in slide.notes for slide in with_limit[-1].deck.slides)


def test_without_a_time_limit_a_slow_slide_is_waited_for(classic, held):
    threading.Timer(1.0, held.set).start()
    events, seconds = _timed(5, llm="none")
    assert seconds >= 1.0
    assert _texts(events[-1].deck.slides[2])[0] == "Slow about cats"


def test_the_title_slide_has_no_time_limit(monkeypatch, held):
    slow_title = _generator(
        "Title slide",
        PeakedWeight((0,), 100000, 0),
        slide_generator_types.TitleSlideGenerator.of(lambda c: held.wait(10) and c["title"], lambda c: c["presenter"]),
    )
    _use(monkeypatch, _schema([slow_title, _generator("Chart", PeakedWeight((1,), 100000, 0), _chart("Chart"))]))
    threading.Timer(1.0, held.set).start()
    events, seconds = _timed(2, llm="none", slide_seconds=0.2)
    assert seconds >= 1.0 and events[-1].deck.slides[0].type == "title"


# TALKS A LANGUAGE MODEL WRITES: as planned, without looking the pictures up


@pytest.fixture
def planned(monkeypatch, photos):
    """A talk of 5 slides a model writes: a title slide, a photo filling the slide (2 and 5), a big number whose
    picture behind it is one it can do without (3), and two photos with captions (4). Its classic slides are charts."""
    slides = [
        _title(),
        _generator(
            "Full image", PeakedWeight((1, 4), 100000, 0), _chart("Classic"), "full_image", ["neutral"], images=(PHOTO,)
        ),
        _generator("Big number", PeakedWeight((2,), 100000, 0), _chart("Classic"), "big_number", images=(PHOTO,)),
        _generator(
            "Two photos", PeakedWeight((3,), 100000, 0), _chart("Classic"), "two_columns", images=(PHOTO, PHOTO)
        ),
    ]
    return _use(monkeypatch, _schema(slides))


def test_a_planned_slide_out_of_time_keeps_its_texts_with_spare_pictures_of_the_topic(planned, photos):
    photos.slow.add("slide 4")  # (the two photos' searches)
    events, seconds = _timed(5, llm=FakeModel(), slide_seconds=SECONDS)

    assert seconds < 5
    fourth = events[-1].deck.slides[3]
    assert fourth.type == "two_column_image"
    assert "title of slide 4" in _texts(fourth)  # (the model's)
    assert [url.rsplit("/", 1)[1] for url in _pictures(fourth)] == ["cats-0.jpg", "cats-1.jpg"]  # (of the topic)
    assert "Out of time" in fourth.notes
    # The other slides, as they come without a limit
    assert all("Out of time" not in slide.notes for index, slide in enumerate(events[-1].deck.slides) if index != 3)


def test_a_planned_slide_out_of_time_goes_without_a_picture_it_can_do_without(planned, photos):
    photos.slow.add("slide 3")  # (the picture behind the big number)
    events, seconds = _timed(5, llm=FakeModel(), slide_seconds=SECONDS)

    assert seconds < 5
    third = events[-1].deck.slides[2]
    assert third.type == "big_number" and "label of slide 3" in _texts(third)
    assert _pictures(third) == [] and "Out of time" in third.notes


def test_a_planned_slide_out_of_time_without_a_spare_picture_gets_a_stand_in(planned, photos):
    photos.slow.add("slide 4")
    photos.none.add("cats")  # (no picture of the topic to spare)
    events, seconds = _timed(5, llm=FakeModel(), slide_seconds=SECONDS)

    assert seconds < 5
    fourth = events[-1].deck.slides[3]
    assert _texts(fourth)[0].startswith("Spare ") and "Out of time" in fourth.notes


def test_a_planned_slide_out_of_time_in_another_language_keeps_its_texts(planned, photos):
    photos.slow.add("slide 4")
    events, _ = _timed(5, llm=FakeModel(), slide_seconds=SECONDS, language="nl")

    fourth = events[-1].deck.slides[3]
    assert fourth.type == "two_column_image" and "title of slide 4" in _texts(fourth)
    assert all("cats" in url for url in _pictures(fourth))


def test_a_stand_in_in_another_language_is_a_spare_picture_without_text(monkeypatch, planned, photos):
    # (two photos of a source that's no image slot, which a picture of the topic can't stand in for: as they'd be
    # English otherwise, the stand-in is a picture of the topic, without text)
    def own_photo(context):
        return PHOTO(context)

    slides = planned.slide_generators
    slides[3] = _generator(
        "Two photos", PeakedWeight((3,), 100000, 0), _chart("Classic"), "two_columns", images=(own_photo, own_photo)
    )
    _use(monkeypatch, _schema(slides))
    photos.slow.add("slide 4")
    events, seconds = _timed(5, llm=FakeModel(), slide_seconds=SECONDS, language="nl")

    assert seconds < 5
    fourth = events[-1].deck.slides[3]
    assert fourth.type == "full_image" and _texts(fourth) == []
    assert [url.rsplit("/", 1)[1] for url in _pictures(fourth)] == ["cats-0.jpg"]
    assert "Out of time" in fourth.notes


def test_waiting_for_the_model_to_write_a_slide_is_no_time_it_takes(planned, photos):
    model = SlowModel()  # (writes up to its third slide, then waits until it's told to go on)
    threading.Timer(1.5, model.go_on.set).start()
    events, seconds = _timed(5, llm=model, slide_seconds=0.3)

    assert seconds >= 1.5
    assert not any("Out of time" in slide.notes for slide in events[-1].deck.slides)
    assert all("Planned:" in slide.notes for slide in events[-1].deck.slides)


def test_a_planned_talk_with_a_time_limit_none_of_its_slides_runs_out_of_is_the_same(planned, photos):
    with_limit, _ = _timed(5, llm=FakeModel(), slide_seconds=30)
    without, _ = _timed(5, llm=FakeModel())
    assert with_limit[-1].deck.to_json() == without[-1].deck.to_json()


# THE PARTS


def test_a_slide_has_the_time_from_when_it_could_settle():
    clock = _Clock(0.2)
    assert 0.15 < clock.remaining() <= 0.2 and not clock.over
    time.sleep(0.25)
    assert clock.remaining() == 0.0 and clock.over
    assert _Clock(None).remaining() is None and not _Clock(None).over


def test_spare_pictures_go_where_any_photo_goes_once_each(photos):
    pictures = _SparePictures("cats", 3, random_util.Rng(1))
    pictures._find()  # (as its thread does)

    meme = ImageSlot("a meme's template", aesthetic="meme-templates")
    assert pictures.take(meme) is None and pictures.take(lambda context: None) is None
    weird = ImageSlot("a weird picture", aesthetic="weird")
    taken = [pictures.take(PHOTO), pictures.take(CombinedGenerator((1, PHOTO), (1, weird)))]
    assert [picture.get_image_url().rsplit("/", 1)[1] for picture in taken] == ["cats-0.jpg", "cats-1.jpg"]
    tall = ImageSlot("a portrait", aesthetic="neutral", orientation="portrait")
    assert pictures.take(tall) is None  # (they're 1600×900)
    last = pictures.take(PHOTO, avoid=[ImageData("https://example.com/cats-2.jpg")])
    assert last is None  # (the one left is one to avoid)
    pictures.give_back(taken[:1])
    assert pictures.take(PHOTO).get_image_url().endswith("cats-0.jpg")


def test_only_photo_slots_take_spare_pictures():
    assert _photo_slots(PHOTO) == [PHOTO]
    assert _photo_slots(CombinedGenerator((1, PHOTO), (1, NoneGenerator()))) is None
    assert _photo_slots(ImageSlot("a chart", aesthetic="bad-charts")) is None
    assert presentation_schema.SPARE_PICTURES == 3
