"""Offline tests of themes and layouts (milestone 3): colours and contrast, measuring and fitting text, theme
families, the layout engine, and the renderers of themed decks (PowerPoint shapes, and previews)."""

import itertools

import pytest
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn

from talkgenerator import generator, settings
from talkgenerator.checks.deck import deck_metrics
from talkgenerator.checks.design import check_design, check_variety
from talkgenerator.design import color, engine, fit, fonts, themes, treatments
from talkgenerator.models.deck import Deck, ImageElement, ShapeElement, TextElement
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS
from talkgenerator.render import preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import random_util
from tests import test_seeds
from tests.test_deck import _every_kind_of_slide, _image, _pie_chart_data
from tests.test_deck import images as images  # the fake image downloads (a fixture)

FAMILIES = list(themes.FAMILIES)


def _deck(seed=1, theme=None, **options):
    """A deck of every kind of slide, as the generator makes it (laid out in the theme, if any)."""
    slide_deck = SlideDeck(len(_every_kind_of_slide()), title="Cats", topics=["cats"], seed=seed)
    for index, slide in enumerate(_every_kind_of_slide()):
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    slide_deck.style_chaos = options.get("style_chaos", 0.0)
    return slide_deck


def _theme(family="clean keynote", seed=1):
    return themes.pick(family, random_util.Rng(seed))


# COLOURS


def test_contrast_is_wcags():
    assert color.contrast("#000000", "#ffffff") == pytest.approx(21)
    assert color.contrast("#777777", "#777777") == pytest.approx(1)
    assert color.contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


def test_a_colour_that_doesnt_read_is_repaired():
    for foreground, background in [("#9999ff", "#ffffff"), ("#333333", "#111111"), ("#ff0000", "#ee1111")]:
        repaired = color.readable(foreground, background, 4.5)
        assert color.contrast(repaired, background) >= 4.5
    assert color.readable("#000000", "#ffffff") == "#000000"  # good enough already: unchanged


def test_colours_round_trip():
    assert color.hsl(*color.to_hsl("#3366cc")) == "#3366cc"
    assert color.mix("#000000", "#ffffff", 0.5) == "#808080"


# MEASURING AND FITTING TEXT


def test_text_is_measured_or_generously_estimated(monkeypatch):
    width = fonts.text_width("Hello there", "Arial", 100)
    assert fonts.text_width("Hello there, again", "Arial", 100) > width
    assert fonts.text_width("Hello there", "Arial", 50) == pytest.approx(width / 2, rel=0.01)
    monkeypatch.setattr(fonts, "_font_index", lambda: {})  # a computer without any of the fonts
    assert not fonts.measured("Arial")
    estimate = fonts.text_width("Hello there", "Arial", 100)
    assert estimate == pytest.approx(11 * 100 * 0.52 * fonts.ESTIMATE_MARGIN)


def test_a_text_gets_the_largest_size_at_which_it_fits():
    short = fit.fit("Cats", 1600, 300, "Arial", 140, 60)
    assert short.fits and short.size == 140 and short.lines == ("Cats",)
    long = fit.fit("The secret life of cats, and what they do when nobody is looking", 800, 200, "Arial", 140, 30)
    assert long.fits and long.size < 140 and len(long.lines) > 1
    assert len(long.lines) * long.size * fit.LINE_HEIGHT <= 200
    assert all(fonts.text_width(line, "Arial", long.size) <= 800 for line in long.lines)
    impossible = fit.fit("word " * 80, 200, 50, "Arial", 60, 40)
    assert not impossible.fits and impossible.size == 40


# THEMES


def test_classic_is_no_theme_and_unknown_themes_are_refused():
    assert themes.pick("classic", random_util.Rng(1)) is None
    with pytest.raises(ValueError, match="no theme 'glitter'"):
        themes.pick("glitter", random_util.Rng(1))


