"""Public domain artworks of the Cleveland Museum of Art (https://openaccess-api.clevelandart.org/).

No key is needed, and its Open Access images (the artworks it shares as CC0) come with their search. Its search takes
a type of artwork and a range of years, which the looks ask for as a type, after and before (see
talkgenerator.images.catalog).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://openaccess-api.clevelandart.org/api/artworks/"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from its image server, which
# serves them to any page (checked on 2026-11-07: they load with a referrer and without); they're CC0
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): only CC0 artworks are asked for
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
# The types of artwork the looks ask for, as Cleveland's search names them
TYPES: Final = {
    "painting": "Painting",
    "photograph": "Photograph",
    "print": "Print",
    "drawing": "Drawing",
    "sculpture": "Sculpture",
}
_FIELDS: Final = "id,title,creation_date,type,url,creators,images,share_license_status,culture"
_TIMEOUT = 10
# What a creator's description adds to their name: "Min Zhen (Chinese, 1730–after 1788)"
_LIFE: Final = re.compile(r"\s*\(.*\)\s*$")

_cooldown = http_util.Cooldown("Cleveland Museum of Art")


def available() -> bool:
    """Whether a search can go out now: Cleveland isn't switched off (DISABLE_CLEVELAND), nor skipped for a while."""
    return not settings.is_source_disabled("CLEVELAND") and not _cooldown.active


def _number(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _creator(item: dict[str, Any]) -> str:
    for creator in item.get("creators") or []:
        name = _LIFE.sub("", str(creator.get("description") or "")).strip()
        if name:
            return name
    culture = item.get("culture") or []
    return str(culture[0]) if culture else "Unknown artist"


def _map_artwork(item: dict[str, Any]) -> ImageData | None:
    if str(item.get("share_license_status") or "").upper() != "CC0":
        return None
    images = item.get("images") or {}
    # Its web copy, about 900 pixels on its longest side: its print copy (3,400) takes 4 to 7 MB, which its image
    # server sends slowly (7 seconds, measured on 2026-11-07), and its full one is a TIFF of tens of megabytes
    shown = images.get("web") or images.get("print") or {}
    small = shown
    if not shown.get("url"):
        return None
    artist = _creator(item)
    page = item.get("url") or None
    name, license_url = licenses.CC0
    title = item.get("title") or None
    date = item.get("creation_date")
    return ImageData(
        image_url=shown["url"],
        source=f"{artist} (Cleveland Museum of Art)",
        source_url=page,
        credit=((artist, page), (" (", None), (name, license_url), (", Cleveland Museum of Art)", None)),
        description=f"{title} ({date})" if title and date else title,
        display=DISPLAY,
        license_class="public-domain",
        license=name,
        license_url=license_url,
        thumbnail_url=small.get("url"),
        declared_size=image_util.served_size(_number(shown.get("width")), _number(shown.get("height"))),
    )


def search_artworks(
    query: str, kind: str | None = None, after: int | None = None, before: int | None = None, limit: int = 20
) -> list[ImageData]:
    """CC0 artworks for the query: of a type (one of TYPES), made after and before some years, if given."""
    if not query or not available():
        return []
    params: dict[str, Any] = {"q": query, "has_image": 1, "cc0": 1, "limit": limit, "fields": _FIELDS}
    if kind in TYPES:
        params["type"] = TYPES[kind]
    if after is not None:
        params["created_after"] = after
    if before is not None:
        params["created_before"] = before
    data = http_util.search_json(API_URL, _cooldown, params=params, timeout=_TIMEOUT)
    images = [image for image in map(_map_artwork, (data or {}).get("data") or []) if image]
    if not images:
        logger.info("The Cleveland Museum of Art returned no images for '%s'", query)
    return images
