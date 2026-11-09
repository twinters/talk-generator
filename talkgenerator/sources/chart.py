import math
from collections.abc import Callable, Sequence
from typing import Any, Final

from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.models.deck import Trendline
from talkgenerator.render.charts import set_doughnut_properties, set_histogram_properties, set_pie_properties
from talkgenerator.sources import conceptnet, packs
from talkgenerator.util import generator_util, language_util, random_util

yes_no_question_generator = packs.pack(packs.TED).tracery("charts.yes_no_question")
funny_yes_no_answer_generator = packs.pack(packs.TED).tracery("charts.funny_yes_no_answer")
location_question_generator = packs.pack(packs.TED).tracery("charts.location_question")
property_question_generator = packs.pack(packs.TED).tracery("charts.property_question")
correlation_title_generator = packs.pack(packs.TED).tracery("charts.correlation_title")
ranking_title_generator = packs.pack(packs.TED).tracery("charts.ranking_title")
trend_event_generator = packs.pack(packs.TED).tracery("charts.trend_event")
x_axis_title_generator = packs.pack(packs.TED).tracery("charts.x_axis_title")
y_axis_title_generator = packs.pack(packs.TED).tracery("charts.y_axis_title")
# How often a classic chart goes without axis titles, for the presenter to explain
BARE_CHARTS: Final = 1 / 3


def axis_titles(presentation_context: dict[str, Any]) -> tuple[str | None, str | None]:
    """Funny titles for the axes of a classic chart, from templates about its x_label and y_label, or none (for a
    third of the charts)."""
    if random_util.random() < BARE_CHARTS:
        return None, None
    return x_axis_title_generator(presentation_context), y_axis_title_generator(presentation_context)


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
    # (an axis is a thing: not an antonym such as "dormant", D67)
    if is_too_similar_for_axes(x_label, y_label) or not language_util.is_thing(str(x_label)):
        x_label = "time"
    presentation_context.update({"x_label": x_label, "y_label": y_label})

    title = correlation_title_generator(presentation_context)

    if not title:
        return None

    # A cloud of one of the shapes, or now and then two or three named clouds: things related to the seed
    clusters = _classic_clusters(str(y_label)) if random_util.random() < CLUSTER_ODDS else []
    chart_data, trendlines, labels = correlation_data(None, clusters)
    x_title, y_title = axis_titles(presentation_context)
    return (
        title,
        XL_CHART_TYPE.XY_SCATTER,
        chart_data,
        create_set_scatter_properties(x_label, y_label),
        x_title,
        y_title,
        "all",
        tuple(labels),
        tuple(trendlines),
    )


# How often a classic correlation is of two or three named clouds (as planned ones are, in their variant)
CLUSTER_ODDS: Final = 0.3


def _classic_clusters(seed: str) -> list[str]:
    """Two or three words related to the seed (capitalised), as a correlation's clouds' names: none if ConceptNet
    has too few."""
    related = conceptnet.remove_containing(conceptnet.related_things(seed, 30), seed) or []
    words = [str(word) for _, word in conceptnet.remove_duplicates(related) or [] if len(str(word)) <= 20]
    if len(words) < 2:
        return []
    chosen = random_util.sample(words, min(len(words), random_util.randint(2, MOST_CLUSTERS)))
    return [word[:1].upper() + word[1:] for word in chosen]


