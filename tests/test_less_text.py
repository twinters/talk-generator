"""Offline tests of talks with less text and more surprise (docs/v5-plan.md, D73: the user's feedback of 2026-11-10).

Charts and diagrams try a picture first, now and then, in their place (a real chart from the internet for a chart, a
weird picture for a diagram), under their title: a slide is that picture when one is found (in its time, in a talk with
a time limit per slide), and else its text version, which stands in for it until its picture comes. Planned and classic
slides alike; DISABLE_PICTURE_FIRST (which offline tests have) switches it off. And a slide that lists things, or a
diagram, breaks its pattern now and then in its punchline: an emoji alone, a few words, or a picture in its place (red
flags, reviews, an org chart's boss, a tier list's S tier, an alignment chart's chaotic evil), and the third of three
pictures doesn't follow the first two; DISABLE_PATTERN_BREAKS (which offline tests have too) switches them off.

The talks are made with test_slide_time_limit's small fake schemas, fake model and fake image finder.
"""

import dataclasses
import threading
import types

import pytest

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight
from talkgenerator.design import engine, themes
from talkgenerator.models.events import SlideEarly, SlideReady, SlideUpdated
from talkgenerator.plan import kinds, prompt
from talkgenerator.plan.kinds import KINDS, PICTURE, Recipe
from talkgenerator.schema.slide_schemas import slide_generators
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
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
    assert "Picture first: in place of its chart" in events[-1].deck.slides[1].notes  # (and how it was made)
    assert "Generator: Trend" in events[-1].deck.slides[1].notes
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


def test_a_classic_charts_text_version_stands_in_before_its_early_version(classic_charts, photos, held):
    # (the slide's own words first, as a planned slide stands in as it's planned before its early version: D73)
    photos.slow.add("cats")
    threading.Timer(1.5, held.set).start()
    events, _ = _timed(2, llm="none", early=1, slide_seconds=SECONDS, parallel=False)
    (early,) = [event for event in events if isinstance(event, SlideEarly)]
    assert early.index == 1 and _texts(early.slide)[0].startswith("Spare ")
    ready = [event for event in events if isinstance(event, SlideReady)]
    assert ready[1].slide.type == "chart" and _texts(ready[1].slide)[0] == "Chart about cats"
    (late,) = [event for event in events if isinstance(event, SlideUpdated) and event.late]
    assert late.index == 1 and late.slide.type == "full_image"


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


# PATTERN BREAKS: a list's punchline (its last thing), or a diagram's, breaks the pattern now and then: an emoji alone,
# a few words, or a picture in its place


@pytest.fixture
def breaking(monkeypatch):
    """Pattern breaks on (which offline tests have off)."""
    monkeypatch.delenv("DISABLE_PATTERN_BREAKS", raising=False)


def _broken(kind, seeds=400, recipe=None):
    """The recipes of a kind (or the recipe) as the dice vary them over the seeds, and those whose punchline breaks."""
    made = [(recipe or Recipe(kind)).varied(random_util.Rng(seed)) for seed in range(seeds)]
    return made, [varied for varied in made if "breaking the pattern" in varied.brief]


def test_lists_and_diagrams_break_their_pattern_now_and_then(breaking):
    for kind in ("red_flags", "reviews", "org_chart", "tier_list", "alignment_chart", "kpi"):
        made, broken = _broken(kind)
        assert 0.28 < len(broken) / len(made) < 0.42, kind
    for kind in ("pyramid", "funnel", "timeline", "venn", "matrix", "flowchart", "iceberg", "process"):
        made, broken = _broken(kind)
        assert 0.18 < len(broken) / len(made) < 0.32, kind
    made, broken = _broken("agenda")
    assert 0.13 < len(broken) / len(made) < 0.27
    assert KINDS["quiz"].pattern_break is None and KINDS["cycle"].pattern_break is None
    # (from a stream of their own: the variants' and box pictures' draws are as they were)
    for seed in range(30):
        plain = Recipe("red_flags")._varied(random_util.Rng(seed), frozenset())
        assert Recipe("red_flags").varied(random_util.Rng(seed)).omit == plain.omit


