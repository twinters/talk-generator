"""Offline tests of the bolder themes (docs/v5-plan.md, section 9): every family's own decoration (its motif) and
layouts, the shapes they're drawn with (polygons, turned shapes, rounded corners, outlines, background patterns) in
PowerPoint and in previews, the design checks of what's behind a text's letters, and subtler, rarer image filters."""

import dataclasses
import io
import itertools

import pytest
from PIL import Image
from pptx.oxml.ns import qn

from talkgenerator import closers
from talkgenerator.checks.deck import _texts, check_language
from talkgenerator.checks.design import check_design
from talkgenerator.design import color, engine, geometry, layers, motifs, themes, treatments
from talkgenerator.models.deck import (
    DECORATION,
    Box,
    Deck,
    DeckSlide,
    ImageElement,
    ShapeElement,
    SlideBackground,
    TextElement,
    TextStyle,
)
from talkgenerator.models.theme import BackgroundPattern
from talkgenerator.render import backgrounds, preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util
from tests.test_deck import _image
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_design import _deck, _runs, _theme

FAMILIES = list(themes.FAMILIES)
NEW_FAMILIES = ["hacker terminal", "blueprint", "chalkboard", "newspaper", "Swiss poster"]


def _slide(*elements, background=None):
    return DeckSlide(type="title", layout="v5/test", elements=elements, background=background)


def _one_slide_deck(slide, theme=None):
    theme = theme or _theme()
    return Deck(generator="test", theme=theme.name, style=theme, slides=(slide,))


# THE FAMILIES


def test_the_families_keep_their_names_and_the_new_ones_join_them():
    names = [entry["name"] for entry in themes.catalog()]
    old = ["clean keynote", "dark minimal", "corporate", "academic", "startup", "vintage paper", "kids", "brutalist"]
    old += ["neon", "1997 WordArt", "Comic Sans everywhere", "clip-art corporate"]
    assert set(old) <= set(names) and set(NEW_FAMILIES) <= set(names)
    assert all(themes.FAMILIES[name].motif != "none" for name in FAMILIES)  # (each draws its own decoration)
    assert len({themes.FAMILIES[name].motif for name in FAMILIES}) == len(FAMILIES)
    assert not any(themes.FAMILIES[name].extreme for name in NEW_FAMILIES)
    # (and a family's sets of decoration are its own: no two families share one)
    sets = [variant.motif for name in FAMILIES for variant in themes.variants(themes.FAMILIES[name])]
    assert len(sets) == len(set(sets)) and all(motif in motifs._MOTIFS for motif in sets)


@pytest.mark.parametrize("family", FAMILIES)
def test_a_seed_picks_a_member_and_its_decoration(family):
    assert _theme(family, 3) == _theme(family, 3)
    members = [_theme(family, seed) for seed in range(12)]
    assert all(
        member.motif in {variant.motif for variant in themes.variants(themes.FAMILIES[family])} for member in members
    )
    assert len({member.motif_variant for member in members}) > 6


def test_the_committed_families_keep_to_their_palettes():
    for seed in range(20):
        terminal = _theme("hacker terminal", seed)
        assert color.is_dark(terminal.palette.background) and terminal.fonts.body in (
            "Courier New",
            "IBM Plex Mono",
            "Courier Prime",
        )
        assert terminal.pattern is not None and terminal.pattern.kind == "lines"  # (scanlines)
        blueprint = _theme("blueprint", seed)
        hue, _, _ = color.to_hsl(blueprint.palette.background)
        assert 200 <= hue <= 225 and blueprint.pattern is not None and blueprint.pattern.kind == "grid"
        newspaper = _theme("newspaper", seed)
        assert newspaper.image_tint == newspaper.palette.background  # (its photos sit on the page)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_every_family_decorates_its_slides_and_passes_the_design_checks(images, family):
    for seed in range(2):
        deck = _runs(seed, _theme(family, seed)).to_deck()
        assert check_design(deck) == [], (family, seed)
        decorated = [slide for slide in deck.slides if any(element.role == DECORATION for element in slide.elements)]
        # (every slide but those a photo covers, or a side of, to its edges, has the family's fixture, or its
        # decoration's shapes or texts: a photo slide's motifs keep off it, D63's big number beside its picture and
        # D69's problem beside its photo too)
        covered = [slide for slide in deck.slides if slide.type == "full_image" or slide.layout in _SIDE_PHOTOS]
        # (nor a closer, which has no number: all that some families put on such a slide, as brutalist's tag, D76)
        unnumbered = [slide for slide in deck.slides if slide.closer]
        assert len(decorated) >= len(deck.slides) - len(covered) - len(unnumbered) - 2, (family, seed)


