"""The texts of milestone 6's slide types, the classic way: big numbers and KPI tiles, quizzes, social media posts and
news headlines, an agenda, a section's divider and the closing "Questions?" (docs/v5-plan.md, section 8).

They come from templates (`data/text-templates/slide_texts.json`) about the slide's seed, with the words ConceptNet
relates to it where a slide needs more than one thing (a quiz's options, an agenda's items), and numbers made up
here. Each generator takes a presentation context and returns its Slide class's arguments (or None when it can't make
one), for `talkgenerator.slide.slide_generator_types.DrawnSlideGenerator`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import cache
from typing import Any, Final

from talkgenerator.sources import conceptnet, text_generator
from talkgenerator.util import random_util

_TEMPLATES: Final = "data/text-templates/slide_texts.json"
_LONGEST_WORD: Final = 24  # a related word longer than this is a phrase that doesn't fit an option or an item
ImageSource = Callable[[dict[str, Any]], Any]


@cache
def _template(name: str) -> Callable[[dict[str, Any]], str | None]:
    generate: Callable[[dict[str, Any]], str | None] = text_generator.TraceryTextGenerator(_TEMPLATES, name).generate
    return generate


_full_name = text_generator.TraceryTextGenerator("data/text-templates/name.json", "full_name").generate


def related_words(seed: str, count: int = 12) -> list[str]:
    """Words that ConceptNet relates to the seed, the weightiest first: short ones, without the seed, capitalised."""
    entries = conceptnet.get_weighted_related_words(seed, 30) or []
    kept = conceptnet.remove_duplicates(conceptnet.remove_containing(list(entries), seed.lower()) or []) or []
    words = [str(word).strip() for _, word in sorted(kept, key=lambda entry: -entry[0])]
    return [_capitalised(word) for word in words if word and len(word) <= _LONGEST_WORD][:count]


def _context(presentation_context: dict[str, Any], related: list[str] | None = None) -> dict[str, Any]:
    """The variables the templates use: the seed, and a word related to it (if any)."""
    variables = {"seed": presentation_context["seed"]}
    if related:
        variables["related"] = random_util.choice(related).lower()
    return variables


def _maybe(chance: float, text: str | None) -> str | None:
    """The text, that share of the time."""
    return text if random_util.random() < chance else None


# FIGURES


def _thousands(number: int) -> str:
    return f"{number:,}"


def _figure(kind: str) -> str:
    """A made-up number of a kind: a percentage, a count, or a ratio ("1 in 7")."""
    if kind == "percent":
        return random_util.choice((f"{random_util.randint(3, 99)}%", "0.3%", "110%", f"{random_util.randint(51, 97)}%"))
    if kind == "ratio":
        return f"1 in {random_util.choice((3, 4, 5, 7, 8, 10, 12))}"
    return random_util.choice(
        (
            str(random_util.randint(2, 99)),
            _thousands(random_util.randint(1000, 99999)),
            f"{random_util.randint(2, 9)}.{random_util.randint(1, 9)} million",
            f"{random_util.randint(2, 12)} billion",
        )
    )


def generate_big_number(presentation_context: dict[str, Any]) -> tuple[str | None, str, str, str | None] | None:
    """A big number about the seed, with what it counts and a made-up source: a title, the number, its label, the
    source."""
    kind = random_util.choice(("percent", "percent", "count", "ratio"))
    variables = _context(presentation_context)
    label = _template(f"{kind}_label")(variables)
    if not label:
        return None
    title = _maybe(0.6, _template("big_number_title")(variables))
    return title, _figure(kind), label, _maybe(0.7, _template("big_number_source")(variables))


def _kpi_number(punchline: bool) -> str:
    if punchline:
        return random_util.choice(("0", "∞", "1", "-100%", "9,001", "404"))
    return random_util.choice(
        (
            f"+{random_util.randint(2, 48)}%",
            f"-{random_util.randint(2, 30)}%",
            _thousands(random_util.randint(120, 9999)),
            str(random_util.randint(2, 99)),
            f"{random_util.randint(2, 9)}.{random_util.randint(1, 9)}M",
        )
    )


def generate_kpi(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """Three or four made-up figures about the seed, as on a dashboard, the last one a punchline: a title, then
    every figure's number and label."""
    related = related_words(presentation_context["seed"])
    variables = _context(presentation_context, related)
    title = _template("kpi_title")(variables)
    count = 4 if random_util.random() < 0.4 else 3
    labels: list[str] = []
    for _ in range(50):  # (different labels, from different related words)
        if len(labels) == count - 1:
            break
        label = _template("kpi_label")(_context(presentation_context, related))
        if label and label not in labels:
            labels.append(label)
    punchline = _template("kpi_punchline")(_context(presentation_context, related))
    if not title or len(labels) < count - 1 or not punchline:
        return None
    figures: list[str | None] = []
    for label in labels:
        figures += [_kpi_number(False), label]
    figures += [_kpi_number(True), punchline]
    return (title, *figures)


