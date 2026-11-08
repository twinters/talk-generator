"""Offline tests of the language model providers: the real SDKs, talking to a fake HTTP transport.

The fake API answers the way the real one streams (server-sent events). The tests check what each adapter sends,
and how it reads the answer: the text in pieces, how the answer ended, its usage and cost, and errors, which all
become ProviderErrors (without keys in their messages).
"""

import json
import logging
import sys

import anthropic
import httpx2
import openai
import pytest

from talkgenerator import generator, llm, settings
from talkgenerator.llm import prices
from talkgenerator.llm.base import ProviderError, ProviderUnavailable, RateLimited, TextRequest
from talkgenerator.util import http_util

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


class Api:
    """A fake API: answers requests with the given responses (the last one again and again), and keeps them."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    @property
    def body(self):
        return json.loads(self.requests[-1].content)

    @property
    def headers(self):
        return self.requests[-1].headers


def _stream(events, *, named=True, done=False):
    body = "".join(
        (f"event: {event['type']}\n" if named else "") + f"data: {json.dumps(event)}\n\n" for event in events
    )
    if done:
        body += "data: [DONE]\n\n"
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


def _error(status, message="it went wrong", headers=None):
    return httpx2.Response(status, headers=headers or {}, json={"error": {"type": "error", "message": message}})


def _transport(api):
    return httpx2.MockTransport(api)


# CLAUDE


def _claude(api, model="claude-opus-5-5", **options):
    client = anthropic.Anthropic(
        api_key="sk-ant-test-key-0000000000",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=_transport(api)),
    )
    return llm.ClaudeProvider(model, client=client, **options)


def _claude_answer(*texts, stop_reason="end_turn", model="claude-opus-5-5", usage=None, before=(), index=0):
    """A streamed message: its text in a block at the given index, after the events before it."""
    events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 1000, "output_tokens": 1},
            },
        },
        *before,
        {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}},
        *(
            {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": text}}
            for text in texts
        ),
        {"type": "content_block_stop", "index": index},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": usage or {"output_tokens": 300},
        },
        {"type": "message_stop"},
    ]
    return _stream(events)


def test_claude_writes_with_structured_outputs_low_effort_and_fallbacks():
    api = Api(_claude_answer(*ANSWER))
    pieces = []
    response = _claude(api).stream(REQUEST, pieces.append)

    body = api.body
    assert body["model"] == "claude-opus-5-5"
    assert body["max_tokens"] == 1000 + 4000  # room to think at low effort
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert body["system"] == [{"type": "text", "text": "You write talks.", "cache_control": {"type": "ephemeral"}}]
    assert body["messages"] == [{"role": "user", "content": "Topic: cats"}]
    assert body["fallbacks"] == "default"
    assert api.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert not {"temperature", "top_p", "top_k", "thinking"} & set(body)

    assert pieces == list(ANSWER)
    assert (response.text, response.data) == ('{"title": "Cats"}', {"title": "Cats"})
    assert (response.finish, response.model) == ("complete", "anthropic:claude-opus-5-5")
    assert (response.input_tokens, response.output_tokens) == (1000, 300)
    assert response.cost_usd == pytest.approx((1000 * 4.00 + 300 * 20.00) / 1e6)


def test_claude_gets_the_schema_as_text_when_anthropic_finds_its_grammar_too_large(caplog, monkeypatch):
    # (Anthropic's answer to a talk of many kinds of slides, Claude Haiku 5.5, 2026-11-08)
    monkeypatch.setattr(logging.getLogger("talkgenerator"), "propagate", True)  # (the command line turns it off)
    too_large = (
        "The compiled grammar is too large, which would cause performance issues. Simplify your tool schemas or "
        "reduce the number of strict tools."
    )
    api = Api(_error(400, too_large), _claude_answer(*ANSWER))
    pieces = []
    with caplog.at_level("INFO", logger="talkgenerator"):
        response = _claude(api).stream(REQUEST, pieces.append)
    # (said in the log: nothing then holds the answer to the schema's shape)
    assert [record.getMessage() for record in caplog.records if "too large a grammar" in record.getMessage()] == [
        "Anthropic found the answer's schema too large a grammar: anthropic:claude-opus-5-5 gets it as text"
    ]

    held, written = (json.loads(request.content) for request in api.requests)
    assert held["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert written["output_config"] == {"effort": "low"}
    content = written["messages"][-1]["content"]
    assert content.startswith("Topic: cats\n\n") and content.endswith(json.dumps(SCHEMA, separators=(",", ":")))
    assert pieces == list(ANSWER) and response.data == {"title": "Cats"}


def test_claude_asks_once_and_never_again_for_other_bad_requests():
    api = Api(_error(400, "messages: at least one message is required"))
    with pytest.raises(ProviderError, match="at least one message"):
        _claude(api).complete(REQUEST)
    assert len(api.requests) == 1


def test_claude_haiku_has_no_server_side_fallbacks():
    api = Api(_claude_answer("{}", model="claude-haiku-5-5"))
    _claude(api, "claude-haiku-5-5", effort="medium").complete(REQUEST)
    assert "fallbacks" not in api.body and "anthropic-beta" not in api.headers
    assert api.body["output_config"]["effort"] == "medium"


def test_a_declined_answer_goes_on_with_the_fallback_model():
    declined = {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": ANSWER[0]}}
    before = (
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        declined,
        {"type": "content_block_stop", "index": 0},
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "fallback",
                "from": {"model": "claude-opus-5-5"},
                "to": {"model": "claude-opus-5"},
                "trigger": {"type": "refusal", "category": "cyber"},
            },
        },
        {"type": "content_block_stop", "index": 1},
    )
    attempts = [
        {"type": "message", "model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 10},
        {"type": "fallback_message", "model": "claude-opus-5", "input_tokens": 1010, "output_tokens": 290},
    ]
    attempts = [{**attempt, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0} for attempt in attempts]
    usage = {"output_tokens": 290, "iterations": attempts}
    # The declined model's text and the fallback block come first; the fallback model goes on in block 2
    answer = _claude_answer(ANSWER[1], usage=usage, before=before, index=2)
    pieces = []
    response = _claude(Api(answer)).stream(REQUEST, pieces.append)

    assert pieces == list(ANSWER)
    assert response.text == '{"title": "Cats"}'
    assert (response.finish, response.model) == ("complete", "anthropic:claude-opus-5")
    assert (response.input_tokens, response.output_tokens) == (2010, 300)
    expected = (1000 * 4.00 + 10 * 20.00) / 1e6 + (1010 * 5.00 + 290 * 25.00) / 1e6
    assert response.cost_usd == pytest.approx(expected)


@pytest.mark.parametrize(("stop_reason", "finish"), [("refusal", "refused"), ("max_tokens", "truncated")])
def test_how_a_claude_answer_ended(stop_reason, finish):
    response = _claude(Api(_claude_answer(ANSWER[0], stop_reason=stop_reason))).complete(REQUEST)
    assert response.finish == finish


def test_claude_errors_are_provider_errors():
    limited = _claude(Api(_error(429, "slow down", {"retry-after": "7"})))
    with pytest.raises(RateLimited) as error:
        limited.complete(REQUEST)
    assert error.value.retry_after == 7.0
    with pytest.raises(ProviderUnavailable, match="refused the key"):
        _claude(Api(_error(401))).complete(REQUEST)
    with pytest.raises(ProviderUnavailable):
        _claude(Api(_error(529, "Overloaded"))).complete(REQUEST)
    broken = _stream([{"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}])
    with pytest.raises(ProviderError):
        _claude(Api(broken)).complete(REQUEST)


def test_claude_needs_a_key():
    with pytest.raises(ProviderUnavailable, match="ANTHROPIC_API_KEY"):
        llm.ClaudeProvider().complete(REQUEST)


# OPENROUTER


def _openrouter(api, models=()):
    client = openai.OpenAI(
        api_key="sk-or-v1-test-key-000000000000",
        base_url=llm.openrouter.API_URL,
        default_headers=llm.openrouter.APP_HEADERS,
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=_transport(api)),
    )
    return llm.OpenRouterProvider(models, client=client)


def _chunk(content=None, finish=None, model="vendor/some-model:free", usage=None):
    chunk = {
        "id": "gen-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": model,
        "choices": [{"index": 0, "delta": {"content": content or ""}, "finish_reason": finish}],
    }
    if usage is not None:
        chunk["usage"] = usage
    return chunk


def _openrouter_answer(*texts, finish="stop", usage=None):
    usage = usage or {"prompt_tokens": 1200, "completion_tokens": 700, "total_tokens": 1900, "cost": 0}
    chunks = [_chunk(text) for text in texts] + [_chunk(finish=finish), _chunk(finish=finish, usage=usage)]
    return _stream(chunks, named=False, done=True)


def test_openrouter_writes_to_the_schema_with_the_free_router():
    api = Api(_openrouter_answer(*ANSWER))
    pieces = []
    provider = _openrouter(api)
    response = provider.stream(REQUEST, pieces.append)

    assert str(api.requests[-1].url) == "https://openrouter.ai/api/v1/chat/completions"
    body = api.body
    assert body["model"] == "openrouter/free"
    assert body["messages"] == [
        {"role": "system", "content": "You write talks."},
        {"role": "user", "content": "Topic: cats"},
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "strict": True, "schema": SCHEMA},
    }
    assert body["provider"] == {"require_parameters": True}
    assert body["max_tokens"] == 1000 + 8000
    assert body["stream"] is True
    assert body["reasoning"] == {"effort": "none"}  # thinking first took the free models minutes
    assert "models" not in body
    assert api.headers["HTTP-Referer"].startswith("https://github.com/")
    assert api.headers["X-OpenRouter-Title"] == "talkgenerator"

    assert pieces == list(ANSWER)
    assert (response.data, response.finish) == ({"title": "Cats"}, "complete")
    assert response.model == "openrouter:vendor/some-model:free"
    assert (response.input_tokens, response.output_tokens, response.cost_usd) == (1200, 700, 0.0)


def test_openrouter_falls_back_to_the_models_after_the_first(monkeypatch):
    api = Api(_openrouter_answer("{}"))
    provider = _openrouter(api, ["vendor/a:free", "vendor/b:free"])
    provider.complete(REQUEST)
    assert (api.body["model"], api.body["models"]) == ("vendor/a:free", ["vendor/b:free"])
    assert provider.possible_models() == ("openrouter:vendor/a:free", "openrouter:vendor/b:free")
    # Models named in the spec may not reason at all: they only get an effort when it's set
    assert "reasoning" not in api.body
    monkeypatch.setenv("TALKGENERATOR_LLM_EFFORT", "medium")
    provider.complete(REQUEST)
    assert api.body["reasoning"] == {"effort": "medium"}


def test_a_model_that_has_to_think_gets_the_request_again_at_minimal_effort():
    mandatory = _error(400, "Reasoning is mandatory for this endpoint and cannot be disabled.")
    api = Api(mandatory, _openrouter_answer(*ANSWER))
    response = _openrouter(api).complete(REQUEST)
    assert response.data == {"title": "Cats"}
    efforts = [json.loads(request.content)["reasoning"] for request in api.requests]
    assert efforts == [{"effort": "none"}, {"effort": "minimal"}]


def test_other_bad_requests_arent_sent_again():
    api = Api(_error(400, "Invalid schema"), _openrouter_answer(*ANSWER))
    with pytest.raises(ProviderError, match="Invalid schema"):
        _openrouter(api).complete(REQUEST)
    assert len(api.requests) == 1


def _failed_stream(message):
    return _stream([{**_chunk(finish="error"), "error": {"code": 408, "message": message}}], named=False)


def test_a_model_whose_provider_fails_before_it_writes_gets_one_more_try():
    api = Api(_failed_stream("Provider timed out after 11796ms"), _openrouter_answer(*ANSWER))
    assert _openrouter(api).complete(REQUEST).data == {"title": "Cats"}
    assert len(api.requests) == 2
    api = Api(_error(502, "Provider returned error"), _openrouter_answer(*ANSWER))
    assert _openrouter(api).complete(REQUEST).data == {"title": "Cats"}


def test_but_only_one():
    api = Api(_failed_stream("Provider timed out"), _failed_stream("Provider timed out"), _openrouter_answer(*ANSWER))
    with pytest.raises(ProviderUnavailable, match="Provider timed out"):
        _openrouter(api).complete(REQUEST)
    assert len(api.requests) == 2


def test_openrouter_reports_cached_tokens_and_cost():
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 100,
        "total_tokens": 1100,
        "prompt_tokens_details": {"cached_tokens": 400},
        "cost": 0.0123,
    }
    response = _openrouter(Api(_openrouter_answer("{}", usage=usage))).complete(REQUEST)
    assert (response.input_tokens, response.cached_input_tokens, response.cost_usd) == (600, 400, 0.0123)


@pytest.mark.parametrize(
    ("finish", "ending"), [("length", "truncated"), ("content_filter", "refused"), (None, "truncated")]
)
def test_how_an_openrouter_answer_ended(finish, ending):
    chunks = [_chunk(ANSWER[0]), _chunk(finish=finish)] if finish else [_chunk(ANSWER[0])]
    response = _openrouter(Api(_stream(chunks, named=False, done=True))).complete(REQUEST)
    assert response.finish == ending


def test_openrouter_errors_are_provider_errors():
    with pytest.raises(RateLimited):
        _openrouter(Api(_error(429, "Rate limit exceeded: free-models-per-day"))).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="credits"):
        _openrouter(Api(_error(402, "Insufficient credits"))).complete(REQUEST)
    broken = {**_chunk(finish="error"), "error": {"code": "server_error", "message": "Provider disconnected"}}
    with pytest.raises(ProviderError, match="Provider disconnected"):
        _openrouter(Api(_stream([_chunk(ANSWER[0]), broken], named=False))).complete(REQUEST)


def test_openrouter_needs_a_key():
    with pytest.raises(ProviderUnavailable, match="OPENROUTER_API_KEY"):
        llm.OpenRouterProvider().complete(REQUEST)


# OPENAI


def _openai(api, model="gpt-test"):
    client = openai.OpenAI(
        api_key="sk-proj-test-key-0000000000",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=_transport(api)),
    )
    return llm.OpenAIProvider(model, client=client)


def _response_event(kind, status, **response):
    usage = {
        "input_tokens": 900,
        "input_tokens_details": {"cached_tokens": 100},
        "output_tokens": 400,
        "output_tokens_details": {"reasoning_tokens": 50},
        "total_tokens": 1300,
    }
    body = {"id": "resp_1", "object": "response", "created_at": 1, "model": "gpt-test-2026", "output": []}
    return {"type": kind, "sequence_number": 9, "response": {**body, "status": status, "usage": usage, **response}}


def _openai_answer(*texts, final=None):
    deltas = [
        {
            "type": "response.output_text.delta",
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "delta": text,
            "sequence_number": number,
            "logprobs": [],
        }
        for number, text in enumerate(texts, 1)
    ]
    return _stream([*deltas, final or _response_event("response.completed", "completed")])


def test_openai_writes_to_the_schema_through_the_responses_api():
    api = Api(_openai_answer(*ANSWER))
    pieces = []
    response = _openai(api).stream(REQUEST, pieces.append)

    assert str(api.requests[-1].url) == "https://api.openai.com/v1/responses"
    body = api.body
    assert (body["model"], body["instructions"], body["store"], body["stream"]) == (
        "gpt-test",
        "You write talks.",
        False,
        True,
    )
    assert body["input"] == [{"role": "user", "content": "Topic: cats"}]
    assert body["text"] == {"format": {"type": "json_schema", "name": "answer", "schema": SCHEMA, "strict": True}}
    assert body["max_output_tokens"] == 1000 + 8000
    assert "reasoning" not in body

    assert pieces == list(ANSWER)
    assert (response.data, response.finish, response.model) == ({"title": "Cats"}, "complete", "openai:gpt-test-2026")
    assert (response.input_tokens, response.cached_input_tokens, response.output_tokens) == (800, 100, 400)


def test_how_an_openai_answer_ended():
    cut_off = _response_event("response.incomplete", "incomplete", incomplete_details={"reason": "max_output_tokens"})
    assert _openai(Api(_openai_answer(ANSWER[0], final=cut_off))).complete(REQUEST).finish == "truncated"
    refusal = {
        "type": "response.refusal.delta",
        "item_id": "msg_1",
        "output_index": 0,
        "content_index": 0,
        "delta": "I can't help with that.",
        "sequence_number": 1,
    }
    refused = _stream([refusal, _response_event("response.completed", "completed")])
    assert _openai(Api(refused)).complete(REQUEST).finish == "refused"
    failed = _response_event("response.failed", "failed", error={"code": "server_error", "message": "it broke"})
    with pytest.raises(ProviderError, match="it broke"):
        _openai(Api(_openai_answer(ANSWER[0], final=failed))).complete(REQUEST)


def test_openai_needs_a_model_and_a_key():
    with pytest.raises(ValueError, match="openai:"):
        llm.provider_from_spec("openai")
    with pytest.raises(ProviderUnavailable, match="OPENAI_API_KEY"):
        llm.provider_from_spec("openai:gpt-test").complete(REQUEST)


# CHOOSING A PROVIDER


def test_specs_name_the_provider_and_its_models():
    assert llm.provider_from_spec("openrouter").id == "openrouter:openrouter/free"
    fallbacks = llm.provider_from_spec("openrouter:google/gemma-4-31b-it:free, vendor/b:free")
    assert fallbacks.models == ("google/gemma-4-31b-it:free", "vendor/b:free")
    assert llm.provider_from_spec("anthropic").id == "anthropic:claude-opus-5-5"
    assert llm.provider_from_spec("anthropic:claude-haiku-5-5").id == "anthropic:claude-haiku-5-5"
    assert llm.provider_from_spec("openai:gpt-test").id == "openai:gpt-test"


@pytest.mark.parametrize(("spec", "message"), [("openai", "Name the OpenAI model"), ("gpt", "Unknown")])
def test_the_command_refuses_a_model_it_cant_use(capsys, spec, message):
    with pytest.raises(SystemExit):
        generator.get_argument_parser().parse_args(["--llm", spec])
    assert message in capsys.readouterr().err


def test_by_default_only_free_models_write_talks(monkeypatch):
    assert settings.llm_spec() == "none"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-0000000000")
    assert settings.llm_spec() == "none"  # a paid model writes talks only when it's asked for
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test-key-000000000000")
    assert settings.llm_spec() == "openrouter"
    monkeypatch.setenv("TALKGENERATOR_LLM", "anthropic:claude-haiku-5-5")
    assert settings.llm_spec() == "anthropic:claude-haiku-5-5"
    monkeypatch.setenv("DISABLE_LLM", "1")
    assert settings.llm_spec() == "none"


def test_free_models_cost_nothing():
    assert prices.price_of("openrouter:openrouter/free") == prices.FREE
    assert prices.price_of("openrouter:vendor/model:free") == prices.FREE
    assert prices.price_of("openrouter:vendor/model") is None


def test_a_free_budget_keeps_out_fallbacks_that_may_cost(monkeypatch):
    ledger = llm.Ledger()
    free = llm.MeteredProvider(_openrouter(Api(_openrouter_answer("{}"))), ledger, llm.Budget(max_cost_usd=0))
    assert free.complete(REQUEST).text == "{}"
    paid = _openrouter(Api(_openrouter_answer("{}")), ["vendor/a:free", "vendor/paid-model"])
    with pytest.raises(llm.BudgetExceeded, match="vendor/paid-model"):
        llm.MeteredProvider(paid, ledger, llm.Budget(max_cost_usd=0)).complete(REQUEST)


def test_budgets_leave_room_for_thinking():
    # The 1,000 tokens the answer may take cost $0.02 at Claude Opus 5.5's price, but thinking may add 4,000 more
    claude = llm.ClaudeProvider("claude-opus-5-5", client=object())
    with pytest.raises(llm.BudgetExceeded):
        llm.MeteredProvider(claude, llm.Ledger(), llm.Budget(max_cost_usd=0.05)).complete(REQUEST)


@pytest.mark.parametrize(("module", "provider"), [("anthropic", "anthropic"), ("openai", "openrouter")])
def test_without_its_sdk_a_provider_says_how_to_install_it(monkeypatch, module, provider):
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ProviderUnavailable, match=rf"talkgenerator\[{module}\]"):
        llm.provider_from_spec(provider).complete(REQUEST)


def test_keys_never_show_up_in_messages():
    message = (
        "Error with sk-or-v1-0123456789abcdef0123456789abcdef and sk-ant-api03-abcdefghijklmnopqrstuvwx, "
        "header Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789"
    )
    redacted = http_util.redact(message)
    assert "0123456789abcdef" not in redacted and "abcdefghijklmnop" not in redacted
    assert redacted.count("REDACTED") == 3
