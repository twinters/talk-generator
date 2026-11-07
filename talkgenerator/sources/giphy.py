"""GIFs from GIPHY (https://developers.giphy.com). Needs GIPHY_API_KEY.

GIPHY asks apps to show "Powered by GIPHY", which the credits on the slides do. Its searches aren't cached (see
http_util.CACHE_EXPIRY), as its rules forbid caching API responses and media URLs.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.giphy.com/v1/gifs/search"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): GIPHY requires its media to be
# loaded from its links by the browser itself: "Do not proxy requests to GIPHY", nor store copies
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its gifs (see talkgenerator.images.licenses): fair use
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"fair-use"})
# A still of a gif, small, for a look at it (see talkgenerator.images.analysis)
_STILLS = ("fixed_width_still", "480w_still", "downsized_still")
# Renditions from largest to smallest; image_util refuses GIFs above 16 MB anyway
_RENDITIONS = ("downsized_large", "downsized_medium", "original", "downsized")

_cooldown = http_util.Cooldown("GIPHY")


def _api_key() -> str | None:
    if settings.is_source_disabled("GIPHY"):
        return None
    return settings.giphy_auth()["giphy_api_key"] or None


def available() -> bool:
    """Whether GIPHY can be searched: there's a key. (While it's skipped for a while, see _cooldown, a search finds
    nothing: GIPHY's answers aren't kept. Its place among a look's sources stays the same, as other sources' do.)"""
    return _api_key() is not None


def _map_gif(gif: dict[str, Any]) -> ImageData | None:
    images = gif.get("images") or {}
    still = next((images[name]["url"] for name in _STILLS if (images.get(name) or {}).get("url")), None)
    for rendition in _RENDITIONS:
        url = (images.get(rendition) or {}).get("url")
        if url:
            creator = gif.get("username") or "GIPHY"
            size = images[rendition]
            return ImageData(
                image_url=url,
                source=f"{creator} (Powered by GIPHY)",
                source_url=gif.get("url"),
                description=gif.get("title"),
                display=DISPLAY,
                license_class="fair-use",
                thumbnail_url=still,
                declared_size=image_util.served_size(_number(size.get("width")), _number(size.get("height"))),
            )
    return None


def _number(value: Any) -> int | None:
    """A number GIPHY gives as text, such as a width ("480")."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def search_gifs(query: str) -> list[ImageData]:
    api_key = _api_key()
    if not query or not api_key or _cooldown.active:
        return []
    response = http_util.get(
        API_URL,
        params={"api_key": api_key, "q": query[:50], "limit": 25, "rating": "pg-13", "lang": "en"},
    )
    if response is None or response.status_code >= 500:
        _cooldown.trigger_outage(response)
        return []
    if response.status_code in (401, 403):
        _cooldown.trigger(60 * 60, "GIPHY_API_KEY was rejected")
        return []
    if response.status_code == 429:
        _cooldown.trigger(15 * 60, "rate limit reached")
        return []
    if not response.ok:
        logger.warning("GIPHY returned HTTP %s", response.status_code)
        return []
    try:
        gifs = response.json().get("data") or []
    except ValueError:
        return []
    return [image for image in map(_map_gif, gifs) if image]
