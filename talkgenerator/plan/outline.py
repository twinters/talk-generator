"""How much a language model does for a talk: Basic, or Advanced, where it plans the talk before it writes it
(docs/v5-plan.md, D67).

At the Basic level, a talk a language model writes is one request (section 5.3): Python picks the slides and every
slide's word to riff on (a related thing that wanders away from the topic and back: see
talkgenerator.schema.slide_topic_generators), and the model writes the whole talk in one go. That's what
talkgenerator.com's free models do, whose daily quota counts requests.

At the Advanced level, the model first plans the talk, in a small request of its own (the outline): its thesis and a
running gag, and for every slide the word it riffs on (one of the words the talk's dice offer it, or a sharper one of
its own) and its idea, in a sentence: what the slide's joke is, and for a chart or a diagram what it measures,
compares or ranks, so that the relation itself is funny. Then it writes the talk as at the Basic level, with the
outline in the request, which says what each slide is to do. Two requests a talk: the outline, of a few hundred
tokens, and the talk, as long as at the Basic level. When the outline fails (an error, a refusal, the budget), the
talk is written as at the Basic level, from the dice's words.

The outline's answer, like the talk's, has its properties in alphabetical order (see talkgenerator.plan.prompt): its
spine, "about", first, then the slides by their keys.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from talkgenerator import settings
from talkgenerator.llm.base import Message, ProviderError, TextProvider, TextRequest
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS
from talkgenerator.plan.stream import ObjectReader
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.personas import Persona
    from talkgenerator.plan.prompt import PlannedSlide
    from talkgenerator.schema.formats import Format

logger = logging.getLogger("talkgenerator")

BASIC: Final = "basic"
ADVANCED: Final = "advanced"
LEVELS: Final = (BASIC, ADVANCED)
# What each level does, for the command line, the MCP server and the docs
DESCRIPTIONS: Final = {
    BASIC: "one request a talk: the model writes every slide from the word the talk's dice give it",
    ADVANCED: "two requests a talk: the model first plans it (a thesis, a running gag, and every slide's word and "
    "idea: what its joke is, what a chart measures or a diagram compares), then writes it",
}

PURPOSE: Final = "talk outline"  # (its ledger entries' purpose)
# How long a riff and an idea may be: a word or a few, and a short sentence
RIFF_LENGTH: Final = 40
IDEA_LENGTH: Final = 160

OUTLINE_SYSTEM_PROMPT: Final = """\
You plan talks for improv theatre, for formats such as PowerPoint karaoke and improvised TED talks: a performer \
presents slides they've never seen, and the fun is in watching them make it all make sense. You don't write the \
slides: you plan what each one does, so that the talk is clever, funny and about its topic.

