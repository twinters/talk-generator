"""Offline tests of early versions of a streamed talk's last slides (stream_talk's early, docs/v5-plan.md D70): each is
that slide's stand-in, made from the talk's start, about the slide's own topic, handed over as a slide.early at the
slide's place before the slide is in. It's none of the deck's slides, unless the slide runs out of time or can't be
made: then the early version takes its place, so what a presentation showed stays.

The talks are test_slide_time_limit's: small fake schemas with fake spare generators, a fake model and a fake image
finder, whose slow parts wait for `held`.
"""

import threading
import time
import types

import pytest
from pydantic import TypeAdapter

from talkgenerator import generator
from talkgenerator.models.deck import DeckSlide
from talkgenerator.models.events import SlideEarly, SlideReady, TalkEvent
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.slide.slide_deck import SlideDeck
from tests.test_livelier_slides import _numbers
from tests.test_llm_talks import FakeModel
from tests.test_slide_time_limit import SECONDS, _pictures, _texts, _timed
from tests.test_slide_time_limit import classic as classic  # (fixtures)
from tests.test_slide_time_limit import held as held
from tests.test_slide_time_limit import images as images
from tests.test_slide_time_limit import no_late_wait as no_late_wait
from tests.test_slide_time_limit import photos as photos
from tests.test_slide_time_limit import planned as planned


def _early(events):
    return [event for event in events if isinstance(event, SlideEarly)]


def _ready(events):
    return [event for event in events if isinstance(event, SlideReady)]


# CLASSIC TALKS


@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_early_versions_of_the_last_slides_come_before_those_slides(classic, held, parallel):
    threading.Timer(1.5, held.set).start()  # (the third slide's generator is done 1.5 s in)
    events, _ = _timed(5, llm="none", early=3, parallel=parallel)

    early = _early(events)
    assert [event.index for event in early] == [2, 3, 4]  # (the last three slides', in order)
    ready = {event.index: events.index(event) for event in _ready(events)}
    for event in early:
        assert events.index(event) < ready[event.index]
        assert _texts(event.slide)[0].startswith("Spare ") and _texts(event.slide)[0].endswith("about cats")
        assert _numbers(event.slide) == [(event.index + 1, 5)]  # (numbered as the slide it's an early version of)
        assert "Out of time" not in event.slide.notes


def test_early_versions_are_none_of_the_decks_slides(classic, held):
    threading.Timer(1.5, held.set).start()
    with_early, _ = _timed(5, llm="none", early=3)
    held.clear()
    threading.Timer(1.5, held.set).start()
    without, _ = _timed(5, llm="none")

    assert _early(with_early) and not _early(without)
    assert with_early[-1].deck.to_json() == without[-1].deck.to_json()
    assert _texts(with_early[-1].deck.slides[2])[0] == "Slow about cats"


def test_early_version_events_are_json_that_reads_back(classic, held):
    threading.Timer(1.5, held.set).start()
    events, _ = _timed(5, llm="none", early=2)

    early = _early(events)
    assert early and all(event.event == "slide.early" for event in early)
    assert [TypeAdapter(TalkEvent).validate_json(event.to_json()) for event in early] == early


@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
def test_a_slide_out_of_time_has_its_early_version_stand_in(classic, held, no_late_wait, parallel):
    events, seconds = _timed(5, llm="none", early=3, slide_seconds=SECONDS, parallel=parallel)

    assert seconds < 5
    (third_early,) = [event for event in _early(events) if event.index == 2]
    third = events[-1].deck.slides[2]
    assert _texts(third) == _texts(third_early.slide)  # (what a presentation showed stays)
    assert "Out of time" in third.notes


def test_a_slide_that_cant_be_made_gets_its_early_version_instead_of_being_left_out(monkeypatch, classic, held):
    work_out = PresentationSchema._work_out_slide

    def cant_make_the_third(schema, slide_nr, *args, **kwargs):
        if slide_nr == 2:
            time.sleep(0.5)  # (by then, its early version is made: it takes a hundredth of a second)
            return None
        return work_out(schema, slide_nr, *args, **kwargs)

    monkeypatch.setattr(PresentationSchema, "_work_out_slide", cant_make_the_third)
    without, _ = _timed(5, llm="none")
    with_early, _ = _timed(5, llm="none", early=3)

    assert without[-1].deck.counted() == 4  # (left out)
    deck = with_early[-1].deck
    assert deck.counted() == 5 and _texts(deck.slides[2])[0].startswith("Spare ")
    assert "Couldn't be made" in deck.slides[2].notes
    assert [event.index for event in _ready(with_early)] == list(range(6))  # (and the closer)


def test_a_talk_wants_no_early_versions_unless_it_asks_for_them(classic, held):
    held.set()
    events, _ = _timed(5, llm="none")
    assert _early(events) == []


# TALKS A LANGUAGE MODEL WRITES


def test_a_planned_talk_has_early_versions_of_its_last_slides(planned, photos, held):
    photos.slow.add("slide 4")  # (the two photos' searches)
    threading.Timer(1.5, held.set).start()
    events, _ = _timed(5, llm=FakeModel(), early=2)

    early = _early(events)
    assert [event.index for event in early] == [3, 4]
    ready = {event.index: events.index(event) for event in _ready(events)}
    assert all(events.index(event) < ready[event.index] for event in early)
    assert all(_texts(event.slide)[0].startswith("Spare ") for event in early)
    fourth = events[-1].deck.slides[3]
    assert fourth.type == "two_column_image" and "title of slide 4" in _texts(fourth)  # (the model's, in the deck)


def test_an_early_version_in_another_language_is_a_picture_of_the_slides_topic(planned, photos, held):
    # (one: every slide's topic here is "cats", and a second picture of it from the fake finder would repeat the first)
    photos.slow.add("slide 4")
    threading.Timer(1.5, held.set).start()
    events, _ = _timed(5, llm=FakeModel(), early=1, language="nl")

    (early,) = _early(events)
    assert early.index == 4
    assert early.slide.type == "full_image" and _texts(early.slide) == []
    assert [url.rsplit("/", 1)[1] for url in _pictures(early.slide)] == ["cats-0.jpg"]


# THE PARTS


def _slide(name):
    """A settled slide, as the talk hands it over (without a theme, not laid out)."""
    return types.SimpleNamespace(to_deck_slide=lambda: DeckSlide(type=name, layout=name), image_store=lambda: {})


def test_an_early_version_comes_at_its_slides_place_unless_that_slide_is_in():
    got = []
    following = generator._Following(got.append, early=3)
    deck = SlideDeck(5, title="Cats")
    following.started(deck)
    following.settled(deck, 0, _slide("title"))
    following.settled(deck, 1, _slide("one"))
    following.early_version(deck, 1, _slide("early one"))  # (in already: of no use)
    following.settled(deck, 3, _slide("three"))  # (slide 3, the second one left out: the places after it move up)
    following.early_version(deck, 2, _slide("early two"))  # (left out: of no use either)
    following.early_version(deck, 4, _slide("early four"))

    assert [(event.index, event.slide.type) for event in _early(got)] == [(3, "early four")]
    following.cancelled.set()
    following.early_version(deck, 4, _slide("early four"))
    assert len(_early(got)) == 1
