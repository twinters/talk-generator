"""A theme's design tokens, as a deck keeps them (docs/v5-plan.md, section 9): its colours, fonts, background and
decoration. `talkgenerator.design.themes` makes them, from a family and the talk's seed."""

from __future__ import annotations

from typing import Literal

from talkgenerator.models.base import Data as _Data

BackgroundStyle = Literal["solid", "gradient"]
Decoration = Literal["none", "bar", "underline", "frame"]
Alignment = Literal["left", "center"]
# How pictures look in a theme: a filter (sepia and duotone map a picture's light onto two colours), and a frame
ImageFilter = Literal["none", "grayscale", "sepia", "duotone", "black and white"]
ImageFrame = Literal["none", "rounded", "polaroid"]
# WordArt's shapes for a heading: a wave, an arch, inflated in the middle, or slanting up
Warp = Literal["wave", "arch", "inflate", "slant"]


class Palette(_Data):
    background: str  # colours as "#rrggbb"
    surface: str  # panels, and bands behind texts on photos
    text: str
    muted: str  # captions and credits
    accent: str
    accent_2: str  # what stands out: a ranking's winner, a punchline


class TextEffect(_Data):
    """WordArt-style effects on a theme's headings: a gradient fill (its colours from the top of the text to its
    bottom, instead of one colour), an outline, a shadow and a glow (sizes in canvas pixels, opacities from 0 to 1),
    and a warp, the text bent into one of WordArt's shapes."""

    fill: tuple[str, ...] = ()
    outline: str | None = None
    outline_width: float = 0.0
    shadow: str | None = None
    shadow_offset: tuple[float, float] = (0.0, 0.0)  # right and down
    shadow_blur: float = 0.0
    shadow_opacity: float = 0.6
    glow: str | None = None
    glow_radius: float = 0.0
    warp: Warp | None = None


class Fonts(_Data):
    heading: str  # one of the fonts of talkgenerator.design.fonts
    body: str
    heading_bold: bool = True
    heading_uppercase: bool = False


class Theme(_Data):
    name: str  # such as "dark minimal 37": the family, and which of its members
    family: str
    extreme: bool = False  # one of the themes for laughs, such as 1997 WordArt
    palette: Palette
    fonts: Fonts
    background: BackgroundStyle = "solid"
    gradient_to: str | None = None  # the bottom colour of a gradient background
    decoration: Decoration = "none"
    title_align: Alignment = "left"
    image_border: bool = False
    text_scale: float = 1.0  # bigger or smaller type than the layouts' sizes
    # Image treatments, which give pictures from mixed sources one look: a filter, a frame (on pictures in a box, not
    # over a whole slide), and how much grain and vignette they get (from 0, none, to 1)
    image_filter: ImageFilter = "none"
    image_frame: ImageFrame = "none"
    image_grain: float = 0.0
    image_vignette: float = 0.0
    heading_effect: TextEffect | None = None  # WordArt-style effects on its titles and statements
