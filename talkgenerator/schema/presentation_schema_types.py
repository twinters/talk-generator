"""The presentation schemas: which groups of slide generators a talk is made of, and how many of each kind."""

from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.registry import Registry
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types

schemas: Registry[PresentationSchema] = Registry("presentation schema")

# The groups of slide generators (see slide_schemas.py) that each schema draws from
DEFAULT_GROUPS = (
    "title",
    "about_me",
    "history",
    "single_image",
    "statement",
    "captioned_images",
    "reddit_chart",
    "chart",
    "diagram",
    "numbers",
    "quiz",
    "mockups",
    "memes",
    "fun_fact",
    "karaoke",
    "structure",
    "conclusion",
)
COPYRIGHT_FREE_GROUPS = (
    "title",
    "history_copyright_free",
    "single_image_copyright_free",
    "statement_copyright_free",
    "captioned_images_copyright_free",
    "chart",
    "diagram",
    "numbers",
    "quiz",
    "mockups_copyright_free",
    "fun_fact_copyright_free",
    "karaoke",
    "structure",
    "conclusion_copyright_free",
)

# Default schema: all kinds of slides, images from every source
presentation_schema = schemas.register(
    "default",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=slide_topic_generators.SideTrackingTopicGenerator,
        title_generator=cg.talk_title_generator,
        title_candidates=(cg.wikihow_title_generator,),
        slide_generators=slide_generators.groups(*DEFAULT_GROUPS),
        max_allowed_tags=default_max_allowed_tags,
    ),
)

# Interview schema: no "about me" slides
interview_max_allowed_tags = default_max_allowed_tags.copy()
interview_max_allowed_tags["about_me"] = 0

interview_schema = schemas.register(
    "interview",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=slide_topic_generators.SideTrackingTopicGenerator,
        title_generator=cg.talk_title_generator,
        title_candidates=(cg.wikihow_title_generator,),
        slide_generators=slide_generators.groups(*DEFAULT_GROUPS),
        max_allowed_tags=interview_max_allowed_tags,
    ),
)

# Test schema: for testing purposes
_test_sourcing_slide_generator = slide_generators.register(
    "Test sourcing",
    SlideGeneratorData(
        slide_generator_types.ImageSlideGenerator.of(cg.inspiration_title_generator, cg.generate_unsplash_image),
        weight_function=ConstantWeightFunction(8),
        allowed_repeated_elements=10,
        name="Test sourcing",
        llm=Recipe("image", (cg.generate_unsplash_image,), brief="A photo with a title"),
    ),
    group="test",
)

test_schema = schemas.register(
    "test",
    PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        title_generator=cg.talk_title_generator,
        title_candidates=(cg.wikihow_title_generator,),
        seed_generator=slide_topic_generators.IdentityTopicGenerator,
        slide_generators=slide_generators.groups("title", "test"),
    ),
)

# TED schema: only images from sources that allow reuse, by its slide generators (as in v4) and its license policy:
# everything but fair use (see talkgenerator.images.licenses)
ted_schema = schemas.register(
    "ted",
    PresentationSchema(
        license_policy="open",
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=lambda topics, num_slides: slide_topic_generators.SideTrackingTopicGenerator(
            topics=topics, num_slides=num_slides, topic_return_period_range=range(2, 4)
        ),
        title_generator=cg.talk_ted_title_generator,
        title_candidates=(cg.wikihow_title_generator,),
        slide_generators=slide_generators.groups(*COPYRIGHT_FREE_GROUPS),
        max_allowed_tags={
            # Absolute maxima
            "title": 1,
            "history": 1,
            "anecdote": 1,
            "location_chart": 1,
            "trend_chart": 1,
            "bar_chart": 1,
            "venn_diagram": 1,
            "matrix_diagram": 1,
            "chart": 1,
            "deep": 2,
            "big_number": 1,
            "kpi": 1,
            "quiz": 1,
            "social_post": 1,
            "news": 1,
            "fun_fact": 1,
            "acronym": 1,
            "dare": 1,
            "flowchart": 1,
            "tier_list": 1,
            "wall_of_text": 1,
            "alignment_chart": 1,
            "red_flags": 1,
            "reviews": 1,
            "error_message": 1,
            "agenda": 1,
            "questions": 1,
            "timeline": 1,
            "pyramid": 1,
            "funnel": 1,
            "cycle": 1,
            "org_chart": 1,
            "iceberg": 1,
            # Relative (procentual) maxima
            "section": 0.1,
            "diagram": 0.2,
            "two_captions": 0.3,
            "three_captions": 0.2,
            "multi_captions": 0.3,
            "gif": 0.5,
            "quote": 0.2,
            "statement": 0.2,
        },
    ),
)


def get_schema(name):
    return schemas.get(name)
