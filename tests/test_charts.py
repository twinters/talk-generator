"""Offline tests of the charts that came with v5: trends along two odd axes (whose second line draws itself in on a
click), rankings that the punchline wins by far, and titled axes; and of how every chart looks: quiet, and readable
in the classic template and in themes."""

import itertools
from collections import Counter

import pytest
from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.oxml.ns import qn
from pptx.text.text import Font

from talkgenerator.checks.deck import check_leftovers
from talkgenerator.design import color, engine, themes
from talkgenerator.models.deck import Deck
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, kinds, languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import clean_text
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_pptx
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
    monkeypatch.setattr(chart, "chart_claim_generator", lambda context: "The data doesn't lie")
    monkeypatch.setattr(chart, "axis_titles", lambda context: (f"Love of {context['x_label']}", context["y_label"]))
    with random_util.use(random_util.Rng(4)):
        content = chart.generate_trend_chart({"topic": "cats", "seed": "naps"})
    title, chart_type, _, _, x_title, y_title, _, _ = content
    # (its axes say what it compares: its title is a claim, D73)
    assert (title, chart_type, x_title, y_title) == ("The data doesn't lie", XL_CHART_TYPE.LINE, "Love of cats", "naps")
    spec = _spec(slides.ChartSlide(*content))
    assert (spec.chart_type, spec.x_title, spec.y_title) == ("line", "Love of cats", "naps")

    with random_util.use(random_util.Rng(4)):
        assert chart.generate_trend_chart({"topic": "cat", "seed": "cats"})[4] == "Love of time"  # axes too alike
    monkeypatch.setattr(chart, "axis_titles", lambda context: (None, None))
    with random_util.use(random_util.Rng(4)):
        assert chart.generate_trend_chart({"topic": "cats", "seed": "naps"})[0] == "naps over time"  # (bare: it names)


def test_a_planned_charts_title_that_says_what_it_compares_goes_on_its_axes():
    assert kinds.axes_from_title("Coffee vs. productivity", None, None) == (None, "Coffee", "Productivity")
    assert kinds.axes_from_title("naps versus genius: the data", None, "Hours") == ("The data", "Naps", "Hours")
    assert kinds.axes_from_title("Penguins v. pigeons", "Joy", "Time") == (None, "Joy", "Time")
    claim = "Penguins get happier the colder it gets"
    assert kinds.axes_from_title(claim, None, None) == (claim, None, None)
    long = "Why cats always win against every single dog vs. the rest"  # (a claim, with "vs." in it)
    assert kinds.axes_from_title(long, None, None) == (long, None, None)
    slide = kinds.KINDS["chart_correlation"].build({"title": "Socks vs. sadness", "shape": "rising"}, {}, ENGLISH)
    spec = _spec(slide)
    assert (spec.y_title, spec.x_title) == ("Socks", "Sadness") and slide.to_deck_slide().elements[0].role == "chart"


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
    assert str(drawn.plots[0].series[0].format.fill.fore_color.rgb) == "808080"  # and the others grey
    assert not drawn.plots[0].vary_by_categories
    assert drawn.category_axis.major_tick_mark == XL_TICK_MARK.NONE

    with pytest.raises(ValueError):
        KINDS["chart_bars"].build({**texts, "bars": "AI | My cat"}, {}, ENGLISH)


def test_scores_between_a_rankings_names_are_left_out():
    texts = {"title": "Who worships cats most?", "bars": "Druids | 6 | Hittite priests | 4.5 | Scholars | 20%"}
    with random_util.use(random_util.Rng(5)):
        slide = KINDS["chart_bars"].build({**texts, "value_axis": ""}, {}, ENGLISH)
    assert _spec(slide).categories == ("Druids", "Hittite priests", "Scholars")


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


# HOW CHARTS LOOK


def _answers(kind):
    """A yes/no chart with a funny third answer (in one of chart.PIE, chart.PROCENT_HISTOGRAM or chart.DOUGHNUT)."""
    data = ChartData()
    data.categories = ["Yes", "No", "Only on Tuesdays"]
    data.add_series("", [0.12, 0.07, 0.81])
    chart_type, style = kind
    return slides.ChartSlide("Do you believe sugar was a medieval wonder drug?", chart_type, data, style)