@pytest.mark.parametrize("family", FAMILIES)
def test_every_member_of_every_family_reads(family):
    for seed in range(8):
        theme = _theme(family, seed)
        palette = theme.palette
        backgrounds = [palette.background, *([theme.gradient_to] if theme.gradient_to else [])]
        for background in backgrounds:
            assert color.contrast(palette.text, background) >= 4.5, (theme.name, background)
            assert color.contrast(palette.muted, background) >= 4.5, (theme.name, background)
            assert color.contrast(palette.accent, background) >= 3, (theme.name, background)
        assert theme.fonts.heading in fonts.FONTS and theme.fonts.body in fonts.FONTS


def test_a_theme_comes_from_its_seed():
    assert _theme("neon", 3) == _theme("neon", 3)
    assert len({_theme("neon", seed).palette.accent for seed in range(10)}) > 5


def test_the_random_mix_leaves_extremes_out_when_asked():
    picked = [themes.pick("random", random_util.Rng(seed), extremes=False) for seed in range(60)]
    assert not any(theme.extreme for theme in picked)
    assert any(themes.pick("random", random_util.Rng(seed)).extreme for seed in range(60))
    assert "1997 WordArt" not in themes.names(extremes=False) and "1997 WordArt" in themes.names()


# THE LAYOUT ENGINE


@pytest.mark.parametrize("family", FAMILIES)
def test_every_element_gets_a_place_and_every_text_fits(images, family):
    deck = _deck(theme=_theme(family)).to_deck()
    assert deck.theme.startswith(family) and deck.style.family == family
    for slide in deck.slides:
        assert slide.layout.startswith("v5/") and slide.background is not None
        for element in slide.elements:
            box = element.box
            assert box is not None, (slide.type, element.role)
            assert box.x >= 0 and box.y >= 0 and box.x + box.w <= 1920 and box.y + box.h <= 1080
            if isinstance(element, TextElement):
                style = element.style
                text = element.text.upper() if style.uppercase else element.text
                fitted = fit.fit(text, box.w, box.h, style.font, style.size, style.size, style.bold)
                assert fitted.fits, (slide.type, element.role, element.text, style.size)


def test_layouts_and_sizes_come_from_the_seed(images):
    theme = _theme()
    assert _deck(seed=4, theme=theme).to_deck() == _deck(seed=4, theme=theme).to_deck()
    layouts = {tuple(slide.layout for slide in _deck(seed=seed, theme=theme).to_deck().slides) for seed in range(12)}
    assert len(layouts) > 1  # a slide gets one of the layouts of its type


def _runs(seed=1, theme=None):
    """A deck with runs of slides of one type, as talks have them: two-column slides, full-screen pictures with and
    without a title, charts, image slides, statements and three-column slides, several of each in a row, each with
    a credit."""
    wide, tall = _image("wide"), _image("tall")
    runs = [
        *(slides.TwoColumnImageSlide("Cats", "Expectation", wide, "Reality", tall) for _ in range(5)),
        *(slides.FullImageSlide(None, wide) for _ in range(3)),
        *(slides.FullImageSlide("Look at this", wide) for _ in range(4)),
        *(slides.ChartSlide("Cat growth", XL_CHART_TYPE.COLUMN_CLUSTERED, _pie_chart_data(), None) for _ in range(3)),
        *(slides.ImageSlide("Cats", wide) for _ in range(4)),
        *(slides.LarqeQuoteSlide(None, "Be brave, little cat", background_image=wide) for _ in range(4)),
        *(slides.ThreeColumnImageSlide(None, "One", wide, "Two", tall, "Three", wide) for _ in range(3)),
    ]
    slide_deck = SlideDeck(len(runs), title="Cats", topics=["cats"], seed=seed)
    for index, slide in enumerate(runs):
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")  # (credits on every layout)
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    return slide_deck


@pytest.mark.parametrize("family", FAMILIES)
def test_no_layout_comes_twice_in_a_row_and_every_one_passes_the_design_checks(images, family):
    for seed in range(3):
        deck = _runs(seed, _theme(family, seed)).to_deck()
        layouts = [slide.layout for slide in deck.slides]
        assert all(before != after for before, after in itertools.pairwise(layouts)), layouts
        assert check_design(deck) == [], (family, seed)


