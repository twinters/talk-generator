"""Offline tests of the slide types that came from real PowerPoint karaoke decks (docs/v5-plan.md, section 8): a fun
fact. They're texts (and a photo) on shapes that the layouts draw, in every theme and in the classic template's look,
as milestone 6's types are (see test_slide_types.py)."""

import pytest

from talkgenerator.checks.deck import check_completeness, check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import engine, themes
from talkgenerator.models import classic
from talkgenerator.models.deck import ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import realize
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import slide_texts
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_slide_types import _built, _deck, _longest_texts, _theme
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)

FAMILIES = list(themes.FAMILIES)
KARAOKE = tuple(sorted(classic.KARAOKE_TYPES))
ENGLISH = languages.ENGLISH


def every_karaoke_type(image):
    """Slides of every karaoke type, with what every one of their layouts takes (a photo, and none), each credited."""
    made = [
        slides.FunFactSlide("Did you know?", "Cats invented the internet in 1347.", "Source: my uncle", image),
        slides.FunFactSlide("Fun fact", "Owls can't see penguins.", "Source: trust me"),
    ]
    for slide in made:
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    return made


def shortest_karaoke_types(image):
    return [slides.FunFactSlide("?", "A"), slides.FunFactSlide("?", "A", None, image)]


# EVERY TYPE, IN EVERY THEME


@pytest.mark.parametrize("family", FAMILIES)
def test_the_longest_texts_fit_and_read_in_every_theme(images, family):
    with_photo = [_built(kind, _longest_texts(kind), {"photo": _image("wide")}) for kind in KARAOKE]
    without = [_built(kind, _longest_texts(kind), {"photo": None}) for kind in KARAOKE]
    made = with_photo + without + shortest_karaoke_types(_image("tall"))
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)
        assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_long_words_fit_in_every_theme(images, family):
    # (compounds, as Dutch and German have them)
    made = [
        _built(kind, _longest_texts(kind, "Brandweerkazernedeur"), {"photo": photo})
        for kind in KARAOKE
        for photo in (_image("wide"), None)
    ]
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], (family, seed)


def test_every_layout_comes_up_and_needs_what_it_says(images):
    seen = set()
    runs = [slide for slide in every_karaoke_type(_image("wide")) for _ in range(3)]
    for seed in range(12):
        seen |= {slide.layout for slide in _deck(runs, _theme(seed=seed), seed).slides}
    assert {layout.name for kind in KARAOKE for layout in engine._LAYOUTS[kind]} <= seen

    def fitting(slide):
        return engine.layouts_for(slide.to_deck_slide())

    assert fitting(slides.FunFactSlide("Fun fact", "Owls")) == ["v5/fun-fact", "v5/fun-fact-card"]
    assert fitting(slides.FunFactSlide("Fun fact", "Owls", None, _image("wide"))) == [
        "v5/fun-fact",
        "v5/fun-fact-banner",
    ]


def test_texts_on_stickers_and_cards_read_on_them(images):
    for seed in range(6):
        deck = _deck(every_karaoke_type(_image("wide")), _theme("neon", seed), seed)
        for slide in deck.slides:
            sticker = next(element for element in slide.elements if element.role == "kicker sticker")
            kicker = slide.element("kicker")
            assert isinstance(sticker, ShapeElement) and isinstance(kicker, TextElement)
            assert kicker.style.color != sticker.color
        assert check_design(deck) == []


# THE CLASSIC TEMPLATE AND PREVIEWS


def test_a_classic_deck_draws_them_in_the_templates_look(images):
    deck = _deck(every_karaoke_type(_image("wide")))
    assert deck.theme == "classic" and all(slide.layout == f"classic/{slide.type}" for slide in deck.slides)
    presentation = render_pptx(deck)
    assert [ppt_slide.slide_layout.name for ppt_slide in presentation.slides] == ["Leeg"] * len(deck.slides)
    look = themes.CLASSIC_LOOK
    for made in (every_karaoke_type(_image("wide")), shortest_karaoke_types(_image("tall"))):
        classic_deck = _deck(made)
        placed = tuple(
            engine.lay_out_slide(slide, look, random_util.Rng(0).child("classic", slide.type))
            for slide in classic_deck.slides
        )
        checked = classic_deck.model_copy(update={"slides": placed, "style": look, "theme": "classic look"})
        assert [finding for finding in check_design(checked) if finding.check != "variety"] == []


def test_previews_draw_them(images):
    deck = _deck(every_karaoke_type(_image("wide")), _theme("brutalist"))
    assert preview.contact_sheet(deck).width > 0
    picture = preview.slide_image(deck.slides[1], deck.style, width=480)  # (the fact on its sticky note)
    accent = tuple(int(deck.style.palette.accent[index : index + 2], 16) for index in (1, 3, 5))
    assert accent in {colour for _, colour in picture.getcolors(480 * 270)}


# WHAT A PLAN ASKS FOR, AND THE TALK'S LANGUAGE


