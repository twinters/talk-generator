"""Offline tests of themes and layouts (milestone 3): colours and contrast, measuring and fitting text, theme
families, the layout engine, and the renderers of themed decks (PowerPoint shapes, and previews)."""

import dataclasses
import itertools
import os
from pathlib import Path

import pytest
from PIL import ImageFont
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.oxml.ns import qn

from talkgenerator import generator, settings
from talkgenerator.checks.deck import deck_metrics
from talkgenerator.checks.design import check_design, check_variety
from talkgenerator.design import color, engine, fit, fonts, themes, treatments
from talkgenerator.models.deck import DECORATION, Deck, ImageElement, ShapeElement, TextElement
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS
from talkgenerator.render import embedding, preview
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.slide import slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import os_util, random_util
from tests import test_seeds
from tests.test_deck import _every_kind_of_slide, _image, _pie_chart_data
from tests.test_deck import images as images  # the fake image downloads (a fixture)
from tests.test_karaoke_types import KARAOKE, SHORT_CELLS, _axes, every_karaoke_type
from tests.test_karaoke_types import _longest as _karaoke_longest
from tests.test_picture_prompts import PROMPTS, every_picture_prompt
from tests.test_slide_types import EVERY_KIND, _built, _longest_texts
from tests.test_slide_types import _deck as _deck_of
from tests.test_slide_types import runs_of_new_types as _runs_of_new_types

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


_TWINS = {
    ("Arial", False): "LiberationSans-Regular.ttf",
    ("Arial", True): "LiberationSans-Bold.ttf",
    ("Times New Roman", False): "LiberationSerif-Regular.ttf",
    ("Times New Roman", True): "LiberationSerif-Bold.ttf",
    ("Courier New", False): "LiberationMono-Regular.ttf",
    ("Courier New", True): "LiberationMono-Bold.ttf",
    ("Calibri", False): "Carlito-Regular.ttf",
    ("Calibri", True): "Carlito-Bold.ttf",
    ("Cambria", False): "Caladea-Regular.ttf",
    ("Cambria", True): "Caladea-Bold.ttf",
    ("Georgia", False): "Gelasio-Regular.ttf",
    ("Georgia", True): "Gelasio-Bold.ttf",
}
_BUNDLED = Path(os_util.to_actual_file("data/fonts"))


def test_the_bundled_twins_measure_where_the_fonts_themselves_are_missing(monkeypatch):
    monkeypatch.setattr(fonts, "_font_folders", lambda: [_BUNDLED])  # (a computer without any fonts of its own)
    fonts._font_index.cache_clear()
    try:
        for (font, bold), twin in _TWINS.items():
            assert fonts.font_file(font, bold) == _BUNDLED / twin
        assert fonts.measured("Calibri") and fonts.font_file("Impact") is None  # (no open twin: see its width table)
    finally:
        fonts._font_index.cache_clear()


def _open_font_files():
    """The files of the open fonts themes use, by font."""
    return {font: sorted({*fonts.FONTS[font].regular, *fonts.FONTS[font].bold}) for font in fonts.OPEN_FONTS}


def test_every_bundled_font_is_credited_with_its_license():
    readme = (_BUNDLED / "README.md").read_text(encoding="utf-8")
    open_files = [name for names in _open_font_files().values() for name in names]
    assert sorted(path.name for path in _BUNDLED.glob("*.ttf")) == sorted([*_TWINS.values(), *open_files])
    assert all(name in readme for name in [*_TWINS.values(), *open_files]) and "widths.json" in readme
    licenses = ["LICENSE-Liberation.txt", "OFL-Carlito.txt", "LICENSE-Caladea.txt", "OFL-Gelasio.txt"]
    # (each open font's own: OFL-<its files' name>.txt)
    licenses += [f"OFL-{names[0].split('-')[0]}.txt" for names in _open_font_files().values()]
    for license_file in licenses:
        assert (_BUNDLED / license_file).is_file() and license_file in readme
    for license_file in licenses[4:]:
        assert "sil open font license version 1.1" in (_BUNDLED / license_file).read_text(encoding="utf-8").lower()


