"""Language models (docs/v5-plan.md, section 5): one interface for every provider, recorded answers for offline
use, and a ledger and budget per talk."""

from talkgenerator.llm.base import (
    BudgetExceeded,
    Capabilities,
    Message,
    ProviderError,
    ProviderUnavailable,
    RateLimited,
    TextProvider,
    TextRequest,
    TextResponse,
)
from talkgenerator.llm.ledger import Budget, Ledger, LedgerEntry, MeteredProvider
from talkgenerator.llm.providers import NoneProvider, from_settings, provider_from_spec, register
from talkgenerator.llm.replay import CassetteMiss, ReplayProvider, request_key

__all__ = [
    "Budget",
    "BudgetExceeded",
    "Capabilities",
    "CassetteMiss",
    "Ledger",
    "LedgerEntry",
    "Message",
    "MeteredProvider",
    "NoneProvider",
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
