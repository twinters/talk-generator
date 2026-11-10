"""Offline tests of a streamed talk's progress (talkgenerator.generator.stream_talk's progress, docs/v5-plan.md D72):
talk.progress events from the talk's very start, whenever how far it is changes: where the talk is (starting, asking
its language model, planning, writing, composing, finishing), where every slide is (waiting, planned, written, ready),
how much of the model's plan came in, and how many of its slides the model wrote. They come only when they're asked
for, and change nothing else.

The talks are the fake ones of test_llm_talks (a fake schema with recipes, a fake model and fake images).
"""

import itertools
import threading

import pytest
from pydantic import TypeAdapter

from talkgenerator import generator
from talkgenerator.models.events import TalkEvent, TalkFinished, TalkProgress, TalkStarted
from talkgenerator.plan.outline import ADVANCED
from talkgenerator.plan.prompt import SPINE
from talkgenerator.plan.stream import ObjectReader
from tests.test_llm_talks import NUM_SLIDES, FakeModel, fake_schema
from tests.test_streaming import images as images  # every image at example.com exists (a fixture)

TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3}
STAGES = ["starting", "asking", "planning", "writing", "composing", "finishing"]
SLIDE_STAGES = ["waiting", "planned", "written", "ready"]


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _streamed(llm, progress=True, **options):
    return list(generator.stream_talk("fake", NUM_SLIDES, llm=llm, progress=progress, **{**TALK, **options}))


def _progress(events):
    return [event for event in events if isinstance(event, TalkProgress)]


def _stages(progress):
    """The talk's stages, in the order they came (each once in a row)."""
    return [stage for stage, _ in itertools.groupby(event.stage for event in progress)]


def _slide(progress, slide_nr):
    """The slide's stages, in the order they came (each once in a row)."""
    return [stage for stage, _ in itertools.groupby(event.slides[slide_nr] for event in progress)]


def _forward(progress):
    """Whether every slide's stage only went forward."""
    return all(
        _slide(progress, slide_nr) == sorted(_slide(progress, slide_nr), key=SLIDE_STAGES.index)
        for slide_nr in range(NUM_SLIDES)
    )


# ONLY WHEN IT'S ASKED FOR


def test_a_talk_tells_its_progress_only_when_asked_and_that_changes_nothing_else():
    with_it = _streamed(FakeModel())
    without = _streamed(FakeModel(), progress=False)

    assert not _progress(without)
    others = [event for event in with_it if not isinstance(event, TalkProgress)]
    assert [event.event for event in others] == [event.event for event in without]
    assert others[-1].deck.to_json() == without[-1].deck.to_json()
    # From its very start, before talk.started, and whenever it changes (never twice the same in a row)
    assert isinstance(with_it[0], TalkProgress) and with_it[0].stage == "starting"
    progress = _progress(with_it)
    assert all(before != after for before, after in itertools.pairwise(progress))


def test_progress_events_are_json_that_reads_back():
    progress = _progress(_streamed(FakeModel(), llm_level=ADVANCED))
    adapter = TypeAdapter(TalkEvent)
    assert progress and all(event.event == "talk.progress" for event in progress)
    assert [adapter.validate_json(event.to_json()) for event in progress] == progress


# A TALK A LANGUAGE MODEL WRITES


def test_a_basic_talk_is_asked_for_planned_written_and_composed():
    events = _streamed(FakeModel())
    progress = _progress(events)

    assert _stages(progress) == STAGES
    assert progress[0].slides == ("waiting",) * NUM_SLIDES
    # The spine's fields one by one as the model writes them (a dot each on talkgenerator.com), as its plan
    planning = [event.parts for event in progress if event.stage == "planning"]
    assert planning == sorted(planning) and planning[0] == 0 and len(set(planning)) > 2
    # Its slides as the model writes them (every slide but the title slide), each ready once it's handed over
    assert progress[-1].writes == progress[-1].written == NUM_SLIDES - 1
    assert _slide(progress, 0) == ["waiting", "ready"]  # (the title slide comes from the spine)
    assert all(_slide(progress, slide_nr) == ["waiting", "written", "ready"] for slide_nr in range(1, NUM_SLIDES))
    # The last one says every slide is in, before talk.finished
    assert progress[-1].stage == "finishing" and progress[-1].slides == ("ready",) * NUM_SLIDES
    assert events[-2] == progress[-1] and isinstance(events[-1], TalkFinished)


