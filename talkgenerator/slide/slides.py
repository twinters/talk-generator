import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from talkgenerator.datastructures.image_data import CreditPart, ImageData
from talkgenerator.images import analysis
from talkgenerator.models import classic
from talkgenerator.models import deck as model
from talkgenerator.plan.languages import ENGLISH, Language
from talkgenerator.render import charts
from talkgenerator.render.powerpoint import render_slide
from talkgenerator.slide import powerpoint_slide_creator
from talkgenerator.util import image_util, os_util, random_util

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
        # The real facts it shows as they are (a classic slide's: see talkgenerator.facts), for the deck
        self.facts: list[model.Fact] = []
        self._text_credits = False  # (whether it credits a text too: a real fact it shows or builds on)

    @property
    def type_name(self) -> str:
        return self._type_name

    def add_source(
        self,
        source: str | None,
        url: str | None = None,
        credit: Sequence[CreditPart] | None = None,
        image: ImageData | None = None,
        text: bool = False,
    ):
        """Credit an image source (for the image, if given), or with text, a text's (a real fact the slide shows or
        builds on: see talkgenerator.facts). In the PowerPoint, the credit links to the url (if given), or reads as the
        given credit parts, each linking to its own page."""
        if source is not None:
            self._sources.append(source)
            self._source_urls.append(url)
            self._credits.append(tuple(credit) if credit else ((source, url),))
            self._credited.append(image)
            self._text_credits = self._text_credits or text

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

    def picture_title(self) -> str | None:
        """The title a picture in its place goes under (a chart's or a diagram's that tries a picture first: D73): its
        title, or else its question (a yes-or-no chart's, a flowchart's); None when it has neither."""
        for role in ("title", "question"):
            value = self._arguments.get(role)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @property
    def note(self) -> str:
        """The debug information about how the slide was generated, so far."""
        return self._note

    def set_note(self, note: str):
        """Debug information about how the slide was generated."""
        self._note = note

    def add_note(self, note: str) -> None:
        """A line more of debug information (what a slide that ran out of time became, say)."""
        self._note = f"{self._note}\n{note}" if self._note else note

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
            if value is None:  # (a list's thing that's a picture in its text's place, as its pattern break: D73)
                value = self._arguments.get(picture_role(name))
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
            text_credits=True if self._text_credits else None,
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
        vision=image.vision,
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
        trendlines: Sequence[tuple[int, model.Trendline]] = (),
        point_picture: ImageData | None = None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        # (a classic trend's picture by its named moment comes as the picture of its "event": see slides.Pictures)
        point_picture = point_picture or (pictures or {}).get("event")
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
                "trendlines": tuple(trendlines),
                "point_picture": point_picture if point_labels else None,  # (by a trend's named point)
            },
        )

    def to_deck_slide(self) -> model.DeckSlide:
        """The chart's numbers, axis titles, named points, fitted lines and how it appears go into the deck; the
        renderer styles the chart by its type (the chart_modifier stays out: a deck holds data, not functions). A
        picture by a trend's named point appears on a click of its own, after the second line's, if it has one (where
        the layout puts it: see talkgenerator.design.engine.point_picture)."""
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
            chart = charts.with_trendlines(chart, self._arguments.get("trendlines") or ())
            elements.append(model.ChartElement(role="chart", chart=chart))
            picture = _to_element(POINT_PICTURE, self._arguments.get(POINT_PICTURE), "cover")
            if isinstance(picture, model.ImageElement) and charts.named_point(chart) is not None:
                after = len(chart.series) - 1 if chart.reveal == "series" else 0  # (the second line's click)
                elements.append(picture.model_copy(update={"appears_on_click": after + 1}))
        return self._deck_slide(tuple(elements))


# The role of the picture by a trend's named point
POINT_PICTURE = "point_picture"


@dataclass(frozen=True)
class Pictures:
    """Pictures in some of a diagram's boxes, by the role of the box's text ("step_2", "top_left"): what a classic
    generator gives after its slide's other arguments, which talkgenerator.slide.slide_generator_types passes on to
    the slide by name (docs/v5-plan.md, D64)."""

    boxes: tuple[tuple[str, ImageData], ...] = ()

    def by_box(self) -> dict[str, ImageData]:
        return dict(self.boxes)


def picture_role(box: str) -> str:
    """The role of the picture in a diagram's box, by the role of the box's text: "step_2_picture"."""
    return f"{box}_picture"


# How often a diagram has pictures in some of its boxes, and how often two of them (of those that have any, where
# two may), for the language model's diagrams and classic ones alike (docs/v5-plan.md, D64)
PICTURE_ODDS = 0.35
# What a slide's presentation context says when the slide stands in for one that ran out of time, as the text
# version of a chart or a diagram that tries a picture first (D73): its boxes look no picture up
STANDING_IN: Final = "standing_in"
TWO_PICTURES = 0.3


def picked_boxes(boxes: Sequence[str], most: int = 2, odds: float = PICTURE_ODDS) -> list[str]:
    """The boxes that get a picture, by the dice (the talk's random stream in use): none most of the time, else one
    or, now and then, two (at most so many), in the boxes' order."""
    if not boxes or random_util.random() >= odds:
        return []
    count = 2 if most >= 2 and random_util.random() < TWO_PICTURES else 1
    return sorted(random_util.sample(list(boxes), min(count, len(boxes))), key=list(boxes).index)


