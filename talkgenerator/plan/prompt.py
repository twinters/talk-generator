"""Asking a language model for a talk's plan (docs/v5-plan.md, sections 5.2 and 5.3).

Python picks the slides (see PresentationSchema); the model writes what goes on them, in one request. The response is
one JSON object, whose schema is built for this talk's slides: its spine (title, the presenter's job, the thesis, and
a made-up name for the presenter when nobody gave theirs: see talkgenerator.names) first, then one property per
slide, in order, so the slides can be read while the model writes them. Seeded "dice" make every seed give its own
talk, where current models take no sampling temperature: the talk's persona (see talkgenerator.personas), whose voice
the model writes in, with one of its angles on the topic and what its titles are like.

Some models write the properties in alphabetical order instead of the schema's (OpenRouter's free router often picks
one that does), so the answer's properties are in alphabetical order too: the spine is one object, called "about",
and the slides' numbers have as many digits as the last one's ("slide_02" to "slide_10"). A model may name an earlier
slide by its key in a callback ("Huddling scales trust (from slide_03)"), but no key goes on a slide: the brackets
that name one go, and a text with a key anywhere else is a leftover, as template code is (talkgenerator.checks.deck).
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from talkgenerator.facts import Given, request_line
from talkgenerator.images.generation import PROMPT_DESCRIPTION, prompt_field
from talkgenerator.llm.base import Message, TextRequest
from talkgenerator.models.plan import SlidePlan
from talkgenerator.names import NameRequest
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, PRESENTER_JOB, TALK_TITLE, Recipe, TextField
from talkgenerator.titles import OWN_TITLE, TitleRequest
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.images.generation import ImageGeneration
    from talkgenerator.personas import Persona
    from talkgenerator.schema.formats import Format

SYSTEM_PROMPT: Final = """\
You write the slides of talks for improv theatre, for formats such as PowerPoint karaoke and improvised TED talks. A \
performer presents your slides without having seen them before, and has to make them work: the fun is in watching \
them explain every slide as if they had planned it all.

