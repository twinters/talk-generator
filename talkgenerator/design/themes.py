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
    BackgroundStyle,
    Decoration,
    Fonts,
    ImageFilter,
    ImageFrame,
    Palette,
    TextEffect,
    Theme,
    Warp,
)
from talkgenerator.util import random_util

T = TypeVar("T")
Harmony = Literal["analogous", "complementary", "triadic", "mono"]
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
class Family:
    name: str
    dark: bool = False  # a dark background with light text
    hues: tuple[float, float] = (0, 360)
    harmony: Harmony = "complementary"
    background_saturation: tuple[float, float] = (0.0, 0.08)
    background_lightness: tuple[float, float] = (0.95, 0.99)
    accent_saturation: tuple[float, float] = (0.6, 0.85)
    fonts: tuple[tuple[str, str], ...] = (("Calibri", "Calibri"),)  # (heading, body) pairs of installed fonts
    open_fonts: tuple[tuple[str, str], ...] = ()  # (heading, body) pairs of open fonts (see OPEN_FONT_CHANCE)
    uppercase: float = 0.0  # the chance that headings are in capitals
    backgrounds: tuple[BackgroundStyle, ...] = ("solid",)
    decorations: tuple[Decoration, ...] = ("none",)
    alignments: tuple[Alignment, ...] = ("left",)
    image_border: float = 0.0  # the chance that images get a frame
    # Image treatments (see talkgenerator.design.treatments): filters and frames with how likely each is, and the
    # chances of grain and of a vignette
    image_filters: tuple[tuple[ImageFilter, float], ...] = (("none", 1.0),)
    image_frames: tuple[tuple[ImageFrame, float], ...] = (("none", 1.0),)
    image_grain: float = 0.0
    image_vignette: float = 0.0
    # WordArt-style effects on its headings: which kind, and the chance that a member has them
    heading_effect: HeadingEffect = "none"
    heading_effect_chance: float = 0.0
    text_scale: tuple[float, float] = (1.0, 1.0)
    extreme: bool = False
    weight: float = 1.0  # how often the random mix picks it
    description: str = ""  # what its members look like, for a settings menu


