"""Offline tests of the charts that came with v5: trends along two odd axes (whose second line draws itself in on a
click), rankings that the punchline wins by far, and titled axes."""

import pytest
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn

from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import clean_text
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
    with random_util.use(random_util.Rng(4)):
        content = chart.generate_trend_chart({"topic": "cats", "seed": "naps"})
    title, chart_type, _, _, x_title, y_title = content
    assert (title, chart_type, x_title, y_title) == ("naps over time", XL_CHART_TYPE.LINE, "cats", "naps")
    spec = _spec(slides.ChartSlide(*content))
    assert (spec.chart_type, spec.x_title, spec.y_title) == ("line", "cats", "naps")

    with random_util.use(random_util.Rng(4)):
        assert chart.generate_trend_chart({"topic": "cat", "seed": "cats"})[4] == "time"  # axes too alike


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