def test_the_layouts_pass_the_design_checks_in_random_themes(images):
    for seed in range(20):
        theme = themes.pick(themes.RANDOM, random_util.Rng(seed))  # (extremes included)
        assert check_design(_runs(seed, theme).to_deck()) == [], (seed, theme.name)


def test_every_layout_comes_up(images):
    seen = set()
    for seed in range(12):
        seen |= {slide.layout for slide in _runs(seed, _theme(seed=seed)).to_deck().slides}
    assert set(engine.layout_names()) - {"v5/title", "v5/diagram"} <= seen  # (the deck has no title or diagram)


def test_a_slide_gets_the_layouts_that_fit_its_elements(images):
    def fitting(slide):
        return engine.layouts_for(slide.to_deck_slide())

    two = slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", "A quote, not a picture")
    assert fitting(two) == ["v5/columns-2", "v5/columns-2-headed", "v5/columns-2-rows", "v5/columns-2-split"]
    assert fitting(slides.FullImageSlide(None, _image("wide"))) == ["v5/full-image", "v5/full-image-framed"]
    titled = slides.FullImageSlide("Look at this", _image("wide"))
    assert fitting(titled) == ["v5/full-image", "v5/full-image-low", "v5/full-image-corner"]
    assert fitting(slides.ImageSlide(None, _image("wide"))) == ["v5/image-top"]  # (no title to put beside it)


def test_a_title_over_a_picture_is_drawn_over_it(images):
    for seed in range(8):
        slide_deck = SlideDeck(1, seed=seed)
        slide_deck.add_slide(0, slides.FullImageSlide("Look at this", _image("wide")))
        slide_deck.theme = _theme()
        (slide,) = slide_deck.to_deck().slides
        order = [element.role for element in slide.elements]
        assert order.index("content") < order.index("title band") < order.index("title"), (slide.layout, order)


def test_the_design_checks_find_a_text_under_a_picture_and_a_layout_twice_in_a_row(images):
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, slides.FullImageSlide("Look at this", _image("wide")))
    slide_deck.theme = _theme()
    deck = slide_deck.to_deck()
    (slide,) = deck.slides
    title = slide.element("title")
    under = slide.model_copy(
        update={"elements": (title, *(element for element in slide.elements if element is not title))}
    )
    findings = check_design(deck.model_copy(update={"slides": (under,)}))
    assert [finding.message for finding in findings if finding.check == "covered"] == [
        "the title is under a picture drawn over it"
    ]

    deck = _runs(theme=_theme()).to_deck()
    assert check_variety(deck) == []
    first = deck.slides[1]  # (a two-column slide)
    twice = deck.model_copy(update={"slides": (first, first)})
    assert [finding.message for finding in check_variety(twice)] == [
        f"the same layout as the slide before ({first.layout})"
    ]


def test_the_metrics_count_layouts(images):
    classic = deck_metrics(_runs().to_deck())
    themed = deck_metrics(_runs(theme=_theme()).to_deck())
    assert classic["same_layout_in_a_row"] > 0  # (the 2019 template has one layout per slide type)
    assert themed["same_layout_in_a_row"] == 0 and themed["layouts"] > classic["layouts"]


def test_every_layout_draws_and_previews(images):
    deck = _runs(theme=_theme("neon")).to_deck()
    assert len(render_pptx(deck).slides) == len(deck.slides)
    assert preview.contact_sheet(deck).width > 0


# IMAGE TREATMENTS


def _treated(slide=None, family="clean keynote", **treatment):
    """A one-slide deck (a picture under a title, by default) in a theme with the treatment, its slide drawn in
    PowerPoint, and the theme."""
    theme = _theme(family).model_copy(update={f"image_{name}": value for name, value in treatment.items()})
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, slide or slides.ImageSlide("Cats", _image("wide")))
    slide_deck.theme = theme
    deck = slide_deck.to_deck()
    return deck, render_pptx(deck).slides[0], theme


