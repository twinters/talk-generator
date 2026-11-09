"""Slide kinds: the shapes of slide a plan can ask for, what to write for each, and how each becomes a slide.

A kind names its text fields (with a description and a length limit, for the language model and the Skill) and its
image slots, and builds one of v4's Slide classes from them. A Recipe ties a kind to a slide generator of a
presentation schema: what its slots ask for (image slots, see talkgenerator.images.slots: which look, from which
sources), what this particular slide is about (its brief and hints), which fields and slots it leaves out, and which
texts come from classic sources instead (real quotes, for instance).

A diagram's kind can have pictures in some of its boxes now and then (a process's steps, a pyramid's levels, a
matrix's quadrants: `BoxPictures`): the talk's dice pick which, if any, when they pick the recipe's variant, and the
picture of a box is searched for (or generated) like a slide's other pictures, but a box goes without one when none
is found (docs/v5-plan.md, D64).
"""

from __future__ import annotations

import dataclasses
import functools
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.models.deck import VennDiagram
from talkgenerator.plan.languages import Language
from talkgenerator.slide import slides
from talkgenerator.sources import chart, diagram, memes
from talkgenerator.util import language_util, random_util

if TYPE_CHECKING:
    from talkgenerator.images.slots import ImageSlot


@dataclass(frozen=True)
class TextField:
    name: str
    description: str
    max_length: int = 80
    optional: bool = False  # may stay empty, and the slide then shows nothing there
    options: tuple[str, ...] = ()  # the words it can be, when it's a choice (such as how a trend line goes)


# Builds the slide from its texts (None where a field stays empty), its images (whatever the sources found), and the
# talk's language (for the words talkgenerator adds itself, such as a chart's Yes and No)
Builder = Callable[[Mapping[str, str | None], Mapping[str, Any], Language], slides.Slide]


@dataclass(frozen=True)
class Variant:
    """A way a recipe's slide can come out, which the talk's dice pick by weight: the text fields and image slots it
    does without (a slot left out isn't searched, and its builder gets None for it), a note for the language model
    (added to the slide's brief), what to write in some of its fields (hints, over the recipe's) and how long that may
    be (limits), what some of its slots search for, instead of the model's query (a meme's template), whether its
    slide may build on a real fact or a flavour text, as its kind's do (a dare on a dad joke: not a dare for the
    audience), and the fields whose things get an emoji in front, of a mood (where the model wrote none: see
    talkgenerator.sources.emoji)."""

    weight: float
    omit: frozenset[str] = frozenset()
    note: str = ""
    hints: Mapping[str, str] = field(default_factory=dict)
    limits: Mapping[str, int] = field(default_factory=dict)
    queries: Mapping[str, str] = field(default_factory=dict)
    facts: bool = True
    emoji: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BoxPictures:
    """Pictures in some of a diagram's boxes, now and then: a weird but related picture in a box, beside its text
    (docs/v5-plan.md, D64). The boxes are the text fields that can have one (a box's picture is its own image slot,
    "<box>_picture", which every recipe of the kind has: see box_picture_slot), each described for the language
    model; a slide has pictures that share of the time (odds: slides.PICTURE_ODDS, as classic diagrams have them),
    in one box or, at most, in so many."""

    boxes: Mapping[str, str]  # text field: what its box is, for the model ("the second step")
    odds: float = slides.PICTURE_ODDS
    most: int = 2
    aside: str = ""  # what else the model is told of a slide with pictures (a matrix's: where its dot goes)

    @staticmethod
    def slot(box: str) -> str:
        """The image slot of a box's picture (named as the slide's role for it: "step_2_picture")."""
        return slides.picture_role(box)

    def pick(self, rng: random_util.Rng) -> list[str]:
        """The boxes that get a picture, by the dice: none most of the time."""
        with random_util.use(rng):
            return slides.picked_boxes(list(self.boxes), self.most, self.odds)


@functools.cache
def box_picture_slot() -> ImageSlot:
    """What a diagram's box asks of its picture: a stock photo of something weird, or a generated picture in a talk
    that generates them (its stock photo stands in until it's in)."""
    from talkgenerator.images.slots import ImageSlot  # (here, as at the top for type checking: its sources are many)

    return ImageSlot("a weird but related picture in a diagram's box", aesthetic="weird-stock", generate=True)


@dataclass(frozen=True)
class Kind:
    name: str
    description: str
    texts: tuple[TextField, ...]
    images: tuple[str, ...]
    build: Builder
    # The ways its slides come out where a recipe of it has no variants of its own (a matrix with names in its
    # quadrants, with dots instead, or bare), and the pictures some of its boxes can have
    variants: tuple[Variant, ...] = ()
    pictures: BoxPictures | None = None


# A v4 content generator: a presentation context (with the "seed" to search for) in, an image (or None) out
ContentSource = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True, eq=False)
class Recipe:
    kind: str
    # One per image slot of the kind, in order: what the slot asks for (an ImageSlot), or a v4 content generator
    images: tuple[ImageSlot | ContentSource, ...] = ()
    brief: str = ""  # what this slide is, for the language model
    hints: Mapping[str, str] = field(default_factory=dict)  # per text field: what to write here, instead of the kind's
    # Text fields and image slots that this slide does without, and "<slot>_query" image queries it doesn't need
    # (that slot is searched for with the slide's concept)
    omit: frozenset[str] = frozenset()
    texts_from: Mapping[str, ContentSource] = field(default_factory=dict)  # texts found by classic sources instead
    variants: tuple[Variant, ...] = ()  # ways a slide can come out, such as a chart with or without labels
    # Per text field: how long it may be on this slide, when that's less than its kind's length (a meme's small box)
    limits: Mapping[str, int] = field(default_factory=dict)
    # Per image slot: what it searches for, instead of a query the model writes (a meme's template, the dice's pick)
    queries: Mapping[str, str] = field(default_factory=dict)
    # The boxes of a diagram that have a picture on this slide (see BoxPictures): none, but where the dice put some
    pictures: tuple[str, ...] = ()
    # Whether its slide may build on a real fact or a flavour text, as its kind's do (see talkgenerator.facts.use_of)
    facts: bool = True
    # Per text field: the mood of the emoji its things get in front, where the model wrote none (a tier list's tiers)
    emoji: Mapping[str, str] = field(default_factory=dict)

    def text_field(self, text: TextField) -> TextField:
        """A text field of the kind as this slide has it: as long as its limit here allows."""
        limit = self.limits.get(text.name)
        return dataclasses.replace(text, max_length=limit) if limit and limit < text.max_length else text

    def written_fields(self) -> list[TextField]:
        """The text fields the language model writes for this slide."""
        return [
            self.text_field(text)
            for text in KINDS[self.kind].texts
            if text.name not in self.omit and text.name not in self.texts_from
        ]

    def image_queries(self) -> list[str]:
        """The image slots the language model writes a search query for."""
        return [
            slot
            for slot in [*KINDS[self.kind].images, *self.optional_slots()]
            if f"{slot}_query" not in self.omit and slot not in self.omit and slot not in self.queries
        ]

    def slots(self) -> list[tuple[str, ImageSlot | ContentSource]]:
        """The image slots this slide has, by name, with what they ask for (not the ones it leaves out): the kind's,
        then the pictures of its boxes that it has."""
        own = [
            (name, source)
            for name, source in zip(KINDS[self.kind].images, self.images, strict=True)
            if name not in self.omit
        ]
        return own + [(slot, box_picture_slot()) for slot in self.optional_slots() if slot not in self.omit]

    def optional_slots(self) -> list[str]:
        """The image slots that may stay empty when nothing is found for them: the pictures of its boxes."""
        return [BoxPictures.slot(box) for box in self.pictures]

    def varied(self, rng: random_util.Rng, avoid: frozenset[str] = frozenset()) -> Recipe:
        """The recipe as one of its variants, picked by weight with the random stream (itself, without variants; its
        kind's, if it has none of its own): not one whose queries are in avoid, while there are others (a meme's
        template that the talk has already). And, for a diagram whose kind has pictures in its boxes, the boxes that
        get one, from a stream of their own (none, most of the time)."""
        kind = KINDS[self.kind]
        variants = self.variants or kind.variants
        varied = self
        if variants:
            fresh = [variant for variant in variants if not set(variant.queries.values()) & avoid] or variants
            with random_util.use(rng):
                variant = random_util.weighted_random([(variant.weight, variant) for variant in fresh])
            if variant is not None:
                brief = (self.brief or kind.description).rstrip(".")
                varied = dataclasses.replace(
                    self,
                    omit=self.omit | variant.omit,
                    brief=f"{brief}, {variant.note}" if variant.note else brief,
                    hints={**self.hints, **variant.hints},
                    limits={**self.limits, **variant.limits},
                    queries={**self.queries, **variant.queries},
                    facts=self.facts and variant.facts,
                    emoji={**self.emoji, **variant.emoji},
                    variants=(),
                )
        if kind.pictures is None:
            return varied
        boxes = [box for box in kind.pictures.pick(rng.child("pictures")) if box not in varied.omit]
        if not boxes:
            return varied
        brief = (varied.brief or kind.description).rstrip(".")
        which = " and ".join(kind.pictures.boxes[box] for box in boxes)
        note = (
            f"with a weird but related picture in the box of {which}: the {'queries' if len(boxes) > 1 else 'query'}"
            f" for {'them' if len(boxes) > 1 else 'it'}, something odd that the box's words make one think of"
            + (f"; {kind.pictures.aside}" if kind.pictures.aside else "")
        )
        return dataclasses.replace(varied, brief=f"{brief}, {note}", pictures=tuple(boxes), variants=())


