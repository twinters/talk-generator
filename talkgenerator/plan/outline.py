"""How much a language model does for a talk: Basic, or Advanced, where it plans the talk before it writes it, and
then writes its slides in parallel (docs/v5-plan.md, D68).

At the Basic level, a talk a language model writes is one request (section 5.3): Python picks the slides and every
slide's word to riff on (a related thing that wanders away from the topic and back: see
talkgenerator.schema.slide_topic_generators), and the model writes the whole talk in one go. That's what
talkgenerator.com's free models do, whose daily quota counts requests.

At the Advanced level, the model first plans the talk, in a request of its own (the outline, outline_request): the
talk's spine, as a Basic talk's request has it (its title, the presenter's job, its thesis), a running gag, and for
every slide the word it riffs on (one of the words the talk's dice offer it, or a sharper one of its own) and its
idea, in a sentence: the point it makes, and for a chart or a diagram what it measures, compares or ranks, so that the
relation itself is funny. The outline is read while it's written, and its slides are written as soon as their ideas
are in, a few at a time (BATCHES: the second slide alone, so that the talk starts soon, then two, then three at a
time), each batch in a request of its own (writing_request), in parallel with the others: the plan holds the talk's
thread, so a slide needs no other slide's texts. A batch's request has the talk's spine and running gag in its system
prompt, and the plan so far. Measured with Claude Haiku on 2026-11-09, a slide to a request made Advanced talks start
and end as soon as Basic ones or sooner, but cost three and a half times as much: every request has the talk's system
prompt and the plan again, and none of it is cached (Claude caches what comes before the system prompt's end, which
starts with the request's schema, a slide's own). When the outline fails before its spine is in (an error, a refusal,
the budget, a topic it finds unsafe), the talk is written as a Basic one.

A talk's level is the one it asks for, or TALKGENERATOR_LLM_LEVEL's, or else default_level's: Advanced on a model of
your own that costs (Claude, OpenAI's models, Gemini's, your ChatGPT plan's, OpenRouter's paid ones), Basic on free
ones (whose free quotas count requests) and on any other.

The outline's answer, like the talk's, has its properties in alphabetical order (see talkgenerator.plan.prompt): its
spine, "about", first, then the slides by their keys.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from talkgenerator import settings
from talkgenerator.facts import request_line
from talkgenerator.llm import prices
from talkgenerator.llm.base import Message, TextProvider, TextRequest
from talkgenerator.plan import languages, prompt
from talkgenerator.plan.kinds import KINDS
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.facts import Given
    from talkgenerator.images.generation import ImageGeneration
    from talkgenerator.names import NameRequest
    from talkgenerator.personas import Persona
    from talkgenerator.plan.prompt import PlannedSlide
    from talkgenerator.schema.formats import Format
    from talkgenerator.titles import TitleRequest

logger = logging.getLogger("talkgenerator")

BASIC: Final = "basic"
ADVANCED: Final = "advanced"
LEVELS: Final = (BASIC, ADVANCED)
# The providers whose models cost their owner (an API key, a plan), where a talk is Advanced unless it asks otherwise
# (Gemini's too: its free tier is a key's, not a model's, and talkgenerator can't tell it from the paid one)
_PAID: Final = frozenset({"anthropic", "openai", "gemini", "chatgpt"})

PURPOSE: Final = "talk outline"  # (the outline's ledger entry's purpose)
SLIDE_PURPOSE: Final = "talk slide"  # (and a slide's, written as its idea comes in)
# How many of a talk's batches of slides are written at the same time at most, as their ideas come in
WRITERS: Final = 6
# How many slides a talk's first batches have (the second slide alone, for a talk that starts soon), and the others
BATCHES: Final = (1, 2, 3)
# How long a riff and an idea may be: a word or a few, and a short sentence
RIFF_LENGTH: Final = 40
IDEA_LENGTH: Final = 160
RUNNING_GAG: Final = "running_gag"

OUTLINE_SYSTEM_PROMPT: Final = """\
You plan talks for improv theatre, for formats such as PowerPoint karaoke and improvised TED talks: a performer \
presents slides they've never seen, and the fun is in watching them make it all make sense. You plan what each slide \
does, so that the talk is clever, funny and about its topic; the slides are written afterwards, from your plan.

- One thread: a thesis, an absurd claim that the talk argues as if it were obvious, and a running gag that comes \
back on two or three slides (their ideas say so). The talk's spine (its title, the presenter's made-up job) fits it.
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

Never plan quotes attributed to real people, anything about real private persons, slurs, sexual content, mockery of \
people for who they are, or statements about real-world politics, unless the topic is about them.
If the topic asks for something hateful or harmful, set "unsafe_topic" to true, and keep everything else short.
Answer with one JSON object in the shape you're given, and nothing else."""

# What a batch's request says of the plan (in its system prompt, after the talk's own)
_WRITING: Final = """\
The talk is planned: every slide has its word to riff on and its idea, and the slides are written a few at a time, \
from the plan, which holds the talk's thread. Write the slides you're asked for so that their ideas land, in words of \
your own: an idea is a plan, not a text, so never copy its words onto a slide; write titles and captions as the \
fields ask, and call back to earlier slides by what they're about."""

