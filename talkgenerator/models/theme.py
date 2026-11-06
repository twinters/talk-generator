"""A theme's design tokens, as a deck keeps them (docs/v5-plan.md, section 9): its colours, fonts, background and
decoration. `talkgenerator.design.themes` makes them, from a family and the talk's seed."""

from __future__ import annotations

from typing import Literal

from talkgenerator.models.base import Data as _Data

BackgroundStyle = Literal["solid", "gradient"]
Decoration = Literal["none", "bar", "underline", "frame"]
Alignment = Literal["left", "center"]


class Palette(_Data):
    background: str  # colours as "#rrggbb"
    surface: str  # panels, and bands behind texts on photos
    text: str
    muted: str  # captions and credits
    accent: str
    accent_2: str  # what stands out: a ranking's winner, a punchline


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
