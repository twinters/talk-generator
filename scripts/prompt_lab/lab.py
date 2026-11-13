"""The prompt lab's shared code (docs/v5-plan.md, D80): talks written by a language model through talkgenerator's own
code (its prompts, its outline and batches, its realizing of the answers), with a stand-in picture for every image
slot instead of a search, so a talk costs only its model's requests and comes in in a minute; its slides as text, for a
judge; and what a talk's texts measure (words on a slide, title lengths, recurring names...).

A variant is the code as it is when its talks are made: make talks with a tag ("base"), change a prompt, make them
again with another tag, and judge the two (judge.py). Outputs go to scripts/prompt_lab/work/<tag>/, which git ignores.
"""

from __future__ import annotations

import ast
import json
import os
import re
import statistics
import struct
import threading
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

LAB = Path(__file__).resolve().parent
WORK = LAB / "work"
STAND_INS = WORK / "stand-ins"

# The talks a variant is made of: one setup each (a topic, a format, a persona, a seed and a language), so that two
# variants' talks of a setup have the same kinds of slides in the same order, and differ only by what the model wrote
SETUPS: list[dict[str, Any]] = [
    {"id": "penguins-founder", "topic": "penguins", "schema": "default", "persona": "startup_founder", "seed": 1},
    {"id": "coffee-conspiracy", "topic": "coffee", "schema": "default", "persona": "conspiracy_blogger", "seed": 2},
    {
        "id": "sourdough-teacher",
        "topic": "sourdough bread",
        "schema": "default",
        "persona": "kindergarten_teacher",
        "seed": 3,
    },
    {
        "id": "volcanoes-historian",
        "topic": "volcanoes",
        "schema": "default",
        "persona": "medieval_historian",
        "seed": 4,
    },
    {"id": "printer-court", "topic": "the office printer", "schema": "court", "persona": "detective", "seed": 5},
    {"id": "ducks-wedding", "topic": "rubber ducks", "schema": "wedding", "persona": "best_man", "seed": 6},
    {"id": "socks-coach", "topic": "socks", "schema": "default", "persona": "life_coach", "seed": 7},
    {"id": "timetravel-pitch", "topic": "time travel", "schema": "pitch", "persona": "startup_founder", "seed": 8},
    {
        "id": "houseplants-documentary",
        "topic": "houseplants",
        "schema": "documentary",
        "persona": "nature_narrator",
        "seed": 9,
    },
    {
        "id": "procrastination-speaker",
        "topic": "procrastination",
        "schema": "default",
        "persona": "motivational_speaker",
        "seed": 10,
    },
    {"id": "cats-influencer", "topic": "cats", "schema": "default", "persona": "influencer", "seed": 11},
    {"id": "bureaucracy-it", "topic": "bureaucracy", "schema": "default", "persona": "it_support", "seed": 12},
    {
        "id": "frietjes-retiree-nl",
        "topic": "frietjes",
        "schema": "default",
        "persona": "retiree",
        "seed": 13,
        "language": "nl",
    },
]
# Talks in Dutch (2026-11-13: the user found the site's free models writing English in a Dutch talk now and then), of
# every format, by personas that fit them
NL_SETUPS: list[dict[str, Any]] = [
    {"id": "nl-regen-influencer", "topic": "regen", "schema": "default", "persona": "influencer", "seed": 21},
    {"id": "nl-fietsen-pitch", "topic": "fietsen", "schema": "pitch", "persona": "startup_founder", "seed": 22},
    {"id": "nl-kaas-documentary", "topic": "kaas", "schema": "documentary", "persona": "nature_narrator", "seed": 23},
    {"id": "nl-kabouters-museum", "topic": "tuinkabouters", "schema": "museum", "persona": "museum_guide", "seed": 24},
    {
        "id": "nl-stofzuiger-infomercial",
        "topic": "de stofzuiger",
        "schema": "infomercial",
        "persona": "infomercial_host",
        "seed": 25,
    },
    {"id": "nl-verjaardagen-wedding", "topic": "verjaardagen", "schema": "wedding", "persona": "best_man", "seed": 26},
    {"id": "nl-huiswerk-court", "topic": "huiswerk", "schema": "court", "persona": "detective", "seed": 27},
    {"id": "nl-trein-keynote", "topic": "de trein", "schema": "keynote", "persona": "passionate_expert", "seed": 28},
    {
        "id": "nl-drop-book-report",
        "topic": "drop",
        "schema": "book_report",
        "persona": "kindergarten_teacher",
        "seed": 29,
    },
    {
        "id": "nl-vergaderen-corporate",
        "topic": "vergaderen",
        "schema": "corporate",
        "persona": "consultant",
        "seed": 30,
    },
]
for _setup in NL_SETUPS:
    _setup["language"] = "nl"
SETS = {"main": SETUPS, "nl": NL_SETUPS}
ALL_SETUPS = [*SETUPS, *NL_SETUPS]
MODELS = {
    "opus": "anthropic:claude-opus-5-5",
    "sonnet": "anthropic:claude-sonnet-5-5",
    "haiku": "anthropic:claude-haiku-5-5",
    "free": "openrouter",  # (OpenRouter's free router, which picks a free model a request: the site's Basic AI)
}

