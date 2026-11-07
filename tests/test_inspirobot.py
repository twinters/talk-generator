"""InspiroBot's posters come from the talk's seed, so a talk with one comes out the same every time it's made.

InspiroBot's API makes a new poster for every request: `talkgenerator check`, which makes every talk twice (in
parallel, then one by one) and compares the decks, found that no talk with an InspiroBot slide came out the same.
"""

import json
import re

import pytest

from talkgenerator import generator
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_schemas import slide_generators
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types
from talkgenerator.sources import inspirobot
from talkgenerator.util import http_util, image_util, random_util

_POSTER_URL = re.compile(r"https://generated\.inspirobot\.me/(\d{3})/aXm(\d{1,4})xjU\.jpg")


def _poster_url(seed, *path):
    with random_util.use(random_util.Rng(seed).child(*path)):
        return inspirobot.get_random_inspirobot_image().get_image_url()


def test_the_same_seed_gives_the_same_poster():
    assert _poster_url(7, "slide", 4, "content", 12) == _poster_url(7, "slide", 4, "content", 12)


def test_other_seeds_and_other_slides_give_other_posters():
    other_seeds = {_poster_url(seed, "slide", 4) for seed in range(100, 120)}
    other_slides = {_poster_url(7, "slide", number) for number in range(20)}
    assert len(other_seeds | other_slides) == 40  # (of 73 times 9,999)


def test_posters_are_inspirobot_s_own():
    for seed in range(300):
        found = _POSTER_URL.fullmatch(_poster_url(seed))
        assert found is not None
        assert 1 <= int(found[1]) <= inspirobot.FOLDERS
        assert 0 <= int(found[2]) < inspirobot.POSTERS_PER_FOLDER
    image = inspirobot.get_random_inspirobot_image()
    assert (image.get_source(), image.get_source_url(), image.display) == (
        "InspiroBot",
        "https://inspirobot.me",
        "direct",
    )


def test_a_poster_asks_nothing_of_inspirobot(monkeypatch):
    def no_session():
        raise AssertionError("a poster needs no request")

    monkeypatch.setattr(http_util, "get_session", no_session)  # (every request of talkgenerator's goes through it)
    assert _POSTER_URL.fullmatch(_poster_url(3)) is not None


def _talk_json(int_seed, parallel):
    """A talk of InspiroBot slides (the real slide generator) and slides of numbers, as JSON."""
    title_slide = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(
            lambda context: context["title"], lambda context: context["presenter"]
        ),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
    )
    numbers = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(
            lambda context: context["seed"], lambda context: str(random_util.randrange(1_000_000))
        ),
        weight_function=ConstantWeightFunction(0.6),
        allowed_repeated_elements=1,  # (the slide's topic, its title)
        name="Numbers",
    )
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context: "Inspired by " + context["seed"],
        slide_generators=[title_slide, slide_generators.get("Inspirobot"), numbers],
        max_allowed_tags={"title": 1},
    )
    get_schema = generator.get_schema
    generator.get_schema = lambda name: schema
    try:
        _, slide_deck, _ = generator.generate_presentation(
            schema="inspirobot", slides=8, topic="cat, bread", parallel=parallel, int_seed=int_seed, save_ppt=False
        )
    finally:
        generator.get_schema = get_schema
    return slide_deck.to_deck().to_json()


@pytest.mark.parametrize("int_seed", [1, 2, 3])
def test_a_talk_with_posters_comes_out_the_same_in_parallel_and_one_by_one(int_seed, monkeypatch):
    """What `talkgenerator check` compares, with InspiroBot's API answering as it does: a new poster every time."""
    answers = []

    class NewPoster:
        ok = True

        def __init__(self):
            answers.append(self)
            self.text = f"https://generated.inspirobot.me/a/{len(answers)}.jpg"

    def get(url, **kwargs):
        return NewPoster() if url.startswith("https://inspirobot.me/api") else None

    monkeypatch.setattr(http_util, "get", get)
    monkeypatch.setattr(image_util, "check_image", lambda image: True)  # (taken as they are: nothing is downloaded)

    in_parallel = _talk_json(int_seed, parallel=True)
    assert in_parallel == _talk_json(int_seed, parallel=False)
    assert _posters(in_parallel)
    assert answers == []


def _posters(deck_json):
    elements = (element for slide in json.loads(deck_json)["slides"] for element in slide.get("elements", ()))
    return [element["image"]["url"] for element in elements if element.get("image", {}).get("source") == "InspiroBot"]


@pytest.mark.network
def test_posters_load():
    for seed in range(3):
        with random_util.use(random_util.Rng(seed)):
            image = inspirobot.get_random_inspirobot_image()
        assert image_util.check_image(image), image.get_image_url()
