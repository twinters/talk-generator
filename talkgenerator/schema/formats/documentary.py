"""The nature documentary (docs/v5-plan.md, section 7; D79): the talk's topic as a wild species, filmed for years and
narrated in a hushed, reverent voice, as nature documentaries follow their animals.

Its arc goes from the opening shot (a sweeping landscape of the topic's world under the narrator's hushed first line,
or a grand line over a calm photo) through its habitat (one photo under the name of its natural habitat, where it's
found as a pie chart, or a fact about how it lives), its behaviour (three photos of what it does, the last what it's
really doing; two of its stages or moods side by side; or a day in its life as a cycle), a rare sighting (an odd photo,
full-bleed, as the crew's first footage of it, or the news of it), its rituals (an ancient ritual in an odd photo, or
its courtship dance as a process), the dangers it faces (how few are left as one big number, its numbers falling as a
trend chart, or a harmless, everyday danger told as a grave one) to a closing reflection (over a calm photo, its last
shot at sunset under the narrator's farewell or next time's episode, or the whole room hushed, as the species is near:
a closing that needs no picture, so a documentary always has one). A short documentary keeps its opening, its
behaviour, the rare sighting and its closing; a fifth of a talk's slides are free (D63), for memes, full-screen pictures
and gifs, deep questions over photos, a quiz on the species ("Which of these is Penguinus domesticus?") and its own
provocations ("Majestic.", over a full-screen picture); a long one gives its behaviour a second slide. The species'
made-up Latin name comes from the topic (see talkgenerator.schema.formats.species), so that a classic documentary's
slides follow the species its title names.

A nature-documentary narrator presents a documentary more often than the other personas, an alien anthropologist
often too, and an over-passionate expert and a time traveller a little more often; its themes are dark minimal ones
more often, and clean keynotes.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.datastructures.slide_generator_data import PeakedWeight, SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import Recipe, Variant, pictured
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats import (
    BIG_NUMBER_PICTURES,
    Format,
    KindSlideGenerator,
    Made,
    behind,
    different,
    maybe,
    photos,
    provocation,
    species,
    text,
    words,
)
from talkgenerator.schema.formats.arcs import Arc, Free, InPart, Part
from talkgenerator.schema.slide_schemas import default_max_allowed_tags, slide_generators
from talkgenerator.slide import slide_generator_types
from talkgenerator.util import random_util

PACK: Final = "documentary"

# (its rare sighting stays longer than its habitat: an odd photo to explain is a documentary's best slide in a short talk)
ARC: Final = Arc(
    (
        Part("opening", rank=1),
        Part("habitat", rank=4),
        Part("behaviour", 1, 2, rank=3),
        Part("sighting", rank=2),
        Part("ritual", rank=6),
        Part("threat", rank=5),
        Part("closing", rank=0),
    ),
    free=0.2,  # (D63: a slide of ten for a meme, a gif or a picture; its parts are mostly pictures already)
)

DOCUMENTARY: Final = Format(
    brief="a nature documentary about the topic as if it were a wild species, narrated in a hushed, reverent voice: "
    "an establishing shot of its world, its habitat, its behaviour, a rare sighting, its rituals, the dangers it faces "
    "and a closing reflection. The topic is the species, however unlikely, studied with the utmost seriousness, and "
    "every slide is a nature documentary's, played straight: big wildlife photos and few words",
    title_hint="like a nature documentary's title or episode: grand, hushed and a little dramatic, in a few words",
    job_hint="their part in the documentary, as its credits would put it: its narrator, its wildlife camera operator "
    "or its field researcher",
    personas={"passionate_expert": 1.5, "time_traveller": 1.2},
    themes={
        "dark minimal": 4,
        "clean keynote": 2,
        "vintage paper": 1.3,
        "1997 WordArt": 0.4,
        "Comic Sans everywhere": 0.4,
        "clip-art corporate": 0.5,
        "corporate": 0.5,
        "hacker terminal": 0.5,
        "kids": 0.6,
    },
    arc=ARC,
)


def _variables(context: dict[str, Any]) -> dict[str, Any]:
    """What the pack's templates may use: the slide's seed, the talk's topic, its species' made-up name, the presenter
    and the title."""
    variables = {key: context[key] for key in ("seed", "topic", "presenter", "title") if context.get(key)}
    variables["species"] = species(str(context.get("topic") or context["seed"]))
    return variables


def _items(prefix: str, texts: list[str]) -> dict[str, str | None]:
    return {f"{prefix}_{index}": item for index, item in enumerate(texts, 1)}


# THE TITLE SLIDE: the documentary's title, and who narrates or filmed it


def title_generator(context: dict[str, Any]) -> str | None:
    """A classic documentary's title, about the seed (the talk's topic)."""
    return text(PACK, "title.talk_title", {**context, "species": species(str(context["seed"]))})


def _title_if_not_generated(context: dict[str, Any]) -> str | None:
    return context["title"] if context.get("title") is not None else title_generator(context)


def _subtitle(context: dict[str, Any]) -> str | None:
    return text(PACK, "title.subtitle", _variables(context))


# Images: a sweeping landscape for the opening shot (the sky and earth pictures people are proud of, else stock photos),
# the topic in its habitat, wildlife photos of what it does, an odd photo of a rare sighting and of a ritual, a calm
# photo behind the narrator's lines, and the topic at sunset for the last shot
_LANDSCAPE = ImageSlot(
    "a sweeping landscape of the topic's world, as a nature documentary opens",
    queries=("{} landscape", "{}"),
    aesthetic="places",
    backups=("photo",),
)
_HABITAT = ImageSlot(
    "the topic in its natural habitat, as a nature documentary shows it",
    queries=("{} habitat", "{}"),
    aesthetic="places",
    backups=("photo",),
)
_WILD = ImageSlot("a wildlife photo of the topic", aesthetic="photo")
_SIGHTING = ImageSlot("an odd photo of the topic, as if caught on camera in the wild", aesthetic="weird-stock")
_RITUAL = ImageSlot("an odd photo of a gathering, as the topic's ancient ritual", aesthetic="weird-stock")
_BACKDROP = cg.statement_backdrop_generator
_SUNSET = ImageSlot("the topic at sunset, as a nature documentary's last shot", queries=("{} sunset", "{}"))


# THE OPENING: a landscape under a hushed first line, or a grand line over a calm photo


def _opening_shot(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "opening.dawn", _variables(context))
    return ({"title": title}, {"image": _LANDSCAPE(context)}) if title else None


def _opening_line(context: dict[str, Any]) -> Made | None:
    line = text(PACK, "opening.planet", _variables(context))
    return ({"text": line}, {"background": _BACKDROP(context)}) if line else None


# THE HABITAT: one photo under its name, where it's found as a pie chart, or a fact about how it lives


def _habitat(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "habitat.home_title", _variables(context))
    return ({"title": title}, {"image": _HABITAT(context)}) if title else None


def _range(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    places = different(PACK, "habitat.range", variables, random_util.randint(3, 4))
    question = text(PACK, "habitat.range_question", variables)
    if not question or len(places) < 3:
        return None
    return {"question": question, "categories": " | ".join(places)}, {}


def _habitat_fact(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    fact = text(PACK, "habitat.fact", variables)
    if not fact:
        return None
    return {"fact": fact, "source": maybe(0.8, text(PACK, "habitat.fact_source", variables))}, {"photo": _WILD(context)}


# THE BEHAVIOUR: three photos of what it does, two of its stages or moods, or a day in its life


def _behaviour(context: dict[str, Any]) -> Made | None:
    """Three photos of what the species does, the last what it's really doing: two things it does that the punchline
    doesn't start with (not "Hiding" before "Hiding from the crew")."""
    variables = _variables(context)
    punchline = text(PACK, "behaviour.activity_punchline", variables)
    title = text(PACK, "behaviour.behaviour_title", variables)
    if not punchline or not title:
        return None
    said = {word.strip(",.").lower() for word in punchline.split()}
    doing = [
        activity
        for activity in different(PACK, "behaviour.activity", variables, 4)
        if activity.split()[0].strip(",.").lower() not in said
    ][:2]
    if len(doing) < 2:
        return None
    texts = {"title": title, **_items("caption", [*doing, punchline])}
    return texts, {f"image_{index}": photo for index, photo in enumerate(photos(_WILD, context, 3), 1)}


