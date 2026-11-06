"""The deck format: a generated talk as plain data.

Every renderer draws a deck: for now the PowerPoint renderer (`talkgenerator.render.powerpoint`), later the browser
view on talkgenerator.com. So a deck holds no image bytes, python-pptx objects or callbacks, only JSON-serializable
data, and `deck_version` changes whenever the format changes in a way older readers can't handle.

A slide has a type and a layout. Its content is a list of elements, each with a role that the layout knows where to
put ("title", "caption_1", "content_1", ...), so a layout or theme can change without changing the content.

In a deck with a theme other than the classic one, every element also has its place (a box on a 1920×1080
canvas) and every text its style, as the layout engine (`talkgenerator.design.engine`) put them: so every
renderer draws such a deck the same way. A classic deck's elements go in the 2019 template's placeholders.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data as _Data
from talkgenerator.models.theme import Theme
from talkgenerator.models.usage import Usage

DECK_VERSION: Final = 1

ImageFit = Literal["contain", "cover"]
ChartType = Literal["pie", "doughnut", "column", "bar", "line", "scatter"]
# How a chart appears: all at once, or the series after the first on clicks, one by one
ChartReveal = Literal["all", "series"]
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


class CreditPart(_Data):
    """A piece of a credit as it reads on a slide, and the page it links to (if any)."""

    text: str
    url: str | None = None


Credit = tuple[CreditPart, ...]


class ImageAsset(_Data):
    """An image, and where it came from. The url is a web address or a local path."""

    url: str
    source: str | None = None
    source_url: str | None = None
    credit: Credit = ()
    query: str | None = None  # the search that found it, for an image a plan asked for
    description: str | None = None  # what it shows, as its source describes it (for alt text, say)


class TextElement(_Data):
    kind: Literal["text"] = "text"
    role: str
    text: str
    box: Box | None = None
    style: TextStyle | None = None


class ImageElement(_Data):
    kind: Literal["image"] = "image"
    role: str
    image: ImageAsset
    # contain: the whole image, padded to fit its frame; cover: the image fills its frame, cropped where needed
    fit: ImageFit = "contain"
    box: Box | None = None
    border: str | None = None  # a frame around the image, in this colour ("#rrggbb")


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


class SlideBackground(_Data):
    """A slide's background: a colour, or a gradient from it at the top to color_2 at the bottom."""

    color: str
    color_2: str | None = None


Element = Annotated[TextElement | ImageElement | ChartElement | ShapeElement, Field(discriminator="kind")]
Content = TextElement | ImageElement | ChartElement | ShapeElement


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


class Deck(_Data):
    deck_version: Literal[1] = DECK_VERSION
    generator: str  # what made the deck, such as "talkgenerator 5.0.0"
    title: str | None = None
    topics: tuple[str, ...] = ()
    presenter: str | None = None
    language: str = "en"  # the language of its texts (the credits stay as their sources word them)
    schema_name: str | None = None
    seed: int | None = None
    theme: str = "classic"  # the name of the theme: "classic" (the 2019 template), or one of a family's
    style: Theme | None = None  # the theme's tokens (none for the classic theme)
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
