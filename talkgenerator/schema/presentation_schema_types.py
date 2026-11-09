"""The presentation schemas: which groups of slide generators a talk is made of, and how many of each kind. And the
format a talk's seed picks, when the talk leaves it to its seed (see pick_format)."""

from typing import TYPE_CHECKING, Final

from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
from talkgenerator.plan.kinds import Recipe
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.formats import academic, corporate, keynote, pitch
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.registry import Registry
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.personas import Persona

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
    "problem",
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
    "problem",
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
            "problem_slide": 1,
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


def _wandering(topics, num_slides):
    """The topics of a talk's slides that wander from its topic and come back to it every two or three slides."""
    return slide_topic_generators.SideTrackingTopicGenerator(
        topics=topics, num_slides=num_slides, topic_return_period_range=range(2, 4)
    )


# TALK FORMATS BEYOND THE TED-LIKE TALKS (docs/v5-plan.md, section 7; see talkgenerator.schema.formats): each its arc
# of slides, its content pack, its brief for the language model, and its favourite personas and themes. Their images
# come from every source, as the default schema's do; their arcs' slides need none that's fair use, so they work with
# the open license policy too.
pitch_schema = schemas.register(
    "pitch",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_wandering,
        title_generator=pitch.title_generator,
        slide_generators=slide_generators.group("pitch"),
        max_allowed_tags=pitch.CAPS,
        format=pitch.PITCH,
    ),
)
academic_schema = schemas.register(
    "academic",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_wandering,
        title_generator=academic.title_generator,
        slide_generators=slide_generators.group("academic"),
        max_allowed_tags=academic.CAPS,
        format=academic.ACADEMIC,
    ),
)
corporate_schema = schemas.register(
    "corporate",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_wandering,
        title_generator=corporate.title_generator,
        slide_generators=slide_generators.group("corporate"),
        max_allowed_tags=corporate.CAPS,
        format=corporate.CORPORATE,
    ),
)
keynote_schema = schemas.register(
    "keynote",
    PresentationSchema(
        powerpoint_creator=powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=_wandering,
        title_generator=keynote.title_generator,
        slide_generators=slide_generators.group("keynote"),
        max_allowed_tags=keynote.CAPS,
        format=keynote.KEYNOTE,
    ),
)


# THE FORMAT A TALK'S SEED PICKS (decisions D61 and D63): a talk that leaves its format to its seed (schema "random")
# gets one of these, by these weights times its persona's multipliers (talkgenerator.personas.Persona.formats), so a
# startup founder pitches and a disgraced professor gives academic talks far more often than the others do (about two
# talks in five; half of theirs are TED-like still), and every format keeps some chance with every persona. Most talks
# are TED-like: 7 in 10 over all the personas, 8 in 10 without one, as the user asked after reviewing 35 talks
# (2026-11-09), with the pitch and the academic talk the rarest. Not ted: that's the TED-like talk with copyright-free
# images only, which is a choice of license rather than of format: a talk asks for those images with license_policy
# "open", whatever format its seed picks (the formats' arcs need no image that's fair use). Nor interview and test.
RANDOM: Final = "random"
FORMAT_WEIGHTS: Final[dict[str, float]] = {"default": 20, "pitch": 1, "academic": 1, "corporate": 1.5, "keynote": 1.5}


def choices() -> tuple[str, ...]:
    """What generate_presentation's schema takes: random (a format the talk's seed picks) or a schema's name."""
    return (RANDOM, *schemas.names())


def format_odds(persona: "Persona | None" = None) -> dict[str, float]:
    """How likely a talk that leaves its format to its seed is to be of each format (FORMAT_WEIGHTS), with that
    persona (or with none), from 0 to 1."""
    multipliers = persona.formats if persona is not None else {}
    weights = {name: weight * multipliers.get(name, 1.0) for name, weight in FORMAT_WEIGHTS.items()}
    total = sum(weights.values())
    return {name: weight / total for name, weight in weights.items()}


def pick_format(chosen: str, rng: random_util.Rng, persona: "Persona | None" = None) -> str:
    """The talk's format, as the name of its schema: the one chosen, or for random, one the talk's dice pick (rng: the
    talk's, whose "format" stream picks it), after its persona, by the odds that persona gives them (format_odds)."""
    if chosen != RANDOM:
        return chosen
    odds = format_odds(persona)
    with random_util.use(rng.child("format")):
        return random_util.weighted_random([(odds[name], name) for name in odds]) or next(iter(odds))


def get_schema(name):
    return schemas.get(name)