# The layouts whose photo fills a side of the slide, to its edges
_SIDE_PHOTOS = frozenset({"v5/big-number-side", "v5/problem-split"})


@pytest.mark.parametrize("family", FAMILIES)
def test_the_big_slides_get_the_big_motifs_and_pass_the_checks(images, family):
    deck = _deck(seed=2, theme=_theme(family, 2)).to_deck()
    assert check_design(deck) == []
    made = [slides.TitleSlide("The secret life of lighthouses", "By Prof. Anna Tomy")]
    section = SlideDeck(1, title="Cats", topics=["cats"], seed=1)
    section.add_slide(0, made[0])
    section.theme = _theme(family, 4)
    assert check_design(section.to_deck()) == []


def test_some_families_have_title_and_section_slides_of_their_own(images):
    owners = {
        "kids": "v5/kids-title",
        "neon": "v5/neon-title",
        "Swiss poster": "v5/swiss-title",
        "newspaper": "v5/newspaper-title",
        "academic": "v5/beamer-title",
        "corporate": "v5/corporate-title",
    }
    title = slides.TitleSlide("The secret life of lighthouses", "By Prof. Anna Tomy").to_deck_slide()
    for family, layout in owners.items():
        theme = _theme(family)
        assert layout in engine.layouts_for(title, theme) and layout in engine.layout_names(theme)
        others = [name for other, name in owners.items() if other != family]
        assert not set(others) & set(engine.layout_names(theme))
        assert layout not in engine.layouts_for(title)  # (no theme: the layouts every family has)
        deck = _deck(theme=theme).to_deck()
        assert deck.slides[0].layout == layout, family


def test_some_families_have_section_slides_of_their_own(images):
    owners = {"kids": "v5/kids-section", "neon": "v5/neon-section", "Swiss poster": "v5/swiss-section"}
    made = [slides.TitleSlide("Cats", "By An O. Nymous"), slides.SectionSlide("The dark years", "In which the cat")]
    for family, layout in owners.items():
        seen = set()
        for seed in range(8):
            slide_deck = SlideDeck(len(made), title="Cats", topics=["cats"], seed=seed)
            for index, slide in enumerate(made):
                slide_deck.add_slide(index, slide)
            slide_deck.theme = _theme(family, seed)
            deck = slide_deck.to_deck()
            assert check_design(deck) == [], (family, seed)
            seen.add(deck.slides[1].layout)
        assert layout in seen, family


@pytest.mark.slow
def test_a_kindergartens_title_has_scenery_and_its_slides_bunting(images):
    crayon = _kids("crayon")  # (crayon drawings: one of its sets of decoration)
    deck = _runs(1, crayon).to_deck()
    first = engine.lay_out(_deck(theme=crayon).to_deck(), crayon).slides[0]
    polygons = [element for element in first.elements if isinstance(element, ShapeElement) and element.points]
    assert len(polygons) > 10  # (pennants, a sun's rays, flowers...)
    assert any(element.rotation for element in polygons)  # (the pennants hang along a sagging string)
    for slide in deck.slides:
        over_a_photo = any(
            isinstance(element, ImageElement) and element.box == engine.FULL for element in slide.elements
        )
        if not over_a_photo:  # (no bunting over a photo across the slide)
            assert any(
                element.points == geometry.pennant() for element in slide.elements if isinstance(element, ShapeElement)
            )


def test_a_terminals_titles_get_a_prompt_and_its_talk_title_a_cursor(images):
    theme = _theme("hacker terminal")
    deck = _deck(theme=theme).to_deck()
    title_slide = deck.slides[0]
    prompts = [element for element in title_slide.elements if element.role == DECORATION and element.kind == "text"]
    assert {element.text for element in prompts} & {"$", ">"}
    title = title_slide.element("title")
    prompt = next(element for element in prompts if element.text in ("$", ">"))
    assert prompt.box.x + prompt.box.w <= title.box.x  # (the title moved over for it)
    cursor = [
        element
        for element in title_slide.elements
        if isinstance(element, ShapeElement) and element.color == theme.palette.text and element.box.w < 200
    ]
    assert cursor and check_design(deck) == []


