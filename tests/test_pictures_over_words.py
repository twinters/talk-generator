"""Pictures over words (docs/v5-plan.md, D85): fewer words, more pictures to explain and fewer bad jokes, as the models
tacked tags on to their lines to make them funny ("twice", ", on a Tuesday")."""

import re

import pytest

from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, themes
from talkgenerator.plan import kinds, prompt
from talkgenerator.plan.kinds import KINDS, Recipe, TextField
from talkgenerator.plan.realize import clean_text, untagged
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util
from tests.test_slide_time_limit import held as held  # (fixtures)
from tests.test_slide_time_limit import photos as photos
from tests.test_streaming import images as images


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
        ("The tuxedo is patented, obviously", "The tuxedo is patented"),
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
        "Answer honestly",
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


# LISTS OF PICTURES: a quiz's options, a tier list's tiers, red flags, an alignment chart's cells and reviews, all
# pictures in their words' place now and then


@pytest.fixture
def pictured(monkeypatch):
    """Lists of pictures on (which offline tests have off)."""
    monkeypatch.delenv("DISABLE_PICTURED_LISTS", raising=False)


_PICTURED_KINDS = {
    "quiz": 0.55,
    "tier_list": 0.55,
    "red_flags": 0.55,
    "traffic_flags": 0.55,
    "alignment_chart": 0.4,
    "reviews": 0.45,
}


def _varied(kind, seeds=400, recipe=None):
    return [(recipe or Recipe(kind)).varied(random_util.Rng(seed)) for seed in range(seeds)]


def test_a_lists_things_are_all_pictures_now_and_then(pictured):
    assert {kind for kind, made in KINDS.items() if made.pictured} == set(_PICTURED_KINDS)
    for kind, odds in _PICTURED_KINDS.items():
        made = _varied(kind)
        pictures = [recipe for recipe in made if "shown as pictures in their words' place" in recipe.brief]
        assert odds - 0.08 < len(pictures) / len(made) < odds + 0.08, kind
        items = list(KINDS[kind].pictured.items)
        for recipe in pictures:
            assert set(items) <= set(recipe.pictures), kind
            assert {f"{item}_picture" for item in items} <= set(recipe.image_queries()), kind
            # (its pictures are its surprise: no pattern break besides)
            assert "breaking the pattern" not in recipe.brief, kind


def test_the_model_writes_every_things_words_and_a_query_for_its_picture(pictured):
    recipe = next(recipe for recipe in _varied("quiz") if recipe.pictures)
    lines = prompt.slide_lines(prompt.PlannedSlide(4, "Quiz", recipe, "geese"))
    for letter in "abcd":
        assert any(line.startswith(f"- option_{letter}: ") for line in lines)
        assert any(
            line.startswith(
                f"- option_{letter}_picture_query: an image search query for a picture that takes the place"
            )
            for line in lines
        )


def test_without_lists_of_pictures_a_recipe_is_as_it_was(monkeypatch):
    plain = {kind: _varied(kind, 60) for kind in _PICTURED_KINDS}
    assert not any(
        recipe.pictures and "shown as pictures" in recipe.brief for made in plain.values() for recipe in made
    )
    monkeypatch.delenv("DISABLE_PICTURED_LISTS", raising=False)
    for kind, made in plain.items():  # (from a stream of their own: the others come out as they did)
        for before, after in zip(made, _varied(kind, 60), strict=True):
            if "shown as pictures" not in after.brief:
                assert vars(after) == vars(before), kind


def _picture(name):
    return ImageData(
        f"https://example.com/{name}.jpg",
        source="Fake photos",
        declared_size=(1600, 900),
        license_class="public-domain",
    )


