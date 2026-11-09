"""Offline tests: how much a language model does for a talk (docs/v5-plan.md, D67). At the Basic level, it writes the
talk in one request, from the words the talk's dice give its slides; at the Advanced level, it plans the talk first,
in a small request of its own (an outline: its thesis, a running gag, and every slide's word and idea), and then
writes it with that plan in its request. An outline that fails leaves the talk as at the Basic level."""

import importlib.util
import json

import pytest

from talkgenerator import generator
from talkgenerator.llm.base import ProviderError, TextResponse
from talkgenerator.llm.ledger import Budget
from talkgenerator.models.events import TalkFinished
from talkgenerator.plan import outline
from talkgenerator.plan.outline import ADVANCED, BASIC
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _planned, _talk
from tests.test_llm_talks import images as images  # (fake images at example.com: an autouse fixture)
from tests.test_llm_talks import schema as schema  # (the fake schema, as a fixture)


class _Seeds(SlideSeedGenerator):
    """The dice's words: the topic on the first slide, "word 2" to "word 7" on the others, each with two others that
    would have done."""

    def __init__(self, topics, slides):
        self.topics = topics

    def get_seed(self, slide_nr):
        return self.topics[0] if slide_nr == 0 else f"word {slide_nr + 1}"

    def alternatives(self, slide_nr):
        return () if slide_nr == 0 else (f"other {slide_nr + 1}", f"third {slide_nr + 1}")


@pytest.fixture
def seeds(schema, monkeypatch):
    monkeypatch.setattr(schema, "_seed_generator", _Seeds)
    return schema


def _purposes(model):
    return [request.purpose for request in model.requests]


def test_a_basic_talk_is_one_request(seeds):
    model = FakeModel()
    deck = _talk(model)
    assert _purposes(model) == ["talk plan"]
    assert deck.llm_level == BASIC and deck.usage.requests == 1
    assert "The idea:" not in model.requests[0].messages[0].content


def test_an_advanced_talk_is_planned_before_it_is_written(seeds):
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED)
    assert _purposes(model) == [outline.PURPOSE, "talk plan"]
    assert deck.llm_level == ADVANCED and deck.usage.requests == 2
    assert all(_planned(deck))

    # The outline is offered the dice's words for every slide but the title slide
    asked = model.requests[0].messages[0].content
    assert "slide_2: " in asked and "Its words: word 2, other 2, third 2" in asked
    assert "slide_1:" not in asked
    # The talk's request has its thesis, its running gag, and every slide's word and idea
    written = model.requests[1].messages[0].content
    assert "The thesis: The thesis" in written and "The running gag: The running gag" in written
    assert "slide_2: " in written and "A word to riff on: riff of slide 2. The idea: idea of slide 2" in written
    assert "word 2" not in written
    # (and its slides say what they riffed on, in their notes)
    assert deck.slides[1].notes.startswith("Seed: riff of slide 2")


def test_the_outline_asks_for_a_word_and_an_idea_for_every_slide(seeds):
    model = FakeModel()
    _talk(model, llm_level=ADVANCED)
    schema = model.requests[0].json_schema
    assert list(schema["properties"]) == [outline.SPINE, *(f"slide_{number}" for number in range(2, NUM_SLIDES + 1))]
    assert list(schema["properties"][outline.SPINE]["properties"]) == ["thesis", "running_gag"]
    assert list(schema["properties"]["slide_2"]["properties"]) == ["riff", "idea"]
    assert model.requests[0].system == outline.OUTLINE_SYSTEM_PROMPT


def test_slides_the_outline_leaves_out_keep_the_dice_s_words(seeds):
    def forget(answer):
        if outline.SPINE in answer and "slide_3" in answer and "riff" in answer["slide_3"]:
            answer["slide_3"] = {"riff": "", "idea": "an idea without a word"}

    model = FakeModel(change=forget)
    _talk(model, llm_level=ADVANCED)
    written = model.requests[1].messages[0].content
    assert "A word to riff on: word 3\n" in written or "A word to riff on: word 3." in written
    assert "riff of slide 2" in written


class _Failing(FakeModel):
    """Fails (or declines) the outline, and writes the talk."""

    def __init__(self, refuse=False):
        super().__init__()
        self.refuse = refuse

    def complete(self, request):
        if request.purpose == outline.PURPOSE:
            self.requests.append(request)
            if self.refuse:
                return TextResponse(text="", finish="refused", model=self.id)
            raise ProviderError("the outline failed")
        return super().complete(request)


@pytest.mark.parametrize("refuse", [False, True])
def test_a_talk_whose_outline_fails_is_written_as_a_basic_one(seeds, refuse):
    model = _Failing(refuse)
    deck = _talk(model, llm_level=ADVANCED)
    assert _purposes(model) == [outline.PURPOSE, "talk plan"]
    assert deck.llm_level == BASIC and all(_planned(deck))
    assert "A word to riff on: word 2" in model.requests[1].messages[0].content


def test_an_outline_cut_off_keeps_the_slides_it_planned():
    planned = [_slide(2), _slide(3)]
    text = (
        '{"about": {"thesis": "Cats are liquid", "running_gag": "a teapot"}, "slide_2": {"riff": "teapot", "idea": "A '
    )
    assert outline.read_outline(outline._properties(text), planned) is None  # (no slide's plan came in whole)
    text += 'chart of pour rates"}, "slide_3": {"riff": "box'
    found = outline.read_outline(outline._properties(text), planned)
    assert found is not None and found.thesis == "Cats are liquid" and found.running_gag == "a teapot"
    assert found.slides == {2: outline.SlideIdea("teapot", "A chart of pour rates")}


