"""Offline tests of Gemini's provider: Google's google-genai SDK, talking to a fake HTTP transport that answers the way
the Gemini API streams (server-sent events of GenerateContentResponses), as tests/test_llm_providers.py does for the
other providers. (The SDK isn't installed on Windows on Arm, where these skip: see pyproject.toml.)
"""

import base64
import json
import logging
from datetime import date
from types import SimpleNamespace

import httpx2
import pytest

from talkgenerator import generator, llm
from talkgenerator.llm import gemini, prices
from talkgenerator.llm.base import ImagePart, ProviderError, ProviderUnavailable, RateLimited, TextRequest
from talkgenerator.plan import outline
from talkgenerator.util import http_util

genai = pytest.importorskip("google.genai")

KEY = "AIzaSyTest-Key_000000000000000000000000"
SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
    "additionalProperties": False,
}
REQUEST = TextRequest.ask(
    "talk plan", "Topic: cats", system="You write talks.", json_schema=SCHEMA, max_output_tokens=1000
)
ANSWER = ('{"title": ', '"Cats"}')
USAGE = {
    "promptTokenCount": 1000,
    "cachedContentTokenCount": 200,
    "candidatesTokenCount": 300,
    "thoughtsTokenCount": 50,
    "totalTokenCount": 1350,
}
# (Gemini's answer to a schema of too many slides' kinds, as it worded it for Gemini 2.0 and later)
TOO_COMPLEX = (
    "The specified schema produces a constraint that has too many states for serving. Typical causes of this error are "
    "schemas with lots of text (for example, very long property or enum names)"
)


