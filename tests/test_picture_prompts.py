"""Offline tests of the slides of a picture to explain (docs/v5-plan.md, D78): Exhibit A (and a talk's later Exhibit B,
of the same case), two pictures to pick one of, a picture equation of pictures or emoji, "What do you see?" over a face
in something (pareidolia) or an inkblot that its layout draws, and a before and after. They're a picture or three, and
talkgenerator's few words on shapes of their own, in every theme and in the classic template's look, as the karaoke
types are (see test_karaoke_types.py); classic ones from the TED pack's pictures.* templates, and planned ones."""

import pytest

from talkgenerator.checks.deck import check_completeness, check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import color, engine, themes
from talkgenerator.images import finder, licenses
from talkgenerator.models import classic
from talkgenerator.models.deck import ImageElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages, prompt
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import realize
from talkgenerator.render import preview
from talkgenerator.schema import slide_schemas
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import slide_texts
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_slide_types import _built, _deck, _longest_texts, _theme
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)

FAMILIES = list(themes.FAMILIES)
PROMPTS = tuple(sorted(classic.PICTURE_PROMPT_TYPES))
ENGLISH = languages.ENGLISH
LONG_WORD = "Brandweerkazernedeur"  # (a compound, as Dutch and German have them)


def every_picture_prompt(wide, tall):
    """Slides of every type of a picture to explain, with what every one of their layouts takes (pictures and an
    inkblot, a title and none, a short question and one with a long word), each credited; of each type, the one that
    fits one layout only before the one that fits more, so that one after the other, they never have the same layout
    twice in a row."""
    made = [
        slides.ExhibitSlide("Exhibit", "Case No. 4417-23", wide, "Found next to the cat"),
        slides.ExhibitSlide("Exhibit", "Case No. 1234-56", tall),
        slides.PickOneSlide("Pick one:", wide, tall),
        slides.PickOneSlide("Choose your fighter:", tall, wide),
        slides.EquationSlide("The formula", "🐱", "🧶", "🚀"),
        slides.EquationSlide(None, "🐱", "🧶", "🚀", pictures={"term_1": wide, "result": tall}),
        slides.WhatDoYouSeeSlide(f"Do you see {LONG_WORD}?"),  # (a word too long for the side: one layout)
        slides.WhatDoYouSeeSlide("What do you see?"),
        slides.WhatDoYouSeeSlide("What do you see?", wide),
        slides.WhatDoYouSeeSlide("Be honest: what do you see?", tall),
        slides.BeforeAfterSlide(None, "Before", wide, "After", tall),
        slides.BeforeAfterSlide("Twelve weeks of cats", "Before", tall, "After", wide),
    ]
    for slide in made:
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    return made


def shortest_picture_prompts(wide, tall):
    return [
        slides.ExhibitSlide("E", "C", wide),
        slides.PickOneSlide("P", wide, tall),
        slides.EquationSlide(None, "A", "B", "C"),
        slides.WhatDoYouSeeSlide("?"),
        slides.WhatDoYouSeeSlide("?", tall),
        slides.BeforeAfterSlide(None, "B", wide, "A", tall),
    ]


# The pictures of every kind's slots, as tests give them: a landscape one and a portrait one, by turns
def _pictures(kind):
    return {slot: _image("wide" if index % 2 == 0 else "tall") for index, slot in enumerate(KINDS[kind].images)}


def _longest(kind, word="Expectation", pictured=True):
    """A slide of the kind with every text as long as a slide takes it (each with the word), with its pictures (or,
    where it can do without them, without: an equation of words, an inkblot)."""
    return _built(kind, _longest_texts(kind, word), _pictures(kind) if pictured else {})


_WITHOUT_PICTURES = ("equation", "what_do_you_see")


# EVERY TYPE, IN EVERY THEME


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_the_longest_texts_fit_and_read_in_every_theme(images, family):
    made = [_longest(kind) for kind in PROMPTS]
    made += [_longest(kind, pictured=False) for kind in _WITHOUT_PICTURES]
    made += shortest_picture_prompts(_image("wide"), _image("tall"))
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)
        assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == []


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_long_words_fit_in_every_theme(images, family):
    made = [_longest(kind, LONG_WORD) for kind in PROMPTS]
    made += [_longest(kind, LONG_WORD, pictured=False) for kind in _WITHOUT_PICTURES]
    made += every_picture_prompt(_image("wide"), _image("tall"))  # (and every layout)
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], (family, seed)


