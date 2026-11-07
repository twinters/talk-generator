"""Choosing a language model provider, from a spec: the provider's name, and after a colon what it needs.

- "openrouter" (OpenRouter's free models), or "openrouter:<model>[,<fallback model>...]"
- "anthropic" (Claude Opus 5.5), or "anthropic:<model>"
- "openai:<model>"
- "chatgpt" (the models of your ChatGPT plan, once you've signed in: talkgenerator login chatgpt), or
  "chatgpt:<model>"
- "replay:<cassette.json>": answers recorded earlier (talkgenerator.llm.replay)
- "none": no language model; talks are classic

TALKGENERATOR_LLM sets the spec (see `settings.llm_spec` for the default), and DISABLE_LLM=1 makes it "none".
"""

from __future__ import annotations

from collections.abc import Callable

from talkgenerator import settings
from talkgenerator.llm.base import Capabilities, ProviderUnavailable, TextProvider, TextRequest, TextResponse
from talkgenerator.llm.chatgpt import ChatGPTProvider
from talkgenerator.llm.claude import ClaudeProvider
from talkgenerator.llm.openai_responses import OpenAIProvider
from talkgenerator.llm.openrouter import OpenRouterProvider
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
register("openrouter", lambda models: OpenRouterProvider(models.split(",")))
register("anthropic", lambda model: ClaudeProvider(model))
register("openai", lambda model: OpenAIProvider(model))
register("chatgpt", lambda model: ChatGPTProvider(model))
