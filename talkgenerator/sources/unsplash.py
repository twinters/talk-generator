"""Photos from Unsplash (https://unsplash.com/developers). Needs UNSPLASH_ACCESS_KEY.

Talks directly to the REST API (the old `pyunsplash` wrapper is unmaintained). Follows the API
guidelines: images are requested through the `urls` Unsplash returns, photographers are credited,
and a download is registered when a photo ends up on a slide. New Unsplash apps start in demo mode
(50 requests per hour); when that runs out, Unsplash is skipped until the limit resets.
"""

import logging

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.unsplash.com"
_IMAGE_WIDTH = 1920

_cooldown = http_util.Cooldown("Unsplash")


def _access_key() -> str | None:
    if settings.is_source_disabled("UNSPLASH"):
        return None
    return settings.unsplash_auth()["unsplash_access_key"] or None


def _api_get(path, params=None):
    access_key = _access_key()
    if not access_key or _cooldown.active:
        return None
    response = http_util.get(
        API_URL + path,
        params=params,
        headers={"Authorization": "Client-ID " + access_key, "Accept-Version": "v1"},
    )
    if response is None:
        return None
    if response.status_code == 401:
        _cooldown.trigger(60 * 60, "UNSPLASH_ACCESS_KEY was rejected")
        return None
    if response.status_code in (403, 429) and response.headers.get("X-Ratelimit-Remaining") == "0":
        limit = response.headers.get("X-Ratelimit-Limit", "?")
        _cooldown.trigger(15 * 60, f"rate limit of {limit} requests per hour reached")
        return None
    if not response.ok:
        logger.warning("Unsplash returned HTTP %s for %s", response.status_code, path)
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _track_download(download_location):
    """Unsplash asks API users to register downloads: https://help.unsplash.com/en/articles/2511258"""
    _api_get(download_location.replace(API_URL, ""))


def _map_to_image_data(photo) -> ImageData | None:
    urls = photo.get("urls") or {}
    image_url = urls.get("raw")
    if image_url:
        image_url = http_util.with_query_params(image_url, w=_IMAGE_WIDTH, fit="max", q=80, fm="jpg")
    else:
        image_url = urls.get("full") or urls.get("regular")
    if not image_url:
        return None
    user = photo.get("user") or {}
    source = user["name"] + " (via Unsplash)" if user.get("name") else "Unsplash"
    download_location = (photo.get("links") or {}).get("download_location")
    on_use = (lambda: _track_download(download_location)) if download_location else None
    return ImageData(image_url=image_url, source=source, on_use=on_use)


def random(_=None) -> ImageData | None:
    photo = _api_get("/photos/random")
    if not photo:
        logger.info("Couldn't get a random Unsplash image")
        return None
    return _map_to_image_data(photo)


def random_as_list(_=None) -> list[ImageData]:
    result = random(_)
    return [result] if result else []


def search_photos(query) -> list[ImageData]:
    if not query:
        return random_as_list()
    if not _access_key():
        logger.debug("Unsplash is disabled or UNSPLASH_ACCESS_KEY is missing")
        return []
    results = _api_get("/search/photos", params={"query": query, "per_page": 30, "content_filter": "high"})
    photos = (results or {}).get("results") or []
    images = [image for image in map(_map_to_image_data, photos) if image]
    if not images:
        logger.info("Unsplash returned no images for '%s'", query)
    return images
