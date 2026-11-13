import dataclasses
from typing import Final

from talkgenerator.datastructures.slide_generator_data import (
    BetweenWeight,
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import (
    CLUSTERED,
    EMOJI_NOTE,
    KINDS,
    TREND_PICTURE_ODDS,
    Recipe,
    Variant,
    box_picture_slot,
    closing_variants,
    pictured,
    problem_variants,
    with_emoji,
)
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import formats
from talkgenerator.schema.formats import Made
from talkgenerator.schema.registry import Registry
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import chart, diagram, memes, packs, slide_texts
from talkgenerator.util import random_util
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
# The third of three captioned pictures in a row breaks the pattern of the first two most of the time, as 2019's talks
# had a weird picture last, which the user remembered as usual (2026-11-10, D73: a list's other pattern breaks are its
# kind's, see talkgenerator.plan.kinds.PatternBreak)
_THIRD_BREAKS = (
    "with the third one breaking the pattern of the first two: an unexpected picture, under a caption that doesn't "
    "follow theirs"
)
_THIRD_CAPTION = "the right caption: one that breaks the pattern of the first two (the punchline)"
_THIRD_PICTURE = (
    "an image search query for the third picture: something unexpected that breaks the pattern of the first two, in "
    "two to six plain English words"
)
# (and classic ones: a list's punchline an emoji alone or a picture in its place, a diagram's an emoji, D73)
_PICTURE_OR_EMOJI = {"emoji": 1.0, "picture": 1.3}
_EMOJI = {"emoji": 1.0}
_DIAGRAM_BREAKS = 0.25
_LATE_PICTURES = 0.2  # (of the classic red flags and reviews, whose last one is a few words 35% of the time already)
_SEQUENCE_VARIANTS = (
    Variant(0.4),
    Variant(0.6, note=_THIRD_BREAKS, hints={"caption_3": _THIRD_CAPTION, "image_3_query": _THIRD_PICTURE}),
)
# (Asked for "a lesson from the talk, calling back to an earlier slide", a free model wrote "Huddling scales trust
# (from slide_03)": the slide's key in its answer; and lessons as whole sentences, which a caption's 40 characters cut,
# as in "Your plants are not decorations—they")
_CALLBACK = (
    "a lesson from the talk in six words at most, calling back to an earlier slide by what it said (not by its number "
    "or key): a new twist on it, never a recap"
)


def _conclusions(number: int) -> dict[str, str]:
    hints = {"title": _CONCLUSIONS_TITLE}
    for nr in range(1, number + 1):
        hints[f"caption_{nr}"] = _CALLBACK
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
    (cg.statement_backdrop_generator,),
    brief="A deep question over a photo",
    hints={"text": "a short, deep question, such as 'But... why?'"},
)
_REAL_QUOTE_BRIEF = "A real quote over a photo (talkgenerator finds the quote, about the concept)"

single_image_slide_generators_copyright_free = _register(
    "single_image_copyright_free",
    [
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                NoneGenerator(), cg.deep_abstract_generator, cg.statement_backdrop_generator
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
                cg.statement_backdrop_generator,
            ),
            tags=["full_image", "quote"],
            name="Full Screen Pixabay Quote",
            llm=Recipe(
                "statement",
                (cg.statement_backdrop_generator,),
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
    (cg.statement_backdrop_generator,),
    brief="A bold statement over a photo",
    hints={"text": "a bold claim or question about the concept, such as 'Don't we all secretly want to ...?'"},
)
_REAL_QUOTE = Recipe(
    "statement",
    (cg.statement_backdrop_generator,),
    brief=_REAL_QUOTE_BRIEF,
    texts_from={"text": cg.quote_generator},
)
_ANECDOTE = Recipe(
    "statement",
    (cg.statement_backdrop_generator,),
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
                background_image_generator=cg.statement_backdrop_generator,
            ),
            tags=["bold_statement", "statement"],
            name="Wikihow Bold Statement",
            llm=_BOLD_STATEMENT,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.quote_generator,
                background_image_generator=cg.statement_backdrop_generator,
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
                background_image_generator=cg.statement_backdrop_generator,
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
                background_image_generator=cg.statement_backdrop_generator,
            ),
            tags=["bold_statement", "statement"],
            name="Wikihow Bold Statement (CRF)",
            llm=_BOLD_STATEMENT,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.quote_generator,
                background_image_generator=cg.statement_backdrop_generator,
            ),
            tags=["quote", "statement"],
            name="Quote (CRF)",
            llm=_REAL_QUOTE,
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.anecdote_prompt_generator,
                background_image_generator=cg.statement_backdrop_generator,
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
                variants=_SEQUENCE_VARIANTS,
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
                variants=_SEQUENCE_VARIANTS,
            ),
        ),
    ],
)

