"""Charts in PowerPoint: deck chart data to python-pptx chart data and back, and the chart styles.

A deck only holds a chart's numbers (`ChartSpec`); the renderer rebuilds the python-pptx chart data from them,
styles the chart by its type, and then finishes it in a look (`ChartLook`): the colours and font of the classic
template, or of the deck's theme.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (
    XL_CHART_TYPE,
    XL_LABEL_POSITION,
    XL_LEGEND_POSITION,
    XL_MARKER_STYLE,
    XL_TICK_LABEL_POSITION,
    XL_TICK_MARK,
)
from pptx.enum.dml import MSO_FILL
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.text.text import Font
from pptx.util import Pt

from talkgenerator.design import fonts
from talkgenerator.models.deck import ChartReveal, ChartSeries, ChartSpec, ChartType

PPTX_CHART_TYPES: dict[ChartType, XL_CHART_TYPE] = {
    "pie": XL_CHART_TYPE.PIE,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "bar": XL_CHART_TYPE.BAR_CLUSTERED,
    "line": XL_CHART_TYPE.LINE,
    "scatter": XL_CHART_TYPE.XY_SCATTER,
}
# The colour of what a chart points out: a ranking's winner, a labelled point
PUNCHLINE_COLOUR = RGBColor(0xE0, 0x3C, 0x31)
# The charts that have axes, which can have titles
AXIS_CHART_TYPES: tuple[ChartType, ...] = ("column", "bar", "line", "scatter")
_DECK_CHART_TYPES: dict[XL_CHART_TYPE, ChartType] = {pptx_type: name for name, pptx_type in PPTX_CHART_TYPES.items()}


def chart_spec(
    chart_type: XL_CHART_TYPE,
    chart_data: CategoryChartData | XyChartData,
    x_title: str | None = None,
    y_title: str | None = None,
    reveal: ChartReveal = "all",
) -> ChartSpec:
    """The deck's description of a python-pptx chart: its numbers, the titles of its axes, and how it appears."""
    extras: dict[str, Any] = {"x_title": x_title or "", "y_title": y_title or "", "reveal": reveal}
    deck_type = _DECK_CHART_TYPES.get(chart_type)
    if deck_type is None:
        raise ValueError(f"Charts of type {chart_type} can't be stored in a deck yet")
    if isinstance(chart_data, XyChartData):
        xy_series = tuple(
            ChartSeries(
                name=series.name or "",
                points=tuple(zip(_finite(series.x_values), _finite(series.y_values), strict=True)),
            )
            for series in chart_data
        )
        return ChartSpec(chart_type=deck_type, series=xy_series, **extras)
    categories = tuple(str(category.label) for category in chart_data.categories)
    category_series = tuple(
        ChartSeries(name=series.name or "", values=_finite(getattr(series, "values", ()))) for series in chart_data
    )
    return ChartSpec(chart_type=deck_type, categories=categories, series=category_series, **extras)


def pptx_chart_data(spec: ChartSpec) -> tuple[XL_CHART_TYPE, CategoryChartData | XyChartData]:
    """The python-pptx chart type and data that draw a deck's chart."""
    if spec.chart_type == "scatter":
        xy_data = XyChartData()
        for series in spec.series:
            xy_series = xy_data.add_series(series.name)
            for x, y in series.points:
                xy_series.add_data_point(x, y)
        return XL_CHART_TYPE.XY_SCATTER, xy_data
    category_data = CategoryChartData()
    category_data.categories = list(spec.categories)
    for series in spec.series:
        category_data.add_series(series.name, list(series.values))
    return PPTX_CHART_TYPES[spec.chart_type], category_data


def with_point_labels(spec: ChartSpec, labels: Iterable[tuple[int, int, str]]) -> ChartSpec:
    """The chart with names on some of its points: (series, point, name) each, counted from 0. Names of points the
    chart doesn't have are left out."""
    series = list(spec.series)
    for series_index, point_index, label in labels:
        if not label or not 0 <= series_index < len(series):
            continue
        current = series[series_index]
        size = len(current.points) or len(current.values)
        if not 0 <= point_index < size:
            continue
        names = [*current.labels, *[""] * (size - len(current.labels))]
        names[point_index] = label
        while names and not names[-1]:  # (no names after the last one)
            names.pop()
        series[series_index] = current.model_copy(update={"labels": tuple(names)})
    return spec.model_copy(update={"series": tuple(series)})


def _finite(values: Iterable[Any]) -> tuple[float, ...]:
    """The values as floats, with anything that JSON can't hold (NaN, infinity, nothing) as 0."""
    numbers = []
    for value in values:
        number = float(value) if value is not None else 0.0
        numbers.append(number if math.isfinite(number) else 0.0)
    return tuple(numbers)


