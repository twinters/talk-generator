"""Offline tests of livelier dares, closing slides and references, emoji in lists, and slide numbers (docs/v5-plan.md,
D65), from the user's look at 35 sample talks (2026-11-09): dares that are real challenges for the presenter or for the
whole audience, closing slides that end on a funny picture, a last tip or a callback to an earlier slide's picture,
references with a picture of one of the works, emoji in front of a list's things now and then, and every slide
numbered of the deck's ("7/12")."""

import dataclasses
import re

import pytest
from pptx.oxml.ns import qn

from talkgenerator.checks.deck import check_deck
from talkgenerator.checks.design import check_design
from talkgenerator.design import engine, fonts, themes
from talkgenerator.models.deck import DECORATION, ImageElement, TextElement
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import CALLBACK_LINE, KINDS, LAST_TIP
from talkgenerator.plan.realize import clean_text, length_limit, realize
from talkgenerator.render import shapes
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import presentation_schema, slide_schemas
from talkgenerator.schema.formats import (
    academic,
    book_report,
    corporate,
    court,
    documentary,
    infomercial,
    museum,
    pitch,
    wedding,
)
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.sources import emoji, packs, slide_texts
from talkgenerator.util import emoji_util, random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_design import _deck as _every_kind_of_slide_deck
from tests.test_slide_types import _deck, _theme
from tests.test_slide_types import related as related  # fake ConceptNet (a fixture)

FAMILIES = list(themes.FAMILIES)
# A slide's number of the deck's as a family writes it: "7/12", "07/12", "7 / 12", "[07/12]", "# 07/12"
_COUNT = re.compile(r"^\[?(?:# )?0*(\d+) ?/ ?(\d+)\]?$")


def _numbers(slide):
    """The slide numbers a slide's decoration writes, as (number, total)."""
    return [
        (int(match.group(1)), int(match.group(2)))
        for element in slide.elements
        if isinstance(element, TextElement) and element.role == DECORATION
        if (match := _COUNT.match(element.text))
    ]


# SLIDE NUMBERS


@pytest.mark.parametrize("family", FAMILIES)
def test_every_family_numbers_its_slides_of_the_decks(images, family):
    for seed in (1, 2):
        deck = _every_kind_of_slide_deck(seed=seed, theme=_theme(family, seed)).to_deck()
        total = len(deck.slides)
        numbered = 0
        for number, slide in enumerate(deck.slides, 1):
            found = _numbers(slide)
            assert found in ([], [(number, total)]), (family, number, found)
            numbered += bool(found)
        assert numbered >= total - 3, (family, seed)  # (not over a full-screen photo, nor where a big title is)
        findings = [finding for finding in check_design(deck) if "decoration" in finding.message]
        assert findings == [], (family, findings)


def test_a_padded_number_pads_its_total_too():
    # (the user, 2026-11-10: "03/8" put a 0 before the number but not before the total; "either one")
    from talkgenerator.design import motifs

    eight = dataclasses.make_dataclass("Scene", [("number", int), ("total", int)])(2, 8)
    assert motifs._count(eight, padded=True) == "03/08"
    assert motifs._count(eight) == "3/8"
    assert motifs._count(dataclasses.replace(eight, number=6, total=12), padded=True, gap=" ") == "07 / 12"


def test_a_talk_that_streams_numbers_its_slides_of_the_ones_it_will_have():
    layout = engine.DeckLayout(3, _theme("clean keynote"), total=12)
    first = layout.next(slides.AgendaSlide("Today", "One", "Two", "Three").to_deck_slide())
    second = layout.next(slides.QuestionsSlide("Questions?").to_deck_slide())
    assert _numbers(first) == [(1, 12)] and _numbers(second) == [(2, 12)]
    alone = engine.lay_out_slide(slides.QuestionsSlide("?").to_deck_slide(), _theme(), random_util.Rng(1), number=6)
    written = [element.text for element in alone.elements if isinstance(element, TextElement)]
    assert "07" in written and not any("/" in text for text in written)  # (no total: its number alone, "07")


