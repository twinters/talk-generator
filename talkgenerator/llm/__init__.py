"""Language models (docs/v5-plan.md, section 5): one interface for every provider, recorded answers for offline
use, and a ledger and budget per talk."""

from talkgenerator.llm.base import (
    BudgetExceeded,
    Capabilities,
    Finish,
    Message,
    ProviderError,
    ProviderUnavailable,
    RateLimited,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.claude import ClaudeProvider
from talkgenerator.llm.ledger import Budget, Ledger, LedgerEntry, MeteredProvider
from talkgenerator.llm.openai_responses import OpenAIProvider
from talkgenerator.llm.openrouter import OpenRouterProvider
from talkgenerator.llm.providers import NoneProvider, from_settings, provider_from_spec, register
from talkgenerator.llm.replay import CassetteMiss, ReplayProvider, request_key

__all__ = [
    "Budget",
    "BudgetExceeded",
    "Capabilities",
    "CassetteMiss",
    "ClaudeProvider",
    "Finish",
    "Ledger",
    "LedgerEntry",
    "Message",
    "MeteredProvider",
    "NoneProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "ProviderError",
    "ProviderUnavailable",
    "RateLimited",
    "ReplayProvider",
    "TextProvider",
    "TextRequest",
    "TextResponse",
    "from_settings",
    "provider_from_spec",
    "register",
    "request_key",
]