# CORRELATIONS: clouds of points in one of these shapes (each a curve over 0 to 1; the ring and the smile have points
# of their own: see correlation_points), with a little noise or a lot (docs/v5-plan.md, D64)
CORRELATION_SHAPES: Final[dict[str, Callable[[float], float] | None]] = {
    "rising": lambda x: 0.1 + 0.8 * x,
    "falling": lambda x: 0.9 - 0.8 * x,
    "exponential": lambda x: 0.05 + 0.9 * (math.exp(4 * x) - 1) / (math.exp(4) - 1),
    "saturating": lambda x: 0.05 + 0.9 * math.log1p(9 * x) / math.log(10),
    "u-shaped": lambda x: 0.1 + 0.8 * (2 * x - 1) ** 2,
    "hill": lambda x: 0.1 + 0.8 * math.sin(math.pi * x),
    "wave": lambda x: 0.5 + 0.35 * math.sin(5 * math.pi * x),
    "step": lambda x: 0.2 if x < 0.55 else 0.8,
    "none": None,  # (no correlation at all: a blob)
    "ring": None,  # (a perfect circle)
    "smile": None,  # (a smiling face)
}
# How often each comes up, where the plan doesn't say (the silly ones less often)
_CORRELATION_WEIGHTS: Final = {
    "rising": 3.0,
    "falling": 2.0,
    "exponential": 2.0,
    "saturating": 1.5,
    "u-shaped": 1.5,
    "hill": 1.5,
    "wave": 1.0,
    "step": 1.0,
    "none": 1.5,
    "ring": 0.5,
    "smile": 0.5,
}
# How loose a cloud is: the spread of its noise, as a share of the chart's height
_NOISES: Final = (0.02, 0.05, 0.09, 0.15)
# How often a correlation has a line fitted through it (of those with one cloud), and a parabola rather than a line
TRENDLINE_ODDS: Final = 0.35
_PARABOLAS: Final = 0.35
MOST_CLUSTERS: Final = 3


def correlation_points(shape: str | None = None) -> tuple[str, list[tuple[float, float]]]:
    """A cloud of points in the shape (one of CORRELATION_SHAPES; a random one, by their weights, for none), from a
    dozen to a hundred and fifty of them, as tight or as loose as the dice say, on axes of a size of their own (x up to
    10, 100 or 1000, say): none below 0."""
    if shape not in CORRELATION_SHAPES:
        shape = random_util.weighted_random([(weight, name) for name, weight in _CORRELATION_WEIGHTS.items()])
    assert shape is not None
    count = int(2 ** random_util.uniform(3.6, 7.2))
    noise = random_util.choice(_NOISES)
    unit_x, unit_y = 10 ** random_util.randint(1, 3), 10 ** random_util.randint(1, 3)
    points: list[tuple[float, float]] = []
    if shape == "ring":
        for _ in range(count):
            angle = random_util.uniform(0, 2 * math.pi)
            points.append((0.5 + 0.4 * math.cos(angle), 0.5 + 0.4 * math.sin(angle)))
    elif shape == "smile":
        for _ in range(count):
            part = random_util.random()
            if part < 0.6:  # (the mouth)
                x = random_util.uniform(0.2, 0.8)
                points.append((x, 0.2 + 1.2 * (x - 0.5) ** 2))
            else:  # (the eyes)
                points.append((random_util.choice((0.33, 0.67)) + random_util.gauss(0, 0.02), 0.75))
    else:
        curve = CORRELATION_SHAPES[shape]
        for _ in range(count):
            x = random_util.uniform(0.02, 0.98)
            points.append((x, curve(x) if curve is not None else random_util.uniform(0.15, 0.85)))
    noisy = [
        (max(0.0, (x + random_util.gauss(0, noise / 3)) * unit_x), max(0.0, (y + random_util.gauss(0, noise)) * unit_y))
        for x, y in points
    ]
    return shape, [(round(x, 3), round(y, 3)) for x, y in noisy]


