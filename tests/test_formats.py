"""Offline tests of the talk formats beyond TED-like talks (docs/v5-plan.md, section 7; decisions D56 and D59): the
startup pitch, the academic conference talk, the corporate all-hands and the product keynote
(talkgenerator.schema.formats).

A format's talks go through its arc, the same for every persona, classic or planned; a short talk keeps its most
important parts and a long one gets free slides between them. Its classic slides come from its content pack, its
requests tell the language model what the format is, its favourite personas present it more often and its themes come
up more often. And the process, the slide type an academic talk's method brought, draws in every theme.
"""

from __future__ import annotations

import collections
import io
import json
import zlib

import pytest
from PIL import Image, ImageDraw

from talkgenerator import generator, personas
from talkgenerator.checks.deck import check_arc, check_completeness, check_deck, check_leftovers
from talkgenerator.checks.design import check_design
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine, themes
from talkgenerator.images import context as image_context
from talkgenerator.images import finder, licenses
from talkgenerator.llm.base import Capabilities, TextProvider, TextResponse
from talkgenerator.models import classic
from talkgenerator.plan import external, prompt, realize
from talkgenerator.plan.kinds import KINDS
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import formats, presentation_schema, presentation_schema_types
from talkgenerator.schema.formats import (
    academic,
    book_report,
    corporate,
    court,
    documentary,
    infomercial,
    keynote,
    museum,
    pitch,
    wedding,
)
from talkgenerator.schema.formats.arcs import PART_WEIGHT, STAND_IN, Arc, Free, InPart, Part
from talkgenerator.schema.presentation_schema_types import get_schema, schemas
from talkgenerator.slide import slides
from talkgenerator.sources import conceptnet
from talkgenerator.util import image_util, random_util
from tests.test_slide_types import _clicks, _deck, _longest, _theme

FORMATS = {
    "pitch": pitch,
    "academic": academic,
    "corporate": corporate,
    "keynote": keynote,
    # (D79)
    "infomercial": infomercial,
    "documentary": documentary,
    "court": court,
    "museum": museum,
    "wedding": wedding,
    "book_report": book_report,
}
FAMILIES = list(themes.FAMILIES)


def _format(name):
    """A format's Format, by its module's constant of the format's name in capitals (PITCH, BOOK_REPORT)."""
    return FORMATS[name].__dict__[name.upper()]


def _part_of(generator_data, arc):
    """The part of the arc a slide generator makes slides of (None for the format's other slides)."""
    return next((tag for tag in generator_data.get_tags() if tag in arc.names()), None)


# THE ARCS


@pytest.mark.parametrize("name", FORMATS)
def test_an_arc_lays_out_talks_of_every_length(name):
    arc = FORMATS[name].ARC
    ranked = sorted(arc.parts, key=lambda part: part.rank)
    for num_slides in range(1, 31):
        layout = arc.layout(num_slides)
        assert len(layout) == num_slides and layout[0] is None
        kept = arc.kept(num_slides)
        # The parts it keeps: the lowest ranks of those it's long enough for (D63's parts of text wait for long talks:
        # Part.shortest), in the arc's order, each with as many slides as it takes, in the room that the slides its
        # free share keeps free leave
        reserved = arc.reserved(num_slides)
        eligible = [part for part in ranked if num_slides >= part.shortest]
        assert set(kept) == {part.name for part in eligible[: min(len(eligible), num_slides - 1 - reserved)]}
        assert list(kept) == [part for part in arc.names() if part in kept]
        counts = collections.Counter(part for part in layout if part is not None)
        assert all(part.fewest <= counts[part.name] <= part.most for part in arc.parts if part.name in kept)
        # Free slides: those its free share keeps, and more only once every part it's long enough for has its most
        # slides; between parts (none after the last)
        free = arc.free_slides(num_slides)
        assert free >= reserved and (free == reserved or all(counts[part.name] == part.most for part in eligible))
        if free and len(kept) > 1:
            assert layout[1] is not None and layout[-1] is not None
        runs = [part for index, part in enumerate(layout[1:], 1) if part is not None and part != layout[index - 1]]
        assert runs == list(kept)  # (each part's slides one after the other)


