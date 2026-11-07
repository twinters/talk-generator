"""Public domain artworks of The Metropolitan Museum of Art (https://metmuseum.github.io/).

No key is needed. Its search gives object IDs, and every object takes a request of its own (both cached for 30 days,
see http_util.CACHE_EXPIRY); the Met asks to keep to 80 requests a second. Its Open Access images (the objects it
marks isPublicDomain) are CC0, and only those carry images in its API. The search (v1.1 since 2026-10-01, when v1's
was retired) takes a medium or type of object and a range of years, which the looks ask for as a type, after and
before (see talkgenerator.images.catalog).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{}"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from its image server, which
# serves them to any page (checked on 2026-11-07: they load with a referrer and without); they're CC0
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): its Open Access images are CC0
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
# The types of object the looks ask for, as the Met's search names them (its "medium")
TYPES: Final = {
    "painting": "Paintings",
    "photograph": "Photographs",
    "print": "Prints",
    "drawing": "Drawings",
    "sculpture": "Sculpture",
}
_FOUND: Final = 12  # objects asked for: only some are public domain (and have their images in the API)
_TIMEOUT = 10
_EARLIEST, _LATEST = -5000, 2100  # (a range needs both of its ends)

_cooldown = http_util.Cooldown("The Met")
_objects = ThreadPoolExecutor(max_workers=4, thread_name_prefix="the Met")


def available() -> bool:
    """Whether the Met can be searched: it isn't switched off (DISABLE_MET). (While it's skipped for a while, see
    _cooldown, a search finds what it found before, from the caches, and the others nothing.)"""
    return not settings.is_source_disabled("MET")


def _map_object(item: dict[str, Any]) -> ImageData | None:
    image_url = item.get("primaryImage")
    if not item.get("isPublicDomain") or not image_url:
        return None
    artist = item.get("artistDisplayName") or item.get("culture") or "Unknown artist"
    page = item.get("objectURL") or None
    name, license_url = licenses.CC0
    title = item.get("title") or None
    date = item.get("objectDate")
    return ImageData(
        image_url=image_url,
        source=f"{artist} (The Metropolitan Museum of Art)",
        source_url=page,
        credit=((artist, page), (" (", None), (name, license_url), (", The Metropolitan Museum of Art)", None)),
        description=f"{title} ({date})" if title and date else title,
        display=DISPLAY,
        license_class="public-domain",
        license=name,
        license_url=license_url,
        # (its "web-large" copy, a few hundred pixels wide: the original can be thousands, and megabytes)
        thumbnail_url=item.get("primaryImageSmall") or None,
    )


def _object(object_id: int) -> dict[str, Any] | None:
    # (its search lists some objects its object API doesn't give: those answer 404)
    data = http_util.search_json(OBJECT_URL.format(object_id), _cooldown, timeout=_TIMEOUT, missing_ok=True)
    return data if isinstance(data, dict) else None


def search_artworks(
    query: str, kind: str | None = None, after: int | None = None, before: int | None = None, limit: int = _FOUND
) -> list[ImageData]:
    """Public domain artworks for the query: of a type (one of TYPES), made after and before some years, if given."""
    if not query or not available():
        return []
    params: dict[str, Any] = {"q": query, "hasImages": "true", "limit": limit}
    if kind in TYPES:
        params["medium"] = TYPES[kind]
    if after is not None or before is not None:
        params["dateBegin"] = after if after is not None else _EARLIEST
        params["dateEnd"] = before if before is not None else _LATEST
    data = http_util.search_json(SEARCH_URL, _cooldown, params=params, timeout=_TIMEOUT)
    ids = [found for found in (data or {}).get("objectIDs") or [] if isinstance(found, int)][:limit]
    images = [image for image in (_map_object(item) for item in _objects.map(_object, ids) if item) if image]
    if not images:
        logger.info("The Met returned no public domain images for '%s'", query)
    return images
