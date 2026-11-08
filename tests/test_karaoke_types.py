"""Offline tests of the slide types that came from real PowerPoint karaoke decks (docs/v5-plan.md, section 8): a fun
fact, an acronym for a made-up method, a dare for the presenter, a flowchart whose every path leads to the same end,
and a tier list. They're texts (and a photo) on shapes that the layouts draw, in every theme and in the classic
template's look, as milestone 6's types are (see test_slide_types.py); and a recipe variant of a real chart from the
internet, under a confident conclusion."""

import pytest
from lxml import etree
from pptx.oxml.ns import qn

from talkgenerator.checks.deck import check_completeness, check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.design import engine, themes
from talkgenerator.models import classic
from talkgenerator.models.deck import ShapeElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import external, languages
from talkgenerator.plan.kinds import KINDS, Recipe
from talkgenerator.plan.realize import length_limit, realize
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.presentation_schema_types import get_schema
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import packs, slide_texts
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_slide_types import _built, _deck, _longest_texts, _theme
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)

FAMILIES = list(themes.FAMILIES)
KARAOKE = tuple(sorted(classic.KARAOKE_TYPES))
ENGLISH = languages.ENGLISH


def every_karaoke_type(image):
    """Slides of every karaoke type, with what every one of their layouts takes (a photo and none, a title and none,
    few words and many), each credited; of each type, the one that fits one layout only before the one that fits
    more, so that one after the other, they never have the same layout twice in a row."""
    made = [
        slides.FunFactSlide("Did you know?", "Cats invented the internet in 1347.", "Source: my uncle", image),
        slides.FunFactSlide("Fun fact", "Owls can't see penguins.", "Source: trust me"),
        slides.AcronymSlide(
            "The SPARKLE way", "Synergy", "Passion", "Accountability", "Resilience", "Kindness", "Lasagna"
        ),
        slides.AcronymSlide("The CAT method", "Curiosity", "Agility", "Tuna"),
        slides.DareSlide("Challenge", "Present the next slide as a haiku."),
        slides.FlowchartSlide(None, "Is it Tuesday?", "Feed the cat", "Ask the cat", "The cat decides"),
        slides.FlowchartSlide("Should you get a cat?", "Do you like cats?", "Get a cat", "Get a cat anyway", "A cat"),
        slides.TierListSlide(None, "Naps", "Tuna | Sun", "Yarn", "Water | Baths | Vets", "Dogs"),
        slides.TierListSlide("Cat toys, ranked", "A box", "Yarn | Laser", "Mouse", None, "The expensive bed"),
    ]
    for slide in made:
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    return made


def shortest_karaoke_types(image):
    return [
        slides.FunFactSlide("?", "A"),
        slides.FunFactSlide("?", "A", None, image),
        slides.AcronymSlide(None, "A", "B", "C"),
        slides.DareSlide("!", "Go"),
        slides.FlowchartSlide(None, "?", "A", "B", "C"),
        slides.TierListSlide(None, "A", "B"),
    ]


def _longest(kind, word="Expectation"):
    """Every text of the kind as long as a slide takes it, as in test_slide_types; an acronym's acronym the initials
    of its words, and a tier list's tiers three things each."""
    texts = _longest_texts(kind, word)
    if kind == "acronym":
        texts["acronym"] = word[0] * slides.ACRONYM_LETTERS
    if kind == "tier_list":
        for name in ("a_tier", "b_tier", "c_tier", "f_tier"):
            limit = length_limit(next(text for text in KINDS[kind].texts if text.name == name))
            item = " ".join([word] * 3)[: limit // 3 - 3].strip()
            texts[name] = " | ".join([item] * 3)
    return texts


# EVERY TYPE, IN EVERY THEME


@pytest.mark.parametrize("family", FAMILIES)
def test_the_longest_texts_fit_and_read_in_every_theme(images, family):
    with_photo = [_built(kind, _longest(kind), {"photo": _image("wide")}) for kind in KARAOKE]
    without = [_built(kind, _longest(kind), {"photo": None}) for kind in KARAOKE]
    one_long_thing = _longest("tier_list")
    one_long_thing.update({name: _longest_texts("tier_list")[name] for name in ("a_tier", "f_tier")})
    made = [*with_photo, *without, _built("tier_list", one_long_thing), *shortest_karaoke_types(_image("tall"))]
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)
        assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == []


