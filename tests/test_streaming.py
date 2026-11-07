"""Offline tests of talks that stream (talkgenerator.generator.stream_talk): talk.started, a slide.ready for every slide
in order, and talk.finished, with the same deck as a talk made at once; slides handed over while the language model
still writes; and a talk that stops once nobody wants it anymore.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images.
"""

import threading

import pytest
from pydantic import TypeAdapter

from talkgenerator import generator
from talkgenerator.models.events import SlideReady, TalkEvent, TalkFinished, TalkStarted
from talkgenerator.schema.presentation_schema import TalkCancelled
from talkgenerator.util import image_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _jpeg, fake_schema


@pytest.fixture(autouse=True)
def images(monkeypatch):
    """Every image at example.com exists; local files load as usual."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: jpeg if url.startswith("https://example.com/") else load(url)
    )


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3}


def _streamed(**options):
    return list(generator.stream_talk("fake", NUM_SLIDES, **{**TALK, **options}))


def _made_at_once(**options):
    _, slide_deck, _ = generator.generate_presentation("fake", NUM_SLIDES, save_ppt=False, **{**TALK, **options})
    return slide_deck.to_deck(schema_name="fake")


def _parts(events):
    started, *ready, finished = events
    assert isinstance(started, TalkStarted) and isinstance(finished, TalkFinished)
    assert all(isinstance(event, SlideReady) for event in ready)
    return started, ready, finished.deck


@pytest.mark.parametrize("parallel", [True, False], ids=["in parallel", "one by one"])
@pytest.mark.parametrize("llm", ["fake", "none"], ids=["planned", "classic"])
@pytest.mark.parametrize("theme", ["clean keynote", "classic"], ids=["themed", "classic theme"])
def test_a_streamed_talk_is_the_talk_made_at_once(parallel, llm, theme):
    def model():
        return FakeModel() if llm == "fake" else "none"

    started, ready, deck = _parts(_streamed(llm=model(), parallel=parallel, theme=theme))

    assert deck.to_json() == _made_at_once(llm=model(), parallel=parallel, theme=theme).to_json()
    assert (started.title, started.presenter, started.topics, started.seed) == (
        deck.title,
        deck.presenter,
        deck.topics,
        deck.seed,
    )
    assert (started.slides, started.theme, started.style) == (NUM_SLIDES, deck.theme, deck.style)
    # Every slide in order, as the deck has it (laid out in the theme, in a themed talk)
    assert [event.index for event in ready] == list(range(len(deck.slides)))
    assert [event.slide for event in ready] == list(deck.slides)
    if theme != "classic":
        assert all(event.slide.layout.startswith("v5/") for event in ready)
    if llm == "fake":
        assert deck.usage.requests == 1


def test_events_are_json_that_reads_back():
    events = _streamed(llm=FakeModel(), theme="neon")
    adapter = TypeAdapter(TalkEvent)
    assert [adapter.validate_json(event.to_json()) for event in events] == events
    assert [event.event for event in events] == ["talk.started", *["slide.ready"] * NUM_SLIDES, "talk.finished"]


class SlowModel(FakeModel):
    """Writes the talk up to its third slide, then waits until it's told to go on (or for ten seconds)."""

    def __init__(self):
        super().__init__()
        self.go_on = threading.Event()
        self.done = threading.Event()
        self.stopped = None  # what stopped its answer halfway, if anything did

    def stream(self, request, on_text):
        response = self.complete(request)
        cut = response.text.index('"slide_3"')
        on_text(response.text[:cut])
        self.go_on.wait(timeout=10)
        try:
            on_text(response.text[cut:])
        except Exception as error:
            self.stopped = error
            raise
        finally:
            self.done.set()
        return response


def test_slides_come_while_the_model_still_writes():
    model = SlowModel()
    stream = generator.stream_talk("fake", NUM_SLIDES, llm=model, **TALK)
    assert isinstance(next(stream), TalkStarted)
    title_slide, second = next(stream), next(stream)

    assert (title_slide.index, second.index) == (0, 1)
    assert "Planned:" in second.slide.notes  # (the model's slide, not a classic one)
    assert not model.done.is_set()  # handed over while the model was still writing the rest

    model.go_on.set()
    *ready, finished = list(stream)
    assert [event.index for event in ready] == list(range(2, NUM_SLIDES))
    assert all("Planned:" in slide.notes for slide in finished.deck.slides)


def test_a_talk_stops_once_nobody_wants_it():
    model = SlowModel()
    stream = generator.stream_talk("fake", NUM_SLIDES, llm=model, **TALK)
    for event in stream:
        if isinstance(event, SlideReady) and event.index == 1:
            break  # (closes the stream)
    stream.close()

    model.go_on.set()
    assert model.done.wait(timeout=10)
    assert isinstance(model.stopped, TalkCancelled)  # the rest of the answer wasn't read
    talks = [thread for thread in threading.enumerate() if thread.name in ("talk", "talk plan")]
    for thread in talks:
        thread.join(timeout=10)
    assert not any(thread.is_alive() for thread in talks)


def test_what_stops_a_talk_comes_out_of_the_stream():
    with pytest.raises(ValueError, match="language"):
        _streamed(language="xx")