def _built(kind, texts, seed):
    with random_util.use(random_util.Rng(seed)):
        return KINDS[kind].build(texts, {}, ENGLISH)


_EVERY_KIND_OF_CHART = {
    "column": lambda: _answers(chart.PROCENT_HISTOGRAM),
    "pie": lambda: _answers(chart.PIE),
    "doughnut": lambda: _answers(chart.DOUGHNUT),
    "ranking": lambda: _built(
        "chart_bars", {"title": "Threats", "bars": "AI | Asteroids | My cat", "value_axis": "Danger"}, 5
    ),
    "trend": lambda: _trend(shape="hockey stick", event="I got a cat", line="Me", second_line="My cat"),
    "correlation": lambda: _built(
        "chart_correlation", {"title": "Naps cause cats", "x_axis": "Naps", "y_axis": "Cats", "outlier": "Me"}, 8
    ),
}


def _drawn_in(slide, family=None):
    """The slide's chart drawn in the classic template, or in a theme of the family; with the colour of the slide
    behind it, and the font its texts should be in."""
    deck = Deck(generator="test", seed=1, slides=(slide.to_deck_slide(),))
    if family is None:
        presentation, background, font = render_pptx(deck), "#000000", "Calibri"
    else:
        theme = themes.pick(family, random_util.Rng(1))
        presentation = render_pptx(engine.lay_out(deck, theme))
        background, font = theme.palette.background, theme.fonts.body
    (frame,) = [shape for shape in presentation.slides[0].shapes if shape.has_chart]
    return frame.chart, background, font


def test_a_column_chart_shows_its_shares_on_its_columns_without_an_axis_or_gridlines():
    drawn, _, _ = _drawn_in(_answers(chart.PROCENT_HISTOGRAM))
    value_axis = drawn.value_axis
    assert not value_axis.visible
    assert not value_axis.has_major_gridlines and not value_axis.has_minor_gridlines  # (v4 misspelt them, so had them)
    assert drawn.category_axis.major_tick_mark == XL_TICK_MARK.NONE
    plot = drawn.plots[0]
    assert plot.has_data_labels and plot.data_labels.show_value
    assert (plot.data_labels.number_format, plot.data_labels.position) == ("0%", XL_LABEL_POSITION.OUTSIDE_END)


def test_a_correlation_is_dots_without_gridlines_or_numbers():
    drawn, _, _ = _drawn_in(_EVERY_KIND_OF_CHART["correlation"]())
    for axis in (drawn.category_axis, drawn.value_axis):
        assert not axis.has_major_gridlines
        assert axis.tick_label_position == XL_TICK_LABEL_POSITION.NONE
        assert axis.major_tick_mark == XL_TICK_MARK.NONE
    assert drawn.plots[0].series[0].marker.style == XL_MARKER_STYLE.CIRCLE


@pytest.mark.parametrize("family", [None, "dark minimal", "clean keynote"])
@pytest.mark.parametrize("kind", list(_EVERY_KIND_OF_CHART))
def test_every_text_of_a_chart_reads_on_its_slide(kind, family):
    """Every text in the look's colour and font: the names, shares and axis titles that talkgenerator writes too,
    which PowerPoint drew in black (on the classic template's black, and on dark themes)."""
    drawn, background, font_name = _drawn_in(_EVERY_KIND_OF_CHART[kind](), family)
    space = drawn._chartSpace
    texts = [Font(properties) for properties in space.xpath(".//c:txPr//a:defRPr")]
    runs = [Font(run.get_or_add_rPr()) for run in space.xpath(".//a:r")]
    assert texts and (runs or kind == "column")
    on_background = texts + (runs if kind != "doughnut" else [])  # (a doughnut's shares are on its slices)
    for font in texts + runs:
        assert font.color.type is not None and font.name == font_name
    for font in on_background:
        assert color.contrast(f"#{font.color.rgb}", background) >= 4.5