def test_a_slide_is_ready_in_the_progress_once_it_s_handed_over():
    events = _streamed(FakeModel())
    ready = 0
    for event in events:
        if isinstance(event, TalkProgress):
            assert event.slides.count("ready") == ready
        elif event.event == "slide.ready":
            ready += 1


def test_an_advanced_talk_tells_every_slide_s_idea_as_its_outline_comes_in():
    progress = _progress(_streamed(FakeModel(), llm_level=ADVANCED))

    # (its plan is in once every slide's idea is: its last batch is asked for after that, so it's written after it)
    assert _stages(progress) == STAGES
    assert _forward(progress)
    # Every slide the model writes is planned (its idea in) before it's written, in a request of its own
    assert all(
        _slide(progress, slide_nr) == ["waiting", "planned", "written", "ready"] for slide_nr in range(1, NUM_SLIDES)
    )
    # Its plan is the outline's spine and every slide's idea
    spine = next(event.parts for event in progress if "planned" in event.slides)
    assert progress[-1].parts == spine - 1 + NUM_SLIDES - 1


def test_a_talk_waits_in_asking_until_its_model_says_a_word():
    class Silent(FakeModel):
        """Says nothing until it's told to go on, as a free model can keep a talk waiting."""

        def __init__(self):
            super().__init__()
            self.go_on = threading.Event()

        def stream(self, request, on_text):
            self.go_on.wait(timeout=10)
            return super().stream(request, on_text)

    model = Silent()
    stream = generator.stream_talk("fake", NUM_SLIDES, llm=model, progress=True, **TALK)
    first, second = next(stream), next(stream)
    assert (first.stage, second.stage) == ("starting", "asking")
    assert second.writes == NUM_SLIDES - 1 and second.written == 0

    model.go_on.set()
    rest = list(stream)
    assert any(isinstance(event, TalkStarted) for event in rest)
    assert _stages(_progress(rest)) == STAGES[2:]


def test_a_model_asked_again_takes_the_talk_back_to_asking():
    writer = FakeModel()
    writer.change = lambda answer: answer[SPINE].update(unsafe_topic=len(writer.requests) == 1)
    progress = _progress(_streamed(writer))

    stages = _stages(progress)
    assert stages.count("asking") == 2 and stages[-2:] == ["composing", "finishing"]
    # (the second answer's slides: the first one's, on a topic it found unsafe, weren't taken)
    asked_again = max(index for index, event in enumerate(progress) if event.stage == "asking")
    assert progress[-1].written == NUM_SLIDES - 1 and all(event.written == 0 for event in progress[:asked_again])


@pytest.mark.parametrize("where", ["planning", "_stage"], ids=["the model's", "the talk's"])
def test_telling_how_far_a_talk_is_never_stops_it(monkeypatch, where):
    def crash(*args):
        raise RuntimeError("a bug in telling how far the talk is")

    monkeypatch.setattr(generator._Stages, where, crash)
    events = _streamed(FakeModel())

    assert isinstance(events[-1], TalkFinished)
    assert all("Planned:" in slide.notes for slide in events[-1].deck.slides)  # (the model's slides, every one)


def test_a_model_that_fails_leaves_a_classic_talk_that_s_composed():
    progress = _progress(_streamed(FakeModel(fail=RuntimeError("down"))))
    assert _stages(progress)[-2:] == ["composing", "finishing"]
    assert progress[-1].written == 0 and _forward(progress)


# A CLASSIC TALK


def test_a_classic_talk_goes_from_starting_to_composing():
    progress = _progress(_streamed("none"))

    assert _stages(progress) == ["starting", "composing", "finishing"]
    assert all(event.parts == event.writes == event.written == 0 for event in progress)
    assert all(_slide(progress, slide_nr) == ["waiting", "ready"] for slide_nr in range(NUM_SLIDES))


# READING THE ANSWER


def test_the_reader_tells_how_many_of_a_value_s_own_parts_are_in():
    reader = ObjectReader()
    assert reader.reading == (None, 0)
    reader.feed('{"about": {"title": "Cats, and why", "presenter_job"')
    assert reader.reading == ("about", 1)  # (the title: the comma in it is a text's)
    reader.feed(': "Vet", "thesis": "Cats {rule}, [sort of]"}')
    assert reader.reading == ("about", 2)  # (the thesis counts once the spine is complete, and handed over)
    found = reader.feed(', "slide_2": {"title": "T", "points": ["a", "b"]')
    assert [key for key, _ in found] == ["about"] and reader.reading == ("slide_2", 1)
    reader.feed("}}")
    assert reader.reading == (None, 0) and reader.done
