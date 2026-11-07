import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from talkgenerator.datastructures.image_data import CreditPart, ImageData
from talkgenerator.images import analysis
from talkgenerator.models import classic
from talkgenerator.models import deck as model
from talkgenerator.plan.languages import ENGLISH, Language
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_slide
from talkgenerator.slide import powerpoint_slide_creator
from talkgenerator.util import image_util, os_util

if TYPE_CHECKING:
    from talkgenerator.images.generation import Wish


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
        self._credited: list[ImageData | None] = []  # the image each credit is for, if it's known
        # The pictures the slide wishes to have generated, each with the stock photo that stands in for it until it's
        # in (see talkgenerator.images.generation)
        self.wishes: list[tuple[ImageData, Wish]] = []

    @property
    def type_name(self) -> str:
        return self._type_name

    def add_source(
        self,
        source: str | None,
        url: str | None = None,
        credit: Sequence[CreditPart] | None = None,
        image: ImageData | None = None,
    ):
        """Credit an image source (for the image, if given). In the PowerPoint, the credit links to the url (if
        given), or reads as the given credit parts, each linking to its own page."""
        if source is not None:
            self._sources.append(source)
            self._source_urls.append(url)
            self._credits.append(tuple(credit) if credit else ((source, url),))
            self._credited.append(image)

    def replace_image(self, old: ImageData, new: ImageData) -> None:
        """Put the new image where the old one is on the slide, crediting it instead: a generated picture in place of
        the stock photo that stood in for it (see talkgenerator.images.generation)."""
        for name, value in list(self._arguments.items()):
            if value is old:
                self._arguments[name] = new
        for index, credited in enumerate(self._credited):
            if credited is old:
                self._sources[index] = new.get_source() or ""
                self._source_urls[index] = new.get_source_url()
                self._credits[index] = new.get_credit()
                self._credited[index] = new

    def set_note(self, note: str):
        """Debug information about how the slide was generated."""
        self._note = note

    def missing_content(self) -> list[str]:
        """The required arguments that are empty, hold an image that can't be downloaded or used, or repeat an
        image shown elsewhere on the slide (or nearly: see talkgenerator.images.analysis.near_duplicates).

        Checking an image downloads it, and its ImageData keeps the bytes for when the slide is added to the
        PowerPoint (see image_util.check_image; a talk that streams probes it instead).
        """
        missing = []
        images_on_slide: list[ImageData] = []
        for name in self.required_arguments:
            value = self._arguments.get(name)
            repeated = isinstance(value, ImageData) and any(
                value == other or analysis.near_duplicates(value.analysis, other.analysis) for other in images_on_slide
            )
            if repeated or not _has_content(value):
                missing.append(name)
            elif isinstance(value, ImageData):
                images_on_slide.append(value)
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
        self, elements: tuple[model.TextElement | model.ImageElement | model.ChartElement | model.DiagramElement, ...]
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
        """The slide's images by the URL the deck gives them (see ImageData.get_shown_url), with the bytes downloaded
        while checking them (so they aren't downloaded again) and what to do once they end up on a slide (such as
        Unsplash's download tracking)."""
        return {value.get_shown_url(): value for value in self._arguments.values() if isinstance(value, ImageData)}

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
            display: model.DisplayPolicy = "direct" if value.startswith(("http://", "https://")) else "local"
            return model.ImageElement(role=role, image=model.ImageAsset(url=value, display=display), fit=fit)
    text = str(value)
    return model.TextElement(role=role, text=text) if text.strip() else None


def _to_image_asset(image: ImageData) -> model.ImageAsset:
    # Checked first (if it wasn't yet), as that settles what shows: a gif too large to embed, say, plays as its video
    image_util.check_image(image)
    video = image.video if image.plays_video else None
    url = image.get_shown_url()
    return model.ImageAsset(
        url=url,
        video_url=video.url if video is not None else None,
        source=image.get_source(),
        source_url=image.get_source_url(),
        credit=tuple(model.CreditPart(text=text, url=url) for text, url in image.get_credit()),
        query=image.query,
        description=image.description,
        # (a file of the computer's own, but a generated picture, whose app keeps a copy of it, as of Pixabay's)
        display=image.display if url.startswith(("http://", "https://")) or image.display == "copy" else "local",
        width=image.size[0] if image.size else None,
        height=image.size[1] if image.size else None,
        license_class=image.license_class,
        license=image.license,
        license_url=image.license_url,
        look=image.look,
        analysis=image.analysis,
    )


def _has_content(value) -> bool:
    if value is None:
        return False
    if isinstance(value, ImageData):
        return image_util.check_image(value)
    if isinstance(value, str):
        if os_util.is_image(value):  # the URL or path of an image
            return image_util.is_usable_image(value)
        return bool(value.strip())
    return True