# THE CHART STYLES
#
# Charts stay quiet, so that what they say stands out: no gridlines, tick marks or numbers along their axes (the
# axes' titles say what they measure, and the numbers are made up anyway), and their numbers, where they're part of
# the joke, on what they're about: a column's share on top of it, a slice's on the slice. The styles shape a chart by
# its type; label_points and finish then draw what it points out, its texts and its lines in a look: the classic
# template's, or a theme's.

# Text sizes, in points: the chart's own (a legend's), what names its parts (bars, slices, axes, named points), and a
# column's share, on top of it
TEXT_SIZE: Final = 18
LABEL_SIZE: Final = 20
SHARE_SIZE: Final = 24
# The bars of a ranking that the punchline beats, in the classic template: grey, so that the punchline stands out
RUNNER_UP_COLOUR: Final = RGBColor(0x80, 0x80, 0x80)
_EMU_PER_POINT: Final = 12700
# From a named point's dot to its name, in points: the dot's radius, and a little
_DOT_GAP: Final = 12
# Where a chart's plot roughly is, as shares of the chart's width (the rest holds the value axis's title, and margins)
_PLOT_SPAN: Final = (0.08, 0.97)


@dataclass(frozen=True)
class ChartLook:
    """The colours and font that a chart's named points, texts and lines are drawn in (see label_points and finish):
    the classic template's, or a theme's."""

    text: RGBColor  # labels, titles and legends
    line: RGBColor  # the axes
    background: RGBColor  # what's behind the chart: the lines between a pie's slices are in it, to keep them apart
    font: str  # one of talkgenerator.design.fonts, to measure names with
    punchline: RGBColor = PUNCHLINE_COLOUR  # a named point's dot


# The classic template's: white on black, in its body font, with grey axes
CLASSIC_LOOK: Final = ChartLook(
    text=RGBColor(0xFF, 0xFF, 0xFF),
    line=RGBColor(0x80, 0x80, 0x80),
    background=RGBColor(0x00, 0x00, 0x00),
    font="Calibri",
)


def _write(data_label, text: str, size: float = LABEL_SIZE, bold: bool = False) -> None:
    """Have the data label say the text. (PowerPoint draws a label's own text by its runs alone: the font of the label,
    or of the chart, doesn't reach it. So its size and boldness go on the runs, as finish's colour does.)"""
    frame = data_label.text_frame
    frame.text = text
    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(size)
            run.font.bold = bold


def _without_tick_marks(axis) -> None:
    axis.major_tick_mark = XL_TICK_MARK.NONE
    axis.minor_tick_mark = XL_TICK_MARK.NONE


def _set_pie_label_positions(chart, series, chart_data, label_position):
    chart.plots[0].has_data_labels = True
    for i in range(len(chart_data.categories)):
        point = series.points[i]
        value = series.values[i]
        _write(point.data_label, "{} ({:.0%})".format(chart_data.categories[i].label, value))
        if label_position:
            point.data_label.position = label_position


def set_histogram_properties(chart, chart_data):
    """Columns of shares, such as the answers to a yes-or-no question: every column's share on top of it, so that
    they need no axis or gridlines to be read by. (v4 meant to leave the gridlines out too, but misspelt them.)"""
    value_axis = chart.value_axis
    value_axis.has_major_gridlines = False
    value_axis.has_minor_gridlines = False
    value_axis.visible = False
    category_axis = chart.category_axis
    _without_tick_marks(category_axis)
    category_axis.tick_labels.font.size = Pt(LABEL_SIZE)
    plot = chart.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    shares = plot.data_labels
    shares.show_value = True
    shares.number_format = "0%"
    shares.number_format_is_linked = False
    shares.position = XL_LABEL_POSITION.OUTSIDE_END
    shares.font.size = Pt(SHARE_SIZE)
    shares.font.bold = True
    return chart


def set_pie_properties(chart, chart_data):
    """A pie: every slice's name and share on it, or around the pie when a slice is too thin to hold them."""
    if chart and chart_data:
        chart.has_legend = False
        chart.has_title = False
        series = chart.series[0]
        label_position = (
            XL_LABEL_POSITION.OUTSIDE_END if any(t < 0.10 for t in series.values) else XL_LABEL_POSITION.CENTER
        )
        _set_pie_label_positions(chart, series, chart_data, label_position)


