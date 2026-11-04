"""Freely licensed images from Wikimedia Commons (https://commons.wikimedia.org).

Used for historic photographs, as a reliable alternative to the vintage subreddits. No key is
needed; Wikimedia asks for a descriptive User-Agent, which every request sends.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://commons.wikimedia.org/w/api.php"
_THUMBNAIL_WIDTH = 1920
_IMAGE_MIME_TYPES = ("image/jpeg", "image/png", "image/gif", "image/tiff", "image/webp")
# Old photos: "deepcat" also searches all subcategories (photos per decade, per country, ...)
_HISTORIC_QUERY = '{} deepcat:"Black and white photographs"'


def _plain_text(value: str, max_length: int = 60) -> str:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"


def _map_page(page: dict[str, Any]) -> ImageData | None:
    info = (page.get("imageinfo") or [{}])[0]
    if info.get("mime") not in _IMAGE_MIME_TYPES:
        return None
    image_url = info.get("thumburl") or info.get("url")
    if not image_url:
        return None
    metadata = info.get("extmetadata") or {}
    artist = _plain_text((metadata.get("Artist") or {}).get("value", "")) or "Unknown author"
    license_name = _plain_text((metadata.get("LicenseShortName") or {}).get("value", ""), 30)
    source = (
        f"{artist} ({license_name}, via Wikimedia Commons)" if license_name else f"{artist} (via Wikimedia Commons)"
    )
    return ImageData(image_url=image_url, source=source, source_url=info.get("descriptionurl"))


def search_images(query: str, limit: int = 20) -> list[ImageData]:
    if not query or settings.is_source_disabled("WIKIMEDIA_COMMONS"):
        return []
    data = http_util.get_json(
        API_URL,
        params={
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": str(limit),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": str(_THUMBNAIL_WIDTH),
            "iiextmetadatafilter": "Artist|LicenseShortName",
        },
        timeout=15,
    )
    pages = ((data or {}).get("query") or {}).get("pages") or []
    pages.sort(key=lambda page: page.get("index", 0))  # keep the search ranking
    return [image for image in map(_map_page, pages) if image]


def search_historic_photos(query: str) -> list[ImageData]:
    """Old (black and white) photographs about the query."""
    if not query:
        return []
    return search_images(_HISTORIC_QUERY.format(query)) or search_images(f"{query} historical photograph")
