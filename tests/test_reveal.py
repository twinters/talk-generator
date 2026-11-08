"""Offline tests of what appears when, as a deck is presented (docs/v5-plan.md, D52 and D53): a picture's frame, its
shadow or its tape (a theme's decoration that belongs to it) come in with the picture, in PowerPoint and in the
previewer's steps; a two-column slide has no panel behind one half; and a list of things (figures, options, levels,
steps...) shows its things one by one, a click each, each with the shapes it's drawn on."""

import re

import pytest

from talkgenerator.design import engine, themes
from talkgenerator.models.deck import ImageElement, ShapeElement, TextElement
from talkgenerator.render import preview, reveal
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_karaoke_types import every_karaoke_type
from tests.test_slide_types import _clicks, _deck, every_new_type

# The families whose decoration frames pictures: stickers, hard shadows, windows, figure plates, tape, outlines
FRAMING = ("kids", "brutalist", "hacker terminal", "blueprint", "chalkboard", "newspaper")


def _theme(family, seed=1):
    return themes.pick(family, random_util.Rng(seed))


def _columns(count):
    wide, tall = _image("wide"), _image("tall")
    if count == 2:
        return slides.TwoColumnImageSlide("Cats", "Expectation", wide, "Reality", tall)
    return slides.ThreeColumnImageSlide("Cats", "One", wide, "Two", tall, "Three", wide)


@pytest.mark.parametrize("family", FRAMING)
@pytest.mark.parametrize("count", [2, 3])
def test_a_pictures_frame_belongs_to_it_and_comes_in_with_its_column(images, family, count):
    for seed in range(1, 4):
        (slide,) = _deck([_columns(count)], _theme(family, seed), seed).slides
        framed = {element.part_of for element in slide.elements if getattr(element, "part_of", None)}
        assert framed >= {f"content_{index}" for index in range(2, count + 1)}, (family, seed, slide.layout)
        for element in slide.elements:
            owner = getattr(element, "part_of", None)
            if owner is None:
                continue
            column = int(owner[-1])
            comes = reveal.column_click(slide, column)
            assert reveal.opacity(slide, element, comes) == 1.0
            if comes:  # (nothing of a column that comes on a click shows before it: not its frame either)
                assert reveal.opacity(slide, element, comes - 1) == 0.0
            else:
                assert reveal.opacity(slide, element, 1) == reveal.DIMMED  # (dimming with its picture)


@pytest.mark.parametrize("family", ["hacker terminal", "kids"])
def test_powerpoint_shows_a_columns_frame_on_its_columns_click(images, family):
    deck = _deck([_columns(2)], _theme(family))
    (ppt_slide,) = render_pptx(deck).slides
    (shown,) = _clicks(ppt_slide)  # (the second column's: the first is there from the start)
    names = set(shown)
    assert {"caption_2", "decoration"} <= names  # (its window, its sticker's border and shadow)
    assert any(name.startswith("Picture") for name in names)  # (and its picture)
    frames = [element for element in deck.slides[0].elements if getattr(element, "part_of", None) == "content_2"]
    assert frames and all(isinstance(frame, ShapeElement | TextElement) for frame in frames)
    if family == "hacker terminal":  # (and the name on the window's bar)
        assert any(isinstance(frame, TextElement) and frame.text.startswith("./evidence_") for frame in frames)


def test_the_split_layout_has_no_panel_and_its_rule_comes_with_the_second_half(images):
    for family in themes.FAMILIES:
        for seed in range(1, 12):
            (slide,) = _deck([_columns(2)], _theme(family, seed), seed).slides
            if slide.layout != "v5/columns-2-split":
                continue
            assert all(element.role != "panel" for element in slide.elements), family
            (divider,) = [element for element in slide.elements if element.role == "divider"]
            assert isinstance(divider, ShapeElement) and divider.part_of == "content_2" and divider.box.w <= 3
            break


def test_every_list_shows_its_things_one_by_one_with_their_shapes(images):
    """Every list type's things come a click each (1, 2, 3...), and every shape a thing is drawn on (its tile, badge,
    band, oval, box or dot) comes with it, in every one of its layouts."""
    theme = _theme("clean keynote")
    made = [*every_new_type(_image("wide")), *every_karaoke_type(_image("wide"))]
    lists = ("kpi", "quiz", "agenda", "timeline", "pyramid", "funnel", "cycle", "org_chart", "iceberg")
    lists += ("acronym", "flowchart", "tier_list")
    for slide in made:
        if slide.type_name not in lists:
            continue
        content = slide.to_deck_slide()
        roles = {element.role: element for element in content.elements}
        clicks = sorted({element.appears_on_click for element in content.elements if element.appears_on_click})
        assert clicks == list(range(1, len(clicks) + 1)) and len(clicks) >= 2, slide.type_name
        assert all(not element.appears_on_click for element in content.elements if element.role == "title")
        for layout in engine._LAYOUTS[slide.type_name]:
            if not layout.fits(roles) or not layout.for_family(theme.family):
                continue
            placement = layout.build(roles, theme)
            for shape in [*placement.shapes, *placement.overlays]:
                text = _thing(shape.role)
                if text in roles:
                    assert shape.appears_on_click == roles[text].appears_on_click, (layout.name, shape.role)


