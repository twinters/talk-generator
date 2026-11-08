from talkgenerator.datastructures.slide_generator_data import (
    BetweenWeight,
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.plan.kinds import Recipe, Variant
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.registry import Registry
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import chart, diagram, memes, slide_texts
from talkgenerator.util.generator_util import CombinedGenerator, NoneGenerator

# ==============================
# =====  SLIDE GENERATORS  =====
# ==============================

# Every slide generator is registered under its (unique) name, in a group that schemas pick from.
# Its `llm` recipe says how a language model fills this kind of slide (talkgenerator.plan.kinds): which slide shape,
# which of the same image sources, and what to write. Without a recipe, a slide is always classic.
slide_generators: Registry[SlideGeneratorData] = Registry("slide generator")


def _register(group: str, generators: list[SlideGeneratorData]) -> list[SlideGeneratorData]:
    for generator in generators:
        slide_generators.register(generator.name or "", generator, group=group)
    return generators


# What some recipes share
_ABOUT_ME_TITLE = "a title such as 'About me' or 'Who am I?'"
_FROM = "where the presenter comes from: a country, a city or a place"
_JOB = "the presenter's (possibly made-up) job"
_HOBBY = "the presenter's weird hobby"
# (With "like 'Expectation' and 'Reality'" here, a third of the talks had an "Expectation vs Reality" slide)
_CONTRAST = "Two captioned images that contrast or compare: two sides, two eras, or two kinds of one thing"
_SEQUENCE = "Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan"
_CONCLUSIONS_TITLE = "a title for the conclusions, in a few words of your own"


def _conclusions(number: int) -> dict[str, str]:
    hints = {"title": _CONCLUSIONS_TITLE}
    for nr in range(1, number + 1):
        hints[f"caption_{nr}"] = "a lesson from the talk, calling back to an earlier slide"
    return hints


# TITLE SLIDE
title_slide_generators = _register(
    "title",
    [
        SlideGeneratorData(
            slide_generator_types.TitleSlideGenerator.of(
                cg.talk_title_generator_if_not_generated, cg.talk_subtitle_generator
            ),
            allowed_repeated_elements=3,
            weight_function=PeakedWeight((0,), 100000, 0),
            tags=["title"],
            name="Title slide",
            llm=Recipe("title"),
        )
    ],
)

# ABOUT ME
about_me_slide_generators = _register(
    "about_me",
    [
        SlideGeneratorData(
            # slide_templates.generate_three_column_images_slide_tuple(
            slide_generator_types.ThreeColumnImageSlideGenerator.of_tupled_captioned_images(
                cg.about_me_title_generator,
                cg.about_me_location_or_country_tuple_generator,
                cg.about_me_job_tuple_generator,
                cg.about_me_hobby_tuple_generator,
            ),
            PeakedWeight((1,), 10, 0),
            allowed_repeated_elements=3,
            tags=["about_me"],
            name="About Me: Location-Job-WeirdHobby",
            llm=Recipe(
                "three_columns",
                (cg.country_image_generator, cg.neutral_image_generator, cg.hobby_image_generator),
                brief="About the presenter: where they come from, their job and their weird hobby",
                hints={"title": _ABOUT_ME_TITLE, "caption_1": _FROM, "caption_2": _JOB, "caption_3": _HOBBY},
            ),
        ),
        SlideGeneratorData(
            # slide_templates.generate_two_column_images_slide_tuple(
            slide_generator_types.TwoColumnImageSlideGenerator.of_tupled_captioned_images(
                cg.about_me_title_generator,
                cg.about_me_location_or_country_tuple_generator,
                cg.about_me_job_tuple_generator,
            ),
            PeakedWeight((1,), 4, 0),
            allowed_repeated_elements=3,
            tags=["about_me"],
            name="About Me: Location-Job",
            llm=Recipe(
                "two_columns",
                (cg.country_image_generator, cg.neutral_image_generator),
                brief="About the presenter: where they come from and their job",
                hints={"title": _ABOUT_ME_TITLE, "caption_1": _FROM, "caption_2": _JOB},
            ),
        ),
        SlideGeneratorData(
            # slide_templates.generate_three_column_images_slide_tuple(
            slide_generator_types.ThreeColumnImageSlideGenerator.of_tupled_captioned_images(
                cg.about_me_title_generator,
                cg.about_me_location_or_country_tuple_generator,
                cg.about_me_book_tuple_generator,
                cg.about_me_hobby_tuple_generator,
            ),
            PeakedWeight((1,), 4, 0),
            allowed_repeated_elements=0,
            tags=["about_me"],
            name="About Me: Location-Book-WeirdHobby",
            llm=Recipe(
                "three_columns",
                (cg.country_image_generator, cg.book_cover_generator, cg.hobby_image_generator),
                brief="About the presenter: where they come from, the book they wrote, and their weird hobby",
                hints={
                    "title": _ABOUT_ME_TITLE,
                    "caption_1": _FROM,
                    "caption_2": "the title of a book the presenter wrote",
                    "caption_3": _HOBBY,
                },
            ),
        ),
        SlideGeneratorData(
            # slide_templates.generate_image_slide_tuple(
            slide_generator_types.ImageSlideGenerator.of_tupled_captioned_image(cg.about_me_hobby_tuple_generator),
            PeakedWeight((1, 2), 3, 0),
            allowed_repeated_elements=0,
            tags=["about_me"],
            name="Weird Hobby",
            llm=Recipe(
                "image",
                (cg.hobby_image_generator,),
                brief="The presenter's weird hobby",
                hints={"title": _HOBBY},
            ),
        ),
    ],
)

# HISTORY
_HISTORY_QUOTE_BRIEF = "What a made-up historical figure once said about the slide's concept"
_HISTORY_PICTURES_BRIEF = "Two old photos from the history of the slide's concept"
_HISTORY_PICTURES_HINTS = {
    "title": "a title about the concept's history",
    "caption_1": "a moment from long ago",
    "caption_2": "a later moment",
}

history_slide_generators = _register(
    "history",
    [
        SlideGeneratorData(
            # slide_templates.generate_two_column_images_slide(
            slide_generator_types.TwoColumnImageSlideGenerator.of(
                cg.history_and_history_person_title_generator,
                cg.historical_name_generator,
                cg.vintage_person_generator,
                NoneGenerator(),
                cg.quote_generator,
            ),
            weight_function=PeakedWeight((2, 3), 20, 0.3),
            allowed_repeated_elements=0,
            tags=["history", "quote"],
            name="Historical Figure Quote",
            llm=Recipe("history_quote", (cg.historic_figure_generator,), brief=_HISTORY_QUOTE_BRIEF),
        ),
        SlideGeneratorData(
            # slide_templates.generate_two_column_images_slide_tuple_caption(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.history_title_generator,
                cg.historic_double_captions_generator,
                cg.vintage_picture_generator,
                cg.vintage_picture_generator,
            ),
            weight_function=PeakedWeight((2, 3), 12, 0.1),
            allowed_repeated_elements=0,
            tags=["history", "two_images"],
            name="Two History Pictures",
            llm=Recipe(
                "two_columns",
                (cg.historic_moment_generator, cg.historic_moment_generator),
                brief=_HISTORY_PICTURES_BRIEF,
                hints=_HISTORY_PICTURES_HINTS,
            ),
        ),
    ],
)
history_slide_generators_copyright_free = _register(
    "history_copyright_free",
    [
        SlideGeneratorData(
            # slide_templates.generate_two_column_images_slide(
            slide_generator_types.TwoColumnImageSlideGenerator.of(
                cg.history_and_history_person_title_generator,
                cg.historical_name_generator,
                cg.historic_person_copyright_free_generator,
                NoneGenerator(),
                cg.short_quote_generator,
            ),
            weight_function=PeakedWeight((1, 2), 20, 0.3),
            allowed_repeated_elements=2,
            tags=["history", "quote"],
            name="Historical Figure Quote (CRF)",
            llm=Recipe("history_quote", (cg.historic_figure_copyright_free_generator,), brief=_HISTORY_QUOTE_BRIEF),
        ),
        SlideGeneratorData(
            # slide_templates.generate_two_column_images_slide_tuple_caption(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.history_title_generator,
                cg.historic_double_captions_generator,
                cg.historic_copyright_free_generator,
                cg.historic_copyright_free_generator,
            ),
            weight_function=PeakedWeight((1, 2), 12, 0.1),
            allowed_repeated_elements=2,
            tags=["history", "two_images"],
            name="Two History Pictures (CRF)",
            llm=Recipe(
                "two_columns",
                (cg.historic_moment_generator, cg.historic_moment_generator),
                brief=_HISTORY_PICTURES_BRIEF,
                hints=_HISTORY_PICTURES_HINTS,
            ),
        ),
    ],
)


