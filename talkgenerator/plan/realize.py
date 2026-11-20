"""Turning a planned slide into a slide: its texts checked and trimmed, its images found with its queries.

Realizing a slide only depends on its plan, its recipe, its presentation context and the attempt's random stream,
never on the other slides: so slides can be realized in parallel, in any order, and a talk still comes out the same
(the schema settles them in order, and rejects one that repeats what the slides before it used).

A slide's pictures are searched for all at once, each with a random stream of its own, so they come out the same
whichever search is done first: a slide of three pictures takes about as long as its slowest search, not as the three
one after another (searches are nearly all of a picture slide's time, as measured on 2026-11-14). Then, in the slots'
order, a picture that's one of the slide's pictures before it (or nearly) is searched for again without them, as it
would be one after another.
"""

from __future__ import annotations

import contextvars
import functools
import logging
import re
import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeVar

from talkgenerator import facts
from talkgenerator.checks.deck import leftovers_in, real_politics, without_key_references
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import analysis
from talkgenerator.images import context as image_context
from talkgenerator.images.generation import FALLBACK, FIRST, Wish
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import Fact
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, ContentSource, Recipe, TextField
from talkgenerator.slide.slides import Slide
from talkgenerator.sources import emoji
from talkgenerator.util import emoji_util, generator_util, language_util, os_util, random_util

logger = logging.getLogger("talkgenerator")

# The first attempt searches with the plan's queries, the second tries other images for them, and the last searches
# for the slide's concept for the images whose queries find nothing
ATTEMPTS: Final = 3

# How many pictures of the slides being realized are searched for at the same time, in threads of their own (besides
# the one that realizes each slide): never in the image finder's, which a search waits for (see _at_once)
SEARCH_THREADS: Final = 12

_T = TypeVar("_T")

_QUOTE_MARKS: Final = "\"'“”‘’«»"
# Bars that look like the | that separates a list's things, which a free model wrote instead of it (a box drawing's)
_BARS: Final = str.maketrans(dict.fromkeys("│┃｜¦∣", "|"))
# What a cut may leave at the end of a text, besides little words: punctuation that leads on to more
_DANGLING: Final = ",;:-–—([{/&+ "
# Where a sentence or a clause ends, for a cut to end there: a full stop, question or exclamation mark, a semicolon or
# a colon before a space, or a dash ("decorations—they're", "lost – adaptation"). (Not a comma: "Cats, as it turns
# out" is no clause; nor a range, as in "1890–1920")
_CLAUSE_END: Final = re.compile(r"[.!?;:](?=\s)|\s*—\s*|\s+[–-]\s+")
# And in English, where the next clause starts with a word that opens one: "The mountain breathes", of "The mountain
# breathes when prayers are whispered" (not "and" or "or", which join things as often: "salt and pepper")
_CLAUSE_START: Final = re.compile(
    r",?\s+(?=(?:but|yet|when|whenever|while|because|if|unless|until|although|though|since|whereas)\b)", re.IGNORECASE
)
# Where a cut may end when no clause does: after a comma, as in a list or an affiliation ("Professor of Serenity
# Studies", of "Professor of Serenity Studies, Department of Calm, University of Tranquil Grounds")
_COMMA: Final = re.compile(r",(?=\s)")
# A bracket that a cut would leave open ("Kaito Tanaka (Head of Temporal"): the cut ends before it instead
_OPEN_BRACKET: Final = re.compile(r"\s*[(\[][^)\]]*$")
# (and where a phrase may end besides, for a text that's only cut there: before a bracket, or before a word)
_BRACKET: Final = re.compile(r"\s*[(\[]")
_WORD: Final = re.compile(r"(?<=\s)\S+")
# A backslash before a quote mark, as some models escape one where their JSON needn't (what\'s)
_STRAY_ESCAPE: Final = re.compile(r"\\(?=['\"’])")

