"""Offline tests of talks a language model writes: a fake model, a fake schema with recipes, fake image sources.

The model writes what goes on the slides Python picked; slides it gets wrong, whose images can't be found, or that it
doesn't write at all, are classic. The presenter's name never reaches the model, and the same seed (with the same
answers) gives the same talk, in parallel or one by one.
"""

import io
import json
import logging
import re

import anthropic
import httpx2
import openai
import pytest
from PIL import Image
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator import generator, llm
from talkgenerator.checks import benchmark
from talkgenerator.checks.deck import check_deck, leftovers_in, without_key_references
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.llm import providers
from talkgenerator.llm.base import Capabilities, TextProvider, TextResponse
from talkgenerator.models.deck import Deck
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe, TextField
from talkgenerator.plan.realize import clean_text
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.render import charts
from talkgenerator.schema import slide_schemas
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util import image_util, random_util
from talkgenerator.util.generator_util import NoneGenerator, StaticGenerator

NUM_SLIDES = 7


def _jpeg():
    output = io.BytesIO()
    Image.new("RGB", (400, 300), (30, 120, 200)).save(output, "JPEG")
    return output.getvalue()


@pytest.fixture(autouse=True)
def images(monkeypatch):
    """Every image at example.com exists; local files load as usual."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: jpeg if url.startswith("https://example.com/") else load(url)
    )


def _photos(context, slot=""):
    query = context["seed"]
    if "unfindable" in query:
        return None
    slug = re.sub(r"\W+", "-", query)
    return ImageData(f"https://example.com/{slug}{slot}.jpg", source="Fake photos")


def _photo(slot):
    """A classic slot's images: different for every slot and slide (yet the same for the same seed), as the classic
    slides search the same word for all of them."""
    return lambda context: _photos(context, f"-{slot}-{random_util.randint(0, 10**9)}")


def _classic_chart(context):
    data = ChartData()
    data.categories = ["Yes", "No"]
    data.add_series("", [0.5, 0.5])
    return "A classic chart", XL_CHART_TYPE.PIE, data, charts.set_pie_properties


def fake_schema():
    def generator_(kind, weight, classic, tags=(), **recipe):
        return SlideGeneratorData(
            classic,
            weight_function=weight,
            allowed_repeated_elements=10,
            tags=[kind, *tags],
            name=f"Fake {kind}",
            llm=Recipe(kind, **recipe),
        )

    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "A classic title about " + context["seed"],
        slide_generators=[
            generator_(
                "title",
                PeakedWeight((0,), 100000, 0),
                slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
            ),
            generator_(
                "two_columns",
                ConstantWeightFunction(3),
                slide_generator_types.TwoColumnImageSlideGenerator.of(
                    StaticGenerator("Classic captions"),
                    StaticGenerator("Before"),
                    _photo("left"),
                    StaticGenerator("After"),
                    _photo("right"),
                ),
                images=(_photos, _photos),
                brief="Two images that contrast",
            ),
            generator_(
                "statement",
                ConstantWeightFunction(2),
                slide_generator_types.LarqeQuoteSlideGenerator.of(
                    NoneGenerator(), StaticGenerator("Classic words"), _photo("background")
                ),
                images=(_photos,),
            ),
            generator_(
                "chart_yes_no", ConstantWeightFunction(1), slide_generator_types.ChartSlideGenerator(_classic_chart)
            ),
            # Never picked (weight 0): the picture a slide of a talk in another language becomes when it fails
            generator_(
                "full_image",
                ConstantWeightFunction(0),
                slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), _photo("full")),
                images=(_photos,),
                tags=["neutral"],
            ),
            generator_(
                "three_columns",
                PeakedWeight((-1,), 10000, 0),
                slide_generator_types.ThreeColumnImageSlideGenerator.of(
                    StaticGenerator("Classic conclusions"),
                    StaticGenerator("One"),
                    _photo("one"),
                    StaticGenerator("Two"),
                    _photo("two"),
                    StaticGenerator("Three"),
                    _photo("three"),
                ),
                images=(_photos, _photos, _photos),
                brief="The conclusions",
            ),
        ],
        max_allowed_tags={"title": 1, "three_columns": 1},
    )


def _answer(schema):
    """Fill in every property of the response schema: the spine's as "The title" and so on (the only boolean,
    unsafe_topic, with false), and every slide's as "title of slide 2" (not of slide_2: a slide's key in the answer
    is a leftover on a slide)."""
    answer = {}
    for key, value in schema["properties"].items():
        if value["type"] == "boolean":
            answer[key] = False
        elif value["type"] == "string":
            answer[key] = f"The {key.replace('_', ' ')}"
        elif key == prompt.SPINE:
            answer[key] = _answer(value)
        else:
            slide = key.replace("_", " ")
            answer[key] = {
                name: "Yes | No | Only on Tuesdays" if name == "categories" else f"{name.replace('_', ' ')} of {slide}"
                for name in value["properties"]
            }
    return answer


class FakeModel(TextProvider):
    """Answers any talk request, in pieces of seven characters; `change` can edit its answer first."""

    id = "fake:model"
    capabilities = Capabilities(structured_output=True, streaming=True)

    def __init__(self, change=None, fail=None):
        self.requests = []
        self.change = change
        self.fail = fail

    def complete(self, request):
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        answer = _answer(request.json_schema)
        if self.change is not None:
            self.change(answer)
        text = "```json\n" + json.dumps(answer) + "\n```"
        return TextResponse(text=text, model=self.id, input_tokens=1000, output_tokens=300)

    def stream(self, request, on_text):
        response = self.complete(request)
        for start in range(0, len(response.text), 7):
            on_text(response.text[start : start + 7])
        return response


@pytest.fixture
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _talk(model, int_seed=1, parallel=True, **options):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=NUM_SLIDES,
        topic="cats",
        presenter="Ann Example",
        int_seed=int_seed,
        parallel=parallel,
        save_ppt=False,
        llm=model,
        **options,
    )
    return slide_deck.to_deck()


def _planned(deck):
    """Which slides the language model wrote (the others are classic)."""
    return ["Planned:" in slide.notes for slide in deck.slides]


# TALKS


def test_a_language_model_writes_the_talk(schema):
    model = FakeModel()
    deck = _talk(model)

    assert len(model.requests) == 1
    assert deck.title == "The title"
    title, subtitle = (element.text for element in deck.slides[0].elements)
    assert title == "The title"
    assert subtitle.endswith("Ann Example, The presenter job")
    assert all(_planned(deck))
    assert check_deck(deck, NUM_SLIDES) == []
    assert (deck.usage.requests, deck.usage.input_tokens, deck.usage.output_tokens) == (1, 1000, 300)


def test_the_presenter_s_name_never_reaches_the_model(schema):
    model = FakeModel()
    _talk(model)
    request = model.requests[0]
    assert "Ann Example" not in request.system + json.dumps(request.model_dump())


def test_the_same_seed_gives_the_same_talk_in_parallel_or_not(schema):
    talk = _talk(FakeModel(), int_seed=3).to_json()
    assert _talk(FakeModel(), int_seed=3).to_json() == talk
    assert _talk(FakeModel(), int_seed=3, parallel=False).to_json() == talk
    assert _talk(FakeModel(), int_seed=4).to_json() != talk


def test_a_recorded_talk_can_be_made_again(schema, tmp_path):
    cassette = tmp_path / "talk.json"
    recorded = _talk(llm.ReplayProvider(cassette, record=FakeModel()), int_seed=5)
    replayed = _talk(llm.ReplayProvider(cassette), int_seed=5)
    assert replayed.slides == recorded.slides


def test_slides_the_model_gets_wrong_are_classic(schema):
    def spoil(answer):
        slides = [key for key in answer if key.startswith("slide_")]
        first, second = slides[0], slides[1]
        answer[first] = {key: "{seed}" for key in answer[first]}  # template code
        answer[second] = "not a slide"

    deck = _talk(FakeModel(change=spoil))
    planned = _planned(deck)
    assert planned[0] and not planned[1] and not planned[2] and all(planned[3:])
    assert check_deck(deck, NUM_SLIDES) == []


def test_slides_whose_images_cant_be_found_are_classic(schema):
    def unfindable(answer):
        for key, value in answer.items():
            if key.startswith("slide_") and isinstance(value, dict):
                value["concept"] = "the unfindable"
                for name in value:
                    if name.endswith("_query"):
                        value[name] = "an unfindable image"

    deck = _talk(FakeModel(change=unfindable))
    # Only slides without images (the title and charts) kept what the model wrote; the others are classic
    planned_types = {slide.type for slide, planned in zip(deck.slides, _planned(deck), strict=True) if planned}
    assert planned_types <= {"title", "chart"}
    assert not all(_planned(deck))
    assert check_deck(deck, NUM_SLIDES) == []


def _texts_of(slide):
    return {element.role: element.text for element in slide.elements if element.kind == "text"}


def test_a_callback_loses_the_brackets_that_name_its_slide_by_its_key(schema):
    # A free model's conclusion read "Huddling scales trust (from slide_03)": the slide's key in its answer
    def cite(answer):
        first, second, *_, last = (key for key in answer if key.startswith("slide_"))
        answer[last]["caption_1"] = f"Huddling scales trust (from {first})"
        answer[last]["caption_2"] = f"Waddling [see {first} and {second}] wins"

    deck = _talk(FakeModel(change=cite))
    conclusions = deck.slides[-1]
    assert conclusions.type == "three_column_image" and all(_planned(deck))
    assert _texts_of(conclusions)["caption_1"] == "Huddling scales trust"
    assert _texts_of(conclusions)["caption_2"] == "Waddling wins"
    assert "slide_" not in conclusions.notes  # (the texts it planned, as they went on the slide)
    assert check_deck(deck, NUM_SLIDES) == []


def test_a_slide_with_a_key_of_the_answer_elsewhere_in_a_text_is_classic(schema):
    def cite(answer):
        first, *_, last = (key for key in answer if key.startswith("slide_"))
        answer[last]["caption_1"] = f"As {first} showed, huddling scales"

    deck = _talk(FakeModel(change=cite))
    assert deck.slides[-1].type == "three_column_image"
    assert _planned(deck) == [True] * (NUM_SLIDES - 1) + [False]
    assert _texts_of(deck.slides[-1])["caption_1"] == "One"  # (the classic conclusions')
    assert check_deck(deck, NUM_SLIDES) == []


def test_a_model_that_fails_makes_a_classic_talk(schema):
    deck = _talk(FakeModel(fail=llm.RateLimited("free quota used up")))
    assert deck.title.startswith("A classic title")
    assert not any(_planned(deck))
    assert len(deck.slides) == NUM_SLIDES
    assert (deck.usage.requests, deck.usage.failed_requests) == (1, 1)


def test_a_model_that_crashes_makes_a_classic_talk(schema):
    deck = _talk(FakeModel(fail=RuntimeError("a bug in a provider")))
    assert deck.title.startswith("A classic title")
    assert not any(_planned(deck))
    assert len(deck.slides) == NUM_SLIDES


def test_a_topic_the_model_finds_unsafe_makes_a_classic_talk(schema):
    model = FakeModel(change=lambda answer: answer[prompt.SPINE].update(unsafe_topic=True))
    deck = _talk(model)
    assert deck.title.startswith("A classic title")
    assert not any(_planned(deck))
    assert len(model.requests) == 2  # it was asked once more


def test_a_model_that_wrongly_finds_a_topic_unsafe_is_asked_once_more(schema):
    # Some of the free models get the flag wrong (one turned down "penguins"): the router may pick another one
    model = FakeModel(change=lambda answer: answer[prompt.SPINE].update(unsafe_topic=len(model.requests) == 1))
    deck = _talk(model)
    assert all(_planned(deck))
    first, second = (request.messages[0].content for request in model.requests)
    assert "Asked again" not in first and "Asked again: a model said this topic" in second


def test_a_topic_wrongly_found_unsafe_in_english_is_asked_again_as_unsafe(schema):
    # (a talk in another language whose first answer finds the topic unsafe, in English: the flag is what's wrong)
    model = FakeModel(change=lambda answer: answer[prompt.SPINE].update(unsafe_topic=len(model.requests) == 1))
    deck = _talk(model, language="sv")
    second = model.requests[1].messages[0].content
    assert "Asked again: a model said this topic" in second and "the last answer was in English" not in second
    assert len(model.requests) == 2 and all(_planned(deck))  # (the second answer is kept, whatever its language)


def test_without_a_language_model_the_talk_is_classic(schema):
    deck = _talk(None)
    assert not any(_planned(deck))
    assert deck.usage.requests == 0


def test_a_budget_can_keep_a_model_out(schema):
    deck = _talk(FakeModel(), budget=llm.Budget(max_requests=0))
    assert not any(_planned(deck))
    assert deck.usage.requests == 0


def test_the_language_and_a_given_title_reach_the_prompt(schema):
    model = FakeModel()
    deck = _talk(model, language="nl", title="Over katten")
    user_prompt = model.requests[0].messages[0].content
    assert "every slide in Dutch" in user_prompt
    assert "Title: Over katten" in user_prompt
    assert deck.title == "Over katten"


# TALKS IN OTHER LANGUAGES


def test_a_dutch_talk_has_dutch_words_of_its_own(schema):
    deck = _talk(FakeModel(), language="nl")
    assert deck.language == "nl"
    by = deck.slides[0].elements[1].text.split(" Ann Example")[0]
    assert by in languages.LANGUAGES["nl"].by
    chart = KINDS["chart_yes_no"].build({"question": "Ooit?", "funny_answer": "Soms"}, {}, languages.LANGUAGES["nl"])
    (element,) = [element for element in chart.to_deck_slide().elements if element.kind == "chart"]
    assert element.chart.categories == ("Ja", "Nee", "Soms")


def test_a_swedish_talk_has_swedish_words_of_its_own(schema):
    model = FakeModel()
    deck = _talk(model, language="sv")
    assert deck.language == "sv"
    assert "every slide in Swedish" in model.requests[0].messages[0].content
    by = deck.slides[0].elements[1].text.split(" Ann Example")[0]
    assert by in ("Av", "En presentation av", "Presenterad av")
    swedish = languages.language("sv")
    chart = KINDS["chart_yes_no"].build({"question": "Någonsin?", "funny_answer": "Ibland"}, {}, swedish)
    (element,) = [element for element in chart.to_deck_slide().elements if element.kind == "chart"]
    assert element.chart.categories == ("Ja", "Nej", "Ibland")


def test_texts_for_another_language_that_read_as_english_are_told():
    english = ["FikaFlow: The Fika-Based Productivity Engine", "Fika breaks are a problem that only an app can solve"]
    swedish = [
        "FikaFlow: Produktivitetsmotorn för fika",
        "Fika är den hemliga motorn som alla arbetsplatser har missat",
    ]
    assert languages.reads_as_english(english, "sv")
    assert not languages.reads_as_english(swedish, "sv")
    assert not languages.reads_as_english(english, "en")  # (never for English)
    assert not languages.reads_as_english(["Bitcoin", "CEO of the year"], "nl")  # (too few words to tell)


def test_a_talk_whose_answer_starts_in_english_is_asked_again(schema):
    # (a free model wrote a Swedish talk in English, 2026-11-08: the spine tells, before any slide is looked for)
    def in_swedish_the_second_time(answer):
        if len(model.requests) > 1:
            spine = answer[prompt.SPINE]
            spine.update(
                title="Katternas tid", thesis="Katter är motorn som alla har missat", presenter_job="Kattens röst"
            )

    model = FakeModel(change=in_swedish_the_second_time)
    deck = _talk(model, language="sv")
    first, second = (request.messages[0].content for request in model.requests)
    asked_again = "Asked again: the last answer was in English. Write the title, the thesis, the presenter's job and"
    assert asked_again not in first and asked_again in second
    assert "every slide in Swedish; only the image search queries are in English." in second
    assert deck.title == "Katternas tid"
    assert all(_planned(deck))
    assert deck.usage.requests == 2  # (the first answer, stopped once its spine was in, counts too)
    assert deck.usage.input_tokens == 1000  # (of the second: the first one's aren't known)


def test_a_second_answer_in_english_is_kept(schema):
    # (better the model's slides than slides that come out as pictures without text)
    model = FakeModel()
    deck = _talk(model, language="sv")
    assert len(model.requests) == 2
    assert deck.title == "The title"
    assert all(_planned(deck))


def test_every_text_of_a_talk_in_another_language_is_asked_for_in_it():
    # (a free model copied a hint's English examples into a German talk: "Outline", "Related work", "Method")
    planned = [
        prompt.PlannedSlide(
            2, "Fake", Recipe("agenda", hints={"title": "the slide's title, such as 'Outline'"}), "cat"
        ),
        prompt.PlannedSlide(3, "Fake", Recipe("quiz"), "cat"),
    ]
    request = prompt.talk_request(["cat"], planned, random_util.Rng(1), "de").messages[0].content
    # (and the example says it's English, D74: a free model still put "Live demo" on a Dutch keynote's slide)
    assert "- title: the slide's title, such as 'Outline' (in English: yours in German), in German (at most" in request
    assert "- answer: the letter of the right option (one of" in request  # (a choice of words isn't translated)
    schema = prompt.response_schema(planned, "de")["properties"]
    assert schema["slide_2"]["properties"]["title"]["description"].startswith(
        "the slide's title, such as 'Outline' (in English: yours in German), in German ("
    )
    assert "in German" in schema[prompt.SPINE]["properties"]["thesis"]["description"]
    english = prompt.talk_request(["cat"], planned, random_util.Rng(1)).messages[0].content
    assert "- title: the slide's title, such as 'Outline' (at most" in english
    assert "the thesis" not in english.splitlines()[1]  # (an English talk's request is as it was)


@pytest.mark.parametrize("language", ["nl", "sv"])
def test_a_slide_of_a_talk_in_another_language_that_doesnt_come_out_becomes_a_picture(schema, language):
    def spoil(answer):
        first = next(key for key in answer if key.startswith("slide_"))
        answer[first] = {key: "{seed}" for key in answer[first]}  # template code: it can't come out

    deck = _talk(FakeModel(change=spoil), language=language)
    spoiled = deck.slides[1]
    assert spoiled.type == "full_image"
    assert [element for element in spoiled.elements if element.kind == "text"] == []  # no English classic slide
    assert len(deck.slides) == NUM_SLIDES


def test_a_dutch_talk_gets_no_slides_that_find_english_texts(monkeypatch):
    fake = fake_schema()
    quote = SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(NoneGenerator(), StaticGenerator("A quote"), _photo("q")),
        weight_function=ConstantWeightFunction(1000),
        allowed_repeated_elements=10,
        name="Fake quote",
        llm=Recipe("statement", images=(_photos,), texts_from={"text": lambda context: "An English quote"}),
    )
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "A classic title",
        slide_generators=[*fake.slide_generators, quote],
        max_allowed_tags={"title": 1, "three_columns": 1},
    )
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)

    def texts(deck):
        return [element.text for slide in deck.slides for element in slide.elements if element.kind == "text"]

    assert "An English quote" in texts(_talk(FakeModel()))
    assert "An English quote" not in texts(_talk(FakeModel(), language="nl"))


def test_a_language_talkgenerator_doesnt_know_is_refused(schema):
    with pytest.raises(ValueError, match="doesn't know the language 'xx'"):
        _talk(FakeModel(), language="xx")


# THROUGH THE PROVIDERS' APIS (FAKED AT THE HTTP LEVEL)


def _event_stream(body):
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


class _OpenRouterApi:
    """OpenRouter's Chat Completions API, answering any talk request in pieces, as a free model would."""

    def __init__(self):
        self.bodies = []

    def __call__(self, request):
        self.bodies.append(request.content.decode())
        text = json.dumps(_answer(json.loads(request.content)["response_format"]["json_schema"]["schema"]))
        chunk = {"id": "gen-1", "object": "chat.completion.chunk", "created": 1, "model": "vendor/model:free"}
        pieces = [text[start : start + 7] for start in range(0, len(text), 7)]
        chunks = [{**chunk, "choices": [{"index": 0, "delta": {"content": piece}}]} for piece in pieces]
        usage = {"prompt_tokens": 2000, "completion_tokens": 900, "total_tokens": 2900, "cost": 0}
        chunks.append({**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage})
        return _event_stream("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n")