@pytest.mark.slow
def test_every_layout_comes_up_and_needs_what_it_says(images):
    seen = set()
    runs = [slide for slide in every_picture_prompt(_image("wide"), _image("tall")) for _ in range(3)]
    for seed in range(12):
        seen |= {slide.layout for slide in _deck(runs, _theme(seed=seed), seed).slides}
    assert {layout.name for kind in PROMPTS for layout in engine._LAYOUTS[kind]} <= seen

    def fitting(slide):
        return engine.layouts_for(slide.to_deck_slide())

    wide, tall = _image("wide"), _image("tall")
    assert fitting(slides.ExhibitSlide("Exhibit", "Case", wide)) == ["v5/exhibit", "v5/exhibit-marker"]
    assert fitting(slides.PickOneSlide("Pick one:", wide, tall)) == ["v5/pick-one", "v5/pick-one-split"]
    assert fitting(slides.EquationSlide(None, "A", "B", "C")) == ["v5/equation", "v5/equation-stacked"]
    assert fitting(slides.WhatDoYouSeeSlide("What do you see?")) == ["v5/inkblot", "v5/inkblot-side"]
    assert fitting(slides.WhatDoYouSeeSlide(f"See {LONG_WORD}?")) == ["v5/inkblot"]
    assert fitting(slides.WhatDoYouSeeSlide("What do you see?", wide)) == [
        "v5/what-do-you-see",
        "v5/what-do-you-see-band",
    ]
    assert fitting(slides.BeforeAfterSlide(None, "B", wide, "A", tall)) == ["v5/before-after", "v5/before-after-split"]


# WHAT EACH SHOWS


def test_a_talks_exhibits_are_lettered_in_turn_and_are_of_its_first_ones_case(images):
    first = slides.ExhibitSlide("Exhibit", "Case No. 4417-23", _image("wide"), "Found at the scene")
    second = slides.ExhibitSlide("Exhibit", "Case No. 1234-56", _image("tall"))
    between = slides.FunFactSlide("Did you know?", "Cats invented the internet.")
    for seed in range(4):  # (both layouts of each)
        deck = _deck([first, between, second], _theme("clean keynote", seed), seed)
        exhibits = [slide for slide in deck.slides if slide.type == "exhibit"]
        assert [slide.element("label").text for slide in exhibits] == ["Exhibit A", "Exhibit B"]
        assert [slide.element("case").text for slide in exhibits] == ["Case No. 4417-23"] * 2
        for slide in exhibits:
            letter = slide.element("letter")
            if slide.layout == "v5/exhibit-marker":  # (its letter on the marker, which stands over the picture)
                marker = next(element for element in slide.elements if element.role == "marker")
                assert letter.text in "AB" and letter.box.y > marker.box.y and letter.style.color != marker.color
            else:  # (its label on the tag, tied to the picture by a string)
                assert letter is None and {"tag", "tag hole", "string"} <= {element.role for element in slide.elements}
        assert check_design(deck) == []
    assert [slides.exhibit_letter(number) for number in (1, 2, 26, 27, 28)] == ["A", "B", "Z", "AA", "AB"]


def test_an_equations_things_are_pictures_or_emoji_and_what_they_make_comes_on_a_click(images):
    slide = slides.EquationSlide("The formula", "🐱", "🧶", "🚀", pictures={"term_1": _image("wide")})
    content = slide.to_deck_slide()
    assert content.element("term_1") is None and isinstance(content.element("term_1_picture"), ImageElement)
    assert content.element("term_2").text == "🧶" and content.element("result").text == "🚀"
    assert (content.element("plus").text, content.element("equals").text) == ("+", "=")
    clicks = {element.role: element.appears_on_click for element in content.elements if element.appears_on_click}
    assert clicks == {"equals": 1, "result": 1}
    assert slide.missing_content() == []
    for seed in range(4):  # (both layouts)
        (laid_out,) = _deck([slide], _theme("neon", seed), seed).slides
        card = next(element for element in laid_out.elements if element.role == "result card")
        assert card.appears_on_click == 1 and laid_out.element("result").style.size >= 160  # (an emoji, as large)
        assert not next(element for element in laid_out.elements if element.role == "term_2 card").appears_on_click
    # (a thing without its picture nor its emoji is missing)
    assert slides.EquationSlide(None, "🐱", None, "🚀").missing_content() == ["term_2"]


