"""Offline tests of decision D69 (docs/v5-plan.md): the problem slide, a talk's why, early on, as the user found that
"what makes a good pitch and a good academic deck is typically that they explain the WHY / problem really well in the
beginning" (2026-11-09).

A problem slide has a short heading on a sticker, the problem in big words, and a line under it that makes it hit
home, which appears on a click; a picture of it behind it, or one beside it that shows it (generated, in a talk that
generates pictures). The talk's dice pick its angle (a weird problem, an everyday one, the topic running into something
else, the problem typical of the topic, or a real one: a wikiHow how-to about the topic), for a classic slide as for a
planned one. A pitch's problem part opens with one most of the time, an academic talk's new motivation part too, and
some TED-like talks have one as their third slide; never two in a talk.
"""

from __future__ import annotations

import collections
import datetime
import itertools

import pytest

from talkgenerator import facts
from talkgenerator.checks.deck import check_completeness, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.design import engine, themes
from talkgenerator.images import context as image_context
from talkgenerator.images import profiles
from talkgenerator.images.generation import ImageBudget, ImageGeneration
from talkgenerator.images.profiles import Profile, SourceUse
from talkgenerator.models.deck import ImageElement, ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import prompt
from talkgenerator.plan.kinds import (
    KINDS,
    PROBLEM_ANGLES,
    PROBLEM_DETAIL,
    PROBLEM_KICKER,
    PROBLEM_TEXT,
    Recipe,
    problem_variants,
)
from talkgenerator.plan.languages import ENGLISH, language
from talkgenerator.plan.realize import realize
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import formats, slide_schemas
from talkgenerator.schema.formats import academic, pitch
from talkgenerator.schema.presentation_schema import _fact_use
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.schema.slide_schemas import slide_generators
from talkgenerator.slide import slides
from talkgenerator.sources import flavour, packs, text_generator, wikihow
from talkgenerator.util import random_util
from tests.test_content_pack import LONG, OFFLINE, _longest
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_design import _OPEN_PAIRINGS, _with_fonts
from tests.test_facts import web as web  # the fake Wikipedia (a fixture)
from tests.test_formats import _context
from tests.test_formats import offline as offline  # images and related words without the internet (a fixture)
from tests.test_generated_images import FakePainter
from tests.test_pictures_on_text_slides import stock as stock  # a fake stock source's pictures (a fixture)
from tests.test_slide_types import _deck, _theme

FAMILIES = list(themes.FAMILIES)
SHORT = ("The problem", "Every morning, your coffee is already cold.", "Three billion cups a day.")
_LONG_WORD = "Brandweerkazernedeur"


def _problem_slide(texts=SHORT, picture="behind"):
    """A problem slide of the texts (heading, problem, line), with a picture behind it, beside it, or none."""
    pictures = {"behind": {"background": _image("wide")}, "beside": {"photo": _image("tall")}}.get(picture, {})
    return slides.ProblemSlide(*texts, **pictures)