def test_a_quizs_options_can_be_pictures_in_their_words_place(images):
    pictures = {"option_1": _picture("goose"), "option_2": _picture("duck"), "option_3": _picture("swan")}
    quiz = slides.QuizSlide("Which bird?", "Goose", "Duck", "Swan", "A sofa", "B", "It quacks", pictures=pictures)
    assert quiz.missing_content() == []
    elements = {element.role: element for element in quiz.to_deck_slide().elements}
    for index in (1, 2, 3):
        assert f"option_{index}" not in elements and elements[f"option_{index}_picture"].kind == "image"
        # (with its letter, on its click)
        assert elements[f"option_{index}_picture"].appears_on_click == elements[f"letter_{index}"].appears_on_click
    assert elements["option_4"].text == "A sofa"  # (no picture: its words)
    assert elements["answer"].appears_on_click > elements["option_4"].appears_on_click
    deck = SlideDeck(2, seed=1)
    deck.add_slide(0, slides.TitleSlide("Geese", None))
    deck.add_slide(1, quiz)
    deck.theme = themes.pick("clean keynote", random_util.Rng(3))
    laid = deck.to_deck().slides[1]
    assert laid.layout == "v5/quiz-pictures"
    boxes = {element.role: element.box for element in laid.elements if element.box is not None}
    # (side by side, as large as they fit, the same size)
    sizes = {
        (round(boxes[f"option_{index}_picture"].w), round(boxes[f"option_{index}_picture"].h)) for index in (1, 2, 3)
    }
    assert len(sizes) == 1 and next(iter(sizes))[0] > 350
    assert check_design(deck.to_deck()) == []
    # (a quiz in words keeps its layouts)
    words = slides.QuizSlide("Which bird?", "Goose", "Duck", "Swan", "A sofa", "B")
    assert "v5/quiz-pictures" not in engine.layouts_for(words.to_deck_slide())


def test_a_planned_quizs_pictures_take_its_options_places_or_they_stay_as_written(images, photos, pictured):
    from talkgenerator.plan.realize import realize

    recipe = next(recipe for recipe in _varied("quiz") if recipe.pictures)
    plan = kinds.SlidePlan(
        kind="quiz",
        recipe="Quiz",
        concept="geese",
        texts={
            "question": "Which one honks?",
            "option_a": "A goose",
            "option_b": "A duck",
            "option_c": "A swan",
            "option_d": "My uncle",
            "answer": "D",
        },
        images={
            f"option_{letter}_picture": f"{animal} in a tie"
            for letter, animal in zip("abcd", ("goose", "duck", "swan", "uncle"), strict=True)
        },
    )
    photos.none.add("swan in a tie")  # (no picture for option C: its words)
    made = realize(plan, recipe, {"seed": "geese"}, random_util.Rng(1), 0)
    assert made is not None
    elements = {element.role: element for element in made[0].to_deck_slide().elements}
    assert {"option_1_picture", "option_2_picture", "option_4_picture"} <= set(elements)
    assert "option_3_picture" not in elements and elements["option_3"].text == "A swan"
    assert elements["answer"].text == "D"


# UPVOTES: of the posts a Reddit search finds, the more upvoted ones' pictures are picked more often


def test_a_reddit_posts_picture_is_more_likely_picked_the_more_it_was_upvoted(monkeypatch):
    from talkgenerator.images import catalog, profiles
    from talkgenerator.sources import reddit

    posts = [
        reddit.RedditImage(f"https://i.redd.it/{number}.jpg", "u/ann (on r/pics)", None, score=score)
        for number, score in enumerate((0, 9, 99, 9_999, -5))
    ]
    monkeypatch.setattr(reddit, "search_images", lambda *arguments, **options: posts)
    found = catalog.source(profiles.reddit("weird")).search(catalog.Search(query="geese"))
    assert [round(weight, 2) for weight, _ in found] == [1.0, 2.0, 3.0, 5.0, 1.0]
    assert [image.get_image_url() for _, image in found] == [post.url for post in posts]  # (in the search's order)


# EXAMPLES COPIED: a free model wrote the bold statement's example, "Don't we all secretly want to ...?", as it was


def test_an_examples_placeholder_on_a_slide_is_a_leftover():
    from talkgenerator.checks.deck import leftovers_in

    for text in ("Don't we all secretly want to ...?", "The time I ...", "Introducing …"):
        assert leftovers_in(text), text
        assert clean_text(text, TextField("text", "a text", 90)) is None
    for text in ("But why...?", "Wait for it...", "And then… nothing", "Cats... and dogs?"):
        assert not leftovers_in(text), text


def test_no_hint_gives_an_example_with_a_gap_to_copy():
    from talkgenerator.schema import presentation_schema_types

    gaps = re.compile(r"(?<=\s)(?:\.\.\.|…)")
    for name in presentation_schema_types.schemas.names():
        for generator in presentation_schema_types.get_schema(name).slide_generators:
            recipe = generator.llm
            if recipe is not None:
                for field, hint in recipe.hints.items():
                    assert not gaps.search(hint), (name, generator.name, field, hint)
