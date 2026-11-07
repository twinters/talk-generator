"""Openly licensed photos from Openverse (https://openverse.org).

Openverse is WordPress's search engine for Creative Commons and public domain media, from Flickr,
museums, Wikimedia and more. No key is needed: anonymous use is limited to 20 requests per minute
and 200 per day, which the response cache stretches a long way. With the credentials of a registered
app (OPENVERSE_CLIENT_ID and OPENVERSE_CLIENT_SECRET), searches are signed in with an access token,
and get higher limits. Only public domain and open licenses (CC0, the public domain mark, CC BY and CC BY-SA) are
requested: they allow commercial use, since decks get shown at (possibly paid) shows, and adaptations, since a theme
recolours its pictures.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Final

import requests

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import licenses
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

API_URL = "https://api.openverse.org/v1/images/"
# How a browser may show its images (see talkgenerator.models.deck.DisplayPolicy): from the hosts it finds them on
# (Flickr, museums, Wikimedia...), credited as their licenses ask (checked on 2026-11-07: its images load in a browser's <img>, with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its images (see talkgenerator.images.licenses), each its own: public domain or open
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"public-domain", "open"})
# The licenses it's asked for, by class: the ones that allow commercial use and adaptations
_LICENSE_CODES: Final[dict[LicenseClass, tuple[str, ...]]] = {"public-domain": ("cc0", "pdm"), "open": ("by", "by-sa")}
# The filters its search takes (https://api.openverse.org/v1/#tag/images/operation/images_search)
CATEGORIES: Final = ("photograph", "illustration", "digitized_artwork")
ASPECT_RATIOS: Final = {"landscape": "wide", "portrait": "tall", "square": "square"}
TOKEN_URL = "https://api.openverse.org/v1/auth_tokens/token/"
_MIN_LONG_SIDE = 800  # smaller images look blurry on a slide
_TIMEOUT_SECONDS = 8
_TOKEN_RENEWAL_MARGIN_SECONDS = 5 * 60  # get a new access token this long before the current one expires
_DEFAULT_TOKEN_LIFETIME_SECONDS = 60 * 60  # for an access token that doesn't say when it expires

_cooldown = http_util.Cooldown("Openverse")


class _AccessToken:
    """The access token of the registered app, requested once and reused until shortly before it expires.

    It's only kept in memory: it's never logged, and the on-disk response cache leaves out the Authorization
    header. When Openverse doesn't hand out a token (rejected credentials, an outage...), searches go out
    anonymously for a while, as they do without credentials.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._client_id = ""
        self._renew_at = 0.0
        self._next_sign_in = 0.0

    def get(self) -> str | None:
        """An access token, or None without credentials or when signing in failed."""
        credentials = settings.openverse_auth()
        client_id, client_secret = credentials["client_id"], credentials["client_secret"]
        if not (client_id and client_secret):
            return None
        with self._lock:  # one thread signs in, the others wait for its token
            now = time.monotonic()
            if self._token and self._client_id == client_id and now < self._renew_at:
                return self._token
            self._token = None
            if now >= self._next_sign_in:
                self._sign_in(client_id, client_secret)
            return self._token

    def discard(self, token: str) -> None:
        """Openverse rejected the token (it expired early, or was revoked): sign in again for the next search."""
        with self._lock:
            if self._token == token:
                self._token = None

    def _sign_in(self, client_id: str, client_secret: str) -> None:
        response = http_util.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            timeout=_TIMEOUT_SECONDS,
        )
        token = _parse_token(response)
        if token is None:
            seconds, reason = _sign_in_failure(response)
            self._next_sign_in = time.monotonic() + seconds
            logger.warning(
                "Can't sign in to Openverse (%s); searching it anonymously for the next %d minutes.",
                reason,
                round(seconds / 60),
            )
            return
        self._token, lifetime = token
        self._client_id = client_id
        self._renew_at = time.monotonic() + lifetime - min(_TOKEN_RENEWAL_MARGIN_SECONDS, lifetime / 2)
        logger.info(
            "Signed in to Openverse as a registered app; the access token lasts %d minutes.", round(lifetime / 60)
        )


