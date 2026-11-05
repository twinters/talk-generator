from collections.abc import Sequence

from talkgenerator.datastructures.image_data import CreditPart, ImageData
from talkgenerator.models import classic
from talkgenerator.models import deck as model
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_slide
from talkgenerator.slide import powerpoint_slide_creator
from talkgenerator.util import image_util, os_util


class Slide:
    """Class representing a slide object that could be used to export to Powerpoint pptx or other representations later"""

    # The arguments a slide can't do without: without them, the slide would show an empty frame (or no slide at all)
    required_arguments: tuple[str, ...] = ()

    def __init__(self, type_name: str, ppt_slide_creator, arguments: dict):
        self._type_name = type_name
        self._ppt_slide_creator = ppt_slide_creator
        self._arguments = arguments
        self._note = ""
        self._sources: list[str] = []
        self._source_urls: list[str | None] = []
        self._credits: list[tuple[CreditPart, ...]] = []

    @property
    def type_name(self) -> str:
        return self._type_name

    def add_source(self, source: str, url: str | None = None, credit: Sequence[CreditPart] | None = None):
        """Credit an image source. In the PowerPoint, the credit links to the url (if given), or reads as the
        given credit parts, each linking to its own page."""
        if source is not None:
            self._sources.append(source)
            self._source_urls.append(url)
            self._credits.append(tuple(credit) if credit else ((source, url),))

    def set_note(self, note: str):
        """Debug information about how the slide was generated."""
        self._note = note

    def missing_content(self) -> list[str]:
        """The required arguments that are empty, hold an image that can't be downloaded or used, or repeat an
        image shown elsewhere on the slide.

        Checking an image downloads it, and its ImageData keeps the bytes for when the slide is added to the
        PowerPoint (see image_util.fetch_image_data).
        """
        missing = []
        images_on_slide: set[ImageData] = set()
        for name in self.required_arguments:
            value = self._arguments.get(name)
            repeated = isinstance(value, ImageData) and value in images_on_slide
            if repeated or not _has_content(value):
                missing.append(name)
            elif isinstance(value, ImageData):
                images_on_slide.add(value)
        return missing

    def create_powerpoint_slide(self, prs, debug_notes: bool = False):
        """Add this slide to the presentation. With debug_notes, the speaker notes explain how it was generated
        (off by default: presenters see the notes, and they spoil the surprise).

        The slide is drawn from its deck form (see to_deck_slide), like every slide of a deck."""
        return render_slide(prs, self.to_deck_slide(), debug_notes=debug_notes, images=self.image_store())

    def to_deck_slide(self) -> model.DeckSlide:
        """The slide as deck data (see talkgenerator.models.deck): its content as elements, its credits and notes."""
        fit: model.ImageFit = "contain" if self._arguments.get("original_image_size", True) else "cover"
        elements = []
        for argument, role in classic.CLASSIC_ROLES[self._type_name].items():
            element = _to_element(role, self._arguments.get(argument), "cover" if role in classic.COVER_ROLES else fit)
            if element is not None:
                elements.append(element)
        return self._deck_slide(tuple(elements))

    def _deck_slide(
        self, elements: tuple[model.TextElement | model.ImageElement | model.ChartElement, ...]
    ) -> model.DeckSlide:
        credits = tuple(tuple(model.CreditPart(text=text, url=url) for text, url in credit) for credit in self._credits)
        return model.DeckSlide(
            type=self._type_name,
            layout=classic.layout_id(self._type_name),
            elements=elements,
            credits=credits,
            notes=self._note,
        )

    def image_store(self) -> dict[str, ImageData]:
        """The slide's images by URL, with the bytes downloaded while checking them (so they aren't downloaded
        again) and what to do once they end up on a slide (such as Unsplash's download tracking)."""
        return {value.get_image_url(): value for value in self._arguments.values() if isinstance(value, ImageData)}

    def to_slide_dictionary(self) -> dict:
        slide_dict = dict(self._arguments)
        slide_dict["type"] = self._type_name
        slide_dict["sources"] = self._sources
        slide_dict["source_urls"] = self._source_urls
        return slide_dict


def _to_element(role: str, value: object, fit: model.ImageFit) -> model.TextElement | model.ImageElement | None:
    """A slide argument as a deck element: an image, a text, or nothing when it's empty."""
    if value is None:
        return None
    if role not in classic.TEXT_ROLES:
        if isinstance(value, ImageData):
            return model.ImageElement(role=role, image=_to_image_asset(value), fit=fit)
        if isinstance(value, str) and os_util.is_image(value):
            return model.ImageElement(role=role, image=model.ImageAsset(url=value), fit=fit)
    text = str(value)
    return model.TextElement(role=role, text=text) if text.strip() else None