def _inkblot(deck):
    (slide,) = deck.slides
    card = next(element for element in slide.elements if element.role == "inkblot card")
    ink = [element for element in slide.elements if element.role == "inkblot"]
    return card, ink


def _mirror_of(shape, axis, others):
    """Whether another of the shapes is the shape mirrored about the axis (the shape itself, for one across its middle,
    as the body of ink is)."""
    return any(
        abs((2 * axis - other.box.x - other.box.w) - shape.box.x) < 0.5
        and abs(other.box.y - shape.box.y) < 0.5
        and other.shape == shape.shape
        and tuple((round(1 - x, 4), y) for x, y in other.points) == shape.points
        for other in others
    )


def test_without_a_picture_what_do_you_see_is_an_inkblot_mirrored_about_its_middle(images):
    blot = slides.WhatDoYouSeeSlide("What do you see?")
    for family in ("clean keynote", "neon", "kids"):
        card, ink = _inkblot(_deck([blot], _theme(family), 3))
        axis = card.box.x + card.box.w / 2
        assert len(ink) >= 11, family
        assert all(card.box.x <= shape.box.x and shape.box.x + shape.box.w <= card.box.x + card.box.w for shape in ink)
        assert all(_mirror_of(shape, axis, ink) for shape in ink), family  # (every blob and drop has its mirror image)
        assert color.contrast(ink[0].color, card.color) >= color.BODY_CONTRAST, family
    # (laid out again, a deck's inkblot is the same; another deck's another)
    assert _inkblot(_deck([blot], _theme(), 3))[1] == _inkblot(_deck([blot], _theme(), 3))[1]
    assert _inkblot(_deck([blot], _theme(), 3))[1] != _inkblot(_deck([blot], _theme(), 4))[1]


def test_pick_one_has_its_or_on_a_disc_and_an_after_comes_on_a_click(images):
    pick = slides.PickOneSlide("Pick one:", _image("wide"), _image("tall"), "OF")
    after = slides.BeforeAfterSlide("Twelve weeks", "Voor", _image("wide"), "Na", _image("tall"))
    assert not any(element.appears_on_click for element in pick.to_deck_slide().elements)  # (both at once)
    for seed in range(4):  # (both layouts of each)
        picked, transformed = _deck([pick, after], _theme("brutalist", seed), seed).slides
        disc = next(element for element in picked.elements if element.role == "or disc")
        assert picked.element("or").text == "OF" and disc.box.x < picked.element("or").box.x
        clicks = {element.role: element.appears_on_click for element in transformed.elements}
        assert clicks["after"] == clicks["after_picture"] == clicks["after sticker"] == clicks["arrow"] == 1
        assert not clicks["before"] and not clicks["before_picture"] and not clicks["before sticker"]
        assert check_design(_deck([pick, after], _theme("brutalist", seed), seed)) == []


# THE CLASSIC TEMPLATE AND PREVIEWS


def test_a_classic_deck_draws_them_in_the_templates_look(images):
    made = every_picture_prompt(_image("wide"), _image("tall"))
    deck = _deck(made)
    assert deck.theme == "classic" and all(slide.layout == f"classic/{slide.type}" for slide in deck.slides)
    look = themes.CLASSIC_LOOK
    for kinds in (made, shortest_picture_prompts(_image("wide"), _image("tall"))):
        classic_deck = _deck(kinds)
        placed = tuple(
            engine.lay_out_slide(slide, look, random_util.Rng(0).child("classic", slide.type))
            for slide in classic_deck.slides
        )
        checked = classic_deck.model_copy(update={"slides": placed, "style": look, "theme": "classic look"})
        assert [finding for finding in check_design(checked) if finding.check != "variety"] == []


