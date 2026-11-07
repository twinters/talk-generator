"""Flags of countries (and of some regions and US states) from flagcdn.com, by Flagpedia (https://flagpedia.net).

No key is needed. Flagpedia's flags are in the public domain ("can be used freely without restriction"), and it
appreciates a link back, which their credits give. A search finds a flag when its query names a country, as its list
of names has it ("Belgium", "the Netherlands", "flag of Japan"), or by a few other names ("Holland", "the USA");
the list is cached for 30 days (see http_util.CACHE_EXPIRY).
"""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
from typing import Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

CODES_URL = "https://flagcdn.com/en/codes.json"
FLAG_URL = "https://flagcdn.com/w{width}/{code}.png"
SITE = "https://flagpedia.net"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from flagcdn.com, whose own docs
# show its flags in <img> tags (checked on 2026-11-07: they load with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses): public domain
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain"})
_WIDTH, _THUMBNAIL_WIDTH = 1280, 320  # (two of its widths: they double from 20 to 2560)
_TIMEOUT = 10
# Other names of countries, and words a query may have around a country's name ("the flag of Japan")
_ALIASES: Final = {
    "usa": "us",
    "us": "us",
    "america": "us",
    "united states of america": "us",
    "uk": "gb",
    "britain": "gb",
    "great britain": "gb",
    "holland": "nl",
    "czech republic": "cz",
    "korea": "kr",
    "republic of korea": "kr",
    "democratic republic of the congo": "cd",
    "burma": "mm",
    "east timor": "tl",
    "macedonia": "mk",
    "cabo verde": "cv",
    "vatican": "va",
    "turkiye": "tr",
    # (and the names talkgenerator's own list of countries gives them: data/text-templates/about_me_facts.json)
    "brunei darussalam": "bn",
    "congo": "cg",
    "kyrgyz republic": "kg",
    "myanmar burma": "mm",
    "republic of macedonia": "mk",
    "russian federation": "ru",
    "saint vincent s and grenadines": "vc",
    "slovak republic": "sk",
    "turks and caicos islands": "tc",
    "virgin islands": "vi",
}
_AROUND: Final = re.compile(r"\b(?:the|national|flags?|of|country)\b")

_cooldown = http_util.Cooldown("flagcdn.com")
_lock = threading.Lock()
_codes: dict[str, str] | None = None  # (code: name, once flagcdn.com has listed them)


def available() -> bool:
    """Whether flags can be searched: they aren't switched off (DISABLE_FLAGS). (While it's skipped for a while, see
    _cooldown, a search finds what it found before, from the caches, and the others nothing.)"""
    return not settings.is_source_disabled("FLAGS")


def _plain(name: str) -> str:
    """A name as names are compared: in small letters, without accents, brackets or words around it."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().replace("&", " and ")
    words = _AROUND.sub(" ", re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()))
    return " ".join(words.split())


def _listed() -> dict[str, str]:
    """flagcdn.com's flags, by code, with their names (none when it can't be reached: asked again next time)."""
    global _codes
    with _lock:
        if _codes is None:
            data = http_util.search_json(CODES_URL, _cooldown, timeout=_TIMEOUT)
            if isinstance(data, dict) and data:
                _codes = {str(code): str(name) for code, name in data.items()}
        return _codes or {}


def _names(listed: dict[str, str]) -> dict[str, str]:
    """The codes by the names a query can give: every flag's name (and the one in its brackets, as in "Côte d'Ivoire
    (Ivory Coast)"), and the aliases; a country's before a US state's of the same name (Georgia)."""
    names: dict[str, str] = {}
    for code, name in sorted(listed.items(), key=lambda entry: entry[0].startswith("us-")):
        for part in [re.sub(r"\(.*?\)", "", name), *re.findall(r"\((.*?)\)", name)]:
            names.setdefault(_plain(part), code)
    for alias, code in _ALIASES.items():
        if code in listed:
            names.setdefault(_plain(alias), code)
    return names


def code(name: str) -> str | None:
    """The code of the flag a name names ("Belgium": "be"), or None."""
    listed = _listed()
    return _names(listed).get(_plain(name)) if listed else None


def search_flags(query: str) -> list[ImageData]:
    """The flag the query names, if it names a country (or a region, or a US state, that has its own)."""
    if not query or not available():
        return []
    listed = _listed()
    found = _names(listed).get(_plain(query)) if listed else None
    if found is None:
        return []
    name = listed[found]
    shown = re.sub(r"\s*\(.*?\)", "", name)
    license_name, license_url = licenses.PUBLIC_DOMAIN_MARK
    return [
        ImageData(
            image_url=FLAG_URL.format(width=_WIDTH, code=found),
            source=f"Flag of {shown} ({license_name}, via Flagpedia)",
            source_url=SITE,
            credit=(
                (f"Flag of {shown}", SITE),
                (" (", None),
                (license_name, license_url),
                (", via Flagpedia)", None),
            ),
            description=f"the flag of {shown}",
            display=DISPLAY,
            license_class="public-domain",
            license=license_name,
            license_url=license_url,
            thumbnail_url=FLAG_URL.format(width=_THUMBNAIL_WIDTH, code=found),
        )
    ]
