"""Offline tests of talks that stream (talkgenerator.generator.stream_talk): talk.started, a slide.ready for every slide
in order, and talk.finished, with the same deck as a talk made at once; slides handed over while the language model
still writes; and a talk that stops once nobody wants it anymore.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images.
"""

import json
import threading

import pytest
from pydantic import TypeAdapter

from talkgenerator import generator
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.events import SlideReady, TalkEvent, TalkFinished, TalkStarted
from talkgenerator.plan.prompt import SPINE
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.schema.presentation_schema import TalkCancelled
from talkgenerator.util import image_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _jpeg, fake_schema


@pytest.fixture(autouse=True)
def images(monkeypatch):
    """Every image at example.com exists; local files load as usual. A probe finds what a download would, and .got
    are the images downloaded (whole) and probed."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    got = {"downloaded": [], "probed": []}

    def fetch(url):
        got["downloaded"].append(url)
        return jpeg if url.startswith("https://example.com/") else load(url)

    def probe(url):
        got["probed"].append(url)
        return url.startswith("https://example.com/") or load(url) is not None

    monkeypatch.setattr(image_util, "fetch_image", fetch)
    monkeypatch.setattr(image_util, "probe", probe)
    return got


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3}


def _streamed(slides=NUM_SLIDES, **options):
    return list(generator.stream_talk("fake", slides, **{**TALK, **options}))


def _made_at_once(slides=NUM_SLIDES, **options):
    _, slide_deck, _ = generator.generate_presentation("fake", slides, save_ppt=False, **{**TALK, **options})
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

    def __init__(self, change=None):
        super().__init__(change)
        self.go_on = threading.Event()
        self.done = threading.Event()
        self.stopped = None  # what stopped its answer halfway, if anything did

    def stream(self, request, on_text):
        response = self.complete(request)
        cut = response.text.index('"slide_', response.text.index('"slide_') + 1)  # (the second slide it writes)
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


class AlphabeticalModel(SlowModel):
    """Writes its answer's properties in alphabetical order, at every level, as some free models do (the free router
    often picks dots-studio/dots-3-note-preview:free, which does)."""

    def complete(self, request):
        response = super().complete(request)
        answer = json.loads(response.text.removeprefix("```json\n").removesuffix("\n```"))
        return response.model_copy(update={"text": json.dumps(answer, sort_keys=True, indent=2)})


def _while_the_model_writes(model, slides=NUM_SLIDES, **options):
    """A streamed talk's events, of which talk.started and the first two slides come while the model still writes."""
    stream = generator.stream_talk("fake", slides, llm=model, **{**TALK, **options})
    events = [next(stream), next(stream), next(stream)]
    assert not model.done.is_set()  # (as early as with the schema's order: once the spine and the first slide are in)
    model.go_on.set()
    return _parts([*events, *stream])


def _at_once(model, slides=NUM_SLIDES, **options):
    model.go_on.set()
    return _made_at_once(slides, llm=model, **options)


@pytest.mark.parametrize("slides", [NUM_SLIDES, 12], ids=["7 slides", "12 slides"])
def test_a_model_that_writes_in_alphabetical_order_streams_the_talk_made_at_once(slides):
    model = AlphabeticalModel()
    started, ready, deck = _while_the_model_writes(model, slides)

    # Every slide as the model wrote it (slide_10 doesn't sort before slide_2, which would have been taken for
    # skipped), and the model's title from the start (its spine sorts before its slides)
    assert all("Planned:" in event.slide.notes for event in ready)
    assert started.title == deck.title == "The title"
    assert deck.to_json() == _at_once(AlphabeticalModel(), slides).to_json()
    keys = [key for key, _ in ObjectReader().feed(model.complete(model.requests[0]).text)]
    assert keys == sorted(keys) and len(keys) == slides  # (the spine, and every slide but the title slide)


def _flat(answer):
    """The answer as a model writes it that doesn't put the spine in its object: its fields first, one by one."""
    spine = answer.pop(SPINE)
    slides = dict(answer)
    answer.clear()
    answer.update({**spine, **slides})


def test_a_model_that_writes_the_spine_field_by_field_streams_the_talk_made_at_once():
    started, ready, deck = _while_the_model_writes(SlowModel(change=_flat), theme="neon")
    assert started.title == deck.title == "The title"
    assert all("Planned:" in event.slide.notes for event in ready)
    assert deck.to_json() == _at_once(SlowModel(change=_flat), theme="neon").to_json()


def test_a_model_that_writes_the_spine_last_streams_the_talk_made_at_once():
    # (Then the talk starts once the answer is in: its title and the presenter's job come last)
    def spine_last(answer):
        answer[SPINE] = answer.pop(SPINE)

    model = SlowModel(change=spine_last)
    threading.Timer(0.5, model.go_on.set).start()  # (a while after it wrote the first slide, without the spine)
    started, ready, deck = _parts(_streamed(llm=model))
    assert started.title == deck.title == "The title"
    assert deck.slides[0].elements[1].text.endswith("Ann Example, The presenter job")
    assert deck.to_json() == _at_once(SlowModel(change=spine_last)).to_json()


def test_a_streamed_talk_that_a_model_wrongly_finds_unsafe_is_the_second_answers():
    def model():
        writer = FakeModel()
        writer.change = lambda answer: answer[SPINE].update(
            unsafe_topic=len(writer.requests) == 1, title=f"Take {len(writer.requests)}"
        )
        return writer

    started, ready, deck = _parts(_streamed(llm=model()))
    assert started.title == deck.title == "Take 2"
    assert all("Planned:" in event.slide.notes for event in ready)
    assert deck.to_json() == _made_at_once(llm=model()).to_json()


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


def test_a_streamed_talk_probes_its_images_instead_of_downloading_them(images):
    _streamed(llm=FakeModel(), theme="neon", parallel=True)

    web = [url for url in images["probed"] if url.startswith("https://example.com/")]
    assert web and not [url for url in images["downloaded"] if url.startswith("https://example.com/")]

    images["probed"].clear()
    _made_at_once(llm=FakeModel(), theme="neon", parallel=True)  # (a talk for a PowerPoint downloads them)
    assert not images["probed"] and any(url.startswith("https://example.com/") for url in images["downloaded"])


def test_a_streamed_slide_tells_its_images_sources_that_they_were_used(monkeypatch):
    # (Unsplash counts a download when a photo is used: a PowerPoint tells it when it gets the slide)
    used = []
    monkeypatch.setattr(ImageData, "mark_used", lambda image: used.append(image.get_shown_url()))

    *_, finished = _streamed(llm=FakeModel(), theme="neon")

    shown = [
        element.image.url for slide in finished.deck.slides for element in slide.elements if element.kind == "image"
    ]
    assert shown and sorted(used) == sorted(set(shown))
    used.clear()
    _made_at_once(llm=FakeModel(), theme="neon")  # (without a PowerPoint, nothing is used yet)
    assert used == []


class RoutedModel(FakeModel):
    """A router: asked as fake:router, it has another model answer."""

    id = "fake:router"

    def complete(self, request):
        return super().complete(request).model_copy(update={"model": "fake:picked-model"})


def test_a_streamed_talk_says_which_model_writes_it():
    started, _, deck = _parts(_streamed(llm=RoutedModel(), theme="neon"))
    assert started.language_model == "fake:router"  # (the one asked)
    assert deck.language_model == "fake:picked-model"  # (the one that answered)
    assert _made_at_once(llm=RoutedModel(), theme="neon").language_model == "fake:picked-model"

    started, _, deck = _parts(_streamed(llm="none"))
    assert started.language_model is None and deck.language_model is None  # (a classic talk)
