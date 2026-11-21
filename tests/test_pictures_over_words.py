"""Pictures over words (docs/v5-plan.md, D85): fewer words, more pictures to explain and fewer bad jokes, as the models
tacked tags on to their lines to make them funny ("twice", ", on a Tuesday")."""

import pytest

from talkgenerator.plan import prompt
from talkgenerator.plan.kinds import TextField
from talkgenerator.plan.realize import clean_text, untagged


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Wore them under tights. Twice.", "Wore them under tights."),
        ("I fell asleep in the meeting, twice.", "I fell asleep in the meeting."),
        ("Independent Thinker, Allegedly", "Independent Thinker"),
        ("Waited four hours on a Tuesday", "Waited four hours"),
        ("Waited four hours, on a Tuesday!", "Waited four hours!"),
        ("The printer jammed again, apparently.", "The printer jammed again."),
        ("Are cats liquid, technically?", "Are cats liquid?"),
        ("Emails sent, at 3 a.m.", "Emails sent"),
        ("A trusted source (allegedly)", "A trusted source"),
        ("The printer jammed, again, on a Tuesday", "The printer jammed"),
        ("The stapler | The printer, allegedly | The cat", "The stapler | The printer | The cat"),
    ],
)
def test_a_tag_tacked_on_to_a_line_goes(text, expected):
    assert untagged(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Measure twice",  # (no comma: what it says, not a tag)
        "Never again",
        "Read it twice.",
        "Once bitten, twice shy",
        "Yes, twice",  # (a chart's funny answer: too little would be left)
        "Only on Tuesdays",
        "The museum is closed on Sundays",
        "Twice.",
        "Genius (allegedly)",
    ],
)
def test_a_line_whose_words_say_something_keeps_them(text):
    assert untagged(text) == text


def test_only_english_talks_lose_their_tags():
    # (the patterns are English: a Dutch "twice" is "twee keer")
    assert untagged("Independent Thinker, Allegedly", "nl") == "Independent Thinker, Allegedly"


def test_every_written_text_loses_its_tag():
    assert clean_text("Silent seating by rank. Flawless. Twice.", TextField("text", "a text", 90)) == (
        "Silent seating by rank. Flawless."
    )
    assert clean_text("Bad news, allegedly", TextField("text", "a text", 90), "de") == "Bad news, allegedly"


def test_the_prompt_asks_for_fewer_words_and_no_tacked_on_tags():
    assert "oddly specific" not in prompt.SYSTEM_PROMPT
    assert "suspiciously" not in prompt.SYSTEM_PROMPT
    assert "ten words or fewer" in prompt.SYSTEM_PROMPT
    assert "Let the pictures talk" in prompt.SYSTEM_PROMPT
    assert '"on a Tuesday"' in prompt.SYSTEM_PROMPT
