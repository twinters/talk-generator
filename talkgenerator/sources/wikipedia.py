"""Real facts from Wikipedia (https://en.wikipedia.org), the free encyclopedia: an article's lead (and the rest of it,
for the years of its history), and the events of a year, from the year's article ("1886"), for talks with real facts in
them (see talkgenerator.facts, docs/v5-plan.md D60 and D73).

English Wikipedia's, whatever the talk's language: a topic typed in another language is looked up in that language's
Wikipedia and followed to its English article, as English Wikipedia's "Category:Living people" tells which of its
articles are about living people (no fact about one goes on a slide), and the checks of what a slide shouldn't make
light of read English. Its texts are under CC BY-SA 4.0: a slide that shows one credits its article.

Wikimedia asks API clients for a User-Agent that says who they are (http_util's does) and for no more than 200
requests a minute: a talk asks four to eight times, and the cache keeps the answers for a week. No key; a source that
fails is skipped for a while (its cooldown).
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import quote

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API: Final = "https://{language}.wikipedia.org/w/api.php"
LICENSE: Final = "CC BY-SA 4.0"
LICENSE_URL: Final = "https://creativecommons.org/licenses/by-sa/4.0/"
LIVING_PEOPLE: Final = "Category:Living people"
TIMEOUT: Final = 4.0  # seconds: Wikipedia answers in a fraction of one
SENTENCES: Final = 6  # of an article's lead
_TITLES_AT_ONCE: Final = 50  # (the most titles one query takes)
MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_cooldown = http_util.Cooldown("Wikipedia")
_links: ThreadPoolExecutor | None = None
_links_lock = threading.Lock()


def _linking() -> ThreadPoolExecutor:
    """The threads that ask for articles' lead links while the articles are looked up: kept from one article to the
    next, with their sessions and connections (see talkgenerator.facts._asking). Their tasks wait for nothing."""
    global _links
    with _links_lock:
        if _links is None:
            _links = ThreadPoolExecutor(max_workers=4, thread_name_prefix="wikipedia")
        return _links


@dataclass(frozen=True)
class Article:
    """An English Wikipedia article: its title, address, short description and lead (its first sentences, as plain
    text), whether it's about a living person, and the articles its lead links to (by title)."""

    title: str
    url: str
    description: str
    extract: str
    living: bool
    links: tuple[str, ...] = ()


@dataclass(frozen=True)
class Event:
    """An event of a year, as the year's article lists it: its year, and what happened (without its date)."""

    year: int
    text: str


def available() -> bool:
    return not settings.is_source_disabled("WIKIPEDIA")


def article_url(title: str, language: str = "en") -> str:
    return f"https://{language}.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="(),:'!")


def article(topic: str, language: str = "en") -> Article | None:
    """The English article about a topic: the one its title leads to (through redirects), or else the best hit of a
    search whose title has only words of the topic ("Cat" for "Cats are liquid", "Plant" for "office plants"). A topic
    in another language is looked up in that language's Wikipedia first, and followed to its English article. None
    when there's none (or only a disambiguation page), or Wikipedia can't be asked."""
    topic = " ".join(topic.split())
    if not topic or not available():
        return None
    title = topic if language == "en" else _english_title(topic, language)
    if title is None:
        return None
    # (its lead's links while it's looked up: the article the title leads to, most of the time)
    linked = _linking().submit(_lead_links, title)
    page = _page(title)
    links = linked.result()
    if page is None:
        page = _searched(title)
        links = _lead_links(str(page["title"])) if page is not None else ()
    if page is None:
        return None
    found = str(page["title"])
    return Article(
        title=found,
        url=article_url(found),
        description=str(page.get("description") or ""),
        extract=str(page.get("extract") or ""),
        living=bool(page.get("categories")),  # (the only category asked for: see _PAGE)
        links=links,
    )


# What a query asks of an article: its lead's first sentences (as plain text), short description, whether it's in the
# living people's category (the only one asked for), and whether it's a disambiguation page
_PAGE: Final[dict[str, Any]] = {
    "prop": "extracts|description|categories|pageprops",
    "exintro": 1,
    "explaintext": 1,
    "exsentences": SENTENCES,
    "clcategories": LIVING_PEOPLE,
    "ppprop": "disambiguation",
}


def _query(language: str = "en", **params: Any) -> dict[str, Any] | None:
    data = http_util.search_json(
        API.format(language=language),
        _cooldown,
        params={"action": "query", "format": "json", "formatversion": 2, **params},
        timeout=TIMEOUT,
    )
    return data if isinstance(data, dict) else None


