"""The deck format: a generated talk as plain data.

Every renderer draws a deck: for now the PowerPoint renderer (`talkgenerator.render.powerpoint`), later the browser
view on talkgenerator.com. So a deck holds no image bytes, python-pptx objects or callbacks, only JSON-serializable
data, and `deck_version` changes whenever the format changes in a way older readers can't handle.

A slide has a type and a layout. Its content is a list of elements, each with a role that the layout knows where to
put ("title", "caption_1", "content_1", ...), so a layout or theme can change without changing the content. A text,
picture or shape can appear on a click of its slide instead of with it (`appears_on_click`), such as a quiz's answer:
a renderer that plays no clicks shows it from the start.

In a deck with a theme other than the classic one, every element also has its place (a box on a 1920×1080
canvas) and every text its style, as the layout engine (`talkgenerator.design.engine`) put them: so every
renderer draws such a deck the same way. A classic deck's elements go in the 2019 template's placeholders.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data as _Data
from talkgenerator.models.theme import ImageFilter, ImageFrame, TextEffect, Theme
from talkgenerator.models.usage import Usage

DECK_VERSION: Final = 1

ImageFit = Literal["contain", "cover"]
ChartType = Literal["pie", "doughnut", "column", "bar", "line", "scatter"]
# How a chart appears: all at once, or the series after the first on clicks, one by one
ChartReveal = Literal["all", "series"]
# How a diagram appears: all at once, or without its punchline, which appears on a click
DiagramReveal = Literal["all", "punchline"]
# How a browser may show an image, as its source's terms (and its server) allow:
# - direct: from its url (and video_url), as Unsplash and GIPHY require
# - proxy: through a pass-through proxy that keeps nothing, which adds what the source asks requests to carry (the
#   Art Institute of Chicago refuses requests without its AIC-User-Agent header, which an <img> tag can't send)
# - copy: from a copy of the app's own, kept as long as the deck, or not at all: Pixabay doesn't allow hotlinking for
#   good, and its image links stop working after 24 hours
# - local: a file of talkgenerator's own (or a plan's), which the app serves
DisplayPolicy = Literal["direct", "proxy", "copy", "local"]
# The license class of an image (see talkgenerator.images.licenses): public domain and CC0; Creative Commons BY and
# BY-SA; the stock licenses of Unsplash, Pexels and Pixabay; AI images, under their provider's terms; and fair use
# (Reddit's posts, GIPHY's gifs, Imgflip's meme templates, InspiroBot's posters, ShitpostBot's images)
LicenseClass = Literal["public-domain", "open", "stock", "generated", "fair-use"]
TextAlign = Literal["left", "center", "right"]
TextAnchor = Literal["top", "middle", "bottom"]
ShapeKind = Literal["rectangle", "ellipse"]


class Box(_Data):
    """A place on the 1920×1080 canvas, in pixels from its top left corner (a pixel is half a point)."""

    x: float
    y: float
    w: float
    h: float


class TextStyle(_Data):
    """How a text looks: its font and size (in canvas pixels), colour ("#rrggbb") and place in its box."""

    font: str
    size: float
    color: str
    bold: bool = False
    italic: bool = False
    uppercase: bool = False
    align: TextAlign = "left"
    anchor: TextAnchor = "top"
    effect: TextEffect | None = None  # (a heading's, in a theme with WordArt-style effects)


class CreditPart(_Data):
    """A piece of a credit as it reads on a slide, and the page it links to (if any)."""

    text: str
    url: str | None = None


Credit = tuple[CreditPart, ...]


class ImageAnalysis(_Data):
    """What a look at an image's thumbnail found (see talkgenerator.images.analysis), from 0 to 1: how light it is,
    how colourful, how much of it is without colour (gray), whether it's all one colour (gray, or a tint such as
    sepia), and how much detail it has where a slide's text goes over it (if it does); its main colours, most first;
    and a perceptual hash (16 hex digits), which near-duplicates share but for a few bits."""

    brightness: float
    colourfulness: float
    grayscale: float
    monochrome: bool
    detail: float | None = None
    colors: tuple[str, ...] = ()
    hash: str = ""


class ImageAsset(_Data):
    """An image, and where it came from. The url is a web address or a local path."""

    url: str
    # A video that plays in the image's place, by itself, looping and without sound, with the image as its poster
    # frame: a gif too large to embed comes as its mp4 copy (and a renderer that plays no videos shows the image)
    video_url: str | None = None
    source: str | None = None
    source_url: str | None = None
    credit: Credit = ()
    query: str | None = None  # the search that found it, for an image a plan asked for
    description: str | None = None  # what it shows, as its source describes it (for alt text, say)
    display: DisplayPolicy = "direct"  # how a browser may show it (a PowerPoint embeds it whatever it says)
    # Its size in pixels, as the check that let it on the slide found it (none if it didn't tell): for a browser to
    # place a picture before it has loaded it
    width: int | None = None
    height: int | None = None
    # Its license class, and its license as its credit names it, with the license's page (none for a file of
    # talkgenerator's own or a plan's, and no license for fair use)
    license_class: LicenseClass | None = None
    license: str | None = None
    license_url: str | None = None
    # The look it was found for (an aesthetic profile: see talkgenerator.images.profiles), and what a look at it found
    look: str | None = None
    analysis: ImageAnalysis | None = None


# The click of its slide on which an element appears (the first is 1), when it isn't there from the start: a quiz's
# answer, say, or the punchline of a row of figures. Elements with the same click appear together, fading in
AppearsOnClick = Annotated[int | None, Field(ge=1)]


class TextElement(_Data):
    kind: Literal["text"] = "text"
    role: str
    text: str
    box: Box | None = None
    style: TextStyle | None = None
    appears_on_click: AppearsOnClick = None


class ImageTreatment(_Data):
    """How a theme treats a picture (see talkgenerator.design.treatments): a filter, with a duotone's (or sepia's)
    colours, from what's darkest in the picture to what's lightest; a frame, a polaroid's tilted by a few degrees
    (clockwise); and grain and a vignette, from 0 (none) to 1. Renderers apply it their own way (PowerPoint with its
    picture effects), and the deck keeps the original picture."""

    filter: ImageFilter = "none"
    dark: str | None = None
    light: str | None = None
    frame: ImageFrame = "none"
    tilt: float = 0.0
    grain: float = 0.0
    vignette: float = 0.0


class ImageElement(_Data):
    kind: Literal["image"] = "image"
    role: str
    image: ImageAsset
    # contain: the whole image, padded to fit its frame; cover: the image fills its frame, cropped where needed
    fit: ImageFit = "contain"
    box: Box | None = None
    border: str | None = None  # a frame around the image, in this colour ("#rrggbb")
    treatment: ImageTreatment | None = None  # (in a themed deck)
    appears_on_click: AppearsOnClick = None


class ChartSeries(_Data):
    name: str = ""
    values: tuple[float, ...] = ()  # one per category
    points: tuple[tuple[float, float], ...] = ()  # (x, y) pairs, for scatter charts
    # Names on some of its points, by index ("" for none), on line and scatter charts: a moment on a trend, say
    labels: tuple[str, ...] = ()


class ChartSpec(_Data):
    chart_type: ChartType
    categories: tuple[str, ...] = ()
    series: tuple[ChartSeries, ...] = ()
    # The titles of the axes, on charts that have axes: what the chart goes along (its categories, or its x values),
    # and what it measures (its values, or its y values)
    x_title: str = ""
    y_title: str = ""
    reveal: ChartReveal = "all"  # "series": the series after the first appear on clicks, one by one


class ChartElement(_Data):
    kind: Literal["chart"] = "chart"
    role: str
    chart: ChartSpec
    box: Box | None = None


class ShapeElement(_Data):
    """A shape a theme draws: an accent bar, a band behind a title, a shade over a photo."""

    kind: Literal["shape"] = "shape"
    role: str = "decoration"
    shape: ShapeKind = "rectangle"
    box: Box
    color: str
    opacity: float = 1.0  # from 0 (not there) to 1 (solid)
    appears_on_click: AppearsOnClick = None


class SlideBackground(_Data):
    """A slide's background: a colour, or a gradient from it at the top to color_2 at the bottom."""

    color: str
    color_2: str | None = None