# FULL SCREEN RELATED IMAGES
# (Without an example: the free models wrote the example's teaser on every gif)
_TEASER = "two to four words of your own that build up to the gif, or empty for none"

single_image_slide_generators = _register(
    "single_image",
    [
        SlideGeneratorData(
            # slide_templates.generate_full_image_slide(
            slide_generator_types.FullImageSlideGenerator.of(
                cg.anticipation_title_generator, cg.combined_gif_generator
            ),
            tags=["full_image", "gif"],
            name="Full Screen Gif",
            llm=Recipe(
                "full_image", (cg.combined_gif_generator,), brief="A gif, filling the slide", hints={"title": _TEASER}
            ),
        ),
        SlideGeneratorData(
            # slide_templates.generate_image_slide(
            slide_generator_types.ImageSlideGenerator.of(cg.default_slide_title_generator, cg.combined_gif_generator),
            tags=["single_image", "gif"],
            name="Single Image Gif",
            llm=Recipe("image", (cg.combined_gif_generator,), brief="A gif with a title"),
        ),
        SlideGeneratorData(
            # slide_templates.generate_full_image_slide(
            slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), cg.meme_reddit_image_generator),
            tags=["full_image", "meme"],
            name="Full Screen Meme",
            llm=Recipe(
                "full_image",
                (cg.meme_reddit_image_generator,),
                brief="A meme, filling the slide",
                omit=frozenset({"title"}),
            ),
        ),
        SlideGeneratorData(
            # slide_templates.generate_full_image_slide(
            slide_generator_types.FullImageSlideGenerator.of(
                CombinedGenerator((1, NoneGenerator()), (1, cg.default_slide_title_generator)),
                cg.neutral_image_generator,
            ),
            tags=["full_image", "neutral"],
            name="Full Screen Neutral Images",
            llm=Recipe("full_image", (cg.neutral_image_generator,), brief="A photo, filling the slide"),
        ),
    ],
)

