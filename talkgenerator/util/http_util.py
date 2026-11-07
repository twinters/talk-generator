"""Shared HTTP plumbing for all content sources.

Every outgoing request goes through here, so they all get a descriptive User-Agent,
a timeout (no more hanging forever on a dead host), a couple of retries on flaky 5xx
responses, and log lines that never contain API keys.

Responses of the search APIs are also cached on disk (see `CACHE_EXPIRY`): repeated topics
generate faster, rate limits last longer, and Pixabay asks API users to cache for 24 hours.
GIPHY's aren't, as its API rules forbid caching them, and neither are images and HTML pages.
Set DISABLE_CACHE=1 to switch the cache off, or TALKGENERATOR_CACHE_DIR to choose where it lives.
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
from requests_cache.policy.expiration import ExpirationPatterns
from urllib3.util.retry import Retry

from talkgenerator import __version__, settings

logger = logging.getLogger("talkgenerator")

USER_AGENT = f"talkgenerator/{__version__} (+https://github.com/twinters/talk-generator)"
DEFAULT_TIMEOUT = 10  # seconds
OUTAGE_COOLDOWN_SECONDS = 5 * 60

# How long successful responses are reused, per URL prefix. Anything else is never cached, such as GIPHY's
# searches: "Do not cache API responses or media URLs" (https://developers.giphy.com/docs/api).
CACHE_EXPIRY: ExpirationPatterns = {
    "api.datamuse.com": timedelta(days=30),
    "pixabay.com/api": timedelta(hours=24),  # Pixabay's API terms ask to cache requests for 24 hours
    "api.pexels.com": timedelta(hours=24),
    "api.unsplash.com/search": timedelta(hours=24),
    "api.openverse.org/v1/images": timedelta(hours=24),
    "commons.wikimedia.org/w/api.php": timedelta(days=7),
    "api.artic.edu/api/v1": timedelta(days=30),
    "en.wikiquote.org/w/api.php": timedelta(days=30),
    # (the museums' and archives' collections change slowly; NASA's library gets new pictures every week)
    "collectionapi.metmuseum.org/public/collection": timedelta(days=30),
    "openaccess-api.clevelandart.org/api": timedelta(days=30),
    "api.wellcomecollection.org/catalogue": timedelta(days=30),
    "api.si.edu/openaccess": timedelta(days=30),
    "images-api.nasa.gov/search": timedelta(days=7),
    "flagcdn.com/en/codes.json": timedelta(days=30),
    "api.imgflip.com/get_memes": timedelta(days=7),
}

# Extra headers some hosts ask for. The Art Institute of Chicago wants API clients to identify
# themselves in AIC-User-Agent, and refuses image requests without it.
_HOST_HEADERS = {
    "artic.edu": {"AIC-User-Agent": USER_AGENT},
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
    "client_secret",
    "key",
)

_SECRET_PARAMS = re.compile(
    r"((?:key|client_id|client_secret|api_key|token|access_token|id_token_hint)=)[^&\s'\"]+", re.IGNORECASE
)
# The keys of language model providers wherever they show up (sk-or-v1-... at OpenRouter, sk-ant-... at Anthropic,
# sk-... and sk-proj-... at OpenAI), bearer tokens, and JSON Web Tokens (a sign-in's, such as Sign in with ChatGPT's)
_SECRET_TOKENS = re.compile(
    r"\bsk-[A-Za-z0-9_\-]{16,}|(?<=Bearer )[A-Za-z0-9._~+/\-]{16,}=*|\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*",
    re.IGNORECASE,
)
_thread_local = threading.local()
_cache_lock = threading.Lock()
_cache_backend: requests_cache.SQLiteCache | None = None
_cache_unavailable = False


def _cache_expiry_patterns() -> ExpirationPatterns:
    conceptnet = urlsplit(settings.conceptnet_api_url())
    patterns: ExpirationPatterns = dict(CACHE_EXPIRY)
    patterns[conceptnet.netloc + conceptnet.path] = _CONCEPTNET_CACHE_EXPIRY
    return patterns


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


def redact(text: object) -> str:
    """Remove API keys and tokens from URLs and error messages before logging them."""
    return _SECRET_TOKENS.sub("REDACTED", _SECRET_PARAMS.sub(r"\1REDACTED", str(text)))


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


def _host_headers(url: str) -> dict[str, str]:
    host = urlsplit(url).hostname or ""
    headers: dict[str, str] = {}
    for domain, extra_headers in _HOST_HEADERS.items():
        if host == domain or host.endswith("." + domain):
            headers.update(extra_headers)
    return headers


def get(url: str, *, timeout: float = DEFAULT_TIMEOUT, **kwargs: Any) -> requests.Response | None:
    """GET a URL. Returns None instead of raising on connection errors and timeouts."""
    return _request("GET", url, timeout=timeout, **kwargs)


def post(url: str, *, timeout: float = DEFAULT_TIMEOUT, **kwargs: Any) -> requests.Response | None:
    """POST to a URL, like get. POSTs are never cached, and aren't retried after server errors or timeouts."""
    return _request("POST", url, timeout=timeout, **kwargs)


def _request(method: str, url: str, *, timeout: float, **kwargs: Any) -> requests.Response | None:
    extra_headers = _host_headers(url)
    if extra_headers:
        kwargs["headers"] = {**extra_headers, **(kwargs.get("headers") or {})}
    try:
        return get_session().request(method, url, timeout=timeout, **kwargs)
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


def search_json(
    url: str,
    cooldown: Cooldown,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    missing_ok: bool = False,
) -> Any | None:
    """GET a search API's JSON answer, keeping a service that can't answer now out for a while (its cooldown): no
    answer or a server error (5 minutes), a rate limit (15 minutes, or as long as it asks), a refusal (an hour: a
    rejected key, or a network it won't serve). None on any failure, and while the cooldown lasts. With missing_ok,
    a 404 is an answer too (nothing there), not worth a warning."""
    if cooldown.active:
        return None
    response = get(url, params=params, headers=headers, timeout=timeout)
    if response is None or response.status_code >= 500:
        cooldown.trigger_outage(response)
        return None
    if response.status_code == 429:
        cooldown.trigger(max(15 * 60, _retry_after(response)), "rate limit reached")
        return None
    if response.status_code in (401, 403):
        cooldown.trigger(60 * 60, f"HTTP {response.status_code}: it refuses these requests")
        return None
    if not response.ok:
        if not (missing_ok and response.status_code == 404):
            logger.warning("%s returned HTTP %s", describe_url(url), response.status_code)
        return None
    try:
        return response.json()
    except ValueError:  # (a challenge page, say, instead of an answer)
        cooldown.trigger(60 * 60, "its answer isn't JSON")
        return None


def _retry_after(response: requests.Response) -> float:
    """The seconds a rate limited answer asks to wait (Retry-After), if it says."""
    try:
        return float(response.headers.get("Retry-After", 0))
    except (TypeError, ValueError):
        return 0.0


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

    def trigger_outage(self, response: requests.Response | None) -> None:
        """The service didn't answer (even after retries) or had a server error. Every request would wait
        for its timeouts and retries again, so skip the service for a while and let other sources fill in."""
        reason = "no answer" if response is None else f"HTTP {response.status_code}"
        self.trigger(OUTAGE_COOLDOWN_SECONDS, reason)
