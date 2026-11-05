"""Turning a planned slide into a slide: its texts checked and trimmed, its images found with its queries.

Realizing a slide only depends on its plan, its recipe, its presentation context and the attempt's random stream,
never on the other slides: so slides can be realized in parallel, in any order, and a talk still comes out the same
(the schema settles them in order, and rejects one that repeats what the slides before it used).
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator.checks.deck import leftovers_in
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.plan import SlidePlan
from talkgenerator.plan.kinds import KINDS, Recipe, TextField
from talkgenerator.slide.slides import Slide
from talkgenerator.util import random_util

# The first attempt searches with the plan's queries, the second tries other images for them, and the last searches
# for the slide's concept instead
ATTEMPTS: Final = 3

_QUOTE_MARKS: Final = "\"'“”‘’«»"


def clean_text(value: Any, text_field: TextField) -> str | None:
    """The text as it goes on a slide: on one line, without wrapping quote marks, at most the field's length (cut
    between words). None when it's empty, or holds bits of templates or code."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split()).strip(_QUOTE_MARKS + " ")
    if not text or leftovers_in(text):
        return None
    if len(text) > text_field.max_length:
        cut = text[: text_field.max_length + 1].rsplit(" ", 1)[0].rstrip(",;:-–— ")
        text = cut or text[: text_field.max_length]
    return text


def realize(
    plan: SlidePlan,
    recipe: Recipe,
    presentation_context: dict[str, Any],
    rng: random_util.Rng,
    attempt: int,
) -> tuple[Slide, list[Any]] | None:
    """A planned slide as a slide, with what it's made of (to check for repeats). None if anything it needs is
    missing: a text, or an image the sources couldn't find."""
    kind = KINDS[recipe.kind]
    concept = plan.concept.strip() or str(presentation_context.get("seed") or "")
    with random_util.use(rng.child("attempt", attempt)):
        texts: dict[str, str | None] = {}
        for text_field in kind.texts:
            if text_field.name in recipe.omit:
                texts[text_field.name] = None
                continue
            if text_field.name in recipe.texts_from:
                found = recipe.texts_from[text_field.name]({**presentation_context, "seed": concept})
                texts[text_field.name] = clean_text(found, text_field)
            else:
                texts[text_field.name] = clean_text(plan.texts.get(text_field.name), text_field)
            if texts[text_field.name] is None and not text_field.optional:
                return None

        images: dict[str, Any] = {}
        queries: dict[str, str] = {}
        for slot, source in zip(kind.images, recipe.images, strict=True):
            query = plan.images.get(slot, "").strip()
            queries[slot] = concept if attempt >= ATTEMPTS - 1 or not query else query
            images[slot] = source({**presentation_context, "seed": queries[slot]})

        try:
            slide = kind.build(texts, images)
        except (ValueError, KeyError):
            return None

    if slide.missing_content():
        return None
    slide.set_note(
        f"Seed: {presentation_context.get('seed')}\nPlanned: a {recipe.kind} slide for {plan.recipe}, about {concept!r}"
        f"\nTexts: {texts}\nImage queries: {queries}"
    )
    for image in images.values():
        if isinstance(image, ImageData):
            slide.add_source(image.get_source(), image.get_source_url(), image.get_credit())
    generated = [value for value in (*texts.values(), *images.values()) if value is not None]
    return slide, generated