# TACKED-ON TAGS (docs/v5-plan.md, D85): what models add to the end of a line to make it funny, the jokes the user
# found most tiresome ("adds a lot of words at the end like 'twice' or ', on a Tuesday', as if that's a joke",
# 2026-11-21). The prompt asks for none; in an English talk, these go where a model wrote one anyway: a count, a hedge,
# a day or 3 a.m. after a comma or in brackets ("Independent thinker, allegedly"), the same as a fragment of its own
# after a sentence ("Wore them under tights. Twice."), and a day at the very end ("Waited four hours on a Tuesday"),
# as long as a few words are left ("Yes, twice", a chart's funny answer, stays)
_DAY: Final = r"(?:mon|tues|wednes|thurs|fri|satur|sun)day"
_TAG: Final = (
    r"(?:twice|thrice|again|allegedly|apparently|reportedly|supposedly|probably|somehow|technically"
    rf"|(?:on|every) (?:a )?{_DAY}s?|at 3 ?a\.?m\.?)"
)
_FRAGMENT_TAG: Final = re.compile(rf"(?<=[.!?…])\s+{_TAG}[.!?…]*$", re.IGNORECASE)
_CLAUSE_TAG: Final = re.compile(rf"\s*(?:,\s*{_TAG}|\(\s*{_TAG}\s*\))(?P<end>[.!?…]*)$", re.IGNORECASE)
_DAY_TAG: Final = re.compile(rf"\s+on a {_DAY}(?P<end>[.!?…]*)$", re.IGNORECASE)  # (not "closed on Sundays")
# How many words a text keeps at least, for its tag to go (and for a day at its very end, which needs no comma)
_UNTAGGED_WORDS: Final = 2
_UNDAYED_WORDS: Final = 3
_WORDS: Final = re.compile(r"\w+")


def untagged(text: str, language: str = languages.ENGLISH.code) -> str:
    """The text without a tag tacked on to its end to make it funny (see _TAG: "twice", ", allegedly", "on a
    Tuesday"), in an English talk: each of a list's things (separated by |) on its own. The text as it is in
    another language, or when what's left would be too short to say anything."""
    if language != languages.ENGLISH.code:
        return text
    if "|" in text:
        parts = text.split("|")
        cleaned = [untagged(part.strip()) for part in parts]
        return text if cleaned == [part.strip() for part in parts] else " | ".join(cleaned)
    for pattern, fewest in ((_FRAGMENT_TAG, _UNTAGGED_WORDS), (_CLAUSE_TAG, _UNTAGGED_WORDS), (_DAY_TAG, _UNDAYED_WORDS)):
        shorter = pattern.sub(lambda found: found.groupdict().get("end") or "", text).rstrip()
        if shorter != text and len(_WORDS.findall(shorter)) >= fewest:
            return untagged(shorter, language)  # (a tag before it too: "Late, again, on a Tuesday")
    return text


