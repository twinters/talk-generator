"""Offline tests: a source that's skipped for a while (a cooldown, after an outage or a rate limit) still answers the
searches it answered before, from its caches, and asks nothing new.

Before, a cooldown skipped the source altogether, cached answers and all: one that started in the middle of a talk made
the rest of it, and the second run of `talkgenerator check`, lose images that were found already.
"""

from types import SimpleNamespace

import pytest
from prawcore.exceptions import TooManyRequests

from talkgenerator import settings
from talkgenerator.sources import conceptnet, datamuse, openverse, pexels, pixabay, reddit, unsplash
from talkgenerator.util import http_util

_ANSWERS = {
    pixabay: {"hits": [{"largeImageURL": "https://x/1.jpg", "imageWidth": 4000, "imageHeight": 2000}]},
    pexels: {"photos": [{"src": {"original": "https://x/1.jpg"}, "photographer": "Bo", "width": 3840, "height": 2560}]},
    unsplash: {
        "results": [{"urls": {"raw": "https://x/1.jpg"}, "user": {"name": "Ann"}, "width": 5000, "height": 2500}]
    },
    openverse: {"results": [{"url": "https://x/1.jpg", "license": "cc0", "width": 1024, "height": 768}]},
}


class _Answer:
    status_code = 200
    ok = True
    headers: dict[str, str] = {}

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def source(monkeypatch):
    """A source whose searches the fake API answers, but for "dog", which gets no answer (its outage)."""
    monkeypatch.setattr(settings, "pixabay_auth", lambda: {"pixabay_key": "test"})
    monkeypatch.setattr(settings, "pexels_auth", lambda: {"pexels_key": "test"})
    monkeypatch.setattr(settings, "unsplash_auth", lambda: {"unsplash_access_key": "test"})
    asked = []
    kept = {}  # what the caches keep: what a cached_only search finds

    def get(url, cached_only=False, params=None, **kwargs):
        key = (url, repr(sorted((params or {}).items())))
        if cached_only:
            return kept.get(key)
        asked.append(params)
        if any(value == "dog" for value in (params or {}).values()):
            return None
        kept[key] = _Answer(current["answer"])
        return kept[key]

    current = {}
    monkeypatch.setattr(http_util, "get", get)

    def install(module):
        monkeypatch.setattr(module, "_cooldown", http_util.Cooldown(module.__name__ + " (test)"))
        current["answer"] = _ANSWERS[module]
        return asked

    return install


@pytest.mark.parametrize("module", list(_ANSWERS), ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_a_source_that_is_skipped_for_a_while_still_finds_what_it_found_before(source, module):
    asked = source(module)
    found = [image.get_image_url() for image in module.search_photos("cat")]
    assert len(found) == 1
    assert module.search_photos("dog") == []  # no answer: skipped for a while
    assert module._cooldown.active
    until = module._cooldown._until

    assert [image.get_image_url() for image in module.search_photos("cat")] == found
    assert module.search_photos("owl") == []
    assert len(asked) == 2  # (cat and dog: nothing while it's skipped)
    assert module._cooldown._until == until  # (a search the caches don't have doesn't make the cooldown longer)
    assert module.available()  # (so it keeps its place among a look's sources)


class _RateLimited:
    status_code = 429
    headers: dict[str, str] = {}
    text = ""


def test_reddit_still_finds_what_it_found_before_while_it_is_skipped(monkeypatch):
    monkeypatch.setattr(reddit, "_cooldown", http_util.Cooldown("Reddit (test)"))
    monkeypatch.setattr(reddit, "has_reddit_access", lambda: True)
    monkeypatch.setattr(reddit, "_has_credentials", lambda: True)
    reddit._search_images.cache_clear()
    asked = []

    def search(name, query, sort, limit, animated):
        asked.append(query)
        if query == "dog":
            raise TooManyRequests(_RateLimited())
        return (reddit.RedditImage("https://i.redd.it/cat.jpg", "u/ann (on r/pics)", None),)

    monkeypatch.setattr(reddit, "_search_reddit", search)
    try:
        found = reddit.search_images("pics", "cat")
        assert reddit.search_images("pics", "dog") is None  # rate limited: skipped for a while
        assert reddit.search_images("pics", "cat") == found
        assert reddit.search_images("pics", "owl") is None
        assert asked == ["cat", "dog"]
        assert reddit.available()
    finally:
        reddit._search_images.cache_clear()


def test_conceptnet_still_answers_what_it_answered_before_while_it_is_skipped(monkeypatch):
    edges = {"edges": [{"start": {"label": "puppy"}, "end": {"label": "dog"}, "weight": 5, "rel": {"label": "x"}}]}
    asked = []
    kept = {}

    def get(url, cached_only=False, **kwargs):
        if cached_only:
            return kept.get(url)
        asked.append(url)
        if "/c/en/cat" in url:
            return SimpleNamespace(status_code=502, ok=False)
        kept[url] = _Answer(edges)
        return kept[url]

    monkeypatch.setattr(http_util, "get", get)
    monkeypatch.setattr(conceptnet, "_cooldown", http_util.Cooldown("ConceptNet API (test)"))
    monkeypatch.setattr(datamuse, "_query", lambda relation, word, max_results: (("from datamuse", 100),))
    conceptnet._fetch_edges.cache_clear()
    try:
        before = conceptnet.get_weighted_related_words("dog", 10)
        assert [word for _, word in before] == ["puppy"]
        conceptnet.get_weighted_related_words("cat", 10)  # HTTP 502: skipped for a while
        assert conceptnet.get_weighted_related_words("dog", 10) == before  # (from memory)
        conceptnet._fetch_edges.cache_clear()  # (as in another process: only the on-disk cache has it)
        assert conceptnet.get_weighted_related_words("dog", 10) == before
        assert [word for _, word in conceptnet.get_weighted_related_words("owl", 10)] == ["from datamuse"]
        assert len(asked) == 2
    finally:
        conceptnet._fetch_edges.cache_clear()