def _to_image_asset(image: ImageData) -> model.ImageAsset:
    return model.ImageAsset(
        url=image.get_image_url(),
        source=image.get_source(),
        source_url=image.get_source_url(),
        credit=tuple(model.CreditPart(text=text, url=url) for text, url in image.get_credit()),
    )


def _has_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, ImageData):
        return image_util.fetch_image_data(value) is not None
    if isinstance(value, str):
        if os_util.is_image(value):  # the URL or path of an image
            return image_util.is_usable_image(value)
        return bool(value.strip())
    return True


class TitleSlide(Slide):
    required_arguments = ("title",)

    def __init__(self, title: str, subtitle: str):
        super().__init__(
            type_name="title",
            ppt_slide_creator=powerpoint_slide_creator.create_title_slide,
            arguments={"title": title, "subtitle": subtitle},
        )


class LarqeQuoteSlide(Slide):
    required_arguments = ("text", "background_image")

    def __init__(self, title: str, text: str, background_image=None):
        super().__init__(
            type_name="large_quote",
            ppt_slide_creator=powerpoint_slide_creator.create_large_quote_slide,
            arguments={
                "title": title,
                "text": text,
                "background_image": background_image,
            },
        )


class ImageSlide(Slide):
    required_arguments = ("image_url",)

    def __init__(self, title=None, image_url=None, original_image_size=True):
        super().__init__(
            type_name="image",
            ppt_slide_creator=powerpoint_slide_creator.create_image_slide,
            arguments={
                "title": title,
                "image_url": image_url,
                "original_image_size": original_image_size,
            },
        )


class FullImageSlide(Slide):
    required_arguments = ("image_url",)

    def __init__(self, title=None, image_url=None, original_image_size=True):
        super().__init__(
            type_name="full_image",
            ppt_slide_creator=powerpoint_slide_creator.create_full_image_slide,
            arguments={
                "title": title,
                "image_url": image_url,
                "original_image_size": original_image_size,
            },
        )


class TwoColumnImageSlide(Slide):
    required_arguments = ("image_or_text_1", "image_or_text_2")

    def __init__(
        self,
        title=None,
        caption_1=None,
        image_or_text_1=None,
        caption_2=None,
        image_or_text_2=None,
        original_image_size=True,
    ):
        super().__init__(
            type_name="two_column_image",
            ppt_slide_creator=powerpoint_slide_creator.create_two_column_images_slide,
            arguments={
                "title": title,
                "caption_1": caption_1,
                "image_or_text_1": image_or_text_1,
                "caption_2": caption_2,
                "image_or_text_2": image_or_text_2,
                "original_image_size": original_image_size,
            },
        )


class ThreeColumnImageSlide(Slide):
    required_arguments = ("image_or_text_1", "image_or_text_2", "image_or_text_3")

    def __init__(
        self,
        title=None,
        caption_1=None,
        image_or_text_1=None,
        caption_2=None,
        image_or_text_2=None,
        caption_3=None,
        image_or_text_3=None,
        original_image_size=True,
    ):
        super().__init__(
            type_name="three_column_image",
            ppt_slide_creator=powerpoint_slide_creator.create_three_column_images_slide,
            arguments={
                "title": title,
                "caption_1": caption_1,
                "image_or_text_1": image_or_text_1,
                "caption_2": caption_2,
                "image_or_text_2": image_or_text_2,
                "caption_3": caption_3,
                "image_or_text_3": image_or_text_3,
                "original_image_size": original_image_size,
            },
        )


class ChartSlide(Slide):
    required_arguments = ("chart_type", "chart_data")

    def __init__(self, title, chart_type, chart_data, chart_modifier=None):
        super().__init__(
            type_name="chart",
            ppt_slide_creator=powerpoint_slide_creator.create_chart_slide,
            arguments={
                "title": title,
                "chart_type": chart_type,
                "chart_data": chart_data,
                "chart_modifier": chart_modifier,
            },
        )

    def to_deck_slide(self) -> model.DeckSlide:
        """The chart's numbers go into the deck; the renderer styles the chart by its type (the chart_modifier
        stays out: a deck holds data, not functions)."""
        elements: list[model.TextElement | model.ImageElement | model.ChartElement] = []
        title = _to_element("title", self._arguments.get("title"), "contain")
        if title is not None:
            elements.append(title)
        chart_data = self._arguments.get("chart_data")
        if chart_data is not None:
            chart = charts.chart_spec(self._arguments["chart_type"], chart_data)
            elements.append(model.ChartElement(role="chart", chart=chart))
        return self._deck_slide(tuple(elements))
