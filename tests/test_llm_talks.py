"""Offline tests of talks a language model writes: a fake model, a fake schema with recipes, fake image sources.

The model writes what goes on the slides Python picked; slides it gets wrong, whose images can't be found, or that it
doesn't write at all, are classic. The presenter's name never reaches the model, and the same seed (with the same
answers) gives the same talk, in parallel or one by one.
"""

import io
import json
import re

import pytest
from PIL import Image
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator import generator, llm
from talkgenerator.checks.deck import check_deck
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.llm.base import Capabilities, TextProvider, TextResponse
from talkgenerator.models.deck import Deck
from talkgenerator.plan import prompt
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
    def generator_(kind, weight, classic, **recipe):
        return SlideGeneratorData(
            classic,
            weight_function=weight,
            allowed_repeated_elements=10,
            tags=[kind],
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
    """Fill in every property of the response schema."""
    answer = {}
    for key, value in schema["properties"].items():
        if value["type"] == "boolean":
            answer[key] = True
        elif value["type"] == "string":
            answer[key] = f"The {key.replace('_', ' ')}"
        else:
            answer[key] = {
                name: "Yes | No | Only on Tuesdays" if name == "categories" else f"{name.replace('_', ' ')} of {key}"
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
    _, slide_deck, _ = generator.generate_presentation(
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
    deck = _talk(FakeModel(change=lambda answer: answer.update(safe_topic=False)))
    assert deck.title.startswith("A classic title")
    assert not any(_planned(deck))


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
    assert "write the slides in Dutch" in user_prompt
    assert "Title: Over katten" in user_prompt
    assert deck.title == "Over katten"


# THE REQUEST


def test_the_response_schema_is_strict_and_in_order():
    planned = [
        prompt.PlannedSlide(number, generator_.name, generator_.llm, "cat")
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
    assert list(schema["properties"])[:4] == ["safe_topic", "thesis", "title", "presenter_job"]
    assert list(schema["properties"])[4:] == [slide.key for slide in planned]


def test_every_recipe_of_the_schemas_fits_its_kind():
    for generator_ in slide_schemas.slide_generators:
        recipe = generator_.llm
        assert recipe is not None, generator_.name
        kind = KINDS[recipe.kind]
        assert len(recipe.images) == len(kind.images), generator_.name
        assert set(recipe.hints) <= {text.name for text in kind.texts}, generator_.name


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
    assert clean_text("A caption that is far too long to fit", field) == "A caption that is"
    assert clean_text("About {seed.plural}", field) is None
    assert clean_text("   ", field) is None
    assert clean_text(42, field) is None


def test_a_deck_from_an_llm_talk_renders(schema):
    from talkgenerator.render.powerpoint import render_pptx

    deck = Deck.from_json(_talk(FakeModel()).to_json())
    assert len(render_pptx(deck).slides) == NUM_SLIDES