def length_limit(text_field: TextField) -> int:
    """How long a text of the field may be before it's cut: a little longer than the field's length (by an eighth,
    or at least four characters), as a few characters too many rarely spoil a slide, and a phrase cut off always
    does; or than its room, where its slides hold more than the model is asked for (TextField.room: D80 asked for
    less, and the user would rather have a text a little long than cut off mid-sentence)."""
    longest = max(text_field.max_length, text_field.room)
    return longest + max(4, longest // 8)


def clean_text(value: Any, text_field: TextField, language: str = "en") -> str | None:
    """The text as it goes on a slide: on one line, without wrapping quote marks or brackets that name a slide by its
    key in the model's answer ("(from slide_03)"), in an English talk without a tag tacked on to its end to make it
    funny (", allegedly", "on a Tuesday": see untagged), and cut to the field's length when it's longer than its
    length_limit (between words, and not after a little word of its language, such as "the"; a list, between its
    things; a presenter's job only where a phrase of it ends, or else not at all: see TextField.phrases), or the
    option it names when the field is a choice. Its emoji count as two characters each, however many
    characters they're written with (a joined one, "🕵️‍♂️", is five). None when it's empty, names no option, or holds
    bits of templates or code (a slide's key elsewhere in it too: see talkgenerator.checks.deck)."""
    if not isinstance(value, str):
        return None
    value = without_key_references(value)  # (a callback that names its slide by its key keeps the rest of it)
    if text_field.options:
        return option_of(value, text_field)
    text = _unquoted(" ".join(_STRAY_ESCAPE.sub("", value).split()).translate(_BARS))
    if not text or leftovers_in(text):
        return None
    if "|" in text:
        text = _folded(text)
    text = untagged(text, language)
    extra = len(text) - emoji_util.room(text)  # (the characters its emoji are written with, beyond their room)
    if len(text) > length_limit(text_field) + extra:
        if text_field.phrases:  # (a presenter's job: where a phrase of it ends, or not at all, D81)
            return _at_phrase(text, length_limit(text_field) + extra, language)
        cut = _cut_list if "|" in text else _cut
        text = cut(text, max(text_field.max_length, text_field.room) + extra, language)
    return text


def _folded(text: str) -> str:
    """A list written as one text (its things separated by |), each of its emoji that a model wrote as a thing of its
    own ("🔥 | Roasting | 🔥", as a free model wrote a tier) in front of the thing after it (one at its end goes)."""
    things: list[str] = []
    waiting = ""
    for thing in (part.strip() for part in text.split("|")):
        if not thing:
            continue
        if not emoji_util.plain(thing).strip():
            waiting = waiting or thing
            continue
        things.append(f"{waiting} {thing}" if waiting else thing)
        waiting = ""
    return " | ".join(things) if things else text


def _cut_list(text: str, length: int, language: str) -> str:
    """A list written as one text (its things separated by |) cut to its length between its things, keeping as many
    of them as fit whole (or else its first thing, whole if it's only a little too long, as a text that long would
    be kept, or else cut as a text is: a tier's one thing, D80)."""
    things = [thing.strip() for thing in text.split("|") if thing.strip()]
    kept: list[str] = []
    for thing in things:
        if len(" | ".join([*kept, thing])) > length:
            break
        kept.append(thing)
    if not kept and things and len(things[0]) <= length + max(4, length // 8):
        return things[0]
    return " | ".join(kept) if kept else _cut(things[0] if things else text, length, language)


# Each quote mark that opens a quote, with the mark that closes it (Swedish and Danish close with what opens)
_CLOSING: Final = {'"': '"', "'": "'", "“": "”", "‘": "’", "«": "»", "»": "«", "”": "”", "’": "’"}


def _quoting(text: str, mark: str) -> bool:
    """Whether the text uses the mark as a quote mark: not only as an apostrophe between two letters ("it's")."""
    return any(
        character == mark
        and not (0 < index < len(text) - 1 and text[index - 1].isalpha() and text[index + 1].isalpha())
        for index, character in enumerate(text)
    )


def _unquoted(text: str) -> str:
    """The text without the quote marks that wrap all of it (a model's "Expectation", in quotes), and without a quote
    mark at either end that nothing in it pairs with; but a quote that ends it keeps its closing mark ("calling it
    'Steve'"), as one that starts it keeps its opening mark."""
    text = text.strip()
    while (
        len(text) >= 2
        and text[-1] == _CLOSING.get(text[0])
        and not any(_quoting(text[1:-1], mark) for mark in {text[0], text[-1]})
    ):
        text = text[1:-1].strip()
    if text[:1] in _CLOSING and _CLOSING[text[0]] not in text[1:]:
        text = text[1:].strip()
    if (
        text
        and text[-1] in _QUOTE_MARKS
        and not any(text[-1] == close and mark in text[:-1] for mark, close in _CLOSING.items())
    ):
        text = text[:-1].strip()
    return text


def _cut(text: str, length: int, language: str) -> str:
    """The text cut to its length: where a sentence or a clause in it ends, if that keeps at least a third of it ("Your
    plants are not decorations", of "Your plants are not decorations—they're coworkers who need feedback"; "The Data
    Is Clear", of "The Data Is Clear: Coffee Correlates with Alertness"), or in English before a word that opens the
    next clause, if that keeps half ("The mountain breathes", of "The mountain breathes when prayers are whispered"),
    or else after a comma, if that keeps a third ("Professor of Serenity Studies", of a long affiliation; "Wim Fietsen",
    of "Wim Fietsen, de enige die ooit een fiets repareerde met een broodjespunt"), or else between words, without the
    little words and punctuation that a cut leaves hanging at its end (as in "Cats were the true scholars of the"),
    and with an ellipsis, so that it reads as meant (D80: the user finds a text cut off mid-sentence worse than one
    that's too long, which TextField.room makes rare); and each of them before a bracket it would leave open, if that
    keeps a third of it ("Kaito Tanaka", of "Kaito Tanaka (Head of Temporal Planning)"; "Arctic Expansion", of "Arctic
    Expansion (High Impact, Low Urgency)")."""
    head = text[: length + 1]
    little = _little_words(language)
    ends = [end.start() + (1 if end.group(0) in ".!?" else 0) for end in _CLAUSE_END.finditer(head)]
    starts = [start.start() for start in _CLAUSE_START.finditer(head)] if language == "en" else []
    commas = [comma.start() for comma in _COMMA.finditer(head)]
    # (a whole sentence or clause, or a part before a comma, reads as one even when it's short: "Wim Fietsen", of "Wim
    # Fietsen, de enige die ooit een fiets repareerde"; a clause before a word that opens the next one less so)
    places = [
        *((at, length // 3) for at in reversed(ends)),
        *((at, length // 2) for at in reversed(starts)),
        *((at, length // 3) for at in reversed(commas)),
    ]
    for at, least in places:
        clause = head[:at].rstrip(_DANGLING)
        last = clause.rsplit(" ", 1)[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower()
        if len(clause) >= least and last not in little:
            return _closed(clause, length)
    if " " not in head:  # one long word
        return text[:length]
    words = head.rsplit(" ", 1)[0].split()
    while len(words) > 1 and words[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower() in little | {""}:
        words.pop()
    cut = " ".join(words).rstrip(_DANGLING)
    closed = _closed(cut, length)
    if not closed:
        return text[:length]
    # (but a part before a bracket is a part: "Kaito Tanaka")
    return closed if closed != cut else f"{closed.rstrip('.!?…')}…"


def _at_phrase(text: str, length: int, language: str) -> str | None:
    """The text cut to its length where a phrase of it ends, the longest that fits: where a sentence or a clause
    ends, after a comma, before a bracket, or before a little word of its language that starts the next phrase
    ("Senior Vice President of Applied Sock Theory", of "Senior Vice President of Applied Sock Theory at the
    Department of Mismatched Footwear"), and never after a little word ("Head of"), nor with an ellipsis; None where
    there's no such place (D81: for a presenter's job, which reads as a mistake when it's cut off mid-phrase)."""
    head = text[: length + 1]
    little = _little_words(language)
    places = {end.start() + (1 if end.group(0) in ".!?" else 0) for end in _CLAUSE_END.finditer(head)}
    places |= {comma.start() for comma in _COMMA.finditer(head)}
    places |= {bracket.start() for bracket in _BRACKET.finditer(head)}
    places |= {
        word.start() for word in _WORD.finditer(head) if word.group(0).strip(_DANGLING + _QUOTE_MARKS).lower() in little
    }
    for at in sorted(places, reverse=True):
        phrase = head[:at].rstrip(_DANGLING)
        last = phrase.rsplit(" ", 1)[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower()
        if phrase and last and last not in little and _OPEN_BRACKET.search(phrase) is None:
            return phrase
    return None


def _closed(cut: str, length: int) -> str:
    """A cut text before a bracket it leaves open, if that keeps a third of the length it was cut to (else as it is)."""
    opened = _OPEN_BRACKET.search(cut)
    if opened is not None and len(cut[: opened.start()].rstrip(_DANGLING)) >= length // 3:
        return cut[: opened.start()].rstrip(_DANGLING)
    return cut


def _little_words(language: str) -> frozenset[str]:
    try:
        return language_util.stopwords(languages.language(language).stopwords)
    except (LookupError, OSError, ValueError):  # NLTK's lists can't be had: cut between words only
        return frozenset()


def option_of(value: str, text_field: TextField) -> str | None:
    """The option of the field that the value names (ignoring case, quote marks, dashes and underscores)."""

    def plain(text: str) -> str:
        return " ".join(text.replace("-", " ").replace("_", " ").split()).strip(_QUOTE_MARKS + " .").lower()

    return next((option for option in text_field.options if plain(option) == plain(value)), None)


def realize(
    plan: SlidePlan,
    recipe: Recipe,
    presentation_context: dict[str, Any],
    rng: random_util.Rng,
    attempt: int,
    *,
    problems: list[str] | None = None,
    local_images: Path | None = None,
    spare_pictures: Callable[[Any, list[ImageData]], ImageData | None] | None = None,
) -> tuple[Slide, list[Any]] | None:
    """A planned slide as a slide, with what it's made of (to check for repeats). None if anything it needs is
    missing: a text, or an image the sources couldn't find; problems then gets why.

    With local_images (a folder), an image "query" that names an image file (relative to that folder, or absolute)
    puts that file on the slide: for plans that people or agents write, never for what a language model wrote.

    With spare_pictures, nothing is looked up, for a slide out of time (see PresentationSchema._in_time): it goes without
    the images it can do without, and the ones it needs come from spare_pictures (given an image's source and the slide's
    other images: a picture found earlier, or None, and then the slide doesn't come out)."""
    kind = KINDS[recipe.kind]
    concept = plan.concept.strip() or str(presentation_context.get("seed") or "")
    language = presentation_context.get("language", "en")
    topic = " ".join(presentation_context.get("topics") or [str(presentation_context.get("topic") or "")])
    with random_util.use(rng.child("attempt", attempt)):
        texts: dict[str, str | None] = {}
        for text_field in map(recipe.text_field, kind.texts):  # (as long as each may be on this slide)
            name = text_field.name
            if name in recipe.omit:
                texts[name] = None
                continue
            if name in recipe.texts_from:
                # (searched for the theme the plan gives it, if any, and else, or when that finds none, for its
                # concept: see talkgenerator.plan.prompt.FOUND_QUERY)
                theme = " ".join(str(plan.texts.get(f"{name}_query") or "").split())
                searches = list(dict.fromkeys(search for search in (theme, concept) if search))
                found = None
                for search in searches:
                    found = recipe.texts_from[name]({**presentation_context, "seed": search})
                    if clean_text(found, text_field, language):
                        break
                texts[name] = clean_text(found, text_field, language)
                why = f"{name}: talkgenerator found none about {' or '.join(map(repr, searches)) or 'nothing'}"
            else:
                value = plan.texts.get(name)
                texts[name] = clean_text(value, text_field, language)
                written = isinstance(value, str) and value.strip()
                held = ", ".join(leftovers_in(value)) if isinstance(value, str) else ""
                why = f"{name}: holds {held or 'template code'} ({value!r})" if written else f"{name}: not written"
                # (a free model wrote a statement on a country's history of aggression as a lighthouse talk's quote)
                politics = real_politics(str(value), topic) if texts[name] and language == "en" else None
                if politics:
                    logger.warning("Left out a planned text about real-world politics (%r): %r", politics, value)
                    texts[name], why = None, f"{name}: about real-world politics ({politics!r}): {value!r}"
                    _note(problems, why)
            if texts[name] is None and not text_field.optional:
                _note(problems, why)
                return None
            mood = recipe.emoji.get(name)
            if mood is not None and texts[name]:  # (a list its variant asks emoji for: the model's, or else ours)
                texts[name] = emoji.listed(texts[name], mood, own=language == languages.ENGLISH.code)

        images: dict[str, Any] = dict.fromkeys(slot for slot in kind.images if slot in recipe.omit)
        queries: dict[str, str] = {}
        talk = image_context.current()
        generation = talk.generation
        last = attempt >= ATTEMPTS - 1
        wishes: list[tuple[str, Wish]] = []  # the pictures to generate in place of their stock photos
        unfound: list[Wish] = []  # the pictures to generate, as their slots found none (on the last try)
        # (the pictures of a diagram's boxes: a box without one, when nothing is found, still makes the slide)
        optional = set(recipe.optional_slots())
        slots = list(recipe.slots())
        # (what the recipe has each slot search for, such as a meme's template, or the plan's query)
        asked = {slot: recipe.queries.get(slot) or plan.images.get(slot, "").strip() for slot, _ in slots}
        local = {slot: _local_image(asked[slot], local_images) for slot, _ in slots}

        def look_for(slot: str, source: ImageSlot | ContentSource, avoid: list[ImageData]) -> _Search:
            return _search(
                slot,
                source,
                asked[slot] or concept,
                concept,
                presentation_context,
                avoid,
                rng.child("attempt", attempt, "picture", slot),
                behind=slot in kind.optional_images,
                required=slot not in optional,
                last=last,
                own_query=slot in recipe.queries,
            )

        # The pictures that are looked up (none out of time), all at once: see the module's documentation
        looked_up = [(slot, source) for slot, source in slots if local[slot] is None] if spare_pictures is None else []
        at_once = _at_once([functools.partial(look_for, slot, source, []) for slot, source in looked_up])
        searched = dict(zip((slot for slot, _ in looked_up), at_once, strict=True))
        for slot, source in slots:
            query = asked[slot]
            path = local[slot]
            if path is not None:
                queries[slot], images[slot] = query, ImageData(path).found_with(query)
                continue
            queries[slot] = query or concept
            # (not one of the slide's other images, nor nearly)
            others = [image for image in images.values() if isinstance(image, ImageData)]
            behind = slot in kind.optional_images
            if spare_pictures is not None:  # (out of time: no lookups)
                found = None if behind or slot in optional else spare_pictures(source, others)
                if found is None and not (behind or slot in optional):
                    _note(problems, f"{slot}: no time to look for an image of {queries[slot]!r}, and no spare one")
                    return None
                images[slot] = found
                continue
            searching = searched[slot]
            if isinstance(source, ImageSlot) and _repeats(searching.found, others):
                # (found at the same time as the slide's pictures before it, it's one of them, or nearly: searched
                # for again without them, as it is when they come first)
                searching = look_for(slot, source, others)
            for problem in searching.problems:
                _note(problems, problem)
            found, queries[slot] = searching.found, searching.query
            if found is None and behind:
                images[slot] = None
                continue
            wish = None
            if generation is not None and isinstance(source, ImageSlot):
                look = talk.look(source.aesthetic)
                prompt = plan.prompts.get(slot)
                stream = rng.child("generated", slot)  # (the same seed on every try)
                if found is None and last and not behind and generation.fills(source, look):
                    wish = generation.wish(source, slot, FALLBACK, query or concept, stream, prompt, look)
                elif found is not None and generation.prefers(source):
                    wish = generation.wish(source, slot, FIRST, query or concept, stream, prompt, look)
            if found is None and wish is not None:
                unfound.append(wish)
                continue
            if found is None:
                if slot in optional:
                    images[slot] = None
                    continue
                return None
            images[slot] = found.found_with(queries[slot]) if isinstance(found, ImageData) else found
            if wish is not None and isinstance(images[slot], ImageData):
                wishes.append((slot, wish))

        # (the slide's last try, which runs while it's settled, in order: so the talk grants the same pictures, made
        # in parallel or one by one; and all of those the slide needs or none, and then those it can do without)
        for needed in (
            [wish for wish in unfound if wish.slot not in optional],
            [w for w in unfound if w.slot in optional],
        ):
            if not needed:
                continue
            assert generation is not None
            pictures = generation.fill(needed)
            if pictures is None and needed[0].slot in optional:
                images.update(dict.fromkeys((wish.slot for wish in needed), None))
                continue
            if pictures is None:
                _note(problems, "no picture could be generated for " + ", ".join(wish.slot for wish in needed))
                return None
            for wish, picture in zip(needed, pictures, strict=True):
                images[wish.slot] = picture.found_with(queries[wish.slot])

        try:
            slide = kind.build(texts, images, languages.language(language))
        except (ValueError, KeyError) as error:
            _note(problems, str(error))
            return None
        slide.wishes = [(images[slot], wish) for slot, wish in wishes]

    missing = slide.missing_content()
    if missing:
        _note(problems, f"an image couldn't be downloaded, or is on the slide twice ({', '.join(missing)})")
        return None
    # The real facts the slide was given (see talkgenerator.facts: a coincidence's two, D73), each of which it credits
    # when its texts build on it
    given = [fact for fact in (presentation_context.get("fact"), presentation_context.get("also_fact")) if fact]
    built_on = [isinstance(fact, Fact) and facts.used_in(fact, texts.values()) for fact in given]
    slide.set_note(
        f"Seed: {presentation_context.get('seed')}\nPlanned: a {recipe.kind} slide for {plan.recipe}, about {concept!r}"
        f"\nTexts: {texts}\nImage queries: {queries}"
        + "".join(f"\nTo generate ({wish.reason}) for {wish.slot}: {wish.request.prompt!r}" for _, wish in slide.wishes)
        + "".join(
            f"\nReal fact ({'built on' if used else 'left out'}): {fact.text!r}"
            for fact, used in zip(given, built_on, strict=True)
            if isinstance(fact, Fact)
        )
    )
    for image in images.values():
        if isinstance(image, ImageData):
            slide.add_source(image.get_source(), image.get_source_url(), image.get_credit(), image=image)
    for fact, used in zip(given, built_on, strict=True):
        if used and isinstance(fact, Fact):
            slide.add_source(fact.source, fact.url, facts.credit(fact), text=True)
    generated = [value for value in (*texts.values(), *images.values()) if value is not None]
    return slide, generated


def _find(
    source: ImageSlot | ContentSource, query: str, presentation_context: dict[str, Any], others: list[ImageData]
) -> Any:
    """What a slot finds for the query (a v4 content generator: for the query as its seed)."""
    if isinstance(source, ImageSlot):
        return source.find(query, avoid=others)
    return source({**presentation_context, "seed": query})


@dataclass(frozen=True)
class _Search:
    """What a slot's search found (None for nothing), the query that found it, and what went wrong on the way."""

    found: Any
    query: str
    problems: tuple[str, ...] = ()


def _search(
    slot: str,
    source: ImageSlot | ContentSource,
    query: str,
    concept: str,
    presentation_context: dict[str, Any],
    avoid: list[ImageData],
    stream: random_util.Rng,
    *,
    behind: bool,
    required: bool,
    last: bool,
    own_query: bool,
) -> _Search:
    """A slot's picture, searched as written (among the best results) with its query and its own random stream, not one
    of those to avoid (nor nearly). One the slide can do without (behind, such as the picture behind a big number) is
    searched for with the slide's concept at once when its query finds none, and else left out, on any try, so the slide
    comes without it rather than not at all; one it needs is searched for with the concept on the last try. A query of
    the recipe's own (own_query) stays: a meme's captions are for its template, and no other."""
    problems: list[str] = []
    with random_util.use(stream), generator_util.as_planned():
        found = _find(source, query, presentation_context, avoid)
        if found is None and behind:
            if query != concept and not own_query:
                query = concept
                found = _find(source, concept, presentation_context, avoid)
        elif found is None and required:
            problems.append(f"{slot}: no image found for {query!r}")
            if last and query != concept and not own_query:
                query = concept
                found = _find(source, concept, presentation_context, avoid)
    return _Search(found, query, tuple(problems))


def _repeats(found: Any, others: Sequence[ImageData]) -> bool:
    """Whether a picture is one of the others, or nearly (as an image slot avoids them: see finder._pick)."""
    return isinstance(found, ImageData) and any(
        found == other or analysis.near_duplicates(found.analysis, other.analysis) for other in others
    )


_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()


def _at_once(tasks: Sequence[Callable[[], _T]]) -> list[_T]:
    """What the tasks give, in their order: run at the same time, each in a copy of this context (its random stream, how
    images are found and checked, the talk's pictures), the first here and the others in threads of their own
    (SEARCH_THREADS). Not in the image finder's, whose threads a search waits for: there, searches that wait for each
    other could take up every thread."""
    if len(tasks) <= 1:
        return [contextvars.copy_context().run(task) for task in tasks]
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=SEARCH_THREADS, thread_name_prefix="picture search")
        pool = _pool
    futures = [pool.submit(contextvars.copy_context().run, task) for task in tasks[1:]]
    first = contextvars.copy_context().run(tasks[0])
    return [first, *(future.result() for future in futures)]


def _local_image(query: str, folder: Path | None) -> str | None:
    """The image file a query names, if local images are allowed and it is one."""
    if folder is None or not query or not os_util.is_image(query):
        return None
    path = Path(query).expanduser()
    path = path if path.is_absolute() else folder / path
    return str(path) if path.is_file() else None


def _note(problems: list[str] | None, problem: str) -> None:
    if problems is not None and problem not in problems:
        problems.append(problem)
