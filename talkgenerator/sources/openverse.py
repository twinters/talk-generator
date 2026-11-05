"""Openly licensed photos from Openverse (https://openverse.org).

Openverse is WordPress's search engine for Creative Commons and public domain media, from Flickr,
museums, Wikimedia and more. No key is needed: anonymous use is limited to 20 requests per minute
and 200 per day, which the response cache stretches a long way. Only licenses that allow commercial
use are requested, since decks get shown at (possibly paid) shows.
"""

from __future__ import annotations

import logging
from typing import Any

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.openverse.org/v1/images/"
_MIN_LONG_SIDE = 800  # smaller images look blurry on a slide
_TIMEOUT_SECONDS = 8

_cooldown = http_util.Cooldown("Openverse")


def _license_label(item: dict[str, Any]) -> str:
    code = str(item.get("license") or "").lower()
    if code == "pdm":
        return "public domain"
    if code == "cc0":
        return "CC0"
    return f"CC {code.upper()} {item.get('license_version') or ''}".strip()


def _map_to_image_data(item: dict[str, Any]) -> ImageData | None:
    url = item.get("url")
    if not url:
        return None
    width, height = item.get("width") or 0, item.get("height") or 0
    if width and height and max(width, height) < _MIN_LONG_SIDE:
        return None
    creator = item.get("creator") or "Unknown creator"
    return ImageData(
        image_url=url,
        source=f"{creator} ({_license_label(item)}, via Openverse)",
        source_url=item.get("foreign_landing_url"),
    )


def search_photos(query: str) -> list[ImageData]:
    if not query or settings.is_source_disabled("OPENVERSE") or _cooldown.active:
        return []
    response = http_util.get(
        API_URL,
        params={"q": query, "page_size": 20, "license_type": "commercial", "mature": "false"},
        timeout=_TIMEOUT_SECONDS,
    )
    if response is None:
        # Openverse can be slow; don't let every slide wait for it
        _cooldown.trigger(10 * 60, f"no answer within {_TIMEOUT_SECONDS} seconds")
        return []
    if response.status_code >= 500:
        _cooldown.trigger_outage(response)
        return []
    if response.status_code == 429:
        _cooldown.trigger(15 * 60, "rate limit reached")
        return []
    if response.status_code == 403:
        # Openverse refuses some networks outright (talkgenerator.com's server, for one): asking again won't help
        _cooldown.trigger(60 * 60, "HTTP 403: it refuses requests from this network")
        return []
    if not response.ok:
        logger.warning("Openverse returned HTTP %s", response.status_code)
        return []
    try:
        results = response.json().get("results") or []
    except ValueError:
        return []
    images = [image for image in map(_map_to_image_data, results) if image]
    if not images:
        logger.info("Openverse returned no images for '%s'", query)
    return images
