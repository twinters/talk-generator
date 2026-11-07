"""Offline tests: a seed decides a talk.

A talk is a series of random choices: its title and presenter, every slide's topic, slide generator and content. The
same seed has to make the same choices every time, in parallel (the CLI's default) as well as one by one (as on
talkgenerator.com), and in every Python process. Live sources can return other content from one run to the next, so
these tests use fake ones, which take their time like real ones: while one thread waits, the others draw.
"""

import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator import generator
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.render import charts
from talkgenerator.schema import presentation_schema
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.sources import text_generator
from talkgenerator.util import random_util

NUM_SLIDES = 9
SEEDS = [0, 1, 42, 2024, 31337]

_PHRASES = {
    "origin": ["#adjective# #things#", "why #things# #verb#", "#things# and #things#"],
    "adjective": ["surprising", "hidden", "forgotten", "electric", "tiny", "endless"],
    "things": ["ideas", "maps", "spoons", "clouds", "ladders", "secrets", "engines"],
    "verb": ["matter", "fail", "win", "travel", "sing"],
}


def _slowly(text):
    def generate(context):
        time.sleep(0.001)
        return text(context)

    return generate


def _phrase(context):
    return f"{context['seed']}: {text_generator.new_tracery_grammar(_PHRASES).flatten('#origin#')}"


def _colour(context):
    # Few options, so slides often repeat each other's colour and have to try again (or give up)
    return random_util.choice(["red", "green", "blue", "gold", "teal", "mauve"])


def _slide_generator(name, weight, text, tags=(), flaky=False):
    def title(context):
        if flaky and random_util.random() < 0.5:
            return None  # a missing title: the try fails, like a source that couldn't deliver
        return name

    return SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(title, _slowly(text)),
        weight_function=ConstantWeightFunction(weight),
        allowed_repeated_elements=1,  # the slide's title, the generator's name, comes back on all its slides
        tags=list(tags),
        name=name,
    )


def fake_schema():
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
        title_generator=lambda context: (
            random_util.choice(["In praise of", "Rethinking", "The end of"]) + " " + context["seed"]
        ),
        slide_generators=[
            title_slide,
            _slide_generator("Colours", 4, _colour),
            _slide_generator("Phrases", 2, _phrase),
            _slide_generator("Statements", 4, _phrase, tags=["statement"]),  # capped: parallel picks collide
            _slide_generator("Flaky", 2, _phrase, flaky=True),
        ],
        max_allowed_tags={"title": 1, "statement": 2},
    )


def talk_json(int_seed, parallel):
    """Generate a talk the way the CLI and talkgenerator.com do, and return its deck as JSON."""
    schema = fake_schema()
    get_schema = generator.get_schema
    generator.get_schema = lambda name: schema
    random.seed()  # whatever state Python's own random generator is in, the seed decides
    try:
        _, slide_deck, _ = generator._generate_presentation(
            schema="fake",
            slides=NUM_SLIDES,
            topic="cat, dog, bread, house",
            parallel=parallel,
            int_seed=int_seed,
            save_ppt=False,
        )
    finally:
        generator.get_schema = get_schema
    return slide_deck.to_deck().to_json()


@pytest.fixture
def pool_rounds(monkeypatch):
    """Count the rounds of parallel generation."""
    rounds = []

    class CountingPool(presentation_schema.ThreadPool):
        def __init__(self, *args, **kwargs):
            rounds.append(kwargs.get("processes"))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(presentation_schema, "ThreadPool", CountingPool)
    return rounds


@pytest.mark.parametrize("parallel", [False, True], ids=["one by one", "parallel"])
@pytest.mark.parametrize("int_seed", SEEDS)
def test_the_same_seed_gives_the_same_talk(int_seed, parallel):
    assert talk_json(int_seed, parallel) == talk_json(int_seed, parallel)


@pytest.mark.parametrize("int_seed", SEEDS)
def test_parallel_gives_the_same_talk_as_one_by_one(int_seed):
    assert talk_json(int_seed, parallel=True) == talk_json(int_seed, parallel=False)


def test_parallel_rounds_settle_conflicts(pool_rounds):
    """The fake schema's tag cap and repeated colours make parallel picks collide, so some talks need more rounds,
    in which the remaining slides are worked out again."""
    talks_needing_more_rounds = 0
    for int_seed in SEEDS:
        pool_rounds.clear()
        talk_json(int_seed, parallel=True)
        assert pool_rounds[0] == NUM_SLIDES
        talks_needing_more_rounds += len(pool_rounds) > 1
    assert talks_needing_more_rounds > 0


def test_another_seed_gives_another_talk():
    assert len({talk_json(int_seed, parallel=False) for int_seed in SEEDS}) == len(SEEDS)


def test_a_talk_without_a_seed_tells_its_seed():
    deck = generator.Deck.from_json(talk_json(None, parallel=True))
    assert isinstance(deck.seed, int)
    assert talk_json(deck.seed, parallel=True) == deck.to_json()


