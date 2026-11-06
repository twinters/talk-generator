"""Slide kinds: the shapes of slide a plan can ask for, what to write for each, and how each becomes a slide.

A kind names its text fields (with a description and a length limit, for the language model and the Skill) and its
image slots, and builds one of v4's Slide classes from them. A Recipe ties a kind to a slide generator of a
presentation schema: which of v4's image sources fill its slots, what this particular slide is about (its brief and
hints), which fields it leaves out, and which texts come from classic sources instead (real quotes, for instance).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.plan.languages import Language
from talkgenerator.slide import slides
from talkgenerator.sources import chart
from talkgenerator.util import random_util


@dataclass(frozen=True)
class TextField:
    name: str
    description: str
    max_length: int = 80
    optional: bool = False  # may stay empty, and the slide then shows nothing there
    options: tuple[str, ...] = ()  # the words it can be, when it's a choice (such as how a trend line goes)


# Builds the slide from its texts (None where a field stays empty), its images (whatever the sources found), and the
# talk's language (for the words talkgenerator adds itself, such as a chart's Yes and No)
Builder = Callable[[Mapping[str, str | None], Mapping[str, Any], Language], slides.Slide]


@dataclass(frozen=True)
class Kind:
    name: str
    description: str
    texts: tuple[TextField, ...]
    images: tuple[str, ...]
    build: Builder


# A v4 content generator: a presentation context (with the "seed" to search for) in, an image (or None) out
ContentSource = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True, eq=False)
class Recipe:
    kind: str
    images: tuple[ContentSource, ...] = ()  # one per image slot of the kind, in order
    brief: str = ""  # what this slide is, for the language model
    hints: Mapping[str, str] = field(default_factory=dict)  # per text field: what to write here, instead of the kind's
    omit: frozenset[str] = frozenset()  # text fields, or "<slot>_query" image queries, that this slide does without
    texts_from: Mapping[str, ContentSource] = field(default_factory=dict)  # texts found by classic sources instead

    def written_fields(self) -> list[TextField]:
        """The text fields the language model writes for this slide."""
        return [
            text for text in KINDS[self.kind].texts if text.name not in self.omit and text.name not in self.texts_from
        ]

    def image_queries(self) -> list[str]:
        """The image slots the language model writes a search query for."""
        return [slot for slot in KINDS[self.kind].images if f"{slot}_query" not in self.omit]


def _title(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.TitleSlide(texts["title"] or "", texts.get("subtitle"))


def _image(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.ImageSlide(texts.get("title"), images.get("image"))


def _full_image(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FullImageSlide(texts.get("title"), images.get("image"))


def _statement(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.LarqeQuoteSlide(None, texts.get("text") or "", images.get("background"))


def _two_columns(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.TwoColumnImageSlide(
        texts.get("title"), texts.get("caption_1"), images.get("image_1"), texts.get("caption_2"), images.get("image_2")
    )


def _three_columns(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.ThreeColumnImageSlide(
        texts.get("title"),
        texts.get("caption_1"),
        images.get("image_1"),
        texts.get("caption_2"),
        images.get("image_2"),
        texts.get("caption_3"),
        images.get("image_3"),
    )


def _history_quote(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # A made-up historical figure (never a real person) and their quote, where v4 put a real quote next to a made-up name
    return slides.TwoColumnImageSlide(
        texts.get("title"), texts.get("name"), images.get("portrait"), None, texts.get("quote")
    )


def _chart_yes_no(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    data = ChartData()
    data.categories = [language.yes, language.no, texts["funny_answer"] or ""]
    data.add_series("", chart.normalise_data(chart.create_equal_data_with_outlier_end(3, 0.2, 1, 2.5, 1, 20)))
    chart_type, style = random_util.choice((chart.PIE, chart.PROCENT_HISTOGRAM, chart.DOUGHNUT))
    return slides.ChartSlide(texts["question"], chart_type, data, style)


def _chart_categories(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    categories = [part.strip() for part in (texts["categories"] or "").split("|") if part.strip()][:5]
    if len(categories) < 2:
        raise ValueError("a pie chart needs two answers or more")
    data = ChartData()
    data.categories = categories
    data.add_series("", chart.normalise_data([random_util.uniform(1, 10) ** 2 for _ in categories]))
    chart_type, style = random_util.choice((chart.PIE, chart.DOUGHNUT))
    return slides.ChartSlide(texts["question"], chart_type, data, style)


def _chart_trend(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # The first line goes the way the plan says (or a random way), and a second line, if any, another way
    shape, values = chart.trend_values(texts.get("shape"))
    lines = [(texts.get("line") or "", values)]
    second = texts.get("second_line")
    if second:
        lines.append((second, chart.trend_values(texts.get("second_shape"), avoid=shape)[1]))
    return slides.ChartSlide(
        texts["title"],
        XL_CHART_TYPE.LINE,
        chart.trend_chart_data(lines),
        x_title=texts["x_axis"],
        y_title=texts["y_axis"],
        reveal="series" if second else "all",
    )


def _chart_bars(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    bars = [part.strip() for part in (texts["bars"] or "").split("|") if part.strip()][:6]
    if len(bars) < 3:
        raise ValueError("a ranking needs three bars or more")
    return slides.ChartSlide(
        texts["title"], XL_CHART_TYPE.BAR_CLUSTERED, chart.ranking_chart_data(bars), y_title=texts.get("value_axis")
    )


def _chart_correlation(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # The made-up data of v4's correlation curves, under the plan's claim
    data = XyChartData()
    series = data.add_series("Model")
    xs = chart.generate_random_x(0, 2 ** random_util.uniform(1, 10), int(2 ** random_util.uniform(3, 8)))
    points = chart.generate_y(xs, chart.create_interesting_curve_function())
    points = chart.add_gaussian_noise_to_multidim_points(1.5 * random_util.uniform(0, max(xs) / 10), points)
    chart.add_data_to_series(series, [(abs(x), abs(y)) for x, y in points])
    return slides.ChartSlide(
        texts["title"],
        XL_CHART_TYPE.XY_SCATTER,
        data,
        chart.create_set_scatter_properties("", ""),
        x_title=texts.get("x_axis"),
        y_title=texts.get("y_axis"),
    )


_OPTIONAL_TITLE = TextField("title", "the slide's title", 60, optional=True)

# The talk's own texts, on its title slide: "By <presenter>, <job>" under the title
TALK_TITLE: Final = TextField("title", "the talk's title", 80)
PRESENTER_JOB: Final = TextField(
    "presenter_job", "the presenter's grand, made-up job, such as 'Professor of Applied Sock Theory'", 50
)

KINDS: Final[dict[str, Kind]] = {
    kind.name: kind
    for kind in (
        Kind(
            "title",
            "The title slide: the talk's title, and the presenter (their name is added by talkgenerator).",
            (TextField("title", "the talk's title", 80), TextField("subtitle", "who presents it", 120, optional=True)),
            (),
            _title,
        ),
        Kind("image", "An image with a title.", (TextField("title", "the slide's title", 60),), ("image",), _image),
        Kind(
            "full_image",
            "An image filling the slide, with an optional title.",
            (_OPTIONAL_TITLE,),
            ("image",),
            _full_image,
        ),
        Kind(
            "statement",
            "A big text over a photo.",
            (TextField("text", "the big text over the photo", 140),),
            ("background",),
            _statement,
        ),
        Kind(
            "two_columns",
            "Two captioned images side by side.",
            (
                _OPTIONAL_TITLE,
                TextField("caption_1", "the left caption", 40),
                TextField("caption_2", "the right caption", 40),
            ),
            ("image_1", "image_2"),
            _two_columns,
        ),
        Kind(
            "three_columns",
            "Three captioned images side by side.",
            (
                _OPTIONAL_TITLE,
                TextField("caption_1", "the left caption", 40),
                TextField("caption_2", "the middle caption", 40),
                TextField("caption_3", "the right caption", 40),
            ),
            ("image_1", "image_2", "image_3"),
            _three_columns,
        ),
        Kind(
            "history_quote",
            "A made-up historical figure's portrait, next to their quote.",
            (
                TextField("title", "a title about history", 60),
                TextField("name", "a made-up historical figure (never a real person): name and title", 60),
                TextField("quote", "what this made-up figure once said", 160),
            ),
            ("portrait",),
            _history_quote,
        ),
        Kind(
            "chart_yes_no",
            "A chart of answers to a yes-or-no question: yes, no, and a funny third answer.",
            (
                TextField("question", "a yes-or-no question, as the chart's title", 90),
                TextField("funny_answer", "a third answer, besides yes and no, such as 'Only on Tuesdays'", 30),
            ),
            (),
            _chart_yes_no,
        ),
        Kind(
            "chart_categories",
            "A pie chart of made-up shares.",
            (
                TextField("question", "the question the pie chart answers, as its title", 90),
                TextField("categories", "two to five answers, separated by |", 120),
            ),
            (),
            _chart_categories,
        ),
        Kind(
            "chart_correlation",
            "A scatter plot of made-up data, under a claim of a correlation.",
            (
                TextField("title", "a made-up correlation between two things, as a claim", 90),
                TextField("x_axis", "the axis along the bottom: the first of the two things", 40, optional=True),
                TextField("y_axis", "the axis going up: the second thing", 40, optional=True),
            ),
            (),
            _chart_correlation,
        ),
        Kind(
            "chart_trend",
            "A line chart of a made-up trend along two odd axes; a second line, if any, draws itself across it on a "
            "click, as the punchline.",
            (
                TextField("title", "the chart's claim, as its title", 90),
                TextField("x_axis", "what the chart goes along, such as 'Hours since the meeting started'", 40),
                TextField("y_axis", "what the line measures, such as 'Times someone said synergy'", 40),
                TextField("shape", "how the line goes", 20, optional=True, options=tuple(chart.TREND_SHAPES)),
                TextField("line", "the line's name in the legend, such as 'Me'", 30, optional=True),
                TextField(
                    "second_line",
                    "a second line's name in the legend, such as 'My cat'; it appears on a click, as the punchline",
                    30,
                    optional=True,
                ),
                TextField(
                    "second_shape", "how the second line goes", 20, optional=True, options=tuple(chart.TREND_SHAPES)
                ),
            ),
            (),
            _chart_trend,
        ),
        Kind(
            "chart_bars",
            "A ranking in bars, whose last bar, the punchline, wins by far.",
            (
                TextField("title", "the question the ranking answers, as its title", 90),
                TextField("bars", "three to six things, separated by |, the last one the punchline", 160),
                TextField("value_axis", "what the bars measure, such as 'Danger level'", 40, optional=True),
            ),
            (),
            _chart_bars,
        ),
    )
}