_DEEP_QUESTION = Recipe(
    "statement",
    (cg.generate_horizontal_pixabay_image,),
    brief="A deep question over a photo",
    hints={"text": "a short, deep question, such as 'But... why?'"},
)
_REAL_QUOTE_BRIEF = "A real quote over a photo (talkgenerator finds the quote, about the concept)"

single_image_slide_generators_copyright_free = _register(
    "single_image_copyright_free",
    [
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                NoneGenerator(), cg.deep_abstract_generator, cg.generate_horizontal_pixabay_image
            ),
            weight_function=PeakedWeight((2, 3, 4, 5), 2.5, 1),
            tags=["full_image", "deep"],
            name="Full Screen Pixabay Deep",
            llm=_DEEP_QUESTION,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                NoneGenerator(),
                cg.short_quote_generator,
                cg.generate_horizontal_pixabay_image,
            ),
            tags=["full_image", "quote"],
            name="Full Screen Pixabay Quote",
            llm=Recipe(
                "statement",
                (cg.generate_horizontal_pixabay_image,),
                brief=_REAL_QUOTE_BRIEF,
                texts_from={"text": cg.short_quote_generator},
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(cg.default_slide_title_generator, cg.copyright_free_generator),
            tags=["single_image"],
            name="Single Image Copyright free",
            llm=Recipe("image", (cg.copyright_free_generator,), brief="A photo with a title"),
        ),
    ],
)

# WISE STATEMENTS
_BOLD_STATEMENT = Recipe(
    "statement",
    (cg.generate_horizontal_pixabay_image,),
    brief="A bold statement over a photo",
    hints={"text": "a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'"},
)
_REAL_QUOTE = Recipe(
    "statement",
    (cg.generate_horizontal_pixabay_image,),
    brief=_REAL_QUOTE_BRIEF,
    texts_from={"text": cg.quote_generator},
)
_ANECDOTE = Recipe(
    "statement",
    (cg.generate_horizontal_pixabay_image,),
    brief="A personal anecdote the presenter now has to tell",
    hints={"text": "the title of the anecdote, such as 'The time I ...'"},
)

statement_slide_generators = _register(
    "statement",
    [
        SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(cg.inspiration_title_generator, cg.inspirobot_image_generator),
            weight_function=ConstantWeightFunction(0.6),
            tags=["inspiration", "statement"],
            name="Inspirobot",
            llm=Recipe(
                "image",
                (cg.inspirobot_image_generator,),
                brief="An inspirational poster (made by InspiroBot) that the presenter has to explain",
                hints={"title": "a title such as 'Something my father always told me'"},
                omit=frozenset({"image_query"}),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.wikihow_bold_statement_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["bold_statement", "statement"],
            name="Wikihow Bold Statement",
            llm=_BOLD_STATEMENT,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.quote_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            weight_function=ConstantWeightFunction(1),
            tags=["quote", "statement"],
            name="Quote",
            llm=_REAL_QUOTE,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.anecdote_prompt_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            weight_function=ConstantWeightFunction(1.2),
            tags=["anecdote"],
            name="Anecdote",
            llm=_ANECDOTE,
        ),
    ],
)

statement_slide_generators_copyright_free = _register(
    "statement_copyright_free",
    [
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.wikihow_bold_statement_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["bold_statement", "statement"],
            name="Wikihow Bold Statement (CRF)",
            llm=_BOLD_STATEMENT,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.quote_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["quote", "statement"],
            name="Quote (CRF)",
            llm=_REAL_QUOTE,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.anecdote_prompt_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["anecdote"],
            name="Anecdote (CRF)",
            llm=_ANECDOTE,
        ),
    ],
)