def _named(ppt_slide, name):
    return [shape for shape in ppt_slide.shapes if shape.name == name]


def _the_picture(ppt_slide):
    (picture,) = [shape for shape in ppt_slide.shapes if shape.shape_type == 13 and shape.name != "Grain"]
    return picture


def _blip(picture):
    return picture._element.blipFill.blip


def test_families_treat_their_pictures():
    def share(family, wanted):
        members = [themes.pick(family, random_util.Rng(seed)) for seed in range(40)]
        return sum(wanted(member) for member in members) / len(members)

    assert share("vintage paper", lambda theme: theme.image_filter in ("sepia", "grayscale")) > 0.8
    assert share("vintage paper", lambda theme: theme.image_grain > 0) > 0.3
    assert share("brutalist", lambda theme: theme.image_filter in ("black and white", "grayscale")) > 0.6
    assert share("neon", lambda theme: theme.image_filter == "duotone") > 0.3
    assert share("kids", lambda theme: theme.image_frame in ("rounded", "polaroid")) > 0.8
    assert share("clean keynote", lambda theme: theme.image_filter == "none") == 1


def test_a_themed_picture_gets_its_themes_treatment(images):
    deck, _, theme = _treated(filter="duotone", frame="rounded", grain=0.14, vignette=0.7)
    (picture,) = [element for element in deck.slides[0].elements if isinstance(element, ImageElement)]
    look = picture.treatment
    assert (look.filter, look.frame, look.grain, look.vignette) == ("duotone", "rounded", 0.14, 0.7)
    assert (look.dark, look.light) == treatments.duotone(theme.palette)
    assert Deck.from_json(deck.to_json()) == deck
    classic = _deck().to_deck()
    assert all(
        element.treatment is None
        for slide in classic.slides
        for element in slide.elements
        if isinstance(element, ImageElement)
    )


def test_a_picture_over_the_whole_slide_gets_its_filter_but_no_frame(images):
    deck, _, _ = _treated(slides.FullImageSlide("Look at this", _image("wide")), filter="sepia", frame="polaroid")
    (picture,) = [element for element in deck.slides[0].elements if isinstance(element, ImageElement)]
    assert (picture.treatment.filter, picture.treatment.frame) == ("sepia", "none")
    assert (picture.treatment.dark, picture.treatment.light) == treatments.SEPIA


@pytest.mark.parametrize("name", ["grayscale", "sepia", "duotone", "black and white"])
def test_a_filter_is_a_picture_effect_in_powerpoint(images, name):
    deck, ppt_slide, theme = _treated(filter=name)
    blip = _blip(_the_picture(ppt_slide))
    if name == "grayscale":
        assert blip.find(qn("a:grayscl")) is not None
    elif name == "black and white":
        threshold = int(blip.find(qn("a:biLevel")).get("thresh"))
        low, high = treatments.THRESHOLDS
        assert round(low * 100000) <= threshold <= round(high * 100000)
    else:
        colours = [element.get("val").lower() for element in blip.find(qn("a:duotone"))]
        expected = treatments.SEPIA if name == "sepia" else treatments.duotone(theme.palette)
        assert colours == [colour.lstrip("#") for colour in expected]


def test_rounded_corners_a_vignette_and_grain(images):
    _, ppt_slide, _ = _treated(frame="rounded", grain=0.14, vignette=0.7)
    picture = _the_picture(ppt_slide)
    (vignette,) = _named(ppt_slide, "Vignette")
    (grain,) = _named(ppt_slide, "Grain")
    shapes = list(ppt_slide.shapes)
    assert shapes.index(picture) < shapes.index(vignette) < shapes.index(grain)  # (over the picture)
    for shape in (picture, vignette, grain):
        assert shape._element.spPr.find(qn("a:prstGeom")).get("prst") == "roundRect"
        assert (shape.left, shape.top, shape.width, shape.height) == (
            picture.left,
            picture.top,
            picture.width,
            picture.height,
        )
    gradient = vignette._element.spPr.find(qn("a:gradFill"))
    assert gradient.find(qn("a:path")).get("path") == "circle"


