"""Automated checks of a deck (docs/v5-plan.md, section 14): a deck in, findings out.

An error is a broken talk: a slide without what it needs, template code on a slide, or an image its license policy
doesn't allow. A warning is worth a look, such as an image without a credit, one that comes back on another slide
(or nearly the same one), or one without the look it was found for (a vintage photo in colour). Checks of contrast
and overflowing text are in talkgenerator.checks.design.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from talkgenerator.models import classic
from talkgenerator.models.deck import (
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


# Bits of generator machinery that should never make it onto a slide
_LEFTOVERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\{[A-Za-z_]\w*(?:\.\w+)*\}"), "an unfilled template variable"),
    (re.compile(r"#[A-Za-z_]\w*(?:\.\w+)*#"), "an unexpanded tracery symbol"),
    (re.compile(r"\(\([A-Za-z_]\w*\)\)"), "a missing tracery symbol"),
    (re.compile(r"<(?:built-in method|bound method|function|lambda)\b"), "Python code"),
    (re.compile(r"\b(?:ImageData|ChartData|XyChartData|DeckSlide)\("), "a Python object"),
)
# A word followed by None, as in "About None": a template variable that was None. (Not "None of us were ready")
_NONE = re.compile(r"\S\s+None\b|^None$")


def leftovers_in(text: str) -> list[str]:
    """The bits of generator machinery in a text: what they are, and the bit itself."""
    return [f"{what}: {found.group(0)!r}" for pattern, what in _LEFTOVERS if (found := pattern.search(text))]


def check_deck(deck: Deck, expected_slides: int | None = None) -> list[Finding]:
    """Every check of a deck (and of a themed deck's design: see talkgenerator.checks.design)."""
    from talkgenerator.checks.design import check_design  # (it needs this module's Finding)

    return [
        *check_completeness(deck, expected_slides),
        *check_leftovers(deck),
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
    own, foreign = expected - english, english - expected  # the words that tell the two apart
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
        "same_type_in_a_row": sum(1 for before, after in itertools.pairwise(types) if before == after),
        "layouts": len({slide.layout for slide in deck.slides}),
        "same_layout_in_a_row": sum(
            1 for before, after in itertools.pairwise(deck.slides) if before.layout == after.layout
        ),
        "images": sum(1 for slide in deck.slides for element in slide.elements if isinstance(element, ImageElement)),
        **_image_matches(deck),
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
    texts = []
    for element in elements:
        if isinstance(element, TextElement):
            texts.append((element.role, element.text))
        elif isinstance(element, ChartElement):
            texts.extend((f"{element.role} label", category) for category in element.chart.categories)
            texts.extend((f"{element.role} label", name) for series in element.chart.series for name in series.labels)
        elif isinstance(element, DiagramElement):
            texts.extend((f"{element.role}'s {name}", label) for name, label in element.diagram.labels())
    return texts