def test_decoration_texts_are_not_the_talks_words(images):
    for family in ("newspaper", "hacker terminal", "blueprint", "90s desktop"):
        deck = _deck(theme=_theme(family)).to_deck()
        decoration = [
            element.text
            for slide in deck.slides
            for element in slide.elements
            if element.role == DECORATION and element.kind == "text"
        ]
        assert decoration, family
        assert not any(text in decoration for slide in deck.slides for _, text in _texts(slide.elements))
        dutch = deck.model_copy(update={"language": "nl"})
        assert [finding for finding in check_language(dutch) if "decoration" in finding.message] == []


# A KINDERGARTEN'S SETS OF DECORATION (D77): crayon drawings, a sticker book, a school notebook, paper cut-outs

KIDS_SETS = ["crayon", "stickers", "notebook", "cutouts"]


def _kids(motif, palette=None):
    """The first kids member (by seed) with that set of decoration, and that palette of its family's (if any)."""
    family = themes.FAMILIES["kids"]
    for seed in range(1, 1000):
        theme = _theme("kids", seed)
        if theme.motif == motif and (
            palette is None or theme.palette.background == family.palettes[palette].background
        ):
            return theme
    raise AssertionError(f"no kids member with {motif} and palette {palette}")


def test_a_kids_member_has_one_of_its_familys_sets_of_decoration():
    kids = themes.FAMILIES["kids"]
    assert [variant.motif for variant in themes.variants(kids)] == KIDS_SETS
    members = [_theme("kids", seed) for seed in range(60)]
    assert {member.motif for member in members} == set(KIDS_SETS)
    notebooks = [member for member in members if member.motif == "notebook"]
    assert {member.pattern.kind for member in notebooks} == {"lines", "grid"}  # (ruled or squared paper)
    assert all(member.pattern is None for member in members if member.motif == "cutouts")
    # (which set it has comes from a stream of its own: the rest of a member is as it was before kids had sets)
    plain = dataclasses.replace(kids, variants=())
    for seed in range(20):
        with random_util.use(random_util.Rng(seed)):
            member = themes.member(kids)
        with random_util.use(random_util.Rng(seed)):
            before = themes.member(plain)
        assert before.motif == "crayon"
        same = ("name", "fonts", "title_align", "text_scale", "image_filter", "image_frame", "image_tint")
        assert all(getattr(member, field) == getattr(before, field) for field in [*same, "motif_variant"]), seed
        assert member.palette.background == before.palette.background
        if member.motif == "crayon":
            assert member == before
    # (and a family without sets of decoration keeps its one motif)
    assert all(
        themes.variants(themes.FAMILIES[name]) == (themes.Variant(themes.FAMILIES[name].motif),)
        for name in NEW_FAMILIES
    )


def test_a_kindergartens_decoration_is_in_its_palettes_colours(images):
    kids = themes.FAMILIES["kids"]
    bunting = []
    for palette in range(len(kids.palettes)):
        theme = _kids("crayon", palette)
        paints = motifs._paints(theme.palette)
        assert len(paints) == 3 and all(color.contrast(paint, theme.palette.background) >= 1.5 for paint in paints)
        deck = _deck(theme=theme).to_deck()
        pennants = {
            element.color
            for slide in deck.slides
            for element in slide.elements
            if isinstance(element, ShapeElement) and element.points == geometry.pennant()
        }
        assert pennants and pennants <= set(paints), palette  # (no rainbow of its own: the palette's colours)
        bunting.append(frozenset(pennants))
    assert len(set(bunting)) == len(kids.palettes)  # (each palette's bunting its own)


