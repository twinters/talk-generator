"""OpenRouter: many models behind one key, free ones among them (docs/v5-plan.md, section 5.5), through its
OpenAI-compatible Chat Completions API and the openai SDK (pip install 'talkgenerator[openai]').

Without a model, OpenRouter's free router (openrouter/free) picks one of the free models: they cost nothing, with
20 requests a minute and 50 a day (1,000 once the account has bought $10 of credits). Models after the first are
fallbacks, tried in order when the one before fails (rate limited, down, or flagged by moderation). A request is
billed at the price of the model that answered it, so only `:free` models are sure to cost nothing; the answer says
what it cost, and the talk's ledger keeps that.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.llm.base import (
    Capabilities,
    Finish,
    ProviderError,
    ProviderUnavailable,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.sdk import MAX_RETRIES, TIMEOUT_SECONDS, import_sdk, parse_json, provider_error

API_URL: Final = "https://openrouter.ai/api/v1"
DEFAULT_MODEL: Final = "openrouter/free"
# How hard the free router's models think before they write. Measured on 2026-11-06 with 10-slide talks: thinking
# as much as they liked, they took about two minutes and could run out of room; at minimal effort, 50 to 160
# seconds; without thinking, 10 to 15 seconds, and they wrote as well. A model that has to think turns "none" down,
# and then gets the request again at minimal effort. Models named in the spec only get an effort when
# TALKGENERATOR_LLM_EFFORT sets one: a model that can't reason at all would turn the request down.
DEFAULT_EFFORT: Final = "none"
_LEAST_EFFORT: Final = "minimal"
# Which app sends the requests, for the key owner's activity page and OpenRouter's app rankings
APP_HEADERS: Final = {
    "HTTP-Referer": "https://github.com/twinters/talk-generator",
    "X-OpenRouter-Title": "talkgenerator",
}
# Most free models think before they write, which counts as output: room for that on top of the answer
_THINKING_TOKENS: Final = 8000
_FINISH: Final[dict[str, Finish]] = {"stop": "complete", "length": "truncated", "content_filter": "refused"}

logger = logging.getLogger("talkgenerator")


class _ThinkingRequired(ProviderError):
    """The model can't write without thinking first ("Reasoning is mandatory for this endpoint")."""


class _NoAnswer(ProviderError):
    """The model's provider failed before the model wrote anything (it timed out, say): asked again, the router may
    send the request to another model, or the provider may be back."""


