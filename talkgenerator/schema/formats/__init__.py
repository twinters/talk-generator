"""Talk formats beyond the TED-like talks (docs/v5-plan.md, section 7; decisions D56 and D59).

A format is a presentation schema (talkgenerator.schema.presentation_schema) with a Format: what the format is, for the
language model (its brief: "a startup pitch to investors..."), what its titles and its presenter's job are like, how
likely each persona is to present it, the theme families its talks are in more often, and its arc (see arcs): the parts
its talks go through, in order, each made by slide generators of its own. Every slide generator has a recipe for the
language model and a classic way, from the format's content pack (talkgenerator/data/packs/<format>: see
talkgenerator.sources.packs), so a format works without a language model too.

Each format has a module here, with its arc, its slide generators and its tag caps, which
talkgenerator.schema.presentation_schema_types registers: `pitch` (a startup pitch to investors), `academic` (a talk
at an academic conference), `corporate` (a company's all-hands, or its quarterly business review) and `keynote` (a
product keynote on a big stage). Another format would follow the same pattern: a module with a Format and its slide
generators, a content pack, a line in plan.external.FORMATS, and the schema registered.

A format's slides reuse the slide types there are (a big number for a pitch's ask, a funnel for its market, a 2×2
matrix for its competition; charts for an academic talk's results, an iceberg for its limitations; KPI tiles against
their targets and a new org chart for an all-hands; a fake error message for a keynote's demo), with recipes and
classic texts of their own: KindSlideGenerator makes a classic slide of a kind from texts, as a planned slide is made
from the language model's (talkgenerator.plan.kinds).
"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final

from talkgenerator.datastructures.slide_generator_data import SlideGeneratorData
from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import KINDS, PROBLEM_ANGLES, PROBLEM_BEHIND, Recipe, box_picture_slot
from talkgenerator.plan.languages import ENGLISH
from talkgenerator.schema import content_generators as cg
from talkgenerator.schema.formats.arcs import Arc, Free
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import packs

# (how often a format's big numbers and KPI tiles have a picture behind them, as the TED-like talks' do: D63)
from talkgenerator.sources.slide_texts import BIG_NUMBER_PICTURES as BIG_NUMBER_PICTURES
from talkgenerator.sources.slide_texts import KPI_PICTURES as KPI_PICTURES
from talkgenerator.util import language_util, random_util

# What a classic generator of a kind of slide makes: the slide's texts, by the kind's text fields (None where it has
# none), and its images, by the kind's image slots (what the slide's image slots found)
Made = tuple[Mapping[str, str | None], Mapping[str, Any]]
Content = Callable[[dict[str, Any]], Made | None]


@dataclass(frozen=True)
class Format:
    """What a talk format is, besides its slides (see the module's documentation)."""

    # What the format is, for the language model, on the request's "The format:" line
    brief: str
    # What its titles are like, for a title the model makes up (with the persona's, if the talk has one)
    title_hint: str = ""
    # What the presenter's job on its title slide is, for the model (with the persona's)
    job_hint: str = ""
    # Weights over the personas, for a talk whose persona the seed picks (1 for those it doesn't name)
    personas: Mapping[str, float] = field(default_factory=dict)
    # Multipliers on the theme families' weights, for a talk whose theme the seed picks (with the persona's)
    themes: Mapping[str, float] = field(default_factory=dict)
    arc: Arc | None = None
    # The kind of its closer, the slide after its talks' last (D76: one of talkgenerator.closers.KINDS); the TED-like
    # talk's ("Thank you!") for a format without one of its own
    closer: str = "ted"


def multiplied(*multipliers: Mapping[str, float] | None) -> dict[str, float] | None:
    """The multipliers of several (a persona's and a format's), multiplied by name; None if none has any."""
    names = {name for factors in multipliers if factors for name in factors}
    if not names:
        return None
    product: dict[str, float] = {}
    for name in sorted(names):
        value = 1.0
        for factors in multipliers:
            value *= (factors or {}).get(name, 1.0)
        product[name] = value
    return product


class KindSlideGenerator(slide_generator_types.SlideGenerator):
    """A classic slide of a kind (talkgenerator.plan.kinds): its texts and images from a content generator, built by
    the kind's builder, as a planned slide is from the language model's. None when the content repeats too much of
    what the talk used already, or the slide misses something (its builder turns it down, or it lacks an image)."""

    def __init__(self, kind: str, content: Content):
        if kind not in KINDS:
            raise ValueError(f"there's no slide kind {kind!r}")
        super().__init__(content)
        self.kind = kind

    @property
    def slide_type(self) -> type[slides.Slide]:
        return slides.Slide

    def generate_slide(self, presentation_context: dict[str, Any], used: Any) -> tuple[slides.Slide, list] | None:
        made = self._slide_content_generator(presentation_context)
        if made is None:
            return None
        texts, images = made
        images = {**images, **self._box_pictures(presentation_context, texts)}
        generated = [value for value in (*texts.values(), *images.values()) if value is not None]
        if not slide_generator_types.is_different_enough(generated, used):
            return None
        try:
            slide = KINDS[self.kind].build(texts, images, ENGLISH)
        except ValueError:  # (what a builder turns down: a ranking of fewer than three bars, say)
            return None
        if slide.missing_content():
            return None
        return slide, generated

    def _box_pictures(self, presentation_context: dict[str, Any], texts: Mapping[str, str | None]) -> dict[str, Any]:
        """The pictures of a diagram's boxes, now and then, as a planned diagram of its kind has them (see
        talkgenerator.plan.kinds.BoxPictures): those of the boxes the dice pick (of those with a text), each a
        picture about its box's text, by its slot."""
        pictures = KINDS[self.kind].pictures
        if pictures is None or presentation_context.get(slides.STANDING_IN):  # (standing in: no lookups, D73)
            return {}
        boxes = [box for box in pictures.boxes if texts.get(box)]
        found = {}
        for box in slides.picked_boxes(boxes, pictures.most, pictures.odds):
            image = box_picture_slot()({**presentation_context, "seed": texts[box]})
            if image is not None:
                found[pictures.slot(box)] = image
        return found


@cache
def _rules(format_name: str, rule: str) -> Callable[[dict[str, Any]], str | None]:
    generate: Callable[[dict[str, Any]], str | None] = packs.pack(format_name).tracery(rule)
    return generate


def text(format_name: str, rule: str, variables: Mapping[str, Any]) -> str | None:
    """A text of a rule of the format's pack ("ask.ask_title"), filled in with the variables, from the current random
    stream (None if no template of it fills in)."""
    filled = _rules(format_name, rule)(dict(variables))
    return str(filled) if filled else None


def words(format_name: str, rule: str) -> list[str]:
    """A rule's templates, as they are (a list of words, such as the amounts a startup raises)."""
    return list(packs.pack(format_name).rule(rule))


@cache
def _template(format_name: str, grammar: str, template: str) -> Callable[[dict[str, Any]], str | None]:
    """A generator of one template's texts, its rules expanded with its grammar's (as tracery does)."""
    from talkgenerator.sources import text_generator  # (here: it loads the text sources)

    rules = {**packs.pack(format_name).grammar(grammar), "_template": [template]}
    generate: Callable[[dict[str, Any]], str | None] = text_generator.TraceryTextGenerator(rules, "_template").generate
    return generate


def different(format_name: str, rule: str, variables: Mapping[str, Any], count: int) -> list[str]:
    """That many texts of a rule, each from a template of its own (fewer, if it hasn't as many that fill in), in an
    order the current random stream picks: the items of a list, say, none twice."""
    grammar = rule.partition(".")[0]
    templates = list(dict.fromkeys(packs.pack(format_name).rule(rule)))
    found: list[str] = []
    for template in random_util.sample(templates, len(templates)):
        if len(found) == count:
            break
        filled = _template(format_name, grammar, template)(dict(variables))
        if filled and str(filled) not in found:
            found.append(str(filled))
    return found


def photos(slot: ImageSlot, context: Mapping[str, Any], count: int, avoid: Sequence[Any] = ()) -> list[Any]:
    """That many different images for the slide's seed from an image slot (see talkgenerator.images.slots), each
    unlike the ones before it and the ones to avoid (None where none is found)."""
    found: list[Any] = []
    for _ in range(count):
        others = [image for image in (*avoid, *found) if image is not None]
        found.append(slot.find(str(context.get("seed")), avoid=others))
    return found


def behind(context: Mapping[str, Any], share: float) -> dict[str, Any]:
    """The images of a classic big number or KPI tiles: a picture of the slide's seed behind them (the backdrop look's,
    see talkgenerator.schema.content_generators.backdrop_generator), that share of the time, as the current random
    stream decides (D63); none when none is found."""
    if random_util.random() >= share:
        return {}
    picture = cg.backdrop_generator(dict(context))
    return {"background": picture} if picture is not None else {}


def provocation(
    format_name: str,
    arc: Arc,
    weight: float,
    variables: Callable[[dict[str, Any]], dict[str, Any]],
    named: str,
    voice: str,
) -> SlideGeneratorData:
    """A free slide of the format's own (D63): a striking or weird picture of the slide's topic filling it (the
    backdrop look's: stock photos most often, now and then a weird one from Reddit, a space photograph, an old one or
    a painting), with a provocative word or two over it, in the format's voice (its pack's free.provocation: "Disrupt."
    in a pitch, "Peer reviewed." in an academic talk), as the user asked for "more odds on random full-slide images
    ... with like random provoking (relevant?) word" after reviewing 35 talks. Named "Provocation (<named>)", tagged
    provocation (a format's caps keep it to one slide in ten)."""
    image = cg.provocation_image_generator

    def content(context: dict[str, Any]) -> Made | None:
        title = text(format_name, "free.provocation", variables(context))
        return ({"title": title}, {"image": image(context)}) if title else None

    return SlideGeneratorData(
        KindSlideGenerator("full_image", content),
        weight_function=Free(arc, weight),
        retries=3,
        allowed_repeated_elements=1,
        tags=["full_image", "provocation"],
        name=f"Provocation ({named})",
        llm=Recipe(
            "full_image",
            (image,),
            brief="A dramatic pause between the talk's parts: a striking or weird picture of the concept, filling the "
            "slide, under a provocative word or two",
            hints={"title": f"one or two provocative words, {voice}, ending in a full stop or a question mark"},
        ),
    )


def maybe(chance: float, value: str | None) -> str | None:
    """The value, that share of the time (from the current random stream)."""
    return value if random_util.random() < chance else None


# THE PROBLEM SLIDE (docs/v5-plan.md, D69): a classic one, from a pack's rules of problems (a pitch's in its "problem"
# grammar, an academic talk's in "motivation", a TED-like talk's in the TED pack's "problem"): an angle the slide's
# dice pick, as a planned slide's variant does (talkgenerator.plan.kinds.PROBLEM_ANGLES), whose rule's templates are
# the problem and the line under it ("...|..."), under a heading of the pack's, with a picture of it behind the
# problem, or one beside it that shows it. A real problem is a wikiHow how-to about the seed ("{seed.wikihow_action}"),
# when there's one
PROBLEM_LINES: Final = 0.8  # of the classic problem slides with a line under the problem


def problem(
    format_name: str,
    rules: Mapping[str, str],
    variables: Mapping[str, Any],
    context: Mapping[str, Any],
    pictures: tuple[Callable[[dict[str, Any]], Any], Callable[[dict[str, Any]], Any]],
    weights: Mapping[str, float] | None = None,
) -> Made | None:
    """A classic problem slide's texts and picture, from the pack's rules (by name: the heading's, "kicker", and the
    problems' of every angle), with the variables: the angle the slide's dice pick by weight (PROBLEM_ANGLES' weights
    times these; another, when none of its templates fills in), and a picture from the first source (behind the
    problem, PROBLEM_BEHIND of the time) or from the second (beside it). The slide goes without a picture when its
    source finds none."""
    left = {
        name: weight * (weights or {}).get(name, 1.0)
        for name, (weight, _, _) in PROBLEM_ANGLES.items()
        if weight * (weights or {}).get(name, 1.0) > 0
    }
    filled = None
    while left and not filled:
        angle = random_util.weighted_random([(weight, name) for name, weight in left.items()]) or next(iter(left))
        del left[angle]
        filled = text(format_name, rules[angle], variables)
    kicker = text(format_name, rules["kicker"], variables)
    if not filled or not kicker:
        return None
    stated, _, line = filled.partition("|")
    texts = {"kicker": kicker, "problem": stated.strip(), "detail": maybe(PROBLEM_LINES, line.strip() or None)}
    behind = random_util.random() < PROBLEM_BEHIND
    picture = pictures[0 if behind else 1](dict(context))
    return texts, {"background" if behind else "photo": picture}


def _stable(text: str, choices: Sequence[str]) -> str:
    """One of the choices for a text, always the same one (a hash that's the same in every run)."""
    return choices[zlib.crc32(text.lower().encode("utf-8")) % len(choices)]


_LONGEST_NAME = 16  # (letters of a made-up name's word: with the longest form, 21 characters in all)


def _name_word(topic: str) -> str:
    """The topic as one capitalised word, for a made-up name: one of it ("penguin", for "penguins") in words without
    articles, joined ("TimeTravel"), or else its last word, when they'd be longer than 16 letters ("Intelligence", for
    "artificial intelligence")."""
    one = language_util.bare(topic) if topic.strip() else topic
    kept = [word for word in one.replace("-", " ").split() if word.lower() not in ("the", "a", "an")]
    cleaned = ["".join(letter for letter in word if letter.isalnum()) for word in kept]
    capitalised = [word[:1].upper() + word[1:] for word in cleaned if word]
    joined = "".join(capitalised)
    if len(joined) > _LONGEST_NAME and capitalised:
        joined = capitalised[-1]
    return joined[:_LONGEST_NAME] or "Topic"


# How a startup and a research method get their made-up names from a talk's topic (as the founders and researchers of
# talks would name them)
_STARTUP_FORMS = (
    "{}ly",
    "{}ify",
    "{}.ai",
    "{}Hub",
    "Get{}",
    "{} Labs",
    "{}Base",
    "{}Pal",
    "{}Stack",
    "{}io",
    "{}Flow",
    "Open{}",
)
_METHOD_FORMS = ("{}Net", "Deep{}", "{}Former", "{}GAN", "Auto{}", "{}2Vec", "{}-Flow", "{}LM", "Neural{}", "{}-X")


def startup(topic: str) -> str:
    """The made-up name of a pitch's startup, from the talk's topic: the same on every slide (and in every run)."""
    word = _name_word(topic)
    form = _stable(topic, _STARTUP_FORMS)
    return form.format(word[:-1] if form == "{}ly" and word.endswith("ly") else word)


def method(topic: str) -> str:
    """The made-up name of an academic talk's method, from the talk's topic: the same on every slide."""
    return _stable(topic, _METHOD_FORMS).format(_name_word(topic))


# How a company and a product get their made-up names from a talk's topic, as a corporation and a keynote would name
# them (at most 9 and 7 characters around the topic's word: "PenguinCo", "Global Penguin"; "Penguin Pro", "HyperPenguin")
_COMPANY_FORMS = (
    "{} Corp",
    "{} Group",
    "{}Co",
    "{} Inc.",
    "{} Holdings",
    "Global {}",
    "United {}",
    "{} Systems",
    "{} Partners",
    "{} Works",
)
_PRODUCT_FORMS = (
    "{} Pro",
    "{} One",
    "{} X",
    "{} Air",
    "{} Max",
    "{} Ultra",
    "{}OS",
    "{} 2",
    "Hyper{}",
    "{} Neo",
    "{} Studio",
)


def company(topic: str) -> str:
    """The made-up name of the company whose all-hands it is, from the talk's topic: the same on every slide."""
    return _stable(topic, _COMPANY_FORMS).format(_name_word(topic))


def product(topic: str) -> str:
    """The made-up name of the product that a keynote launches, from the talk's topic: the same on every slide."""
    return _stable(topic, _PRODUCT_FORMS).format(_name_word(topic))