# The boxes of a Venn diagram and of a matrix that can have a picture: its first two circles (beside them, or in their
# part of the circle, as their labels leave room: see talkgenerator.design.engine), and its quadrants
VENN_BOXES = ("circle_1", "circle_2")
MATRIX_BOXES = ("top_left", "top_right", "bottom_left", "bottom_right")


class DiagramSlide(Slide):
    """A diagram drawn as shapes, under a title: a Venn diagram or a 2×2 matrix (see talkgenerator.render.diagrams),
    with pictures by some of its circles or in some of its quadrants, if it has them (there from the start)."""

    required_arguments = ("diagram",)

    def __init__(
        self,
        title: str | None,
        diagram: model.VennDiagram | model.MatrixDiagram | None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        boxes = VENN_BOXES if isinstance(diagram, model.VennDiagram) else MATRIX_BOXES
        arguments: dict[str, object] = {"title": title, "diagram": diagram}
        for box in boxes:
            picture = (pictures or {}).get(box)
            if picture is not None:
                arguments[picture_role(box)] = picture
        super().__init__(
            type_name="diagram",
            ppt_slide_creator=powerpoint_slide_creator.create_diagram_slide,
            arguments=arguments,
        )

    def to_deck_slide(self) -> model.DeckSlide:
        elements: list[model.TextElement | model.ImageElement | model.ChartElement | model.DiagramElement] = []
        title = _to_element("title", self._arguments.get("title"), "contain")
        if title is not None:
            elements.append(title)
        diagram = self._arguments.get("diagram")
        if diagram is not None:
            elements.append(model.DiagramElement(role="diagram", diagram=diagram))
        for box in (*VENN_BOXES, *MATRIX_BOXES):
            picture = _to_element(picture_role(box), self._arguments.get(picture_role(box)), "cover")
            if picture is not None:
                elements.append(picture)
        return self._deck_slide(tuple(elements))


# MILESTONE 6'S SLIDE TYPES: drawn as texts on shapes (see talkgenerator.design.engine), also in a classic deck, in the
# 2019 template's look (talkgenerator.render.powerpoint)

# A quiz's options, as its slides name them
LETTERS = "ABCD"


class DrawnSlide(Slide):
    """A slide of a type that the 2019 template has no layout for (milestone 6's: big numbers, quizzes, posts...):
    its texts (and photo) by role, which the layout engine places on shapes in a theme's colours, and a classic deck
    in the template's (talkgenerator.models.classic.DRAWN_TYPES). Some of its elements may appear on a click: a
    slide of a list of things (figures, levels, steps...) shows its title (and the list's frame: a timeline's line,
    an iceberg) from the start, and its things one by one, a click each, the punchline last (docs/v5-plan.md, D53)."""

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

    def _there(self, *roles: str) -> bool:
        return any(self._arguments.get(role) for role in roles)

    def _one_by_one(self, *groups: Sequence[str]) -> dict[str, int]:
        """The groups of roles that the slide has (a figure's number and label, say), each on a click of its own, in
        order: the first on the slide's first click."""
        there = [group for group in groups if self._there(*group)]
        return {role: click for click, group in enumerate(there, 1) for role in group}


class BigNumberSlide(DrawnSlide):
    """A big number, with what it counts under it, and a title and a (made-up) source, if any; and a picture of what
    it's about behind it (or beside it), if it has one (D63)."""

    required_arguments = ("number", "label")

    def __init__(
        self,
        title: str | None,
        number: str | None,
        label: str | None,
        source: str | None = None,
        background: ImageData | None = None,
    ):
        arguments = {"background": background, "title": title, "number": number, "label": label, "source": source}
        super().__init__("big_number", None, arguments)


class KpiSlide(DrawnSlide):
    """Three or four figures under a title, each a number and what it measures, appearing one by one, a click each:
    the last one is the punchline; over a picture of what they're about, if it has one (D63)."""

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
        background: ImageData | None = None,
    ):
        fourth = bool(number_4 and label_4)  # (a fourth figure is both, or none)
        figures = ((number_1, label_1), (number_2, label_2), (number_3, label_3), (number_4, label_4))
        arguments: dict[str, str | ImageData | None] = {"background": background, "title": title}
        for index, (number, label) in enumerate(figures, 1):
            arguments[f"number_{index}"] = number if index < 4 or fourth else None
            arguments[f"label_{index}"] = label if index < 4 or fourth else None
        super().__init__("kpi", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*((f"number_{index}", f"label_{index}") for index in range(1, 5)))


