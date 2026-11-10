"""Offline tests of talks with less text and more surprise (docs/v5-plan.md, D73: the user's feedback of 2026-11-10).

Charts and diagrams try a picture first, now and then, in their place (a real chart from the internet for a chart, a
weird picture for a diagram), under their title: a slide is that picture when one is found (in its time, in a talk with
a time limit per slide), and else its text version, which stands in for it until its picture comes. Planned and classic
slides alike; DISABLE_PICTURE_FIRST (which offline tests have) switches it off.

The talks are made with test_slide_time_limit's small fake schemas, fake model and fake image finder.
"""

import dataclasses
import threading
import types

import pytest

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight
from talkgenerator.models.events import SlideUpdated
from talkgenerator.plan import kinds, prompt
from talkgenerator.plan.kinds import KINDS, PICTURE, Recipe
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.util import random_util
from tests.test_llm_talks import FakeModel
from tests.test_slide_time_limit import (
    SECONDS,
    _chart,
    _generator,
    _pictures,
    _schema,
    _texts,
    _timed,
    _title,
    _use,
)
from tests.test_slide_time_limit import held as held  # (fixtures)
from tests.test_slide_time_limit import no_late_wait as no_late_wait
from tests.test_slide_time_limit import photos as photos
from tests.test_streaming import images as images


@pytest.fixture
def pictures_first(monkeypatch):
    """Charts and diagrams that try a picture first (which offline tests don't), every one of them: the dice of a trend
    chart's and a Venn diagram's say yes every time."""
    monkeypatch.delenv("DISABLE_PICTURE_FIRST", raising=False)
    for kind in ("chart_trend", "venn"):
        first = dataclasses.replace(KINDS[kind].picture_first, odds=1.0)
        monkeypatch.setitem(KINDS, kind, dataclasses.replace(KINDS[kind], picture_first=first))


# WHICH SLIDES TRY A PICTURE FIRST


def test_about_half_of_the_charts_and_diagrams_try_a_picture_first(monkeypatch):
    monkeypatch.delenv("DISABLE_PICTURE_FIRST", raising=False)
    pictured = [kind for kind, made in KINDS.items() if made.picture_first is not None]
    assert {"chart_trend", "chart_bars", "chart_yes_no", "venn", "matrix", "pyramid", "process", "timeline"} <= set(
        pictured
    )
    assert not {"big_number", "kpi", "quiz", "reviews", "image", "two_columns"} & set(pictured)
    tried = [Recipe("chart_trend").varied(random_util.Rng(seed)).picture_first for seed in range(400)]
    assert 0.42 < sum(tried) / len(tried) < 0.58
    assert not any(Recipe("quiz").varied(random_util.Rng(seed)).picture_first for seed in range(50))
    # (from a stream of its own: the variant's draw is as it was)
    for seed in range(20):
        varied = Recipe("chart_trend").varied(random_util.Rng(seed))
        assert varied.omit == Recipe("chart_trend")._varied(random_util.Rng(seed), frozenset()).omit
    monkeypatch.setenv("DISABLE_PICTURE_FIRST", "1")
    assert not any(Recipe("chart_trend").varied(random_util.Rng(seed)).picture_first for seed in range(50))


def test_a_slide_that_tries_a_picture_first_asks_the_model_for_its_query(pictures_first):
    recipe = Recipe("chart_trend").varied(random_util.Rng(1))
    assert recipe.picture_first and PICTURE in recipe.image_queries()
    planned = prompt.PlannedSlide(2, "Trend Chart", recipe, "naps")
    lines = prompt.slide_lines(planned)
    assert any(line.startswith("- picture_query: an image search query for a real chart") for line in lines)
    assert "may show a picture under its title in its place" in lines[0]
    assert "picture_query" in prompt.slide_schema(recipe)["properties"]
    plain = Recipe("quiz").varied(random_util.Rng(1))
    assert PICTURE not in plain.image_queries() and "picture_query" not in prompt.slide_schema(plain)["properties"]


