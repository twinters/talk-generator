"""Offline tests of the fixes for what v5's live and benchmark runs of 2026-11-08 found (docs/v5-plan.md, D50): tag
caps of none that hold from a talk's first slide, "a title or none" that gives none, historical figures' titles that
fit every theme, cut texts that end where a clause does, quizzes whose answer agrees with their explanation, and texts
about real-world politics left out of talks that aren't about it.
(The classic templates' plural slips are for the TED content pack to fix, as it rewrites the templates.)"""

from collections import Counter

from talkgenerator.checks.deck import check_deck, check_politics, check_quizzes, real_politics
from talkgenerator.checks.design import check_design
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import clean_text, realize
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import slide_schemas
from talkgenerator.schema.presentation_schema import most_slides
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slides
from talkgenerator.sources import text_generator, wikihow
from talkgenerator.util import language_util, random_util
from talkgenerator.util.generator_util import CombinedGenerator, NoneGenerator
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_slide_types import _deck, _theme

ENGLISH = languages.ENGLISH


def _tags_of_picks(schema_name, num_slides, seeds=range(1, 201)):
    """How many of the talks (by seed) have each tag, in the slides the language model would write (the plan's picks,
    as classic talks pick their first generators too)."""
    schema = get_schema(schema_name)
    talks_with: Counter[str] = Counter()
    for seed in seeds:
        picks = schema._pick_generators(num_slides, random_util.Rng(seed))
        talks_with.update({tag for pick in picks if pick is not None for tag in pick.get_tags()})
    return talks_with


# TAG CAPS


def test_a_tags_cap_is_how_many_slides_a_talk_may_have_of_it():
    assert [most_slides(cap, 10) for cap in (0, 1, 2)] == [0, 1, 2]  # (absolute: as many slides, none for 0)
    assert [most_slides(cap, 10) for cap in (0.1, 0.2, 0.3, 0.5)] == [1, 2, 3, 5]  # (relative: a share of the slides)
    # Rounded down, but at least one: a strict 0.2 of 4 slides would forbid memes, diagrams, quotes...
    assert most_slides(0.2, 4) == most_slides(0.1, 9) == most_slides(0.3, 3) == 1


def test_an_interview_has_no_about_me_slide():
    # (the cap of none only held after a first about-me slide: 41% of interviews had one)
    assert _tags_of_picks("interview", 10)["about_me"] == 0
    assert _tags_of_picks("interview", 5)["about_me"] == 0
    interview = get_schema("interview")
    about_me = {generator for generator in interview.slide_generators if "about_me" in generator.get_tags()}
    assert about_me and about_me <= interview._calculate_prohibited_generators({}, 10)  # (classic slides too)
    assert _tags_of_picks("default", 10)["about_me"] > 50  # (the default format has them)


def test_a_section_divider_needs_a_talk_of_ten_slides():
    # (about one 9-slide talk in ten had one, where the cap's comment said none under ten slides)
    divider = next(
        generator for generator in get_schema("default").slide_generators if generator.name == "Section Divider"
    )
    assert divider.get_weight_for(4, 9) == 0 < divider.get_weight_for(4, 10)
    for format_name in ("default", "ted"):
        assert _tags_of_picks(format_name, 9)["section"] == _tags_of_picks(format_name, 7)["section"] == 0
        assert _tags_of_picks(format_name, 10)["section"] > 10


def test_short_talks_keep_their_kinds_of_slides():
    # (one of each kind with a relative cap, as before: a 4-slide talk's middle can be a meme or a diagram)
    talks_with = _tags_of_picks("default", 4, range(1, 301))
    assert all(talks_with[tag] > 0 for tag in ("meme", "diagram", "quote", "statement", "two_captions", "chart"))
    assert talks_with["about_me"] < 0.5 * 300  # (strict caps would have given 57% of them an about-me slide)


# "A TITLE OR NONE"


def _calls(generator, seeds=range(200), context=None):
    results = []
    for seed in seeds:
        with random_util.use(random_util.Rng(seed)):
            results.append(generator(context or {"seed": "cat"}))
    return results


def test_a_none_generator_picked_gives_none():
    # (it used to give way to the other generators, so "a title or none" always had a title)
    results = _calls(CombinedGenerator((1, lambda context: "A title"), (1, NoneGenerator())))
    assert 70 <= results.count(None) <= 130 and results.count("A title") == len(results) - results.count(None)
    # A generator that fails still gives way to another one
    assert set(_calls(CombinedGenerator((1, lambda context: None), (1, lambda context: "Found")), range(50))) == {
        "Found"
    }


def test_classic_captioned_pictures_and_full_screen_photos_go_without_a_title_now_and_then():
    titles = _calls(cg.default_or_no_title_generator, context={"seed": "cat"})
    assert 70 <= titles.count(None) <= 130 and all(title is None or title.strip() for title in titles)
    neutral = next(
        generator
        for generator in slide_schemas.single_image_slide_generators
        if generator.name == "Full Screen Neutral Images"
    )
    title_generator = neutral._generator._slide_content_generator._generators[0]
    assert 70 <= _calls(title_generator).count(None) <= 130