def test_previews_draw_them(images):
    deck = _deck(every_picture_prompt(_image("wide"), _image("tall")), _theme("brutalist"))
    assert preview.contact_sheet(deck).width > 0
    inkblot = next(slide for slide in deck.slides if slide.layout.startswith("v5/inkblot"))
    picture = preview.slide_image(inkblot, deck.style, width=480)
    ink = next(element.color for element in inkblot.elements if element.role == "inkblot")
    shown = {colour for _, colour in picture.getcolors(480 * 270)}
    assert tuple(int(ink[index : index + 2], 16) for index in (1, 3, 5)) in shown


# WHAT A PLAN ASKS FOR, AND THE TALK'S LANGUAGE


def _found(context):
    """A fake image source: the fake image a query names, or none."""
    return _image(context["seed"]) if context["seed"] in ("wide", "tall", "square") else None


def _realized(kind, texts, queries=None, language="en", problems=None, omit=frozenset()):
    recipe = Recipe(kind, tuple(_found for _ in KINDS[kind].images), omit=omit)
    plan = SlidePlan(kind=kind, concept="cats", texts=texts, images=queries or {})
    context = {"seed": "cats", "topic": "cats", "language": language}
    return realize(plan, recipe, context, random_util.Rng(1), 0, problems=problems)


def test_planned_slides_come_out_as_planned(images):
    slide, _ = _realized("exhibit", {"note": "Found at the scene"}, {"picture": "wide"})
    content = slide.to_deck_slide()
    assert (content.element("label").text, content.element("note").text) == ("Exhibit A", "Found at the scene")
    assert content.element("case").text.startswith("Case No. ")
    problems = []
    assert _realized("exhibit", {}, {"picture": "nothing"}, problems=problems) is None and problems
    slide, _ = _realized("pick_one", {}, {"picture_1": "wide", "picture_2": "tall"})
    assert slide.to_deck_slide().element("title").text == "Pick one:"
    slide, _ = _realized("pick_one", {"title": "Choose wisely"}, {"picture_1": "wide", "picture_2": "tall"}, "nl")
    assert (slide.to_deck_slide().element("title").text, slide.to_deck_slide().element("or").text) == (
        "Choose wisely",
        "OF",
    )
    # (an equation's thing whose picture isn't found is its emoji; one whose picture the variant leaves out, too)
    things = {"term_1": "🐱", "term_2": "🧶", "result": "🚀"}
    slide, _ = _realized("equation", things, {"term_1_picture": "wide", "term_2_picture": "nothing"})
    content = slide.to_deck_slide()
    assert isinstance(content.element("term_1_picture"), ImageElement) and content.element("term_1") is None
    assert content.element("term_2").text == "🧶" and content.element("result").text == "🚀"
    problems = []
    assert _realized("equation", {"term_1": "🐱", "result": "🚀"}, problems=problems) is None
    assert problems == ["term_2: not written"]
    # ("What do you see?" without a picture is an inkblot, under talkgenerator's question in the talk's language)
    slide, _ = _realized("what_do_you_see", {}, omit=frozenset({"picture"}), language="de")
    assert slide.to_deck_slide().element("question").text == "Was siehst du?"
    assert slide.to_deck_slide().element("picture") is None
    slide, _ = _realized("what_do_you_see", {"question": "Who is this?"}, {"picture": "tall"})
    assert slide.to_deck_slide().element("question").text == "Who is this?"
    slide, _ = _realized("before_after", {}, {"before_picture": "wide", "after_picture": "tall"}, "nl")
    content = slide.to_deck_slide()
    assert (content.element("before").text, content.element("after").text) == ("Voor", "Na")


