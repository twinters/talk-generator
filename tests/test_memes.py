"""Offline tests of memes with live captions (docs/v5-plan.md, sections 8 and 10.4): one of Imgflip's templates, with
its captions as texts in its boxes, written by the language model for the template the talk's dice pick, or taken from
the template's own sentences in a classic talk. Drawn from the deck's pictures, texts and shapes, as every renderer
draws them, in every theme."""

import pytest
from pptx.oxml.ns import qn

from talkgenerator.checks.deck import check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import engine, themes
from talkgenerator.models import classic
from talkgenerator.models.deck import Box, ImageElement, ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import realize
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.schema.slide_schemas import meme_slide_generators
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import conceptnet, imgflip, memes, slide_texts
from talkgenerator.util import image_util, random_util
from tests.test_deck import _jpeg

FAMILIES = list(themes.FAMILIES)
TEMPLATES = list(memes.templates().values())
DRAKE, GRU = memes.template("Drake Hotline Bling"), memes.template("Gru's Plan")
RECIPE = meme_slide_generators[0].llm


@pytest.fixture
def pictures(monkeypatch):
    """Serve fake pictures of the known templates, at their sizes, and have Imgflip list them as memes.json does."""
    served = {template.url: _jpeg((template.width, template.height)) for template in TEMPLATES}
    load = image_util.fetch_image

    def fetch(url):
        return served.get(url) if url.startswith("http") else load(url)

    monkeypatch.setattr(image_util, "fetch_image", fetch)
    monkeypatch.setattr(imgflip, "templates", memes.known)
    return served


@pytest.fixture
def related(monkeypatch):
    words = {"cat": [(1.0, "dog"), (0.9, "mouse"), (0.8, "yarn"), (0.7, "milk")]}
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: words.get(word, []))


def _meme(template, captions=None):
    captions = captions or [f"Caption {index}" for index in range(1, template.captions + 1)]
    slide = slides.MemeSlide(imgflip.image(template.imgflip()), *template.texts(captions))
    slide.add_source(*_credited(template))
    return slide


def _credited(template):
    image = imgflip.image(template.imgflip())
    return image.get_source(), image.get_source_url(), image.get_credit()


def _deck(made, theme=None, seed=1):
    slide_deck = SlideDeck(len(made), title="Cats", topics=["cats"], seed=seed)
    for index, slide in enumerate(made):
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    return slide_deck.to_deck()


def _theme(family="clean keynote", seed=1):
    return themes.pick(family, random_util.Rng(seed))


def _inside(box, area, slack=0.5):
    return (
        box.x >= area.x - slack
        and box.y >= area.y - slack
        and box.x + box.w <= area.x + area.w + slack
        and box.y + box.h <= area.y + area.h + slack
    )


# THE TEMPLATES


def test_every_template_is_sound():
    assert len(TEMPLATES) >= 20 and len({template.name for template in TEMPLATES}) == len(TEMPLATES)
    for template in TEMPLATES:
        assert template.url.startswith("https://i.imgflip.com/") and template.width > 0 and template.height > 0
        assert 1 <= template.captions <= memes.MOST_CAPTIONS and template.about, template.name
        for number, box in enumerate(template.boxes, 1):
            assert 0 <= box.x and 0 <= box.y and box.x + box.w <= 1.001 and box.y + box.h <= 1.001, template.name
            assert (box.fill is not None) == (box.style == "plain"), (template.name, number)
            assert box.same_as is None or box.same_as < number, (template.name, number)
            assert box.says, (template.name, number)
        assert template.classic and all(len(captions) == template.captions for captions in template.classic)


def test_gru_s_fourth_board_repeats_the_third():
    assert GRU.captions == 3 and len(GRU.boxes) == 4
    assert GRU.texts(["Learn", "Teach", "Oops"]) == ["Learn", "Teach", "Oops", "Oops"]
    with pytest.raises(ValueError):
        GRU.texts(["Learn", "Teach", ""])


def test_templates_by_id_name_or_picture():
    assert memes.template("181913649") is DRAKE and memes.template("drake hotline bling") is DRAKE
    assert memes.of_picture(DRAKE.url) is DRAKE
    assert memes.of_picture("https://i.imgflip.com/other.jpg", "https://imgflip.com/memetemplate/181913649") is DRAKE
    assert memes.template("Not a meme") is None and memes.template(None) is None


