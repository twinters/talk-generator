"""Photos from Unsplash (https://unsplash.com/developers). Needs UNSPLASH_ACCESS_KEY.

Talks directly to the REST API (the old `pyunsplash` wrapper is unmaintained). Follows the API
guidelines: images are requested through the `urls` Unsplash returns, photographers are credited,
and a download is registered when a photo ends up on a slide. New Unsplash apps start in demo mode
(50 requests per hour); when that runs out, Unsplash is skipped until the limit resets.
"""

import logging
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import CreditPart, ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util
from talkgenerator.util.generator_util import planned

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.unsplash.com"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): Unsplash's guidelines require
# showing its photos from the links its API returns, so every view counts for the photographer
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): the Unsplash License
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"stock"})
UNSPLASH_URL = "https://unsplash.com/"
_IMAGE_WIDTH = 1920
# The filters its search takes (https://unsplash.com/documentation#search-photos)
COLORS: Final = (
    "black_and_white",
    "black",
    "white",
    "yellow",
    "orange",
    "red",
    "purple",
    "magenta",
    "green",
    "teal",
    "blue",
)
ORIENTATIONS: Final = {"landscape": "landscape", "portrait": "portrait", "square": "squarish"}

_cooldown = http_util.Cooldown("Unsplash")


def _access_key() -> str | None:
    if settings.is_source_disabled("UNSPLASH"):
        return None
    return settings.unsplash_auth()["unsplash_access_key"] or None


def available() -> bool:
    """Whether a search can go out now: there's a key, and Unsplash isn't skipped for a while (see _cooldown)."""
    return _access_key() is not None and not _cooldown.active


def _api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    access_key = _access_key()
    if not access_key or _cooldown.active:
        return None
    response = http_util.get(
        API_URL + path,
        params=params,
        headers={"Authorization": "Client-ID " + access_key, "Accept-Version": "v1"},
    )
    if response is None or response.status_code >= 500:
        _cooldown.trigger_outage(response)
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


def _track_download(download_location: str) -> None:
    """Unsplash asks API users to register downloads: https://help.unsplash.com/en/articles/2511258"""
    _api_get(download_location.replace(API_URL, ""))


def _map_to_image_data(photo: dict[str, Any]) -> ImageData | None:
    urls = photo.get("urls") or {}
    image_url = urls.get("raw")
    if image_url:
        image_url = http_util.with_query_params(image_url, w=_IMAGE_WIDTH, fit="max", q=80, fm="jpg")
    else:
        image_url = urls.get("full") or urls.get("regular")
    if not image_url:
        return None
    thumbnail = urls.get("thumb") or urls.get("small")
    user = photo.get("user") or {}
    name = user.get("name")
    profile = _profile_link(user)
    # The attribution Unsplash asks for: "Photo by <photographer> on Unsplash", linking both
    credit: tuple[CreditPart, ...]
    if name:
        source = f"Photo by {name} on Unsplash"
        credit = (("Photo by ", None), (name, profile), (" on ", None), ("Unsplash", _with_referral(UNSPLASH_URL)))
    else:
        source, credit = "Unsplash", (("Unsplash", _with_referral(UNSPLASH_URL)),)
    download_location = (photo.get("links") or {}).get("download_location")
    on_use = (lambda: _track_download(download_location)) if download_location else None
    description = photo.get("alt_description") or photo.get("description")
    return ImageData(
        image_url=image_url,
        source=source,
        on_use=on_use,
        source_url=profile,
        credit=credit,
        description=description,
        display=DISPLAY,
        license_class="stock",
        license=licenses.UNSPLASH_LICENSE[0],
        license_url=licenses.UNSPLASH_LICENSE[1],
        thumbnail_url=thumbnail,
        declared_size=image_util.served_size(photo.get("width"), photo.get("height"), max_width=_IMAGE_WIDTH),
    )


def _profile_link(user: dict[str, Any]) -> str:
    """Link to the photographer's profile, tagged the way Unsplash's attribution guidelines ask."""
    return _with_referral((user.get("links") or {}).get("html") or UNSPLASH_URL)


def _with_referral(url: str) -> str:
    # Unsplash's guidelines: every link back to Unsplash says which app it comes from
    return http_util.with_query_params(url, utm_source=settings.unsplash_app_name(), utm_medium="referral")


def random(_: object = None) -> ImageData | None:
    photo = _api_get("/photos/random")
    if not photo:
        logger.info("Couldn't get a random Unsplash image")
        return None
    return _map_to_image_data(photo)


def random_as_list(_: object = None) -> list[ImageData]:
    if planned():  # a plan asked for something: a random photo isn't it
        return []
    result = random(_)
    return [result] if result else []


def search_photos(query: str | None, color: str | None = None, orientation: str | None = None) -> list[ImageData]:
    """Photos for the query, of a color (one of COLORS) and an orientation (landscape, portrait or square), if given."""
    if not query:
        return random_as_list()
    if not _access_key():
        logger.debug("Unsplash is disabled or UNSPLASH_ACCESS_KEY is missing")
        return []
    params: dict[str, Any] = {"query": query, "per_page": 30, "content_filter": "high"}
    if color in COLORS:
        params["color"] = color
    if orientation in ORIENTATIONS:
        params["orientation"] = ORIENTATIONS[orientation]
    results = _api_get("/search/photos", params=params)
    photos = (results or {}).get("results") or []
    images = [image for image in map(_map_to_image_data, photos) if image]
    if not images:
        logger.info("Unsplash returned no images for '%s'", query)
    return images