class VennDiagram(_Data):
    """Two or three overlapping circles, each with a label, and a label where they all overlap: the punchline."""

    diagram_type: Literal["venn"] = "venn"
    circles: tuple[str, ...] = ()  # the circles' labels: two or three
    overlap: str = ""
    reveal: DiagramReveal = "all"

    def labels(self) -> tuple[tuple[str, str], ...]:
        """Its texts, each with what it is."""
        return (
            *((f"circle {number}", label) for number, label in enumerate(self.circles, 1)),
            ("overlap", self.overlap),
        )


class MatrixDiagram(_Data):
    """A 2×2 matrix: two axes that cross in its middle, with a title at each end, a label in each quadrant, and one
    dot with a name, the punchline."""

    diagram_type: Literal["matrix"] = "matrix"
    # The titles at the ends of the axes: of the one along the bottom (left and right), and of the one going up
    x_left: str = ""
    x_right: str = ""
    y_bottom: str = ""
    y_top: str = ""
    top_left: str = ""
    top_right: str = ""
    bottom_left: str = ""
    bottom_right: str = ""
    dot: str = ""
    # Where the dot is, along each axis: from its left end (0) to its right end (1), and from the bottom (0) to the top
    # (1); the axes cross at 0.5
    dot_x: float = Field(0.5, ge=0, le=1)
    dot_y: float = Field(0.5, ge=0, le=1)
    reveal: DiagramReveal = "all"

    def labels(self) -> tuple[tuple[str, str], ...]:
        """Its texts, each with what it is."""
        return (
            ("left end", self.x_left),
            ("right end", self.x_right),
            ("bottom end", self.y_bottom),
            ("top end", self.y_top),
            ("top left quadrant", self.top_left),
            ("top right quadrant", self.top_right),
            ("bottom left quadrant", self.bottom_left),
            ("bottom right quadrant", self.bottom_right),
            ("dot", self.dot),
        )