_RUNNING_GAG_DESCRIPTION: Final = (
    "the running gag: something that keeps coming back (a thing, a made-up person, a claim), in a few words"
)
_RIFF: Final = (
    f"the word the slide riffs on: one of its words, or a sharper one of your own (at most {RIFF_LENGTH} characters)"
)
_IDEA: Final = (
    "the slide's idea, in one short sentence: the point it makes with its word, for the thesis; for a chart or a "
    f"diagram, what it measures, ranks or compares; no texts for the slide (at most {IDEA_LENGTH} characters)"
)


def _riff(language: str) -> str:
    """What to write for a slide's riff: in a talk in another language than English, in that language, as the slide's
    writer then needn't say an English word in it (D74: "redevelopment" became "geherontwikkeld" on a Dutch slide)."""
    if language == languages.ENGLISH.code:
        return _RIFF
    name = languages.language(language).name
    return (
        f"the word the slide riffs on, in {name}: one of its words (an English one said in {name}, as a {name} speaker "
        f"would say it), or a sharper one of your own (at most {RIFF_LENGTH} characters)"
    )


def level(value: str | None, model: TextProvider | None = None) -> str:
    """The level a talk is made at: the one asked for (case and spaces don't matter), or else TALKGENERATOR_LLM_LEVEL's,
    or else the model's default (default_level). A ValueError for a level there isn't."""
    asked = check(value) or check(settings.llm_level())
    return asked or default_level(model)


def check(value: str | None) -> str | None:
    """The level a value names (case and spaces don't matter), or None for none; a ValueError for a level there isn't."""
    asked = (value or "").strip().lower()
    if asked and asked not in LEVELS:
        raise ValueError(f"There's no language model level {asked!r}; there are {', '.join(LEVELS)}")
    return asked or None


def default_level(model: TextProvider | None) -> str:
    """Advanced on a model of your own that costs, every model that may answer for it (a paid OpenRouter model's
    fallbacks too): Claude, OpenAI's models, Gemini's (also on its free tier, which talkgenerator can't tell from the
    paid one: ask for Basic there), your ChatGPT plan's (which counts toward your plan's usage) and OpenRouter's paid
    models. Basic on free models (OpenRouter's free models and its free router, whose free quotas count requests, and
    which are slow), and on any other (a replayed talk, a test's)."""
    models = model.possible_models() if model is not None else ()
    return ADVANCED if models and all(_paid(spec) for spec in models) else BASIC


def _paid(spec: str) -> bool:
    provider = spec.split(":", 1)[0]
    if provider == "openrouter":
        return prices.price_of(spec) != prices.FREE
    return provider in _PAID


@dataclass(frozen=True)
class SlideIdea:
    riff: str  # the word the slide riffs on
    idea: str  # the point it makes with it, in a sentence


@dataclass(frozen=True)
class Outline:
    """A talk as its language model planned it: the thesis, the running gag, and the slides' ideas by slide number
    (from 1: the slides it planned)."""

    thesis: str
    running_gag: str
    slides: Mapping[int, SlideIdea]


def outline_request(
    topics: list[str],
    planned: Sequence[PlannedSlide],
    offers: Mapping[int, Sequence[str]],
    rng: random_util.Rng,
    language: str = languages.ENGLISH.code,
    title: str | None = None,
    name: NameRequest | None = None,
    typed: TitleRequest | None = None,
    persona: Persona | None = None,
    talk_format: Format | None = None,
) -> TextRequest:
    """The request for a talk's outline: what a Basic talk's request says of the talk (its topic or what was typed, the
    format and the persona), its spine to write as a Basic talk's request has it (prompt.spine: the title, the
    presenter's job and made-up name, the thesis, the unsafe flag), a running gag, and for every planned slide what it
    is (its brief) and the words the dice offer it (offers, by slide number: its seed first, then the others that
    would have done), for its riff and its idea. In a talk in another language than English, the riffs are in that
    language too (English words offered say they're English: D74), and the ideas in English."""
    fields = _spine_fields(language, title, name, typed, persona, talk_format)
    language_name = languages.language(language).name
    other = language != languages.ENGLISH.code
    plans_in = f", every slide's riff in {language_name} too, and its idea in English" if other else ""
    lines = [
        *prompt.header(
            topics,
            rng,
            f"{prompt.spine_language(language, name, typed)} in {language_name}{plans_in}",
            title,
            typed,
            persona,
            talk_format,
            language=language,
        ),
        "",
        f"Plan the talk as one JSON object. First its spine, as an object called {prompt.SPINE}:",
        *(f"- {field}: {description}" for field, description in fields.items()),
        "",
        "Then every slide, in order (slide 1, the title slide, is made from the spine), each with its riff and its idea.",
    ]
    for slide in planned:
        brief = (slide.recipe.brief or KINDS[slide.recipe.kind].description).rstrip(".")
        words = ", ".join(dict.fromkeys(word for word in offers.get(slide.number, (slide.seed,)) if word))
        marked = " (English)" if slide.english and other else ""
        lines += ["", f"{slide.key}: {brief}. Its words{marked}: {words or slide.seed}"]
    return TextRequest(
        purpose=PURPOSE,
        system=OUTLINE_SYSTEM_PROMPT,
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=_outline_schema(fields, planned, language),
        max_output_tokens=600 + 120 * len(planned),
    )