class TitleSlide(Slide):
    required_arguments = ("title",)

    def __init__(self, title: str, subtitle: str | None):
        super().__init__(
            type_name="title",
            ppt_slide_creator=powerpoint_slide_creator.create_title_slide,
            arguments={"title": title, "subtitle": subtitle},
        )


class LarqeQuoteSlide(Slide):
    required_arguments = ("text", "background_image")

    def __init__(self, title: str | None, text: str, background_image=None):
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

    def __init__(
        self,
        title,
        chart_type,
        chart_data,
        chart_modifier=None,
        x_title: str | None = None,
        y_title: str | None = None,
        reveal: model.ChartReveal = "all",
        point_labels: Sequence[tuple[int, int, str]] = (),
    ):
        super().__init__(
            type_name="chart",
            ppt_slide_creator=powerpoint_slide_creator.create_chart_slide,
            arguments={
                "title": title,
                "chart_type": chart_type,
                "chart_data": chart_data,
                "chart_modifier": chart_modifier,
                "x_title": x_title,
                "y_title": y_title,
                "reveal": reveal,
                "point_labels": tuple(point_labels),
            },
        )

    def to_deck_slide(self) -> model.DeckSlide:
        """The chart's numbers, axis titles, named points and how it appears go into the deck; the renderer styles
        the chart by its type (the chart_modifier stays out: a deck holds data, not functions)."""
        elements: list[model.TextElement | model.ImageElement | model.ChartElement] = []
        title = _to_element("title", self._arguments.get("title"), "contain")
        if title is not None:
            elements.append(title)
        chart_data = self._arguments.get("chart_data")
        if chart_data is not None:
            chart = charts.chart_spec(
                self._arguments["chart_type"],
                chart_data,
                x_title=self._arguments.get("x_title"),
                y_title=self._arguments.get("y_title"),
                reveal=self._arguments.get("reveal") or "all",
            )
            chart = charts.with_point_labels(chart, self._arguments.get("point_labels") or ())
            elements.append(model.ChartElement(role="chart", chart=chart))
        return self._deck_slide(tuple(elements))


class DiagramSlide(Slide):
    """A diagram drawn as shapes, under a title: a Venn diagram or a 2×2 matrix (see talkgenerator.render.diagrams)."""

    required_arguments = ("diagram",)

    def __init__(self, title: str | None, diagram: model.VennDiagram | model.MatrixDiagram | None):
        super().__init__(
            type_name="diagram",
            ppt_slide_creator=powerpoint_slide_creator.create_diagram_slide,
            arguments={"title": title, "diagram": diagram},
        )

    def to_deck_slide(self) -> model.DeckSlide:
        elements: list[model.TextElement | model.ImageElement | model.ChartElement | model.DiagramElement] = []
        title = _to_element("title", self._arguments.get("title"), "contain")
        if title is not None:
            elements.append(title)
        diagram = self._arguments.get("diagram")
        if diagram is not None:
            elements.append(model.DiagramElement(role="diagram", diagram=diagram))
        return self._deck_slide(tuple(elements))


# MILESTONE 6'S SLIDE TYPES: drawn as texts on shapes (see talkgenerator.design.engine), also in a classic deck, in the
# 2019 template's look (talkgenerator.render.powerpoint)

# A quiz's options, as its slides name them
LETTERS = "ABCD"


class DrawnSlide(Slide):
    """A slide of a type that the 2019 template has no layout for (milestone 6's: big numbers, quizzes, posts...):
    its texts (and photo) by role, which the layout engine places on shapes in a theme's colours, and a classic deck
    in the template's (talkgenerator.models.classic.DRAWN_TYPES). Some of its elements may appear on a click."""

    def to_deck_slide(self) -> model.DeckSlide:
        clicks = self.clicks()
        elements: list[model.TextElement | model.ImageElement | model.ChartElement | model.DiagramElement] = []
        for argument, role in classic.CLASSIC_ROLES[self._type_name].items():
            fit: model.ImageFit = "cover" if role in classic.COVER_ROLES else "contain"
            element = _to_element(role, self._arguments.get(argument), fit)
            if element is None:
                continue
            if role in clicks:
                element = element.model_copy(update={"appears_on_click": clicks[role]})
            elements.append(element)
        return self._deck_slide(tuple(elements))

    def clicks(self) -> dict[str, int]:
        """The roles of the elements that appear on a click, and on which (the first is 1)."""
        return {}


class BigNumberSlide(DrawnSlide):
    """A big number, with what it counts under it, and a title and a (made-up) source, if any."""

    required_arguments = ("number", "label")

    def __init__(self, title: str | None, number: str | None, label: str | None, source: str | None = None):
        super().__init__("big_number", None, {"title": title, "number": number, "label": label, "source": source})