@pytest.mark.parametrize("family", FAMILIES)
def test_long_words_fit_in_every_theme(images, family):
    # (compounds, as Dutch and German have them)
    made = [
        _built(kind, _longest(kind, "Brandweerkazernedeur"), {"photo": photo})
        for kind in KARAOKE
        for photo in (_image("wide"), None)
    ]
    made += every_karaoke_type(_image("wide"))  # (and the layouts for few short words, or a title beside)
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
    assert fitting(slides.AcronymSlide("C", "Cat", "Apple", "Toast")) == ["v5/acronym", "v5/acronym-across"]
    assert fitting(slides.AcronymSlide("C", "Cat", "Apple", "Teamworkingness")) == ["v5/acronym"]  # (a long word)
    assert fitting(slides.AcronymSlide("C", *"ABCDEF")) == ["v5/acronym"]  # (six letters)
    assert fitting(slides.FlowchartSlide(None, "?", "A", "B", "C")) == ["v5/flowchart"]
    assert fitting(slides.TierListSlide("Ranked", "A", "B")) == ["v5/tier-list", "v5/tier-list-side"]


def test_texts_on_shapes_read_on_them(images):
    for seed in range(6):
        deck = _deck(every_karaoke_type(_image("wide")), _theme("neon", seed), seed)
        for slide in deck.slides:
            if slide.type == "fun_fact":
                sticker = next(element for element in slide.elements if element.role == "kicker sticker")
                kicker = slide.element("kicker")
                assert isinstance(sticker, ShapeElement) and isinstance(kicker, TextElement)
                assert kicker.style.color != sticker.color
        assert check_design(deck) == []


# WHAT AN ACRONYM, A DARE, A FLOWCHART AND A TIER LIST SHOW


def test_an_acronym_is_its_words_initials_and_its_words_come_one_by_one():
    deck_slide = slides.AcronymSlide("The SPARK method", "synergy", "Passion", "agility", "Resilience", "kazoos")
    deck_slide = deck_slide.to_deck_slide()
    assert [deck_slide.element(f"letter_{index}").text for index in range(1, 6)] == list("SPARK")
    clicks = [(element.role, element.appears_on_click) for element in deck_slide.elements if element.appears_on_click]
    assert clicks == [(f"word_{index}", index) for index in range(1, 6)]  # (its letters are there from the start)
    assert deck_slide.element("letter_6") is None and deck_slide.element("word_6") is None


def test_a_dares_heading_and_a_flowcharts_answers_speak_the_talks_language():
    dutch = languages.language("nl")
    dare = KINDS["dare"].build({"dare": "Doe de volgende dia als haiku."}, {}, dutch).to_deck_slide()
    assert dare.element("kicker").text == "Uitdaging"
    texts = {"title": None, "question": "Is het dinsdag?", "yes_step": "Ja", "no_step": "Nee", "end": "Koffie"}
    flowchart = KINDS["flowchart"].build(texts, {}, dutch).to_deck_slide()
    assert (flowchart.element("yes").text, flowchart.element("no").text) == ("Ja", "Nee")
    clicks = {element.role: element.appears_on_click for element in flowchart.elements if element.appears_on_click}
    assert clicks == {"yes": 1, "yes_step": 1, "no": 2, "no_step": 2, "end": 3}


def test_a_flowcharts_ways_and_its_end_appear_with_their_boxes_and_lines(images):
    deck = _deck([slides.FlowchartSlide("F", "Q?", "A", "B", "The end")], _theme())
    end_box = next(element for element in deck.slides[0].elements if element.role == "end box")
    assert end_box.appears_on_click == 3 == deck.slides[0].element("end").appears_on_click
    yes, no, end = _clicks(render_pptx(deck).slides[0])
    assert set(yes) == {"yes", "yes_step", "yes_step box", "line"} and set(no) == {
        "no",
        "no_step",
        "no_step box",
        "line",
    }
    assert set(end) == {"end", "end box", "line"}


def test_a_tier_list_leaves_out_empty_tiers_and_fills_its_tiers_from_the_worst_up(images):
    deck_slide = slides.TierListSlide("Ranked", "Naps", "Tuna | Sun", " | ", "Baths", None).to_deck_slide()
    roles = [element.role for element in deck_slide.elements]
    assert "tier_b" not in roles and "tier_f" not in roles and {"tier_s", "tier_a", "tier_c"} <= set(roles)
    clicks = [(element.role, element.appears_on_click) for element in deck_slide.elements if element.appears_on_click]
    assert sorted(clicks, key=lambda click: click[1]) == [
        ("item_c_1", 1),
        ("item_a_1", 2),
        ("item_a_2", 2),
        ("item_s_1", 3),
    ]
    placed = _deck([slides.TierListSlide("Ranked", "Naps", "Tuna | Sun", None, "Baths")], _theme()).slides[0]
    tiles = [element for element in placed.elements if element.role.endswith(" tile")]
    assert [tile.role for tile in tiles] == ["tier s tile", "tier a tile", "tier c tile"]
    assert tiles[0].color == engine._TIER_COLOURS["s"] and tiles[0].box.y < tiles[1].box.y < tiles[2].box.y