def test_a_single_slide_is_the_same_for_the_same_seed():
    def slide_3(int_seed):
        context = {"topic": "cat", "topics": ["cat"], "presenter": "Ann", "title": "Cats", "seed": "cat"}
        slide, _, slide_generator, _ = fake_schema().generate_slide(context, 3, NUM_SLIDES, set(), int_seed=int_seed)
        return slide_generator.name, slide.to_deck_slide()

    assert slide_3(0) == slide_3(0)
    assert slide_3(7) == slide_3(7)


def test_notes_are_the_same_in_every_run():
    """A chart slide's notes used to hold the memory addresses of its chart data and chart style, found by
    `talkgenerator check`: they differ in every run, and so did the deck."""

    def chart_content(context):
        data = ChartData()
        data.categories = ["Yes", "No"]
        data.add_series("", [0.5, 0.5])
        return "Do cats dream?", XL_CHART_TYPE.PIE, data, charts.set_pie_properties

    slide_generator = SlideGeneratorData(slide_generator_types.ChartSlideGenerator(chart_content), name="Chart")
    notes = [slide_generator.generate({"seed": "cat"}, set())[0].to_deck_slide().notes for _ in range(2)]
    assert notes[0] == notes[1]
    assert "0x" not in notes[0]
    assert "<set_pie_properties>" in notes[0]


# THE STREAMS


def test_a_stream_doesnt_depend_on_other_streams():
    first = random_util.Rng(5).child("slide", 1)
    talk = random_util.Rng(5)
    for _ in range(100):
        talk.child("slide", 0).random()
        talk.random()
    assert talk.child("slide", 1).random() == first.random()


def test_streams_are_the_same_in_every_version_and_process():
    """Changing how streams are derived changes every seeded talk, so it should take changing this test too."""
    assert random_util.Rng(42).child("slide", 3, "pick", 0).randrange(1_000_000) == 40899


def test_outside_a_talk_python_s_random_seed_still_works():
    random.seed(3)
    expected = [random.choice(range(100)) for _ in range(5)], random.uniform(0, 1)
    random.seed(3)
    assert ([random_util.choice(range(100)) for _ in range(5)], random_util.uniform(0, 1)) == expected


def test_a_stream_only_applies_to_its_own_thread():
    seen_in_thread = []
    with random_util.use(random_util.Rng(1)) as rng:
        thread = threading.Thread(target=lambda: seen_in_thread.append(random_util.current()))
        thread.start()
        thread.join()
        assert random_util.current() is rng
    assert seen_in_thread[0] is not rng


def test_tracery_draws_from_the_current_stream():
    def phrases(int_seed):
        with random_util.use(random_util.Rng(int_seed)):
            return [text_generator.new_tracery_grammar(_PHRASES).flatten("#origin#") for _ in range(10)]

    assert phrases(1) == phrases(1)
    assert phrases(1) != phrases(2)


# TEMPLATES


def test_longer_template_variables_are_filled_in_first():
    # With {seed.plural} renamed first, {seed.plural.title} used to turn into "{seed_plural.title}"
    generator_ = text_generator.TemplatedTextGenerator(templates_list=["{seed.plural} and {seed.plural.title}"])
    for _ in range(10):
        assert generator_.generate({"seed": "cat"}) == "cats and Cats"


def test_template_functions_run_in_the_same_order_whatever_order_they_come_in(monkeypatch):
    calls = []
    for name in ("first", "second", "third"):
        monkeypatch.setitem(text_generator.known_functions, name, lambda word, name=name: calls.append(name) or word)
    template = "{a.first} {b.second} {c.third}"
    found = list(text_generator.get_format_variables_and_functions(template))

    orders = []
    for variables in (found, list(reversed(found))):
        calls.clear()
        text_generator.apply_functions_to_variables(template, {"a": "x", "b": "y", "c": "z"}, variables)
        orders.append(list(calls))
    assert orders[0] == orders[1]


_IN_ANOTHER_PROCESS = """
from talkgenerator.sources import text_generator
from talkgenerator.util import random_util
from tests.test_seeds import talk_json

# Template functions that draw random numbers: which one draws first used to depend on the order of a set
text_generator.known_functions["pick_a"] = lambda word: word + str(random_util.randrange(1000))
text_generator.known_functions["pick_b"] = lambda word: word + str(random_util.randrange(1000))
with random_util.use(random_util.Rng(9)):
    print(text_generator.apply_variables_to_template("{x.pick_a} {y.pick_b}", {"x": "a", "y": "b"}))
print(talk_json(42, parallel=True))
"""


def test_the_same_seed_gives_the_same_talk_in_every_process():
    """Python randomizes the order of sets of strings for every process: none of that may leak into a talk."""
    outputs = set()
    for hash_seed in ("1", "2"):
        result = subprocess.run(
            [sys.executable, "-c", _IN_ANOTHER_PROCESS],
            cwd=Path(__file__).parent.parent,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1