# CHART GENERATORS
# Charts with funny labels, and bare ones for the presenter to explain: what a trend or correlation does without
_NAMES_ON_A_TREND = frozenset({"line", "second_line", "second_shape", "event"})
_BARE_CORRELATION = frozenset({"x_axis", "y_axis", "outlier"})
_CLUSTERS = frozenset({"cluster_1", "cluster_2", "cluster_3"})
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
                # (one cloud, or now and then two or three named ones: docs/v5-plan.md, D64)
                variants=(
                    Variant(1.6, _CLUSTERS, "with funny, oddly specific titles on its axes"),
                    Variant(
                        0.8, _CLUSTERS | _BARE_CORRELATION, "bare: no titles on its axes, for the presenter to explain"
                    ),
                    dataclasses.replace(CLUSTERED, note=f"{CLUSTERED.note}, and funny titles on its axes"),
                ),
            ),
        ),
        SlideGeneratorData(
            slide_generator_types.ChartSlideGenerator(
                slide_texts.pictured(
                    chart.generate_trend_chart, box_picture_slot(), chart.trend_boxes, 1, TREND_PICTURE_ODDS
                )
            ),
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
            slide_generator_types.DiagramSlideGenerator(
                slide_texts.pictured(diagram.generate_venn, box_picture_slot(), diagram.venn_boxes)
            ),
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
            slide_generator_types.DiagramSlideGenerator(
                slide_texts.pictured(diagram.generate_matrix, box_picture_slot(), diagram.matrix_boxes)
            ),
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


# FIGURES: over a picture of what they're about, if one is found (three big numbers in four, and half the KPI tiles:
# D63, as the user found slides of text boring), from one of many sources (the backdrop look's)
number_slide_generators = _register(
    "numbers",
    [
        _drawn(
            slide_texts.big_number(cg.backdrop_generator),
            slides.BigNumberSlide,
            _middle(1.2),
            ["big_number"],
            "Big Number",
            Recipe(
                "big_number",
                (cg.backdrop_generator,),
                brief="A suspiciously precise statistic about the concept, as one big number",
                variants=pictured(
                    (Variant(2), Variant(1, frozenset({"source"}), "without a source, for the presenter to give")),
                    "background",
                    slide_texts.BIG_NUMBER_PICTURES,
                ),
            ),
        ),
        _drawn(
            slide_texts.kpi(cg.backdrop_generator),
            slides.KpiSlide,
            _middle(0.8),
            ["kpi"],
            "KPI Tiles",
            Recipe(
                "kpi",
                (cg.backdrop_generator,),
                brief="The concept's made-up key performance indicators, as on a corporate dashboard: figures that "
                "start out plausible, the last one the punchline",
                variants=pictured(
                    (
                        Variant(1, frozenset({"number_4", "label_4"}), "with three figures"),
                        Variant(1, note="with four figures"),
                    ),
                    "background",
                    slide_texts.KPI_PICTURES,
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
# weigh seven times what the other middle slides weigh (four until the user asked for more of them, D63; five until
# the pictures to explain shared the middle of a talk, D78, which the user wanted them to keep their half of the talks
# against): half of all 10-slide talks have one (one in five did at first), and a talk has two at most (caption_meme),
# and two memes of any kind in ten slides, Reddit's too (meme)
_MEME_BRIEF = "A meme about the concept"
MEME_WEIGHT = 7
MEME_ROOM_SIZE = 30  # (the font size, in canvas pixels, at which a box's room is how long a caption is kept whole)
_MEME_CAPTION = max(max(text.max_length, text.room) for text in KINDS["meme"].texts)  # (a caption's own room at most)


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
                # (a caption that's longer is kept whole as far as its box holds it at a smaller size: a meme's
                # captions shrink to 28 pixels, and a caption cut off mid-sentence spoils the joke, D80)
                rooms={
                    field: min(_MEME_CAPTION, max(12, template.room(box, MEME_ROOM_SIZE)))
                    for field, box in zip(fields, written, strict=True)
                },
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
# (the reviews' punchline: models gave three glowing ones in a row, a motivational speaker's especially)
_ONE_STAR = "how many stars the {which} and last reviewer gives: 1, the one-star review that's the punchline"


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

# THE PROBLEM (docs/v5-plan.md, D69): some TED-like talks open on their why too, as a pitch and an academic talk do: as
# their third slide (after the presenter's), the problem the talk is about, on an angle the talk's dice pick (see
# talkgenerator.plan.kinds.PROBLEM_ANGLES), over a picture of it or beside one that shows it (generated, in a talk that
# generates pictures); a classic one from the TED pack's problems
PROBLEM_WEIGHT = 26  # (at the third slide: a quarter to a third of TED-like talks open on their problem)
_PROBLEM_PICTURE = ImageSlot(
    "a picture that shows the problem the talk is about, as it happens", aesthetic="weird-stock", generate=True
)
# (the TED speaker's: everyday and weird ones a little more often than the other angles)
_PROBLEM_ANGLES = {"everyday": 1.3, "weird": 1.2}
_TED_PROBLEMS = {
    "kicker": "problem.kicker",
    "weird": "problem.weird",
    "everyday": "problem.everyday",
    "crossed": "problem.crossed",
    "typical": "problem.typical",
    "real": "problem.real",
}


def _ted_problem(context: dict) -> Made | None:
    seed = str(context["seed"])
    if slide_texts.sensitive(seed):
        return None
    variables = {
        "seed": seed,
        "number": str(random_util.randint(3, 40)),
        "percent": f"{random_util.randint(12, 97)}%",
        "year": str(random_util.randint(1950, 2019)),
    }
    pictures = (cg.statement_backdrop_generator, _PROBLEM_PICTURE)
    return formats.problem(packs.TED, _TED_PROBLEMS, variables, context, pictures, _PROBLEM_ANGLES)


problem_slide_generators = _register(
    "problem",
    [
        SlideGeneratorData(
            formats.KindSlideGenerator("problem", _ted_problem),
            weight_function=PeakedWeight((2,), PROBLEM_WEIGHT, 0),
            retries=3,
            allowed_repeated_elements=2,
            tags=["problem_slide"],
            name="Problem",
            llm=Recipe(
                "problem",
                (cg.statement_backdrop_generator, _PROBLEM_PICTURE),
                brief="The problem the talk is about, early on, as a TED speaker opens with one to hook the audience: "
                "a problem with the concept that the talk's thesis will answer",
                hints={
                    "kicker": "a short heading over the problem, as a TED speaker would open with it, such as 'Picture "
                    "this' or 'Sound familiar?'",
                },
                variants=problem_variants(_PROBLEM_ANGLES),
            ),
        )
    ],
)

# The ones without pictures, in every format: an acronym for a made-up method, a dare for the presenter (organisers put
# one such slide in a deck, at most: so it's rarer), a flowchart whose every path leads to the same end, and a tier list.
# A third of the tier lists and alignment charts have an emoji in front of every thing (docs/v5-plan.md, D65)
_TIERS_WITHOUT_B_AND_C = frozenset({"b_tier", "c_tier"})
# (and the moods of the emoji talkgenerator puts where a model wrote none: see talkgenerator.sources.emoji)
_TIER_MOODS = {f"{tier.lower()}_tier": f"tier_{tier.lower()}" for tier in slides.TIERS}
_ALIGNMENT_MOODS = {alignment: alignment for alignment in slides.ALIGNMENTS}
_TIER_EMOJI = {
    **with_emoji("tier_list", ("s_tier",)),
    **with_emoji("tier_list", ("a_tier", "b_tier", "c_tier", "f_tier"), each=True),
}
_ALIGNMENT_EMOJI = with_emoji("alignment_chart", slides.ALIGNMENTS)

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
            # (over a picture of what it's about, now and then: D80)
            slide_texts.with_backdrop(
                slide_texts.generate_dare, cg.words_backdrop_generator, slide_texts.DARE_PICTURES
            ),
            slides.DareSlide,
            _middle(0.6),
            ["dare"],
            "Dare",
            Recipe(
                "dare",
                (cg.words_backdrop_generator,),
                brief="A dare, halfway through the talk",
                # (a real challenge for the presenter, or the audience joining in, from the user's look at the dares of
                # 2026-11-09, D65; and in an English talk, now and then a real dad joke to tell: see
                # talkgenerator.facts)
                variants=pictured(
                    (
                        Variant(
                            2,
                            frozenset({"audience"}),
                            "a real challenge for the presenter, which they have to keep up from now on: the audience "
                            "will watch them try",
                            facts=False,
                        ),
                        Variant(
                            2,
                            frozenset({"dare"}),
                            "for the whole audience: the presenter gets everyone to join in, as a show of hands or a call "
                            "and response",
                            facts=False,
                        ),
                        Variant(1, frozenset({"audience"}), "for the presenter, on the next slide or from now on"),
                    ),
                    "background",
                    slide_texts.DARE_PICTURES,
                ),
            ),
            repeats=1,
        ),
        _drawn(
            slide_texts.pictured(
                slide_texts.broken(slide_texts.generate_flowchart, slide_texts.at(4), _EMOJI, _DIAGRAM_BREAKS),
                box_picture_slot(),
                slide_texts.flowchart_boxes,
            ),
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
            slide_texts.broken(
                slide_texts.generate_tier_list,
                slide_texts.at(1, "s_tier"),
                _PICTURE_OR_EMOJI,
                picture=box_picture_slot(),
            ),
            slides.TierListSlide,
            _middle(1),
            ["tier_list"],
            "Tier List",
            Recipe(
                "tier_list",
                brief="A tier list that ranks things to do with the concept as if it were science: arguable "
                "placements, and a surprising S tier as the punchline",
                variants=(
                    Variant(4 / 3),
                    Variant(2 / 3, note=EMOJI_NOTE, hints=_TIER_EMOJI, emoji=_TIER_MOODS),
                    Variant(2 / 3, _TIERS_WITHOUT_B_AND_C, "with only its S, A and F tiers"),
                    Variant(
                        1 / 3,
                        _TIERS_WITHOUT_B_AND_C,
                        f"with only its S, A and F tiers, {EMOJI_NOTE}",
                        hints=_TIER_EMOJI,
                        emoji=_TIER_MOODS,
                    ),
                ),
            ),
        ),
        # The next ones from the catalogue (2026-11-08): a wall of text that nobody can read (organisers warn against
        # text-heavy decks, so it's rarer), an alignment chart, red flags, reviews with stars, and a fake error
        # message, which breaks the illusion as the dare does (so it's rarer too)
        _drawn(
            slide_texts.generate_wall_of_text,
            slides.WallOfTextSlide,
            _middle(0.6),
            ["wall_of_text"],
            "Wall of Text",
            Recipe(
                "wall_of_text",
                brief="An executive summary of the concept that nobody can read: a wall of dense jargon about it, with "
                "one absurd point hidden among the rest, which the presenter points at as if it were obvious",
            ),
            repeats=4,
        ),
        _drawn(
            slide_texts.broken(
                slide_texts.generate_alignment_chart,
                slide_texts.at(-1, "chaotic_evil"),
                _PICTURE_OR_EMOJI,
                picture=box_picture_slot(),
            ),
            slides.AlignmentChartSlide,
            _middle(0.8),
            ["alignment_chart"],
            "Alignment Chart",
            Recipe(
                "alignment_chart",
                brief="An alignment chart of things to do with the concept, as Dungeons & Dragons sorts characters: "
                "harmless and wholesome as lawful good, unhinged as chaotic evil, the punchline",
                variants=(Variant(2), Variant(1, note=EMOJI_NOTE, hints=_ALIGNMENT_EMOJI, emoji=_ALIGNMENT_MOODS)),
            ),
            repeats=3,
        ),
        _drawn(
            slide_texts.broken(
                slide_texts.generate_red_flags,
                slide_texts.last("flag"),
                {"picture": 1.0},
                _LATE_PICTURES,
                picture=box_picture_slot(),
            ),
            slides.RedFlagsSlide,
            _middle(0.5),
            ["red_flags"],
            "Red Flags",
            Recipe(
                "red_flags",
                brief="Three red flags about the concept, as in dating advice: warning signs that someone or "
                "something around it is trouble, each more alarming than the last",
            ),
        ),
        # (the user's variation, 2026-11-13: a green, an orange and a red flag; one of the two kinds a talk, at most)
        _drawn(
            slide_texts.broken(
                slide_texts.generate_traffic_flags,
                slide_texts.last("flag"),
                {"picture": 1.0},
                _LATE_PICTURES,
                picture=box_picture_slot(),
            ),
            slides.TrafficFlagsSlide,
            _middle(0.4),
            ["red_flags", "traffic_flags"],
            "Traffic Flags",
            Recipe(
                "traffic_flags",
                brief="A green flag, an orange flag and a red flag about the concept, as in dating advice: a good "
                "sign, a doubtful one and an alarming one, the punchline",
            ),
        ),
        _drawn(
            slide_texts.broken(
                slide_texts.generate_reviews,
                slide_texts.last_review,
                {"picture": 1.0},
                _LATE_PICTURES,
                picture=box_picture_slot(),
            ),
            slides.ReviewsSlide,
            _middle(0.8),
            ["reviews"],
            "Reviews",
            Recipe(
                "reviews",
                brief="Made-up customer reviews of the concept, as if it were a product: glowing ones that take it "
                "far too seriously, then a one-star review, the punchline",
                variants=(
                    Variant(2, note="with three reviews", hints={"stars_3": _ONE_STAR.format(which="third")}),
                    Variant(
                        1,
                        frozenset({"stars_3", "review_3", "reviewer_3"}),
                        "with two reviews",
                        hints={"stars_2": _ONE_STAR.format(which="second")},
                    ),
                ),
            ),
        ),
        _drawn(
            slide_texts.generate_error_message,
            slides.ErrorMessageSlide,
            _middle(0.25),
            ["error_message"],
            "Error Message",
            Recipe(
                "error_message",
                brief="A fake error message about the concept, as if the talk itself just crashed: a dialog with a "
                "short, absurd message about the concept, worded as computers word them, and buttons, the last one "
                "the punchline",
                variants=(Variant(1), Variant(2, frozenset({"code"}), "without an error code")),
            ),
        ),
    ],
)

# SLIDES OF A PICTURE TO EXPLAIN (docs/v5-plan.md, D78): a surprising picture that the presenter has to explain, with
# little or no text, as improv suggestions and story cubes give a performer something to explain (the user's request
# of 2026-11-12): Exhibit A, two pictures to pick one of, a picture equation, a picture to see something in (a face in
# something: pareidolia, or an inkblot), and a before and after. One to three pictures a slide, as a slide has 8 seconds
# on talkgenerator.com before something stands in for it (D67); an equation's things are emoji where their pictures
# aren't found in time, and "What do you see?" an inkblot. Talks without fair use (ted) have no pareidolia, which only
# Reddit has: their "What do you see?" is an inkblot
_ODD_PICTURE = ImageSlot("an odd picture, as the evidence in a case", aesthetic="weird-stock", generate=True)
_OPTION = ImageSlot("one of two things for the audience to pick from", aesthetic="weird-stock")
_THING = ImageSlot("a thing in a picture equation", aesthetic="photo")
_SURPRISE = ImageSlot("what two things make together in a picture equation: a surprise", aesthetic="weird-stock")
# (searched for the plan's query, and then for any face: a planned search gets no subreddit's hot posts when it finds
# none, as a classic one does, and a face in a thing to do with the topic is rare)
_PAREIDOLIA = ImageSlot(
    "a face in something that has none (pareidolia)", aesthetic="pareidolia", queries=("{}", "face")
)
_BEFORE = ImageSlot("the 'before' of a transformation", aesthetic="photo")
_AFTER = ImageSlot(
    "the 'after' of a transformation, which has nothing to do with its 'before'", aesthetic="weird-stock"
)
_WORDS = "in two to six plain English words"
_EXHIBIT_HINTS = {
    "picture_query": "an image search query for the odd picture that is the evidence: something concrete and "
    f"surprising that the case could hinge on, {_WORDS}"
}
_PICK_ONE_HINTS = {
    "picture_1_query": f"an image search query for the first thing to pick: something concrete, {_WORDS}",
    "picture_2_query": "an image search query for the second thing to pick: something just as concrete, but absurdly "
    f"different from the first, {_WORDS}",
}
_EQUATION_HINTS = {
    "term_1_picture_query": "an image search query for a photo of the first thing, in one to four plain English words",
    "term_2_picture_query": "an image search query for a photo of the second thing, in one to four plain English words",
    "result_picture_query": f"an image search query for a picture of what the two make together, the surprise, {_WORDS}",
}
_PAREIDOLIA_HINTS = {
    "picture_query": "an image search query for an everyday thing to do with the concept that could have a face in it "
    "(pareidolia), in one or two plain English words: the thing's name"
}
_BEFORE_AFTER_HINTS = {
    "before_picture_query": f"an image search query for the 'before' picture, of something to do with the concept, "
    f"{_WORDS}",
    "after_picture_query": "an image search query for the 'after' picture: something that has nothing to do with the "
    f"first, as if the first became it, {_WORDS}",
}
_EQUATION_VARIANTS = (
    Variant(2, frozenset({"title"}), "of three pictures (with their emoji, for a picture that isn't found)"),
    Variant(1, frozenset({"title", "result_picture"}), "of two pictures that make an emoji"),
    Variant(1, frozenset({"title", "term_1_picture", "term_2_picture"}), "of two emoji that make a picture"),
    Variant(1, frozenset({"term_1_picture", "term_2_picture", "result_picture"}), "of three emoji, under a title"),
)
_WHAT_QUESTIONS = (
    Variant(2, frozenset({"question"}), "under talkgenerator's 'What do you see?'"),
    Variant(1, note="under a question of its own"),
)
_INKBLOT = (
    "An inkblot that talkgenerator draws, as a Rorschach test has them, for the audience to say what they see in it and "
    "the presenter to explain what everyone should see"
)
PICTURE_PROMPT_WEIGHTS: Final[dict[str, float]] = {
    "exhibit": 1,
    "pick_one": 0.8,
    "equation": 0.8,
    "what_do_you_see": 0.8,
    "before_after": 0.7,
}


def _picture_prompts(pareidolia: bool, suffix: str = "") -> list[SlideGeneratorData]:
    """The slides of a picture to explain, with pareidolia in "What do you see?" (in talks with fair use) or without
    (an inkblot, always)."""
    weights = PICTURE_PROMPT_WEIGHTS
    if pareidolia:
        seeing = Recipe(
            "what_do_you_see",
            (_PAREIDOLIA,),
            brief="A picture of a face in something to do with the concept, which has none (pareidolia), for the "
            "audience to say what they see in it and the presenter to explain what everyone should see",
            hints=_PAREIDOLIA_HINTS,
            variants=(
                *_WHAT_QUESTIONS,
                Variant(
                    1,
                    frozenset({"picture", "question"}),
                    "this one an inkblot instead of a picture, which talkgenerator draws, as a Rorschach test has them",
                ),
            ),
        )
    else:
        # (its picture left out: an inkblot, always)
        seeing = Recipe(
            "what_do_you_see", (_PAREIDOLIA,), brief=_INKBLOT, omit=frozenset({"picture"}), variants=_WHAT_QUESTIONS
        )
    return [
        _drawn(
            slide_texts.exhibit(_ODD_PICTURE),
            slides.ExhibitSlide,
            _middle(weights["exhibit"]),
            ["exhibit"],
            f"Exhibit A{suffix}",
            Recipe(
                "exhibit",
                (_ODD_PICTURE,),
                brief="Exhibit A: an odd picture to do with the concept, as the evidence in a case, for the "
                "presenter to explain what it proves",
                hints=_EXHIBIT_HINTS,
                variants=(
                    Variant(1, note="with a few words on its evidence tag"),
                    Variant(1, frozenset({"note"}), "bare, without a note: the presenter says what it proves"),
                ),
            ),
            repeats=1,
        ),
        _drawn(
            slide_texts.pick_one(_OPTION, _OPTION),
            slides.PickOneSlide,
            _middle(weights["pick_one"]),
            ["pick_one"],
            f"Pick One{suffix}",
            Recipe(
                "pick_one",
                (_OPTION, _OPTION),
                brief="Two pictures to pick one of, without captions: two things to do with the concept that are "
                "absurdly hard to choose between, for the audience to vote on and the presenter to explain",
                hints=_PICK_ONE_HINTS,
                variants=(
                    Variant(2, frozenset({"title"}), "under talkgenerator's 'Pick one:'"),
                    Variant(1, note="under a heading of its own"),
                ),
            ),
            repeats=1,
        ),
        _drawn(
            slide_texts.equation(_THING, _SURPRISE),
            slides.EquationSlide,
            _middle(weights["equation"]),
            ["equation"],
            f"Picture Equation{suffix}",
            Recipe(
                "equation",
                (_THING, _THING, _SURPRISE),
                brief="A picture equation about the concept, as story cubes tell a story: something to do with it plus "
                "something else equals a surprise, for the presenter to explain how it adds up",
                hints=_EQUATION_HINTS,
                variants=_EQUATION_VARIANTS,
            ),
        ),
        _drawn(
            slide_texts.what_do_you_see(_PAREIDOLIA if pareidolia else None),
            slides.WhatDoYouSeeSlide,
            _middle(weights["what_do_you_see"]),
            ["what_do_you_see"],
            f"What Do You See{suffix}",
            seeing,
            repeats=1,
        ),
        _drawn(
            slide_texts.before_after(_BEFORE, _AFTER),
            slides.BeforeAfterSlide,
            _middle(weights["before_after"]),
            ["before_after"],
            f"Before And After{suffix}",
            Recipe(
                "before_after",
                (_BEFORE, _AFTER),
                brief="A before and after about the concept: two pictures that have nothing to do with each other, as "
                "a transformation, for the presenter to explain how the one became the other",
                hints=_BEFORE_AFTER_HINTS,
                variants=(
                    Variant(2, frozenset({"title"}), "without a title"),
                    Variant(1, note="under a title of its own"),
                ),
            ),
            repeats=1,
        ),
    ]


picture_prompt_slide_generators = _register("picture_prompts", _picture_prompts(pareidolia=True))
picture_prompt_slide_generators_copyright_free = _register(
    "picture_prompts_copyright_free", _picture_prompts(pareidolia=False, suffix=" (CRF)")
)

# THE TALK'S STRUCTURE: an agenda after the title, a section's divider in the middle; and "Questions?", which no talk
# of talkgenerator's own has among its slides anymore (D76: its closer asks for them, after its last slide, so that every
# slide it asked for is one of its content), only a plan written elsewhere that asks for one (its recipe)
_AGENDA_ITEMS = "three to five parts of the talk, in the order the slides after this one come, separated by |"
_AGENDA_EMOJI = with_emoji("agenda", ("items",), {"items": _AGENDA_ITEMS}, each=True)

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
                hints={"items": _AGENDA_ITEMS},
                # (a quarter of them with an emoji in front of every item: docs/v5-plan.md, D65)
                variants=(Variant(3), Variant(1, note=EMOJI_NOTE, hints=_AGENDA_EMOJI, emoji={"items": "agenda"})),
            ),
        ),
        _drawn(
            # (over a picture of what it's about, now and then: D80)
            slide_texts.with_backdrop(
                slide_texts.generate_section, cg.words_backdrop_generator, slide_texts.SECTION_PICTURES, slots=1
            ),
            slides.SectionSlide,
            # (one per ten slides, by its cap: and none in a shorter talk, where a part would be a slide or two)
            BetweenWeight(0.8, after=3, before=2, shortest=10),
            ["section"],
            "Section Divider",
            Recipe(
                "section",
                (cg.words_backdrop_generator,),
                brief="A section's divider, opening the next part of the talk",
                hints={
                    "title": "the title of the part of the talk that starts here, without a number (the slide has it)"
                },
                variants=pictured(
                    (Variant(1), Variant(1, frozenset({"subtitle"}), "without a subtitle")),
                    "background",
                    slide_texts.SECTION_PICTURES,
                ),
            ),
        ),
        _drawn(
            slide_texts.questions(cg.closing_picture_generator),
            slides.QuestionsSlide,
            ConstantWeightFunction(0),  # (D76: a plan's alone, see above)
            ["questions"],
            "Questions",
            Recipe(
                "questions",
                (cg.closing_picture_generator,),
                brief="The closing slide, inviting the audience's questions",
                hints={"subtitle": "a line under it, such as a disclaimer about the answers"},
                # (a funny picture, a last tip or a callback to an earlier picture: docs/v5-plan.md, D65)
                variants=closing_variants("a line under it, such as a disclaimer about the answers"),
            ),
        ),
    ],
)

