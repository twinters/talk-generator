"""OpenAI's models with your own OPENAI_API_KEY, through the Responses API and the openai SDK
(pip install 'talkgenerator[openai]').

Name the model, as in "openai:gpt-5-mini": OpenAI's line-up changes too often for a default. Answers aren't stored
at OpenAI (store=False), and TALKGENERATOR_LLM_EFFORT sets the reasoning effort of the models that reason.
"""

from __future__ import annotations

from collections.abc import Callable
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
from talkgenerator.util.http_util import redact

# Reasoning counts as output: room for it on top of the answer
_THINKING_TOKENS: Final = 8000
_INCOMPLETE: Final[dict[str, Finish]] = {"max_output_tokens": "truncated", "content_filter": "refused"}


class OpenAIProvider(TextProvider):
    capabilities = Capabilities(structured_output=True, streaming=True, vision=True)
    # Who answers, in messages, and the provider's name in model ids (the chatgpt provider has the same API)
    service = "OpenAI"
    prefix = "openai"

    def __init__(self, model: str, *, client: Any = None) -> None:
        if not model.strip():
            raise ValueError("Name the OpenAI model to write talks with, as in 'openai:gpt-5-mini'")
        self.model = model.strip()
        self.id = f"openai:{self.model}"
        self._client = client

    def max_output_tokens(self, request: TextRequest) -> int:
        return request.max_output_tokens + _THINKING_TOKENS

    def complete(self, request: TextRequest) -> TextResponse:
        return self.stream(request, lambda text: None)

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        sdk = import_sdk("openai", "openai")
        client = self._client or self._new_client(sdk)
        parts: list[str] = []
        final = None
        refused = False
        try:
            for event in client.responses.create(**self.arguments(request)):
                if event.type == "response.output_text.delta":
                    parts.append(event.delta)
                    on_text(event.delta)
                elif event.type == "response.refusal.delta":
                    refused = True
                elif event.type in ("response.completed", "response.incomplete"):
                    final = event.response
                elif event.type == "response.failed":
                    raise self.failed(getattr(event.response, "error", None))
                elif event.type == "error":
                    raise self.failed(event)
        except sdk.OpenAIError as error:
            raise self.error(error, sdk) from error

        ending: Finish = "complete"
        if final is None:
            ending = "truncated"
        elif final.status == "incomplete":
            ending = _INCOMPLETE.get(getattr(final.incomplete_details, "reason", None) or "", "truncated")
        if refused:
            ending = "refused"
        text = "".join(parts)
        usage = getattr(final, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        cached_tokens = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
        return TextResponse(
            text=text,
            data=parse_json(text) if request.json_schema is not None else None,
            finish=ending,
            model=f"{self.prefix}:{getattr(final, 'model', None) or self.model}",
            input_tokens=max(input_tokens - cached_tokens, 0),
            cached_input_tokens=cached_tokens,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    def arguments(self, request: TextRequest) -> dict[str, Any]:
        """The request, as the Responses API takes it."""
        arguments: dict[str, Any] = {
            "model": self.model,
            "input": [{"role": message.role, "content": message.content} for message in request.messages],
            "max_output_tokens": self.max_output_tokens(request),
            "stream": True,
            "store": False,
        }
        if request.system:
            arguments["instructions"] = request.system
        if request.json_schema is not None:
            arguments["text"] = {
                "format": {"type": "json_schema", "name": "answer", "schema": request.json_schema, "strict": True}
            }
        effort = settings.llm_effort()
        if effort:
            arguments["reasoning"] = {"effort": effort}
        return arguments

    def failed(self, error: Any) -> ProviderError:
        """The ProviderError for an answer that failed while it streamed (the error the stream ended with)."""
        reason = getattr(error, "message", None) or "no reason given"
        return ProviderError(f"{self.service}: the answer failed ({redact(reason)})")

    def error(self, error: Exception, sdk: Any) -> ProviderError:
        """The ProviderError for an error of the SDK (a request turned down, say)."""
        return provider_error(error, sdk, self.service)

    def _new_client(self, sdk: Any) -> Any:
        key = settings.openai_api_key()
        if not key:
            raise ProviderUnavailable("OpenAI's models need a key: set OPENAI_API_KEY")
        self._client = sdk.OpenAI(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)
        return self._client