# A HISTORICAL FIGURE'S TITLE

_LONG_ACTION = "Instantly Remove Oxidation from Headlight Without Sandpaper"  # (61 letters as one word, with -ing)


def _history_titles(monkeypatch, actions, seeds=range(80)):
    monkeypatch.setattr(wikihow, "get_related_wikihow_actions", lambda seed: list(actions))
    return _calls(cg.history_person_title_generator, seeds, {"seed": "headlight"})


def test_a_historical_figures_title_never_makes_one_word_of_a_long_action(monkeypatch):
    titles = _history_titles(monkeypatch, [_LONG_ACTION, "Remove Rust", "Clean Headlights"])
    words = [word.strip('"') for title in titles for word in title.split()]
    assert max(len(word) for word in words) <= text_generator.LONGEST_WORD
    assert {"Removing-Rust", "Cleaning-Headlights"} <= set(words)  # (short ones still make one)
    # With only long actions, the titles that make one word of one give way to the others
    titles = _history_titles(monkeypatch, [_LONG_ACTION])
    assert all(title.count("-") == 0 for title in titles) and len(set(titles)) >= 3
    assert text_generator.apply_variables_to_template("My {seed.title.dashes} Accident", {"seed": "time travel"}) == (
        "My Time-Travel Accident"
    )
    assert text_generator.apply_variables_to_template("My {seed.dashes}", {"seed": "a" * 10 + " " + "b" * 10}) is None


def test_the_longest_historical_figures_title_fits_a_brutalist_theme(images):
    # (both errors of the last classic benchmark, seed 12: a 61-letter action overflowed)
    word = '"' + "Removing-Rust-Fastly"[: text_generator.LONGEST_WORD] + '"'
    made = [slides.TwoColumnImageSlide(f"First Olympic {word} Champion", "Lord Byron", _image("tall"), None, "Hm")] * 3
    for seed in range(3):
        deck = _deck(made, _theme("brutalist", seed), seed)
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], seed


# CONCLUSIONS THAT AREN'T CUT MID-CLAUSE


def test_a_cut_ends_where_a_clause_does():
    caption = KINDS["two_columns"].texts[1]
    assert caption.name == "caption_1" and caption.max_length == 40
    cases = {
        # (free models' conclusions, cut at 40 characters, read "Your plants are not decorations—they")
        "Your plants are not decorations—they're coworkers with feelings": "Your plants are not decorations",
        "Flight was lost, not gained — adaptation was the point": "Flight was lost, not gained",
        "Lighthouses never sleep. Their keepers, however, do all the time": "Lighthouses never sleep.",
        "Seagulls run the harbour: ask any keeper who has met one": "Seagulls run the harbour",
        # (and in English, before a word that opens the next clause: live, 2026-11-08, "The mountain breathes when
        # prayers" and "Seamounts grow in silence, but scream")
        "The mountain breathes when prayers are whispered into it": "The mountain breathes",
        "Seamounts grow in silence, but scream when they wake up": "Seamounts grow in silence",
        "The secret history of salt and pepper in old monasteries": "The secret history of salt and pepper",
        # (without a clause that keeps half of it, between words, as before: a comma ends no clause)
        "Even the clumsiest waddle carries a lesson in quiet grace": "Even the clumsiest waddle carries",
        "Cats, as it turns out, were always the true rulers of the night": "Cats, as it turns out, were always",
        "Trust it: lighthouses have opinions about every single ship": "Trust it: lighthouses have opinions",
        # (a range is no clause)
        "The keepers of 1890–1920 were all cats, every last one of them": "The keepers of 1890–1920 were all cats",
    }
    assert {text: clean_text(text, caption) for text in cases} == cases
    # (not in another language, whose words that open clauses aren't known: between words)
    assert clean_text("The mountain breathes when prayers are whispered into it", caption, "nl") == (
        "The mountain breathes when prayers are"
    )
    assert clean_text("Lighthouses talk, and seagulls listen to them", caption) == (
        "Lighthouses talk, and seagulls listen to them"  # (no longer than an eighth too long: whole)
    )


def test_the_model_is_asked_for_conclusions_of_a_few_words():
    conclusions = next(generator for generator in slide_schemas.conclusion_slide_generators if generator.llm)
    assert conclusions.llm is not None
    hint = prompt.field_description(conclusions.llm, conclusions.llm.written_fields()[1])
    assert "six words at most" in hint and "at most 40 characters" in hint


# QUIZZES


def _quiz(answer, explanation, option_d=None):
    texts = {
        "question": "What is a lighthouse really for?",
        "option_a": "Warning ships of rocks",
        "option_b": "Guiding ships to port",
        "option_c": "Telling the moon what time it is",
        "option_d": option_d,
        "answer": answer,
        "explanation": explanation,
    }
    with random_util.use(random_util.Rng(1)):
        return KINDS["quiz"].build(texts, {}, ENGLISH)


