"""Choosing a language model provider: from a spec such as "none" or "replay:<cassette>".

TALKGENERATOR_LLM sets the spec (`settings.llm_spec`); without it, or with DISABLE_LLM=1, it's "none", and talks
are classic. The providers that talk to real models (OpenRouter, Anthropic, OpenAI, ...) register here with
`register` as they arrive (docs/v5-plan.md, 5.0.0a2).
"""

from __future__ import annotations

from collections.abc import Callable

from talkgenerator import settings
from talkgenerator.llm.base import Capabilities, ProviderUnavailable, TextProvider, TextRequest, TextResponse
from talkgenerator.llm.replay import ReplayProvider


class NoneProvider(TextProvider):
    """No language model: every request is unavailable, so callers fall back to the classic generator."""

    id = "none"
    capabilities = Capabilities()

    def complete(self, request: TextRequest) -> TextResponse:
        raise ProviderUnavailable("No language model is set up (TALKGENERATOR_LLM is 'none')")


# A provider's name -> a function that makes the provider from what follows the name in the spec
ProviderFactory = Callable[[str], TextProvider]

_FACTORIES: dict[str, ProviderFactory] = {}


def register(name: str, factory: ProviderFactory) -> None:
    if name in _FACTORIES:
        raise ValueError(f"There already is a language model provider called {name!r}")
    _FACTORIES[name] = factory


def names() -> list[str]:
    return list(_FACTORIES)


def provider_from_spec(spec: str) -> TextProvider:
    """The provider a spec stands for: its name, and what the provider needs after a colon (such as a model)."""
    name, _, argument = spec.strip().partition(":")
    factory = _FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"Unknown language model provider {name!r} in {spec!r}; choose from: {', '.join(_FACTORIES)}")
    return factory(argument.strip())


def from_settings() -> TextProvider:
    """The provider that TALKGENERATOR_LLM (and DISABLE_LLM) ask for."""
    return provider_from_spec(settings.llm_spec())


def _replay(cassette: str) -> TextProvider:
    if not cassette:
        raise ValueError("A replay provider needs its cassette, as in 'replay:tests/cassettes/talk.json'")
    return ReplayProvider(cassette)


register("none", lambda _: NoneProvider())
register("replay", _replay)