@pytest.mark.parametrize("family", [None, "clean keynote", "dark minimal"])
def test_a_doughnut_has_its_shares_on_its_ring_and_names_its_slices_in_a_legend(family):
    drawn, _, _ = _drawn_in(_answers(chart.DOUGHNUT), family)
    assert drawn.has_legend
    points = drawn.plots[0].series[0].points
    assert [point.data_label.text_frame.text for point in points] == ["12%", "7%", "81%"]  # once, not twice
    if family is not None:  # in whichever of the theme's text and background reads on the slice
        for point in points:
            run = point.data_label.text_frame.paragraphs[0].runs[0]
            assert color.contrast(f"#{run.font.color.rgb}", f"#{point.format.fill.fore_color.rgb}") >= 3


@pytest.mark.parametrize("family", [None, "dark minimal"])
def test_a_pies_slices_are_kept_apart_by_lines_in_the_background_colour(family):
    drawn, background, _ = _drawn_in(_answers(chart.PIE), family)
    outlines = {str(point.format.line.color.rgb).lower() for point in drawn.plots[0].series[0].points}
    assert outlines == {background.lstrip("#").lower()}


def _named_point_label(drawn):
    """How a named point's label wraps (its text, and its own text properties), and how far it's moved over."""
    (label,) = drawn._chartSpace.xpath(".//c:dLbl[c:tx]")
    wraps = [body.get("wrap") for body in label.xpath("./c:tx/c:rich/a:bodyPr | ./c:txPr/a:bodyPr")]
    moved = label.xpath("./c:layout/c:manualLayout/c:x/@val")
    return wraps, float(moved[0]) if moved else 0.0


@pytest.mark.parametrize(("shape", "side"), [("hockey stick", -1), ("rising", -1), ("falling", 1)])
@pytest.mark.parametrize("family", [None, "neon"])
def test_a_named_moment_is_on_one_line_on_the_side_its_line_leaves_free(shape, side, family):
    """Above its dot, ending there where the line climbs on after it, and starting there where the line comes down
    to it."""
    drawn, _, _ = _drawn_in(_trend(shape=shape, event="Someone found the cookies"), family)
    wraps, moved = _named_point_label(drawn)
    assert wraps == ["none", "none"]
    assert (moved > 0) - (moved < 0) == side
    assert drawn._chartSpace.xpath(".//c:dLbl[c:tx]/c:dLblPos/@val") == ["t"]


def test_the_side_a_line_leaves_free():
    climbing, falling = [1, 1, 1, 1, 30, 60], [60, 50, 40, 30, 20]
    assert charts.free_side(climbing, 3) == -1  # (a hockey stick: the line climbs on after the point)
    assert charts.free_side(falling, 2) == 1
    assert charts.free_side([10, 50, 90, 50, 10], 2) == 0  # a peak: above it
    assert charts.free_side([90, 50, 10, 50, 90], 2) == 0  # a dip: no side is free
    assert charts.free_side([50] * 5, 2) == 0
    assert charts.free_side(falling, 9) == 0


def test_a_named_moment_moves_only_as_far_as_it_fits_in_the_plot():
    left, right = charts._PLOT_SPAN
    climbing = [1, 1, 1, 1, 30, 60]  # (its point 3 is at about 0.6 of the chart's width)
    assert charts._name_shift(climbing, 3, 0.2, 0.01) == pytest.approx(-0.11)  # its right end 0.01 left of the dot
    dot = left + 3.5 / 6 * (right - left)
    long = charts._name_shift(climbing, 3, 0.7, 0.01)  # doesn't fit on the left: it starts where the plot does
    assert dot + long - 0.35 == pytest.approx(left)
    assert charts._name_shift(climbing, 3, 2.0, 0.01) == pytest.approx((left + right) / 2 - dot)  # (wider than it)


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


# LIVELIER CORRELATIONS (docs/v5-plan.md, D64): clouds of many shapes, lines fitted through them, and named clusters


@pytest.mark.parametrize("shape", list(chart.CORRELATION_SHAPES))
def test_a_correlation_comes_in_many_shapes(shape):
    with random_util.use(random_util.Rng(3)):
        found, points = chart.correlation_points(shape)
    assert found == shape and 12 <= len(points) <= 150
    assert all(x >= 0 and y >= 0 for x, y in points)