def test_a_talk_written_through_openrouter(schema):
    api = _OpenRouterApi()
    http_client = openai.DefaultHttpxClient(transport=httpx2.MockTransport(api))
    client = openai.OpenAI(api_key="test", base_url=llm.openrouter.API_URL, max_retries=0, http_client=http_client)
    deck = _talk(llm.OpenRouterProvider(client=client), budget=llm.Budget(max_cost_usd=0))

    assert all(_planned(deck))
    assert check_deck(deck, NUM_SLIDES) == []
    assert (deck.usage.requests, deck.usage.cost_usd, deck.usage.unpriced_requests) == (1, 0.0, 0)
    assert len(api.bodies) == 1 and "Ann Example" not in api.bodies[0]


def _claude_api_that_declines_halfway(request):
    text = json.dumps(_answer(json.loads(request.content)["output_config"]["format"]["schema"]))
    message = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 2000, "output_tokens": 1},
    }
    events = [
        {"type": "message_start", "message": message},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text[: len(text) // 2]}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "refusal"}, "usage": {"output_tokens": 400}},
        {"type": "message_stop"},
    ]
    return _event_stream("".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events))


def test_the_check_replays_what_the_model_answered(schema, monkeypatch):
    # A model that never answers the same twice: the second run of the check has to replay the first one's answer
    model = FakeModel()
    model.change = lambda answer: answer[prompt.SPINE].update(title=f"Take {len(model.requests)}")
    monkeypatch.setitem(providers._FACTORIES, "fake", lambda argument: model)
    report = benchmark.check_talk("cats", 1, schema="fake", slides=NUM_SLIDES, llm="fake")
    assert report.deterministic is True
    assert report.findings == []
    assert len(model.requests) == 1
    assert report.metrics["usage"]["requests"] == 1
    assert report.metrics["written_by_language_model"] == NUM_SLIDES