def test_ten_and_five_slide_talks_have_the_arcs_the_formats_promise():
    # (D63: two free slides of ten, for memes, gifs and pictures; a pitch's market and business model and an academic
    # talk's outline and acknowledgements wait for longer talks. D76: no closing "Questions?" among them, as the closer
    # after the talk's last slide asks for them: the roadmap has its slide)
    assert pitch.ARC.layout(10) == (
        None,
        "problem",
        "solution",
        None,
        "traction",
        "competition",
        "team",
        None,
        "roadmap",
        "ask",
    )
    assert pitch.ARC.kept(5) == ("problem", "solution", "traction", "ask")
    assert pitch.ARC.kept(12) == (
        "problem",
        "solution",
        "market",
        "business_model",
        "traction",
        "competition",
        "team",
        "roadmap",
        "ask",
    )
    assert "market" not in pitch.ARC.kept(10) and "business_model" not in pitch.ARC.kept(11)
    # (D69: an academic talk's motivation first, its why; D76: its future work where "Questions?" was)
    assert academic.ARC.layout(10) == (
        None,
        "motivation",
        "related_work",
        None,
        "method",
        "results",
        "limitations",
        None,
        "future_work",
        "references",
    )
    assert academic.ARC.kept(5) == ("motivation", "method", "results", "limitations")
    assert "outline" in academic.ARC.kept(12) and "acknowledgements" in academic.ARC.kept(13)
    assert "outline" not in academic.ARC.kept(11) and "acknowledgements" not in academic.ARC.kept(12)


def test_an_all_hands_and_a_keynote_have_the_arcs_they_promise():
    # (D59: an all-hands goes from its agenda to the ask, its KPIs two slides in longer talks, and its closer opens Q&A
    # (D76); a keynote from its opening to its closing line. D63: two free slides of ten in an all-hands, whose agenda
    # waits for longer talks, and one in a keynote)
    assert corporate.ARC.layout(10) == (
        None,
        "kpis",
        "kpis",
        "wins",
        None,
        "roadmap",
        "org_change",
        None,
        "synergies",
        "ask",
    )
    assert corporate.ARC.kept(5) == ("kpis", "wins", "roadmap", "org_change")
    assert "agenda" not in corporate.ARC.kept(10)
    assert corporate.ARC.layout(12).count("kpis") == 2 and corporate.ARC.kept(12)[0] == "agenda"
    assert keynote.ARC.layout(10) == (
        None,
        "opening",
        "idea",
        "reveal",
        "features",
        None,
        "demo",
        "price",
        "one_more_thing",
        "closing",
    )
    assert keynote.ARC.kept(5) == ("opening", "reveal", "features", "one_more_thing")
    assert keynote.ARC.kept(3) == ("reveal", "one_more_thing")  # (the reveal and one more thing stay longest)


def test_a_long_talk_gives_its_parts_more_slides_and_then_free_ones():
    layout = pitch.ARC.layout(20)
    counts = collections.Counter(layout[1:])
    assert counts["problem"] == counts["solution"] == counts["traction"] == 2 and counts["roadmap"] == 1
    assert counts[None] == pitch.ARC.free_slides(20) == 19 - 12
    assert academic.ARC.layout(20).count("results") == 3 and academic.ARC.layout(20).count("method") == 2


def test_a_part_of_text_waits_for_a_talk_long_enough_for_it():
    # (D63's parts of text, kept waiting by D76: whatever its rank, such a part waits, and its room goes to the others)
    arc = Arc((Part("list", rank=0, shortest=6), Part("chart", 1, 2, rank=1), Part("end", rank=2)))
    assert arc.kept(5) == ("chart", "end") and arc.layout(5) == (None, "chart", "chart", None, "end")
    assert arc.kept(6) == ("list", "chart", "end")


def test_an_arc_keeps_its_free_share_of_a_talk_free():
    # (D63: a quarter of a ten-slide talk's slides but its first and its last, rounded down)
    arc = Arc((Part("first", 1, 3, rank=1), Part("last", rank=0)), free=0.25)
    assert [arc.reserved(num_slides) for num_slides in (2, 5, 6, 10, 14, 30)] == [0, 0, 1, 2, 3, 7]
    assert arc.layout(10).count(None) == 1 + 2 + (9 - 2 - 4)  # (the title, the free share, and what's left)
    assert Arc((Part("only"),)).reserved(30) == 0
    for share in (-0.1, 1):
        with pytest.raises(ValueError):
            Arc((Part("only"),), free=share)


def test_a_parts_slide_generators_weigh_in_on_its_slides_and_the_others_on_the_free_ones():
    arc = Arc((Part("first", rank=1), Part("last", rank=0)))
    assert arc.layout(5) == (None, "first", None, None, "last")
    in_first, free = InPart(arc, "first", 2), Free(arc, 3)
    assert [in_first(slide_nr, 5) for slide_nr in range(5)] == [0, 2 * PART_WEIGHT, 0, 0, 0]
    assert [free(slide_nr, 5) for slide_nr in range(5)] == [
        0,
        3 * STAND_IN,
        3 * PART_WEIGHT,
        3 * PART_WEIGHT,
        3 * STAND_IN,
    ]
    with pytest.raises(ValueError):
        InPart(arc, "middle")
    with pytest.raises(ValueError):
        Arc((Part("twice"), Part("twice")))


# PERSONAS AND THEMES


