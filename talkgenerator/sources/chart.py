import math
from collections.abc import Callable
from typing import Any, Final

from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.render.charts import set_doughnut_properties, set_histogram_properties, set_pie_properties
from talkgenerator.sources import conceptnet, text_generator
from talkgenerator.util import generator_util, random_util

yes_no_question_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "yes_no_question"
).generate
funny_yes_no_answer_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "funny_yes_no_answer"
).generate
location_question_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "location_question"
).generate
property_question_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "property_question"
).generate
correlation_title_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "correlation_title"
).generate
ranking_title_generator = text_generator.TraceryTextGenerator(
    "data/text-templates/chart_texts.json", "ranking_title"
).generate


# DATA POINTS HELPERS


def add_noise_to_points(max_noise_ratio, datapoints):
    return [add_noise_to_point(max_noise_ratio, point) for point in datapoints]


def add_noise_to_point(max_noise_ratio, datapoint):
    return max(0, datapoint + (datapoint * random_util.uniform(-max_noise_ratio, max_noise_ratio)))


def add_gaussian_noise_to_multidim_points(max_noise_ratio, datapoints):
    return [_add_gaussian_noise_to_multidim_point(max_noise_ratio, point) for point in datapoints]


def _add_gaussian_noise_to_multidim_point(max_noise_ratio, datapoint):
    return [value * random_util.gauss(1, max_noise_ratio) for value in datapoint]


def normalise_data(datapoints):
    total_sum = sum(datapoints)
    return [datapoint / total_sum for datapoint in datapoints]


def is_too_similar_for_axes(word1, word2):
    """Checks if the words contain each other"""
    return word1 in word2 or word2 in word1


def create_interesting_curve_function():
    # Build an optional list

    # random small integer
    a = random_util.uniform(-10, 10)
    _b = random_util.uniform(0.001, 10)

    # random relative
    _r = random_util.uniform(0, 1)

    interesting_functions = [
        lambda x: a * x,
        lambda x: a / x,
        lambda x: a + x,
        lambda x: a - x,
        # lambda x: min(float(5e8), float(a ** math.log(x))),
        # lambda x: min(float(5e8), float(x ** math.log(a))),
        lambda x: math.sin(x),
    ]

    chosen = random_util.choice(interesting_functions)

    # Add chance of adding another function
    # random_number = random_util.uniform(0, 1)
    # if random_number < 0.4:
    #     chosen = lambda x: random_util.choice(interesting_functions)(chosen(x))
    # elif random_number < 0.8:
    #     chosen = lambda x: random_util.choice(interesting_functions)(x) * chosen(x)
    # else:
    #     chosen = lambda x: random_util.choice(interesting_functions)(x) + chosen(x)

    return chosen


# DATA SET CREATION


def create_equal_data_with_outlier_end(size, noise_factor, normal_min, normal_max, outlier_min_size, outlier_max_size):
    # Create data with same number between normal_min and normal_max everywhere
    datapoints = [random_util.uniform(normal_min, normal_max) for _ in range(0, size)]

    # Make last number an outlier
    datapoints[-1] = random_util.uniform(outlier_min_size, outlier_max_size)

    # Apply noise
    datapoints = add_noise_to_points(noise_factor, datapoints)

    return datapoints


def generate_random_x(lower_bound, upper_bound, number):
    return [random_util.uniform(lower_bound, upper_bound) for _ in range(number)]


def generate_y(xs, function):
    return [(x, function(x)) for x in xs]


# CHART TYPES PROPERTIES SETTING


def add_data_to_series(serie, data_points):
    for data_point in data_points:
        x, y = data_point
        serie.add_data_point(x, y)


# The pie, doughnut and histogram styles live in talkgenerator.render.charts now: the renderer styles every chart
# by its type, so that a chart drawn from a deck looks the same as one drawn straight from its slide.


def create_set_scatter_properties(x_label, y_label):
    def set_scatter_properties(chart, chart_data):
        chart.has_legend = False

        # TODO: Fix it so that this actually has a title
        # x_axis.has_title = True
        # y_axis.has_title = True

    return set_scatter_properties


# CHART TYPES
PIE = XL_CHART_TYPE.PIE, set_pie_properties
PROCENT_HISTOGRAM = XL_CHART_TYPE.COLUMN_CLUSTERED, set_histogram_properties
DOUGHNUT = XL_CHART_TYPE.DOUGHNUT, set_doughnut_properties