def test_the_check_says_when_the_model_wrote_nothing(schema, monkeypatch):
    model = FakeModel(change=lambda answer: answer[prompt.SPINE].update(unsafe_topic=True))
    monkeypatch.setitem(providers._FACTORIES, "fake", lambda argument: model)
    report = benchmark.check_talk("cats", 1, schema="fake", slides=NUM_SLIDES, llm="fake", determinism=False)
    assert [(finding.check, finding.severity) for finding in report.findings] == [("language model", "warning")]


def test_no_slide_shows_an_image_of_a_slide_before_it():
    # Conclusions may repeat many elements (they sum up), but not a picture
    from talkgenerator.schema import presentation_schema

    state = presentation_schema._DeckState()
    cat = ImageData("https://example.com/cat.jpg")
    presentation_schema._add_used(state, [cat, "Cats rule"])
    generous = SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(_classic_chart), allowed_repeated_elements=10
    )
    new_enough = presentation_schema.PresentationSchema._is_new_enough
    assert not new_enough((None, [ImageData("https://example.com/cat.jpg"), "Conclusions"]), generous, state)
    assert new_enough((None, [ImageData("https://example.com/dog.jpg"), "Cats rule"]), generous, state)


def test_a_talk_claude_declines_halfway_is_classic(schema):
    transport = httpx2.MockTransport(_claude_api_that_declines_halfway)
    client = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=anthropic.DefaultHttpxClient(transport=transport)
    )
    deck = _talk(llm.ClaudeProvider(client=client), llm_level="basic")  # (an Advanced one's: test_llm_levels)
    # What Claude wrote before it declined isn't used: not the title, nor the slides it got to
    assert deck.title.startswith("A classic title")
    assert not any(_planned(deck))
    assert len(deck.slides) == NUM_SLIDES
    assert deck.usage.requests == 1


