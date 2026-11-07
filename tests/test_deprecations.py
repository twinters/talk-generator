"""Offline tests of what talkgenerator 5 deprecates (docs/v5-plan.md, section 15, and docs/migrating-from-4.md):
generator.generate_presentation() and SlideDeck.to_slide_deck_dictionary() keep working throughout talkgenerator 5,
with a DeprecationWarning that says what to use instead, and talkgenerator's own ways of making talks never warn.

The talks are the fake ones of test_llm_talks and test_streaming: a fake schema with recipes, a fake model and fake
images.
"""

import inspect
import warnings
from pathlib import Path

import pytest

from talkgenerator import generator, runtime_checker
from talkgenerator.checks import benchmark
from talkgenerator.models.events import TalkFinished
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from tests.test_llm_talks import NUM_SLIDES, FakeModel, fake_schema
from tests.test_streaming import images as images  # fake images, downloaded and probed (an autouse fixture)

TALK = {"topic": "cats", "presenter": "Ann Example", "int_seed": 3}
# What every deprecation warning of talkgenerator's says
DEPRECATED = "is deprecated (it keeps working throughout talkgenerator 5)"


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _deprecations(caught):
    """The messages of talkgenerator's own deprecation warnings among the warnings caught."""
    return [str(caught_warning.message) for caught_warning in caught if DEPRECATED in str(caught_warning.message)]


# GENERATE_PRESENTATION


def test_generate_presentation_warns_and_says_what_to_use_instead():
    with pytest.warns(DeprecationWarning) as caught:
        generator.generate_presentation("fake", NUM_SLIDES, save_ppt=False, **TALK)

    (warning,) = [caught_warning for caught_warning in caught if DEPRECATED in str(caught_warning.message)]
    message = str(warning.message)
    assert message.startswith("generator.generate_presentation() is deprecated")
    for instead in ("generator.stream_talk()", "talk.finished", "render_pptx(deck)", "render_plan()"):
        assert instead in message
    assert message.endswith("docs/migrating-from-4.md")
    # The caller's line gets the blame, so that warning filters and logs show who still calls it
    assert Path(warning.filename) == Path(__file__)


def test_generate_presentation_makes_the_talk_it_always_made():
    """The same deck as the talk made the way talkgenerator makes its own, and as stream_talk's."""
    with pytest.warns(DeprecationWarning, match="stream_talk"):
        _, slide_deck, saved = generator.generate_presentation(
            "fake", NUM_SLIDES, save_ppt=False, llm=FakeModel(), **TALK
        )
    _, made, _ = generator._generate_presentation("fake", NUM_SLIDES, save_ppt=False, llm=FakeModel(), **TALK)
    events = list(generator.stream_talk("fake", NUM_SLIDES, llm=FakeModel(), **TALK))

    assert saved is None
    deck = slide_deck.to_deck(schema_name="fake")
    assert deck.to_json() == made.to_deck(schema_name="fake").to_json()
    assert isinstance(events[-1], TalkFinished) and events[-1].deck.to_json() == deck.to_json()
    assert sum("Planned:" in slide.notes for slide in deck.slides) > 0  # (the fake model wrote it)


def test_generate_presentation_hands_every_option_on(monkeypatch):
    shim, implementation = map(inspect.signature, (generator.generate_presentation, generator._generate_presentation))
    assert shim == implementation  # (an option of one is an option of the other)

    given = {name: object() for name in shim.parameters}
    received = {}

    def record(schema, slides, **options):
        received.update(schema=schema, slides=slides, **options)
        return None, None, None

    monkeypatch.setattr(generator, "_generate_presentation", record)
    with pytest.warns(DeprecationWarning):
        generator.generate_presentation(**given)
    assert received == given


def test_generate_presentation_takes_what_talkgenerator_com_passes(tmp_path):
    """talkgenerator.com's older /api/generate (talkgeneratorweb/generation.py) calls it so, and gets a PowerPoint."""
    with pytest.warns(DeprecationWarning, match="stream_talk"):
        _, _, presentation_file = generator.generate_presentation(
            schema="default",
            slides=NUM_SLIDES,
            topic="cats",
            title=None,
            presenter="Ann Example",
            output_folder=str(tmp_path),
            save_ppt=True,
            open_ppt=False,
            print_logs=False,
            parallel=False,
        )
    assert Path(presentation_file).parent == tmp_path and Path(presentation_file).suffix == ".pptx"


def test_talkgenerators_own_ways_of_making_talks_dont_warn(monkeypatch, tmp_path):
    """stream_talk (the site's talks), the command line and the checks make their talks without the warning (and the
    MCP server, which test_mcp_server checks)."""
    monkeypatch.setattr(runtime_checker, "check_runtime_environment", lambda: True)
    arguments = ["--topic", "cats", "--num_slides", str(NUM_SLIDES), "--int_seed", "3", "--output_folder"]
    args = generator.get_argument_parser().parse_args(
        [*arguments, str(tmp_path), "--open_ppt", "false", "--print_logs", "false"]
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        events = list(generator.stream_talk("fake", NUM_SLIDES, llm=FakeModel(), **TALK))
        render_pptx(events[-1].deck)  # (a streamed talk's PowerPoint)
        _, _, saved = generator.generate_presentation_using_cli_arguments(args)  # talkgenerator --topic cats
        benchmark.generate_deck("cats", 3, "fake", NUM_SLIDES, parallel=False)  # talkgenerator check

    assert Path(saved).is_file()
    assert _deprecations(caught) == []


# TO_SLIDE_DECK_DICTIONARY


def test_to_slide_deck_dictionary_warns_and_says_what_to_use_instead():
    slide_deck = SlideDeck(1)
    slide_deck.add_slide(0, slides.TitleSlide("Cats", None))

    with pytest.warns(DeprecationWarning) as caught:
        dictionary = slide_deck.to_slide_deck_dictionary()

    (message,) = _deprecations(caught)
    assert message.startswith("SlideDeck.to_slide_deck_dictionary() is deprecated")
    assert "slide_deck.to_deck()" in message and "to_json()" in message
    assert message.endswith("docs/migrating-from-4.md")
    # What it gives is the deck's slides, as data
    assert dictionary == [slide.model_dump(mode="json", exclude_none=True) for slide in slide_deck.to_deck().slides]
