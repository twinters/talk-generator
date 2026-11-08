"""Themes: families of design tokens, and their members, made from the talk's seed (docs/v5-plan.md, section 9).

A family says what its members can be: how light their backgrounds are, which hues and colour harmony they use,
their font pairs, decoration and casing. A member picks from that with the seed, and then repairs its colours until
every text reads on its background (WCAG contrast: at least 4.5 for body text, 3 for titles). Some families are
extremes, for laughs ("1997 WordArt", "Comic Sans everywhere"): they're in the random mix unless left out.

A family's fonts are pairs of fonts that nearly every computer has, and (most of the time, OPEN_FONT_CHANCE) a pair
of open fonts with more personality, which decks carry inside them (talkgenerator.design.fonts.OPEN_FONTS). The
extremes keep to the installed ones: Comic Sans MS, Impact and Arial Black are the joke.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal, TypeVar

from talkgenerator.design import color
from talkgenerator.models.theme import (
    Alignment,
    BackgroundPattern,
    BackgroundStyle,
    Decoration,
    FilterScope,
    Fonts,
    ImageFilter,
    ImageFrame,
    Motif,
    Palette,
    PatternKind,
    TextEffect,
    Theme,
    Warp,
)
from talkgenerator.util import random_util

T = TypeVar("T")
Harmony = Literal["analogous", "complementary", "triadic", "mono"]
# The gentle tints a family's pictures can have: none, a slight warm or cool cast, a wash of its background (its
# paper: pictures fade into the page a little), or of its accent
Tint = Literal["none", "warm", "cool", "paper", "accent"]
TINTS: Final[dict[str, tuple[str, float]]] = {"warm": ("#ff9a3c", 0.07), "cool": ("#3c8dff", 0.07)}
TINT_OPACITY: Final = {"paper": 0.1, "accent": 0.08}
SOFT_GRAIN: Final = 0.06
# Where an accent's hue lies, from the background's: the first accent, and the second
_HARMONIES: Final[dict[str, tuple[float, float]]] = {
    "analogous": (30, -30),
    "complementary": (180, 150),
    "triadic": (120, 240),
    "mono": (0, 0),
}
CLASSIC: Final = "classic"
RANDOM: Final = "random"
CHAOS: Final = "chaos"  # (every slide its own theme)
# How much grain and vignette a member's pictures get, if they get any
GRAIN: Final = 0.14
VIGNETTE: Final = 0.7
# WordArt's shapes, for the 1997 WordArt family's headings
WARPS: Final[tuple[Warp, ...]] = ("wave", "arch", "inflate", "slant")
# The kinds of heading effects a family can have (see _heading_effect)
HeadingEffect = Literal["none", "wordart", "glow", "hard shadow", "comic", "clip art"]
# How often a member of a family with open fonts has a pair of them (else a pair of the installed fonts)
OPEN_FONT_CHANCE: Final = 2 / 3


@dataclass(frozen=True)
class PatternSpec:
    """A family's background pattern (see talkgenerator.models.theme.BackgroundPattern), its colour one of the
    member's palette's (by name: "text", "accent"...) or a colour of its own."""

    kind: PatternKind
    color: str
    opacity: float
    spacing: float
    size: float
    offset: float = 0.0
    major: int = 0


@dataclass(frozen=True)
class Family:
    name: str
    dark: bool = False  # a dark background with light text
    hues: tuple[float, float] = (0, 360)
    harmony: Harmony = "complementary"
    background_saturation: tuple[float, float] = (0.0, 0.08)
    background_lightness: tuple[float, float] = (0.95, 0.99)
    accent_saturation: tuple[float, float] = (0.6, 0.85)
    # Palettes of its own, which its members pick from instead of colours from its hues (a family that commits to a
    # scheme: a terminal's phosphor green on black, a blueprint's blue): repaired until they read, as others are
    palettes: tuple[Palette, ...] = ()
    fonts: tuple[tuple[str, str], ...] = (("Calibri", "Calibri"),)  # (heading, body) pairs of installed fonts
    open_fonts: tuple[tuple[str, str], ...] = ()  # (heading, body) pairs of open fonts (see OPEN_FONT_CHANCE)
    open_font_chance: float | None = None  # how often a member has a pair of open fonts (else OPEN_FONT_CHANCE)
    uppercase: float = 0.0  # the chance that headings are in capitals
    backgrounds: tuple[BackgroundStyle, ...] = ("solid",)
    decorations: tuple[Decoration, ...] = ("none",)
    alignments: tuple[Alignment, ...] = ("left",)
    image_border: float = 0.0  # the chance that images get a frame
    # Image treatments (see talkgenerator.design.treatments): filters and frames with how likely each is, which
    # pictures a filter is for, the chances of grain (soft, or as strong as GRAIN) and of a vignette, and gentle
    # tints with how likely each is (most pictures stay as they are: the strong filters are for the families made
    # for them)
    image_filters: tuple[tuple[ImageFilter, float], ...] = (("none", 1.0),)
    filter_scope: FilterScope = "all"
    image_frames: tuple[tuple[ImageFrame, float], ...] = (("none", 1.0),)
    image_grain: float = 0.0
    grain: float = 0.14  # (GRAIN; SOFT_GRAIN for a family whose grain is soft)
    image_vignette: float = 0.0
    image_tints: tuple[tuple[Tint, float], ...] = (("none", 1.0),)
    # WordArt-style effects on its headings: which kind, and the chance that a member has them
    heading_effect: HeadingEffect = "none"
    heading_effect_chance: float = 0.0
    text_scale: tuple[float, float] = (1.0, 1.0)
    # Its own decoration (see talkgenerator.design.motifs), the patterns its members' backgrounds can have, each with
    # how likely it is (None: none), and the see-through tints of its palette's colours that its decoration lays under
    # texts (a startup's blobs: its accent at 15%), which its texts and accents are made to read on too
    motif: Motif = "none"
    tints_under_text: tuple[tuple[str, float], ...] = ()
    patterns: tuple[tuple[PatternSpec | None, float], ...] = ((None, 1.0),)
    extreme: bool = False
    weight: float = 1.0  # how often the random mix picks it
    description: str = ""  # what its members look like, for a settings menu


FAMILIES: Final[dict[str, Family]] = {
    family.name: family
    for family in (
        Family(
            "clean keynote",
            description="light and calm: a sans-serif, lots of room, a short accent bar over the titles",
            harmony="analogous",
            fonts=(("Calibri", "Calibri"), ("Arial", "Arial"), ("Trebuchet MS", "Calibri")),
            open_fonts=(("Barlow", "Barlow"), ("Atkinson Hyperlegible", "Atkinson Hyperlegible")),
            uppercase=0.2,
            decorations=("none", "underline"),
            alignments=("left", "center"),
            image_frames=(("none", 0.6), ("rounded", 0.4)),
            image_tints=(("none", 0.8), ("warm", 0.1), ("cool", 0.1)),
            motif="keynote",
            tints_under_text=(("accent", 0.08),),
        ),
        Family(
            "dark minimal",
            description="light text on a near-black background, a thin line by the titles, now and then grayscale "
            "backdrops",
            dark=True,
            background_saturation=(0.0, 0.15),
            background_lightness=(0.06, 0.12),
            accent_saturation=(0.5, 0.8),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Verdana")),
            open_fonts=(("IBM Plex Mono", "Barlow"), ("Titillium Web", "Titillium Web")),
            uppercase=0.4,
            decorations=("none", "underline"),
            image_filters=(("none", 0.6), ("grayscale", 0.4)),
            filter_scope="backdrops",
            image_vignette=0.3,
            motif="minimal",
        ),
        Family(
            "corporate",
            description="blues and greys, a band along the top, a slanted panel on its title slide, framed pictures "
            "with a cool cast",
            hues=(200, 230),
            background_saturation=(0.0, 0.1),
            background_lightness=(0.96, 0.99),
            accent_saturation=(0.55, 0.75),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Arial")),
            open_fonts=(("Poppins", "Lato"), ("Lato", "Lato")),
            decorations=("bar",),
            image_border=0.5,
            image_tints=(("none", 0.6), ("cool", 0.4)),
            motif="corporate",
        ),
        Family(
            "academic",
            description="a lecture's slides: serif type, titles on a band, a row of dots counting the slides",
            hues=(35, 55),
            harmony="mono",
            background_saturation=(0.2, 0.4),
            background_lightness=(0.93, 0.97),
            accent_saturation=(0.4, 0.6),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Times New Roman"), ("Cambria", "Calibri")),
            open_fonts=(("Crimson Text", "Crimson Text"), ("Spectral", "Spectral")),
            decorations=("none",),
            text_scale=(0.9, 0.95),
            image_tints=(("none", 0.6), ("paper", 0.4)),
            motif="lecture",
            patterns=((None, 0.7), (PatternSpec("grid", "accent", 0.06, 48, 1.5), 0.3)),
        ),
        Family(
            "startup",
            description="bold type, bright colours, soft blobs in the corners and rounded pictures",
            harmony="triadic",
            accent_saturation=(0.75, 0.95),
            fonts=(("Arial Black", "Arial"), ("Trebuchet MS", "Arial"), ("Verdana", "Verdana")),
            open_fonts=(("Poppins", "Poppins"), ("Archivo Black", "Poppins")),
            uppercase=0.3,
            backgrounds=("solid", "gradient"),
            decorations=("bar", "none"),
            alignments=("left", "center"),
            image_frames=(("rounded", 0.7), ("none", 0.3)),
            image_tints=(("none", 0.8), ("accent", 0.2)),
            motif="blobs",
            tints_under_text=(("accent", 0.15), ("accent_2", 0.12)),
        ),
        Family(
            "vintage paper",
            description="parchment in an ornamented double frame, serif type, and sepia polaroids with soft grain",
            hues=(32, 48),
            harmony="mono",
            background_saturation=(0.3, 0.5),
            background_lightness=(0.82, 0.9),
            accent_saturation=(0.35, 0.55),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Georgia"), ("Courier New", "Courier New")),
            open_fonts=(("Abril Fatface", "Crimson Text"), ("Courier Prime", "Courier Prime")),
            decorations=("none",),
            alignments=("center",),
            image_border=0.8,
            image_filters=(("sepia", 0.6), ("grayscale", 0.2), ("none", 0.2)),
            image_frames=(("none", 0.6), ("polaroid", 0.4)),
            image_grain=0.6,
            grain=SOFT_GRAIN,
            image_vignette=0.3,
            image_tints=(("none", 0.5), ("paper", 0.5)),
            motif="ornate",
        ),
        Family(
            "kids",
            description="a kindergarten's: crayon colours on cream, bunting, a sun and hills, stars and confetti, "
            "pictures as stickers",
            palettes=(
                Palette(
                    background="#fff6e9",
                    surface="#ffe9c7",
                    text="#1d1d1d",
                    muted="#4a4038",
                    accent="#ff5d73",
                    accent_2="#2ec4b6",
                ),
                Palette(
                    background="#eaf3ff",
                    surface="#d3e5ff",
                    text="#1b2a6b",
                    muted="#3a4a80",
                    accent="#ffb400",
                    accent_2="#ff5d73",
                ),
                Palette(
                    background="#fffbe0",
                    surface="#fff0a8",
                    text="#2b2d42",
                    muted="#4b4d63",
                    accent="#3a86ff",
                    accent_2="#ff006e",
                ),
                Palette(
                    background="#f1fbef",
                    surface="#d8f3d2",
                    text="#1f2a1f",
                    muted="#3f4a3c",
                    accent="#8e5ad8",
                    accent_2="#ff7a1a",
                ),
            ),
            fonts=(("Trebuchet MS", "Verdana"), ("Verdana", "Verdana"), ("Comic Sans MS", "Trebuchet MS")),
            open_fonts=(("Sniglet", "Mali"), ("Mali", "Mali")),
            open_font_chance=0.8,
            decorations=("none",),
            alignments=("center",),
            text_scale=(1.05, 1.1),
            image_frames=(("rounded", 1.0),),
            motif="crayon",
            patterns=((None, 0.6), (PatternSpec("dots", "accent", 0.1, 56, 10), 0.4)),
        ),
        Family(
            "brutalist",
            description="loud colours, heavy capitals, thick black outlines, hard shadows and black-and-white "
            "backdrops",
            background_saturation=(0.0, 0.9),
            background_lightness=(0.88, 0.95),
            accent_saturation=(0.9, 1.0),
            fonts=(("Arial Black", "Courier New"), ("Impact", "Arial"), ("Courier New", "Courier New")),
            open_fonts=(("Archivo Black", "IBM Plex Mono"), ("Space Mono", "IBM Plex Mono")),
            uppercase=0.8,
            decorations=("none",),
            image_border=1.0,
            text_scale=(1.1, 1.15),
            image_filters=(("black and white", 0.1), ("grayscale", 0.4), ("none", 0.5)),
            filter_scope="all",
            heading_effect="hard shadow",
            heading_effect_chance=0.5,
            motif="brutal",
        ),
        Family(
            "neon",
            description="glowing headings in neon colours on a dark background, a striped sun and a grid floor on "
            "its big slides",
            dark=True,
            background_saturation=(0.3, 0.6),
            background_lightness=(0.04, 0.08),
            accent_saturation=(0.95, 1.0),
            fonts=(("Verdana", "Verdana"), ("Arial Black", "Arial"), ("Trebuchet MS", "Trebuchet MS")),
            open_fonts=(("Audiowide", "Chakra Petch"), ("Chakra Petch", "Chakra Petch")),
            uppercase=0.5,
            backgrounds=("solid", "gradient"),
            decorations=("underline",),
            image_filters=(("duotone", 0.5), ("none", 0.5)),
            filter_scope="backdrops",
            image_frames=(("none", 0.7), ("rounded", 0.3)),
            image_vignette=0.3,
            image_tints=(("none", 0.6), ("accent", 0.4)),
            heading_effect="glow",
            heading_effect_chance=0.8,
            motif="synthwave",
        ),
        Family(
            "hacker terminal",
            description="green or amber phosphor on black, in a monospace font: a terminal window, scanlines, "
            "prompts and a status line",
            dark=True,
            palettes=(
                Palette(
                    background="#061006",
                    surface="#0e2210",
                    text="#33ff66",
                    muted="#7fbf93",
                    accent="#1fbf4c",
                    accent_2="#ffb000",
                ),
                Palette(
                    background="#0d0902",
                    surface="#221806",
                    text="#ffb000",
                    muted="#c9a05a",
                    accent="#d98e00",
                    accent_2="#ff5f3c",
                ),
                Palette(
                    background="#0a0e14",
                    surface="#141c27",
                    text="#c8d6e5",
                    muted="#8ea3ba",
                    accent="#50fa7b",
                    accent_2="#ff79c6",
                ),
            ),
            fonts=(("Courier New", "Courier New"),),
            open_fonts=(
                ("IBM Plex Mono", "IBM Plex Mono"),
                ("Space Mono", "IBM Plex Mono"),
                ("Courier Prime", "Courier Prime"),
            ),
            open_font_chance=0.8,
            uppercase=0.6,
            image_filters=(("duotone", 0.3), ("none", 0.7)),
            image_tints=(("none", 0.5), ("accent", 0.5)),
            motif="terminal",
            patterns=((PatternSpec("lines", "text", 0.05, 6, 2), 1.0),),
        ),
        Family(
            "blueprint",
            description="white lines on a blueprint's blue grid, technical capitals, dimension lines, a title block "
            "and figure plates, with a red pencil's corrections",
            dark=True,
            palettes=(
                Palette(
                    background="#173a66",
                    surface="#1f4a7c",
                    text="#eaf3ff",
                    muted="#9fc6ff",
                    accent="#9fc6ff",
                    accent_2="#ff8a7a",
                ),
                Palette(
                    background="#12305a",
                    surface="#1a3e6e",
                    text="#eaf3ff",
                    muted="#a8ccff",
                    accent="#bcd9ff",
                    accent_2="#ffd84a",
                ),
                Palette(
                    background="#1b4677",
                    surface="#24568d",
                    text="#f2f7ff",
                    muted="#b2d2ff",
                    accent="#cfe4ff",
                    accent_2="#ff9a8a",
                ),
            ),
            fonts=(("Arial", "Courier New"), ("Verdana", "Verdana"), ("Courier New", "Courier New")),
            open_fonts=(
                ("Titillium Web", "IBM Plex Mono"),
                ("Chakra Petch", "Titillium Web"),
                ("Barlow", "IBM Plex Mono"),
            ),
            uppercase=0.85,
            image_filters=(("duotone", 0.25), ("none", 0.75)),
            image_tints=(("none", 0.4), ("paper", 0.6)),
            motif="blueprint",
            patterns=((PatternSpec("grid", "#ffffff", 0.07, 24, 1.5, major=5), 1.0),),
        ),
        Family(
            "chalkboard",
            description="chalk on a dark green or slate board in a wooden frame: handwriting, chalk underlines, "
            "doodles, and pictures taped on",
            dark=True,
            palettes=(
                Palette(
                    background="#2a3b2f",
                    surface="#334637",
                    text="#f2f0e4",
                    muted="#c9cdbf",
                    accent="#e8d44d",
                    accent_2="#f4a7b9",
                ),
                Palette(
                    background="#2b2f33",
                    surface="#363b40",
                    text="#f2f0e4",
                    muted="#c4c8c9",
                    accent="#9ccbea",
                    accent_2="#f4a7b9",
                ),
                Palette(
                    background="#22362a",
                    surface="#2c4234",
                    text="#f2f0e4",
                    muted="#c6cfc2",
                    accent="#f4a7b9",
                    accent_2="#e8d44d",
                ),
            ),
            fonts=(("Comic Sans MS", "Comic Sans MS"), ("Trebuchet MS", "Trebuchet MS")),
            open_fonts=(("Mali", "Mali"), ("Sniglet", "Mali")),
            open_font_chance=0.85,
            uppercase=0.5,
            alignments=("left", "center"),
            text_scale=(1.0, 1.05),
            image_tints=(("none", 0.4), ("paper", 0.6)),
            motif="chalkboard",
        ),
        Family(
            "newspaper",
            description="a newspaper's front page: newsprint, a masthead with rules, bold serif headlines, red "
            "kickers and grayscale photos",
            palettes=(
                Palette(
                    background="#faf7f0",
                    surface="#efe9dc",
                    text="#1a1a1a",
                    muted="#4d4a45",
                    accent="#1a1a1a",
                    accent_2="#a61b1b",
                ),
                Palette(
                    background="#f2ece0",
                    surface="#e6decd",
                    text="#1c1915",
                    muted="#4f4840",
                    accent="#1c1915",
                    accent_2="#9b1c1c",
                ),
                Palette(
                    background="#fdeee2",
                    surface="#f6dcc8",
                    text="#1a1716",
                    muted="#55443b",
                    accent="#1a1716",
                    accent_2="#0d6b73",
                ),
            ),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Times New Roman"), ("Arial Black", "Georgia")),
            open_fonts=(("Abril Fatface", "Crimson Text"), ("Spectral", "Spectral")),
            uppercase=0.3,
            alignments=("center", "left"),
            image_filters=(("grayscale", 0.8), ("none", 0.2)),
            image_tints=(("paper", 1.0),),
            motif="newsprint",
        ),
        Family(
            "Swiss poster",
            description="the International Typographic Style: a grotesk flush left, a strict grid, black rules, "
            "one red block per slide, black-and-white photos",
            palettes=(
                Palette(
                    background="#f4f1ea",
                    surface="#e6e1d6",
                    text="#111111",
                    muted="#4d4d4d",
                    accent="#111111",
                    accent_2="#e32213",
                ),
                Palette(
                    background="#ffffff",
                    surface="#ececec",
                    text="#111111",
                    muted="#505050",
                    accent="#111111",
                    accent_2="#e32213",
                ),
                Palette(
                    background="#111111",
                    surface="#262626",
                    text="#f4f1ea",
                    muted="#b8b2a7",
                    accent="#f4f1ea",
                    accent_2="#ff3b2f",
                ),
                Palette(
                    background="#e32213",
                    surface="#c91d10",
                    text="#111111",
                    muted="#111111",
                    accent="#111111",
                    accent_2="#ffffff",
                ),
            ),
            fonts=(("Arial", "Arial"), ("Arial Black", "Arial")),
            open_fonts=(("Archivo Black", "Barlow"), ("Barlow", "Barlow")),
            text_scale=(1.05, 1.15),
            image_filters=(("grayscale", 0.5), ("none", 0.5)),
            motif="swiss",
        ),
        # The extremes, for laughs
        Family(
            "1997 WordArt",
            description="rainbow WordArt headings bent into waves and arches, on a loud gradient, with starbursts",
            background_saturation=(0.8, 1.0),
            background_lightness=(0.35, 0.55),
            accent_saturation=(0.9, 1.0),
            fonts=(("Impact", "Arial"), ("Arial Black", "Times New Roman")),
            uppercase=0.5,
            backgrounds=("gradient",),
            decorations=("frame",),
            alignments=("center",),
            text_scale=(1.05, 1.15),
            image_frames=(("none", 0.7), ("polaroid", 0.3)),
            heading_effect="wordart",
            heading_effect_chance=1.0,
            motif="starburst",
            extreme=True,
            weight=0.5,
        ),
        Family(
            "Comic Sans everywhere",
            description="Comic Sans, outlined, on solid shadows, everywhere: halftone dots, speech balloons and POW",
            harmony="triadic",
            background_saturation=(0.5, 0.8),
            background_lightness=(0.85, 0.92),
            fonts=(("Comic Sans MS", "Comic Sans MS"),),
            decorations=("none", "bar", "none"),
            alignments=("center",),
            image_frames=(("polaroid", 0.5), ("rounded", 0.2), ("none", 0.3)),
            heading_effect="comic",
            heading_effect_chance=0.7,
            motif="comic",
            patterns=((PatternSpec("dots", "accent", 0.14, 28, 9), 1.0),),
            extreme=True,
            weight=0.5,
        ),
        Family(
            "clip-art corporate",
            description="a 1990s office deck: gradients, frames, soft shadows and a swoosh along the bottom",
            hues=(200, 220),
            background_saturation=(0.3, 0.5),
            background_lightness=(0.78, 0.88),
            fonts=(("Times New Roman", "Arial"), ("Arial", "Times New Roman")),
            backgrounds=("gradient",),
            decorations=("bar",),
            image_border=1.0,
            image_frames=(("none", 0.6), ("rounded", 0.4)),
            heading_effect="clip art",
            heading_effect_chance=0.8,
            motif="swoosh",
            extreme=True,
            weight=0.5,
        ),
    )
}
# Fonts that are bold already, or display faces with no bold (PowerPoint would make one up, wider): their headings
# aren't made bolder
_HEAVY_FONTS: Final = frozenset({"Impact", "Arial Black", "Archivo Black", "Abril Fatface", "Audiowide", "Sniglet"})
# Display faces too wide in capitals for the longest titles, even at their smallest size: their headings aren't
# put in capitals
_NO_CAPITALS: Final = frozenset({"Audiowide"})

# The 2019 template's look, as tokens: white Calibri on black, its titles centred, with its accents (orange, which reads
# on black, and blue, which white reads on) and its dark grey for panels. A classic deck draws the slide types that the template has no layouts for (big numbers,
# quizzes...) as shapes in it (see talkgenerator.render.powerpoint); it's no theme a talk can ask for.
CLASSIC_LOOK: Final = Theme(
    name=CLASSIC,
    family=CLASSIC,
    palette=Palette(
        background="#000000",
        surface="#323232",
        text="#ffffff",
        muted="#bfbfbf",
        accent="#f07f09",
        accent_2="#1b587c",
    ),
    fonts=Fonts(heading="Calibri Light", body="Calibri", heading_bold=False),
    title_align="center",
)


def names(extremes: bool = True) -> list[str]:
    """The families' names, with classic and random."""
    return [CLASSIC, RANDOM, *(name for name, family in FAMILIES.items() if extremes or not family.extreme)]