def _realized(kind, texts, images=None, problems=None):
    """A planned slide of the kind, realized without its pictures (the slots it has left out)."""
    recipe = Recipe(
        kind, tuple(cg.neutral_image_generator for _ in KINDS[kind].images), omit=frozenset(KINDS[kind].images)
    )
    plan = SlidePlan(kind=kind, concept="cats", texts=texts, images=images or {})
    return realize(plan, recipe, {"seed": "cats", "topic": "cats"}, random_util.Rng(1), 0, problems=problems)


def test_planned_slides_come_out_as_planned(images):
    slide, generated = _realized("fun_fact", {"fact": "Owls can't see cats.", "source": "Source: my uncle"})
    assert isinstance(slide, slides.FunFactSlide) and "Owls can't see cats." in generated
    deck_slide = slide.to_deck_slide()
    assert deck_slide.element("kicker").text in ENGLISH.fun_facts and deck_slide.element("photo") is None
    problems = []
    assert _realized("fun_fact", {"source": "Source: my uncle"}, problems=problems) is None
    assert problems == ["fact: not written"]


@pytest.mark.parametrize("code", sorted(languages.LANGUAGES))
def test_a_fun_facts_heading_speaks_the_talks_language(code):
    language = languages.language(code)
    assert len(language.fun_facts) == 2 and all(heading.strip() for heading in language.fun_facts)
    assert code == "en" or set(language.fun_facts).isdisjoint(ENGLISH.fun_facts)
    with random_util.use(random_util.Rng(3)):
        slide = KINDS["fun_fact"].build({"fact": "Ugler kan ikke se katter", "source": None}, {"photo": None}, language)
    assert slide.to_deck_slide().element("kicker").text in language.fun_facts


# THE CLASSIC GENERATORS


def _photo(context):
    return _image("wide")


CLASSIC = {"fun_fact": (slide_texts.fun_fact(_photo), slides.FunFactSlide)}


@pytest.mark.parametrize("kind", KARAOKE)
def test_the_classic_generators_make_complete_slides(images, related, kind):
    content, slide_class = CLASSIC[kind]
    generator = SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(content, slide_class), retries=1, name=kind
    )
    for seed in range(8):
        with random_util.use(random_util.Rng(seed)):
            result = generator.generate({"seed": "cat", "topic": "cats"}, set())
        assert result is not None, (kind, seed)
        slide, _ = result
        assert isinstance(slide, slide_class) and slide.missing_content() == []
        deck = _deck([slide], _theme(seed=seed), seed)
        assert [finding for finding in check_deck(deck) if finding.severity == "error"] == [], (kind, seed)
        assert check_leftovers(deck) == []


@pytest.mark.parametrize(
    ("seed", "said", "never"),
    [
        ("coffee", "coffee", ("coffees", "a coffee")),
        ("penguin", "penguins", ("penguins is", "penguins was", "a penguins")),
        ("the french revolution", "the french revolution", ("the the", "a the", "revolutions")),
    ],
)
def test_classic_fun_facts_speak_of_the_seed_as_english_does(seed, said, never):
    facts = slide_texts._grammar()["fun_fact"]
    variables = {"seed": seed, "related": "bean", "number": "12", "percent": "40%", "year": "1823"}
    filled = [slide_texts.text_generator.apply_variables_to_template(fact, variables) for fact in facts]
    assert all(filled) and len(filled) >= 20
    assert any(said in fact.lower() for fact in filled)
    assert not [fact for fact in filled if any(wrong in fact.lower() for wrong in never) or "{" in fact]


def test_the_classic_generators_leave_sensitive_seeds_alone(related):
    with random_util.use(random_util.Rng(1)):
        assert all(content({"seed": "islam", "topic": "cats"}) is None for content, _ in CLASSIC.values())


# THE FORMATS


@pytest.mark.parametrize("format_name", ["default", "interview", "ted"])
def test_every_format_has_them_once_at_most(format_name):
    schema = get_schema(format_name)
    kinds = {generator.llm.kind: generator for generator in schema.slide_generators if generator.llm is not None}
    assert set(KARAOKE) <= set(kinds)
    assert all(schema._max_allowed_tags[tag] == 1 for tag in KARAOKE)
    for kind in KARAOKE:  # (in the middle of a talk: not the title, the presenter's introduction, or the end)
        weight = kinds[kind].get_weight_for
        assert weight(5, 10) > 0 == weight(1, 10) == weight(9, 10)
    choices = external.recipes_of(schema)
    assert {external.default_recipe(choices, kind).recipe.kind for kind in KARAOKE} == set(KARAOKE)


def test_ted_gets_copyright_free_photos():
    ted = {generator.name: generator for generator in get_schema("ted").slide_generators}
    assert ted["Fun Fact (CRF)"].llm.images == (cg.copyright_free_generator,)
    default = {generator.name: generator for generator in get_schema("default").slide_generators}
    assert default["Fun Fact"].llm.images == (cg.neutral_or_weird_image_generator,)


def test_they_are_drawn_types():
    assert classic.KARAOKE_TYPES <= classic.DRAWN_TYPES
    for kind in KARAOKE:
        assert set(classic.REQUIRED_ROLES[kind]) <= set(classic.CLASSIC_ROLES[kind].values())
        assert kind in engine._LAYOUTS and kind in KINDS
