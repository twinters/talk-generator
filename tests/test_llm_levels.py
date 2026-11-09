"""Offline tests: how much a language model does for a talk (docs/v5-plan.md, D68). At the Basic level, it writes the
talk in one request, from the words the talk's dice give its slides; at the Advanced level, it plans the talk first
(an outline: its spine, a running gag, and every slide's word and idea), and every slide is written in a request of
its own as soon as its idea is in, in parallel. An outline that brings no spine leaves the talk a Basic one."""

import importlib.util
import json
import threading
import time

import pytest

from talkgenerator import generator
from talkgenerator.llm import providers
from talkgenerator.llm.base import ProviderError, TextResponse
from talkgenerator.llm.ledger import Budget
from talkgenerator.models.events import TalkFinished
from talkgenerator.plan import outline, prompt
from talkgenerator.plan.outline import ADVANCED, BASIC
from talkgenerator.schema.slide_topic_generators import SlideSeedGenerator
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _planned, _talk
from tests.test_llm_talks import images as images  # (fake images at example.com: an autouse fixture)
from tests.test_llm_talks import schema as schema  # (the fake schema, as a fixture)

PLANNED = NUM_SLIDES - 1  # (every slide but the title slide, which the spine makes)


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


def _slide_request(model, key):
    """The request that wrote the slide of this key (a slide's request at the Advanced level)."""
    return next(
        request
        for request in model.requests
        if request.purpose == outline.SLIDE_PURPOSE and key in request.json_schema["properties"]
    )


def test_a_basic_talk_is_one_request(seeds):
    model = FakeModel()
    deck = _talk(model)
    assert _purposes(model) == ["talk plan"]
    assert deck.llm_level == BASIC and deck.usage.requests == 1
    assert "The idea:" not in model.requests[0].messages[0].content


def test_an_advanced_talk_is_planned_and_its_slides_written_one_by_one(seeds):
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED)
    purposes = _purposes(model)
    assert purposes[0] == outline.PURPOSE and sorted(purposes[1:]) == [outline.SLIDE_PURPOSE] * PLANNED
    assert deck.llm_level == ADVANCED and deck.usage.requests == 1 + PLANNED
    assert all(_planned(deck))
    assert deck.title == "The title"  # (the outline's spine is the talk's)

    # The outline is offered the dice's words for every slide but the title slide, and writes the spine
    asked = model.requests[0].messages[0].content
    assert "slide_2: " in asked and "Its words: word 2, other 2, third 2" in asked
    assert "slide_1:" not in asked
    assert "- title: " in asked and f"- {outline.RUNNING_GAG}: " in asked
    # A slide's request has the talk's spine and running gag (the same for every slide), the plan, and the slide
    second = _slide_request(model, "slide_2")
    assert "The talk's title: The title" in second.system and "The talk's running gag: The running gag" in second.system
    assert second.system.startswith(prompt.SYSTEM_PROMPT)
    assert {request.system for request in model.requests[1:]} == {second.system}  # (cached once)
    written = second.messages[0].content
    assert "A word to riff on: riff of slide 2. The idea: idea of slide 2" in written
    assert "- slide_2 (this one): " in written and "word 2" not in written
    assert list(second.json_schema["properties"]) == ["slide_2"]
    # (and its slide says what it riffed on, in its notes)
    assert deck.slides[1].notes.startswith("Seed: riff of slide 2")


def test_the_presenter_s_name_never_reaches_a_slide_s_request(seeds):
    model = FakeModel()
    _talk(model, llm_level=ADVANCED)
    assert all("Ann Example" not in request.system + json.dumps(request.model_dump()) for request in model.requests)


def test_the_outline_asks_for_the_spine_and_a_word_and_an_idea_for_every_slide(seeds):
    model = FakeModel()
    _talk(model, llm_level=ADVANCED)
    schema = model.requests[0].json_schema
    assert list(schema["properties"]) == [prompt.SPINE, *(f"slide_{number}" for number in range(2, NUM_SLIDES + 1))]
    spine = schema["properties"][prompt.SPINE]["properties"]
    assert list(spine)[-1] == outline.RUNNING_GAG and {"unsafe_topic", "thesis", "title", "presenter_job"} <= set(spine)
    assert list(schema["properties"]["slide_2"]["properties"]) == ["riff", "idea"]
    assert model.requests[0].system == outline.OUTLINE_SYSTEM_PROMPT