So write slides that give the presenter something to work with, rather than finished jokes:
- Keep it short, and specific. Titles of two to six words, captions of one to four, no paragraphs or bullet \
points: the presenter reads a slide at a glance, so most slides need fewer than fifteen words in all, and the lengths \
given are limits, not targets. Short isn't bland: one oddly specific detail (a number, a name, a place) beats a \
general phrase.
- Play it straight. Write like a confident expert giving a serious talk, however absurd the content. The audience \
laughs at the presenter making sense of it, not at puns on the slides.
- Leave gaps. A good slide raises a question the presenter has to answer: an odd juxtaposition, a suspiciously \
specific claim, something that needs backing up. Don't explain the joke, or the image, and don't finish it: no \
punchline spelled out, no recap of earlier jokes.
- Set up and break. A slide that lists things (bars, flags, tiers, steps, options) sets a pattern with its first \
ones and breaks it with its last, the punchline.
- No stock formulas: no "Uber for X" or "X for Y", no "The Great X", no title with a colon and a subtitle, and no \
buzzwords unless the presenter talks like that.
- Build one talk. The slides follow one thread, the talk's thesis. A later slide may call back to an earlier one (a \
strange claim, a thing from before), and the conclusions call back to a few of them; but nothing comes back on more \
than two slides, and no made-up person recurs unless the request says so.
- Wander and come back. Every slide gets a word to riff on, which may wander away from the topic: take it as a \
starting point (not as the slide's title), and tie it back to the talk's thread.
- Fit the slide. Write every field the way its description asks, within its length.
- Image search queries say what the image should show, in two to six plain English words, for stock photo and gif \
sites: concrete things rather than ideas ("a cat wearing sunglasses", not "coolness"). Pictures are half the joke: ask \
for something concrete and a little odd that the presenter has to explain, rather than a literal picture of the \
slide's words.

Never write:
- quotes attributed to real people (quotes on the slides belong to made-up people, or to no one),
- anything about real private persons, or the presenter's name on the slides (the title slide has it),
- made-up people with names that are puns or no names at all: they have names a real person could have, with a \
first name of their own in every talk rather than the usual comic ones,
- slurs, sexual content, or anything that mocks people for who they are,
- statements about real-world politics, such as a country's wars or disputes, unless the topic is about them,
- markup, hashtags, placeholders in curly braces, or the keys of your answer (such as slide_03): a callback \
repeats what the earlier slide said, never its key or number,
- emoji, except where a field asks for them.

If the topic asks for something hateful or harmful, set "unsafe_topic" to true, and keep everything else short.
Answer with one JSON object in the shape you're given, and nothing else."""


@dataclass(frozen=True, eq=False)
class PlannedSlide:
    """A slide the model writes: its place in the talk, and what to write."""

    number: int  # counted from 1
    generator: str  # the name of the slide generator it stands in for
    recipe: Recipe
    seed: str  # the word the slide starts from (from the schema's topic generator, or the talk's outline)
    digits: int = 1  # as many as the number of the talk's last slide has
    idea: str = ""  # what the slide does with its word, in a talk the model planned first (talkgenerator.plan.outline)
    # Whether its word is English in a talk in another language (the related words seeds wander to are English: see
    # talkgenerator.schema.slide_topic_generators), which the request then marks, for the model to say it in the
    # talk's language (D74: English words such as "goaltender" and "Healing" ended up on Dutch slides as they were)
    english: bool = False
    # What it does for the talk's agenda, if anything (see agenda_cues): the agenda's own announcements, or which item
    # of it announced this slide
    cue: str = ""

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
    titled: bool = False,
) -> dict[str, str]:
    """The talk's spine, which the answer starts with: what to write in each of its fields. With a name request, the
    presenter's name too, before their job (which then agrees with it). For what was typed, which could be the topic
    or the title (see talkgenerator.titles), the title as its request asks (with classic titles to pick, the model's
    own title, own_title, before the title it settles on). Otherwise, the talk's title when it's given (titled), or
    else a title of the model's own. With a title hint (what the persona's titles are like, for a title the model
    makes up), the title the model makes up is to be like that; with a job hint (the persona's), the presenter's job
    too, in place of the job field's example."""
    language_name = languages.language(language).name
    fields = {
        # (Asked the other way around, as "safe_topic", the free models sometimes turned down harmless topics)
        "unsafe_topic": "true only if the topic asks for something hateful or harmful; false for every other topic, "
        "however odd",
        "thesis": "the talk's thesis, its absurd claim in one sentence"
        + (f", in {language_name}" if language != languages.ENGLISH.code else "")
        + " (not shown)",
    }
    if typed is not None:
        fields.update(typed.fields(language, title_hint or ""))
    else:
        like = f", {title_hint}" if title_hint else ""
        title = TALK_TITLE.description if titled else OWN_TITLE
        fields["title"] = f"{title}{like}, in {language_name} (at most {TALK_TITLE.max_length} characters)"
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


def concept(language: str = languages.ENGLISH.code) -> str:
    """What to write for a slide's concept: in English words in a talk in another language too, as it's searched for
    pictures (which the picture sources search best in English)."""
    if language == languages.ENGLISH.code:
        return CONCEPT
    return CONCEPT.replace("two to five words", "two to five English words")


