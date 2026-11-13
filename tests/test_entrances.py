"""Offline tests of entrances (D83): in a theme that moves, a slide's things come in with PowerPoint's entrance effects
as it's presented (talkgenerator.design.entrances), in PowerPoint as PowerPoint writes them
(talkgenerator.render.entrance_effects); a calm theme's slides stay as they were."""

import io
import typing

import pytest
from lxml import etree
from pptx import Presentation

from talkgenerator.design import entrances, themes
from talkgenerator.models.deck import (
    DECORATION,
    ENTRANCE_DURATIONS,
    ChartElement,
    DiagramElement,
    Entrance,
    ImageElement,
    TextElement,
)
from talkgenerator.models.theme import EntranceEffect
from talkgenerator.render import reveal
from talkgenerator.render.entrance_effects import TEMPLATES
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_slide_types import _deck, every_new_type
from tests.test_videos import _big_gif, _themed
from tests.test_videos import served as served  # the fake gifs and videos (a fixture)

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
EFFECTS = typing.get_args(EntranceEffect)
# PowerPoint's preset numbers for them, as it wrote them (2026-11-13)
PRESETS = {
    "fade": "10",
    "wipe": "22",
    "float_in": "42",
    "rise_up": "37",
    "zoom": "53",
    "fly_in": "2",
    "grow_turn": "31",
    "swivel": "45",
    "boomerang": "25",
    "curve_up": "52",
    "drop": "38",
    "bounce": "26",
    "spiral_in": "15",
    "pinwheel": "35",
    "flip": "56",
}
CALM = [name for name, family in themes.FAMILIES.items() if family.motion == (("none", 1.0),)]


def _theme(motion, family="clip-art corporate", seed=3):
    theme = themes.pick(family, random_util.Rng(seed))
    return theme.model_copy(update={"motion": motion, "entrances": themes.FAMILIES[family].entrances})


def _slides():
    return [
        slides.ImageSlide("A wild picture appears", _image("wide")),
        slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", _image("tall")),
        slides.ThreeColumnImageSlide("Cats", "One", _image("wide"), "Two", _image("tall"), "Three", _image("square")),
        *every_new_type(_image("wide")),
    ]


def _moves(element):
    return getattr(element, "entrance", None) is not None


# THE THEMES


def test_every_effect_has_powerpoints_template_and_duration():
    assert set(TEMPLATES) == set(EFFECTS) == set(ENTRANCE_DURATIONS) == set(PRESETS)
    for effect, template in TEMPLATES.items():
        par = etree.fromstring(
            f'<r xmlns:p="{P[1:-1]}">{template.format(spid=7, group=0, node="clickEffect", delay=250)}</r>'
        )[0]
        node = par.find(f"{P}cTn")
        assert (node.get("presetClass"), node.get("presetID")) == ("entr", PRESETS[effect])
        assert node.find(f"{P}stCondLst/{P}cond").get("delay") == "250"
        assert {target.get("spid") for target in par.iter(f"{P}spTgt")} == {"7"}
        assert par.find(f".//{P}iterate") is None  # (the whole shape, not letter by letter)


def test_every_family_moves_as_much_as_it_says_with_effects_of_its_own():
    for name, family in themes.FAMILIES.items():
        assert sum(weight for _, weight in family.motion) == pytest.approx(1.0), name
        assert (family.entrances == ()) == all(motion == "none" for motion, _ in family.motion), name
        assert set(family.entrances) <= set(EFFECTS)
    assert {"clean keynote", "dark minimal", "academic", "Swiss poster"} <= set(CALM)  # (the user's: "serious ones")
    for extreme in (family for family in themes.FAMILIES.values() if family.extreme):
        assert dict(extreme.motion)["lots"] >= 0.5  # (for laughs: everything moves in half of them)


