"""Offline tests: the same int_seed gives the same talk.

A talk is a series of random choices: the slide generator for every slide, its topic, its texts. With a seed, every
run makes the same choices, also when the slides would be generated in parallel (the CLI's default), where threads
would take turns drawing from Python's one shared random generator. Live sources can still return other content from
one run to the next, so these tests use fake ones.
"""

import random
import time

import pytest
import tracery

from talkgenerator import generator
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.schema.presentation_schema import PresentationSchema, SlideGeneratorContext
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.util.generator_util import StaticGenerator

NUM_SLIDES = 8

# Tracery picks its rules with the global random generator too
_phrases = tracery.Grammar(
    {
        "origin": ["#adjective# #things#", "why #things# #verb#", "#things#, #things# and #things#"],
        "adjective": ["surprising", "hidden", "forgotten", "electric", "tiny", "endless"],
        "things": ["ideas", "maps", "spoons", "clouds", "ladders", "secrets", "engines"],
        "verb": ["matter", "fail", "win", "travel", "sing"],
    }
)


def _text_from_a_slow_source(presentation_context):
    """Random choices with waits in between, like a source waiting for its API: while one thread waits, the others
    draw from the random generator."""
    phrase = _phrases.flatten("#origin#")
    time.sleep(0.002)
    number = random.randrange(1_000_000)
    time.sleep(0.002)
    return f"{presentation_context['seed']}: {phrase} ({number})"


def _slide_generator(name, weight):
    return SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(StaticGenerator(name), _text_from_a_slow_source),
        weight_function=ConstantWeightFunction(weight),
        allowed_repeated_elements=1,  # the slide's title, the generator's name, is the same on all its slides
        name=name,
    )


def _fake_schema():
    title_slide = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(
            lambda context: context["title"], lambda context: context["presenter"]
        ),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
    )
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,  # a random one of the topics for every slide
        title_generator=lambda context: random.choice(["In praise of", "Rethinking"]) + " " + context["seed"],
        slide_generators=[title_slide]
        + [_slide_generator(name, weight) for name, weight in [("Anecdote", 4), ("Statement", 3), ("Quote", 2)]],
        max_allowed_tags={"title": 1},
    )


@pytest.fixture(autouse=True)
def _restore_the_global_random_state():
    state = random.getstate()
    yield
    random.setstate(state)


@pytest.fixture
def fake_schema(monkeypatch):
    schema = _fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _talk(int_seed, parallel):
    """Generate a talk the way the CLI and talkgenerator.com do. Every slide is a (title, subtitle) pair: the slide
    generator's name and its text, or the talk's title and its (random) presenter on the title slide."""
    random.seed()  # whatever state the random generator is in, the seed decides
    _, slide_deck, _ = generator.generate_presentation(
        schema="fake",
        slides=NUM_SLIDES,
        topic="cat, dog, bread, house",
        parallel=parallel,
        int_seed=int_seed,
        save_ppt=False,
    )
    return [(slide["title"], slide["subtitle"]) for slide in slide_deck.to_slide_deck_dictionary()]


@pytest.mark.parametrize("parallel", [False, True], ids=["serial", "parallel"])
@pytest.mark.parametrize("int_seed", [0, 42])
def test_the_same_seed_gives_the_same_talk(fake_schema, int_seed, parallel):
    talk = _talk(int_seed, parallel)
    assert len(talk) == NUM_SLIDES
    assert _talk(int_seed, parallel) == talk


@pytest.mark.parametrize("int_seed", [0, 42])
def test_with_a_seed_parallel_and_serial_give_the_same_talk(fake_schema, int_seed):
    assert _talk(int_seed, parallel=True) == _talk(int_seed, parallel=False)


def test_another_seed_gives_another_talk(fake_schema):
    assert _talk(0, parallel=False) != _talk(42, parallel=False)


def test_parallel_slide_generation_reseeds_for_seed_0_too(fake_schema):
    # A parallel worker reseeds the random generator for its slide, which it skipped for seed 0
    worker = SlideGeneratorContext(
        presentation_schema=fake_schema,
        presentation_context={"topic": "cat", "topics": ["cat", "dog"], "presenter": "A. Nymous", "title": "Cats"},
        seed_generator=IdentityTopicGenerator(["cat", "dog"], NUM_SLIDES),
        num_slides=NUM_SLIDES,
        used_elements=set(),
        int_seed=0,
    )

    def slide_3():
        slide, _, slide_generator, _ = worker(3)
        return slide_generator.name, slide.to_slide_dictionary()

    random.seed(1)
    first = slide_3()
    random.seed(2)
    assert slide_3() == first
