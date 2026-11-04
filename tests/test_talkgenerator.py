"""End-to-end generation tests. These talk to all the live content sources."""

import logging
import random

import pytest

from talkgenerator import generator
from talkgenerator.schema import slide_schemas
from talkgenerator.slide import powerpoint_slide_creator
from tests.support import requires_keys

pytestmark = pytest.mark.network


def _cli_args(tmp_path, *extra):
    return generator.get_argument_parser().parse_args(
        [
            "--topic",
            "cat",
            "--num_slides",
            "3",
            "--int_seed",
            "123",
            "--open_ppt",
            "false",
            "--print_logs",
            "false",
            "--output_folder",
            str(tmp_path),
            *extra,
        ]
    )


def test_serial(tmp_path):
    ppt, _, output_file = generator.generate_presentation_using_cli_arguments(
        _cli_args(tmp_path, "--parallel", "false")
    )
    assert len(ppt.slides) == 3
    assert output_file.startswith(str(tmp_path))


def test_parallel_multiple_topics(tmp_path):
    ppt, _, _ = generator.generate_presentation_using_cli_arguments(
        _cli_args(tmp_path, "--topic", "cat, dog, bread, house", "--num_slides", "6")
    )
    assert len(ppt.slides) == 6


def test_to_dictionary():
    _, slide_deck, _ = generator.generate_presentation(
        schema="default",
        slides=3,
        topic="cat",
        parallel=True,
        int_seed=123,
        save_ppt=False,
    )
    slides_dict = slide_deck.to_slide_deck_dictionary()
    assert len(slides_dict) == 3


@requires_keys(
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_USER_AGENT",
    "UNSPLASH_ACCESS_KEY",
    "PIXABAY_KEY",
    "PEXELS_KEY",
)
def test_all_slide_generators():
    """Every slide generator must produce a slide (some only use keyed sources such as Reddit)."""
    basic_presentation_context = {
        "topic": "dog",
        "seed": "cat",
        "presenter": "An O. Nymous",
        "title": "Mock title",
    }
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    failed = []
    for slide_generator in slide_schemas.all_slide_generators:
        logging.info("Testing Slide Generator: %s", slide_generator)
        random.seed(123)
        result = slide_generator.generate(basic_presentation_context, [])
        if not result:
            failed.append(str(slide_generator))
            continue
        slide, _ = result
        slide.create_powerpoint_slide(presentation)
    assert not failed, f"These slide generators produced nothing: {failed}"
