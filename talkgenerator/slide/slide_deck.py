import logging
import warnings
from collections.abc import Callable, Sequence
from typing import Final

from talkgenerator import __version__
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.design import engine
from talkgenerator.models.deck import Deck, Fact, TalkPersona, TopicOrTitle
from talkgenerator.models.theme import Theme
from talkgenerator.models.usage import Usage
from talkgenerator.render.powerpoint import render_slide
from talkgenerator.slide.slides import QuestionsSlide, SectionSlide, Slide

logger = logging.getLogger("talkgenerator")

TO_SLIDE_DECK_DICTIONARY_DEPRECATION: Final = (
    "SlideDeck.to_slide_deck_dictionary() is deprecated (it keeps working throughout talkgenerator 5). Use "
    "slide_deck.to_deck() instead: the whole talk as a deck (talkgenerator.models.deck), whose to_json() is the deck "
    "JSON, and whose slides are these dictionaries, as data. See "
    "https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md"
)


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
        # The families the slides' own themes can be of (None: all of them; see talkgenerator.design.themes.allowed)
        self.theme_families: tuple[str, ...] | None = None
        # The language model that writes the talk ("provider:model"), or None: a classic talk
        self.language_model: str | None = None
        # How much it did: "basic" or "advanced" (it planned the talk first: see talkgenerator.plan.outline)
        self.llm_level: str | None = None
        # The vision model that picked its pictures among their candidates, if it had a vision pick that did (see
        # talkgenerator.images.vision)
        self.vision_model: str | None = None
        # The license classes its images may have (see talkgenerator.images.licenses)
        self.license_policy = "all"
        # What was typed, when it could be the talk's topic or its title, and how it was read (see talkgenerator.titles)
        self.topic_or_title: TopicOrTitle | None = None
        # Who presents it, as its dice picked them (see talkgenerator.personas)
        self.persona: TalkPersona | None = None
        # Its format: the name of the schema it asked for, or of the one its seed picked (see
        # talkgenerator.schema.presentation_schema_types.pick_format)
        self.schema_name: str | None = None
        # The real facts its language model's request gave its slides (see talkgenerator.facts); the deck adds the ones
        # its classic slides show
        self.facts: tuple[Fact, ...] = ()
        # Who wants to know about every slide once it's added (a talk that streams: see talkgenerator.generator), and
        # about a slide that changed after it was added (a generated picture in its stock photo's place)
        self.listener: Callable[[SlideDeck, int, Slide], None] | None = None
        self.update_listener: Callable[[SlideDeck, int, Slide], None] | None = None
        # And about a slide that took the place of another (a slide that ran out of time, come after all in place of
        # what stood in for it: see talkgenerator.schema.presentation_schema._LateSlides)
        self.replace_listener: Callable[[SlideDeck, int, Slide], None] | None = None

    @property
    def title(self) -> str | None:
        return self._title

    @property
    def presenter(self) -> str | None:
        return self._presenter

    @property
    def topics(self) -> tuple[str, ...]:
        return self._topics

    @property
    def seed(self) -> int | None:
        return self._seed

    @property
    def language(self) -> str:
        return self._language

    @property
    def size(self) -> int:
        """How many slides the talk is to have (a slide that can't be made is left out)."""
        return self._size

    def add_slide(self, slide_index: int, slide):
        self._place(slide_index, slide)
        if self.listener is not None:
            self.listener(self, slide_index, slide)

    def replace_slide(self, slide_index: int, slide) -> None:
        """Another slide in place of the one at the index (a slide that ran out of time, come after all in place of
        what stood in for it): the replace_listener hears of it."""
        self._place(slide_index, slide)
        if self.replace_listener is not None:
            self.replace_listener(self, slide_index, slide)

    def _place(self, slide_index: int, slide) -> None:
        if isinstance(slide, SectionSlide):  # (numbered after the sections before it: the talk's opening is the first)
            slide.number(2 + sum(isinstance(other, SectionSlide) for other in self._slides[:slide_index]))
        if isinstance(slide, QuestionsSlide):  # (a closing slide that calls back shows an earlier slide's picture)
            slide.call_back([other for other in self._slides[:slide_index] if other is not None])
        self._slides[slide_index] = slide

    def slide_updated(self, slide_index: int) -> None:
        """The slide at the index changed since it was added (it has a generated picture now, say)."""
        slide = self._slides[slide_index]
        if slide is not None and self.update_listener is not None:
            self.update_listener(self, slide_index, slide)

    def slides(self) -> list[Slide]:
        """The slides added so far, in order."""
        return [slide for slide in self._slides if slide is not None]

    def is_complete(self):
        return len(self._slides) >= self._size and (None not in self._slides)

    def save_to_powerpoint(self, prs_template, debug_notes: bool = False):
        """Add the slides to the presentation, drawn from the deck (see to_deck). Returns the PowerPoint slides."""
        if not self.is_complete():
            logger.error("ERROR: SOME SLIDES WERE NOT GENERATED: {}".format(self._slides))
            self._slides = [slide for slide in self._slides if slide is not None]
        deck = self.to_deck()
        images = self.image_store()  # (after the deck, which settles how its images show: as a video, say)
        total = len(deck.slides)  # (each numbered of them: "7/12")
        return [
            render_slide(prs_template, deck_slide, debug_notes=debug_notes, images=images, number=number, total=total)
            for number, deck_slide in enumerate(deck.slides, 1)
        ]

    def to_deck(self, schema_name: str | None = None) -> Deck:
        """The talk as a deck: plain data that renders the same PowerPoint, and that can be saved as JSON. Its schema
        is the talk's format (schema_name), unless one is given."""
        deck = Deck(
            generator=f"talkgenerator {__version__}",
            title=self._title,
            topics=self._topics,
            topic_or_title=self.topic_or_title,
            presenter=self._presenter,
            persona=self.persona,
            language=self._language,
            schema_name=schema_name if schema_name is not None else self.schema_name,
            seed=self._seed,
            language_model=self.language_model,
            llm_level=self.llm_level,
            vision_model=self.vision_model,
            license_policy=self.license_policy,
            slides=tuple(slide.to_deck_slide() for slide in self._slides if slide is not None),
            usage=self.usage,
            facts=self._facts() or None,
        )
        if self.theme is not None:  # every element in its box, in the theme's style
            return engine.lay_out(deck, self.theme, self.style_chaos, self.extreme_themes, self.theme_families)
        return deck

    def _facts(self) -> tuple[Fact, ...]:
        """The real facts of the talk: the ones its request gave its slides, and the ones its slides show (each with
        the number of its slide in the talk)."""
        shown = [
            fact.model_copy(update={"slide": number})
            for number, slide in enumerate(self._slides, 1)
            if slide is not None
            for fact in slide.facts
        ]
        return (*self.facts, *shown)

    def image_store(self) -> dict[str, ImageData]:
        """The images on the slides by URL, with their downloaded bytes (see Slide.image_store)."""
        images: dict[str, ImageData] = {}
        for slide in self._slides:
            if slide is not None:
                for url, image in slide.image_store().items():
                    images.setdefault(url, image)
        return images

    def to_slide_deck_dictionary(self) -> list[dict]:
        """Deprecated: the slides as JSON-ready dictionaries, the slides of the deck format. It keeps working
        throughout talkgenerator 5, with a DeprecationWarning: to_deck gives the whole deck, with these slides."""
        warnings.warn(TO_SLIDE_DECK_DICTIONARY_DEPRECATION, DeprecationWarning, stacklevel=2)
        return [slide.model_dump(mode="json", exclude_none=True) for slide in self.to_deck().slides]

    def get_structured_data(self):
        """Return slide deck as structured data for alternative presentation"""
        if not self.is_complete():
            logger.error("ERROR: SOME SLIDES WERE NOT GENERATED: {}".format(self._slides))
            self._slides = [slide for slide in self._slides if slide is not None]
        return [slide for slide in self._slides]

    def has_slide_nr(self, index):
        return 0 <= index < self._size and self._slides[index] is not None