@pytest.mark.parametrize("name", FORMATS)
def test_every_persona_keeps_the_formats_arc(name):
    schema, arc = get_schema(name), FORMATS[name].ARC
    for persona in (None, *personas.PERSONAS.values()):
        for num_slides in (5, 10, 15):
            for seed in range(12):
                picks = schema._pick_generators(num_slides, random_util.Rng(seed), "en", persona)
                assert picks[0] is not None and "title" in picks[0].get_tags()
                parts = [_part_of(pick, arc) if pick is not None else "?" for pick in picks[1:]]
                assert parts == list(arc.layout(num_slides)[1:]), (persona, num_slides, seed)


@pytest.mark.parametrize("name", FORMATS)
def test_a_formats_arc_needs_no_image_that_is_fair_use(name):
    # (so a talk with the open license policy keeps every part: only the format's other slides may go, its memes)
    schema, arc = get_schema(name), FORMATS[name].ARC
    with image_context.for_talk(image_context.ImageContext(licenses.policy("open"))):
        unservable = schema.unservable()
    assert unservable and [maker.name for maker in unservable if _part_of(maker, arc) is not None] == []
    for policy in ("open", "all"):
        for num_slides in (5, 10, 20, 30):
            for seed in range(4):
                with image_context.for_talk(image_context.ImageContext(licenses.policy(policy))):
                    picks = schema._pick_generators(num_slides, random_util.Rng(seed), "en", None)
                parts = [_part_of(pick, arc) if pick is not None else "?" for pick in picks[1:]]
                assert parts == list(arc.layout(num_slides)[1:]), (policy, num_slides, seed)


def test_a_persona_still_moves_a_parts_slides_between_its_kinds():
    schema = get_schema("pitch")

    def kpis(persona):  # (in twelve-slide pitches, which have their business model: D63)
        return sum(
            "kpi" in pick.get_tags()
            for seed in range(200)
            for pick in schema._pick_generators(12, random_util.Rng(seed), "en", persona)
            if pick is not None
        )

    assert kpis(personas.persona("startup_founder")) > 1.25 * kpis(None)  # (one a talk at most, by its cap)
    assert kpis(personas.persona("medieval_historian")) < kpis(None)


def test_a_formats_favourite_personas_present_it_more_often():
    def shares(weights):
        picked = collections.Counter(
            personas.pick(None, random_util.Rng(seed), weights).name
            for seed in range(1300)  # type: ignore[union-attr]
        )
        return {name: count / 1300 for name, count in picked.items()}

    plain, pitches, talks = shares(None), shares(pitch.PITCH.personas), shares(academic.ACADEMIC.personas)
    assert pitches["startup_founder"] > 0.24 > 2.5 * plain["startup_founder"]
    assert talks["disgraced_professor"] > 0.24 > 2.5 * plain["disgraced_professor"]
    assert all(talks.get(name, 0) > 0 for name in personas.PERSONAS)  # (every persona still presents some)
    all_hands, keynotes = shares(corporate.CORPORATE.personas), shares(keynote.KEYNOTE.personas)
    assert all_hands["consultant"] > 0.24 > 2.5 * plain["consultant"]
    assert keynotes["startup_founder"] > 0.2 and keynotes["motivational_speaker"] > 1.5 * plain["motivational_speaker"]
    assert all(all_hands.get(name, 0) > 0 and keynotes.get(name, 0) > 0 for name in personas.PERSONAS)
    # A TED-like talk's persona is the one its seed picked before
    for seed in range(50):
        assert personas.pick(None, random_util.Rng(seed), None) == personas.pick(None, random_util.Rng(seed), {})
    assert personas.pick("none", random_util.Rng(1), pitch.PITCH.personas) is None


# (D79: a newer format's specialist presents about 30% of its talks, as a pitch's founder does; the book report, which
# has no specialist, is the kindergarten teacher's more often)
NEWER_FAVOURITES = {
    "infomercial": "infomercial_host",
    "documentary": "nature_narrator",
    "court": "detective",
    "museum": "museum_guide",
    "wedding": "best_man",
    "book_report": "kindergarten_teacher",
}


@pytest.mark.parametrize("name", NEWER_FAVOURITES)
def test_a_newer_formats_favourite_persona_presents_it_more_often(name):
    picked = collections.Counter(
        personas.pick(None, random_util.Rng(seed), _format(name).personas).name  # type: ignore[union-attr]
        for seed in range(1300)
    )
    share = picked[NEWER_FAVOURITES[name]] / 1300
    assert share > 2.5 / len(personas.PERSONAS), (name, share)  # (two and a half times its share without)
    if name != "book_report":
        assert share > 0.24, (name, share)
    assert all(picked.get(other, 0) > 0 for other in personas.PERSONAS), name  # (every persona still presents some)