def test_the_2019_template_numbers_its_slides_too(images):
    made = [
        slides.TitleSlide("Cats", "By me"),
        slides.ImageSlide("A cat", _image("wide")),
        slides.QuestionsSlide("Questions?", "Answers not guaranteed"),
    ]
    made[1].add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    presentation = render_pptx(_deck(made))
    width = presentation.slide_width
    for number, ppt_slide in enumerate(presentation.slides, 1):
        numbers = [shape for shape in ppt_slide.shapes if shape.name == "Slide number"]
        assert [shape.text_frame.text for shape in numbers] == [f"{number}/3"]
        assert numbers[0].left + numbers[0].width <= width
        credits = [shape for shape in ppt_slide.placeholders if shape.placeholder_format.idx == 10]
        assert all(shape.left + shape.width <= numbers[0].left for shape in credits)  # (the credit line ends first)


# EMOJI


def test_emoji_are_told_apart_and_measured_as_wide_as_an_emoji_font_draws_them():
    assert emoji_util.runs("🐧 Penguins") == [("🐧", True), (" Penguins", False)]
    assert emoji_util.runs("Love ❤️ it") == [("Love ", False), ("❤️", True), (" it", False)]
    assert emoji_util.count("☕ Coffee") == 1 and emoji_util.count("★ 4/5 → ×") == 0  # (stars and arrows are text)
    plain = fonts.text_width(" Penguins", "Arial", 100)
    assert fonts.text_width("🐧 Penguins", "Arial", 100) == pytest.approx(plain + emoji_util.WIDTH * 100)


def test_the_language_model_writes_emoji_only_where_a_field_asks_for_them():
    assert "- emoji, except where a field asks for them." in prompt.SYSTEM_PROMPT
    for name in ("Tier List", "Alignment Chart", "Agenda"):
        recipe = slide_schemas.slide_generators.get(name).llm
        asking = [variant for variant in recipe.variants if any("emoji" in hint for hint in variant.hints.values())]
        assert asking and all("emoji" in variant.note for variant in asking), name
        # (in front of every thing: not D73's pattern breaks, such as an S tier of one emoji)
        in_front = [variant for variant in asking if "pattern" not in variant.note]
        share = sum(variant.weight for variant in in_front) / sum(variant.weight for variant in recipe.variants)
        assert 0.2 <= share <= 1 / 3 + 0.01, name  # (now and then)
        plain = [variant for variant in recipe.variants if variant not in asking]
        assert plain and not any("emoji" in hint for variant in plain for hint in variant.hints.values())


def test_a_variant_that_asks_for_emoji_gets_them_where_the_model_wrote_none():
    recipe = slide_schemas.slide_generators.get("Tier List").llm
    asking = next(variant for variant in recipe.variants if variant.emoji and not variant.omit)
    chosen = dataclasses.replace(recipe, variants=(asking,)).varied(random_util.Rng(1))
    texts = {
        "title": "Pigeons, ranked",
        "s_tier": "🐦 Pigeons",  # (the model's own emoji stays)
        "a_tier": "Bread | Statues",
        "b_tier": "Benches",
        "c_tier": "Cars",
        "f_tier": "Hawks",
    }
    for language, own in (("en", True), ("nl", False)):
        plan = SlidePlan(kind="tier_list", concept="pigeons", texts=texts)
        context = {"seed": "pigeons", "topic": "pigeons", "language": language}
        made = realize(plan, chosen, context, random_util.Rng(1), 0)
        assert made is not None
        things = made[0].to_slide_dictionary()
        assert things["item_s_1"] == "🐦 Pigeons"
        assert things["item_a_1"] == ("🍞 Bread" if own else things["item_a_1"])  # (by its word, in English)
        listed = [value for key, value in things.items() if key.startswith("item_") and value]
        assert len(listed) == 6 and all(emoji_util.runs(value)[0][1] for value in listed), listed
    plain = next(variant for variant in recipe.variants if not variant.emoji and not variant.omit)
    unasked = dataclasses.replace(recipe, variants=(plain,)).varied(random_util.Rng(1))
    made = realize(SlidePlan(kind="tier_list", concept="pigeons", texts=texts), unasked, context, random_util.Rng(1), 0)
    assert made is not None and made[0].to_slide_dictionary()["item_a_1"] == "Bread"