def native_line(language: str) -> str | None:
    """What a request for a talk in another language than English says of writing it (None for English): as a native
    speaker of the language writes, for its speakers. Talks written from requests in English came out with English
    words left in ("de geheime goaltender", "hier comes de netwerk"), word for word ("Over duizend soorten kaas
    bestaan", for "Over a thousand types of cheese exist"), with look-alikes ("graf", a grave, for a graph) and titles
    with a capital on every word, as English titles have them (D74)."""
    if language == languages.ENGLISH.code:
        return None
    spoken = languages.language(language)
    name = spoken.name
    looks = f" ({spoken.false_friend})" if spoken.false_friend else ""
    return (
        f"Write as a native {name} speaker writes for {name} speakers: in the words and idioms they use, never word "
        f"for word from English, with no English words left in, nor {name} words that only look like English ones"
        f"{looks}. This request is in English, and so are its examples and the words marked (English): write your "
        f"own, in {name}. A title has capitals as in {name}: on {spoken.capitals}, not on every word as in English."
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
    talk_format: Format | None = None,
    facts: Mapping[int, Given] | None = None,
    answered_in_english: bool = False,
) -> TextRequest:
    """The request for a talk (with the presenter's name, when there's a name request). Asked again, it says that a
    model found the topic unsafe: some of the free models get the flag wrong whichever way it's asked (one turned
    down "penguins"). Asked again for a talk in another language whose first answer started in English
    (answered_in_english: a free model wrote a Swedish talk in English), it says so, and what's to be in the language.
    In a talk in another language than English, every text field's description says the language too, so that an
    example of a hint's ("such as 'Outline'") is said in it: a free model copied the English ones into a German talk.
    And it asks for the talk as a native speaker of its language writes, with its English words marked (see
    native_line and slide_lines, D74). For what was typed, which could be the topic or the title (see
    talkgenerator.titles), it says what the title is to be: what was typed, with its slips fixed, or a title of the
    model's own on it. In a talk that generates pictures (with a generation), the model writes a prompt for every
    image that prefers one.

    With real facts for some of its slides (by slide number: see talkgenerator.facts), it says how to use them, and
    each slide's line says what the slide does with its fact (a fun fact twists it, a timeline puts it among made-up
    moments). Without them, it's as it was before talks had facts.

    The talk's persona (see talkgenerator.personas) is who presents it: the model writes in its voice, on the angle
    the talk's dice pick among its angles, a title it makes up is like the persona's titles, and the presenter's job
    is the persona's kind of job. (Without one, the request has none of that: the talk is the format's own.)

    A talk format beyond the TED-like talks (talk_format: see talkgenerator.schema.formats) says what the talk is, on
    a line of its own, and what its titles and its presenter's job are like, with the persona's. (The TED-like
    formats have none, and their requests say nothing of a format.)"""
    hint = title_hint(persona, title, typed, talk_format)
    job = job_hint(persona, talk_format)
    titled = bool(title)
    fields = spine(language, name, typed, hint, job, titled)
    language_name = languages.language(language).name
    lines = [
        *header(
            topics,
            rng,
            f"{spine_language(language, name, typed)} and every slide in {language_name}, and the image search "
            "queries in English",
            title,
            typed,
            persona,
            talk_format,
            facts=bool(facts),
            language=language,
        ),
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
        *(
            [
                f"Asked again: the last answer was in English. Write the title, the thesis, the presenter's job and every "
                f"slide in {language_name}; only the image search queries are in English.",
                "",
            ]
            if answered_in_english
            else []
        ),
        f"Write the talk as one JSON object. First its spine, as an object called {SPINE}:",
        *(f"- {field}: {description}" for field, description in fields.items()),
        "",
        "Then every slide, in order (slide 1, the title slide, is made from the spine), each with its texts, a search "
        f"query for each of its images, and its concept: {concept(language)}.",
    ]
    # The guidance per field is in the schema too, but not every model gets to read the schema's descriptions
    for slide in planned:
        lines += ["", *slide_lines(slide, language, (facts or {}).get(slide.number), generation)]
    prompts = sum(len(generated(slide.recipe, generation)) for slide in planned)
    return TextRequest(
        purpose="talk plan",
        system=SYSTEM_PROMPT,
        messages=(Message(role="user", content="\n".join(lines)),),
        json_schema=response_schema(planned, language, name, typed, generation, hint, job, titled),
        max_output_tokens=1000 + 300 * len(planned) + 100 * prompts,
    )


