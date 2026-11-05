import math
import random

from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.render.charts import set_doughnut_properties, set_histogram_properties, set_pie_properties
from talkgenerator.sources import conceptnet, text_generator
from talkgenerator.util import generator_util

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


# DATA POINTS HELPERS


def add_noise_to_points(max_noise_ratio, datapoints):
    return [add_noise_to_point(max_noise_ratio, point) for point in datapoints]


def add_noise_to_point(max_noise_ratio, datapoint):
    return max(0, datapoint + (datapoint * random.uniform(-max_noise_ratio, max_noise_ratio)))


def add_gaussian_noise_to_multidim_points(max_noise_ratio, datapoints):
    return [_add_gaussian_noise_to_multidim_point(max_noise_ratio, point) for point in datapoints]


def _add_gaussian_noise_to_multidim_point(max_noise_ratio, datapoint):
    return [value * random.gauss(1, max_noise_ratio) for value in datapoint]


def normalise_data(datapoints):
    total_sum = sum(datapoints)
    return [datapoint / total_sum for datapoint in datapoints]


def is_too_similar_for_axes(word1, word2):
    """Checks if the words contain each other"""
    return word1 in word2 or word2 in word1


def create_interesting_curve_function():
    # Build an optional list

    # random small integer
    a = random.uniform(-10, 10)
    _b = random.uniform(0.001, 10)

    # random relative
    _r = random.uniform(0, 1)

    interesting_functions = [
        lambda x: a * x,
        lambda x: a / x,
        lambda x: a + x,
        lambda x: a - x,
        # lambda x: min(float(5e8), float(a ** math.log(x))),
        # lambda x: min(float(5e8), float(x ** math.log(a))),
        lambda x: math.sin(x),
    ]

    chosen = random.choice(interesting_functions)

    # Add chance of adding another function
    # random_number = random.uniform(0, 1)
    # if random_number < 0.4:
    #     chosen = lambda x: random.choice(interesting_functions)(chosen(x))
    # elif random_number < 0.8:
    #     chosen = lambda x: random.choice(interesting_functions)(x) * chosen(x)
    # else:
    #     chosen = lambda x: random.choice(interesting_functions)(x) + chosen(x)

    return chosen


# DATA SET CREATION


def create_equal_data_with_outlier_end(size, noise_factor, normal_min, normal_max, outlier_min_size, outlier_max_size):
    # Create data with same number between normal_min and normal_max everywhere
    datapoints = [random.uniform(normal_min, normal_max) for _ in range(0, size)]

    # Make last number an outlier
    datapoints[-1] = random.uniform(outlier_min_size, outlier_max_size)

    # Apply noise
    datapoints = add_noise_to_points(noise_factor, datapoints)

    return datapoints


def generate_random_x(lower_bound, upper_bound, number):
    return [random.uniform(lower_bound, upper_bound) for _ in range(number)]


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
        random.shuffle(conceptnet_relations)

        conceptnet_relations = conceptnet_relations[0 : random.randint(2, 5)]
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
    chart_type, chart_modifier = random.choice(_YES_NO_CHART_TYPES)
    return title, chart_type, chart_data, chart_modifier


def generate_location_pie(presentation_context):
    result = generate_location_data(presentation_context)
    if result:
        title, chart_data = result
        chart_type, chart_modifier = random.choice(_YES_NO_CHART_TYPES)
        return title, chart_type, chart_data, chart_modifier


def generate_property_pie(presentation_context):
    result = generate_property_data(presentation_context)
    if result:
        title, chart_data = result
        chart_type, chart_modifier = random.choice(_YES_NO_CHART_TYPES)
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
    xs = generate_random_x(0, 2 ** random.uniform(1, 10), int(2 ** random.uniform(3, 8)))

    # Generate y
    data_points = generate_y(xs, create_interesting_curve_function())

    max_x = max(xs)

    data_points = add_gaussian_noise_to_multidim_points(1.5 * random.uniform(0, max_x / 10), data_points)

    # Remove negatives
    data_points = [(abs(datapoint[0]), abs(datapoint[1])) for datapoint in data_points]

    add_data_to_series(serie, data_points)

    return (
        title,
        XL_CHART_TYPE.XY_SCATTER,
        chart_data,
        create_set_scatter_properties(x_label, y_label),
    )
