"""Asking a language model for a talk's plan (docs/v5-plan.md, sections 5.2 and 5.3).

Python picks the slides (see PresentationSchema); the model writes what goes on them, in one request. The response is
one JSON object, whose schema is built for this talk's slides: its spine (title, the presenter's job, the thesis, and
a made-up name for the presenter when nobody gave theirs: see talkgenerator.names) first, then one property per
slide, in order, so the slides can be read while the model writes them. Seeded "dice" make every seed give its own
talk, where current models take no sampling temperature: the talk's persona (see talkgenerator.personas), whose voice
the model writes in, with one of its angles on the topic and what its titles are like.

Some models write the properties in alphabetical order instead of the schema's (OpenRouter's free router often picks
one that does), so the answer's properties are in alphabetical order too: the spine is one object, called "about",
and the slides' numbers have as many digits as the last one's ("slide_02" to "slide_10").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from talkgenerator.images.generation import PROMPT_DESCRIPTION, prompt_field
from talkgenerator.llm.base import Message, TextRequest
from talkgenerator.models.plan import SlidePlan
from talkgenerator.names import NameRequest
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, PRESENTER_JOB, TALK_TITLE, Recipe, TextField
from talkgenerator.titles import TitleRequest
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.images.generation import ImageGeneration
    from talkgenerator.personas import Persona

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
- anything about real private persons, or the presenter's name on the slides (the title slide has it),
- slurs, sexual content, or anything that mocks people for who they are,
- markup, emoji, hashtags, or placeholders in curly braces.

If the topic asks for something hateful or harmful, set "unsafe_topic" to true, and keep everything else short.
Answer with one JSON object in the shape you're given, and nothing else."""


@dataclass(frozen=True, eq=False)
class PlannedSlide:
    """A slide the model writes: its place in the talk, and what to write."""

    number: int  # counted from 1
    generator: str  # the name of the slide generator it stands in for
    recipe: Recipe
    seed: str  # the word the slide starts from (from the schema's topic generator)
    digits: int = 1  # as many as the number of the talk's last slide has

    @property
    def key(self) -> str:
        """Its property in the answer: slide_2, or slide_02 in a talk of 10 slides or more, so that slide_10 doesn't
        come before slide_2 in alphabetical order."""
        return f"slide_{self.number:0{self.digits}d}"


# The property the answer's spine is in, which sorts before the slides' (see the module's documentation)
SPINE: Final = "about"