def test_the_open_fonts_are_static_truetype_fonts_that_allow_embedding():
    """(An EOT holds TrueType outlines; PowerPoint makes up a missing bold, wider than a real one: so a font with
    only a regular is a heading font that isn't made bolder, never a body, which some roles make bold)"""
    bodies = {body for family in themes.FAMILIES.values() for _, body in family.open_fonts}
    for font, stand_in in fonts.OPEN_FONTS.items():
        assert stand_in in fonts.FONTS and stand_in not in fonts.OPEN_FONTS
        regular, bold = fonts.font_file(font), fonts.font_file(font, bold=True)
        assert regular is not None and regular.parent == _BUNDLED and bold is not None and bold.parent == _BUNDLED
        facts = embedding.font_facts(regular.read_bytes())
        assert facts.truetype and not facts.variable and facts.fs_type == 0 and facts.weight == 400, font
        assert facts.names[1] == font and facts.names[2] == "Regular"  # (the name a run and PowerPoint look for)
        if bold == regular:
            assert font in themes._HEAVY_FONTS and font not in bodies, font
        else:
            bold_facts = embedding.font_facts(bold.read_bytes())
            assert bold_facts.truetype and not bold_facts.variable and bold_facts.fs_type == 0
            assert (bold_facts.names[1], bold_facts.names[2], bold_facts.weight) == (font, "Bold", 700), font


def test_a_text_in_an_open_font_fits_its_stand_in_too():
    for (font, stand_in), bold in itertools.product(fonts.OPEN_FONTS.items(), (False, True)):
        path = fonts.font_file(font, bold)
        own = ImageFont.truetype(str(path), 100, layout_engine=ImageFont.Layout.BASIC)
        for text in ("The quiet power of spreadsheets", _ACROSS_EUROPE, _ACROSS_EUROPE.upper()):
            width = fonts.text_width(text, font, 50, bold)
            assert width == pytest.approx(max(own.getlength(text), fonts.text_width(text, stand_in, 100, bold)) / 2)
    # (Barlow is narrower than Arial: its texts are as wide as Arial's; Poppins is wider: as wide as its own)
    assert fonts.text_width("Spreadsheets", "Barlow", 100) == fonts.text_width("Spreadsheets", "Arial", 100)
    assert fonts.text_width("Spreadsheets", "Poppins", 100) > fonts.text_width("Spreadsheets", "Arial", 100)


def test_the_twins_are_as_wide_as_the_fonts_they_stand_in_for():
    originals = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    files = {
        ("Arial", False): "arial.ttf",
        ("Arial", True): "arialbd.ttf",
        ("Times New Roman", False): "times.ttf",
        ("Times New Roman", True): "timesbd.ttf",
        ("Courier New", False): "cour.ttf",
        ("Courier New", True): "courbd.ttf",
        ("Calibri", False): "calibri.ttf",
        ("Calibri", True): "calibrib.ttf",
        ("Cambria", False): "cambria.ttc",
        ("Cambria", True): "cambriab.ttf",
        ("Georgia", False): "georgia.ttf",
        ("Georgia", True): "georgiab.ttf",
    }
    if not all((originals / name).is_file() for name in files.values()):
        pytest.skip("needs the original fonts to compare with (as Windows has them)")
    sentence = "The quick brown fox jumps over the lazy dog: Expectation vs Reality, 1997 WordArt?"
    for key, original in files.items():
        twin = ImageFont.truetype(str(_BUNDLED / _TWINS[key]), 100).getlength(sentence)
        assert twin == pytest.approx(ImageFont.truetype(str(originals / original), 100).getlength(sentence), rel=0.005)


# The fonts themes use that have no open twin: where they're missing, texts in them are measured with the widths of
# their characters, measured from their own files (data/fonts/widths.json)
_UNTWINNED = ("Arial Black", "Verdana", "Trebuchet MS", "Impact", "Comic Sans MS")
_ACROSS_EUROPE = "Brandweerkazernedeur — Über Größenwahn, «Œuvres», Ça va? 1,000,000,000 €"


