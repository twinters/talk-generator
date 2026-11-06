"""Themes: families of design tokens, and their members, made from the talk's seed (docs/v5-plan.md, section 9).

A family says what its members can be: how light their backgrounds are, which hues and colour harmony they use,
their font pairs, decoration and casing. A member picks from that with the seed, and then repairs its colours until
every text reads on its background (WCAG contrast: at least 4.5 for body text, 3 for titles). Some families are
extremes, for laughs ("1997 WordArt", "Comic Sans everywhere"): they're in the random mix unless left out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypeVar

from talkgenerator.design import color
from talkgenerator.models.theme import (
    Alignment,
    BackgroundStyle,
    Decoration,
    Fonts,
    ImageFilter,
    ImageFrame,
    Palette,
    Theme,
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
# How much grain and vignette a member's pictures get, if they get any
GRAIN: Final = 0.14
VIGNETTE: Final = 0.7


@dataclass(frozen=True)
class Family:
    name: str
    dark: bool = False  # a dark background with light text
    hues: tuple[float, float] = (0, 360)
    harmony: Harmony = "complementary"
    background_saturation: tuple[float, float] = (0.0, 0.08)
    background_lightness: tuple[float, float] = (0.95, 0.99)
    accent_saturation: tuple[float, float] = (0.6, 0.85)
    fonts: tuple[tuple[str, str], ...] = (("Calibri", "Calibri"),)  # (heading, body) pairs
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
    text_scale: tuple[float, float] = (1.0, 1.0)
    extreme: bool = False
    weight: float = 1.0  # how often the random mix picks it


FAMILIES: Final[dict[str, Family]] = {
    family.name: family
    for family in (
        Family(
            "clean keynote",
            harmony="analogous",
            fonts=(("Calibri", "Calibri"), ("Arial", "Arial"), ("Trebuchet MS", "Calibri")),
            uppercase=0.2,
            decorations=("none", "underline"),
            alignments=("left", "center"),
            image_frames=(("none", 0.6), ("rounded", 0.4)),
        ),
        Family(
            "dark minimal",
            dark=True,
            background_saturation=(0.0, 0.15),
            background_lightness=(0.06, 0.12),
            accent_saturation=(0.5, 0.8),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Verdana")),
            uppercase=0.4,
            decorations=("none", "underline"),
            image_filters=(("none", 0.6), ("grayscale", 0.4)),
            image_vignette=0.3,
        ),
        Family(
            "corporate",
            hues=(200, 230),
            background_saturation=(0.0, 0.1),
            background_lightness=(0.96, 0.99),
            accent_saturation=(0.55, 0.75),
            fonts=(("Arial", "Arial"), ("Calibri", "Calibri"), ("Verdana", "Arial")),
            decorations=("bar",),
            image_border=0.5,
            image_filters=(("none", 0.7), ("duotone", 0.3)),
        ),
        Family(
            "academic",
            hues=(35, 55),
            harmony="mono",
            background_saturation=(0.2, 0.4),
            background_lightness=(0.93, 0.97),
            accent_saturation=(0.4, 0.6),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Times New Roman"), ("Cambria", "Calibri")),
            decorations=("underline", "bar"),
            text_scale=(0.9, 0.95),
            image_filters=(("none", 0.7), ("grayscale", 0.3)),
        ),
        Family(
            "startup",
            harmony="triadic",
            accent_saturation=(0.75, 0.95),
            fonts=(("Arial Black", "Arial"), ("Trebuchet MS", "Arial"), ("Verdana", "Verdana")),
            uppercase=0.3,
            backgrounds=("solid", "gradient"),
            decorations=("bar", "none"),
            alignments=("left", "center"),
            image_filters=(("none", 0.8), ("duotone", 0.2)),
            image_frames=(("rounded", 0.7), ("none", 0.3)),
        ),
        Family(
            "vintage paper",
            hues=(32, 48),
            harmony="mono",
            background_saturation=(0.3, 0.5),
            background_lightness=(0.82, 0.9),
            accent_saturation=(0.35, 0.55),
            fonts=(("Georgia", "Georgia"), ("Times New Roman", "Georgia"), ("Courier New", "Courier New")),
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
            harmony="triadic",
            background_saturation=(0.6, 0.9),
            background_lightness=(0.86, 0.92),
            accent_saturation=(0.8, 1.0),
            fonts=(("Trebuchet MS", "Verdana"), ("Verdana", "Verdana"), ("Comic Sans MS", "Trebuchet MS")),
            decorations=("frame", "bar"),
            alignments=("center",),
            text_scale=(1.05, 1.1),
            image_frames=(("rounded", 0.5), ("polaroid", 0.4), ("none", 0.1)),
        ),
        Family(
            "brutalist",
            background_saturation=(0.0, 0.9),
            background_lightness=(0.88, 0.95),
            accent_saturation=(0.9, 1.0),
            fonts=(("Arial Black", "Courier New"), ("Impact", "Arial"), ("Courier New", "Courier New")),
            uppercase=0.8,
            decorations=("frame", "bar"),
            image_border=1.0,
            text_scale=(1.1, 1.15),
            image_filters=(("black and white", 0.4), ("grayscale", 0.4), ("none", 0.2)),
        ),
        Family(
            "neon",
            dark=True,
            background_saturation=(0.3, 0.6),
            background_lightness=(0.04, 0.08),
            accent_saturation=(0.95, 1.0),
            fonts=(("Verdana", "Verdana"), ("Arial Black", "Arial"), ("Trebuchet MS", "Trebuchet MS")),
            uppercase=0.5,
            backgrounds=("solid", "gradient"),
            decorations=("underline", "frame"),
            image_filters=(("duotone", 0.6), ("none", 0.4)),
            image_frames=(("none", 0.7), ("rounded", 0.3)),
            image_vignette=0.3,
        ),
        # The extremes, for laughs
        Family(
            "1997 WordArt",
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
            extreme=True,
            weight=0.5,
        ),
        Family(
            "Comic Sans everywhere",
            harmony="triadic",
            background_saturation=(0.5, 0.8),
            background_lightness=(0.85, 0.92),
            fonts=(("Comic Sans MS", "Comic Sans MS"),),
            decorations=("frame", "bar", "none"),
            alignments=("center",),
            image_frames=(("polaroid", 0.5), ("rounded", 0.2), ("none", 0.3)),
            extreme=True,
            weight=0.5,
        ),
        Family(
            "clip-art corporate",
            hues=(200, 220),
            background_saturation=(0.3, 0.5),
            background_lightness=(0.78, 0.88),
            fonts=(("Times New Roman", "Arial"), ("Arial", "Times New Roman")),
            backgrounds=("gradient",),
            decorations=("bar",),
            image_border=1.0,
            image_filters=(("none", 0.7), ("duotone", 0.3)),
            image_frames=(("none", 0.6), ("rounded", 0.4)),
            extreme=True,
            weight=0.5,
        ),
    )
}
# Fonts that are bold already: their headings aren't made bolder
_HEAVY_FONTS: Final = frozenset({"Impact", "Arial Black"})


def names(extremes: bool = True) -> list[str]:
    """The families' names, and what else --theme takes."""
    return [CLASSIC, RANDOM, *(name for name, family in FAMILIES.items() if extremes or not family.extreme)]


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
    # The image treatments come last, so that a seed's member has the colours, fonts and such it had before
    return theme.model_copy(
        update={
            "image_filter": _weighted(family.image_filters),
            "image_frame": _weighted(family.image_frames),
            "image_grain": GRAIN if random_util.random() < family.image_grain else 0.0,
            "image_vignette": VIGNETTE if random_util.random() < family.image_vignette else 0.0,
        }
    )


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