def test_a_list_is_cut_between_its_things_and_its_emoji_count_as_two_characters():
    tier = next(text for text in KINDS["tier_list"].texts if text.name == "a_tier")
    # (a free model's tier, cut in the middle of its last thing, left a bare emoji: "| 🦅")
    written = "💩 Pooping on wedding dresses | 🤯 Getting stuck in escalators | 🦅 Running from hawks"
    assert clean_text(written, tier) == "💩 Pooping on wedding dresses | 🤯 Getting stuck in escalators"
    # (83 characters, but 76 characters' room: its joined emoji are written with five or three characters each)
    spies = "🕵️‍♂️ Navigating subway tunnels | 🕵️‍♀️ Delivering love notes | 🧑‍🚀 Hitting targets"
    assert len(spies) > length_limit(tier) >= emoji_util.room(spies) and clean_text(spies, tier) == spies
    assert emoji_util.room("🕵️‍♂️ Spies") == 8 and emoji_util.room("❤️ it") == 5 and emoji_util.room("Plain") == 5


def test_a_list_whose_model_wrote_other_bars_or_emoji_as_things_of_their_own_comes_out_whole():
    tier = next(text for text in KINDS["tier_list"].texts if text.name == "a_tier")
    # (a free model's tiers, 2026-11-09: box-drawing bars for its |, and its emoji as things of their own)
    written = "🏋️ │ Loving your boss │ ☕│ Buying good cheese │ 🧀│ Doing moderate exercise │ 🏃"
    assert clean_text(written, tier) == "🏋️ Loving your boss | ☕ Buying good cheese | 🧀 Doing moderate exercise"
    assert clean_text("🔥 │ Roasting coffee as tea │ 🔥", tier) == "🔥 Roasting coffee as tea"
    assert clean_text("Bread｜Statues", tier) == "Bread | Statues"


def test_a_third_of_classic_tier_lists_alignment_charts_and_agendas_have_emoji(related):
    def emojified(texts):
        things = [thing for text in texts if text for thing in text.split("|")]
        starts = [emoji_util.runs(thing.strip())[0][1] for thing in things if thing.strip()]
        assert all(starts) or not any(starts)  # (every thing, or none)
        return all(starts)

    counts = {"tier list": 0, "alignment chart": 0, "agenda": 0}
    for seed in range(30):
        with random_util.use(random_util.Rng(seed)):
            tier_list = slide_texts.generate_tier_list({"seed": "cat", "topic": "cats"})
            alignment = slide_texts.generate_alignment_chart({"seed": "cat", "topic": "cats"})
            agenda = slide_texts.generate_agenda({"seed": "cat", "topic": "cats"})
        counts["tier list"] += emojified(tier_list[1:])
        counts["alignment chart"] += emojified(alignment[3:])
        counts["agenda"] += emojified(agenda[1:])
        if emojified(tier_list[1:]):
            assert tier_list[1].startswith("🐱 ")  # (the S tier's cats, by their own emoji)
    assert all(4 <= count <= 18 for count in counts.values()), counts


def test_a_things_own_emoji_go_first_and_its_places_mood_else():
    assert emoji.own("Fresh bread") == "🍞" and emoji.own("Hot dogs") == "🌭" and emoji.own("Penguins") == "🐧"
    assert emoji.own("Antarctica") is None
    with random_util.use(random_util.Rng(1)):
        assert emoji.with_emoji("Antarctica", "tier_f").split(" ", 1)[0] in emoji._emoji()[1]["tier_f"]
        assert emoji.with_emoji("🐧 Penguins", "tier_s") == "🐧 Penguins"  # (one emoji is enough)
        assert emoji.listed("Fish | Ice", "tier_a") == "🐟 Fish | 🧊 Ice"