# TWO CAPTIONS VARIATIONS
captioned_images_slide_generators = _register(
    "captioned_images",
    [
        SlideGeneratorData(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.double_image_captions_generator,
                cg.neutral_or_weird_image_generator,
                cg.gif_with_backup_generator,
            ),
            weight_function=ConstantWeightFunction(2),
            tags=["multi_caption", "two_captions", "gif"],
            name="Two Captions Gifs",
            llm=Recipe(
                "two_columns", (cg.neutral_or_weird_image_generator, cg.gif_with_backup_generator), brief=_CONTRAST
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.double_image_captions_generator,
                cg.weird_image_with_backup_generator,
                cg.weird_punchline_image_generator,
            ),
            weight_function=ConstantWeightFunction(2),
            tags=["multi_caption", "two_captions", "reddit"],
            name="Two Captions Weird Reddit",
            llm=Recipe(
                "two_columns",
                (cg.weird_image_with_backup_generator, cg.weird_punchline_image_generator),
                brief=_CONTRAST,
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.double_image_captions_generator,
                cg.weird_punchline_image_generator,
                cg.weird_punchline_image_generator,
            ),
            weight_function=ConstantWeightFunction(2),
            tags=["multi_caption", "two_captions", "reddit"],
            name="Two Captions Weird",
            llm=Recipe(
                "two_columns", (cg.weird_punchline_image_generator, cg.weird_punchline_image_generator), brief=_CONTRAST
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ThreeColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.triple_image_captions_generator,
                cg.neutral_or_weird_image_generator,
                cg.weird_punchline_image_generator,
                cg.weird_punchline_static_image_generator,
            ),
            weight_function=ConstantWeightFunction(1),
            allowed_repeated_elements=4,
            tags=["multi_caption", "three_captions", "reddit"],
            name="Three Captions Weird",
            llm=Recipe(
                "three_columns",
                (
                    cg.neutral_or_weird_image_generator,
                    cg.weird_punchline_image_generator,
                    cg.weird_punchline_static_image_generator,
                ),
                brief=_SEQUENCE,
            ),
        ),
    ],
)

captioned_images_slide_generators_copyright_free = _register(
    "captioned_images_copyright_free",
    [
        SlideGeneratorData(
            slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.double_image_captions_generator,
                cg.copyright_free_related_generator,
                cg.normal_or_weird_copyright_free_generator,
            ),
            weight_function=ConstantWeightFunction(5),
            tags=["multi_caption", "two_captions"],
            name="Two Captions Copyright free",
            llm=Recipe(
                "two_columns",
                (cg.copyright_free_related_generator, cg.normal_or_weird_copyright_free_generator),
                brief=_CONTRAST,
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ThreeColumnImageSlideGenerator.of_images_and_tupled_captions(
                cg.default_or_no_title_generator,
                cg.triple_image_captions_generator,
                cg.copyright_free_generator,
                cg.copyright_free_related_generator,
                cg.weird_copyright_free_generator,
            ),
            weight_function=ConstantWeightFunction(2),
            allowed_repeated_elements=4,
            tags=["multi_caption", "three_captions"],
            name="Three Captions Weird (CRF)",
            llm=Recipe(
                "three_columns",
                (cg.copyright_free_generator, cg.copyright_free_related_generator, cg.weird_copyright_free_generator),
                brief=_SEQUENCE,
            ),
        ),
    ],
)

# CHART GENERATORS
# Charts with funny labels, and bare ones for the presenter to explain: what a trend or correlation does without
_NAMES_ON_A_TREND = frozenset({"line", "second_line", "second_shape", "event"})
_BARE_CORRELATION = frozenset({"x_axis", "y_axis", "outlier"})
own_chart_generators = _register(
    "chart",
    [
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_yes_no_pie),
            retries=1,
            allowed_repeated_elements=4,
            weight_function=ConstantWeightFunction(2.5),
            tags=["pie_chart", "yes_no_chart", "chart"],
            name="Yes/No/Funny Chart",
            llm=Recipe("chart_yes_no", brief="A survey of the audience's opinion about the concept"),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_location_pie),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(0.3),
            tags=["location_chart", "pie_chart", "chart"],
            name="Location Chart",
            llm=Recipe(
                "chart_categories",
                brief="Where the concept is found",
                hints={
                    "question": "a question such as 'Where do we find ...?'",
                    "categories": "two to five places, separated by |",
                },
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_property_pie),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(0.15),
            tags=["property_chart", "pie_chart", "chart"],
            name="Property Chart",
            llm=Recipe(
                "chart_categories",
                brief="What the concept is like",
                hints={
                    "question": "a question such as 'What are ... like?'",
                    "categories": "two to five properties, separated by |",
                },
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_correlation_curve),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(0.25),
            tags=["curve", "chart"],
            name="Correlation Curve",
            llm=Recipe(
                "chart_correlation",
                brief="A made-up scientific finding about the concept",
                variants=(
                    Variant(2, note="with funny, oddly specific titles on its axes"),
                    Variant(1, _BARE_CORRELATION, "bare: no titles on its axes, for the presenter to explain"),
                ),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_trend_chart),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(1.5),
            tags=["trend_chart", "chart"],
            name="Trend Chart",
            llm=Recipe(
                "chart_trend",
                brief="A made-up trend about the concept along two odd axes, with a second line as the "
                "punchline when that's funnier",
                variants=(
                    Variant(2, note="with funny, oddly specific titles on its axes and names on its lines"),
                    Variant(1, _NAMES_ON_A_TREND, "with funny titles on its axes, and no names on its line"),
                    Variant(
                        1,
                        _NAMES_ON_A_TREND | {"x_axis", "y_axis"},
                        "bare: one line, without titles on its axes or names, for the presenter to explain",
                    ),
                ),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_ranking_bars),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(1),
            tags=["bar_chart", "chart"],
            name="Bar Ranking",
            llm=Recipe(
                "chart_bars",
                brief="A ranking that the concept wins by far",
                variants=(Variant(3), Variant(1, frozenset({"value_axis"}), "without a title on its axis")),
            ),
        ),
    ],
)