def spine(
    language: str = "en",
    name: NameRequest | None = None,
    typed: TitleRequest | None = None,
    title_hint: str | None = None,
    job_hint: str | None = None,
) -> dict[str, str]:
    """The talk's spine, which the answer starts with: what to write in each of its fields. With a name request, the
    presenter's name too, before their job (which then agrees with it). For what was typed, which could be the topic
    or the title (see talkgenerator.titles), the title as its request asks (with classic titles to pick, the model's
    own title, own_title, before the title it settles on). With a title hint (what the persona's titles are like, for a
    title the model makes up), the title the model makes up is to be like that; with a job hint (the persona's), the
    presenter's job too, in place of the job field's example."""
    language_name = languages.language(language).name
    fields = {
        # (Asked the other way around, as "safe_topic", the free models sometimes turned down harmless topics)
        "unsafe_topic": "true only if the topic asks for something hateful or harmful; false for every other topic, "
        "however odd",
        "thesis": "the talk's thesis, its absurd claim in one sentence (not shown)",
    }
    if typed is not None:
        fields.update(typed.fields(language, title_hint or ""))
    else:
        like = f", {title_hint}" if title_hint else ""
        fields["title"] = (
            f"{TALK_TITLE.description}{like}, in {language_name} (at most {TALK_TITLE.max_length} characters)"
        )
    agreeing = ""
    if name is not None:
        fields["name_plays_on"] = name.plays_on_description()
        fields["presenter_name"] = name.description(language)
        agreeing = ", agreeing with presenter_name (a Prof. is a professor of something, a Dr. a doctor)"
    job = f"the presenter's grand, made-up job: {job_hint}" if job_hint else PRESENTER_JOB.description
    fields["presenter_job"] = (
        f"{job}, for the title slide{agreeing}, in {language_name} (at most {PRESENTER_JOB.max_length} characters)"
    )
    return fields


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
    asked_again: bool = False,
    name: NameRequest | None = None,
    typed: TitleRequest | None = None,
    generation: ImageGeneration | None = None,
    persona: Persona | None = None,
) -> TextRequest:
    """The request for a talk (with the presenter's name, when there's a name request). Asked again, it says that a
    model found the topic unsafe: some of the free models get the flag wrong whichever way it's asked (one turned
    down "penguins"). For what was typed, which could be the topic or the title (see talkgenerator.titles), it says
    what the title is to be: what was typed, with its slips fixed, or a title of the model's own on it. In a talk
    that generates pictures (with a generation), the model writes a prompt for every image that prefers one.

    The talk's persona (see talkgenerator.personas) is who presents it: the model writes in its voice, on the angle
    the talk's dice pick among its angles, a title it makes up is like the persona's titles, and the presenter's job
    is the persona's kind of job. (Without one, the request has none of that: the talk is the format's own.)"""
    hint = title_hint(persona, title, typed)
    job = persona.job_hint if persona is not None else None
    topic = topics[0] + (f" (and {', '.join(topics[1:])})" if len(topics) > 1 else "")
    kept = " (the typed title keeps its words)" if typed is not None and typed.keep else ""
    lines = [
        *(
            typed.lines(topic)
            if typed is not None
            else [f"Topic: {topic}", f"Title: {title}" if title else "Title: come up with one"]
        ),
        f"Language: write the title{kept}, the presenter's {'name and ' if name is not None else ''}job and every "
        f"slide in {languages.language(language).name}, and the image search queries in English",
        *([f"The presenter: {persona.voice}", f"The angle: {persona.angle(rng)}"] if persona is not None else []),
        "",
        *(
            [
                "Asked again: a model said this topic asks for something hateful or harmful. Set unsafe_topic to true "
                "only if it plainly does; an odd, silly or everyday topic is fine.",
                "",
            ]
            if asked_again
            else []
        ),
        f"Write the talk as one JSON object. First its spine, as an object called {SPINE}:",
        *(f"- {field}: {description}" for field, description in spine(language, name, typed, hint, job).items()),
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
        lines += [f"- {prompt_field(slot)}: {about}" for slot, about in generated(slide.recipe, generation)]
    prompts = sum(len(generated(slide.recipe, generation)) for slide in planned)
    return TextRequest(
        purpose="talk plan",
        system=SYSTEM_PROMPT,
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=response_schema(planned, language, name, typed, generation, hint, job),
        max_output_tokens=1000 + 300 * len(planned) + 100 * prompts,
    )


def title_hint(persona: Persona | None, title: str | None = None, typed: TitleRequest | None = None) -> str | None:
    """What the persona's titles are like, for a title the model makes up: none when the talk has its title already
    (given, or typed and kept), or no persona."""
    if persona is None or title or (typed is not None and typed.keep):
        return None
    return persona.title_hint


def response_schema(
    planned: list[PlannedSlide],
    language: str = "en",
    name: NameRequest | None = None,
    typed: TitleRequest | None = None,
    generation: ImageGeneration | None = None,
    title_hint: str | None = None,
    job_hint: str | None = None,
) -> dict[str, Any]:
    """The JSON Schema of the answer: every property required, nothing else allowed (as strict structured outputs
    want), the spine first and the slides in order (which is alphabetical order too)."""
    fields: dict[str, Any] = {
        field: {"type": "boolean" if field == "unsafe_topic" else "string", "description": description}
        for field, description in spine(language, name, typed, title_hint, job_hint).items()
    }
    properties: dict[str, Any] = {SPINE: _object(fields)}
    for slide in planned:
        properties[slide.key] = slide_schema(slide.recipe, generation)
    return _object(properties)


def slide_schema(recipe: Recipe, generation: ImageGeneration | None = None) -> dict[str, Any]:
    properties: dict[str, Any] = {"concept": {"type": "string", "description": CONCEPT}}
    for text in recipe.written_fields():
        properties[text.name] = {"type": "string", "description": field_description(recipe, text)}
        if text.options:  # one of these words (or empty, when the field may stay empty)
            properties[text.name]["enum"] = [*text.options, *([""] if text.optional else [])]
    for slot in recipe.image_queries():
        properties[f"{slot}_query"] = {"type": "string", "description": _query_description(slot)}
    for slot, about in generated(recipe, generation):
        properties[prompt_field(slot)] = {"type": "string", "description": about}
    return _object(properties)


def generated(recipe: Recipe, generation: ImageGeneration | None) -> list[tuple[str, str]]:
    """The image slots the language model writes a prompt for, to generate their pictures from (those that prefer a
    generated picture, in a talk that generates them), with what to write."""
    if generation is None:
        return []
    queried = set(recipe.image_queries())
    return [
        (name, _prompt_description(source))
        for name, source in recipe.slots()
        if name in queried and generation.prefers(source)
    ]


def _prompt_description(source: Any) -> str:
    intent = getattr(source, "intent", "") or "the picture"
    cover = getattr(source, "aesthetic", "") == "book-covers"
    return f"{PROMPT_DESCRIPTION}, for {intent}" + (
        "; a book cover has the book's title on it, in quotes" if cover else ""
    )


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
    prompts = {
        slot: value[prompt_field(slot)]
        for slot in slide.recipe.image_queries()
        if isinstance(value.get(prompt_field(slot)), str) and value[prompt_field(slot)].strip()
    }
    concept = value.get("concept")
    return SlidePlan(
        kind=slide.recipe.kind,
        recipe=slide.generator,
        concept=concept if isinstance(concept, str) else "",
        texts=texts,
        images=queries,
        prompts=prompts,
    )