def _slides_moved(into):
    """A change to the fake model's answer that moves its slides into another object: the spine's, or one of its own."""

    def change(answer):
        slides = {key: answer.pop(key) for key in list(answer) if key != prompt.SPINE}
        (answer[prompt.SPINE] if into == prompt.SPINE else answer.setdefault(into, {})).update(slides)

    return change


def test_slides_inside_the_spine_or_another_object_still_make_the_talk(schema):
    # (Claude Haiku, given the talk's schema as text when Anthropic found it too large a grammar, wrote every slide into
    # the spine's object, "about": the talk read none of them, and came out classic but for its title; 2026-11-08)
    whole = _planned(_talk(FakeModel()))
    for into in (prompt.SPINE, "slides"):
        deck = _talk(FakeModel(change=_slides_moved(into)))
        assert deck.title == "The title" and _planned(deck) == whole and all(whole), into


def test_an_answer_without_a_slide_to_read_says_what_it_brought(schema, caplog, monkeypatch):
    # (Before slides inside the spine counted, Claude Haiku's answer to one talk of 2026-11-08 came out classic but
    # for its title, without a word of why)
    monkeypatch.setattr(logging.getLogger("talkgenerator"), "propagate", True)  # (the command line turns it off)

    def listed(answer):
        answer["slides"] = [answer.pop(key) for key in list(answer) if key != prompt.SPINE]

    def texts(answer):
        for key in list(answer):
            if key != prompt.SPINE:
                answer[key] = "Some slide"

    for change, brought in ((listed, "slides (a list of {})"), (texts, "{} (a text)")):
        caplog.clear()
        model = FakeModel(change=change)
        with caplog.at_level("WARNING", logger="talkgenerator"):
            deck = _talk(model)
        assert deck.title == "The title" and not any(_planned(deck))  # (the spine is read, the slides are classic)
        keys = [key for key in model.requests[0].json_schema["properties"] if key != prompt.SPINE]
        warned = [
            record.getMessage() for record in caplog.records if "no slide that could be read" in record.getMessage()
        ]
        expected = brought.format(len(keys)) if change is listed else brought.format(keys[0])
        assert len(warned) == 1 and expected in warned[0] and "fake:model" in warned[0], warned
        assert f"{prompt.SPINE} (an object of " in warned[0] and "of slide 2" not in warned[0]  # (keys, never texts)
    caplog.clear()
    with caplog.at_level("WARNING", logger="talkgenerator"):
        _talk(FakeModel())
    assert not [record for record in caplog.records if "no slide that could be read" in record.getMessage()]