def _usable(page: dict[str, Any]) -> bool:
    return (
        not page.get("missing")
        and not page.get("invalid")
        and page.get("ns", 0) == 0
        and "disambiguation" not in (page.get("pageprops") or {})
        and bool(str(page.get("extract") or "").strip())
    )


def _page(title: str) -> dict[str, Any] | None:
    data = _query(titles=title, redirects=1, **_PAGE)
    pages = ((data or {}).get("query") or {}).get("pages") or []
    page = pages[0] if pages and isinstance(pages[0], dict) else None
    return page if page is not None and _usable(page) else None


def _searched(topic: str) -> dict[str, Any] | None:
    data = _query(generator="search", gsrsearch=topic, gsrlimit=5, gsrnamespace=0, exlimit=5, **_PAGE)
    pages = [page for page in ((data or {}).get("query") or {}).get("pages") or [] if isinstance(page, dict)]
    for page in sorted(pages, key=lambda page: int(page.get("index") or 0)):
        if _usable(page) and titled_after(str(page.get("title") or ""), topic):
            return page
    return None


def english_title(topic: str, language: str) -> str | None:
    """The title of the English Wikipedia's article about a topic typed in another language (see _english_title), such
    as "Rain" for Dutch "regen" and "Cinnamon roll" for Swedish "kanelbullar"; None when there's none, or Wikipedia
    can't be asked."""
    topic = " ".join(topic.split())
    if not topic or not available():
        return None
    return _english_title(topic, language)


def _english_title(topic: str, language: str) -> str | None:
    """The English Wikipedia's title of the article that a topic leads to in its language's Wikipedia (or that a
    search there finds first, among those with only words of the topic in their titles). Never an English
    disambiguation page: the article a Dutch page "Regen" links to is "Regen (disambiguation)", where the search finds
    "Regen (neerslag)", rain (D74)."""
    links = {"prop": "langlinks|pageprops", "lllang": "en", "ppprop": "disambiguation"}
    data = _query(language, titles=topic, redirects=1, **links)
    pages = [page for page in ((data or {}).get("query") or {}).get("pages") or [] if isinstance(page, dict)]
    if not pages or pages[0].get("missing") or "disambiguation" in (pages[0].get("pageprops") or {}):
        pages = []
    found = _english_link(pages)
    if found is None:
        data = _query(language, generator="search", gsrsearch=topic, gsrlimit=5, gsrnamespace=0, **links)
        hits = [page for page in ((data or {}).get("query") or {}).get("pages") or [] if isinstance(page, dict)]
        hits.sort(key=lambda page: int(page.get("index") or 0))
        titled = [
            page
            for page in hits
            if titled_after(str(page.get("title") or ""), topic)
            and "disambiguation" not in (page.get("pageprops") or {})
        ]
        found = _english_link(titled)
    return found


def _english_link(pages: Iterable[dict[str, Any]]) -> str | None:
    """The English article that the first of these pages with one links to, but a disambiguation page."""
    for page in pages:
        for link in page.get("langlinks") or []:
            if isinstance(link, dict) and link.get("lang") == "en" and link.get("title"):
                title = str(link["title"])
                if not title.endswith("(disambiguation)"):
                    return title
    return None


def _lead_links(title: str) -> tuple[str, ...]:
    """The articles that an article's lead links to, by title (its infobox's among them)."""
    data = http_util.search_json(
        API.format(language="en"),
        _cooldown,
        params={
            "action": "parse",
            "page": title,
            "prop": "links",
            "section": 0,
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        },
        timeout=TIMEOUT,
    )
    links = ((data or {}).get("parse") or {}).get("links") or [] if isinstance(data, dict) else []
    return tuple(
        str(link["title"]) for link in links if isinstance(link, dict) and link.get("ns") == 0 and link.get("title")
    )


def living(titles: Iterable[str]) -> frozenset[str] | None:
    """Which of these English Wikipedia articles are about living people (in "Category:Living people"), by the titles
    as given (also when one redirects to such an article); None when Wikipedia couldn't tell for all of them."""
    asked = sorted({" ".join(title.split()) for title in titles if title and title.strip()})
    found: set[str] = set()
    for start in range(0, len(asked), _TITLES_AT_ONCE):
        batch = asked[start : start + _TITLES_AT_ONCE]
        data = _query(titles="|".join(batch), redirects=1, prop="categories", clcategories=LIVING_PEOPLE, cllimit="max")
        query = (data or {}).get("query")
        if not isinstance(query, dict):
            return None
        # (a title as given becomes the article's through its normalized form and its redirect, if any)
        renamed = {
            str(step.get("from")): str(step.get("to"))
            for key in ("normalized", "redirects")
            for step in query.get(key) or []
            if isinstance(step, dict)
        }
        people = {
            str(page.get("title"))
            for page in query.get("pages") or []
            if isinstance(page, dict) and page.get("categories")
        }
        for title in batch:
            final = title
            for _ in range(3):  # (normalized, then redirected)
                final = renamed.get(final, final)
            if final in people:
                found.add(title)
    return frozenset(found)