def _parse_token(response: requests.Response | None) -> tuple[str, float] | None:
    """The access token and its lifetime in seconds, from Openverse's answer to signing in."""
    if response is None or not response.ok:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    token = body.get("access_token") if isinstance(body, dict) else None
    if not token or not isinstance(token, str):
        return None
    lifetime = body.get("expires_in")
    if not isinstance(lifetime, int | float) or lifetime <= 0:
        lifetime = _DEFAULT_TOKEN_LIFETIME_SECONDS
    return token, float(lifetime)


def _sign_in_failure(response: requests.Response | None) -> tuple[float, str]:
    """How long to search anonymously after signing in failed, and why it failed."""
    if response is None:
        return 10 * 60, f"no answer within {_TIMEOUT_SECONDS} seconds"
    if response.status_code == 401:
        return 60 * 60, "HTTP 401: the OPENVERSE_CLIENT_ID and OPENVERSE_CLIENT_SECRET were rejected"
    if response.status_code == 429:
        return 15 * 60, "rate limit reached"
    if response.status_code >= 500:
        return http_util.OUTAGE_COOLDOWN_SECONDS, f"HTTP {response.status_code}"
    if not response.ok:
        return 60 * 60, f"HTTP {response.status_code}"
    return 60 * 60, "its answer has no access token"


_access_token = _AccessToken()


def available() -> bool:
    """Whether a search can go out now: Openverse isn't switched off, nor skipped for a while (see _cooldown)."""
    return not settings.is_source_disabled("OPENVERSE") and not _cooldown.active


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
    found = licenses.creative_commons(str(item.get("license") or ""), item.get("license_version"))
    if found is None:  # a license that isn't public domain or open (it wasn't asked for)
        return None
    license_class, license_name, license_url = found
    label = _license_label(item)
    creator = item.get("creator") or "Unknown creator"
    return ImageData(
        image_url=url,
        source=f"{creator} ({label}, via Openverse)",
        source_url=item.get("foreign_landing_url"),
        # The credit Creative Commons licenses ask for: who made it (linking its page), and the license (its deed)
        credit=(
            (creator, item.get("foreign_landing_url")),
            (" (", None),
            (label, item.get("license_url") or license_url),
            (", via Openverse)", None),
        ),
        description=item.get("title"),
        display=DISPLAY,
        license_class=license_class,
        license=label if license_class == "open" else license_name,
        license_url=item.get("license_url") or license_url,
        thumbnail_url=item.get("thumbnail"),
        declared_size=image_util.served_size(width, height),
    )


def search_photos(
    query: str,
    classes: frozenset[LicenseClass] | None = None,
    category: str | None = None,
    orientation: str | None = None,
    sources: str | None = None,
) -> list[ImageData]:
    """Openly licensed images for the query: of the license classes (public domain and open, without any), of a
    category (one of CATEGORIES), an orientation (landscape, portrait or square), and from some of Openverse's
    sources (separated by commas, such as "met,clevelandmuseum"), if given."""
    if not query or settings.is_source_disabled("OPENVERSE") or _cooldown.active:
        return []
    codes = [code for license_class in sorted(classes or LICENSES) for code in _LICENSE_CODES.get(license_class, ())]
    if not codes:
        return []
    params: dict[str, Any] = {"q": query, "page_size": 20, "license": ",".join(codes), "mature": "false"}
    if category in CATEGORIES:
        params["category"] = category
    if orientation in ASPECT_RATIOS:
        params["aspect_ratio"] = ASPECT_RATIOS[orientation]
    if sources:
        params["source"] = sources
    token = _access_token.get()
    response = http_util.get(
        API_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"} if token else {},
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
    if response.status_code == 401 and token:
        logger.warning("Openverse rejected its access token (HTTP 401); signing in again for the next search.")
        _access_token.discard(token)
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
