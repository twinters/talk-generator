"""Photos from Pixabay (https://pixabay.com/api/docs/). Needs PIXABAY_KEY."""

import logging
from typing import Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://pixabay.com/api/"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): Pixabay's API terms say
# that "permanent hotlinking of images (using Pixabay URLs in your app) is not allowed", and to download images to
# your own server to use them; its image links also stop working after 24 hours
DISPLAY: Final[DisplayPolicy] = "copy"
# The license classes of its images (see talkgenerator.images.licenses): the Pixabay Content License
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"stock"})
_MAX_QUERY_LENGTH = 100  # imposed by the Pixabay API
_LARGE_SIDE = 1280  # (its largeImageURL is at most this wide or high)
# The filters its search takes (https://pixabay.com/api/docs/#api_search_images)
COLORS: Final = (
    "grayscale",
    "transparent",
    "red",
    "orange",
    "yellow",
    "green",
    "turquoise",
    "blue",
    "lilac",
    "pink",
    "white",
    "gray",
    "black",
    "brown",
)
IMAGE_TYPES: Final = ("photo", "illustration", "vector")
ORIENTATIONS: Final = {
    "landscape": "horizontal",
    "portrait": "vertical",
    "horizontal": "horizontal",
    "vertical": "vertical",
}

_cooldown = http_util.Cooldown("Pixabay")


def get_pixabay_session() -> str | None:
    if settings.is_source_disabled("PIXABAY"):
        return None
    return settings.pixabay_auth()["pixabay_key"] or None


def available() -> bool:
    """Whether Pixabay can be searched: there's a key. (While it's skipped for a while, see _cooldown, a search finds
    what it found before, from the caches, and the others nothing.)"""
    return get_pixabay_session() is not None


def search_horizontal(query: str) -> list[ImageData]:
    return search_photos(query, orientation="horizontal")


def search_vertical(query: str) -> list[ImageData]:
    return search_photos(query, orientation="vertical")


def search_photos(
    query: str | None, orientation: str = "all", colors: str | None = None, image_type: str = "photo"
) -> list[ImageData]:
    """Images for the query: photos, illustrations or vector graphics (image_type); horizontal or vertical (or
    landscape and portrait), and of some of COLORS (separated by commas), if given."""
    api_key = get_pixabay_session()
    if not api_key or not query:
        return []
    params = {
        "key": api_key,
        "q": query[:_MAX_QUERY_LENGTH],
        "image_type": image_type if image_type in IMAGE_TYPES else "photo",
        "orientation": ORIENTATIONS.get(orientation, "all"),
        "safesearch": "true",
        "per_page": 50,
    }
    chosen_colors = ",".join(color.strip() for color in (colors or "").split(",") if color.strip() in COLORS)
    if chosen_colors:
        params["colors"] = chosen_colors
    cooling = _cooldown.active  # (then only the answers that are kept will do)
    response = http_util.get(API_URL, params=params, cached_only=cooling)
    if response is None and cooling:
        return []
    if response is None or response.status_code >= 500:
        _cooldown.trigger_outage(response)
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
            source_url=photo.get("pageURL"),
            description=photo.get("tags"),
            display=DISPLAY,
            license_class="stock",
            license=licenses.PIXABAY_LICENSE[0],
            license_url=licenses.PIXABAY_LICENSE[1],
            thumbnail_url=photo.get("previewURL"),
            declared_size=image_util.served_size(
                photo.get("imageWidth"), photo.get("imageHeight"), max_side=_LARGE_SIDE
            ),
        )
        for photo in hits
        if photo.get("largeImageURL")
    ]
    if not images:
        logger.info("Pixabay returned no images for '%s'", query)
    return images
