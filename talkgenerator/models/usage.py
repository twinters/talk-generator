"""What the language models of a talk were used for: requests, tokens and dollars."""

from __future__ import annotations

from talkgenerator.models.base import Data


class Usage(Data):
    requests: int = 0
    input_tokens: int = 0  # uncached input
    cached_input_tokens: int = 0  # input read from the provider's prompt cache, which costs less
    output_tokens: int = 0
    cost_usd: float = 0.0  # what the priced requests cost: what the provider said, or else an estimate from list prices
    unpriced_requests: int = 0  # requests to models without a known price, which cost_usd leaves out
    failed_requests: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            requests=self.requests + other.requests,
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            unpriced_requests=self.unpriced_requests + other.unpriced_requests,
            failed_requests=self.failed_requests + other.failed_requests,
        )