class OpenRouterProvider(TextProvider):
    """A model at OpenRouter, with fallbacks: `models` in the order to try them."""

    capabilities = Capabilities(structured_output=True, streaming=True)

    def __init__(self, models: Sequence[str] = (), *, effort: str | None = None, client: Any = None) -> None:
        self.models = tuple(model.strip() for model in models if model.strip()) or (DEFAULT_MODEL,)
        self.id = f"openrouter:{self.models[0]}"
        self.effort = effort  # (None: TALKGENERATOR_LLM_EFFORT's, or for the free router, DEFAULT_EFFORT)
        self._client = client

    def possible_models(self) -> tuple[str, ...]:
        return tuple(f"openrouter:{model}" for model in self.models)

    def max_output_tokens(self, request: TextRequest) -> int:
        return request.max_output_tokens + _THINKING_TOKENS

    def complete(self, request: TextRequest) -> TextResponse:
        return self.stream(request, lambda text: None)

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        sdk = import_sdk("openai", "openai")
        client = self._client or self._new_client(sdk)
        arguments = self.arguments(request)
        asked_again = False
        while True:
            try:
                return self._stream(client, sdk, request, arguments, on_text)
            except _ThinkingRequired:
                # The model that answered has to think: it may think as little as it can (this happens only once, as
                # the request then asks for some thinking)
                arguments["extra_body"]["reasoning"] = {"effort": _LEAST_EFFORT}
            except _NoAnswer as error:
                if asked_again:
                    raise ProviderUnavailable(str(error)) from error
                # (A talk without the model is classic: one more try is worth the wait, as in the benchmark, where
                # "Provider timed out after 11796ms" turned one talk in thirty classic)
                logger.info("%s: asking once more", error)
                asked_again = True

    def _stream(
        self, client: Any, sdk: Any, request: TextRequest, arguments: dict[str, Any], on_text: Callable[[str], None]
    ) -> TextResponse:
        parts: list[str] = []
        model = finish = usage = None
        try:
            for chunk in client.chat.completions.create(**arguments):
                model = chunk.model or model
                usage = chunk.usage or usage
                for choice in chunk.choices:
                    if choice.delta.content:
                        parts.append(choice.delta.content)
                        on_text(choice.delta.content)
                    finish = choice.finish_reason or finish
        except sdk.OpenAIError as error:  # also an error in the middle of the stream
            no_thinking = arguments.get("extra_body", {}).get("reasoning") == {"effort": "none"}
            if no_thinking and not parts and "reasoning is mandatory" in str(error).lower():
                raise _ThinkingRequired(str(error)) from error
            if not parts and _provider_failed(error, sdk):
                raise _NoAnswer(str(provider_error(error, sdk, "OpenRouter"))) from error
            raise provider_error(error, sdk, "OpenRouter") from error
        if finish == "error":
            raise ProviderError("OpenRouter: the model broke off its answer with an error")

        text = "".join(parts)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        cached_tokens = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        cost = getattr(usage, "cost", None)  # OpenRouter's own field: what the request cost, in dollars
        # Without a reason to finish, the stream broke off
        ending: Finish = _FINISH.get(finish, "complete") if finish else "truncated"
        return TextResponse(
            text=text,
            data=parse_json(text) if request.json_schema is not None else None,
            finish=ending,
            model=f"openrouter:{model or self.models[0]}",
            input_tokens=max(prompt_tokens - cached_tokens, 0),
            cached_input_tokens=cached_tokens,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=float(cost) if isinstance(cost, int | float) else None,
        )

    def arguments(self, request: TextRequest) -> dict[str, Any]:
        """The request, as OpenRouter's Chat Completions API takes it (a message that shows pictures as parts: its
        pictures, then its text)."""
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}] if request.system else []
        for message in request.messages:
            content: Any = message.content
            if message.images:
                content = [
                    *({"type": "image_url", "image_url": {"url": image.data_url()}} for image in message.images),
                    {"type": "text", "text": message.content},
                ]
            messages.append({"role": message.role, "content": content})
        arguments: dict[str, Any] = {
            "model": self.models[0],
            "messages": messages,
            "max_tokens": self.max_output_tokens(request),
            "stream": True,
        }
        extra: dict[str, Any] = {}
        if len(self.models) > 1:
            extra["models"] = list(self.models[1:])
        if request.json_schema is not None:
            arguments["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": request.json_schema},
            }
            # Only to providers that hold their answer to the schema
            extra["provider"] = {"require_parameters": True}
        effort = self.effort or settings.llm_effort() or (DEFAULT_EFFORT if self.models == (DEFAULT_MODEL,) else None)
        if effort:
            extra["reasoning"] = {"effort": effort}
        if extra:
            arguments["extra_body"] = extra
        return arguments

    def _new_client(self, sdk: Any) -> Any:
        key = settings.openrouter_api_key()
        if not key:
            raise ProviderUnavailable(
                "OpenRouter needs a key: sign in with `talkgenerator login openrouter`, or set OPENROUTER_API_KEY "
                "(free at https://openrouter.ai/settings/keys)"
            )
        self._client = sdk.OpenAI(
            api_key=key,
            base_url=API_URL,
            default_headers=APP_HEADERS,
            timeout=TIMEOUT_SECONDS,
            max_retries=MAX_RETRIES,
        )
        return self._client


def _provider_failed(error: Exception, sdk: Any) -> bool:
    """Whether an error is the model's provider failing (an error in the stream, a timeout there, a server error),
    rather than the request, the key or the credits, which asking again doesn't change. Not a timeout of
    talkgenerator's own: after TIMEOUT_SECONDS, another try would keep the audience waiting too long."""
    if isinstance(error, sdk.APIConnectionError):
        return False
    if isinstance(error, sdk.APIStatusError):
        return error.status_code >= 500 or error.status_code == 408
    return True