def test_emoji_go_into_powerpoint_in_an_emoji_font_and_their_texts_fit(images):
    tier_list = slides.TierListSlide("Cats, ranked", "🐱 Cats", "🐶 Dogs | 🐭 Mice", None, None, "🛁 Baths")
    deck = _deck([tier_list], _theme("clean keynote"))
    assert [finding for finding in check_deck(deck) if finding.severity == "error"] == []
    presentation = render_pptx(deck)
    runs = [
        run
        for shape in presentation.slides[0].shapes
        if shape.has_text_frame
        for run in shape.text_frame.paragraphs[0].runs
    ]
    fonts_of = {run.text: run.font.name for run in runs}
    assert fonts_of["🐱"] == emoji_util.EMOJI_FONT and fonts_of[" Cats"] == deck.style.fonts.body
    emoji_run = next(run for run in runs if run.text == "🐶")
    typefaces = {child.tag.split("}")[1]: child.get("typeface") for child in emoji_run._r.find(qn("a:rPr"))}
    assert typefaces["ea"] == typefaces["cs"] == typefaces["sym"] == emoji_util.EMOJI_FONT
    assert shapes.emoji_util is emoji_util


# DARES


def test_a_dare_is_a_challenge_for_the_presenter_or_something_for_the_whole_audience():
    dutch = languages.language("nl")
    challenge = KINDS["dare"].build({"dare": "Spreek vanaf nu met een piratenaccent.", "audience": None}, {}, dutch)
    everyone = KINDS["dare"].build(
        {"dare": None, "audience": "Steek je hand op als je ooit een pinguïn zag."}, {}, dutch
    )
    assert challenge.to_deck_slide().element("kicker").text == "Uitdaging"
    assert everyone.to_deck_slide().element("kicker").text == "Publieksparticipatie"
    assert all(language.audience for language in languages.LANGUAGES.values())
    with pytest.raises(ValueError):
        KINDS["dare"].build({"dare": None, "audience": None}, {}, dutch)


def test_the_language_models_dares_are_challenges_audience_dares_and_now_and_then_a_dad_joke():
    recipe = slide_schemas.slide_generators.get("Dare").llm
    by_kind = {
        "audience": [variant for variant in recipe.variants if "dare" in variant.omit],
        "presenter": [variant for variant in recipe.variants if "audience" in variant.omit],
    }
    weight = sum(variant.weight for variant in recipe.variants)
    assert sum(variant.weight for variant in by_kind["audience"]) / weight == pytest.approx(0.4)
    jokes = [variant for variant in recipe.variants if variant.facts]
    assert len(jokes) == 1 and jokes[0] in by_kind["presenter"]  # (the only one that may build on a dad joke)
    assert sum(variant.weight for variant in jokes) / weight == pytest.approx(0.2)
    pick = slide_schemas.slide_generators.get("Dare")
    for variant in recipe.variants:  # (a slide of a variant that takes no fact gets none, in a talk's request)
        chosen = dataclasses.replace(recipe, variants=(variant,)).varied(random_util.Rng(1))
        assert (presentation_schema._fact_use(pick, chosen) is not None) == variant.facts


def test_the_classic_dares_are_real_challenges_or_the_audiences(related):
    ted = packs.pack(packs.TED)
    assert len(ted.rule("karaoke.dare")) >= 40 and len(ted.rule("karaoke.audience_dare")) >= 30
    assert not any("next slide as" in dare and "haiku" not in dare for dare in ted.rule("karaoke.dare"))
    made = {"Challenge": 0, "Audience participation": 0}
    for seed in range(30):
        with random_util.use(random_util.Rng(seed)):
            heading, dare = slide_texts.generate_dare({"seed": "cat", "topic": "cats"})
        made[heading] += 1
        assert len(dare) <= 130
    assert made["Audience participation"] >= 6 and made["Challenge"] >= 6


# CLOSING SLIDES


def _picture(name, query, description=None):
    picture = _image(name).found_with(query)
    picture.description = description
    return picture


