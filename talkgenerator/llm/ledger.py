"""A talk's ledger and budget: what it asks of language models, what that costs, and what it may cost.

Wrap a talk's provider in a MeteredProvider: every request it lets through is written down in the talk's Ledger,
failed ones too (OpenRouter's free tier counts requests, not tokens), and the Budget is checked before each request.
A budget of max_cost_usd=0 lets only free models through, which is how talkgenerator.com stays at $0.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from talkgenerator.llm import prices
from talkgenerator.llm.base import BudgetExceeded, ProviderError, TextProvider, TextRequest, TextResponse
from talkgenerator.models.usage import Usage


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
        """One line for the logs."""
        total = self.total()
        if not total.requests:
            return "No language model requests"
        models = ", ".join(sorted({entry.model for entry in self.entries}))
        line = (
            f"{total.requests} language model request{'s' if total.requests != 1 else ''} ({models}): "
            f"{total.input_tokens + total.cached_input_tokens:,} tokens in ({total.cached_input_tokens:,} cached), "
            f"{total.output_tokens:,} out, ${total.cost_usd:.4f}"
        )
        if total.unpriced_requests:
            line += f" plus {total.unpriced_requests} of unknown price"
        if total.failed_requests:
            line += f"; {total.failed_requests} failed"
        return line


@dataclass(frozen=True)
class Budget:
    """What a talk may spend on language models. None means no limit; max_cost_usd=0 allows free models only."""

    max_requests: int | None = None
    max_cost_usd: float | None = None

    def check(self, ledger: Ledger, model: str, request: TextRequest) -> None:
        """Raise BudgetExceeded if the request could take the talk over its budget."""
        spent = ledger.total()
        if self.max_requests is not None and spent.requests >= self.max_requests:
            raise BudgetExceeded(f"the talk already made its {self.max_requests} language model requests")
        if self.max_cost_usd is not None:
            worst_case = prices.worst_case_cost(model, request)
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

    def _metered(self, request: TextRequest, call: Callable[[], TextResponse]) -> TextResponse:
        self.budget.check(self.ledger, self.id, request)
        start = time.monotonic()
        try:
            response = call()
        except ProviderError as error:
            usage = Usage(requests=1, failed_requests=1)
            self.ledger.add(LedgerEntry(self.id, request.purpose, usage, time.monotonic() - start, error=str(error)))
            raise
        self.ledger.add(
            LedgerEntry(
                response.model or self.id, request.purpose, usage_of(response, self.id), time.monotonic() - start
            )
        )
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
