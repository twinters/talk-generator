"""Shared HTTP plumbing for all content sources.

Every outgoing request goes through here, so they all get a descriptive User-Agent,
a timeout (no more hanging forever on a dead host), a couple of retries on flaky 5xx
responses, and log lines that never contain API keys.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from talkgenerator import __version__

logger = logging.getLogger("talkgenerator")

USER_AGENT = f"talkgenerator/{__version__} (+https://github.com/twinters/talk-generator)"
DEFAULT_TIMEOUT = 10  # seconds

_SECRET_PARAMS = re.compile(r"((?:key|client_id|api_key|token|access_token)=)[^&\s'\"]+", re.IGNORECASE)
_thread_local = threading.local()


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
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers["User-Agent"] = USER_AGENT
        _thread_local.session = session
    return session


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
