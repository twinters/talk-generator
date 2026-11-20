"""Offline tests of making one slide of a finished talk again (generator.regenerate_slide), for whoever shows the talk
and doesn't want that slide: a live show's operator, say (talkgenerator.com's show mode). The new slide is a classic
one of a kind the talk's format has for that place, about a word of the talk's topic, laid out in the old slide's
theme and numbered as it was.

The talks are made with test_slide_time_limit's small fake schemas and fake image finder: nothing is looked up.
"""

import pytest

from talkgenerator import generator
from talkgenerator.datastructures.slide_generator_data import PeakedWeight
from talkgenerator.models.deck import Deck
from talkgenerator.models.events import TalkFinished
from tests.test_livelier_slides import _numbers
from tests.test_llm_talks import FakeModel
from tests.test_slide_time_limit import TALK, _chart, _generator, _pictures, _schema, _texts, _title, _use
from tests.test_slide_time_limit import held as held  # (fixtures)
from tests.test_slide_time_limit import images as images
from tests.test_slide_time_limit import photos as photos
from tests.test_slide_time_limit import planned as planned


def _deck(slides=5, **options) -> Deck:
    *_, finished = generator.stream_talk("fake", slides, **{**TALK, **options})
    assert isinstance(finished, TalkFinished)
    return finished.deck


@pytest.fixture
def charts(monkeypatch):
    """A talk of charts: two kinds, each titled after itself and its slide's word, for every place but the title's."""
    slides = [
        _title(),
        _generator("Bars", PeakedWeight((1, 2, 3, 4), 100, 0), _chart("Bars")),
        _generator("Pies", PeakedWeight((1, 2, 3, 4), 100, 0), _chart("Pies")),
    ]
    return _use(monkeypatch, _schema(slides))


def test_a_slide_made_again_is_a_slide_of_the_talk_numbered_as_the_one_it_replaces(charts):
    deck = _deck()

    again = generator.regenerate_slide(deck, 2, int_seed=7)

    assert again.type == deck.slides[2].type
    title, *_ = _texts(again)
    assert title.endswith("about cats") and title.split()[0] in ("Bars", "Pies")
    assert _numbers(again) == [(3, 5)]  # (as the third of the talk's five slides: its closer isn't counted)
    assert "Made again" in again.notes and not again.closer
    # Laid out in the deck's theme, as the talk's slides are: every element in its box
    assert all(element.box is not None for element in again.elements)


def test_the_same_seed_makes_the_same_slide_again(charts):
    deck = _deck()
    assert generator.regenerate_slide(deck, 3, int_seed=11) == generator.regenerate_slide(deck, 3, int_seed=11)


def test_in_another_language_a_slide_made_again_is_a_picture_without_text(planned, photos):
    # (a classic slide would be English: as a planned slide that doesn't come out, it's a picture of its word instead)
    deck = _deck(llm=FakeModel(), language="nl")
    assert deck.language == "nl"

    again = generator.regenerate_slide(deck, 3, int_seed=2)

    assert again.type == "full_image" and _texts(again) == []
    assert [url.rsplit("/", 1)[1] for url in _pictures(again)] == ["cats-0.jpg"]  # (the talk's word: "cats")
    assert all(element.box is not None for element in again.elements)


def test_what_a_slide_made_again_mustnt_repeat_is_what_the_deck_shows(planned, photos):
    deck = _deck(llm=FakeModel())

    used = generator._used_elements(deck)

    pictures = {url for slide in deck.slides for url in _pictures(slide)}
    texts = {text for slide in deck.slides for text in _texts(slide)}
    assert pictures and {image.get_image_url() for image in used if not isinstance(image, str)} == pictures
    assert {text for text in used if isinstance(text, str)} == texts  # (not the slides' numbers, "3/5")


def test_the_title_slide_and_the_closer_are_the_talks_own(charts):
    deck = _deck()
    assert deck.slides[0].type == "title" and deck.slides[-1].closer

    with pytest.raises(ValueError, match="title slide"):
        generator.regenerate_slide(deck, 0)
    with pytest.raises(ValueError, match="closer"):
        generator.regenerate_slide(deck, len(deck.slides) - 1)
    with pytest.raises(IndexError):
        generator.regenerate_slide(deck, len(deck.slides))


def test_a_slide_that_cant_be_made_again_says_so(monkeypatch, charts):
    deck = _deck()
    monkeypatch.setattr(charts, "another_slide", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="slide 3"):
        generator.regenerate_slide(deck, 2)


def test_a_slide_made_again_reads_back_as_the_deck_format(charts):
    deck = _deck()
    again = generator.regenerate_slide(deck, 1, int_seed=5)

    remade = deck.model_copy(update={"slides": (deck.slides[0], again, *deck.slides[2:])})
    assert Deck.from_json(remade.to_json()).slides[1] == again
