"""Offline tests of the closer (talkgenerator.closers, docs/v5-plan.md D76): the slide after a talk's last, which says
the talk is over, of its format's kind and in its language, outside the slides the talk asked for. The deck marks it,
none of the slides' numbers count it, stream_talk sends it as one more slide.ready right after the last slide, the
.pptx ends with it, and every theme family lays it out as a title slide (or, for a question, beside a huge question
mark), without a number.

The talks are the fake ones of test_llm_talks: a fake schema with recipes, a fake model and fake images.
"""

import re

import pytest
from pydantic import TypeAdapter

from talkgenerator import closers, generator
from talkgenerator.checks.deck import check_deck
from talkgenerator.checks.design import check_design
from talkgenerator.design import engine, themes
from talkgenerator.models.deck import DECORATION, Deck, TextElement
from talkgenerator.models.events import SlideReady, TalkEvent, TalkFinished
from talkgenerator.plan import languages
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema import formats
from talkgenerator.schema.formats import academic, corporate, keynote, pitch
from talkgenerator.schema.presentation_schema_types import get_schema, schemas
from talkgenerator.slide.slides import TitleSlide
from talkgenerator.util import random_util
from tests.test_llm_talks import NUM_SLIDES, FakeModel, _talk, fake_schema, images  # noqa: F401

_COUNT = re.compile(r"^\[?(?:# )?0*(\d+) ?/ ?(\d+)\]?$")


@pytest.fixture
def fake(monkeypatch):
    """The fake schema of test_llm_talks, for every talk."""
    made = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: made)
    return made


def _texts(slide):
    return {element.role: element.text for element in slide.elements if isinstance(element, TextElement)}


def _numbers(slide):
    """The slide numbers a slide's decoration writes ("7/12")."""
    return [
        element.text
        for element in slide.elements
        if isinstance(element, TextElement) and element.role == DECORATION and _COUNT.match(element.text)
    ]


# WHAT A CLOSER SAYS

# Every format's closer, by the name of its schema (a schema without a format of its own: the TED-like talk's)
CLOSERS = {name: closers.of(get_schema(name).format) for name in schemas.names()}
FORMATS = {
    "default": closers.DEFAULT,
    "academic": academic.ACADEMIC.closer,
    "pitch": pitch.PITCH.closer,
    "corporate": corporate.CORPORATE.closer,
    "keynote": keynote.KEYNOTE.closer,
}


def _said(closer, code="en", presenter="Ann Example", title="Penguinly: Uber for Penguins", topic="penguins"):
    return _texts(closer.slide(closers.Ending.of(code, presenter, title, topic)).to_deck_slide())


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_every_formats_closer_says_it_in_the_talks_language(code):
    words = languages.language(code)
    made = {name: _said(closer, code) for name, closer in FORMATS.items()}
    assert made["default"] == {"title": words.thanks, "subtitle": "Ann Example", "note": words.questions}
    assert made["academic"] == {
        "title": words.questions,
        "subtitle": words.attention,
        "note": "Ann Example",
        "mark": "?",
    }
    assert made["pitch"] == {"title": words.lets_talk, "subtitle": "ann@penguinly.com", "note": "Ann Example"}
    assert made["corporate"] == {
        "title": words.questions,
        "subtitle": words.back_to_work,
        "note": "Ann Example",
        "mark": "?",
    }
    assert made["keynote"] == {"title": words.available, "subtitle": "Penguinly", "note": "Ann Example"}
    # (each language's own words, not English's: but its question mark, its exclamation mark)
    if code != "en":
        english = languages.ENGLISH
        assert (words.thanks, words.lets_talk, words.back_to_work, words.available) != (
            english.thanks,
            english.lets_talk,
            english.back_to_work,
            english.available,
        )


@pytest.mark.parametrize("name", list(CLOSERS))
def test_every_formats_closer_says_something_in_every_talk_language(name):
    # (a new format's closer included: one it doesn't define is the TED-like talk's)
    for code in languages.LANGUAGES:
        texts = _said(CLOSERS[name], code)
        assert texts.get("title", "").strip(), (name, code)
        assert all(text.strip() for text in texts.values()), (name, code)


def test_a_format_without_a_closer_gets_the_ted_like_talks():
    assert closers.of(None) is closers.of(formats.Format(brief="")) is closers.DEFAULT
    assert get_schema("default").format is None and CLOSERS["default"] is CLOSERS["ted"] is closers.DEFAULT
    own = {name: CLOSERS[name] is not closers.DEFAULT for name in FORMATS}
    assert own == {"default": False, "academic": True, "pitch": True, "corporate": True, "keynote": True}


