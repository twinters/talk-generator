"""Public domain artworks from the Art Institute of Chicago (https://api.artic.edu/docs/).

No key is needed. AIC asks API clients to identify themselves in an AIC-User-Agent header (its
image server refuses requests without one), which http_util sends to every artic.edu address.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.artic.edu/api/v1/artworks/search"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): its image server refuses requests
# without an AIC-User-Agent header (checked on 2026-11-07: Cloudflare answers 403, with a challenge), which an
# <img> tag can't send, so a pass-through proxy that adds it shows them
DISPLAY: Final[DisplayPolicy] = "proxy"
# The license classes of its images (see talkgenerator.images.licenses): only public domain works are asked for, whose
# images AIC releases under CC0
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
_IIIF_URL = "https://www.artic.edu/iiif/2"
_IMAGE_WIDTH = 1686  # twice AIC's recommended 843 pixels; available for public domain works
_THUMBNAIL_WIDTH = 200


def available() -> bool:
    """Whether a search can go out: the Art Institute isn't switched off (DISABLE_ART_INSTITUTE)."""
    return not settings.is_source_disabled("ART_INSTITUTE")


def _map_artwork(item: dict[str, Any], iiif_url: str) -> ImageData | None:
    image_id = item.get("image_id")
    if not image_id:
        return None
    artist = item.get("artist_title") or "Unknown artist"
    page = f"https://www.artic.edu/artworks/{item['id']}" if item.get("id") else None
    name, license_url = licenses.CC0
    thumbnail = item.get("thumbnail") or {}
    return ImageData(
        image_url=f"{iiif_url}/{image_id}/full/{_IMAGE_WIDTH},/0/default.jpg",
        source=f"{artist} (Art Institute of Chicago)",
        source_url=page,
        credit=((artist, page), (" (", None), (name, license_url), (", Art Institute of Chicago)", None)),
        description=item.get("title"),
        display=DISPLAY,
        license_class="public-domain",
        license=name,
        license_url=license_url,
        thumbnail_url=f"{iiif_url}/{image_id}/full/{_THUMBNAIL_WIDTH},/0/default.jpg",
        declared_size=image_util.served_size(thumbnail.get("width"), thumbnail.get("height"), max_width=_IMAGE_WIDTH),
    )


def search_artworks(query: str, limit: int = 20) -> list[ImageData]:
    if not query or settings.is_source_disabled("ART_INSTITUTE"):
        return []
    data = http_util.get_json(
        API_URL,
        params={
            "q": query,
            "limit": limit,
            "fields": "id,title,artist_title,image_id,thumbnail",
            "query[term][is_public_domain]": "true",
        },
        timeout=15,
    )
    if not isinstance(data, dict):
        return []
    iiif_url = (data.get("config") or {}).get("iiif_url") or _IIIF_URL
    return [image for image in (_map_artwork(item, iiif_url) for item in data.get("data") or []) if image]
