"""Offline tests of the charts that came with v5: trends along two odd axes (whose second line draws itself in on a
click), rankings that the punchline wins by far, and titled axes."""

import pytest
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn

from talkgenerator.checks.deck import check_leftovers
from talkgenerator.models.deck import Deck
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import clean_text
from talkgenerator.render import charts
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.sources import chart, conceptnet
from talkgenerator.util import random_util

ENGLISH = languages.LANGUAGES["en"]
TREND = {
    "title": "Why I'm always tired",
    "x_axis": "Hours since the meeting started",
    "y_axis": "Times someone said synergy",
    "shape": "exponential",
    "line": "",
    "second_line": "",
    "second_shape": "",
}


def _spec(slide):
    (element,) = [element for element in slide.to_deck_slide().elements if element.kind == "chart"]
    return element.chart


def _drawn(slide):
    """The slide in a PowerPoint, and its chart."""
    ppt_slide = slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())
    (frame,) = [shape for shape in ppt_slide.shapes if shape.has_chart]
    return ppt_slide, frame.chart


def _trend(**texts):
    with random_util.use(random_util.Rng(7)):
        return KINDS["chart_trend"].build({**TREND, **texts}, {}, ENGLISH)


def _field(kind, name):
    return next(text for text in KINDS[kind].texts if text.name == name)


# TRENDS


@pytest.mark.parametrize("shape", list(chart.TREND_SHAPES))
def test_a_trend_line_goes_the_way_its_shape_says(shape):
    with random_util.use(random_util.Rng(1)):
        name, values = chart.trend_values(shape)
    assert name == shape
    assert len(values) == chart.TREND_POINTS
    assert min(values) >= 0


def test_the_shapes_look_like_their_names():
    def values(shape):
        with random_util.use(random_util.Rng(2)):
            return chart.trend_values(shape)[1]

    assert values("rising")[-1] > values("rising")[0] + 50
    assert values("falling")[-1] < values("falling")[0] - 50
    exponential = values("exponential")
    assert exponential[6] - exponential[0] < exponential[-1] - exponential[6]  # slow, then fast
    peak, dip = values("peak"), values("dip")
    assert max(peak[3:9]) == max(peak) and min(dip[3:9]) == min(dip)
    crash = values("crash")
    assert crash[-1] < crash[8] / 2  # up and up, then down at once


def test_a_trend_without_a_shape_gets_one_and_a_second_line_another():
    with random_util.use(random_util.Rng(3)):
        shapes = {chart.trend_values(None)[0] for _ in range(50)}
        seconds = {chart.trend_values(None, avoid="rising")[0] for _ in range(50)}
    assert len(shapes) > 5
    assert "rising" not in seconds


def test_a_trend_chart_has_titled_axes_and_one_line():
    spec = _spec(_trend())
    assert spec.chart_type == "line"
    assert (spec.x_title, spec.y_title) == ("Hours since the meeting started", "Times someone said synergy")
    assert len(spec.series) == 1 and len(spec.series[0].values) == chart.TREND_POINTS
    assert spec.reveal == "all"

    ppt_slide, drawn = _drawn(_trend())
    assert drawn.category_axis.axis_title.text_frame.text == "Hours since the meeting started"
    assert drawn.value_axis.axis_title.text_frame.text == "Times someone said synergy"
    assert not drawn.has_legend  # one nameless line needs none
    assert drawn.value_axis.minimum_scale == 0  # so a flat line looks flat
    assert ppt_slide.element.find(qn("p:timing")) is None  # nothing to click for