def choices(extremes: bool = True) -> list[str]:
    """Every theme a talk can ask for (as --theme, TALKGENERATOR_THEME and generate_presentation take it)."""
    return [*names(extremes), CHAOS]


def catalog(extremes: bool = True) -> list[dict[str, Any]]:
    """The themes a talk can have, for a settings menu (talk-generator-web's, say): each with its name (what
    choices has), a label, a line on what it looks like, and whether it's one of the themes for laughs."""
    special = [
        (RANDOM, "Surprise me", "a theme of a family the talk's seed picks", False),
        (CLASSIC, "Classic", "the 2019 template", False),
        (CHAOS, "Chaos", "every slide in a theme of its own", False),
    ]
    families = [
        (name, name[0].upper() + name[1:], family.description, family.extreme)
        for name, family in FAMILIES.items()
        if extremes or not family.extreme
    ]
    return [
        {"name": name, "label": label, "description": description, "extreme": extreme}
        for name, label, description, extreme in [*special, *families]
    ]


def pick(spec: str, rng: random_util.Rng, extremes: bool = True) -> Theme | None:
    """The theme a spec asks for: None for the classic one, a member of a family by its name, or (for "random") of
    a family the seed picks, extremes included unless they're left out."""
    if spec == CLASSIC:
        return None
    with random_util.use(rng):
        if spec == RANDOM:
            pool = [family for family in FAMILIES.values() if extremes or not family.extreme]
            family = random_util.weighted_random([(family.weight, family) for family in pool]) or pool[0]
        elif spec in FAMILIES:
            family = FAMILIES[spec]
        else:
            raise ValueError(f"There's no theme {spec!r}; there are {', '.join(names())}")
        return member(family)