class QuizSlide(DrawnSlide):
    """A quiz: a question, and three or four options (A to D), appearing one by one, a click each; on the click
    after them, the answer (the letter of the right option) and its explanation, if any."""

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
        options = [(f"letter_{index}", f"option_{index}") for index in range(1, 5)]
        return self._one_by_one(*options, ("answer", "explanation"))


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
    """The talk's agenda: three to five items, numbered, under a title, appearing one by one, a click each."""

    required_arguments = ("item_1", "item_2", "item_3")

    def __init__(self, title: str | None, *items: str | None):
        listed = [item for item in items if item][:5]
        arguments: dict[str, str | None] = {"title": title}
        for index in range(1, 6):
            item = listed[index - 1] if index <= len(listed) else None
            arguments[f"number_{index}"] = str(index) if item else None
            arguments[f"item_{index}"] = item
        super().__init__("agenda", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*((f"number_{index}", f"item_{index}") for index in range(1, 6)))


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
    """The closing slide: a question to the audience ("Questions?"), a subtitle, if any (a last tip, say), and a
    picture to end on, if it has one: a funny one, or, as a callback, an earlier slide's picture, which the deck gives
    it once the slides before it are in (see call_back). The callback says what that picture showed (in a model's
    words: "" for any of them), and pick is the dice's share of the way along the earlier pictures, for when no
    picture's words match it; a line that only makes sense with the picture (a classic "Remember this one?") goes
    when there's none."""

    required_arguments = ("title",)

    def __init__(
        self,
        title: str | None,
        subtitle: str | None = None,
        photo: ImageData | None = None,
        callback: str | None = None,
        pick: float = 0.0,
        line_needs_picture: bool = False,
    ):
        super().__init__("questions", None, {"photo": photo, "title": title, "subtitle": subtitle, "mark": "?"})
        self.callback = callback
        self._pick = pick
        self._line_needs_picture = line_needs_picture

    def call_back(self, earlier: Sequence[Slide]) -> ImageData | None:
        """Show an earlier slide's picture again, as the callback (if this slide calls back, and has no picture yet):
        the one whose search query and description share the most words with the callback, or else the dice's pick
        of them (not a meme's template, which is no joke without its captions); credited as on its slide. The
        picture, or None when there's none to call back to."""
        if self.callback is None or self._arguments.get("photo") is not None:
            return None
        pictures: list[ImageData] = []
        for slide in earlier:
            if isinstance(slide, MemeSlide):
                continue
            pictures += [value for value in slide._arguments.values() if isinstance(value, ImageData)]
        pictures = [picture for index, picture in enumerate(pictures) if picture not in pictures[:index]]
        if not pictures:
            if self._line_needs_picture:
                self._arguments["subtitle"] = None
            return None
        wanted = _words(self.callback)
        scores = [len(wanted & _words(f"{picture.query or ''} {picture.description or ''}")) for picture in pictures]
        best = max(scores)
        picked = (
            pictures[scores.index(best)] if best else pictures[min(len(pictures) - 1, int(self._pick * len(pictures)))]
        )
        self._arguments["photo"] = picked
        self.add_source(picked.get_source(), picked.get_source_url(), picked.get_credit(), image=picked)
        return picked


def _words(text: str) -> set[str]:
    """A text's words, in lowercase, without little words: to tell what two texts share."""
    return set(re.findall(r"[a-z]+", text.lower())) - _LITTLE


_LITTLE: Final = frozenset("a an the of and or in on at to for with by from its it is are this that".split())


class CloserSlide(DrawnSlide):
    """The talk's closer (docs/v5-plan.md, D76): the slide after its last, which says the talk is over, outside the
    slides it asked for (its deck marks it, and none of its numbers count it). Its big words ("Thank you!",
    "Questions?", "Let's talk"...), a line under them (the presenter's name, a made-up contact line...), a small note,
    if any, and for big words that ask a question, a huge question mark beside them, in a layout of its own (see
    talkgenerator.closers, which makes them)."""

    required_arguments = ("title",)

    def __init__(self, title: str | None, subtitle: str | None = None, note: str | None = None, mark: bool = False):
        super().__init__(
            "closer", None, {"title": title, "subtitle": subtitle, "note": note, "mark": "?" if mark else None}
        )

    def to_deck_slide(self) -> model.DeckSlide:
        return super().to_deck_slide().model_copy(update={"closer": True})


# NATIVE DIAGRAMS, drawn as texts on shapes too (Venn diagrams and 2×2 matrices have their own drawing: DiagramSlide)


def _listed(
    prefix: str, most: int, items: Sequence[str | None], pictures: Mapping[str, ImageData | None] | None = None
) -> dict[str, Any]:
    """The items that are there, in order, as numbered arguments (prefix_1, prefix_2...), the rest None; and the
    pictures of their boxes, by the items' numbers as written ("level_3" for the third level written, even when the
    second stayed empty), as the picture of the item's argument ("level_2_picture", then)."""
    there = [(number, item) for number, item in enumerate(items, 1) if item][:most]
    arguments: dict[str, Any] = {
        f"{prefix}_{index}": there[index - 1][1] if index <= len(there) else None for index in range(1, most + 1)
    }
    for index, (number, _) in enumerate(there, 1):
        picture = (pictures or {}).get(f"{prefix}_{number}")
        if picture is not None:
            arguments[picture_role(f"{prefix}_{index}")] = picture
    return arguments