def test_a_formats_talks_are_in_its_favourite_theme_families_more_often():
    def share(family, multipliers):
        picked = [themes.pick("random", random_util.Rng(seed).child("theme"), True, multipliers) for seed in range(800)]
        return sum(theme is not None and theme.family == family for theme in picked) / len(picked)

    assert share("startup", pitch.PITCH.themes) > 2.5 * share("startup", None)
    assert share("academic", academic.ACADEMIC.themes) > 2.5 * share("academic", None)
    assert share("corporate", corporate.CORPORATE.themes) > 2.5 * share("corporate", None)
    assert share("dark minimal", keynote.KEYNOTE.themes) > 2.5 * share("dark minimal", None)
    founder = personas.persona("startup_founder").themes
    assert (
        formats.multiplied(founder, pitch.PITCH.themes)["startup"] == founder["startup"] * pitch.PITCH.themes["startup"]
    )
    assert formats.multiplied(None, None) is None and formats.multiplied(founder, None) == dict(founder)


# MADE-UP NAMES


def test_a_pitch_s_startup_and_a_talk_s_method_are_named_after_the_topic():
    assert formats.startup("penguins") == formats.startup("penguins") and "Penguin" in formats.startup("penguins")
    assert "Penguins" not in formats.startup("penguins")  # (one of it)
    assert "TimeTravel" in formats.startup("time travel") and "Intelligence" in formats.method(
        "artificial intelligence"
    )
    names = {formats.startup(topic) for topic in ("cat", "coffee", "the moon", "Belgium", "socks", "jazz", "bread")}
    assert len(names) > 3  # (topics get startups of several kinds)
    for topic in ("conference interpreters", "a plant that won't die", "the French Revolution", "x", ""):
        assert 0 < len(formats.startup(topic)) <= 21 and 0 < len(formats.method(topic)) <= 22
        # (no longer than the pack lint's longest company and product: see tests/test_content_pack.LONG)
        assert 0 < len(formats.company(topic)) <= 25 and 0 < len(formats.product(topic)) <= 23


def test_an_all_hands_company_and_a_keynotes_product_are_named_after_the_topic():
    assert formats.company("penguins") == formats.company("penguins") and "Penguin" in formats.company("penguins")
    assert "Penguin" in formats.product("penguins") and "Penguins" not in formats.product("penguins")
    topics = ("cat", "coffee", "the moon", "Belgium", "socks", "jazz", "bread", "penguins")
    assert len({formats.company(topic).replace(formats._name_word(topic), "") for topic in topics}) > 3
    assert len({formats.product(topic).replace(formats._name_word(topic), "") for topic in topics}) > 3


# (and those of D79's formats: each at most as long as the pack lint's longest, tests/test_content_pack.LONG)
NAMERS = {
    "gadget": (formats.gadget, 24),
    "species": (formats.species, 29),
    "museum": (formats.museum_name, 33),
    "artist": (formats.artist, 29),
    "friend": (formats.friend, 7),
    "book": (formats.book, 28),
    "author": (formats.author, 21),
    "crime": (formats.crime, 34),
}


@pytest.mark.parametrize("variable", NAMERS)
def test_the_newer_formats_made_up_names_come_from_the_topic(variable):
    namer, longest = NAMERS[variable]
    topics = ("cat", "coffee", "the moon", "Belgium", "socks", "jazz", "bread", "penguins", "time travel")
    assert namer("penguins") == namer("penguins")  # (the same on every slide, and in every run)
    assert len({namer(topic) for topic in topics}) > 3
    for topic in ("conference interpreters", "a plant that won't die", "the French Revolution", "x", "", *topics):
        assert 0 < len(namer(topic)) <= longest, (topic, namer(topic))
    if variable not in ("friend", "author", "crime"):  # (a name or a crime of its own; the others name the topic)
        assert "enguin" in namer("penguins") and "Penguins" not in namer("penguins")


def test_a_documentarys_species_is_latin_ish():
    assert formats.species("penguins").split()[0] == "Penguinus"
    assert formats.species("coffee").split()[0] == "Coffeus" and formats.species("a bunny").split()[0] == "Bunnius"
    assert formats.species("Belgium").split()[0] == "Belgium"
    assert formats.species("time travel").split()[0] == "Timetravelus"
    assert all(formats.species(topic).split()[1].islower() for topic in ("cat", "coffee", "jazz"))


# CLASSIC SLIDES AND TALKS, OFFLINE


def _picture(url: str) -> bytes:
    """A JPEG of its own for an address: light blocks on blue, in an arrangement of its own (by the address's hash)."""
    picture = Image.new("RGB", (400, 300), (30, 120, 200))
    draw = ImageDraw.Draw(picture)
    bits = zlib.crc32(url.encode("utf-8"))
    for block in range(16):
        if bits >> block & 1:
            x, y = block % 4 * 100, block // 4 * 75
            draw.rectangle((x, y, x + 99, y + 74), fill=(235, 235, 235))
    output = io.BytesIO()
    picture.save(output, "JPEG")
    return output.getvalue()