def test_the_fonts_without_a_twin_are_measured_with_their_characters_widths(monkeypatch):
    monkeypatch.setattr(fonts, "_font_folders", lambda: [_BUNDLED])  # (a computer without any fonts of its own)
    fonts._font_index.cache_clear()
    try:
        for font, bold in itertools.product(_UNTWINNED, (False, True)):
            table = fonts.width_table(font, bold)
            assert fonts.font_file(font, bold) is None and table is not None and fonts.measured(font)
            for text in (_ACROSS_EUROPE, _ACROSS_EUROPE.upper()):
                assert fonts.text_width(text, font, 50, bold) == pytest.approx(sum(table[c] for c in text) / 2)
            # (wider in capitals, as the fonts are: an estimate from an average letter took them as wide)
            assert fonts.text_width("CAPITALS", font, 50, bold) > fonts.text_width("Capitals", font, 50, bold)
            # A character that isn't in the table is estimated, generously
            estimate = 100 * fonts.FONTS[font].average * (1.08 if bold else 1.0) * fonts.ESTIMATE_MARGIN
            assert fonts.text_width("Cat 猫", font, 100, bold) == pytest.approx(
                sum(table[c] for c in "Cat ") + estimate
            )
        assert fonts.width_table("Arial") is None and not fonts.measured("Papyrus")  # (a twin; no font of the themes)
    finally:
        fonts._font_index.cache_clear()


def test_the_width_tables_are_as_wide_as_the_fonts_they_stand_in_for():
    """(scripts/font_widths.py measures them, on a computer with the fonts: again, if the fonts change)"""
    originals = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    files = {
        (font, bold): (fonts.FONTS[font].bold if bold else fonts.FONTS[font].regular)[0]
        for font, bold in itertools.product(_UNTWINNED, (False, True))
    }
    if not all((originals / name).is_file() for name in files.values()):
        pytest.skip("needs the fonts themselves to compare with (as Windows has them)")
    sentence = "The quick brown fox jumps over the lazy dog: Expectation vs Reality, 1997 WordArt?"
    for (font, bold), name in files.items():
        original = ImageFont.truetype(str(originals / name), 100, layout_engine=ImageFont.Layout.BASIC)
        table = fonts.width_table(font, bold)
        for text in (sentence, _ACROSS_EUROPE, _ACROSS_EUROPE.upper()):
            assert sum(table[c] for c in text) == pytest.approx(original.getlength(text), rel=0.005), (font, bold)


def test_texts_are_measured_without_kerning_on_every_computer():
    """(Pillow kerns where it finds raqm, as on some Linux computers: so a text would get another size there, and
    another one than the width tables give it)"""
    assert fonts._truetype(str(_BUNDLED / "Carlito-Regular.ttf")).layout_engine == ImageFont.Layout.BASIC


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


def test_most_members_have_open_fonts_and_keep_everything_else_they_had(monkeypatch):
    members = {(name, seed): _theme(name, seed) for name in FAMILIES for seed in range(60)}
    members_chance = {name: family.open_font_chance for name, family in themes.FAMILIES.items()}
    default_chance = themes.OPEN_FONT_CHANCE
    monkeypatch.setattr(themes, "OPEN_FONT_CHANCE", 0.0)  # (as members were before there were open fonts)
    for name, family in themes.FAMILIES.items():  # (the families with a chance of their own, too)
        monkeypatch.setitem(themes.FAMILIES, name, dataclasses.replace(family, open_font_chance=None))
    before = {(name, seed): _theme(name, seed) for name in FAMILIES for seed in range(60)}
    for name, family in themes.FAMILIES.items():
        family = dataclasses.replace(family, open_font_chance=members_chance[name])
        open_members = [members[name, seed] for seed in range(60) if members[name, seed].fonts.body in fonts.OPEN_FONTS]
        if family.extreme:  # (their installed fonts are the joke)
            assert not family.open_fonts and not open_members
            continue
        chance = default_chance if family.open_font_chance is None else family.open_font_chance
        assert abs(len(open_members) / 60 - chance) <= 0.17, name  # (two in three, OPEN_FONT_CHANCE, or its own)
        assert {(theme.fonts.heading, theme.fonts.body) for theme in open_members} == set(family.open_fonts)
        assert all(theme.fonts.heading in fonts.OPEN_FONTS for theme in open_members)
        for seed in range(60):
            member, old = members[name, seed], before[name, seed]
            assert member.model_copy(update={"fonts": old.fonts}) == old, (name, seed)  # only the fonts changed
            # (in capitals as before, unless the font is too wide for them)
            capitals = old.fonts.heading_uppercase and member.fonts.heading not in themes._NO_CAPITALS
            assert member.fonts.heading_uppercase == capitals
            assert member.fonts.heading_bold == (member.fonts.heading not in themes._HEAVY_FONTS)


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
            if isinstance(element, ShapeElement):  # (a theme's decoration may reach beyond the slide: a sun, a hill)
                continue
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


