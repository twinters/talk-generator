"""The corporate all-hands, or quarterly business review (docs/v5-plan.md, section 7; D59): a company whose business
is the talk's topic, as its leadership presents the quarter to everyone.

Its arc goes from the agenda (or an executive summary nobody can read) through the KPIs against their targets (tiles,
the actual results falling away from the target's line, the results by region, one headline number, or the sales
pipeline as a funnel), the quarter's wins (three photos, the CEO's post, or customers' reviews), the roadmap (a
timeline, the new process, or the planning cycle), an org change (the new org chart, whose boss is the punchline, the
new hierarchy as a pyramid, or the company before and after), the synergies (a Venn diagram, or a 2×2 matrix of
priorities) to the ask of everyone (a bold statement, or a big number); its closer opens Q&A ("Questions?", and back to
work, D76), outside the talk's slides. A short all-hands keeps the KPIs, the wins and the roadmap; a quarter of a talk's
slides are free (D63), for memes, full-screen pictures, its own provocations ("Synergy.", over a full-screen picture),
inspirational quotes, InspiroBot's posters, the company's values as an acronym, news and the like, and its agenda comes
in talks of eleven slides or more; a long one gives the KPIs and the wins a second slide. The company's made-up name
comes from the topic (see talkgenerator.schema.formats.company), so that a classic all-hands' slides name the same
company as its title.

A management consultant presents an all-hands more often than the other personas, and a startup founder, a
motivational speaker and a life coach a little more often; its themes are the corporate families' more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import AGENDA_ITEM, Recipe, Variant, matrix_landscape, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    company,
    different,
    maybe,
    photos,
    provocation,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.sources import slide_texts
from talkgenerator.util import random_util

PACK: Final = "corporate"

# (D63: a quarter of its slides are free, for memes, pictures and the like, and its agenda, a list of text, waits for
# a talk of eleven slides or more: the user found all-hands decks too textual; D76: no Q&A among its slides, as its
# closer opens it, and the agenda still waits)
ARC: Final = Arc(
    (
        Part("agenda", rank=7, shortest=11),
        Part("kpis", 1, 2, rank=1),
        Part("wins", 1, 2, rank=2),
        Part("roadmap", rank=3),
        Part("org_change", rank=4),
        Part("synergies", rank=5),
        Part("ask", rank=6),
    ),
    free=0.25,
)

CORPORATE: Final = Format(
    brief="a company's all-hands meeting, or its quarterly business review, presented by its leadership to "
    "everyone: the agenda, the KPIs against their targets, the quarter's wins, the roadmap, an org change, the "
    "synergies and the ask of everyone. The topic is what the company does, however absurd, and every slide is "
    "an all-hands deck's, played straight",
    title_hint="like an all-hands' or a quarterly business review's title: the quarter, and a corporate slogan for it",
    job_hint="their position at the company, as its org chart says it, with the company's made-up name",
    # (×9, from ×6, since D79 brought the personas to 21: the consultant still presents about 30% of the all-hands)
    personas={
        "consultant": 9,
        "startup_founder": 1.5,
        "motivational_speaker": 1.5,
        "life_coach": 1.2,
        "it_support": 1.5,
    },
    themes={
        "spreadsheet": 3,
        "corporate": 5,
        "clip-art corporate": 2.5,
        "Swiss poster": 1.3,
        "clean keynote": 1.3,
        "kids": 0.4,
        "chalkboard": 0.5,
        "neon": 0.5,
        "hacker terminal": 0.6,
        "vintage paper": 0.6,
        "Comic Sans everywhere": 0.7,
    },
    arc=ARC,
    # (its closer opens Q&A, and sends everyone back to work: D76)
    closer=Closer(said("questions"), said("back_to_work"), presenter, mark=True),
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its company's name, the presenter and
    the title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["company"] = company(str(context.get("topic") or context["seed"]))
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE TITLE SLIDE: the quarter and its slogan, and who presents it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic all-hands' title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "company": company(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a calm backdrop behind a statement, office photos of the wins and of the company before its reorganisation
# (and an odd one of it after), and the photo the CEO posted
_BACKDROP = cg.statement_backdrop_generator
_WIN = ImageSlot(
    "an office photo of one of the quarter's wins",
    queries=("{}", "office celebration"),
    aesthetic="corporate-stock",
    backups=("photo",),
)
_BEFORE = ImageSlot(
    "an office photo of the company before its reorganisation", aesthetic="corporate-stock", backups=("photo",)
)
_AFTER = cg.weird_copyright_free_generator
_POST_PHOTO = ImageSlot("the photo the CEO posted", aesthetic="corporate-stock", backups=("photo",))


# THE AGENDA, OR AN EXECUTIVE SUMMARY


def _agenda(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    first, last = text(PACK, "agenda.agenda_first", variables), text(PACK, "agenda.agenda_last", variables)
    middle = different(PACK, "agenda.agenda_item", variables, random_util.randint(1, 3))
    title = text(PACK, "agenda.agenda_title", variables)
    if not title or not first or not last or not middle:
        return None
    return {"title": title, "items": " | ".join([first, *middle, last])}, {}


def _executive_summary(context: dict[str, Any]) -> Made | None:
    """A wall of jargon about the seed, of the TED pack's (its points are a consultant's already), under a title of an
    all-hands' own."""
    wall = slide_texts.generate_wall_of_text(context)
    title = text(PACK, "agenda.summary_title", _variables(context))
    if wall is None or not title:
        return None
    _, highlight, _, *points = wall
    written = [str(point) for point in points if point]
    if not highlight or not written:
        return None
    return {"title": title, "points": " | ".join(written), "highlight": str(highlight)}, {}