def _longest_texts(word="Expectation"):
    """A heading, a problem and a line as long as a problem slide takes them, of words, starting with the word."""
    return tuple(
        " ".join([word] + ["Expectation"] * (limit // 11 + 1))[:limit].strip()
        for limit in (PROBLEM_KICKER, PROBLEM_TEXT, PROBLEM_DETAIL)
    )


# THE SLIDE


def test_a_problem_slide_has_a_heading_the_problem_and_a_line_that_appears_on_a_click(images):
    slide = KINDS["problem"].build(
        {"kicker": "The problem", "problem": SHORT[1], "detail": SHORT[2]}, {"background": _image("wide")}, ENGLISH
    )
    assert isinstance(slide, slides.ProblemSlide) and slide.missing_content() == []
    elements = {element.role: element for element in slide.to_deck_slide().elements}
    assert set(elements) == {"background", "kicker", "problem", "detail"}
    assert [role for role, element in elements.items() if element.appears_on_click] == ["detail"]
    assert elements["detail"].appears_on_click == 1
    # (a model's empty heading: talkgenerator's word, in the talk's language)
    dutch = KINDS["problem"].build({"kicker": " ", "problem": "Elke ochtend is je koffie al koud."}, {}, language("nl"))
    assert {
        element.role: element.text for element in dutch.to_deck_slide().elements if isinstance(element, TextElement)
    } == {
        "kicker": "Het probleem",
        "problem": "Elke ochtend is je koffie al koud.",
    }
    assert slides.ProblemSlide("The problem", None).missing_content() == ["problem"]


def test_a_problem_slide_gets_the_layouts_that_fit_its_picture(images):
    def fitting(picture):
        return engine.layouts_for(_problem_slide(picture=picture).to_deck_slide())

    assert fitting("behind") == ["v5/problem", "v5/problem-band"]
    assert fitting("beside") == ["v5/problem", "v5/problem-split"]
    assert fitting(None) == ["v5/problem"]


def test_a_problem_slide_is_drawn_with_texts_pictures_and_shapes(images):
    """(what the site's renderer draws too, unchanged: talk-generator-web needs no change for it)"""
    seen = set()
    for seed, picture in itertools.product(range(8), ("behind", "beside", None)):
        deck = _deck([_problem_slide(picture=picture)], _theme("startup", seed), seed=seed)
        (slide,) = deck.slides
        seen.add(slide.layout)
        assert all(isinstance(element, TextElement | ImageElement | ShapeElement) for element in slide.elements)
        roles = [element.role for element in slide.elements]
        assert {"kicker", "problem", "detail", "kicker sticker"} <= set(roles), roles
        # (the sticker under its heading, the problem under the line, and only the line on a click)
        assert roles.index("kicker sticker") < roles.index("kicker")
        assert [element.role for element in slide.elements if getattr(element, "appears_on_click", None)] == ["detail"]
        assert check_design(deck) == [], (seed, picture, slide.layout)
    assert seen == {"v5/problem", "v5/problem-band", "v5/problem-split"}


def test_a_classic_deck_and_the_previews_draw_a_problem_slide(images):
    made = [_problem_slide(picture=picture) for picture in ("behind", "beside", None)]
    for theme in (None, _theme("academic")):  # (the 2019 template's look, and a theme's)
        deck = _deck(made, theme)
        assert {slide.type for slide in deck.slides} == {"problem"}
        assert len(render_pptx(deck).slides) == 3
    assert {slide.layout for slide in _deck(made).slides} == {"classic/problem"}
    assert preview.contact_sheet(_deck(made, _theme("academic")), columns=3, width=240).width > 0


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_the_longest_problems_and_long_words_fit_in_every_theme(images, family):
    longest = [_problem_slide(_longest_texts(), picture) for picture in ("behind", "beside", None)]
    long_words = [_problem_slide(_longest_texts(_LONG_WORD), picture) for picture in ("behind", "beside", None)]
    seen = set()
    for seed in range(3):
        # (each in a run, so that every layout that fits comes up)
        deck = _deck(longest * 2, _theme(family, seed), seed)
        seen |= {slide.layout for slide in deck.slides}
        assert check_design(deck) == [], (family, seed)
        deck = _deck(long_words * 2, _theme(family, seed), seed)
        seen |= {slide.layout for slide in deck.slides}
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], (family, seed)
    assert seen == {"v5/problem", "v5/problem-band", "v5/problem-split"}


@pytest.mark.parametrize(("family", "pair"), _OPEN_PAIRINGS, ids=[f"{n}: {h} over {b}" for n, (h, b) in _OPEN_PAIRINGS])
@pytest.mark.slow
def test_the_longest_problems_and_long_words_fit_in_every_open_pairing(images, family, pair):
    longest = [_problem_slide(_longest_texts(), picture) for picture in ("behind", "beside", None)]
    long_words = [_problem_slide(_longest_texts(_LONG_WORD), picture) for picture in ("behind", "beside", None)]
    capitals = themes.FAMILIES[family].uppercase > 0 and pair[0] not in themes._NO_CAPITALS
    for uppercase in (False, True) if capitals else (False,):
        theme = _with_fonts(_theme(family), *pair, uppercase=uppercase)
        for seed in range(2):  # (two seeds: the band and the split come up too)
            assert check_design(_deck(longest * 2, theme, seed)) == [], (family, pair, uppercase, seed)
            deck = _deck(long_words * 2, theme, seed)
            overflow = [finding for finding in check_design(deck) if finding.check == "overflow"]
            assert overflow == [], (family, pair, uppercase, seed)


# THE DICE: AN ANGLE, AND WHERE THE PICTURE GOES


def test_the_dice_pick_an_angle_and_a_picture_behind_or_beside():
    variants = problem_variants()
    assert len(variants) == 2 * len(PROBLEM_ANGLES)
    assert sum(variant.weight for variant in variants) == pytest.approx(sum(w for w, _, _ in PROBLEM_ANGLES.values()))
    assert {variant.omit for variant in variants} == {frozenset({"photo"}), frozenset({"background"})}
    # (only a real problem builds on something real: a how-to people look up)
    assert [variant for variant in variants if variant.note.startswith(PROBLEM_ANGLES["real"][1])] == [
        variant for variant in variants if variant.facts
    ]
    assert len([variant for variant in variants if variant.facts]) == 2
    weighted = problem_variants({"real": 2, "crossed": 0})
    assert not any(PROBLEM_ANGLES["crossed"][1] in variant.note for variant in weighted)
    assert sum(variant.weight for variant in weighted if variant.facts) == pytest.approx(2)
    # A recipe's slides come out every way, over a talk's dice
    recipe = Recipe(
        "problem",
        (cg.statement_backdrop_generator, slide_schemas._PROBLEM_PICTURE),
        brief="A problem",
        variants=variants,
    )
    varied = [recipe.varied(random_util.Rng(seed)) for seed in range(300)]
    assert {(planned.brief, planned.omit, planned.facts) for planned in varied} == {
        (f"A problem, {variant.note}", variant.omit, variant.facts) for variant in variants
    }


def test_the_request_says_the_slides_angle_and_where_its_picture_goes():
    generator = slide_generators.get("Problem (Pitch)")
    recipe = generator.llm.varied(random_util.Rng(3))
    planned = prompt.PlannedSlide(2, generator.name, recipe, "penguins")
    request = prompt.talk_request(["penguins"], [planned], random_util.Rng(1), talk_format=get_schema("pitch").format)
    text = request.messages[0].content
    assert recipe.brief in text and "such as 'The problem'" in text
    slot = "background" if "background" not in recipe.omit else "photo"
    assert f"- {slot}_query:" in text
    assert set(request.json_schema["properties"]["slide_2"]["properties"]) == {
        "concept",
        "kicker",
        "problem",
        "detail",
        f"{slot}_query",
    }


def test_a_talk_that_generates_pictures_draws_the_problem_beside_it_from_the_models_prompt(stock, monkeypatch):
    monkeypatch.setitem(profiles.PROFILES, "weird-stock", Profile("weird-stock", "fake", (SourceUse("fake-stock"),)))
    generator = slide_generators.get("Problem (Pitch)")
    assert generator.llm is not None
    recipes = [generator.llm.varied(random_util.Rng(seed)) for seed in range(40)]
    beside = next(recipe for recipe in recipes if "background" in recipe.omit)
    behind = next(recipe for recipe in recipes if "photo" in recipe.omit)
    painter = FakePainter()
    talk_generation = ImageGeneration(painter, ImageBudget(3))
    asked = dict(prompt.generated(beside, talk_generation))
    assert set(asked) == {"photo"} and "the problem the startup solves" in asked["photo"]
    assert prompt.generated(behind, talk_generation) == []  # (a backdrop is searched for, as a statement's)
    plan = SlidePlan(
        kind="problem",
        concept="pigeons on balconies",
        texts={
            "kicker": "The problem",
            "problem": "Pigeons have taken every balcony in town.",
            "detail": "Yours is next.",
        },
        images={"photo": "pigeons on a balcony"},
        prompts={"photo": "A balcony crowded with pigeons, a man peeking out of the door"},
    )
    with image_context.for_talk(image_context.ImageContext(generation=talk_generation)):
        made = realize(plan, beside, {"seed": "pigeons", "topic": "pigeons"}, random_util.Rng(1), 0)
    assert made is not None
    slide, _ = made
    ((stand_in, wish),) = slide.wishes
    assert "pigeons_on_a_balcony" in stand_in.get_image_url()  # (the stock photo of its query, until it's in)
    assert wish.request.prompt == plan.prompts["photo"]
    talk_generation.settled(slide)
    assert talk_generation.finish()
    shown = slide.to_deck_slide().element("photo")
    assert isinstance(shown, ImageElement) and shown.image.license_class == "generated"


# THE FORMATS: WHICH TALKS OPEN ON THEIR PROBLEM, AND WHERE


def _picks(schema_name, num_slides, seed):
    return get_schema(schema_name)._pick_generators(num_slides, random_util.Rng(seed), "en")


def _problems(picks):
    return [index + 1 for index, pick in enumerate(picks) if pick is not None and "problem_slide" in pick.get_tags()]


@pytest.mark.parametrize(
    ("schema_name", "slide", "fewest", "most"),
    [("pitch", 2, 0.62, 0.82), ("academic", 2, 0.7, 0.88), ("default", 3, 0.16, 0.32), ("ted", 3, 0.24, 0.42)],
)
def test_most_pitches_and_academic_talks_open_on_their_problem_and_some_ted_like_talks(
    schema_name, slide, fewest, most
):
    counted = collections.Counter()
    for seed in range(300):
        found = _problems(_picks(schema_name, 10, seed))
        assert len(found) <= 1  # (one problem slide a talk, at most)
        counted[found[0] if found else None] += 1
    assert set(counted) <= {slide, None}
    assert fewest <= counted[slide] / 300 <= most, counted


def test_a_long_pitch_has_two_slides_of_its_problem_but_one_problem_slide():
    for seed in range(60):
        picks = _picks("pitch", 20, seed)
        parts = [pick.get_tags()[0] for pick in picks[1:3]]
        assert parts == ["problem", "problem"], (seed, [pick.name for pick in picks[1:3]])
        assert len(_problems(picks)) <= 1


def test_an_academic_talk_starts_from_its_motivation_at_every_length():
    for num_slides in range(3, 31):
        assert academic.ARC.layout(num_slides)[1] == "motivation", num_slides
    assert pitch.ARC.layout(5)[1] == "problem"


# CLASSIC PROBLEM SLIDES


@pytest.fixture
def howtos(monkeypatch):
    """wikiHow's how-tos without the internet: one about any seed, or none for one with "nothing" in it."""
    actions = {"wikihow_action": lambda seed: None if "nothing" in seed else "stop a penguin from biting"}
    for name, fake in actions.items():
        monkeypatch.setitem(text_generator.known_functions, name, fake)


_CLASSIC = {
    "Problem (Pitch)": (packs.pack("pitch").format, pitch._PROBLEMS),
    "Motivation (Academic)": (packs.pack("academic").format, academic._PROBLEMS),
    "Problem": (packs.TED, slide_schemas._TED_PROBLEMS),
}


@pytest.mark.parametrize("name", [*_CLASSIC, "Research Question (Academic)"])
def test_every_classic_problem_slide_is_complete(offline, howtos, name):
    maker = slide_generators.get(name)
    pictured = collections.Counter()
    for seed in range(12):
        with random_util.use(random_util.Rng(seed)):
            made = maker.generate(_context(("penguin", "coffee", "the moon")[seed % 3]), set())
        assert made is not None, (name, seed)
        slide, _ = made
        deck = _deck([slide])
        assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == [], name
        assert check_leftovers(deck) == [], name
        pictured.update(element.role for element in deck.slides[0].elements if isinstance(element, ImageElement))
    if name in _CLASSIC:
        assert set(pictured) == {"background", "photo"}  # (behind the problem, or beside it)


@pytest.mark.parametrize("name", _CLASSIC)
def test_a_classic_problem_comes_on_every_angle_with_a_line_under_it_most_of_the_time(offline, howtos, name):
    pack, rules = _CLASSIC[name]
    lines = 0
    for angle in PROBLEM_ANGLES:
        only = {other: 0.0 for other in PROBLEM_ANGLES if other != angle}
        for seed in range(10):
            with random_util.use(random_util.Rng(seed)):
                made = formats.problem(
                    pack,
                    rules,
                    {
                        **_context(),
                        "number": "12",
                        "percent": "40%",
                        "year": "1987",
                        "startup": "Penguinly",
                        "method": "PenguinNet",
                    },
                    _context(),
                    (lambda c: None, lambda c: None),
                    only,
                )
            assert made is not None, (name, angle, seed)
            texts, _ = made
            assert texts["kicker"] and texts["problem"] and "|" not in texts["problem"]
            lines += bool(texts["detail"])
            if angle == "real":
                assert "stop a penguin from biting" in texts["problem"]
    assert 0.6 <= lines / (10 * len(PROBLEM_ANGLES)) <= 0.95


def test_a_classic_real_problem_gives_way_when_wikihow_has_no_how_to(offline, howtos):
    with random_util.use(random_util.Rng(1)):
        made = formats.problem(
            packs.TED,
            slide_schemas._TED_PROBLEMS,
            {"seed": "nothing at all", "number": "12", "percent": "40%", "year": "1987"},
            {"seed": "nothing at all"},
            (lambda c: None, lambda c: None),
            {"real": 100},  # (the real angle first, nearly always)
        )
    assert made is not None and "how to" not in made[0]["problem"]


@pytest.fixture
def lint_offline(monkeypatch):
    """The pack lint's functions without the internet (a long wikiHow action, related words)."""
    for name, fake in OFFLINE.items():
        monkeypatch.setitem(text_generator.known_functions, name, fake)


@pytest.mark.parametrize(
    ("pack", "grammar"), [("pitch", "problem"), ("academic", "motivation"), (packs.TED, "problem")]
)
def test_the_packs_lines_fit_under_their_problems(lint_offline, pack, grammar):
    """(the pack lint holds every part of a slot to its field's length, the problem's: its line has less room)"""
    for angle in PROBLEM_ANGLES:
        for index in range(3):
            variables = {variable: values[index % len(values)] for variable, values in LONG.items()}
            problem, line = _longest(pack, grammar, angle, variables)
            assert problem <= PROBLEM_TEXT and line <= PROBLEM_DETAIL, (pack, angle)


# A REAL PROBLEM FOR A PLANNED SLIDE: A HOW-TO PEOPLE LOOK UP ON WIKIHOW


def _howto(text):
    return facts.flavour_candidate(flavour.Flavour(text, "wikiHow", wikihow.page_of(text[7:])), "howto")


def test_a_planned_problem_slide_on_a_real_angle_gets_a_how_to():
    assert facts.use_of("problem") == "problem"
    generator = slide_generators.get("Problem (Pitch)")
    real = next(variant for variant in generator.llm.variants if variant.facts)
    other = next(variant for variant in generator.llm.variants if not variant.facts)
    planned = {seed: generator.llm.varied(random_util.Rng(seed)) for seed in range(40)}
    uses = {_fact_use(generator, recipe) for recipe in planned.values()}
    assert uses == {"problem", None}  # (the real angle's slides, and only theirs)
    assert real.note and other.note
    sheet = facts.Sheet((_howto("How to Draw a Penguin"), _howto("How to Stop a Penguin from Biting")))
    for seed in range(8):
        given = facts.assign(sheet, [(2, "problem")], random_util.Rng(seed))
        # (one that says what it fixes first)
        assert given[2].fact.text == "How to Stop a Penguin from Biting"
        assert given[2].line().startswith("Start from this real how-to")
    assert facts.credit(given[2].fact) == (("wikiHow", "https://www.wikihow.com/Stop-a-Penguin-from-Biting"),)


def test_how_tos_that_say_what_they_fix_come_first(monkeypatch):
    found = ["Draw a Penguin", "Keep a Pet Pigeon", "Stop a Penguin from Biting", "Keep Pigeons Away", "Fix a Beak"]
    monkeypatch.setattr(wikihow, "get_related_wikihow_actions", lambda topic: list(found))
    assert [howto.text for howto in facts.howtos("penguins")] == [
        "How to Stop a Penguin from Biting",
        "How to Keep Pigeons Away",
        "How to Fix a Beak",
        "How to Draw a Penguin",
        "How to Keep a Pet Pigeon",
    ]
    assert facts.howtos("penguins")[0].url == "https://www.wikihow.com/Stop-a-Penguin-from-Biting"
    assert wikihow.page_of("Have a Good Night's Sleep") == "https://www.wikihow.com/Have-a-Good-Night%27s-Sleep"

    def broken(topic):
        raise ConnectionError("down")

    monkeypatch.setattr(wikihow, "get_related_wikihow_actions", broken)
    assert facts.howtos("penguins") == []


def test_an_english_talk_with_a_problem_slide_looks_up_how_tos_and_others_do_not(web, monkeypatch):
    asked = []
    monkeypatch.setattr(wikihow, "get_related_wikihow_actions", lambda topic: asked.append(topic) or ["Fix a Beak"])
    day = datetime.date(2026, 11, 9)
    sheet = facts.look_up("penguins", "en", day, frozenset({"problem"}))
    assert asked == ["penguins"] and [candidate.text for candidate in sheet.candidates] == ["How to Fix a Beak"]
    assert facts.look_up("pinguïns", "nl", day, frozenset({"problem"})).candidates == ()
    facts.look_up("penguins", "en", day, frozenset({"quiz"}))
    assert asked == ["penguins"]  # (a talk without a problem slide looks up no how-to)
    # (and none of the grim ones)
    monkeypatch.setattr(wikihow, "get_related_wikihow_actions", lambda topic: ["Stop a Goose Attack"])
    assert facts.look_up("geese", "en", day, frozenset({"problem"})).candidates == ()
