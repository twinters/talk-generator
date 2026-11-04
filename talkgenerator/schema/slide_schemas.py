from talkgenerator.datastructures.slide_generator_data import (
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.schema.content_generators import *
from talkgenerator.slide import slide_generator_types
from talkgenerator.sources import chart
from talkgenerator.util.generator_util import CombinedGenerator, NoneGenerator

# ==============================
# =====  SLIDE GENERATORS  =====
# ==============================


# TITLE SLIDE
title_slide_generators = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(talk_title_generator_if_not_generated, talk_subtitle_generator),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
    )
]

# ABOUT ME
about_me_slide_generators = [
    SlideGeneratorData(
        # slide_templates.generate_three_column_images_slide_tuple(
        slide_generator_types.ThreeColumnImageSlideGenerator.of_tupled_captioned_images(
            about_me_title_generator,
            about_me_location_or_country_tuple_generator,
            about_me_job_tuple_generator,
            about_me_hobby_tuple_generator,
        ),
        PeakedWeight((1,), 10, 0),
        allowed_repeated_elements=3,
        tags=["about_me"],
        name="About Me: Location-Job-WeirdHobby",
    ),
    SlideGeneratorData(
        # slide_templates.generate_two_column_images_slide_tuple(
        slide_generator_types.TwoColumnImageSlideGenerator.of_tupled_captioned_images(
            about_me_title_generator,
            about_me_location_or_country_tuple_generator,
            about_me_job_tuple_generator,
        ),
        PeakedWeight((1,), 4, 0),
        allowed_repeated_elements=3,
        tags=["about_me"],
        name="About Me: Location-Job",
    ),
    SlideGeneratorData(
        # slide_templates.generate_three_column_images_slide_tuple(
        slide_generator_types.ThreeColumnImageSlideGenerator.of_tupled_captioned_images(
            about_me_title_generator,
            about_me_location_or_country_tuple_generator,
            about_me_book_tuple_generator,
            about_me_hobby_tuple_generator,
        ),
        PeakedWeight((1,), 4, 0),
        allowed_repeated_elements=0,
        tags=["about_me"],
        name="About Me: Location-Book-WeirdHobby",
    ),
    SlideGeneratorData(
        # slide_templates.generate_image_slide_tuple(
        slide_generator_types.ImageSlideGenerator.of_tupled_captioned_image(about_me_hobby_tuple_generator),
        PeakedWeight((1, 2), 3, 0),
        allowed_repeated_elements=0,
        tags=["about_me"],
        name="Weird Hobby",
    ),
]

# HISTORY
history_slide_generators = [
    SlideGeneratorData(
        # slide_templates.generate_two_column_images_slide(
        slide_generator_types.TwoColumnImageSlideGenerator.of(
            history_and_history_person_title_generator,
            historical_name_generator,
            vintage_person_generator,
            NoneGenerator(),
            goodreads_quote_generator,
        ),
        weight_function=PeakedWeight((2, 3), 20, 0.3),
        allowed_repeated_elements=0,
        tags=["history", "quote"],
        name="Historical Figure Quote",
    ),
    SlideGeneratorData(
        # slide_templates.generate_two_column_images_slide_tuple_caption(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            history_title_generator,
            historic_double_captions_generator,
            vintage_picture_generator,
            vintage_picture_generator,
        ),
        weight_function=PeakedWeight((2, 3), 12, 0.1),
        allowed_repeated_elements=0,
        tags=["history", "two_images"],
        name="Two History Pictures",
    ),
]
history_slide_generators_copyright_free = [
    SlideGeneratorData(
        # slide_templates.generate_two_column_images_slide(
        slide_generator_types.TwoColumnImageSlideGenerator.of(
            history_and_history_person_title_generator,
            historical_name_generator,
            copyright_free_prefixed_generator(["historic person", "person", "man", "woman"]),
            NoneGenerator(),
            goodreads_short_quote_generator,
        ),
        weight_function=PeakedWeight((1, 2), 20, 0.3),
        allowed_repeated_elements=2,
        tags=["history", "quote"],
        name="Historical Figure Quote",
    ),
    SlideGeneratorData(
        # slide_templates.generate_two_column_images_slide_tuple_caption(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            history_title_generator,
            historic_double_captions_generator,
            copyright_free_prefixed_generator(["vintage", "historic", "old", "ancient"]),
            copyright_free_prefixed_generator(["vintage", "historic", "old", "ancient"]),
        ),
        weight_function=PeakedWeight((1, 2), 12, 0.1),
        allowed_repeated_elements=2,
        tags=["history", "two_images"],
        name="Two History Pictures",
    ),
]