def _pictured_punchlines(image):
    """Lists whose punchline is a picture in its text's place (a pattern break, D73): red flags (four, which fit their
    rows and their cards), reviews, an org chart's boss, a tier list's S tier and an alignment chart's chaotic evil;
    and lists and diagrams whose punchline is an emoji alone."""
    return [
        slides.RedFlagsSlide(
            "Red flags", "Hates naps", "Owns a dog", "Says 'meow' wrong", "x", pictures={"flag_4": image}
        ),
        slides.ReviewsSlide(
            "What people say", "5", "Purrfect.", "Ann", "4", "Fine.", "Bo", "1", "", "Cy", pictures={"review_3": image}
        ),
        slides.OrgChartSlide("Who's in charge", "The cat", "Me", "The dog", "The vet", pictures={"boss": image}),
        slides.TierListSlide(
            "Cat toys, ranked", "A box", "Yarn | Laser", "Mouse", None, "Bed", pictures={"s_tier": image}
        ),
        slides.AlignmentChartSlide("Cats", *_axes(), *SHORT_CELLS, pictures={"chaotic_evil": image}),
        # (and an emoji alone in a punchline's place, drawn as large as its box takes)
        slides.RedFlagsSlide("Red flags", "Hates naps", "Owns a dog", "Is a dog", "🦖"),
        slides.ReviewsSlide("What people say", "5", "Purrfect.", "Ann", "4", "Fine.", "Bo", "1", "🙄", "Cy"),
        slides.OrgChartSlide("Who's in charge", "🤯", "Me", "The dog", "The vet"),
        slides.TierListSlide("Cat toys, ranked", "🦄", "Yarn | Laser", "Mouse", None, "Bed"),
        slides.AlignmentChartSlide("Cats", *_axes(), *SHORT_CELLS[:-1], "😈"),
        slides.PyramidSlide("Needs", "🦆", "Naps", "Tuna"),
        slides.FunnelSlide("The funnel", "Cats", "Kittens", "Naps", "🧀"),
        slides.TimelineSlide("A history of cats", "1900", "Cats", "1950", "More cats", "Next year", "🚀"),
        slides.IcebergSlide("Just the tip", "Cats", "Naps", "🐙"),
        slides.FlowchartSlide(None, "Is it Tuesday?", "Feed the cat", "Ask the cat", "🎵"),
    ]


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
        # (milestone 6's types, with what every one of their layouts takes: short numbers, four options, a title...)
        *_runs_of_new_types(wide),
        # (and a meme, of a picture whose boxes talkgenerator doesn't know: its captions at its top and its bottom;
        # one, as memes have a layout of their own, and a talk at most one meme)
        slides.MemeSlide(wide, "When the cat", "Sits on the keyboard"),
        # (and the ones from PowerPoint karaoke decks, with a photo and without, few words and many...)
        *(every_karaoke_type(wide) * 3),
        # (and the slides of a picture to explain, D78: with pictures and an inkblot, a title and none)
        *(every_picture_prompt(wide, tall) * 3),
        # (and the talk formats' process, whose words are short enough to go across, or one under the other)
        *(slides.ProcessSlide("Method", "Collect cats", "Clean data", "???", "Profit") for _ in range(3)),
        # (and, from D65, closing slides with a picture to end on, and an academic talk's references, with a picture of
        # one of its works and without)
        *(slides.QuestionsSlide("Questions?", "Remember this one?", wide) for _ in range(3)),
        # (the one without a picture first: it fits one layout, which its neighbours avoid then)
        slides.ReferencesSlide("References", "Purr et al. (2021)", "Meow (2019)", "Whiskers et al. (2001)"),
        *(
            slides.ReferencesSlide(
                "References", "Purr et al. (2021)", "Meow (2019)", "Whiskers et al. (2001)", figure=tall, caption="[2]"
            )
            for _ in range(3)
        ),
        # (and, from D69, problem slides: without a picture first, as it fits one layout, then over a picture and
        # beside one)
        slides.ProblemSlide("The problem", "Cats keep sitting on keyboards.", "Every single day."),
        *(
            slides.ProblemSlide("The problem", "Cats keep sitting on keyboards.", "Every single day.", background=wide)
            for _ in range(3)
        ),
        *(
            slides.ProblemSlide("Sound familiar?", "Cats keep sitting on keyboards.", "Every single day.", photo=tall)
            for _ in range(3)
        ),
        # (and, from D73, lists whose punchline is a picture or an emoji in its text's place, one kind after the
        # other, twice)
        *(_pictured_punchlines(wide) * 2),
    ]
    slide_deck = SlideDeck(len(runs), title="Cats", topics=["cats"], seed=seed)
    for index, slide in enumerate(runs):
        slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")  # (credits on every layout)
        slide_deck.add_slide(index, slide)
    slide_deck.theme = theme
    return slide_deck


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_no_layout_comes_twice_in_a_row_and_every_one_passes_the_design_checks(images, family):
    for seed in range(3):
        deck = _runs(seed, _theme(family, seed)).to_deck()
        layouts = [slide.layout for slide in deck.slides]
        assert all(before != after for before, after in itertools.pairwise(layouts)), layouts
        assert check_design(deck) == [], (family, seed)