def cluster_points(count: int) -> list[list[tuple[float, float]]]:
    """Clouds of points of their own, that many (two or three): each round or stretched, tight or loose, around a
    middle of its own, apart from the others, of ten to sixty points."""
    unit_x, unit_y = 10 ** random_util.randint(1, 3), 10 ** random_util.randint(1, 3)
    middles: list[tuple[float, float]] = []
    for attempt in range(200):  # (far enough apart that every cloud reads as one, as far as the dice allow)
        middle = (random_util.uniform(0.2, 0.8), random_util.uniform(0.2, 0.8))
        if all(math.dist(middle, other) > 0.32 for other in middles) or attempt >= 150:
            middles.append(middle)
        if len(middles) == count:
            break
    clouds = []
    for x0, y0 in middles:
        spread_x, spread_y = random_util.uniform(0.03, 0.09), random_util.uniform(0.03, 0.09)
        tilt = random_util.uniform(-1, 1)  # (how its points lean: up, along, or down)
        cloud = []
        for _ in range(random_util.randint(10, 60)):
            dx = random_util.gauss(0, spread_x)
            dy = random_util.gauss(0, spread_y) + tilt * dx
            cloud.append((round(max(0.0, (x0 + dx) * unit_x), 3), round(max(0.0, (y0 + dy) * unit_y), 3)))
        clouds.append(cloud)
    return clouds


def trendline_for(shape: str) -> Trendline | None:
    """A line fitted through a cloud of the shape, now and then (TRENDLINE_ODDS): a straight one, or a parabola,
    now and then (whatever the shape: a straight line through a U is a joke of its own); none for a ring or a
    smile."""
    if shape in ("ring", "smile") or random_util.random() >= TRENDLINE_ODDS:
        return None
    return "quadratic" if random_util.random() < _PARABOLAS else "linear"


def correlation_data(
    shape: str | None = None, clusters: Sequence[str] = (), outlier: str | None = None
) -> tuple[XyChartData, list[tuple[int, Trendline]], list[tuple[int, int, str]]]:
    """A scatter chart's data: a cloud in the shape (see correlation_points), or two or three named clouds of their
    own (the clusters' names, in their colours); one more point far above the others, named, if there's an outlier
    (its own series); and the lines fitted through it (a single cloud's, now and then: see trendline_for), and the
    named points, by series."""
    data = XyChartData()
    names = [name for name in clusters if name][:MOST_CLUSTERS]
    trendlines: list[tuple[int, Trendline]] = []
    if len(names) >= 2:
        clouds = cluster_points(len(names))
        for name, cloud in zip(names, clouds, strict=True):
            add_data_to_series(data.add_series(name), cloud)
    else:
        shape, points = correlation_points(shape)
        add_data_to_series(data.add_series(""), points)
        clouds = [points]
        trendline = trendline_for(shape)
        if trendline is not None:
            trendlines.append((0, trendline))
    labels: list[tuple[int, int, str]] = []
    if outlier:  # one point far above the others
        every = [point for cloud in clouds for point in cloud]
        highest = max((y for _, y in every), default=1.0)
        widest = max((x for x, _ in every), default=1.0)
        data.add_series(outlier).add_data_point(widest * random_util.uniform(0.4, 0.8), highest * 1.4 or 1)
        labels.append((len(clouds), 0, outlier))
    return data, trendlines, labels


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
    """A classic trend: the slide's seed, going some way along the topic (or along time, if they're alike), and half
    of the time a moment on it, where its line turns."""
    x_label = presentation_context["topic"]
    y_label = presentation_context["seed"]
    if is_too_similar_for_axes(x_label, y_label):
        x_label = "time"
    presentation_context.update({"x_label": x_label, "y_label": y_label})
    title = correlation_title_generator(presentation_context)
    if not title:
        return None
    shape, values = trend_values(None)
    event = trend_event_generator(presentation_context) if random_util.random() < 0.5 else None
    labels = ((0, trend_turn(shape), event),) if event else ()
    x_title, y_title = axis_titles(presentation_context)
    return title, XL_CHART_TYPE.LINE, trend_chart_data([("", values)]), None, x_title, y_title, "all", labels


def trend_boxes(generated: tuple[Any, ...]) -> dict[str, str]:
    """A classic trend's "box" that can have a picture: its named moment (as its point labels have it, after its
    title, type, data, style, axis titles and how it appears), by the point (docs/v5-plan.md, D64)."""
    labels = generated[7] if len(generated) > 7 else ()
    return {"event": str(label)} if (label := next((name for _, _, name in labels if name), None)) else {}


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