def test_slides_the_outline_leaves_out_keep_the_dice_s_words(seeds):
    def forget(answer):
        if prompt.SPINE in answer and "slide_3" in answer and "riff" in answer["slide_3"]:
            answer["slide_3"] = {"riff": "", "idea": "an idea without a word"}

    model = FakeModel(change=forget)
    deck = _talk(model, llm_level=ADVANCED)
    assert "A word to riff on: word 3\n" in _slide_request(model, "slide_3").messages[0].content
    assert "riff of slide 2" in _slide_request(model, "slide_2").messages[0].content
    assert all(_planned(deck))


class _Failing(FakeModel):
    """Fails, declines, or cuts off the outline (or flags its topic), and writes the rest."""

    def __init__(self, how="fail", **options):
        super().__init__(**options)
        self.how = how

    def complete(self, request):
        if request.purpose == outline.PURPOSE:
            self.requests.append(request)
            if self.how == "refuse":
                return TextResponse(text="", finish="refused", model=self.id)
            if self.how == "unsafe":
                answer = json.loads(super().complete(request).text.strip("`").removeprefix("json"))
                self.requests.pop()
                answer[prompt.SPINE]["unsafe_topic"] = True
                return TextResponse(text=json.dumps(answer), model=self.id)
            if self.how == "cut":  # (after the spine and the second slide's idea)
                answer = super().complete(request).text
                self.requests.pop()
                cut = answer.index('"slide_3"')
                return TextResponse(text=answer[:cut], finish="truncated", model=self.id)
            raise ProviderError("the outline failed")
        return super().complete(request)


@pytest.mark.parametrize("how", ["fail", "refuse", "unsafe"])
def test_a_talk_whose_outline_brings_no_spine_is_a_basic_one(seeds, how):
    model = _Failing(how)
    deck = _talk(model, llm_level=ADVANCED)
    assert _purposes(model) == [outline.PURPOSE, "talk plan"]
    assert deck.llm_level == BASIC and all(_planned(deck))
    assert "A word to riff on: word 2" in model.requests[1].messages[0].content


def test_an_outline_cut_off_still_writes_every_slide(seeds):
    model = _Failing("cut")
    deck = _talk(model, llm_level=ADVANCED)
    assert sorted(_purposes(model)[1:]) == [outline.SLIDE_PURPOSE] * PLANNED
    assert all(_planned(deck)) and deck.llm_level == ADVANCED
    assert "The idea: idea of slide 2" in _slide_request(model, "slide_2").messages[0].content
    assert "A word to riff on: word 3\n" in _slide_request(model, "slide_3").messages[0].content  # (the dice's)


class _DeclinesLate(FakeModel):
    """Writes the whole outline, a title of its own in its spine, and then declines (as Claude can, halfway)."""

    def stream(self, request, on_text):
        response = super().stream(request, on_text)
        if request.purpose == outline.PURPOSE:
            return response.model_copy(update={"finish": "refused"})
        return response

    def complete(self, request):
        response = super().complete(request)
        if request.purpose == outline.PURPOSE:
            return response.model_copy(update={"text": response.text.replace('"The title"', '"A declined title"')})
        return response


def test_what_a_declined_outline_wrote_is_not_used(seeds):
    model = _DeclinesLate()
    deck = _talk(model, llm_level=ADVANCED)
    # (its slides' requests that had started are dropped, and the talk is a Basic one, from the dice's words)
    assert "talk plan" in _purposes(model) and deck.llm_level == BASIC
    assert deck.title == "The title" and all(_planned(deck))
    basic = next(request for request in model.requests if request.purpose == "talk plan")
    assert "A word to riff on: word 2" in basic.messages[0].content and "The idea:" not in basic.messages[0].content