def _spine_fields(
    language: str,
    title: str | None,
    name: NameRequest | None,
    typed: TitleRequest | None,
    persona: Persona | None,
    talk_format: Format | None,
) -> dict[str, str]:
    """The outline's spine: a Basic talk's (prompt.spine, as its request has it), and the running gag."""
    hint = prompt.title_hint(persona, title, typed, talk_format)
    job = prompt.job_hint(persona, talk_format)
    return {**prompt.spine(language, name, typed, hint, job, bool(title)), RUNNING_GAG: _RUNNING_GAG_DESCRIPTION}


def _outline_schema(
    fields: Mapping[str, str], planned: Sequence[PlannedSlide], language: str = languages.ENGLISH.code
) -> dict[str, Any]:
    """The JSON Schema of the outline's answer: its spine first, then the slides in order (alphabetical order too)."""
    spine = {
        field: {"type": "boolean" if field == "unsafe_topic" else "string", "description": description}
        for field, description in fields.items()
    }
    properties: dict[str, Any] = {prompt.SPINE: _object(spine)}
    for slide in planned:
        properties[slide.key] = _object({"riff": _string(_riff(language)), "idea": _string(_IDEA)})
    return _object(properties)


def read_idea(value: Any) -> SlideIdea | None:
    """A slide's riff and idea in the outline's answer (a riff cut to a few words, an idea to a sentence or two), or
    None when either is missing."""
    if not isinstance(value, dict):
        return None
    riff, idea = _text(value.get("riff"), RIFF_LENGTH), _text(value.get("idea"), IDEA_LENGTH)
    return SlideIdea(riff, idea) if riff and idea else None


def batch_size(batch: int) -> int:
    """How many slides a talk's batch has at most (counted from 0: see BATCHES)."""
    return BATCHES[min(batch, len(BATCHES) - 1)]


def writing_request(
    topics: list[str],
    slides: Sequence[PlannedSlide],
    planned: Sequence[PlannedSlide],
    spine: Mapping[str, Any],
    rng: random_util.Rng,
    language: str = languages.ENGLISH.code,
    persona: Persona | None = None,
    talk_format: Format | None = None,
    given: Mapping[int, Given] | None = None,
    generation: ImageGeneration | None = None,
) -> TextRequest:
    """The request for a batch of a planned talk's slides (slides, in order): the talk's own system prompt, with what
    the talk is (its topic, format and persona, its title, the presenter's job, its thesis and running gag: the spine,
    as the outline wrote it) and the plan's rules after it, the same for all of the talk's batches; and the plan of the
    slides before them (planned: the talk's slides with the words and ideas they have so far), then the slides to write,
    as a Basic talk's request asks for them (prompt.slide_lines), with their real facts (given, by slide number). The
    presenter's name, given or made up, never goes in."""
    language_name = languages.language(language).name
    talk = [
        *prompt.header(
            topics,
            rng,
            f"write every text of the slide in {language_name}, and the image search queries in English",
            persona=persona,
            talk_format=talk_format,
            language=language,
        ),
        *(f"The talk's {what}: {spine[field]}" for field, what in _TOLD.items() if _told(spine.get(field))),
    ]
    first = slides[0].number
    marked = language != languages.ENGLISH.code  # (an English word in a talk in another language says it's English)
    plan = [
        f"- {other.key}: {(other.recipe.brief or KINDS[other.recipe.kind].description).rstrip('.')}. Its word: "
        f"{other.seed}"
        + (" (English)" if marked and other.english else "")
        + (f". Its idea: {other.idea.rstrip('.')}" if other.idea else "")
        for other in planned
        if other.number < first
    ]
    facts = given or {}
    keys = ", ".join(slide.key for slide in slides)
    lines = [
        *(["The plan of the talk so far:", *plan, ""] if plan else []),
        *([request_line(language)] if any(slide.number in facts for slide in slides) else []),
        f"Write {keys} as one JSON object with a property for each ({keys}): an object of its texts, a search query "
        f"for each of its images, and its concept: {prompt.concept(language)}.",
    ]
    for slide in slides:
        lines += ["", *prompt.slide_lines(slide, language, facts.get(slide.number), generation)]
    prompts = sum(len(prompt.generated(slide.recipe, generation)) for slide in slides)
    return TextRequest(
        purpose=SLIDE_PURPOSE,
        system="\n\n".join([prompt.SYSTEM_PROMPT, "\n".join(talk), _WRITING]),
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=_object({slide.key: prompt.slide_schema(slide.recipe, generation, language) for slide in slides}),
        max_output_tokens=400 + 400 * len(slides) + 100 * prompts,
    )


# What a slide's request says of the talk's spine, by its field (never the presenter's name)
_TOLD: Final = {
    "title": "title",
    "presenter_job": "presenter",
    "thesis": "thesis",
    RUNNING_GAG: "running gag",
}


def _told(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