def test_a_polaroid_is_a_tilted_white_frame_around_its_picture(images):
    deck, ppt_slide, _ = _treated(frame="polaroid", border=True)
    (frame,) = _named(ppt_slide, "Polaroid frame")
    picture = _the_picture(ppt_slide)
    (element,) = [element for element in deck.slides[0].elements if isinstance(element, ImageElement)]
    tilt = element.treatment.tilt
    assert treatments.POLAROID_TILT[0] <= abs(tilt) <= treatments.POLAROID_TILT[1]
    assert frame.rotation == picture.rotation == pytest.approx(tilt % 360)
    shapes = list(ppt_slide.shapes)
    assert shapes.index(frame) < shapes.index(picture)  # (the frame behind it)
    assert element.border is None  # (the white frame instead of the theme's border)
    assert picture.width < frame.width and picture.height < frame.height


def test_previews_show_the_treatments(images):
    deck, _, theme = _treated(filter="grayscale")
    slide = deck.slides[0]
    (element,) = [element for element in slide.elements if isinstance(element, ImageElement)]
    picture = preview.slide_image(slide, theme, width=1920)
    middle = (round(element.box.x + element.box.w / 2), round(element.box.y + element.box.h / 2))
    red, green, blue = picture.getpixel(middle)
    assert red == green == blue  # (the fake picture is blue)
    for treatment in ({"frame": "polaroid", "grain": 0.14, "vignette": 0.7}, {"frame": "rounded", "filter": "duotone"}):
        deck, _, theme = _treated(**treatment)
        assert preview.slide_image(deck.slides[0], theme).width == 960


def test_a_photo_behind_a_statement_gets_a_shade(images):
    deck = _deck(theme=_theme()).to_deck()
    statement = next(slide for slide in deck.slides if slide.type == "large_quote")
    background, shade = statement.elements[0], statement.elements[1]
    assert isinstance(background, ImageElement) and background.fit == "cover" and background.box == engine.FULL
    assert isinstance(shade, ShapeElement) and shade.opacity == engine.SHADE_OPACITY
    assert statement.element("text").style.color == engine.LIGHT_TEXT


def test_with_style_chaos_slides_get_themes_of_their_own(images):
    theme = _theme()
    calm = _deck(theme=theme).to_deck()
    assert not any(slide.style for slide in calm.slides)
    chaos = _deck(theme=theme, style_chaos=1.0).to_deck()
    assert all(slide.style is not None for slide in chaos.slides)
    assert len({slide.style.name for slide in chaos.slides}) > 3


def test_a_classic_deck_stays_classic(images):
    deck = _deck().to_deck()
    assert deck.theme == "classic" and deck.style is None
    assert all(slide.layout.startswith("classic/") for slide in deck.slides)
    assert '"box"' not in deck.to_json()  # (nothing for the empty fields)


# DRAWING THEMED DECKS


def test_a_themed_deck_is_drawn_as_shapes(images):
    theme = _theme("dark minimal")
    slide_deck = _deck(theme=theme)
    deck = slide_deck.to_deck()
    presentation = render_pptx(deck, images=slide_deck.image_store())
    assert (presentation.slide_width, presentation.slide_height) == (12192000, 6858000)
    assert len(presentation.slides) == len(deck.slides)
    title_slide = presentation.slides[0]
    assert not list(title_slide.placeholders)  # blank slides, drawn on
    fill = title_slide.background.fill
    assert str(fill.fore_color.rgb).lower() == theme.palette.background.lstrip("#")
    runs = [
        run
        for shape in title_slide.shapes
        if shape.has_text_frame
        for p in shape.text_frame.paragraphs
        for run in p.runs
    ]
    assert runs[0].text == "A talk about cats" and runs[0].font.name == theme.fonts.heading
    # The credits link to their pages
    credited = presentation.slides[2]
    links = [
        run.hyperlink.address
        for shape in credited.shapes
        if shape.has_text_frame
        for p in shape.text_frame.paragraphs
        for run in p.runs
        if run.hyperlink.address
    ]
    assert links == ["https://www.pexels.com/photo/cat-123/"]
    pictures = [shape for slide in presentation.slides for shape in slide.shapes if shape.shape_type == 13]
    assert len(pictures) == sum(len(slide.images()) for slide in deck.slides)