def member(family: Family) -> Theme:
    """A member of the family, from the current random stream."""
    number = random_util.randint(1, 999)
    style: BackgroundStyle = "solid"
    gradient_to: str | None = None
    if family.palettes:
        palette = _repaired(random_util.choice(family.palettes))
    else:
        palette, style, gradient_to = _generated(family)
    heading, body = random_util.choice(family.fonts)
    theme = Theme(
        name=f"{family.name} {number}",
        family=family.name,
        extreme=family.extreme,
        palette=palette,
        fonts=Fonts(
            heading=heading,
            body=body,
            heading_bold=heading not in _HEAVY_FONTS,
            heading_uppercase=random_util.random() < family.uppercase,
        ),
        background=style,
        gradient_to=gradient_to,
        decoration=random_util.choice(family.decorations),
        title_align=random_util.choice(family.alignments),
        image_border=random_util.random() < family.image_border,
        text_scale=round(random_util.uniform(*family.text_scale), 2),
    )
    # The image treatments come last, and the heading effects after them, so that a seed's member has the colours,
    # fonts and such it had before there were any
    image_filter = _weighted(family.image_filters)
    image_frame = _weighted(family.image_frames)
    image_grain = family.grain if random_util.random() < family.image_grain else 0.0
    image_vignette = VIGNETTE if random_util.random() < family.image_vignette else 0.0
    effect = None
    if random_util.random() < family.heading_effect_chance:
        effect = _heading_effect(family.heading_effect, theme)
    # The family's decoration, its pattern and its pictures' tint come from a stream of their own (one number of this
    # one's), so that the open fonts below, whichever pair they are, take nothing from them
    own = random_util.Rng(random_util.randint(0, 2**31))
    with random_util.use(own):
        motif_variant = random_util.randint(0, 9999)
        pattern = _pattern(_weighted(family.patterns), theme.palette)
        tint, tint_opacity = _tint(_weighted(family.image_tints), theme.palette)
    # And the open fonts after everything else, for the same reason: they take the place of the installed pair
    fonts = theme.fonts
    chance = OPEN_FONT_CHANCE if family.open_font_chance is None else family.open_font_chance
    if family.open_fonts and random_util.random() < chance:
        heading, body = random_util.choice(family.open_fonts)
        update = {"heading": heading, "body": body, "heading_bold": heading not in _HEAVY_FONTS}
        fonts = fonts.model_copy(
            update={**update, "heading_uppercase": fonts.heading_uppercase and heading not in _NO_CAPITALS}
        )
    palette = _reads_on_pattern(theme.palette, pattern, gradient_to, family.tints_under_text)
    return theme.model_copy(
        update={
            "palette": palette,
            "image_filter": image_filter,
            "image_filter_scope": family.filter_scope,
            "image_frame": image_frame,
            "image_grain": image_grain,
            "image_vignette": image_vignette,
            "image_tint": tint,
            "image_tint_opacity": tint_opacity,
            "heading_effect": effect,
            "motif": family.motif,
            "motif_variant": motif_variant,
            "pattern": pattern,
            "fonts": fonts,
        }
    )


