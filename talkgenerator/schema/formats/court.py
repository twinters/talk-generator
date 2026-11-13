"""The court case (docs/v5-plan.md, section 7; D79): the talk's topic on trial for a harmless, petty crime (taking the
last biscuit, hiding the TV remote), as a courtroom drama plays it, dead serious about something silly. A talk's crime
comes from its topic (see talkgenerator.schema.formats.crime), so that its slides try the same one: the charges, a
witness, the alibi, the closing argument and the verdict name it.

Its arc goes from the charges (breaking news that the topic has been charged, the counts read out one by one, or the
People versus the topic over a photo) through the evidence (D78's Exhibit A, an odd picture beside its evidence tag
that the presenter has to explain, and on a second slide Exhibit B, of the same case; or the lab's forensic analysis as
a scatter plot), a witness (their post about that
night, three photos of the witnesses, or a quiz for the audience on where the defendant was), the alibi (the night in
question minute by minute, a flowchart whose every answer ends in guilt, or "Alibi not found" as an error message), an
objection (shouted under a dramatic photo, or said over a calm one) and the closing argument (to the jury, over a photo;
the defendant's face, filling the slide: "Is this a criminal mastermind?"; or a Venn diagram of the signs of guilt, with
the defendant where they all meet) to the verdict (the jury's, as a pie chart; one big number, the vote or the sentence:
"30 days without Wi-Fi"; or the audience as the jury, by a show of hands), before its closer adjourns the court (D76),
outside its slides. A short trial keeps its evidence, its verdict, its charges and the alibi; a quarter of a talk's
slides are free (D63), for memes, gifs, full-screen pictures, deep questions over photos, its own provocations
("Objection.", over a full-screen picture), a fun fact, red flags, an alignment chart and a tier list, and a long one
gives the evidence a second slide. Every crime is harmless: nobody is hurt, and the worst sentence is community service.

A detective presents a court case more often than the other personas, a conspiracy blogger, a medieval historian and
a game-show host a little more often; its themes are newspapers and vintage paper more often, and brutalist and dark
minimal ones.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.closers import Closer, presenter, said
from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.plan.kinds import AGENDA_ITEM, ERROR_BUTTON, Recipe, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    crime,
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
from talkgenerator.sources import text_generator
from talkgenerator.util import random_util

PACK: Final = "court"

# (D63: a quarter of its slides are free, for memes, gifs and pictures. A trial too short for all of its parts keeps the
# evidence, the verdict and the charges first: what the topic did, what proves it, and what it gets)
ARC: Final = Arc(
    (
        Part("charges", rank=2),
        Part("evidence", 1, 2, rank=0),
        Part("witness", rank=4),
        Part("alibi", rank=3),
        Part("objection", rank=6),
        Part("closing_argument", rank=5),
        Part("verdict", rank=1),
    ),
    free=0.25,
)

COURT: Final = Format(
    brief="a court case in which the topic stands trial for a harmless, petty crime (the last biscuit, a sock that "
    "vanished), as a courtroom drama plays it: the charges, the evidence (Exhibit A, Exhibit B), a witness, the alibi, "
    "an objection, the closing argument and the verdict, which the audience may help reach. The topic is the "
    "defendant, however absurd, and every slide is a courtroom's, dead serious about something silly: nobody is hurt, "
    "and the worst sentence is community service",
    title_hint="like a court case's name or a true-crime story's: 'The People v.' and the topic, or the case of "
    "something petty that went missing",
    job_hint="their part in the trial, as the court introduces them: the prosecutor, the counsel for the defence or "
    "the detective on the case",
    personas={"detective": 9, "conspiracy_blogger": 2.5, "medieval_historian": 1.3, "game_show_host": 1.2},
    themes={
        "corkboard": 3,
        "newspaper": 4,
        "vintage paper": 2,
        "brutalist": 1.5,
        "dark minimal": 1.3,
        "academic": 1.2,
        "kids": 0.4,
        "neon": 0.5,
        "Comic Sans everywhere": 0.5,
        "startup": 0.5,
    },
    arc=ARC,
    # (its closer adjourns the court: D76)
    closer=Closer(said("adjourned"), presenter),
    scene="courtroom",
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic (the defendant) and its crime, the
    presenter and the title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["topic"] = context.get("topic") or context["seed"]
    variables["crime"] = crime(str(variables["topic"]))
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE TITLE SLIDE: the case, and who argues it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic court case's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", context)


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a calm backdrop behind what's said in court, a photo of the defendant (and of the witnesses, and the one in
# the news), and a dramatic one for an objection (the evidence's odd pictures are D78's exhibits')
_BACKDROP = cg.statement_backdrop_generator
_PHOTO = cg.copyright_free_generator
_DRAMATIC = cg.weird_copyright_free_generator


# THE CHARGES: breaking news, the counts read out, or the People versus the topic


def _breaking_news(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    outlet, headline = text(PACK, "charges.outlet", variables), text(PACK, "charges.headline", variables)
    if not outlet or not headline:
        return None
    texts = {
        "outlet": outlet,
        "headline": headline,
        "subheadline": maybe(0.8, text(PACK, "charges.subheadline", variables)),
    }
    return texts, {"photo": _PHOTO(context)}


def _charges(context: dict[str, Any]) -> Made | None:
    """The counts: the talk's crime first, one or two lesser charges, and the punchline."""
    variables = _variables(context)
    first = text(PACK, "charges.first_count", variables)
    counts = different(PACK, "charges.count", variables, random_util.randint(1, 2))
    punchline, title = text(PACK, "charges.count_punchline", variables), text(PACK, "charges.charges_title", variables)
    if not title or not first or not punchline or not counts:
        return None
    return {"title": title, "items": " | ".join([first, *counts, punchline])}, {}


