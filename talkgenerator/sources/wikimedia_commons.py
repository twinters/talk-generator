"""Freely licensed images from Wikimedia Commons (https://commons.wikimedia.org).

Used for historic photographs, as a reliable alternative to the vintage subreddits. No key is
needed; Wikimedia asks for a descriptive User-Agent, which every request sends.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://commons.wikimedia.org/w/api.php"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): Commons allows hotlinking
# (though it doesn't recommend it), credited as each file's license asks (checked on 2026-11-07: its images load in a browser's <img>, with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses), each its own: Commons only has free files,
# in the public domain or under licenses that ask for credit (and Creative Commons ones for their license)
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain", "open"})
_THUMBNAIL_WIDTH = 1920
# The width of the thumbnails talkgenerator looks at (see talkgenerator.images.analysis): one of Commons' own sizes
_SMALL_WIDTH = 330
_SIZED_THUMBNAIL = re.compile(r"/(\d+)px-")
_IMAGE_MIME_TYPES = ("image/jpeg", "image/png", "image/gif", "image/tiff", "image/webp")
# Old photos: "deepcat" also searches all subcategories (photos per decade, per country, ...)
_HISTORIC_QUERY = '{} deepcat:"Black and white photographs"'


def _plain_text(value: str, max_length: int = 60) -> str:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()
    return text if len(text) <= max_length else text[: max_length - 1].rstrip() + "…"


def available() -> bool:
    """Whether a search can go out: Wikimedia Commons isn't switched off (DISABLE_WIKIMEDIA_COMMONS)."""
    return not settings.is_source_disabled("WIKIMEDIA_COMMONS")


def _map_page(page: dict[str, Any]) -> ImageData | None:
    info = (page.get("imageinfo") or [{}])[0]
    if info.get("mime") not in _IMAGE_MIME_TYPES:
        return None
    image_url = info.get("thumburl") or info.get("url")
    if not image_url:
        return None
    metadata = info.get("extmetadata") or {}
    artist = _once(_plain_text((metadata.get("Artist") or {}).get("value", ""))) or "Unknown author"
    license_name = _plain_text((metadata.get("LicenseShortName") or {}).get("value", ""), 30)
    license_code = _plain_text((metadata.get("License") or {}).get("value", ""), 30)
    license_url = (metadata.get("LicenseUrl") or {}).get("value") or None
    found = licenses.from_name(license_name, license_code, license_url)
    # (Commons only has free files: a license it doesn't recognise still asks for credit, as the open ones do)
    license_class: LicenseClass = found[0] if found is not None else "open"
    source = (
        f"{artist} ({license_name}, via Wikimedia Commons)" if license_name else f"{artist} (via Wikimedia Commons)"
    )
    credit = (
        (
            (artist, info.get("descriptionurl")),
            (" (", None),
            (license_name, license_url),
            (", via Wikimedia Commons)", None),
        )
        if license_name
        else None
    )
    description = _plain_text((metadata.get("ImageDescription") or {}).get("value", ""), 200)
    width, height = info.get("thumbwidth") or info.get("width"), info.get("thumbheight") or info.get("height")
    return ImageData(
        image_url=image_url,
        source=source,
        source_url=info.get("descriptionurl"),
        credit=credit,
        description=description or None,
        display=DISPLAY,
        license_class=license_class,
        license=license_name or None,
        license_url=license_url,
        thumbnail_url=_small(image_url),
        declared_size=image_util.served_size(width, height),
    )


def _once(text: str) -> str:
    """A name that Commons' HTML holds twice (a visible copy and a hidden one, as in "Unknown author Unknown author"),
    once."""
    words = text.split()
    half = len(words) // 2
    if half and len(words) % 2 == 0 and words[:half] == words[half:]:
        return " ".join(words[:half])
    return text


def _small(image_url: str) -> str | None:
    """The address of a small thumbnail of a file (as Commons makes them), for a look at it; None for a file without
    one: smaller than the size asked for (its address is the file's own), or a page of a document (a TIFF's)."""
    found = _SIZED_THUMBNAIL.search(image_url)
    if found is None:
        return None
    return image_url[: found.start()] + f"/{_SMALL_WIDTH}px-" + image_url[found.end() :]


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
            "iiprop": "url|extmetadata|mime|size",
            "iiurlwidth": str(_THUMBNAIL_WIDTH),
            "iiextmetadatafilter": "Artist|LicenseShortName|License|LicenseUrl",
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
