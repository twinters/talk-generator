"""Google's Gemini, with your own GEMINI_API_KEY (or GOOGLE_API_KEY), through the Gemini API and Google's google-genai
SDK (pip install 'talkgenerator[gemini]'; D71 in docs/v5-plan.md).

The default model is Gemini 3.8 Flash ("gemini"); "gemini:<model>" names another, such as
"gemini:gemini-3.5-flash-lite" or "gemini:gemini-4-argon". As with Claude, talks take no sampling parameters (the
seeded dice in the prompt bring the variety), structured outputs hold the answer to the talk's JSON schema
(response_json_schema), and the effort sets how hard the Gemini 3 models and later think before they write: their
thinking level, low by default (TALKGENERATOR_LLM_EFFORT: minimal, low, medium or high), which suits short creative
writing. Gemini counts its thinking as output, within the request's output limit, so requests leave room for it.

When Gemini finds a schema too complex to hold an answer to (a 400 that names the schema, before it writes anything),
it gets the schema as text and writes the JSON by itself, as Claude does then. An answer that reaches the model's
limit for one request isn't continued in another (the SDK's automatic continuation is off): it ends truncated, and
broken streams end in an error, as with the other providers.

Gemini's free tier (a key whose Google Cloud project has no billing) costs nothing, within small limits a minute and
a day, but talkgenerator can't tell a key on it from a paid one: talks are priced, budgeted and made Advanced as on
the paid tier (docs/language-models.md says to ask for Basic on the free tier: one request a talk).
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from collections.abc import Callable, Mapping
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.llm import prices
from talkgenerator.llm.base import (
    Capabilities,
    Finish,
    Message,
    ProviderError,
    ProviderUnavailable,
    RateLimited,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.sdk import MAX_RETRIES, SCHEMA_AS_TEXT, TIMEOUT_SECONDS, import_sdk, parse_json
from talkgenerator.util.http_util import redact

logger = logging.getLogger("talkgenerator")

PROVIDER: Final = "gemini"
DEFAULT_MODEL: Final = "gemini-3.8-flash"
DEFAULT_EFFORT: Final = "low"
KEYS_PAGE: Final = "https://aistudio.google.com/apikey"
# The thinking level for each effort TALKGENERATOR_LLM_EFFORT may name (Gemini's own, and the other providers')
_LEVELS: Final = {
    "none": "minimal",
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}
# Room for thinking on top of the answer, by thinking level
_THINKING_TOKENS: Final = {"minimal": 2000, "low": 4000, "medium": 8000, "high": 16000}
# The models a thinking level is sent to: Gemini 3 and later (Gemini 2.5's keep their own default, without thinking
# on 2.5 Flash-Lite)
_THINKING_LEVEL_MODELS: Final = re.compile(r"^gemini-(?:[3-9]|[1-9]\d)")
# The models whose thinking goes no lower than low (aistudio.google.com/docs/thinking, 2026-11-10)
_LOW_AT_LEAST: Final = frozenset({"gemini-4-argon", "gemini-3.8-flash", "gemini-3.1-pro-preview"})
_ROLES: Final = {"user": "user", "assistant": "model"}
# How an answer ended, by its candidate's finish reason: any other (the output limit, the limit of a request, a
# malformed answer) or none, truncated
_FINISH: Final[dict[str, Finish]] = {
    "STOP": "complete",
    "SAFETY": "refused",
    "RECITATION": "refused",
    "LANGUAGE": "refused",
    "BLOCKLIST": "refused",
    "PROHIBITED_CONTENT": "refused",
    "SPII": "refused",
}


class GeminiProvider(TextProvider):
    capabilities = Capabilities(structured_output=True, streaming=True, vision=True)

    def __init__(self, model: str = DEFAULT_MODEL, *, effort: str | None = None, client: Any = None) -> None:
        self.model = model.strip().removeprefix("models/") or DEFAULT_MODEL
        self.effort = (effort or settings.llm_effort() or DEFAULT_EFFORT).lower()
        self.id = f"{PROVIDER}:{self.model}"
        self._client = client

    @property
    def thinking_level(self) -> str | None:
        """The thinking level its requests ask for, or None for a model that takes none (Gemini 2.5's)."""
        if not _THINKING_LEVEL_MODELS.match(self.model):
            return None
        level = _LEVELS.get(self.effort, _LEVELS[DEFAULT_EFFORT])
        return "low" if level == "minimal" and self.model in _LOW_AT_LEAST else level

    def max_output_tokens(self, request: TextRequest) -> int:
        return request.max_output_tokens + _THINKING_TOKENS[self.thinking_level or _LEVELS[DEFAULT_EFFORT]]

    def complete(self, request: TextRequest) -> TextResponse:
        return self.stream(request, lambda text: None)

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        sdk = import_sdk("google.genai", "gemini")
        errors = importlib.import_module("google.genai.errors")
        client = self._client or self._new_client(sdk)
        parts: list[str] = []
        try:
            try:
                return self._answer(client, self.arguments(request), request, on_text, parts)
            except errors.ClientError as error:
                if request.json_schema is None or parts or not _about_the_schema(error):
                    raise
                # Gemini turns a schema down that's too large or too deep for it to hold an answer to (a talk with many
                # kinds of slides can have one) before it writes anything. Then the schema goes along as text, and the
                # model writes the JSON by itself: the talk checks every slide's texts anyway. (Said in the log, as
                # nothing then holds the answer to the schema's shape)
                logger.info("Gemini found the answer's schema too complex: %s gets it as text", self.id)
                return self._answer(client, self.arguments(request, schema_as_text=True), request, on_text, parts)
        except errors.APIError as error:  # also an error in the middle of the stream
            raise _provider_error(error) from error
        except errors.UnknownApiResponseError as error:
            raise ProviderError(f"Gemini: an answer that can't be read ({redact(error)})") from error
        except _transport_errors() as error:  # (the SDK doesn't wrap the HTTP client's errors)
            raise ProviderUnavailable(f"Gemini can't be reached ({redact(error)})") from error

    def arguments(self, request: TextRequest, *, schema_as_text: bool = False) -> dict[str, Any]:
        """The request, as the SDK's generate_content_stream takes it: the answer held to the request's JSON schema,
        or with schema_as_text, that schema written at the end of the last message instead."""
        contents: list[dict[str, Any]] = [
            {"role": _ROLES[message.role], "parts": _parts(message)} for message in request.messages
        ]
        config: dict[str, Any] = {
            "max_output_tokens": self.max_output_tokens(request),
            # (The SDK's own: one request, without functions to call)
            "automatic_continuation": False,
            "automatic_function_calling": {"disable": True},
        }
        if request.system:
            config["system_instruction"] = request.system
        if request.json_schema is not None:
            config["response_mime_type"] = "application/json"
            if schema_as_text:
                schema = json.dumps(request.json_schema, ensure_ascii=False, separators=(",", ":"))
                contents[-1]["parts"][-1]["text"] += f"\n\n{SCHEMA_AS_TEXT}{schema}"
            else:
                config["response_json_schema"] = request.json_schema
        level = self.thinking_level
        if level:
            config["thinking_config"] = {"thinking_level": level}
        return {"model": self.model, "contents": contents, "config": config}

    def _answer(
        self,
        client: Any,
        arguments: dict[str, Any],
        request: TextRequest,
        on_text: Callable[[str], None],
        parts: list[str],
    ) -> TextResponse:
        """Gemini's answer, its text handed to on_text (and kept in parts) as it's written."""
        finish = blocked = usage = answered = None
        chunks = client.models.generate_content_stream(**arguments)
        try:
            for chunk in chunks:
                answered = chunk.model_version or answered
                usage = chunk.usage_metadata or usage  # (the request's total so far)
                blocked = getattr(chunk.prompt_feedback, "block_reason", None) or blocked
                for candidate in (chunk.candidates or ())[:1]:
                    for part in getattr(candidate.content, "parts", None) or ():
                        if part.text and not part.thought:
                            parts.append(part.text)
                            on_text(part.text)
                    finish = _name(candidate.finish_reason) or finish
        finally:
            close = getattr(chunks, "close", None)
            if close is not None:
                close()  # (also when on_text stopped the answer: the connection goes)

        text = "".join(parts)
        ending: Finish = _FINISH.get(finish or "", "truncated")
        if blocked:
            ending = "refused"
        prompt = _count(usage, "prompt_token_count")
        cached = _count(usage, "cached_content_token_count")
        input_tokens = max(prompt - cached, 0)
        # The answer and the thinking before it: both are billed as output
        output_tokens = _count(usage, "candidates_token_count") + _count(usage, "thoughts_token_count")
        model = f"{PROVIDER}:{str(answered or self.model).removeprefix('models/')}"
        # At the price of the model that answered, or else the one asked for (Gemini may name a version of it)
        cost = prices.estimate_cost(model, input_tokens, cached, output_tokens)
        if cost is None:
            cost = prices.estimate_cost(self.id, input_tokens, cached, output_tokens)
        return TextResponse(
            text=text,
            data=parse_json(text) if request.json_schema is not None else None,
            finish=ending,
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached,
            output_tokens=output_tokens,
            cost_usd=cost,
        )

    def _new_client(self, sdk: Any) -> Any:
        key = settings.gemini_api_key()
        if not key:
            raise ProviderUnavailable(f"Gemini needs a key: set GEMINI_API_KEY (one is free at {KEYS_PAGE})")
        self._client = new_client(key, sdk)
        return self._client


def new_client(key: str, sdk: Any = None) -> Any:
    """A client of the SDK's with a key, as talks use it: it waits TIMEOUT_SECONDS for Gemini, and asks once more
    (MAX_RETRIES) when it's rate limited or has a problem (talkgenerator.com makes one with a visitor's key)."""
    sdk = sdk or import_sdk("google.genai", "gemini")
    options = {"timeout": round(TIMEOUT_SECONDS * 1000), "retry_options": {"attempts": MAX_RETRIES + 1}}
    return sdk.Client(api_key=key, http_options=options)


def _parts(message: Message) -> list[dict[str, Any]]:
    """A message's parts, as the Gemini API takes them: the pictures it shows, if any, then its text."""
    pictures = [{"inline_data": {"mime_type": image.media_type, "data": image.data}} for image in message.images]
    return [*pictures, {"text": message.content}]


def _name(value: Any) -> str | None:
    """An enum's name, as the API writes it ("STOP"), or None."""
    return str(getattr(value, "value", value)) if value else None


def _count(usage: Any, field: str) -> int:
    count = getattr(usage, field, None)
    return count if isinstance(count, int) else 0


def _about_the_schema(error: Any) -> bool:
    """Whether Gemini turned a request down for its schema (too many states, too deep, or a part it can't take)."""
    return getattr(error, "code", None) == 400 and "schema" in str(getattr(error, "message", "") or "").lower()


def _provider_error(error: Any) -> ProviderError:
    """The ProviderError for an error of the Gemini API, without keys in its message."""
    code = getattr(error, "code", None) or 0
    said = redact(getattr(error, "message", None) or error)
    message = f"Gemini: {said}"
    if code == 429:
        return RateLimited(message, retry_after=_retry_delay(getattr(error, "details", None)))
    if code in (401, 403) or (code == 400 and "api key" in said.lower()):
        return ProviderUnavailable(f"Gemini refused the key ({message})")
    if code == 404:
        return ProviderUnavailable(f"Gemini doesn't know that model ({message})")
    if code >= 500:
        return ProviderUnavailable(f"Gemini had a problem ({message})")
    if getattr(error, "status", None) == "FAILED_PRECONDITION":
        # (as when the free tier isn't offered where the request comes from)
        return ProviderUnavailable(f"Gemini can't answer this key from here ({message})")
    return ProviderError(message)


def _retry_delay(details: Any) -> float | None:
    """How long Gemini says to wait before asking again (a RetryInfo's retryDelay, such as "37s"), or None."""
    error = details.get("error") if isinstance(details, Mapping) else None
    for entry in (error.get("details") if isinstance(error, Mapping) else None) or ():
        delay = entry.get("retryDelay") if isinstance(entry, Mapping) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                return None
    return None


def _transport_errors() -> tuple[type[Exception], ...]:
    """The errors of the HTTP clients the SDK can use (httpx2, or httpx), when a connection fails or times out."""
    found: list[type[Exception]] = []
    for module in ("httpx2", "httpx"):
        try:
            found.append(importlib.import_module(module).TransportError)
        except (ImportError, AttributeError):
            continue
    return tuple(found)