def _generated(family: Family) -> tuple[Palette, BackgroundStyle, str | None]:
    """A palette from the family's hues, colour harmony and lightness (from the current random stream): its
    background, and a gradient's other end if it has one."""
    hue = random_util.uniform(*family.hues)
    background = color.hsl(
        hue, random_util.uniform(*family.background_saturation), random_util.uniform(*family.background_lightness)
    )
    first, second = _HARMONIES[family.harmony]
    saturation = random_util.uniform(*family.accent_saturation)
    style: BackgroundStyle = random_util.choice(family.backgrounds)
    gradient_to = None
    if style == "gradient":
        gradient_to = color.hsl(hue + first, *_gradient_end(background, family))
    base_text = color.hsl(hue, 0.15, 0.95 if family.dark else 0.12)
    backgrounds = [background]
    text = color.readable_on(base_text, backgrounds, 7.0)
    for _ in range(6):  # a gradient no text reads on all of goes less far, until one does (or it's gone)
        if gradient_to is None:
            break
        backgrounds = [background, gradient_to]
        text = color.readable_on(base_text, backgrounds, 7.0)
        if color.worst_contrast(text, backgrounds) >= color.BODY_CONTRAST:
            break
        gradient_to = color.mix(gradient_to, background, 0.5)
    else:
        gradient_to, backgrounds = None, [background]
        text = color.readable_on(base_text, backgrounds, 7.0)
    if gradient_to is None:
        style = "solid"
    accent = color.readable_on(color.hsl(hue + first, saturation, 0.6 if family.dark else 0.42), backgrounds, 3.0)
    accent_2 = color.readable_on(
        color.hsl(hue + second + 40, saturation, 0.62 if family.dark else 0.45), backgrounds, 3.0
    )
    palette = Palette(
        background=background,
        surface=color.mix(background, text, 0.1),
        text=text,
        muted=color.readable_on(color.mix(text, background, 0.3), backgrounds, color.BODY_CONTRAST),
        accent=accent,
        accent_2=accent_2,
    )
    return palette, style, gradient_to