@pytest.fixture
def offline(monkeypatch):
    """Talks without the internet: images found and served from example.com (each search finds others than those to
    avoid, and each looks like no other: one picture for all would be a near-duplicate of every other, which a slide
    may not repeat), and the same related words for any word."""

    def find(slot, query, avoid=()):
        # (one of a search's pictures, as the slide's dice pick it, as the finder does: a slide that tries again, as
        # its first try repeated a picture the talk has, may find another)
        first = random_util.randint(0, 9)
        for number in range(first, first + 20):
            image = ImageData(
                f"https://example.com/{slot.aesthetic}-{query}-{number}.jpg".replace(" ", "-"),
                source="Test",
                source_url="https://example.com/",
            )
            if image not in avoid:
                return image
        return None

    fetch = image_util.fetch_image
    monkeypatch.setattr(finder, "find", find)
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: _picture(url) if url.startswith("https://example.com/") else fetch(url)
    )
    monkeypatch.setattr(image_util, "probe", lambda url: url.startswith("https://example.com/"))
    words = [(1.0, "feather"), (0.9, "ice"), (0.8, "fish"), (0.7, "snow"), (0.6, "beak"), (0.5, "colony")]
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: list(words))


def _context(seed="penguin"):
    return {"seed": seed, "topic": "penguins", "presenter": "Ann Wells", "title": "Penguinly: Penguins on Demand"}


@pytest.mark.parametrize("name", FORMATS)
def test_every_parts_slide_generator_makes_complete_classic_slides(offline, name):
    module = FORMATS[name]
    makers = [maker for maker in module.GENERATORS if _part_of(maker, module.ARC) is not None]
    assert {_part_of(maker, module.ARC) for maker in makers} == set(module.ARC.names())
    for maker in makers:
        for seed in range(6):
            with random_util.use(random_util.Rng(seed)):
                made = maker.generate(_context(("penguin", "coffee", "the moon")[seed % 3]), set())
            assert made is not None, (maker.name, seed)
            slide, _ = made
            deck = _deck([slide])
            assert [finding for finding in check_completeness(deck) if finding.severity == "error"] == [], maker.name
            assert check_leftovers(deck) == [], maker.name


def _talk(name, seed=1, parallel=True, llm="none", **options):
    _, slide_deck, _ = generator._generate_presentation(
        schema=name, slides=10, topic="penguins", int_seed=seed, parallel=parallel, save_ppt=False, llm=llm, **options
    )
    return slide_deck.to_deck()  # (with the format its seed picked, for schema random)


@pytest.mark.parametrize("name", FORMATS)
def test_a_classic_talk_of_each_format_follows_its_arc_and_passes_the_checks(offline, name):
    for seed in (1, 2, 3):
        deck = _talk(name, seed, theme="random")
        assert deck.counted() == 10 and deck.schema_name == name
        assert [finding for finding in check_deck(deck, 10) if finding.severity == "error"] == [], seed
        assert check_arc(deck, 10) == []
    assert _talk(name, 4, parallel=True).to_json() == _talk(name, 4, parallel=False).to_json()


def test_a_talk_that_leaves_its_format_to_its_seed_is_the_talk_of_the_format_it_picked(offline):
    # (decision D61: the seed's format stream moves nothing else, so with the persona it names, a talk of schema random
    # is the talk of the format its seed picked)
    founder = personas.persona("startup_founder")
    picked = set()
    for seed in (1, 9, 83, 5):  # (a pitch, a TED-like talk, a keynote and a court case, as it happens: D79's odds)
        deck = _talk(presentation_schema_types.RANDOM, seed, persona="startup_founder", theme="random")
        assert deck.schema_name == presentation_schema_types.pick_format("random", random_util.Rng(seed), founder)
        assert deck.to_json() == _talk(deck.schema_name, seed, persona="startup_founder", theme="random").to_json()
        assert [finding for finding in check_deck(deck, 10) if finding.severity == "error"] == [], seed
        if deck.schema_name in FORMATS:
            assert check_arc(deck, 10) == []
        picked.add(deck.schema_name)
    assert picked == {"pitch", "default", "keynote", "court"}


def test_a_classic_pitch_names_its_startup_and_an_academic_talk_its_affiliation(offline):
    deck = _talk("pitch", 5, persona="none")
    texts = " ".join(element.text for slide in deck.slides for element in slide.elements if hasattr(element, "text"))
    assert formats.startup("penguins") in texts
    talk = _talk("academic", 5, persona="none")
    subtitle = talk.slides[0].element("subtitle")
    assert subtitle is not None and talk.presenter in subtitle.text  # type: ignore[union-attr, operator]


