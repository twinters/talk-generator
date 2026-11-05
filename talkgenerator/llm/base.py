"""The interface every language model provider offers (see docs/v5-plan.md, section 5.4).

Requests and responses are plain data, the same for every provider, so that providers can stand in for one another,
and a recorded answer can be replayed (see talkgenerator.llm.replay). Whatever goes wrong with a provider raises a
ProviderError, and callers then fall back (in the end, to the classic generator): a talk never fails for it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from talkgenerator.models.base import Data


class Message(Data):
    role: Literal["user", "assistant"]
    content: str


class TextRequest(Data):
    purpose: str  # what the text is for, such as "talk plan": for the ledger and the logs
    messages: tuple[Message, ...]
    system: str = ""
    json_schema: dict[str, Any] | None = None  # to get JSON that fits this schema back
    max_output_tokens: int = 4000

    @classmethod
    def ask(cls, purpose: str, prompt: str, **options: Any) -> TextRequest:
        """A request of one user message."""
        return cls(purpose=purpose, messages=(Message(role="user", content=prompt),), **options)


class TextResponse(Data):
    text: str
    data: Any = None  # the parsed JSON, when the request asked for JSON
    finish: Literal["complete", "truncated", "refused"] = "complete"
    model: str = ""  # the model that answered, as "provider:model" (it can differ from the one asked for)
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None  # what the provider says the request cost, if it says so


@dataclass(frozen=True)
class Capabilities:
    structured_output: bool = False  # can be held to a JSON schema
    streaming: bool = False  # hands over its text while writing it
    vision: bool = False  # reads images
    max_output_tokens: int = 4000


class ProviderError(Exception):
    """A language model couldn't answer. Callers fall back to another provider, or to the classic generator."""


class ProviderUnavailable(ProviderError):
    """No usable provider: none is configured, a key is missing, or the service is down."""


class RateLimited(ProviderError):
    """The provider's rate limit or quota (such as OpenRouter's free requests per day) ran out for now."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class BudgetExceeded(ProviderError):
    """The talk's budget doesn't allow the request (see talkgenerator.llm.ledger.Budget)."""


class TextProvider(ABC):
    """A language model, as talkgenerator uses it."""

    id: str  # "provider:model", such as "anthropic:claude-opus-5-5"
    capabilities: Capabilities = Capabilities()

    @abstractmethod
    def complete(self, request: TextRequest) -> TextResponse:
        """The model's answer to the request. Raises a ProviderError when there's none."""

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        """Like complete, but handing over the text in pieces while it's being written, so that slides can show up
        before the whole talk is written. Providers that can't stream hand it over in one piece."""
        response = self.complete(request)
        if response.text:
            on_text(response.text)
        return response

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"