def _repaired(palette: Palette) -> Palette:
    """A family's own palette, its colours made lighter or darker where they don't read on its background (its text
    and muted text at 4.5, its accents at 3), and its text on its surface too."""
    backgrounds = [palette.background, palette.surface]
    return palette.model_copy(
        update={
            "text": color.readable_on(palette.text, backgrounds),
            "muted": color.readable_on(palette.muted, backgrounds),
            "accent": color.readable_on(palette.accent, [palette.background], color.LARGE_TEXT_CONTRAST),
            "accent_2": color.readable_on(palette.accent_2, [palette.background], color.LARGE_TEXT_CONTRAST),
        }
    )


def _reads_on_pattern(
    palette: Palette,
    pattern: BackgroundPattern | None,
    gradient_to: str | None,
    tints: tuple[tuple[str, float], ...] = (),
) -> Palette:
    """The palette, its texts and accents made lighter or darker where they don't read on its background's pattern
    too (dots of its accent, a grid's lines), and on the tints its decoration lays under texts, as they read on its
    background."""
    if pattern is None and not tints:
        return palette
    plain = [palette.background, *([gradient_to] if gradient_to else [])]
    backgrounds = list(plain)
    if pattern is not None:
        backgrounds += [color.mix(colour, pattern.color, pattern.opacity) for colour in plain]
    for name, opacity in tints:
        backgrounds += [color.mix(colour, getattr(palette, name), opacity) for colour in plain]
    return palette.model_copy(
        update={
            "text": color.readable_on(palette.text, backgrounds),
            "muted": color.readable_on(palette.muted, backgrounds),
            "accent": color.readable_on(palette.accent, backgrounds, color.LARGE_TEXT_CONTRAST),
            "accent_2": color.readable_on(palette.accent_2, backgrounds, color.LARGE_TEXT_CONTRAST),
        }
    )