def _the_people(context: dict[str, Any]) -> Made | None:
    statement = text(PACK, "charges.case_statement", _variables(context))
    return ({"text": statement}, {"background": _BACKDROP(context)}) if statement else None


# THE EVIDENCE: D78's Exhibit A (an odd picture beside its evidence tag; Exhibit B on a second slide), or the
# lab's analysis


def _forensics(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "evidence.forensics_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "evidence.forensics_x", variables),
        "y_axis": text(PACK, "evidence.forensics_y", variables),
        "outlier": maybe(0.7, text(PACK, "evidence.forensics_outlier", variables)),
    }, {}


# A WITNESS: their post, the witnesses in photos, or a quiz for the audience


def _handle(author: str) -> str:
    first = "".join(letter for letter in author.split()[0].lower() if letter.isalpha()) if author.split() else "witness"
    return random_util.choice((f"{first}_saw_it_all", f"real{first}", f"{first}{random_util.randint(2, 99)}"))[:24]


def _witness_post(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    post = text(PACK, "witness.post", variables)
    author = cg.full_name_generator({})
    if not post or not author:
        return None
    photo = _PHOTO(context) if random_util.random() < 0.5 else None
    texts = {
        "title": maybe(0.7, text(PACK, "witness.post_title", variables)),
        "author": str(author),
        "handle": _handle(str(author)),
        "text": post,
    }
    return texts, {"photo": photo}


def _witnesses(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    witnesses = different(PACK, "witness.witness", variables, 2)
    punchline = text(PACK, "witness.witness_punchline", variables)
    if len(witnesses) < 2 or not punchline:
        return None
    texts = {"title": text(PACK, "witness.witnesses_title", variables), **_items("caption", [*witnesses, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_PHOTO, context, 3), 1)}


def _quiz(context: dict[str, Any]) -> Made | None:
    """Where the defendant was: two or three innocent places and, in a place the dice pick, the suspicious one, the
    answer (with an explanation that names none of the options, so it never names a wrong one)."""
    variables = _variables(context)
    count = 4 if random_util.random() < 0.6 else 3
    elsewhere = different(PACK, "witness.quiz_option", variables, count - 1)
    answer, question = text(PACK, "witness.quiz_answer", variables), text(PACK, "witness.quiz_question", variables)
    if not question or not answer or len(elsewhere) < count - 1:
        return None
    place = random_util.randint(0, count - 1)
    options = [*elsewhere[:place], answer, *elsewhere[place:]]
    texts: dict[str, str | None] = {
        "question": question,
        "answer": "ABCD"[place],
        "explanation": maybe(0.8, text(PACK, "witness.quiz_explanation", variables)),
    }
    texts.update({f"option_{letter}": option for letter, option in zip("abcd", options, strict=False)})
    return texts, {}


# THE ALIBI: the night in question, a flowchart, or an alibi that can't be found


def _night(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "alibi.night_first", variables), text(PACK, "alibi.night_punchline", variables)
    middle = different(PACK, "alibi.night_event", variables, count - 2)
    title = text(PACK, "alibi.night_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    # (in the order they'd happen that night, the crime itself among them)
    events = [
        text_generator.apply_variables_to_template(event, dict(variables)) for event in words(PACK, "alibi.night_event")
    ]
    middle.sort(key=lambda event: events.index(event) if event in events else len(events))
    known = words(PACK, "alibi.night_time")  # (earliest first)
    times = [known[index] for index in sorted(random_util.sample(range(len(known)), count))]
    texts: dict[str, str | None] = {"title": title}
    for index, (time, event) in enumerate(zip(times, [first, *middle, last], strict=True), 1):
        texts[f"date_{index}"], texts[f"event_{index}"] = time, event
    return texts, {}


def _alibi_check(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    texts = {
        "question": text(PACK, "alibi.flow_question", variables),
        "yes_step": text(PACK, "alibi.flow_yes", variables),
        "no_step": text(PACK, "alibi.flow_no", variables),
        "end": text(PACK, "alibi.flow_end", variables),
    }
    if not all(texts.values()):
        return None
    return {"title": maybe(0.6, text(PACK, "alibi.flow_title", variables)), **texts}, {}


def _alibi_not_found(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    buttons = different(PACK, "alibi.button", variables, random_util.randint(1, 2))
    punchline, message = text(PACK, "alibi.button_punchline", variables), text(PACK, "alibi.error", variables)
    if not message or not punchline or not buttons:
        return None
    return {
        "title": maybe(0.8, text(PACK, "alibi.error_title", variables)),
        "message": message,
        "code": maybe(0.8, text(PACK, "alibi.error_code", variables)),
        "buttons": " | ".join([*buttons, punchline]),
    }, {}


# AN OBJECTION: shouted under a dramatic photo, or said over a calm one


def _objection(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "objection.objection_title", _variables(context))
    return ({"title": title}, {"image": _DRAMATIC(context)}) if title else None


def _objection_statement(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "objection.objection_statement", _variables(context))
    return ({"text": said}, {"background": _BACKDROP(context)}) if said else None


# THE CLOSING ARGUMENT: to the jury, the defendant's face, or the signs of guilt where they meet


def _closing_argument(context: dict[str, Any]) -> Made | None:
    argument = text(PACK, "closing.closing_statement", _variables(context))
    return ({"text": argument}, {"background": _BACKDROP(context)}) if argument else None


def _this_face(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "closing.face_title", _variables(context))
    return ({"title": title}, {"image": _PHOTO(context)}) if title else None


def _signs_of_guilt(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    circles = different(PACK, "closing.venn_circle", variables, 3 if random_util.random() < 0.6 else 2)
    title, overlap = text(PACK, "closing.venn_title", variables), text(PACK, "closing.venn_overlap", variables)
    if not title or not overlap or len(circles) < 2:
        return None
    return {"title": title, **_items("circle", circles), "overlap": overlap}, {}


# THE VERDICT: the jury's pie chart, one big number, or the audience as the jury


def _jury_chart(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    question, funny = text(PACK, "verdict.verdict_question", variables), text(PACK, "verdict.verdict_funny", variables)
    return ({"question": question, "funny_answer": funny}, {}) if question and funny else None


def _verdict(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    number, _, label = (text(PACK, "verdict.verdict_number", variables) or "").partition("|")
    if not number.strip() or not label.strip():
        return None
    return {
        "title": text(PACK, "verdict.verdict_title", variables),
        "number": number.strip(),
        "label": label.strip(),
        "source": maybe(0.7, text(PACK, "verdict.verdict_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _the_jury(context: dict[str, Any]) -> Made | None:
    said = text(PACK, "verdict.jury", _variables(context))
    return ({"audience": said}, {}) if said else None


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
        name=f"{name} (Court)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a courtroom drama's slide has it"
_FEW_WORDS = "in two to four words"
_PETTY = "a harmless, petty crime (never violence, weapons or anyone hurt)"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Court)",
        llm=Recipe("title"),
    ),
    # The charges
    _part(
        "charges",
        1.3,
        "news_headline",
        _breaking_news,
        ["news"],
        "Breaking News",
        Recipe(
            "news_headline",
            (_PHOTO,),
            brief=f"The charges, as breaking news: a headline that the topic has been charged with {_PETTY}, over a "
            "photo of the accused",
            hints={
                "outlet": "the made-up name of a newspaper or a channel that covers court cases",
                "headline": f"the headline: what the topic is charged with, {_PETTY}",
                "subheadline": "a line under it, with one more absurd detail of the case",
            },
        ),
    ),
    _part(
        "charges",
        1,
        "agenda",
        _charges,
        ["agenda"],
        "The Charges",
        Recipe(
            "agenda",
            brief="The charges against the topic, read out as numbered counts: three to five harmless, petty crimes, "
            "the last one the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The charges'",
                "items": f"three to five charges, separated by |, each at most {AGENDA_ITEM} characters, the last one "
                "the punchline",
            },
        ),
        repeats=3,
    ),
    _part(
        "charges",
        1,
        "statement",
        _the_people,
        ["statement"],
        "The People Versus",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The case opens: the court's solemn words over a photo, the People versus the topic, and what for",
            hints={"text": "the court's opening words, in one or two sentences, naming the case and the petty crime"},
        ),
    ),
    # The evidence
    _part(
        "evidence",
        0.8,
        "chart_correlation",
        _forensics,
        ["curve", "chart"],
        "Forensic Analysis",
        Recipe(
            "chart_correlation",
            brief="The lab's forensic analysis, as a scatter plot of made-up data that proves the topic's guilt: the "
            "nearer the topic, the more of the evidence",
            hints={
                "title": "the lab's finding, as a claim in a few words",
                "x_axis": "how near the topic, or when, along the bottom",
                "y_axis": "how much of the evidence was found, such as crumbs",
                "outlier": "one point far from the others, named after another suspect",
            },
        ),
    ),
    # A witness
    _part(
        "witness",
        1.1,
        "social_post",
        _witness_post,
        ["social_post"],
        "Witness Statement",
        Recipe(
            "social_post",
            (_PHOTO,),
            brief="A witness's post about the night of the crime: what they saw or heard, as people post it, sure of "
            "the wrong details",
            hints={
                "title": "a title such as 'Witness statement', or empty for none",
                "author": "the witness's made-up name (never a real person)",
            },
        ),
        repeats=1,
    ),
    _part(
        "witness",
        1.2,
        "three_columns",
        _witnesses,
        ["three_captions"],
        "The Witnesses",
        Recipe(
            "three_columns",
            (_PHOTO, _PHOTO, _PHOTO),
            brief="The witnesses: three photos, each captioned with who the witness is, the last one the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The witnesses'",
                "caption_1": f"a witness, {_FEW_WORDS}",
                "caption_2": f"another witness, {_FEW_WORDS}",
                "caption_3": f"the last witness, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "witness",
        1,
        "quiz",
        _quiz,
        ["quiz"],
        "Where Was the Defendant",
        Recipe(
            "quiz",
            brief="A quiz for the audience, as if they were the detectives: where the defendant was on the night of "
            "the crime, with three or four places, the right one the most suspicious",
            hints={
                "question": "where the defendant was at the time of the crime, as a question to the audience",
                "explanation": "how the court knows, without naming another option",
            },
        ),
    ),
    # The alibi
    _part(
        "alibi",
        1.2,
        "timeline",
        _night,
        ["timeline"],
        "The Night in Question",
        Recipe(
            "timeline",
            brief="The night in question, as a timeline: what the defendant did, minute by minute, the last moment the "
            "punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The night in question'",
                **{f"date_{index}": "a time of that night, such as '21:13'" for index in range(1, 6)},
                **{f"event_{index}": f"what the defendant did then, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    _part(
        "alibi",
        1,
        "flowchart",
        _alibi_check,
        ["flowchart"],
        "Alibi Check",
        Recipe(
            "flowchart",
            brief="Checking the defendant's alibi, as a flowchart whose every answer leads to the same end: guilt",
            hints={
                "title": "a title such as 'The alibi', or empty for none",
                "question": "a yes-or-no question about the defendant's alibi",
                "end": "where both answers lead: the defendant's guilt, the punchline",
            },
        ),
    ),
    _part(
        "alibi",
        1,
        "error_message",
        _alibi_not_found,
        ["error_message"],
        "Alibi Not Found",
        Recipe(
            "error_message",
            brief="The defendant's alibi, as a fake error message from the court's records: it can't be found, with "
            "buttons, the last one the punchline",
            hints={
                "title": "the dialog's title, such as the court's records system",
                "buttons": f"two or three buttons, separated by |, each at most {ERROR_BUTTON} characters: the last one "
                "the punchline, such as a confession",
            },
        ),
    ),
    # An objection
    _part(
        "objection",
        1.3,
        "full_image",
        _objection,
        ["full_image"],
        "Objection",
        Recipe(
            "full_image",
            (_DRAMATIC,),
            brief="An objection, shouted in court: a dramatic photo filling the slide, under 'Objection!' and an absurd "
            "reason",
            hints={"title": "'Objection!' and its reason, in a few words"},
        ),
    ),
    _part(
        "objection",
        1,
        "statement",
        _objection_statement,
        ["statement"],
        "Objection, Your Honour",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="An objection, as one sentence over a photo: what counsel objects to, absurdly",
            hints={"text": "the objection, in one sentence that starts with 'Objection'"},
        ),
    ),
    # The closing argument
    _part(
        "closing_argument",
        1,
        "statement",
        _closing_argument,
        ["statement"],
        "Closing Argument",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The closing argument, as one sentence to the jury over a photo: why it can only have been the topic",
            hints={"text": "the closing argument, in one or two sentences to the jury"},
        ),
    ),
    _part(
        "closing_argument",
        1.2,
        "full_image",
        _this_face,
        ["full_image"],
        "Look at This Face",
        Recipe(
            "full_image",
            (_PHOTO,),
            brief="The defendant, in a photo filling the slide, under a question to the jury: does this look like the "
            "face of someone who did it?",
            hints={"title": "a question to the jury about the defendant's face, in a few words"},
        ),
    ),
    _part(
        "closing_argument",
        1,
        "venn",
        _signs_of_guilt,
        ["venn_diagram"],
        "Signs of Guilt",
        Recipe(
            "venn",
            brief="The case against the topic, as a Venn diagram: two or three signs of guilt (a motive, the chance, "
            "crumbs), and the defendant where they all meet, the punchline",
            hints={
                "title": _TITLE_HINT + ", such as 'The case against' the topic",
                "overlap": "the defendant: the topic, in a few words",
            },
        ),
    ),
    # The verdict
    _part(
        "verdict",
        1,
        "chart_yes_no",
        _jury_chart,
        ["yes_no_chart", "chart"],
        "The Jury Decides",
        Recipe(
            "chart_yes_no",
            brief="The jury's verdict, as a pie chart: guilty or not, and a funny third answer",
            hints={"question": "the verdict's yes-or-no question: whether the defendant did it"},
        ),
    ),
    _part(
        "verdict",
        1.2,
        "big_number",
        _verdict,
        ["big_number"],
        "The Verdict",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="The verdict, as one big number: the jury's vote, or how long the harmless sentence lasts",
            hints={
                "title": _TITLE_HINT + ", such as 'The verdict'",
                "number": "the number as people read it, with its unit: a vote, or a sentence's days or hours",
                "label": "what it counts, the vote or the harmless sentence, without the number itself",
                "source": "who decided it, such as the judge, after lunch",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "verdict",
        1.1,
        "dare",
        _the_jury,
        ["dare"],
        "You Are the Jury",
        Recipe(
            "dare",
            brief="The audience as the jury: what everyone does to give their verdict on the defendant",
            hints={
                "audience": "what the whole audience does to give its verdict, said to them: a show of hands, or a "
                "word said together; harmless, fun to join in, and singling nobody out"
            },
            omit=frozenset({"dare"}),
        ),
        repeats=1,
    ),
]

# The format's other slides, for a trial's free slides (and to stand in for a part's slide that none of the part's
# generators can make): memes (the most, as in the other formats), gifs, deep questions over photos and full-screen
# photos, which a talk may have any number of (so that the free slides of a long one, without fair use too, never run
# out of slides), a fun fact, red flags, an alignment chart (lawful to chaotic, as a court sees it) and a tier list
_OTHERS: Final = {
    "Meme": 2,
    "Full Screen Gif": 1,
    "Full Screen Pixabay Deep": 0.9,
    "Full Screen Neutral Images": 0.8,
    "Two Captions Gifs": 0.5,
    "Fun Fact": 0.5,
    "Red Flags": 0.6,
    "Alignment Chart": 0.6,
    "Tier List": 0.4,
}

GENERATORS: Final = [
    *_GENERATORS,
    # (its evidence's exhibits are D78's, whose second in a talk is Exhibit B, of the same case)
    slide_generators.get("Exhibit A").weighted(InPart(ARC, "evidence", 1.6), "Exhibit A (Court)", ("evidence",)),
    *(slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Court)") for name, weight in _OTHERS.items()),
    provocation(PACK, ARC, 1.3, _variables, "Court", "as a courtroom hears them"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a court case may have (see presentation_schema.most_slides): each kind once, so that the
# evidence's two slides are two kinds, but for the statements (the case, an objection and the closing argument may each
# have one) and the charts (the lab's and the jury's); full-bleed photos aren't capped, as the TED-like talks' aren't;
# and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 3,
    "chart": 2,
    "single_image": 1,
    "two_captions": 1,
    "three_captions": 1,
    "curve": 1,
    "provocation": 0.1,
}
