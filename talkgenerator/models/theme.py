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
# Which of its pictures a theme's filter is for: all of them, or only those behind or across a whole slide (a
# statement's photo, a full-screen one), where it sets the mood, leaving pictures in boxes as they are
FilterScope = Literal["all", "backdrops"]
# WordArt's shapes for a heading: a wave, an arch, inflated in the middle, or slanting up
Warp = Literal["wave", "arch", "inflate", "slant"]
# How much a theme's slides move as they're presented (D83): not at all, a picture or a text now and then, or
# everything on every slide (for laughs)
Motion = Literal["none", "some", "lots"]
# PowerPoint's entrance effects that a slide's elements can come in with (D83): as PowerPoint names them, from the
# subtle to the exciting (talkgenerator.render.animation writes them as PowerPoint does, talk-generator-web plays them)
EntranceEffect = Literal[
    "fade",
    "wipe",
    "float_in",
    "rise_up",
    "zoom",
    "fly_in",
    "grow_turn",
    "swivel",
    "boomerang",
    "curve_up",
    "drop",
    "bounce",
    "spiral_in",
    "pinwheel",
    "flip",
]
# A family's own decoration, which its slides are drawn with besides their layout's shapes (see
# talkgenerator.design.motifs): a terminal window's frame and scanlines, a blueprint's grid and title block, crayon
# scenery, a chalkboard's wooden frame... (a family can have several, of which a member has one: a kindergarten's
# crayon drawings, sticker book, school notebook or paper cut-outs)
Motif = Literal[
    "none",
    "keynote",
    "minimal",
    "corporate",
    "lecture",
    "blobs",
    "ornate",
    "crayon",
    "stickers",
    "notebook",
    "cutouts",
    "brutal",
    "synthwave",
    "starburst",
    "comic",
    "swoosh",
    "terminal",
    "blueprint",
    "chalkboard",
    "newsprint",
    "swiss",
    "workshop",
    "desktop",
    "corkboard",
    "spreadsheet",
    "y2k",
    "seventies",
    "magazine",
]
# A pattern over a slide's background: lines across it (ruled paper's, a screen's scanlines), a grid (graph paper's, a
# blueprint's), or dots
PatternKind = Literal["lines", "grid", "dots"]


class BackgroundPattern(_Data):
    """A pattern drawn over a slide's background: lines across it (from the top down), a grid, or dots (in rows and
    columns), in a colour, this opaque, this far apart and this thick (a dot this wide), in canvas pixels; the first
    line (or row of dots) is offset from the top (and from the left), and with major, every major-th line of a grid
    (or of lines) is twice as thick."""

    kind: PatternKind
    color: str
    opacity: float = 0.1
    spacing: float = 40.0
    size: float = 2.0
    offset: float = 0.0
    major: int = 0


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
    # Image treatments, which give pictures from mixed sources one look: a filter (for all of them, or only for those
    # behind or across a whole slide), a frame (on pictures in a box, not over a whole slide), how much grain and
    # vignette they get (from 0, none, to 1), and a tint (a colour laid over them, this opaque)
    image_filter: ImageFilter = "none"
    image_filter_scope: FilterScope = "all"
    image_frame: ImageFrame = "none"
    image_grain: float = 0.0
    image_vignette: float = 0.0
    image_tint: str | None = None
    image_tint_opacity: float = 0.0
    heading_effect: TextEffect | None = None  # WordArt-style effects on its titles and statements
    # Its decoration (see talkgenerator.design.motifs: its family's, or one of its family's sets of decoration), a
    # member's variant of it (which corner its sun is in, say: the same on every slide), and the pattern over its
    # slides' backgrounds, if any
    motif: Motif = "none"
    motif_variant: int = 0
    pattern: BackgroundPattern | None = None
    # How much its slides move as they're presented (D83, see talkgenerator.design.entrances): not at all, now and then
    # a picture or a text that comes in with one of PowerPoint's entrance effects, or everything on every slide; and
    # the effects its members use
    motion: Motion = "none"
    entrances: tuple[EntranceEffect, ...] = ()
