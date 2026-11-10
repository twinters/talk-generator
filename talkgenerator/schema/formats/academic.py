"""The academic conference talk (docs/v5-plan.md, section 7; D56): research on the talk's topic, presented at a
conference, with its affiliations on the title slide.

Its arc goes from its motivation (D69: the problem the research is about, its why, as a problem slide four times in
five, or else its research question over a photo) and the outline through related work (a Venn diagram with this work
where the fields overlap, a 2×2 matrix of earlier work, or the field's history), the method (a diagram of its steps,
its equation, or its setup), the results (charts with suspicious p-values, or one p-value as a big number), the
limitations (an iceberg), future work (a timeline, the research cycle, or a flowchart whose every answer leads to more
research), the acknowledgements and the references to the questions. A short talk keeps the motivation, the method,
the results and the questions; a quarter of a talk's slides are free (D63), for memes, real charts from the internet, Reddit's weird pictures, the talk's own
provocations ("Peer reviewed.", over a full-screen picture), fun facts and the like, and its outline and
acknowledgements come in talks of eleven slides or more; a long one gives the method a second slide and the results up
to three. The method's made-up name comes from the topic (see talkgenerator.schema.formats.method).

A disgraced professor presents an academic talk more often than the other personas, and an over-passionate expert, a
medieval historian and a time traveller a little more often; its themes are the academic family's more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import (
    AGENDA_ITEM,
    Recipe,
    Variant,
    closing_variants,
    matrix_landscape,
    pictured,
    problem_variants,
)
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    different,
    maybe,
    method,
    photos,
    problem,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.util import random_util

PACK: Final = "academic"

# (D63: a quarter of its slides are free, for memes, real charts from the internet and weird pictures, and its outline
# and acknowledgements, lists of text, wait for a talk of eleven slides or more: the user found ten-slide academic
# talks "pretty boring with mostly boring text and a lot of superfluous slides"; D69: its motivation first, its why,
# kept by every talk of three slides or more, as good academic talks explain their problem first, the user said, so a
# ten-slide talk goes without future work)
ARC: Final = Arc(
    (
        Part("motivation", rank=1),
        Part("outline", rank=8),
        Part("related_work", rank=6),
        Part("method", 1, 2, rank=2),
        Part("results", 1, 3, rank=3),
        Part("limitations", rank=4),
        Part("future_work", rank=7),
        Part("acknowledgements", rank=9),
        Part("references", rank=5),
        Part("questions", rank=0),
    ),
    free=0.25,
)

ACADEMIC: Final = Format(
    brief="a talk at an academic conference: its motivation (the problem the research is about), an outline, "
    "related work, the method, the results with their statistics (p-values, error bars), the limitations, future work, "
    "the acknowledgements, the references and the questions. The topic is the research field, however absurd, and "
    "every slide is a conference talk's, played straight",
    title_hint="like a paper's title at a conference: a catchy phrase, a colon and a dry subtitle",
    job_hint="an affiliation, as on a paper, in a few words: their position and a made-up university or department",
    personas={"disgraced_professor": 6, "passionate_expert": 2.5, "medieval_historian": 1.5, "time_traveller": 1.3},
    themes={
        "academic": 5,
        "chalkboard": 2,
        "blueprint": 1.6,
        "clean keynote": 1.2,
        "vintage paper": 1.2,
        "startup": 0.4,
        "neon": 0.5,
        "kids": 0.4,
        "1997 WordArt": 0.7,
    },
    arc=ARC,
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its method's name, the presenter and the
    title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["method"] = method(str(context.get("topic") or context["seed"]))
    return variables


# THE TITLE SLIDE: a paper's title, and who presents it, with their affiliation


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic academic talk's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "method": method(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a calm backdrop behind a statement (D63: calm photos mixed with the backdrop look), an odd photo of the
# experimental setup, whoever is thanked, and a picture of one of the references (D65): a book's cover (generated, in a
# talk that generates pictures), or a figure from a paper, a real chart from the internet; old prints and plates from
# museums, or illustrations, without Reddit
_BACKDROP = cg.statement_backdrop_generator
_SETUP = ImageSlot("a photo of the experiment's setup", aesthetic="weird-stock", generate=True)
_THANKED = cg.copyright_free_generator
_COVER = ImageSlot(
    "the cover of one of the works the talk cites, as a book",
    aesthetic="book-covers",
    generate=True,
    backups=("museum", "illustration"),
)
_FIGURE = ImageSlot(
    "a figure from one of the works the talk cites: a chart", aesthetic="bad-charts", backups=("museum", "illustration")
)
# (D69: the problem slide's picture beside the problem, which shows it as it happens; generated, in a talk that
# generates pictures)
_PUZZLE = ImageSlot(
    "a picture that shows the problem the research is about, as it happens", aesthetic="weird-stock", generate=True
)


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE MOTIVATION: the problem slide (D69), or the research question over a photo

# (a puzzle: typical and weird ones a little more often than the other angles)
_ANGLES: Final = {"typical": 1.3, "weird": 1.2}
_PROBLEMS: Final = {
    "kicker": "motivation.kicker",
    "weird": "motivation.weird",
    "everyday": "motivation.everyday",
    "crossed": "motivation.crossed",
    "typical": "motivation.typical",
    "real": "motivation.real",
}


def _motivation(context: dict[str, Any]) -> Made | None:
    return problem(PACK, _PROBLEMS, _variables(context), context, (_BACKDROP, _PUZZLE), _ANGLES)


def _research_question(context: dict[str, Any]) -> Made | None:
    question = text(PACK, "motivation.research_question", _variables(context))
    return ({"text": question}, {"background": _BACKDROP(context)}) if question else None


# THE OUTLINE


def _outline(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    first, last = text(PACK, "outline.outline_first", variables), text(PACK, "outline.outline_last", variables)
    middle = different(PACK, "outline.outline_item", variables, random_util.randint(1, 3))
    title = text(PACK, "outline.outline_title", variables)
    if not title or not first or not last or not middle:
        return None
    return {"title": title, "items": " | ".join([first, *middle, last])}, {}


# RELATED WORK: this work where the fields overlap, earlier work in a 2×2 matrix, or the field's history


def _related_venn(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    fields = different(PACK, "related.field", variables, 3 if random_util.random() < 0.5 else 2)
    title, overlap = text(PACK, "related.venn_title", variables), text(PACK, "related.overlap", variables)
    if not title or not overlap or len(fields) < 2:
        return None
    return {"title": title, **_items("circle", fields), "overlap": overlap}, {}


def _related_matrix(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    axes = different(PACK, "related.axis", variables, 2)
    citations = different(PACK, "related.citation", variables, 3)
    title, gap = text(PACK, "related.matrix_title", variables), text(PACK, "related.gap", variables)
    if not title or not gap or len(axes) < 2 or len(citations) < 3:
        return None
    (x_left, x_right), (y_bottom, y_top) = (axis.split("|") for axis in axes)
    return {
        "title": title,
        "x_left": x_left.strip(),
        "x_right": x_right.strip(),
        "y_bottom": y_bottom.strip(),
        "y_top": y_top.strip(),
        "top_left": citations[0],
        "bottom_left": citations[1],
        "bottom_right": citations[2],
        "top_right": gap,
        "dot": variables["method"],
        "dot_quadrant": "top right",
    }, {}


def _related_timeline(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    milestones = different(PACK, "related.milestone", variables, count - 1)
    punchline, now = text(PACK, "related.this_work", variables), text(PACK, "related.now", variables)
    title = text(PACK, "related.timeline_title", variables)
    if not title or not punchline or not now or len(milestones) < count - 1:
        return None
    known = words(PACK, "related.when")  # (oldest first)
    dates = [known[index] for index in sorted(random_util.sample(range(len(known)), count - 1))] + [now]
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(dates, [*milestones, punchline], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


# THE METHOD: a diagram of its steps, its equation, or its setup


def _method(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "method.step_first", variables), text(PACK, "method.step_last", variables)
    middle = different(PACK, "method.step", variables, count - 2)
    title = text(PACK, "method.method_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    return {"title": title, **_items("step", [first, *middle, last])}, {}


def _equation(context: dict[str, Any]) -> Made | None:
    equation = text(PACK, "method.equation", _variables(context))
    return ({"text": equation}, {"background": _BACKDROP(context)}) if equation else None


def _setup(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "method.setup_title", _variables(context))
    return ({"title": title}, {"image": _SETUP(context)}) if title else None


# THE RESULTS: charts with suspicious p-values, or one p-value as a big number


def _results_ranking(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    baselines = different(PACK, "results.baseline", variables, random_util.randint(3, 4))
    title = text(PACK, "results.ranking_title", variables)
    if not title or len(baselines) < 3:
        return None
    return {
        "title": title,
        "bars": " | ".join([*baselines, variables["method"]]),
        "value_axis": text(PACK, "results.measure", variables),
    }, {}


def _results_correlation(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "results.correlation_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "results.correlation_x", variables),
        "y_axis": text(PACK, "results.correlation_y", variables),
        "outlier": maybe(0.6, text(PACK, "results.outlier", variables)),
    }, {}


def _results_trend(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "results.trend_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "results.trend_x", variables),
        "y_axis": text(PACK, "results.trend_y", variables),
        "shape": random_util.choice(("rising", "diminishing", "plateau", "exponential")),
        "line": variables["method"],
        "second_line": maybe(0.7, text(PACK, "results.baseline", variables)),
        "second_shape": random_util.choice(("flat", "falling", "dip", "rollercoaster")),
    }, {}


def _p_value(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "results.p_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "results.p_title", variables),
        "number": random_util.choice(words(PACK, "results.p_number")),
        "label": label,
        "source": maybe(0.8, text(PACK, "results.p_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


# THE LIMITATIONS, AND FUTURE WORK


def _limitations_iceberg(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    hidden = different(PACK, "limitations.hidden", variables, random_util.randint(2, 3))
    title, tip = text(PACK, "limitations.limitations_title", variables), text(PACK, "limitations.tip", variables)
    if not title or not tip or len(hidden) < 2:
        return None
    return {"title": title, "tip": tip, **_items("hidden", hidden)}, {}


def _limitations_statement(context: dict[str, Any]) -> Made | None:
    admission = text(PACK, "limitations.admission", _variables(context))
    return ({"text": admission}, {"background": _BACKDROP(context)}) if admission else None


def _future_timeline(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    steps = different(PACK, "future.future_step", variables, count - 1)
    punchline, title = text(PACK, "future.future_punchline", variables), text(PACK, "future.future_title", variables)
    if not title or not punchline or len(steps) < count - 1:
        return None
    known = words(PACK, "future.future_when")  # (soonest first)
    dates = [known[index] for index in sorted(random_util.sample(range(len(known)), count))]
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(dates, [*steps, punchline], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


def _future_cycle(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    steps = different(PACK, "future.cycle_step", variables, random_util.randint(3, 5))
    title = text(PACK, "future.cycle_title", variables)
    if not title or len(steps) < 3:
        return None
    return {"title": title, **_items("step", steps)}, {}


def _future_flowchart(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    texts = {
        "question": text(PACK, "future.flow_question", variables),
        "yes_step": text(PACK, "future.flow_yes", variables),
        "no_step": text(PACK, "future.flow_no", variables),
        "end": text(PACK, "future.flow_end", variables),
    }
    if not all(texts.values()):
        return None
    return {"title": maybe(0.6, text(PACK, "future.flow_title", variables)), **texts}, {}


# THE ACKNOWLEDGEMENTS, THE REFERENCES AND THE QUESTIONS


def _thanks(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    thanked = (text(PACK, "thanks.three_thanks", variables) or "").split("|")
    if len(thanked) != 3:
        return None
    texts = {"title": text(PACK, "thanks.thanks_title", variables), **_items("caption", [t.strip() for t in thanked])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_THANKED, context, 3), 1)}


def _thanks_list(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    thanked = different(PACK, "thanks.thanks_item", variables, random_util.randint(3, 5))
    title = text(PACK, "thanks.thanks_title", variables)
    if not title or len(thanked) < 3:
        return None
    return {"title": title, "items": " | ".join(thanked)}, {}


def _references(picture: Any, caption: str) -> Any:
    """Classic references, and four times in five a picture of one of them from the image source (when one can be
    found: a book's cover, or a paper's figure), with a caption of the rule that says which."""

    def references(context: dict[str, Any]) -> Made | None:
        variables = _variables(context)
        references = different(PACK, "references.reference", variables, random_util.randint(3, 5))
        title = text(PACK, "references.references_title", variables)
        if not title or len(references) < 3:
            return None
        texts: dict[str, str | None] = {"title": title, "items": " | ".join(references)}
        if random_util.random() >= _PICTURED:
            return texts, {}
        found = picture(context)
        if found is None:
            return texts, {}
        cited = {"number": str(random_util.randint(1, len(references))), "figure": str(random_util.randint(1, 9))}
        cited["page"] = str(random_util.randint(2, 400))
        return {**texts, "caption": text(PACK, caption, cited)}, {"figure": found}

    return references


_PICTURED: Final = 0.8  # of the references that show a picture of one of the works (when one can be found)


def _questions(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "questions.questions_title", variables)
    subtitle = maybe(0.8, text(PACK, "questions.questions_subtitle", variables))
    return ({"title": title, "subtitle": subtitle}, {}) if title else None


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
        name=f"{name} (Academic)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a conference talk's slide has it"
# (Free models wrote steps, events and references too long for their places, which cut them off: "Develop app for
# guided", "Brew et al. (2022). Journal of Caffeine and")
_FEW_WORDS = "in two to four words"
_P_VALUE = "with a suspicious p-value, just under 0.05"
_LIST = f"separated by |, each at most {AGENDA_ITEM} characters"


def _references_recipe(picture: ImageSlot, note: str, caption: str) -> Recipe:
    """The references' recipe, with a picture of one of the works four times in five (of the slot's look), whose
    caption says which."""
    return Recipe(
        "references",
        (picture,),
        brief="The references: three to five made-up works that the talk cites, in a citation style",
        hints={
            "title": _TITLE_HINT + ", such as 'References'",
            "items": "three to five short made-up references, each an author 'et al.', a year in brackets and a "
            f"journal of two or three words (no paper's title), {_LIST}",
            "caption": caption,
        },
        variants=(
            Variant(4, note=note),
            Variant(1, frozenset({"figure", "caption"}), "without a picture"),
        ),
    )


_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Academic)",
        llm=Recipe("title"),
    ),
    # The motivation (D69: the problem slide, four times in five)
    _part(
        "motivation",
        4,
        "problem",
        _motivation,
        ["problem_slide"],
        "Motivation",
        Recipe(
            "problem",
            (_BACKDROP, _PUZZLE),
            brief="The talk's motivation, right after the title, to hook the audience: the problem the research is "
            "about, as a conference talk states it, played straight however absurd",
            hints={
                "kicker": "a short heading over the problem, as a conference talk has it, such as 'Motivation' or "
                "'The problem'",
                "detail": "a short line under it, a few words, that makes it hit home, dryly: how often it happens, "
                "to whom, or what science doesn't know about it; it appears on a click",
            },
            variants=problem_variants(_ANGLES),
        ),
    ),
    _part(
        "motivation",
        1,
        "statement",
        _research_question,
        ["statement", "research_question"],
        "Research Question",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The talk's motivation, right after the title: its research question, big over a photo",
            hints={"text": "the research question about the concept, as one short question, in twelve words at most"},
            limits={"text": 100},
        ),
    ),
    _part(
        "outline",
        1,
        "agenda",
        _outline,
        ["agenda"],
        "Outline",
        Recipe(
            "agenda",
            brief="The talk's outline, as a conference talk has it: the parts it goes through, in order",
            hints={
                "title": _TITLE_HINT + ", such as 'Outline'",
                "items": f"three to five parts of the talk, in the order they come, {_LIST}",
            },
        ),
        repeats=3,
    ),
    # Related work
    _part(
        "related_work",
        1.2,
        "venn",
        _related_venn,
        ["venn_diagram"],
        "Related Work Venn",
        Recipe(
            "venn",
            brief="Related work, as a Venn diagram: two or three fields of research that seem to have nothing in "
            "common, and this work where they overlap, the punchline",
            hints={"title": _TITLE_HINT + ", such as 'Related work'", "overlap": "this work, the punchline"},
        ),
    ),
    _part(
        "related_work",
        1,
        "matrix",
        _related_matrix,
        ["matrix_diagram"],
        "Related Work Matrix",
        Recipe(
            "matrix",
            brief="Related work, as a 2×2 matrix: earlier work in three of its quadrants (made-up authors, as "
            "'et al.' with a year), and this work's method as the dot, alone in the last one",
            hints={
                "title": _TITLE_HINT + ", such as 'Related work'",
                "x_left": "the end of the axis along the bottom where earlier work is",
                "x_right": "its other end, the opposite, where this work is",
                "y_bottom": "the end of the axis going up where earlier work is",
                "y_top": "its other end, the opposite, where this work is",
                **{
                    corner: "an earlier work, as a made-up author 'et al.' and a year in brackets"
                    for corner in ("top_left", "bottom_left", "bottom_right")
                },
                "top_right": "the label of the quadrant where only this work is, such as the gap it fills",
                "dot": "this work's method, by its made-up name",
                "dot_quadrant": "top right",
            },
            variants=matrix_landscape(
                "an earlier work, as a made-up author 'et al.' and a year in brackets", "earlier work"
            ),
        ),
    ),
    _part(
        "related_work",
        0.8,
        "timeline",
        _related_timeline,
        ["timeline"],
        "Related Work Timeline",
        Recipe(
            "timeline",
            brief="Related work, as the field's made-up history: what earlier research found, oldest first, and this "
            "work last, the punchline",
            hints={"title": _TITLE_HINT + ", such as 'A brief history of the field'"},
        ),
    ),
    # The method
    _part(
        "method",
        1.5,
        "process",
        _method,
        ["process"],
        "Method",
        Recipe(
            "process",
            brief="The method, as a diagram of three to five steps, each leading to the next, the last one the "
            "punchline (a step that can't be right, say)",
            hints={
                "title": _TITLE_HINT + ", such as 'Method'",
                **{f"step_{index}": f"a step, {_FEW_WORDS}" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"step_4", "step_5"}), "in three steps"),
                Variant(1, frozenset({"step_5"}), "in three or four steps"),
                Variant(1, note="in three to five steps"),
            ),
        ),
    ),
    _part(
        "method",
        0.5,
        "statement",
        _equation,
        ["statement", "equation"],
        "Equation",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The method's key equation, big over a photo: one line in letters and symbols, with the concept in "
            "it, that sums up the method",
            hints={"text": "the equation, written out in plain characters (such as x² and ×), on one line"},
        ),
    ),
    _part(
        "method",
        1.3,
        "image",
        _setup,
        ["single_image"],
        "Experimental Setup",
        Recipe(
            "image",
            (_SETUP,),
            brief="The experimental setup, as one photo of an odd contraption, under a title",
            hints={"title": _TITLE_HINT + ", such as 'Experimental setup'"},
        ),
    ),
    # The results
    _part(
        "results",
        1.2,
        "chart_bars",
        _results_ranking,
        ["bar_chart", "chart"],
        "Results Ranking",
        Recipe(
            "chart_bars",
            brief="The results, as a bar chart of the methods compared: baselines and earlier methods, and this "
            "work's method last, winning by far",
            hints={
                "title": f"what the bars compare, {_P_VALUE}",
                "bars": "three to five baselines and earlier methods (only their names), separated by |, and this "
                "work's method's made-up name last",
                "value_axis": "the measure, with its unit",
            },
        ),
    ),
    _part(
        "results",
        1,
        "chart_correlation",
        _results_correlation,
        ["curve", "chart"],
        "Results Correlation",
        Recipe(
            "chart_correlation",
            brief="The results, as a scatter plot of a made-up correlation about the concept, with its r and its "
            "p-value in the title",
            hints={"title": f"the correlation found, as a claim, with its r and {_P_VALUE}"},
        ),
    ),
    _part(
        "results",
        0.8,
        "chart_trend",
        _results_trend,
        ["trend_chart", "chart"],
        "Results Over Time",
        Recipe(
            "chart_trend",
            brief="The results over time: this work's method as one line, and a baseline as a second line that "
            "appears on a click, as the punchline",
            hints={
                "title": f"the chart's claim, {_P_VALUE}",
                "line": "this work's method, by its made-up name",
                "second_line": "a baseline or an earlier method",
            },
        ),
    ),
    _part(
        "results",
        1,
        "big_number",
        _p_value,
        ["big_number"],
        "P-Value",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The result that matters, as one p-value: a big number just under the threshold, what it shows, "
            "and where in the paper it is",
            hints={
                "title": _TITLE_HINT + ", such as 'Main result'",
                "number": "the p-value, just under 0.05, such as 'p = 0.049'",
                "label": "what it shows, and what it took to get it, without the number itself",
                "source": "where in the paper it is, such as an appendix",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
    ),
    # The limitations
    _part(
        "limitations",
        1.3,
        "iceberg",
        _limitations_iceberg,
        ["iceberg"],
        "Limitations",
        Recipe(
            "iceberg",
            brief="The study's limitations, as an iceberg: the small one everyone sees, on its tip, and the ones "
            "under the water that sink the study",
            hints={"title": _TITLE_HINT + ", such as 'Limitations'"},
        ),
    ),
    _part(
        "limitations",
        0.6,
        "statement",
        _limitations_statement,
        ["statement"],
        "Limitations Statement",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The study's main limitation, admitted in one short sentence over a photo, as if it were minor",
            hints={"text": "the limitation, admitted as if it were minor, in ten words at most"},
            limits={"text": 80},  # (D63: shorter texts on an academic talk's slides)
        ),
    ),
    # Future work
    _part(
        "future_work",
        1,
        "timeline",
        _future_timeline,
        ["timeline"],
        "Future Work",
        Recipe(
            "timeline",
            brief="Future work, as a timeline of what comes next, soonest first, the last moment the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Future work'",
                **{f"event_{index}": f"what comes then, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "future_work",
        1,
        "cycle",
        _future_cycle,
        ["cycle"],
        "Research Cycle",
        Recipe(
            "cycle",
            brief="Future work, as the research cycle: three to five steps of academic life, each leading to the "
            "next, and the last back to the first",
            hints={
                "title": _TITLE_HINT + ", such as 'Future work'",
                **{f"step_{index}": f"a step, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "future_work",
        0.8,
        "flowchart",
        _future_flowchart,
        ["flowchart"],
        "Future Work Flowchart",
        Recipe(
            "flowchart",
            brief="Future work, as a flowchart that pretends to decide what comes next, whose every answer leads to "
            "more research",
        ),
    ),
    # The acknowledgements, the references and the questions
    _part(
        "acknowledgements",
        1,
        "three_columns",
        _thanks,
        ["three_captions"],
        "Acknowledgements",
        Recipe(
            "three_columns",
            (_THANKED, _THANKED, _THANKED),
            brief="The acknowledgements: three who made the work possible (made up, or a funder, a lab animal, a "
            "coffee machine), each a photo with a caption",
            hints={"title": _TITLE_HINT + ", such as 'Acknowledgements'"},
        ),
    ),
    _part(
        "acknowledgements",
        0.8,
        "agenda",
        _thanks_list,
        [],
        "Acknowledgements List",
        Recipe(
            "agenda",
            brief="The acknowledgements, as a list of who and what made the work possible (made up, never real people)",
            hints={
                "title": _TITLE_HINT + ", such as 'Acknowledgements'",
                "items": f"three to five who or what to thank, each in a few words, {_LIST}",
            },
        ),
        repeats=3,
    ),
    # (a picture of one of them, most of the time: the user found plain references boring, 2026-11-09, D65)
    _part(
        "references",
        1.2,
        "references",
        _references(_COVER, "references.cover_caption"),
        [],
        "References",
        _references_recipe(
            _COVER,
            "with the cover of one of the works, as if it were a book",
            "which work it's the cover of, by its number in the list, such as 'Cover of [2]'",
        ),
        repeats=3,
    ),
    _part(
        "references",
        0.8,
        "references",
        _references(_FIGURE, "references.figure_caption"),
        [],
        "References Figure",
        _references_recipe(
            _FIGURE,
            "with a figure from one of the works: a chart",
            "which work the figure is from, by its number in the list, such as '[3], Fig. 2'",
        ),
        repeats=3,
    ),
    _part(
        "questions",
        1,
        "questions",
        _questions,
        ["questions"],
        "Questions",
        Recipe(
            "questions",
            (cg.closing_picture_generator,),
            brief="The closing slide, inviting the audience's questions, as at a conference",
            hints={"subtitle": "a line under it, such as a plea to the audience"},
            variants=closing_variants("a line under it, such as a plea to the audience"),
        ),
        repeats=3,
    ),
]

# The format's other slides, for a long talk's free slides (and to stand in for a part's slide that none of the
# part's generators can make): real charts from the internet, quotes, fun facts, a quiz, a meme, and deep questions
# over photos, which a talk may have any number of (so that the free slides of a long one never run out of slides)
# (D63: memes, real charts from the internet, gifs and Reddit's weird pictures more often, and fewer slides of text, as
# the user found academic talks "pretty boring with mostly boring text"; and the talk's own provocations, a word over a
# full-screen picture: "Peer reviewed.")
_OTHERS: Final = {
    "Reddit Chart": 1.5,
    "Quote": 0.6,
    "Fun Fact": 0.8,
    "Quiz": 0.6,
    "Meme": 2.5,
    "Full Screen Pixabay Deep": 0.6,
    "Wikihow Bold Statement": 0.3,
    "Full Screen Gif": 0.8,
    "Two Captions Weird Reddit": 0.6,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Academic)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 1.5, _variables, "Academic", "as a researcher puts them on a slide, dryly"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag an academic talk may have (see presentation_schema.most_slides): each kind once, so that a
# part of more slides has more kinds (up to four charts, for the results and a real one), and the free slides' caps
# of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "chart": 4,
    "statement": 2,
    "single_image": 1,
    "three_captions": 1,
    "process": 1,
    "big_number": 1,
    "curve": 1,
    "provocation": 0.1,
}
