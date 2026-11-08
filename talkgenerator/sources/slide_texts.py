"""The texts of milestone 6's slide types, the classic way: big numbers and KPI tiles, quizzes, social media posts and
news headlines, an agenda, a section's divider and the closing "Questions?" (docs/v5-plan.md, section 8).

They come from the TED content pack's templates (`data/packs/ted`: see talkgenerator.sources.packs) about the slide's
seed, with the words ConceptNet relates to it where a slide needs more than one thing (a quiz's options, an agenda's
items), and numbers made up here. Each generator takes a presentation context and returns its Slide class's arguments
(or None when it can't make one), for `talkgenerator.slide.slide_generator_types.DrawnSlideGenerator`. A talk's seeds
wander from its topic, so words on faiths, violence and hate, or not for a family audience, are left out: a slide whose
seed is one of them isn't made this way (another kind of slide takes its place), and such related words are skipped.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable
from functools import cache
from typing import Any, Final, TypeVar

from talkgenerator.plan.languages import ENGLISH
from talkgenerator.sources import conceptnet, memes, packs, text_generator
from talkgenerator.util import language_util, random_util

_LONGEST_WORD: Final = 24  # a related word longer than this is a phrase that doesn't fit an option or an item
ImageSource = Callable[[dict[str, Any]], Any]
# Words a slide shouldn't make light of (see the module's documentation)
_SENSITIVE: Final = frozenset(
    ("islam", "islamic", "muslim", "muslims", "jihad", "allah", "quran", "koran", "mosque", "shia", "sunni", "imam")
    + ("christian", "christianity", "christ", "jesus", "god", "gods", "bible", "church", "pope", "satan", "devil")
    + ("jew", "jews", "jewish", "judaism", "synagogue", "torah", "rabbi", "hindu", "hinduism", "buddha", "buddhist")
    + ("buddhism", "sikh", "prophet", "religion", "religious", "kill", "killing", "killer", "murder", "rape")
    + ("suicide", "terror", "terrorist", "terrorism", "bomb", "nazi", "nazis", "hitler", "genocide", "holocaust")
    + ("slave", "slavery", "racist", "racism", "sex", "sexual", "sexy", "porn", "nude", "naked", "penis", "vagina")
    + ("drug", "drugs", "cocaine", "heroin", "abuse", "torture", "weapon", "gun", "guns", "corpse", "death")
)


@cache
def _template(name: str) -> Callable[[dict[str, Any]], str | None]:
    """A generator of a rule's texts, by its full name in the TED pack ("numbers.kpi_title")."""
    generate: Callable[[dict[str, Any]], str | None] = packs.pack(packs.TED).tracery(name)
    return generate


_full_name = text_generator.TraceryTextGenerator("data/text-templates/name.json", "full_name").generate


def _rule(name: str) -> list[str]:
    """A rule's templates (or words), by its full name in the TED pack ("karaoke.tier_list_worst")."""
    return packs.pack(packs.TED).rule(name)


def sensitive(text: str) -> bool:
    """Whether a text has a word that a slide shouldn't make light of (a faith, violence, hate...)."""
    return any(word in _SENSITIVE for word in re.findall(r"[a-z]+", text.lower()))


def related_words(seed: str, count: int = 12) -> list[str]:
    """Words that ConceptNet relates to the seed, the weightiest first: short ones, without the seed or sensitive
    words, capitalised."""
    entries = conceptnet.get_weighted_related_words(seed, 30) or []
    kept = conceptnet.remove_duplicates(conceptnet.remove_containing(list(entries), seed.lower()) or []) or []
    words = [str(word).strip() for _, word in sorted(kept, key=lambda entry: -entry[0])]
    usable = [word for word in words if word and len(word) <= _LONGEST_WORD and not sensitive(word)]
    return [_capitalised(word) for word in usable][:count]


Generated = TypeVar("Generated")