def test_each_set_of_decoration_draws_its_own_pieces_and_passes_the_checks(images):
    pieces = {}
    for palette, motif in enumerate(KIDS_SETS):
        theme = _kids(motif, palette)
        deck = _deck(seed=2, theme=theme).to_deck()
        assert check_design(deck) == [], motif
        shapes = [
            element
            for slide in deck.slides
            for element in slide.elements
            if isinstance(element, ShapeElement) and element.role == DECORATION
        ]
        pieces[motif] = {element.points for element in shapes if element.points}
        if motif == "crayon":  # (bunting)
            assert geometry.pennant() in pieces[motif]
        elif motif == "stickers":  # (titles on white labels, pictures as stickers with a corner peeling off)
            assert any(element.color == "#ffffff" and element.corner > 0 for element in shapes)
            assert ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)) in pieces[motif]
        elif motif == "notebook":  # (ruled or squared paper, and a margin line down its left side)
            assert theme.pattern is not None and theme.pattern.kind in ("lines", "grid")
            assert any(element.box.x == 72.5 and element.box.w == 3 for element in shapes)
        else:  # (a strip with a pinked edge under a title)
            assert any(element.points == geometry.pinked(teeth, 0.4) for teeth in range(6, 15) for element in shapes)
    assert len({frozenset(points) for points in pieces.values()}) == len(KIDS_SETS)


@pytest.mark.parametrize("motif", KIDS_SETS)
def test_each_set_has_its_own_title_and_section_slides(images, motif):
    theme = _kids(motif)
    made = [
        slides.TitleSlide("The secret life of lighthouses", "By Prof. Anna Tomy"),
        slides.SectionSlide("The dark years", "In which the lamp"),
    ]
    badges = set()
    for seed in range(10):
        slide_deck = SlideDeck(len(made), title="Lighthouses", topics=["lighthouses"], seed=seed)
        for index, slide in enumerate(made):
            slide_deck.add_slide(index, slide)
        slide_deck.theme = theme
        deck = slide_deck.to_deck()
        assert check_design(deck) == [], (motif, seed)
        title, section = deck.slides
        assert title.layout == "v5/kids-title"
        if section.layout == "v5/kids-section":  # (its number on a badge of its own: a sun, a rosette, a circle...)
            kicker = section.element("kicker")
            badges.add(kicker.style.color)
            under = [
                element
                for element in section.elements
                if isinstance(element, ShapeElement)
                and geometry.bounds(element).x < engine.KIDS_BADGE.x + engine.KIDS_BADGE.w
            ]
            assert len(under) >= 2, (motif, seed)
    assert badges, motif


@pytest.mark.slow
@pytest.mark.parametrize("motif", KIDS_SETS)
def test_every_set_of_decoration_passes_the_design_checks(images, motif):
    theme = _kids(motif, KIDS_SETS.index(motif) + 2)  # (each in another of the family's palettes than the quick test's)
    assert check_design(_runs(2, theme).to_deck()) == [], motif


# THE NEW FAMILIES (D77): a workshop on a whiteboard, a 1990s computer's desktop, ...


def test_a_workshop_has_sticky_notes_on_a_whiteboard(images):
    for seed in range(3):
        theme = _theme("sticky notes", seed)
        deck = _deck(seed=seed, theme=theme).to_deck()
        assert check_design(deck) == [], seed
        for slide in deck.slides:  # (the board's frame and its tray, on every slide)
            shapes = [element for element in slide.elements if isinstance(element, ShapeElement)]
            assert any(shape.box == engine.FULL and not shape.filled for shape in shapes), slide.layout
        notes = [
            element
            for slide in deck.slides
            for element in slide.elements
            if isinstance(element, ShapeElement) and element.color in motifs.STICKIES
        ]
        assert notes and any(note.rotation for note in notes)  # (sticky notes, turned a little)


def test_a_90s_desktop_has_windows_a_taskbar_and_dialogs(images):
    theme = _theme("90s desktop", 1)
    deck = _deck(seed=1, theme=theme).to_deck()
    assert check_design(deck) == []
    texts = [
        element.text
        for slide in deck.slides
        for element in slide.elements
        if element.role == DECORATION and element.kind == "text"
    ]
    assert "TALK.PPT" in texts and any(text.startswith("PIC") and text.endswith(".BMP") for text in texts)
    assert any("/" in text for text in texts)  # (the slide's number, in the taskbar's tray)
    # (a big slide of nothing but texts is a dialog box on the desktop, which has the second accent's colour)
    made = [slides.TitleSlide("Lighthouses", "By Anna Tomy")]
    title_deck = SlideDeck(1, title="Lighthouses", topics=["lighthouses"], seed=1)
    title_deck.add_slide(0, made[0])
    title_deck.theme = theme
    (title,) = title_deck.to_deck().slides
    assert any(
        isinstance(element, ShapeElement) and element.box == engine.FULL and element.color == theme.palette.accent_2
        for element in title.elements
    )
    assert check_design(title_deck.to_deck()) == []