class KpiSlide(DrawnSlide):
    """Three or four figures under a title, each a number and what it measures: the last one, the punchline,
    appears on a click."""

    required_arguments = ("number_1", "label_1", "number_2", "label_2", "number_3", "label_3")

    def __init__(
        self,
        title: str | None,
        number_1: str | None,
        label_1: str | None,
        number_2: str | None,
        label_2: str | None,
        number_3: str | None,
        label_3: str | None,
        number_4: str | None = None,
        label_4: str | None = None,
    ):
        fourth = bool(number_4 and label_4)  # (a fourth figure is both, or none)
        figures = ((number_1, label_1), (number_2, label_2), (number_3, label_3), (number_4, label_4))
        arguments: dict[str, str | None] = {"title": title}
        for index, (number, label) in enumerate(figures, 1):
            arguments[f"number_{index}"] = number if index < 4 or fourth else None
            arguments[f"label_{index}"] = label if index < 4 or fourth else None
        super().__init__("kpi", None, arguments)

    def clicks(self) -> dict[str, int]:
        last = 4 if self._arguments.get("number_4") else 3
        return {f"number_{last}": 1, f"label_{last}": 1}


class QuizSlide(DrawnSlide):
    """A quiz: a question, and three or four options (A to D); on a click, the answer (the letter of the right
    option) and its explanation, if any."""

    required_arguments = ("question", "option_1", "option_2", "option_3", "answer")

    def __init__(
        self,
        question: str | None,
        option_1: str | None,
        option_2: str | None,
        option_3: str | None,
        option_4: str | None,
        answer: str | None,
        explanation: str | None = None,
    ):
        options = (option_1, option_2, option_3, option_4)
        arguments: dict[str, str | None] = {"question": question}
        for index, option in enumerate(options, 1):
            arguments[f"letter_{index}"] = LETTERS[index - 1] if option else None
            arguments[f"option_{index}"] = option
        # (the answer is the letter of one of the options, or none: then the slide misses it)
        letter = (answer or "").strip()[:1].upper()
        known = letter in LETTERS and bool(options[LETTERS.index(letter)])
        arguments["answer"] = letter if known else None
        arguments["explanation"] = explanation
        super().__init__("quiz", None, arguments)

    def clicks(self) -> dict[str, int]:
        return {"answer": 1, "explanation": 1}


def initials(name: str | None) -> str | None:
    """The initials of a name, as on an avatar: of its first two words, leaving out titles such as "Dr."."""
    words = [word for word in (name or "").split() if word[:1].isalpha()]
    named = [word for word in words if not word.endswith(".")] or words
    return "".join(word[0] for word in named[:2]).upper() or None


def handle(name: str | None) -> str | None:
    """A username as a post shows it: "@" and the name, without spaces."""
    plain = re.sub(r"\s+", "_", (name or "").strip().lstrip("@"))
    return f"@{plain}" if plain else None


def count(number: int) -> str:
    """A count as social media round it: 873, 12K, 3M."""
    if number >= 1_000_000:
        return f"{number // 1_000_000}M"
    return f"{number // 1000}K" if number >= 1000 else str(number)


class SocialPostSlide(DrawnSlide):
    """A made-up social media post: its author (their initials on an avatar) and their handle, the post, its photo
    if it has one, and how often it was liked and shared (in the talk's language)."""

    required_arguments = ("author", "text")

    def __init__(
        self,
        title: str | None,
        author: str | None,
        handle_name: str | None,
        text: str | None,
        photo: ImageData | None = None,
        likes: int = 0,
        shares: int = 0,
        language: Language = ENGLISH,
    ):
        arguments = {
            "title": title,
            "initials": initials(author),
            "author": author,
            "handle": handle(handle_name),
            "text": text,
            "photo": photo,
            "stats": f"{count(likes)} {language.likes} · {count(shares)} {language.shares}",
        }
        super().__init__("social_post", None, arguments)


class NewsHeadlineSlide(DrawnSlide):
    """A made-up news story: its outlet, its headline and subheadline, and its photo; on television, under the
    words for breaking news (in the talk's language)."""

    required_arguments = ("outlet", "headline", "photo")

    def __init__(
        self,
        outlet: str | None,
        headline: str | None,
        subheadline: str | None,
        photo: ImageData | None,
        language: Language = ENGLISH,
    ):
        arguments = {
            "photo": photo,
            "kicker": language.breaking,
            "outlet": outlet,
            "headline": headline,
            "subheadline": subheadline,
        }
        super().__init__("news_headline", None, arguments)


class AgendaSlide(DrawnSlide):
    """The talk's agenda: three to five items, numbered, under a title."""

    required_arguments = ("item_1", "item_2", "item_3")

    def __init__(self, title: str | None, *items: str | None):
        listed = [item for item in items if item][:5]
        arguments: dict[str, str | None] = {"title": title}
        for index in range(1, 6):
            item = listed[index - 1] if index <= len(listed) else None
            arguments[f"number_{index}"] = str(index) if item else None
            arguments[f"item_{index}"] = item
        super().__init__("agenda", None, arguments)