def _texts(deck):
    return " ".join(element.text for slide in deck.slides for element in slide.elements if hasattr(element, "text"))


def test_a_classic_all_hands_names_its_company_and_a_keynote_its_product(offline):
    assert formats.company("penguins") in _texts(_talk("corporate", 5, persona="none"))
    assert formats.product("penguins") in _texts(_talk("keynote", 5, persona="none"))


# PLANNED TALKS


def _plausible(schema):
    """An answer to a talk request with a plausible text in every field: a field's first option, several things
    separated by | where a slide lists them, and else the field's name and the slide's number."""
    answer = {}
    for key, value in schema["properties"].items():
        if value["type"] == "boolean":
            answer[key] = False
        elif value["type"] == "string":
            answer[key] = "Ann Wells" if key == "presenter_name" else f"The {key.replace('_', ' ')}"
        elif key == prompt.SPINE:
            answer[key] = _plausible(value)
        else:
            number = key.rsplit("_", 1)[-1]
            slide = {}
            for name, field in value["properties"].items():
                if "enum" in field:
                    slide[name] = next(option for option in field["enum"] if option)
                elif name in ("bars", "categories", "items", "buttons"):
                    slide[name] = "Alpha | Beta | Gamma | Delta"
                elif name == "points":  # (a wall of text's: five points or more)
                    slide[name] = " | ".join(f"Point {letter} of the plan, said at length" for letter in "ABCDEFG")
                elif name.startswith("number"):
                    slide[name] = f"{number}%"
                else:
                    slide[name] = f"{name.replace('_', ' ').capitalize()} {number}"
            answer[key] = slide
    return answer


class PlausibleModel(TextProvider):
    id = "fake:plausible"
    capabilities = Capabilities(structured_output=True, streaming=True)

    def __init__(self):
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        return TextResponse(text=json.dumps(_plausible(request.json_schema)), model=self.id, output_tokens=300)

    def stream(self, request, on_text):
        response = self.complete(request)
        on_text(response.text)
        return response


@pytest.mark.parametrize("name", FORMATS)
def test_a_planned_talk_of_each_format_follows_its_arc_as_the_model_wrote_it(offline, name):
    model = PlausibleModel()
    favourites = FORMATS[name].__dict__[name.upper()].personas  # (its favourite persona presents it)
    deck = _talk(name, 2, llm=model, persona=max(favourites, key=favourites.get))
    planned = sum(1 for slide in deck.slides if "Planned:" in slide.notes)
    assert planned >= 8, [slide.notes.splitlines()[:2] for slide in deck.slides]
    assert [finding for finding in check_deck(deck, 10) if finding.severity == "error"] == []
    assert check_arc(deck, 10) == []
    request = model.requests[0].messages[0].content
    assert f"The format: {FORMATS[name].__dict__[name.upper()].brief}" in request


def test_a_formats_request_tells_the_model_the_format_and_its_kinds_of_title_and_job():
    founder = personas.persona("startup_founder")
    request = prompt.talk_request(["penguins"], [], random_util.Rng(1), persona=founder, talk_format=pitch.PITCH)
    lines = request.messages[0].content.splitlines()
    assert f"The format: {pitch.PITCH.brief}" in lines
    assert lines.index(f"The format: {pitch.PITCH.brief}") < lines.index(f"The presenter: {founder.voice}")
    spine = request.json_schema["properties"][prompt.SPINE]["properties"]
    assert pitch.PITCH.title_hint in spine["title"]["description"]
    assert founder.title_hint in spine["title"]["description"]
    assert f"{founder.job_hint}, given as {pitch.PITCH.job_hint}" in spine["presenter_job"]["description"]
    # Without a persona, the format's hints alone; with a title of its own, no title hint
    alone = prompt.talk_request(["penguins"], [], random_util.Rng(1), talk_format=academic.ACADEMIC)
    alone_spine = alone.json_schema["properties"][prompt.SPINE]["properties"]
    assert academic.ACADEMIC.title_hint in alone_spine["title"]["description"]
    assert academic.ACADEMIC.job_hint in alone_spine["presenter_job"]["description"]
    titled = prompt.talk_request(["penguins"], [], random_util.Rng(1), title="A Title", talk_format=pitch.PITCH)
    assert pitch.PITCH.title_hint not in titled.messages[0].content


def test_a_ted_like_talks_request_says_nothing_of_a_format():
    request = prompt.talk_request(["penguins"], [], random_util.Rng(1), persona=personas.persona("consultant"))
    assert "The format:" not in request.messages[0].content
    assert prompt.title_hint(None) is None and prompt.job_hint(None) is None
    assert get_schema("default").format is None and get_schema("ted").format is None


# WHAT THE FORMATS ARE, FOR PEOPLE AND AGENTS


