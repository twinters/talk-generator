"""Source images scraped from the ShitpostBot 5000 gallery (https://www.shitpostbot.com)."""

import logging
import random
from functools import lru_cache

from bs4 import BeautifulSoup

from talkgenerator import settings
from talkgenerator.util import http_util, scraper_util

logger = logging.getLogger("talkgenerator")

_MAX_RANDOM_PAGE = 150
_SEARCH_URL = "https://www.shitpostbot.com/gallery/sourceimages"
source_image_prefix = "https://www.shitpostbot.com/img/sourceimages/"


def _search_shitpostbot_page(search_term, page):
    return [element[1] for element in _search_shitpostbot_page_rated(search_term, page)]


@lru_cache(maxsize=64)
def _search_shitpostbot_page_rated(search_term, page):
    if settings.is_source_disabled("SHITPOSTBOT"):
        return []
    params = {
        "query": search_term,
        "review_state": "accepted",
        "order": "total_rating",
        "direction": "DESC",
        "page": page,
    }
    response = http_util.get(_SEARCH_URL, params=params, timeout=8)
    if response is None or not response.ok:
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    image_urls = []
    for entry in soup.find_all("div", class_="col-md-4"):
        try:
            # Check if author doesn't have the search term (False positive)
            user = entry.find("div", class_="caption").find_all("p")[1].find("a").get_text()
            if bool(search_term) and search_term in user:
                continue

            # Get real image url
            image_url = _get_source_image(entry.find("img").get("src"))
            rating_span = entry.find("span", class_="rating")
            rating = int(rating_span.text if rating_span else 1)
        except (AttributeError, IndexError, TypeError, ValueError):
            logger.debug("Skipping unexpected ShitpostBot gallery entry")
            continue
        if rating > 0:
            image_urls.append((rating, image_url))
    return image_urls


def _get_source_image(image_url):
    image_url = image_url.replace("%2F", "/")
    last_slash_idx = image_url.rfind("/")
    image_file_name = image_url[last_slash_idx + 1 :]
    return source_image_prefix + image_file_name


def get_random_images(_):
    return _search_shitpostbot_page("", random.choice(range(1, _MAX_RANDOM_PAGE)))


def get_random_images_rated(_):
    return _search_shitpostbot_page_rated("", random.choice(range(1, _MAX_RANDOM_PAGE)))


_search_image_function = scraper_util.create_page_scraper(_search_shitpostbot_page)
_search_image_function_rated = scraper_util.create_page_scraper(_search_shitpostbot_page_rated)


def search_images(search_term, number=50):
    return _search_image_function(search_term, number)


def search_images_rated(search_term, number=50):
    return _search_image_function_rated(search_term, number)
