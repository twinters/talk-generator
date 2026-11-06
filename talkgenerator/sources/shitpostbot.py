"""Source images scraped from the ShitpostBot 5000 gallery (https://www.shitpostbot.com)."""

import logging
from functools import lru_cache

from bs4 import BeautifulSoup, Tag

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util, random_util, scraper_util
from talkgenerator.util.generator_util import planned

logger = logging.getLogger("talkgenerator")

_MAX_RANDOM_PAGE = 150
_SEARCH_URL = "https://www.shitpostbot.com/gallery/sourceimages"
# Its source images are its users' uploads: credited to the gallery they come from
_SOURCE = "ShitpostBot 5000"
source_image_prefix = "https://www.shitpostbot.com/img/sourceimages/"


def _search_shitpostbot_page(search_term: str, page: int) -> list[ImageData]:
    return [element[1] for element in _search_shitpostbot_page_rated(search_term, page)]


@lru_cache(maxsize=64)
def _search_shitpostbot_page_rated(search_term: str, page: int) -> list[tuple[int, ImageData]]:
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
        # Skip false positives: images found because the search term is in the uploader's name
        caption = entry.find("div", class_="caption")
        paragraphs = caption.find_all("p") if isinstance(caption, Tag) else []
        uploader = paragraphs[1].find("a") if len(paragraphs) > 1 else None
        if search_term and isinstance(uploader, Tag) and search_term in uploader.get_text():
            continue

        image = entry.find("img")
        source = image.get("src") if isinstance(image, Tag) else None
        if not isinstance(source, str):
            logger.debug("Skipping unexpected ShitpostBot gallery entry")
            continue
        image_url = _get_source_image(source)
        rating_span = entry.find("span", class_="rating")
        try:
            rating = int(rating_span.get_text()) if isinstance(rating_span, Tag) else 1
        except ValueError:
            rating = 1
        if rating > 0:
            image_urls.append((rating, ImageData(image_url, source=_SOURCE, source_url=_SEARCH_URL)))
    return image_urls


def _get_source_image(image_url: str) -> str:
    image_url = image_url.replace("%2F", "/")
    last_slash_idx = image_url.rfind("/")
    image_file_name = image_url[last_slash_idx + 1 :]
    return source_image_prefix + image_file_name


def get_random_images(_: object) -> list[ImageData]:
    if planned():  # a plan asked for something: a random page isn't it
        return []
    return _search_shitpostbot_page("", random_util.choice(range(1, _MAX_RANDOM_PAGE)))


def get_random_images_rated(_: object) -> list[tuple[int, ImageData]]:
    if planned():
        return []
    return _search_shitpostbot_page_rated("", random_util.choice(range(1, _MAX_RANDOM_PAGE)))


_search_image_function = scraper_util.create_page_scraper(_search_shitpostbot_page)
_search_image_function_rated = scraper_util.create_page_scraper(_search_shitpostbot_page_rated)


def search_images(search_term: str, number: int = 50) -> list[ImageData]:
    return _search_image_function(search_term, number)


def search_images_rated(search_term: str, number: int = 50) -> list[tuple[int, ImageData]]:
    return _search_image_function_rated(search_term, number)