Diagram = Annotated[VennDiagram | MatrixDiagram, Field(discriminator="diagram_type")]


class DiagramStyle(_Data):
    """How a diagram looks in a theme: its labels' font; the colours of its circles or quadrants (in order) and how
    opaque they are (from 0 to 1); and the colours of its labels, its axes, its punchline (a matrix's dot and the
    dot's name) and the ring around the dot ("#rrggbb")."""

    font: str
    fills: tuple[str, ...]
    opacity: float
    text: str
    lines: str
    punchline: str
    outline: str


class DiagramElement(_Data):
    """A diagram drawn as shapes, so it needs no image source and looks the same wherever the deck is shown."""

    kind: Literal["diagram"] = "diagram"
    role: str
    diagram: Diagram
    box: Box | None = None  # where it goes, and how it looks (in a themed deck)
    style: DiagramStyle | None = None


Element = Annotated[
    TextElement | ImageElement | ChartElement | DiagramElement | ShapeElement, Field(discriminator="kind")
]
Content = TextElement | ImageElement | ChartElement | DiagramElement | ShapeElement


class DeckSlide(_Data):
    type: str
    layout: str
    elements: tuple[Element, ...] = ()
    credits: tuple[Credit, ...] = ()  # the credit line on the slide, one credit per image
    notes: str = ""  # how the slide was made; only rendered when asked for (presenters see the notes)
    background: SlideBackground | None = None  # (in a themed deck)
    credits_box: Box | None = None  # where the credit line goes, and how it looks (in a themed deck)
    credits_style: TextStyle | None = None
    style: Theme | None = None  # the slide's own theme, when it differs from the deck's (a chaos deck)

    def element(self, role: str) -> Content | None:
        return next((element for element in self.elements if element.role == role), None)

    def images(self) -> tuple[ImageAsset, ...]:
        return tuple(element.image for element in self.elements if isinstance(element, ImageElement))


# What was typed for a talk can be read as its topic ("penguins", or a premise such as "Cats are liquid"), which the
# talk's title builds on, or as its title ("Why I Joined a Penguin Cult"), which it keeps
Reading = Literal["topic", "title"]


class TopicOrTitle(_Data):
    """What was typed for a talk that could be its topic or its title (generate_presentation's topic_or_title), and
    how it was read (see talkgenerator.titles)."""

    text: str
    read_as: Reading


class Deck(_Data):
    deck_version: Literal[1] = DECK_VERSION
    generator: str  # what made the deck, such as "talkgenerator 5.0.0"
    title: str | None = None
    topics: tuple[str, ...] = ()
    # What was typed, when it could be the topic or the title, and how it was read (none: a topic or a title, given)
    topic_or_title: TopicOrTitle | None = None
    presenter: str | None = None
    language: str = "en"  # the language of its texts (the credits stay as their sources word them)
    schema_name: str | None = None
    seed: int | None = None
    theme: str = "classic"  # the name of the theme: "classic" (the 2019 template), or one of a family's
    style: Theme | None = None  # the theme's tokens (none for the classic theme)
    # The language model that wrote the talk, as "provider:model" (the one that answered), or none: a classic talk
    language_model: str | None = None
    # The license classes its images may have: "all", "open" (everything but fair use), or the classes, as
    # "public-domain,open" (see talkgenerator.images.licenses)
    license_policy: str = "all"
    slides: tuple[DeckSlide, ...] = ()
    usage: Usage = Usage()  # what the talk asked of language models, and what that cost

    def to_json(self, indent: int | None = 2) -> str:
        """The deck as JSON. The same deck always gives the same text: no timestamps, fields in a fixed order, and
        nothing for what's empty (a classic deck has no boxes or styles)."""
        return self.model_dump_json(indent=indent, exclude_none=True)

    @classmethod
    def from_json(cls, text: str | bytes) -> Deck:
        return cls.model_validate_json(text)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """The JSON Schema of the format, for other tools (such as the web app) to check decks against."""
        return cls.model_json_schema()