def _side_by_side(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    pair = [part.strip() for part in (text(PACK, "behaviour.pair", variables) or "").split("|")]
    title = text(PACK, "behaviour.pair_title", variables)
    if not title or len(pair) != 2 or not all(pair):
        return None
    first, second = photos(_WILD, context, 2)
    return {"title": title, "caption_1": pair[0], "caption_2": pair[1]}, {"image_1": first, "image_2": second}


def _day(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    steps = different(PACK, "behaviour.cycle_step", variables, random_util.randint(4, 5))
    title = text(PACK, "behaviour.cycle_title", variables)
    if not title or len(steps) < 3:
        return None
    return {"title": title, **_items("step", steps)}, {}


# THE RARE SIGHTING: an odd photo, full-bleed, or the news of it


def _rare_sighting(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "sighting.rare", _variables(context))
    return ({"title": title}, {"image": _SIGHTING(context)}) if title else None


def _sighting_news(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    outlet, headline = text(PACK, "sighting.outlet", variables), text(PACK, "sighting.headline", variables)
    if not outlet or not headline:
        return None
    return {
        "outlet": outlet,
        "headline": headline,
        "subheadline": maybe(0.8, text(PACK, "sighting.subheadline", variables)),
    }, {"photo": _SIGHTING(context)}


# THE RITUAL: an ancient ritual in an odd photo, or its courtship dance, step by step


def _ritual(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "ritual.ancient", _variables(context))
    return ({"title": title}, {"image": _RITUAL(context)}) if title else None


def _dance(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    count = random_util.randint(3, 5)
    first, last = text(PACK, "ritual.dance_first", variables), text(PACK, "ritual.dance_last", variables)
    middle = different(PACK, "ritual.dance_step", variables, count - 2)
    title = text(PACK, "ritual.dance_title", variables)
    if not title or not first or not last or len(middle) < count - 2:
        return None
    return {"title": title, **_items("step", [first, *middle, last])}, {}


# THE THREAT: how few are left, its numbers falling, or an everyday danger told as a grave one


def _left(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    label = text(PACK, "threat.left_label", variables)
    if not label:
        return None
    return {
        "title": text(PACK, "threat.left_title", variables),
        "number": random_util.choice(words(PACK, "threat.left_number")),
        "label": label,
        "source": maybe(0.7, text(PACK, "threat.left_source", variables)),
    }, behind(context, BIG_NUMBER_PICTURES)


def _fewer(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    title = text(PACK, "threat.trend_title", variables)
    if not title:
        return None
    return {
        "title": title,
        "x_axis": text(PACK, "threat.trend_x", variables),
        "y_axis": text(PACK, "threat.trend_y", variables),
        "shape": random_util.choice(("falling", "falling", "crash")),
        "line": variables["species"],
        "event": maybe(0.8, text(PACK, "threat.trend_event", variables)),
    }, {}


def _danger(context: dict[str, Any]) -> Made | None:
    line = text(PACK, "threat.danger", _variables(context))
    return ({"text": line}, {"background": _BACKDROP(context)}) if line else None


# THE CLOSING: a reflection over a calm photo, the last shot at sunset, or the room hushed


def _reflection(context: dict[str, Any]) -> Made | None:
    line = text(PACK, "closing.reflection", _variables(context))
    return ({"text": line}, {"background": _BACKDROP(context)}) if line else None


def _farewell(context: dict[str, Any]) -> Made | None:
    title = text(PACK, "closing.farewell", _variables(context))
    return ({"title": title}, {"image": _SUNSET(context)}) if title else None


def _hush(context: dict[str, Any]) -> Made | None:
    """The room, hushed: everyone keeps very still, as the species might be watching (it needs no picture of its own,
    so the documentary always has a way to end)."""
    said = text(PACK, "closing.hush", _variables(context))
    return ({"audience": said}, {}) if said else None


# A FREE SLIDE OF ITS OWN: a quiz on the species, of one of these kinds (each with its question, its options and why)
_QUIZZES: Final = ("lookalike", "diet", "sleep", "sound")


def _spot_the_species(context: dict[str, Any]) -> Made | None:
    variables = _variables(context)
    quiz = random_util.choice(_QUIZZES)
    count = 4 if random_util.random() < 0.6 else 3
    options = different(PACK, f"free.options_{quiz}", variables, count)
    question = text(PACK, f"free.question_{quiz}", variables)
    if not question or len(options) < count:
        return None
    texts: dict[str, str | None] = {"question": question}
    for letter, option in zip("abcd", options, strict=False):
        texts[f"option_{letter}"] = option
    texts["answer"] = "ABCD"[random_util.randrange(count)]
    texts["explanation"] = maybe(0.7, text(PACK, f"free.why_{quiz}", variables))
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
        name=f"{name} (Documentary)",
        llm=recipe,
    )


_TITLE_HINT = "the slide's title, as a nature documentary's caption has it: a few words"
_HUSHED = "in a few words, as the narrator would whisper them"
_FEW_WORDS = "in one to three words"

_GENERATORS: Final = [
    SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(_title_if_not_generated, _subtitle),
        allowed_repeated_elements=3,
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide (Documentary)",
        llm=Recipe("title"),
    ),
    # The opening
    _part(
        "opening",
        1.3,
        "full_image",
        _opening_shot,
        ["full_image"],
        "Opening Shot",
        Recipe(
            "full_image",
            (_LANDSCAPE,),
            brief="The documentary's opening shot: a sweeping landscape of the species' world, filling the slide, "
            "under the narrator's hushed first line",
            hints={"title": f"the narrator's first line, {_HUSHED}"},
        ),
    ),
    _part(
        "opening",
        1,
        "statement",
        _opening_line,
        ["statement"],
        "Opening Line",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The documentary's opening, over a calm photo: a grand, hushed line that introduces the topic as a "
            "wild species",
            hints={"text": "the narrator's opening line, in one or two short sentences, grand and hushed"},
        ),
    ),
    # The habitat
    _part(
        "habitat",
        1.3,
        "image",
        _habitat,
        ["single_image"],
        "Natural Habitat",
        Recipe(
            "image",
            (_HABITAT,),
            brief="The species' natural habitat, in one photo, under a title that names it: a grand one, or an "
            "absurdly everyday one",
            hints={"title": "the species' natural habitat, as the narrator names it, in a few words"},
        ),
    ),
    _part(
        "habitat",
        0.8,
        "chart_categories",
        _range,
        ["pie_chart", "chart"],
        "Where It Is Found",
        Recipe(
            "chart_categories",
            brief="Where the species is found, as a pie chart of its habitats, the wild ones and the absurdly "
            "everyday ones",
            hints={
                "question": "the chart's title: where the species is found",
                "categories": "three or four habitats, separated by |",
            },
        ),
    ),
    _part(
        "habitat",
        1,
        "fun_fact",
        _habitat_fact,
        ["fun_fact"],
        "Habitat Fact",
        Recipe(
            "fun_fact",
            (_WILD,),
            brief="A fact about how the species lives in the wild, stated with total certainty, with its photo",
            hints={
                "fact": "the fact: one sentence about how the species lives, stated as certain",
                "source": "a made-up source: the crew's notes, a ranger, a survey",
            },
        ),
    ),
    # The behaviour
    _part(
        "behaviour",
        1.4,
        "three_columns",
        _behaviour,
        ["three_captions"],
        "Behaviour",
        Recipe(
            "three_columns",
            (_WILD, _WILD, _WILD),
            brief="Three photos of the species' behaviour, each with what it's doing, the last one what it's really "
            "doing, the punchline",
            hints={
                "title": _TITLE_HINT,
                "caption_1": f"what it's doing, {_FEW_WORDS}",
                "caption_2": f"something else it does, {_FEW_WORDS}",
                "caption_3": "what it's really doing, the punchline, in a few words",
            },
        ),
    ),
    _part(
        "behaviour",
        1,
        "two_columns",
        _side_by_side,
        ["two_captions"],
        "Side by Side",
        Recipe(
            "two_columns",
            (_WILD, _WILD),
            brief="The species in two photos side by side: two stages of its life, or two of its moods, the second "
            "the punchline",
            hints={
                "title": _TITLE_HINT,
                "caption_1": f"the first stage or mood, {_FEW_WORDS}",
                "caption_2": f"the second, the punchline, {_FEW_WORDS}",
            },
        ),
    ),
    _part(
        "behaviour",
        0.9,
        "cycle",
        _day,
        ["cycle"],
        "A Day in the Life",
        Recipe(
            "cycle",
            brief="A day in the life of the species, as a cycle: three to five things it does, the last leading back "
            "to the first",
            hints={
                "title": _TITLE_HINT,
                **{f"step_{index}": f"a thing it does, {_FEW_WORDS}" for index in range(1, 6)},
            },
        ),
    ),
    # The rare sighting
    _part(
        "sighting",
        1.5,
        "full_image",
        _rare_sighting,
        ["full_image"],
        "Rare Sighting",
        Recipe(
            "full_image",
            (_SIGHTING,),
            brief="A rare sighting: an odd photo of the species, filling the slide, as the crew's first footage of it",
            hints={"title": f"what the narrator says about it, {_HUSHED}"},
        ),
    ),
    _part(
        "sighting",
        0.8,
        "news_headline",
        _sighting_news,
        ["news"],
        "Sighting in the News",
        Recipe(
            "news_headline",
            (_SIGHTING,),
            brief="The news of a rare sighting of the species, as a nature paper reports it, with its photo",
            hints={
                "outlet": "the made-up name of a nature paper or channel",
                "headline": "the headline: the sighting, as big news",
                "subheadline": "a line under it: what an expert or a witness says",
            },
        ),
    ),
    # The ritual
    _part(
        "ritual",
        1.3,
        "full_image",
        _ritual,
        ["full_image"],
        "Ancient Ritual",
        Recipe(
            "full_image",
            (_RITUAL,),
            brief="The species' ancient ritual, in an odd photo filling the slide, under the narrator's line about it",
            hints={"title": f"the narrator's line about the ritual, {_HUSHED}"},
        ),
    ),
    _part(
        "ritual",
        1,
        "process",
        _dance,
        ["process"],
        "Courtship Dance",
        Recipe(
            "process",
            brief="The species' courtship dance, or the ritual by which it greets another, step by step, the last "
            "step the punchline; for all ages",
            hints={
                "title": _TITLE_HINT,
                **{f"step_{index}": "a step of the dance, in two to five words" for index in range(1, 6)},
            },
            variants=(
                Variant(1, frozenset({"step_4", "step_5"}), "in three steps"),
                Variant(1, frozenset({"step_5"}), "in three or four steps"),
                Variant(1, note="in three to five steps"),
            ),
        ),
    ),
    # The threat
    _part(
        "threat",
        1.1,
        "big_number",
        _left,
        ["big_number"],
        "Left in the Wild",
        Recipe(
            "big_number",
            (cg.backdrop_generator,),
            brief="How few of the species are left in the wild, as one big number",
            hints={
                "title": _TITLE_HINT,
                "number": "how many are left: a small number",
                "label": "what it counts, without the number itself",
                "source": "a made-up, unreliable source for the count",
            },
            variants=pictured((), "background", BIG_NUMBER_PICTURES),
        ),
        repeats=3,
    ),
    _part(
        "threat",
        0.9,
        "chart_trend",
        _fewer,
        ["trend_chart", "chart"],
        "Fewer Every Year",
        Recipe(
            "chart_trend",
            brief="The species' numbers over the years, falling, with the moment it all went wrong: something "
            "harmless and everyday arriving, told as a disaster",
            hints={
                "title": "the chart's claim about the species' numbers",
                "shape": "how the line goes: falling, or crash",
                "line": "the species",
                "event": "the moment it all went wrong, marked on the line",
            },
            omit=frozenset({"second_line", "second_shape"}),
        ),
    ),
    _part(
        "threat",
        1,
        "statement",
        _danger,
        ["statement"],
        "Danger",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The danger the species faces, over a photo: something harmless and everyday, told as a grave threat",
            hints={"text": "the danger, as the narrator tells it, in one or two short sentences"},
        ),
    ),
    # The closing
    _part(
        "closing",
        1,
        "statement",
        _reflection,
        ["statement"],
        "Closing Reflection",
        Recipe(
            "statement",
            (_BACKDROP,),
            brief="The narrator's closing reflection on the species, over a calm photo, as the documentary ends",
            hints={"text": "the narrator's last reflection, in one or two short sentences, hushed and a bit too deep"},
        ),
    ),
    _part(
        "closing",
        1.2,
        "full_image",
        _farewell,
        ["full_image"],
        "Farewell",
        Recipe(
            "full_image",
            (_SUNSET,),
            brief="The documentary's last shot: the species at sunset, filling the slide, under the narrator's "
            "farewell, or what next time's episode is about",
            hints={"title": f"the narrator's farewell, or next time's episode, {_HUSHED}"},
        ),
    ),
    _part(
        "closing",
        0.7,
        "dare",
        _hush,
        ["dare"],
        "Stay Very Still",
        Recipe(
            "dare",
            brief="The documentary's last moment, as audience participation: the narrator hushes the whole room, as if "
            "the species were right there and might be scared off",
            hints={
                "audience": "what everyone in the room does, whispered to them: keep very still and quiet, for the "
                "species is close"
            },
            omit=frozenset({"dare"}),
            facts=False,
        ),
        repeats=1,
    ),
]

# The format's other slides, for its free slides (and to stand in for a part's slide that none of the part's
# generators can make): memes most of all (D63), full-screen photos and deep questions over them, which a talk may have
# any number of (so the free slides of a long one, without fair use too, never run out), gifs, and a quiz of its own
_OTHERS: Final = {
    "Meme": 1.6,
    "Full Screen Neutral Images": 1.2,
    "Full Screen Pixabay Deep": 1,
    "Full Screen Gif": 0.9,
}

GENERATORS: Final = [
    *_GENERATORS,
    *(
        slide_generators.get(name).weighted(Free(ARC, weight), f"{name} (Documentary)")
        for name, weight in _OTHERS.items()
    ),
    SlideGeneratorData(
        KindSlideGenerator("quiz", _spot_the_species),
        weight_function=Free(ARC, 0.7),
        retries=3,
        allowed_repeated_elements=1,
        tags=["quiz"],
        name="Spot the Species (Documentary)",
        llm=Recipe(
            "quiz",
            brief="A quiz for the audience about the species: which of some ordinary things is really it, what it "
            "eats, how long it sleeps, or what sound it makes",
            hints={
                "question": "the quiz question, about the species",
                "explanation": "why that's the answer, as the narrator would whisper it",
            },
        ),
    ),
    provocation(PACK, ARC, 1.2, _variables, "Documentary", "as a nature documentary's narrator whispers them"),
]
for _generator in GENERATORS:
    slide_generators.register(_generator.name or "", _generator, group=PACK)

# How many slides of a tag a documentary may have (see presentation_schema.most_slides): each kind once, but for the
# narrator's lines, as many as its opening, its threat and its closing may have (full-bleed photos aren't capped, as the
# TED-like talks' aren't), and the free slides' caps of the TED-like talks
CAPS: Final = {
    **{tag: cap for tag, cap in default_max_allowed_tags.items() if tag not in ("diagram", "chart", "statement")},
    "statement": 3,
    "single_image": 1,
    "two_captions": 1,
    "three_captions": 1,
    "process": 1,
    "big_number": 1,
    "provocation": 0.1,
}