def test_a_gradient_runs_from_the_top_down():
    theme = next(_theme("1997 WordArt", seed) for seed in range(20) if _theme("1997 WordArt", seed).gradient_to)
    slide = Deck(generator="test", slides=(_deck().to_deck().slides[0],))
    presentation = render_pptx(engine.lay_out(slide, theme))
    linear = presentation.slides[0].element.find(".//" + qn("a:lin"))
    assert linear.get("ang") == "5400000"  # DrawingML's 90 degrees: the first colour at the top
    colors = [element.get("val").lower() for element in presentation.slides[0].element.iter(qn("a:srgbClr"))][:2]
    assert colors == [theme.palette.background.lstrip("#"), theme.gradient_to.lstrip("#")]


def test_a_deck_from_json_is_laid_out_when_drawn(images):
    deck = _deck().to_deck().model_copy(update={"theme": "neon 1", "style": _theme("neon")})
    presentation = render_pptx(Deck.from_json(deck.to_json()))
    assert len(presentation.slides) == len(deck.slides) and not list(presentation.slides[0].placeholders)


def test_a_themed_trend_with_two_lines_still_draws_its_second_line_on_a_click(images):
    with random_util.use(random_util.Rng(5)):
        trend = KINDS["chart_trend"].build(
            {"title": "Me versus my cat", "line": "Me", "second_line": "My cat"}, {}, languages.LANGUAGES["en"]
        )
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, trend)
    slide_deck.theme = _theme("startup")
    presentation = render_pptx(slide_deck.to_deck())
    slide = presentation.slides[0]
    assert slide.element.find(qn("p:timing")) is not None
    (frame,) = [shape for shape in slide.shapes if shape.has_chart]
    assert frame.chart.chart_type == XL_CHART_TYPE.LINE


def test_previews_show_the_slides(images, tmp_path):
    theme = _theme("vintage paper")
    slide_deck = _deck(theme=theme)
    deck = slide_deck.to_deck()
    picture = preview.slide_image(deck.slides[0], theme, slide_deck.image_store(), width=480)
    assert picture.size == (480, 270)
    assert picture.getpixel((2, 135)) == color.rgb(theme.palette.background)
    paths = preview.save_previews(deck, tmp_path / "previews", slide_deck.image_store())
    assert [path.name for path in paths][-1] == "slides.png" and len(paths) == len(deck.slides) + 1
    with pytest.raises(ValueError, match="classic"):
        preview.contact_sheet(_deck().to_deck())


# THE GENERATOR


def test_the_generator_makes_themed_talks(monkeypatch, images):
    schema = test_seeds.fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    _, slide_deck, _ = generator.generate_presentation(
        schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False, theme="neon"
    )
    deck = slide_deck.to_deck()
    assert deck.theme.startswith("neon") and all(slide.layout.startswith("v5/") for slide in deck.slides)
    _, classic, _ = generator.generate_presentation(
        schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False
    )
    # The theme doesn't change what's on the slides
    texts = [[e.text for e in s.elements if isinstance(e, TextElement)] for s in classic.to_deck().slides]
    assert texts == [[e.text for e in s.elements if isinstance(e, TextElement)] for s in deck.slides]
    _, chaos, _ = generator.generate_presentation(
        schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False, theme="chaos"
    )
    assert all(slide.style is not None for slide in chaos.to_deck().slides)


def test_the_command_line_takes_a_theme():
    arguments = generator.get_argument_parser().parse_args(["--theme", "dark minimal", "--no_extreme_themes"])
    assert (arguments.theme, arguments.extreme_themes, arguments.style_chaos) == ("dark minimal", False, 0.0)
    assert generator.get_argument_parser().parse_args([]).theme is None  # (TALKGENERATOR_THEME's, or else random)


