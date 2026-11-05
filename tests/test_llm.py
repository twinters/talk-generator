"""Offline tests of the language model groundwork: choosing a provider, recorded answers, the ledger and budgets."""

import json
import math
import threading

import pytest

from talkgenerator import llm
from talkgenerator.llm import prices
from talkgenerator.llm.base import Capabilities, TextProvider, TextRequest, TextResponse
from talkgenerator.models.deck import Deck
from talkgenerator.models.usage import Usage
from talkgenerator.slide.slide_deck import SlideDeck


class FakeModel(TextProvider):
    """A model that answers "About <prompt>!", in three pieces when streaming, and counts what it's asked."""

    def __init__(self, id="anthropic:claude-haiku-5-5", fail=None, cost_usd=None):
        self.id = id
        self.capabilities = Capabilities(structured_output=True, streaming=True)
        self.requests = []
        self.fail = fail
        self.cost_usd = cost_usd

    def complete(self, request):
        self.requests.append(request)
        if self.fail is not None:
            raise self.fail
        return TextResponse(
            text=f"About {request.messages[-1].content}!",
            input_tokens=1000,
            cached_input_tokens=500,
            output_tokens=200,
            cost_usd=self.cost_usd,
        )

    def stream(self, request, on_text):
        response = self.complete(request)
        third = math.ceil(len(response.text) / 3)
        for start in range(0, len(response.text), third):
            on_text(response.text[start : start + third])
        return response


def _ask(prompt="cats", **options):
    return TextRequest.ask("test", prompt, **options)


# CHOOSING A PROVIDER


def test_without_a_language_model_talks_are_classic(monkeypatch):
    monkeypatch.delenv("TALKGENERATOR_LLM", raising=False)
    provider = llm.from_settings()
    assert isinstance(provider, llm.NoneProvider)
    with pytest.raises(llm.ProviderUnavailable):
        provider.complete(_ask())


def test_disable_llm_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("TALKGENERATOR_LLM", f"replay:{tmp_path / 'talk.json'}")
    assert isinstance(llm.from_settings(), llm.ReplayProvider)
    monkeypatch.setenv("DISABLE_LLM", "1")
    assert isinstance(llm.from_settings(), llm.NoneProvider)


def test_specs(tmp_path):
    replay = llm.provider_from_spec(f" replay: {tmp_path / 'talk.json'} ")
    assert isinstance(replay, llm.ReplayProvider)
    assert replay.path == tmp_path / "talk.json"
    with pytest.raises(ValueError, match="cassette"):
        llm.provider_from_spec("replay")
    with pytest.raises(ValueError, match="choose from: none, replay"):
        llm.provider_from_spec("crystal-ball:9000")


# RECORDED ANSWERS


def test_a_cassette_records_and_replays(tmp_path):
    cassette = tmp_path / "talk.json"
    model = FakeModel()
    recorder = llm.ReplayProvider(cassette, record=model)
    answer = recorder.complete(_ask("cats"))
    assert recorder.complete(_ask("cats")) == answer
    assert len(model.requests) == 1  # the second answer came from the cassette

    replayer = llm.ReplayProvider(cassette)
    assert replayer.complete(_ask("cats")) == answer
    with pytest.raises(llm.CassetteMiss):
        replayer.complete(_ask("dogs"))

    entries = json.loads(cassette.read_text(encoding="utf-8"))["entries"]
    (entry,) = entries.values()
    assert entry["request"]["messages"] == [{"role": "user", "content": "cats"}]
    assert entry["response"]["text"] == "About cats!"
    assert list(entries) == [llm.request_key(_ask("cats"))]


def test_cassettes_dont_depend_on_the_order_of_requests(tmp_path):
    for name, prompts in (("first.json", ["cats", "dogs", "bread"]), ("second.json", ["bread", "cats", "dogs"])):
        recorder = llm.ReplayProvider(tmp_path / name, record=FakeModel())
        for prompt in prompts:
            recorder.complete(_ask(prompt))
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()


def test_request_keys_are_the_same_in_every_process():
    """Changing how requests are keyed would orphan every recorded answer, so it should take changing this test."""
    request = TextRequest.ask("talk plan", "Write a talk about cats", system="Be funny", max_output_tokens=2000)
    assert llm.request_key(request) == "b32f5114c9707bd5029007af27be25aa5b7b2e98e1e9fc96638534a0992a1500"
    assert llm.request_key(request.model_copy(update={"max_output_tokens": 2001})) != llm.request_key(request)


def test_replayed_answers_stream_in_pieces(tmp_path):
    cassette = tmp_path / "talk.json"
    pieces = []
    recorded = llm.ReplayProvider(cassette, record=FakeModel()).stream(_ask("a very long topic indeed"), pieces.append)
    assert len(pieces) == 3  # passed on as the model wrote them
    assert "".join(pieces) == recorded.text

    pieces.clear()
    replayed = llm.ReplayProvider(cassette, chunk_size=5).stream(_ask("a very long topic indeed"), pieces.append)
    assert replayed == recorded
    assert len(pieces) == math.ceil(len(recorded.text) / 5)
    assert "".join(pieces) == recorded.text