def test_a_charts_picture_goes_under_its_title_and_a_yes_or_no_charts_under_its_question(pictures_first):
    plan = kinds.SlidePlan(
        kind="chart_trend",
        recipe="Trend Chart",
        concept="naps",
        texts={"title": "Naps make you rich"},
        images={PICTURE: "napping chart"},
    )
    picture, recipe = kinds.picture_version(plan, Recipe("chart_trend", picture_first=True))
    assert (picture.kind, picture.texts, picture.images) == (
        "full_image",
        {"title": "Naps make you rich"},
        {"image": "napping chart"},
    )
    assert recipe.slots()[0][1].aesthetic == "bad-charts"
    asked = kinds.SlidePlan(kind="chart_yes_no", recipe="Yes/No", concept="naps", texts={"question": "Nap today?"})
    picture, recipe = kinds.picture_version(asked, Recipe("chart_yes_no", picture_first=True))
    assert picture.texts == {"title": "Nap today?"} and picture.images == {"image": "naps"}  # (the concept: no query)
    assert kinds.picture_version(plan, Recipe("chart_trend")) is None  # (a slide that doesn't try one)


# PLANNED SLIDES


@pytest.fixture
def charted(monkeypatch, photos, pictures_first):
    """A talk of 4 slides a model writes: a title slide, two trend charts (2 and 4) and a Venn diagram (3), each of
    which tries a picture first; its classic slides are charts."""
    slides_ = [
        _title(),
        _generator("Trend", PeakedWeight((1, 3), 100000, 0), _chart("Classic"), "chart_trend"),
        _generator("Venn", PeakedWeight((2,), 100000, 0), _chart("Classic"), "venn"),
    ]
    return _use(monkeypatch, _schema(slides_, {"title": 1, "trend": 2, "venn": 1}))


def test_a_planned_chart_that_finds_its_picture_is_that_picture_under_its_title(charted, photos):
    events, _ = _timed(4, llm=FakeModel())
    deck = events[-1].deck
    second = deck.slides[1]
    assert second.type == "full_image" and _texts(second) == ["title of slide 2"]
    assert _pictures(second) == ["https://example.com/picture-query-of-slide-2-0.jpg"]
    assert "Picture first" in second.notes
    assert deck.slides[2].type == "full_image" and "picture query of slide 3" in photos.asked  # (the diagram's too)


def test_a_planned_chart_without_a_picture_is_its_text_version(charted, photos):
    photos.none.add("picture query")
    events, _ = _timed(4, llm=FakeModel())
    second = events[-1].deck.slides[1]
    assert second.type == "chart" and "title of slide 2" in _texts(second)
    assert events[-1].deck.slides[2].type == "diagram"


def test_a_planned_charts_picture_out_of_time_stands_in_as_its_text_version_and_comes_late(charted, photos, held):
    photos.slow.add("picture query of slide 2")
    threading.Timer(1.5, held.set).start()  # (the picture comes once the other slides are in)
    events, _ = _timed(4, llm=FakeModel(), slide_seconds=SECONDS)
    ready = [event for event in events if type(event).__name__ == "SlideReady"]
    assert ready[1].slide.type == "chart" and "title of slide 2" in _texts(ready[1].slide)
    assert "its text version, while its picture is looked for" in ready[1].slide.notes
    (late,) = [event for event in events if isinstance(event, SlideUpdated) and event.late]
    assert late.index == 1 and late.slide.type == "full_image" and _texts(late.slide) == ["title of slide 2"]
    assert events[-1].deck.slides[1].type == "full_image"


def test_a_late_text_version_leaves_the_one_that_stands_in(charted, photos, held):
    photos.slow.add("picture query of slide 2")
    photos.none.add("picture query of slide 2")  # (slow, and then nothing: the text version again)
    threading.Timer(1.0, held.set).start()
    events, _ = _timed(4, llm=FakeModel(), slide_seconds=SECONDS)
    assert not [event for event in events if isinstance(event, SlideUpdated) and event.late]
    assert events[-1].deck.slides[1].type == "chart"


# CLASSIC SLIDES


def _found(context):
    return ImageData(
        f"https://example.com/chart-of-{context['seed']}.jpg",
        source="Fake charts",
        declared_size=(1600, 900),
        license_class="public-domain",
    )