def test_a_correlation_without_a_shape_gets_one_of_them_all():
    shapes = Counter()
    noise = set()
    for seed in range(300):
        with random_util.use(random_util.Rng(seed)):
            shape, points = chart.correlation_points(None)
        shapes[shape] += 1
        noise.add(len(points) // 40)
    assert set(shapes) == set(chart.CORRELATION_SHAPES) and shapes["rising"] > shapes["smile"]
    assert len(noise) >= 3  # (from a dozen points to a hundred and more)


def test_a_planned_correlation_takes_its_shape(monkeypatch):
    for shape in ("ring", "u-shaped"):
        with random_util.use(random_util.Rng(1)):
            spec = _spec(KINDS["chart_correlation"].build({"title": "Naps", "shape": shape}, {}, ENGLISH))
        (series,) = spec.series
        assert series.name == "" and len(series.points) >= 12
    assert clean_text("U-shaped", _field("chart_correlation", "shape")) == "u-shaped"


def test_a_line_is_fitted_through_a_cloud_now_and_then():
    found = Counter()
    for seed in range(400):
        with random_util.use(random_util.Rng(seed)):
            data, trendlines, _ = chart.correlation_data("rising")
        found[trendlines[0][1] if trendlines else None] += 1
    assert 0.25 <= (found["linear"] + found["quadratic"]) / 400 <= 0.45 and found["quadratic"] < found["linear"]
    with random_util.use(random_util.Rng(1)):
        assert all(chart.trendline_for("smile") is None for _ in range(20))


def test_a_fitted_line_is_the_least_squares_one():
    straight = [(x, 2 * x + 1) for x in range(10)]
    fitted = charts.fitted_line(straight, "linear", steps=9)
    assert all(y == pytest.approx(2 * x + 1) for x, y in fitted)
    curved = [(x, (x - 3) ** 2) for x in range(7)]
    assert all(y == pytest.approx((x - 3) ** 2) for x, y in charts.fitted_line(curved, "quadratic"))
    flat = charts.fitted_line(curved, "linear")  # (a straight line through a U: flat, and the joke)
    assert flat[0][1] == pytest.approx(flat[-1][1])
    assert charts.fitted_line([(1, 1), (1, 2), (1, 3)], "linear") == []


@pytest.mark.parametrize("family", [None, "clean keynote"])
def test_a_fitted_line_is_a_dashed_trendline_out_of_the_legend(family):
    data = XyChartData()
    series = data.add_series("")
    for x, y in [(1, 2), (2, 3), (3, 5), (4, 4), (5, 7)]:
        series.add_data_point(x, y)
    slide = slides.ChartSlide("Naps cause cats", XL_CHART_TYPE.XY_SCATTER, data, trendlines=((0, "quadratic"),))
    assert _spec(slide).series[0].trendline == "quadratic"
    drawn, _, _ = _drawn_in(slide, family)
    (line,) = drawn._chartSpace.xpath(".//c:ser/c:trendline")
    assert line.find(qn("c:trendlineType")).get("val") == "poly" and line.find(qn("c:order")).get("val") == "2"
    assert line.find(qn("c:spPr")).find(qn("a:ln")).find(qn("a:prstDash")).get("val") == "dash"
    assert line.getnext().tag == qn("c:xVal")  # (where the schema has it)
    assert not drawn.has_legend


@pytest.mark.parametrize("family", [None, "dark minimal"])
def test_named_clusters_are_clouds_of_their_own_in_a_legend(family):
    with random_util.use(random_util.Rng(4)):
        slide = KINDS["chart_correlation"].build(
            {"title": "Who naps most", "cluster_1": "Cats", "cluster_2": "Dogs", "cluster_3": "Owls", "outlier": "Me"},
            {},
            ENGLISH,
        )
    spec = _spec(slide)
    assert [series.name for series in spec.series] == ["Cats", "Dogs", "Owls", "Me"]
    assert all(len(series.points) >= 10 for series in spec.series[:3]) and not any(s.trendline for s in spec.series)
    assert spec.series[3].labels == ("Me",)
    drawn, _, _ = _drawn_in(slide, family)
    assert drawn.has_legend
    hidden = drawn._chartSpace.xpath(".//c:legend/c:legendEntry[c:delete/@val='1']/c:idx/@val")
    assert hidden == ["3"]  # (the outlier, a series of one point, isn't a cluster)
    if family is not None:  # each in its own colour
        fills = {str(series.marker.format.fill.fore_color.rgb) for series in list(drawn.plots[0].series)[:3]}
        assert len(fills) == 3


def test_a_correlation_comes_out_as_one_cloud_or_as_clusters():
    recipe = next(
        generator.llm for generator in get_schema("default").slide_generators if generator.name == "Correlation Curve"
    )
    varied = [recipe.varied(random_util.Rng(seed)) for seed in range(300)]
    clustered = [version for version in varied if "cluster_1" not in version.omit]
    assert 0.2 <= len(clustered) / len(varied) <= 0.4
    assert all("shape" in version.omit and "groups of points" in version.brief for version in clustered)
    assert all(
        {"cluster_1", "cluster_2", "cluster_3"} <= version.omit for version in varied if version not in clustered
    )
    # A recipe of its own without variants gets the kind's (one cloud, or now and then clusters)
    plain = [Recipe("chart_correlation").varied(random_util.Rng(seed)) for seed in range(100)]
    assert any("cluster_1" in version.omit for version in plain) and any("cluster_1" not in v.omit for v in plain)


def test_a_classic_correlation_has_clusters_now_and_then(monkeypatch):
    monkeypatch.setattr(chart, "correlation_title_generator", lambda context: "Naps cause cats")
    related = [(1.0, "dog"), (0.9, "mouse"), (0.8, "yarn"), (0.7, "milk")]
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: related)
    shown = Counter()
    for seed in range(120):
        with random_util.use(random_util.Rng(seed)):
            made = chart.generate_correlation_curve({"topic": "cats", "seed": "naps"})
        title, _, data, _, _, _, reveal, labels, trendlines = made
        names = [series.name for series in data]
        shown["clusters" if any(names) else "cloud"] += 1
        if any(names):
            assert set(names) <= {"Dog", "Mouse", "Yarn", "Milk"} and 2 <= len(names) <= 3 and not trendlines
        shown["fitted"] += bool(trendlines)
        slide = slides.ChartSlide(*made)
        assert slide.missing_content() == []
    assert 0.15 <= shown["clusters"] / 120 <= 0.45 and shown["fitted"] > 10