def _answer(slide):
    return slide.to_deck_slide().element("answer").text


def test_a_quizs_explanation_decides_which_option_is_the_answer():
    # (a free model marked one option, and its explanation said why another one was right)
    assert (
        _answer(_quiz("A", "Lighthouses have always told the time to the moon: telling the moon what time it is."))
        == "C"
    )
    assert _answer(_quiz("A", "They guide ships into port, every night.")) == "B"  # (in any form: "guide", "guiding")
    assert _answer(_quiz("C", "Option B, as every keeper knows.")) == "B"  # (by its letter)
    # An explanation that agrees, names no option, names several, or dismisses one, leaves the answer as it is
    assert _answer(_quiz("C", "The moon has to know what time it's telling.")) == "C"
    assert _answer(_quiz("C", "Ask any keeper.")) == "C"
    assert _answer(_quiz("A", "Guiding ships to port? Telling the moon the time? Both, obviously.")) == "A"
    assert _answer(_quiz("B", "Not the moon, whatever it tells you: ships need guiding to port.")) == "B"
    assert language_util.named_options("A penguin, obviously.", ["Penguins", "Owls", None, None]) == [0]


def test_the_checks_warn_of_a_quiz_whose_explanation_names_other_options(images):
    agreeing, contradicting = (
        _quiz("C", "Telling the moon what time it is, of course."),
        _quiz("A", "Guiding ships to port, or telling the moon what time it is: never warning them."),
    )
    deck = _deck([agreeing, contradicting])
    assert [(finding.check, finding.slide) for finding in check_quizzes(deck)] == [("quiz", 2)]
    assert any(finding.check == "quiz" for finding in check_deck(deck))


# REAL-WORLD POLITICS

_STATEMENT = (
    "Japan needs to earnestly reflect on its history of aggression, respect the security concerns of Asian "
    "neighbors, act prudently in the field"
)


def test_a_statement_on_real_world_politics_is_told_from_absurd_humour():
    # (what a free model wrote as a lighthouse talk's quote, 2026-11-08, seed 12)
    assert real_politics(_STATEMENT, "lighthouses") == "history of aggression"
    for political in (
        "Taiwan is an inalienable part of China, and peaceful reunification is the will of the people",
        "The Chinese government firmly opposes any separatist forces",
        "Russia's annexation of Crimea violated Ukraine's sovereignty",
        "Western hegemony must end",
    ):
        assert real_politics(political, "coffee"), political
    for humour in (
        "There are more penguins in Belgium than people.",
        "The French president secretly collects lighthouses",
        "The Great Seagull War of 1888",
        "A strict Japanese skincare regime for volcanoes",
        "Passive-aggressive office plants from Sweden",
        "The internal affairs of the lighthouse",
        "Belgian sanctions against bad coffee",
        "Chad's dictatorship over the office fridge",  # (a country's name that's a person's too)
    ):
        assert real_politics(humour, "lighthouses") is None, humour
    # (its countries are its own list, apart from the content packs, without names that are people's too)
    assert real_politics("Belgium's annexation of the moon", "coffee") and not real_politics("Chad's dictatorship")
    # A talk about the country, or about the politics, may speak of it
    assert real_politics(_STATEMENT, "the history of Japan") is None
    assert real_politics("Colonialism, as told by the British", "colonialism") is None


def test_a_planned_text_about_real_world_politics_makes_its_slide_classic(images):
    recipe = Recipe("statement", (lambda context: _image("wide"),), brief="A quote over a photo")
    context = {"topic": "lighthouses", "topics": ["lighthouses"], "seed": "lighthouse", "language": "en"}
    problems: list[str] = []

    def realized(text, problems=None):
        plan = SlidePlan(kind="statement", recipe="Quote", concept="lighthouses", texts={"text": text})
        return realize(plan, recipe, context, random_util.Rng(1), 0, problems=problems)

    assert realized(_STATEMENT, problems) is None
    assert any("real-world politics" in problem for problem in problems)
    assert realized("Never trust a seagull with your secrets") is not None
    # An optional text about it is left out, and the slide stays
    photo = Recipe("full_image", (lambda context: _image("wide"),))
    plan = SlidePlan(kind="full_image", recipe="Photo", concept="lighthouses", texts={"title": _STATEMENT})
    realized_photo = realize(plan, photo, context, random_util.Rng(1), 0)
    assert realized_photo is not None and realized_photo[0].to_deck_slide().element("title") is None


def test_the_prompt_asks_for_no_real_world_politics_and_the_checks_warn_of_it(images):
    assert "real-world politics" in prompt.SYSTEM_PROMPT
    deck = _deck([slides.LarqeQuoteSlide(None, _STATEMENT, _image("wide"))])
    assert [(finding.check, finding.severity) for finding in check_politics(deck)] == [("politics", "warning")]
    assert not check_politics(_deck([slides.LarqeQuoteSlide(None, "Never trust a seagull", _image("wide"))]))