# THE KPIS AGAINST THEIR TARGETS: tiles, the actual results against the target, by region, one number, the pipeline


def _count() -> str:
    """A made-up count, as a dashboard writes it ("42", "1,337")."""
    return random_util.choice((str(random_util.randint(12, 99)), f"{random_util.randint(100, 9999):,}"))


def _dashboard(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.5 else 3
    target = text(PACK, "kpis.target_label", variables)
    counts = different(PACK, "kpis.count_label", variables, count - 2)
    punchline = text(PACK, "kpis.punchline_label", variables)
    title = text(PACK, "kpis.dashboard_title", variables)
    if not title or not target or not punchline or len(counts) < count - 2:
        return None
    figures = [
        (f"{random_util.randint(91, 119)}%", target),
        *((_count(), label) for label in counts),
        (random_util.choice(words(PACK, "kpis.punchline_number")), punchline),
    ]
    texts: dict[str, str | None] = {"title": title}
    for index, (number, label) in enumerate(figures, 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = number, label
    return texts, behind(context, KPI_PICTURES)


def _actual_vs_target(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "kpis.trend_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "kpis.trend_x", variables),
        "y_axis": text(PACK, "kpis.trend_y", variables),
        "shape": random_util.choice(("rising", "exponential", "hockey stick")),
        "line": text(PACK, "kpis.target_line", variables),
        "second_line": text(PACK, "kpis.actual_line", variables),
        "second_shape": random_util.choice(("flat", "falling", "dip", "rollercoaster", "crash", "peak")),
        "event": maybe(0.6, text(PACK, "kpis.trend_event", variables)),
    }, {}


def _by_region(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    regions = different(PACK, "kpis.region", variables, random_util.randint(3, 4))
    title, winner = text(PACK, "kpis.bars_title", variables), text(PACK, "kpis.winner", variables)
    if not title or not winner or len(regions) < 3:
        return None
    return {
        "title": title,
        "bars": " | ".join([*regions, winner]),
        "value_axis": maybe(0.8, text(PACK, "kpis.bars_axis", variables)),
    }, {}


def _headline_number(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    if random_util.random() < 0.5:  # (a share of a target, or a growth)
        number = f"{random_util.randint(87, 99)}.{random_util.randint(1, 9)}%"
        label = text(PACK, "kpis.share_label", variables)
    else:
        number = random_util.choice(
            (f"+{random_util.randint(1, 3)}.{random_util.randint(1, 9)}%", f"-{random_util.randint(1, 9)}%", "+0.1%")
        )
        label = text(PACK, "kpis.growth_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "kpis.number_title", variables),
        "number": number,
        "label": label,
        "source": maybe(0.8, text(PACK, "kpis.number_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _pipeline(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    top, bottom = text(PACK, "kpis.funnel_top", variables), text(PACK, "kpis.funnel_bottom", variables)
    middle = different(PACK, "kpis.funnel_stage", variables, count - 2)
    title = text(PACK, "kpis.funnel_title", variables)
    if not title or not top or not bottom or len(middle) < count - 2:
        return None
    # (each stage a number and what they did, fewer and fewer of them, down to the deals at the bottom)
    numbers = [random_util.randint(8000, 60000)]
    for _ in middle:
        numbers.append(max(2, numbers[-1] // random_util.randint(4, 12)))
    stages = [f"{number:,} {stage}" for number, stage in zip(numbers, [top, *middle], strict=True)] + [bottom]
    return {"title": title, **_items("stage", stages)}, {}


# THE QUARTER'S WINS: three photos, the CEO's post, or customers' reviews


def _three_wins(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    wins = different(PACK, "wins.win", variables, 2)
    punchline = text(PACK, "wins.win_punchline", variables)
    if len(wins) < 2 or not punchline:
        return None
    texts = {"title": text(PACK, "wins.wins_title", variables), **_items("caption", [*wins, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_WIN, context, 3), 1)}


def _handle(author: str, name: str) -> str:
    first = "".join(letter for letter in author.split()[0].lower() if letter.isalpha()) if author.split() else "ceo"
    firm = "".join(letter for letter in name.lower() if letter.isalnum())[:12]
    return random_util.choice((f"{first}_{firm}", f"{first}.ceo", f"{firm}_{first}"))[:24]


def _ceo_post(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "wins.post", variables)
    author = cg.full_name_generator({})
    if not post or not author:
        return None
    photo = _POST_PHOTO(context) if random_util.random() < 0.6 else None
    texts = {
        "title": maybe(0.7, text(PACK, "wins.post_title", variables)),
        "author": str(author),
        "handle": _handle(str(author), variables["company"]),
        "text": post,
    }
    return texts, {"photo": photo}


def _reviews(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 3 if random_util.random() < 0.6 else 2
    good = different(PACK, "wins.review_good", variables, count - 1)
    bad = text(PACK, "wins.review_bad", variables)
    reviewers = different(PACK, "wins.reviewer", variables, count)
    if len(good) < count - 1 or not bad or len(reviewers) < count:
        return None
    stars = [random_util.choice(("5", "5", "4")) for _ in good] + ["1"]
    texts: dict[str, str | None] = {"title": maybe(0.8, text(PACK, "wins.reviews_title", variables))}
    for index, (rating, review, reviewer) in enumerate(zip(stars, [*good, bad], reviewers, strict=True), 1):
        texts[f"stars_{index}"], texts[f"review_{index}"], texts[f"reviewer_{index}"] = rating, review, reviewer
    return texts, {}


# THE ROADMAP: a timeline, the new process, or the planning cycle


def _roadmap(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    milestones = different(PACK, "roadmap.milestone", variables, count - 1)
    punchline = text(PACK, "roadmap.roadmap_punchline", variables)
    title = text(PACK, "roadmap.roadmap_title", variables)
    if not title or not punchline or len(milestones) < count - 1:
        return None
    known = words(PACK, "roadmap.when")  # (soonest first)
    dates = [known[index] for index in sorted(random_util.sample(range(len(known)), count))]
    texts: dict[str, str | None] = {"title": title}
    for index, (date, event) in enumerate(zip(dates, [*milestones, punchline], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = date, event
    return texts, {}


def _new_process(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "roadmap.process_first", variables), text(PACK, "roadmap.process_last", variables)
    middle = different(PACK, "roadmap.process_step", variables, count - 2)
    title = text(PACK, "roadmap.process_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    return {"title": title, **_items("step", [first, *middle, last])}, {}


def _planning_cycle(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    steps = different(PACK, "roadmap.cycle_step", variables, random_util.randint(3, 5))
    title = text(PACK, "roadmap.cycle_title", variables)
    if not title or len(steps) < 3:
        return None
    return {"title": title, **_items("step", steps)}, {}


# THE ORG CHANGE: the new org chart, the new hierarchy, or the company before and after


def _new_structure(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    teams = different(PACK, "org.team", variables, random_util.randint(2, 4))
    title, boss = text(PACK, "org.org_title", variables), text(PACK, "org.boss", variables)
    if not title or not boss or len(teams) < 2:
        return None
    return {"title": title, "boss": boss, **_items("report", teams)}, {}


def _hierarchy(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    rules = ["org.pyramid_top", "org.pyramid_upper", "org.pyramid_middle", "org.pyramid_base"]
    if random_util.random() < 0.4:
        rules.remove("org.pyramid_middle")
    levels = [text(PACK, rule, variables) for rule in rules]
    title = text(PACK, "org.pyramid_title", variables)
    if not title or not all(levels):
        return None
    return {"title": title, **_items("level", [str(level) for level in levels])}, {}


def _before_and_after(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    captions = (text(PACK, "org.before_after", variables) or "").split("|")
    if len(captions) != 2:
        return None
    title = maybe(0.7, text(PACK, "org.before_after_title", variables))
    texts = {"title": title, "caption_1": captions[0].strip(), "caption_2": captions[1].strip()}
    before = _BEFORE(context)
    return texts, {"image_1": before, "image_2": photos(_AFTER, context, 1, avoid=[before])[0]}


# THE SYNERGIES: a Venn diagram, or a 2×2 matrix of priorities


def _synergies(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    circles = different(PACK, "synergies.circle", variables, 3 if random_util.random() < 0.4 else 2)
    title, overlap = text(PACK, "synergies.venn_title", variables), text(PACK, "synergies.overlap", variables)
    if not title or not overlap or len(circles) < 2:
        return None
    return {"title": title, **_items("circle", circles), "overlap": overlap}, {}


def _priorities(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    axes = different(PACK, "synergies.axis", variables, 2)
    initiatives = different(PACK, "synergies.initiative", variables, 3)
    title, best = text(PACK, "synergies.matrix_title", variables), text(PACK, "synergies.best_quadrant", variables)
    dot = text(PACK, "synergies.dot", variables)
    if not title or not best or not dot or len(axes) < 2 or len(initiatives) < 3:
        return None
    (x_left, x_right), (y_bottom, y_top) = (axis.split("|") for axis in axes)
    return {
        "title": title,
        "x_left": x_left.strip(),
        "x_right": x_right.strip(),
        "y_bottom": y_bottom.strip(),
        "y_top": y_top.strip(),
        "top_left": initiatives[0],
        "bottom_left": initiatives[1],
        "bottom_right": initiatives[2],
        "top_right": best,
        "dot": dot,
        "dot_quadrant": "top right",
    }, {}


# THE ASK


def _ask_statement(context: dict[str, Any]) -> Made | None:
    statement = text(PACK, "ask.ask_statement", _variables(context))
    return ({"text": statement}, {"background": _BACKDROP(context)}) if statement else None


def _ask_number(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "ask.ask_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "ask.ask_title", variables),
        "number": random_util.choice(words(PACK, "ask.ask_number")),
        "label": label,
        "source": maybe(0.8, text(PACK, "ask.ask_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


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
        name=f"{name} (Corporate)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as an all-hands deck's slide has it"
_FEW_WORDS = "in two to four words"
# (Free models repeated the number in a label, and wrote big numbers without their units: see the pitch's)
_LABEL = "what the number measures, without the number itself"
_NUMBER = "the number as people read it, with its unit, such as '97%' or '+0.3%'"
_LIST = f"separated by |, each at most {AGENDA_ITEM} characters"
_TEAM = "a team or a role, in a few words (without a person's name)"
# (A free model added its quadrant's ends in brackets: "Arctic Expansion (High Impact, Low Urgency)")
_INITIATIVE = "an initiative of the company, by its made-up name alone"
# (A free model wrote one title at both ends of an axis, and quadrants that restated the axes: see the pitch's)
_ENDS = {
    "x_left": "the bad end of the axis along the bottom",
    "x_right": "its good end, the opposite of the bad one",
    "y_bottom": "the bad end of the axis going up",
    "y_top": "its good end, the opposite of the bad one",
}

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Corporate)",
        llm=Recipe("title"),
    ),
    # The agenda, or an executive summary
    _part(
        "agenda",
        1.4,
        "agenda",
        _agenda,
        ["agenda"],
        "Agenda",
        Recipe(
            "agenda",
            brief="The all-hands' agenda: the parts it goes through, in order, from a welcome to Q&A",
            hints={
                "title": _TITLE_HINT + ", such as 'Agenda'",
                "items": f"three to five parts of the all-hands, in the order they come, {_LIST}",
            },
        ),
        repeats=3,
    ),
    _part(
        "agenda",
        0.5,
        "wall_of_text",
        _executive_summary,
        ["wall_of_text"],
        "Executive Summary",
        Recipe(
            "wall_of_text",
            brief="The quarter's executive summary, as a wall of text that nobody can read: dense points of corporate "
            "jargon about the company's business, and one absurd point hidden among them, the punchline",
            hints={"title": _TITLE_HINT + ", such as 'Executive summary'"},
        ),
        repeats=3,
    ),
    # The KPIs against their targets
    _part(
        "kpis",
        1.5,
        "kpi",
        _dashboard,
        ["kpi"],
        "KPI Dashboard",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The KPIs against their targets, as figures on tiles: each a number and what it measures, the first "
            "a share of its target, the last one the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'KPIs against target'",
                **{f"number_{index}": _NUMBER for index in range(1, 5)},
                **{f"label_{index}": _LABEL for index in range(1, 5)},
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
    _part(
        "kpis",
        1.2,
        "chart_trend",
        _actual_vs_target,
        ["trend_chart", "chart"],
        "Actual vs Target",
        Recipe(
            "chart_trend",
            brief="The quarter's results against their target: the target as one line that climbs, and the actual "
            "results as a second line, which appears on a click, as the punchline",
            hints={
                "title": "the chart's claim, as a business review puts it",
                "shape": "how the target goes: rising, exponential or hockey stick",
                "line": "the target's name in the legend, such as 'Target'",
                "second_line": "the actual results' name in the legend, such as 'Actual'",
                "second_shape": "how the actual results go: flat, falling, dip, rollercoaster, crash or peak",
                "event": "a moment on the target's line, where it takes off, such as a board meeting",
            },
        ),
    ),
    _part(
        "kpis",
        1,
        "chart_bars",
        _by_region,
        ["bar_chart", "chart"],
        "Results by Region",
        Recipe(
            "chart_bars",
            brief="The results by region or team, as a ranking in bars: the company's regions and teams, and the last "
            "bar, the punchline, which wins by far",
            hints={
                "title": "what the ranking compares, as a business review's chart has it",
                # (A free model named its last bar "Emperor Elite (Punchline)")
                "bars": "three to five regions or teams (only their names), separated by |, and last an unlikely "
                "team that wins by far",
                "value_axis": "the measure, such as '% of target'",
            },
        ),
    ),
    _part(
        "kpis",
        0.9,
        "big_number",
        _headline_number,
        ["big_number"],
        "Headline Number",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The quarter in one number: a share of its target just short of it, or a growth that's "
            "suspiciously small, presented as a triumph",
            hints={
                "title": _TITLE_HINT + ", such as 'The quarter in one number'",
                "number": _NUMBER,
                "label": _LABEL,
                "source": "a made-up, unreliable source, such as a preliminary report",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
    ),
    _part(
        "kpis",
        0.9,
        "funnel",
        _pipeline,
        ["funnel"],
        "Sales Pipeline",
        Recipe(
            "funnel",
            brief="The sales pipeline, as a funnel: the many leads at its top, each stage a number and what they did, "
            "down to the deals at the bottom, the punchline (one deal, say, and with whom)",
            hints={
                "title": _TITLE_HINT + ", such as 'Our pipeline'",
                "stage_1": "the leads at the top: a number and who they are",
                **{f"stage_{index}": "a number and what they did" for index in range(2, 5)},
                "stage_5": "the deals at the bottom: a number and who with, the punchline",
            },
            variants=(
                Variant(1, frozenset({"stage_4", "stage_5"}), "in three stages, the third the punchline"),
                Variant(1, frozenset({"stage_5"}), "in four stages, the fourth the punchline"),
                Variant(1, note="in five stages"),
            ),
        ),
    ),
    # The quarter's wins
    _part(
        "wins",
        1.6,
        "three_columns",
        _three_wins,
        ["three_captions"],
        "Wins of the Quarter",
        Recipe(
            "three_columns",
            (_WIN, _WIN, _WIN),
            brief="The quarter's wins, celebrated: three photos, each captioned with a win, the last one the "
            "punchline (a win that isn't one)",
            hints={
                "title": _TITLE_HINT + ", such as 'Wins of the quarter'",
                "caption_1": f"a win, {_FEW_WORDS}",
                "caption_2": f"another win, {_FEW_WORDS}",
                "caption_3": f"the last win, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "wins",
        1,
        "social_post",
        _ceo_post,
        ["social_post"],
        "CEO's Post",
        Recipe(
            "social_post",
            (_POST_PHOTO,),
            # (With "humbled, grateful" in it, the free models' posts all began "Humbled and grateful")
            brief="The CEO's post about the quarter, as leaders post on a business network: a lesson drawn from "
            "something trivial, or pride in the wrong thing",
            hints={
                "title": "a title such as 'From our CEO', or empty for none",
                "author": "the CEO's made-up name (never a real person)",
            },
        ),
        repeats=1,
    ),
    _part(
        "wins",
        0.9,
        "reviews",
        _reviews,
        ["reviews"],
        "Customer Reviews",
        Recipe(
            "reviews",
            brief="What customers said this quarter, as reviews with stars: glowing ones, and the last one, the "
            "punchline, a one-star review",
            hints={"title": "a title such as 'Voice of the customer', or empty for none"},
        ),
    ),
    # The roadmap
    _part(
        "roadmap",
        1.3,
        "timeline",
        _roadmap,
        ["timeline"],
        "Roadmap",
        Recipe(
            "timeline",
            brief="The roadmap: what the company will do when, soonest first, the last moment the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Roadmap'",
                **{f"date_{index}": "a quarter or a year, such as 'Q3' or 'FY27'" for index in range(1, 6)},
                **{f"event_{index}": f"what the company does then, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "roadmap",
        1,
        "process",
        _new_process,
        ["process"],
        "New Process",
        Recipe(
            "process",
            brief="How the company works from now on, as a process, step by step, the last one the punchline (a step "
            "that undoes the others, say)",
            hints={
                "title": _TITLE_HINT + ", such as 'Our new process'",
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
        "roadmap",
        0.7,
        "cycle",
        _planning_cycle,
        ["cycle"],
        "Planning Cycle",
        Recipe(
            "cycle",
            brief="The planning cycle: three to five steps of how the company plans, each leading to the next, and the "
            "last back to the first",
            hints={
                "title": _TITLE_HINT + ", such as 'Our planning cycle'",
                **{f"step_{index}": f"a step, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    # The org change
    _part(
        "org_change",
        1.4,
        "org_chart",
        _new_structure,
        ["org_chart"],
        "New Structure",
        Recipe(
            "org_chart",
            brief="The org change, as the new org chart: the teams and roles, under who's in charge now, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Our new structure'",
                "boss": "who's in charge now, in a few words: the punchline",
                **{f"report_{index}": _TEAM for index in range(1, 5)},
            },
        ),
    ),
    _part(
        "org_change",
        0.9,
        "pyramid",
        _hierarchy,
        ["pyramid"],
        "New Hierarchy",
        Recipe(
            "pyramid",
            brief="The new hierarchy, as a pyramid: everyone at its base, the levels above them, and who's at the top, "
            "the punchline",
            hints={"title": _TITLE_HINT + ", such as 'The new hierarchy'"},
        ),
    ),
    _part(
        "org_change",
        1.2,
        "two_columns",
        _before_and_after,
        ["two_captions"],
        "Before and After the Reorganisation",
        Recipe(
            "two_columns",
            (_BEFORE, _AFTER),
            brief="The company before its reorganisation and after it, as two captioned photos: how little changed",
            hints={"caption_1": "the company before, in a few words", "caption_2": "the company after"},
        ),
    ),
    # The synergies
    _part(
        "synergies",
        1.4,
        "venn",
        _synergies,
        ["venn_diagram"],
        "Synergies",
        Recipe(
            "venn",
            brief="The synergies, as a Venn diagram: two or three parts of the company (or things it does, or a "
            "company it bought) that seem to have nothing in common, and the synergy where they overlap, the punchline",
            hints={"title": _TITLE_HINT + ", such as 'Synergies'", "overlap": "the synergy, the punchline"},
        ),
    ),
    _part(
        "synergies",
        1,
        "matrix",
        _priorities,
        ["matrix_diagram"],
        "Priority Matrix",
        Recipe(
            "matrix",
            brief="The strategic priorities, as a 2×2 matrix: the company's initiatives in three of its quadrants, and "
            "its initiative about the topic as the dot, alone in the best one",
            hints={
                "title": _TITLE_HINT + ", such as 'Strategic priorities'",
                **_ENDS,
                **{corner: _INITIATIVE for corner in ("top_left", "bottom_left", "bottom_right")},
                "top_right": "the label of the quadrant that's best on both axes, such as 'Quick wins'",
                "dot": "the initiative about the topic, by its made-up name",
                "dot_quadrant": "top right, the quadrant that's best on both axes",
            },
            variants=matrix_landscape(_INITIATIVE, "the company's initiatives"),
        ),
    ),
    # The ask
    # (The ask's kinds have no tags of their kinds: the free slides' quotes, earlier in a long talk, take the
    # statements' cap, and the KPIs' headline number the big numbers', as an academic talk's references keep clear of
    # its outline's agenda)
    _part(
        "ask",
        1.2,
        "statement",
        _ask_statement,
        [],
        "The Ask",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The ask: what leadership needs from everyone, as one bold sentence over a photo, impossible and "
            "cheerful",
            hints={"text": "the ask, as one bold sentence, said to everyone"},
        ),
    ),
    _part(
        "ask",
        1,
        "big_number",
        _ask_number,
        [],
        "The Ask in Numbers",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The ask, as one big number: how much more leadership needs from everyone, and of what",
            hints={
                "title": _TITLE_HINT + ", such as 'Our ask'",
                "number": "the number as people read it, with its unit, such as '110%'",
                "label": "what it is of, and from whom, without the number itself",
                "source": "the small print, such as when it starts",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
]

# The format's other slides, for a long all-hands' free slides (and to stand in for a part's slide that none of the
# part's generators can make): inspirational quotes and posters, the company's values as an acronym, news, an
# alignment chart, a tier list, a meme, a fun fact, a fake error message, and full-screen photos, which a talk may
# have any number of (so that the free slides of a long one, without fair use too, never run out of slides)
# (D63: memes, full-screen pictures and Reddit's weird pictures more often, and fewer slides of text, as the user found
# all-hands decks too textual; and the all-hands' own provocations, a word over a full-screen picture: "Synergy.")
_OTHERS: Final = {
    "Quote": 0.6,
    "Acronym": 0.8,
    "Inspirobot": 0.8,
    "News Headline": 0.8,
    "Meme": 2,
    "Two Captions Weird Reddit": 0.6,
    "Alignment Chart": 0.6,
    "Full Screen Pixabay Quote": 0.6,
    "Tier List": 0.5,
    "Fun Fact": 0.5,
    "Full Screen Neutral Images": 0.8,
    "Error Message": 0.4,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(
        slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Corporate)")
        for name, weight in _OTHERS.items()
    ),
    provocation(PACK, ARC, 1.5, _variables, "Corporate", "in corporate jargon, as leadership says them"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag an all-hands may have (see presentation_schema.most_slides): each kind once, so that a part
# of two slides has two kinds (up to two charts, for the KPIs), and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "chart": 2,
    "statement": 2,
    "two_captions": 1,
    "three_captions": 1,
    "process": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
