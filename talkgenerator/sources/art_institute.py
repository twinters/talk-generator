"""Public domain artworks from the Art Institute of Chicago (https://api.artic.edu/docs/).

No key is needed. AIC asks API clients to identify themselves in an AIC-User-Agent header (its
image server refuses requests without one), which http_util sends to every artic.edu address.
"""

from __future__ import annotations

import logging
from typing import Any

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.artic.edu/api/v1/artworks/search"
_IIIF_URL = "https://www.artic.edu/iiif/2"
_IMAGE_WIDTH = 1686  # twice AIC's recommended 843 pixels; available for public domain works


def _map_artwork(item: dict[str, Any], iiif_url: str) -> ImageData | None:
    image_id = item.get("image_id")
    if not image_id:
        return None
    artist = item.get("artist_title") or "Unknown artist"
    return ImageData(
        image_url=f"{iiif_url}/{image_id}/full/{_IMAGE_WIDTH},/0/default.jpg",
        source=f"{artist} (Art Institute of Chicago)",
        source_url=f"https://www.artic.edu/artworks/{item['id']}" if item.get("id") else None,
    )


def search_artworks(query: str, limit: int = 20) -> list[ImageData]:
    if not query or settings.is_source_disabled("ART_INSTITUTE"):
        return []
    data = http_util.get_json(
        API_URL,
        params={
            "q": query,
            "limit": limit,
            "fields": "id,title,artist_title,image_id",
            "query[term][is_public_domain]": "true",
        },
        timeout=15,
    )
    if not isinstance(data, dict):
        return []
    iiif_url = (data.get("config") or {}).get("iiif_url") or _IIIF_URL
    return [image for image in (_map_artwork(item, iiif_url) for item in data.get("data") or []) if image]