def test_a_members_motion_comes_from_a_stream_of_its_own():
    for family in ("kids", "1997 WordArt", "corporate"):
        motions = {themes.pick(family, random_util.Rng(seed)).motion for seed in range(40)}
        assert len(motions) > 1, family  # (members of a family move differently)
        theme = themes.pick(family, random_util.Rng(5))
        assert theme.entrances == (themes.FAMILIES[family].entrances if theme.motion != "none" else ())


def test_moving_changes_nothing_else_of_a_deck(images):
    still = _theme("none")
    moving = _theme("lots")
    calm_deck = _deck(_slides(), still, seed=4)
    lively_deck = _deck(_slides(), moving, seed=4)

    for calm, lively in zip(calm_deck.slides, lively_deck.slides, strict=True):
        assert calm.layout == lively.layout
        assert [
            element.model_copy(update={"entrance": None}) if _moves(element) else element for element in lively.elements
        ] == list(calm.elements)
        assert not any(_moves(element) for element in calm.elements)


@pytest.mark.parametrize("family", CALM)
def test_a_calm_familys_slides_never_move(images, family):
    for seed in range(3):
        deck = _deck(_slides(), themes.pick(family, random_util.Rng(seed)), seed=seed)
        assert not any(_moves(element) for slide in deck.slides for element in slide.elements)


# WHAT COMES IN, AND WHEN


def test_with_lots_of_motion_every_thing_comes_in_the_title_first(images):
    deck = _deck(_slides(), _theme("lots"), seed=2)

    for slide in deck.slides:
        for element in slide.elements:
            if isinstance(element, ChartElement | DiagramElement) or element.role.startswith("build "):
                assert not _moves(element)
            elif isinstance(element, TextElement) and element.role != DECORATION:
                assert _moves(element), (slide.type, element.role)
            elif isinstance(element, ImageElement) and element.role != "background":
                assert _moves(element), (slide.type, element.role)
        starting = [
            element
            for element in slide.elements
            if _moves(element) and not reveal.click_of(slide, element) and not _column_click(slide, element)
        ]
        delays = sorted({element.entrance.delay for element in starting})
        assert delays[0] == 0 and delays[-1] <= entrances.MOST_STAGGER
        title = slide.element("title")
        if title is not None and title in starting:
            assert title.entrance.delay == 0, slide.type


def test_a_clicks_things_come_in_together_with_one_effect(images):
    deck = _deck(_slides(), _theme("lots"), seed=2)

    for slide in deck.slides:
        by_click = {}
        for element in slide.elements:
            click = reveal.click_of(slide, element) or _column_click(slide, element)
            if click and _moves(element):
                by_click.setdefault(click, set()).add(element.entrance)
        assert all(len(kinds) == 1 for kinds in by_click.values()), slide.type
        assert all(entrance.delay == 0 for kinds in by_click.values() for entrance in kinds)


def test_what_belongs_to_a_picture_comes_in_with_it(images):
    framing = themes.pick("kids", random_util.Rng(1))
    theme = framing.model_copy(update={"motion": "lots", "entrances": themes.FAMILIES["kids"].entrances})
    deck = _deck([slides.ImageSlide("Look", _image("wide")), slides.FullImageSlide("Look", _image("tall"))], theme)

    belonging = 0
    for slide in deck.slides:
        for element in slide.elements:
            owner = getattr(element, "part_of", None)
            target = slide.element(owner) if owner else None
            if target is not None and _moves(target):
                belonging += 1
                assert element.entrance == target.entrance, (slide.layout, element.role)
    assert belonging


def test_with_some_motion_a_slide_now_and_then_has_one_thing_or_two(images):
    counts = []
    for seed in range(12):
        deck = _deck(_slides(), _theme("some"), seed=seed)
        counts += [len(set(entrances.effects(slide))) for slide in deck.slides]
    assert set(counts) <= {0, 1, 2}
    assert 0.25 < counts.count(0) / len(counts) < 0.75  # (every other slide, about)
    assert counts.count(2) < counts.count(1)


def _column_click(slide, element):
    column = reveal.column_of(slide, element)
    return reveal.column_click(slide, column) if column is not None else None


