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
ChartType = Literal["pie", "doughnut", "column", "scatter"]


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


class ChartSpec(_Data):
    chart_type: ChartType
    categories: tuple[str, ...] = ()
    series: tuple[ChartSeries, ...] = ()


class ChartElement(_Data):
    kind: Literal["chart"] = "chart"
    role: str
    chart: ChartSpec


Element = Annotated[TextElement | ImageElement | ChartElement, Field(discriminator="kind")]


class DeckSlide(_Data):
    type: str
    layout: str
    elements: tuple[Element, ...] = ()
    credits: tuple[Credit, ...] = ()  # the credit line on the slide, one credit per image
    notes: str = ""  # how the slide was made; only rendered when asked for (presenters see the notes)

    def element(self, role: str) -> TextElement | ImageElement | ChartElement | None:
        return next((element for element in self.elements if element.role == role), None)

    def images(self) -> tuple[ImageAsset, ...]:
        return tuple(element.image for element in self.elements if isinstance(element, ImageElement))


class Deck(_Data):
    deck_version: Literal[1] = DECK_VERSION
    generator: str  # what made the deck, such as "talkgenerator 5.0.0"
    title: str | None = None
    topics: tuple[str, ...] = ()
    presenter: str | None = None
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