def test_a_punchline_breaks_as_an_emoji_a_few_words_or_a_picture_in_its_place(breaking):
    _, broken = _broken("red_flags")
    ways = {
        "emoji" if "a single emoji" in recipe.brief else "short" if "one to three words" in recipe.brief else "picture"
        for recipe in broken
    }
    assert ways == {"emoji", "short", "picture"}
    picture = next(recipe for recipe in broken if recipe.pictures)
    assert picture.pictures == ("flag_5",) and "flag_5_picture" in picture.image_queries()
    lines = prompt.slide_lines(prompt.PlannedSlide(5, "Red Flags", picture, "geese"))
    assert any(
        line.startswith("- flag_5_picture_query: an image search query for a surprising picture") for line in lines
    )
    emoji = next(recipe for recipe in broken if "a single emoji" in recipe.brief)
    assert emoji.hints["flag_5"] == "a fifth red flag: a single emoji, nothing else (the pattern break)"
    # (the last red flag the slide has: by its variant, the third or the fourth)
    flags = slide_generators.get("Red Flags").llm
    _, broken = _broken("red_flags", recipe=flags)
    for recipe in broken:
        named = {name.removesuffix("_picture_query") for name in recipe.hints if name.startswith("flag_")}
        named |= set(recipe.pictures)
        assert len(named) == 1 and not named & recipe.omit, recipe.brief
    # (a list written as one field breaks in its last thing)
    _, broken = _broken("agenda")
    assert all("the last of them" in recipe.hints["items"] for recipe in broken)
    # (a picture in a thing's place only where the kind's layouts show one: a diagram's punchline is an emoji alone)
    pictured = {kind for kind, made in KINDS.items() if made.pattern_break and "picture" in made.pattern_break.ways}
    assert pictured == {"red_flags", "reviews", "org_chart", "tier_list", "alignment_chart"}
    _, broken = _broken("pyramid")
    assert broken and all(
        recipe.hints["level_1"].endswith("a single emoji, nothing else (the pattern break)") for recipe in broken
    )


def test_without_breaks_a_recipe_is_as_it_was():
    assert not any(
        "breaking the pattern" in Recipe("red_flags").varied(random_util.Rng(seed)).brief for seed in range(60)
    )


def _picture(name="https://example.com/goose.jpg"):
    return ImageData(name, source="Fake photos", declared_size=(1600, 900), license_class="public-domain")


@pytest.mark.parametrize(
    ("slide", "role"),
    [
        (lambda p: slides.RedFlagsSlide("Flags", "One", "Two", "Three", "Four", pictures={"flag_4": p}), "flag_4"),
        (lambda p: slides.RedFlagsSlide("Flags", "One", "Two", "Three", pictures={"flag_3": p}), "flag_3"),
        (
            lambda p: slides.ReviewsSlide("Said", "5", "Great.", "Ann", "1", "Bad.", "Bob", pictures={"review_2": p}),
            "review_2",
        ),
        (lambda p: slides.OrgChartSlide("Boss", "The goose", "Me", "You", pictures={"boss": p}), "boss"),
        (lambda p: slides.TierListSlide("Ranked", "Geese", "Ducks", pictures={"s_tier": p}), "item_s_1"),
        (
            lambda p: slides.AlignmentChartSlide(
                "A", ("L", "N", "C"), ("G", "N", "E"), *"abcdefgh", "i", pictures={"chaotic_evil": p}
            ),
            "chaotic_evil",
        ),
    ],
)
def test_a_lists_punchline_can_be_a_picture_in_its_texts_place(images, slide, role):
    made = slide(_picture())
    assert made.missing_content() == []
    elements = {element.role: element for element in made.to_deck_slide().elements}
    assert role not in elements and elements[f"{role}_picture"].kind == "image"  # (instead of its text)
    clicks = [element.appears_on_click for element in elements.values() if element.appears_on_click]
    assert elements[f"{role}_picture"].appears_on_click == max(clicks)  # (as the punchline, last)
    from talkgenerator.checks.deck import check_completeness
    from talkgenerator.models.deck import Deck

    deck = Deck(generator="test", slides=(slides.TitleSlide("Geese", None).to_deck_slide(), made.to_deck_slide()))
    assert check_completeness(deck) == []  # (a picture in a thing's place is no thing missing)


def test_an_emoji_alone_is_drawn_as_large_as_its_box_takes():
    deck = SlideDeck(2, seed=1)
    deck.add_slide(0, slides.TitleSlide("Geese", None))
    deck.add_slide(1, slides.RedFlagsSlide("Flags", "It honks at night", "It owns a car", "🙄"))
    deck.theme = themes.pick("kids", random_util.Rng(2))
    flags = {element.role: element for element in deck.to_deck().slides[1].elements}
    assert flags["flag_3"].style.size > max(flags[role].style.size for role in ("flag_1", "flag_2"))
    # (a text with a letter in it is no emoji alone, without looking for emoji in it: fitting texts stays fast)
    assert [engine._emoji_alone(text) for text in ("🙄", "👍 👍", "1️⃣", "~/talk", "Meh 🙄", " ", "")] == [
        True,
        True,
        True,
        False,
        False,
        False,
        False,
    ]