# FULL SCREEN RELATED IMAGES
single_image_slide_generators = [
    SlideGeneratorData(
        # slide_templates.generate_full_image_slide(
        slide_generator_types.FullImageSlideGenerator.of(anticipation_title_generator, combined_gif_generator),
        tags=["full_image", "gif"],
        name="Full Screen Gif",
    ),
    SlideGeneratorData(
        # slide_templates.generate_image_slide(
        slide_generator_types.ImageSlideGenerator.of(default_slide_title_generator, combined_gif_generator),
        tags=["single_image", "gif"],
        name="Single Image Gif",
    ),
    SlideGeneratorData(
        # slide_templates.generate_full_image_slide(
        slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), meme_reddit_image_generator),
        tags=["full_image", "meme"],
        name="Full Screen Meme",
    ),
    SlideGeneratorData(
        # slide_templates.generate_full_image_slide(
        slide_generator_types.FullImageSlideGenerator.of(
            CombinedGenerator((1, NoneGenerator()), (1, default_slide_title_generator)), neutral_image_generator
        ),
        tags=["full_image", "neutral"],
        name="Full Screen Neutral Images",
    ),
]

single_image_slide_generators_copyright_free = [
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            NoneGenerator(), deep_abstract_generator, generate_horizontal_pixabay_image
        ),
        weight_function=PeakedWeight((2, 3, 4, 5), 2.5, 1),
        tags=["full_image", "deep"],
        name="Full Screen Pixabay Deep",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            NoneGenerator(),
            goodreads_short_quote_generator,
            generate_horizontal_pixabay_image,
        ),
        tags=["full_image", "quote"],
        name="Full Screen Pixabay Goodreads",
    ),
    SlideGeneratorData(
        slide_generator_types.ImageSlideGenerator.of(default_slide_title_generator, copyright_free_generator),
        tags=["single_image"],
        name="Single Image Copyright free",
    ),
]

# WISE STATEMENTS
statement_slide_generators = [
    SlideGeneratorData(
        slide_generator_types.ImageSlideGenerator.of(inspiration_title_generator, inspirobot_image_generator),
        weight_function=ConstantWeightFunction(0.6),
        tags=["inspiration", "statement"],
        name="Inspirobot",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=generate_wikihow_bold_statement,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        tags=["bold_statement", "statement"],
        name="Wikihow Bold Statement",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=goodreads_quote_generator,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        weight_function=ConstantWeightFunction(1),
        tags=["quote", "statement"],
        name="Goodreads Quote",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=anecdote_prompt_generator,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        weight_function=ConstantWeightFunction(1.2),
        tags=["anecdote"],
        name="Anecdote",
    ),
]

statement_slide_generators_copyright_free = [
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=generate_wikihow_bold_statement,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        tags=["bold_statement", "statement"],
        name="Wikihow Bold Statement (CRF)",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=goodreads_quote_generator,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        tags=["quote", "statement"],
        name="Goodreads Quote (CRF)",
    ),
    SlideGeneratorData(
        slide_generator_types.LarqeQuoteSlideGenerator.of(
            title_generator=NoneGenerator(),
            text_generator=anecdote_prompt_generator,
            background_image_generator=generate_horizontal_pixabay_image,
        ),
        tags=["anecdote"],
        name="Anecdote (CRF)",
    ),
]

# TWO CAPTIONS VARIATIONS
captioned_images_slide_generators = [
    SlideGeneratorData(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            double_image_captions_generator,
            neutral_or_weird_image_generator,
            combined_gif_generator,
        ),
        weight_function=ConstantWeightFunction(2),
        tags=["multi_caption", "two_captions", "gif"],
        name="Two Captions Gifs",
    ),
    SlideGeneratorData(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            double_image_captions_generator,
            weird_reddit_image_generator,
            weird_punchline_image_generator,
        ),
        weight_function=ConstantWeightFunction(2),
        tags=["multi_caption", "two_captions", "reddit"],
        name="Two Captions Weird Reddit",
    ),
    SlideGeneratorData(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            double_image_captions_generator,
            weird_punchline_image_generator,
            weird_punchline_image_generator,
        ),
        weight_function=ConstantWeightFunction(2),
        tags=["multi_caption", "two_captions", "reddit"],
        name="Two Captions Weird",
    ),
    SlideGeneratorData(
        slide_generator_types.ThreeColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            triple_image_captions_generator,
            neutral_or_weird_image_generator,
            weird_punchline_image_generator,
            weird_punchline_static_image_generator,
        ),
        weight_function=ConstantWeightFunction(1),
        allowed_repeated_elements=4,
        tags=["multi_caption", "three_captions", "reddit"],
        name="Three Captions Weird",
    ),
]

