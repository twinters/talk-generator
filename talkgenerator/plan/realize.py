"""Turning a planned slide into a slide: its texts checked and trimmed, its images found with its queries.

Realizing a slide only depends on its plan, its recipe, its presentation context and the attempt's random stream,
never on the other slides: so slides can be realized in parallel, in any order, and a talk still comes out the same
(the schema settles them in order, and rejects one that repeats what the slides before it used).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from talkgenerator.checks.deck import leftovers_in, without_key_references
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import context as image_context
from talkgenerator.images.generation import FALLBACK, FIRST, Wish
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan import languages
from talkgenerator.plan.kinds import KINDS, ContentSource, Recipe, TextField
from talkgenerator.slide.slides import Slide
from talkgenerator.util import generator_util, language_util, os_util, random_util

# The first attempt searches with the plan's queries, the second tries other images for them, and the last searches
# for the slide's concept for the images whose queries find nothing
ATTEMPTS: Final = 3

_QUOTE_MARKS: Final = "\"'“”‘’«»"
# What a cut may leave at the end of a text, besides little words: punctuation that leads on to more
_DANGLING: Final = ",;:-–—([{/&+ "


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
    text = " ".join(value.split()).strip(_QUOTE_MARKS + " ")
    if not text or leftovers_in(text):
        return None
    if len(text) > length_limit(text_field):
        text = _cut(text, text_field.max_length, language)
    return text


def _cut(text: str, length: int, language: str) -> str:
    """The text cut to its length between words, without the little words and punctuation that a cut leaves
    hanging at its end (as in "Cats were the true scholars of the")."""
    head = text[: length + 1]
    if " " not in head:  # one long word
        return text[:length]
    words = head.rsplit(" ", 1)[0].split()
    little = _little_words(language)
    while len(words) > 1 and words[-1].strip(_DANGLING + _QUOTE_MARKS + ".!?").lower() in little | {""}:
        words.pop()
    cut = " ".join(words).rstrip(_DANGLING)
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
