"""Automated checks of a deck (docs/v5-plan.md, section 14): a deck in, findings out.

An error is a broken talk: a slide without what it needs, template code on a slide (or a slide's key in the language
model's answer), or an image its license policy doesn't allow. A warning is worth a look, such as an image without a
credit, one that comes back on another slide (or nearly the same one), or one without the look it was found for (a
vintage photo in colour). Checks of contrast and overflowing text are in talkgenerator.checks.design.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from typing import Any, Final, Literal

from talkgenerator.models import classic
from talkgenerator.models.deck import (
    DECORATION,
    ChartElement,
    Content,
    Deck,
    DiagramElement,
    ImageElement,
    MatrixDiagram,
    TextElement,
    VennDiagram,
)
from talkgenerator.util import language_util

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    message: str
    slide: int | None = None  # counted from 1, the way presenters count

    def __str__(self) -> str:
        where = f"slide {self.slide}: " if self.slide is not None else ""
        return f"{self.severity}: {where}{self.message} [{self.check}]"


# A slide's key in a language model's answer, slide_2 or slide_02 (see talkgenerator.plan.prompt), by which a free
# model named the slide that a conclusion called back to: "Huddling scales trust (from slide_03)"
_SLIDE_KEY = r"\bslide_\d+\b"
# Bits of generator machinery that should never make it onto a slide
_LEFTOVERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\{[A-Za-z_]\w*(?:\.\w+)*\}"), "an unfilled template variable"),
    (re.compile(r"#[A-Za-z_]\w*(?:\.\w+)*#"), "an unexpanded tracery symbol"),
    (re.compile(r"\(\([A-Za-z_]\w*\)\)"), "a missing tracery symbol"),
    (re.compile(r"<(?:built-in method|bound method|function|lambda)\b"), "Python code"),
    (re.compile(r"\b(?:ImageData|ChartData|XyChartData|DeckSlide)\("), "a Python object"),
    (re.compile(_SLIDE_KEY, re.IGNORECASE), "a slide's key in the language model's answer"),
)
# A word followed by None, as in "About None": a template variable that was None. (Not "None of us were ready")
_NONE = re.compile(r"\S\s+None\b|^None$")
# Brackets that name a slide by its key, as in "(from slide_03)" or "[see slide_3 and slide_5]"
_KEY_REFERENCE = re.compile(rf"\s*[(\[][^()\[\]]*{_SLIDE_KEY}[^()\[\]]*[)\]]", re.IGNORECASE)


def leftovers_in(text: str) -> list[str]:
    """The bits of generator machinery in a text: what they are, and the bit itself."""
    return [f"{what}: {found.group(0)!r}" for pattern, what in _LEFTOVERS if (found := pattern.search(text))]


# REAL-WORLD POLITICS, which a talk shouldn't hold unless it's about it: a free model wrote "Japan needs to earnestly
# reflect on its history of aggression, respect the security concerns of Asian neighbors, act prudently in the field"
# as a lighthouse talk's quote (2026-11-08), words its training had from statements on politics. Phrases that only such
# statements have give a text away...
_POLITICAL_PHRASES: Final = (
    "history of aggression",
    "territorial integrity",
    "hegemonism",
    "war crimes",
    "ethnic cleansing",
    "genocide",
    "apartheid",
    "communist party",
    "separatist forces",
    "independence forces",
    "cold war mentality",
    "people's republic",
)
# ...and so do these words, with a real country, people or political body: but not words that absurd humour has too
# ("The French president collects lighthouses", "the Great Seagull War", "a strict Japanese skincare regime", "the
# internal affairs of the lighthouse", "There are more penguins in Belgium than people")
_POLITICAL_WORDS: Final = (
    "aggression",
    "sovereignty",
    "hegemony",
    "imperialism",
    "colonialism",
    "militarism",
    "annexation",
    "dictatorship",
    "separatism",
    "separatist",
    "separatists",
    "reunification",
    "atrocities",
    "massacre",
    "massacres",
)
# The peoples, regions and political bodies that statements on politics name, besides the countries (whose names are
# in data/countries.txt, apart from the content packs' words)
_PEOPLES: Final = (
    ("American", "Americans", "Asian", "Asians", "African", "Arab", "Arabs", "British", "Chinese", "European")
    + ("French", "German", "Indian", "Iranian", "Iraqi", "Israeli", "Israelis", "Japanese", "Korean", "Koreans")
    + ("Kurdish", "Palestinian", "Palestinians", "Pakistani", "Russian", "Russians", "Soviet", "Syrian", "Taiwanese")
    + ("Tibetan", "Turkish", "Ukrainian", "Ukrainians", "Uyghur", "Uyghurs", "Western", "the West", "NATO", "EU")
    + ("United Nations", "UN", "CCP", "CPC", "Kremlin", "Beijing", "Moscow", "Washington", "Tokyo", "Taipei")
    + ("Pyongyang", "Tehran", "Kyiv", "Kiev", "Jerusalem", "Gaza", "West Bank", "Taiwan", "Tibet", "Xinjiang")
    + ("Hong Kong", "Crimea", "Donbas", "Kashmir", "Russia", "America", "USA", "UK", "Britain", "Korea")
)
# Countries' names that are people's names or things too ("Chad's dictatorship over the office fridge")
_NOT_ONLY_COUNTRIES: Final = frozenset({"Chad", "Jordan", "Georgia", "Turkey", "Guinea"})


@cache
def _political() -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    """Patterns of the political phrases, the political words, and the peoples and countries (in capitals)."""
    from talkgenerator.util import os_util  # (here: the checks don't need it otherwise)

    with open(os_util.to_actual_file("data/countries.txt"), encoding="utf-8") as file:
        countries = {line.strip() for line in file if line.strip() and not line.startswith("#")}
    names = (countries - _NOT_ONLY_COUNTRIES) | set(_PEOPLES)

    def words(terms: Iterable[str], flags: int = 0) -> re.Pattern[str]:
        alternatives = "|".join(re.escape(term) for term in sorted(set(terms), key=len, reverse=True))
        return re.compile(rf"(?<![\w-])(?:{alternatives})(?![\w-])", flags)

    return words(_POLITICAL_PHRASES, re.IGNORECASE), words(_POLITICAL_WORDS, re.IGNORECASE), words(names)


def real_politics(text: str, topic: str = "") -> str | None:
    """What makes a text about real-world politics (see _POLITICAL_PHRASES): one of the phrases that only statements on
    politics have, or a country, people or political body with one of politics' words, unless the talk's topic is
    about that too (it has the phrase's words, or names a country the text names). None for a text that isn't, as
    absurd humour isn't. (English only.)"""
    phrases, political, peoples = _political()
    text = text.replace("’", "'")
    about = topic.lower()
    topic_words = [word for word in re.findall(r"[a-z]+", about) if len(word) > 3]

    def in_topic(found: str) -> bool:
        words = [word for word in re.findall(r"[a-z]+", found.lower()) if len(word) > 3]
        return bool(words) and all(word in about for word in words)

    def people_in_topic(found: str) -> bool:  # (a talk on "Japanese gardens" may speak of Japan)
        name = found.lower()
        return name in about or any(word in name for word in topic_words)

    if any(people_in_topic(found.group(0)) for found in peoples.finditer(text)):
        return None  # (a talk on a country, or its history, may speak of its politics)
    phrase = next((found.group(0) for found in phrases.finditer(text) if not in_topic(found.group(0))), None)
    if phrase is not None:
        return phrase
    word = next((found.group(0) for found in political.finditer(text) if not in_topic(found.group(0))), None)
    people = next((found.group(0) for found in peoples.finditer(text) if not people_in_topic(found.group(0))), None)
    return f"{people} ... {word}" if word is not None and people is not None else None


def without_key_references(text: str) -> str:
    """The text without the brackets in it that name a slide by its key in the language model's answer: "Huddling
    scales trust (from slide_03)" becomes "Huddling scales trust". (A key elsewhere in a text is a leftover, as in "As
    slide_03 showed": see leftovers_in.)"""
    return _KEY_REFERENCE.sub("", text)


def check_deck(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """Every check of a deck (and of a themed deck's design: see talkgenerator.checks.design)."""
    from talkgenerator.checks.design import check_design  # (it needs this module's Finding)

    return [
        *check_completeness(deck, expected_slides),
        *check_leftovers(deck),
        *check_arc(deck, expected_slides),
        *check_quizzes(deck),
        *check_politics(deck),
        *check_images(deck),
        *check_licenses(deck),
        *check_looks(deck),
        *check_language(deck),
        *check_design(deck),
    ]


_WORD = re.compile(r"[^\W\d_]+")


def check_language(deck: Deck) -> list[Finding]:
    """Whether a talk in another language than English is in that language: by the stopwords its texts hold (NLTK's
    lists of a language's little words, such as "de" and "het", or "the" and "of"). An error when the talk reads as
    English, and a warning for a slide that does. (The classic generator writes English, so English talks pass.)"""
    if deck.language == "en":
        return []
    from talkgenerator.plan import languages  # (here: the checks don't need them otherwise)
    from talkgenerator.util import language_util

    language = languages.language(deck.language)
    expected = language_util.stopwords(language.stopwords)
    english = language_util.stopwords("english")
    # The words that tell the two apart (but the language's words that look like English ones: Swedish "is", ice)
    own, foreign = expected - english, english - expected - language.english_lookalikes
    findings = []
    own_in_talk = english_in_talk = 0
    for number, slide in enumerate(deck.slides, 1):
        words = [word for _, text in _texts(slide.elements) for word in _WORD.findall(text.lower())]
        own_in_slide = sum(word in own for word in words)
        english_in_slide = sum(word in foreign for word in words)
        own_in_talk += own_in_slide
        english_in_talk += english_in_slide
        if english_in_slide >= 2 and own_in_slide == 0:
            findings.append(Finding("language", "warning", f"reads as English, not {language.name}", number))
    if english_in_talk >= 4 and english_in_talk > 2 * own_in_talk:
        findings.insert(0, Finding("language", "error", f"the talk reads as English, not {language.name}"))
    return findings


def check_completeness(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """Every slide is there, and has what its type needs."""
    findings = []
    if expected_slides is not None and len(deck.slides) != expected_slides:
        findings.append(Finding("completeness", "error", f"{len(deck.slides)} of the {expected_slides} slides"))
    if deck.slides and deck.slides[0].type != "title":
        findings.append(
            Finding(
                "completeness",
                "warning",
                f"the first slide isn't the title but a slide of type {deck.slides[0].type}",
                1,
            )
        )
    for number, slide in enumerate(deck.slides, 1):
        required = classic.REQUIRED_ROLES.get(slide.type)
        if required is None:
            findings.append(Finding("completeness", "error", f"an unknown type of slide: {slide.type!r}", number))
            continue
        for role in required:
            if slide.element(role) is None:
                findings.append(Finding("completeness", "error", f"no {role} on this {slide.type} slide", number))
        for element in slide.elements:
            if isinstance(element, TextElement) and not element.text.strip():
                findings.append(Finding("completeness", "error", f"an empty {element.role}", number))
            elif isinstance(element, ImageElement) and not element.image.url.strip():
                findings.append(
                    Finding("completeness", "error", f"an image without an address as {element.role}", number)
                )
            elif isinstance(element, ChartElement) and not any(
                series.values or series.points for series in element.chart.series
            ):
                findings.append(Finding("completeness", "error", "a chart without data", number))
            elif isinstance(element, DiagramElement):
                findings += [Finding("completeness", "error", gap, number) for gap in diagram_gaps(element.diagram)]
    return findings


def diagram_gaps(diagram: VennDiagram | MatrixDiagram) -> list[str]:
    """What a diagram misses: a Venn diagram needs two or three circles, and every diagram all its labels."""
    what = "Venn diagram" if isinstance(diagram, VennDiagram) else "2×2 matrix"
    gaps = []
    if isinstance(diagram, VennDiagram) and len(diagram.circles) not in (2, 3):
        count = len(diagram.circles)
        gaps.append(f"a Venn diagram of {count} circle{'' if count == 1 else 's'} (it takes two or three)")
    gaps += [f"a {what} with an empty {name}" for name, label in diagram.labels() if not label.strip()]
    return gaps


def check_leftovers(deck: Deck) -> list[Finding]:
    """No template variables, tracery symbols or Python objects in the texts (chart and diagram labels included)."""
    findings = []
    for number, slide in enumerate(deck.slides, 1):
        for role, text in _texts(slide.elements):
            for pattern, what in _LEFTOVERS:
                found = pattern.search(text)
                if found:
                    findings.append(Finding("leftovers", "error", f"{what} in its {role}: {found.group(0)!r}", number))
            if _NONE.search(text):
                findings.append(Finding("leftovers", "warning", f"'None' in its {role}: {text!r}", number))
    return findings


# What made a slide, as its notes say: a classic slide's generator, or the slide generator a planned slide stood for
_MADE_BY: Final = re.compile(
    r"^(?:Generator: (?P<classic>.+?)|Planned: an? \S+ slide for (?P<planned>.+?), about .*)\s*$", re.MULTILINE
)


def check_arc(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """A talk of a format with an arc (a pitch, an academic talk: see talkgenerator.schema.formats) goes through the
    parts that a talk of its length keeps, in their order, as its slides' notes say who made them: a warning for a
    part it misses (when none of the part's slide generators could make its slide, one of the format's other slides
    stands in), and for a part that comes before one it should follow."""
    from talkgenerator.plan.external import recipe_id  # (here: the checks don't need them otherwise)
    from talkgenerator.schema.presentation_schema_types import schemas

    if deck.schema_name is None or deck.schema_name not in schemas:
        return []
    schema = schemas.get(deck.schema_name)
    arc = schema.format.arc if schema.format is not None else None
    if arc is None:
        return []
    # (by a slide generator's name, which a talk's notes give, and by its recipe's id, which a rendered plan's give)
    part_of: dict[str, str | None] = {}
    for generator in schema.slide_generators:
        part = next((tag for tag in generator.get_tags() if tag in arc.names()), None)
        part_of[generator.name or ""] = part_of[recipe_id(generator.name or "")] = part
    seen: list[tuple[int, str]] = []
    for number, slide in enumerate(deck.slides, 1):
        made_by = _MADE_BY.search(slide.notes)
        name = (made_by.group("classic") or made_by.group("planned")) if made_by else None
        part = part_of.get(name.strip()) if name else None
        if part is not None:
            seen.append((number, part))
    findings = []
    order = arc.names()
    for (_, before), (number, after) in itertools.pairwise(seen):
        if order.index(after) < order.index(before):
            findings.append(
                Finding(
                    "arc",
                    "warning",
                    f"its {after.replace('_', ' ')} slide comes after its {before.replace('_', ' ')} slide",
                    number,
                )
            )
    parts = {part for _, part in seen}
    for part in arc.kept(expected_slides or len(deck.slides)):
        if part not in parts:
            findings.append(Finding("arc", "warning", f"it has no slide of its {part.replace('_', ' ')} part"))
    return findings


def check_quizzes(deck: Deck) -> list[Finding]:
    """A quiz's explanation agrees with its answer: a warning when it names other options and not the answer (as a
    free model's did). Talks repair the clear cases, where it names one other option (see plan.kinds), so this finds
    the ones that can't be told."""
    from talkgenerator.plan import languages  # (here: the checks don't need them otherwise)

    findings = []
    for number, slide in enumerate(deck.slides, 1):
        explanation, answer = slide.element("explanation"), slide.element("answer")
        if slide.type != "quiz" or not isinstance(explanation, TextElement) or not isinstance(answer, TextElement):
            continue
        options = [_text_of(slide.element(f"option_{index}")) for index in range(1, 5)]
        named = language_util.named_options(explanation.text, options, languages.language(deck.language).stopwords)
        marked = "ABCD".find(answer.text)
        if named and marked not in named:
            others = " and ".join("ABCD"[index] for index in named)
            findings.append(
                Finding(
                    "quiz", "warning", f"its explanation names option {others}, not its answer {answer.text}", number
                )
            )
    return findings


def _text_of(element: Content | None) -> str | None:
    return element.text if isinstance(element, TextElement) else None


def check_politics(deck: Deck) -> list[Finding]:
    """No text is about real-world politics that the talk isn't about, such as the statement on a country's history
    of aggression that a free model wrote as a lighthouse talk's quote (see real_politics): a warning, as talks that
    a language model writes leave such texts out already (see plan.realize)."""
    if deck.language != "en":
        return []
    findings = []
    for number, slide in enumerate(deck.slides, 1):
        for role, text in _texts(slide.elements):
            found = real_politics(text, " ".join(deck.topics))
            if found:
                findings.append(Finding("politics", "warning", f"real-world politics in its {role}: {found!r}", number))
    return findings


def check_images(deck: Deck) -> list[Finding]:
    """Images from the web are credited, and no image comes back on another slide, nor nearly the same one (by the
    perceptual hashes of the images the image finder looked at: see talkgenerator.images.analysis)."""
    from talkgenerator.images import analysis  # (here: the checks don't need it otherwise)

    findings = []
    first_slide_of: dict[str, int] = {}
    hashes: list[tuple[str, int]] = []
    for number, slide in enumerate(deck.slides, 1):
        for element in slide.elements:
            if not isinstance(element, ImageElement):
                continue
            url = element.image.url
            if url.startswith("http") and not element.image.credit:
                findings.append(Finding("images", "warning", f"an image without a credit: {url}", number))
            if url in first_slide_of and first_slide_of[url] != number:
                findings.append(Finding("images", "warning", f"the same image as slide {first_slide_of[url]}", number))
            elif element.image.analysis is not None and element.image.analysis.hash:
                own = element.image.analysis.hash
                near = next(
                    (
                        slide_number
                        for other, slide_number in hashes
                        if slide_number != number and analysis.distance(own, other) <= analysis.NEAR_DUPLICATE
                    ),
                    None,
                )
                if near is not None:
                    findings.append(Finding("images", "warning", f"nearly the same image as slide {near}", number))
                hashes.append((own, number))
            first_slide_of.setdefault(url, number)
    return findings


def check_licenses(deck: Deck) -> list[Finding]:
    """The images have license classes the talk's license policy allows (an error otherwise), and an image whose
    license a credit names (an open or public domain one) has its credit name it (see talkgenerator.images.licenses).
    Under a policy narrower than "all", a web image without a class is worth a look too: its class can't be told."""
    from talkgenerator.images import licenses  # (here: the checks don't need it otherwise)

    try:
        policy = licenses.policy(deck.license_policy)
    except ValueError as error:
        return [Finding("licenses", "error", str(error))]
    findings = []
    for number, slide in enumerate(deck.slides, 1):
        for element in slide.elements:
            if not isinstance(element, ImageElement):
                continue
            image = element.image
            if image.license_class is None:
                if image.url.startswith("http") and policy.classes != licenses.ALL.classes:
                    findings.append(
                        Finding(
                            "licenses",
                            "warning",
                            f"an image without a license class, which the license policy ({policy.name}) can't be "
                            f"checked for: {image.url}",
                            number,
                        )
                    )
                continue
            if not policy.allows(image.license_class):
                findings.append(
                    Finding(
                        "licenses",
                        "error",
                        f"a {image.license_class} image, which the license policy ({policy.name}) doesn't allow: "
                        f"{image.source or image.url}",
                        number,
                    )
                )
            if image.license_class in licenses.SHOWN:
                credit = "".join(part.text for part in image.credit)
                if not image.license:
                    findings.append(
                        Finding("licenses", "warning", f"a {image.license_class} image without its license", number)
                    )
                elif image.license.lower() not in credit.lower():
                    findings.append(
                        Finding("licenses", "warning", f"its credit doesn't name its license ({image.license})", number)
                    )
    return findings


# How far a picture may be from what its look prefers before it's worth a look: half again as much detail where the
# text goes, and a tenth outside the brightness asked for
_DETAIL_TOLERANCE = 1.5
_BRIGHTNESS_TOLERANCE = 0.1


def check_looks(deck: Deck) -> list[Finding]:
    """Every image the image finder looked at has what its look prefers (see talkgenerator.images.profiles), or the
    treatment its look gives a picture that doesn't: a vintage picture is in black and white or sepia, or turned so,
    and a calm backdrop has little detail where the text goes."""
    from talkgenerator.images import profiles  # (here: the checks don't need them otherwise)

    findings = []
    for number, slide in enumerate(deck.slides, 1):
        for element in slide.elements:
            if not isinstance(element, ImageElement) or element.image.look is None:
                continue
            look = profiles.PROFILES.get(element.image.look)
            seen = element.image.analysis
            if look is None:
                findings.append(
                    Finding("looks", "warning", f"an image of a look there isn't: {element.image.look}", number)
                )
                continue
            prefers = look.prefers
            if prefers is None or seen is None:
                continue
            treated = element.treatment is not None and element.treatment.filter in _MONOCHROME_FILTERS
            if prefers.monochrome and not seen.monochrome and not treated:
                findings.append(
                    Finding(
                        "looks",
                        "warning",
                        f"a {look.name} picture in colour ({seen.grayscale:.0%} of it gray), and not turned to "
                        "black and white or sepia",
                        number,
                    )
                )
            if (
                prefers.detail is not None
                and seen.detail is not None
                and seen.detail > _DETAIL_TOLERANCE * prefers.detail
            ):
                findings.append(
                    Finding(
                        "looks",
                        "warning",
                        f"a {look.name} picture with much detail where the text goes ({seen.detail:.2f})",
                        number,
                    )
                )
            if prefers.brightness and not (
                prefers.brightness[0] - _BRIGHTNESS_TOLERANCE
                <= seen.brightness
                <= prefers.brightness[1] + _BRIGHTNESS_TOLERANCE
            ):
                findings.append(
                    Finding(
                        "looks", "warning", f"a {look.name} picture too light or dark ({seen.brightness:.2f})", number
                    )
                )
    return findings


_MONOCHROME_FILTERS = frozenset({"grayscale", "sepia", "black and white", "duotone"})


def deck_metrics(deck: Deck) -> dict[str, Any]:
    """Numbers to follow from one milestone to the next, which aren't right or wrong on their own."""
    types = [slide.type for slide in deck.slides]
    return {
        "slides": len(deck.slides),
        # The slides a language model wrote (their notes say what it planned); the classic generator made the others
        "written_by_language_model": sum(
            1 for slide in deck.slides if any(line.startswith("Planned:") for line in slide.notes.splitlines())
        ),
        "slide_types": dict(sorted(Counter(types).items())),
        # Who presented it, whose kinds of slides come up more often (see talkgenerator.personas)
        "persona": deck.persona.name if deck.persona is not None else None,
        "same_type_in_a_row": sum(1 for before, after in itertools.pairwise(types) if before == after),
        "layouts": len({slide.layout for slide in deck.slides}),
        "same_layout_in_a_row": sum(
            1 for before, after in itertools.pairwise(deck.slides) if before.layout == after.layout
        ),
        "images": sum(1 for slide in deck.slides for element in slide.elements if isinstance(element, ImageElement)),
        **_image_matches(deck),
        # What a vision pick made of the pictures it looked at (see talkgenerator.images.vision), and which model
        "vision_pick": _vision_pick(deck),
        "vision_model": deck.vision_model,
        "license_classes": _license_classes(deck),
        "looks": _looks(deck),
        "repeated_titles": _repeated_titles(deck),
        "usage": deck.usage.model_dump(),
    }


def _image_matches(deck: Deck) -> dict[str, int]:
    """How many images were searched for with a query and came with a description (the sources' alt texts, post
    titles and such), and how many of those share a word with their query: a rough sign of whether the images
    show what the slides asked for."""
    described = matching = 0
    for slide in deck.slides:
        for element in slide.elements:
            if isinstance(element, ImageElement) and element.image.query and element.image.description:
                described += 1
                matching += bool(_content_words(element.image.query) & _content_words(element.image.description))
    return {"images_with_query_and_description": described, "images_matching_their_query": matching}


def _vision_pick(deck: Deck) -> dict[str, int]:
    """How many of the deck's pictures a vision model picked over the finder's, kept (the finder's own) and refused
    (none of their candidates would do)."""
    counts = {"picked": 0, "kept": 0, "refused": 0}
    for slide in deck.slides:
        for image in slide.images():
            if image.vision is not None:
                counts[image.vision] += 1
    return counts


def _license_classes(deck: Deck) -> dict[str, int]:
    """How many of the deck's images have each license class ("none": files of talkgenerator's own, or a plan's)."""
    counts = Counter(
        element.image.license_class or "none"
        for slide in deck.slides
        for element in slide.elements
        if isinstance(element, ImageElement)
    )
    return dict(sorted(counts.items()))


def _looks(deck: Deck) -> dict[str, dict[str, int]]:
    """Per look the images were found for: how many, how many of them were looked at, and how many of those have
    what the look prefers (or get its treatment): for the profile checks across talks, such as the share of vintage
    pictures in black and white or sepia."""
    from talkgenerator.images import profiles  # (here: the checks don't need them otherwise)

    looks: dict[str, dict[str, int]] = {}
    for slide in deck.slides:
        for element in slide.elements:
            if not isinstance(element, ImageElement) or element.image.look is None:
                continue
            counts = looks.setdefault(element.image.look, {"images": 0, "looked_at": 0, "with_the_look": 0})
            counts["images"] += 1
            seen = element.image.analysis
            if seen is None:
                continue
            counts["looked_at"] += 1
            look = profiles.PROFILES.get(element.image.look)
            prefers = look.prefers if look is not None else None
            treated = element.treatment is not None and element.treatment.filter in _MONOCHROME_FILTERS
            if prefers is None or prefers.met_by(seen) or (prefers.monochrome and treated):
                counts["with_the_look"] += 1
    return dict(sorted(looks.items()))


def _content_words(text: str) -> set[str]:
    """The words of an (English) text that say something, roughly singular: "Cats on a roof" gives cat and roof."""
    try:
        little = language_util.stopwords("english")
    except (LookupError, OSError):
        little = frozenset()
    words = re.findall(r"[a-z]+", text.lower())
    return {word.removesuffix("s") for word in words if len(word) > 2 and word not in little}


def _repeated_titles(deck: Deck) -> int:
    """How many slides have the title of a slide before them (such as two gif slides both saying "Look at this")."""
    titles = [
        element.text.lower()
        for slide in deck.slides
        for element in slide.elements
        if isinstance(element, TextElement) and element.role == "title"
    ]
    return len(titles) - len(set(titles))


def _texts(elements: tuple[Content, ...]) -> list[tuple[str, str]]:
    """The talk's texts on a slide, with their roles (charts' and diagrams' labels too; not its theme's decoration's,
    such as a slide's number or a terminal's prompt, which aren't the talk's words)."""
    texts = []
    for element in elements:
        if isinstance(element, TextElement):
            if element.role != DECORATION:
                texts.append((element.role, element.text))
        elif isinstance(element, ChartElement):
            texts.extend((f"{element.role} label", category) for category in element.chart.categories)
            texts.extend((f"{element.role} label", name) for series in element.chart.series for name in series.labels)
        elif isinstance(element, DiagramElement):
            texts.extend((f"{element.role}'s {name}", label) for name, label in element.diagram.labels())
    return texts