# THE REQUEST


def test_the_prompt_says_what_to_write_in_every_field(schema):
    # Not every model reads the descriptions in the schema: the prompt has them too
    model = FakeModel()
    _talk(model)
    request = model.requests[0]
    prompt_text = request.messages[0].content
    assert f"First its spine, as an object called {prompt.SPINE}:\n" in prompt_text
    for key, value in request.json_schema["properties"].items():
        if key != prompt.SPINE:
            assert f"\n{key}: " in prompt_text
        for name, field in value["properties"].items():
            if name != "concept":
                assert f"- {name}: {field['description']}" in prompt_text
    assert "A word to riff on: cats" in prompt_text


def test_the_prompt_asks_for_callbacks_by_what_a_slide_said():
    # Asked for "a lesson from the talk, calling back to an earlier slide", a free model wrote "Huddling scales trust
    # (from slide_03)"
    conclusions = slide_schemas.slide_generators.group("conclusion")
    for generator_ in conclusions:
        assert generator_.llm is not None
        callbacks = [hint for name, hint in generator_.llm.hints.items() if name.startswith("caption_")]
        assert callbacks and all("by what it said (not by its number or key)" in hint for hint in callbacks)
    planned = [prompt.PlannedSlide(2, conclusions[0].name, conclusions[0].llm, "cat")]
    request = prompt.talk_request(["cat"], planned, random_util.Rng(1))
    assert (
        "- caption_1: a lesson from the talk in six words at most, calling back to an earlier slide by what it said"
        in (request.messages[0].content)
    )
    assert "the keys of your answer (such as slide_03)" in request.system


