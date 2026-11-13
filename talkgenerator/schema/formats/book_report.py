"""The school book report (docs/v5-plan.md, section 7; D79): a pupil's report on a book about the talk's topic,
presented as earnestly as book reports are.

Its arc goes from the book (its cover, in one photo or full-bleed, or the book in numbers, on tiles) through its
author (a fun fact about them, with their portrait, or the portrait alone), the main characters (three photos with
captions, or who's who as an org chart), what happens (the plot as a process, how exciting the book is page by page
as a trend chart, or the story as a timeline of its pages), the favourite part (an odd photo, full-bleed, or said over
a photo), the moral of the story (said over a photo, or a quiz for the class) and the rating (one big score, or what
the class said, as reviews), before its closer says "The End" (D76), outside the report's slides.
A short report keeps the book, the characters, what happens and the rating; a quarter of a talk's slides are free (D63),
for memes, gifs, full-screen pictures, a tier list, a fun fact and its own provocations ("Plot twist!", over a
full-screen picture), and its author waits for talks of eleven slides or more. The book's made-up title and its
author's made-up name come from the topic (see talkgenerator.schema.formats.book and author), so that a classic
report's slides name the book its title reports on.

A kindergarten teacher gives a book report more often than the other personas, and an influencer, an alien
anthropologist and an over-passionate expert a little more often; its themes are the kids', the chalkboard's and
Comic Sans' more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import Recipe, Variant, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    author,
    behind,
    book,
    different,
    maybe,
    photos,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.util import random_util

PACK: Final = "book_report"

# (its closer says "The End", outside its slides, as D76's closers do, so none of them says it; its rating, a score to
# end on, stays longest after the book and what happens, and its author waits for talks of eleven slides or more)
ARC: Final = Arc(
    (
        Part("book", rank=0),
        Part("author", rank=6, shortest=11),
        Part("characters", rank=3),
        Part("plot", 1, 2, rank=1),
        Part("favourite", rank=4),
        Part("moral", rank=5),
        Part("rating", rank=2),
    ),
    free=0.25,  # (D63: two slides of ten for a meme, a gif or a picture, as in the other formats)
)

BOOK_REPORT: Final = Format(
    brief="a school book report on a book about the topic, presented by a pupil as earnestly as book reports are: the "
    "book and its cover, the author, the main characters, what happens, the favourite part, the moral of the story "
    "and the rating. The book and its author are made up (never real ones), and every slide is a "
    "pupil's, played straight: short sentences, big pictures, the odd misunderstanding and an obvious wish to be done",
    title_hint="like a book report's title: 'My Book Report:' and the book's made-up title",
    job_hint="their year and class at school, as a pupil gives them on a book report",
    personas={"kindergarten_teacher": 5, "influencer": 1.5, "alien_anthropologist": 1.5, "passionate_expert": 1.3},
    themes={
        "sticky notes": 2,
        "corkboard": 1.5,
        "kids": 4,
        "chalkboard": 3,
        "Comic Sans everywhere": 2.5,
        "vintage paper": 1.3,
        "dark minimal": 0.4,
        "corporate": 0.4,
        "hacker terminal": 0.4,
        "brutalist": 0.5,
        "Swiss poster": 0.6,
    },
    arc=ARC,
    # (its closer says "The End", and asks whether the pupil can sit down now: D76)
    closer=Closer(said("the_end"), said("sit_down"), presenter),
    scene="school classroom book",
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, the presenter and the title, and the
    made-up title and author of the book the report is on."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    topic = str(context.get("topic") or context["seed"])
    variables["book"], variables["author"] = book(topic), author(topic)
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE TITLE SLIDE: the book the report is on, and who reports on it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic book report's title, about the seed (the talk's topic)."""
    topic = str(context["seed"])
    return text(PACK, "title.talk_title", {**context, "book": book(topic), "author": author(topic)})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: the book's cover (a book cover from Reddit, real or fake, or one that prefers to be generated, with its title