def test_the_default_theme_is_random_unless_the_settings_name_one(monkeypatch, images):
    schema = test_seeds.fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)

    def talk():
        _, slide_deck, _ = generator.generate_presentation(
            schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False
        )
        return slide_deck.to_deck()

    monkeypatch.delenv("TALKGENERATOR_THEME")
    assert settings.theme() == "random"
    assert talk().theme == themes.pick(themes.RANDOM, random_util.Rng(2).child("theme")).name  # (from the seed)
    monkeypatch.setenv("TALKGENERATOR_THEME", "neon")
    assert talk().theme.startswith("neon")
    monkeypatch.setenv("TALKGENERATOR_THEME", "classic")
    assert talk().theme == "classic"
    with pytest.raises(ValueError, match="There's no theme 'glitter'"):
        generator.generate_presentation(schema="fake", slides=3, topic="cats", save_ppt=False, theme="glitter")


def test_a_settings_menu_gets_every_theme_with_a_label_and_a_description():
    catalog = themes.catalog()
    assert [entry["name"] for entry in catalog] == ["random", "classic", "chaos", *themes.FAMILIES]
    assert set(themes.choices()) == {entry["name"] for entry in catalog}
    assert all(entry["label"] and entry["description"] for entry in catalog)
    assert {entry["name"] for entry in catalog if entry["extreme"]} == {
        name for name, family in themes.FAMILIES.items() if family.extreme
    }
    assert not any(entry["extreme"] for entry in themes.catalog(extremes=False))


def test_a_saved_themed_pptx_opens(images, tmp_path):
    slide_deck = _deck(theme=_theme("brutalist"))
    path = tmp_path / "themed.pptx"
    render_pptx(slide_deck.to_deck(), images=slide_deck.image_store()).save(path)
    assert len(Presentation(str(path)).slides) == len(_every_kind_of_slide())


# THE DESIGN CHECKS


def test_a_themed_deck_passes_the_design_checks(images):
    for family in FAMILIES:
        assert check_design(_deck(theme=_theme(family)).to_deck()) == [], family
    assert check_design(_deck().to_deck()) == []  # (a classic deck has no design to check)


def test_texts_that_dont_read_fit_or_stay_on_the_slide_are_found(images):
    deck = _deck(theme=_theme()).to_deck()
    slide = deck.slides[0]
    title = slide.element("title")

    def with_title(**changes):
        style = title.style.model_copy(update={key: value for key, value in changes.items() if key != "box"})
        changed = title.model_copy(update={"style": style, "box": changes.get("box", title.box)})
        elements = tuple(changed if element is title else element for element in slide.elements)
        return deck.model_copy(update={"slides": (slide.model_copy(update={"elements": elements}),)})

    def checks(changed):
        return [(finding.check, finding.severity) for finding in check_design(changed)]

    assert checks(with_title(color=slide.background.color)) == [("contrast", "error")]
    assert checks(with_title(size=400)) == [("overflow", "error")]
    assert checks(with_title(size=20)) == [("text size", "warning")]
    off = title.box.model_copy(update={"x": -40})
    assert checks(with_title(box=off)) == [("margins", "warning")]


def test_a_text_on_a_photo_needs_its_shade(images):
    deck = _deck(theme=_theme()).to_deck()
    statement = next(slide for slide in deck.slides if slide.type == "large_quote")
    unshaded = tuple(element for element in statement.elements if element.role != "shade")
    bare = deck.model_copy(update={"slides": (statement.model_copy(update={"elements": unshaded}),)})
    assert [finding.check for finding in check_design(bare)] == ["contrast"]  # white text on a picture: not always


# WORDART-STYLE HEADING EFFECTS


def _wordart(seed=0):
    return themes.pick("1997 WordArt", random_util.Rng(seed))


def _shape_of(ppt_slide, text):
    return next(shape for shape in ppt_slide.shapes if shape.has_text_frame and shape.text_frame.text == text)