# CHART DATA GENERATOR

_YES_NO_CHART_TYPES = PIE, PROCENT_HISTOGRAM, DOUGHNUT


def generate_yes_no_large_funny_answer_chart_data(presentation_context):
    title = yes_no_question_generator(presentation_context)

    presentation_context["chart_title"] = title

    categories = ["Yes", "No", funny_yes_no_answer_generator(presentation_context)]
    series_data = normalise_data(create_equal_data_with_outlier_end(len(categories), 0.2, 1, 2.5, 1, 20))

    chart_data = ChartData()
    chart_data.categories = categories
    chart_data.add_series("", series_data)
    return title, chart_data


def _generate_conceptnet_data(presentation_context, title_generator, conceptnet_function):
    seed = presentation_context["seed"]
    title = title_generator(presentation_context)

    presentation_context["chart_title"] = title

    conceptnet_relations = conceptnet_function(seed)

    if conceptnet_relations:
        conceptnet_relations = conceptnet.remove_duplicates(conceptnet_relations)
        conceptnet_relations = conceptnet.remove_containing(conceptnet_relations, seed)
        random_util.shuffle(conceptnet_relations)

        conceptnet_relations = conceptnet_relations[0 : random_util.randint(2, 5)]
        categories = [location[1] for location in conceptnet_relations]
        values = [float(location[0]) ** 2 for location in conceptnet_relations]

        if len(categories) == 0:
            return None
        series_data = normalise_data(values)

        chart_data = ChartData()
        chart_data.categories = categories
        chart_data.add_series("", series_data)
        return title, chart_data


def generate_location_data(presentation_context):
    return _generate_conceptnet_data(
        presentation_context,
        location_question_generator,
        conceptnet.get_weighted_related_locations,
    )


def generate_property_data(presentation_context):
    return _generate_conceptnet_data(
        presentation_context,
        property_question_generator,
        conceptnet.get_weighted_properties,
    )


# FULL CHART GENERATORS


def generate_yes_no_pie(presentation_context):
    title, chart_data = generate_yes_no_large_funny_answer_chart_data(presentation_context)
    chart_type, chart_modifier = random_util.choice(_YES_NO_CHART_TYPES)
    return title, chart_type, chart_data, chart_modifier


def generate_location_pie(presentation_context):
    result = generate_location_data(presentation_context)
    if result:
        title, chart_data = result
        chart_type, chart_modifier = random_util.choice(_YES_NO_CHART_TYPES)
        return title, chart_type, chart_data, chart_modifier


def generate_property_pie(presentation_context):
    result = generate_property_data(presentation_context)
    if result:
        title, chart_data = result
        chart_type, chart_modifier = random_util.choice(_YES_NO_CHART_TYPES)
        return title, chart_type, chart_data, chart_modifier


_CORRELATION_WORD_GENERATOR = generator_util.WalkingGenerator(
    generator_util.CombinedGenerator(
        (2, conceptnet.unweighted_antonym_generator),
        (1, conceptnet.unweighted_related_word_generator),
    ),
    steps=5,
)


def generate_correlation_curve(presentation_context):
    x_label = presentation_context["topic"]
    y_label = presentation_context["seed"]

    if is_too_similar_for_axes(x_label, y_label):
        x_label = _CORRELATION_WORD_GENERATOR(y_label)
    if is_too_similar_for_axes(x_label, y_label):
        x_label = "time"
    presentation_context.update({"x_label": x_label, "y_label": y_label})

    title = correlation_title_generator(presentation_context)

    if not title:
        return None

    chart_data = XyChartData()

    serie = chart_data.add_series("Model")

    # Generate some Xs, with chance of exponential differences in size between generated x axes
    xs = generate_random_x(0, 2 ** random_util.uniform(1, 10), int(2 ** random_util.uniform(3, 8)))

    # Generate y
    data_points = generate_y(xs, create_interesting_curve_function())

    max_x = max(xs)

    data_points = add_gaussian_noise_to_multidim_points(1.5 * random_util.uniform(0, max_x / 10), data_points)

    # Remove negatives
    data_points = [(abs(datapoint[0]), abs(datapoint[1])) for datapoint in data_points]

    add_data_to_series(serie, data_points)

    return (
        title,
        XL_CHART_TYPE.XY_SCATTER,
        chart_data,
        create_set_scatter_properties(x_label, y_label),
        x_label,
        y_label,
    )