# on it; an illustration of the topic without Reddit), the author's portrait, odd photos of the characters and of the
# favourite part, and a calm backdrop behind what's said (a classic report's end calls back an earlier picture)
_BACKDROP = cg.statement_backdrop_generator
_COVER = ImageSlot(
    "the cover of the book the report is on", aesthetic="book-covers", generate=True, backups=("illustration",)
)
_AUTHOR = ImageSlot("a portrait of the book's author", aesthetic="portrait", generate=True)
_CHARACTER = ImageSlot("a photo of one of the book's characters", aesthetic="weird-stock")
_FAVOURITE = ImageSlot(
    "an odd photo of the reader's favourite part of the book", aesthetic="weird-stock", generate=True
)


# THE BOOK: its cover, in one photo or full-bleed, or the book in numbers


def _cover(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "book.cover_title", _variables(context))
    return ({"title": title}, {"image": _COVER(context)}) if title else None


def _cover_full(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "book.cover_full_title", _variables(context))
    return ({"title": title}, {"image": _COVER(context)}) if title else None


def _in_numbers(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.5 else 3
    stats = [stat.split("|") for stat in different(PACK, "book.stat", variables, count - 1)]
    punchline = (text(PACK, "book.stat_punchline", variables) or "").split("|")
    title = text(PACK, "book.numbers_title", variables)
    if not title or len(stats) < count - 1 or len(punchline) != 2 or any(len(stat) != 2 for stat in stats):
        return None
    texts: dict[str, str | None] = {"title": title}
    for index, (number, label) in enumerate([*stats, punchline], 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = number.strip(), label.strip()
    return texts, behind(context, KPI_PICTURES)


# THE AUTHOR: a fun fact with their portrait, or the portrait alone


def _author_fact(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    fact = text(PACK, "author.author_fact", variables)
    if not fact:
        return None
    texts = {"fact": fact, "source": maybe(0.8, text(PACK, "author.author_source", variables))}
    return texts, {"photo": _AUTHOR(context)}


def _author_photo(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "author.author_title", _variables(context))
    return ({"title": title}, {"image": _AUTHOR(context)}) if title else None


# THE MAIN CHARACTERS: three photos, or who's who


def _characters(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    characters = different(PACK, "characters.character", variables, 2)
    punchline = text(PACK, "characters.character_punchline", variables)
    if len(characters) < 2 or not punchline:
        return None
    texts = {
        "title": text(PACK, "characters.characters_title", variables),
        **_items("caption", [*characters, punchline]),
    }
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_CHARACTER, context, 3), 1)}


def _whos_who(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    characters = different(PACK, "characters.report", variables, random_util.randint(2, 4))
    title, boss = text(PACK, "characters.org_title", variables), text(PACK, "characters.boss", variables)
    if not title or not boss or len(characters) < 2:
        return None
    return {"title": title, "boss": boss, **_items("report", characters)}, {}


# WHAT HAPPENS: in steps, how exciting it is page by page, or page by page


def _what_happens(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "plot.plot_first", variables), text(PACK, "plot.plot_last", variables)
    middle = different(PACK, "plot.plot_step", variables, count - 2)
    title = text(PACK, "plot.process_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    return {"title": title, **_items("step", [first, *middle, last])}, {}


def _excitement(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "plot.chart_title", variables)
    if not title:
        return None
    second = maybe(0.5, text(PACK, "plot.chart_second", variables))
    return {
        "title": title,
        "x_axis": text(PACK, "plot.chart_x", variables),
        "y_axis": text(PACK, "plot.chart_y", variables),
        "shape": random_util.choice(("rollercoaster", "peak", "dip", "exponential", "hockey stick", "crash")),
        "line": text(PACK, "plot.chart_line", variables),
        "second_line": second,
        "second_shape": random_util.choice(("flat", "falling", "plateau")) if second else None,
        "event": maybe(0.7, text(PACK, "plot.chart_event", variables)),
    }, {}


def _page_by_page(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    moments = different(PACK, "plot.timeline_event", variables, count - 1)
    punchline, title = text(PACK, "plot.timeline_punchline", variables), text(PACK, "plot.timeline_title", variables)
    if not title or not punchline or len(moments) < count - 1:
        return None
    known = words(PACK, "plot.page")  # (the first pages first)
    pages = [known[index] for index in sorted(random_util.sample(range(len(known)), count))]
    texts: dict[str, str | None] = {"title": title}
    for index, (page, moment) in enumerate(zip(pages, [*moments, punchline], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = page, moment
    return texts, {}


# THE FAVOURITE PART: an odd photo of it, or said over a photo


def _favourite(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "favourite.favourite_title", _variables(context))
    return ({"title": title}, {"image": _FAVOURITE(context)}) if title else None


def _favourite_said(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "favourite.favourite_statement", _variables(context))
    return ({"text": said}, {"background": _BACKDROP(context)}) if said else None


# THE MORAL OF THE STORY: said over a photo, or a quiz for the class


def _moral(context: dict[str, Any]) -> Made | None:
    moral = text(PACK, "moral.moral", _variables(context))
    return ({"text": moral}, {"background": _BACKDROP(context)}) if moral else None


def _what_we_learned(context: dict[str, Any]) -> Made | None:
    """A quiz whose right answer is the lesson the pupil took from the book, among things it didn't teach."""
    variables = _variables(context)
    count = 4 if random_util.random() < 0.5 else 3
    wrong = different(PACK, "moral.quiz_option", variables, count - 1)
    right, question = text(PACK, "moral.quiz_answer", variables), text(PACK, "moral.quiz_question", variables)
    if not question or not right or len(wrong) < count - 1:
        return None
    options = random_util.sample([*wrong, right], count)
    texts: dict[str, str | None] = {
        "question": question,
        "answer": slides.LETTERS[options.index(right)],
        "explanation": maybe(0.8, text(PACK, "moral.quiz_explanation", variables)),
    }
    for letter, option in zip(slides.LETTERS, options, strict=False):
        texts[f"option_{letter.lower()}"] = option
    return texts, {}


# THE RATING: one big score, or what the class said


def _rating(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "rating.rating_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "rating.rating_title", variables),
        "number": random_util.choice(words(PACK, "rating.score")),
        "label": label,
        "source": maybe(0.7, text(PACK, "rating.rating_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _class_reviews(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 3 if random_util.random() < 0.6 else 2
    good = different(PACK, "rating.review_good", variables, count - 1)
    bad = text(PACK, "rating.review_bad", variables)
    reviewers = different(PACK, "rating.reviewer", variables, count)
    if len(good) < count - 1 or not bad or len(reviewers) < count:
        return None
    stars = [random_util.choice(("5", "5", "4")) for _ in good] + [random_util.choice(("1", "1", "2"))]
    texts: dict[str, str | None] = {"title": maybe(0.8, text(PACK, "rating.reviews_title", variables))}
    for index, (rating, review, reviewer) in enumerate(zip(stars, [*good, bad], reviewers, strict=True), 1):
        texts[f"stars_{index}"], texts[f"review_{index}"], texts[f"reviewer_{index}"] = rating, review, reviewer
    return texts, {}


# THE SLIDE GENERATORS


def _part(
    part: str,
    weight: float,
    kind: str,
    content: Any,
    tags: list[str],
    name: str,
    recipe: Recipe,
    repeats: int = 2,
) -> SlideGeneratorData:
    """A slide generator of one of the arc's parts: its slides are of the kind, classic ones from the content."""
    return SlideGeneratorData(
        KindSlideGenerator(kind, content),
        weight_function=InPart(ARC, part, weight),
        retries=3,
        allowed_repeated_elements=repeats,
        tags=[part, *tags],
        name=f"{name} (Book Report)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a pupil's book report has it: a few plain words"
_FEW_WORDS = "in two to five words"
_PUPIL = "in a pupil's short, earnest sentences"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Book Report)",
        llm=Recipe("title"),
    ),
    # The book
    _part(
        "book",
        1.4,
        "image",
        _cover,
        ["single_image"],
        "The Book",
        Recipe(
            "image",
            (_COVER,),
            brief="The book the report is on: its cover, in one photo, under a title that names the book",
            hints={"title": "a title that names the book by its made-up title, such as 'My Book Report:' and it"},
        ),
    ),
    _part(
        "book",
        1,
        "full_image",
        _cover_full,
        ["full_image"],
        "Book Cover",
        Recipe(
            "full_image",
            (_COVER,),
            brief="The book's cover, filling the slide, under its made-up title and author",
            hints={"title": "the book's made-up title, and who wrote it, in a few words"},
        ),
    ),
    _part(
        "book",
        0.6,
        "kpi",
        _in_numbers,
        ["kpi"],
        "The Book in Numbers",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The book in numbers, on tiles, as a pupil counted them: its pages, its pictures and the like, each "
            "a number and what it counts, the last one the punchline, such as how many pages the pupil really read",
            hints={
                "title": _TITLE_HINT + ", such as 'The book in numbers'",
                **{f"number_{index}": "the number, such as '212'" for index in range(1, 5)},
                **{f"label_{index}": "what the number counts, without the number itself" for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three figures"),
                    Variant(1, note="with four figures"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    # The author
    _part(
        "author",
        1.2,
        "fun_fact",
        _author_fact,
        ["fun_fact"],
        "About the Author",
        Recipe(
            "fun_fact",
            (_AUTHOR,),
            brief="A fun fact about the book's made-up author, with their portrait: something odd about them, or about "
            "how they wrote the book, as the pupil read it on the back cover",
            hints={
                "fact": "the fact about the author, by their made-up name, in one sentence, stated as certain",
                "source": "where the pupil read it, such as the back of the book",
            },
        ),
    ),
    _part(
        "author",
        1,
        "image",
        _author_photo,
        ["single_image"],
        "The Author",
        Recipe(
            "image",
            (_AUTHOR,),
            brief="The book's made-up author, in one portrait, under a title that introduces them",
            hints={"title": "a title that introduces the author by their made-up name, such as 'About the author:'"},
        ),
    ),
    # The main characters
    _part(
        "characters",
        1.4,
        "three_columns",
        _characters,
        ["three_captions"],
        "Main Characters",
        Recipe(
            "three_columns",
            (_CHARACTER, _CHARACTER, _CHARACTER),
            brief="The book's main characters, each a photo with a caption that says who they are, the last one the "
            "punchline, such as someone who isn't in the book at all",
            hints={
                "title": _TITLE_HINT + ", such as 'The main characters'",
                "caption_1": f"a character, and who they are in the book, {_FEW_WORDS}",
                "caption_2": f"another character, {_FEW_WORDS}",
                "caption_3": f"the last character, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "characters",
        1,
        "org_chart",
        _whos_who,
        ["org_chart"],
        "Who's Who",
        Recipe(
            "org_chart",
            brief="Who's who in the book, as an org chart: the book's characters, under who's really in charge, the "
            "punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Who's who in the book'",
                "boss": "who's really in charge in the book, in a few words: the punchline",
                **{f"report_{index}": "a character of the book, in a few words" for index in range(1, 5)},
            },
        ),
    ),
    # What happens
    _part(
        "plot",
        1.3,
        "process",
        _what_happens,
        ["process"],
        "What Happens",
        Recipe(
            "process",
            brief="What happens in the book, step by step, as a pupil retells it: the last step the punchline, such as "
            "how it ends, or where the pupil stopped reading",
            hints={
                "title": _TITLE_HINT + ", such as 'What happens'",
                **{f"step_{index}": f"what happens, {_FEW_WORDS}" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"step_4", "step_5"}), "in three steps"),
                Variant(1, frozenset({"step_5"}), "in three or four steps"),
                Variant(1, note="in three to five steps"),
            ),
        ),
    ),
    _part(
        "plot",
        1,
        "chart_trend",
        _excitement,
        ["trend_chart", "chart"],
        "How Exciting It Is",
        Recipe(
            "chart_trend",
            brief="How exciting the book is, page by page, as a line chart with the twist marked on it; a second "
            "line, if any, someone else's, such as the pupil's little brother's, as the punchline",
            hints={
                "title": "what the chart shows, as a pupil puts it, such as 'How exciting the book is'",
                "x_axis": "the book's pages or chapters, such as 'Page'",
                "y_axis": "how exciting it is, in the pupil's words",
                "line": "the line's name in the legend, such as 'Excitement'",
                "second_line": "someone else's line, such as 'My little brother', who appears on a click",
                "event": "the twist, or another moment of the book, marked on the line, in a few words",
            },
        ),
    ),
    _part(
        "plot",
        0.9,
        "timeline",
        _page_by_page,
        ["timeline"],
        "Page by Page",
        Recipe(
            "timeline",
            brief="What happens in the book, page by page, the first pages first, the last moment the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The story, page by page'",
                **{f"date_{index}": "a page of the book, such as 'Page 12'" for index in range(1, 6)},
                **{f"event_{index}": f"what happens there, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    # The favourite part
    _part(
        "favourite",
        1.3,
        "full_image",
        _favourite,
        ["full_image"],
        "My Favourite Part",
        Recipe(
            "full_image",
            (_FAVOURITE,),
            brief="The pupil's favourite part of the book: an odd photo of it, filling the slide, under a title that "
            "says it's their favourite part",
            hints={"title": "a title that says it's the favourite part, in a few words"},
        ),
    ),
    _part(
        "favourite",
        1,
        "statement",
        _favourite_said,
        ["statement"],
        "Favourite Part",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The pupil's favourite part of the book, said over a photo, earnestly, with too much detail or too "
            "little",
            hints={"text": f"the favourite part, {_PUPIL}, starting with 'My favourite part was'"},
        ),
    ),
    # The moral of the story
    _part(
        "moral",
        1.3,
        "statement",
        _moral,
        ["statement"],
        "The Moral",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The moral of the story, as the pupil understood it, said over a photo: earnest, and a little off",
            hints={"text": f"the moral of the story, {_PUPIL}, starting with 'The moral of the story is'"},
        ),
    ),
    _part(
        "moral",
        1,
        "quiz",
        _what_we_learned,
        ["quiz"],
        "What We Learned",
        Recipe(
            "quiz",
            brief="A quiz for the class about the book's lesson: what we learned from it, with three or four options, "
            "and the lesson the pupil took from it as the answer",
            hints={
                "question": "the quiz question about the book's lesson, such as 'What did we learn from this book?'",
                "explanation": "why that's the lesson, as the pupil is sure of it",
            },
        ),
    ),
    # The rating
    _part(
        "rating",
        1.3,
        "big_number",
        _rating,
        ["big_number"],
        "My Rating",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The pupil's rating of the book, as one big score, with why under it",
            hints={
                "title": _TITLE_HINT + ", such as 'My rating'",
                "number": "the score, such as '7/10' or '4 stars'",
                "label": "why that score, in a pupil's words, without the score itself",
                "source": "who gave the score, such as the pupil and their age",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "rating",
        1,
        "reviews",
        _class_reviews,
        ["reviews"],
        "What the Class Said",
        Recipe(
            "reviews",
            brief="What the pupil's class said about the book, as reviews with stars: kind ones, and the last one, the "
            "punchline, a one-star review",
            hints={
                "title": "a title such as 'What my class thinks', or empty for none",
                **{
                    f"reviewer_{index}": "who in the class wrote it: a made-up first name, and a detail"
                    for index in range(1, 4)
                },
            },
        ),
    ),
]

# The format's other slides, for a report's free slides (and to stand in for a part's slide that none of the part's
# generators can make): memes most of all (D63), gifs, full-screen pictures, deep questions over photos (which a talk
# may have any number of, so that the free slides of a long one, without fair use too, never run out of slides), a
# tier list, a fun fact, and two pictures with gifs
_OTHERS: Final = {
    "Meme": 1.8,
    "Full Screen Gif": 1,
    "Full Screen Neutral Images": 0.8,
    "Full Screen Pixabay Deep": 0.6,
    "Tier List": 0.6,
    "Fun Fact": 0.5,
    "Two Captions Gifs": 0.5,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(
        slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Book Report)")
        for name, weight in _OTHERS.items()
    ),
    provocation(PACK, ARC, 1.2, _variables, "Book Report", "as a pupil reads them out, wide-eyed"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a book report may have (see presentation_schema.most_slides): each kind once, so that its
# plot's two slides are of two kinds, but two statements (its favourite part, its moral and its end may each be one),
# and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "chart": 2,
    "statement": 2,
    "three_captions": 1,
    "process": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
