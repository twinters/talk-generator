"""List prices of language models, to tell what a talk cost, and to hold a talk to its budget.

Prices are in dollars per million tokens, as published by the providers. A model missing from the table has no known
price, which budgets treat as possibly costly. OpenRouter's free models (ids ending in ":free") and replayed answers
cost nothing.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Final

from talkgenerator.llm.base import TextRequest


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cached_input: float | None = None  # reading from the prompt cache; None: the same as input
    # Some models cost more for long prompts: above long_prompt_tokens, these prices apply
    long_prompt_tokens: int | None = None
    long_input: float | None = None
    long_output: float | None = None


FREE: Final = Price(0.0, 0.0)

# Checked on 2026-11-05 (Anthropic's first-party API prices)
PRICES: Final[dict[str, Price]] = {
    "anthropic:claude-opus-5-5": Price(4.00, 20.00, cached_input=0.20),
    "anthropic:claude-sonnet-5-5": Price(2.00, 10.00, cached_input=0.20),
    # The cache price assumes the usual tenth of the input price
    "anthropic:claude-haiku-5-5": Price(
        0.10, 0.50, cached_input=0.01, long_prompt_tokens=100_000, long_input=0.50, long_output=2.50
    ),
}


def price_of(model: str) -> Price | None:
    """The price of a model ("provider:model"), or None if it isn't known."""
    if model in PRICES:
        return PRICES[model]
    provider = model.split(":", 1)[0]
    if provider in ("none", "replay"):
        return FREE
    if provider == "openrouter" and model.endswith(":free"):
        return FREE
    return None


def estimate_cost(model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> float | None:
    """What a request cost in dollars, or None if the model's price isn't known."""
    price = price_of(model)
    if price is None:
        return None
    long_prompt = price.long_prompt_tokens is not None and input_tokens + cached_input_tokens > price.long_prompt_tokens
    input_price = price.long_input if long_prompt and price.long_input is not None else price.input
    output_price = price.long_output if long_prompt and price.long_output is not None else price.output
    cached_price = price.cached_input if price.cached_input is not None else input_price
    return (input_tokens * input_price + cached_input_tokens * cached_price + output_tokens * output_price) / 1e6


def worst_case_cost(model: str, request: TextRequest) -> float | None:
    """The most a request can cost: all its text as uncached input, at a generous three characters per token, and
    its whole output allowance. None if the model's price isn't known."""
    characters = len(request.system) + sum(len(message.content) for message in request.messages)
    if request.json_schema is not None:
        characters += len(json.dumps(request.json_schema))
    return estimate_cost(model, math.ceil(characters / 3), 0, request.max_output_tokens)