@pytest.mark.parametrize("family", themes.families())
def test_clusters_and_a_trends_lines_get_colours_that_tell_them_apart(family):
    with random_util.use(random_util.Rng(4)):
        clustered = KINDS["chart_correlation"].build(
            {"title": "Who naps most", "cluster_1": "Cats", "cluster_2": "Dogs", "cluster_3": "Owls"}, {}, ENGLISH
        )
    lines = _trend(line="Me", second_line="My cat")
    for seed in range(3):
        theme = themes.pick(family, random_util.Rng(seed))
        deck = engine.lay_out(Deck(generator="test", slides=(clustered.to_deck_slide(), lines.to_deck_slide())), theme)
        for slide in deck.slides:
            spec = slide.element("chart").chart
            colours = [series.color for series in spec.series]
            assert all(colours) and len(colours) >= 2
            assert all(engine._far_apart(one, other) for one, other in itertools.combinations(colours, 2)), colours
            behind = engine._backgrounds(theme)
            assert all(color.worst_contrast(colour, behind) >= engine.LINE_CONTRAST for colour in colours)
    # A chart of one cloud keeps its renderer's colours
    one = _built("chart_correlation", {"title": "Naps cause cats", "shape": "rising"}, 2)
    (slide,) = engine.lay_out(
        Deck(generator="test", slides=(one.to_deck_slide(),)), themes.pick(family, random_util.Rng(0))
    ).slides
    assert slide.element("chart").chart.series[0].color is None