# THE LAYOUT


def test_a_meme_is_its_template_with_the_captions_in_its_boxes(pictures):
    deck = _deck([_meme(DRAKE), _meme(memes.template("Two Buttons"))], _theme())
    for slide, template in zip(deck.slides, (DRAKE, memes.template("Two Buttons")), strict=True):
        assert slide.type == "meme" and slide.layout == "v5/meme"
        picture = slide.element("template")
        assert isinstance(picture, ImageElement) and picture.box is not None and picture.treatment is None
        shown = picture.box
        assert abs(shown.w / shown.h - template.width / template.height) < 0.01  # (its own shape)
        assert _inside(shown, Box(x=engine.MARGIN, y=0, w=engine.WIDTH - 2 * engine.MARGIN, h=engine.CREDITS_BOX.y))
        assert max(shown.w, shown.h) >= 900  # (as large as fits)
        for number, box in enumerate(template.boxes, 1):
            text = slide.element(f"text_{number}")
            assert isinstance(text, TextElement) and text.box is not None and text.style is not None
            place = Box(x=shown.x + box.x * shown.w, y=shown.y + box.y * shown.h, w=box.w * shown.w, h=box.h * shown.h)
            assert _inside(text.box, place)
            if box.style == "impact":
                effect = text.style.effect
                assert (text.style.font, text.style.uppercase, text.style.color) == ("Impact", True, "#ffffff")
                assert effect is not None and effect.outline == "#000000" and effect.outline_width >= 2
            else:  # (black on a label in the template's own colour there, drawn over the picture, under the text)
                assert (text.style.font, text.style.uppercase) == ("Arial", False)
                label = slide.element(f"text_{number} label")
                assert isinstance(label, ShapeElement) and label.color == box.fill and label.box == place
                elements = list(slide.elements)
                assert elements.index(picture) < elements.index(label) < elements.index(text)
    assert check_design(deck) == []


@pytest.mark.parametrize("family", ["vintage paper", "brutalist", "1997 WordArt"])
def test_no_theme_treats_a_memes_picture(pictures, family):
    for seed in range(4):
        deck = _deck([_meme(DRAKE)], _theme(family, seed), seed)
        picture = deck.slides[0].element("template")
        assert picture.treatment is None, (family, seed)  # (no sepia or polaroid frame: the captions go in place)


