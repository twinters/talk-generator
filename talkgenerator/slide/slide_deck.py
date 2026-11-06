import logging
from collections.abc import Sequence

from talkgenerator import __version__
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine
from talkgenerator.models.deck import Deck
from talkgenerator.models.theme import Theme
from talkgenerator.models.usage import Usage
from talkgenerator.render.powerpoint import render_slide
from talkgenerator.slide.slides import Slide

logger = logging.getLogger("talkgenerator")


class SlideDeck:
    """Represents a deck of Slide objects, and what the talk is about"""

    def __init__(
        self,
        size,
        *,
        title: str | None = None,
        topics: Sequence[str] = (),
        presenter: str | None = None,
        seed: int | None = None,
        language: str = "en",
    ):
        self._size = size
        self._slides: list[Slide | None] = [None] * size
        self._title = title
        self._topics = tuple(topics)
        self._presenter = presenter
        self._seed = seed
        self._language = language
        # What the talk asked of language models (see talkgenerator.llm), for the deck to tell
        self.usage = Usage()
        # Its theme (None: the classic 2019 template), and how many slides get themes of their own
        self.theme: Theme | None = None
        self.style_chaos = 0.0
        self.extreme_themes = True

    def add_slide(self, slide_index: int, slide):
        self._slides[slide_index] = slide

    def is_complete(self):
        return len(self._slides) >= self._size and (None not in self._slides)

    def save_to_powerpoint(self, prs_template, debug_notes: bool = False):
        """Add the slides to the presentation, drawn from the deck (see to_deck). Returns the PowerPoint slides."""
        if not self.is_complete():
            logger.error("ERROR: SOME SLIDES WERE NOT GENERATED: {}".format(self._slides))
            self._slides = [slide for slide in self._slides if slide is not None]
        deck = self.to_deck()
        images = self.image_store()  # (after the deck, which settles how its images show: as a video, say)
        return [
            render_slide(prs_template, deck_slide, debug_notes=debug_notes, images=images) for deck_slide in deck.slides
        ]

    def to_deck(self, schema_name: str | None = None) -> Deck:
        """The talk as a deck: plain data that renders the same PowerPoint, and that can be saved as JSON."""
        deck = Deck(
            generator=f"talkgenerator {__version__}",
            title=self._title,
            topics=self._topics,
            presenter=self._presenter,
            language=self._language,
            schema_name=schema_name,
            seed=self._seed,
            slides=tuple(slide.to_deck_slide() for slide in self._slides if slide is not None),
            usage=self.usage,
        )
        if self.theme is not None:  # every element in its box, in the theme's style
            return engine.lay_out(deck, self.theme, self.style_chaos, self.extreme_themes)
        return deck

    def image_store(self) -> dict[str, ImageData]:
        """The images on the slides by URL, with their downloaded bytes (see Slide.image_store)."""
        images: dict[str, ImageData] = {}
        for slide in self._slides:
            if slide is not None:
                for url, image in slide.image_store().items():
                    images.setdefault(url, image)
        return images

    def to_slide_deck_dictionary(self) -> list[dict]:
        """The slides as JSON-ready dictionaries: the slides of the deck format (see to_deck)."""
        return [slide.model_dump(mode="json", exclude_none=True) for slide in self.to_deck().slides]

    def get_structured_data(self):
        """Return slide deck as structured data for alternative presentation"""
        if not self.is_complete():
            logger.error("ERROR: SOME SLIDES WERE NOT GENERATED: {}".format(self._slides))
            self._slides = [slide for slide in self._slides if slide is not None]
        return [slide for slide in self._slides]

    def has_slide_nr(self, index):
        return 0 <= index < self._size and self._slides[index] is not None