@pytest.mark.slow
def test_the_layouts_pass_the_design_checks_in_random_themes(images):
    for seed in range(20):
        theme = themes.pick(themes.RANDOM, random_util.Rng(seed))  # (extremes included)
        assert check_design(_runs(seed, theme).to_deck()) == [], (seed, theme.name)


@pytest.mark.slow
def test_every_layout_comes_up(images):
    seen = set()
    for seed in range(12):
        seen |= {slide.layout for slide in _runs(seed, _theme(seed=seed)).to_deck().slides}
    # (the deck has no title or diagram; and a clean keynote theme, none of another family's own layouts)
    assert set(engine.layout_names(_theme())) - {"v5/title", "v5/diagram"} <= seen


def test_a_slide_gets_the_layouts_that_fit_its_elements(images):
    def fitting(slide):
        return engine.layouts_for(slide.to_deck_slide())

    two = slides.TwoColumnImageSlide("Cats", "Expectation", _image("wide"), "Reality", "A quote, not a picture")
    assert fitting(two) == ["v5/columns-2", "v5/columns-2-headed", "v5/columns-2-rows", "v5/columns-2-split"]
    assert fitting(slides.FullImageSlide(None, _image("wide"))) == ["v5/full-image", "v5/full-image-framed"]
    titled = slides.FullImageSlide("Look at this", _image("wide"))
    assert fitting(titled) == ["v5/full-image", "v5/full-image-low", "v5/full-image-corner"]
    assert fitting(slides.ImageSlide(None, _image("wide"))) == ["v5/image-top"]  # (no title to put beside it)
    short, long = (slides.ImageSlide(title, _image("wide")) for title in ("Cats", "Vulkaanuitbarstingen"))
    assert fitting(short) == ["v5/image-top", "v5/image-side", "v5/image-side-right"]
    # A title with a word too long for the side goes across the top
    assert fitting(long) == ["v5/image-top"]
    chart = slides.ChartSlide("Kattenliefhebbersvereniging?", XL_CHART_TYPE.PIE, _pie_chart_data(), None)
    assert fitting(chart) == ["v5/chart"]
    # Swedish compounds as well (of 20 letters, "Kärnkraftsolyckornas" is no wider than the long word below)
    swedish, compound = (
        slides.ImageSlide(title, _image("wide")) for title in ("Pingvinernas liv", "Kärnkraftsolyckan")
    )
    assert (fitting(swedish), fitting(compound)) == (fitting(short), ["v5/image-top"])


# (A compound, as Dutch and German have them, can be wider than a narrow box even at the box's smallest size: a free
# model's "Mantelstromingen" didn't fit one)
_LONG_WORD = "Brandweerkazernedeur"
# (milestone 6's, the ones from PowerPoint karaoke decks and the slides of a picture to explain have tests of their own)
_OLDER_KINDS = [kind for kind in KINDS if kind not in EVERY_KIND and kind not in KARAOKE and kind not in PROMPTS]


