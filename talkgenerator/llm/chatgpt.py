"""The models of your ChatGPT plan, once you've signed in with ChatGPT (talkgenerator login chatgpt; see
talkgenerator.llm.chatgpt_login), through OpenAI's Responses API and the openai SDK (pip install
'talkgenerator[openai]').

"chatgpt" writes with the first model your account lists (talkgenerator login chatgpt --status lists them), and
"chatgpt:<model>" with the one named. Requests cost talkgenerator nothing: they count toward your ChatGPT plan's
usage. As the plan's route asks, answers stream and aren't stored at OpenAI, and requests leave out what it turns
down (a limit on the answer's length, for one). The access token is refreshed when it runs out, and once more when
a request turns it down.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from talkgenerator.llm import chatgpt_login
from talkgenerator.llm.base import ProviderError, ProviderUnavailable, TextRequest, TextResponse
from talkgenerator.llm.openai_responses import OpenAIProvider
from talkgenerator.llm.sdk import TIMEOUT_SECONDS, import_sdk, provider_error
from talkgenerator.util.http_util import redact

# How hard the models think before they write, unless TALKGENERATOR_LLM_EFFORT says: a talk is one request, and its
# audience is waiting
DEFAULT_EFFORT: Final = "low"
_AGAIN_LATER: Final = "using your ChatGPT plan isn't possible right now; try again later"
_SIGN_IN_AGAIN: Final = "the sign-in doesn't allow this request: sign in again (talkgenerator login chatgpt)"
# What the plan's route answers when it turns a request down (OpenAI's error codes), as talkgenerator says it
_TURNED_DOWN: Final[dict[str, str]] = {
    "subscription_sharing_usage_limit_exceeded": (
        f"Usage limit reached: review your plan or this app's limit in ChatGPT settings ({chatgpt_login.USAGE_URL})"
    ),
    "subscription_sharing_user_not_eligible": "your ChatGPT account can't use its plan in talkgenerator",
    "subscription_sharing_usage_unavailable": _AGAIN_LATER,
    "subscription_sharing_user_unavailable": _AGAIN_LATER,
    "subscription_sharing_route_not_supported": "the plan's route doesn't take this kind of request",
    "chatpass_v2_scope_not_authorized": _SIGN_IN_AGAIN,
    "chatpass_v2_invalid_authorization_context": _SIGN_IN_AGAIN,
}

ClientMaker = Callable[[str], Any]  # an openai client that sends this access token


class _TokenRejected(ProviderError):
    """The request turned the access token down: refreshed, it may do."""


class ChatGPTProvider(OpenAIProvider):
    service = "ChatGPT"
    prefix = "chatgpt"

    def __init__(self, model: str = "", *, client_for: ClientMaker | None = None) -> None:
        self.model = model.strip() or chatgpt_login.default_model()
        self.id = f"chatgpt:{self.model or 'default'}"
        self._client: Any = None
        self._client_for = client_for
        self._token: str | None = None

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        token = chatgpt_login.access_token()
        if token != self._token:
            self._connect(token)
        if not self.model:  # (signed in since this provider was made)
            self.model = chatgpt_login.default_model() or next(iter(chatgpt_login.list_models(token)), "")
            if not self.model:
                raise ProviderUnavailable("ChatGPT: your account lists no models to write with")
            self.id = f"chatgpt:{self.model}"
        try:
            return super().stream(request, on_text)
        except _TokenRejected:
            self._connect(chatgpt_login.access_token(rejected=token))
            return super().stream(request, on_text)

    def arguments(self, request: TextRequest) -> dict[str, Any]:
        arguments = super().arguments(request)
        del arguments["max_output_tokens"]  # (the plan's route turns it down)
        arguments.setdefault("reasoning", {"effort": DEFAULT_EFFORT})
        return arguments

    def failed(self, error: Any) -> ProviderError:
        said = _TURNED_DOWN.get(getattr(error, "code", None) or "")
        return ProviderUnavailable(f"ChatGPT: {said}") if said else super().failed(error)

    def error(self, error: Exception, sdk: Any) -> ProviderError:
        status = getattr(error, "status_code", None)
        code = getattr(error, "code", None) or ""
        message = redact(getattr(error, "message", None) or error)
        if status == 401:
            return _TokenRejected(f"ChatGPT turned the sign-in down ({message})")
        if code in _TURNED_DOWN:
            return ProviderUnavailable(f"ChatGPT: {_TURNED_DOWN[code]}")
        if code == "subscription_sharing_unsupported_capability":
            what = getattr(error, "param", None) or "part of the request"
            return ProviderError(f"ChatGPT: the plan's route doesn't support {what} ({message})")
        if status == 403:
            return ProviderUnavailable(f"ChatGPT turned the request down ({message})")
        if status == 503:
            return ProviderUnavailable(f"ChatGPT: {_AGAIN_LATER} ({message})")
        return provider_error(error, sdk, self.service)

    def _connect(self, token: str) -> None:
        if self._client_for is not None:
            self._client = self._client_for(token)
        else:
            sdk = import_sdk("openai", "openai")
            # (No retries: the plan's limits aren't to be pushed, and a talk falls back to classic slides instead)
            self._client = sdk.OpenAI(
                api_key=token, base_url=chatgpt_login.API_URL, timeout=TIMEOUT_SECONDS, max_retries=0
            )
        self._token = token

    def _new_client(self, sdk: Any) -> Any:
        self._connect(chatgpt_login.access_token())
        return self._client