FAMILIES: Final[dict[str, Family]] = {
    family.name: family
    for family in (
        Family(
            "clean keynote",
            description="light and calm: a sans-serif, lots of room, an accent here and there",
            harmony="analogous",
            fonts=(("Calibri", "Calibri"), ("Arial", "Arial"), ("Trebuchet MS", "Calibri")),
            open_fonts=(("Barlow", "Barlow"), ("Atkinson Hyperlegible", "Atkinson Hyperlegible")),
            uppercase=0.2,
            decorations=("none", "underline"),
            alignments=("left", "center"),
            image_frames=(("none", 0.6), ("rounded", 0.4)),
        ),
        Family(
            "dark minimal",
            description="light text on a near-black background, now and then grayscale pictures",
            dark=True,
            background_saturation=(0.0, 0.15),
            background_lightness=(0.06, 0.12),
            accent_saturation=(0.5, 0.8),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Verdana")),
            open_fonts=(("IBM Plex Mono", "Barlow"), ("Titillium Web", "Titillium Web")),
            uppercase=0.4,
            decorations=("none", "underline"),
            image_filters=(("none", 0.6), ("grayscale", 0.4)),
            image_vignette=0.3,
        ),
        Family(
            "corporate",
            description="blues and greys, a bar by the titles, framed or duotone pictures",
            hues=(200, 230),
            background_saturation=(0.0, 0.1),
            background_lightness=(0.96, 0.99),
            accent_saturation=(0.55, 0.75),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Arial")),
            open_fonts=(("Poppins", "Lato"), ("Lato", "Lato")),
            decorations=("bar",),
            image_border=0.5,
            image_filters=(("none", 0.7), ("duotone", 0.3)),
        ),
        Family(
            "academic",
            description="a warm paper tone and serif type, as a lecture's slides",
            hues=(35, 55),
            harmony="mono",
            background_saturation=(0.2, 0.4),
            background_lightness=(0.93, 0.97),
            accent_saturation=(0.4, 0.6),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Times New Roman"), ("Cambria", "Calibri")),
            open_fonts=(("Crimson Text", "Crimson Text"), ("Spectral", "Spectral")),
            decorations=("underline", "bar"),
            text_scale=(0.9, 0.95),
            image_filters=(("none", 0.7), ("grayscale", 0.3)),
        ),
        Family(
            "startup",
            description="bold type, bright colours and rounded pictures",
            harmony="triadic",
            accent_saturation=(0.75, 0.95),
            fonts=(("Arial Black", "Arial"), ("Trebuchet MS", "Arial"), ("Verdana", "Verdana")),
            open_fonts=(("Poppins", "Poppins"), ("Archivo Black", "Poppins")),
            uppercase=0.3,
            backgrounds=("solid", "gradient"),
            decorations=("bar", "none"),
            alignments=("left", "center"),
            image_filters=(("none", 0.8), ("duotone", 0.2)),
            image_frames=(("rounded", 0.7), ("none", 0.3)),
        ),
        Family(
            "vintage paper",
            description="parchment, serif type, and sepia polaroids with grain",
            hues=(32, 48),
            harmony="mono",
            background_saturation=(0.3, 0.5),
            background_lightness=(0.82, 0.9),
            accent_saturation=(0.35, 0.55),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Georgia"), ("Courier New", "Courier New")),
            open_fonts=(("Abril Fatface", "Crimson Text"), ("Courier Prime", "Courier Prime")),
            decorations=("frame", "underline"),
            alignments=("center",),
            image_border=0.8,
            image_filters=(("sepia", 0.6), ("grayscale", 0.3), ("none", 0.1)),
            image_frames=(("none", 0.6), ("polaroid", 0.4)),
            image_grain=0.6,
            image_vignette=0.5,
        ),
        Family(
            "kids",
            description="bright colours, big friendly type, rounded and polaroid pictures",
            harmony="triadic",
            background_saturation=(0.6, 0.9),
            background_lightness=(0.86, 0.92),
            accent_saturation=(0.8, 1.0),
            fonts=(("Trebuchet MS", "Verdana"), ("Verdana", "Verdana"), ("Comic Sans MS", "Trebuchet MS")),
            open_fonts=(("Mali", "Mali"), ("Sniglet", "Mali")),
            decorations=("frame", "bar"),
            alignments=("center",),
            text_scale=(1.05, 1.1),
            image_frames=(("rounded", 0.5), ("polaroid", 0.4), ("none", 0.1)),
        ),
        Family(
            "brutalist",
            description="loud colours, heavy capitals, black-and-white pictures and hard shadows",
            background_saturation=(0.0, 0.9),
            background_lightness=(0.88, 0.95),
            accent_saturation=(0.9, 1.0),
            fonts=(("Arial Black", "Courier New"), ("Impact", "Arial"), ("Courier New", "Courier New")),
            open_fonts=(("Archivo Black", "IBM Plex Mono"), ("Space Mono", "IBM Plex Mono")),
            uppercase=0.8,
            decorations=("frame", "bar"),
            image_border=1.0,
            text_scale=(1.1, 1.15),
            image_filters=(("black and white", 0.4), ("grayscale", 0.4), ("none", 0.2)),
            heading_effect="hard shadow",
            heading_effect_chance=0.5,
        ),
        Family(
            "neon",
            description="glowing headings in neon colours on a dark background",
            dark=True,
            background_saturation=(0.3, 0.6),
            background_lightness=(0.04, 0.08),
            accent_saturation=(0.95, 1.0),
            fonts=(("Verdana", "Verdana"), ("Arial Black", "Arial"), ("Trebuchet MS", "Trebuchet MS")),
            open_fonts=(("Audiowide", "Chakra Petch"), ("Chakra Petch", "Chakra Petch")),
            uppercase=0.5,
            backgrounds=("solid", "gradient"),
            decorations=("underline", "frame"),
            image_filters=(("duotone", 0.6), ("none", 0.4)),
            image_frames=(("none", 0.7), ("rounded", 0.3)),
            image_vignette=0.3,
            heading_effect="glow",
            heading_effect_chance=0.8,
        ),
        # The extremes, for laughs
        Family(
            "1997 WordArt",
            description="rainbow WordArt headings bent into waves and arches, on a loud gradient",
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
            extreme=True,
            weight=0.5,
        ),
        Family(
            "Comic Sans everywhere",
            description="Comic Sans, outlined, on solid shadows, everywhere",
            harmony="triadic",
            background_saturation=(0.5, 0.8),
            background_lightness=(0.85, 0.92),
            fonts=(("Comic Sans MS", "Comic Sans MS"),),
            decorations=("frame", "bar", "none"),
            alignments=("center",),
            image_frames=(("polaroid", 0.5), ("rounded", 0.2), ("none", 0.3)),
            heading_effect="comic",
            heading_effect_chance=0.7,
            extreme=True,
            weight=0.5,
        ),
        Family(
            "clip-art corporate",
            description="a 1990s office deck: gradients, frames and soft shadows",
            hues=(200, 220),
            background_saturation=(0.3, 0.5),
            background_lightness=(0.78, 0.88),
            fonts=(("Times New Roman", "Arial"), ("Arial", "Times New Roman")),
            backgrounds=("gradient",),
            decorations=("bar",),
            image_border=1.0,
            image_filters=(("none", 0.7), ("duotone", 0.3)),
            image_frames=(("none", 0.6), ("rounded", 0.4)),
            heading_effect="clip art",
            heading_effect_chance=0.8,
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
    hue = random_util.uniform(*family.hues)
    background = color.hsl(
        hue, random_util.uniform(*family.background_saturation), random_util.uniform(*family.background_lightness)
    )
    first, second = _HARMONIES[family.harmony]
    saturation = random_util.uniform(*family.accent_saturation)
    style = random_util.choice(family.backgrounds)
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
    heading, body = random_util.choice(family.fonts)
    theme = Theme(
        name=f"{family.name} {number}",
        family=family.name,
        extreme=family.extreme,
        palette=Palette(
            background=background,
            surface=color.mix(background, text, 0.1),
            text=text,
            muted=color.readable_on(color.mix(text, background, 0.3), backgrounds, color.BODY_CONTRAST),
            accent=accent,
            accent_2=accent_2,
        ),
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
    image_grain = GRAIN if random_util.random() < family.image_grain else 0.0
    image_vignette = VIGNETTE if random_util.random() < family.image_vignette else 0.0
    effect = None
    if random_util.random() < family.heading_effect_chance:
        effect = _heading_effect(family.heading_effect, theme)
    # And the open fonts after everything else, for the same reason: they take the place of the installed pair
    fonts = theme.fonts
    if family.open_fonts and random_util.random() < OPEN_FONT_CHANCE:
        heading, body = random_util.choice(family.open_fonts)
        update = {"heading": heading, "body": body, "heading_bold": heading not in _HEAVY_FONTS}
        fonts = fonts.model_copy(
            update={**update, "heading_uppercase": fonts.heading_uppercase and heading not in _NO_CAPITALS}
        )
    return theme.model_copy(
        update={
            "image_filter": image_filter,
            "image_frame": image_frame,
            "image_grain": image_grain,
            "image_vignette": image_vignette,
            "heading_effect": effect,
            "fonts": fonts,
        }
    )


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