def _with_long_words(kind):
    """A slide of the kind with a 20-letter word in every text, as long as the slide takes it (and in every answer of
    a pie chart, every bar of a ranking and every work of references), and a picture in every slot."""
    texts = _longest_texts(kind, _LONG_WORD)
    for name, count in (("categories", 5), ("bars", 6), ("items", 5)):
        if name in texts:
            texts[name] = " | ".join([_LONG_WORD] * count)
    return _built(kind, texts, {slot: _image("wide") for slot in KINDS[kind].images})


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_long_words_fit_the_older_layouts_in_every_theme(images, family):
    fitting = {kind: engine.layouts_for(_with_long_words(kind).to_deck_slide()) for kind in _OLDER_KINDS}
    # (each in a run as long as the layouts that fit it, so that every one of them comes up)
    made = [_with_long_words(kind) for kind in _OLDER_KINDS for _ in fitting[kind]]
    seen = set()
    for seed in range(3):
        deck = _deck_of(made, _theme(family, seed), seed)
        # (a title slide's layout is named for its theme's alignment, as v5/title-left)
        seen |= {"v5/title" if slide.type == "title" else slide.layout for slide in deck.slides}
        # (a Venn diagram's labels too: they go beside its circles, as they don't fit in them)
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], (family, seed)
    assert {layout for layouts in fitting.values() for layout in layouts} <= seen


def _with_fonts(theme, heading, body, uppercase=False):
    """The theme in other fonts (bold headings unless the heading font is heavy already, as members get them)."""
    update = {"heading": heading, "body": body, "heading_bold": heading not in themes._HEAVY_FONTS}
    return theme.model_copy(update={"fonts": theme.fonts.model_copy(update={**update, "heading_uppercase": uppercase})})


_OPEN_PAIRINGS = [(name, pair) for name, family in themes.FAMILIES.items() for pair in family.open_fonts]


