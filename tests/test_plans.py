"""Offline tests of talks planned outside talkgenerator (by Claude through the Skill, say): rendering a plan, the
report that says what to fix, and the commands `talkgenerator render`, `schema` and `formats`.

The plans use the fake schema and image sources of test_llm_talks, so nothing goes over the network.
"""

import json
from pathlib import Path

import pytest
from PIL import Image

from talkgenerator import generator, names
from talkgenerator.checks.deck import check_deck
from talkgenerator.models import classic
from talkgenerator.models.deck import Deck
from talkgenerator.models.plan import SlidePlan, TalkPlan
from talkgenerator.plan import external
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.util import random_util
from tests.test_llm_talks import fake_schema
from tests.test_llm_talks import images as images  # the fake image sources (an autouse fixture)

SKILL = Path(__file__).parent.parent / "skill" / "skills" / "talkgenerator"


@pytest.fixture
def schema(monkeypatch):
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    # Its own recipes are the defaults: no borrowing real (networked) ones from the other schemas
    kinds = {generator_.llm.kind for generator_ in schema.slide_generators}
    monkeypatch.setattr(external, "_DEFAULT_RECIPES", {kind: (f"fake-{kind.replace('_', '-')}",) for kind in kinds})
    return schema


def _plan(*slides, **spine):
    return TalkPlan(
        topic="cats",
        title="The Secret Life of Cats",
        presenter_job="Professor of Applied Napping",
        thesis="Cats run the world.",
        slides=tuple(SlidePlan.model_validate(slide) for slide in slides),
        **spine,
    )


TWO_COLUMNS = {
    "kind": "two_columns",
    "recipe": "fake-two-columns",
    "concept": "cats",
    "texts": {"title": "Then and now", "caption_1": "Expectation", "caption_2": "Reality"},
    "images": {"image_1": "a calm cat", "image_2": "a cat on fire"},
}
STATEMENT = {
    "kind": "statement",
    "recipe": "fake-statement",
    "concept": "cats",
    "texts": {"text": "Don't we all secretly want to nap all day?"},
    "images": {"background": "a sleeping cat"},
}
CHART = {
    "kind": "chart_yes_no",
    "recipe": "fake-chart-yes-no",
    "texts": {"question": "Has a cat ever judged you?", "funny_answer": "Only on Sundays"},
}


def _render(plan, tmp_path, **options):
    return external.render_plan(plan, output_folder=tmp_path, presenter="Ann Example", int_seed=1, **options)


def _summary(deck_slides, as_planned=0, classic=0, picture=0, left_out=0):
    planned = as_planned + classic + picture + left_out
    return {
        "deck_slides": deck_slides,
        "planned_slides": planned,
        "as_planned": as_planned,
        "classic": classic,
        "picture": picture,
        "left_out": left_out,
    }


def _image(searched, credit="Fake photos", page=None, shows=None, license=None, look=None):
    return {"searched": searched, "shows": shows, "credit": credit, "page": page, "license": license, "look": look}


def test_a_plan_becomes_a_deck(schema, tmp_path):
    report = _render(_plan(TWO_COLUMNS, STATEMENT, CHART), tmp_path)

    assert report["summary"] == _summary(4, as_planned=3)
    assert [slide["deck_slide"] for slide in report["slides"]] == [2, 3, 4]
    assert report["slides"][0]["images"] == [_image("a calm cat"), _image("a cat on fire")]
    assert report["checks"] == []
    assert report["deck_json"].endswith("Secret_Life_of_Cats.deck.json")
    with Image.open(report["contact_sheet"]) as sheet:  # every image, labeled with its slide and query
        assert sheet.width > 3 * 240
    deck = Deck.from_json(Path(report["deck_json"]).read_text(encoding="utf-8"))
    title, subtitle = (element.text for element in deck.slides[0].elements)
    assert title == "The Secret Life of Cats"
    assert subtitle.endswith("Ann Example\nProfessor of Applied Napping")  # (its own line: D80)
    assert [element.text for element in deck.slides[1].elements if hasattr(element, "text")] == [
        "Then and now",
        "Expectation",
        "Reality",
    ]
    assert Path(report["pptx"]).is_file()
    assert check_deck(deck, 4) == []