def _thing(shape_role):
    """The role of the text a list's shape is drawn for: a figure's tile, a letter's badge, a step's oval..."""
    named = {"figure": "number", "dot": "event", "tile": "option"}
    if match := re.fullmatch(r"(figure|dot|tile)_(\d)( strip)?", shape_role):
        return f"{named[match.group(1)]}_{match.group(2)}"
    if match := re.fullmatch(r"(\w+?)_?(\d)? ?(badge|band|oval|box|label)", shape_role):
        thing, number = match.group(1), match.group(2)
        return f"{thing}_{number}" if number else thing
    return re.sub(r"^(\w+) (\d) \w+$", r"\1_\2", shape_role)


def test_a_pyramid_builds_from_its_base_and_a_tier_list_from_its_worst_tier():
    pyramid = slides.PyramidSlide("P", "Top", "Middle", "Base", "Rock bottom").to_deck_slide()
    assert [pyramid.element(f"level_{index}").appears_on_click for index in (4, 3, 2, 1)] == [1, 2, 3, 4]
    tiers = slides.TierListSlide("T", "Best", "Good", "Fine", "Meh", "Worst").to_deck_slide()
    assert [tiers.element(f"item_{tier}_1").appears_on_click for tier in "fcbas"] == [1, 2, 3, 4, 5]
    assert all(tiers.element(f"tier_{tier}").appears_on_click is None for tier in "sabcf")  # (the letters stay)


def test_a_memes_captions_come_one_by_one_and_a_lone_caption_with_its_picture():
    two = slides.MemeSlide(_image("wide"), "Setup", "Punchline").to_deck_slide()
    assert [two.element("text_1").appears_on_click, two.element("text_2").appears_on_click] == [1, 2]
    one = slides.MemeSlide(_image("wide"), "Just this").to_deck_slide()
    assert one.element("text_1").appears_on_click is None


def test_clicks_go_in_turn_when_a_layout_leaves_something_out(images):
    # (a meme's picture whose boxes talkgenerator doesn't know has two, at its top and its bottom: a third caption
    # has no place, nor a click, as an empty click would show nothing)
    meme = slides.MemeSlide(_image("wide"), "One", "Two", "Three")
    (slide,) = _deck([meme], _theme("clean keynote")).slides
    assert slide.element("text_3") is None
    assert sorted(e.appears_on_click for e in slide.elements if getattr(e, "appears_on_click", None)) == [1, 2]
    assert reveal.clicks(slide) == 2
    gapped = [TextElement(role="a", text="A", appears_on_click=2), TextElement(role="b", text="B", appears_on_click=5)]
    assert [element.appears_on_click for element in engine._in_turn([*gapped])] == [1, 2]


def test_reveal_counts_a_slides_clicks(images):
    two, three = _deck([_columns(2), _columns(3)], _theme("clean keynote")).slides
    assert (reveal.clicks(two), reveal.clicks(three)) == (1, 3)
    first = two.element("content_1")
    assert [reveal.opacity(two, first, step) for step in (0, 1)] == [1.0, reveal.DIMMED]
    assert [reveal.opacity(three, three.element("content_2"), step) for step in (1, 2, 3)] == [0.0, 1.0, 0.5]
    (quiz,) = _deck([slides.QuizSlide("Why?", "A", "B", "C", "D", "A", "Yes")], _theme("clean keynote")).slides
    assert reveal.clicks(quiz) == 5


def test_previews_show_a_slide_click_by_click(images):
    theme = _theme("hacker terminal")
    deck = _deck([_columns(2), slides.KpiSlide("KPIs", "1", "A", "2", "B", "3", "C")], theme)
    columns, kpi = deck.slides
    first = preview.slide_image(columns, theme, step=0, width=480)
    clicked = preview.slide_image(columns, theme, step=1, width=480)
    everything = preview.slide_image(columns, theme, width=480)
    assert len({first.tobytes(), clicked.tobytes(), everything.tobytes()}) == 3  # (once clicked, the first dims)
    # (before the click, the second column's place is the background, frame and all)
    content = columns.element("content_2")
    assert isinstance(content, ImageElement) and content.box is not None
    box = content.box
    middle = (round((box.x + box.w / 2) / 4), round((box.y + box.h / 2) / 4))
    assert first.getpixel(middle) != clicked.getpixel(middle)
    steps = [preview.slide_image(kpi, theme, step=step, width=240).tobytes() for step in range(4)]
    assert len(set(steps)) == 4  # (a figure more on every click)
    sheet = preview.steps_sheet(deck, width=200)
    assert sheet.width > 4 * 200 and sheet.height > 2 * 112  # (two rows: the slides that take clicks)