def test_a_closing_slide_calls_back_to_the_earlier_picture_it_names(images):
    penguin, kitten = _picture("wide", "a penguin on an iceberg"), _picture("tall", "a sleepy kitten")
    template = _picture("square", "Drake Hotline Bling")
    made = [
        slides.TitleSlide("Penguins", "By me"),
        slides.ImageSlide("Look", penguin),
        slides.MemeSlide(template, "Ice", "More ice"),
        slides.ImageSlide("And this", kitten),
        slides.QuestionsSlide("Questions?", "Remember the penguin?", callback="the penguin on the iceberg"),
    ]
    made[1].add_source("Test", "https://example.com/wide")
    deck = SlideDeck(len(made), title="Penguins", topics=["penguins"], seed=1)
    for index, slide in enumerate(made):
        deck.add_slide(index, slide)
    closing = made[-1]
    assert closing.to_slide_dictionary()["photo"] is penguin
    assert closing.to_deck_slide().element("photo") is not None and closing.to_deck_slide().credits


def test_a_closing_slide_that_names_no_picture_calls_back_to_the_dices_and_never_to_a_meme(images):
    pictures = [_picture("wide", "one"), _picture("tall", "two")]
    meme = slides.MemeSlide(_picture("square", "Drake Hotline Bling"), "A", "B")
    for pick, expected in ((0.1, pictures[0]), (0.9, pictures[1])):
        closing = slides.QuestionsSlide("?", callback="", pick=pick)
        assert closing.call_back([slides.ImageSlide("A", pictures[0]), meme, slides.ImageSlide("B", pictures[1])])
        assert closing.to_slide_dictionary()["photo"] is expected
    lonely = slides.QuestionsSlide("?", "Remember this one?", callback="", line_needs_picture=True)
    assert lonely.call_back([meme]) is None and lonely.to_slide_dictionary()["subtitle"] is None
    plain = slides.QuestionsSlide("?", "Answers not guaranteed")  # (no callback: nothing changes)
    assert plain.call_back([slides.ImageSlide("A", pictures[0])]) is None


@pytest.mark.parametrize("family", ["clean keynote", "kids", "hacker terminal", "chalkboard", "Swiss poster"])
def test_a_closing_slide_with_a_picture_is_laid_out_around_it(images, family):
    for seed in range(4):
        closing = slides.QuestionsSlide("Questions?", "Remember this one?", _image("wide"))
        deck = _deck([closing], _theme(family, seed), seed)
        slide = deck.slides[0]
        assert slide.layout in ("v5/questions-photo", "v5/questions-banner")
        photo = slide.element("photo")
        assert isinstance(photo, ImageElement) and photo.box is not None
        assert [finding for finding in check_deck(deck) if finding.severity == "error"] == [], (family, seed)
    plain = _deck([slides.QuestionsSlide("Questions?")], _theme(family))
    assert plain.slides[0].layout in ("v5/questions", "v5/questions-mark")


def test_every_closing_slide_ends_on_a_picture_a_last_tip_or_a_callback():
    # (D76: a talk of talkgenerator's own ends on its closer instead, so the formats have no "Questions?" anymore, and the
    # TED-like one is a plan's recipe alone, which no talk picks; nor have D79's formats: a book report's closer says
    # "The End")
    for schema in (academic, corporate, pitch, infomercial, documentary, court, museum, wedding, book_report):
        assert not [generator for generator in schema.GENERATORS if generator.llm and generator.llm.kind == "questions"]
    generators = slide_schemas.slide_generators.group("structure")
    recipes = [
        generator.llm for generator in generators if generator.llm is not None and generator.llm.kind == "questions"
    ]
    assert recipes
    questions = [
        generator for generator in generators if generator.llm is not None and generator.llm.kind == "questions"
    ]
    assert all(generator.get_weight_for(slide_nr, 10) == 0 for generator in questions for slide_nr in range(10))
    for recipe in recipes:
        assert len(recipe.images) == 1 and recipe.slots()[0][0] == "photo"
        notes = [variant.note for variant in recipe.variants]
        assert len(recipe.variants) == 3 and len({variant.weight for variant in recipe.variants}) == 1
        assert any("picture to end" in note for note in notes) and any("calling back" in note for note in notes)
        hints = [variant.hints.get("subtitle") for variant in recipe.variants]
        assert LAST_TIP in hints and CALLBACK_LINE in hints
        callback = next(variant for variant in recipe.variants if "calling back" in variant.note)
        assert "photo" in callback.omit and not callback.facts  # (no search: the deck gives it an earlier picture)


