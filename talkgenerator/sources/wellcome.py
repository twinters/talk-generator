"""Images of the Wellcome Collection (https://developers.wellcomecollection.org/): medicine, science and odd history.

No key is needed. Every image has its own license: only the public domain ones (the public domain mark, CC0) and CC BY
are asked for, which allow commercial use and adaptations (its NC and in-copyright images don't). Its images come from
a IIIF image server, in any size. Its search takes a range of years, which the looks ask for as after and before (see
talkgenerator.images.catalog).
"""

from __future__ import annotations

import logging
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.wellcomecollection.org/catalogue/v2/images"
WORK_URL = "https://wellcomecollection.org/works/{}"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from its IIIF image server, which
# serves them to any page (checked on 2026-11-07: they load with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses), each its own: public domain or CC BY
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain", "open"})
# Its licenses that are asked for, by class, as its API names them, and as talkgenerator.images.licenses does
_LICENSE_CODES: Final[dict[LicenseClass, tuple[str, ...]]] = {"public-domain": ("cc-0", "pdm"), "open": ("cc-by",)}
_CODES: Final = {"cc-0": "cc0", "pdm": "pdm", "cc-by": "by"}
_IMAGE_SIZE = 1600  # the longest side asked of its image server
_THUMBNAIL_WIDTH = 400  # (one of the sizes it keeps ready)
_TIMEOUT = 10

_cooldown = http_util.Cooldown("Wellcome Collection")


def available() -> bool:
    """Whether the Wellcome Collection can be searched: it isn't switched off (DISABLE_WELLCOME). (While it's skipped
    for a while, see _cooldown, a search finds what it found before, from the caches, and the others nothing.)"""
    return not settings.is_source_disabled("WELLCOME")


def _iiif(info_url: str, size: str) -> str:
    """The address of an image of the IIIF image server, from its info.json's, at a size ("!1600,1600", "400,")."""
    return info_url.removesuffix("/info.json") + f"/full/{size}/0/default.jpg"


def _served_size(aspect_ratio: Any) -> tuple[int, int] | None:
    """The size it's served at, by its aspect ratio (width over height): its longest side at _IMAGE_SIZE."""
    if not isinstance(aspect_ratio, int | float) or aspect_ratio <= 0:
        return None
    if aspect_ratio >= 1:
        return _IMAGE_SIZE, max(1, round(_IMAGE_SIZE / aspect_ratio))
    return max(1, round(_IMAGE_SIZE * aspect_ratio)), _IMAGE_SIZE


def _map_image(item: dict[str, Any]) -> ImageData | None:
    location = next(
        (place for place in item.get("locations") or [] if (place.get("locationType") or {}).get("id") == "iiif-image"),
        None,
    )
    if location is None or not location.get("url"):
        return None
    code = str((location.get("license") or {}).get("id") or "")
    found = licenses.creative_commons(_CODES[code]) if code in _CODES else None
    if found is None:  # (a license that wasn't asked for)
        return None
    license_class, license_name, license_url = found
    work = item.get("source") or {}
    contributors = [str((one.get("agent") or {}).get("label") or "") for one in work.get("contributors") or []]
    author = location.get("credit") or next((name for name in contributors if name), "") or "Wellcome Collection"
    page = WORK_URL.format(work["id"]) if work.get("id") else None
    tail = ", Wellcome Collection)" if "wellcome" not in author.lower() else ")"
    return ImageData(
        image_url=_iiif(location["url"], f"!{_IMAGE_SIZE},{_IMAGE_SIZE}"),
        source=f"{author} ({license_name}{tail}",
        source_url=page,
        credit=((author, page), (" (", None), (license_name, license_url), (tail, None)),
        description=work.get("title") or None,
        display=DISPLAY,
        license_class=license_class,
        license=license_name,
        license_url=license_url,
        thumbnail_url=_iiif(location["url"], f"{_THUMBNAIL_WIDTH},"),
        declared_size=_served_size(item.get("aspectRatio")),
    )


def search_images(
    query: str,
    classes: frozenset[LicenseClass] | None = None,
    after: int | None = None,
    before: int | None = None,
    limit: int = 20,
) -> list[ImageData]:
    """Images for the query: of the license classes (public domain and open, without any), made after and before
    some years, if given."""
    if not query or not available():
        return []
    codes = [code for license_class in sorted(classes or LICENSES) for code in _LICENSE_CODES.get(license_class, ())]
    if not codes:
        return []
    params: dict[str, Any] = {
        "query": query,
        "pageSize": limit,
        "locations.license": ",".join(codes),
        "include": "source.contributors",
    }
    if after is not None:
        params["source.production.dates.from"] = f"{max(after, 0):04d}-01-01"
    if before is not None:
        params["source.production.dates.to"] = f"{max(before, 0):04d}-12-31"
    data = http_util.search_json(API_URL, _cooldown, params=params, timeout=_TIMEOUT)
    images = [image for image in map(_map_image, (data or {}).get("results") or []) if image]
    if not images:
        logger.info("The Wellcome Collection returned no images for '%s'", query)
    return images