@pytest.mark.parametrize("code", sorted(languages.LANGUAGES))
def test_their_words_speak_the_talks_language(images, code):
    language = languages.language(code)
    words = (language.exhibit, language.pick_one, language.either_or, language.what_do_you_see, *language.before_after)
    assert all(word.strip() for word in words) and "{number}" in language.case
    english = (ENGLISH.exhibit, ENGLISH.pick_one, ENGLISH.what_do_you_see, *ENGLISH.before_after)
    assert code == "en" or set(english).isdisjoint(
        (language.exhibit, language.pick_one, language.what_do_you_see, *language.before_after)
    )
    with random_util.use(random_util.Rng(3)):
        exhibit = KINDS["exhibit"].build({}, {"picture": _image("wide")}, language).to_deck_slide()
        seeing = KINDS["what_do_you_see"].build({}, {}, language).to_deck_slide()
    assert exhibit.element("label").text == f"{language.exhibit} A"
    assert exhibit.element("case").text.startswith(language.case.split("{")[0])
    assert seeing.element("question").text == language.what_do_you_see


# THE CLASSIC GENERATORS


def _photo(context):
    return _image("wide")


def _other(context):
    return _image("tall")


def _by_word(context):
    """A picture of the seed (a cat's), or of anything else."""
    return _image("wide" if context["seed"] == "cat" else "square")


CLASSIC = {
    "exhibit": (slide_texts.exhibit(_photo), slides.ExhibitSlide),
    "pick_one": (slide_texts.pick_one(_photo, _other), slides.PickOneSlide),
    "equation": (slide_texts.equation(_by_word, _other), slides.EquationSlide),
    "what_do_you_see": (slide_texts.what_do_you_see(_photo), slides.WhatDoYouSeeSlide),
    "before_after": (slide_texts.before_after(_photo, _other), slides.BeforeAfterSlide),
}


@pytest.mark.parametrize("kind", PROMPTS)
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


def test_the_classic_ones_take_their_words_from_the_pack_or_talkgenerator(related):
    seen = {"titles": set(), "questions": set(), "inkblots": 0, "shapes": set()}
    for seed in range(60):
        with random_util.use(random_util.Rng(seed)):
            title, *_ = slide_texts.pick_one(_photo, _other)({"seed": "cat", "topic": "cats"})
            question, picture = slide_texts.what_do_you_see(_photo)({"seed": "cat", "topic": "cats"})
            made = slide_texts.equation(_by_word, _other)({"seed": "cat", "topic": "cats"})
        seen["titles"].add(title)
        seen["questions"].add(question)
        seen["inkblots"] += picture is None
        boxes = made[-1].by_box() if isinstance(made[-1], slides.Pictures) else {}
        seen["shapes"].add(tuple(thing in boxes for thing in classic.EQUATION))
        assert made[1] == "🐱" and made[3]  # (the seed's own emoji first; a surprise last)
    assert ENGLISH.pick_one in seen["titles"] and len(seen["titles"]) > 3
    assert ENGLISH.what_do_you_see in seen["questions"] and len(seen["questions"]) > 3
    assert 5 <= seen["inkblots"] <= 25  # (a quarter of them, INKBLOTS)
    assert seen["shapes"] == {(True, True, True), (True, True, False), (False, False, True), (False, False, False)}


def test_slides_that_stand_in_look_no_picture_up(related):
    def never(context):
        raise AssertionError("looked a picture up")

    standing_in = {"seed": "cat", "topic": "cats", slides.STANDING_IN: True}
    for seed in range(6):
        with random_util.use(random_util.Rng(seed)):
            assert slide_texts.exhibit(never)(standing_in) is None
            assert slide_texts.pick_one(never, never)(standing_in) is None
            assert slide_texts.before_after(never, never)(standing_in) is None
            made = slide_texts.equation(never, never)(standing_in)
            assert not isinstance(made[-1], slides.Pictures) and all(made[1:])  # (emoji, or words)
            assert slide_texts.what_do_you_see(never)(standing_in)[1] is None  # (an inkblot)


def test_the_classic_generators_leave_sensitive_seeds_alone(related):
    with random_util.use(random_util.Rng(1)):
        assert all(content({"seed": "islam", "topic": "cats"}) is None for content, _ in CLASSIC.values())


# THE FORMATS