# (A real chart from the internet, out of context: in PowerPoint karaoke, best under a confident conclusion that it
# supposedly proves, or else bare)
_CHART_CONCLUSION = (
    "a confident conclusion about the concept that the chart supposedly proves, as if it were obvious (the chart is a "
    "real one, about something else entirely)"
)
chart_slide_generators = (
    _register(
        "reddit_chart",
        [
            SlideGeneratorData(
                slide_generator_types.FullImageSlideGenerator.of(
                    cg.chart_conclusion_or_none_generator, cg.reddit_chart_generator
                ),
                weight_function=ConstantWeightFunction(4),
                allowed_repeated_elements=0,
                tags=["chart"],
                name="Reddit Chart",
                llm=Recipe(
                    "full_image",
                    (cg.reddit_chart_generator,),
                    brief="A real chart from the internet, filling the slide",
                    hints={"title": _CHART_CONCLUSION},
                    variants=(
                        Variant(2, note="under a confident conclusion that it supposedly proves"),
                        Variant(1, frozenset({"title"}), "bare: without a title, for the presenter to explain"),
                    ),
                ),
            )
        ],
    )
    + own_chart_generators
)

# DIAGRAMS: drawn as shapes, so they need no images (and fit every format)
diagram_slide_generators = _register(
    "diagram",
    [
        SlideGeneratorData(
            slide_generator_types.DiagramSlideGenerator(diagram.generate_venn),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(1),
            tags=["venn_diagram", "diagram"],
            name="Venn Diagram",
            llm=Recipe(
                "venn",
                brief="A Venn diagram about the concept: groups of things that seem to have nothing in common, and "
                "what they share, as the punchline",
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.DiagramSlideGenerator(diagram.generate_matrix),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(1),
            tags=["matrix_diagram", "diagram"],
            name="2x2 Matrix",
            llm=Recipe(
                "matrix",
                brief="A 2×2 matrix about the concept along two odd axes, with one surprising dot as the punchline",
            ),
        ),
    ],
)

# MILESTONE 6'S SLIDE TYPES (docs/v5-plan.md, section 8): drawn as texts on shapes, so the ones without a photo fit
# every format


def _middle(weight: float) -> BetweenWeight:
    """A weight for the slides in the middle of a talk: not the title slide, the one after it (where the presenter
    introduces themself) or the last (the conclusions)."""
    return BetweenWeight(weight, after=2, before=1)


def _drawn(content, slide_class, weight, tags, name, recipe, repeats=2) -> SlideGeneratorData:
    return SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(content, slide_class),
        weight_function=weight,
        retries=2,
        allowed_repeated_elements=repeats,
        tags=tags,
        name=name,
        llm=recipe,
    )


# FIGURES
number_slide_generators = _register(
    "numbers",
    [
        _drawn(
            slide_texts.generate_big_number,
            slides.BigNumberSlide,
            _middle(1.2),
            ["big_number"],
            "Big Number",
            Recipe(
                "big_number",
                brief="A suspiciously precise statistic about the concept, as one big number",
                variants=(Variant(2), Variant(1, frozenset({"source"}), "without a source, for the presenter to give")),
            ),
        ),
        _drawn(
            slide_texts.generate_kpi,
            slides.KpiSlide,
            _middle(0.8),
            ["kpi"],
            "KPI Tiles",
            Recipe(
                "kpi",
                brief="The concept's made-up key performance indicators, as on a corporate dashboard: figures that "
                "start out plausible, the last one the punchline",
                variants=(
                    Variant(1, frozenset({"number_4", "label_4"}), "with three figures"),
                    Variant(1, note="with four figures"),
                ),
            ),
        ),
    ],
)