def test_a_second_line_draws_itself_in_on_a_click():
    slide = _trend(line="Me", second_line="My cat", second_shape="crash")
    spec = _spec(slide)
    assert [series.name for series in spec.series] == ["Me", "My cat"]
    assert spec.reveal == "series"

    ppt_slide, drawn = _drawn(slide)
    assert drawn.has_legend
    targets = ppt_slide.element.xpath(".//p:timing//a:chart")
    assert {target.get("seriesIdx") for target in targets} == {"1"}  # the first line is there from the start
    assert {target.get("bldStep") for target in targets} == {"series"}
    assert ppt_slide.element.xpath(".//p:bldLst/p:bldGraphic/p:bldSub/a:bldChart/@bld") == ["series"]
    spid = ppt_slide.element.xpath(".//p:bldGraphic/@spid")[0]
    assert ppt_slide.element.xpath(".//p:graphicFrame/p:nvGraphicFramePr/p:cNvPr/@id") == [spid]
    effects = ppt_slide.element.xpath(".//p:cTn[@nodeType='clickEffect']")
    assert len(effects) == 1 and effects[0].get("presetClass") == "entr"
    # The timing goes after the colour map (and the transition, if any), as PowerPoint wants
    tags = [child.tag for child in ppt_slide.element]
    assert tags.index(qn("p:timing")) > tags.index(qn("p:clrMapOvr"))


def test_a_nameless_line_stays_out_of_the_legend():
    _, drawn = _drawn(_trend(second_line="My cat"))
    entries = drawn.legend._element.findall(qn("c:legendEntry"))
    assert [(entry.find(qn("c:idx")).get("val"), entry.find(qn("c:delete")).get("val")) for entry in entries] == [
        ("0", "1")
    ]
    children = [child.tag for child in drawn.legend._element]
    assert children.index(qn("c:legendEntry")) == children.index(qn("c:legendPos")) + 1


def test_a_shape_is_one_of_the_options():
    shape = _field("chart_trend", "shape")
    assert clean_text("Hockey-Stick", shape) == "hockey stick"
    assert clean_text(" 'Exponential.' ", shape) == "exponential"
    assert clean_text("sideways", shape) is None  # and the line gets a shape of its own
    assert len(_spec(_trend(shape="sideways")).series[0].values) == chart.TREND_POINTS


def test_the_language_model_picks_a_shape_from_the_options():
    properties = prompt.slide_schema(Recipe("chart_trend"))["properties"]
    assert properties["shape"]["enum"] == [*chart.TREND_SHAPES, ""]
    assert "one of rising, falling" in properties["shape"]["description"]
    assert "enum" not in properties["title"]


def test_a_plan_with_a_shape_that_isnt_an_option_gets_a_warning():
    plan = SlidePlan(kind="chart_trend", texts={**TREND, "shape": "sideways"})
    (warning,) = external.plan_warnings(plan, Recipe("chart_trend"))
    assert warning.startswith("shape is none of 'rising', 'falling'") and warning.endswith("talkgenerator picked one")
    assert external.plan_warnings(SlidePlan(kind="chart_trend", texts=TREND), Recipe("chart_trend")) == []


def test_the_reference_lists_the_options():
    reference = external.catalog_markdown("default")
    assert "## `chart_trend`" in reference and "`hockey stick`" in reference
    (trend,) = [kind for kind in external.catalog("default")["kinds"] if kind["kind"] == "chart_trend"]
    assert {text["name"]: text.get("options") for text in trend["texts"]}["shape"] == list(chart.TREND_SHAPES)


def test_the_classic_trend_chart(monkeypatch):
    monkeypatch.setattr(chart, "correlation_title_generator", lambda context: f"{context['y_label']} over time")
    monkeypatch.setattr(chart, "axis_titles", lambda context: (f"Love of {context['x_label']}", context["y_label"]))
    with random_util.use(random_util.Rng(4)):
        content = chart.generate_trend_chart({"topic": "cats", "seed": "naps"})
    title, chart_type, _, _, x_title, y_title, _, _ = content
    assert (title, chart_type, x_title, y_title) == ("naps over time", XL_CHART_TYPE.LINE, "Love of cats", "naps")
    spec = _spec(slides.ChartSlide(*content))
    assert (spec.chart_type, spec.x_title, spec.y_title) == ("line", "Love of cats", "naps")

    with random_util.use(random_util.Rng(4)):
        assert chart.generate_trend_chart({"topic": "cat", "seed": "cats"})[4] == "Love of time"  # axes too alike