def _longest(template, number, word="Expectation"):
    """A caption as long as its box is said to hold, of words."""
    room = max(12, template.room(template.written()[number - 1]))
    limit = min(KINDS["meme"].texts[number - 1].max_length, room)
    return " ".join([word] + ["Expectation"] * (limit // 11 + 1))[:limit].strip()


@pytest.mark.parametrize("family", FAMILIES)
def test_every_template_fits_and_reads_in_every_theme(pictures, family):
    longest = [
        _meme(template, [_longest(template, n) for n in range(1, template.captions + 1)]) for template in TEMPLATES
    ]
    shortest = [_meme(template, ["A"] * template.captions) for template in TEMPLATES]
    for seed in range(2):
        deck = _deck(longest + shortest, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)


def test_long_words_fit_in_every_template(pictures):
    made = [
        _meme(template, [_longest(template, n, "Brandweerkazernedeur") for n in range(1, template.captions + 1)])
        for template in TEMPLATES
    ]
    for family in FAMILIES:
        deck = _deck(made, _theme(family))
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], family


def test_a_picture_whose_boxes_arent_known_gets_captions_at_its_top_and_bottom(pictures):
    unknown = imgflip.image(imgflip.Template("1", "Something else", DRAKE.url.replace("30b1gx", "zzz"), 400, 300))
    pictures[unknown.get_image_url()] = _jpeg((400, 300))
    built = KINDS["meme"].build({"text_1": "Top", "text_2": "Bottom", "text_3": "Gone"}, {"template": unknown}, None)
    deck = _deck([built], _theme())
    slide = deck.slides[0]
    top, bottom = slide.element("text_1"), slide.element("text_2")
    assert slide.element("text_3") is None and top.box.y < slide.element("template").box.y + 200 < bottom.box.y


# WHAT THE DICE AND THE MODEL DO


def test_the_dice_pick_a_template_and_the_model_writes_its_captions():
    assert len(RECIPE.variants) == len(TEMPLATES)
    seen = set()
    for seed in range(60):
        varied = RECIPE.varied(random_util.Rng(seed))
        template = memes.template(varied.queries["template"])
        seen.add(template.id)
        assert varied.image_queries() == []  # (the template is the dice's pick, not the model's query)
        written = [text.name for text in varied.written_fields()]
        assert written == [f"text_{n}" for n in range(1, template.captions + 1)]
        assert template.name in varied.brief
        for text, box in zip(varied.written_fields(), template.written(), strict=True):
            assert box.says in varied.hints[text.name] and text.max_length <= 70
    assert len(seen) >= len(TEMPLATES) * 0.6
    request = prompt.talk_request(
        ["cats"],
        [prompt.PlannedSlide(2, "Meme", RECIPE.varied(random_util.Rng(3)), "cat")],
        random_util.Rng(1),
    )
    text = request.messages[0].content
    assert "meme" in text and "template_query" not in text


def _realized(recipe, texts, images=None, problems=None):
    plan = SlidePlan(kind="meme", concept="cats", texts=texts, images=images or {})
    return realize(plan, recipe, {"seed": "cats", "topic": "cats"}, random_util.Rng(1), 0, problems=problems)


def test_a_planned_meme_searches_for_its_template(pictures):
    gru = next(variant for variant in RECIPE.variants if variant.queries["template"] == GRU.id)
    recipe = Recipe(  # (the recipe as the dice make it Gru's)
        "meme",
        RECIPE.images,
        brief=RECIPE.brief,
        omit=gru.omit,
        hints=gru.hints,
        limits=gru.limits,
        queries=gru.queries,
    )
    made = _realized(recipe, {"text_1": "Learn about cats", "text_2": "Teach it", "text_3": "Cats teach me"})
    assert made is not None
    slide, _ = made
    assert isinstance(slide, slides.MemeSlide)
    deck = _deck([slide])
    texts = [deck.slides[0].element(f"text_{n}").text for n in range(1, 5)]
    assert texts == ["Learn about cats", "Teach it", "Cats teach me", "Cats teach me"]
    assert deck.slides[0].element("template").image.url == GRU.url


def test_a_planned_meme_needs_all_its_captions(pictures):
    problems = []
    drake = Recipe("meme", RECIPE.images, queries={"template": DRAKE.id})
    assert _realized(drake, {"text_1": "Only one"}, problems=problems) is None
    assert any("needs 2 captions" in problem for problem in problems)


def test_an_agent_names_the_template_of_its_meme(pictures):
    made = _realized(
        Recipe("meme", RECIPE.images), {"text_1": "No", "text_2": "Yes"}, {"template": "Drake Hotline Bling"}
    )
    assert made is not None and made[0].image_store()  # (the template's picture)
    assert next(iter(made[0].image_store())) == DRAKE.url


def test_the_kind_is_in_the_plans_catalog():
    entry = next(kind for kind in external.catalog("default")["kinds"] if kind["kind"] == "meme")
    assert entry["images"] == ["template"] and [text["name"] for text in entry["texts"]][:2] == ["text_1", "text_2"]
    assert "meme" not in {kind["kind"] for kind in external.catalog("ted")["kinds"]}  # (fair use, which ted leaves out)


# CLASSIC TALKS


def test_classic_memes_come_out_complete_for_every_template(pictures, related):
    generator = SlideGeneratorData(
        slide_generator_types.DrawnSlideGenerator(slide_texts.meme(cg.meme_template_generator), slides.MemeSlide),
        retries=1,
        name="Meme",
    )
    seen = set()
    for seed in range(40):
        with random_util.use(random_util.Rng(seed)):
            result = generator.generate({"seed": "cat", "topic": "cats"}, set())
        assert result is not None, seed
        slide, _ = result
        assert isinstance(slide, slides.MemeSlide) and slide.missing_content() == []
        deck = _deck([slide], _theme(seed=seed), seed)
        assert [finding for finding in check_deck(deck) if finding.severity == "error"] == [], seed
        assert check_leftovers(deck) == []
        seen.add(memes.of_picture(deck.slides[0].element("template").image.url).id)
    assert len(seen) >= 12


def test_every_templates_classic_captions_fill_in(related):
    for template in TEMPLATES:
        for captions in template.classic:
            for caption in captions:
                filled = slide_texts.text_generator.apply_variables_to_template(
                    caption, {"seed": "cat", "related": "dog"}
                )
                assert filled and "{" not in filled, (template.name, caption)


# RENDERING


def test_powerpoint_draws_a_memes_captions_as_outlined_text_on_its_picture(pictures):
    deck = _deck([_meme(DRAKE), _meme(memes.template("Distracted Boyfriend"))], _theme("dark minimal"))
    presentation = render_pptx(deck)
    boyfriend = presentation.slides[1]
    pictures_on_it = [shape for shape in boyfriend.shapes if shape.shape_type == 13]
    assert len(pictures_on_it) == 1
    runs = [
        run
        for shape in boyfriend.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
        if run.text.startswith("Caption")
    ]
    assert len(runs) == 3 and all(run.font.name == "Impact" for run in runs)
    assert all(run._r.get_or_add_rPr().find(qn("a:ln")) is not None for run in runs)  # (the black outline)
    assert all(run._r.get_or_add_rPr().get("cap") == "all" for run in runs)


def test_a_classic_deck_draws_a_meme_on_the_templates_blank_slide(pictures):
    deck = _deck([_meme(DRAKE)])
    assert deck.theme == "classic" and deck.slides[0].layout == "classic/meme"
    presentation = render_pptx(deck)
    assert presentation.slides[0].slide_layout.name == "Leeg"
    look = themes.CLASSIC_LOOK
    placed = engine.lay_out_slide(deck.slides[0], look, random_util.Rng(0))
    checked = deck.model_copy(update={"slides": (placed,), "style": look, "theme": "classic look"})
    assert check_design(checked) == []


def test_previews_draw_a_meme(pictures):
    deck = _deck([_meme(DRAKE)], _theme("brutalist"))
    picture = preview.slide_image(deck.slides[0], deck.style, width=480)
    assert picture.width == 480


# FORMATS


def test_memes_are_in_talks_that_allow_fair_use_twice_at_most():
    default = get_schema("default")
    assert "Meme" in {generator.name for generator in default.slide_generators}
    assert default._max_allowed_tags["caption_meme"] == 2 and default._max_allowed_tags["meme"] == 0.2
    assert "Meme" not in {generator.name for generator in get_schema("ted").slide_generators}
    assert classic.CLASSIC_ROLES["meme"]["template"] == "template" and "template" not in classic.TEXT_ROLES


def test_memes_come_up_in_most_talks_but_never_all_over_them():
    # (the user loves them: four times the weight of the other middle slides, from the third slide to the one before
    # the conclusions)
    default = get_schema("default")
    by_name = {generator.name: generator for generator in default.slide_generators}
    meme, quiz = by_name["Meme"], by_name["Quiz"]
    assert meme.get_weight_for(5, 10) == 4 * quiz.get_weight_for(5, 10)
    assert meme.get_weight_for(1, 10) == 0 == meme.get_weight_for(9, 10)
    counts = []
    for seed in range(1, 121):
        picks = default._pick_generators(10, random_util.Rng(seed))
        counts.append(sum(1 for pick in picks if pick is not None and pick.name == "Meme"))
    assert 0.45 <= sum(1 for count in counts if count) / len(counts) <= 0.7  # (one in five talks, before)
    assert max(counts) == 2


@pytest.mark.parametrize(
    ("seed", "related", "said", "never"),
    [
        ("coffee", "bean", "coffee", ("coffees", "a coffee")),
        ("happiness", "smile", "happiness", ("happinesses", "a happiness")),
        ("penguin", "fish", "penguins", ("penguin is", "penguins is")),
        ("the french revolution", "guillotine", "the french revolution", ("the the", "a the", "revolutions")),
    ],
)
def test_classic_captions_speak_of_the_seed_as_english_does(seed, related, said, never):
    # (a seed's plural, "coffees" or "happinesses", read wrong on four memes in five, before)
    filled = [
        slide_texts.text_generator.apply_variables_to_template(caption, {"seed": seed, "related": related})
        for template in TEMPLATES
        for captions in template.classic
        for caption in captions
    ]
    assert all(filled) and any(said in caption.lower() for caption in filled)
    assert not [caption for caption in filled if any(wrong in caption.lower() for wrong in never)]
    assert not [caption for caption in filled if "{" in caption or "  " in caption]
