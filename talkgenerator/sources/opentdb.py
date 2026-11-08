"""Real quiz questions from Open Trivia DB (https://opentdb.com), a free database of trivia questions that its users
write and its moderators check (5,299 checked ones on 2026-11-08), for classic quiz slides (see talkgenerator.facts,
docs/v5-plan.md D60). Its questions are under CC BY-SA 4.0: a slide that shows one credits it.

No key, but one request every five seconds at most from one address: a category's questions come 50 at a time, the
cache keeps them for a week (the API answers at random: so they're the same all week), and a request waits its turn.
Only the categories a family audience's talk can use (not its celebrities, politics or brands: see CATEGORIES).
"""

from __future__ import annotations

import html
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API: Final = "https://opentdb.com/api.php"
SITE: Final = "https://opentdb.com"
LICENSE: Final = "CC BY-SA 4.0"
LICENSE_URL: Final = "https://creativecommons.org/licenses/by-sa/4.0/"
TIMEOUT: Final = 5.0
SPACING: Final = 5.0  # seconds between requests, at least (its rule: each address once every five seconds)
QUESTIONS: Final = 50  # a request's (the most it gives)

# Its categories that talks use, by id, and the words of a topic's description that lead to each (the first that
# matches, a word ending in "*" for every word it starts; general knowledge for the rest). Left out: celebrities and
# politics (real living people), entertainment, sports, gadgets and board games (stars and brands), and mythology
# (faiths).
GENERAL_KNOWLEDGE: Final = 9
CATEGORIES: Final[dict[int, str]] = {
    27: "animal* bird birds mammal* fish fishes insect* reptil* amphibian* species genus breed* spider* whale* dog dogs "
    "cat cats",
    28: "ship ships liner* vehicle* car cars aircraft* airplane* airliner* train trains locomotive* boat boats bicycle* "
    "truck trucks",
    22: "countr* city cities town towns capital river* lake lakes mountain* island* region* continent* ocean* desert* "
    "village* province*",
    18: "comput* software* program programs programming internet website* algorithm* network*",
    19: "mathemat* geometr* equation* theorem* arithmetic*",
    25: "painting* sculpt* artwork* art arts artist*",
    23: "histor* ancient empire* centur* dynast* era eras",
    17: "plant plants tree trees flower* fung* chemi* element* mineral* rock rocks physic* biolog* weather phenomen* "
    "planet* volcan* geolog* smell* scent* odour* odor* science* scientific",
    GENERAL_KNOWLEDGE: "",
}


def _words(words: str) -> re.Pattern[str] | None:
    alternatives = [re.escape(word[:-1]) + r"\w*" if word.endswith("*") else re.escape(word) for word in words.split()]
    return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b") if alternatives else None


_CATEGORY_WORDS: Final = {category: _words(words) for category, words in CATEGORIES.items()}

_cooldown = http_util.Cooldown("Open Trivia DB")
_turns = threading.Lock()  # (one request at a time, five seconds apart)
_last_asked = float("-inf")


@dataclass(frozen=True)
class Question:
    """A multiple-choice question: what it asks, its right answer, its three wrong ones, and how hard it is."""

    question: str
    answer: str
    wrong: tuple[str, ...]
    category: str = ""
    difficulty: str = ""


def available() -> bool:
    return not settings.is_source_disabled("OPENTDB")


def category_for(description: str) -> int:
    """The category of a topic's questions, by the words of what it is ("Family of aquatic flightless birds"):
    general knowledge when none of the others fits."""
    words = description.lower()
    for category, pattern in _CATEGORY_WORDS.items():
        if pattern is not None and pattern.search(words):
            return category
    return GENERAL_KNOWLEDGE


def questions(category: int) -> list[Question]:
    """A category's multiple-choice questions (50, the same all week: see the module's documentation); none when it
    can't be asked, or not now (its cooldown)."""
    if category not in CATEGORIES or not available():
        return []
    params = {"amount": QUESTIONS, "category": category, "type": "multiple"}
    kept = http_util.get(API, params=params, cached_only=True, timeout=TIMEOUT)
    if kept is not None:
        data: Any = _json(kept)
    else:
        data = _ask(params)
    if not isinstance(data, dict) or data.get("response_code") != 0:
        return []
    found = []
    for entry in data.get("results") or []:
        question = _question(entry)
        if question is not None:
            found.append(question)
    return found


def _ask(params: dict[str, Any]) -> Any:
    """Ask the API, five seconds after the request before (waiting for that, if need be)."""
    global _last_asked
    with _turns:
        wait = _last_asked + SPACING - time.monotonic()
        if wait > 0 and not _cooldown.active:
            time.sleep(wait)
        try:
            return http_util.search_json(API, _cooldown, params=params, timeout=TIMEOUT)
        finally:
            _last_asked = time.monotonic()


def _json(response: Any) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _question(entry: Any) -> Question | None:
    if not isinstance(entry, dict) or entry.get("type") != "multiple":
        return None
    wrong = tuple(html.unescape(str(answer)).strip() for answer in entry.get("incorrect_answers") or [])
    question = html.unescape(str(entry.get("question") or "")).strip()
    answer = html.unescape(str(entry.get("correct_answer") or "")).strip()
    if not question or not answer or len(wrong) != 3 or not all(wrong):
        return None
    return Question(
        question,
        answer,
        wrong,
        html.unescape(str(entry.get("category") or "")),
        str(entry.get("difficulty") or ""),
    )