def test_a_classic_chart_tries_a_picture_first_under_its_title(monkeypatch, images):
    monkeypatch.delenv("DISABLE_PICTURE_FIRST", raising=False)
    context, used = {"seed": "cats"}, (set(), 10)
    sometimes = slide_generator_types.PictureFirstSlideGenerator(_chart("Chart"), _found, 1.0)
    with random_util.use(random_util.Rng(1)):
        slide, generated = sometimes.generate_slide(context, used)
    assert isinstance(slide, slides.FullImageSlide) and slide.picture_title() == "Chart about cats"
    assert [element.role for element in slide.to_deck_slide().elements] == ["title", "content"]
    never = slide_generator_types.PictureFirstSlideGenerator(_chart("Chart"), _found, 0.0)
    unfound = slide_generator_types.PictureFirstSlideGenerator(_chart("Chart"), lambda context: None, 1.0)
    for text_version in (never, unfound):
        with random_util.use(random_util.Rng(1)):
            assert isinstance(text_version.generate_slide(context, used)[0], slides.ChartSlide)
    monkeypatch.setenv("DISABLE_PICTURE_FIRST", "1")
    with random_util.use(random_util.Rng(1)):
        assert isinstance(sometimes.generate_slide(context, used)[0], slides.ChartSlide)


def test_a_schemas_charts_and_diagrams_try_pictures_first_and_keep_their_text_versions():
    trend = _generator("Trend", ConstantWeightFunction(1), _chart("Classic"), "chart_trend")
    quiz = _generator("Quiz", ConstantWeightFunction(1), _chart("Classic"), "quiz")
    classic = _generator("Classic", ConstantWeightFunction(1), _chart("Classic"))
    schema = _schema([_title(), trend, quiz, classic])
    wrapped, kept, plain = schema.slide_generators[1:]
    assert isinstance(wrapped.slide_generator, slide_generator_types.PictureFirstSlideGenerator)
    assert wrapped.text_version is trend and (wrapped.name, set(wrapped.get_tags()), wrapped.llm) == (
        "Trend",
        set(trend.get_tags()),
        trend.llm,
    )
    assert kept is quiz and plain is classic  # (not a chart or a diagram, or no recipe)
    assert wrapped.weighted(ConstantWeightFunction(2), "Trend 2").text_version.name == "Trend 2"


@pytest.fixture
def classic_charts(monkeypatch, photos, pictures_first):
    """A classic talk of 4 slides: a title slide and three trend charts, which try a picture first (found by the fake
    finder for the slide's seed: cats)."""
    trend = _generator("Trend", PeakedWeight((1, 2, 3), 100000, 0), _chart("Chart"), "chart_trend")
    return _use(monkeypatch, _schema([_title(), trend], {"title": 1}))


def test_a_classic_chart_is_its_picture_when_one_is_found(classic_charts, photos):
    events, _ = _timed(4, llm="none")
    assert [slide.type for slide in events[-1].deck.slides[1:]] == ["full_image"] * 3
    assert _texts(events[-1].deck.slides[1]) == ["Chart about cats"]
    photos.none.add("cats")
    events, _ = _timed(4, llm="none")
    assert [slide.type for slide in events[-1].deck.slides[1:]] == ["chart"] * 3


def test_a_classic_charts_picture_out_of_time_stands_in_as_its_text_version_and_comes_late(
    classic_charts, photos, held
):
    # (one chart: the fake finder finds every slide of the talk the same picture of cats, which a talk shows once)
    photos.slow.add("cats")
    threading.Timer(1.5, held.set).start()
    events, _ = _timed(2, llm="none", slide_seconds=SECONDS, parallel=False)
    ready = [event for event in events if type(event).__name__ == "SlideReady"]
    assert ready[1].slide.type == "chart" and _texts(ready[1].slide)[0] == "Chart about cats"
    assert "its text version, while its picture is looked for" in ready[1].slide.notes
    (late,) = [event for event in events if isinstance(event, SlideUpdated) and event.late]
    assert late.index == 1 and late.slide.type == "full_image" and _texts(late.slide) == ["Chart about cats"]


def test_a_stand_in_looks_no_picture_up_for_its_boxes(monkeypatch):
    looked = types.SimpleNamespace(count=0)

    def picture(context):
        looked.count += 1
        return None

    generate = slides_texts_pictured(picture)
    assert generate({"seed": "cats", slides.STANDING_IN: True}) == ("A title", "One", "Two", "Three")
    assert looked.count == 0


def slides_texts_pictured(picture):
    from talkgenerator.sources import slide_texts

    return slide_texts.pictured(
        lambda context: ("A title", "One", "Two", "Three"),
        picture,
        slide_texts.numbered_boxes("level"),
        odds=1.0,
    )