def _instead(
    prefix: str, most: int, items: Sequence[str | None], pictures: Mapping[str, ImageData | None] | None
) -> dict[str, Any]:
    """The items that are there, in order, as numbered arguments (prefix_1, prefix_2...), the rest None, as _listed has
    them; but an item with a picture (by its number as written) is that picture in its text's place, as a list's
    pattern break (docs/v5-plan.md, D73): its argument None, its picture's role the picture."""
    there = [
        (number, item) for number, item in enumerate(items, 1) if item or (pictures or {}).get(f"{prefix}_{number}")
    ][:most]
    arguments: dict[str, Any] = {}
    for index in range(1, most + 1):
        number, item = there[index - 1] if index <= len(there) else (0, None)
        picture = (pictures or {}).get(f"{prefix}_{number}") if number else None
        arguments[f"{prefix}_{index}"] = None if picture is not None else item
        if picture is not None:
            arguments[picture_role(f"{prefix}_{index}")] = picture
    return arguments


def _or_its_picture(role: str) -> tuple[str, str]:
    """A thing's text, or the picture in its place (D73): whichever it has appears on its click."""
    return role, picture_role(role)


def _with_pictures(
    arguments: dict[str, object], boxes: Sequence[str], pictures: Mapping[str, ImageData | None] | None
) -> dict[str, object]:
    """The arguments, with the pictures of those boxes that have one and a text (a flowchart's steps, an iceberg's
    tip)."""
    for box in boxes:
        picture = (pictures or {}).get(box)
        if picture is not None and arguments.get(box):
            arguments[picture_role(box)] = picture
    return arguments


class TimelineSlide(DrawnSlide):
    """Three to five moments along a line, oldest first, each a date and what happened, appearing one by one, a
    click each: the last one is the punchline."""

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
        return self._one_by_one(*((f"date_{index}", f"event_{index}") for index in range(1, 6)))


