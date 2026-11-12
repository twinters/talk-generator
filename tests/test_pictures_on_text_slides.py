"""Offline tests of decision D63, after the user reviewed 35 talks (2026-11-09): pictures behind and beside slides of
text (big numbers and KPI tiles over a picture, statements over a backdrop from a mix of sources), the varied backdrop
look, more of Reddit's weird pictures and of the live-caption memes, the formats' free slides and provocations, and a
pitch's product shown off (searched as a gadget, or generated as a product shot)."""

from __future__ import annotations

import collections
import os

import pytest

from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, themes
from talkgenerator.images import catalog, generation, licenses, profiles
from talkgenerator.images import context as image_context
from talkgenerator.images.generation import ImageBudget, ImageGeneration
from talkgenerator.images.profiles import Profile, SourceUse
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import ImageElement, ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, prompt
from talkgenerator.plan.kinds import KINDS, Recipe, Variant, pictured
from talkgenerator.plan.realize import realize
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema import slide_schemas
from talkgenerator.schema.formats import (
    academic,
    corporate,
    infomercial,
    keynote,
    pitch,
)
from talkgenerator.schema.formats.arcs import PART_WEIGHT
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.schema.slide_schemas import slide_generators
from talkgenerator.slide import slides
from talkgenerator.sources import packs, slide_texts
from talkgenerator.util import image_util, random_util
from tests.test_deck import _image, _jpeg
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_generated_images import FakePainter
from tests.test_slide_types import _deck, _theme, every_pictured_figure
from tests.test_slide_types import related as related  # (fake ConceptNet: words related to a cat)

FORMATS = {
    "Pitch": pitch,
    "Academic": academic,
    "Corporate": corporate,
    "Keynote": keynote,
    # (D79)
    "Infomercial": infomercial,
}