def header(
    topics: list[str],
    rng: random_util.Rng,
    written: str,
    title: str | None = None,
    typed: TitleRequest | None = None,
    persona: Persona | None = None,
    talk_format: Format | None = None,
    facts: bool = False,
    language: str = "en",
) -> list[str]:
    """The lines a request for a talk (or its plan, or one of its slides: see talkgenerator.plan.outline) starts
    with: what it's about (its topic and title, or what was typed), what's written in which language (written), and in
    another language than English, writing it as a native speaker would (see native_line), its format beyond the
    TED-like talks, its persona's voice and angle, and how to use real facts (with facts)."""
    topic = topics[0] + (f" (and {', '.join(topics[1:])})" if len(topics) > 1 else "")
    native = native_line(language)
    return [
        *(typed.lines(topic) if typed is not None else [f"Topic: {topic}", *([f"Title: {title}"] if title else [])]),
        f"Language: {written}",
        *([native] if native else []),
        *([f"The format: {talk_format.brief}"] if talk_format is not None else []),
        *([f"The presenter: {persona.voice}", f"The angle: {persona.angle(rng)}"] if persona is not None else []),
        callbacks_line(rng),
        *([request_line(language)] if facts else []),
    ]


# RUNNING GAGS (D80): a made-up person who keeps coming back, now and then, on two slides at most (the user, 2026-11-13:
# "many talks have a character they cite who comes back later, but we do that a bit too much": a sourdough talk had its
# Gerald on five of its ten slides)
RECURRING_CHARACTER_ODDS: Final = 0.2


def recurring_character(rng: random_util.Rng) -> bool:
    """Whether the talk's running gag may be a made-up person (that share of talks, by a stream of its own)."""
    with random_util.use(rng.child("running gag")):
        return random_util.random() < RECURRING_CHARACTER_ODDS


def callbacks_line(rng: random_util.Rng) -> str:
    """What a request says of the talk's callbacks: a made-up person who turns up on two slides, now and then, or else
    callbacks to things and claims, with no recurring person."""
    if recurring_character(rng):
        return "Callbacks: one made-up person may come back as a running gag, on two slides at most."
    return (
        "Callbacks: a thing or a claim of an earlier slide may come back once; no recurring characters (no made-up "
        "person on more than one slide)."
    )


def spine_language(language: str, name: NameRequest | None = None, typed: TitleRequest | None = None) -> str:
    """What of the spine is written in the talk's language, for a request's language line ("write the title, the
    thesis, the presenter's job"): the thesis only in another language than English (it's never shown)."""
    kept = " (the typed title keeps its words)" if typed is not None and typed.keep else ""
    thesis = "the thesis, " if language != languages.ENGLISH.code else ""
    return f"write the title{kept}, {thesis}the presenter's {'name and ' if name is not None else ''}job"


def slide_lines(
    slide: PlannedSlide,
    language: str = languages.ENGLISH.code,
    given: Given | None = None,
    generation: ImageGeneration | None = None,
) -> list[str]:
    """What a request says of a slide it asks for: its key, what it is, its word to riff on (with its idea, in a talk
    the model planned first) and its real fact (what to do with it), then every field to write, with its description
    (which is in the schema too, but not every model gets to read the schema's descriptions). In a talk in another
    language than English, an English word to riff on and a fact (they're in English) say they're English, for the
    model to say them in the talk's language (D74)."""
    brief = (slide.recipe.brief or KINDS[slide.recipe.kind].description).rstrip(".")
    other = language != languages.ENGLISH.code
    in_english = f" (in English: tell it in {languages.language(language).name})" if other else ""
    fact = f". {given.line()}{in_english}" if given is not None else ""
    idea = f". The idea: {slide.idea.rstrip('.')}" if slide.idea else ""
    word = f"{slide.seed} (English)" if slide.english and other else slide.seed
    cue = f". {slide.cue}" if slide.cue else ""
    return [
        f"{slide.key}: {brief}. A word to riff on: {word}{idea}{fact}{cue}",
        *(
            f"- {text.name}: {field_description(slide.recipe, text, language)}"
            for text in slide.recipe.written_fields()
        ),
        *(f"- {slot}_query: {_query_description(slot, slide.recipe)}" for slot in slide.recipe.image_queries()),
        *(f"- {name}: {FOUND_QUERY}" for name in found_queries(slide.recipe)),
        *(f"- {prompt_field(slot)}: {about}" for slot, about in generated(slide.recipe, generation)),
    ]