class PyramidSlide(DrawnSlide):
    """Three or four levels of a pyramid, from its top (the rarest, the punchline) down to its base, appearing one
    by one, a click each, from the base up (each with its picture, if it has one)."""

    required_arguments = ("level_1", "level_2", "level_3")

    def __init__(self, title: str | None, *levels: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        super().__init__("pyramid", None, {"title": title, **_listed("level", 4, levels, pictures)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_with_its_picture(f"level_{index}") for index in range(4, 0, -1)))


def _with_its_picture(box: str) -> tuple[str, str]:
    """A box's text and its picture, which appear together."""
    return box, picture_role(box)


class FunnelSlide(DrawnSlide):
    """Three to five stages of a funnel, from its widest at the top to its narrowest at the bottom, the punchline,
    appearing one by one, a click each (each with its picture, if it has one)."""

    required_arguments = ("stage_1", "stage_2", "stage_3")

    def __init__(self, title: str | None, *stages: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        super().__init__("funnel", None, {"title": title, **_listed("stage", 5, stages, pictures)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_with_its_picture(f"stage_{index}") for index in range(1, 6)))


class CycleSlide(DrawnSlide):
    """Three to five steps around a circle, each leading to the next, and the last back to the first, appearing one
    by one, a click each (a step's picture, if it has one, with it: in the middle of the circle)."""

    required_arguments = ("step_1", "step_2", "step_3")

    def __init__(self, title: str | None, *steps: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        super().__init__("cycle", None, {"title": title, **_listed("step", 5, steps, pictures)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_with_its_picture(f"step_{index}") for index in range(1, 6)))


class OrgChartSlide(DrawnSlide):
    """A small org chart: who's in charge (the punchline) over two to four people, who appear one by one, a click
    each, and who's in charge on the click after them."""

    required_arguments = ("boss", "report_1", "report_2")

    def __init__(
        self,
        title: str | None,
        boss: str | None,
        *reports: str | None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        # (who's in charge may be a picture in their name's place, as the chart's pattern break: D73)
        picture = (pictures or {}).get("boss")
        arguments: dict[str, Any] = {"title": title, "boss": None if picture is not None else boss}
        if picture is not None:
            arguments[picture_role("boss")] = picture
        super().__init__("org_chart", None, {**arguments, **_listed("report", 4, reports)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*((f"report_{index}",) for index in range(1, 5)), _or_its_picture("boss"))


class IcebergSlide(DrawnSlide):
    """An iceberg: what everyone sees, above the water, and two or three things under it, which appear one by one,
    a click each (each with its picture, if it has one; the tip's is there with it from the start)."""

    required_arguments = ("tip", "hidden_1", "hidden_2")

    def __init__(
        self,
        title: str | None,
        tip: str | None,
        *hidden: str | None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        arguments = {"title": title, "tip": tip, **_listed("hidden", 3, hidden, pictures)}
        super().__init__("iceberg", None, _with_pictures(arguments, ("tip",), pictures))

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_with_its_picture(f"hidden_{index}") for index in range(1, 4)))


class ProcessSlide(DrawnSlide):
    """A process: three to five steps, each leading to the next by an arrow, appearing one by one, a click each: the
    last one is the punchline (a talk format's method, or how its product works). A step's picture, if it has one,
    comes with it."""

    required_arguments = ("step_1", "step_2", "step_3")

    def __init__(self, title: str | None, *steps: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        super().__init__("process", None, {"title": title, **_listed("step", 5, steps, pictures)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_with_its_picture(f"step_{index}") for index in range(1, 6)))


REFERENCES = 5  # the most works a references slide lists


class ReferencesSlide(DrawnSlide):
    """A talk's references, as an academic talk ends with them: three to five works, numbered as citations ("[1]"),
    appearing one by one, a click each; and a picture of one of them, if it has one (a book's cover, or a figure from a
    paper), with a caption that says which ("Cover of [2]"), on the click after them (docs/v5-plan.md, D65)."""

    required_arguments = ("item_1", "item_2", "item_3")

    def __init__(
        self, title: str | None, *works: str | None, figure: ImageData | None = None, caption: str | None = None
    ):
        listed = [work.strip() for work in works if work and work.strip()][:REFERENCES]
        arguments: dict[str, object] = {"title": title}
        for index in range(1, REFERENCES + 1):
            work = listed[index - 1] if index <= len(listed) else None
            arguments[f"number_{index}"] = f"[{index}]" if work else None
            arguments[f"item_{index}"] = work
        arguments["figure"] = figure
        arguments["caption"] = caption if figure is not None else None
        super().__init__("references", None, arguments)

    def clicks(self) -> dict[str, int]:
        works = ((f"number_{index}", f"item_{index}") for index in range(1, REFERENCES + 1))
        return self._one_by_one(*works, ("figure", "caption"))


class FunFactSlide(DrawnSlide):
    """A fun fact: one absurd fact, stated as certain, under a heading in the talk's language ("Did you know?"), with
    its (made-up) source and a photo, if it has them."""

    required_arguments = ("kicker", "fact")

    def __init__(self, kicker: str | None, fact: str | None, source: str | None = None, photo: ImageData | None = None):
        super().__init__("fun_fact", None, {"kicker": kicker, "fact": fact, "source": source, "photo": photo})


class ProblemSlide(DrawnSlide):
    """The problem a talk is about, early on, to hook its audience (docs/v5-plan.md, D69): a short heading ("The
    problem", "Motivation", "Sound familiar?"), the problem in big words, and a line under it that makes it hit home,
    which appears on a click; over a picture of it (its background), or beside a picture that shows it (its photo), if
    it has one."""

    required_arguments = ("kicker", "problem")

    def __init__(
        self,
        kicker: str | None,
        problem: str | None,
        detail: str | None = None,
        background: ImageData | None = None,
        photo: ImageData | None = None,
    ):
        arguments = {"background": background, "photo": photo, "kicker": kicker, "problem": problem, "detail": detail}
        super().__init__("problem", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(("detail",))


# The most letters an acronym has, and the tiers of a tier list, best first (as tier lists have them)
ACRONYM_LETTERS = 6
TIERS = ("S", "A", "B", "C", "F")
TIER_ITEMS = 3  # the most things in a tier


class AcronymSlide(DrawnSlide):
    """A made-up method, as an acronym: its letters, each with the word it stands for (three to six), under a title;
    the words appear one by one, a click each, the last one the punchline."""

    required_arguments = ("letter_1", "word_1", "letter_2", "word_2", "letter_3", "word_3")

    def __init__(self, title: str | None, *words: str | None):
        listed = [word.strip() for word in words if word and word.strip()][:ACRONYM_LETTERS]
        arguments: dict[str, str | None] = {"title": title}
        for index in range(1, ACRONYM_LETTERS + 1):
            word = listed[index - 1] if index <= len(listed) else None
            arguments[f"letter_{index}"] = word[0].upper() if word else None
            arguments[f"word_{index}"] = word
        super().__init__("acronym", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*((f"word_{index}",) for index in range(1, ACRONYM_LETTERS + 1)))


class DareSlide(DrawnSlide):
    """A dare for the presenter: a playful task for the next slide or the rest of the talk, under a heading in the
    talk's language ("Challenge")."""

    required_arguments = ("kicker", "dare")

    def __init__(self, kicker: str | None, dare: str | None):
        super().__init__("dare", None, {"kicker": kicker, "dare": dare})


class FlowchartSlide(DrawnSlide):
    """A flowchart that pretends to help decide: a yes-or-no question, where each answer leads (labelled with the
    talk's words for yes and no), and the end both lead to, the punchline: Yes's way on a click, No's on the next,
    and the end on the one after."""

    required_arguments = ("question", "yes_step", "no_step", "end")

    def __init__(
        self,
        title: str | None,
        question: str | None,
        yes_step: str | None,
        no_step: str | None,
        end: str | None,
        yes: str = "Yes",
        no: str = "No",
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        arguments: dict[str, object] = {
            "title": title,
            "question": question,
            "yes": yes,
            "no": no,
            "yes_step": yes_step,
            "no_step": no_step,
            "end": end,
        }
        super().__init__("flowchart", None, _with_pictures(arguments, FLOWCHART_BOXES, pictures))

    def clicks(self) -> dict[str, int]:
        steps = (("yes", *_with_its_picture("yes_step")), ("no", *_with_its_picture("no_step")))
        return self._one_by_one(*steps, _with_its_picture("end"))


# The boxes of a flowchart that can have a picture: where each answer leads, and the end
FLOWCHART_BOXES = ("yes_step", "no_step", "end")


def tier_items(text: str | None) -> list[str]:
    """The things of a tier, as written: separated by |, at most three."""
    return [part.strip() for part in (text or "").split("|") if part.strip()][:TIER_ITEMS]


class TierListSlide(DrawnSlide):
    """A tier list: things ranked in tiers, from S (the best) to F (the worst), each tier a row of one to three things
    under its letter (each tier as written: its things separated by |). The tiers' letters are there from the start,
    and each tier's things appear on a click of their own, from the worst tier up to the S tier, the punchline. A tier
    without things is left out."""

    required_arguments = ("tier_s", "item_s_1", "tier_a", "item_a_1")

    def __init__(self, title: str | None, *tiers: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        arguments: dict[str, Any] = {"title": title}
        for letter, written in zip(TIERS, (*tiers, *([None] * len(TIERS)))[: len(TIERS)], strict=True):
            key = letter.lower()
            # (a tier may be a picture in its things' place, as the list's pattern break: the S tier's, D73)
            picture = (pictures or {}).get(f"{key}_tier")
            things = tier_items(written) if picture is None else []
            arguments[f"tier_{key}"] = letter if things or picture is not None else None
            for index in range(1, TIER_ITEMS + 1):
                arguments[f"item_{key}_{index}"] = things[index - 1] if index <= len(things) else None
            if picture is not None:
                arguments[picture_role(f"item_{key}_1")] = picture
        super().__init__("tier_list", None, arguments)

    def clicks(self) -> dict[str, int]:
        tiers = [tier.lower() for tier in reversed(TIERS)]  # (the worst first)
        groups = (
            (*(f"item_{tier}_{index}" for index in range(1, TIER_ITEMS + 1)), picture_role(f"item_{tier}_1"))
            for tier in tiers
        )
        return self._one_by_one(*groups)


def listed_items(text: str | None, most: int) -> list[str]:
    """The things of a list written as one text: separated by | (or on lines of their own), each without a bullet or
    a number of its own in front ("• ", "- ", "3. "), at most so many."""
    parts = re.split(r"\s*\|\s*|\s*\n\s*", text or "")
    return [_BULLET.sub("", part).strip() for part in parts if _BULLET.sub("", part).strip()][:most]


_BULLET = re.compile(r"^\s*(?:[•·*▪◦‣–—-]+|\d{1,2}[.)])\s*")

# The most points a wall of text has (besides its highlighted one), and the fewest that make a wall
WALL_POINTS = 16
WALL_FEWEST = 5
# A wall's points go in a rhythm of top-level points and points under them (as nested bullets): this one, over and
# over (True: under the point before it)
_WALL_RHYTHM = (False, True, True, False, True, False, True, True, True, False, False, True)


class WallOfTextSlide(DrawnSlide):
    """A wall of text that nobody can read, as an executive summary: dense points of jargon in fine print, some as
    points under others, with one more point hidden among them (in the middle, a little past it), the punchline, which
    a marker highlights on the slide's one click; under it all, "continued on next slide" in the talk's language."""

    required_arguments = ("title", *(f"point_{index}" for index in range(1, WALL_FEWEST + 1)), "highlight")

    def __init__(self, title: str | None, highlight: str | None, continued: str | None, *points: str | None):
        listed = [point.strip() for point in points if point and point.strip()][:WALL_POINTS]
        at = classic.highlighted_at(len(listed))
        bullets = [_WALL_RHYTHM[index % len(_WALL_RHYTHM)] for index in range(len(listed) + 1)]
        bullets[0] = False  # (the first point is no point under another)
        arguments: dict[str, str | None] = {"title": title}
        for index in range(1, WALL_POINTS + 1):
            if index > len(listed):
                arguments[f"point_{index}"] = None
                continue
            position = index - 1 if index <= at else index  # (the points after the highlighted one move down one)
            bullet = classic.SUB_BULLET if bullets[position] else classic.TOP_BULLET
            arguments[f"point_{index}"] = bullet + listed[index - 1]
        highlighted = (highlight or "").strip()
        bullet = classic.SUB_BULLET if bullets[at] else classic.TOP_BULLET
        arguments["highlight"] = bullet + highlighted if highlighted else None
        arguments["continued"] = continued
        super().__init__("wall_of_text", None, arguments)


# An alignment chart's cells, in reading order: lawful to chaotic across, good to evil down
ALIGNMENTS = classic.ALIGNMENTS


class AlignmentChartSlide(DrawnSlide):
    """An alignment chart: nine things in a grid of three by three, lawful to chaotic across and good to evil down
    (the axes' words in the talk's language), which appear one by one, a click each, in reading order: chaotic evil,
    the punchline, last."""

    required_arguments = ALIGNMENTS

    def __init__(
        self,
        title: str | None,
        columns: Sequence[str],
        rows: Sequence[str],
        *cells: str | None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        arguments: dict[str, Any] = {"title": title}
        for index in range(1, 4):
            arguments[f"column_{index}"] = columns[index - 1] if index <= len(columns) else None
            arguments[f"row_{index}"] = rows[index - 1] if index <= len(rows) else None
        for index, alignment in enumerate(ALIGNMENTS):
            cell = cells[index] if index < len(cells) else None
            # (a cell may be a picture in its thing's place, as the chart's pattern break: chaotic evil's, D73)
            picture = (pictures or {}).get(alignment)
            arguments[alignment] = cell.strip() if cell and cell.strip() and picture is None else None
            if picture is not None:
                arguments[picture_role(alignment)] = picture
        super().__init__("alignment_chart", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_or_its_picture(alignment) for alignment in ALIGNMENTS))


RED_FLAGS = 5  # the most red flags a slide has


class RedFlagsSlide(DrawnSlide):
    """Red flags: three to five warning signs about something, each beside a red flag, appearing one by one, a click
    each: the last one is the punchline."""

    required_arguments = ("flag_1", "flag_2", "flag_3")

    def __init__(self, title: str | None, *flags: str | None, pictures: Mapping[str, ImageData | None] | None = None):
        # (a flag may be a picture in its words' place, as the list's pattern break: the last one's, D73)
        super().__init__("red_flags", None, {"title": title, **_instead("flag", RED_FLAGS, flags, pictures)})

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(*(_or_its_picture(f"flag_{index}") for index in range(1, RED_FLAGS + 1)))


REVIEWS = 3  # the most reviews a slide has
MOST_STARS = 5


def stars(rating: object) -> int | None:
    """A rating as a number of stars, from 1 to 5 ("4", "4/5", "4 stars", "★★★★☆" all give 4); None when it's no
    rating."""
    text = str(rating or "").strip()
    if "★" in text:
        return min(MOST_STARS, text.count("★"))
    match = re.match(r"(\d+(?:[.,]\d+)?)", text)
    if match is None:
        return None
    number = round(float(match.group(1).replace(",", ".")))
    return number if 1 <= number <= MOST_STARS else None


class ReviewsSlide(DrawnSlide):
    """Made-up reviews of something: two or three, each its stars (from one to five, drawn, and as "4/5" beside them),
    what the reviewer wrote and who they are; appearing one by one, a click each: the last one, a one-star review most
    of the time, is the punchline. (Each review as three arguments in a row: its stars, its text and its reviewer.)"""

    required_arguments = ("stars_1", "review_1", "stars_2", "review_2")

    def __init__(
        self,
        title: str | None,
        *stars_reviews_and_reviewers: object,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        given = stars_reviews_and_reviewers
        # (a review may be a picture its reviewer posted, in its words' place, as the list's pattern break: the last
        # one's, by its number as written, D73)
        written: list[tuple[int, str, str, ImageData | None]] = []
        for index in range(0, len(given) - 1, 3):
            rating, review = stars(given[index]), str(given[index + 1] or "").strip()
            reviewer = str(given[index + 2] or "").strip() if index + 2 < len(given) else ""
            picture = (pictures or {}).get(f"review_{index // 3 + 1}")
            if rating is not None and (review or picture is not None):
                written.append((rating, review, reviewer, picture))
        arguments: dict[str, Any] = {"title": title}
        for index in range(1, REVIEWS + 1):
            there = index <= len(written)
            given_stars, given_review, given_reviewer, picture = written[index - 1] if there else (0, "", "", None)
            arguments[f"stars_{index}"] = f"{given_stars}/{MOST_STARS}" if there else None
            arguments[f"review_{index}"] = given_review if there and picture is None else None
            arguments[f"reviewer_{index}"] = f"— {given_reviewer}" if there and given_reviewer else None
            if picture is not None:
                arguments[picture_role(f"review_{index}")] = picture
        super().__init__("reviews", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(
            *(
                (f"stars_{index}", *_or_its_picture(f"review_{index}"), f"reviewer_{index}")
                for index in range(1, REVIEWS + 1)
            )
        )


ERROR_BUTTONS = 3  # the most buttons an error message has


class ErrorMessageSlide(DrawnSlide):
    """A fake error message, as if the talk itself crashed: a dialog's title, an icon ("!"), the message, an error
    code (if any), and two or three buttons, the last one the punchline ("Panic"). It comes up whole: an error doesn't
    build up."""

    required_arguments = ("message", "button_1", "button_2")

    def __init__(self, title: str | None, message: str | None, code: str | None, *buttons: str | None):
        arguments: dict[str, str | None] = {"title": title, "icon": "!", "message": message, "code": code}
        arguments.update(_listed("button", ERROR_BUTTONS, buttons))
        super().__init__("error_message", None, arguments)


# SLIDES OF A PICTURE TO EXPLAIN (docs/v5-plan.md, D78): a surprising picture the presenter has to explain, with little
# or no text, as improv suggestions and story cubes give a performer something to explain: Exhibit A, two pictures to
# pick one of, a picture equation, a picture to see something in (or an inkblot), and a before and after


def case_number(language: Language = ENGLISH) -> str:
    """A made-up case's number, as the talk's language writes one ("Case No. 4417-23"), by the dice."""
    return language.case.format(number=f"{random_util.randint(1000, 9999)}-{random_util.randint(10, 99)}")


def exhibit_letter(number: int) -> str:
    """The letter of a talk's number-th exhibit (from 1): A, B, C..., and after Z, AA, AB..."""
    letters = ""
    while number > 0:
        number, rest = divmod(number - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters or "A"


class ExhibitSlide(DrawnSlide):
    """A piece of evidence: one odd picture, as Exhibit A of a case (its word in the talk's language, and its letter),
    the case's number, and a short note, if it has one, as on an evidence tag; the presenter explains what it proves.
    The deck letters a talk's exhibits in turn: a later one is Exhibit B, of the same case (see lettered)."""

    required_arguments = ("label", "picture")

    def __init__(self, exhibit: str, case: str | None, picture: ImageData | None, note: str | None = None):
        self._exhibit = exhibit  # (the word before the letter: "Exhibit", "Bewijsstuk")
        arguments = {"picture": picture, "letter": "A", "label": f"{exhibit} A", "case": case, "note": note}
        super().__init__("exhibit", None, arguments)

    @property
    def case(self) -> str | None:
        """The number of the case it's evidence in, as it's written ("Case No. 4417-23")."""
        case = self._arguments.get("case")
        return case if isinstance(case, str) else None

    def lettered(self, number: int, case: str | None = None) -> None:
        """Make it the talk's number-th exhibit (from 1: B for the second), of the case of that number, if one is
        given (the case of the talk's first exhibit: one case a talk)."""
        letter = exhibit_letter(number)
        self._arguments["letter"] = letter
        self._arguments["label"] = f"{self._exhibit} {letter}"
        if case:
            self._arguments["case"] = case


class PickOneSlide(DrawnSlide):
    """Two pictures side by side, without captions, under "Pick one:" (or a heading of its own), with the talk's word
    for "or" between them: the audience picks, and the presenter explains. Both are there from the start."""

    required_arguments = ("title", "picture_1", "picture_2")

    def __init__(
        self, title: str | None, picture_1: ImageData | None, picture_2: ImageData | None, either_or: str = "OR"
    ):
        arguments = {"picture_1": picture_1, "picture_2": picture_2, "title": title, "or": either_or}
        super().__init__("pick_one", None, arguments)


class EquationSlide(DrawnSlide):
    """A picture equation, as story cubes tell a story: a thing plus another thing equals a third, the punchline. Each
    thing is its picture, if it has one, or else its emoji (or a word or two), with a "+" and a "=" between them; the
    "=" and what the two make together appear on a click."""

    required_arguments = classic.EQUATION

    def __init__(
        self,
        title: str | None,
        term_1: str | None,
        term_2: str | None,
        result: str | None,
        pictures: Mapping[str, ImageData | None] | None = None,
    ):
        arguments: dict[str, Any] = {"title": title}
        for thing, text in zip(classic.EQUATION, (term_1, term_2, result), strict=True):
            picture = (pictures or {}).get(thing)
            arguments[thing] = None if picture is not None else text
            arguments[picture_role(thing)] = picture
        arguments.update({"plus": "+", "equals": "="})
        super().__init__("equation", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(("equals", "result", picture_role("result")))


class WhatDoYouSeeSlide(DrawnSlide):
    """What do you see?: a picture of a face in something that has none (pareidolia), under the question to the
    audience; without a picture, an inkblot, as a Rorschach test has it, which its layout draws. The presenter explains
    what everyone should see in it."""

    required_arguments = ("question",)

    def __init__(self, question: str | None, picture: ImageData | None = None):
        super().__init__("what_do_you_see", None, {"picture": picture, "question": question})


class BeforeAfterSlide(DrawnSlide):
    """Before and after: two pictures as a transformation, that have nothing to do with each other, each under its
    word ("Before", "After"), with an arrow between them, and a title, if it has one; the after appears on a click,
    and the presenter explains how the one became the other."""

    required_arguments = ("before", "before_picture", "after", "after_picture")

    def __init__(
        self,
        title: str | None,
        before: str | None,
        before_picture: ImageData | None,
        after: str | None,
        after_picture: ImageData | None,
    ):
        arguments = {
            "title": title,
            "before_picture": before_picture,
            "before": before,
            "after_picture": after_picture,
            "after": after,
        }
        super().__init__("before_after", None, arguments)

    def clicks(self) -> dict[str, int]:
        return self._one_by_one(("after", "after_picture"))


class MemeSlide(DrawnSlide):
    """A meme: a template's picture (one of Imgflip's, see talkgenerator.sources.memes), with its captions as texts on
    it, each in the box the template has for it (a box that repeats another's caption gets it too). Of two captions
    or more, each appears on a click of its own, in the template's order, the last one the punchline."""

    required_arguments = ("template", "text_1")

    def __init__(self, template: ImageData | None, *texts: str | None):
        # (in the template's order: a caption belongs to its box, even next to an empty one)
        captions = {f"text_{index}": texts[index - 1] if index <= len(texts) else None for index in range(1, 5)}
        super().__init__("meme", None, {"template": template, **captions})

    def clicks(self) -> dict[str, int]:
        clicks = self._one_by_one(*((f"text_{index}",) for index in range(1, 5)))
        return clicks if len(clicks) > 1 else {}
