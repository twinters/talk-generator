"""Meme templates from Imgflip (https://imgflip.com/api): the blank pictures that memes caption.

No key is needed to list them: its API gives the 100 templates most captioned lately (each with its picture and its
size), cached for a week (see http_util.CACHE_EXPIRY). talkgenerator captions them itself, with live text over the
picture (see talkgenerator.sources.memes, which knows where each template's captions go), instead of asking Imgflip
to draw the captions into the picture (its caption_image, which needs an account). The pictures are stills of films,
shows and photos: fair use, so a talk whose license policy leaves fair use out has no memes.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.imgflip.com/get_memes"
TEMPLATE_PAGE = "https://imgflip.com/memetemplate/{}"  # (by its ID: Imgflip redirects to its page by name)
# How a browser may show its pictures (see talkgenerator.models.deck.DisplayPolicy): from Imgflip's image server,
# which serves them to any page (checked on 2026-11-07: they load with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its pictures (see talkgenerator.images.licenses): fair use
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"fair-use"})
_TIMEOUT = 10

_cooldown = http_util.Cooldown("Imgflip")


@dataclass(frozen=True)
class Template:
    """A meme template as Imgflip lists it: its ID, its name, its picture and the picture's size, how many captions
    Imgflip's own generator gives it, and how often it was captioned (when Imgflip says)."""

    id: str
    name: str
    url: str
    width: int
    height: int
    box_count: int = 2
    captions: int = 0


def available() -> bool:
    """Whether Imgflip can be searched: it isn't switched off (DISABLE_IMGFLIP). (While it's skipped for a while, see
    _cooldown, a search finds what it found before, from the caches, and the others nothing.)"""
    return not settings.is_source_disabled("IMGFLIP")


def _template(item: dict[str, Any]) -> Template | None:
    try:
        return Template(
            id=str(item["id"]),
            name=str(item["name"]),
            url=str(item["url"]),
            width=int(item["width"]),
            height=int(item["height"]),
            box_count=int(item.get("box_count") or 2),
            captions=int(item.get("captions") or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def templates() -> list[Template]:
    """The templates Imgflip lists now: the 100 most captioned lately (none when it can't be reached)."""
    if not available():
        return []
    data = http_util.search_json(API_URL, _cooldown, timeout=_TIMEOUT)
    if not isinstance(data, dict) or not data.get("success"):
        return []
    found = (data.get("data") or {}).get("memes") or []
    return [template for template in map(_template, found) if template]


def image(template: Template) -> ImageData:
    """A template's picture, credited to Imgflip, where it's a template of."""
    page = TEMPLATE_PAGE.format(template.id)
    return ImageData(
        image_url=template.url,
        source=f"{template.name} (meme template, via Imgflip)",
        source_url=page,
        credit=((template.name, page), (" (meme template, via Imgflip)", None)),
        description=f"the {template.name} meme",
        display=DISPLAY,
        license_class="fair-use",
        thumbnail_url=template.url,
        declared_size=image_util.served_size(template.width, template.height),
    )


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def find(query: str, known: Sequence[Template] = ()) -> list[ImageData]:
    """The template a query names, by its ID or its name ("181913649", "Drake Hotline Bling"), among those Imgflip lists
    now and the known ones (as they were listed once: Imgflip's list changes, and can't always be reached); else the
    ones whose names have every word of the query."""
    wanted = query.strip()
    if not wanted:
        return []
    listed = templates()
    ids = {template.id for template in listed}
    listed += [template for template in known if template.id not in ids]
    exact = [
        template
        for template in listed
        if wanted in (template.id, template.name) or _words(wanted) == _words(template.name)
    ]
    if exact:
        return [image(exact[0])]
    words = set(_words(wanted))
    return [image(template) for template in listed if words and words <= set(_words(template.name))]


def template_id(page: str | None) -> str | None:
    """The ID of the template whose page a credit links to (TEMPLATE_PAGE), if it's one."""
    found = re.fullmatch(r"https://imgflip\.com/memetemplate/(\d+)", page or "")
    return found.group(1) if found else None