def _pattern(spec: PatternSpec | None, palette: Palette) -> BackgroundPattern | None:
    if spec is None:
        return None
    colour = spec.color if spec.color.startswith("#") else getattr(palette, spec.color)
    return BackgroundPattern(
        kind=spec.kind,
        color=colour,
        opacity=spec.opacity,
        spacing=spec.spacing,
        size=spec.size,
        offset=spec.offset,
        major=spec.major,
    )


def _tint(kind: Tint, palette: Palette) -> tuple[str | None, float]:
    """A tint's colour and opacity, in the palette (none for none)."""
    if kind in TINTS:
        return TINTS[kind]
    if kind == "paper":
        return palette.background, TINT_OPACITY["paper"]
    if kind == "accent":
        return palette.accent, TINT_OPACITY["accent"]
    return None, 0.0


def _heading_effect(kind: HeadingEffect, theme: Theme) -> TextEffect | None:
    """A family's kind of heading effect, in the member's colours. A heading reads on what's behind it (the
    background, and the bands behind titles on photos), by its fill or by its outline: an outline that reads on the
    background, around a fill that reads on the outline (see talkgenerator.checks.design)."""
    palette = theme.palette
    backgrounds = [palette.background, palette.surface, *([theme.gradient_to] if theme.gradient_to else [])]
    if kind == "wordart":  # a rainbow in a black or white outline, with a drop shadow, bent into a WordArt shape
        outline = max(("#1a1a1a", "#ffffff"), key=lambda extreme: color.worst_contrast(extreme, backgrounds))
        hue = color.to_hsl(palette.accent)[0]
        rainbow = tuple(
            color.readable_on(color.hsl(hue + turn, 0.95, 0.55), [outline], color.BODY_CONTRAST)
            for turn in (0, 70, 140)
        )
        return TextEffect(
            fill=rainbow,
            outline=outline,
            outline_width=4,
            shadow="#000000",
            shadow_offset=(8, 8),
            shadow_blur=4,
            shadow_opacity=0.55,
            warp=random_util.choice(WARPS),
        )
    if kind == "glow":  # a neon sign's
        return TextEffect(glow=palette.accent, glow_radius=16)
    if kind == "hard shadow":  # a solid block, offset
        return TextEffect(shadow=palette.accent_2, shadow_offset=(8, 8), shadow_opacity=1.0)
    if kind == "comic":  # the text in a light outline, on a solid shadow
        lightest = max((palette.text, palette.background, "#ffffff"), key=color.luminance)
        return TextEffect(
            outline=lightest, outline_width=3, shadow=palette.accent, shadow_offset=(6, 6), shadow_opacity=1.0
        )
    if kind == "clip art":  # a gradient from the text's colour towards the accent, with a soft shadow
        tinted = color.readable_on(color.mix(palette.text, palette.accent, 0.6), backgrounds, color.LARGE_TEXT_CONTRAST)
        return TextEffect(
            fill=(tinted, palette.text), shadow="#000000", shadow_offset=(5, 5), shadow_blur=6, shadow_opacity=0.45
        )
    return None


def _weighted(choices: tuple[tuple[T, float], ...]) -> T:
    return random_util.weighted_random([(weight, choice) for choice, weight in choices]) or choices[0][0]


def _gradient_end(background: str, family: Family) -> tuple[float, float]:
    """The saturation and lightness a gradient goes to: a little further from the text's colour."""
    _, saturation, lightness = color.to_hsl(background)
    if family.dark:
        return saturation, max(0.0, lightness - 0.04)
    if family.extreme:
        return min(1.0, saturation + 0.1), max(0.2, lightness - 0.15)
    return saturation, max(0.0, lightness - 0.08)