def test_the_response_schema_is_strict_and_in_order():
    digits = len(str(len(slide_schemas.slide_generators) + 1))
    planned = [
        prompt.PlannedSlide(number, generator_.name, generator_.llm, "cat", digits=digits)
        for number, generator_ in enumerate(slide_schemas.slide_generators, 2)
        if generator_.llm is not None and generator_.llm.kind != "title"
    ]
    schema = prompt.response_schema(planned)

    def check(node):
        assert node["additionalProperties"] is False
        assert node["required"] == list(node["properties"])
        for value in node["properties"].values():
            if value["type"] == "object":
                check(value)

    check(schema)
    assert list(schema["properties"]) == [prompt.SPINE, *(slide.key for slide in planned)]
    spine = schema["properties"][prompt.SPINE]
    assert list(spine["properties"]) == ["unsafe_topic", "thesis", "title", "presenter_job"]
    # In alphabetical order too, in which some models write the answer: the spine first, and slide_02 before slide_10
    # (as many digits as the last slide's number has: three, now that there are over a hundred slide generators)
    assert planned[-1].number >= 10 and planned[0].key == f"slide_{planned[0].number:0{digits}d}"
    assert sorted(schema["properties"]) == list(schema["properties"])


def test_every_recipe_of_the_schemas_fits_its_kind():
    for generator_ in slide_schemas.slide_generators:
        recipe = generator_.llm
        assert recipe is not None, generator_.name
        kind = KINDS[recipe.kind]
        assert len(recipe.images) == len(kind.images), generator_.name
        # (its hints are for the kind's texts, and for its pictures' queries: what a picture to explain searches for)
        queries = {f"{slot}_query" for slot in kind.images}
        assert set(recipe.hints) <= {text.name for text in kind.texts} | queries, generator_.name
        # (their variants leave out fields the kind has, which may stay empty, or an image slot: a fun fact's photo)
        for variant in recipe.variants:
            assert variant.omit <= {text.name for text in kind.texts if text.optional} | set(kind.images), (
                generator_.name
            )