def test_a_cassette_of_another_version_is_refused(tmp_path):
    cassette = tmp_path / "old.json"
    cassette.write_text(json.dumps({"cassette_version": 0, "entries": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        llm.ReplayProvider(cassette)


# THE LEDGER


def test_the_ledger_writes_down_every_request():
    ledger = llm.Ledger()
    model = llm.MeteredProvider(FakeModel("anthropic:claude-haiku-5-5"), ledger)
    model.complete(_ask("cats"))
    model.stream(_ask("dogs"), lambda piece: None)

    total = ledger.total()
    assert (total.requests, total.input_tokens, total.cached_input_tokens, total.output_tokens) == (2, 2000, 1000, 400)
    # 1,000 tokens in at $0.10, 500 cached at $0.01 and 200 out at $0.50 per million, twice
    assert total.cost_usd == pytest.approx(2 * (1000 * 0.10 + 500 * 0.01 + 200 * 0.50) / 1e6)
    assert [entry.purpose for entry in ledger.entries] == ["test", "test"]
    assert ledger.summary().startswith("2 language model requests (anthropic:claude-haiku-5-5): 3,000 tokens in")


def test_failed_and_unpriced_requests_count_too():
    ledger = llm.Ledger()
    with pytest.raises(llm.RateLimited):
        llm.MeteredProvider(FakeModel(fail=llm.RateLimited("slow down", retry_after=60)), ledger).complete(_ask())
    llm.MeteredProvider(FakeModel("openai:a-model-of-unknown-price"), ledger).complete(_ask())

    total = ledger.total()
    assert (total.requests, total.failed_requests, total.unpriced_requests) == (2, 1, 1)
    assert ledger.entries[0].error == "slow down"
    assert "1 of unknown price" in ledger.summary()
    assert "1 failed" in ledger.summary()
    assert llm.Ledger().summary() == "No language model requests"


def test_the_cost_a_provider_reports_beats_the_list_price():
    ledger = llm.Ledger()
    llm.MeteredProvider(FakeModel("openai:a-model-of-unknown-price", cost_usd=0.25), ledger).complete(_ask())
    assert (ledger.total().cost_usd, ledger.total().unpriced_requests) == (0.25, 0)


def test_the_ledger_can_be_shared_between_threads():
    ledger = llm.Ledger()
    model = llm.MeteredProvider(FakeModel(), ledger)
    threads = [threading.Thread(target=lambda: [model.complete(_ask()) for _ in range(50)]) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert ledger.total().requests == 400


# BUDGETS


def test_a_zero_budget_lets_only_free_models_through():
    free_only = llm.Budget(max_cost_usd=0)
    for paid in (FakeModel("anthropic:claude-haiku-5-5"), FakeModel("openai:a-model-of-unknown-price")):
        with pytest.raises(llm.BudgetExceeded):
            llm.MeteredProvider(paid, llm.Ledger(), free_only).complete(_ask())
        assert paid.requests == []  # never even asked

    ledger = llm.Ledger()
    llm.MeteredProvider(FakeModel("openrouter:some-lab/some-model:free"), ledger, free_only).complete(_ask())
    llm.MeteredProvider(FakeModel("replay"), ledger, free_only).complete(_ask())
    assert (ledger.total().requests, ledger.total().cost_usd) == (2, 0.0)


def test_budgets_limit_requests_and_dollars():
    ledger = llm.Ledger()
    model = llm.MeteredProvider(FakeModel(), ledger, llm.Budget(max_requests=2))
    model.complete(_ask())
    model.complete(_ask())
    with pytest.raises(llm.BudgetExceeded, match="2 language model requests"):
        model.complete(_ask())
    assert ledger.total().requests == 2

    # The most 4,000 tokens out of Haiku can cost is $0.002: over a budget of a tenth of a cent
    cheap = llm.MeteredProvider(FakeModel(), llm.Ledger(), llm.Budget(max_cost_usd=0.001))
    with pytest.raises(llm.BudgetExceeded):
        cheap.complete(_ask(max_output_tokens=4000))
    assert cheap.complete(_ask(max_output_tokens=1000)).text == "About cats!"


# PRICES


def test_prices():
    assert prices.estimate_cost("anthropic:claude-haiku-5-5", 100_000, 0, 0) == pytest.approx(0.01)
    # Above 100K tokens of prompt, Haiku costs more
    assert prices.estimate_cost("anthropic:claude-haiku-5-5", 200_000, 0, 1_000_000) == pytest.approx(0.10 + 2.50)
    assert prices.estimate_cost("anthropic:claude-opus-5-5", 0, 1_000_000, 1_000_000) == pytest.approx(0.20 + 20.00)
    assert prices.estimate_cost("openrouter:some-lab/some-model:free", 10**9, 0, 10**9) == 0.0
    assert prices.estimate_cost("openrouter:some-lab/some-model", 1, 0, 1) is None
    with_schema = _ask(json_schema={"type": "object", "properties": {"title": {"type": "string"}}})
    assert prices.worst_case_cost("anthropic:claude-opus-5-5", with_schema) > prices.worst_case_cost(
        "anthropic:claude-opus-5-5", _ask()
    )


# THE DECK


def test_a_deck_tells_what_its_talk_asked_of_language_models():
    assert Deck(generator="test").usage == Usage()
    slide_deck = SlideDeck(0)
    slide_deck.usage = Usage(requests=1, output_tokens=10) + Usage(requests=2, cost_usd=0.5)
    deck = slide_deck.to_deck()
    assert deck.usage == Usage(requests=3, output_tokens=10, cost_usd=0.5)
    assert json.loads(deck.to_json())["usage"]["requests"] == 3