def _clicks(ppt_slide):
    """The shapes (by name) that each click of the slide shows, in order."""
    names = {str(shape.shape_id): shape.name for shape in ppt_slide.shapes}
    timing = ppt_slide.element.find(qn("p:timing"))
    if timing is None:
        return []
    namespaces = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    steps = etree.XPath(".//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par", namespaces=namespaces)(timing)
    targets = etree.XPath(".//p:spTgt/@spid", namespaces=namespaces)
    return [sorted({names[spid] for spid in targets(step)}) for step in steps]


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
    words = {"word_1": "S - Synergy", "word_2": "Passion", "word_3": "Élan", "word_4": "Kazoos"}
    slide, _ = _realized("acronym", {"title": "The SPEK method", "acronym": "S.P.E.K.", **words})
    assert [slide.to_deck_slide().element(f"letter_{index}").text for index in range(1, 5)] == ["S", "P", "É", "K"]
    assert slide.to_deck_slide().element("word_1").text == "Synergy"  # (without the letter the model put in front)
    # (a model's acronym that its words don't spell: the words decide, and the title says what they spell)
    slide, _ = _realized("acronym", {"title": "The S.P.A.R.K. method", "acronym": "S.P.A.R.K.", **words})
    assert slide.to_deck_slide().element("title").text == "The S.P.E.K. method"
    slide, _ = _realized("acronym", {"title": "The Pirates way", "acronym": "PIRATES", **words})
    assert slide.to_deck_slide().element("title").text == "The SPEK way"
    six = {f"word_{index}": word for index, word in enumerate(("Clip", "Aerate", "Lock", "Eat", "Nap", "Dance"), 1)}
    eight = {"title": "The C.A.L.E.N.D.A.R. Method", "acronym": "CALENDAR", **six}  # (eight letters, six words)
    assert _built("acronym", eight).to_deck_slide().element("title").text == "The C.A.L.E.N.D. Method"
    # (and a title that names another acronym than the one the model wrote, which the words spell)
    other = {"title": "PRISM Method For Plants", "acronym": "CALEND", **six}
    assert _built("acronym", other).to_deck_slide().element("title").text == "CALEND Method For Plants"
    plain = {"title": "The Lighthouse Method", "acronym": "CALEND", **six}  # (one that names none stays)
    assert _built("acronym", plain).to_deck_slide().element("title").text == "The Lighthouse Method"
    tiers = {"title": "Ranked", "s_tier": "Naps", "a_tier": "Tuna | Sun | Yarn | Laser", "f_tier": ""}
    slide, _ = _realized("tier_list", tiers)
    assert [element.text for element in slide.to_deck_slide().elements if element.role.startswith("item_a")] == [
        "Tuna",
        "Sun",
        "Yarn",
    ]
    problems = []
    assert _realized("tier_list", {**tiers, "a_tier": " | "}, problems=problems) is None
    assert problems == ["a tier list needs things in its S and A tiers"]


@pytest.mark.parametrize("code", sorted(languages.LANGUAGES))
def test_their_headings_speak_the_talks_language(code):
    language = languages.language(code)
    assert len(language.fun_facts) == 2 and all(heading.strip() for heading in language.fun_facts)
    assert code == "en" or (set(language.fun_facts).isdisjoint(ENGLISH.fun_facts) and language.dare != ENGLISH.dare)
    with random_util.use(random_util.Rng(3)):
        slide = KINDS["fun_fact"].build({"fact": "Ugler kan ikke se katter", "source": None}, {"photo": None}, language)
    assert slide.to_deck_slide().element("kicker").text in language.fun_facts


# THE CLASSIC GENERATORS


def _photo(context):
    return _image("wide")


CLASSIC = {
    "fun_fact": (slide_texts.fun_fact(_photo), slides.FunFactSlide),
    "acronym": (slide_texts.generate_acronym, slides.AcronymSlide),
    "dare": (slide_texts.generate_dare, slides.DareSlide),
    "flowchart": (slide_texts.generate_flowchart, slides.FlowchartSlide),
    "tier_list": (slide_texts.generate_tier_list, slides.TierListSlide),
}


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