def _unless_sensitive(
    generate: Callable[[dict[str, Any]], Generated | None],
) -> Callable[[dict[str, Any]], Generated | None]:
    """The generator, making nothing for a slide whose seed is sensitive."""

    @functools.wraps(generate)
    def generator(presentation_context: dict[str, Any]) -> Generated | None:
        return None if sensitive(str(presentation_context["seed"])) else generate(presentation_context)

    return generator


def _context(presentation_context: dict[str, Any], related: list[str] | None = None) -> dict[str, Any]:
    """The variables the templates use: the seed, and a word related to it (if any)."""
    variables = {"seed": presentation_context["seed"]}
    if related:
        variables["related"] = random_util.choice(related).lower()
    return variables


def _maybe(chance: float, text: str | None) -> str | None:
    """The text, that share of the time."""
    return text if random_util.random() < chance else None


def _different(name: str, presentation_context: dict[str, Any], related: list[str], count: int) -> list[str]:
    """That many texts from a list of templates, each from a template of its own, and those about a related word each
    about another one (fewer if there aren't enough)."""
    words = list(related)
    found: list[str] = []
    templates = _rule(name)
    for template in random_util.sample(templates, len(templates)):
        if len(found) == count:
            break
        variables = {"seed": presentation_context["seed"]}
        if "{related" in template:
            if not words:
                continue
            word = random_util.choice(words)
            words.remove(word)
            variables["related"] = word.lower()
        text = text_generator.apply_variables_to_template(template, variables)
        if text and text not in found:
            found.append(text)
    return found


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


@_unless_sensitive
def generate_big_number(presentation_context: dict[str, Any]) -> tuple[str | None, str, str, str | None] | None:
    """A big number about the seed, with what it counts and a made-up source: a title, the number, its label, the
    source."""
    kind = random_util.choice(("percent", "percent", "count", "ratio"))
    variables = _context(presentation_context)
    label = _template(f"numbers.{kind}_label")(variables)
    if not label:
        return None
    title = _maybe(0.6, _template("numbers.big_number_title")(variables))
    return title, _figure(kind), label, _maybe(0.7, _template("numbers.big_number_source")(variables))


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