def test_the_classic_closing_slides_end_on_a_picture_a_callback_or_a_last_tip(images, related):
    generate = slide_texts.questions(lambda context: _image("wide"))
    ways = {"picture": 0, "callback": 0, "tip": 0}
    tips = packs.pack(packs.TED).rule("structure.last_tip")
    for seed in range(45):
        with random_util.use(random_util.Rng(seed)):
            made = generate({"seed": "cat", "topic": "cats"})
        closing = slides.QuestionsSlide(*made)
        if made[2:3] and made[2] is not None:
            ways["picture"] += 1
        elif closing.callback is not None:
            ways["callback"] += 1
            assert made[1] in packs.pack(packs.TED).rule("structure.callback_line")
        else:
            ways["tip"] += 1
    assert all(9 <= count <= 21 for count in ways.values()), ways
    assert len(tips) >= 15


# REFERENCES


def test_references_list_their_works_and_show_a_picture_of_one(images):
    works = "Brew et al. (2022). J. Coffee | Bean (2019). Proc. Roast | Mug et al. (2001). Cups"
    made = KINDS["references"].build(
        {"title": "References", "items": works, "caption": "Cover of [2]"},
        {"figure": _image("tall")},
        languages.ENGLISH,
    )
    slide = made.to_deck_slide()
    assert [slide.element(f"number_{index}").text for index in (1, 2, 3)] == ["[1]", "[2]", "[3]"]
    assert slide.element("caption").text == "Cover of [2]" and isinstance(slide.element("figure"), ImageElement)
    clicks = {element.role: element.appears_on_click for element in slide.elements}
    assert [clicks["item_1"], clicks["item_2"], clicks["item_3"]] == [1, 2, 3] and clicks["figure"] == 4
    for family in ("clean keynote", "academic", "chalkboard", "blueprint"):
        deck = _deck([made], _theme(family))
        placed = deck.slides[0]
        assert placed.layout in ("v5/references", "v5/references-left")
        figure, caption = placed.element("figure"), placed.element("caption")
        assert figure.box.y + figure.box.h <= caption.box.y  # (the caption under it)
        assert [finding for finding in check_deck(deck) if finding.severity == "error"] == [], family
    bare = KINDS["references"].build({"title": "References", "items": works, "caption": None}, {}, languages.ENGLISH)
    assert bare.to_deck_slide().element("figure") is None
    with pytest.raises(ValueError):
        KINDS["references"].build({"title": "References", "items": "One | Two", "caption": None}, {}, languages.ENGLISH)


def test_an_academic_talks_references_show_a_cover_or_a_figure_most_of_the_time(images):
    for rule in ("references.cover_caption", "references.figure_caption"):
        content = academic._references(lambda context: _image("tall"), rule)
        pictured = 0
        for seed in range(40):
            with random_util.use(random_util.Rng(seed)):
                texts, pictures = content({"seed": "coffee", "topic": "coffee"})
            if pictures:
                pictured += 1
                assert re.search(r"\[\d\]", texts["caption"]) and len(texts["caption"]) <= 30
            else:
                assert "caption" not in texts
        assert 24 <= pictured <= 38, (rule, pictured)  # (four times in five)
        nothing = academic._references(lambda context: None, rule)  # (a picture that can't be found: the list alone)
        with random_util.use(random_util.Rng(1)):
            assert nothing({"seed": "coffee", "topic": "coffee"})[1] == {}
    recipes = {
        generator.name: generator.llm
        for generator in academic.GENERATORS
        if generator.llm is not None and generator.llm.kind == "references"
    }
    looks = {name: recipe.slots()[0][1].aesthetic for name, recipe in recipes.items()}
    assert looks == {"References (Academic)": "book-covers", "References Figure (Academic)": "bad-charts"}
    for recipe in recipes.values():
        assert [variant.weight for variant in recipe.variants] == [4, 1]
        assert recipe.variants[1].omit == {"figure", "caption"}  # (the list alone)