def _decoration(deck):
    """A deck's decoration: its shapes, and its texts' words."""
    elements = [element for slide in deck.slides for element in slide.elements if element.role == DECORATION]
    shapes = [element for element in elements if isinstance(element, ShapeElement)]
    return shapes, [element.text for element in elements if isinstance(element, TextElement)]


def _is_issue(element):
    """Whether it's a magazine roundel's issue number ("N°7")."""
    return isinstance(element, TextElement) and element.text.startswith("N°")


def _big_slides(theme, seed=1):
    """A title slide and a section slide, laid out in the theme."""
    made = [slides.TitleSlide("Lighthouses", "By Anna Tomy"), slides.SectionSlide("The dark years", "In which")]
    slide_deck = SlideDeck(len(made), title="Lighthouses", topics=["lighthouses"], seed=seed)
    for index, slide in enumerate(made):
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    return slide_deck.to_deck()


@pytest.mark.parametrize("family", ["corkboard", "spreadsheet", "Y2K", "70s retro", "glossy magazine"])
def test_the_new_families_draw_their_own_pieces_and_pass_the_checks(images, family):
    theme = _theme(family, 2)
    deck = _deck(seed=2, theme=theme).to_deck()
    big = _big_slides(theme, 2)
    assert check_design(deck) == [] and check_design(big) == [], family
    shapes, texts = _decoration(deck)
    big_shapes, big_texts = _decoration(big)
    framed = [shape for shape in shapes if shape.part_of]  # (what frames its pictures, and comes in with them)
    assert framed, family
    if family == "corkboard":  # (pins, polaroids' paper, a cork's grain; a red string on its big slides)
        assert any(shape.shape == "ellipse" and shape.color in motifs._PINS for shape in shapes)
        assert any(shape.color == motifs._PAPER for shape in framed)
        assert theme.pattern is not None and theme.pattern.kind == "dots"
        assert any(shape.color == motifs._STRING for shape in big_shapes)
    elif family == "spreadsheet":  # (its columns' letters and its rows' numbers; pictures' selection handles)
        assert {"A", "B", "C", "1", "2", "3"} <= set(texts)
        assert sum(shape.color == "#ffffff" and shape.box.w == 14 for shape in framed) >= 8
        assert theme.pattern is not None and theme.pattern.kind == "lines"
    elif family == "Y2K":  # (chrome headings on a pastel gradient, four-pointed sparkles)
        assert theme.background == "gradient" and theme.heading_effect is not None
        assert theme.heading_effect.outline and len(theme.heading_effect.fill) == len(themes.CHROME)
        assert any(shape.points == geometry.star(4, 0.22) for shape in [*shapes, *big_shapes])
    elif family == "70s retro":  # (four stripes turning the top left corner, on every slide)
        stripes = [shape for shape in shapes if shape.shape == "polygon" and len(shape.points) > 20]
        assert len(stripes) >= 4 * len(deck.slides) - 4
    else:  # (a folio, giant quotation marks by a quote, the issue's roundel on its big slides)
        assert "“" in texts and any(text.startswith("N°") for text in big_texts)
        # (the member's issue, the same on each big slide, the closer's too, which has no slide number: D76)
        closer = closers.DEFAULT.slide(closers.Ending.of(presenter="Anna Tomy")).to_deck_slide()
        title = slides.TitleSlide("Lighthouses", "By Anna Tomy").to_deck_slide()
        closing = engine.lay_out(Deck(generator="test", seed=2, slides=(title, closer)), theme)
        assert check_design(closing) == []
        issues = [
            [element.text for element in slide.elements if element.role == DECORATION and _is_issue(element)]
            for slide in (*big.slides, *closing.slides)
        ]
        assert all(issues) and len({text for texts in issues for text in texts}) == 1, issues