_count = 0
_lock = threading.Lock()


def _png(path: Path, colour: tuple[int, int, int]) -> None:
    """A small PNG of one colour (a stand-in picture), written without an imaging library."""
    width, height = 64, 48
    raw = b"".join(b"\x00" + bytes(colour) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


def stand_in(query: str | None) -> Any:
    """A stand-in picture for an image slot, found with the query: a PNG of its own (so no two are the same)."""
    from talkgenerator.datastructures.image_data import ImageData

    global _count
    with _lock:
        _count += 1
        number = _count
    STAND_INS.mkdir(parents=True, exist_ok=True)
    path = STAND_INS / f"{os.getpid()}-{number}.png"
    _png(path, ((number * 53) % 256, (number * 97) % 256, (number * 31) % 256))
    image = ImageData(str(path), source="prompt lab")
    return image.found_with(query or "") if hasattr(image, "found_with") else image


def without_searches() -> None:
    """Make every image search find a stand-in at once: a planned slide's (talkgenerator.plan.realize._find), and any
    other (the finder's: a title picture, a classic slide's)."""
    from talkgenerator.images import finder
    from talkgenerator.plan import realize

    realize._find = lambda source, query, context, others: stand_in(query)  # type: ignore[assignment]
    finder.find = lambda slot, query, avoid=(): stand_in(query)  # type: ignore[assignment]


# The texts realize cut to their fields' lengths in this process's talk: the text as written, its length, the cut, and
# where it was cut ("clause": where a sentence or a clause ends; "comma"; "words": between words, mid-sentence)
CUTS: list[dict[str, Any]] = []


def _where_cut(text: str, cut: str) -> str:
    rest = text[len(cut) :].lstrip(" \"'”’)")
    if cut.rstrip().endswith((".", "!", "?")) or rest[:1] in tuple(".!?;:—–-"):
        return "clause"
    return "comma" if rest[:1] == "," else "words"


def record_cuts() -> None:
    """Record every cut that realize makes (see CUTS)."""
    from talkgenerator.plan import realize

    def recording(cut: Any) -> Any:
        def recorded(text: str, length: int, language: str) -> str:
            made = cut(text, length, language)
            if made != text:
                CUTS.append({"text": text, "length": length, "cut": made, "where": _where_cut(text, made)})
            return made

        return recorded

    realize._cut = recording(realize._cut)  # type: ignore[assignment]
    realize._cut_list = recording(realize._cut_list)  # type: ignore[assignment]


# The models that answered this process's talk's requests (OpenRouter's free router picks one a request)
ANSWERED_BY: list[str] = []


def record_models() -> None:
    from talkgenerator.llm import openrouter

    streamed = openrouter.OpenRouterProvider._stream

    def recorded(self: Any, *arguments: Any) -> Any:
        response = streamed(self, *arguments)
        ANSWERED_BY.append(response.model)
        return response

    openrouter.OpenRouterProvider._stream = recorded  # type: ignore[method-assign]


def make_talk(setup: dict[str, Any], model: str, level: str, folder: Path) -> dict[str, Any]:
    """Make the setup's talk with the model at the level, without searches; save its deck and the cuts its texts got;
    return what it cost, and who wrote it."""
    os.environ.setdefault("DISABLE_FACTS", "1")  # (real facts change with the day: a lab compares prompts)
    without_searches()
    record_cuts()
    record_models()
    from talkgenerator import generator

    _, slide_deck, _ = generator._generate_presentation(
        schema=setup["schema"],
        slides=setup.get("slides", 10),
        topic=setup["topic"],
        int_seed=setup["seed"],
        llm=model,
        llm_level=level,
        theme="random",
        persona=setup["persona"],
        language=setup.get("language", "en"),
        output_folder=str(folder / "_out"),
        save_ppt=False,
        open_ppt=False,
        image_generator="none",
    )
    deck = slide_deck.to_deck(schema_name=setup["schema"])
    (folder / f"{setup['id']}.deck.json").write_text(deck.to_json(), encoding="utf-8")
    (folder / f"{setup['id']}.cuts.json").write_text(json.dumps(CUTS, indent=1, ensure_ascii=False), encoding="utf-8")
    usage = deck.usage
    return {
        "id": setup["id"],
        "cost": getattr(usage, "cost_usd", None),
        "level": deck.llm_level,
        "model": deck.language_model,
        "answered_by": ANSWERED_BY,
        "cuts": len(CUTS),
    }


# READING A DECK


_SKIPPED_ROLES = {"decoration", "credits"}


def slide_texts(slide: dict[str, Any]) -> list[str]:
    """A slide's texts as shown, in order (without decoration)."""
    return [
        element["text"]
        for element in slide.get("elements", [])
        if element.get("kind") == "text" and element.get("role") not in _SKIPPED_ROLES and element.get("text")
    ]


def _queries(slide: dict[str, Any]) -> list[str]:
    match = re.search(r"Image queries: (\{.*\})", slide.get("notes") or "")
    if not match:
        return []
    try:
        found = ast.literal_eval(match.group(1))  # (the notes write a dict as Python does)
    except (ValueError, SyntaxError):
        return []
    return [str(value) for value in found.values() if value]


def as_text(deck: dict[str, Any]) -> str:
    """The deck as a judge reads it: every slide's kind and texts, its pictures as their search queries in brackets."""
    lines = []
    for number, slide in enumerate(deck.get("slides", []), 1):
        texts = " | ".join(text.replace("\n", " / ") for text in slide_texts(slide))
        pictures = "".join(f" [picture: {query}]" for query in _queries(slide))
        kind = slide.get("type", "?")
        lines.append(f"{number}. ({kind}) {texts}{pictures}")
    return "\n".join(lines)


def load(tag: str, setup_id: str) -> dict[str, Any] | None:
    path = WORK / tag / f"{setup_id}.deck.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# MEASURING A DECK

_FIRST_NAMES: set[str] | None = None


def first_names() -> set[str]:
    global _FIRST_NAMES
    if _FIRST_NAMES is None:
        from talkgenerator.util import os_util

        names = json.loads(Path(os_util.to_actual_file("data/text-templates/name.json")).read_text(encoding="utf-8"))
        _FIRST_NAMES = {name.lower() for key in ("male_name", "female_name") for name in names.get(key, [])}
    return _FIRST_NAMES


def _common(word: str) -> bool:
    """Whether a name is a common English word too ("Will", "Grace"), which a slide says as a word."""
    from wordfreq import zipf_frequency

    return zipf_frequency(word.lower(), "en") > 4.3


def metrics(deck: dict[str, Any]) -> dict[str, Any]:
    """What a deck's texts measure: words on its slides (mean, most, slides over 25), its talk title's length, slide
    titles over 45 characters, the most slides one capitalised name is on (a recurring character), and whether its
    presenter's first name is a known first name."""
    slides = deck.get("slides", [])[1:]  # (not the title slide)
    words = [
        sum(len(text.split()) for text in slide_texts(slide)) for slide in slides if slide.get("type") != "wall_of_text"
    ]
    titles = [
        element["text"]
        for slide in slides
        for element in slide.get("elements", [])
        if element.get("kind") == "text" and element.get("role") == "title"
    ]
    names: Counter[str] = Counter()
    for slide in slides:
        found = set(re.findall(r"\b([A-Z][a-z]{2,})\b", " ".join(slide_texts(slide))))
        names.update(name for name in found if name.lower() in first_names() and not _common(name))
    presenter = (deck.get("presenter") or "").replace("Dr.", "").replace("Prof.", "").split()
    english = english_words(deck)
    return {
        "words_mean": round(statistics.mean(words), 1) if words else 0,
        "words_max": max(words, default=0),
        "over_25": sum(count > 25 for count in words),
        "title_chars": len(deck.get("title") or ""),
        "long_titles": sum(len(title) > 45 for title in titles),
        "recurring": max(names.values(), default=0),
        "real_first_name": bool(presenter) and presenter[0].lower() in first_names(),
        "english_words": sum(len(found) for found in english.values()),
        "english_slides": sum(len(found) >= 2 for found in english.values()),
        "language_findings": len(language_findings(deck)),
        "classic": deck.get("language_model") is None,
    }


# ENGLISH IN A TALK IN ANOTHER LANGUAGE

_WORDS = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


def english_words(deck: dict[str, Any]) -> dict[int, list[str]]:
    """The English words on each slide of a talk in another language (by the slide's number): common in English
    (wordfreq's Zipf frequency of 3 or more) and a hundred times rarer in the talk's language, which keeps loanwords
    such as "team", "live" or "deadline" out; a capitalised word inside a text is a name, and none."""
    language = deck.get("language") or "en"
    if language == "en":
        return {}
    from wordfreq import zipf_frequency

    found: dict[int, list[str]] = {}
    for number, slide in enumerate(deck.get("slides", []), 1):
        words = [
            word
            for text in slide_texts(slide)
            for index, word in enumerate(_WORDS.findall(text))
            if not (index > 0 and word[:1].isupper()) and len(word) > 2
        ]
        english = [
            word
            for word in words
            if (zipf := zipf_frequency(word.lower(), "en")) >= 3 and zipf - zipf_frequency(word.lower(), language) >= 2
        ]
        if english:
            found[number] = english
    return found


def language_findings(deck: dict[str, Any]) -> list[Any]:
    """talkgenerator's own check of a talk's language (talkgenerator.checks.deck.check_language)."""
    from talkgenerator.checks.deck import check_language
    from talkgenerator.models.deck import Deck

    return check_language(Deck.from_json(json.dumps(deck)))


def cuts(tag: str, setup_id: str) -> list[dict[str, Any]]:
    """The cuts a talk's texts got (see make_talk), or none recorded."""
    path = WORK / tag / f"{setup_id}.cuts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