def test_a_format_defines_its_closer_from_talkgenerators_words_its_own_or_the_talks():
    # (as a new format would, here an infomercial's: words of its own in every talk language, and the presenter's name)
    call_now = {code: f"Call now! ({code})" for code in languages.LANGUAGES}
    infomercial = closers.Closer(closers.in_every_language(call_now), closers.presenter, closers.said("questions"))
    assert _said(infomercial, "sv") == {"title": "Call now! (sv)", "subtitle": "Ann Example", "note": "Frågor?"}
    assert _said(closers.Closer(lambda ending: ending.topic.upper()), "nl") == {"title": "PENGUINS"}
    with pytest.raises(ValueError):  # (a language left out)
        closers.in_every_language({"en": "Call now!"})
    with pytest.raises(ValueError):  # (a word talkgenerator doesn't have)
        closers.said("call_now")


def test_a_closer_is_marked_and_of_a_type_of_its_own():
    slide = closers.DEFAULT.slide(closers.Ending.of(presenter="Ann Example")).to_deck_slide()
    assert (slide.type, slide.layout, slide.closer) == ("closer", "classic/closer", True)
    assert not TitleSlide("A title", "By Ann").to_deck_slide().closer  # (no other slide is)
    with pytest.raises(ValueError):
        closers.Ending.of("tlh")  # (a language talkgenerator doesn't know)


def test_a_closer_without_a_presenter_still_says_it_is_over():
    assert _said(closers.DEFAULT, presenter=None) == {"title": "Thank you!", "note": "Questions?"}
    assert _said(FORMATS["academic"], presenter="  ")["title"] == "Questions?"


def test_a_pitchs_contact_line_is_the_presenters_first_name_at_its_startups_domain():
    assert closers.contact("Prof. Anna Tomy", "Penguinly: Uber for Penguins", "penguins") == "anna@penguinly.com"
    assert closers.contact("Dr. Émile Zola", "Pingüino.ai: Penguins for All", "pinguinos") == "emile@pinguino.ai"
    assert closers.contact("Ann Example", "Penguin Labs: Penguins, Scaled", "penguins") == "ann@penguinlabs.com"
    # (a name without a first name: its surname, whole, as a Dutch kindergarten teacher's "Juf Van Wielen")
    assert closers.contact("Juf Van Wielen", "Trapzo: Fietsen Zonder Trappen", "fietsen") == "vanwielen@trapzo.com"
    assert closers.first_name("Dr. Smith") == "smith" and closers.first_name("Prof.") is None
    # (a title that names no startup: the startup a classic pitch names after its topic, and no name: hello@)
    named = formats.startup("time travel").lower().replace(" ", "")
    assert closers.contact(None, "Why Time Travel Matters", "time travel").startswith("hello@" + named.split(".")[0])
    assert re.fullmatch(r"hello@[a-z0-9]+\.[a-z]+", closers.contact(None, None, "time travel"))


def test_a_keynotes_closer_names_the_product_its_title_names():
    assert closers.product_name("Penguin Pro: Flight, Reimagined", "penguins") == "Penguin Pro"
    assert closers.product_name("The Penguin Keynote", "penguins") == formats.product("penguins")
    assert closers.named("A Title Far Too Long to Be the Name of Anything: Really") is None
    assert closers.named(None) is None and closers.named("No colon") is None


def test_no_format_spends_a_slide_of_its_arc_on_questions():
    assert {module.ARC.names()[-1] for module in (academic, corporate, pitch)} == {"references", "ask"}
    for module in (academic, corporate, pitch):  # (no "Questions?" among a format's slides anymore)
        assert not {"questions", "qa", "closing"} & set(module.ARC.names())


# HOW IT LOOKS


