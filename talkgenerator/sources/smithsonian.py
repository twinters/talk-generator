"""CC0 images of the Smithsonian's museums and archives (https://www.si.edu/openaccess). Needs DATA_GOV_API_KEY.

Its Open Access API takes a free key from api.data.gov (https://api.data.gov/signup/), which allows 1,000 requests an
hour; searches are cached for 30 days (see http_util.CACHE_EXPIRY). Only CC0 images are asked for, from its IIIF
image server, in any size. Its search takes a type of object (as its records name them: "Paintings",
"Photographs"...), which the looks ask for as a type (see talkgenerator.images.catalog).
"""

from __future__ import annotations

import logging
from typing import Any, Final
from urllib.parse import quote

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.si.edu/openaccess/api/v1.0/search"
IIIF_URL = "https://ids.si.edu/ids/iiif/{}/full/{}/0/default.jpg"
RECORD_URL = "https://collections.si.edu/search/detail/{}"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from its IIIF image server, which
# serves them to any page (checked on 2026-11-07: they load with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): only CC0 images are asked for
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
# The types of object the looks ask for, as its records name them
TYPES: Final = {"painting": "Paintings", "photograph": "Photographs"}
_IMAGE_SIZE = 1600  # the longest side asked of its image server
_THUMBNAIL_WIDTH = 300
_TIMEOUT = 15

_cooldown = http_util.Cooldown("Smithsonian Open Access")


def _api_key() -> str | None:
    if settings.is_source_disabled("SMITHSONIAN"):
        return None
    return settings.data_gov_auth()["data_gov_api_key"] or None


def available() -> bool:
    """Whether a search can go out now: there's a key, and the Smithsonian isn't skipped for a while."""
    return _api_key() is not None and not _cooldown.active


def _text(field: Any) -> str:
    """The text of one of its fields, which it gives as {"label": ..., "content": ...} (or a list of them)."""
    if isinstance(field, list):
        field = field[0] if field else None
    if isinstance(field, dict):
        return str(field.get("content") or "").strip()
    return str(field or "").strip()


def _map_row(row: dict[str, Any]) -> ImageData | None:
    content = row.get("content") or {}
    record = content.get("descriptiveNonRepeating") or {}
    media = [
        found
        for found in (record.get("online_media") or {}).get("media") or []
        if found.get("type") == "Images" and (found.get("usage") or {}).get("access") == "CC0" and found.get("idsId")
    ]
    if not media:
        return None
    shown = media[0]
    ids_id = quote(str(shown["idsId"]), safe="")
    freetext = content.get("freetext") or {}
    # (its names come with their lives: "Thomas Eakins, American, b. Philadelphia, Pennsylvania, 1844–1916")
    artist = _text(freetext.get("name")).split(",")[0].strip() or "Unknown artist"
    museum = str(record.get("data_source") or "Smithsonian Institution")
    page = record.get("record_link") or (RECORD_URL.format(row["url"]) if row.get("url") else None)
    name, license_url = licenses.CC0
    title = _text(record.get("title")) or row.get("title") or None
    width, height = shown.get("width"), shown.get("height")
    return ImageData(
        image_url=IIIF_URL.format(ids_id, f"!{_IMAGE_SIZE},{_IMAGE_SIZE}"),
        source=f"{artist} ({museum})",
        source_url=page,
        credit=((artist, page), (" (", None), (name, license_url), (f", {museum})", None)),
        description=title,
        display=DISPLAY,
        license_class="public-domain",
        license=name,
        license_url=license_url,
        thumbnail_url=IIIF_URL.format(ids_id, f"{_THUMBNAIL_WIDTH},"),
        # (the size its record gives can be the original's, larger than what its image server serves)
        declared_size=image_util.served_size(width, height, max_side=_IMAGE_SIZE),
    )


def search_images(query: str, kind: str | None = None, limit: int = 20) -> list[ImageData]:
    """CC0 images for the query, of a type of object (one of TYPES), if given."""
    api_key = _api_key()
    if not query or not api_key or _cooldown.active:
        return []
    terms = [query.replace('"', " "), "online_media_type:Images", "media_usage:CC0"]
    if kind in TYPES:
        terms.append(f'object_type:"{TYPES[kind]}"')
    params = {"q": " AND ".join(terms), "rows": limit, "api_key": api_key}
    data = http_util.search_json(API_URL, _cooldown, params=params, timeout=_TIMEOUT)
    rows = ((data or {}).get("response") or {}).get("rows") or []
    images = [image for image in map(_map_row, rows) if image]
    if not images:
        logger.info("The Smithsonian returned no CC0 images for '%s'", query)
    return images
