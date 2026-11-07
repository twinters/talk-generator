"""Photos from Pexels (https://www.pexels.com/api/). Needs PEXELS_KEY.

Talks directly to the REST API (the old `pexels-api` wrapper is unmaintained).
"""

import logging
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.pexels.com/v1/search"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): Pexels' guidelines ask for credit and
# a link, and nothing against showing its photos from its links (checked on 2026-11-07: its images load in a browser's <img>, with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): the Pexels License
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"stock"})
_IMAGE_WIDTH = 1920
_THUMBNAIL_WIDTH = 240
# The filters its search takes (https://www.pexels.com/api/documentation/#photos-search)
COLORS: Final = (
    "red",
    "orange",
    "yellow",
    "green",
    "turquoise",
    "blue",
    "violet",
    "pink",
    "brown",
    "black",
    "gray",
    "white",
)
ORIENTATIONS: Final = {"landscape": "landscape", "portrait": "portrait", "square": "square"}

_cooldown = http_util.Cooldown("Pexels")


def _api_key() -> str | None:
    if settings.is_source_disabled("PEXELS"):
        return None
    return settings.pexels_auth()["pexels_key"] or None


def available() -> bool:
    """Whether a search can go out now: there's a key, and Pexels isn't skipped for a while (see _cooldown)."""
    return _api_key() is not None and not _cooldown.active


def _search_pexels(query: str, color: str | None = None, orientation: str | None = None) -> Any:
    api_key = _api_key()
    if not api_key or _cooldown.active:
        return None
    params: dict[str, Any] = {"query": query, "per_page": 40}
    if color in COLORS:
        params["color"] = color
    if orientation in ORIENTATIONS:
        params["orientation"] = ORIENTATIONS[orientation]
    response = http_util.get(API_URL, params=params, headers={"Authorization": api_key})
    if response is None or response.status_code >= 500:
        _cooldown.trigger_outage(response)
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
    return ImageData(
        image_url=image_url,
        source=source,
        source_url=photo.get("url"),
        description=photo.get("alt"),
        display=DISPLAY,
        license_class="stock",
        license=licenses.PEXELS_LICENSE[0],
        license_url=licenses.PEXELS_LICENSE[1],
        thumbnail_url=http_util.with_query_params(original, auto="compress", cs="tinysrgb", w=_THUMBNAIL_WIDTH),
        declared_size=image_util.served_size(photo.get("width"), photo.get("height"), max_width=_IMAGE_WIDTH),
    )


def search_photos(query: str | None, color: str | None = None, orientation: str | None = None) -> list[ImageData]:
    """Photos for the query, of a color (one of COLORS) and an orientation (landscape, portrait or square), if given."""
    if not query:
        return []
    results = _search_pexels(query, color, orientation)
    photos = (results or {}).get("photos") or []
    images = [image for image in map(_map_to_image_data, photos) if image]
    if not images:
        logger.info("Pexels returned no images for '%s'", query)
    return images