# READING THE ANSWER


def test_the_answer_is_read_property_by_property_while_it_comes_in():
    answer = {
        "title": 'A "quoted" title, with {braces} and [brackets]',
        "slide_2": {"caption_1": "a, b", "nested": [1, {"deep": "}"}]},
        "count": 3,
        "last": None,
    }
    text = "Here you go:\n```json\n" + json.dumps(answer) + "\n```"
    reader = ObjectReader()
    found = []
    for character in text:
        found.extend(reader.feed(character))
    assert found == list(answer.items())
    assert reader.done


def test_a_value_that_doesnt_parse_is_left_out():
    reader = ObjectReader()
    assert reader.feed('{"good": "yes", "bad": tru, "also good": 1}') == [("good", "yes"), ("also good", 1)]


def test_slide_texts_are_cleaned_up():
    field = TextField("caption", "a caption", 20)
    assert clean_text('  "Expectation"\n', field) == "Expectation"
    assert clean_text("A caption that is far too long to fit", field) == "A caption"  # not "A caption that is"
    assert clean_text("About {seed.plural}", field) is None
    assert clean_text("   ", field) is None
    assert clean_text(42, field) is None


def test_a_text_keeps_the_quote_marks_of_a_quote_in_it():
    # (a free model's "Watering it and calling it 'Steve'" lost its last mark, 2026-11-08)
    field = TextField("caption", "a caption", 80)
    assert clean_text("Watering it and calling it 'Steve'", field) == "Watering it and calling it 'Steve'"
    assert clean_text("Ignoring them | Calling them 'just decor'", field) == "Ignoring them | Calling them 'just decor'"
    assert clean_text("“Expectation”", field) == "Expectation"  # (quote marks around all of it go)
    assert clean_text("'It's fine'", field) == "It's fine"
    assert clean_text('"Hello," she said, "bye"', field) == '"Hello," she said, "bye"'
    assert clean_text("'A claim", field) == "A claim" == clean_text("A claim'", field)  # (stray ones go)