# A QUIZ


def generate_quiz(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A quiz about the seed, its options things ConceptNet relates to it: the question, four options (the fourth
    may be None), the right one's letter (any: the presenter explains why), and an explanation, if any."""
    related = related_words(presentation_context["seed"])
    count = 4 if len(related) >= 4 and random_util.random() < 0.6 else 3
    if len(related) < count:
        return None
    variables = _context(presentation_context)
    question = _template("quiz_question")(variables)
    if not question:
        return None
    options: list[str | None] = list(random_util.sample(related, count))
    options += [None] * (4 - count)
    answer = "ABCD"[random_util.randrange(count)]
    return (question, *options, answer, _maybe(0.6, _template("quiz_explanation")(variables)))


# MOCKUPS


def _handle(name: str, seed: str) -> str:
    """A made-up username, from the poster's name and the seed: "anna_socks", "socksfan42"..."""
    first = re.sub(r"[^a-z]", "", name.split()[0].lower()) if name.split() else "anon"
    topic = re.sub(r"[^a-z0-9]", "", seed.lower())[:12] or "topic"
    forms = (f"{first}_{topic}", f"{topic}fan{random_util.randint(2, 99)}", f"real{first}{random_util.randint(1, 9)}")
    return random_util.choice(forms)


def social_post(image: ImageSource) -> Callable[[dict[str, Any]], tuple[Any, ...] | None]:
    """A generator of made-up social media posts about the seed, with a photo from the image source: a title (if
    any), the poster's name and username, the post, its photo, and how often it was liked and shared."""

    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        variables = _context(presentation_context)
        author = _full_name({})
        text = _template("post_text")(variables)
        if not author or not text:
            return None
        photo = image(dict(presentation_context))
        if photo is None:
            return None
        likes = round(10 ** random_util.uniform(1.5, 6.3))
        shares = round(likes * random_util.uniform(0.02, 0.4))
        title = _maybe(0.3, _template("post_title")(variables))
        return title, author, _handle(author, presentation_context["seed"]), text, photo, likes, shares

    return generate


def news_headline(image: ImageSource) -> Callable[[dict[str, Any]], tuple[Any, ...] | None]:
    """A generator of made-up news stories about the seed, with a photo from the image source: the outlet, the
    headline, a subheadline (if any) and the photo."""

    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        variables = _context(presentation_context)
        outlet = _template("news_outlet")(variables)
        headline = _template("news_headline")(variables)
        if not outlet or not headline:
            return None
        photo = image(dict(presentation_context))
        if photo is None:
            return None
        return outlet, headline, _maybe(0.7, _template("news_subheadline")(variables)), photo

    return generate


# THE TALK'S STRUCTURE


def generate_agenda(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """An agenda for a talk about the seed: a title, and three to five items (an opening, things related to the seed,
    and an end)."""
    related = related_words(presentation_context["seed"])
    variables = _context(presentation_context)
    title = _template("agenda_title")(variables)
    first, last = _template("agenda_first")(variables), _template("agenda_last")(variables)
    middle: list[str] = []
    wanted = random_util.randint(1, 3)
    for _ in range(50):
        if len(middle) == wanted:
            break
        item = _template("agenda_item")(_context(presentation_context, related))
        if item and item not in middle:
            middle.append(item)
    if not title or not first or not last or not middle:
        return None
    return title, first, *middle, last


def generate_section(presentation_context: dict[str, Any]) -> tuple[str, str | None] | None:
    """A section's divider about the seed: its title and subtitle (if any). The deck numbers it."""
    variables = _context(presentation_context)
    title = _template("section_title")(variables)
    if not title:
        return None
    return title, _maybe(0.5, _template("section_subtitle")(variables))


def generate_questions(presentation_context: dict[str, Any]) -> tuple[str, str | None] | None:
    """The closing slide: a question to the audience, and a subtitle (if any)."""
    variables = _context(presentation_context)
    title = _template("questions_title")(variables)
    if not title:
        return None
    return title, _maybe(0.6, _template("questions_subtitle")(variables))


def _capitalised(text: str) -> str:
    return text[:1].upper() + text[1:]
