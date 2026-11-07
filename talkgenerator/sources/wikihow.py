"""Actions ("how to ...") scraped from WikiHow's public search."""

import logging
import re
from functools import lru_cache
from itertools import chain
from typing import Final

import inflect
from bs4 import BeautifulSoup

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

_SEARCH_URL = "https://www.wikihow.com/wikiHowTo"

# A how-to's title: "How to Draw a Penguin", or "4 Easy Ways to Draw Cute Cats". WikiHow's search finds other pages
# too, which teach no action: lists ("330 Cool & Unique Names for Penguins"), quizzes, questions ("How Do You Store
# Cheese?") and categories
_HOW_TO: Final = re.compile(r"(?:how to|(?:\d+\s+)?(?:[^\W\d_]+\s+)?ways to)\s+(?P<action>.+)", re.IGNORECASE)


def action_of(wikihow_title: str) -> str | None:
    """The action a wikiHow page's title teaches ("How to Draw a Penguin": "Draw a Penguin"), without what's in
    brackets or after a colon ("...: 8 Simple Tricks"), or None for a page that isn't a how-to."""
    match = _HOW_TO.fullmatch(" ".join(wikihow_title.split()))
    if match is None:
        return None
    return clean_wikihow_action(match.group("action").split(": ")[0]) or None


def clean_wikihow_action(action: str) -> str:
    action = _remove_between_brackets(action)
    action = _remove_trademarks(action)
    action = re.sub(r"\s+", " ", action).strip()
    return action


def _remove_between_brackets(sentence: str) -> str:
    while True:
        s_new = re.sub(r"\([^(]*?\)", r"", sentence)
        if s_new == sentence:
            break
        sentence = s_new
    return sentence


def _remove_trademarks(action: str) -> str:
    if " - wikihow.com" in action:
        return re.sub(" - wikihow.com", "", action)
    return action


@lru_cache(maxsize=64)
def basic_search_wikihow(search_words: str) -> bytes | None:
    response = http_util.get(_SEARCH_URL, params={"search": search_words}, timeout=8)
    if response is None or not response.ok:
        return None
    return response.content


def get_related_wikihow_actions_basic_search(seed_word: str) -> list[str]:
    if not seed_word or not seed_word.strip():
        return []
    page = basic_search_wikihow(seed_word)
    # Try again but with plural if nothing is found
    if not page:
        page = basic_search_wikihow(inflect.engine().plural(seed_word))
    if not page:
        return []

    soup = BeautifulSoup(page, "html.parser")
    actions_elements = soup.find_all("a", class_="result_link")
    action_titles = list(chain.from_iterable([a.find_all("div", class_="result_title") for a in actions_elements]))
    actions = [action_of(x.get_text()) for x in action_titles if x is not None]
    return [action for action in actions if action]


def get_related_wikihow_actions(seed_word: str) -> list[str]:
    """Uses WikiHow's basic search (the advanced search requires logging in)."""
    if settings.is_source_disabled("WIKIHOW"):
        return []
    return get_related_wikihow_actions_basic_search(seed_word)