# TRENDS: a line along two axes, going one of these ways (each a curve over 0 to 1)
TREND_SHAPES: Final[dict[str, Callable[[float], float]]] = {
    "rising": lambda x: x,
    "falling": lambda x: 1 - x,
    "exponential": lambda x: (math.exp(4 * x) - 1) / (math.exp(4) - 1),
    "diminishing": lambda x: math.log1p(9 * x) / math.log(10),
    "hockey stick": lambda x: 0.1 * x if x < 0.75 else 0.075 + (x - 0.75) * 3.7,
    "peak": lambda x: math.sin(math.pi * x),
    "crash": lambda x: 0.05 + 0.9 * x if x < 0.8 else 0.05,
    "plateau": lambda x: 1 / (1 + math.exp(-12 * (x - 0.35))),
    "rollercoaster": lambda x: 0.5 + 0.4 * math.sin(3 * math.pi * x),
    "dip": lambda x: (2 * x - 1) ** 2,
    "flat": lambda x: 0.5,
}
TREND_POINTS: Final = 12
# Where on each shape something happens (as a share of the way along): where it takes off, turns or drops
_TREND_TURNS: Final[dict[str, float]] = {
    "rising": 0.5,
    "falling": 0.5,
    "exponential": 0.7,
    "diminishing": 0.3,
    "hockey stick": 0.75,
    "peak": 0.5,
    "crash": 0.75,
    "plateau": 0.5,
    "rollercoaster": 0.2,
    "dip": 0.5,
    "flat": 0.5,
}


def trend_values(shape: str | None, avoid: str | None = None) -> tuple[str, list[float]]:
    """A trend line's values, going the way its shape says, with some noise. Without a shape (or with one that
    isn't in TREND_SHAPES), a random one, other than the one to avoid (a first line's, for a second line)."""
    if shape not in TREND_SHAPES:
        shape = random_util.choice([name for name in TREND_SHAPES if name != avoid])
    curve = TREND_SHAPES[shape]
    values = [
        100 * max(0.0, curve(point / (TREND_POINTS - 1)) + random_util.gauss(0, 0.03)) for point in range(TREND_POINTS)
    ]
    return shape, values


def trend_turn(shape: str) -> int:
    """The point of a trend line where something happens, for its shape: where it takes off, turns or drops."""
    return round(_TREND_TURNS.get(shape, 0.5) * (TREND_POINTS - 1))


def trend_chart_data(lines: list[tuple[str, list[float]]]) -> ChartData:
    """The chart data of trend lines: (name, values) each, along unnamed points."""
    chart_data = ChartData()
    chart_data.categories = [str(point) for point in range(1, TREND_POINTS + 1)]
    for name, values in lines:
        chart_data.add_series(name, values)
    return chart_data


def generate_trend_chart(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
    """A classic trend: the slide's seed, going some way along the topic (or along time, if they're alike)."""
    x_label = presentation_context["topic"]
    y_label = presentation_context["seed"]
    if is_too_similar_for_axes(x_label, y_label):
        x_label = "time"
    presentation_context.update({"x_label": x_label, "y_label": y_label})
    title = correlation_title_generator(presentation_context)
    if not title:
        return None
    _, values = trend_values(None)
    return title, XL_CHART_TYPE.LINE, trend_chart_data([("", values)]), None, x_label, y_label


# RANKINGS: bars, the last of which, the punchline, wins by far


def ranking_chart_data(bars: list[str]) -> ChartData:
    values = sorted(random_util.uniform(10, 40) for _ in bars[:-1]) + [random_util.uniform(80, 100)]
    chart_data = ChartData()
    chart_data.categories = bars
    chart_data.add_series("", values)
    return chart_data


def generate_ranking_bars(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
    """A classic ranking: things related to the slide's seed, beaten by far by the seed itself."""
    seed = presentation_context["seed"]
    related = conceptnet.remove_containing(conceptnet.get_weighted_related_words(seed, 30), seed) or []
    words = [word for _, word in conceptnet.remove_duplicates(related) or []]
    if len(words) < 3:
        return None
    title = ranking_title_generator(presentation_context)
    if not title:
        return None
    bars = [*random_util.sample(words, 3), seed]
    return title, XL_CHART_TYPE.BAR_CLUSTERED, ranking_chart_data(bars), None
