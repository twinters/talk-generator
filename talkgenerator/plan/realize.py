"""Turning a planned slide into a slide: its texts checked and trimmed, its images found with its queries.

Realizing a slide only depends on its plan, its recipe, its presentation context and the attempt's random stream,
never on the other slides: so slides can be realized in parallel, in any order, and a talk still comes out the same
(the schema settles them in order, and rejects one that repeats what the slides before it used).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Final

from talkgenerator.checks.deck import leftovers_in, real_politics, without_key_references
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import context as image_context
from talkgenerator.images.generation import FALLBACK, FIRST, Wish
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, ContentSource, Recipe, TextField
from talkgenerator.slide.slides import Slide
from talkgenerator.util import generator_util, language_util, os_util, random_util

logger = logging.getLogger("talkgenerator")

# The first attempt searches with the plan's queries, the second tries other images for them, and the last searches
# for the slide's concept for the images whose queries find nothing
ATTEMPTS: Final = 3

_QUOTE_MARKS: Final = "\"'“”‘’«»"
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
# A backslash before a quote mark, as some models escape one where their JSON needn't (what\'s)
_STRAY_ESCAPE: Final = re.compile(r"\\(?=['\"’])")


def length_limit(text_field: TextField) -> int:
    """How long a text of the field may be before it's cut: a little longer than the field's length (by an eighth,
    or at least four characters), as a few characters too many rarely spoil a slide, and a phrase cut off always
    does."""
    return text_field.max_length + max(4, text_field.max_length // 8)


def clean_text(value: Any, text_field: TextField, language: str = "en") -> str | None:
    """The text as it goes on a slide: on one line, without wrapping quote marks or brackets that name a slide by its
    key in the model's answer ("(from slide_03)"), and cut to the field's length when it's longer than its
    length_limit (between words, and not after a little word of its language, such as "the"), or the option it names
    when the field is a choice. None when it's empty, names no option, or holds bits of templates or code (a slide's
    key elsewhere in it too: see talkgenerator.checks.deck)."""
    if not isinstance(value, str):
        return None
    value = without_key_references(value)  # (a callback that names its slide by its key keeps the rest of it)
    if text_field.options:
        return option_of(value, text_field)
    text = _unquoted(" ".join(_STRAY_ESCAPE.sub("", value).split()))
    if not text or leftovers_in(text):
        return None
    if len(text) > length_limit(text_field):
        text = _cut(text, text_field.max_length, language)
    return text


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
    """The text cut to its length: where a sentence or a clause in it ends, if that keeps at least half of it ("Your
    plants are not decorations", of "Your plants are not decorations—they're coworkers who need feedback"), or in
    English before a word that opens the next clause ("The mountain breathes", of "The mountain breathes when prayers
    are whispered"), or else after a comma ("Professor of Serenity Studies", of a long affiliation), or else between
    words, without the little words and punctuation that a cut leaves hanging at its end (as in "Cats were the true
    scholars of the"), and before a bracket it would leave open, if that keeps a third of it ("Kaito Tanaka", of
    "Kaito Tanaka (Head of Temporal Planning)")."""
    head = text[: length + 1]
    little = _little_words(language)
    ends = [end.start() + (1 if end.group(0) in ".!?" else 0) for end in _CLAUSE_END.finditer(head)]
    starts = [start.start() for start in _CLAUSE_START.finditer(head)] if language == "en" else []
    commas = [comma.start() for comma in _COMMA.finditer(head)]
    for at in (*reversed(ends), *reversed(starts), *reversed(commas)):
        clause = head[:at].rstrip(_DANGLING)
        last = clause.rsplit(" ", 1)[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower()
        if len(clause) >= length // 2 and last not in little:
            return clause
    if " " not in head:  # one long word
        return text[:length]
    words = head.rsplit(" ", 1)[0].split()
    while len(words) > 1 and words[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower() in little | {""}:
        words.pop()
    cut = " ".join(words).rstrip(_DANGLING)
    opened = _OPEN_BRACKET.search(cut)
    if opened is not None and len(cut[: opened.start()].rstrip(_DANGLING)) >= length // 3:
        cut = cut[: opened.start()].rstrip(_DANGLING)
    return cut or text[:length]


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
) -> tuple[Slide, list[Any]] | None:
    """A planned slide as a slide, with what it's made of (to check for repeats). None if anything it needs is
    missing: a text, or an image the sources couldn't find; problems then gets why.

    With local_images (a folder), an image "query" that names an image file (relative to that folder, or absolute)
    puts that file on the slide: for plans that people or agents write, never for what a language model wrote."""
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
                found = recipe.texts_from[name]({**presentation_context, "seed": concept})
                texts[name] = clean_text(found, text_field, language)
                why = f"{name}: talkgenerator found none about {concept!r}"
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

        images: dict[str, Any] = dict.fromkeys(slot for slot in kind.images if slot in recipe.omit)
        queries: dict[str, str] = {}
        talk = image_context.current()
        generation = talk.generation
        last = attempt >= ATTEMPTS - 1
        wishes: list[tuple[str, Wish]] = []  # the pictures to generate in place of their stock photos
        unfound: list[Wish] = []  # the pictures to generate, as their slots found none (on the last try)
        for slot, source in recipe.slots():
            # (what the recipe has it search for, such as a meme's template, or the plan's query)
            query = recipe.queries.get(slot) or plan.images.get(slot, "").strip()
            local = _local_image(query, local_images)
            if local is not None:
                queries[slot], images[slot] = query, ImageData(local).found_with(query)
                continue
            queries[slot] = query or concept
            # (not one of the slide's other images, nor nearly)
            others = [image for image in images.values() if isinstance(image, ImageData)]
            with generator_util.as_planned():  # searched as written, among the best results
                found = _find(source, queries[slot], presentation_context, others)
            if found is None:
                _note(problems, f"{slot}: no image found for {queries[slot]!r}")
                # (a query of the recipe's own stays: a meme's captions are for its template, and no other)
                if last and queries[slot] != concept and slot not in recipe.queries:
                    queries[slot] = concept
                    with generator_util.as_planned():
                        found = _find(source, concept, presentation_context, others)
            wish = None
            if generation is not None and isinstance(source, ImageSlot):
                look = talk.look(source.aesthetic)
                prompt = plan.prompts.get(slot)
                stream = rng.child("generated", slot)  # (the same seed on every try)
                if found is None and last and generation.fills(source, look):
                    wish = generation.wish(source, slot, FALLBACK, query or concept, stream, prompt, look)
                elif found is not None and generation.prefers(source):
                    wish = generation.wish(source, slot, FIRST, query or concept, stream, prompt, look)
            if found is None and wish is not None:
                unfound.append(wish)
                continue
            if found is None:
                return None
            images[slot] = found.found_with(queries[slot]) if isinstance(found, ImageData) else found
            if wish is not None and isinstance(images[slot], ImageData):
                wishes.append((slot, wish))

        if unfound:
            # (the slide's last try, which runs while it's settled, in order: so the talk grants the same pictures,
            # made in parallel or one by one; and all of them or none, as the slide needs them all)
            assert generation is not None
            pictures = generation.fill(unfound)
            if pictures is None:
                _note(problems, "no picture could be generated for " + ", ".join(wish.slot for wish in unfound))
                return None
            for wish, picture in zip(unfound, pictures, strict=True):
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
    slide.set_note(
        f"Seed: {presentation_context.get('seed')}\nPlanned: a {recipe.kind} slide for {plan.recipe}, about {concept!r}"
        f"\nTexts: {texts}\nImage queries: {queries}"
        + "".join(f"\nTo generate ({wish.reason}) for {wish.slot}: {wish.request.prompt!r}" for _, wish in slide.wishes)
    )
    for image in images.values():
        if isinstance(image, ImageData):
            slide.add_source(image.get_source(), image.get_source_url(), image.get_credit(), image=image)
    generated = [value for value in (*texts.values(), *images.values()) if value is not None]
    return slide, generated


def _find(
    source: ImageSlot | ContentSource, query: str, presentation_context: dict[str, Any], others: list[ImageData]
) -> Any:
    """What a slot finds for the query (a v4 content generator: for the query as its seed)."""
    if isinstance(source, ImageSlot):
        return source.find(query, avoid=others)
    return source({**presentation_context, "seed": query})


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