def test_a_talk_claude_declines_to_plan_is_written_as_a_basic_one_and_classic_if_declined_again(schema):
    import anthropic
    import httpx2

    from talkgenerator import llm
    from tests.test_llm_talks import _claude_api_that_declines_halfway

    transport = httpx2.MockTransport(_claude_api_that_declines_halfway)
    client = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=transport)
    )
    deck = _talk(llm.ClaudeProvider(client=client))  # (Claude: Advanced, unless a talk asks otherwise)
    assert deck.title.startswith("A classic title") and not any(_planned(deck))
    assert deck.usage.requests >= 2  # (the outline, a slide it had planned by then, the Basic talk's, declined too)


class _OneSlideFails(FakeModel):
    def complete(self, request):
        if request.purpose == outline.SLIDE_PURPOSE and "slide_4" in request.json_schema["properties"]:
            self.requests.append(request)
            raise ProviderError("this slide failed")
        return super().complete(request)


def test_a_slide_whose_request_fails_is_classic_and_the_others_planned(seeds):
    deck = _talk(_OneSlideFails(), llm_level=ADVANCED)
    planned = _planned(deck)
    assert not planned[3] and all(planned[:3]) and all(planned[4:])


class _SlowSecondSlide(FakeModel):
    """Writes the second slide last of all: the slides come in out of order."""

    def __init__(self):
        super().__init__()
        self.others_done = threading.Event()
        self.written: list[str] = []

    def complete(self, request):
        keys = list(request.json_schema["properties"]) if request.purpose == outline.SLIDE_PURPOSE else []
        if keys == ["slide_2"]:
            self.others_done.wait(5)
        response = super().complete(request)
        if keys:
            self.written.append(keys[0])
            if len(self.written) == PLANNED - 1:
                self.others_done.set()
        return response


def test_slides_that_come_in_out_of_order_are_settled_in_order(seeds):
    model = _SlowSecondSlide()
    deck = _talk(model, llm_level=ADVANCED)
    assert model.written[-1] == "slide_2" and all(_planned(deck))
    assert _talk(FakeModel(), llm_level=ADVANCED).to_json() == deck.to_json()  # (the same talk, whatever the order)


def test_an_advanced_talk_takes_about_as_long_as_its_slowest_slide(seeds):
    class Slow(FakeModel):
        def complete(self, request):
            time.sleep(0.4)
            return super().complete(request)

    start = time.monotonic()
    _talk(Slow(), llm_level=ADVANCED)
    # (the outline, then its six slides at once rather than one after another: 2 times 0.4 seconds, not 7)
    assert time.monotonic() - start < 0.4 * (1 + PLANNED) + 1.5


def test_an_outline_s_texts_are_kept_short():
    idea = outline.read_idea({"riff": "a riff " * 20, "idea": "an idea " * 60})
    assert idea is not None
    assert len(idea.riff) <= outline.RIFF_LENGTH and len(idea.idea) <= outline.IDEA_LENGTH
    assert not idea.idea.endswith(" ")
    assert outline.read_idea({"riff": "", "idea": "x"}) is None and outline.read_idea("not a slide") is None


def test_a_budget_without_room_for_a_request_per_slide_makes_a_basic_talk(seeds):
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_requests=PLANNED))
    assert _purposes(model) == ["talk plan"]
    assert deck.llm_level == BASIC and all(_planned(deck))
    model = FakeModel()
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_requests=1 + PLANNED))
    assert deck.llm_level == ADVANCED


def test_a_budget_of_no_money_skips_a_model_of_unknown_price(seeds):
    model = FakeModel()  # (fake:model has no price: a talk at $0 doesn't ask it at all)
    deck = _talk(model, llm_level=ADVANCED, budget=Budget(max_cost_usd=0.0))
    assert model.requests == [] and deck.llm_level is None


def test_the_level_comes_from_the_settings(seeds, monkeypatch):
    monkeypatch.setenv("TALKGENERATOR_LLM_LEVEL", "Advanced")
    model = FakeModel()
    assert _talk(model).llm_level == ADVANCED and len(model.requests) == 1 + PLANNED
    model = FakeModel()
    assert _talk(model, llm_level="basic").llm_level == BASIC and len(model.requests) == 1


