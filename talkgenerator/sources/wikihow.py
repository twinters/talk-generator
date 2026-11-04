"""Actions ("how to ...") scraped from WikiHow's public search."""

import logging
import re
from functools import lru_cache
from itertools import chain

import inflect
from bs4 import BeautifulSoup

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

_SEARCH_URL = "https://www.wikihow.com/wikiHowTo"


def remove_how_to(wikihow_title: str) -> str:
    index_of_to = wikihow_title.find("to")
    return wikihow_title[index_of_to + 3 :]


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
    actions = [
        clean_wikihow_action(remove_how_to(x.get_text()))
        for x in action_titles
        if x is not None and not x.get_text().startswith("Category")
    ]
    return [action for action in actions if action]


def get_related_wikihow_actions(seed_word: str) -> list[str]:
    """Uses WikiHow's basic search (the advanced search requires logging in)."""
    if settings.is_source_disabled("WIKIHOW"):
        return []
    return get_related_wikihow_actions_basic_search(seed_word)
