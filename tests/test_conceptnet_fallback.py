"""Offline tests: the ConceptNet module falls back to Datamuse when the ConceptNet API is unavailable."""

import pytest

from talkgenerator.sources import conceptnet, datamuse
from talkgenerator.util import http_util


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        raise ValueError("not json")


_DATAMUSE_ANSWERS = {
    ("rel_trg", "cat"): (("kitten", 1000), ("mouse", 800), ("cats", 700), ("litter", 100)),
    ("rel_jjb", "cat"): (("black", 500), ("lazy", 250)),
    ("rel_ant", "hot"): (("cold", 100),),
}


@pytest.fixture
def conceptnet_down(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(502)

    monkeypatch.setattr(http_util, "get", fake_get)
    monkeypatch.setattr(conceptnet, "_cooldown", http_util.Cooldown("ConceptNet API (test)"))
    conceptnet._fetch_edges.cache_clear()
    monkeypatch.setattr(datamuse, "_query", lambda relation, word, max_results: _DATAMUSE_ANSWERS.get((relation, word), ()))
    return calls


def test_related_words_fall_back_to_datamuse(conceptnet_down):
    related = conceptnet.get_weighted_related_words("cat", 10)
    words = [word for _, word in related]
    assert "kitten" in words
    assert "cats" not in words  # too similar to the word itself
    assert all(0 < weight <= 10 for weight, _ in related)


def test_conceptnet_is_not_retried_while_down(conceptnet_down):
    conceptnet.get_weighted_related_words("cat", 10)
    conceptnet.get_weighted_properties("cat")
    conceptnet.get_weighted_antonyms("hot")
    assert len(conceptnet_down) == 1


def test_lookups_never_return_none(conceptnet_down):
    assert [word for _, word in conceptnet.get_weighted_properties("cat")] == ["black", "lazy"]
    assert [word for _, word in conceptnet.get_weighted_antonyms("hot")] == ["cold"]
    assert conceptnet.get_weighted_has("cat") == []
    assert len(conceptnet.get_weighted_related_locations("unknownword")) >= 4  # padded with generic places


def test_disabled_conceptnet_is_never_called(conceptnet_down, monkeypatch):
    monkeypatch.setenv("DISABLE_CONCEPTNET", "1")
    conceptnet.get_weighted_related_words("cat", 10)
    assert conceptnet_down == []
