"""Slide kinds: the shapes of slide a plan can ask for, what to write for each, and how each becomes a slide.

A kind names its text fields (with a description and a length limit, for the language model and the Skill) and its
image slots, and builds one of v4's Slide classes from them. A Recipe ties a kind to a slide generator of a
presentation schema: what its slots ask for (image slots, see talkgenerator.images.slots: which look, from which
sources), what this particular slide is about (its brief and hints), which fields and slots it leaves out, and which
texts come from classic sources instead (real quotes, for instance).
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from pptx.chart.data import ChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

from talkgenerator.models.deck import MatrixDiagram, VennDiagram
from talkgenerator.plan.languages import Language
from talkgenerator.slide import slides
from talkgenerator.sources import chart, diagram, memes
from talkgenerator.util import random_util

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
class Kind:
    name: str
    description: str
    texts: tuple[TextField, ...]
    images: tuple[str, ...]
    build: Builder


@dataclass(frozen=True)
class Variant:
    """A way a recipe's slide can come out, which the talk's dice pick by weight: the text fields and image slots it
    does without (a slot left out isn't searched, and its builder gets None for it), a note for the language model
    (added to the slide's brief), what to write in some of its fields (hints, over the recipe's) and how long that may
    be (limits), and what some of its slots search for, instead of the model's query (a meme's template)."""

    weight: float
    omit: frozenset[str] = frozenset()
    note: str = ""
    hints: Mapping[str, str] = field(default_factory=dict)
    limits: Mapping[str, int] = field(default_factory=dict)
    queries: Mapping[str, str] = field(default_factory=dict)


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
            for slot in KINDS[self.kind].images
            if f"{slot}_query" not in self.omit and slot not in self.omit and slot not in self.queries
        ]

    def slots(self) -> list[tuple[str, ImageSlot | ContentSource]]:
        """The image slots this slide has, by name, with what they ask for (not the ones it leaves out)."""
        return [
            (name, source)
            for name, source in zip(KINDS[self.kind].images, self.images, strict=True)
            if name not in self.omit
        ]

    def varied(self, rng: random_util.Rng, avoid: frozenset[str] = frozenset()) -> Recipe:
        """The recipe as one of its variants, picked by weight with the random stream (itself, without variants): not
        one whose queries are in avoid, while there are others (a meme's template that the talk has already)."""
        if not self.variants:
            return self
        fresh = [variant for variant in self.variants if not set(variant.queries.values()) & avoid] or self.variants
        with random_util.use(rng):
            variant = random_util.weighted_random([(variant.weight, variant) for variant in fresh])
        if variant is None:
            return self
        brief = (self.brief or KINDS[self.kind].description).rstrip(".")
        return dataclasses.replace(
            self,
            omit=self.omit | variant.omit,
            brief=f"{brief}, {variant.note}" if variant.note else brief,
            hints={**self.hints, **variant.hints},
            limits={**self.limits, **variant.limits},
            queries={**self.queries, **variant.queries},
            variants=(),
        )


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
    # The made-up data of v4's correlation curves, under the plan's claim
    data = XyChartData()
    series = data.add_series("Model")
    xs = chart.generate_random_x(0, 2 ** random_util.uniform(1, 10), int(2 ** random_util.uniform(3, 8)))
    points = chart.generate_y(xs, chart.create_interesting_curve_function())
    points = chart.add_gaussian_noise_to_multidim_points(1.5 * random_util.uniform(0, max(xs) / 10), points)
    points = [(abs(x), abs(y)) for x, y in points]
    chart.add_data_to_series(series, points)
    outlier = texts.get("outlier")
    if outlier:  # one point far above the others
        highest = max(y for _, y in points)
        data.add_series(outlier).add_data_point(max(xs) * random_util.uniform(0.4, 0.8), highest * 1.4 or 1)
    return slides.ChartSlide(
        texts["title"],
        XL_CHART_TYPE.XY_SCATTER,
        data,
        chart.create_set_scatter_properties("", ""),
        x_title=texts.get("x_axis"),
        y_title=texts.get("y_axis"),
        point_labels=((1, 0, outlier),) if outlier else (),
    )


def _venn(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    circles = tuple(text for text in (texts["circle_1"], texts["circle_2"], texts.get("circle_3")) if text)
    return slides.DiagramSlide(
        texts["title"], VennDiagram(circles=circles, overlap=texts["overlap"] or "", reveal="punchline")
    )


def _matrix(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    # The dot goes in the quadrant the plan says (or a random one)
    dot_x, dot_y = diagram.dot_position(texts.get("dot_quadrant"))
    return slides.DiagramSlide(
        texts["title"],
        MatrixDiagram(
            x_left=texts["x_left"] or "",
            x_right=texts["x_right"] or "",
            y_bottom=texts["y_bottom"] or "",
            y_top=texts["y_top"] or "",
            top_left=texts["top_left"] or "",
            top_right=texts["top_right"] or "",
            bottom_left=texts["bottom_left"] or "",
            bottom_right=texts["bottom_right"] or "",
            dot=texts["dot"] or "",
            dot_x=dot_x,
            dot_y=dot_y,
            reveal="punchline",
        ),
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
    first, second, third, fourth = options
    return slides.QuizSlide(texts["question"], first, second, third, fourth, answer, texts.get("explanation"))


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
    return slides.QuestionsSlide(texts["title"], texts.get("subtitle"))


def _numbered(texts: Mapping[str, str | None], prefix: str, most: int) -> list[str | None]:
    return [texts.get(f"{prefix}_{index}") for index in range(1, most + 1)]


def _timeline(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    moments = [texts.get(f"{part}_{index}") for index in range(1, 6) for part in ("date", "event")]
    return slides.TimelineSlide(texts["title"], *moments)


def _pyramid(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.PyramidSlide(texts["title"], *_numbered(texts, "level", 4))


def _funnel(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FunnelSlide(texts["title"], *_numbered(texts, "stage", 5))


def _cycle(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.CycleSlide(texts["title"], *_numbered(texts, "step", 5))


def _org_chart(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.OrgChartSlide(texts["title"], texts["boss"], *_numbered(texts, "report", 4))


def _iceberg(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.IcebergSlide(texts["title"], texts["tip"], *_numbered(texts, "hidden", 3))


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
    return slides.AcronymSlide(title, *written)


def _respelled(title: str, acronym: str, initials: str) -> str:
    """The title with the acronym it names spelled as its words' initials, where a model's acronym isn't (its
    "PIRATES" over the words "Public Invoicing, Reimbursement..."): the letters on the slide are the words', so the
    title says them too, with dots between them if the model wrote it so ("S.P.A.R.K.")."""
    written = acronym.strip()
    dotted = "." in written
    respelled = "".join(f"{letter}." for letter in initials) if dotted else initials
    if written and written in title:
        return title.replace(written, respelled)
    plain = written.replace(".", "")
    pattern = re.compile(rf"\b{re.escape(plain)}\b", re.IGNORECASE) if plain else None
    return pattern.sub(respelled, title) if pattern is not None and pattern.search(title) else title


def _dare(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.DareSlide(language.dare, texts["dare"])  # (its heading is talkgenerator's: "Challenge")


def _flowchart(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    return slides.FlowchartSlide(
        texts.get("title"),
        texts["question"],
        texts["yes_step"],
        texts["no_step"],
        texts["end"],
        yes=language.yes,
        no=language.no,
    )


def _tier_list(texts: Mapping[str, str | None], images: Mapping[str, Any], language: Language) -> slides.Slide:
    tiers = [texts.get(f"{tier.lower()}_tier") for tier in slides.TIERS]
    if not slides.tier_items(tiers[0]) or not slides.tier_items(tiers[1]):
        raise ValueError("a tier list needs things in its S and A tiers")
    return slides.TierListSlide(texts["title"], *tiers)


def _shortened(text: str, length: int) -> str:
    """The text, cut between words to at most this many characters (or within its first word, if that's longer)."""
    if len(text) <= length:
        return text
    cut = text[: length + 1].rsplit(" ", 1)[0].rstrip(",;:-–— ")
    return cut if 0 < len(cut) <= length else text[:length]


def _quadrant(corner: str, ends: str) -> TextField:
    return TextField(corner.replace(" ", "_"), f"the label of the {corner} quadrant: what is {ends}", 30)


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
            "A scatter plot of made-up data, under a claim of a correlation.",
            (
                TextField("title", "a made-up correlation between two things, as a claim", 90),
                TextField("x_axis", "the axis along the bottom: the first of the two things", 40, optional=True),
                TextField("y_axis", "the axis going up: the second thing", 40, optional=True),
                TextField(
                    "outlier",
                    "one point far above the others, named after someone or something that doesn't belong there",
                    30,
                    optional=True,
                ),
            ),
            (),
            _chart_correlation,
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
        ),
        Kind(
            "matrix",
            "A 2×2 matrix: two axes that cross in the middle, with a title at each end, a label in each quadrant, and "
            "one dot with a name, the punchline, which appears on a click.",
            (
                TextField("title", "the matrix's title", 60),
                TextField("x_left", "the title at the left end of the axis along the bottom", 30),
                TextField("x_right", "the title at the right end of that axis: the opposite of the left end", 30),
                TextField("y_bottom", "the title at the bottom end of the axis going up", 30),
                TextField("y_top", "the title at the top end of that axis: the opposite of the bottom end", 30),
                _quadrant("top left", "both like the top end and like the left end"),
                _quadrant("top right", "both like the top end and like the right end"),
                _quadrant("bottom left", "both like the bottom end and like the left end"),
                _quadrant("bottom right", "both like the bottom end and like the right end"),
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
            "Three or four made-up figures on tiles, as on a dashboard, each a number and what it measures; the last "
            "one, the punchline, appears on a click.",
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
            "A quiz question for the audience, with three or four options (A to D); the answer, and why, appear on a "
            "click.",
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
            "The talk's agenda: three to five items it will cover, numbered.",
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
            "The closing slide, inviting the audience's questions.",
            (
                TextField("title", "a question that invites the audience's questions", 30),
                TextField("subtitle", "a line under it", 80, optional=True),
            ),
            (),
            _questions,
        ),
        # Native diagrams, drawn as texts on shapes
        Kind(
            "timeline",
            "A timeline of three to five moments, oldest first, each a date and what happened; the last one, the "
            "punchline, appears on a click.",
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
            "A pyramid of three or four levels, from its top (the rarest, the punchline, which appears on a click) "
            "down to its base.",
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
        ),
        Kind(
            "funnel",
            "A funnel of three to five stages, from its widest at the top to its narrowest at the bottom, the "
            "punchline, which appears on a click.",
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
        ),
        Kind(
            "cycle",
            "A cycle of three to five steps around a circle, each leading to the next, and the last back to the first.",
            (
                TextField("title", "the cycle's title", 60),
                *_items(
                    "step", 24, "the first step", "the second step", "the third step", "a fourth step", "a fifth step"
                ),
            ),
            (),
            _cycle,
        ),
        Kind(
            "org_chart",
            "A small org chart: who's in charge (the punchline, which appears on a click), over two to four people "
            "or things.",
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
            "nobody sees, which appear on a click.",
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
        ),
        # Media
        Kind(
            "meme",
            "A meme: a well-known template's picture, with its captions in the template's boxes. Its template_query "
            "names the template, one of those `talkgenerator formats --memes` lists (with what each caption says), "
            "such as 'Drake Hotline Bling'.",
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
                TextField("fact", "the fact: one sentence, stated as certain, that the presenter has to back up", 120),
                TextField("source", "a made-up, unreliable source for the fact", 60, optional=True),
            ),
            ("photo",),
            _fun_fact,
        ),
        Kind(
            "acronym",
            "A made-up method, as an acronym: its letters down the slide, each with the word it stands for; the last "
            "word, the punchline, appears on a click.",
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
            "A dare for the presenter, on a card: a playful task for the next slide or the rest of the talk, which the "
            "audience then watches them do (talkgenerator adds its heading).",
            (
                TextField(
                    "dare",
                    "the task, said to the presenter: a way of speaking, a word to work in, a voice; for the presenter "
                    "alone, and nothing physical",
                    130,
                ),
            ),
            (),
            _dare,
        ),
        Kind(
            "flowchart",
            "A flowchart that pretends to help decide: a yes-or-no question at the top, where each answer leads, and "
            "the end both lead to, the punchline, which appears on a click (talkgenerator adds the Yes and the No).",
            (
                _OPTIONAL_TITLE,
                TextField("question", "the yes-or-no question at the top", 70),
                TextField("yes_step", "where Yes leads: a short step", 48),
                TextField("no_step", "where No leads: another short step", 48),
                TextField("end", "where both steps lead: the same end, the punchline", 48),
            ),
            (),
            _flowchart,
        ),
        Kind(
            "tier_list",
            "A tier list: things ranked in tiers from S (the best) to F (the worst), one to three in a tier; the S "
            "tier, the punchline, appears on a click.",
            (
                TextField("title", "the tier list's title", 60),
                TextField("s_tier", "the S tier, the very best: one surprising thing, the punchline", 50),
                TextField("a_tier", "the A tier: one to three things, separated by |", 70),
                TextField("b_tier", "the B tier: one to three things, separated by |", 70, optional=True),
                TextField("c_tier", "the C tier: one to three things, separated by |", 70, optional=True),
                TextField("f_tier", "the F tier, the worst: one to three things, separated by |", 70, optional=True),
            ),
            (),
            _tier_list,
        ),
    )
}
