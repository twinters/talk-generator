from talkgenerator.datastructures.slide_generator_data import (
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.registry import Registry
from talkgenerator.slide import slide_generator_types
from talkgenerator.sources import chart
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
_CONTRAST = "Two captioned images that contrast or compare, like 'Expectation' and 'Reality'"
_SEQUENCE = "Three captioned images that build up, like 'Good, Better, Best' or three steps of a plan"
_CONCLUSIONS_TITLE = "a title such as 'Conclusions' or 'What we learned'"


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
                (cg.neutral_image_generator, cg.neutral_image_generator, cg.weird_punchline_image_generator),
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
                (cg.neutral_image_generator, cg.neutral_image_generator),
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
                (cg.neutral_image_generator, cg.reddit_book_cover_generator, cg.weird_punchline_image_generator),
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
                (cg.weird_punchline_image_generator,),
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
            llm=Recipe("history_quote", (cg.vintage_person_generator,), brief=_HISTORY_QUOTE_BRIEF),
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
                (cg.vintage_picture_generator, cg.vintage_picture_generator),
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
            llm=Recipe("history_quote", (cg.historic_person_copyright_free_generator,), brief=_HISTORY_QUOTE_BRIEF),
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
                (cg.historic_copyright_free_generator, cg.historic_copyright_free_generator),
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
            llm=Recipe("chart_correlation", brief="A made-up scientific finding about the concept"),
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
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(chart.generate_ranking_bars),
            allowed_repeated_elements=4,
            retries=1,
            weight_function=ConstantWeightFunction(1),
            tags=["bar_chart", "chart"],
            name="Bar Ranking",
            llm=Recipe("chart_bars", brief="A ranking that the concept wins by far"),
        ),
    ],
)

chart_slide_generators = (
    _register(
        "reddit_chart",
        [
            SlideGeneratorData(
                slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), cg.reddit_chart_generator),
                weight_function=ConstantWeightFunction(4),
                allowed_repeated_elements=0,
                tags=["chart"],
                name="Reddit Chart",
                llm=Recipe(
                    "full_image",
                    (cg.reddit_chart_generator,),
                    brief="A chart, filling the slide",
                    omit=frozenset({"title"}),
                ),
            )
        ],
    )
    + own_chart_generators
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
    # Relative (procentual) maxima
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