# AUDIENCE
quiz_slide_generators = _register(
    "quiz",
    [
        _drawn(
            slide_texts.generate_quiz,
            slides.QuizSlide,
            _middle(1),
            ["quiz"],
            "Quiz",
            Recipe(
                "quiz",
                brief="A quiz question about the concept for the audience: options that all seem possible, and a "
                "surprising answer",
                variants=(
                    Variant(2),
                    Variant(1, frozenset({"option_d"}), "with three options"),
                    Variant(1, frozenset({"explanation"}), "without an explanation, for the presenter to give"),
                ),
            ),
        )
    ],
)

# MOCKUPS: a social media post and a news story, with a photo
_POST_BRIEF = "A made-up social media post about the concept, by someone with strong opinions about it"
_NEWS_BRIEF = "A made-up news story about the concept, as breaking news"


def _mockups(post_image, news_image, suffix: str = "") -> list[SlideGeneratorData]:
    return [
        _drawn(
            slide_texts.social_post(post_image),
            slides.SocialPostSlide,
            _middle(1),
            ["social_post"],
            f"Social Media Post{suffix}",
            Recipe("social_post", (post_image,), brief=_POST_BRIEF),
            repeats=1,
        ),
        _drawn(
            slide_texts.news_headline(news_image),
            slides.NewsHeadlineSlide,
            _middle(1),
            ["news"],
            f"News Headline{suffix}",
            Recipe("news_headline", (news_image,), brief=_NEWS_BRIEF),
            repeats=1,
        ),
    ]


mockup_slide_generators = _register("mockups", _mockups(cg.neutral_or_weird_image_generator, cg.news_photo_generator))
mockup_slide_generators_copyright_free = _register(
    "mockups_copyright_free",
    _mockups(cg.copyright_free_generator, cg.news_photo_copyright_free_generator, " (CRF)"),
)

# MEMES WITH LIVE CAPTIONS: one of Imgflip's templates, with captions of the talk's own in its boxes (see
# talkgenerator.sources.memes): the dice pick the template, and the language model writes what each box says (or, in
# a classic talk, the template's own sentences about the slide's topic). The user loves them (2026-11-07), so they
# weigh four times what the other middle slides weigh: about half of all 10-slide talks have one (one in five did),
# and a talk has two at most (caption_meme), and two memes of any kind in ten slides, Reddit's too (meme)
_MEME_BRIEF = "A meme about the concept"
MEME_WEIGHT = 4


def _meme_variants() -> tuple[Variant, ...]:
    """A variant per template: its boxes' captions, what each says and about how long it can be, and its picture."""
    variants = []
    for template in memes.templates().values():
        written = template.written()
        fields = [f"text_{index}" for index in range(1, len(written) + 1)]
        variants.append(
            Variant(
                1,
                omit=frozenset(f"text_{index}" for index in range(len(written) + 1, memes.MOST_CAPTIONS + 1)),
                note=f"as the '{template.name}' meme ({template.about})",
                hints={field: f"{box.says}, in a few words" for field, box in zip(fields, written, strict=True)},
                limits={field: max(12, template.room(box)) for field, box in zip(fields, written, strict=True)},
                queries={"template": template.id},
            )
        )
    return tuple(variants)


meme_slide_generators = _register(
    "memes",
    [
        _drawn(
            slide_texts.meme(cg.meme_template_generator),
            slides.MemeSlide,
            _middle(MEME_WEIGHT),
            ["meme", "caption_meme"],
            "Meme",
            Recipe("meme", (cg.meme_template_generator,), brief=_MEME_BRIEF, variants=_meme_variants()),
            repeats=1,
        )
    ],
)

# SLIDE TYPES FROM POWERPOINT KARAOKE DECKS (docs/v5-plan.md, section 8): what real karaoke and battle decks have that
# makes audiences laugh, drawn as texts on shapes (and a photo), in the middle of a talk
_FUN_FACT_BRIEF = "A fun fact about the concept: something absurd, stated as certain, that the presenter has to back up"


def _fun_fact(photo, suffix: str = "") -> list[SlideGeneratorData]:
    return [
        _drawn(
            slide_texts.fun_fact(photo),
            slides.FunFactSlide,
            _middle(1),
            ["fun_fact"],
            f"Fun Fact{suffix}",
            Recipe(
                "fun_fact",
                (photo,),
                brief=_FUN_FACT_BRIEF,
                variants=(
                    Variant(2, note="with a photo of what it's about"),
                    Variant(1, frozenset({"photo"}), "without a photo"),
                    Variant(1, frozenset({"source"}), "with a photo, without a source: the presenter names one"),
                ),
            ),
            repeats=1,
        ),
    ]


fun_fact_slide_generators = _register("fun_fact", _fun_fact(cg.neutral_or_weird_image_generator))
fun_fact_slide_generators_copyright_free = _register(
    "fun_fact_copyright_free", _fun_fact(cg.copyright_free_generator, " (CRF)")
)