- One thread: a thesis, an absurd claim that the talk argues as if it were obvious, and a running gag that comes \
back on two or three slides (their ideas say so).
- Every slide riffs on a word: one of the words it's offered (the talk's dice found them, wandering away from the \
topic: their surprise is the point), or a sharper one of your own. A thing, which a picture can show; never a word \
another slide has.
- Every slide has an idea: in one short sentence, the point it makes with its word, and how that serves the thesis: \
its claim, comparison or reveal. For a chart, what it measures against what (its axes), what it ranks or what its \
groups are; for a diagram, what its parts are. Make the relation the joke: specific, a little absurd, never random. \
Every slide makes a point of its own: the thesis from another side, not the same joke again.
- An idea is a plan for the writer, not the slide: no titles, captions or quotes in it, and no description of its \
pictures (they're searched for afterwards, and memes and gifs are what they are).
- Leave the punchlines to the presenter: an idea raises a question for them to answer, it doesn't explain the joke.

Never plan quotes of real people, anything about real private persons, slurs, sexual content, mockery of people for \
who they are, or statements about real-world politics, unless the topic is about them.
Answer with one JSON object in the shape you're given, and nothing else."""

SPINE: Final = "about"
_THESIS: Final = "the talk's thesis: its absurd claim, in one sentence"
_RUNNING_GAG: Final = (
    "the running gag: something that keeps coming back (a thing, a made-up person, a claim), in a few words"
)
_RIFF: Final = (
    f"the word the slide riffs on: one of its words, or a sharper one of your own (at most {RIFF_LENGTH} characters)"
)
_IDEA: Final = (
    "the slide's idea, in one short sentence: the point it makes with its word, for the thesis; for a chart or a "
    f"diagram, what it measures, ranks or compares; no texts for the slide (at most {IDEA_LENGTH} characters)"
)


def level(value: str | None) -> str:
    """The level a talk is made at: the one asked for (case and spaces don't matter), or else TALKGENERATOR_LLM_LEVEL's,
    or else BASIC. A ValueError for a level there isn't."""
    asked = (value or "").strip().lower() or settings.llm_level() or BASIC
    if asked not in LEVELS:
        raise ValueError(f"There's no language model level {asked!r}; there are {', '.join(LEVELS)}")
    return asked


@dataclass(frozen=True)
class SlideIdea:
    riff: str  # the word the slide riffs on
    idea: str  # what the slide does with it, in a sentence


@dataclass(frozen=True)
class Outline:
    """A talk as its language model planned it: the thesis, the running gag, and the slides' ideas by slide number
    (from 1: the slides it planned)."""

    thesis: str
    running_gag: str
    slides: Mapping[int, SlideIdea]


def outline_request(
    topics: Sequence[str],
    planned: Sequence[PlannedSlide],
    offers: Mapping[int, Sequence[str]],
    rng: random_util.Rng,
    language: str = languages.ENGLISH.code,
    title: str | None = None,
    persona: Persona | None = None,
    talk_format: Format | None = None,
) -> TextRequest:
    """The request for a talk's outline: its topic (and title, if it has one), the format and the persona as the
    talk's request has them, and every planned slide with what it is (its brief) and the words the dice offer it
    (offers, by slide number: its seed first, then the other words that would have done)."""
    topic = topics[0] + (f" (and {', '.join(topics[1:])})" if len(topics) > 1 else "")
    language_name = languages.language(language).name
    writes_in = "" if language == languages.ENGLISH.code else f" (the talk will be in {language_name})"
    lines = [
        f"Topic: {topic}",
        *([f"Title: {title}"] if title else []),
        f"Language: plan the talk in English{writes_in}",
        *([f"The format: {talk_format.brief}"] if talk_format is not None else []),
        *([f"The presenter: {persona.voice}", f"The angle: {persona.angle(rng)}"] if persona is not None else []),
        "",
        f"Plan the talk as one JSON object. First its spine, as an object called {SPINE}:",
        f"- thesis: {_THESIS}",
        f"- running_gag: {_RUNNING_GAG}",
        "",
        "Then every slide, in order (slide 1, the title slide, needs no plan), each with its riff and its idea.",
    ]
    for slide in planned:
        brief = (slide.recipe.brief or KINDS[slide.recipe.kind].description).rstrip(".")
        words = ", ".join(dict.fromkeys(word for word in offers.get(slide.number, (slide.seed,)) if word))
        lines += ["", f"{slide.key}: {brief}. Its words: {words or slide.seed}"]
    return TextRequest(
        purpose=PURPOSE,
        system=OUTLINE_SYSTEM_PROMPT,
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=response_schema(planned),
        max_output_tokens=400 + 120 * len(planned),
    )


def response_schema(planned: Sequence[PlannedSlide]) -> dict[str, Any]:
    """The JSON Schema of the outline's answer: its spine first, then the slides in order (alphabetical order too)."""
    spine = {"thesis": _string(_THESIS), "running_gag": _string(_RUNNING_GAG)}
    properties: dict[str, Any] = {SPINE: _object(spine)}
    for slide in planned:
        properties[slide.key] = _object({"riff": _string(_RIFF), "idea": _string(_IDEA)})
    return _object(properties)


def read_outline(answer: Mapping[str, Any], planned: Sequence[PlannedSlide]) -> Outline | None:
    """The outline in the model's answer (its properties, as far as they came in): the slides with a riff and an idea
    (a riff cut to a few words, an idea to a sentence or two), the others left to the dice. None when no slide has
    one."""
    found = answer.get(SPINE)
    spine: Mapping[str, Any] = found if isinstance(found, dict) else {}
    slides: dict[int, SlideIdea] = {}
    for slide in planned:
        value = answer.get(slide.key)
        if not isinstance(value, dict):
            continue
        riff, idea = _text(value.get("riff"), RIFF_LENGTH), _text(value.get("idea"), IDEA_LENGTH)
        if riff and idea:
            slides[slide.number] = SlideIdea(riff, idea)
    if not slides:
        return None
    return Outline(_text(spine.get("thesis"), IDEA_LENGTH), _text(spine.get("running_gag"), IDEA_LENGTH), slides)


def ask_for_outline(llm: TextProvider, request: TextRequest, planned: Sequence[PlannedSlide]) -> Outline | None:
    """The model's outline, or None when it has none (an error, a refusal, a budget that doesn't allow the request,
    an answer without a slide's plan): the talk is then written as at the Basic level."""
    try:
        response = llm.complete(request)
    except ProviderError as error:
        logger.warning("The language model didn't plan the talk (%s): it writes it from the dice's words", error)
        return None
    except Exception:  # (a misbehaving provider shouldn't sink the talk either)
        logger.exception("Asking the language model for the talk's outline crashed: it writes it from the dice's words")
        return None
    if response.finish == "refused":
        logger.warning("The language model declined to plan the talk: it writes it from the dice's words")
        return None
    answer = response.data if isinstance(response.data, dict) else _properties(response.text)
    outline = read_outline(answer, planned)
    if outline is None:
        logger.warning(
            "The language model's outline had no slide that could be read: the talk is written from the dice's words"
        )
    elif response.finish != "complete":
        logger.info(
            "The language model's outline was %s: the slides it didn't plan keep the dice's words", response.finish
        )
    return outline


def _properties(text: str) -> dict[str, Any]:
    """The properties of the JSON object in a text, as far as they're complete (an answer cut off keeps its first
    slides); none when it has no object."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return dict(ObjectReader().feed(text))


def _text(value: Any, length: int) -> str:
    """A text of the answer on one line, cut between words to its length (or empty, when it's no text)."""
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if len(text) <= length:
        return text
    return text[: length + 1].rsplit(" ", 1)[0].rstrip(",;:-–— ") or text[:length]


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