def test_classic_charts_have_funny_axis_titles_or_none():
    titles = []
    with random_util.use(random_util.Rng(11)):
        for _ in range(30):
            titles.append(chart.axis_titles({"x_label": "cat", "y_label": "nap"}))
    bare = [pair for pair in titles if pair == (None, None)]
    assert 4 <= len(bare) <= 16  # about a third
    named = [pair for pair in titles if pair != (None, None)]
    assert all("cat" in x.lower() and "nap" in y.lower() for x, y in named)
    assert len({x for x, _ in named}) > 3 and all("{" not in x + y for x, y in named)


def test_a_moment_on_a_trend_is_marked_where_the_line_turns():
    slide = _trend(shape="hockey stick", event="I got a cat")
    (line,) = _spec(slide).series
    knee = chart.trend_turn("hockey stick")
    assert knee == 8  # three quarters of the way along
    assert line.labels[knee] == "I got a cat" and [label for label in line.labels if label] == ["I got a cat"]

    _, drawn = _drawn(slide)
    point = drawn.plots[0].series[0].points[knee]
    assert point.data_label.text_frame.text == "I got a cat"
    assert point.marker.size == 18
    assert not drawn.plots[0].series[0].points[0].data_label.has_text_frame  # the other points have no names


def test_names_go_only_on_points_the_chart_has():
    spec = _spec(_trend())
    labelled = charts.with_point_labels(spec, [(0, 3, "Here"), (0, 99, "Nowhere"), (5, 0, "No line"), (0, 4, "")])
    assert labelled.series[0].labels == ("", "", "", "Here")


def test_a_classic_trend_marks_a_moment_half_of_the_time(monkeypatch):
    monkeypatch.setattr(chart, "correlation_title_generator", lambda context: "Naps over time")
    events = []
    with random_util.use(random_util.Rng(10)):
        for _ in range(20):
            content = chart.generate_trend_chart({"topic": "cats", "seed": "nap"})
            events += [label for _, _, label in content[7]]
            spec = _spec(slides.ChartSlide(*content))
            assert sum(1 for label in spec.series[0].labels if label) == len(content[7])
    assert 4 <= len(events) <= 16
    assert all("{" not in event and event for event in events)
    assert any("nap" in event.lower() for event in events)


# RANKINGS


def test_a_ranking_is_won_by_its_punchline_by_far():
    texts = {"title": "The greatest threats to humanity", "bars": "Climate | AI | Asteroids | My cat", "value_axis": ""}
    with random_util.use(random_util.Rng(5)):
        slide = KINDS["chart_bars"].build({**texts, "value_axis": "Danger level"}, {}, ENGLISH)
    spec = _spec(slide)
    assert spec.chart_type == "bar"
    assert spec.categories == ("Climate", "AI", "Asteroids", "My cat")
    values = spec.series[0].values
    assert list(values[:-1]) == sorted(values[:-1]) and values[-1] > 2 * values[-2]
    assert spec.y_title == "Danger level"

    _, drawn = _drawn(slide)
    assert drawn.value_axis.axis_title.text_frame.text == "Danger level"
    assert not drawn.has_legend
    punchline = drawn.plots[0].series[0].points[3].format.fill
    assert str(punchline.fore_color.rgb) == "E03C31"

    with pytest.raises(ValueError):
        KINDS["chart_bars"].build({**texts, "bars": "AI | My cat"}, {}, ENGLISH)


def test_the_classic_ranking(monkeypatch):
    related = [(1.0, "dog"), (0.9, "mouse"), (0.8, "cat food"), (0.7, "dog"), (0.5, "yarn")]
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: related)
    monkeypatch.setattr(chart, "ranking_title_generator", lambda context: "What experts fear most")
    with random_util.use(random_util.Rng(6)):
        title, chart_type, data, _ = chart.generate_ranking_bars({"topic": "cats", "seed": "cat"})
    labels = [category.label for category in data.categories]
    assert (title, chart_type) == ("What experts fear most", XL_CHART_TYPE.BAR_CLUSTERED)
    assert sorted(labels[:-1]) == ["dog", "mouse", "yarn"] and labels[-1] == "cat"  # "cat food" holds the seed

    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: [])
    assert chart.generate_ranking_bars({"topic": "cats", "seed": "cat"}) is None