# THE SHAPES THEY'RE DRAWN WITH


def test_polygons_in_their_boxes():
    shapes = [geometry.star(), geometry.burst(), geometry.heart(), geometry.pennant(), geometry.wave()]
    shapes += [geometry.scallop(), geometry.arch(), geometry.pinked(), geometry.leaf(), geometry.ribbon()]
    for points in shapes:
        xs, ys = [x for x, _ in points], [y for _, y in points]
        assert min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1
        assert min(xs) == 0 and max(xs) == 1 and min(ys) == 0 and max(ys) == 1  # (filling it)
    assert len(geometry.star(5)) == 10 and geometry.star()[0] == (0.5, 0.0)
    box, outline = geometry.stroke([(100, 100), (300, 100)], 10)
    assert (box.x, box.y, box.w, box.h) == (100, 95, 200, 10) and len(outline) == 4


def test_a_turned_shape_is_where_its_drawn():
    bar = ShapeElement(box=Box(x=0, y=0, w=200, h=20), color="#000000", rotation=90)
    bounds = geometry.bounds(bar)
    assert (round(bounds.x), round(bounds.y), round(bounds.w), round(bounds.h)) == (90, -90, 20, 200)
    assert geometry.contains(bar, (100, -50)) and not geometry.contains(bar, (10, 10))
    assert geometry.touches(bar, Box(x=95, y=-60, w=10, h=10))
    assert not geometry.touches(bar, Box(x=110, y=0, w=10, h=10))  # (an edge that only meets the bar's)


def test_powerpoint_draws_polygons_turns_corners_outlines_and_patterns():
    pattern = BackgroundPattern(kind="grid", color="#ffffff", opacity=0.1, spacing=24, size=2, major=5)
    star = ShapeElement(shape="polygon", points=geometry.star(), box=Box(x=100, y=100, w=200, h=200), color="#ffcc00")
    turned = ShapeElement(box=Box(x=400, y=100, w=300, h=60), color="#ff0000", rotation=-8, corner=20)
    ring = ShapeElement(
        shape="ellipse",
        box=Box(x=800, y=100, w=200, h=200),
        color="#000000",
        filled=False,
        outline="#00ff00",
        outline_width=10,
        opacity=0.5,
    )
    background = SlideBackground(color="#173a66", pattern=pattern)
    deck = _one_slide_deck(_slide(star, turned, ring, background=background))
    presentation = render_pptx(Deck.from_json(deck.to_json()))  # (as the deck's JSON keeps them)
    ppt_slide = presentation.slides[0]
    shapes = list(ppt_slide.shapes)
    geometry_xml = shapes[0]._element.spPr.find(qn("a:custGeom"))
    path = geometry_xml.find(".//" + qn("a:path"))
    assert int(path.get("w")) == 200 * 6350 and len(path.findall(qn("a:lnTo"))) == 9
    assert (
        shapes[1].rotation == pytest.approx(352)
        and shapes[1]._element.spPr.find(qn("a:prstGeom")).get("prst") == "roundRect"
    )
    line = shapes[2].line
    assert line.width == 10 * 6350 and shapes[2]._element.spPr.find(qn("a:noFill")) is not None
    alpha = shapes[2]._element.spPr.find(qn("a:ln")).find(".//" + qn("a:alpha"))
    assert alpha.get("val") == "50000"
    assert shapes[2].left == round(805 * 6350)  # (its outline inside its box: the shape half a line's width in)
    fill = ppt_slide._element.cSld.bg.bgPr.find(qn("a:blipFill"))
    assert fill is not None  # (the background, a picture of its colour and grid)


def test_slides_share_their_background_picture():
    pattern = BackgroundPattern(kind="lines", color="#33ff66", opacity=0.05, spacing=6, size=2)
    background = SlideBackground(color="#061006", pattern=pattern)
    deck = _one_slide_deck(_slide(background=background))
    deck = deck.model_copy(update={"slides": deck.slides * 4})
    presentation = render_pptx(deck)
    parts = {
        ppt_slide.part.related_part(
            ppt_slide._element.cSld.bg.bgPr.find(qn("a:blipFill")).find(qn("a:blip")).get(qn("r:embed"))
        ).partname
        for ppt_slide in presentation.slides
    }
    assert len(parts) == 1