def set_doughnut_properties(chart, chart_data):
    """A doughnut: every slice's share on it, and a legend that names them. (A doughnut's labels can't go around it,
    where names would have room, and on it, longer names run into each other.)"""
    if chart and chart_data:
        series = chart.series[0]
        chart.plots[0].has_data_labels = True
        for i in range(len(chart_data.categories)):
            _write(series.points[i].data_label, "{:.0%}".format(series.values[i]), bold=True)
        chart.has_legend = True
        legend = chart.legend
        legend.position = XL_LEGEND_POSITION.RIGHT
        legend.include_in_layout = False
        legend.font.size = Pt(LABEL_SIZE)


def set_scatter_properties(chart, chart_data):
    """A correlation: round dots, without gridlines or numbers along the axes (the numbers are made up; the axes'
    titles say what they measure)."""
    chart.has_legend = False
    for axis in (chart.category_axis, chart.value_axis):
        axis.has_major_gridlines = False
        axis.has_minor_gridlines = False
        axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        _without_tick_marks(axis)
    for series in chart.plots[0].series:
        series.marker.style = XL_MARKER_STYLE.CIRCLE
        series.marker.size = 11


def set_line_properties(chart, chart_data):
    """A trend: thick smooth lines, a second one (the punchline) in the punchline's colour, and no numbers on the axes
    (their titles say what they are). The value axis starts at 0, or PowerPoint would zoom in on a flat line until its
    noise looks like a rollercoaster."""
    for index, series in enumerate(chart.plots[0].series):
        series.smooth = True
        series.format.line.width = Pt(5)
        if index == 1:
            series.format.line.color.rgb = PUNCHLINE_COLOUR
    for axis in (chart.category_axis, chart.value_axis):
        axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
        _without_tick_marks(axis)
    chart.value_axis.has_major_gridlines = False
    chart.value_axis.minimum_scale = 0
    _legend_for_named_series(chart)


def set_bar_properties(chart, chart_data):
    """A ranking: bars without numbers, from a line on the left, all grey but the last one, the punchline, in its
    colour."""
    chart.has_legend = False
    value_axis = chart.value_axis
    value_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
    _without_tick_marks(value_axis)
    value_axis.has_major_gridlines = False
    value_axis.format.line.fill.background()  # (no line along the bottom, under the axis's title if it has one)
    category_axis = chart.category_axis
    _without_tick_marks(category_axis)
    category_axis.tick_labels.font.size = Pt(LABEL_SIZE)
    plot = chart.plots[0]
    plot.gap_width = 60
    plot.vary_by_categories = False
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = RUNNER_UP_COLOUR
    if len(chart_data.categories):
        punchline = series.points[len(chart_data.categories) - 1].format.fill
        punchline.solid()
        punchline.fore_color.rgb = PUNCHLINE_COLOUR


def _legend_for_named_series(chart) -> None:
    """A legend at the bottom for the series that have a name (and none if no series has one)."""
    names = [series.name for series in chart.plots[0].series]
    chart.has_legend = any(names)
    if not any(names):
        return
    legend = chart.legend
    legend.position = XL_LEGEND_POSITION.BOTTOM
    legend.include_in_layout = False
    legend.font.size = Pt(TEXT_SIZE)
    # The series without a name stay out of it (their entries come right after the legend's position)
    previous = legend._element.find(qn("c:legendPos"))
    for index, name in enumerate(names):
        if name:
            continue
        entry = parse_xml(f'<c:legendEntry {nsdecls("c")}><c:idx val="{index}"/><c:delete val="1"/></c:legendEntry>')
        if previous is None:
            legend._element.insert(0, entry)
        else:
            previous.addnext(entry)
        previous = entry


def set_axis_titles(chart, spec: ChartSpec) -> None:
    """Title the axes of a chart that has axes, as its spec says (the category axis: what the chart goes along)."""
    if spec.chart_type not in AXIS_CHART_TYPES:
        return
    for axis, title in ((chart.category_axis, spec.x_title), (chart.value_axis, spec.y_title)):
        if title:
            axis.has_title = True
            axis.axis_title.text_frame.text = title
            axis.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(LABEL_SIZE)