# The sections of an article that say nothing of its topic's history (lists of links and sources)
_NOT_HISTORY: Final = frozenset(
    "see also|references|notes|external links|further reading|bibliography|sources|citations|footnotes".split("|")
)
_HEADING: Final = re.compile(r"^(=+)\s*(.*?)\s*\1$")


def article_text(title: str) -> str:
    """The plain text of an English article (by its title, as article gives it): its lead and every section of it but
    those that list links and sources (see also, references...), for the years of its topic's history (a lead that
    names none, say: D73). Empty when there's none, or Wikipedia can't be asked."""
    if not title.strip() or not available():
        return ""
    data = _query(titles=title, redirects=1, prop="extracts", explaintext=1, exsectionformat="wiki")
    pages = ((data or {}).get("query") or {}).get("pages") or []
    page = pages[0] if pages and isinstance(pages[0], dict) else None
    if page is None or not _usable(page):
        return ""
    kept: list[str] = []
    skipping = False
    for line in str(page.get("extract") or "").splitlines():
        heading = _HEADING.match(line.strip())
        if heading is not None:
            if len(heading.group(1)) == 2:  # (a section: a subsection goes with its section)
                skipping = heading.group(2).strip().lower() in _NOT_HISTORY
            continue
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


# The first and last years whose articles list their events by date, under "Events": the first year that's titled by
# its number alone ("1000"; before it, "AD 79" and "79 BC"), and the year before this one (whose article is still growing)
FIRST_YEAR: Final = 1000

# An event of a year's article, on a line of its own: its date (a month, its day or days, or none) and what happened
_MONTH: Final = "|".join(MONTHS)
_EVENT: Final = re.compile(
    rf"^(?:(?:{_MONTH})(?:\s+\d{{1,2}})?(?:\s*[–-]\s*(?:(?:{_MONTH})\s+)?\d{{1,2}})?\s+)?[–—-]\s+(?P<text>\S.*)$"
)


def year_url(year: int) -> str:
    return article_url(str(year))


def year_events(year: int) -> list[Event]:
    """The events of a year, as its English article ("1886") lists them under "Events", in its order, each without its
    date ("Karl Benz patents the first successful gasoline-driven automobile"); none for a year before FIRST_YEAR, or
    when Wikipedia can't be asked."""
    if year < FIRST_YEAR or not available():
        return []
    data = _query(titles=str(year), redirects=1, prop="extracts", explaintext=1, exsectionformat="wiki")
    pages = ((data or {}).get("query") or {}).get("pages") or []
    page = pages[0] if pages and isinstance(pages[0], dict) else None
    if page is None or not _usable(page):
        return []
    events: list[Event] = []
    listing = False
    for line in str(page.get("extract") or "").splitlines():
        line = " ".join(line.split())
        heading = _HEADING.match(line)
        if heading is not None:
            if len(heading.group(1)) == 2:  # (its months are subsections of "Events")
                listing = heading.group(2).strip().lower() == "events"
            continue
        found = _EVENT.match(line) if listing else None
        if found is not None:
            events.append(Event(year, found.group("text").strip()))
    return events


# A word of a title or a topic, without its qualifier in brackets ("Mercury (planet)")
_WORD: Final = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")


def _forms(word: str) -> set[str]:
    """A word and the forms of it that its plural or singular may have."""
    word = word.lower().replace("’", "'")
    forms = {word, word + "s", word + "es"}
    if word.endswith("ies"):
        forms.add(word[:-3] + "y")
    if word.endswith("es"):
        forms.add(word[:-2])
    if word.endswith("s"):
        forms.add(word[:-1])
    if word.endswith("y"):
        forms.add(word[:-1] + "ies")
    return forms


def titled_after(title: str, topic: str) -> bool:
    """Whether a title has only words of the topic (in their singular or plural), leaving out what it says in brackets:
    "Cat" for "Cats are liquid", "Mercury (planet)" for "Mercury"; not "Die Hard" for "a plant that won't die"."""
    words = _WORD.findall(re.sub(r"\([^)]*\)", " ", title).lower())
    forms = set().union(*(_forms(word) for word in _WORD.findall(topic))) if topic else set()
    return bool(words) and all(word.replace("’", "'") in forms for word in words)
