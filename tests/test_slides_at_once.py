"""Offline tests of making a few slides at once (parallel as a number, as talkgenerator.com does on its small server):
the talk is the one made one by one, or all at once, in classic talks and in talks a language model writes, made at
once or streamed; and no more slides are made at the same time than asked for.

The talks are the fake ones of test_seeds, test_llm_talks and test_streaming.
"""

import threading
import time

import pytest

from talkgenerator import generator
from talkgenerator.schema import presentation_schema
from talkgenerator.schema.presentation_schema import slides_at_once
from talkgenerator.util import image_util
from tests import test_llm_talks, test_streaming
from tests.test_llm_talks import FakeModel, _jpeg, fake_schema
from tests.test_seeds import SEEDS, talk_json


@pytest.mark.parametrize(
    ("parallel", "slides", "most", "at_once"),
    [
        (False, 7, None, 1),
        (True, 7, None, 7),
        (True, 12, 8, 8),
        (True, 3, 8, 3),
        (0, 7, None, 1),
        (1, 7, None, 1),
        (2, 7, None, 2),
        (3, 7, 8, 3),
        (3, 2, None, 2),
        (3, 0, None, 1),
    ],
)
def test_how_many_slides_are_made_at_once(parallel, slides, most, at_once):
    assert slides_at_once(parallel, slides, most) == at_once


@pytest.mark.parametrize("at_once", [2, 3])
@pytest.mark.parametrize("int_seed", SEEDS)
def test_a_few_slides_at_once_give_the_talk_made_one_by_one(int_seed, at_once):
    assert talk_json(int_seed, parallel=at_once) == talk_json(int_seed, parallel=False)


def test_a_round_has_as_many_threads_as_slides_it_makes_at_once(monkeypatch):
    rounds = []

    class CountingPool(presentation_schema.ThreadPool):
        def __init__(self, *args, **kwargs):
            rounds.append(kwargs.get("processes"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(presentation_schema, "ThreadPool", CountingPool)
    for int_seed in SEEDS:
        talk_json(int_seed, parallel=2)
    assert rounds and set(rounds) == {2}
    rounds.clear()
    talk_json(SEEDS[0], parallel=1)
    assert rounds == []  # (one by one: no pool at all)


def test_no_more_slides_are_worked_out_at_the_same_time_than_asked_for(monkeypatch):
    working, most = 0, 0
    lock = threading.Lock()
    work_out = presentation_schema.PresentationSchema._work_out_slide

    def counted(self, *args, **kwargs):
        nonlocal working, most
        generating = args[6] if len(args) > 6 else kwargs.get("generate")
        if not generating or threading.current_thread() is threading.main_thread():
            return work_out(self, *args, **kwargs)
        with lock:
            working += 1
            most = max(most, working)
        try:
            time.sleep(0.02)  # (so that the slides being worked out overlap)
            return work_out(self, *args, **kwargs)
        finally:
            with lock:
                working -= 1

    monkeypatch.setattr(presentation_schema.PresentationSchema, "_work_out_slide", counted)
    talk_json(SEEDS[0], parallel=2)
    assert most == 2


@pytest.fixture
def images(monkeypatch):
    """Every image at example.com exists (downloaded or probed); local files load as usual."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: jpeg if url.startswith("https://example.com/") else load(url)
    )
    monkeypatch.setattr(
        image_util, "probe", lambda url: url.startswith("https://example.com/") or load(url) is not None
    )


@pytest.fixture
def llm_schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _planned_talk(parallel):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=test_llm_talks.NUM_SLIDES,
        topic="cats",
        presenter="Ann Example",
        int_seed=3,
        parallel=parallel,
        save_ppt=False,
        llm=FakeModel(),
    )
    return slide_deck.to_deck().to_json()


def test_a_planned_talk_is_the_same_made_a_few_slides_at_once(llm_schema, images):
    one_by_one = _planned_talk(False)
    assert _planned_talk(2) == one_by_one
    assert _planned_talk(3) == one_by_one


@pytest.mark.parametrize("llm", ["fake", "none"], ids=["planned", "classic"])
def test_a_talk_streamed_a_few_slides_at_once_is_the_talk_made_at_once(llm, llm_schema, images):
    def model():
        return FakeModel() if llm == "fake" else "none"

    _, ready, deck = test_streaming._parts(test_streaming._streamed(llm=model(), parallel=2, theme="clean keynote"))
    made = test_streaming._made_at_once(llm=model(), parallel=False, theme="clean keynote")
    assert deck.to_json() == made.to_json()
    assert [event.index for event in ready] == list(range(len(deck.slides)))