def test_previews_draw_the_new_shapes_and_patterns():
    star = ShapeElement(shape="polygon", points=geometry.star(), box=Box(x=100, y=100, w=400, h=400), color="#ff0000")
    turned = ShapeElement(box=Box(x=900, y=500, w=600, h=40), color="#0000ff", rotation=90)
    ring = ShapeElement(
        shape="ellipse",
        box=Box(x=1300, y=100, w=400, h=400),
        color="#000000",
        filled=False,
        outline="#00ff00",
        outline_width=20,
    )
    grid = BackgroundPattern(kind="grid", color="#000000", opacity=1.0, spacing=100, size=4, offset=50)
    picture = preview.slide_image(
        _slide(star, turned, ring, background=SlideBackground(color="#ffffff", pattern=grid)), _theme(), width=1920
    )
    assert picture.getpixel((300, 300)) == (255, 0, 0)  # (the star's middle)
    assert picture.getpixel((110, 110))[0] < 255 or picture.getpixel((110, 110)) == (255, 255, 255)
    assert picture.getpixel((1200, 330)) == (0, 0, 255)  # (the bar, turned upright)
    assert picture.getpixel((1500, 300)) == (255, 255, 255)  # (the ring's inside, empty)
    assert picture.getpixel((1305, 300))[1] > 200  # (its outline)
    assert picture.getpixel((51, 75)) == (0, 0, 0) and picture.getpixel((75, 75)) == (255, 255, 255)  # (the grid)


def test_a_pattern_layer_is_as_light_in_a_small_preview():
    lines = BackgroundPattern(kind="lines", color="#000000", opacity=0.5, spacing=10, size=2)
    full = backgrounds.pattern_layer(lines, (1920, 1080), 1.0)
    small = backgrounds.pattern_layer(lines, (192, 108), 0.1)
    assert full.getchannel("A").getextrema() == (0, 128)
    assert small.getchannel("A").getextrema()[1] <= 26  # (a line a fifth of a pixel thick, a fifth as dark)
    assert Image.open(io.BytesIO(backgrounds.picture(SlideBackground(color="#ffffff", pattern=lines)))).size == (
        1920,
        1080,
    )


# THE DESIGN CHECKS: WHAT'S BEHIND A TEXT'S LETTERS


def _text(text="Hello", box=Box(x=100, y=100, w=1000, h=120), color="#111111"):
    return TextElement(role="title", text=text, box=box, style=TextStyle(font="Arial", size=80, color=color))


def test_a_shape_behind_part_of_a_texts_letters_counts():
    dark = ShapeElement(box=Box(x=150, y=90, w=40, h=200), color="#111111")  # (under its first letters)
    findings = check_design(_one_slide_deck(_slide(dark, _text(), background=SlideBackground(color="#ffffff"))))
    assert [finding.check for finding in findings] == ["contrast"]


def test_a_shape_beside_a_texts_letters_in_its_box_doesnt_count():
    cursor = ShapeElement(box=Box(x=600, y=110, w=40, h=80), color="#111111")  # (after "Hello", in its box)
    deck = _one_slide_deck(_slide(cursor, _text(), background=SlideBackground(color="#ffffff")))
    assert check_design(deck) == []
    lines = engine.line_boxes(
        "Hello", Box(x=100, y=100, w=1000, h=120), TextStyle(font="Arial", size=80, color="#000000")
    )
    assert lines[0].x == 100 and lines[0].w < 300
    assert layers.letters(lines, 80)[0].h == pytest.approx(64)


def test_a_texts_letters_on_a_pattern_need_to_read_on_its_lines_too():
    pattern = BackgroundPattern(kind="lines", color="#000000", opacity=0.9, spacing=10, size=4)
    deck = _one_slide_deck(_slide(_text(color="#555555"), background=SlideBackground(color="#ffffff", pattern=pattern)))
    assert [finding.check for finding in check_design(deck)] == ["contrast"]


# SUBTLER, RARER IMAGE FILTERS


STRONG = {"grayscale", "sepia", "duotone", "black and white"}


