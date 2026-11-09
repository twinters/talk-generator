"""Quotes from Wikiquote (https://en.wikiquote.org), the free quote collection of the Wikimedia projects.

Used next to Goodreads, so quote slides keep working when one of the two is down or changes.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from bs4 import BeautifulSoup, Tag

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://en.wikiquote.org/w/api.php"
MIN_QUOTE_LENGTH = 20
MAX_QUOTE_LENGTH = 300
# Sections that don't contain (reliable) quotes
_SKIPPED_SECTIONS = {"see also", "external links", "references", "sources", "notes", "disputed", "misattributed"}
# and a film's or a show's cast list, its actors and their roles (a quote slide said "<an actor> - Japanese Kid /
# Announcer", from The Proud Family Movie's page, all 23 of whose "quotes" were its cast)
_CAST_LIST = re.compile(
    r"(?:(?:main|voice|principal|supporting|recurring|guest) )?cast(?: (?:list|members|and characters|and crew))?"
    r"|starring"
)


def _clean(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text)  # footnote markers
    return re.sub(r"\s+", " ", text).strip()


def _heading_text(element: Tag) -> str | None:
    if element.name in ("h2", "h3"):
        return element.get_text(" ", strip=True)
    if "mw-heading" in (element.get("class") or []):
        heading = element.find(["h2", "h3"])
        return heading.get_text(" ", strip=True) if heading else ""
    return None


def extract_quotes(page_html: str) -> list[str]:
    """The quotes of a Wikiquote page: top-level list items, without their nested attributions."""
    soup = BeautifulSoup(page_html, "html.parser")
    root = soup.find(class_="mw-parser-output") or soup
    quotes = []
    skipping = False
    for element in root.find_all(recursive=False):
        heading = _heading_text(element)
        if heading is not None:
            skipping = heading.lower() in _SKIPPED_SECTIONS or bool(_CAST_LIST.fullmatch(heading.lower()))
            continue
        if skipping or element.name != "ul":
            continue
        for item in element.find_all("li", recursive=False):
            for nested in item.find_all(["ul", "ol", "dl"]):
                nested.decompose()  # the attribution ("Author, Work (year)")
            quote = _clean(item.get_text(" "))
            if MIN_QUOTE_LENGTH <= len(quote) <= MAX_QUOTE_LENGTH:
                quotes.append(quote)
    return quotes


def _get(params: dict[str, Any]) -> dict[str, Any]:
    data = http_util.get_json(API_URL, params={**params, "format": "json", "formatversion": "2"}, timeout=15)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=128)
def search_quotes(topic: str, max_pages: int = 2) -> tuple[str, ...]:
    """Quotes from the Wikiquote pages that best match the topic."""
    if not topic or not topic.strip() or settings.is_source_disabled("WIKIQUOTE"):
        return ()
    hits = (
        _get({"action": "query", "list": "search", "srsearch": topic, "srlimit": max_pages}).get("query") or {}
    ).get("search") or []
    quotes: list[str] = []
    for hit in hits:
        page = _get({"action": "parse", "page": hit["title"], "prop": "text", "redirects": "1"})
        quotes.extend(extract_quotes((page.get("parse") or {}).get("text", "")))
    return tuple(quotes)