# The ones without pictures, in every format: an acronym for a made-up method, a dare for the presenter (organisers put
# one such slide in a deck, at most: so it's rarer), a flowchart whose every path leads to the same end, and a tier list
karaoke_slide_generators = _register(
    "karaoke",
    [
        _drawn(
            slide_texts.generate_acronym,
            slides.AcronymSlide,
            _middle(1),
            ["acronym"],
            "Acronym",
            Recipe(
                "acronym",
                brief="A made-up method for the concept, as an acronym sold as the key to it all: its words get less "
                "plausible letter by letter, and the last one is the punchline",
                variants=(
                    Variant(1, frozenset({"word_5", "word_6"}), "of three or four letters"),
                    Variant(1, note="of four to six letters"),
                ),
            ),
        ),
        _drawn(
            slide_texts.generate_dare,
            slides.DareSlide,
            _middle(0.6),
            ["dare"],
            "Dare",
            Recipe(
                "dare",
                brief="A dare for the presenter, halfway through the talk: something playful they now have to do on "
                "the next slide or for the rest of the talk",
            ),
            repeats=1,
        ),
        _drawn(
            slide_texts.generate_flowchart,
            slides.FlowchartSlide,
            _middle(0.8),
            ["flowchart", "diagram"],
            "Flowchart",
            Recipe(
                "flowchart",
                brief="A flowchart that pretends to help decide something about the concept, but whatever the answer, "
                "it leads to the same absurd end",
                variants=(Variant(1), Variant(1, frozenset({"title"}), "without a title")),
            ),
        ),
        _drawn(
            slide_texts.generate_tier_list,
            slides.TierListSlide,
            _middle(1),
            ["tier_list"],
            "Tier List",
            Recipe(
                "tier_list",
                brief="A tier list that ranks things to do with the concept as if it were science: arguable "
                "placements, and a surprising S tier as the punchline",
                variants=(Variant(2), Variant(1, frozenset({"b_tier", "c_tier"}), "with only its S, A and F tiers")),
            ),
        ),
    ],
)

# THE TALK'S STRUCTURE: an agenda after the title, a section's divider in the middle, "Questions?" at the end
structure_slide_generators = _register(
    "structure",
    [
        _drawn(
            slide_texts.generate_agenda,
            slides.AgendaSlide,
            PeakedWeight((1,), 4, 0),
            ["agenda"],
            "Agenda",
            Recipe(
                "agenda",
                brief="The talk's agenda: what it will cover",
                hints={
                    "items": "three to five parts of the talk, in the order the slides after this one come, "
                    "separated by |"
                },
            ),
        ),
        _drawn(
            slide_texts.generate_section,
            slides.SectionSlide,
            BetweenWeight(0.8, after=3, before=2),
            ["section"],
            "Section Divider",
            Recipe(
                "section",
                brief="A section's divider, opening the next part of the talk",
                hints={
                    "title": "the title of the part of the talk that starts here, without a number (the slide has it)"
                },
                variants=(Variant(1), Variant(1, frozenset({"subtitle"}), "without a subtitle")),
            ),
        ),
        _drawn(
            slide_texts.generate_questions,
            slides.QuestionsSlide,
            PeakedWeight((-1,), 1800, 0),
            ["questions"],
            "Questions",
            Recipe(
                "questions",
                brief="The closing slide, inviting the audience's questions",
                hints={"subtitle": "a line under it, such as a disclaimer about the answers"},
            ),
        ),
    ],
)

# NATIVE DIAGRAMS: more of the diagram group's, drawn as texts on shapes
native_diagram_slide_generators = _register(
    "diagram",
    [
        _drawn(
            slide_texts.generate_timeline,
            slides.TimelineSlide,
            _middle(0.4),
            ["timeline", "diagram"],
            "Timeline",
            Recipe("timeline", brief="The concept's made-up history, as a timeline whose last moment is the punchline"),
        ),
        _drawn(
            slide_texts.generate_pyramid,
            slides.PyramidSlide,
            _middle(0.4),
            ["pyramid", "diagram"],
            "Pyramid",
            Recipe(
                "pyramid", brief="A hierarchy of needs about the concept, as a pyramid with something absurd at the top"
            ),
        ),
        _drawn(
            slide_texts.generate_funnel,
            slides.FunnelSlide,
            _middle(0.4),
            ["funnel", "diagram"],
            "Funnel",
            Recipe("funnel", brief="A sales funnel about the concept, narrowing down to something absurd"),
        ),
        _drawn(
            slide_texts.generate_cycle,
            slides.CycleSlide,
            _middle(0.4),
            ["cycle", "diagram"],
            "Cycle",
            Recipe("cycle", brief="A vicious circle about the concept: steps that lead to each other, and back"),
        ),
        _drawn(
            slide_texts.generate_org_chart,
            slides.OrgChartSlide,
            _middle(0.4),
            ["org_chart", "diagram"],
            "Org Chart",
            Recipe("org_chart", brief="Who's really in charge of the concept, as an org chart with a surprising boss"),
        ),
        _drawn(
            slide_texts.generate_iceberg,
            slides.IcebergSlide,
            _middle(0.4),
            ["iceberg", "diagram"],
            "Iceberg",
            Recipe(
                "iceberg",
                brief="What lies beneath the concept: an iceberg whose tip everyone knows, and what's under the water",
            ),
        ),
    ],
)