def test_the_same_seed_gives_the_same_deck_in_parallel_or_not(schema, tmp_path):
    plan = _plan(TWO_COLUMNS, STATEMENT, CHART)
    decks = []
    for number, parallel in enumerate((True, False)):
        report = _render(plan, tmp_path / str(number), parallel=parallel)
        decks.append(Path(report["deck_json"]).read_text(encoding="utf-8"))
    assert decks[0] == decks[1]


def test_what_cant_be_made_as_planned_is_classic_or_left_out(schema, tmp_path):
    unwritten = {**TWO_COLUMNS, "texts": {"caption_2": "Reality"}}  # no caption_1
    unknown = {"kind": "video", "texts": {"title": "Watch this"}}
    report = _render(_plan(unwritten, unknown, STATEMENT), tmp_path)

    classic, left_out, planned = report["slides"]
    assert (classic["outcome"], classic["deck_slide"]) == ("classic", 2)
    assert classic["problems"] == ["caption_1: not written"]
    assert (left_out["outcome"], left_out["deck_slide"]) == ("left out", None)
    assert "there's no slide kind 'video'" in left_out["warnings"][0]
    assert (planned["outcome"], planned["deck_slide"]) == ("as planned", 3)
    assert report["summary"] == _summary(3, as_planned=1, classic=1, left_out=1)


def test_images_that_cant_be_found_are_searched_for_with_the_concept(schema, tmp_path):
    unfindable = {**TWO_COLUMNS, "images": {"image_1": "an unfindable cat", "image_2": "a cat"}}
    report = _render(_plan(unfindable), tmp_path)
    (slide,) = report["slides"]
    assert slide["outcome"] == "as planned"
    assert slide["retried_because"] == ["image_1: no image found for 'an unfindable cat'"]
    # The query that worked stays; only the other image was searched for with the slide's concept
    assert slide["images"] == [_image("cats"), _image("a cat")]


def test_the_slides_notes_name_the_recipe_they_got(schema, tmp_path):
    report = _render(_plan({**STATEMENT, "recipe": None}), tmp_path)
    deck = Deck.from_json(Path(report["deck_json"]).read_text(encoding="utf-8"))
    assert "a statement slide for fake-statement" in deck.slides[1].notes