class SectionSlide(DrawnSlide):
    """A section's divider: its title and subtitle, under its number (which the deck gives it: see number)."""

    required_arguments = ("title",)

    def __init__(self, title: str | None, subtitle: str | None = None, kicker: str | None = None):
        super().__init__("section", None, {"kicker": kicker, "title": title, "subtitle": subtitle})

    def number(self, number: int) -> None:
        """Give the section its number, as its slide shows it ("02"), unless it has a kicker of its own."""
        if not self._arguments.get("kicker"):
            self._arguments["kicker"] = f"{number:02d}"


class QuestionsSlide(DrawnSlide):
    """The closing slide: a question to the audience ("Questions?"), and a subtitle, if any."""

    required_arguments = ("title",)

    def __init__(self, title: str | None, subtitle: str | None = None):
        super().__init__("questions", None, {"title": title, "subtitle": subtitle, "mark": "?"})


# NATIVE DIAGRAMS, drawn as texts on shapes too (Venn diagrams and 2×2 matrices have their own drawing: DiagramSlide)


def _listed(prefix: str, most: int, items: Sequence[str | None]) -> dict[str, str | None]:
    """The items that are there, in order, as numbered arguments (prefix_1, prefix_2...), the rest None."""
    there = [item for item in items if item][:most]
    return {f"{prefix}_{index}": there[index - 1] if index <= len(there) else None for index in range(1, most + 1)}


class TimelineSlide(DrawnSlide):
    """Three to five moments along a line, oldest first, each a date and what happened: the last one, the
    punchline, appears on a click."""

    required_arguments = ("date_1", "event_1", "date_2", "event_2", "date_3", "event_3")

    def __init__(self, title: str | None, *dates_and_events: str | None):
        moments = [
            (date, event)
            for date, event in zip(dates_and_events[::2], dates_and_events[1::2], strict=False)
            if date and event
        ][:5]
        arguments: dict[str, str | None] = {"title": title}
        for index in range(1, 6):
            date, event = moments[index - 1] if index <= len(moments) else (None, None)
            arguments[f"date_{index}"], arguments[f"event_{index}"] = date, event
        super().__init__("timeline", None, arguments)

    def clicks(self) -> dict[str, int]:
        last = max(index for index in range(1, 6) if self._arguments.get(f"event_{index}") or index == 1)
        return {f"date_{last}": 1, f"event_{last}": 1}


class PyramidSlide(DrawnSlide):
    """Three or four levels of a pyramid, from its top (the rarest, the punchline, which appears on a click) down to
    its base."""

    required_arguments = ("level_1", "level_2", "level_3")

    def __init__(self, title: str | None, *levels: str | None):
        super().__init__("pyramid", None, {"title": title, **_listed("level", 4, levels)})

    def clicks(self) -> dict[str, int]:
        return {"level_1": 1}


class FunnelSlide(DrawnSlide):
    """Three to five stages of a funnel, from its widest at the top to its narrowest at the bottom: the last one, the
    punchline, appears on a click."""

    required_arguments = ("stage_1", "stage_2", "stage_3")

    def __init__(self, title: str | None, *stages: str | None):
        super().__init__("funnel", None, {"title": title, **_listed("stage", 5, stages)})

    def clicks(self) -> dict[str, int]:
        last = max(index for index in range(1, 6) if self._arguments.get(f"stage_{index}") or index == 1)
        return {f"stage_{last}": 1}


class CycleSlide(DrawnSlide):
    """Three to five steps around a circle, each leading to the next, and the last back to the first."""

    required_arguments = ("step_1", "step_2", "step_3")

    def __init__(self, title: str | None, *steps: str | None):
        super().__init__("cycle", None, {"title": title, **_listed("step", 5, steps)})


class OrgChartSlide(DrawnSlide):
    """A small org chart: who's in charge (the punchline, which appears on a click) over two to four people."""

    required_arguments = ("boss", "report_1", "report_2")

    def __init__(self, title: str | None, boss: str | None, *reports: str | None):
        super().__init__("org_chart", None, {"title": title, "boss": boss, **_listed("report", 4, reports)})

    def clicks(self) -> dict[str, int]:
        return {"boss": 1}


class IcebergSlide(DrawnSlide):
    """An iceberg: what everyone sees, above the water, and two or three things under it, which appear on a click."""

    required_arguments = ("tip", "hidden_1", "hidden_2")

    def __init__(self, title: str | None, tip: str | None, *hidden: str | None):
        super().__init__("iceberg", None, {"title": title, "tip": tip, **_listed("hidden", 3, hidden)})

    def clicks(self) -> dict[str, int]:
        return {f"hidden_{index}": 1 for index in range(1, 4)}