def test_a_text_thats_cut_ends_on_a_word_that_matters():
    caption = TextField("caption", "a caption", 40)
    # A little too long is fine: up to an eighth more (here 45 characters) stays whole
    assert clean_text("Cats were the true scholars of the abbey", caption) == "Cats were the true scholars of the abbey"
    assert clean_text("Cats were the true scholars of the Middle Ages", caption) == "Cats were the true scholars"
    assert (
        clean_text("The abbot was the first time traveler, obviously so", caption)
        == "The abbot was the first time traveler"
    )
    dutch = "De kat was de ware geleerde van de Middeleeuwen"
    assert clean_text(dutch, TextField("caption", "a caption", 35), "nl") == "De kat was de ware geleerde"
    assert clean_text("Supercalifragilisticexpialidocious", TextField("word", "a word", 10)) == "Supercalif"


def test_a_slide_s_key_in_the_answer_never_goes_on_a_slide():
    caption = TextField("caption", "a caption", 40)
    # Brackets that name a slide by its key go; what they were in stays
    assert clean_text("Huddling scales trust (from slide_03)", caption) == "Huddling scales trust"
    assert clean_text("Huddling (see slide_3 and slide_10) scales", caption) == "Huddling scales"
    assert clean_text("Trust [slide_3], always.", caption) == "Trust, always."
    assert clean_text("Waddling wins (callback: slide_04, the ice)", caption) == "Waddling wins"
    # A key anywhere else is a leftover, as template code is: the slide is classic
    assert clean_text("As slide_03 showed, we huddle", caption) is None
    assert clean_text("(Slide_03)", caption) is None
    assert leftovers_in("As slide_03 showed") == ["a slide's key in the language model's answer: 'slide_03'"]
    # A slide's number, written out, is no key
    assert clean_text("Back to slide 3", caption) == "Back to slide 3"
    # Whatever the number of digits the answer's keys have
    for number, digits in ((2, 1), (3, 2), (10, 2)):
        key = prompt.PlannedSlide(number, "Fake", Recipe("chart_yes_no"), "cat", digits=digits).key
        assert leftovers_in(f"As {key} showed") and without_key_references(f"Trust (from {key})") == "Trust"


def test_the_spine_is_in_the_talks_language():
    planned = [prompt.PlannedSlide(2, "Fake", Recipe("chart_yes_no"), "cat")]
    spine = prompt.response_schema(planned, "nl")["properties"][prompt.SPINE]["properties"]
    assert "in Dutch" in spine["presenter_job"]["description"]
    assert "in Dutch" in spine["title"]["description"]
    request = prompt.talk_request(["cat"], planned, random_util.Rng(1), "nl")
    assert "- presenter_job: the presenter's grand, made-up job, such as" in request.messages[0].content
    assert "in Dutch (at most 50 characters)" in request.messages[0].content


def test_a_deck_from_an_llm_talk_renders(schema):
    from talkgenerator.render.powerpoint import render_pptx

    deck = Deck.from_json(_talk(FakeModel()).to_json())
    assert len(render_pptx(deck).slides) == NUM_SLIDES
