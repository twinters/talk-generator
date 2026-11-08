"""Talk formats beyond the TED-like talks (docs/v5-plan.md, section 7; decision D56).

A format is a presentation schema (talkgenerator.schema.presentation_schema) with a Format: what the format is, for the
language model (its brief: "a startup pitch to investors..."), what its titles and its presenter's job are like, how
likely each persona is to present it, the theme families its talks are in more often, and its arc (see arcs): the parts
its talks go through, in order, each made by slide generators of its own. Every slide generator has a recipe for the
language model and a classic way, from the format's content pack (talkgenerator/data/packs/<format>: see
talkgenerator.sources.packs), so a format works without a language model too.

Each format has a module here, with its arc, its slide generators and its tag caps, which
talkgenerator.schema.presentation_schema_types registers: `pitch` (a startup pitch to investors) and `academic` (a talk
at an academic conference). The formats to come (a corporate all-hands, a product keynote, Pecha Kucha's timing) follow
the same pattern: a module with a Format and its slide generators, a content pack, a line in plan.external.FORMATS,
and the schema registered.

A format's slides reuse the slide types there are (a big number for a pitch's ask, a funnel for its market, a 2×2
matrix for its competition; charts for an academic talk's results, an iceberg for its limitations), with recipes and
classic texts of their own: KindSlideGenerator makes a classic slide of a kind from texts, as a planned slide is made
from the language model's (talkgenerator.plan.kinds).
"""

from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from talkgenerator.images.slots import ImageSlot
from talkgenerator.plan.kinds import KINDS
from talkgenerator.plan.languages import ENGLISH
from talkgenerator.schema.formats.arcs import Arc
from talkgenerator.slide import slide_generator_types, slides
from talkgenerator.sources import packs
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


def maybe(chance: float, value: str | None) -> str | None:
    """The value, that share of the time (from the current random stream)."""
    return value if random_util.random() < chance else None


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