def test_the_formats_are_listed_with_what_they_are_and_their_slides():
    assert set(FORMATS) <= set(schemas.names()) and set(FORMATS) <= set(external.FORMATS)
    for name, module in FORMATS.items():
        catalog = external.catalog(name)
        assert catalog["description"] == external.FORMATS[name]
        recipes = [recipe for kind in catalog["kinds"] for recipe in kind["recipes"]]
        assert catalog["arc"] == [
            {
                "part": part.name,
                "slides": [part.fewest, part.most],
                "recipes": sorted(recipe["id"] for recipe in recipes if part.name in recipe["tags"]),
            }
            for part in module.ARC.parts
        ]
        # Its own recipes are its kinds' defaults; it borrows a TED-like talk's only for a kind it has none of (its own
        # end in its name, with dashes: "-book-report")
        ending = "-" + name.replace("_", "-")
        own = {kind["kind"] for kind in catalog["kinds"] if any(r["id"].endswith(ending) for r in kind["recipes"])}
        for kind in catalog["kinds"]:
            default = next(recipe for recipe in kind["recipes"] if recipe["default"])
            assert default["id"].endswith(ending) == (kind["kind"] in own), (name, kind["kind"])
        assert catalog["titles"] == module.__dict__[name.upper()].title_hint
    assert "process" in {kind["kind"] for kind in external.catalog("academic")["kinds"]}
    assert "process" not in {kind["kind"] for kind in external.catalog("default")["kinds"]}
    assert "## The arc" in external.catalog_markdown("pitch") and "## The arc" not in external.catalog_markdown("ted")


# THE PROCESS SLIDE


def _process_texts(word="Expectation", steps=5):
    texts = {text.name: _longest(text, word) for text in KINDS["process"].texts}
    return {name: value for name, value in texts.items() if not name.startswith("step_") or int(name[-1]) <= steps}


