"""Charts in PowerPoint: deck chart data to python-pptx chart data and back, and the classic chart styles.

A deck only holds a chart's numbers (`ChartSpec`); the renderer rebuilds the python-pptx chart data from them and
styles the chart by its type, the way the 2019 generator did.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any

from pptx.chart.data import CategoryChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_MARK

from talkgenerator.models.deck import ChartSeries, ChartSpec, ChartType

PPTX_CHART_TYPES: dict[ChartType, XL_CHART_TYPE] = {
    "pie": XL_CHART_TYPE.PIE,
    "doughnut": XL_CHART_TYPE.DOUGHNUT,
    "column": XL_CHART_TYPE.COLUMN_CLUSTERED,
    "scatter": XL_CHART_TYPE.XY_SCATTER,
}
_DECK_CHART_TYPES: dict[XL_CHART_TYPE, ChartType] = {pptx_type: name for name, pptx_type in PPTX_CHART_TYPES.items()}


def chart_spec(chart_type: XL_CHART_TYPE, chart_data: CategoryChartData | XyChartData) -> ChartSpec:
    """The deck's description of a python-pptx chart."""
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
        return ChartSpec(chart_type=deck_type, series=xy_series)
    categories = tuple(str(category.label) for category in chart_data.categories)
    category_series = tuple(
        ChartSeries(name=series.name or "", values=_finite(getattr(series, "values", ()))) for series in chart_data
    )
    return ChartSpec(chart_type=deck_type, categories=categories, series=category_series)


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


def _finite(values: Iterable[Any]) -> tuple[float, ...]:
    """The values as floats, with anything that JSON can't hold (NaN, infinity, nothing) as 0."""
    numbers = []
    for value in values:
        number = float(value) if value is not None else 0.0
        numbers.append(number if math.isfinite(number) else 0.0)
    return tuple(numbers)


# THE CLASSIC CHART STYLES (moved here unchanged from talkgenerator.sources.chart)


def _set_pie_label_positions(chart, series, chart_data, label_position):
    chart.plots[0].has_data_labels = True
    for i in range(len(chart_data.categories)):
        point = series.points[i]
        value = series.values[i]
        point.data_label.text_frame.text = "{} ({:.0%})".format(chart_data.categories[i].label, value)
        if label_position:
            point.data_label.position = label_position


def set_histogram_properties(chart, chart_data):
    value_axis = chart.value_axis
    value_axis.mayor_tick_mark = XL_TICK_MARK.NONE
    value_axis.minor_tick_mark = XL_TICK_MARK.NONE
    value_axis.has_mayor_gridlines = False
    value_axis.has_minor_gridlines = False
    # value_axis.visible = False

    tick_labels = value_axis.tick_labels
    tick_labels.number_format = "0%"

    return chart


def set_pie_properties(chart, chart_data):
    if chart and chart_data:
        chart.has_legend = False
        chart.has_title = False

        # Data points
        series = chart.series[0]
        # Check if there are small values that can't be contained on the pie piece
        label_position = (
            XL_LABEL_POSITION.OUTSIDE_END if any(t < 0.10 for t in series.values) else XL_LABEL_POSITION.CENTER
        )

        # set labels to contain category and value
        _set_pie_label_positions(chart, series, chart_data, label_position)


def set_doughnut_properties(chart, chart_data):
    if chart and chart_data:
        chart.has_legend = False
        series = chart.series[0]
        _set_pie_label_positions(chart, series, chart_data, None)


def set_scatter_properties(chart, chart_data):
    chart.has_legend = False


CHART_STYLES: dict[ChartType, Callable[[Any, Any], Any]] = {
    "pie": set_pie_properties,
    "doughnut": set_doughnut_properties,
    "column": set_histogram_properties,
    "scatter": set_scatter_properties,
}
