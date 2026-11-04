from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_schemas import *
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types

# ==================================
# =====  PRESENTATION SCHEMAS  =====
# ==================================


# This object holds all the information about how to generate the presentation
presentation_schema = PresentationSchema(
    # Basic powerpoint generator
    powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
    # Topic per slide generator
    seed_generator=slide_topic_generators.SideTrackingTopicGenerator,
    # Title of the presentation
    title_generator=talk_title_generator,
    # Slide generators
    slide_generators=all_slide_generators,
    # Max tags
    max_allowed_tags=default_max_allowed_tags,
)

# Interview schema: Disallow about_me slides
interview_max_allowed_tags = default_max_allowed_tags.copy()
interview_max_allowed_tags["about_me"] = 0

interview_schema = PresentationSchema(
    # Basic powerpoint generator
    powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
    # Topic per slide generator
    seed_generator=slide_topic_generators.SideTrackingTopicGenerator,
    # Title of the presentation
    title_generator=talk_title_generator,
    # Slide generators
    slide_generators=all_slide_generators,
    # Max tags
    max_allowed_tags=interview_max_allowed_tags,
)

# Test schema: for testing purposes

test_schema = PresentationSchema(
    # Basic powerpoint generator
    powerpoint_slide_creator.create_new_powerpoint,
    # Title of the presentation
    title_generator=talk_title_generator,
    # Topic per slide generator
    # seed_generator=slide_topic_generators.SideTrackingTopicGenerator,
    seed_generator=slide_topic_generators.IdentityTopicGenerator,
    # Slide generators
    slide_generators=title_slide_generators
    + [
        SlideGeneratorData(
            # slide_templates.generate_image_slide(
            slide_generator_types.ImageSlideGenerator.of(inspiration_title_generator, generate_unsplash_image),
            weight_function=ConstantWeightFunction(8),
            allowed_repeated_elements=10,
            name="Test sourcing",
        )
    ],
    # ignore_weights=True,
)


# TED schema: using only images from approved sources
ted_schema = PresentationSchema(
    # Basic powerpoint generator
    powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
    # Topic per slide generator
    seed_generator=lambda topics, num_slides: slide_topic_generators.SideTrackingTopicGenerator(
        topics=topics, num_slides=num_slides, topic_return_period_range=range(2, 4)
    ),
    # Title of the presentation
    title_generator=talk_ted_title_generator,
    # Slide generators
    slide_generators=title_slide_generators
    + history_slide_generators_copyright_free
    + single_image_slide_generators_copyright_free
    + statement_slide_generators_copyright_free
    + captioned_images_slide_generators_copyright_free
    + own_chart_generators
    + conclusion_slide_generators_copyright_free,
    # Max tags
    max_allowed_tags={
        # Absolute maxima
        "title": 1,
        "history": 1,
        "anecdote": 1,
        "location_chart": 1,
        "chart": 1,
        "deep": 2,
        # Relative (procentual) maxima
        "two_captions": 0.3,
        "three_captions": 0.2,
        "multi_captions": 0.3,
        "gif": 0.5,
        "quote": 0.2,
        "statement": 0.2,
    },
)

schemas = {
    "default": presentation_schema,
    "interview": interview_schema,
    "test": test_schema,
    "ted": ted_schema,
}


def get_schema(name):
    return schemas[name]