@pytest.mark.parametrize("family", list(themes.FAMILIES))
def test_every_family_lays_a_closer_out_as_a_title_slide_without_a_number(family):
    rng = random_util.Rng(7)
    for member in range(2):
        theme = themes.pick(family, rng.child("theme", member), True, None, None)
        for kind in ("default", "academic", "pitch"):
            ending = closers.Ending.of(presenter="Dr. Anna Tomy", title="Penguinly: Uber for Penguins")
            slides = (
                TitleSlide("Penguinly: Uber for Penguins", "By Dr. Anna Tomy").to_deck_slide(),
                FORMATS[kind].slide(ending).to_deck_slide(),
            )
            deck = engine.lay_out(Deck(generator="test", seed=member, slides=slides), theme)
            closer = deck.slides[-1]
            assert closer.closer and closer.layout in ("v5/closer", "v5/closer-mark"), (family, kind)
            assert closer.layout == "v5/closer" or kind != "pitch"  # (the mark is a question's)
            assert _numbers(closer) == [], (family, kind)  # (none of the slides' numbers count it)
            assert all(int(_COUNT.match(text).group(2)) == 1 for text in _numbers(deck.slides[0])), family
            assert check_design(deck) == [], (family, kind)


@pytest.mark.slow
@pytest.mark.parametrize("family", list(themes.FAMILIES))
def test_every_closer_in_every_language_fits_and_reads_in_every_family(family):
    # (the longest name a talk takes, 45 characters, and a title that names a long startup and product)
    name = "Prof. Dr. Maximiliane Oberbergmeister-Hoffmann"[:45]
    title = "Sauerteigmanufaktur: Brot, Neu Gedacht"
    theme = themes.pick(family, random_util.Rng(1).child("theme"), True, None, None)
    for code in languages.LANGUAGES:
        for kind, closer in CLOSERS.items():  # (every format's, a new one's too)
            slide = closer.slide(closers.Ending.of(code, name, title, "Sauerteig"))
            for seed in range(2):  # (both layouts, for a question)
                deck = engine.lay_out(Deck(generator="test", seed=seed, slides=(slide.to_deck_slide(),)), theme)
                assert check_design(deck) == [], (family, code, kind, seed)


# IN A TALK


def test_a_talk_ends_with_its_closer_after_the_slides_it_asked_for(fake):
    deck = _talk(FakeModel(), theme="clean keynote")
    closer = deck.slides[-1]
    assert closer.closer and closer.type == "closer" and deck.counted() == NUM_SLIDES == len(deck.slides) - 1
    assert _texts(closer) == {"title": "Thank you!", "subtitle": "Ann Example", "note": "Questions?"}
    assert not any(slide.closer for slide in deck.slides[:-1])
    # Numbered of the talk's own slides ("7/7"), the closer none
    numbered = [text for slide in deck.slides for text in _numbers(slide)]
    assert numbered and all(int(_COUNT.match(text).group(2)) == NUM_SLIDES for text in numbered)
    assert _numbers(closer) == [] and check_deck(deck, NUM_SLIDES) == []
    assert "closer" in closer.notes  # (how it was made, for whoever reads the notes)
    assert len(render_pptx(deck).slides) == NUM_SLIDES + 1  # (the .pptx ends with it too)


def test_a_classic_decks_closer_has_no_number_where_its_slides_have_theirs(fake):
    deck = _talk("none", theme="classic")
    presentation = render_pptx(deck)
    numbers = [
        shape.text_frame.text for slide in presentation.slides for shape in slide.shapes if shape.name == "Slide number"
    ]
    assert numbers == [f"{number}/{NUM_SLIDES}" for number in range(1, NUM_SLIDES + 1)]
    assert len(presentation.slides) == NUM_SLIDES + 1 and deck.slides[-1].layout == "classic/closer"


def test_a_talk_in_another_language_ends_with_its_closer_in_that_language(fake):
    deck = _talk(FakeModel(), language="nl")
    assert deck.language == "nl"
    assert _texts(deck.slides[-1]) == {"title": "Bedankt!", "subtitle": "Ann Example", "note": "Vragen?"}


def test_a_talk_streams_its_closer_last_as_one_more_slide(fake):
    events = list(
        generator.stream_talk("fake", NUM_SLIDES, topic="cats", presenter="Ann Example", int_seed=3, llm=FakeModel())
    )
    ready = [event for event in events if isinstance(event, SlideReady)]
    assert [event.index for event in ready] == list(range(NUM_SLIDES + 1))
    assert [event.slide.closer for event in ready] == [None] * NUM_SLIDES + [True]
    assert events[-2] is ready[-1] and isinstance(events[-1], TalkFinished)
    assert list(events[-1].deck.slides) == [event.slide for event in ready]  # (laid out as the deck has it)
    assert _numbers(ready[-1].slide) == []
    assert TypeAdapter(TalkEvent).validate_json(ready[-1].to_json()) == ready[-1]
    assert '"closer":true' in ready[-1].to_json() and '"closer"' not in ready[0].to_json()