# AGENDA (D80): an agenda's items announce slides of the talk, which pick them up, so that what the agenda promises comes
# back (the user, 2026-11-13: "there are overview slides of 'what we'll do', but those topics never come back")
AGENDA_KIND: Final = "agenda"
ANNOUNCED: Final = 3  # how many slides an agenda announces, at most
# The kinds of slide an agenda doesn't announce: what isn't a slide of the talk's matter
_UNANNOUNCED: Final = frozenset({"agenda", "section", "questions", "closer", "title"})


def agenda_cues(planned: Mapping[int, PlannedSlide]) -> dict[int, PlannedSlide]:
    """The planned slides (by their index), with the talk's agenda, if it has one, announcing up to three of the slides
    after it, spread over them (the first, one in the middle and the last but the talk's last slide, which ends it),
    each by its word to riff on, and those slides each picking up their item: so that what the agenda promises comes
    back, as the presenter can then point out. Without an agenda, they're as they were."""
    slides = dict(planned)
    agenda = next((slide for slide in slides.values() if slide.recipe.kind == AGENDA_KIND), None)
    if agenda is None:
        return slides
    last = max(slide.number for slide in slides.values())
    later = sorted(
        (
            slide
            for slide in slides.values()
            if agenda.number < slide.number < last and slide.recipe.kind not in _UNANNOUNCED
        ),
        key=lambda slide: slide.number,
    )
    if not later:
        return slides
    count = min(ANNOUNCED, len(later))
    picked = list(dict.fromkeys(later[round(index * (len(later) - 1) / max(1, count - 1))] for index in range(count)))
    words = ", ".join(f"{slide.key}'s {slide.seed!r}" for slide in picked)
    announcing = (
        f"Its first {len(picked)} items announce, in order, slides that come after it, each by its word ({words}): "
        "an agenda item of a few words about it; a last item may be your own"
    )
    for key, slide in slides.items():
        if slide is agenda:
            slides[key] = dataclasses.replace(slide, cue=announcing)
        elif slide in picked:
            slides[key] = dataclasses.replace(
                slide,
                cue=f"The agenda announced this slide as its item {picked.index(slide) + 1} (by the word "
                f"{slide.seed!r}): its title picks that item up",
            )
    return slides


def title_hint(
    persona: Persona | None,
    title: str | None = None,
    typed: TitleRequest | None = None,
    talk_format: Format | None = None,
) -> str | None:
    """What the talk's titles are like, for a title the model makes up: the format's kind of title (a pitch's, a
    paper's), and the persona's; none when the talk has its title already (given, or typed and kept), or neither."""
    if title or (typed is not None and typed.keep):
        return None
    hints = [
        hint
        for hint in (talk_format.title_hint if talk_format is not None else "", persona.title_hint if persona else "")
        if hint
    ]
    return ", and ".join(hints) or None


def job_hint(persona: Persona | None, talk_format: Format | None = None) -> str | None:
    """What the presenter's job on the title slide is, for the model: the persona's kind of job, given as the format
    has it (a pitch's role at the startup, an academic talk's affiliation); none for neither."""
    persona_hint = persona.job_hint if persona is not None else ""
    format_hint = talk_format.job_hint if talk_format is not None else ""
    if persona_hint and format_hint:
        return f"{persona_hint}, given as {format_hint}"
    return persona_hint or format_hint or None


