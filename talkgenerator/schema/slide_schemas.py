from talkgenerator.datastructures.slide_generator_data import (
    ConstantWeightFunction,
    PeakedWeight,
    SlideGeneratorData,
)
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.registry import Registry
from talkgenerator.slide import slide_generator_types
from talkgenerator.sources import chart
from talkgenerator.util.generator_util import CombinedGenerator, NoneGenerator

# ==============================
# =====  SLIDE GENERATORS  =====
# ==============================

# Every slide generator is registered under its (unique) name, in a group that schemas pick from.
slide_generators: Registry[SlideGeneratorData] = Registry("slide generator")


def _register(group: str, generators: list[SlideGeneratorData]) -> list[SlideGeneratorData]:
    for generator in generators:
        slide_generators.register(generator.name or "", generator, group=group)
    return generators


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
        ),
        SlideGeneratorData(
            # slide_templates.generate_image_slide_tuple(
            slide_generator_types.ImageSlideGenerator.of_tupled_captioned_image(cg.about_me_hobby_tuple_generator),
            PeakedWeight((1, 2), 3, 0),
            allowed_repeated_elements=0,
            tags=["about_me"],
            name="Weird Hobby",
        ),
    ],
)

# HISTORY
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
        ),
    ],
)


# FULL SCREEN RELATED IMAGES
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
        ),
        SlideGeneratorData(
            # slide_templates.generate_image_slide(
            slide_generator_types.ImageSlideGenerator.of(cg.default_slide_title_generator, cg.combined_gif_generator),
            tags=["single_image", "gif"],
            name="Single Image Gif",
        ),
        SlideGeneratorData(
            # slide_templates.generate_full_image_slide(
            slide_generator_types.FullImageSlideGenerator.of(NoneGenerator(), cg.meme_reddit_image_generator),
            tags=["full_image", "meme"],
            name="Full Screen Meme",
        ),
        SlideGeneratorData(
            # slide_templates.generate_full_image_slide(
            slide_generator_types.FullImageSlideGenerator.of(
                CombinedGenerator((1, NoneGenerator()), (1, cg.default_slide_title_generator)),
                cg.neutral_image_generator,
            ),
            tags=["full_image", "neutral"],
            name="Full Screen Neutral Images",
        ),
    ],
)

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
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                NoneGenerator(),
                cg.short_quote_generator,
                cg.generate_horizontal_pixabay_image,
            ),
            tags=["full_image", "quote"],
            name="Full Screen Pixabay Quote",
        ),
        SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(cg.default_slide_title_generator, cg.copyright_free_generator),
            tags=["single_image"],
            name="Single Image Copyright free",
        ),
    ],
)

# WISE STATEMENTS
statement_slide_generators = _register(
    "statement",
    [
        SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(cg.inspiration_title_generator, cg.inspirobot_image_generator),
            weight_function=ConstantWeightFunction(0.6),
            tags=["inspiration", "statement"],
            name="Inspirobot",
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.wikihow_bold_statement_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["bold_statement", "statement"],
            name="Wikihow Bold Statement",
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
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.quote_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["quote", "statement"],
            name="Quote (CRF)",
        ),
        SlideGeneratorData(
            slide_generator_types.LarqeQuoteSlideGenerator.of(
                title_generator=NoneGenerator(),
                text_generator=cg.anecdote_prompt_generator,
                background_image_generator=cg.generate_horizontal_pixabay_image,
            ),
            tags=["anecdote"],
            name="Anecdote (CRF)",
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
