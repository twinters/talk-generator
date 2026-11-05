"""Claude, with your own ANTHROPIC_API_KEY, through Anthropic's Messages API and the anthropic SDK
(pip install 'talkgenerator[anthropic]'; docs/v5-plan.md, section 5.5).

The default model is Claude Opus 5.5. Claude takes no sampling parameters (the seeded dice in the prompt bring the
variety instead), structured outputs hold its answer to the talk's JSON schema, and the effort sets how hard it
thinks before it writes: low by default (TALKGENERATOR_LLM_EFFORT changes it), which suits short creative writing.
Claude Opus 5.5 always thinks, so requests leave room for that.

When Claude's safety classifiers decline a request, the models that have server-side fallbacks run it again on the
model Anthropic recommends for it, in the same request. If that declines too, the answer comes back refused, and
the talk is classic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.llm import prices
from talkgenerator.llm.base import (
    Capabilities,
    Finish,
    ProviderUnavailable,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.sdk import MAX_RETRIES, TIMEOUT_SECONDS, import_sdk, parse_json, provider_error

DEFAULT_MODEL: Final = "claude-opus-5-5"
DEFAULT_EFFORT: Final = "low"
# The models with server-side fallbacks (`fallbacks: "default"`); Claude Haiku 5.5 has none
FALLBACK_MODELS: Final = frozenset({"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5"})
FALLBACK_BETA: Final = "server-side-fallback-2026-07-01"
# Room for thinking on top of the answer, by effort
_THINKING_TOKENS: Final = {"low": 4000, "medium": 8000, "high": 16000, "xhigh": 32000, "max": 64000}
_FINISH: Final[dict[str, Finish]] = {
    "max_tokens": "truncated",
    "model_context_window_exceeded": "truncated",
    "refusal": "refused",
}
# Writing to the prompt cache costs a quarter more than plain input
_CACHE_WRITE_PRICE: Final = 1.25


class ClaudeProvider(TextProvider):
    capabilities = Capabilities(structured_output=True, streaming=True, vision=True, max_output_tokens=64000)

    def __init__(self, model: str = DEFAULT_MODEL, *, effort: str | None = None, client: Any = None) -> None:
        self.model = model.strip() or DEFAULT_MODEL
        self.effort = effort or settings.llm_effort() or DEFAULT_EFFORT
        self.id = f"anthropic:{self.model}"
        self._client = client

    def max_output_tokens(self, request: TextRequest) -> int:
        return request.max_output_tokens + _THINKING_TOKENS.get(self.effort, _THINKING_TOKENS["high"])

    def complete(self, request: TextRequest) -> TextResponse:
        return self.stream(request, lambda text: None)

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        sdk = import_sdk("anthropic", "anthropic")
        client = self._client or self._new_client(sdk)
        try:
            with client.beta.messages.stream(**self.arguments(request)) as stream:
                for text in stream.text_stream:
                    on_text(text)
                message = stream.get_final_message()
        except sdk.AnthropicError as error:  # also an error in the middle of the stream
            raise provider_error(error, sdk, "Anthropic") from error
        return self._response(message, request)

    def arguments(self, request: TextRequest) -> dict[str, Any]:
        """The request, as the Messages API takes it."""
        output_config: dict[str, Any] = {"effort": self.effort}
        if request.json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": request.json_schema}
        arguments: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_output_tokens(request),
            "messages": [{"role": message.role, "content": message.content} for message in request.messages],
            "output_config": output_config,
        }
        if request.system:
            # The same for every talk: cached once it's long enough to be (512 tokens, on current models)
            arguments["system"] = [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}]
        if self.model in FALLBACK_MODELS:
            arguments["fallbacks"] = "default"
            arguments["betas"] = [FALLBACK_BETA]
        return arguments

    def _response(self, message: Any, request: TextRequest) -> TextResponse:
        # After a fallback, the answer is in more than one text block: what the declined model wrote, and what the
        # fallback model went on with
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        # With fallbacks, every model that ran has its own usage; otherwise, the message's usage is all there is
        attempts = [entry for entry in usage.iterations or () if entry.type in ("message", "fallback_message")]
        attempts = attempts or [usage]
        return TextResponse(
            text=text,
            data=parse_json(text) if request.json_schema is not None else None,
            finish=_FINISH.get(message.stop_reason or "", "complete"),
            model=f"anthropic:{message.model}",
            input_tokens=sum(entry.input_tokens + (entry.cache_creation_input_tokens or 0) for entry in attempts),
            cached_input_tokens=sum(entry.cache_read_input_tokens or 0 for entry in attempts),
            output_tokens=sum(entry.output_tokens for entry in attempts),
            cost_usd=_cost(attempts, message.model),
        )

    def _new_client(self, sdk: Any) -> Any:
        key = settings.anthropic_api_key()
        if not key:
            raise ProviderUnavailable("Claude needs an Anthropic API key: set ANTHROPIC_API_KEY")
        self._client = sdk.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
        return self._client


def _cost(attempts: Sequence[Any], answered_by: str) -> float | None:
    """What the attempts cost at list prices, each at the price of its own model; None if one has no known price."""
    total = 0.0
    for entry in attempts:
        model = f"anthropic:{getattr(entry, 'model', None) or answered_by}"
        cost = prices.estimate_cost(model, entry.input_tokens, entry.cache_read_input_tokens or 0, entry.output_tokens)
        cache_writes = prices.estimate_cost(model, entry.cache_creation_input_tokens or 0, 0, 0)
        if cost is None or cache_writes is None:
            return None
        total += cost + cache_writes * _CACHE_WRITE_PRICE
    return total
