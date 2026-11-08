"""The interface every language model provider offers (see docs/v5-plan.md, section 5.4).

Requests and responses are plain data, the same for every provider, so that providers can stand in for one another,
and a recorded answer can be replayed (see talkgenerator.llm.replay). Whatever goes wrong with a provider raises a
ProviderError, and callers then fall back (in the end, to the classic generator): a talk never fails for it.
"""

from __future__ import annotations

import base64
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from pydantic import Field

from talkgenerator.models.base import Data

# How many pixels a picture may have before a provider scales it down (Claude's limits: 1568 on its longest side, and
# about 1.15 megapixels), and how many of them a token stands for (Claude's: a picture costs width x height / 750
# tokens; OpenAI's models count fewer)
_LONGEST_SIDE: Final = 1568
_MOST_PIXELS: Final = 1_150_000
_PIXELS_PER_TOKEN: Final = 750


class ImagePart(Data):
    """A picture a message shows the model, before its text: its bytes (JPEG or PNG), its size in pixels, and its
    name, which says what it shows. The bytes never go into a cassette or a log: a recorded answer is found again by
    the name (see talkgenerator.llm.replay), as the same contact sheet of the same pictures is the same request,
    whatever its bytes came out as."""

    media_type: Literal["image/jpeg", "image/png"] = "image/jpeg"
    data: bytes = Field(exclude=True, repr=False)
    width: int
    height: int
    name: str

    def base64(self) -> str:
        return base64.b64encode(self.data).decode("ascii")

    def data_url(self) -> str:
        """The picture as a data URL, as OpenAI's and OpenRouter's APIs take it."""
        return f"data:{self.media_type};base64,{self.base64()}"

    @property
    def tokens(self) -> int:
        """About how many input tokens the picture costs, at most (as Claude counts them, once it's scaled down to
        what Claude takes)."""
        scale = min(1.0, _LONGEST_SIDE / max(self.width, self.height, 1))
        scale = min(scale, math.sqrt(_MOST_PIXELS / max(self.width * self.height, 1)))
        return math.ceil(self.width * scale * self.height * scale / _PIXELS_PER_TOKEN)


class Message(Data):
    role: Literal["user", "assistant"]
    content: str
    images: tuple[ImagePart, ...] = ()  # what the message shows, before its text (for models that read pictures)


class TextRequest(Data):
    purpose: str  # what the text is for, such as "talk plan": for the ledger and the logs
    messages: tuple[Message, ...]
    system: str = ""
    json_schema: dict[str, Any] | None = None  # to get JSON that fits this schema back
    max_output_tokens: int = 4000

    @classmethod
    def ask(cls, purpose: str, prompt: str, images: Sequence[ImagePart] = (), **options: Any) -> TextRequest:
        """A request of one user message (which shows the images, if any)."""
        return cls(purpose=purpose, messages=(Message(role="user", content=prompt, images=tuple(images)),), **options)

    @property
    def shows_images(self) -> bool:
        """Whether a message of the request shows a picture (for a model that reads them)."""
        return any(message.images for message in self.messages)


# How an answer ended: whole, cut off (by its length limit, or a stream that broke off), or refused by the model
Finish = Literal["complete", "truncated", "refused"]


class TextResponse(Data):
    text: str
    data: Any = None  # the parsed JSON, when the request asked for JSON
    finish: Finish = "complete"
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


class AnswerStopped(Exception):
    """Whoever read an answer while it came in stopped it (raised from on_text, out of the provider's stream): a talk
    whose answer starts in the wrong language, which asks again. The request still counts (see
    talkgenerator.llm.ledger)."""


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

    def possible_models(self) -> tuple[str, ...]:
        """Every model ("provider:model") that may answer a request: more than one when the provider falls back to
        other models. Budgets check them all."""
        return (self.id,)

    def max_output_tokens(self, request: TextRequest) -> int:
        """The most output tokens a request may be billed for: its answer, plus room for thinking on models that
        think before they write."""
        return request.max_output_tokens

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"