def test_the_extremes_give_their_headings_effects():
    for seed in range(10):
        effect = _wordart(seed).heading_effect
        assert len(effect.fill) == 3 and effect.outline and effect.shadow and effect.warp in themes.WARPS
        # The rainbow reads on its outline, and the outline on the background
        assert all(color.contrast(stop, effect.outline) >= color.BODY_CONTRAST for stop in effect.fill)
    glowing = [themes.pick("neon", random_util.Rng(seed)).heading_effect for seed in range(20)]
    assert sum(effect is not None and effect.glow is not None for effect in glowing) >= 10
    assert all(themes.pick("clean keynote", random_util.Rng(seed)).heading_effect is None for seed in range(10))


def test_only_headings_get_the_effect(images):
    theme = _wordart()
    deck = _runs(theme=theme).to_deck()
    styles = {
        element.role: element.style
        for slide in deck.slides
        for element in slide.elements
        if isinstance(element, TextElement)
    }
    assert styles["title"].effect == theme.heading_effect
    assert styles["caption_1"].effect is None
    statement = next(slide for slide in deck.slides if slide.type == "large_quote").element("text").style
    assert statement.effect is not None and statement.effect.fill == ()  # (light on the shaded photo, not a rainbow)


def test_powerpoint_draws_wordart(images):
    theme = _wordart(3)
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, slides.ImageSlide("Cats rule", _image("wide")))
    slide_deck.theme = theme
    (ppt_slide,) = render_pptx(slide_deck.to_deck()).slides

    title = _shape_of(ppt_slide, "Cats rule")
    properties = title.text_frame.paragraphs[0].runs[0]._r.rPr
    tags = [child.tag.split("}")[1] for child in properties]
    assert tags[:3] == ["ln", "gradFill", "effectLst"] and tags.index("latin") > 2  # (in a run's properties' order)
    stops = [stop.get("val").lower() for stop in properties.find(qn("a:gradFill")).iter(qn("a:srgbClr"))]
    assert stops == [colour.lstrip("#") for colour in theme.heading_effect.fill]
    assert properties.find(qn("a:effectLst")).find(qn("a:outerShdw")) is not None
    warp = title.text_frame._bodyPr[0]
    assert warp.tag == qn("a:prstTxWarp") and warp.get("prst").startswith("text")


def test_neon_headings_glow(images):
    theme = next(
        member
        for member in (themes.pick("neon", random_util.Rng(seed)) for seed in range(20))
        if member.heading_effect is not None
    )
    slide_deck = SlideDeck(1, seed=1)
    slide_deck.add_slide(0, slides.ImageSlide("Cats rule", _image("wide")))
    slide_deck.theme = theme
    (ppt_slide,) = render_pptx(slide_deck.to_deck()).slides
    properties = _shape_of(ppt_slide, "Cats rule").text_frame.paragraphs[0].runs[0]._r.rPr
    assert properties.find(qn("a:effectLst")).find(qn("a:glow")) is not None


def test_an_outlined_heading_reads_by_its_outline(images):
    theme = _wordart()
    deck = _runs(theme=theme).to_deck()
    assert [finding for finding in check_design(deck) if finding.check == "contrast"] == []
    # Without its outline, a rainbow doesn't read on WordArt's loud backgrounds
    effect = theme.heading_effect.model_copy(update={"outline": None, "outline_width": 0.0})
    bare = _runs(theme=theme.model_copy(update={"heading_effect": effect})).to_deck()
    assert any(finding.check == "contrast" for finding in check_design(bare))


@pytest.mark.parametrize("seed", range(4))
def test_previews_draw_the_effects(images, seed):
    theme = _wordart(seed)
    slide = _deck(theme=theme).to_deck().slides[0]
    plain = slide.model_copy(
        update={
            "elements": tuple(
                element.model_copy(update={"style": element.style.model_copy(update={"effect": None})})
                if isinstance(element, TextElement)
                else element
                for element in slide.elements
            )
        }
    )
    assert preview.slide_image(slide, theme).tobytes() != preview.slide_image(plain, theme).tobytes()