def test_nothing_is_saved_over_the_plan(schema, tmp_path, capsys):
    path = tmp_path / "cats.deck.json"  # where the deck's JSON of cats.pptx would go
    text = _plan(CHART).model_dump_json()
    path.write_text(text, encoding="utf-8")
    assert external.main("render", [str(path), "-o", str(tmp_path / "cats.pptx")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert path.read_text(encoding="utf-8") == text
    assert report["deck_json"] is None
    assert "is the plan itself" in report["notes"][0]


def test_a_title_or_job_thats_too_long_is_cut(schema, tmp_path):
    plan = _plan(CHART).model_copy(update={"presenter_job": "Professor " * 15})
    report = _render(plan, tmp_path)
    # (a job without a place where a phrase of it ends goes: D81)
    assert report["notes"] == [
        "the presenter_job has more than 40 characters, so it was shortened where a phrase ends, or left out"
    ]


def _title_slide_text(report):
    deck = Deck.from_json(Path(report["deck_json"]).read_text(encoding="utf-8"))
    return deck.slides[0].elements[1].text, deck.presenter


def test_a_plan_can_name_the_presenter(schema, tmp_path):
    plan = _plan(CHART, presenter_name="Dr. Tabby Cattington")
    report = external.render_plan(plan, output_folder=tmp_path, int_seed=1)
    subtitle, presenter = _title_slide_text(report)
    assert report["presenter"] == presenter == "Dr. Tabby Cattington"
    assert subtitle.endswith("Dr. Tabby Cattington\nProfessor of Applied Napping")
    assert "notes" not in report


def test_a_given_name_goes_before_the_plans(schema, tmp_path):
    report = _render(_plan(CHART, presenter_name="Dr. Tabby Cattington"), tmp_path)
    assert report["presenter"] == _title_slide_text(report)[1] == "Ann Example"


def test_a_plans_name_that_wont_do_is_made_up_instead(schema, tmp_path):
    report = external.render_plan(_plan(CHART, presenter_name="[Your name here]"), output_folder=tmp_path, int_seed=1)
    assert report["presenter"] == names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(1))
    assert report["notes"][0].startswith("the presenter_name '[Your name here]' isn't a name talkgenerator puts on")


def test_without_a_name_a_plans_presenter_gets_one_made_up(schema, tmp_path):
    report = external.render_plan(_plan(CHART), output_folder=tmp_path, int_seed=2)
    assert report["presenter"] == names.from_pack(["cats"], names.DEFAULT_STYLES, random_util.Rng(2))
    classic = external.render_plan(_plan(CHART), output_folder=tmp_path, int_seed=2, name_styles="classic")
    assert classic["presenter"] == names.classic(random_util.Rng(2))
    assert "notes" not in report


def test_the_report_says_what_doesnt_show_up_as_written(schema, tmp_path):
    sloppy = {
        **TWO_COLUMNS,
        "recipe": "Fake Two_Columns",  # the generator's name works too
        "texts": {
            "title": "Then and now",
            "caption_1": "An expectation that is far too long to fit under its image",
            "caption_2": "Reality",
            "subtitle": "Not a thing",
        },
        "images": {"image_1": "https://example.com/cat.jpg", "image_2": "a cat", "image_3": "a dog"},
    }
    wrong_recipe = {**STATEMENT, "recipe": "fake-two-columns"}
    no_recipe = {**CHART, "recipe": "no-such-recipe"}
    report = _render(_plan(sloppy, wrong_recipe, no_recipe), tmp_path)

    sloppy_report, wrong_report, missing_report = report["slides"]
    assert sloppy_report["recipe"] == "fake-two-columns"
    assert sloppy_report["warnings"] == [
        "caption_1 has more than 40 characters, so it was cut off",
        "two_columns slides have no text 'subtitle'; they have 'title', 'caption_1', 'caption_2'",
        "image_1 is an address: images are searched for with words (or are files of your own)",
        "two_columns slides have no image 'image_3'; they have 'image_1', 'image_2'",
    ]
    assert "makes two_columns slides, not statement ones" in wrong_report["warnings"][0]
    assert "this format has no recipe 'no-such-recipe'" in missing_report["warnings"][0]
    assert wrong_report["recipe"] == "fake-statement"  # the kind's default (the only one in the fake schema)


def test_a_plan_can_show_your_own_pictures(schema, tmp_path):
    Image.new("RGB", (300, 200), (200, 100, 50)).save(tmp_path / "me.jpg")
    mine = {**STATEMENT, "images": {"background": "me.jpg"}}
    report = _render(_plan(mine), tmp_path, local_images=tmp_path)
    assert report["slides"][0]["images"] == [_image("me.jpg", credit="your file")]
    # Without a folder to take them from (as for plans a language model wrote), a file name is just a query
    report = _render(_plan(mine), tmp_path / "again")
    assert report["slides"][0]["images"] == [_image("me.jpg")]


# THE COMMANDS


def test_render_prints_the_report(schema, tmp_path, capsys):
    path = tmp_path / "cats.json"
    path.write_text(_plan(TWO_COLUMNS, CHART).model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path / "out"), "--int_seed", "4"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert Path(report["pptx"]).name == "cats.pptx"  # named after the plan
    assert report["seed"] == 4
    assert report["summary"]["as_planned"] == 2


def test_render_says_what_is_wrong_with_a_plan(schema, tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"topic": "cats", "slides": [{"kind": "statement", "text": "oops"}]}), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["error"].startswith("it isn't a plan")
    assert {"where": "title", "problem": "Field required"} in report["details"]
    assert {"where": "slides.0.text", "problem": "Extra inputs are not permitted"} in report["details"]