class Api:
    """A fake Gemini API: answers requests with the given responses (the last one again and again), and keeps them."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def body(self):
        return json.loads(self.requests[-1].content)


def _provider(api, model="gemini-3.8-flash", **options):
    http_client = httpx2.Client(transport=httpx2.MockTransport(api))
    client = genai.Client(api_key=KEY, http_options={"httpx_client": http_client})
    return llm.GeminiProvider(model, client=client, **options)


def _chunk(*texts, finish=None, usage=None, model="gemini-3.8-flash", thought=None):
    parts = [{"text": text} for text in texts]
    if thought:
        parts.insert(0, {"text": thought, "thought": True})
    candidate = {"content": {"role": "model", "parts": parts}, "index": 0}
    if finish:
        candidate["finishReason"] = finish
    chunk = {"candidates": [candidate], "modelVersion": model, "responseId": "response-1"}
    if usage:
        chunk["usageMetadata"] = usage
    return chunk


def _stream(*chunks):
    body = "".join(f"data: {json.dumps(chunk)}\r\n\r\n" for chunk in chunks)
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


def _answer(*texts, finish="STOP", usage=None, model="gemini-3.8-flash"):
    """A streamed answer: its text in pieces, the last of which tells how it ended and what it used."""
    *first, last = texts or ("",)
    ending = _chunk(last, finish=finish, usage=usage or USAGE, model=model)
    return _stream(*(_chunk(text, model=model) for text in first), ending)


def _error(code, status, message="it went wrong", details=None):
    error = {"code": code, "message": message, "status": status}
    if details:
        error["details"] = details
    return httpx2.Response(code, json={"error": error})


def test_gemini_writes_to_the_schema_with_low_thinking():
    api = Api(_answer(*ANSWER))
    pieces = []
    response = _provider(api).stream(REQUEST, pieces.append)

    request = api.requests[-1]
    assert request.url.path.endswith("/models/gemini-3.8-flash:streamGenerateContent")
    assert request.url.params["alt"] == "sse"
    assert request.headers["x-goog-api-key"] == KEY
    body = api.body
    assert body["contents"] == [{"role": "user", "parts": [{"text": "Topic: cats"}]}]
    assert [part["text"] for part in body["systemInstruction"]["parts"]] == ["You write talks."]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == SCHEMA
    assert config["maxOutputTokens"] == 1000 + 4000  # room to think, at a low level
    # (The SDK writes this field as thinking_level, which the API takes as it takes thinkingLevel)
    assert list(config["thinkingConfig"].values()) == ["LOW"]
    assert not {"temperature", "topP", "topK", "seed"} & set(config)

    assert pieces == list(ANSWER)
    assert (response.text, response.data) == ('{"title": "Cats"}', {"title": "Cats"})
    assert (response.finish, response.model) == ("complete", "gemini:gemini-3.8-flash")
    # The prompt's cached part apart, and the thinking counted as output (as it's billed)
    assert (response.input_tokens, response.cached_input_tokens, response.output_tokens) == (800, 200, 350)
    assert response.cost_usd == pytest.approx(prices.estimate_cost("gemini:gemini-3.8-flash", 800, 200, 350))
    assert response.cost_usd > 0


def test_its_thoughts_stay_out_of_the_answer():
    api = Api(_stream(_chunk(ANSWER[0], thought="Cats, then."), _chunk(ANSWER[1], finish="STOP", usage=USAGE)))
    pieces = []
    response = _provider(api).stream(REQUEST, pieces.append)
    assert pieces == list(ANSWER) and response.data == {"title": "Cats"}


def test_gemini_gets_the_schema_as_text_when_it_finds_the_schema_too_complex(caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger("talkgenerator"), "propagate", True)  # (the command line turns it off)
    api = Api(_error(400, "INVALID_ARGUMENT", TOO_COMPLEX), _answer(*ANSWER))
    pieces = []
    with caplog.at_level("INFO", logger="talkgenerator"):
        response = _provider(api).stream(REQUEST, pieces.append)
    assert "Gemini found the answer's schema too complex: gemini:gemini-3.8-flash gets it as text" in caplog.messages

    held, written = (json.loads(request.content) for request in api.requests)
    assert held["generationConfig"]["responseJsonSchema"] == SCHEMA
    assert "responseJsonSchema" not in written["generationConfig"]
    assert written["generationConfig"]["responseMimeType"] == "application/json"  # (JSON, without its shape)
    text = written["contents"][-1]["parts"][-1]["text"]
    assert text.startswith("Topic: cats\n\n") and text.endswith(json.dumps(SCHEMA, separators=(",", ":")))
    assert pieces == list(ANSWER) and response.data == {"title": "Cats"}


def test_gemini_asks_once_and_never_again_for_other_bad_requests():
    api = Api(_error(400, "INVALID_ARGUMENT", "Invalid value at 'contents[0].parts'"))
    with pytest.raises(ProviderError, match="Invalid value"):
        _provider(api).complete(REQUEST)
    assert len(api.requests) == 1


def test_messages_show_their_pictures_first_and_answers_are_the_models():
    picture = ImagePart(data=b"\xff\xd8 a jpeg", width=8, height=8, name="sheet")
    request = TextRequest(
        purpose="vision pick",
        messages=(
            llm.Message(role="user", content="Which one?", images=(picture,)),
            llm.Message(role="assistant", content="The cat."),
            llm.Message(role="user", content="Why?"),
        ),
    )
    api = Api(_answer("Because."))
    response = _provider(api).complete(request)
    first, answer, last = api.body["contents"]
    assert first["role"] == "user" and first["parts"][1] == {"text": "Which one?"}
    # (The SDK writes the picture's bytes in URL-safe base64, and mime_type as such: the API takes both)
    inline = first["parts"][0]["inlineData"]
    assert base64.urlsafe_b64decode(inline["data"]) == picture.data and "image/jpeg" in inline.values()
    assert (answer["role"], last["role"]) == ("model", "user")
    assert "responseMimeType" not in api.body["generationConfig"]  # (no schema: text)
    assert (response.text, response.data) == ("Because.", None)


@pytest.mark.parametrize(
    ("finish", "ending"),
    [("MAX_TOKENS", "truncated"), ("SAFETY", "refused"), ("RECITATION", "refused"), (None, "truncated")],
)
def test_how_a_gemini_answer_ended(finish, ending):
    response = _provider(Api(_answer(ANSWER[0], finish=finish))).complete(REQUEST)
    assert response.finish == ending


def test_a_prompt_gemini_blocks_is_refused():
    blocked = {"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}, "usageMetadata": {"promptTokenCount": 10}}
    response = _provider(Api(_stream(blocked))).complete(REQUEST)
    assert (response.finish, response.text, response.data) == ("refused", "", None)


def test_gemini_errors_are_provider_errors():
    retry = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]
    quota = "You exceeded your current quota. Quota exceeded for metric: generate_content_free_tier_requests"
    with pytest.raises(RateLimited, match="exceeded your current quota") as error:
        _provider(Api(_error(429, "RESOURCE_EXHAUSTED", quota, retry))).complete(REQUEST)
    assert error.value.retry_after == 37.0
    invalid_key = _error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.")
    with pytest.raises(ProviderUnavailable, match="refused the key"):
        _provider(Api(invalid_key)).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="refused the key"):
        _provider(Api(_error(403, "PERMISSION_DENIED"))).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="doesn't know that model"):
        _provider(Api(_error(404, "NOT_FOUND", "models/gemini-9 is not found"))).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="had a problem"):
        _provider(Api(_error(503, "UNAVAILABLE", "The model is overloaded."))).complete(REQUEST)
    where = _error(400, "FAILED_PRECONDITION", "User location is not supported for the API use.")
    with pytest.raises(ProviderUnavailable, match="User location"):
        _provider(Api(where)).complete(REQUEST)
    broken = _stream(_chunk(ANSWER[0]), {"error": {"code": 500, "message": "Internal error", "status": "INTERNAL"}})
    with pytest.raises(ProviderError, match="Internal error"):
        _provider(Api(broken)).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="can't be reached"):
        _provider(Api(httpx2.ConnectError("no route to host"))).complete(REQUEST)


def test_keys_stay_out_of_its_errors():
    leaky = _error(400, "INVALID_ARGUMENT", f"Bad key {KEY} in the request")
    with pytest.raises(ProviderError) as error:
        _provider(Api(leaky)).complete(REQUEST)
    assert KEY not in str(error.value) and "REDACTED" in str(error.value)
    assert http_util.redact(f"key={KEY}") == "key=REDACTED"
    assert KEY not in http_util.redact(f"the key {KEY}, again")
    # (AI Studio's keys since 2026-05-28, "auth keys", bound to a service account, are of another form)
    auth_key = "AQ." + "Ab8RN6Lmade-up_test-value" * 2
    assert http_util.redact(f"the key {auth_key}, again") == "the key REDACTED, again"


def test_gemini_needs_a_key():
    with pytest.raises(ProviderUnavailable, match="GEMINI_API_KEY"):
        llm.GeminiProvider().complete(REQUEST)


def test_talks_make_its_clients_wait_and_retry_as_the_other_providers_do():
    made = gemini.new_client(KEY, SimpleNamespace(Client=lambda **arguments: arguments))
    assert made == {"api_key": KEY, "http_options": {"timeout": 120_000, "retry_options": {"attempts": 2}}}
    real = gemini.new_client(KEY)
    assert isinstance(real, genai.Client)


@pytest.mark.parametrize(
    ("model", "effort", "level", "room"),
    [
        ("gemini-3.8-flash", None, "low", 4000),
        ("gemini-3.5-flash-lite", "minimal", "minimal", 2000),
        ("gemini-4-argon", "high", "high", 16000),
        ("gemini-4-argon", "max", "high", 16000),  # (Claude's efforts, as Gemini's levels)
        ("gemini-3.6-flash", "none", "minimal", 2000),
        ("gemini-3.8-flash", "minimal", "low", 4000),  # (which thinks at least at low)
        ("gemini-2.5-flash-lite", "high", None, 4000),  # (Gemini 2.5 takes a budget, not a level: none is sent)
    ],
)
def test_the_effort_is_its_thinking_level(monkeypatch, model, effort, level, room):
    if effort:
        monkeypatch.setenv("TALKGENERATOR_LLM_EFFORT", effort)
    provider = llm.GeminiProvider(model, client=object())
    assert provider.thinking_level == level
    assert provider.max_output_tokens(REQUEST) == 1000 + room
    config = provider.arguments(REQUEST)["config"]
    assert config.get("thinking_config") == ({"thinking_level": level} if level else None)


def test_specs_name_gemini_and_its_models():
    assert llm.provider_from_spec("gemini").id == "gemini:gemini-3.8-flash"
    assert llm.provider_from_spec("gemini:gemini-3.5-flash-lite").id == "gemini:gemini-3.5-flash-lite"
    assert llm.provider_from_spec("gemini:models/gemini-4-argon").id == "gemini:gemini-4-argon"
    assert generator.get_argument_parser().parse_args(["--llm", "gemini"]).llm == "gemini"


def test_a_gemini_model_is_advanced_by_default():
    assert outline.default_level(llm.GeminiProvider(client=object())) == outline.ADVANCED


def test_gemini_prices_go_up_when_their_introductory_prices_end():
    assert prices.price_of("gemini:gemini-3.8-flash", date(2026, 12, 31)) == prices.Price(0.75, 3.75, 0.075)
    assert prices.price_of("gemini:gemini-3.8-flash", date(2027, 1, 1)) == prices.Price(1.50, 7.50, 0.15)
    assert prices.price_of("gemini:gemini-4-argon", date(2026, 11, 30)).input == 2.00
    assert prices.price_of("gemini:gemini-4-argon", date(2026, 12, 1)).input == 4.00
    assert prices.price_of("gemini:gemini-3.5-flash-lite", date(2030, 1, 1)) == prices.Price(0.30, 2.50, 0.03)
    # A model that isn't in the table has no known price: a budget keeps it out
    assert prices.price_of("gemini:gemini-9-ultra") is None


def test_a_version_of_a_model_is_priced_as_the_model():
    api = Api(_answer(*ANSWER, model="gemini-3.5-flash-lite-001"))
    response = _provider(api, "gemini-3.5-flash-lite").complete(REQUEST)
    assert response.model == "gemini:gemini-3.5-flash-lite-001"
    assert response.cost_usd == pytest.approx(prices.estimate_cost("gemini:gemini-3.5-flash-lite", 800, 200, 350))


def test_budgets_hold_gemini_to_its_price():
    free = llm.MeteredProvider(_provider(Api(_answer("{}"))), llm.Ledger(), llm.Budget(max_cost_usd=0))
    with pytest.raises(llm.BudgetExceeded):
        free.complete(REQUEST)
    ledger = llm.Ledger()
    llm.MeteredProvider(_provider(Api(_answer(*ANSWER))), ledger, llm.Budget(max_cost_usd=1)).complete(REQUEST)
    assert ledger.total().cost_usd == pytest.approx(prices.estimate_cost("gemini:gemini-3.8-flash", 800, 200, 350))
