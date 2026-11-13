"""Talks that are playable at a glance (docs/v5-plan.md, D80): the presenter's cues (build dots, a quiz's label), an
agenda that comes back, a recurring character now and then, a photo of the talk's world beside its title, and a
section over a picture of what it's about."""

import types

import pytest

from talkgenerator import title_pictures
from talkgenerator.checks.design import check_design
from talkgenerator.design import engine, themes
from talkgenerator.models.deck import Deck, ShapeElement
from talkgenerator.personas import PERSONAS
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import Recipe
from talkgenerator.render import reveal
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.schema.formats import court, wedding
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)


def _laid_out(made, family="clean keynote", seed=1):
    slide_deck = SlideDeck(len(made), seed=seed)
    for index, slide in enumerate(made):
        slide_deck.add_slide(index, slide)
    slide_deck.theme = themes.pick(family, random_util.Rng(seed))
    return slide_deck.to_deck()


def _dots(slide):
    rings = [element for element in slide.elements if element.role.startswith("build ring")]
    dots = [element for element in slide.elements if element.role.startswith("build dot")]
    return rings, dots


# BUILD DOTS


@pytest.mark.parametrize("family", ["clean keynote", "kids", "90s desktop", "newspaper", "dark minimal"])
def test_a_slide_with_clicks_has_a_ring_for_each_that_fills_on_its_click(images, family):
    flags = slides.RedFlagsSlide("Red flags: geese", "It honks at night", "It owns a car", "It reads your mail")
    title = slides.TitleSlide("Geese", "By Ann")
    deck = _laid_out([title, flags], family)
    assert _dots(deck.slides[0]) == ([], [])  # (nothing to reveal: no dots)
    rings, dots = _dots(deck.slides[1])
    assert len(rings) == len(dots) == reveal.clicks(deck.slides[1]) == 3
    assert all(isinstance(ring, ShapeElement) and not ring.filled and ring.outline for ring in rings)
    assert [dot.appears_on_click for dot in dots] == [1, 2, 3] and [dot.box for dot in dots] == [r.box for r in rings]
    texts = [element.box for element in deck.slides[1].elements if element.kind == "text" and element.box]
    assert not any(engine._overlaps(ring.box, text) for ring in rings for text in texts)


def test_a_column_slides_dots_come_with_its_columns(images):
    columns = slides.ThreeColumnImageSlide(
        "Three", "One", _image("wide"), "Two", _image("tall"), "Three", _image("wide")
    )
    deck = _laid_out([slides.TitleSlide("Cats", None), columns])
    _, dots = _dots(deck.slides[1])
    assert [dot.part_of for dot in dots] == ["content_1", "content_2", "content_3"]
    assert [reveal.opacity(deck.slides[1], dots[1], step) for step in (1, 2)] == [0.0, 1.0]


def test_a_charts_own_clicks_take_its_dots_along_in_powerpoint(images):
    ranking = slides.ChartSlide("Who wins?", None, None)  # (replaced below by a real ranking)
    from talkgenerator.plan.kinds import KINDS

    with random_util.use(random_util.Rng(3)):
        ranking = KINDS["chart_bars"].build(
            {"title": "Who wins?", "bars": "A goose | A duck | My cat"}, {}, languages.ENGLISH
        )
    deck = _laid_out([slides.TitleSlide("Cats", None), ranking])
    _, dots = _dots(deck.slides[1])
    assert len(dots) == 3 == reveal.clicks(deck.slides[1])
    ppt_slide = render_pptx(deck).slides[1]
    steps = ppt_slide.element.xpath(".//p:timing//p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par")
    assert len(steps) == 3  # (a bar a click, its dot with it: no click of their own)


# A QUIZ SAYS IT'S ONE


def test_a_quizs_question_says_its_a_quiz_in_the_talks_language():
    english = slides.quiz_question("Which goose is the loudest?")
    assert english.split()[0] in {label.split()[0] for label in languages.ENGLISH.quizzes}
    assert english.endswith("Which goose is the loudest?")
    dutch = slides.quiz_question("Quiz: welke gans is het luidst?", languages.language("nl"))
    assert dutch.count(":") == 1 and dutch.endswith("Welke gans is het luidst?")  # (in place of the model's own)
    assert slides.quiz_question("Which goose?") == slides.quiz_question("Which goose?")  # (no random stream moves)
    assert all(language.quizzes for language in languages.LANGUAGES.values())


# AN AGENDA THAT COMES BACK


def _planned(number, kind, seed):
    return prompt.PlannedSlide(number, kind, Recipe(kind), seed, digits=2)