@_unless_sensitive
def generate_kpi(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """Three or four made-up figures about the seed, as on a dashboard, the last one a punchline: a title, then
    every figure's number and label."""
    related = related_words(presentation_context["seed"])
    variables = _context(presentation_context, related)
    title = _template("numbers.kpi_title")(variables)
    count = 4 if random_util.random() < 0.4 else 3
    labels = _different("numbers.kpi_label", presentation_context, related, count - 1)
    punchline = _template("numbers.kpi_punchline")(_context(presentation_context, related))
    if not title or len(labels) < count - 1 or not punchline:
        return None
    figures: list[str | None] = []
    for label in labels:
        figures += [_kpi_number(False), label]
    figures += [_kpi_number(True), punchline]
    return (title, *figures)


# A QUIZ


@_unless_sensitive
def generate_quiz(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A quiz about the seed, its options things ConceptNet relates to it: the question, four options (the fourth
    may be None), the right one's letter (any: the presenter explains why), and an explanation, if any."""
    related = related_words(presentation_context["seed"])
    count = 4 if len(related) >= 4 and random_util.random() < 0.6 else 3
    if len(related) < count:
        return None
    variables = _context(presentation_context)
    question = _template("quiz.quiz_question")(variables)
    if not question:
        return None
    options: list[str | None] = list(random_util.sample(related, count))
    options += [None] * (4 - count)
    answer = "ABCD"[random_util.randrange(count)]
    return (question, *options, answer, _maybe(0.6, _template("quiz.quiz_explanation")(variables)))


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

    @_unless_sensitive
    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        variables = _context(presentation_context)
        author = _full_name({})
        text = _template("mockups.post_text")(variables)
        if not author or not text:
            return None
        photo = image(dict(presentation_context))
        if photo is None:
            return None
        likes = round(10 ** random_util.uniform(1.5, 6.3))
        shares = round(likes * random_util.uniform(0.02, 0.4))
        title = _maybe(0.3, _template("mockups.post_title")(variables))
        return title, author, _handle(author, presentation_context["seed"]), text, photo, likes, shares

    return generate


def news_headline(image: ImageSource) -> Callable[[dict[str, Any]], tuple[Any, ...] | None]:
    """A generator of made-up news stories about the seed, with a photo from the image source: the outlet, the
    headline, a subheadline (if any) and the photo."""

    @_unless_sensitive
    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        variables = _context(presentation_context)
        outlet = _template("mockups.news_outlet")(variables)
        headline = _template("mockups.news_headline")(variables)
        if not outlet or not headline:
            return None
        photo = image(dict(presentation_context))
        if photo is None:
            return None
        return outlet, headline, _maybe(0.7, _template("mockups.news_subheadline")(variables)), photo

    return generate


def meme(image: ImageSource) -> Callable[[dict[str, Any]], tuple[Any, ...] | None]:
    """A generator of memes about the seed: one of the templates talkgenerator knows the boxes of (talkgenerator.sources
    .memes), picked by the talk's dice, its picture from the image source (searched for the template), and captions
    from the template's own sentences about the seed and the words related to it, one per box."""

    @_unless_sensitive
    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        template = random_util.choice(list(memes.templates().values()))
        needing = [any("{related" in caption for caption in captions) for captions in template.classic]
        related = related_words(str(presentation_context["seed"])) if any(needing) else []
        options = [captions for captions, needs in zip(template.classic, needing, strict=True) if related or not needs]
        if not options:
            return None
        variables = _context(presentation_context, related)
        captions = [
            text_generator.apply_variables_to_template(caption, variables) for caption in random_util.choice(options)
        ]
        if not all(captions):
            return None
        picture = image({**presentation_context, "seed": template.id})
        if picture is None:
            return None
        return (picture, *template.texts(captions))

    return generate


# THE TALK'S STRUCTURE


@_unless_sensitive
def generate_agenda(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """An agenda for a talk about the seed: a title, and three to five items (an opening, things related to the seed,
    and an end)."""
    related = related_words(presentation_context["seed"])
    variables = _context(presentation_context)
    title = _template("structure.agenda_title")(variables)
    first, last = _template("structure.agenda_first")(variables), _template("structure.agenda_last")(variables)
    middle = _different("structure.agenda_item", presentation_context, related, random_util.randint(1, 3))
    if not title or not first or not last or not middle:
        return None
    return title, first, *middle, last


@_unless_sensitive
def generate_section(presentation_context: dict[str, Any]) -> tuple[str, str | None] | None:
    """A section's divider about the seed: its title and subtitle (if any). The deck numbers it."""
    variables = _context(presentation_context)
    title = _template("structure.section_title")(variables)
    if not title:
        return None
    return title, _maybe(0.5, _template("structure.section_subtitle")(variables))


@_unless_sensitive
def generate_questions(presentation_context: dict[str, Any]) -> tuple[str, str | None] | None:
    """The closing slide: a question to the audience, and a subtitle (if any)."""
    variables = _context(presentation_context)
    title = _template("structure.questions_title")(variables)
    if not title:
        return None
    return title, _maybe(0.6, _template("structure.questions_subtitle")(variables))


# NATIVE DIAGRAMS


@_unless_sensitive
def generate_timeline(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A made-up history of the seed: a title, then three to five dates (oldest first) each with what happened then,
    the last one a punchline."""
    related = related_words(presentation_context["seed"])
    count = random_util.randint(3, 5)
    title = _template("diagrams.timeline_title")(_context(presentation_context))
    events = _different("diagrams.timeline_event", presentation_context, related, count - 1)
    punchline = _template("diagrams.timeline_punchline")(_context(presentation_context, related))
    if not title or len(events) < count - 1 or not punchline:
        return None
    known = _rule("diagrams.timeline_dates")  # (oldest first)
    dates = sorted(random_util.sample(range(len(known)), count))
    moments: list[str | None] = []
    for date, event in zip(dates, [*events, punchline], strict=True):
        moments += [known[date], event]
    return (title, *moments)


@_unless_sensitive
def generate_pyramid(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A hierarchy of needs about the seed: a title, then three or four levels from the top (the seed itself) down to
    the base (something everyone needs), with words related to the seed between them."""
    related = related_words(presentation_context["seed"])
    count = 4 if len(related) >= 2 and random_util.random() < 0.5 else 3
    if len(related) < count - 2:
        return None
    title = _template("diagrams.pyramid_title")(_context(presentation_context))
    base = _template("diagrams.pyramid_base")({})
    if not title or not base:
        return None
    return title, _capitalised(presentation_context["seed"]), *random_util.sample(related, count - 2), base


@_unless_sensitive
def generate_funnel(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A funnel about the seed: a title, then three to five stages, words related to the seed narrowing down to a
    punchline."""
    related = related_words(presentation_context["seed"])
    count = min(random_util.randint(3, 5), len(related) + 1)
    if count < 3:
        return None
    title = _template("diagrams.funnel_title")(_context(presentation_context, related))
    punchline = _template("diagrams.funnel_punchline")(_context(presentation_context))
    if not title or not punchline:
        return None
    return title, *random_util.sample(related, count - 1), punchline


@_unless_sensitive
def generate_cycle(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A cycle about the seed: a title, then three to five words related to it, each leading to the next."""
    related = [word for word in related_words(presentation_context["seed"]) if len(word) <= 24]
    count = min(random_util.randint(3, 5), len(related))
    if count < 3:
        return None
    title = _template("diagrams.cycle_title")(_context(presentation_context))
    if not title:
        return None
    return title, *random_util.sample(related, count)


@_unless_sensitive
def generate_org_chart(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """Who's in charge of the seed: a title, the boss (the punchline), and two to four people under them, each in
    charge of something related to the seed."""
    related = related_words(presentation_context["seed"])
    if len(related) < 2:
        return None
    title = _template("diagrams.org_chart_title")(_context(presentation_context))
    boss = _template("diagrams.org_chart_boss")(_context(presentation_context))
    reports = _different("diagrams.org_chart_report", presentation_context, related, random_util.randint(2, 4))
    if not title or not boss or len(reports) < 2:
        return None
    return title, boss, *reports


@_unless_sensitive
def generate_iceberg(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """An iceberg of the seed: a title, the seed on its tip, and two or three things under the water."""
    related = related_words(presentation_context["seed"])
    title = _template("diagrams.iceberg_title")(_context(presentation_context))
    hidden = _different("diagrams.iceberg_hidden", presentation_context, related, random_util.randint(2, 3))
    if not title or len(hidden) < 2:
        return None
    return title, _capitalised(presentation_context["seed"]), *hidden


# SLIDE TYPES FROM POWERPOINT KARAOKE DECKS (their templates say "{seed.generic}": "penguins", but "coffee"; and no
# verb agrees with the seed, which may be either)


def _numbers() -> dict[str, str]:
    """Made-up numbers for a template: a count, a percentage and a year."""
    return {
        "number": str(random_util.randint(3, 99)),
        "percent": f"{random_util.randint(3, 97)}%",
        "year": random_util.choice(_rule("karaoke.fun_fact_years")),
    }


def fun_fact(image: ImageSource) -> Callable[[dict[str, Any]], tuple[Any, ...] | None]:
    """A generator of fun facts about the seed: a heading ("Did you know?"), the fact (from templates about the seed
    and a word related to it, with made-up numbers), a made-up source (if any) and a photo from the image source (three
    times in five, when it finds one)."""

    @_unless_sensitive
    def generate(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
        related = related_words(presentation_context["seed"])
        variables = {**_context(presentation_context, related), **_numbers()}
        fact = _template("karaoke.fun_fact")(variables)
        if not fact:
            return None
        source = _maybe(0.7, _template("numbers.big_number_source")(variables))
        photo = image(dict(presentation_context)) if random_util.random() < 0.6 else None
        return random_util.choice(ENGLISH.fun_facts), fact, source, photo

    return generate


# An acronym's words: corporate buzzwords for its letters (when no word related to the seed starts with one), and
# something absurd for its last letter, the punchline: the pack's karaoke.buzzword_a... and karaoke.absurd_a...,
# and the method names everyone has heard (karaoke.acronyms)


def _acronym_word(seed: str, related: list[str]) -> str:
    """The word an acronym spells: the seed, or a word related to it, of three to six plain letters; or else one of
    the method names everyone has heard."""
    for word in (seed, *related):
        if word.isascii() and word.isalpha() and 3 <= len(word) <= 6:
            return word.upper()
    return random_util.choice(_rule("karaoke.acronyms"))


@_unless_sensitive
def generate_acronym(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A made-up method about the seed, as an acronym that spells the seed (or a word related to it): a title, then
    the word every letter stands for, words related to the seed where one starts with the letter, else corporate
    buzzwords, and something absurd for the last letter."""
    seed = str(presentation_context["seed"])
    related = related_words(seed)
    acronym = _acronym_word(seed, related)
    words: list[str] = []
    for position, letter in enumerate(acronym):
        last = position == len(acronym) - 1
        # (never a word twice, nor the word it spells; a repeated letter's last word from the same pool stays)
        topical = (
            [word for word in related if word[:1].upper() == letter and word.upper() != acronym] if not last else []
        )
        known = _rule(f"karaoke.{'absurd' if last else 'buzzword'}_{letter.lower()}")
        pool = topical + [word for word in known if not topical]
        words.append(random_util.choice([word for word in pool if word not in words] or pool))
    title = _template("karaoke.acronym_title")({**_context(presentation_context), "acronym": acronym})
    return (title, *words) if title else None


@_unless_sensitive
def generate_dare(presentation_context: dict[str, Any]) -> tuple[str, str] | None:
    """A dare for the presenter (from a list of playful ones, some about the seed): its heading and the dare."""
    dare = _template("karaoke.dare")(_context(presentation_context, related_words(presentation_context["seed"])))
    return (ENGLISH.dare, dare) if dare else None


@_unless_sensitive
def generate_flowchart(presentation_context: dict[str, Any]) -> tuple[str | None, ...] | None:
    """A flowchart about the seed: a title (if any), a yes-or-no question, where yes and no lead, the end both lead
    to, and the words for yes and no."""
    related = related_words(presentation_context["seed"])
    question = _template("karaoke.flowchart_question")(_context(presentation_context))
    yes_step = _template("karaoke.flowchart_yes")(_context(presentation_context, related))
    no_step = _template("karaoke.flowchart_no")(_context(presentation_context, related))
    end = _template("karaoke.flowchart_end")(_context(presentation_context, related))
    title = _maybe(0.5, _template("karaoke.flowchart_title")(_context(presentation_context)))
    if not question or not yes_step or not no_step or not end:
        return None
    return title, question, yes_step, no_step, end, ENGLISH.yes, ENGLISH.no


@_unless_sensitive
def generate_tier_list(presentation_context: dict[str, Any]) -> tuple[Any, ...] | None:
    """A tier list about the seed: a title, the seed itself in the S tier (deadpan), words related to it in the A, B
    and C tiers, and something everyone loves in the F tier."""
    seed = str(presentation_context["seed"])
    related = related_words(seed)
    if len(related) < 3:
        return None
    things = random_util.sample(related, min(len(related), random_util.randint(3, 7)))
    tiers: list[list[str]] = [[], [], []]
    for index, thing in enumerate(things):  # (A, B and C in turn, A first: three things at most in each)
        tiers[index % 3].append(thing)
    loved = [thing for thing in _rule("karaoke.tier_list_worst") if thing.lower() != seed.lower()]
    title = _template("karaoke.tier_list_title")(_context(presentation_context))
    if not title:
        return None
    best = _capitalised(language_util.generic(seed))
    return title, best, *(" | ".join(tier[:3]) or None for tier in tiers), random_util.choice(loved)


def _capitalised(text: str) -> str:
    return text[:1].upper() + text[1:]
