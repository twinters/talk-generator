"""Shared HTTP plumbing for all content sources.

Every outgoing request goes through here, so they all get a descriptive User-Agent,
a timeout (no more hanging forever on a dead host), a couple of retries on flaky 5xx
responses, and log lines that never contain API keys.

Responses of the search APIs are also cached on disk (see `CACHE_EXPIRY`): repeated topics
generate faster, rate limits last longer, and Pixabay asks API users to cache for 24 hours.
Images and HTML pages aren't cached. Set DISABLE_CACHE=1 to switch the cache off, or
TALKGENERATOR_CACHE_DIR to choose where it lives.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from talkgenerator import __version__, settings

logger = logging.getLogger("talkgenerator")

USER_AGENT = f"talkgenerator/{__version__} (+https://github.com/twinters/talk-generator)"
DEFAULT_TIMEOUT = 10  # seconds

# How long successful responses are reused, per URL prefix. Anything else is never cached.
CACHE_EXPIRY = {
    "api.datamuse.com": timedelta(days=30),
    "pixabay.com/api": timedelta(hours=24),  # Pixabay's API terms ask to cache requests for 24 hours
    "api.pexels.com": timedelta(hours=24),
    "api.unsplash.com/search": timedelta(hours=24),
}
_CONCEPTNET_CACHE_EXPIRY = timedelta(days=30)
CACHE_FILE_NAME = "http_cache.sqlite"

# Kept out of the cache keys and redacted from what's stored on disk
_CACHE_IGNORED_PARAMETERS = (
    "Authorization",
    "Proxy-Authorization",
    "X-API-Key",
    "access_token",
    "api_key",
    "client_id",
    "key",
)

_SECRET_PARAMS = re.compile(r"((?:key|client_id|api_key|token|access_token)=)[^&\s'\"]+", re.IGNORECASE)
_thread_local = threading.local()
_cache_lock = threading.Lock()
_cache_backend: requests_cache.SQLiteCache | None = None
_cache_unavailable = False


def _cache_expiry_patterns() -> dict[str, timedelta]:
    conceptnet = urlsplit(settings.conceptnet_api_url())
    return {**CACHE_EXPIRY, conceptnet.netloc + conceptnet.path: _CONCEPTNET_CACHE_EXPIRY}


def _get_cache_backend() -> requests_cache.SQLiteCache | None:
    """The on-disk cache shared by all threads, or None if it's disabled or can't be used."""
    global _cache_backend, _cache_unavailable
    if settings.is_source_disabled("CACHE"):
        return None
    with _cache_lock:
        if _cache_backend is None and not _cache_unavailable:
            cache_dir = Path(settings.cache_dir())
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                backend = requests_cache.SQLiteCache(cache_dir / CACHE_FILE_NAME, wal=True)
                backend.delete(expired=True, vacuum=False)
                _cache_backend = backend
                logger.debug("Caching API responses in %s", cache_dir / CACHE_FILE_NAME)
            except Exception as e:
                _cache_unavailable = True
                logger.warning("Not caching API responses: can't use a cache in %s (%s)", cache_dir, e)
        return _cache_backend


def get_session() -> requests.Session:
    """One session per thread: requests sessions aren't guaranteed to be thread-safe."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        cache_backend = _get_cache_backend()
        if cache_backend is not None:
            session = requests_cache.CachedSession(
                backend=cache_backend,
                expire_after=requests_cache.DO_NOT_CACHE,
                urls_expire_after=_cache_expiry_patterns(),
                allowable_codes=(200,),
                allowable_methods=("GET",),
                ignored_parameters=_CACHE_IGNORED_PARAMETERS,
            )
        else:
            session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers["User-Agent"] = USER_AGENT
        _thread_local.session = session
    return session


def reset_sessions() -> None:
    """Forget the sessions and cache, so they're rebuilt with the current settings."""
    global _thread_local, _cache_backend, _cache_unavailable
    with _cache_lock:
        _thread_local = threading.local()
        _cache_backend = None
        _cache_unavailable = False


def redact(text: str) -> str:
    """Remove API keys and tokens from URLs and error messages before logging them."""
    return _SECRET_PARAMS.sub(r"\1REDACTED", str(text))


def describe_url(url: str) -> str:
    """URL without its query string, safe for logs."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def with_query_params(url: str, **params: Any) -> str:
    """Add or replace query parameters on a URL."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in params.items()})
    return urlunsplit(parts._replace(query=urlencode(query)))


def get(url: str, *, timeout: float = DEFAULT_TIMEOUT, **kwargs: Any) -> requests.Response | None:
    """GET a URL. Returns None instead of raising on connection errors and timeouts."""
    try:
        return get_session().get(url, timeout=timeout, **kwargs)
    except requests.RequestException as e:
        logger.warning("Request to %s failed: %s", describe_url(url), redact(e))
        return None


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any | None:
    """GET a URL and decode its JSON body. Returns None on any failure."""
    response = get(url, params=params, headers=headers, timeout=timeout)
    if response is None:
        return None
    if not response.ok:
        logger.warning("%s returned HTTP %s", describe_url(url), response.status_code)
        return None
    try:
        return response.json()
    except ValueError:
        logger.warning("%s did not return valid JSON", describe_url(url))
        return None


class Cooldown:
    """Remembers that a service is unavailable (down, rate limited, bad key) for a while,
    so we stop hammering it and fall through to other sources straight away."""

    def __init__(self, name: str):
        self._name = name
        self._until = 0.0
        self._lock = threading.Lock()

    @property
    def active(self) -> bool:
        return time.monotonic() < self._until

    def trigger(self, seconds: float, reason: str) -> None:
        with self._lock:
            already_active = self.active
            self._until = max(self._until, time.monotonic() + seconds)
        if not already_active:
            logger.warning(
                "%s unavailable (%s); skipping it for the next %d minutes.",
                self._name,
                reason,
                round(seconds / 60),
            )
