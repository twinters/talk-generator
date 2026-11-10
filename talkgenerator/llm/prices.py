"""List prices of language models, to tell what a talk cost, and to hold a talk to its budget.

Prices are in dollars per million tokens, as published by the providers. A model missing from the table has no known
price, which budgets treat as possibly costly. OpenRouter's free models (ids ending in ":free") and replayed answers
cost nothing, and so do the models of a ChatGPT plan: their requests count toward the plan's usage instead. Gemini's
models have a free tier, but whether a key is on it is its Google Cloud project's (billing linked or not), which
talkgenerator can't tell: they're priced as the paid tier charges, what a request costs at most.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
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
    # The models that server-side fallbacks may hand a declined request to (cache prices: a tenth of the input)
    "anthropic:claude-opus-5": Price(5.00, 25.00, cached_input=0.50),
    "anthropic:claude-opus-4-8": Price(5.00, 25.00, cached_input=0.50),
    "anthropic:claude-sonnet-5": Price(2.00, 10.00, cached_input=0.20),
    # Checked on 2026-11-10 (aistudio.google.com/docs/pricing, the paid tier's Standard prices; the cache price is
    # implicit caching's, which needs nothing asked). Output includes the thinking. The newest models' prices go up on
    # a date: PRICE_CHANGES
    "gemini:gemini-4-argon": Price(2.00, 10.00, cached_input=0.10),
    "gemini:gemini-3.8-flash": Price(0.75, 3.75, cached_input=0.075),
    "gemini:gemini-3.6-flash": Price(0.75, 3.75, cached_input=0.075),
    "gemini:gemini-3.5-flash-lite": Price(0.30, 2.50, cached_input=0.03),
    "gemini:gemini-3.1-flash-lite": Price(0.25, 1.50, cached_input=0.025),
    # (Above 200,000 tokens of prompt, cached input costs $0.40)
    "gemini:gemini-3.1-pro-preview": Price(
        2.00, 12.00, cached_input=0.20, long_prompt_tokens=200_000, long_input=4.00, long_output=18.00
    ),
    "gemini:gemini-3-flash-preview": Price(0.50, 3.00, cached_input=0.05),
    "gemini:gemini-2.5-flash-lite": Price(0.10, 0.40, cached_input=0.01),
}

# Prices that change on a date (where an introductory price ends): a model's price from that day on
PRICE_CHANGES: Final[dict[str, tuple[date, Price]]] = {
    "gemini:gemini-4-argon": (date(2026, 12, 1), Price(4.00, 20.00, cached_input=0.20)),
    "gemini:gemini-3.8-flash": (date(2027, 1, 1), Price(1.50, 7.50, cached_input=0.15)),
    "gemini:gemini-3.6-flash": (date(2027, 1, 1), Price(1.50, 7.50, cached_input=0.15)),
}


# OpenRouter's router that sends every request to one of its free models
OPENROUTER_FREE_ROUTER: Final = "openrouter:openrouter/free"


def price_of(model: str, today: date | None = None) -> Price | None:
    """The price of a model ("provider:model") today (or on the day given), or None if it isn't known."""
    change = PRICE_CHANGES.get(model)
    if change is not None and (today or date.today()) >= change[0]:
        return change[1]
    if model in PRICES:
        return PRICES[model]
    provider = model.split(":", 1)[0]
    if provider in ("none", "replay", "chatgpt"):
        return FREE
    if provider == "openrouter" and (model.endswith(":free") or model == OPENROUTER_FREE_ROUTER):
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


def worst_case_cost(model: str, request: TextRequest, max_output_tokens: int | None = None) -> float | None:
    """The most a request can cost: all its text as uncached input, at a generous three characters per token, and
    the pictures it shows as many tokens as Claude counts for them, and its whole output allowance (the request's, or
    a larger one that leaves room for thinking). None if the model's price isn't known."""
    characters = len(request.system) + sum(len(message.content) for message in request.messages)
    if request.json_schema is not None:
        characters += len(json.dumps(request.json_schema))
    pictures = sum(image.tokens for message in request.messages for image in message.images)
    output_tokens = request.max_output_tokens if max_output_tokens is None else max_output_tokens
    return estimate_cost(model, math.ceil(characters / 3) + pictures, 0, output_tokens)
