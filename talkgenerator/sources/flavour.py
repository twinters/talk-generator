"""Flavour texts, real facts' lighter side (see talkgenerator.facts, docs/v5-plan.md D60): random useless facts
(https://uselessfacts.jsph.pl), dad jokes (https://icanhazdadjoke.com) and advice slips (https://api.adviceslip.com),
from three small free APIs without keys. Their sites state no license for their texts; the user allowed them on the
public site on 2026-11-08. A slide that shows one credits its site.

Every answer is cached (see http_util.CACHE_EXPIRY), so that a talk made again gets the same texts: a useless fact is
one of a pool of POOL a week (the API answers at random, and the cache keeps one answer per number of the pool, which
the API ignores), a dad joke comes from a search for a word (a whole word: the API matches "cat" in "catholic") or else
from one of the pages of all of them, and an advice slip goes by its number. A source that fails is skipped for a while
(its cooldown), and gives nothing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

USELESS_FACTS: Final = "https://uselessfacts.jsph.pl/api/v2/facts/random"
DAD_JOKES: Final = "https://icanhazdadjoke.com/search"
ADVICE: Final = "https://api.adviceslip.com/advice/{number}"
TIMEOUT: Final = 4.0
POOL: Final = 12  # useless facts a week
JOKES_A_PAGE: Final = 30  # (the most the search gives at once)
JOKE_PAGES: Final = 24  # (744 jokes on 2026-11-08: 25 pages of 30, the last not full)
ADVICE_SLIPS: Final = 224  # (numbered from 1; 225 isn't there)

_useless = http_util.Cooldown("Useless facts")
_jokes = http_util.Cooldown("icanhazdadjoke")
_advice = http_util.Cooldown("Advice Slip")


@dataclass(frozen=True)
class Flavour:
    """A flavour text, with its source as a slide credits it and its page."""

    text: str
    source: str
    url: str


def available(name: str) -> bool:
    """Whether a flavour source may be asked: "USELESS_FACTS", "DAD_JOKES" or "ADVICE_SLIPS" (see DISABLE_<NAME>)."""
    return not settings.is_source_disabled(name)


def _clean(text: Any) -> str:
    return " ".join(str(text or "").replace("’", "'").replace("‘", "'").split())


def useless_fact(number: int) -> Flavour | None:
    """The useless fact of the pool's number (0 to POOL - 1) this week, in English; none when it can't be had."""
    if not available("USELESS_FACTS"):
        return None
    params = {"language": "en", "i": number % POOL}  # (the API ignores i: the cache keys an answer by it)
    data = http_util.search_json(USELESS_FACTS, _useless, params=params, timeout=TIMEOUT)
    if not isinstance(data, dict) or data.get("language") not in (None, "en"):
        return None
    text = _clean(data.get("text"))
    url = str(data.get("permalink") or "https://uselessfacts.jsph.pl")
    return Flavour(text, "Useless Facts", url) if text else None


def dad_jokes(word: str | None = None, page: int = 1) -> list[Flavour]:
    """Dad jokes: the ones about a word (as a whole word, or its plural), or without one, a page of all of them (from
    1 to JOKE_PAGES); none when they can't be had."""
    if not available("DAD_JOKES"):
        return []
    params: dict[str, Any] = {"limit": JOKES_A_PAGE}
    if word:
        params["term"] = word.lower()
    else:
        params["page"] = max(1, min(page, JOKE_PAGES))
    data = http_util.search_json(
        DAD_JOKES, _jokes, params=params, headers={"Accept": "application/json"}, timeout=TIMEOUT
    )
    results = data.get("results") if isinstance(data, dict) else None
    whole = re.compile(rf"\b{re.escape(word.lower())}(?:s|es)?\b") if word else None
    jokes = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        text = _clean(result.get("joke"))
        if text and (whole is None or whole.search(text.lower())):
            jokes.append(Flavour(text, "icanhazdadjoke", f"https://icanhazdadjoke.com/j/{result.get('id', '')}"))
    return jokes


def advice(number: int) -> Flavour | None:
    """The advice slip of a number (from 1 to ADVICE_SLIPS); none when it can't be had."""
    if not available("ADVICE_SLIPS"):
        return None
    number = 1 + (number - 1) % ADVICE_SLIPS
    data = http_util.search_json(ADVICE.format(number=number), _advice, timeout=TIMEOUT)
    slip = data.get("slip") if isinstance(data, dict) else None
    text = _clean(slip.get("advice")) if isinstance(slip, dict) else ""
    return Flavour(text, "Advice Slip", ADVICE.format(number=number)) if text else None
