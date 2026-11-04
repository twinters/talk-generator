"""Photos from Pixabay (https://pixabay.com/api/docs/). Needs PIXABAY_KEY."""

import logging

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://pixabay.com/api/"
_MAX_QUERY_LENGTH = 100  # imposed by the Pixabay API

_cooldown = http_util.Cooldown("Pixabay")


def get_pixabay_session():
    if settings.is_source_disabled("PIXABAY"):
        return None
    return settings.pixabay_auth()["pixabay_key"] or None


def search_horizontal(query):
    return search_photos(query, orientation="horizontal")


def search_vertical(query):
    return search_photos(query, orientation="vertical")


def search_photos(query, orientation="all") -> list[ImageData]:
    api_key = get_pixabay_session()
    if not api_key or not query or _cooldown.active:
        return []
    params = {
        "key": api_key,
        "q": query[:_MAX_QUERY_LENGTH],
        "image_type": "photo",
        "orientation": orientation,
        "safesearch": "true",
        "per_page": 50,
    }
    response = http_util.get(API_URL, params=params)
    if response is None:
        return []
    if response.status_code == 429:
        _cooldown.trigger(60, "rate limit reached")
        return []
    if response.status_code in (400, 401, 403) and "key" in response.text.lower():
        _cooldown.trigger(60 * 60, "PIXABAY_KEY was rejected")
        return []
    if not response.ok:
        # Pixabay explains errors in plain text, e.g. "[ERROR 400] ..."
        logger.warning("Pixabay returned HTTP %s: %s", response.status_code, http_util.redact(response.text[:200]))
        return []
    try:
        hits = response.json().get("hits") or []
    except ValueError:
        return []

    images = [
        ImageData(
            image_url=photo["largeImageURL"],
            source=photo["user"] + " (via Pixabay)" if photo.get("user") else "Pixabay",
        )
        for photo in hits
        if photo.get("largeImageURL")
    ]
    if not images:
        logger.info("Pixabay returned no images for '%s'", query)
    return images