# NATIVE DIAGRAMS: more of the diagram group's, drawn as texts on shapes
native_diagram_slide_generators = _register(
    "diagram",
    [
        _drawn(
            slide_texts.broken(slide_texts.generate_timeline, slide_texts.last(), _EMOJI, _DIAGRAM_BREAKS),
            slides.TimelineSlide,
            _middle(0.4),
            ["timeline", "diagram"],
            "Timeline",
            Recipe("timeline", brief="The concept's made-up history, as a timeline whose last moment is the punchline"),
        ),
        _drawn(
            slide_texts.pictured(
                slide_texts.broken(slide_texts.generate_pyramid, slide_texts.at(1), _EMOJI, _DIAGRAM_BREAKS),
                box_picture_slot(),
                slide_texts.numbered_boxes("level"),
            ),
            slides.PyramidSlide,
            _middle(0.4),
            ["pyramid", "diagram"],
            "Pyramid",
            Recipe(
                "pyramid", brief="A hierarchy of needs about the concept, as a pyramid with something absurd at the top"
            ),
        ),
        _drawn(
            slide_texts.pictured(
                slide_texts.broken(slide_texts.generate_funnel, slide_texts.last(), _EMOJI, _DIAGRAM_BREAKS),
                box_picture_slot(),
                slide_texts.numbered_boxes("stage"),
            ),
            slides.FunnelSlide,
            _middle(0.4),
            ["funnel", "diagram"],
            "Funnel",
            Recipe("funnel", brief="A sales funnel about the concept, narrowing down to something absurd"),
        ),
        _drawn(
            slide_texts.pictured(
                slide_texts.generate_cycle, box_picture_slot(), slide_texts.numbered_boxes("step"), most=1
            ),
            slides.CycleSlide,
            _middle(0.4),
            ["cycle", "diagram"],
            "Cycle",
            Recipe("cycle", brief="A vicious circle about the concept: steps that lead to each other, and back"),
        ),
        _drawn(
            slide_texts.broken(
                slide_texts.generate_org_chart,
                slide_texts.at(1, "boss"),
                {"emoji": 1.0, "picture": 1.5},
                picture=box_picture_slot(),
            ),
            slides.OrgChartSlide,
            _middle(0.4),
            ["org_chart", "diagram"],
            "Org Chart",
            Recipe("org_chart", brief="Who's really in charge of the concept, as an org chart with a surprising boss"),
        ),
        _drawn(
            slide_texts.pictured(
                slide_texts.broken(slide_texts.generate_iceberg, slide_texts.last(), _EMOJI, _DIAGRAM_BREAKS),
                box_picture_slot(),
                slide_texts.iceberg_boxes,
            ),
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
    + problem_slide_generators
    + karaoke_slide_generators
    + picture_prompt_slide_generators
    + structure_slide_generators
    + native_diagram_slide_generators
    + conclusion_slide_generators
)

# SPARE SLIDES: what a streamed talk shows while its next slide isn't in yet, when a presenter catches up with the
# making (see talkgenerator.generator.stream_talk's spares): slide types drawn without pictures, from the TED pack's
# templates and the words ConceptNet (or Datamuse) relates to the topic. Timed on 26 topics (docs/v5-plan.md, D66, has
# the numbers), each took a hundredth of a second once those words were in (one lookup a topic, 0.1 to 0.5 s from
# Datamuse), a second at most (a dare's real dad joke), and never failed but on a topic they won't make light of
# (death): where a slide with a picture took 1 to 14 seconds. A quiz takes up to 3 s for a real trivia question, and a
# wall of text 0.8 s to lay out (its fine print), so they come less often; so do the ones that break the illusion (a
# fake error message, a dare), as in a talk. Not the diagrams that look a picture up for a box now and then (3 to 6 s),
# nor the property chart (it failed on 8 of 26 topics), nor the talk's structure (an agenda, a section's divider)
SPARE_WEIGHTS: Final[dict[str, float]] = {
    "Tier List": 1,
    "Alignment Chart": 1,
    "Red Flags": 1,
    "Reviews": 1,
    "Acronym": 1,
    "Quiz": 0.8,
    "Yes/No/Funny Chart": 0.8,
    "Org Chart": 0.6,
    "Timeline": 0.6,
    "Bar Ranking": 0.6,
    "Dare": 0.6,
    "Error Message": 0.5,
    "Wall of Text": 0.4,
    # (and two slides of a picture to explain, which look none up when they stand in: an inkblot to see something in,
    # and a picture equation of emoji, D78)
    "What Do You See": 0.8,
    "Picture Equation": 0.8,
}
SPARE_GENERATORS: Final = tuple((slide_generators.get(name), weight) for name, weight in SPARE_WEIGHTS.items())

# How many slides of a tag a talk may have, from its first slide on (see presentation_schema.most_slides): an absolute
# maximum is a number of slides (0: none), a relative one a share of the talk's slides, rounded down but at least one
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
    "problem_slide": 1,  # (D69: one problem slide a talk, in every format: a pitch's problem part may have two slides)
    "acronym": 1,
    "dare": 1,
    "flowchart": 1,
    "tier_list": 1,
    "wall_of_text": 1,
    "alignment_chart": 1,
    "red_flags": 1,  # (of either kind: red flags, or a green, an orange and a red flag)
    "traffic_flags": 1,
    "reviews": 1,
    "error_message": 1,
    "exhibit": 2,  # (Exhibit A, and later in the talk, now and then, Exhibit B: D78)
    "pick_one": 1,
    "equation": 1,
    "what_do_you_see": 1,
    "before_after": 1,
    "agenda": 1,
    "questions": 1,
    "timeline": 1,
    "pyramid": 1,
    "funnel": 1,
    "cycle": 1,
    "org_chart": 1,
    "iceberg": 1,
    # Relative (procentual) maxima
    "section": 0.1,  # (and none in a talk of fewer than ten slides, by its weight)
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