def test_strong_filters_are_for_the_families_made_for_them():
    for name in themes.FAMILIES:
        members = [themes.pick(name, random_util.Rng(seed)) for seed in range(40)]
        strong = sum(member.image_filter in STRONG for member in members) / len(members)
        made_for_them = {"vintage paper", "newspaper", "brutalist", "neon", "dark minimal", "Swiss poster"}
        if name in made_for_them:
            assert strong > 0.2, name
        elif name in ("hacker terminal", "blueprint"):
            assert 0.05 < strong < 0.5, name  # (now and then: a terminal's green, a cyanotype)
        else:
            assert strong == 0, name


def test_most_pictures_stay_as_they_are_or_get_a_gentle_tint():
    members = [themes.pick(themes.RANDOM, random_util.Rng(seed)) for seed in range(300)]
    untouched = sum(member.image_filter == "none" for member in members) / len(members)
    assert untouched > 0.7
    tints = [member for member in members if member.image_tint]
    assert tints and all(member.image_tint_opacity <= 0.12 for member in tints)


def test_black_and_white_never_goes_behind_a_slides_texts():
    theme = _theme("brutalist").model_copy(update={"image_filter": "black and white", "image_filter_scope": "all"})
    assert (
        treatments.treatment(theme, framed=False) is None or treatments.treatment(theme, framed=False).filter == "none"
    )
    assert treatments.treatment(theme, framed=True).filter == "black and white"


def test_a_backdrop_filter_leaves_pictures_in_boxes_as_they_are():
    theme = _theme("neon").model_copy(update={"image_filter": "duotone", "image_filter_scope": "backdrops"})
    assert treatments.treatment(theme, framed=False).filter == "duotone"
    boxed = treatments.treatment(theme, framed=True)
    assert boxed is None or boxed.filter == "none"


def test_a_tint_is_laid_over_a_picture_everywhere(images):
    theme = _theme().model_copy(update={"image_tint": "#ff9a3c", "image_tint_opacity": 0.07, "image_filter": "none"})
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, slides.ImageSlide("Cats", _image("wide")))
    slide_deck.theme = theme
    deck = slide_deck.to_deck()
    (picture,) = [element for element in deck.slides[0].elements if isinstance(element, ImageElement)]
    assert (picture.treatment.tint, picture.treatment.tint_opacity) == ("#ff9a3c", 0.07)
    ppt_slide = render_pptx(deck).slides[0]
    (tint,) = [shape for shape in ppt_slide.shapes if shape.name == "Tint"]
    assert tint._element.spPr.find(".//" + qn("a:alpha")).get("val") == "7000"
    plain = Image.new("RGB", (10, 10), "#0000ff")
    tinted = treatments.filtered(plain, picture.treatment)
    assert tinted.getpixel((5, 5)) != (0, 0, 255) and tinted.getpixel((5, 5))[2] > 200  # (a slight cast)


@pytest.mark.slow
def test_families_keep_their_treatments_apart_from_their_decoration(images):
    # (a family's pictures in boxes get its own frame: a terminal's window, a sticker's border; not its border too)
    for family in ("hacker terminal", "kids", "blueprint"):
        deck = _runs(1, _theme(family, 1)).to_deck()
        pictures = [
            element
            for slide in deck.slides
            if slide.type in ("image", "two_column_image", "three_column_image")
            for element in slide.elements
            if isinstance(element, ImageElement)
        ]
        assert pictures and all(element.border is None for element in pictures), family


def test_motifs_draw_nothing_for_the_classic_look():
    scene = motifs.Scene(
        placement=engine.Placement("v5/title"),
        roles={},
        slide_type="title",
        theme=themes.CLASSIC_LOOK,
        number=0,
        credits=False,
        backdrop=False,
    )
    motifs.decorate(scene)
    assert not scene.placement.under and not scene.placement.decor and not scene.placement.texts


def test_the_deck_keeps_the_new_fields(images):
    for family in NEW_FAMILIES:
        deck = _deck(theme=_theme(family)).to_deck()
        assert Deck.from_json(deck.to_json()) == deck
    # (and a deck without them reads as before: every new field has a default)
    old = ShapeElement.model_validate({"box": {"x": 0, "y": 0, "w": 1, "h": 1}, "color": "#000000"})
    assert old.shape == "rectangle" and old.filled and not old.points and old.rotation == 0
    assert list(itertools.islice(engine.layout_names(), 1)) == ["v5/title"]
