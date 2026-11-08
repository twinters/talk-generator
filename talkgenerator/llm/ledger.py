"""A talk's ledger and budget: what it asks of language models, what that costs, and what it may cost.

Wrap a talk's provider in a MeteredProvider: every request it lets through is written down in the talk's Ledger,
failed ones too (OpenRouter's free tier counts requests, not tokens), and the Budget is checked before each request.
A budget of max_cost_usd=0 lets only free models through, which is how talkgenerator.com stays at $0.

The talk's generated pictures go in its ledger too (purpose "image": see talkgenerator.images.generation), with their
own budget (talkgenerator.images.generation.ImageBudget): a picture isn't a language model's request.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from talkgenerator.llm import prices
from talkgenerator.llm.base import (
    AnswerStopped,
    BudgetExceeded,
    ProviderError,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.models.usage import Usage

IMAGES = "image"  # the purpose of a generated picture's entry (talkgenerator.images.generation.PURPOSE)
# The purpose of the vision pick's request (talkgenerator.images.vision.PURPOSE): a language model's request, by
# a model that picks the talk's pictures, not the one that writes it
VISION = "vision pick"


@dataclass(frozen=True)
class LedgerEntry:
    model: str
    purpose: str
    usage: Usage
    seconds: float
    error: str | None = None


class Ledger:
    """What a talk asked language models for, and what it cost. Safe to share between threads."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._lock = threading.Lock()

    def add(self, entry: LedgerEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def total(self) -> Usage:
        return sum((entry.usage for entry in self.entries), Usage())

    def summary(self) -> str:
        """One line for the logs (and what the talk's generated pictures cost, if it has any)."""
        total = self.total()
        line = "No language model requests"
        if total.requests:
            models = ", ".join(sorted({entry.model for entry in self.entries if entry.purpose != IMAGES}))
            line = (
                f"{total.requests} language model request{'s' if total.requests != 1 else ''} ({models}): "
                f"{total.input_tokens + total.cached_input_tokens:,} tokens in ({total.cached_input_tokens:,} cached), "
                f"{total.output_tokens:,} out, ${total.cost_usd:.4f}"
            )
            if total.unpriced_requests:
                line += f" plus {total.unpriced_requests} of unknown price"
            if total.vision_requests:
                line += f"; {total.vision_requests} of them to pick pictures"
            if total.failed_requests:
                line += f"; {total.failed_requests} failed"
        if total.images or total.failed_images:
            generators = ", ".join(sorted({entry.model for entry in self.entries if entry.purpose == IMAGES}))
            line += (
                f"; {total.images} generated picture{'s' if total.images != 1 else ''} ({generators}): "
                f"${total.image_cost_usd:.4f}"
            )
            if total.unpriced_images:
                line += f" plus {total.unpriced_images} of unknown price"
            if total.failed_images:
                line += f"; {total.failed_images} failed"
        return line

    def language_models(self) -> list[str]:
        """The language models that answered the talk's requests, in order (not its image generators, nor the vision
        model that picked its pictures: see vision_models)."""
        return [entry.model for entry in self.entries if entry.error is None and entry.purpose not in (IMAGES, VISION)]

    def vision_models(self) -> list[str]:
        """The models that answered the requests of the talk's vision pick, in order."""
        return [entry.model for entry in self.entries if entry.error is None and entry.purpose == VISION]


@dataclass(frozen=True)
class Budget:
    """What a talk may spend on language models. None means no limit; max_cost_usd=0 allows free models only."""

    max_requests: int | None = None
    max_cost_usd: float | None = None

    def check(self, ledger: Ledger, model: str, request: TextRequest, max_output_tokens: int | None = None) -> None:
        """Raise BudgetExceeded if the request could take the talk over its budget (with at most max_output_tokens
        of output, or else the request's own allowance)."""
        spent = ledger.total()
        if self.max_requests is not None and spent.requests >= self.max_requests:
            raise BudgetExceeded(f"the talk already made its {self.max_requests} language model requests")
        if self.max_cost_usd is not None:
            worst_case = prices.worst_case_cost(model, request, max_output_tokens)
            if worst_case is None:
                raise BudgetExceeded(f"{model} has no known price, and the talk may spend at most ${self.max_cost_usd}")
            if spent.cost_usd + worst_case > self.max_cost_usd:
                raise BudgetExceeded(
                    f"a {request.purpose!r} request to {model} could cost ${worst_case:.4f}, and the talk may spend "
                    f"${self.max_cost_usd - spent.cost_usd:.4f} more"
                )


class MeteredProvider(TextProvider):
    """A provider that keeps to a talk's budget and writes every request down in its ledger."""

    def __init__(self, provider: TextProvider, ledger: Ledger, budget: Budget = Budget()) -> None:
        self.provider = provider
        self.ledger = ledger
        self.budget = budget
        self.id = provider.id
        self.capabilities = provider.capabilities

    def complete(self, request: TextRequest) -> TextResponse:
        return self._metered(request, lambda: self.provider.complete(request))

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        return self._metered(request, lambda: self.provider.stream(request, on_text))

    def possible_models(self) -> tuple[str, ...]:
        return self.provider.possible_models()

    def max_output_tokens(self, request: TextRequest) -> int:
        return self.provider.max_output_tokens(request)

    def _metered(self, request: TextRequest, call: Callable[[], TextResponse]) -> TextResponse:
        # Every model that may answer has to fit the budget: a free model can fall back to a paid one
        for model in self.possible_models():
            self.budget.check(self.ledger, model, request, self.max_output_tokens(request))
        start = time.monotonic()
        vision = 1 if request.purpose == VISION else 0
        try:
            response = call()
        except ProviderError as error:
            usage = Usage(requests=1, vision_requests=vision, failed_requests=1)
            self.ledger.add(LedgerEntry(self.id, request.purpose, usage, time.monotonic() - start, error=str(error)))
            raise
        except AnswerStopped:
            # (a request whose answer was stopped while it came in counts too, at a price that isn't known: a free
            # tier counts it as it counts the others)
            usage = Usage(requests=1, vision_requests=vision, unpriced_requests=1)
            self.ledger.add(LedgerEntry(self.id, request.purpose, usage, time.monotonic() - start, error="stopped"))
            raise
        usage = usage_of(response, self.id)
        if vision:
            usage = usage.model_copy(update={"vision_requests": 1})
        self.ledger.add(LedgerEntry(response.model or self.id, request.purpose, usage, time.monotonic() - start))
        return response


def usage_of(response: TextResponse, provider_id: str) -> Usage:
    """A response's usage, priced: what the provider said it cost, or else an estimate from list prices."""
    model = response.model or provider_id
    cost = response.cost_usd
    if cost is None:
        cost = prices.estimate_cost(model, response.input_tokens, response.cached_input_tokens, response.output_tokens)
    return Usage(
        requests=1,
        input_tokens=response.input_tokens,
        cached_input_tokens=response.cached_input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=cost or 0.0,
        unpriced_requests=1 if cost is None else 0,
    )