class _Stock:
    """A source of stock photos named after the query, which finds nothing for a query with "nothing" in it."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def search(self, search):
        self.asked.append(search.query)
        if "nothing" in search.query:
            return []
        name = search.query.replace(" ", "_")
        return [
            (
                1.0,
                ImageData(
                    f"https://images/{name}-{n}.jpg", source="fake", license_class="stock", declared_size=(1600, 1000)
                ),
            )
            for n in range(3)
        ]


@pytest.fixture
def stock(monkeypatch):
    """The looks these tests search, on a fake stock source whose pictures download (and probes find them)."""
    source = _Stock()
    jpeg = _jpeg((1600, 1000))
    load = image_util.fetch_image
    monkeypatch.setattr(image_util, "fetch_image", lambda url: jpeg if url.startswith("https://images/") else load(url))
    monkeypatch.setattr(image_util, "probe", lambda url: url.startswith("https://images/") or os.path.isfile(url))
    monkeypatch.setitem(
        catalog.SOURCES,
        "fake-stock",
        catalog.Source("fake-stock", "fake", frozenset({"stock"}), source.search, lambda: True),
    )
    for name in ("backdrop", "calm-backdrop", "product-shot", "photo"):
        monkeypatch.setitem(profiles.PROFILES, name, Profile(name, "fake", (SourceUse("fake-stock"),)))
    return source


# BIG NUMBERS AND KPI TILES OVER A PICTURE


def test_pictured_variants_have_the_slot_that_share_of_the_time():
    variants = pictured((Variant(2), Variant(1, frozenset({"source"}), "without a source")), "background", 0.75)
    pictured_weight = sum(variant.weight for variant in variants if "background" not in variant.omit)
    assert pictured_weight / sum(variant.weight for variant in variants) == pytest.approx(0.75)
    assert {(variant.note, "source" in variant.omit) for variant in variants} == {
        ("", False),
        ("without a source", True),
    }
    assert pictured((), "background", 0.5) == (Variant(0.5), Variant(0.5, frozenset({"background"})))


def test_big_numbers_and_kpi_tiles_ask_for_a_picture_behind_them_in_every_format():
    shares = {"big_number": slide_texts.BIG_NUMBER_PICTURES, "kpi": slide_texts.KPI_PICTURES}
    assert shares == {"big_number": 0.75, "kpi": 0.5}
    seen = collections.Counter()
    for generator_ in slide_generators:
        recipe = generator_.llm
        if recipe is None or recipe.kind not in shares:
            continue
        seen[recipe.kind] += 1
        assert dict(recipe.slots()) == {"background": cg.backdrop_generator}, generator_.name
        weights = [(variant.weight, "background" not in variant.omit) for variant in recipe.variants]
        assert sum(weight for weight, there in weights if there) / sum(
            weight for weight, _ in weights
        ) == pytest.approx(shares[recipe.kind]), generator_.name
    assert seen["big_number"] >= 8 and seen["kpi"] >= 5  # (the TED-like talks' and the four formats')
    assert KINDS["big_number"].optional_images == KINDS["kpi"].optional_images == frozenset({"background"})


def test_a_recipe_made_before_a_kinds_optional_picture_leaves_it_out():
    assert Recipe("big_number").slots() == [] and Recipe("big_number").image_queries() == []
    recipe = Recipe("big_number", (cg.backdrop_generator,))
    assert recipe.image_queries() == ["background"] and recipe.slots() == [("background", cg.backdrop_generator)]
    with pytest.raises(ValueError):  # (an image the slide needs can't be left out so)
        Recipe("two_columns", (cg.copyright_free_generator,)).slots()


def _number_plan(concept, query):
    texts = {"title": "Cats", "number": "97%", "label": "of cats nap at work", "source": "My neighbour"}
    return SlidePlan(kind="big_number", concept=concept, texts=texts, images={"background": query})


def test_a_planned_big_number_comes_without_its_picture_when_none_is_found(stock):
    recipe = Recipe("big_number", (cg.backdrop_generator,))
    context = {"seed": "cats", "topic": "cats"}
    made = realize(_number_plan("nothing either", "nothing at all"), recipe, context, random_util.Rng(1), 0)
    assert made is not None and made[0].to_deck_slide().element("background") is None
    # (a picture its query doesn't find, its concept may: searched at once, on the slide's first try)
    made = realize(_number_plan("napping cats", "nothing here"), recipe, context, random_util.Rng(1), 0)
    assert made is not None
    background = made[0].to_deck_slide().element("background")
    assert isinstance(background, ImageElement) and background.fit == "cover" and "napping_cats" in background.image.url
    assert stock.asked[-2:] == ["nothing here", "napping cats"]
    # and a KPI dashboard alike
    texts = {
        "title": "KPIs",
        **{f"number_{n}": str(n) for n in (1, 2, 3)},
        **{f"label_{n}": f"thing {n}" for n in (1, 2, 3)},
    }
    plan = SlidePlan(kind="kpi", concept="nothing", texts=texts, images={"background": "nothing"})
    made = realize(plan, Recipe("kpi", (cg.backdrop_generator,)), context, random_util.Rng(1), 0)
    assert made is not None and made[0].to_deck_slide().element("background") is None


def test_a_slide_that_can_do_without_its_picture_stays_with_any_license_policy():
    # (the TED-like talk with copyright-free pictures only keeps its big numbers, whatever their picture's sources)
    with image_context.for_talk(image_context.ImageContext(licenses.OPEN)):
        unservable = {generator_.name for generator_ in get_schema("ted").unservable()}
    assert "Big Number" not in unservable and "KPI Tiles" not in unservable


def _laid_out_every_way(slide, theme, monkeypatch):
    """The slide in every layout that fits it, in the theme."""
    placed = []
    for name in engine.layouts_for(slide, theme):
        layout = next(each for each in engine._LAYOUTS[slide.type] if each.name == name)
        monkeypatch.setitem(engine._LAYOUTS, slide.type, (layout,))
        placed.append(engine.lay_out_slide(slide, theme, random_util.Rng(1)))
        monkeypatch.undo()
    return placed


def _figures_in_every_layout(family, monkeypatch, seed=1):
    theme = _theme(family, seed)
    deck = _deck(every_pictured_figure(_image("wide")), theme, seed)
    placed = [
        laid
        for slide in deck.slides
        for laid in _laid_out_every_way(
            slide.model_copy(update={"layout": f"classic/{slide.type}"}), theme, monkeypatch
        )
    ]
    return deck.model_copy(update={"slides": tuple(placed)})


def test_a_big_number_over_its_picture_is_shaded_and_reads_on_it(images, monkeypatch):
    deck = _figures_in_every_layout("clean keynote", monkeypatch)
    layouts = [slide.layout for slide in deck.slides]
    assert layouts == [
        "v5/big-number",
        "v5/big-number-band",
        "v5/big-number-side",
        "v5/kpi-rows",
        "v5/kpi-tiles",
        "v5/kpi-grid",
    ]
    for slide in deck.slides:
        picture = slide.element("background")
        assert isinstance(picture, ImageElement) and picture.fit == "cover", slide.layout
        if slide.layout == "v5/big-number-side":  # (beside it: the slide's right side, on the theme's background)
            assert picture.box is not None and picture.box.x > 960 and picture.box.w + picture.box.x == 1920
            assert all(
                element.box.x + element.box.w < picture.box.x
                for element in slide.elements
                if isinstance(element, TextElement) and element.role != "decoration"
            )
            continue
        # (behind everything, shaded, and the texts off the tiles light)
        assert slide.elements[0] is picture and picture.box == engine.FULL
        shade = slide.elements[1]
        assert isinstance(shade, ShapeElement) and shade.role == "shade" and shade.box == engine.FULL
        title = slide.element("title")
        assert isinstance(title, TextElement) and title.style.color == engine.LIGHT_TEXT
    assert [finding for finding in check_design(deck) if finding.check != "variety"] == []


@pytest.mark.parametrize("family", ["neon", "kids", "newspaper"])
def test_figures_over_a_picture_pass_the_design_checks(images, monkeypatch, family):
    deck = _figures_in_every_layout(family, monkeypatch)
    assert [finding for finding in check_design(deck) if finding.check != "variety"] == []


@pytest.mark.slow
@pytest.mark.parametrize("family", list(themes.FAMILIES))
def test_figures_over_a_picture_pass_the_design_checks_in_every_family(images, monkeypatch, family):
    for seed in range(3):
        deck = _figures_in_every_layout(family, monkeypatch, seed)
        assert [finding for finding in check_design(deck) if finding.check != "variety"] == [], (family, seed)


def test_the_classic_figures_have_their_picture_that_share_of_the_time(related):
    found = _image("wide")
    big = slide_texts.big_number(lambda context: found)
    tiles = slide_texts.kpi(lambda context: found)
    pictured_numbers = pictured_tiles = 0
    for seed in range(400):
        with random_util.use(random_util.Rng(seed)):
            number = big({"seed": "cat", "topic": "cats"})
            kpi = tiles({"seed": "cat", "topic": "cats"})
        assert number is not None and len(number) == 5 and kpi is not None and len(kpi) == 10
        pictured_numbers += number[-1] is found
        pictured_tiles += kpi[-1] is found
        assert isinstance(slides.KpiSlide(*kpi), slides.KpiSlide)
    assert pictured_numbers / 400 == pytest.approx(0.75, abs=0.06)
    assert pictured_tiles / 400 == pytest.approx(0.5, abs=0.07)


# THE BACKDROP LOOK, REDDIT'S WEIRD PICTURES AND MEMES


def test_the_backdrop_look_mixes_many_sources():
    look = profiles.profile("backdrop")
    weights = {use.source: use.weight for use in look.sources}
    assert {"pixabay", "unsplash", "pexels", "reddit:weird", "reddit:pictures", "nasa", "met", "wikimedia"} <= set(
        weights
    )
    stock = sum(weights[name] for name in ("pixabay", "unsplash", "pexels"))
    assert 0.45 < stock / sum(weights.values()) < 0.7  # (stock photos most often, and now and then the others)
    assert look.orientation == "landscape" and look.fallback == "calm-backdrop"
    assert "backdrop" in generation.STYLES and cg.backdrop_generator.aesthetic == "backdrop"


def test_statements_take_their_backdrops_from_a_mix_of_looks():
    mix = cg.statement_backdrop_generator
    assert mix.choices == (cg.generate_horizontal_pixabay_image, cg.backdrop_generator)
    for name in ("Wikihow Bold Statement", "Quote", "Anecdote", "Full Screen Pixabay Deep", "Quote (CRF)"):
        recipe = slide_generators.get(name).llm
        assert recipe is not None and recipe.images == (mix,), name
        assert external._looks(recipe) == {"background": "calm-backdrop or backdrop"}
    # (every statement a format has: over the mix too, its own as its free slides, or over a calm picture of something
    # of its own, as an infomercial's call centre; a museum tour has none of its own)
    for named, module in FORMATS.items():
        statements = [each for each in module.GENERATORS if each.llm is not None and each.llm.kind == "statement"]
        assert statements, named
        for each in statements:
            (image,) = each.llm.images  # type: ignore[union-attr]
            assert image is mix or getattr(image, "aesthetic", None) == "calm-backdrop", each.name


def test_reddits_weird_pictures_and_the_live_caption_memes_come_up_more_often():
    chaos = {use.source: use.weight for use in profiles.profile("meme-chaos").sources}
    assert chaos["reddit:weird"] > 2 * chaos["shitpostbot"]
    still = {use.source: use.weight for use in profiles.profile("meme-chaos-still").sources}
    assert still["reddit:weird"] > still["shitpostbot"]
    assert "reddit:weird" in {use.source for use in profiles.profile("weird-stock").sources}
    assert slide_schemas.MEME_WEIGHT == 7  # (5 until D78, whose five slide types took memes down to 40% of talks)


# THE FORMATS' FREE SLIDES: MEMES, PICTURES AND PROVOCATIONS


@pytest.mark.parametrize("named", FORMATS)
def test_every_format_has_provocations_in_its_voice(named, stock):
    module = FORMATS[named]
    provocation = next(each for each in module.GENERATORS if each.name == f"Provocation ({named})")
    assert "provocation" in provocation.get_tags() and module.CAPS["provocation"] == 0.1
    recipe = provocation.llm
    assert recipe is not None and recipe.kind == "full_image" and recipe.images == (cg.provocation_image_generator,)
    assert "provocative" in recipe.hints["title"]
    templates = packs.pack(module.PACK).rule("free.provocation")
    assert len(templates) >= 20
    # (a classic one: a full-screen picture of the slide's topic, under a word or two of the pack's)
    with random_util.use(random_util.Rng(3)):
        made = provocation.generate({"seed": "cats", "topic": "cats", "presenter": "Ann", "title": "Cats"}, set())
    assert made is not None
    slide, _ = made
    deck_slide = slide.to_deck_slide()
    title, picture = deck_slide.element("title"), deck_slide.element("content")
    assert isinstance(title, TextElement) and 1 <= len(title.text.split()) <= 6
    assert isinstance(picture, ImageElement) and picture.image.url.startswith("https://images/cats")


# (the formats with two free slides of ten)
@pytest.mark.parametrize("name", ["pitch", "academic", "corporate", "infomercial"])
def test_ten_slide_talks_of_the_formats_have_memes_and_pictures_between_their_parts(name):
    schema, arc = get_schema(name), next(module.ARC for module in FORMATS.values() if module.PACK == name)
    free = memes = pictured_ = 0
    for seed in range(150):
        picks = schema._pick_generators(10, random_util.Rng(seed), "en", None)
        for number, pick in enumerate(picks[1:], 1):
            if arc.part_of(number, 10) is not None or pick is None:
                continue
            free += 1
            tags = pick.get_tags()
            memes += "meme" in tags
            pictured_ += bool({"meme", "gif", "full_image", "reddit", "two_captions", "provocation"} & set(tags))
    assert free == 2 * 150  # (two free slides of ten)
    assert memes / free > 0.15 and pictured_ / free > 0.5, (memes / free, pictured_ / free)


def test_a_formats_free_slides_weigh_memes_more_than_their_slides_of_text():
    def weight(module, named, name):  # (on a ten-slide talk's first free slide)
        free = next(number for number in range(1, 10) if module.ARC.part_of(number, 10) is None)
        found = [each for each in module.GENERATORS if each.name == f"{name} ({named})"]
        return found[0].get_weight_for(free, 10) / PART_WEIGHT if found else 0.0

    for named, module in FORMATS.items():
        meme = weight(module, named, "Meme")
        assert meme >= 1.6, named
        assert all(meme > 2 * weight(module, named, text) for text in ("Wikihow Bold Statement", "Quote", "Anecdote"))


# A PITCH'S PRODUCT, SHOWN OFF


def test_a_pitchs_product_is_searched_as_a_gadget_and_drawn_as_a_product_shot():
    look = profiles.profile("product-shot")
    assert "gadget" in look.modifiers and "invention" in look.modifiers and look.fallback == "weird-stock"
    assert "product" in generation.STYLES["product-shot"]
    for product in (pitch._PRODUCT, keynote._PRODUCT):
        assert isinstance(product, ImageSlot) and product.generate and product.aesthetic == "product-shot"
        assert "absurd invention" in product.intent
    solution = slide_generators.get("Solution (Pitch)")
    assert solution.llm is not None and solution.llm.images == (pitch._PRODUCT,)
    # (the main product slide: the solution part's slide most of the time)
    weights = {each.name: each.get_weight_for(2, 10) for each in pitch.GENERATORS if "solution" in each.get_tags()}
    assert weights["Solution (Pitch)"] > 0.5 * sum(weights.values())


def test_a_talk_that_generates_pictures_draws_the_pitchs_product_from_the_models_prompt(stock):
    recipe = slide_generators.get("Solution (Pitch)").llm
    assert recipe is not None
    painter = FakePainter()
    talk_generation = ImageGeneration(painter, ImageBudget(3))
    asked = dict(prompt.generated(recipe, talk_generation))
    assert "an absurd invention, shown off as an advertisement would" in asked["image"]
    plan = SlidePlan(
        kind="image",
        concept="penguin toaster",
        texts={"title": "Meet PenguinHub"},
        images={"image": "penguin shaped toaster"},
        prompts={"image": "A sleek toaster shaped like a penguin, on a white pedestal in a studio"},
    )
    with image_context.for_talk(image_context.ImageContext(generation=talk_generation)):
        made = realize(plan, recipe, {"seed": "penguins", "topic": "penguins"}, random_util.Rng(1), 0)
    assert made is not None
    slide, _ = made
    ((stand_in, wish),) = slide.wishes
    assert "penguin_shaped_toaster" in stand_in.get_image_url()  # (the stock photo of its query, until it's in)
    assert wish.request.prompt == plan.prompts["image"] and wish.request.style == generation.STYLES["product-shot"]
    talk_generation.settled(slide)
    assert talk_generation.finish()
    shown = slide.to_deck_slide().element("content")
    assert isinstance(shown, ImageElement) and shown.image.license_class == "generated"
    assert [request.prompt for request in painter.requests] == [plan.prompts["image"]]