@pytest.mark.parametrize(
    ("spec", "level"),
    [
        ("anthropic:claude-haiku-5-5", ADVANCED),
        ("openai:gpt-5-mini", ADVANCED),
        ("openrouter:x-ai/grok-4.7", ADVANCED),
        ("openrouter", BASIC),  # (the free router)
        ("openrouter:google/gemma-4-31b-it:free", BASIC),
        ("openrouter:x-ai/grok-4.7,google/gemma-4-31b-it:free", BASIC),  # (it can fall back to a free one)
    ],
)
def test_a_model_of_your_own_that_costs_writes_advanced_talks_unless_asked_otherwise(spec, level, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    model = providers.provider_from_spec(spec)
    assert outline.default_level(model) == level and outline.level(None, model) == level
    assert outline.level("basic", model) == BASIC
    assert outline.default_level(FakeModel()) == BASIC and outline.default_level(None) == BASIC


def test_your_chatgpt_plan_writes_advanced_talks():
    class ChatGPT(FakeModel):
        id = "chatgpt:gpt-5.5"

    assert outline.default_level(ChatGPT()) == ADVANCED


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
    assert _purposes(model)[0] == outline.PURPOSE and len(model.requests) == 1 + PLANNED


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


# A REAL QUOTE'S THEME: the model writes it, and talkgenerator finds a real quote about it


@pytest.fixture
def quotes(seeds, monkeypatch):
    """The fake schema, with a slide of a real quote that a classic source finds (for themes it knows), which every
    slide would rather be; the searches it got."""
    from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
    from talkgenerator.plan.kinds import Recipe
    from talkgenerator.schema.presentation_schema import PresentationSchema
    from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
    from talkgenerator.util.generator_util import NoneGenerator, StaticGenerator
    from tests.test_llm_talks import _photo, _photos

    searched: list[str] = []

    def real_quotes(context):
        searched.append(context["seed"])
        return f"A real quote on {context['seed']}" if "text query" in context["seed"] else None

    quote = SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(NoneGenerator(), StaticGenerator("A quote"), _photo("q")),
        weight_function=ConstantWeightFunction(1000),
        allowed_repeated_elements=10,
        name="Fake quote",
        llm=Recipe("statement", images=(_photos,), texts_from={"text": real_quotes}),
    )
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_Seeds,
        title_generator=lambda context: "A classic title",
        slide_generators=[*seeds.slide_generators, quote],
        max_allowed_tags={"title": 1, "three_columns": 1},
    )
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return searched


def _texts(deck):
    return [element.text for slide in deck.slides for element in slide.elements if element.kind == "text"]


@pytest.mark.parametrize("level", [BASIC, ADVANCED])
def test_a_real_quote_is_found_for_the_theme_the_model_writes(quotes, level):
    model = FakeModel()
    deck = _talk(model, llm_level=level)
    assert "A real quote on text query of slide 2" in _texts(deck)
    assert quotes and all(search.startswith("text query of slide") for search in quotes)  # (the model's themes)
    asking = model.requests[-1] if level == BASIC else _slide_request(model, "slide_2")
    assert f"- text_query: {prompt.FOUND_QUERY}" in asking.messages[0].content
    assert "text_query" in json.dumps(asking.json_schema)


def test_a_theme_that_finds_no_quote_falls_back_on_the_concept(quotes):
    def unknown(answer):
        for key, value in answer.items():
            if key.startswith("slide_") and isinstance(value, dict) and "text_query" in value:
                value["text_query"] = "nothing known"

    deck = _talk(FakeModel(change=unknown))
    themes = [search for search in quotes if search == "nothing known"]
    concepts = [search for search in quotes if search.startswith("concept of slide")]
    assert themes and len(concepts) == len(themes) == len(quotes) // 2  # (every theme, and then its slide's concept)
    assert "concept of slide 2" in concepts
    assert not _planned(deck)[1]  # (neither finds one: the slide is classic)