def _title(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.TitleSlide(texts["title"] or "", texts.get("subtitle"))


def _image(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.ImageSlide(texts.get("title"), images.get("image"))


def _full_image(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FullImageSlide(texts.get("title"), images.get("image"))


def _statement(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.LarqeQuoteSlide(None, texts.get("text") or "", images.get("background"))


def _two_columns(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.TwoColumnImageSlide(
        texts.get("title"), texts.get("caption_1"), images.get("image_1"), texts.get("caption_2"), images.get("image_2")
    )


def _three_columns(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.ThreeColumnImageSlide(
        texts.get("title"),
        texts.get("caption_1"),
        images.get("image_1"),
        texts.get("caption_2"),
        images.get("image_2"),
        texts.get("caption_3"),
        images.get("image_3"),
    )


def _history_quote(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # A made-up historical figure (never a real person) and their quote, where v4 put a real quote next to a made-up name
    return slides.TwoColumnImageSlide(
        texts.get("title"), texts.get("name"), images.get("portrait"), None, texts.get("quote")
    )


def _chart_yes_no(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    data = ChartData()
    data.categories = [language.yes, language.no, texts["funny_answer"] or ""]
    data.add_series("", chart.normalise_data(chart.create_equal_data_with_outlier_end(3, 0.2, 1, 2.5, 1, 20)))
    chart_type, style = random_util.choice((chart.PIE, chart.PROCENT_HISTOGRAM, chart.DOUGHNUT))
    return slides.ChartSlide(texts["question"], chart_type, data, style)


def _chart_categories(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    categories = [part.strip() for part in (texts["categories"] or "").split("|") if part.strip()][:5]
    if len(categories) < 2:
        raise ValueError("a pie chart needs two answers or more")
    data = ChartData()
    data.categories = categories
    data.add_series("", chart.normalise_data([random_util.uniform(1, 10) ** 2 for _ in categories]))
    chart_type, style = random_util.choice((chart.PIE, chart.DOUGHNUT))
    return slides.ChartSlide(texts["question"], chart_type, data, style)


def _chart_trend(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # The first line goes the way the plan says (or a random way), and a second line, if any, another way
    shape, values = chart.trend_values(texts.get("shape"))
    lines = [(texts.get("line") or "", values)]
    second = texts.get("second_line")
    if second:
        lines.append((second, chart.trend_values(texts.get("second_shape"), avoid=shape)[1]))
    event = texts.get("event")
    return slides.ChartSlide(
        texts["title"],
        XL_CHART_TYPE.LINE,
        chart.trend_chart_data(lines),
        x_title=texts.get("x_axis"),
        y_title=texts.get("y_axis"),
        reveal="series" if second else "all",
        point_labels=((0, chart.trend_turn(shape), event),) if event else (),
        # (a weird picture of the moment by its point, now and then, on a click: see BoxPictures)
        point_picture=images.get(BoxPictures.slot("event")) if event else None,
    )


def _chart_bars(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (Bars that are only numbers are scores a model put between the names: "Druids | 6 | Priests | 4")
    parts = [part.strip() for part in (texts["bars"] or "").split("|")]
    bars = [part for part in parts if part and not _NUMBER.fullmatch(part)][:6]
    if len(bars) < 3:
        raise ValueError("a ranking needs three bars or more")
    return slides.ChartSlide(
        texts["title"], XL_CHART_TYPE.BAR_CLUSTERED, chart.ranking_chart_data(bars), y_title=texts.get("value_axis")
    )


def _chart_correlation(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # Made-up data under the plan's claim: a cloud in the shape the plan says (or a random one), now and then with a
    # line fitted through it; or two or three named clouds, each in its colour; and maybe an outlier
    clusters = [texts.get(f"cluster_{index}") or "" for index in range(1, chart.MOST_CLUSTERS + 1)]
    data, trendlines, labels = chart.correlation_data(texts.get("shape"), clusters, texts.get("outlier"))
    return slides.ChartSlide(
        texts["title"],
        XL_CHART_TYPE.XY_SCATTER,
        data,
        chart.create_set_scatter_properties("", ""),
        x_title=texts.get("x_axis"),
        y_title=texts.get("y_axis"),
        point_labels=labels,
        trendlines=trendlines,
    )


def _box_pictures(images: Mapping[str, Any]) -> dict[str, Any]:
    """The pictures the slide's boxes got (see BoxPictures), by the box: the role of its text."""
    suffix = BoxPictures.slot("")
    return {
        slot[: -len(suffix)]: image for slot, image in images.items() if slot.endswith(suffix) and image is not None
    }


def _venn(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    circles = tuple(text for text in (texts["circle_1"], texts["circle_2"], texts.get("circle_3")) if text)
    return slides.DiagramSlide(
        texts["title"],
        VennDiagram(circles=circles, overlap=texts["overlap"] or "", reveal="punchline"),
        pictures=_box_pictures(images),
    )


def _matrix(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # The dot goes in the quadrant the plan says (or a random one), the other things where they belong; the quadrants
    # have labels, or none (in a matrix of dots, or a bare one), and some may have a picture
    labels = [texts.get(corner) or "" for corner in MATRIX_CORNERS]
    things = [
        (thing, quadrant)
        for corner, quadrant in zip(MATRIX_CORNERS, diagram.QUADRANTS, strict=True)
        for thing in slides.listed_items(texts.get(f"{corner}_things"), diagram.DOTS_IN_A_QUADRANT)
    ]
    matrix = diagram.matrix(
        texts["x_left"] or "",
        texts["x_right"] or "",
        texts["y_bottom"] or "",
        texts["y_top"] or "",
        labels,
        texts["dot"] or "",
        texts.get("dot_quadrant"),
        things,
    )
    return slides.DiagramSlide(
        texts["title"], matrix, pictures=diagram.pictured_quadrants(matrix, _box_pictures(images))
    )


def _big_number(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.BigNumberSlide(texts.get("title"), texts["number"], texts["label"], texts.get("source"))


def _kpi(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    figures = [texts.get(f"{part}_{index}") for index in range(1, 5) for part in ("number", "label")]
    return slides.KpiSlide(texts["title"], *figures)


def _quiz(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (without a letter of their own in front: some models write "A) Yes", and the slide adds the letters)
    options = [_LETTERED.sub("", texts.get(f"option_{letter.lower()}") or "") or None for letter in slides.LETTERS]
    answer = texts["answer"] or ""
    if answer not in slides.LETTERS or not options[slides.LETTERS.index(answer)]:
        raise ValueError(f"the quiz's answer, {answer!r}, isn't one of its options")
    explanation = texts.get("explanation")
    if explanation:  # (a free model marked one option and explained why another was right: the explanation wins)
        named = language_util.named_options(explanation, options, language.stopwords)
        if len(named) == 1 and named[0] != slides.LETTERS.index(answer):
            answer = slides.LETTERS[named[0]]
    first, second, third, fourth = options
    return slides.QuizSlide(texts["question"], first, second, third, fourth, answer, explanation)


def _social_post(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    likes = round(10 ** random_util.uniform(1.5, 6.3))  # (from a few dozen to a few million)
    shares = round(likes * random_util.uniform(0.02, 0.4))
    return slides.SocialPostSlide(
        texts.get("title"),
        texts["author"],
        texts["handle"],
        texts["text"],
        images.get("photo"),
        likes,
        shares,
        language,
    )


def _news_headline(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.NewsHeadlineSlide(
        texts["outlet"], texts["headline"], texts.get("subheadline"), images.get("photo"), language
    )


def _agenda(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    items = [_shortened(part.strip(), AGENDA_ITEM) for part in (texts["items"] or "").split("|") if part.strip()]
    if len(items) < 3:
        raise ValueError("an agenda needs three items or more")
    return slides.AgendaSlide(texts["title"], *items[:5])


def _section(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.SectionSlide(texts["title"], texts.get("subtitle"))


def _questions(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (a callback's picture is an earlier slide's, which the deck gives it: see talkgenerator.slide.slide_deck)
    callback = texts.get("callback")
    return slides.QuestionsSlide(
        texts["title"],
        texts.get("subtitle"),
        images.get("photo"),
        callback=callback,
        pick=random_util.random() if callback is not None else 0.0,
    )


def _numbered(texts: Mapping[str, str | None], prefix: str, most: int) -> list[str | None]:
    return [texts.get(f"{prefix}_{index}") for index in range(1, most + 1)]


def _timeline(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    moments = [texts.get(f"{part}_{index}") for index in range(1, 6) for part in ("date", "event")]
    return slides.TimelineSlide(texts["title"], *moments)


def _pyramid(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.PyramidSlide(texts["title"], *_numbered(texts, "level", 4), pictures=_box_pictures(images))


def _funnel(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FunnelSlide(texts["title"], *_numbered(texts, "stage", 5), pictures=_box_pictures(images))


def _cycle(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.CycleSlide(texts["title"], *_numbered(texts, "step", 5), pictures=_box_pictures(images))


def _org_chart(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.OrgChartSlide(texts["title"], texts["boss"], *_numbered(texts, "report", 4))


def _iceberg(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    hidden = _numbered(texts, "hidden", 3)
    return slides.IcebergSlide(texts["title"], texts["tip"], *hidden, pictures=_box_pictures(images))


def _process(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.ProcessSlide(texts["title"], *_numbered(texts, "step", 5), pictures=_box_pictures(images))


def _references(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (a picture of one of the works, a book's cover or a paper's figure, as its recipe searches for it)
    works = [_shortened(part.strip(), AGENDA_ITEM) for part in (texts["items"] or "").split("|") if part.strip()]
    if len(works) < 3:
        raise ValueError("references need three works or more")
    return slides.ReferencesSlide(
        texts.get("title"), *works[: slides.REFERENCES], figure=images.get("figure"), caption=texts.get("caption")
    )


def _meme(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    picture = images.get("template")
    if picture is None:
        raise ValueError("the meme has no template")
    captions = [texts.get(f"text_{index}") for index in range(1, memes.MOST_CAPTIONS + 1)]
    template = memes.of_picture(picture.get_image_url(), picture.get_source_url())
    if template is None:  # (a picture whose boxes talkgenerator doesn't know: captioned at its top and its bottom)
        shown = [caption for caption in captions if caption][:2]
        if not shown:
            raise ValueError("the meme has no captions")
        return slides.MemeSlide(picture, *shown)
    return slides.MemeSlide(picture, *template.texts(captions))


def _fun_fact(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (its heading is talkgenerator's, in the talk's language: "Did you know?" or "Fun fact")
    kicker = random_util.choice(language.fun_facts)
    return slides.FunFactSlide(kicker, texts["fact"], texts.get("source"), images.get("photo"))


def _plain_letters(text: str) -> str:
    """The text's letters, without their accents ("Élan": "Elan"), in capitals."""
    return "".join(
        character for character in unicodedata.normalize("NFKD", text) if character.isascii() and character.isalpha()
    ).upper()


def _acronym(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (without a letter of their own in front: some models write "S - Synergy", and the slide adds the letters)
    words = [_SPELLED.sub("", word or "").strip() for word in _numbered(texts, "word", slides.ACRONYM_LETTERS)]
    written = [word for word in words if word]
    if len(written) < 3:
        raise ValueError("an acronym needs three words or more")
    initials = "".join(_plain_letters(word)[:1] for word in written)
    title = texts["title"]
    if title and _plain_letters(texts.get("acronym") or "") not in ("", initials):
        title = _respelled(title, texts.get("acronym") or "", initials)
    if title and not _spelled_in(title, initials):  # (a title that names another acronym: "PRISM" over P, A, P)
        title = _ACRONYM_LIKE.sub(lambda match: _respelled(match.group(0), match.group(0), initials), title, count=1)
    return slides.AcronymSlide(title, *written)


# A word in capitals, or letters with dots between them, as a title names an acronym ("SPARK", "S.P.A.R.K.")
_ACRONYM_LIKE: Final = re.compile(r"\b(?:[A-Z]\.){2,}[A-Z]?\.?(?![A-Za-z])|\b[A-Z]{3,}\b")


def _spelled_in(title: str, initials: str) -> bool:
    """Whether the title names the acronym of these initials, dotted or not."""
    return bool(re.search(r"\b" + r"[.\s]?".join(map(re.escape, initials)) + r"\.?(?![A-Za-z])", title, re.IGNORECASE))


def _respelled(title: str, acronym: str, initials: str) -> str:
    """The title with the acronym it names spelled as its words' initials, where a model's acronym isn't (its
    "PIRATES" over the words "Public Invoicing, Reimbursement...", or an eight-letter one over six words): the letters
    on the slide are the words', so the title says them too, with dots between them where the title has them
    ("S.P.A.R.K."). A title that doesn't name the acronym, dotted or not, stays as it is."""
    letters = _plain_letters(acronym)
    if not letters:
        return title
    # (its letters, each maybe followed by a dot or a space, as a word of its own)
    pattern = re.compile(r"\b" + r"[.\s]?".join(map(re.escape, letters)) + r"\.?(?![A-Za-z])", re.IGNORECASE)

    def respell(match: re.Match[str]) -> str:
        return "".join(f"{letter}." for letter in initials) if "." in match.group(0) else initials

    return pattern.sub(respell, title, count=1)


def _dare(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # (its heading is talkgenerator's: "Challenge" over a dare for the presenter, "Audience participation" over one
    # for everyone; a variant leaves one of the two out)
    dare, everyone = texts.get("dare"), texts.get("audience")
    if not dare and not everyone:
        raise ValueError("the dare has no task, for the presenter or for the audience")
    return slides.DareSlide(language.dare, dare) if dare else slides.DareSlide(language.audience, everyone)


def _flowchart(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FlowchartSlide(
        texts.get("title"),
        texts["question"],
        texts["yes_step"],
        texts["no_step"],
        texts["end"],
        yes=language.yes,
        no=language.no,
        pictures=_box_pictures(images),
    )


def _tier_list(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    tiers = [texts.get(f"{tier.lower()}_tier") for tier in slides.TIERS]
    if not slides.tier_items(tiers[0]) or not slides.tier_items(tiers[1]):
        raise ValueError("a tier list needs things in its S and A tiers")
    return slides.TierListSlide(texts["title"], *tiers)


def _wall_of_text(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    points = slides.listed_items(texts["points"], slides.WALL_POINTS)
    if len(points) < slides.WALL_FEWEST:
        raise ValueError(f"a wall of text needs {slides.WALL_FEWEST} points or more")
    highlight = slides.listed_items(texts["highlight"], 1)  # (without a bullet the model put in front)
    return slides.WallOfTextSlide(texts["title"], highlight[0] if highlight else None, language.continued, *points)


def _alignment_chart(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    cells = [texts.get(alignment) for alignment in slides.ALIGNMENTS]
    return slides.AlignmentChartSlide(texts.get("title"), language.lawful_to_chaotic, language.good_to_evil, *cells)


def _red_flags(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.RedFlagsSlide(texts["title"], *_numbered(texts, "flag", slides.RED_FLAGS))


def _reviews(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    written = [
        part
        for index in range(1, slides.REVIEWS + 1)
        for part in (texts.get(f"stars_{index}"), texts.get(f"review_{index}"), texts.get(f"reviewer_{index}"))
    ]
    return slides.ReviewsSlide(texts.get("title"), *written)


def _error_message(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    buttons = [_button(button) for button in slides.listed_items(texts["buttons"], slides.ERROR_BUTTONS)]
    if len(buttons) < 2:
        raise ValueError("an error message needs two buttons or more")
    return slides.ErrorMessageSlide(texts.get("title"), texts["message"], texts.get("code"), *buttons)


def _button(text: str) -> str:
    """A dialog's button as long as one may be: cut between words, without a little word left hanging at its end
    ("Become the", of "Become the plant")."""
    cut = _shortened(text, ERROR_BUTTON)
    if cut == text:
        return text
    words = cut.split()
    while len(words) > 1 and words[-1].lower() in _HANGING:
        words.pop()
    return " ".join(words)


# Little words a cut text shouldn't end on
_HANGING: Final = frozenset("a an the of to and or with for in on at by my your our their its from as".split())


def _shortened(text: str, length: int) -> str:
    """The text, cut between words to at most this many characters (or within its first word, if that's longer)."""
    if len(text) <= length:
        return text
    cut = text[: length + 1].rsplit(" ", 1)[0].rstrip(",;:-–— ")
    return cut if 0 < len(cut) <= length else text[:length]


def _quadrant(corner: str, ends: str) -> TextField:
    # (at most 30 letters, for a format's names such as a made-up citation, "Kowalski and Kowalski (2019)")
    return TextField(
        corner.replace(" ", "_"), f"a short name for the {corner} quadrant, a word or two: what is {ends}", 30, True
    )


def _things(corner: str, ends: str) -> TextField:
    return TextField(
        f"{corner.replace(' ', '_')}_things",
        f"one or two familiar things that belong in the {corner} quadrant ({ends}), separated by |",
        50,
        optional=True,
    )


# The first three steps of a process or a cycle, which every one of them has: the boxes that can have a picture
_STEPS: Final = {"step_1": "the first step", "step_2": "the second step", "step_3": "the third step"}


def matrix_landscape(thing: str, things: str) -> tuple[Variant, Variant]:
    """The ways a format's matrix of things in three of its quadrants (a pitch's competitors, a review's
    initiatives, a paper's earlier work) and the dot alone in the best one (top right) comes out: with the things as
    the three quadrants' names, as it was; or as dots where they belong, one in each of those quadrants, and a name
    only in the best one (docs/v5-plan.md, D64). thing says what to write for one of them, things what they are."""
    others = ("top_left", "bottom_left", "bottom_right")
    return (
        Variant(1, _MATRIX_THINGS),
        Variant(
            1,
            frozenset(others) | {"top_right_things"},
            f"with {things} as dots where they belong, one in each of the three other quadrants (their fields of "
            "things), and a name only in the best quadrant, where the dot is",
            hints={f"{corner}_things": f"{thing}: one" for corner in others},
        ),
    )


# How a correlation comes out, where its recipe has no variants of its own (docs/v5-plan.md, D64): one cloud of points,
# or two or three named groups of them (clusters)
_CLUSTERS: Final = frozenset(f"cluster_{index}" for index in range(1, chart.MOST_CLUSTERS + 1))
CLUSTERED: Final = Variant(
    1,
    frozenset({"shape"}),
    "with two or three groups of points, each in its own colour and named in the legend (the clusters' fields): "
    "things of a kind that the claim compares",
)
CORRELATION_VARIANTS: Final = (Variant(2.3, _CLUSTERS), CLUSTERED)
# How often a trend whose moment is marked has a picture of the moment by its point
TREND_PICTURE_ODDS: Final = 0.5
# A matrix's quadrants, as its fields name them (in diagram.QUADRANTS' order), and what is in each
MATRIX_CORNERS: Final = ("top_left", "top_right", "bottom_left", "bottom_right")
_QUADRANT_ENDS: Final = (
    "both like the top end and like the left end",
    "both like the top end and like the right end",
    "both like the bottom end and like the left end",
    "both like the bottom end and like the right end",
)
_MATRIX_THINGS: Final = frozenset(f"{corner}_things" for corner in MATRIX_CORNERS)
_MATRIX_LABELS: Final = frozenset(MATRIX_CORNERS)
# The ways a matrix comes out, where its recipe has none of its own (docs/v5-plan.md, D64): a name in every quadrant;
# no names, but familiar things as dots where they belong, around the punchline's; or bare, with only the axes and
# the punchline's dot
MATRIX_VARIANTS: Final = (
    Variant(2, _MATRIX_THINGS, "with a short name in every quadrant"),
    Variant(
        2,
        _MATRIX_LABELS,
        "without names in its quadrants: instead, two to four familiar things as dots where they belong (in the "
        "quadrants' fields of things: one or two in a quadrant, some quadrants may have none), around the "
        "punchline's dot",
    ),
    Variant(1, _MATRIX_LABELS | _MATRIX_THINGS, "bare: no names in its quadrants, only the axes and the dot"),
)


_NUMBER: Final = re.compile(r"[-+]?\d+(?:[.,]\d+)?\s*%?")
_LETTERED: Final = re.compile(r"^\(?[A-Da-d]\s*[).:]\s*")  # a quiz option's own letter, as in "A) Yes"
_SPELLED: Final = re.compile(r"^[A-Za-z]\s*[-–—:.)=]\s+")  # an acronym's word's own letter, as in "S - Synergy"
_OPTIONAL_TITLE = TextField("title", "the slide's title", 60, optional=True)

# The talk's own texts, on its title slide: "By <presenter>, <job>" under the title. The name is a made-up one, when
# nobody gives theirs (see talkgenerator.names), and it isn't cut when it's too long: half a name is no name
TALK_TITLE: Final = TextField("title", "the talk's title", 80)
PRESENTER_JOB: Final = TextField(
    "presenter_job", "the presenter's grand, made-up job, such as 'Professor of Applied Sock Theory'", 50
)
PRESENTER_NAME: Final = TextField("presenter_name", "a made-up name for the presenter", 40)
AGENDA_ITEM: Final = 45  # how long an item of an agenda may be (they're written as one text)


def _figure(index: int, which: str, optional: bool = False) -> tuple[TextField, TextField]:
    return (
        TextField(f"number_{index}", f"the {which} figure's number, with its unit if it has one", 10, optional),
        TextField(f"label_{index}", f"what the {which} figure measures", 40, optional),
    )


def _moment(index: int, which: str, optional: bool = False) -> tuple[TextField, TextField]:
    return (
        TextField(f"date_{index}", f"the {which} moment's date (a year, say, or a day)", 12, optional),
        TextField(f"event_{index}", f"what happened at the {which} moment", 40, optional),
    )


WALL_TEXT: Final = 2600  # how long a wall of text's points may be, together (they're written as one text)
DARE: Final = 130  # how long a dare may be, for the presenter or for the audience
CALLBACK: Final = 60  # how long the closing slide's note of which earlier picture it calls back to may be
ERROR_BUTTON: Final = 20  # how long a fake error message's button may be (they're written as one text)
# What an alignment chart's description of its cells says of the punchline's
_PUNCHLINE: Final = {"chaotic_evil": ": the punchline"}


def _review(index: int, which: str, optional: bool = False) -> tuple[TextField, TextField, TextField]:
    return (
        TextField(f"stars_{index}", f"how many stars the {which} reviewer gives, from 1 to 5", 1, optional, STARS),
        TextField(f"review_{index}", f"what the {which} reviewer wrote", 110, optional),
        TextField(f"reviewer_{index}", f"who the {which} reviewer is: a made-up first name, and a detail", 30, True),
    )


STARS: Final = ("1", "2", "3", "4", "5")


def _items(prefix: str, length: int, *descriptions: str, required: int = 3) -> tuple[TextField, ...]:
    """Numbered text fields (prefix_1, prefix_2...), the ones after the required ones optional."""
    return tuple(
        TextField(f"{prefix}_{index}", description, length, optional=index > required)
        for index, description in enumerate(descriptions, 1)
    )


KINDS: Final[dict[str, Kind]] = {
    kind.name: kind
    for kind in (
        Kind(
            "title",
            "The title slide: the talk's title, and the presenter (their name is added by talkgenerator).",
            (TextField("title", "the talk's title", 80), TextField("subtitle", "who presents it", 120, optional=True)),
            (),
            _title,
        ),
        Kind("image", "An image with a title.", (TextField("title", "the slide's title", 60),), ("image",), _image),
        Kind(
            "full_image",
            "An image filling the slide, with an optional title.",
            (_OPTIONAL_TITLE,),
            ("image",),
            _full_image,
        ),
        Kind(
            "statement",
            "A big text over a photo.",
            (TextField("text", "the big text over the photo", 140),),
            ("background",),
            _statement,
        ),
        Kind(
            "two_columns",
            "Two captioned images side by side.",
            (
                _OPTIONAL_TITLE,
                TextField("caption_1", "the left caption", 40),
                TextField("caption_2", "the right caption", 40),
            ),
            ("image_1", "image_2"),
            _two_columns,
        ),
        Kind(
            "three_columns",
            "Three captioned images side by side.",
            (
                _OPTIONAL_TITLE,
                TextField("caption_1", "the left caption", 40),
                TextField("caption_2", "the middle caption", 40),
                TextField("caption_3", "the right caption", 40),
            ),
            ("image_1", "image_2", "image_3"),
            _three_columns,
        ),
        Kind(
            "history_quote",
            "A made-up historical figure's portrait, next to their quote.",
            (
                TextField("title", "a title about history", 60),
                TextField("name", "a made-up historical figure (never a real person): name and title", 60),
                TextField("quote", "what this made-up figure once said", 160),
            ),
            ("portrait",),
            _history_quote,
        ),
        Kind(
            "chart_yes_no",
            "A chart of answers to a yes-or-no question: yes, no, and a funny third answer.",
            (
                TextField("question", "a yes-or-no question, as the chart's title", 90),
                # (Examples here get copied: with "such as 'Only on Tuesdays'", half the charts said that)
                TextField(
                    "funny_answer", "a third answer, besides yes and no: an odd one of your own for this question", 30
                ),
            ),
            (),
            _chart_yes_no,
        ),
        Kind(
            "chart_categories",
            "A pie chart of made-up shares.",
            (
                TextField("question", "the question the pie chart answers, as its title", 90),
                TextField("categories", "two to five answers, separated by |", 120),
            ),
            (),
            _chart_categories,
        ),
        Kind(
            "chart_correlation",
            "A scatter plot of made-up data, under a claim of a correlation: one cloud of points in a shape (now and "
            "then with a line fitted through it), or two or three named groups of points, each in its own colour.",
            (
                TextField("title", "a made-up correlation between two things, as a claim", 90),
                TextField("x_axis", "the axis along the bottom: the first of the two things", 40, optional=True),
                TextField("y_axis", "the axis going up: the second thing", 40, optional=True),
                TextField(
                    "shape",
                    "the shape of the cloud of points, the funniest one for the claim",
                    12,
                    optional=True,
                    options=tuple(chart.CORRELATION_SHAPES),
                ),
                *(
                    TextField(f"cluster_{index}", f"the name of the {which} group of points, in the legend", 24, True)
                    for index, which in enumerate(("first", "second", "third"), 1)
                ),
                TextField(
                    "outlier",
                    "one point far above the others, named after someone or something that doesn't belong there",
                    30,
                    optional=True,
                ),
            ),
            (),
            _chart_correlation,
            CORRELATION_VARIANTS,
        ),
        Kind(
            "chart_trend",
            "A line chart of a made-up trend along two odd axes; a second line, if any, draws itself across it on a "
            "click, as the punchline.",
            (
                TextField("title", "the chart's claim, as its title", 90),
                TextField(
                    "x_axis", "what the chart goes along, such as 'Hours since the meeting started'", 40, optional=True
                ),
                TextField("y_axis", "what the line measures, such as 'Times someone said synergy'", 40, optional=True),
                TextField("shape", "how the line goes", 20, optional=True, options=tuple(chart.TREND_SHAPES)),
                TextField("line", "the line's name in the legend, such as 'Me'", 30, optional=True),
                TextField(
                    "second_line",
                    "a second line's name in the legend, such as 'My cat'; it appears on a click, as the punchline",
                    30,
                    optional=True,
                ),
                TextField(
                    "second_shape", "how the second line goes", 20, optional=True, options=tuple(chart.TREND_SHAPES)
                ),
                TextField(
                    "event",
                    "a moment on the first line, marked where it takes off, turns or drops, such as 'I got a cat'",
                    40,
                    optional=True,
                ),
            ),
            (),
            _chart_trend,
            pictures=BoxPictures(
                {"event": "the moment marked on the line"},
                odds=TREND_PICTURE_ODDS,
                most=1,
                aside="it appears on a click, by the moment's point, so the moment has to be there",
            ),
        ),
        Kind(
            "chart_bars",
            "A ranking in bars, whose last bar, the punchline, wins by far.",
            (
                TextField("title", "the question the ranking answers, as its title", 90),
                TextField(
                    "bars", "three to six things (only their names), separated by |, the last one the punchline", 160
                ),
                TextField("value_axis", "what the bars measure, such as 'Danger level'", 40, optional=True),
            ),
            (),
            _chart_bars,
        ),
        # (No examples in these descriptions either: the free models copy them)
        Kind(
            "venn",
            "A Venn diagram: two or three circles of things, each with a label, and what's in all of them at once, "
            "the punchline, which appears on a click.",
            (
                TextField("title", "the diagram's title", 60),
                TextField("circle_1", "the first circle's label: a group of things", 30),
                TextField(
                    "circle_2",
                    "the second circle's label: a group of things that seems to have nothing to do with the first",
                    30,
                ),
                TextField("circle_3", "a third circle's label: another such group", 30, optional=True),
                TextField("overlap", "the one thing that is in all the circles at once: the punchline", 30),
            ),
            (),
            _venn,
            pictures=BoxPictures({"circle_1": "the first circle", "circle_2": "the second circle"}),
        ),
        Kind(
            "matrix",
            "A 2×2 matrix: two axes of everyday opposites that cross in the middle, with a word or two at each end, "
            "a short name in each quadrant (or familiar things as dots where they belong, or neither), and one dot "
            "with a name, the punchline, which appears on a click.",
            (
                TextField("title", "the matrix's title", 60),
                TextField("x_left", "the left end of the axis along the bottom: a word or two", 24),
                TextField("x_right", "the right end of that axis, a word or two: the opposite of the left end", 24),
                TextField("y_bottom", "the bottom end of the axis going up: a word or two", 24),
                TextField("y_top", "the top end of that axis, a word or two: the opposite of the bottom end", 24),
                *(_quadrant(corner, ends) for corner, ends in zip(diagram.QUADRANTS, _QUADRANT_ENDS, strict=True)),
                *(_things(corner, ends) for corner, ends in zip(diagram.QUADRANTS, _QUADRANT_ENDS, strict=True)),
                TextField(
                    "dot",
                    "the name of a dot in one of the quadrants: someone or something surprising there, the punchline",
                    30,
                ),
                TextField(
                    "dot_quadrant",
                    "the quadrant the dot is in, the most surprising one for it",
                    12,
                    optional=True,
                    options=diagram.QUADRANTS,
                ),
            ),
            (),
            _matrix,
            MATRIX_VARIANTS,
            BoxPictures(
                {
                    corner: f"the {quadrant} quadrant"
                    for corner, quadrant in zip(MATRIX_CORNERS, diagram.QUADRANTS, strict=True)
                },
                aside="the dot goes in another quadrant",
            ),
        ),
        # Milestone 6's slide types (docs/v5-plan.md, section 8), drawn as texts on shapes
        Kind(
            "big_number",
            "A big, made-up number, with what it counts under it: a figure the presenter has to explain.",
            (
                _OPTIONAL_TITLE,
                TextField(
                    "number", "the big number, with its unit if it has one: a percentage, an amount or a count", 12
                ),
                TextField("label", "what the number counts or measures, in a few words", 90),
                TextField("source", "a made-up, unreliable source for the number", 60, optional=True),
            ),
            (),
            _big_number,
        ),
        Kind(
            "kpi",
            "Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; they "
            "appear one by one, a click each, the last one the punchline.",
            (
                TextField("title", "the dashboard's title", 60),
                *_figure(1, "first"),
                *_figure(2, "second"),
                *_figure(3, "third"),
                *_figure(4, "fourth", optional=True),
            ),
            (),
            _kpi,
        ),
        Kind(
            "quiz",
            "A quiz question for the audience, with three or four options (A to D), which appear one by one, a click "
            "each; the answer, and why, appear on the click after them.",
            (
                TextField("question", "the quiz question", 90),
                TextField("option_a", "option A (without its letter)", 50),
                TextField("option_b", "option B", 50),
                TextField("option_c", "option C", 50),
                TextField("option_d", "option D", 50, optional=True),
                TextField("answer", "the letter of the right option", 1, options=tuple(slides.LETTERS)),
                TextField("explanation", "why that's the answer, shown with it", 90, optional=True),
            ),
            (),
            _quiz,
        ),
        Kind(
            "social_post",
            "A made-up social media post with a photo: who posted it, and what they wrote (talkgenerator adds its "
            "likes and shares).",
            (
                _OPTIONAL_TITLE,
                TextField("author", "the made-up name of who posted it (never a real person)", 30),
                TextField("handle", "their made-up username, without the @", 24),
                TextField("text", "the post: what they wrote, without hashtags or emoji", 160),
            ),
            ("photo",),
            _social_post,
        ),
        Kind(
            "news_headline",
            "A made-up news story with a photo, as breaking news on television or on a newspaper's front page.",
            (
                TextField("outlet", "the made-up name of the newspaper or the channel", 30),
                TextField("headline", "the headline", 90),
                TextField("subheadline", "a line under the headline, with more of the story", 100, optional=True),
            ),
            ("photo",),
            _news_headline,
        ),
        Kind(
            "agenda",
            "The talk's agenda: three to five items it will cover, numbered, which appear one by one, a click each.",
            (
                TextField("title", "the agenda's title", 40),
                TextField("items", f"three to five items, separated by |, each at most {AGENDA_ITEM} characters", 200),
            ),
            (),
            _agenda,
        ),
        Kind(
            "section",
            "A section's divider, opening a new part of the talk: its title, under its number (talkgenerator adds it).",
            (
                TextField("title", "the new section's title", 50),
                TextField("subtitle", "a line under it", 90, optional=True),
            ),
            (),
            _section,
        ),
        Kind(
            "questions",
            "The closing slide, inviting the audience's questions: a question, a line under it (a last tip, say), and "
            "a picture to end on, if it has one (a funny one, or an earlier slide's, called back).",
            (
                TextField("title", "a question that invites the audience's questions", 30),
                TextField("subtitle", "a line under it", 80, optional=True),
                TextField(
                    "callback",
                    "the earlier slide whose picture this one shows again, as a callback: what that picture showed, "
                    "as its image search query said it",
                    CALLBACK,
                    optional=True,
                ),
            ),
            ("photo",),
            _questions,
        ),
        # Native diagrams, drawn as texts on shapes
        Kind(
            "timeline",
            "A timeline of three to five moments, oldest first, each a date and what happened; they appear one by "
            "one, a click each, the last one the punchline.",
            (
                TextField("title", "the timeline's title", 60),
                *_moment(1, "first"),
                *_moment(2, "second"),
                *_moment(3, "third"),
                *_moment(4, "fourth", optional=True),
                *_moment(5, "fifth", optional=True),
            ),
            (),
            _timeline,
        ),
        Kind(
            "pyramid",
            "A pyramid of three or four levels, from its top (the rarest, the punchline) down to its base; they "
            "appear one by one, a click each, from the base up.",
            (
                TextField("title", "the pyramid's title", 60),
                *_items(
                    "level",
                    30,
                    "the top of the pyramid: the punchline",
                    "the level under the top",
                    "the level under that (the base, if there's no fourth)",
                    "the base, under that",
                ),
            ),
            (),
            _pyramid,
            pictures=BoxPictures(
                {
                    "level_1": "the top of the pyramid",
                    "level_2": "the level under the top",
                    "level_3": "the level under that",
                }
            ),
        ),
        Kind(
            "funnel",
            "A funnel of three to five stages, from its widest at the top to its narrowest at the bottom, the "
            "punchline; they appear one by one, a click each.",
            (
                TextField("title", "the funnel's title", 60),
                *_items(
                    "stage",
                    30,
                    "the widest stage, at the top",
                    "the next stage, narrower",
                    "the next stage (the narrowest, if there are no more)",
                    "the next stage",
                    "the narrowest stage, at the bottom",
                ),
            ),
            (),
            _funnel,
            pictures=BoxPictures(
                {"stage_1": "the widest stage, at the top", "stage_2": "the second stage", "stage_3": "the third stage"}
            ),
        ),
        Kind(
            "cycle",
            "A cycle of three to five steps around a circle, each leading to the next, and the last back to the first; "
            "they appear one by one, a click each.",
            (
                TextField("title", "the cycle's title", 60),
                *_items(
                    "step", 24, "the first step", "the second step", "the third step", "a fourth step", "a fifth step"
                ),
            ),
            (),
            _cycle,
            pictures=BoxPictures(_STEPS, most=1),
        ),
        Kind(
            "org_chart",
            "A small org chart: who's in charge (the punchline), over two to four people or things, who appear one "
            "by one, a click each, and who's in charge on the click after them.",
            (
                TextField("title", "the org chart's title", 60),
                TextField("boss", "who's in charge: the punchline", 30),
                *_items(
                    "report",
                    30,
                    "the first one under them",
                    "the second one under them",
                    "a third one under them",
                    "a fourth one under them",
                    required=2,
                ),
            ),
            (),
            _org_chart,
        ),
        Kind(
            "iceberg",
            "An iceberg: what everyone sees, on its tip above the water, and two or three things under the water that "
            "nobody sees, which appear one by one, a click each.",
            (
                TextField("title", "the iceberg's title", 60),
                TextField("tip", "what everyone sees, on the tip", 30),
                *_items(
                    "hidden",
                    40,
                    "something under the water that nobody sees",
                    "something else under the water",
                    "something deeper under the water",
                    required=2,
                ),
            ),
            (),
            _iceberg,
            pictures=BoxPictures(
                {
                    "tip": "the tip, above the water",
                    "hidden_1": "the first thing under the water",
                    "hidden_2": "the second thing under the water",
                }
            ),
        ),
        # The talk formats' (docs/v5-plan.md, section 7): a method, or how a product works
        Kind(
            "process",
            "A process of three to five steps, each leading to the next by an arrow, from the first to the last, the "
            "punchline; they appear one by one, a click each.",
            (
                TextField("title", "the process's title", 60),
                *_items(
                    "step",
                    40,
                    "the first step",
                    "the second step",
                    "the third step (the last, the punchline, if there are no more)",
                    "a fourth step",
                    "a fifth step",
                ),
            ),
            (),
            _process,
            pictures=BoxPictures(_STEPS),
        ),
        Kind(
            "references",
            "A talk's references, as an academic talk ends with them: three to five made-up works it cites, numbered, "
            "which appear one by one, a click each; and a picture of one of them, if it has one (a book's cover, or a "
            "figure from a paper), with a caption that says which, on the click after them.",
            (
                TextField("title", "the slide's title", 40),
                TextField(
                    "items",
                    f"three to five made-up works the talk cites, separated by |, each at most {AGENDA_ITEM} "
                    "characters",
                    260,
                ),
                TextField(
                    "caption",
                    "which of the works the picture is of, by its number in the list, such as 'Cover of [2]'",
                    30,
                    optional=True,
                ),
            ),
            ("figure",),
            _references,
        ),
        # Media
        Kind(
            "meme",
            "A meme: a well-known template's picture, with its captions in the template's boxes. Its template_query "
            "names the template, one of those `talkgenerator formats --memes` lists (with what each caption says), "
            "such as 'Drake Hotline Bling'. Two captions or more appear one by one, a click each, the last one the "
            "punchline.",
            (
                TextField("text_1", "the meme's first caption", 70),
                TextField("text_2", "its second caption", 70, optional=True),
                TextField("text_3", "its third caption", 70, optional=True),
                TextField("text_4", "its fourth caption", 70, optional=True),
            ),
            ("template",),
            _meme,
        ),
        # Slide types from real PowerPoint karaoke decks (docs/v5-plan.md, section 8)
        Kind(
            "fun_fact",
            "A fun fact: one absurd fact, stated as certain, under a heading such as 'Did you know?' (talkgenerator "
            "adds it), with a made-up source, and a photo if it has one.",
            (
                TextField("fact", "the fact: one sentence, stated as certain, that the presenter has to back up", 150),
                TextField("source", "a made-up, unreliable source for the fact", 60, optional=True),
            ),
            ("photo",),
            _fun_fact,
        ),
        Kind(
            "acronym",
            "A made-up method, as an acronym: its letters down the slide, each with the word it stands for; the words "
            "appear one by one, a click each, the last one the punchline.",
            (
                TextField("title", "the method's title, which names the acronym", 60),
                TextField(
                    "acronym", "the acronym the words spell: their first letters in order, three to six capitals", 6
                ),
                *_items(
                    "word",
                    24,
                    "the word the first letter stands for (one word for one letter)",
                    "the second letter's word",
                    "the third letter's word (the punchline, if it's the last)",
                    "the fourth letter's word",
                    "the fifth letter's word",
                    "the sixth letter's word",
                ),
            ),
            (),
            _acronym,
        ),
        Kind(
            "dare",
            "A dare, on a card: a real challenge for the presenter for the rest of the talk (or the next few slides), "
            "which the audience then watches them keep up, or something the presenter has the whole audience do "
            "(talkgenerator adds its heading).",
            (
                TextField(
                    "dare",
                    "the challenge, said to the presenter, for the rest of the talk or the next few slides: an accent "
                    "or a voice, a gesture on every slide, a word to work into every slide, a rule such as speaking "
                    "only in questions; hard to keep up, harmless, and for the presenter alone",
                    DARE,
                    optional=True,
                ),
                TextField(
                    "audience",
                    "what the presenter has the whole audience do, said to them: a show of hands, a call and response "
                    "(when the presenter says a word, everyone answers with another), the front row standing up, a "
                    "sound everyone makes; harmless, fun to join in, and singling nobody out",
                    DARE,
                    optional=True,
                ),
            ),
            (),
            _dare,
        ),
        Kind(
            "flowchart",
            "A flowchart that pretends to help decide: a yes-or-no question at the top, where each answer leads, and "
            "the end both lead to, the punchline; each appears on a click of its own (talkgenerator adds the Yes and "
            "the No).",
            (
                _OPTIONAL_TITLE,
                TextField("question", "the yes-or-no question at the top", 70),
                TextField("yes_step", "where Yes leads: a short step", 48),
                TextField("no_step", "where No leads: another short step", 48),
                TextField("end", "where both steps lead: the same end, the punchline", 48),
            ),
            (),
            _flowchart,
            pictures=BoxPictures(
                {"yes_step": "where Yes leads", "no_step": "where No leads", "end": "the end both lead to"}
            ),
        ),
        Kind(
            "tier_list",
            "A tier list: things ranked in tiers from S (the best) to F (the worst), one to three in a tier; the tiers "
            "fill one by one, a click each, from the worst up to the S tier, the punchline.",
            (
                TextField("title", "the tier list's title", 60),
                TextField("s_tier", "the S tier, the very best: one surprising thing, the punchline", 70),
                TextField("a_tier", "the A tier: one to three things, separated by |", 70),
                TextField("b_tier", "the B tier: one to three things, separated by |", 70, optional=True),
                TextField("c_tier", "the C tier: one to three things, separated by |", 70, optional=True),
                TextField("f_tier", "the F tier, the worst: one to three things, separated by |", 70, optional=True),
            ),
            (),
            _tier_list,
        ),
        Kind(
            "wall_of_text",
            "A wall of text that nobody can read: dense points of jargon filling the slide, as nested bullets, with one "
            "more point hidden among them, the punchline, which a marker highlights on a click (talkgenerator adds "
            "'Continued on next slide' under it).",
            (
                TextField("title", "the slide's title, as if it were all perfectly clear", 60),
                TextField(
                    "points",
                    "twelve to sixteen points of dense jargon, separated by |, each a long sentence of fifteen to "
                    "twenty-five words: the more the better, as nobody is meant to read them",
                    WALL_TEXT,
                ),
                TextField(
                    "highlight",
                    "one more point, hidden among the others and highlighted on a click: the punchline, as dense as "
                    "they are, but absurd",
                    110,
                ),
            ),
            (),
            _wall_of_text,
        ),
        Kind(
            "alignment_chart",
            "An alignment chart, as Dungeons & Dragons sorts characters: nine things in a grid of three by three, from "
            "lawful to chaotic across and from good to evil down (talkgenerator adds the axes' words), which appear "
            "one by one, a click each, in reading order: chaotic evil, the punchline, last.",
            (
                TextField("title", "the alignment chart's title", 60),
                *(
                    TextField(
                        alignment,
                        f"the {alignment.replace('_', ' ')} one, in a few words{_PUNCHLINE.get(alignment, '')}",
                        60,
                    )
                    for alignment in slides.ALIGNMENTS
                ),
            ),
            (),
            _alignment_chart,
        ),
        Kind(
            "red_flags",
            "Red flags: three to five warning signs, each beside a red flag, appearing one by one, a click each, each "
            "more alarming than the last: the last one is the punchline.",
            (
                TextField("title", "the slide's title, which says these are red flags (of what)", 60),
                *_items(
                    "flag",
                    90,
                    "the first red flag",
                    "the second red flag",
                    "the third red flag (the punchline, if it's the last)",
                    "a fourth red flag",
                    "a fifth red flag",
                ),
            ),
            (),
            _red_flags,
        ),
        Kind(
            "reviews",
            "Made-up reviews, with stars: two or three reviewers' ratings (one to five stars) and what they wrote, "
            "appearing one by one, a click each; the last one, the punchline, is a one-star review most of the time.",
            (
                TextField("title", "the slide's title, such as what people are saying", 60, optional=True),
                *(
                    field
                    for index, which in enumerate(("first", "second", "third"), 1)
                    for field in _review(index, which, optional=index == slides.REVIEWS)
                ),
            ),
            (),
            _reviews,
        ),
        Kind(
            "error_message",
            "A fake error message, as if the talk itself crashed: a dialog with a title, an absurd message, an error "
            "code and two or three buttons, the last one the punchline (talkgenerator adds the warning sign).",
            (
                TextField("title", "the dialog's title, as in its title bar", 30, optional=True),
                TextField("message", "the error message", 120),
                TextField("code", "an error code, made up and absurdly precise", 24, optional=True),
                TextField(
                    "buttons",
                    f"two or three of the dialog's buttons, separated by |, each at most {ERROR_BUTTON} characters: "
                    "the last one the punchline, an absurd choice of the talk's own",
                    3 * ERROR_BUTTON + 6,
                ),
            ),
            (),
            _error_message,
        ),
    )
}


# EMOJI (docs/v5-plan.md, D65): some lists have them now and then, one in front of each thing, where a variant of
# their recipe asks for them (the system prompt asks for none anywhere else)
EMOJI_NOTE: Final = "with an emoji in front of every thing on it, one that fits the thing"


def with_emoji(
    kind: str, fields: Iterable[str], hints: Mapping[str, str] | None = None, each: bool = False
) -> dict[str, str]:
    """Hints for a variant whose list has an emoji in front of its things: each field's own hint (the recipe's, or
    else the kind's description), asking for one (in front of each of its things, for a field of several)."""
    descriptions = {text.name: text.description for text in KINDS[kind].texts}
    asked = ", each with an emoji in front that fits it" if each else ", with an emoji in front that fits it"
    return {name: f"{(hints or {}).get(name, descriptions[name])}{asked}" for name in fields}


# THE CLOSING SLIDE (docs/v5-plan.md, D65): it ends the talk on something, as many of each: a funny picture, a last
# tip, or a callback to an earlier slide's picture
LAST_TIP: Final = "a last tip for the audience: one short piece of advice about the talk's topic, in the talk's voice"
CALLBACK_LINE: Final = "a line under it that calls back to that earlier picture, as the talk's last joke"


def closing_variants(line: str) -> tuple[Variant, ...]:
    """The ways a closing slide (of kind questions) ends a talk, as many of each: a funny picture to end on, with the
    recipe's line under it; a last tip for the audience as its line (in an English talk, now and then a real piece of
    advice: see talkgenerator.facts); or a callback to an earlier slide's picture, which the deck shows again (see
    talkgenerator.slide.slides.QuestionsSlide), with a line that calls back to it."""
    return (
        Variant(1, frozenset({"callback"}), "with a funny picture to end the talk on", {"subtitle": line}, facts=False),
        Variant(1, frozenset({"photo", "callback"}), "with a last tip for the audience", {"subtitle": LAST_TIP}),
        Variant(
            1,
            frozenset({"photo"}),
            "calling back to an earlier slide's picture, which it shows again",
            {"subtitle": CALLBACK_LINE},
            facts=False,
        ),
    )