def label_points(chart, spec: ChartSpec, look: ChartLook = CLASSIC_LOOK, width: int | None = None) -> None:
    """Point out the points that the spec names, on a line or scatter chart: a big dot, with its name above it, on
    one line (rather than piled up in three over the chart's line).

    Given the chart's width (in EMU, to measure the name against), a trend's name goes to the side its line leaves
    free, as far as it fits in the plot: it ends by the dot where the line climbs on after it (as a hockey stick
    does), and starts there where the line comes down to it. (PowerPoint centres a name that it doesn't wrap on its
    dot, whatever the label's position says, so the name is moved over by hand.)"""
    if spec.chart_type not in ("line", "scatter"):
        return
    for series, spec_series in zip(chart.plots[0].series, spec.series, strict=False):
        for index, label in enumerate(spec_series.labels):
            if not label:
                continue
            point = series.points[index]
            point.marker.style = XL_MARKER_STYLE.CIRCLE
            point.marker.size = 18
            point.marker.format.fill.solid()
            point.marker.format.fill.fore_color.rgb = look.punchline
            point.marker.format.line.color.rgb = look.punchline
            data_label = point.data_label
            _write(data_label, label, bold=True)
            data_label.position = XL_LABEL_POSITION.ABOVE
            # On one line: PowerPoint keeps to that only when both the text and the label's own text properties say so
            data_label.text_frame.word_wrap = False
            dLbl = data_label._get_or_add_dLbl()
            dLbl.get_or_add_txPr().find(qn("a:bodyPr")).set("wrap", "none")
            if spec.chart_type != "line" or not width:
                continue
            name = fonts.text_width(label, look.font, LABEL_SIZE, bold=True) * _EMU_PER_POINT / width
            shift = _name_shift(spec_series.values, index, name, _DOT_GAP * _EMU_PER_POINT / width)
            if abs(shift) > 0.001:
                layout = f'<c:manualLayout><c:x val="{shift:.4f}"/><c:y val="0"/></c:manualLayout>'
                dLbl.find(qn("c:tx")).addprevious(parse_xml(f"<c:layout {nsdecls('c')}>{layout}</c:layout>"))


def _name_shift(values: Sequence[float], index: int, name: float, gap: float) -> float:
    """How far a trend's named point's name moves over from above its dot, given its width and its gap to the dot:
    all as shares of the chart's width. It goes to the side the line leaves free, as far as it fits in the plot (a
    line's points are in the middle of their categories)."""
    left, right = _PLOT_SPAN
    dot = left + (index + 0.5) / max(1, len(values)) * (right - left)
    middle = dot + _free_side(values, index) * (gap + name / 2)
    if name >= right - left:
        return (left + right) / 2 - dot
    return min(max(middle, left + name / 2), right - name / 2) - dot


def _free_side(values: Sequence[float], index: int) -> int:
    """The side of a trend's point that its line leaves free for the point's name: -1, the left, when the line climbs
    on after the point (as a hockey stick does); 1, the right, when the line comes down to it; and 0 otherwise (at a
    peak, say), for above it."""
    if not 0 <= index < len(values):
        return 0
    level = values[index] + 0.05 * max(*values, 1.0)
    before = max(values[max(0, index - 2) : index], default=values[index])
    after = max(values[index + 1 : index + 3], default=values[index])
    if after > level >= before:
        return -1
    if before > level >= after:
        return 1
    return 0


def finish(chart, look: ChartLook = CLASSIC_LOOK) -> None:
    """Draw the chart's texts and lines in the look: every text in its colour and font, the axes in thin lines of its
    own colour, and a pie's slices apart by lines of the background's colour.

    That includes the texts the styles wrote themselves, such as a slice's name or an axis's title: PowerPoint draws
    those in black otherwise, whatever the chart's font says, which made them black on the classic template's black,
    and on dark themes. A text that has its colour already, such as a share on a doughnut's slice, keeps it."""
    chart.font.size = Pt(TEXT_SIZE)
    space = chart._chartSpace
    for properties in [*space.xpath(".//c:txPr//a:defRPr"), *(run.get_or_add_rPr() for run in space.xpath(".//a:r"))]:
        font = Font(properties)
        if font.color.type is None:
            font.color.rgb = look.text
        font.name = look.font
    for axis in _axes(chart):
        line = axis.format.line
        if line.fill.type != MSO_FILL.BACKGROUND:  # (unless the style left the line out)
            line.color.rgb = look.line
            line.width = Pt(1.25)
    if chart.chart_type in (XL_CHART_TYPE.PIE, XL_CHART_TYPE.DOUGHNUT):
        plot = chart.plots[0]
        for series in plot.series:
            for index in range(len(plot.categories)):
                outline = series.points[index].format.line
                outline.color.rgb = look.background
                outline.width = Pt(2)


def _axes(chart) -> list[Any]:
    """The chart's axes: none for a pie or a doughnut."""
    axes = []
    for name in ("category_axis", "value_axis"):
        try:
            axes.append(getattr(chart, name))
        except ValueError:
            pass
    return axes


CHART_STYLES: dict[ChartType, Callable[[Any, Any], Any]] = {
    "pie": set_pie_properties,
    "doughnut": set_doughnut_properties,
    "column": set_histogram_properties,
    "bar": set_bar_properties,
    "line": set_line_properties,
    "scatter": set_scatter_properties,
}