def test_a_planned_punchlines_picture_takes_its_texts_place_or_it_stays_as_written(images, photos, breaking):
    from talkgenerator.plan.realize import realize

    picture_way = next(recipe for recipe in _broken("org_chart")[1] if recipe.pictures)
    plan = kinds.SlidePlan(
        kind="org_chart",
        recipe="Org Chart",
        concept="geese",
        texts={"title": "Who's in charge", "boss": "The goose", "report_1": "Me", "report_2": "You"},
        images={"boss_picture": "a goose in a tie"},
    )
    made = realize(plan, picture_way, {"seed": "geese"}, random_util.Rng(1), 0)
    assert made is not None and "a goose in a tie" in photos.asked
    roles = {element.role for element in made[0].to_deck_slide().elements}
    assert "boss_picture" in roles and "boss" not in roles
    photos.none.add("a goose in a tie")  # (no picture: who's in charge, as the model wrote them)
    made = realize(plan, picture_way, {"seed": "geese"}, random_util.Rng(1), 0)
    assert made is not None
    elements = {element.role: element for element in made[0].to_deck_slide().elements}
    assert "boss_picture" not in elements and elements["boss"].text == "The goose"


def test_a_classic_lists_punchline_breaks_its_pattern_now_and_then(breaking, monkeypatch):
    from talkgenerator.sources import packs, slide_texts

    monkeypatch.setattr(slide_texts, "related_words", lambda seed: ["dog", "mouse", "yarn", "milk"])
    context = {"seed": "cat", "topic": "cats"}
    short = {
        slide_texts.text_generator.apply_variables_to_template(template, {"seed": "cat", "related": "dog"})
        for template in packs.pack().rule("karaoke.review_short")
    }
    lasts = []
    for seed in range(60):
        with random_util.use(random_util.Rng(seed)):
            lasts.append(slide_texts.generate_reviews(context)[-2])
    assert 0.2 < sum(last in short for last in lasts) / len(lasts) < 0.5
    numbers = []
    for seed in range(60):
        with random_util.use(random_util.Rng(seed)):
            numbers.append(slide_texts._kpi_number(True))
    words = [number for number in numbers if number in slide_texts._NOT_NUMBERS]
    assert 0.2 < len(words) / len(numbers) < 0.5 and all(len(number) <= 10 for number in slide_texts._NOT_NUMBERS)
    breaking_rows = [template for template in packs.pack().rule("captions.three_captions") if "Step 47" in template]
    assert breaking_rows == ["Step 1|Step 2|Step 47"]


def test_a_classic_punchline_is_an_emoji_or_a_picture_in_its_place(breaking, images):
    from talkgenerator.sources import slide_texts

    found = []

    def picture(context):
        found.append(context["seed"])
        return _picture()

    def org_chart(context):
        return ("Who's in charge", "The van keys", "Me", "You")

    generate = slide_texts.broken(org_chart, slide_texts.at(1, "boss"), {"emoji": 1.0, "picture": 1.0}, 1.0, picture)
    made = []
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            made.append(generate({"seed": "cats"}))
    emojis = [generated for generated in made if not isinstance(generated[-1], slides.Pictures)]
    pictures = [generated for generated in made if isinstance(generated[-1], slides.Pictures)]
    assert emojis and pictures and set(found) == {"The van keys"}  # (a picture of its words)
    assert all(generated[1] == "🔑" for generated in emojis)  # (the thing's own emoji, by a word of it)
    assert all(generated[-1].by_box() == {"boss": _picture()} for generated in pictures)
    slide = slide_generator_types.DrawnSlideGenerator(generate, slides.OrgChartSlide)
    with random_util.use(random_util.Rng(next(n for n, g in enumerate(made) if g in pictures))):
        shown, _ = slide.generate_slide({"seed": "cats"}, (set(), 10))
    assert "boss_picture" in {element.role for element in shown.to_deck_slide().elements}
    # (one that stands in for a slide out of time looks nothing up, nor breaks at all)
    with random_util.use(random_util.Rng(1)):
        assert generate({"seed": "cats", slides.STANDING_IN: True}) == org_chart({})
    monkeypatch_free = slide_texts.broken(org_chart, slide_texts.at(-1), {"emoji": 1.0}, 1.0)
    with random_util.use(random_util.Rng(1)):
        assert monkeypatch_free({"seed": "cats"})[:3] == ("Who's in charge", "The van keys", "Me")


def test_the_third_of_three_pictures_breaks_the_pattern_most_of_the_time():
    for name in ("Three Captions Weird", "Three Captions Weird (CRF)"):
        variants = slide_generators.get(name).llm.variants
        breaking_share = sum(variant.weight for variant in variants if "pattern" in variant.note)
        assert breaking_share / sum(variant.weight for variant in variants) == pytest.approx(0.6), name
    three = slide_generators.get("Three Captions Weird").llm
    varied = next(
        recipe
        for recipe in (three.varied(random_util.Rng(seed)) for seed in range(40))
        if "breaking the pattern" in recipe.brief
    )
    lines = prompt.slide_lines(prompt.PlannedSlide(4, "Three Captions Weird", varied, "naps"))
    assert any(line.startswith("- image_3_query: an image search query for the third picture") for line in lines)
    assert any(line.startswith("- caption_3: the right caption: one that breaks the pattern") for line in lines)
