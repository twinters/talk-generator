"""What the adapters of the providers' SDKs share: importing an SDK that's an optional extra, reading JSON from an
answer, and turning an SDK's errors into ProviderErrors (without keys in their messages)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from typing import Any, Final

from talkgenerator.llm.base import ProviderError, ProviderUnavailable, RateLimited
from talkgenerator.util.http_util import redact

# How long to wait for a provider: to connect, and between two pieces of a streamed answer
TIMEOUT_SECONDS: Final = 120.0
# Retry rate limits and server errors once: a talk falls back to classic slides rather than keep the audience waiting
MAX_RETRIES: Final = 1


def import_sdk(module: str, extra: str) -> Any:
    """The SDK's module, or ProviderUnavailable telling how to install it."""
    try:
        return importlib.import_module(module)
    except ImportError as error:
        raise ProviderUnavailable(
            f"The {module} package isn't installed; install it with: pip install 'talkgenerator[{extra}]'"
        ) from error


def parse_json(text: str) -> Any:
    """The JSON object in an answer, also when it's wrapped in a code fence or in words, or None."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None


def provider_error(error: Exception, sdk: Any, provider: str) -> ProviderError:
    """The ProviderError for an error of the anthropic or openai SDK (they share these error classes)."""
    message = f"{provider}: {redact(getattr(error, 'message', None) or error)}"
    if isinstance(error, sdk.APIConnectionError):  # timeouts too
        return ProviderUnavailable(f"{provider} can't be reached ({message})")
    if isinstance(error, sdk.APIStatusError):
        status = error.status_code
        if status == 429:
            return RateLimited(message, retry_after=_retry_after(error.response.headers))
        if status in (401, 403):
            return ProviderUnavailable(f"{provider} refused the key ({message})")
        if status == 402:
            return ProviderUnavailable(f"{provider} needs more credits ({message})")
        if status == 404:
            return ProviderUnavailable(f"{provider} doesn't know that model ({message})")
        if status >= 500:
            return ProviderUnavailable(f"{provider} had a problem ({message})")
    return ProviderError(message)


def _retry_after(headers: Mapping[str, str]) -> float | None:
    try:
        return float(headers.get("retry-after", ""))
    except ValueError:
        return None