def test_a_classic_acronym_spells_the_seed_and_ends_on_something_absurd(related):
    with random_util.use(random_util.Rng(4)):
        title, *words = slide_texts.generate_acronym({"seed": "cat", "topic": "cats"})
    assert "".join(word[0].upper() for word in words) == "CAT" and "CAT" in title
    assert words[-1] in packs.pack().rule("karaoke.absurd_t")
    with random_util.use(random_util.Rng(4)):  # (a seed that's no word to spell: a related word, or a known one)
        _, *words = slide_texts.generate_acronym({"seed": "the French Revolution", "topic": "history"})
    assert 3 <= len(words) <= 6 and all(word[:1].isupper() or word[:1] == "e" for word in words)


def test_a_classic_tier_list_ranks_the_seed_first_and_something_loved_last(related):
    with random_util.use(random_util.Rng(2)):
        title, best, *tiers, worst = slide_texts.generate_tier_list({"seed": "cat", "topic": "cats"})
    assert best == "Cats" and worst in packs.pack().rule("karaoke.tier_list_worst")
    assert tiers[0] and all(len(slides.tier_items(tier)) <= 3 for tier in tiers) and title


@pytest.mark.parametrize(
    ("seed", "said", "never"),
    [
        ("coffee", "coffee", ("coffees", "a coffee")),
        ("penguin", "penguins", ("penguins is", "penguins was", "a penguins")),
        ("the french revolution", "the french revolution", ("the the", "a the", "revolutions")),
    ],
)
def test_classic_templates_speak_of_the_seed_as_english_does(seed, said, never):
    grammar = packs.pack().grammar("karaoke")
    names = ("fun_fact", "acronym_title", "dare", "flowchart_title", "flowchart_question", "flowchart_end")
    names += ("flowchart_yes", "flowchart_no", "tier_list_title")
    variables = {"seed": seed, "related": "bean", "number": "12", "percent": "40%", "year": "1823", "acronym": "PEN"}
    filled = [
        slide_texts.text_generator.apply_variables_to_template(template, variables)
        for name in names
        for template in grammar[name]
    ]
    assert all(filled) and len(grammar["fun_fact"]) >= 20 and len(grammar["dare"]) >= 12
    assert any(said in text.lower() for text in filled)
    assert not [text for text in filled if any(wrong in text.lower() for wrong in never) or "{" in text]


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
    assert kinds["dare"].get_weight_for(5, 10) < kinds["acronym"].get_weight_for(5, 10)  # (one in a deck, at most)
    assert "diagram" in kinds["flowchart"].get_tags()  # (two diagrams in ten slides, at most)
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


# RECIPE VARIANTS: A REAL CHART FROM THE INTERNET, OUT OF CONTEXT, UNDER A CONFIDENT CONCLUSION


def _reddit_chart():
    return {generator.name: generator for generator in get_schema("default").slide_generators}["Reddit Chart"]


def test_a_real_chart_comes_under_a_confident_conclusion_or_bare():
    recipe = _reddit_chart().llm
    concluded, bare = recipe.variants
    assert concluded.weight == 2 * bare.weight and bare.omit == frozenset({"title"})
    assert "conclusion" in recipe.hints["title"] and "title" not in recipe.omit
    varied = [recipe.varied(random_util.Rng(seed)) for seed in range(30)]
    assert {"title" in recipe.omit for recipe in varied} == {True, False}
    titled = next(recipe for recipe in varied if "title" not in recipe.omit)
    assert [text.name for text in titled.written_fields()] == ["title"] and "conclusion" in titled.brief


def test_a_classic_chart_comes_under_a_conclusion_two_times_in_three(images):
    titles = packs.pack().rule("charts.chart_conclusion")
    generator = SlideGeneratorData(
        slide_generator_types.FullImageSlideGenerator.of(
            _reddit_chart()._generator._slide_content_generator._generators[0], lambda context: _image("wide")
        ),
        retries=1,
        name="Reddit Chart",
    )
    found = []
    for seed in range(60):
        with random_util.use(random_util.Rng(seed)):
            slide, _ = generator.generate({"seed": "penguin", "topic": "penguins"}, set())
        found.append(slide.to_deck_slide().element("title"))
    concluded = [title.text for title in found if title is not None]
    assert 0.5 <= len(concluded) / len(found) <= 0.8
    filled = {slide_texts.text_generator.apply_variables_to_template(title, {"seed": "penguin"}) for title in titles}
    assert set(concluded) <= filled


@pytest.mark.parametrize("seed", ["coffee", "penguin", "the french revolution"])
def test_classic_chart_conclusions_speak_of_the_seed_as_english_does(seed):
    for template in packs.pack().rule("charts.chart_conclusion"):
        text = slide_texts.text_generator.apply_variables_to_template(template, {"seed": seed})
        assert text and "{" not in text and "coffees" not in text and "the the" not in text, text