def test_an_agenda_announces_later_slides_which_pick_its_items_up():
    planned = {
        1: _planned(2, "agenda", "plan"),
        2: _planned(3, "statement", "ice"),
        3: _planned(4, "section", "middle"),
        4: _planned(5, "quiz", "tuxedos"),
        5: _planned(6, "tier_list", "fish"),
        6: _planned(7, "red_flags", "krill"),
        7: _planned(8, "three_columns", "the end"),
    }
    cued = prompt.agenda_cues(planned)
    assert "slide_03's 'ice'" in cued[1].cue and "slide_07's 'krill'" in cued[1].cue
    announced = [key for key, slide in cued.items() if slide.cue and key != 1]
    assert announced == [2, 5, 6] and "item 1" in cued[2].cue and "item 3" in cued[6].cue  # (no section, not the last)
    assert any("Its first 3 items announce" in line for line in prompt.slide_lines(cued[1]))
    assert prompt.agenda_cues({2: _planned(3, "quiz", "ice")})[2].cue == ""  # (no agenda: as they were)


# A RECURRING CHARACTER NOW AND THEN


def test_a_recurring_character_comes_up_in_a_fifth_of_the_talks():
    share = sum(prompt.recurring_character(random_util.Rng(seed)) for seed in range(1000)) / 1000
    assert 0.16 < share < 0.24
    lines = {prompt.callbacks_line(random_util.Rng(seed)) for seed in range(50)}
    assert len(lines) == 2 and all("two slides" in line or "no recurring" in line for line in lines)


# THE TITLE SLIDE'S PICTURE


def test_a_talks_world_is_its_formats_or_else_its_personas():
    detective = PERSONAS["detective"]
    assert title_pictures.scene(wedding.WEDDING, detective) == "wedding"
    assert title_pictures.scene(court.COURT, None) == "courtroom"
    assert title_pictures.scene(None, detective) == "detective"
    assert title_pictures.scene(None, None) is None
    assert set(title_pictures.PERSONA_SCENES) == set(PERSONAS)
    assert title_pictures.queries("penguins", "wedding") == ["penguins wedding", "wedding"]


def test_a_title_photo_of_one_person_is_left_out_but_a_couple_or_a_crowd_is_not():
    # (one grown-up beside the title passes for the presenter: D81, the user's keynote speaker; the descriptions are
    # Pexels' captions and Pixabay's tags, as found for the talks' worlds)
    alone = title_pictures.alone
    assert title_pictures.SLOT.unwanted is alone
    for one in (
        "A woman giving a presentation on stage with a microphone and laptop.",
        "Speaker addressing large audience with phones lit up at night event.",  # (an audience is no one's own)
        "Female judge in a courtroom setting, focusing on legal documents with a gavel.",  # (one, in two words)
        "A male speaker wearing blue raises his fist in enthusiasm while speaking into a microphone indoors.",
        "Woman with red glasses and tinfoil hat in a thoughtful pose indoors.",
        "speaker, speech, presentation, keynote, present, success, lecture, business man, powerpoint",
        "woman, dark, light, shadow, art",
    ):
        assert alone(one), one
    for more in (
        "A beautiful bride and groom embracing on their wedding day indoors.",
        "Bride walking towards the groom in a lively indoor wedding setting with diverse guests celebrating.",
        "People attending a business conference in a modern indoor setting, featuring banners and a speaker.",
        "A teacher reading to her pupils in a colourful kindergarten classroom.",
        "Close-up of a wooden gavel on a judge's desk, symbolizing justice.",  # (a judge's desk is no judge)
        "Detailed image of Lady Justice statue, symbolizing fairness and impartiality.",
        "An empty conference room setup with podium and rows of chairs, ready for an event.",
        "A young boy with eyeglasses sits on the library floor, engrossed in a book.",  # (a child is no presenter)
        "bride, couple, groom, hands, holding hands, wedding, wedding rings",
        "wedding, beach, sea, nature, together, romance, love, woman, man",
        "audience, backlit, concert, crowd, evening, festival, light, outdoors, party, people",
        "gavel, auction, law, hammer, symbol, judge, legal, justice",  # (its subject comes first)
    ):
        assert not alone(more), more


def test_a_title_slide_shows_its_worlds_photo_beside_its_title(images, monkeypatch):
    monkeypatch.delenv("DISABLE_TITLE_PICTURES")
    asked = []
    photo = _image("wide")

    def find(query, avoid=()):
        asked.append(query)
        return photo if query == "wedding" else None

    monkeypatch.setattr(title_pictures, "SLOT", types.SimpleNamespace(find=find))
    found = title_pictures.lookup("rubber ducks", wedding.WEDDING, None, random_util.Rng(1))
    assert found is not None and found.result() is photo and asked == ["rubber ducks wedding", "wedding"]
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.title_picture = found
    slide_deck.add_slide(0, slides.TitleSlide("Ducks at the Altar", "By Ann Wells\nBest woman"))
    slide_deck.theme = themes.pick("clean keynote", random_util.Rng(1))
    (title,) = slide_deck.to_deck().slides
    assert title.layout == "v5/title-picture" and title.element(engine.TITLE_PICTURE) is not None
    assert title.credits  # (credited, as every picture is)
    for family in ("newspaper", "corporate"):  # (the families whose own title layouts have room for it)
        slide_deck.theme = themes.pick(family, random_util.Rng(1))
        assert slide_deck.to_deck().slides[0].element(engine.TITLE_PICTURE) is not None
    monkeypatch.setenv("DISABLE_TITLE_PICTURES", "1")
    assert title_pictures.lookup("rubber ducks", wedding.WEDDING, None, random_util.Rng(1)) is None


