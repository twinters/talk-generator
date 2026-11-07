"""What the image generators' adapters share: their requests (through talkgenerator.util.http_util, or a client of
the caller's own, such as a test's fake), and their providers' answers turned into pictures or GenerationErrors,
without keys in the errors' messages."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Mapping
from typing import Any, Final, Protocol

from talkgenerator.images.generators.base import (
    GenerationError,
    GenerationRateLimited,
    GenerationRefused,
    GeneratorUnavailable,
)
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

# How long a picture may take: they take seconds to tens of seconds, and a server under load longer
TIMEOUT_SECONDS: Final = 120.0
# What a provider's error says when its moderation turned the prompt (or the picture) down
_MODERATED: Final = ("moderation", "moderated", "safety", "content policy", "content_policy", "prohibited", "nsfw")
# The bytes a picture's file starts with, by its type
_SIGNATURES: Final = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


class Response(Protocol):
    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...

    @property
    def content(self) -> bytes: ...

    @property
    def ok(self) -> bool: ...

    def json(self) -> Any: ...


class Client(Protocol):
    """What an adapter sends its requests with: talkgenerator's own requests (see http_util), or a fake."""

    def post(self, url: str, *, json: Any, headers: Mapping[str, str], timeout: float) -> Response | None: ...

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> Response | None: ...


class _Web:
    """talkgenerator's own requests, with its User-Agent, logs without keys, and nothing cached."""

    def post(self, url: str, *, json: Any, headers: Mapping[str, str], timeout: float) -> Response | None:
        return http_util.post(url, json=json, headers=dict(headers), timeout=timeout)

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> Response | None:
        return http_util.get(url, headers=dict(headers), timeout=timeout)


WEB: Final[Client] = _Web()


def answer(response: Response | None, provider: str) -> Any:
    """The JSON of a provider's answer, or the GenerationError it stands for: no answer, a rate limit, a key or
    credits it turns down, a model it doesn't know, a prompt its moderation turned down, a server error."""
    if response is None:
        raise GeneratorUnavailable(f"{provider} can't be reached")
    if not response.ok:
        raise error(response, provider)
    try:
        return response.json()
    except ValueError as failure:
        raise GenerationError(f"{provider} didn't answer with JSON") from failure


def error(response: Response, provider: str) -> GenerationError:
    status = response.status_code
    said = message(response)
    told = f"{provider}: HTTP {status}" + (f" ({said})" if said else "")
    if status == 429 and any(word in said.lower() for word in ("quota", "credit", "billing")):
        # (OpenAI answers an account without credits with a 429 too, which waiting doesn't help)
        return GeneratorUnavailable(f"{provider} needs more credits ({told})")
    if status == 429:
        return GenerationRateLimited(told, retry_after=_retry_after(response.headers))
    if status in (401, 403) and not moderated(said):
        return GeneratorUnavailable(f"{provider} refused the key ({told})")
    if status == 402:
        return GeneratorUnavailable(f"{provider} needs more credits ({told})")
    if status == 404:
        return GeneratorUnavailable(f"{provider} doesn't know that model ({told})")
    if status >= 500:
        return GeneratorUnavailable(f"{provider} had a problem ({told})")
    if moderated(said):
        return GenerationRefused(f"{provider}'s moderation turned it down ({told})", (f"{provider}: moderated",))
    return GenerationError(told)


def message(response: Response) -> str:
    """What an error answer says (its error's message and code, if it has them), without keys, in a line."""
    try:
        data = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        found = data.get("error", data.get("detail", data))
        if isinstance(found, dict):
            parts = [str(found.get(key)) for key in ("code", "type", "message") if found.get(key)]
            text = ": ".join(parts) if parts else json.dumps(found)
        else:
            text = json.dumps(found) if not isinstance(found, str) else found
    else:
        text = response.content[:300].decode("utf-8", "replace")
    return http_util.redact(" ".join(text.split()))[:300]


def moderated(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _MODERATED)


def _retry_after(headers: Mapping[str, str]) -> float | None:
    try:
        return float(headers.get("retry-after", "") or headers.get("Retry-After", ""))
    except ValueError:
        return None


def decoded(data: Any, provider: str) -> bytes:
    """A picture's bytes from its base64 (as a data URL too)."""
    if not isinstance(data, str) or not data:
        raise GenerationError(f"{provider} answered without a picture")
    if data.startswith("data:"):
        data = data.partition(",")[2]
    try:
        return base64.b64decode(data, validate=False)
    except (binascii.Error, ValueError) as failure:
        raise GenerationError(f"{provider} answered with a picture that isn't base64") from failure


def media_type(data: bytes, said: str | None = None) -> str:
    """The type of a picture's bytes: what they start with, or else what the provider said."""
    for signature, kind in _SIGNATURES.items():
        if data.startswith(signature):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return said or "application/octet-stream"


def download(client: Client, url: str, provider: str, headers: Mapping[str, str] | None = None) -> bytes:
    """The picture at a provider's link (BFL's, which works for ten minutes)."""
    response = client.get(url, headers=dict(headers or {}), timeout=TIMEOUT_SECONDS)
    if response is None or not response.ok:
        status = f"HTTP {response.status_code}" if response is not None else "no answer"
        raise GenerationError(f"{provider}'s picture couldn't be downloaded ({status})")
    return response.content
