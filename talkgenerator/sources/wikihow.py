""" Module for interacting with Wikihow """
import re
import time
import logging
from functools import lru_cache
from itertools import chain
from pathlib import Path

import inflect
import requests
from bs4 import BeautifulSoup
# from cachier import cachier

from talkgenerator import settings

logger = logging.getLogger("talkgenerator")

_LOG_IN_URL = "https://www.wikihow.com/index.php?title=Special:UserLogin&action=submitlogin&type=login"
_ADVANCED_SEARCH_URL = (
    "https://www.wikihow.com/index.php?title=Special%3ASearch&profile=default&search={}"
    "&fulltext=Search&ss=relevance&so=desc&ffriy=1&ffrin=1&fft=ffta&fftsi=&profile=default"
)


def _create_log_in_session(username, password):
    log_in_credentials = {"wpName": username, "wpPassword": password}
    session = requests.session()
    max_session_attempts = 16
    trial = 1
    success = False

    while not success and trial < max_session_attempts:
        try:
            resp = session.post(_LOG_IN_URL, log_in_credentials, log_in_credentials)
            if "Unable to continue login." in resp.text:
                logger.warning("Requests login failed. Unable to continue login.")
                return False
            else:
                success = True
        except requests.exceptions.ConnectionError:
            wait_time = 0.25 * 2 ** trial

            # increment the trial counter
            trial += 1
            logger.error(
                "Connection error with Wikihow! Retrying in "
                + str(wait_time)
                + " seconds."
            )
            time.sleep(wait_time)
            return _create_log_in_session(username, password)

    if trial < max_session_attempts:
        logger.info("Logged into Wikihow")
    else:
        logger.warning("Failed logging into Wikihow")
    return session


def get_wikihow_session():
    wikihow_credentials = settings.wikihow_auth()
    # if session:
    #     logger.warning(
    #         "Found Wikihow Session object in credentials, skipping loggin in"
    #     )
    #     return wikihow_credentials["session"]
    # else:
    #     logger.warning(
    #         "No Wikihow Session object in credentials, attempting log in..."
    #     )
    session = _create_log_in_session(**wikihow_credentials)
    wikihow_credentials["session"] = session
    return session


def remove_how_to(wikihow_title):
    index_of_to = wikihow_title.find("to")
    return wikihow_title[index_of_to + 3 :]


def clean_wikihow_action(action):
    action = _remove_between_brackets(action)
    action = _remove_trademarks(action)
    action = action.strip()
    return action


def _remove_between_brackets(sentence):
    while True:
        s_new = re.sub(r"\([^(]*?\)", r"", sentence)
        if s_new == sentence:
            break
        sentence = s_new
    return sentence


def _remove_trademarks(action):
    if " - wikihow.com" in action:
        return re.sub(" - wikihow.com", "", action)
    return action


@lru_cache(maxsize=20)
# @cachier(cache_dir=Path("..", "tmp").absolute())
def basic_search_wikihow(search_words):
    return requests.get(
        "https://en.wikihow.com/wikiHowTo?search=" + search_words.replace(" ", "+")
    )


# wikihow_session = get_wikihow_session()
wikihow_session = None


@lru_cache(maxsize=20)
# @cachier(cache_dir=Path("..", "tmp").absolute())
def _advanced_search_wikihow(search_words):
    # session = get_wikihow_session()
    if wikihow_session:
        url = _ADVANCED_SEARCH_URL.format(search_words.replace(" ", "+"))
        resp = wikihow_session.get(url, allow_redirects=True)
        if "Login Required - wikiHow" in str(resp.content):
            logger.warning(
                "WARNING: Problem logging in on Wikihow: Advanced Search disabled"
            )
        return resp
    return None


def get_related_wikihow_actions_basic_search(seed_word):
    page = basic_search_wikihow(seed_word)
    # Try again but with plural if nothing is found
    if not page:
        page = basic_search_wikihow(inflect.engine().plural(seed_word))

    soup = BeautifulSoup(page.content, "html.parser")
    actions_elements = soup.find_all("a", class_="result_link")
    action_titles = list(
        chain.from_iterable(
            [a.find_all("div", "result_title") for a in actions_elements]
        )
    )
    actions = [
        clean_wikihow_action(remove_how_to(x.get_text()))
        for x in action_titles
        if x is not None and not x.get_text().startswith("Category")
    ]
    return actions


def get_related_wikihow_actions_advanced_search(seed_word):
    page = _advanced_search_wikihow(seed_word)
    # Try again but with plural if nothing is found
    if not page:
        page = _advanced_search_wikihow(inflect.engine().plural(seed_word))
    if page:
        soup = BeautifulSoup(page.content, "html.parser")
        actions_elements = soup.find_all("div", class_="mw-search-result-heading")
        actions = [clean_wikihow_action(x.find("a")["title"]) for x in actions_elements]
        return actions
    return []


def get_related_wikihow_actions(seed_word):
    """Uses the basic search (advanced search is disabled because it requires login)."""
    if settings.is_source_disabled("WIKIHOW"):
        return []
    return get_related_wikihow_actions_basic_search(seed_word)
