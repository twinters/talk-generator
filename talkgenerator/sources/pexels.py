"""Photos from Pexels (https://www.pexels.com/api/). Needs PEXELS_KEY.

Talks directly to the REST API (the old `pexels-api` wrapper is unmaintained).
"""

import logging
from typing import Any

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.pexels.com/v1/search"
_IMAGE_WIDTH = 1920

_cooldown = http_util.Cooldown("Pexels")


def _api_key() -> str | None:
    if settings.is_source_disabled("PEXELS"):
        return None
    return settings.pexels_auth()["pexels_key"] or None


def _search_pexels(query: str) -> Any:
    api_key = _api_key()
    if not api_key or _cooldown.active:
        return None
    response = http_util.get(API_URL, params={"query": query, "per_page": 40}, headers={"Authorization": api_key})
    if response is None:
        return None
    if response.status_code == 401:
        _cooldown.trigger(60 * 60, "PEXELS_KEY was rejected")
        return None
    if response.status_code == 429:
        _cooldown.trigger(15 * 60, "rate limit reached")
        return None
    if not response.ok:
        logger.warning("Pexels returned HTTP %s", response.status_code)
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _map_to_image_data(photo: dict[str, Any]) -> ImageData | None:
    original = (photo.get("src") or {}).get("original")
    if not original:
        return None
    # The original upload can be huge; ask the CDN for a slide-sized version instead
    image_url = http_util.with_query_params(original, auto="compress", cs="tinysrgb", w=_IMAGE_WIDTH)
    source = photo["photographer"] + " (via Pexels)" if photo.get("photographer") else "Pexels"
    return ImageData(image_url=image_url, source=source, source_url=photo.get("url"))


def search_photos(query: str | None) -> list[ImageData]:
    if not query:
        return []
    results = _search_pexels(query)
    photos = (results or {}).get("photos") or []
    images = [image for image in map(_map_to_image_data, photos) if image]
    if not images:
        logger.info("Pexels returned no images for '%s'", query)
    return images
