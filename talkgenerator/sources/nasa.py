"""Pictures from NASA's Image and Video Library (https://images.nasa.gov, its API at https://images-api.nasa.gov).

No key is needed. NASA's own pictures aren't under copyright in the United States (its media usage guidelines), so
they're credited to NASA (and its photographer) without a license; pictures it notes as someone else's copyright are
left out. Its search takes a range of years, which the looks ask for as after and before (see
talkgenerator.images.catalog), and finds NASA's take on almost anything: pizza aboard the space station, a crater
that looks like a cat's eye.
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

API_URL = "https://images-api.nasa.gov/search"
PAGE_URL = "https://images.nasa.gov/details/{}"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from NASA's image server, which
# serves them to any page (checked on 2026-11-07: they load with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): NASA's own work isn't under copyright
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
# Its renditions, largest first (an "orig" can be tens of megabytes), and the small one to look at
_RENDITIONS: Final = ("large", "medium", "orig")
_SMALL: Final = ("small", "thumb", "medium")
_MOST_BYTES: Final = 15 * 1024 * 1024  # (an original larger than this is left for another picture)
_TIMEOUT = 10
# A picture that's someone else's (a news agency's, say), as its description or credits tell
_COPYRIGHTED: Final = re.compile(r"©|\(c\)|\bcopyright\b|\bgetty images\b|\breuters\b|\bap photo\b", re.IGNORECASE)
# A title that's only a picture's number ("iss059e006481", "KSC-2014-4339"), not what it shows
_NUMBERED: Final = re.compile(r"^[\w.-]*\d[\w.-]*$")

_cooldown = http_util.Cooldown("NASA's Image and Video Library")


def available() -> bool:
    """Whether a search can go out now: NASA isn't switched off (DISABLE_NASA), nor skipped for a while."""
    return not settings.is_source_disabled("NASA") and not _cooldown.active


def _rendition(links: list[dict[str, Any]], names: tuple[str, ...]) -> dict[str, Any] | None:
    by_name = {str(link.get("href", "")).rsplit("~", 1)[-1].split(".")[0]: link for link in links if link.get("href")}
    small_enough = [name for name in names if name in by_name and _bytes(by_name[name]) <= _MOST_BYTES]
    return by_name[small_enough[0]] if small_enough else None


def _bytes(link: dict[str, Any]) -> float:
    size = link.get("size")
    return float(size) if isinstance(size, int | float) else 0.0


def _description(data: dict[str, Any]) -> str | None:
    """What a picture shows: its title, or, when its title is only its number, its description's first sentence."""
    title = str(data.get("title") or "").strip()
    if title and not _NUMBERED.match(title):
        return title
    text = str(data.get("description") or "")
    text = text.split("---", 1)[1] if "---" in text else text  # ("iss059e006481 (March 31, 2019) --- Astronauts...")
    sentence = re.split(r"(?<=[.!?])\s", " ".join(text.split()), maxsplit=1)[0]
    return sentence or title or None


def _map_item(item: dict[str, Any]) -> ImageData | None:
    data = (item.get("data") or [{}])[0]
    links = item.get("links") or []
    shown = _rendition(links, _RENDITIONS)
    if data.get("media_type") != "image" or shown is None:
        return None
    people = " ".join(str(data.get(key) or "") for key in ("photographer", "secondary_creator"))
    if _COPYRIGHTED.search(f"{data.get('description') or ''} {people}"):
        return None
    nasa_id = data.get("nasa_id")
    page = PAGE_URL.format(nasa_id) if nasa_id else None
    photographer = str(data.get("photographer") or "").strip()
    author = f"NASA/{photographer}" if photographer and "nasa" not in photographer.lower() else "NASA"
    name, license_url = licenses.PUBLIC_DOMAIN_MARK
    small = _rendition(links, _SMALL) or shown
    return ImageData(
        image_url=shown["href"],
        source=f"{author} (NASA Image and Video Library)",
        source_url=page,
        credit=((author, page), (" (", None), (name, license_url), (", NASA Image and Video Library)", None)),
        description=_description(data),
        display=DISPLAY,
        license_class="public-domain",
        license=name,
        license_url=license_url,
        thumbnail_url=small.get("href"),
        declared_size=image_util.served_size(shown.get("width"), shown.get("height")),
    )


def search_images(query: str, after: int | None = None, before: int | None = None, limit: int = 20) -> list[ImageData]:
    """NASA's pictures for the query, taken after and before some years, if given."""
    if not query or not available():
        return []
    params: dict[str, Any] = {"q": query, "media_type": "image", "page_size": limit}
    if after is not None:
        params["year_start"] = max(after, 1900)
    if before is not None:
        params["year_end"] = before
    data = http_util.search_json(API_URL, _cooldown, params=params, timeout=_TIMEOUT)
    items = ((data or {}).get("collection") or {}).get("items") or []
    images = [image for image in map(_map_item, items) if image]
    if not images:
        logger.info("NASA's library returned no images for '%s'", query)
    return images