# CORRELATIONS


def test_a_correlation_can_have_titled_axes():
    with random_util.use(random_util.Rng(8)):
        slide = KINDS["chart_correlation"].build(
            {"title": "Naps cause cats", "x_axis": "Naps", "y_axis": "Cats"}, {}, ENGLISH
        )
    _, drawn = _drawn(slide)
    assert drawn.category_axis.axis_title.text_frame.text == "Naps"  # the x axis
    assert drawn.value_axis.axis_title.text_frame.text == "Cats"
    with random_util.use(random_util.Rng(8)):
        untitled = KINDS["chart_correlation"].build({"title": "Naps cause cats"}, {}, ENGLISH)
    assert not _drawn(untitled)[1].category_axis.has_title


def test_a_correlation_can_have_an_outlier():
    with random_util.use(random_util.Rng(9)):
        slide = KINDS["chart_correlation"].build({"title": "Naps cause cats", "outlier": "Me"}, {}, ENGLISH)
    model, outlier = _spec(slide).series
    assert outlier.name == "Me" and outlier.labels == ("Me",) and len(outlier.points) == 1
    assert outlier.points[0][1] > max(y for _, y in model.points)  # far above the others
    _, drawn = _drawn(slide)
    assert drawn.plots[0].series[1].points[0].data_label.text_frame.text == "Me"
    assert not drawn.has_legend


def test_point_names_are_checked_for_leftovers():
    slide = _trend(event="The day of {seed}")
    deck = Deck(generator="test", slides=(slide.to_deck_slide(),))
    (finding,) = check_leftovers(deck)
    assert "chart label" in finding.message


def test_a_chart_recipe_comes_out_as_one_of_its_variants():
    recipe = next(
        generator.llm for generator in get_schema("default").slide_generators if generator.name == "Trend Chart"
    )
    varied = []
    for seed in range(40):
        varied.append(recipe.varied(random_util.Rng(seed)))
    assert all(not version.variants for version in varied)
    bare = [version for version in varied if "x_axis" in version.omit]
    labelled = [version for version in varied if not version.omit]
    assert bare and labelled and len(bare) < len(labelled)
    assert all("bare" in version.brief for version in bare)
    # A bare trend's slide asks for no axis titles and no names
    properties = prompt.slide_schema(bare[0])["properties"]
    assert "x_axis" not in properties and "line" not in properties and "title" in properties
    assert "funny" in labelled[0].brief and recipe.varied(random_util.Rng(3)).brief == varied[3].brief
    plain = Recipe("chart_trend")
    assert plain.varied(random_util.Rng(1)) is plain  # (no variants: as it is)


def test_a_bare_trend_has_no_axis_titles():
    with random_util.use(random_util.Rng(12)):
        slide = KINDS["chart_trend"].build({"title": "Why I'm always tired"}, {}, ENGLISH)
    spec = _spec(slide)
    assert (spec.x_title, spec.y_title, [series.name for series in spec.series]) == ("", "", [""])
    _, drawn = _drawn(slide)
    assert not drawn.category_axis.has_title and not drawn.value_axis.has_title


# THE FORMATS


@pytest.mark.parametrize("format_name", ["default", "ted"])
def test_every_format_has_trends_and_rankings_but_not_too_many(format_name):
    schema = get_schema(format_name)
    names = {generator.name: generator for generator in schema.slide_generators}
    assert names["Trend Chart"].llm.kind == "chart_trend"
    assert names["Bar Ranking"].llm.kind == "chart_bars"
    assert schema._max_allowed_tags["trend_chart"] == 1
    assert schema._max_allowed_tags["bar_chart"] == 1
    choices = external.recipes_of(schema)
    assert external.default_recipe(choices, "chart_trend").id == "trend-chart"
    assert external.default_recipe(choices, "chart_bars").id == "bar-ranking"