def _process(texts):
    with random_util.use(random_util.Rng(1)):
        return KINDS["process"].build(texts, {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("family", FAMILIES)
def test_a_process_fits_and_reads_in_every_theme(family):
    made = [
        _process(_process_texts()),
        _process(_process_texts("Brandweerkazernedeur", 3)),
        slides.ProcessSlide("Method", "Collect cats", "Clean data", "???", "Profit"),
        slides.ProcessSlide(None, "A", "B", "C"),
    ]
    for seed in range(3):
        deck = _deck(made, _theme(family, seed), seed)
        assert check_design(deck) == [], (family, seed)


def test_a_process_goes_across_when_its_words_are_short_and_down_when_they_are_not():
    def fitting(*steps):
        return engine.layouts_for(slides.ProcessSlide("Method", *steps).to_deck_slide())

    assert fitting("Collect cats", "Clean data", "???", "Profit") == ["v5/process", "v5/process-across"]
    assert fitting("Brandweerkazernedeur", "B", "C") == ["v5/process", "v5/process-across"]
    assert fitting("Brandweerkazernedeur", "B", "C", "D") == ["v5/process"]
    assert fitting("Twelveletter", "B", "C", "D", "Thirteenlette") == ["v5/process"]


def test_a_process_s_steps_appear_one_by_one_with_their_boxes_and_arrows():
    slide = slides.ProcessSlide("Method", "Collect", "Clean", "???", "Profit")
    for theme in (_theme(), _theme("brutalist")):
        for laid_out in (_deck([slide], theme, seed) for seed in range(6)):
            shown = _clicks(render_pptx(laid_out).slides[0])
            assert len(shown) == 4
            assert {"step_1", "step 1 box"} <= set(shown[0]) or {"step_1", "step 1 band"} <= set(shown[0])
            assert {"step_4", "step 4 arrow"} <= set(shown[3])
    deck_slide = slide.to_deck_slide()
    assert [deck_slide.element(f"step_{index}").appears_on_click for index in range(1, 5)] == [1, 2, 3, 4]


def test_the_punchline_step_is_in_the_second_accent():
    theme = _theme()
    (laid_out,) = _deck([slides.ProcessSlide("M", "One", "Two", "Three")], theme).slides
    fills = [element.color for element in laid_out.elements if element.role.endswith((" box", " band"))]
    assert fills == [theme.palette.accent, theme.palette.accent, theme.palette.accent_2]


def test_a_classic_deck_and_the_previews_draw_a_process():
    slide = slides.ProcessSlide("Method", "Collect", "Clean", "???", "Profit")
    deck = _deck([slide])
    assert deck.slides[0].layout == "classic/process" and "process" in classic.DRAWN_TYPES
    assert len(render_pptx(deck).slides) == 1
    themed = _deck([slide], _theme("academic"))
    assert preview.contact_sheet(themed).width > 0


# WHAT THE LIVE RUNS NEEDED: CUTS THAT READ WHOLE, AND A PRESENTER NAMED ONCE


def test_a_cut_ends_after_a_comma_or_before_a_bracket_it_would_leave_open():
    # (free models' affiliations and roles, too long for their places: "Professor of Serenity Studies, Department")
    long = "Professor of Serenity Studies, Department of Calm, University of Tranquil Grounds"
    assert realize._cut(long, 50, "en") == "Professor of Serenity Studies, Department of Calm"
    assert realize._cut("Kaito Tanaka (Head of Temporal Planning)", 30, "en") == "Kaito Tanaka"
    assert (
        realize._cut("Fresh beans, roasted daily, delivered by drone to your door", 45, "en")
        == "Fresh beans, roasted daily"
    )
    # A clause's end still comes first, a closed bracket stays, and a comma that keeps too little gives way to words
    decorations = "Your plants are not decorations—they are coworkers who need feedback"
    assert realize._cut(decorations, 40, "en") == "Your plants are not decorations"
    assert realize._cut("Dr. Elara Myles (CTO) leads the whole team now", 30, "en") == "Dr. Elara Myles (CTO) leads…"
    assert (
        realize._cut("Penguins, the tuxedoed overlords of the frozen south", 40, "en")
        == "Penguins, the tuxedoed overlords…"
    )


def test_a_cut_at_a_comma_or_a_clause_leaves_no_bracket_open_either():
    # (a free model's initiative in an all-hands' 2×2 matrix, too long for its quadrant: "Arctic Expansion (High Impact")
    assert realize._cut("Arctic Expansion (High Impact, Low Urgency)", 30, "en") == "Arctic Expansion"
    assert realize._cut("Project Ice (phase two; maybe three) is next", 25, "en") == "Project Ice"
    # A closed bracket stays, and a bracket that would keep too little before it stays open
    assert realize._cut("Kaito Tanaka (CTO), the founder of everything here", 30, "en") == "Kaito Tanaka (CTO)"
    assert realize._cut("Q3 (the quarter we prefer not to discuss, at all)", 45, "en").startswith("Q3 (")


def test_a_title_slide_names_its_presenter_once():
    # (a free model wrote the presenter's name into their job: "By Dr. Chronos Vance, Dr. Chronos Vance, Founder...")
    _, texts = presentation_schema._title_slide(
        "Temporal Shift",
        "Dr. Chronos Vance",
        "Dr. Chronos Vance, Founder of Temporal Shift Inc.",
        None,
        random_util.Rng(1),
    )
    # (the job on the line under the name: D80)
    assert texts[1].count("Chronos Vance") == 1 and texts[1].endswith(
        "Dr. Chronos Vance\nFounder of Temporal Shift Inc."
    )
    _, plain = presentation_schema._title_slide("T", "Ann Wells", "Founder of Annly", None, random_util.Rng(1))
    assert plain[1].endswith("Ann Wells\nFounder of Annly")
    _, prefix = presentation_schema._title_slide("T", "Ann", "Annual Report Analyst", None, random_util.Rng(1))
    assert prefix[1].endswith("Ann\nAnnual Report Analyst")
    # (Claude Haiku wrote a title before the name: "By Harold Beanmore, Dr. Harold Beanmore, Chief Chrono-Roaster")
    _, titled = presentation_schema._title_slide(
        "T", "Harold Beanmore", "Dr. Harold Beanmore, Chief Chrono-Roaster", None, random_util.Rng(1)
    )
    assert titled[1].count("Beanmore") == 1 and titled[1].endswith("Harold Beanmore\nChief Chrono-Roaster")
    _, doctor = presentation_schema._title_slide(
        "T", "Dr. Arabica Bean", "Dr. of Temporal Aromatics", None, random_util.Rng(1)
    )
    assert doctor[1].endswith("Dr. Arabica Bean\nDr. of Temporal Aromatics")  # (a job that only starts with a title)


def test_the_arc_check_reads_a_rendered_plans_recipes_too():
    # (a talk's notes name the slide generator, "The Ask (Pitch)"; a rendered plan's its recipe, "the-ask-pitch")
    from talkgenerator.models.deck import Deck, DeckSlide

    def slide(maker):
        return DeckSlide(
            type="big_number", layout="classic/big_number", notes=f"Planned: a big_number slide for {maker}, about 'x'"
        )

    def deck(*makers):
        return Deck(
            generator="test",
            schema_name="pitch",
            slides=(DeckSlide(type="title", layout="classic/title"), *map(slide, makers)),
        )

    assert check_arc(deck("problem-number-pitch", "solution-pitch", "the-ask-pitch"), 4) == []
    assert check_arc(deck("Problem Number (Pitch)", "Solution (Pitch)", "The Ask (Pitch)"), 4) == []
    out_of_order = check_arc(deck("the-ask-pitch", "problem-number-pitch", "solution-pitch"), 4)
    assert [finding.message for finding in out_of_order] == ["its problem slide comes after its ask slide"]