@pytest.mark.parametrize("family", list(themes.FAMILIES))
@pytest.mark.slow
def test_the_longest_title_and_job_fit_every_title_layout(images, family):
    # (a talk's title and the presenter's job as long as they're kept whole, TextField.room: D80, as a free model's
    # jobs of 58 and 59 characters were cut, "Hoofdrondleider van de Verzameling Buitenaardse…"; a job of up to 112, D81)
    from talkgenerator.plan.kinds import PRESENTER_JOB, TALK_TITLE
    from talkgenerator.plan.realize import length_limit

    title = " ".join(["Expectation"] * 9)[: length_limit(TALK_TITLE)].strip()
    job = " ".join(["Brandweer"] * 12)[: length_limit(PRESENTER_JOB)].strip()
    assert len(job) >= length_limit(PRESENTER_JOB) - 1
    for seed in range(3):
        for picture in (None, _image("wide")):
            deck = _laid_out([slides.TitleSlide(title, f"By Ann Wells\n{job}", picture)], family, seed)
            assert check_design(deck) == [], (family, seed, deck.slides[0].layout)


def test_a_kids_title_card_holds_a_long_job_on_a_third_line_in_each_of_its_motifs(images):
    # (the kids' title card holds two lines of subtitle: a long job takes a third, from the title's room, and stays
    # clear of an exercise book's double edge, which a job on the second line crossed: D81)
    from talkgenerator.plan.kinds import PRESENTER_JOB
    from talkgenerator.plan.realize import length_limit

    title = " ".join(["Expectation"] * 9)[:67].strip()
    for job in ("Brandweer", " ".join(["Brandweer"] * 12)[: length_limit(PRESENTER_JOB)].strip()):
        for seed in (0, 2, 3, 7):  # (crayon, stickers, cutouts and notebook)
            deck = _laid_out([slides.TitleSlide(title, f"By Ann Wells\n{job}")], "kids", seed)
            assert deck.slides[0].layout == "v5/kids-title"
            assert check_design(deck) == [], (seed, job)


@pytest.mark.parametrize("family", list(themes.FAMILIES))
@pytest.mark.slow
def test_a_title_slide_with_its_photo_passes_the_design_checks_in_every_theme(images, family):
    # (a talk's title as long as one gets, and one with a compound, as Dutch and German have them; a byline with the
    # presenter's job on a line of its own, as long as a job gets)
    titles = ("Why Rubber Ducks Make the Most Loyal Best Men Ever", "De Brandweerkazernedeur van mijn Oma")
    byline = "By Ann Wells\nPart-time duck whisperer and best woman"
    for seed in range(3):
        for title, shape in zip(titles, ("wide", "tall"), strict=True):
            deck = _laid_out([slides.TitleSlide(title, byline, _image(shape))], family, seed)
            assert check_design(deck) == [], (family, seed, title, deck.slides[0].layout)


# A SECTION OVER A PICTURE


def test_a_section_over_a_picture_has_a_layout_of_its_own(images):
    section = slides.SectionSlide("The dark years", "In which the cat sleeps", None, _image("wide"))
    deck = _laid_out([slides.TitleSlide("Cats", None), section])
    slide = deck.slides[1]
    assert slide.layout == "v5/section-photo"
    assert [element.role for element in slide.elements][:2] == ["background", "shade"]
    plain = _laid_out([slides.TitleSlide("Cats", None), slides.SectionSlide("The dark years")]).slides[1]
    assert plain.layout != "v5/section-photo"
    assert isinstance(Deck.from_json(deck.to_json()), Deck)


# REAL QUOTES THAT A SLIDE MAY MAKE LIGHT OF


def test_a_real_quote_of_self_harm_or_death_stays_off_the_slides():
    from talkgenerator.schema.content_generator_structures import fit_quote

    # (a real quote the prompt lab's judges found on a wedding toast's slide, 2026-11-13)
    assert not fit_quote("We couldn't imagine the emptiness of a creature who put a razor to her wrists and opened")
    assert not fit_quote("Death is not the end.")
    assert fit_quote("A duck is just a boat with opinions.")
