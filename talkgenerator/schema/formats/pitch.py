"""The startup pitch (docs/v5-plan.md, section 7; D56): a startup about the talk's topic, pitched to investors as at a
demo day.

Its arc goes from the problem (a problem slide in three pitches in four, its why: D69) to the solution, the market
(TAM, SAM and SOM, as a funnel), the business model, the traction (a hockey stick), the competition (a 2×2 matrix with
the startup alone in its best corner), the team and the roadmap to the ask (a big number) and the closing
"Questions?". A short pitch keeps the problem, the solution, the traction and the ask; a quarter of a pitch's
slides are free (D63), for memes, gifs, Reddit's weird pictures, its own provocations ("Disrupt.", over a full-screen
picture), press and the like, and its market and business model come in pitches of eleven slides or more; a long one
gives the problem, the solution and the traction a second slide. The startup's made-up name comes from the topic (see
talkgenerator.schema.formats.startup), so that a classic pitch's slides name the same startup as its title.

A startup founder presents a pitch more often than the other personas, and a consultant, an influencer and a
motivational speaker a little more often; its themes are the startup family's more often.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import Recipe, Variant, closing_variants, matrix_landscape, pictured, problem_variants
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    KPI_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    different,
    maybe,
    photos,
    problem,
    provocation,
    startup,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.util import random_util

PACK: Final = "pitch"

# (D63: a quarter of its slides are free, for memes, gifs and pictures, and its market and business model, figures
# on shapes, wait for a talk of eleven slides or more: a ten-slide pitch had all its slides in its parts, too many of
# them text)
ARC: Final = Arc(
    (
        Part("problem", 1, 2, rank=1),
        Part("solution", 1, 2, rank=2),
        Part("market", rank=7),
        Part("business_model", rank=8),
        Part("traction", 1, 2, rank=3),
        Part("competition", rank=4),
        Part("team", rank=6),
        Part("roadmap", rank=9),
        Part("ask", rank=0),
        Part("closing", rank=5),
    ),
    free=0.25,
)

PITCH: Final = Format(
    brief="a startup pitch to investors, as at a demo day: the problem, the solution, the market (TAM, SAM and SOM), "
    "the business model, the traction, the competition, the team and the ask. The topic is what the startup does, "
    "however absurd, and every slide is a pitch deck's, played straight",
    title_hint="like a startup pitch's title: the startup's made-up name and its one-line promise",
    job_hint="their role at the startup they pitch, with the startup's made-up name",
    personas={"startup_founder": 6, "consultant": 2, "influencer": 1.5, "motivational_speaker": 1.5},
    themes={
        "startup": 4,
        "clean keynote": 1.6,
        "Swiss poster": 1.4,
        "dark minimal": 1.4,
        "corporate": 1.3,
        "vintage paper": 0.5,
        "chalkboard": 0.5,
        "academic": 0.5,
        "kids": 0.6,
    },
    arc=ARC,
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its startup's name, the presenter and
    the title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["startup"] = startup(str(context.get("topic") or context["seed"]))
    return variables


# THE TITLE SLIDE: the startup's name and its promise, and who pitches it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic pitch's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "startup": startup(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a calm backdrop behind a statement, the product, life before and after it, and the team's people
_BACKDROP = cg.statement_backdrop_generator
# (D69: the problem slide's picture beside the problem, which shows it as it happens; generated, in a talk that
# generates pictures)
_PAIN = ImageSlot(
    "a picture that shows the problem the startup solves, as it happens", aesthetic="weird-stock", generate=True
)
# (D63: the main product slide's picture shows off an absurd invention: searched as a gadget, an invention or a
# machine, and in a talk that generates pictures, drawn from the model's prompt as an advertisement's product shot)
_PRODUCT = ImageSlot(
    "the startup's product, an absurd invention, shown off as an advertisement would",
    aesthetic="product-shot",
    generate=True,
)
_BEFORE = cg.copyright_free_generator
_AFTER = cg.weird_copyright_free_generator
_PERSON = ImageSlot(
    "a photo of someone on the startup's team", queries=("{}", "business portrait"), aesthetic="portrait"
)
_POST_PHOTO = cg.copyright_free_generator


def _figure(kind: str) -> str:
    """A made-up number: a percentage, a count or a ratio ("1 in 7")."""
    if kind == "percent":
        return random_util.choice((f"{random_util.randint(51, 97)}%", f"{random_util.randint(3, 49)}%", "110%"))
    if kind == "ratio":
        return f"1 in {random_util.choice((3, 4, 5, 7, 8, 10))}"
    return random_util.choice(
        (f"{random_util.randint(2, 9)}.{random_util.randint(1, 9)} million", f"{random_util.randint(2, 12)} billion")
    )


# THE PROBLEM: the problem slide most of the time (D69), a bold statement over a photo, or an alarming number


# (a pain: everyday and real ones a little more often than the other angles)
_ANGLES: Final = {"everyday": 1.3, "real": 1.2}
_PROBLEMS: Final = {
    "kicker": "problem.kicker",
    "weird": "problem.weird",
    "everyday": "problem.everyday",
    "crossed": "problem.crossed",
    "typical": "problem.typical",
    "real": "problem.real",
}


def _problem(context: dict[str, Any]) -> Made | None:
    return problem(PACK, _PROBLEMS, _variables(context), context, (_BACKDROP, _PAIN), _ANGLES)


def _problem_statement(context: dict[str, Any]) -> Made | None:
    statement = text(PACK, "problem.problem_statement", _variables(context))
    return ({"text": statement}, {"background": _BACKDROP(context)}) if statement else None


def _problem_number(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    kind = random_util.choice(("percent", "percent", "count", "ratio"))
    label = text(PACK, "problem.problem_share" if kind == "percent" else "problem.problem_people", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "problem.problem_title", variables),
        "number": _figure(kind),
        "label": label,
        "source": maybe(0.7, text(PACK, "problem.problem_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


# THE SOLUTION


def _solution(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "solution.solution_title", _variables(context))
    return ({"title": title}, {"image": _PRODUCT(context)}) if title else None


def _before_and_after(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    captions = (text(PACK, "solution.before_after", variables) or "").split("|")
    if len(captions) != 2:
        return None
    title = maybe(0.6, text(PACK, "solution.before_after_title", variables))
    texts = {"title": title, "caption_1": captions[0].strip(), "caption_2": captions[1].strip()}
    before = _BEFORE(context)
    return texts, {"image_1": before, "image_2": photos(_AFTER, context, 1, avoid=[before])[0]}


def _how_it_works(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first = text(PACK, "solution.how_first", variables)
    middle = different(PACK, "solution.how_step", variables, count - 2)
    last = text(PACK, "solution.how_last", variables)
    title = text(PACK, "solution.how_title", variables)
    if not first or not last or not title or len(middle) < count - 2:
        return None
    steps = [first, *middle, last]
    return {"title": title, **{f"step_{index}": step for index, step in enumerate(steps, 1)}}, {}


# THE MARKET: TAM, SAM and SOM, in a funnel, or one big number


def _market_funnel(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    stages = [text(PACK, rule, variables) for rule in ("market.tam", "market.sam", "market.som")]
    title = text(PACK, "market.market_title", variables)
    if not title or not all(stages):
        return None
    return {"title": title, **{f"stage_{index}": stage for index, stage in enumerate(stages, 1)}}, {}


def _market_number(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "market.market_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "market.market_number_title", variables),
        "number": random_util.choice(words(PACK, "market.market_amount")),
        "label": label,
        "source": maybe(0.8, text(PACK, "market.market_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


# THE BUSINESS MODEL: pricing tiers, a flywheel, or where the money comes from


def _pricing(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    tiers = [
        (random_util.choice(words(PACK, "business.free_price")), text(PACK, "business.tier_basic", variables)),
        (random_util.choice(words(PACK, "business.paid_price")), text(PACK, "business.tier_pro", variables)),
    ]
    if random_util.random() < 0.5:
        tiers.append(
            (random_util.choice(words(PACK, "business.high_price")), text(PACK, "business.tier_team", variables))
        )
    tiers.append(
        (random_util.choice(words(PACK, "business.odd_price")), text(PACK, "business.tier_punchline", variables))
    )
    title = text(PACK, "business.model_title", variables)
    if not title or not all(label for _, label in tiers):
        return None
    texts: dict[str, str | None] = {"title": title}
    for index, (price, label) in enumerate(tiers, 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = price, label
    return texts, behind(context, KPI_PICTURES)


def _flywheel(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    steps = different(PACK, "business.flywheel_step", variables, random_util.randint(3, 5))
    title = text(PACK, "business.flywheel_title", variables)
    if not title or len(steps) < 3:
        return None
    return {"title": title, **{f"step_{index}": step for index, step in enumerate(steps, 1)}}, {}


def _revenue(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    streams = different(PACK, "business.revenue_stream", variables, random_util.randint(3, 4))
    question = text(PACK, "business.revenue_question", variables)
    if not question or len(streams) < 3:
        return None
    return {"question": question, "categories": " | ".join(streams)}, {}


# THE TRACTION: a hockey stick, KPI tiles, or a happy customer's post


def _hockey_stick(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "traction.traction_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "traction.traction_x", variables),
        "y_axis": text(PACK, "traction.traction_y", variables),
        "shape": random_util.choice(("hockey stick", "hockey stick", "exponential")),
        "line": variables["startup"],
        "event": maybe(0.7, text(PACK, "traction.traction_event", variables)),
    }, {}


def _traction_kpis(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = 4 if random_util.random() < 0.4 else 3
    shares = different(PACK, "traction.kpi_share", variables, 1)
    counts = different(PACK, "traction.kpi_count", variables, count - 2)
    punchline = text(PACK, "traction.kpi_punchline", variables)
    title = text(PACK, "traction.kpi_title", variables)
    if not title or not punchline or len(shares) < 1 or len(counts) < count - 2:
        return None
    figures = [
        (f"+{random_util.randint(40, 900)}%", shares[0]),
        *(
            (random_util.choice((f"{random_util.randint(2, 99):,}", f"{random_util.randint(1000, 99999):,}")), label)
            for label in counts
        ),
        (random_util.choice(words(PACK, "traction.kpi_punchline_number")), punchline),
    ]
    texts: dict[str, str | None] = {"title": title}
    for index, (number, label) in enumerate(figures, 1):
        texts[f"number_{index}"], texts[f"label_{index}"] = number, label
    return texts, behind(context, KPI_PICTURES)


def _handle(author: str, name: str) -> str:
    first = "".join(letter for letter in author.split()[0].lower() if letter.isalpha()) if author.split() else "fan"
    company = "".join(letter for letter in name.lower() if letter.isalnum())[:12]
    return random_util.choice((f"{first}_{company}", f"{company}fan{random_util.randint(2, 99)}", f"real{first}"))[:24]


def _testimonial(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "traction.testimonial", variables)
    author = cg.full_name_generator({})
    if not post or not author:
        return None
    photo = _POST_PHOTO(context) if random_util.random() < 0.6 else None
    texts = {
        "title": maybe(0.5, text(PACK, "traction.testimonial_title", variables)),
        "author": str(author),
        "handle": _handle(str(author), variables["startup"]),
        "text": post,
    }
    return texts, {"photo": photo}


# THE COMPETITION: a 2×2 matrix with the startup alone in its best corner, or a ranking it wins


def _matrix(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    axes = different(PACK, "competition.axis", variables, 2)
    competitors = different(PACK, "competition.competitor", variables, 3)
    title, best = text(PACK, "competition.matrix_title", variables), text(PACK, "competition.best_quadrant", variables)
    if not title or not best or len(axes) < 2 or len(competitors) < 3:
        return None
    (x_left, x_right), (y_bottom, y_top) = (axis.split("|") for axis in axes)
    return {
        "title": title,
        "x_left": x_left.strip(),
        "x_right": x_right.strip(),
        "y_bottom": y_bottom.strip(),
        "y_top": y_top.strip(),
        "top_left": competitors[0],
        "bottom_left": competitors[1],
        "bottom_right": competitors[2],
        "top_right": best,
        "dot": variables["startup"],
        "dot_quadrant": "top right",
    }, {}


def _ranking(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    competitors = different(PACK, "competition.competitor", variables, random_util.randint(3, 4))
    title = text(PACK, "competition.ranking_title", variables)
    if not title or len(competitors) < 3:
        return None
    return {
        "title": title,
        "bars": " | ".join([*competitors, variables["startup"]]),
        "value_axis": maybe(0.8, text(PACK, "competition.ranking_axis", variables)),
    }, {}


# THE TEAM: three people's photos with their roles, or an org chart whose boss is the punchline


def _team(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    roles = (text(PACK, "team.team_roles", variables) or "").split("|")
    if len(roles) != 3:
        return None
    texts = {"title": text(PACK, "team.team_title", variables)}
    texts.update({f"caption_{index}": role.strip() for index, role in enumerate(roles, 1)})
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_PERSON, context, 3), 1)}


def _org_chart(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    members = different(PACK, "team.member", variables, random_util.randint(2, 4))
    title, boss = text(PACK, "team.org_title", variables), text(PACK, "team.boss", variables)
    if not title or not boss or len(members) < 2:
        return None
    return {"title": title, "boss": boss, **{f"report_{index}": member for index, member in enumerate(members, 1)}}, {}


# THE ROADMAP, THE ASK AND THE CLOSING


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


def _ask(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "ask.ask_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "ask.ask_title", variables),
        "number": random_util.choice(words(PACK, "ask.amount")),
        "label": label,
        "source": maybe(0.8, text(PACK, "ask.ask_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _closing(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "closing.closing_title", variables)
    return (
        ({"title": title, "subtitle": maybe(0.8, text(PACK, "closing.closing_subtitle", variables))}, {})
        if title
        else None
    )


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
        name=f"{name} (Pitch)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a pitch deck's slide has it"
_TEAM_ROLE = "a team member's made-up role, as a pitch deck says it"
_MEMBER = "a role on the team, in a few words (without a name)"
# (Free models repeated the number in it: "73% / 73% of Antarctic research stations...")
_LABEL = "what the number counts, without the number itself"
# (and wrote "3700000000" and "50000" as big numbers)
_NUMBER = "the number as people read it, with its unit or currency, such as '3.7 billion' or '$2M'"
_COMPETITOR = "a competitor (made up, or an old way of doing it), by its name"
# (A free model wrote one title at both ends of an axis: "Cost" and "Cost")
_GOOD_ENDS = {
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
        name="Title slide (Pitch)",
        llm=Recipe("title"),
    ),
    # The problem
    # (D69: the problem slide, the pitch's why, three in four pitches' first; a long pitch's second problem slide is
    # one of the others)
    _part(
        "problem",
        6,
        "problem",
        _problem,
        ["problem_slide"],
        "Problem",
        Recipe(
            "problem",
            (_BACKDROP, _PAIN),
            brief="The problem the startup solves, right after the title, to hook the investors: a pain everyone in "
            "the room has, or should have, with the concept",
            hints={
                "kicker": "a short heading over the problem, as a pitch deck has it, such as 'The problem' or 'The "
                "pain'",
                "detail": "a short line under it that makes the pain hit home: how often it happens, to how many "
                "people, or what it costs them; it appears on a click",
            },
            variants=problem_variants(_ANGLES),
        ),
    ),
    _part(
        "problem",
        1,
        "statement",
        _problem_statement,
        ["statement"],
        "Problem Statement",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The problem the startup solves, as a bold statement over a photo: a pain that everyone "
            "supposedly has with the concept",
            hints={"text": "the problem, as one bold sentence or question, stated as a crisis"},
        ),
    ),
    _part(
        "problem",
        1,
        "big_number",
        _problem_number,
        ["big_number"],
        "Problem Number",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The problem the startup solves, as one alarming, suspiciously precise statistic about the concept",
            hints={"title": _TITLE_HINT + ", such as 'The problem'", "number": _NUMBER, "label": _LABEL},
            variants=pictured(
                (Variant(2), Variant(1, frozenset({"source"}), "without a source, for the presenter to give")),
                "background",
                BIG_NUMBER_PICTURES,
            ),
        ),
    ),
    # The solution
    # (the main product slide, most of the time: D63)
    _part(
        "solution",
        3,
        "image",
        _solution,
        ["single_image"],
        "Solution",
        Recipe(
            "image",
            (_PRODUCT,),
            brief="The startup's solution: its product, an absurd invention, in one picture of what it looks like (a "
            "weird gadget, machine or contraption), under a title that introduces it by name",
            hints={"title": "a title that introduces the product by the startup's made-up name"},
        ),
    ),
    _part(
        "solution",
        1,
        "two_columns",
        _before_and_after,
        ["two_captions"],
        "Before and After",
        Recipe(
            "two_columns",
            (_BEFORE, _AFTER),
            brief="Life before the startup's product and after it, as two captioned photos",
            hints={"caption_1": "life before the product, in a few words", "caption_2": "life after it"},
        ),
    ),
    _part(
        "solution",
        0.6,
        "process",
        _how_it_works,
        ["process"],
        "How It Works",
        Recipe(
            "process",
            brief="How the product works, in three to five steps, the last one the punchline: a step that gives the "
            "game away, or one nobody can explain",
            hints={
                "title": _TITLE_HINT + ", such as 'How it works'",
                **{f"step_{index}": "a step, in two to four words" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"step_4", "step_5"}), "in three steps"),
                Variant(1, frozenset({"step_5"}), "in three or four steps"),
                Variant(1, note="in three to five steps"),
            ),
        ),
    ),
    # The market
    _part(
        "market",
        1.5,
        "funnel",
        _market_funnel,
        ["funnel"],
        "Market Size",
        Recipe(
            "funnel",
            brief="The market's size, as a funnel: the total addressable market (TAM) at the top, the serviceable "
            "market (SAM), and the market the startup will win (SOM) at the bottom, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Market size'",
                "stage_1": "TAM, an amount and who's in it",
                "stage_2": "SAM, an amount and who's in it",
                "stage_3": "SOM, an amount and who's in it: the punchline",
            },
            omit=frozenset({"stage_4", "stage_5"}),
        ),
    ),
    _part(
        "market",
        0.6,
        "big_number",
        _market_number,
        ["big_number"],
        "Market Number",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The market's size, as one enormous amount of money that the concept is supposedly worth",
            hints={
                "title": _TITLE_HINT + ", such as 'Market size'",
                "number": "the market's size, in money",
                "label": _LABEL,
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
    ),
    # The business model
    _part(
        "business_model",
        1.2,
        "kpi",
        _pricing,
        ["kpi"],
        "Pricing",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The business model, as pricing plans on tiles: each plan a price and what it gets you, from free "
            "to the last one, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Business model'",
                **{f"number_{index}": "the plan's price" for index in range(1, 5)},
                **{f"label_{index}": "the plan's name and what it gets you" for index in range(1, 5)},
            },
            variants=pictured(
                (
                    Variant(1, frozenset({"number_4", "label_4"}), "with three plans"),
                    Variant(1, note="with four plans"),
                ),
                "background",
                KPI_PICTURES,
            ),
        ),
    ),
    _part(
        "business_model",
        1,
        "cycle",
        _flywheel,
        ["cycle"],
        "Flywheel",
        Recipe(
            "cycle",
            brief="The business model, as a flywheel: three to five things that feed each other, and the last back "
            "into the first",
            hints={
                "title": _TITLE_HINT + ", such as 'Our flywheel'",
                **{f"step_{index}": "a thing that feeds the next, in two to four words" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "business_model",
        0.8,
        "chart_categories",
        _revenue,
        ["pie_chart", "chart"],
        "Revenue Streams",
        Recipe(
            "chart_categories",
            brief="Where the startup's money comes from, as a pie chart of its revenue streams, one of them absurd",
            hints={
                "question": "the chart's title, such as 'Our revenue streams'",
                "categories": "three to five revenue streams, separated by |",
            },
        ),
    ),
    # The traction
    _part(
        "traction",
        1.3,
        "chart_trend",
        _hockey_stick,
        ["trend_chart", "chart"],
        "Hockey Stick",
        Recipe(
            "chart_trend",
            brief="The startup's traction: one line that grows like a hockey stick, with the moment it took off",
            hints={
                "title": "the chart's claim about the startup's growth",
                "shape": "how the line goes: hockey stick, or exponential",
                "line": "the startup's made-up name",
                "event": "the moment it took off, marked on the line",
            },
            omit=frozenset({"second_line", "second_shape"}),
        ),
    ),
    _part(
        "traction",
        1,
        "kpi",
        _traction_kpis,
        ["kpi"],
        "Traction Figures",
        Recipe(
            "kpi",
            (cg.backdrop_generator,),
            brief="The startup's traction, as figures on tiles: growth that starts out impressive, the last figure "
            "the punchline (such as its revenue)",
            hints={"title": _TITLE_HINT + ", such as 'Traction'"},
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
        "traction",
        0.9,
        "social_post",
        _testimonial,
        ["social_post"],
        "Testimonial",
        Recipe(
            "social_post",
            (_POST_PHOTO,),
            brief="A happy customer's post about the startup, as a testimonial: too happy, or happy about the wrong "
            "thing",
            hints={"title": "a title such as 'What our users say', or empty for none"},
        ),
        repeats=1,
    ),
    # The competition
    _part(
        "competition",
        1.5,
        "matrix",
        _matrix,
        ["matrix_diagram"],
        "Competition Matrix",
        Recipe(
            "matrix",
            brief="The competition, as a 2×2 matrix: the competitors (made up, or old ways of doing things) in three "
            "of its quadrants, and the startup as the dot, alone in the best one",
            hints={
                "title": _TITLE_HINT + ", such as 'Competition'",
                **_GOOD_ENDS,
                **{corner: _COMPETITOR for corner in ("top_left", "bottom_left", "bottom_right")},
                "top_right": "the label of the quadrant that's best on both axes, where only the startup is",
                "dot": "the startup, by its made-up name",
                "dot_quadrant": "top right, the quadrant that's best on both axes",
            },
            variants=matrix_landscape(_COMPETITOR, "the competitors"),
        ),
    ),
    _part(
        "competition",
        1,
        "chart_bars",
        _ranking,
        ["bar_chart", "chart"],
        "Competition Ranking",
        Recipe(
            "chart_bars",
            brief="Why the startup wins: a ranking of its competitors (made up, or old ways of doing things), which "
            "the startup, the last bar, wins by far",
            hints={
                "title": "what the ranking compares, as its title",
                "bars": "three to five competitors (only their names), separated by |, and the startup's made-up "
                "name last",
            },
        ),
    ),
    # The team
    _part(
        "team",
        1.6,
        "three_columns",
        _team,
        ["three_captions"],
        "Team",
        Recipe(
            "three_columns",
            (_PERSON, _PERSON, _PERSON),
            brief="The startup's team: three photos of people (never real ones), each with a made-up role",
            hints={
                "title": _TITLE_HINT + ", such as 'The team'",
                "caption_1": _TEAM_ROLE,
                "caption_2": _TEAM_ROLE,
                "caption_3": _TEAM_ROLE + ": the punchline",
            },
        ),
    ),
    _part(
        "team",
        1,
        "org_chart",
        _org_chart,
        ["org_chart"],
        "Team Org Chart",
        Recipe(
            "org_chart",
            brief="The startup's team, as an org chart: its roles, under who's really in charge, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The team'",
                "boss": "who's really in charge, in a few words: the punchline",
                **{f"report_{index}": _MEMBER for index in range(1, 5)},
            },
        ),
    ),
    # The roadmap, the ask and the closing
    _part(
        "roadmap",
        1,
        "timeline",
        _roadmap,
        ["timeline"],
        "Roadmap",
        Recipe(
            "timeline",
            brief="The startup's roadmap: what it will do when, soonest first, the last moment the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'Roadmap'",
                **{f"event_{index}": "what the startup does then, in a few words" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "ask",
        1,
        "big_number",
        _ask,
        [],
        "The Ask",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The ask: how much money the startup is raising, and what for",
            hints={
                "title": _TITLE_HINT + ", such as 'The ask'",
                "number": "the amount the startup raises, with its currency, such as '$2M'",
                "label": "what the money is for, or how much of the startup it buys",
                "source": "the round and its terms, as a pitch deck says them",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "closing",
        1,
        "questions",
        _closing,
        ["questions"],
        "Closing",
        Recipe(
            "questions",
            (cg.closing_picture_generator,),
            brief="The closing slide, after the ask: inviting the investors' questions (and their money)",
            hints={"subtitle": "a line under it, about investing"},
            variants=closing_variants("a line under it, about investing"),
        ),
        repeats=3,
    ),
]

# The format's other slides, for a long pitch's free slides (and to stand in for a part's slide that none of the
# part's generators can make): memes, gifs, press, a secret sauce, a bold statement, a fun fact, an anecdote, and full-
# screen photos, which a talk may have any number of (so that the free slides of a long one, without fair use too,
# never run out of slides)
# (D63: memes, gifs, Reddit's weird pictures and full-screen pictures more often, and fewer slides of text, as the user
# found pitches text-heavy; and the pitch's own provocations, a word over a full-screen picture: "Disrupt.")
_OTHERS: Final = {
    "Meme": 3,
    "Full Screen Gif": 1.2,
    "News Headline": 0.8,
    "Acronym": 0.6,
    "Wikihow Bold Statement": 0.4,
    "Fun Fact": 0.6,
    "Two Captions Gifs": 0.6,
    "Two Captions Weird Reddit": 0.8,
    "Anecdote": 0.3,
    "Inspirobot": 0.5,
    "Full Screen Neutral Images": 0.6,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Pitch)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 2, _variables, "Pitch", "as a startup founder says them on stage"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a pitch may have (see presentation_schema.most_slides): each kind once, so that a part of
# two slides has two kinds, and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 1,
    "single_image": 1,
    "two_captions": 1,
    "three_captions": 1,
    "process": 1,
    "pie_chart": 1,
    "kpi": 1,
    "big_number": 1,
    "provocation": 0.1,
}