def _slide(number):
    from talkgenerator.plan.kinds import Recipe
    from talkgenerator.plan.prompt import PlannedSlide

    return PlannedSlide(number, "Fake", Recipe("statement"), f"word {number}")


def test_an_outline_s_texts_are_kept_short():
    long = "an idea " * 60
    found = outline.read_outline({"slide_2": {"riff": "a riff " * 20, "idea": long}}, [_slide(2)])
    assert found is not None
    assert len(found.slides[2].riff) <= outline.RIFF_LENGTH and len(found.slides[2].idea) <= outline.IDEA_LENGTH
    assert not found.slides[2].idea.endswith(" ")


def test_a_budget_without_room_for_both_requests_skips_the_outline(seeds):
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_requests=1))
    assert _purposes(model) == ["talk plan"]
    assert deck.llm_level == BASIC and all(_planned(deck))
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_requests=2))
    assert deck.llm_level == ADVANCED


def test_a_budget_of_no_money_skips_the_outline_of_a_model_of_unknown_price(seeds):
    model = FakeModel()  # (fake:model has no price: a talk at $0 doesn't ask it at all)
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_cost_usd=0.0))
    assert model.requests == [] and deck.llm_level is None


def test_the_level_comes_from_the_settings(seeds, monkeypatch):
    monkeypatch.setenv("TALKGENERATOR_LLM_LEVEL", "Advanced")
    model = FakeModel()
    assert _talk(model).llm_level == ADVANCED and len(model.requests) == 2
    model = FakeModel()
    assert _talk(model, llm_level="basic").llm_level == BASIC and len(model.requests) == 1


def test_a_level_there_isnt_is_an_error(seeds):
    with pytest.raises(ValueError, match="no language model level 'expert'"):
        _talk(FakeModel(), llm_level="expert")
    assert outline.level(" ADVANCED ") == ADVANCED and outline.level(None) == BASIC


def test_a_classic_talk_has_no_level(seeds):
    deck = _talk("none", llm_level=ADVANCED)
    assert deck.llm_level is None and deck.usage.requests == 0
    assert "llm_level" not in json.loads(deck.to_json())


def test_a_streamed_talk_can_be_advanced(seeds):
    model = FakeModel()
    events = list(
        generator.stream_talk(
            "fake", NUM_SLIDES, topic="cats", presenter="Ann Example", int_seed=1, llm=model, llm_level=ADVANCED
        )
    )
    finished = events[-1]
    assert isinstance(finished, TalkFinished) and finished.deck.llm_level == ADVANCED
    assert _purposes(model) == [outline.PURPOSE, "talk plan"]


def test_the_command_line_takes_the_level():
    args = generator.get_argument_parser().parse_args(["--topic", "cats", "--llm_level", "advanced"])
    assert args.llm_level == ADVANCED
    with pytest.raises(SystemExit):
        generator.get_argument_parser().parse_args(["--llm_level", "expert"])


@pytest.mark.skipif(
    importlib.util.find_spec("mcp") is None, reason="needs the MCP SDK (pip install 'talkgenerator[mcp]')"
)
def test_the_mcp_server_takes_the_level(tmp_path):
    from talkgenerator import mcp_server

    with pytest.raises(ValueError, match="no language model level"):
        mcp_server.make_server(tmp_path, llm_level="expert")
    assert mcp_server.make_server(tmp_path, llm_level="advanced") is not None


# THE TEXTS CLASSIC SOURCES FIND, AT THE BASIC LEVEL: A REAL QUOTE'S


def test_an_advanced_talk_writes_what_a_basic_one_finds():
    from talkgenerator.plan.kinds import Recipe

    found = Recipe("statement", brief="A real quote (talkgenerator finds it)", texts_from={"text": lambda context: "x"})
    written = outline.in_own_words(found)
    assert written.texts_from == {} and written.brief == ""
    assert [text.name for text in written.written_fields()] == ["text"]
    assert "never a real person's words" in written.hints["text"]
    plain = Recipe("statement")
    assert outline.in_own_words(plain) is plain


@pytest.fixture
def quotes(seeds, monkeypatch):
    """The fake schema, with a slide of a real quote that a classic source finds, which every slide would rather be."""
    from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
    from talkgenerator.plan.kinds import Recipe
    from talkgenerator.schema.presentation_schema import PresentationSchema
    from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
    from talkgenerator.util.generator_util import NoneGenerator, StaticGenerator
    from tests.test_llm_talks import _photo, _photos

    quote = SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(NoneGenerator(), StaticGenerator("A quote"), _photo("q")),
        weight_function=ConstantWeightFunction(1000),
        allowed_repeated_elements=10,
        name="Fake quote",
        llm=Recipe("statement", images=(_photos,), texts_from={"text": lambda context: "A real quote"}),
    )
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_Seeds,
        title_generator=lambda context: "A classic title",
        slide_generators=[*seeds.slide_generators, quote],
        max_allowed_tags={"title": 1, "three_columns": 1},
    )
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _texts(deck):
    return [element.text for slide in deck.slides for element in slide.elements if element.kind == "text"]


def test_an_advanced_talk_s_quotes_are_sayings_of_its_own(quotes):
    basic = _talk(FakeModel())
    assert "A real quote" in _texts(basic)
    model = FakeModel()
    advanced = _talk(model, llm_level=ADVANCED)
    assert "A real quote" not in _texts(advanced) and any(text.startswith("text of slide") for text in _texts(advanced))
    assert all(_planned(advanced))
    assert "never a real person's words" in model.requests[1].messages[0].content


def test_an_advanced_talk_without_its_plan_keeps_its_real_quotes(quotes):
    model = _Failing()
    deck = _talk(model, llm_level=ADVANCED)
    assert deck.llm_level == BASIC and "A real quote" in _texts(deck)
    assert "never a real person's words" not in model.requests[1].messages[0].content