@pytest.mark.parametrize("format_name", ["default", "interview", "ted"])
def test_every_ted_like_format_has_them_in_its_middle(format_name):
    schema = get_schema(format_name)
    kinds = {generator.llm.kind: generator for generator in schema.slide_generators if generator.llm is not None}
    assert set(PROMPTS) <= set(kinds)
    assert {tag: schema._max_allowed_tags[tag] for tag in PROMPTS} == {
        "before_after": 1,
        "equation": 1,
        "exhibit": 2,  # (Exhibit A, and now and then a later Exhibit B)
        "pick_one": 1,
        "what_do_you_see": 1,
    }
    for kind in PROMPTS:  # (in the middle of a talk: not the title, the presenter's introduction, or the end)
        weight = kinds[kind].get_weight_for
        assert weight(5, 10) > 0 == weight(1, 10) == weight(9, 10)
    choices = external.recipes_of(schema)
    assert {external.default_recipe(choices, kind).recipe.kind for kind in PROMPTS} == set(PROMPTS)


def test_talks_without_fair_use_get_an_inkblot_and_open_pictures():
    ted = {generator.name: generator for generator in get_schema("ted").slide_generators}
    default = {generator.name: generator for generator in get_schema("default").slide_generators}
    assert ted["What Do You See (CRF)"].llm.slots() == []  # (an inkblot: pareidolia is Reddit's only)
    assert [slot.aesthetic for _, slot in default["What Do You See"].llm.slots()] == ["pareidolia"]
    for name in ("Exhibit A (CRF)", "Pick One (CRF)", "Picture Equation (CRF)", "Before And After (CRF)"):
        assert all(finder.servable(slot, licenses.OPEN) for _, slot in ted[name].llm.slots()), name


def test_the_language_model_is_asked_for_what_each_shows():
    default = {
        generator.llm.kind: generator.llm for generator in get_schema("default").slide_generators if generator.llm
    }
    queries = {kind: set() for kind in PROMPTS}
    fields = {kind: set() for kind in PROMPTS}
    for seed in range(40):
        for kind in PROMPTS:
            recipe = default[kind].varied(random_util.Rng(seed))
            queries[kind].add(tuple(recipe.image_queries()))
            fields[kind].add(tuple(text.name for text in recipe.written_fields()))
            # (every picture's query says what to search for)
            schema = prompt.slide_schema(recipe)
            assert all(
                "image search query for" in schema["properties"][f"{slot}_query"]["description"]
                for slot in recipe.image_queries()
            )
    assert queries["exhibit"] == {("picture",)} and queries["before_after"] == {("before_picture", "after_picture")}
    assert queries["pick_one"] == {("picture_1", "picture_2")}
    assert queries["equation"] == {
        ("term_1_picture", "term_2_picture", "result_picture"),
        ("term_1_picture", "term_2_picture"),
        ("result_picture",),
        (),
    }
    # (an equation's things are always written, as emoji, for a picture that isn't found)
    assert all({"term_1", "term_2", "result"} <= set(written) for written in fields["equation"])
    assert queries["what_do_you_see"] == {("picture",), ()}  # (a face in something, or an inkblot)
    assert ("question",) in fields["what_do_you_see"] and () in fields["what_do_you_see"]


def test_they_are_drawn_types_and_two_are_spares():
    assert classic.PICTURE_PROMPT_TYPES <= classic.DRAWN_TYPES
    for kind in PROMPTS:
        assert set(classic.REQUIRED_ROLES[kind]) <= set(classic.CLASSIC_ROLES[kind].values())
        assert kind in engine._LAYOUTS and kind in KINDS
    spares = {generator.name for generator, _ in slide_schemas.SPARE_GENERATORS}
    assert {"What Do You See", "Picture Equation"} <= spares


def test_a_classic_equation_shows_a_picture_once(related, images):
    # (the same picture for two of its things: the second is its emoji)
    for seed in range(12):
        with random_util.use(random_util.Rng(seed)):
            made = slide_texts.equation(_photo, _photo)({"seed": "cat", "topic": "cats"})
        boxes = made[-1].by_box() if isinstance(made[-1], slides.Pictures) else {}
        assert len(boxes) <= 1 and slides.EquationSlide(*made[:4], pictures=boxes).missing_content() == []