captioned_images_slide_generators_copyright_free = [
    SlideGeneratorData(
        slide_generator_types.TwoColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            double_image_captions_generator,
            copyright_free_related_generator,
            normal_or_weird_copyright_free_generator,
        ),
        weight_function=ConstantWeightFunction(5),
        tags=["multi_caption", "two_captions"],
        name="Two Captions Copyright free",
    ),
    SlideGeneratorData(
        slide_generator_types.ThreeColumnImageSlideGenerator.of_images_and_tupled_captions(
            default_or_no_title_generator,
            triple_image_captions_generator,
            copyright_free_generator,
            copyright_free_related_generator,
            weird_copyright_free_generator,
        ),
        weight_function=ConstantWeightFunction(2),
        allowed_repeated_elements=4,
        tags=["multi_caption", "three_captions"],
        name="Three Captions Weird",
    ),
]

# CHART GENERATORS
own_chart_generators = [
    SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(chart.generate_yes_no_pie),
        retries=1,
        allowed_repeated_elements=4,
        weight_function=ConstantWeightFunction(2.5),
        tags=["pie_chart", "yes_no_chart", "chart"],
        name="Yes/No/Funny Chart",
    ),
    SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(chart.generate_location_pie),
        allowed_repeated_elements=4,
        retries=1,
        weight_function=ConstantWeightFunction(0.3),
        tags=["location_chart", "pie_chart", "chart"],
        name="Location Chart",
    ),
    SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(chart.generate_property_pie),
        allowed_repeated_elements=4,
        retries=1,
        weight_function=ConstantWeightFunction(0.15),
        tags=["property_chart", "pie_chart", "chart"],
        name="Property Chart",
    ),
    SlideGeneratorData(
        slide_generator_types.ChartSlideGenerator(chart.generate_correlation_curve),
        allowed_repeated_elements=4,
        retries=1,
        weight_function=ConstantWeightFunction(0.25),
        tags=["curve", "chart"],
        name="Correlation Curve",
    ),
]

chart_slide_generators = [
    SlideGeneratorData(
        slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), reddit_chart_generator),
        weight_function=ConstantWeightFunction(4),
        allowed_repeated_elements=0,
        tags=["chart"],
        name="Reddit Chart",
    )
] + own_chart_generators

# CONCLUSIONS
conclusion_slide_generators = [
    SlideGeneratorData(
        slide_generator_types.TwoImagesAndTupledCaptions(
            conclusion_title_generator,
            conclusion_two_captions_tuple_generator,
            neutral_image_generator,
            weird_reddit_image_generator,
        ),
        weight_function=PeakedWeight((-1,), 10000, 0),
        allowed_repeated_elements=10,
        tags=["conclusion"],
        name="2 Conclusions",
    ),
    SlideGeneratorData(
        slide_generator_types.ThreeImagesAndTupledCaptions(
            conclusion_title_generator,
            conclusion_three_captions_tuple_generator,
            neutral_image_generator,
            weird_reddit_image_generator,
            combined_gif_generator,
        ),
        weight_function=PeakedWeight((-1,), 8000, 0),
        allowed_repeated_elements=10,
        tags=["conclusion"],
        name="3 Conclusions",
    ),
]

conclusion_slide_generators_copyright_free = [
    SlideGeneratorData(
        slide_generator_types.TwoImagesAndTupledCaptions(
            conclusion_title_generator,
            conclusion_two_captions_tuple_generator,
            copyright_free_generator,
            weird_copyright_free_generator,
        ),
        weight_function=PeakedWeight((-1,), 10000, 0),
        allowed_repeated_elements=10,
        tags=["conclusion"],
        name="2 Conclusions (CRF)",
    ),
    SlideGeneratorData(
        slide_generator_types.ThreeImagesAndTupledCaptions(
            conclusion_title_generator,
            conclusion_three_captions_tuple_generator,
            copyright_free_generator,
            copyright_free_related_generator,
            weird_copyright_free_generator,
        ),
        weight_function=PeakedWeight((-1,), 8000, 0),
        allowed_repeated_elements=10,
        tags=["conclusion"],
        name="3 Conclusions (CRF)",
    ),
]

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