# POWERPOINT


def _timing(ppt_slide):
    return ppt_slide.element.find(f"{P}timing")


def _steps(ppt_slide):
    timing = _timing(ppt_slide)
    if timing is None:
        return []
    return timing.findall(f".//{P}cTn[@nodeType='mainSeq']/{P}childTnLst/{P}par")


def _comes_up(step):
    return step.find(f"./{P}cTn/{P}stCondLst/{P}cond[@evt='onBegin']") is not None


def _effects(step):
    """A step's effects: (preset, delay, shape id)."""
    return [
        (
            node.get("presetID"),
            int(node.find(f"{P}stCondLst/{P}cond").get("delay")),
            node.find(f".//{P}spTgt").get("spid"),
        )
        for node in step.iter(f"{P}cTn")
        if node.get("presetClass") == "entr"
    ]


def test_powerpoint_plays_what_comes_in_as_the_slide_comes_up_then_the_clicks(images):
    deck = _deck(_slides(), _theme("lots"), seed=2)
    output = io.BytesIO()
    render_pptx(deck).save(output)
    reopened = Presentation(output)

    for slide, ppt_slide in zip(deck.slides, reopened.slides, strict=True):
        steps = _steps(ppt_slide)
        starting = [step for step in steps if _comes_up(step)]
        assert len(starting) <= 1 and (not starting or steps[0] is starting[0])  # (one, before the first click)
        clicks = [step for step in steps if not _comes_up(step)]
        assert len(clicks) == reveal.clicks(slide), slide.type
        if starting:
            presets = {preset for preset, _, _ in _effects(starting[0])}
            assert presets <= {PRESETS[effect] for effect in entrances.effects(slide)}
            first = starting[0].find(f".//{P}cTn[@presetClass='entr']")
            assert first.get("nodeType") == "afterEffect"
        timing = _timing(ppt_slide)
        if timing is not None:
            ids = [node.get("id") for node in timing.iter(f"{P}cTn")]
            assert len(ids) == len(set(ids)) and ids[:2] == ["1", "2"]


def test_powerpoint_gives_each_shape_its_effect_and_delay(images):
    effect_of = {effect: index for index, effect in enumerate(EFFECTS)}
    made = [slides.ImageSlide(effect, _image("wide")) for effect in EFFECTS]
    deck = _deck(made, _theme("none"))
    moved = []
    for slide, effect in zip(deck.slides, EFFECTS, strict=True):
        elements = tuple(
            element.model_copy(update={"entrance": Entrance(effect=effect, delay=100 * effect_of[effect])})
            if isinstance(element, TextElement | ImageElement) and element.role != DECORATION
            else element
            for element in slide.elements
        )
        moved.append(slide.model_copy(update={"elements": elements}))
    deck = deck.model_copy(update={"slides": tuple(moved)})

    for effect, ppt_slide in zip(EFFECTS, render_pptx(deck).slides, strict=True):
        (step,) = _steps(ppt_slide)
        assert _comes_up(step)
        found = _effects(step)
        assert found and {(preset, delay) for preset, delay, _ in found} == {(PRESETS[effect], 100 * effect_of[effect])}


def test_a_video_there_from_the_start_plays_with_what_comes_in(served):
    theme = _theme("lots", family="startup")
    _, (ppt_slide,) = _themed(slides.ImageSlide("Look at this", _big_gif()), theme=theme)

    (step,) = _steps(ppt_slide)  # (one step as the slide comes up: the entrances, and the video's play with them)
    assert _comes_up(step)
    plays = step.findall(f".//{P}cTn[@presetClass='mediacall']")
    assert len(plays) == 1
    (video,) = [effect for effect in _effects(step) if effect[2] == plays[0].find(f".//{P}spTgt").get("spid")]
    assert plays[0].find(f"{P}stCondLst/{P}cond").get("delay") == str(video[1])  # (as it comes in)
