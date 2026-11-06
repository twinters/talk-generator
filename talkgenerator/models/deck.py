"""The deck format: a generated talk as plain data.

Every renderer draws a deck: for now the PowerPoint renderer (`talkgenerator.render.powerpoint`), later the browser
view on talkgenerator.com. So a deck holds no image bytes, python-pptx objects or callbacks, only JSON-serializable
data, and `deck_version` changes whenever the format changes in a way older readers can't handle.

A slide has a type and a layout. Its content is a list of elements, each with a role that the layout knows where to
put ("title", "caption_1", "content_1", ...), so a layout or theme can change without changing the content.
"""

from __future__ import annotations

from typing import Annotated, Any, Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data as _Data
from talkgenerator.models.usage import Usage

DECK_VERSION: Final = 1

ImageFit = Literal["contain", "cover"]
ChartType = Literal["pie", "doughnut", "column", "bar", "line", "scatter"]
# How a chart appears: all at once, or the series after the first on clicks, one by one
ChartReveal = Literal["all", "series"]
# How a diagram appears: all at once, or without its punchline, which appears on a click
DiagramReveal = Literal["all", "punchline"]


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


class ImageElement(_Data):
    kind: Literal["image"] = "image"
    role: str
    image: ImageAsset
    # contain: the whole image, padded to fit its frame; cover: the image fills its frame, cropped where needed
    fit: ImageFit = "contain"


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


class DiagramElement(_Data):
    """A diagram drawn as shapes, so it needs no image source and looks the same wherever the deck is shown."""

    kind: Literal["diagram"] = "diagram"
    role: str
    diagram: Diagram


Element = Annotated[TextElement | ImageElement | ChartElement | DiagramElement, Field(discriminator="kind")]


class DeckSlide(_Data):
    type: str
    layout: str
    elements: tuple[Element, ...] = ()
    credits: tuple[Credit, ...] = ()  # the credit line on the slide, one credit per image
    notes: str = ""  # how the slide was made; only rendered when asked for (presenters see the notes)

    def element(self, role: str) -> TextElement | ImageElement | ChartElement | DiagramElement | None:
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
    theme: str = "classic"
    slides: tuple[DeckSlide, ...] = ()
    usage: Usage = Usage()  # what the talk asked of language models, and what that cost

    def to_json(self, indent: int | None = 2) -> str:
        """The deck as JSON. The same deck always gives the same text: no timestamps, fields in a fixed order."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, text: str | bytes) -> Deck:
        return cls.model_validate_json(text)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """The JSON Schema of the format, for other tools (such as the web app) to check decks against."""
        return cls.model_json_schema()