def response_schema(
    planned: list[PlannedSlide],
    language: str = "en",
    name: NameRequest | None = None,
    typed: TitleRequest | None = None,
    generation: ImageGeneration | None = None,
    title_hint: str | None = None,
    job_hint: str | None = None,
    titled: bool = False,
) -> dict[str, Any]:
    """The JSON Schema of the answer: every property required, nothing else allowed (as strict structured outputs
    want), the spine first and the slides in order (which is alphabetical order too)."""
    fields: dict[str, Any] = {
        field: {"type": "boolean" if field == "unsafe_topic" else "string", "description": description}
        for field, description in spine(language, name, typed, title_hint, job_hint, titled).items()
    }
    properties: dict[str, Any] = {SPINE: _object(fields)}
    for slide in planned:
        properties[slide.key] = slide_schema(slide.recipe, generation, language)
    return _object(properties)


def slide_schema(
    recipe: Recipe, generation: ImageGeneration | None = None, language: str = languages.ENGLISH.code
) -> dict[str, Any]:
    properties: dict[str, Any] = {"concept": {"type": "string", "description": concept(language)}}
    for text in recipe.written_fields():
        properties[text.name] = {"type": "string", "description": field_description(recipe, text, language)}
        if text.options:  # one of these words (or empty, when the field may stay empty)
            properties[text.name]["enum"] = [*text.options, *([""] if text.optional else [])]
    for slot in recipe.image_queries():
        properties[f"{slot}_query"] = {"type": "string", "description": _query_description(slot, recipe)}
    for name in found_queries(recipe):
        properties[name] = {"type": "string", "description": FOUND_QUERY}
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


# An example in a field's description ("such as 'Live demo'"), which a request in another language says is English
_EXAMPLE: Final = re.compile(r"(such as '[^']+')")


def field_description(recipe: Recipe, text: TextField, language: str = languages.ENGLISH.code) -> str:
    """What to write in a slide's text field: the recipe's hint, or else the field's own description, in the talk's
    language when that's another one than English (an example of the hint's, "such as 'Outline'", is then to be said
    in it: it says it's English, as a free model put "Live demo", "Introducing: RegenMax" on a Dutch keynote's slides,
    D74), and its length (or the words it can be)."""
    if text.options:
        limit = "one of " + ", ".join(text.options) + (", or empty for any" if text.optional else "")
    else:
        limit = f"at most {text.max_length} characters" + (", or empty for none" if text.optional else "")
    hint = recipe.hints.get(text.name, text.description)
    written_in = ""
    if language != languages.ENGLISH.code and not text.options:
        name = languages.language(language).name
        written_in = f", in {name}"
        hint = _EXAMPLE.sub(rf"\1 (in English: yours in {name})", hint)
    return f"{hint}{written_in} ({limit})"


# What the model writes for a text that talkgenerator finds (a real quote, from Goodreads or Wikiquote): what to search
# it with, as a slide's concept ("the slide's subject in two to five words") found nothing on Goodreads, and random
# lines on Wikiquote (2026-11-09: an anime quote on a tea talk), where a plain theme finds real quotes about it
FOUND_QUERY: Final = (
    "the theme of the real quote talkgenerator finds for this slide, in one or two plain English words that a famous "
    "quote could be about, such as 'patience' or 'tradition': one the slide's point suits"
)


def found_queries(recipe: Recipe) -> list[str]:
    """The fields the model writes a search for, one for each text that a classic source finds for the slide (a real
    quote's): "<text>_query"."""
    return [f"{name}_query" for name in recipe.texts_from if name not in recipe.omit]


def _query_description(slot: str, recipe: Recipe | None = None) -> str:
    """What to write for an image slot's search query: the recipe's hint for it, if it has one (a picture that a chart
    tries first, in its place: see talkgenerator.plan.kinds.PictureFirst), or else what it searches for."""
    hint = recipe.hints.get(f"{slot}_query") if recipe is not None else None
    if hint:
        return hint
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
    for name in found_queries(slide.recipe):  # (with the texts, under their own names: see realize)
        if isinstance(value.get(name), str) and value[name].strip():
            texts[name] = value[name]
    concept = value.get("concept")
    return SlidePlan(
        kind=slide.recipe.kind,
        recipe=slide.generator,
        concept=concept if isinstance(concept, str) else "",
        texts=texts,
        images=queries,
        prompts=prompts,
    )