@pytest.mark.parametrize(("family", "pair"), _OPEN_PAIRINGS, ids=[f"{n}: {h} over {b}" for n, (h, b) in _OPEN_PAIRINGS])
@pytest.mark.slow
def test_the_longest_texts_and_long_words_fit_in_every_open_pairing(images, family, pair):
    """(every pairing, not only the ones a few seeds give their members; headings as written, and in capitals where
    a member can have them)"""
    longest = [_built(kind, _longest_texts(kind), {"photo": _image("wide")}) for kind in EVERY_KIND]
    long_words = [_built(kind, _longest_texts(kind, _LONG_WORD), {"photo": _image("wide")}) for kind in EVERY_KIND]
    for photo in (_image("wide"), None):  # (the karaoke kinds, with an acronym's words as initials, and so on)
        longest += [_built(kind, _karaoke_longest(kind), {"photo": photo}) for kind in KARAOKE]
        long_words += [_built(kind, _karaoke_longest(kind, _LONG_WORD), {"photo": photo}) for kind in KARAOKE]
    older = [_with_long_words(kind) for kind in _OLDER_KINDS]
    capitals = themes.FAMILIES[family].uppercase > 0 and pair[0] not in themes._NO_CAPITALS
    for uppercase in (False, True) if capitals else (False,):
        theme = _with_fonts(_theme(family), *pair, uppercase=uppercase)
        assert check_design(_deck_of(longest, theme, 1)) == [], (family, pair, uppercase)
        deck = _deck_of(long_words + older, theme, 1)
        # (no exception for a Venn diagram's labels: they go beside its circles when they don't fit in them)
        assert [finding for finding in check_design(deck) if finding.check == "overflow"] == [], (
            family,
            pair,
            uppercase,
        )


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
    assert share("brutalist", lambda theme: theme.image_filter in ("black and white", "grayscale")) > 0.35
    assert share("neon", lambda theme: theme.image_filter == "duotone") > 0.3
    assert share("newspaper", lambda theme: theme.image_filter == "grayscale") > 0.6
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
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False, theme="neon"
    )
    deck = slide_deck.to_deck()
    assert deck.theme.startswith("neon") and all(slide.layout.startswith("v5/") for slide in deck.slides)
    _, classic, _ = generator._generate_presentation(
        schema="fake", slides=test_seeds.NUM_SLIDES, topic="cats", int_seed=2, save_ppt=False
    )
    # The theme doesn't change what's on the slides (but its decoration's own texts: a slide's number, say)
    texts = [[e.text for e in s.elements if isinstance(e, TextElement)] for s in classic.to_deck().slides]
    themed = [[e.text for e in s.elements if isinstance(e, TextElement) and e.role != DECORATION] for s in deck.slides]
    assert texts == themed
    _, chaos, _ = generator._generate_presentation(
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
        _, slide_deck, _ = generator._generate_presentation(
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
        generator._generate_presentation(schema="fake", slides=3, topic="cats", save_ppt=False, theme="glitter")


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
    findings = [finding for finding in check_design(bare) if "decoration" not in finding.message]
    assert [finding.check for finding in findings] == ["contrast"]  # white text on a picture: not always


# CREDITS: small, quiet and aligned right, without a band (D51)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.slow
def test_credits_are_small_quiet_and_right_aligned_without_a_band(images, family):
    deck = _runs(theme=_theme(family)).to_deck()
    credited = [slide for slide in deck.slides if slide.credits]
    assert credited and not any(element.role == "credits band" for slide in deck.slides for element in slide.elements)
    for slide in credited:
        style = slide.credits_style
        assert style is not None and style.size == engine.CREDITS_SIZE and style.align == "right"
        over_a_picture = engine.credits_over_picture(engine.credit_line(slide.credits), style, slide.elements)
        # (light with a halo over a picture, and where no colour reads: across a neon grid floor, say, which this
        # deck's credits on every slide have and a talk's don't: its slides without pictures have no credits)
        if over_a_picture or style.effect is not None:
            assert (style.color, style.effect) == (engine.CREDITS_ON_PICTURES, engine.CREDITS_HALO), slide.layout
            assert over_a_picture or not slide.images(), slide.layout
            continue
        # (quieter than any of the slide's texts: as far from what's behind it as it takes to read, and no further)
        behind = engine.credits_behind(engine.credit_line(slide.credits), style, slide.background, slide.elements)
        contrast = color.worst_contrast(style.color, behind)
        assert engine.CREDITS_CONTRAST <= contrast < color.BODY_CONTRAST, (slide.layout, contrast)


def test_credits_on_a_photo_read_by_their_halo(images):
    deck = _runs(theme=_theme()).to_deck()
    photo = next(
        slide
        for slide in deck.slides
        if slide.layout.startswith("v5/full-image") and slide.credits_style.effect is not None
    )
    assert engine.credits_over_picture(engine.credit_line(photo.credits), photo.credits_style, photo.elements)
    assert photo.credits_style.effect == engine.CREDITS_HALO
    bare = photo.model_copy(update={"credits_style": photo.credits_style.model_copy(update={"effect": None})})
    findings = check_design(deck.model_copy(update={"slides": (bare,)}))
    assert [finding.check for finding in findings if "credits" in finding.message] == ["contrast"]  # (a grey photo)


def test_the_credits_have_floors_of_their_own(images):
    deck = _deck(theme=_theme()).to_deck()
    slide = next(slide for slide in deck.slides if slide.credits and slide.credits_style.effect is None)

    def checks(**changes):
        style = slide.credits_style.model_copy(update=changes)
        changed = deck.model_copy(update={"slides": (slide.model_copy(update={"credits_style": style}),)})
        return [(finding.check, finding.severity) for finding in check_design(changed) if "credits" in finding.message]

    assert checks() == []  # (7 points, and a contrast of 2.5: quiet, and fine for credits)
    assert checks(color=slide.background.color) == [("contrast", "error")]
    assert checks(size=10) == [("text size", "warning")]


@pytest.mark.parametrize("family", [None, "clean keynote"], ids=["classic", "themed"])
def test_the_credits_links_keep_the_credits_colour_in_powerpoint(images, family):
    slide_deck = _deck(theme=_theme(family) if family else None)
    presentation = render_pptx(slide_deck.to_deck(), images=slide_deck.image_store())
    clicks = [
        click
        for ppt_slide in presentation.slides
        for click in ppt_slide.element.iter(qn("a:hlinkClick"))
        if click.getparent().getparent().getparent().tag == qn("a:p")  # (a run's)
    ]
    assert clicks
    for click in clicks:
        colour = click.find(f"{qn('a:extLst')}/{qn('a:ext')}/*")
        assert colour is not None and colour.tag.endswith("}hlinkClr") and colour.get("val") == "tx"


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


@pytest.mark.slow
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