def test_a_plan_can_have_a_theme(schema, tmp_path, capsys):
    report = _render(_plan(TWO_COLUMNS, CHART, theme="vintage paper"), tmp_path)
    assert report["theme"].startswith("vintage paper")
    deck = Deck.model_validate_json(Path(report["deck_json"]).read_text(encoding="utf-8"))
    assert all(slide.layout.startswith("v5/") for slide in deck.slides) and deck.style.family == "vintage paper"
    assert _render(_plan(CHART), tmp_path)["theme"] == "classic"  # without one, the 2019 template
    path = tmp_path / "themed.json"
    path.write_text(_plan(CHART, theme="glitter").model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path)]) == 2
    assert json.loads(capsys.readouterr().out)["error"].startswith("there's no theme 'glitter'")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path), "--theme", "neon"]) == 0
    assert json.loads(capsys.readouterr().out)["theme"].startswith("neon")


def test_render_takes_patterns_of_plans(schema, tmp_path, capsys):
    for name in ("one", "two"):
        (tmp_path / f"{name}.json").write_text(_plan(CHART).model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(tmp_path / "*.json"), "--output_folder", str(tmp_path / "out")]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert [Path(report["pptx"]).name for report in reports] == ["one.pptx", "two.pptx"]


def test_schema_prints_the_plan_format(capsys):
    assert external.main("schema", ["plan"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["title"] == "TalkPlan"
    assert "SlidePlan" in schema["$defs"]


def test_formats_lists_the_formats_and_their_slides(capsys):
    assert external.main("formats", []) == 0
    assert capsys.readouterr().out.startswith("default: A TED-like talk")
    assert external.main("formats", ["--details", "--json"]) == 0
    catalog = json.loads(capsys.readouterr().out)
    kinds = {kind["kind"]: kind for kind in catalog["kinds"]}
    # (every kind but the ones that the formats beyond TED-like talks brought, such as an academic talk's process)
    assert set(kinds) == set(external.PLANNABLE_KINDS) - classic.FORMAT_TYPES
    defaults = [recipe["id"] for recipe in kinds["image"]["recipes"] if recipe["default"]]
    assert defaults == ["single-image-copyright-free"]  # borrowed: the default format has no plain photo slide


def test_copyright_free_formats_only_get_copyright_free_defaults():
    choices = external.recipes_of(get_schema("ted"))
    assert external.default_recipe(choices, "full_image") is None  # ted has no full-screen slides
    assert external.default_recipe(choices, "statement").id == "wikihow-bold-statement-crf"


# THE SKILL


@pytest.mark.parametrize(
    ("format_name", "file_name"),
    [
        ("default", "slides.md"),
        ("ted", "slides-ted.md"),
        ("pitch", "slides-pitch.md"),
        ("academic", "slides-academic.md"),
        ("corporate", "slides-corporate.md"),
        ("keynote", "slides-keynote.md"),
        ("infomercial", "slides-infomercial.md"),
        ("documentary", "slides-documentary.md"),
        ("court", "slides-court.md"),
        ("museum", "slides-museum.md"),
        ("wedding", "slides-wedding.md"),
        ("book_report", "slides-book_report.md"),
    ],
)
def test_the_skills_slide_references_are_up_to_date(format_name, file_name):
    # Made with: talkgenerator formats --details --format <format> > skill/skills/talkgenerator/references/<file>
    reference = (SKILL / "references" / file_name).read_text(encoding="utf-8")
    assert reference == external.catalog_markdown(format_name)


def test_the_skills_example_plan_is_a_plan_without_warnings():
    plan = TalkPlan.model_validate_json((SKILL / "references" / "example-plan.json").read_text(encoding="utf-8"))
    assert names.clean(plan.presenter_name) == plan.presenter_name != ""
    choices = external.recipes_of(get_schema("default"))
    for slide in plan.slides:
        choice, warnings = external.choose_recipe(choices, slide)
        assert choice is not None and warnings == [], slide
        assert external.plan_warnings(slide, choice.recipe) == [], slide


# SEARCHING AS PLANNED


def test_a_plans_queries_are_searched_as_written():
    from talkgenerator.util import generator_util

    searched = []
    prefixed = generator_util.PrefixedGenerator("funny", searched.append)
    related = generator_util.RelatedMappingGenerator(lambda seed: "harassment", searched.append)
    prefixed("office plant")
    related("workplace")
    with generator_util.as_planned():
        prefixed("office plant")
        related("workplace")
    assert searched == ["funny office plant", "harassment", "office plant", "workplace"]


def test_a_plans_images_come_from_the_best_results():
    from talkgenerator.util import generator_util, random_util

    results = [f"https://example.com/{rank}.jpg" for rank in range(40)]
    pick = generator_util.ExternalImageListGenerator(lambda seed: results, check_image_validness=False)
    with generator_util.as_planned():
        picked = set()
        for seed in range(30):
            with random_util.use(random_util.Rng(seed)):
                picked.add(pick("owls").get_image_url())
    assert picked <= set(results[: generator_util.TOP_RESULTS])


def test_a_plan_gets_no_random_reddit_post_instead_of_what_it_asked_for():
    from talkgenerator.schema.content_generator_structures import RedditImageGenerator
    from talkgenerator.util import generator_util

    with generator_util.as_planned():
        assert RedditImageGenerator("pics").generate_random({"seed": "owls"}) is None


def test_a_plan_can_name_its_format(schema, tmp_path, capsys):
    path = tmp_path / "cats.json"
    path.write_text(_plan(CHART, format="ted").model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["format"] == "ted"
    path.write_text(_plan(CHART, format="karaoke").model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path)]) == 2
    assert "there's no format 'karaoke'" in json.loads(capsys.readouterr().out)["error"]


# PLANS IN OTHER LANGUAGES


@pytest.mark.parametrize(("language", "reality"), [("nl", "Werkelijkheid"), ("sv", "Verkligheten")])
def test_a_plan_in_another_language_gets_its_words_and_pictures_instead_of_classic_slides(
    schema, tmp_path, language, reality
):
    from talkgenerator.plan import languages

    unwritten = {**TWO_COLUMNS, "texts": {"caption_2": reality}}  # no caption_1: it can't come out
    report = _render(_plan(unwritten, STATEMENT, language=language), tmp_path)
    assert (report["language"], report["summary"]) == (language, _summary(3, as_planned=1, picture=1))
    assert report["slides"][0]["outcome"] == "picture"
    deck = Deck.from_json(Path(report["deck_json"]).read_text(encoding="utf-8"))
    assert deck.language == language
    assert deck.slides[0].elements[1].text.split(" Ann Example")[0] in languages.LANGUAGES[language].by
    assert deck.slides[1].type == "full_image"
    assert [element for element in deck.slides[1].elements if element.kind == "text"] == []


def test_a_dutch_plan_gets_no_recipe_that_finds_english_texts():
    choices = external.recipes_of(get_schema("default"))
    choice, warnings = external.choose_recipe(choices, SlidePlan(kind="statement", recipe="quote"), "nl")
    assert choice.id == "wikihow-bold-statement"
    assert "finds English texts" in warnings[0]
    assert external.choose_recipe(choices, SlidePlan(kind="statement", recipe="quote"))[0].id == "quote"


def test_render_refuses_a_language_it_doesnt_know(schema, tmp_path, capsys):
    path = tmp_path / "cats.json"
    path.write_text(_plan(CHART, language="xx").model_dump_json(), encoding="utf-8")
    assert external.main("render", [str(path), "--output_folder", str(tmp_path)]) == 2
    assert "there's no language 'xx'" in json.loads(capsys.readouterr().out)["error"]


def test_a_plan_gets_no_random_shitpostbot_or_unsplash_images_either():
    from talkgenerator.sources import shitpostbot, unsplash
    from talkgenerator.util import generator_util

    with generator_util.as_planned():  # (no requests: they step aside before asking)
        assert shitpostbot.get_random_images_rated("owls") == []
        assert shitpostbot.get_random_images("owls") == []
        assert unsplash.random_as_list("owls") == []
