"""Asking a language model for a talk's plan (docs/v5-plan.md, sections 5.2 and 5.3).

Python picks the slides (see PresentationSchema); the model writes what goes on them, in one request. The response is
one JSON object, whose schema is built for this talk's slides: its spine (title, the presenter's job, the thesis)
first, then one property per slide, in order, so the slides can be read while the model writes them. Seeded
"dice" (a persona for the presenter and an angle on the topic) make every seed give its own talk, where current
models take no sampling temperature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from talkgenerator.llm.base import Message, TextRequest
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, PRESENTER_JOB, TALK_TITLE, Recipe, TextField
from talkgenerator.util import random_util

SYSTEM_PROMPT: Final = """\
You write the slides of talks for improv theatre, for formats such as PowerPoint karaoke and improvised TED talks. A \
performer presents your slides without having seen them before, and has to make them work: the fun is in watching \
them explain every slide as if they had planned it all.

So write slides that give the presenter something to work with, rather than finished jokes:
- Keep it short. Titles have a few words, captions one to four. No paragraphs, no bullet points, no explanations.
- Play it straight. Write like a confident expert giving a serious talk, however absurd the content. The audience \
laughs at the presenter making sense of it, not at puns on the slides.
- Leave gaps. A good slide raises a question the presenter has to answer: an odd juxtaposition, a suspiciously \
specific claim, something that needs backing up. Don't explain the joke, or the image.
- Build one talk. The slides follow one thread, the talk's thesis. Later slides call back to earlier ones (a running \
gag, a recurring character, a strange claim from before), and the conclusions call back to several of them.
- Wander and come back. Every slide gets a word to riff on, which may wander away from the topic: take it as a \
starting point (not as the slide's title), and tie it back to the talk's thread.
- Fit the slide. Write every field the way its description asks, within its length.
- Image search queries say what the image should show, in two to six plain English words, for stock photo and gif \
sites: concrete things rather than ideas ("a cat wearing sunglasses", not "coolness").

Never write:
- quotes attributed to real people (quotes on the slides belong to made-up people, or to no one),
- anything about real private persons, or the presenter's name (talkgenerator adds it),
- slurs, sexual content, or anything that mocks people for who they are,
- markup, emoji, hashtags, or placeholders in curly braces.

If the topic asks for something hateful or harmful, set "unsafe_topic" to true, and keep everything else short.
Answer with one JSON object in the shape you're given, and nothing else."""

_PERSONAS: Final = (
    "a world-leading expert who is slightly too passionate about the topic",
    "a startup founder who has pivoted eleven times",
    "a retired lighthouse keeper with strong opinions",
    "a motivational speaker who just lost a bet",
    "a scientist whose research was never peer reviewed",
    "an influencer with exactly 31 followers",
    "a professor who has studied this for forty years",
    "a former athlete turned philosopher",
    "a consultant who bills by the slide",
    "a time traveller trying not to give too much away",
    "a medieval historian who sees the Middle Ages in everything",
    "a life coach who is suspiciously calm",
)
_ANGLES: Final = (
    "the topic's hidden history",
    "why everyone gets the topic wrong",
    "how the topic will change the future",
    "the presenter's personal journey with the topic",
    "the economics of the topic that nobody talks about",
    "the topic as a metaphor for life",
    "a scientific breakthrough about the topic",
    "mastering the topic in five steps",
    "the dark side of the topic",
    "a love letter to the topic",
)


@dataclass(frozen=True, eq=False)
class PlannedSlide:
    """A slide the model writes: its place in the talk, and what to write."""

    number: int  # counted from 1
    generator: str  # the name of the slide generator it stands in for
    recipe: Recipe
    seed: str  # the word the slide starts from (from the schema's topic generator)

    @property
    def key(self) -> str:
        return f"slide_{self.number}"


def spine(language: str = "en") -> dict[str, str]:
    """The talk's spine, which the answer starts with: what to write in each of its fields."""
    name = languages.language(language).name
    return {
        # (Asked the other way around, as "safe_topic", the free models sometimes turned down harmless topics)
        "unsafe_topic": "true only if the topic asks for something hateful or harmful; false for every other topic, "
        "however odd",
        "thesis": "the talk's thesis, its absurd claim in one sentence (not shown)",
        "title": f"{TALK_TITLE.description}, in {name} (at most {TALK_TITLE.max_length} characters)",
        "presenter_job": f"{PRESENTER_JOB.description}, for the title slide, in {name} (at most "
        f"{PRESENTER_JOB.max_length} characters)",
    }


# What a slide is about: when its images can't be found, it's searched for instead
CONCEPT: Final = (
    "the slide's subject in two to five words, such as 'volcano worship in medieval Iceland' (not its kind)"
)


def talk_request(
    topics: list[str],
    planned: list[PlannedSlide],
    rng: random_util.Rng,
    language: str = "en",
    title: str | None = None,
) -> TextRequest:
    with random_util.use(rng.child("dice")):
        persona, angle = random_util.choice(_PERSONAS), random_util.choice(_ANGLES)
    topic = topics[0] + (f" (and {', '.join(topics[1:])})" if len(topics) > 1 else "")
    lines = [
        f"Topic: {topic}",
        f"Title: {title}" if title else "Title: come up with one",
        f"Language: write the title, the presenter's job and every slide in {languages.language(language).name}, and "
        "the image search queries in English",
        f"The presenter: {persona}",
        f"The angle: {angle}",
        "",
        "Write the talk as one JSON object. First its spine:",
        *(f"- {name}: {description}" for name, description in spine(language).items()),
        "",
        "Then every slide, in order (slide 1, the title slide, is made from the spine), each with its texts, a search "
        f"query for each of its images, and its concept: {CONCEPT}.",
    ]
    # The guidance per field is in the schema too, but not every model gets to read the schema's descriptions
    for slide in planned:
        brief = (slide.recipe.brief or KINDS[slide.recipe.kind].description).rstrip(".")
        lines += ["", f"{slide.key}: {brief}. A word to riff on: {slide.seed}"]
        lines += [f"- {text.name}: {field_description(slide.recipe, text)}" for text in slide.recipe.written_fields()]
        lines += [f"- {slot}_query: {_query_description(slot)}" for slot in slide.recipe.image_queries()]
    return TextRequest(
        purpose="talk plan",
        system=SYSTEM_PROMPT,
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=response_schema(planned, language),
        max_output_tokens=1000 + 300 * len(planned),
    )


def response_schema(planned: list[PlannedSlide], language: str = "en") -> dict[str, Any]:
    """The JSON Schema of the answer: every property required, nothing else allowed (as strict structured outputs
    want), the spine first and the slides in order."""
    properties: dict[str, Any] = {
        name: {"type": "boolean" if name == "unsafe_topic" else "string", "description": description}
        for name, description in spine(language).items()
    }
    for slide in planned:
        properties[slide.key] = slide_schema(slide.recipe)
    return _object(properties)


def slide_schema(recipe: Recipe) -> dict[str, Any]:
    properties: dict[str, Any] = {"concept": {"type": "string", "description": CONCEPT}}
    for text in recipe.written_fields():
        properties[text.name] = {"type": "string", "description": field_description(recipe, text)}
        if text.options:  # one of these words (or empty, when the field may stay empty)
            properties[text.name]["enum"] = [*text.options, *([""] if text.optional else [])]
    for slot in recipe.image_queries():
        properties[f"{slot}_query"] = {"type": "string", "description": _query_description(slot)}
    return _object(properties)


def field_description(recipe: Recipe, text: TextField) -> str:
    """What to write in a slide's text field: the recipe's hint, or else the field's own description, and its length
    (or the words it can be)."""
    if text.options:
        limit = "one of " + ", ".join(text.options) + (", or empty for any" if text.optional else "")
    else:
        limit = f"at most {text.max_length} characters" + (", or empty for none" if text.optional else "")
    return f"{recipe.hints.get(text.name, text.description)} ({limit})"


def _query_description(slot: str) -> str:
    name = slot.replace("_", " ")  # "image 1", "background", ...
    return f"an image search query for {name if name[-1].isdigit() else 'the ' + name}"


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def slide_plan(slide: PlannedSlide, value: Any) -> SlidePlan | None:
    """The plan of a slide, from its part of the model's answer (None if that isn't an object)."""
    if not isinstance(value, dict):
        return None
    texts = {
        text.name: value[text.name] for text in slide.recipe.written_fields() if isinstance(value.get(text.name), str)
    }
    queries = {
        slot: value[f"{slot}_query"]
        for slot in slide.recipe.image_queries()
        if isinstance(value.get(f"{slot}_query"), str)
    }
    concept = value.get("concept")
    return SlidePlan(
        kind=slide.recipe.kind,
        recipe=slide.generator,
        concept=concept if isinstance(concept, str) else "",
        texts=texts,
        images=queries,
    )