# CONCLUSIONS
conclusion_slide_generators = _register(
    "conclusion",
    [
        SlideGeneratorData(
            slide_generator_types.TwoImagesAndTupledCaptions(
                cg.conclusion_title_generator,
                cg.conclusion_two_captions_tuple_generator,
                cg.neutral_image_generator,
                cg.weird_image_with_backup_generator,
            ),
            weight_function=PeakedWeight((-1,), 10000, 0),
            allowed_repeated_elements=10,
            tags=["conclusion"],
            name="2 Conclusions",
            llm=Recipe(
                "two_columns",
                (cg.neutral_image_generator, cg.weird_image_with_backup_generator),
                brief="The talk's conclusions",
                hints=_conclusions(2),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ThreeImagesAndTupledCaptions(
                cg.conclusion_title_generator,
                cg.conclusion_three_captions_tuple_generator,
                cg.neutral_image_generator,
                cg.weird_image_with_backup_generator,
                cg.gif_with_backup_generator,
            ),
            weight_function=PeakedWeight((-1,), 8000, 0),
            allowed_repeated_elements=10,
            tags=["conclusion"],
            name="3 Conclusions",
            llm=Recipe(
                "three_columns",
                (cg.neutral_image_generator, cg.weird_image_with_backup_generator, cg.gif_with_backup_generator),
                brief="The talk's conclusions",
                hints=_conclusions(3),
            ),
        ),
    ],
)

conclusion_slide_generators_copyright_free = _register(
    "conclusion_copyright_free",
    [
        SlideGeneratorData(
            slide_generator_types.TwoImagesAndTupledCaptions(
                cg.conclusion_title_generator,
                cg.conclusion_two_captions_tuple_generator,
                cg.copyright_free_generator,
                cg.weird_copyright_free_generator,
            ),
            weight_function=PeakedWeight((-1,), 10000, 0),
            allowed_repeated_elements=10,
            tags=["conclusion"],
            name="2 Conclusions (CRF)",
            llm=Recipe(
                "two_columns",
                (cg.copyright_free_generator, cg.weird_copyright_free_generator),
                brief="The talk's conclusions",
                hints=_conclusions(2),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ThreeImagesAndTupledCaptions(
                cg.conclusion_title_generator,
                cg.conclusion_three_captions_tuple_generator,
                cg.copyright_free_generator,
                cg.copyright_free_related_generator,
                cg.weird_copyright_free_generator,
            ),
            weight_function=PeakedWeight((-1,), 8000, 0),
            allowed_repeated_elements=10,
            tags=["conclusion"],
            name="3 Conclusions (CRF)",
            llm=Recipe(
                "three_columns",
                (cg.copyright_free_generator, cg.copyright_free_related_generator, cg.weird_copyright_free_generator),
                brief="The talk's conclusions",
                hints=_conclusions(3),
            ),
        ),
    ],
)

all_slide_generators = (
    title_slide_generators
    + about_me_slide_generators
    + history_slide_generators
    + single_image_slide_generators
    + statement_slide_generators
    + captioned_images_slide_generators
    + chart_slide_generators
    + diagram_slide_generators
    + number_slide_generators
    + quiz_slide_generators
    + mockup_slide_generators
    + meme_slide_generators
    + fun_fact_slide_generators
    + karaoke_slide_generators
    + structure_slide_generators
    + native_diagram_slide_generators
    + conclusion_slide_generators
)

default_max_allowed_tags = {
    # Absolute maxima
    "title": 1,
    "about_me": 1,
    "history": 1,
    "anecdote": 1,
    "location_chart": 1,
    "trend_chart": 1,
    "bar_chart": 1,
    "venn_diagram": 1,
    "matrix_diagram": 1,
    "big_number": 1,
    "kpi": 1,
    "quiz": 1,
    "social_post": 1,
    "news": 1,
    "caption_meme": 2,  # (memes with live captions; and every meme, from Reddit too, two in ten slides: "meme")
    "fun_fact": 1,
    "acronym": 1,
    "dare": 1,
    "flowchart": 1,
    "tier_list": 1,
    "agenda": 1,
    "questions": 1,
    "timeline": 1,
    "pyramid": 1,
    "funnel": 1,
    "cycle": 1,
    "org_chart": 1,
    "iceberg": 1,
    # Relative (procentual) maxima
    "section": 0.1,  # (none in a talk of fewer than ten slides)
    "diagram": 0.2,
    "two_captions": 0.2,
    "three_captions": 0.2,
    "multi_captions": 0.3,
    "gif": 0.5,
    "weird": 0.5,
    "quote": 0.2,
    "statement": 0.2,
    "chart": 0.3,
    "meme": 0.2,
}
