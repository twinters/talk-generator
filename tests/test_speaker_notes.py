"""Offline tests: generation details stay out of the speaker notes unless asked for."""

from talkgenerator import generator
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.slide.slide_deck import SlideDeck


def _deck_with_note():
    slide = slides.TitleSlide("A talk about cats", "By An O. Nymous")
    slide.set_note("Seed: cat\nGenerator: Title slide")
    deck = SlideDeck(1)
    deck.add_slide(0, slide)
    return deck


def test_notes_are_empty_by_default():
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    (ppt_slide,) = _deck_with_note().save_to_powerpoint(presentation)
    assert not ppt_slide.has_notes_slide


def test_debug_notes_explain_the_generation():
    presentation = powerpoint_slide_creator.create_new_powerpoint()
    (ppt_slide,) = _deck_with_note().save_to_powerpoint(presentation, debug_notes=True)
    assert "Generator: Title slide" in ppt_slide.notes_slide.notes_text_frame.text


def test_cli_flag():
    parser = generator.get_argument_parser()
    assert parser.parse_args(["--topic", "cat"]).debug_notes is False
    assert parser.parse_args(["--topic", "cat", "--debug_notes"]).debug_notes is True
