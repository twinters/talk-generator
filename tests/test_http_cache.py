"""Offline tests of the on-disk API response cache, against a local HTTP server."""

import http.server
import json
import threading
import time
from datetime import timedelta

import pytest
import requests
import requests_cache
from requests_cache.policy.expiration import get_url_expiration

from talkgenerator.sources import giphy
from talkgenerator.util import http_util


class _Handler(http.server.BaseHTTPRequestHandler):
    hits: dict[str, int] = {}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.endswith("counter"):  # a new answer every time, like a source whose answers change
            if "slow" in path:
                time.sleep(0.3)
            self._answer(json.dumps({"answer": _Handler.hits.get(path, 0) + 1}).encode())
        else:
            self._answer(b'{"ok": true}')

    def do_POST(self):
        # Like a sign-in, which answers with an access token
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._answer(b'{"access_token": "TOKEN-FROM-THE-SERVER", "expires_in": 36000}')

    def _answer(self, body):
        path = self.path.split("?")[0]
        _Handler.hits[path] = _Handler.hits.get(path, 0) + 1
        self.send_response(404 if path.endswith("/missing") else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # As Unsplash's searches answer (and Openverse's), and Pixabay's
        if path.endswith("/varies-on-authorization"):
            self.send_header("Vary", "Accept-Encoding,Authorization,Accept")
        if path.endswith("/varies-on-cookie"):
            self.send_header("Vary", "Accept-Encoding, Accept-Language, Cookie")
        if path.endswith("/sets-cookie"):  # as a host behind Cloudflare does
            self.send_header("Set-Cookie", "__cf_bm=abc; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Handler.hits = {}
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def cache_dir(tmp_path, monkeypatch, server):
    monkeypatch.delenv("DISABLE_CACHE", raising=False)
    monkeypatch.setenv("TALKGENERATOR_CACHE_DIR", str(tmp_path))
    monkeypatch.setitem(http_util.CACHE_EXPIRY, server + "/api", timedelta(hours=1))
    http_util.reset_sessions()
    yield tmp_path
    http_util.reset_sessions()


def test_api_responses_are_cached(server, cache_dir):
    first = http_util.get(f"http://{server}/api/words?q=cat")
    second = http_util.get(f"http://{server}/api/words?q=cat")
    assert first.json() == second.json() == {"ok": True}
    assert second.from_cache
    assert _Handler.hits["/api/words"] == 1
    assert (cache_dir / http_util.CACHE_FILE_NAME).exists()


def test_images_and_other_urls_are_not_cached(server, cache_dir):
    http_util.get(f"http://{server}/image.jpg")
    http_util.get(f"http://{server}/image.jpg")
    assert _Handler.hits["/image.jpg"] == 2


def test_giphy_searches_are_never_cached(cache_dir):
    # GIPHY's API rules: "Do not cache API responses or media URLs"
    patterns = http_util.get_session().settings.urls_expire_after
    assert get_url_expiration("https://api.pexels.com/v1/search?query=cat", patterns)  # (other searches are)
    assert get_url_expiration(giphy.API_URL + "?q=cat&limit=25", patterns) is None


def test_answers_that_vary_on_authorization_are_read_back(server, cache_dir):
    # Unsplash's searches always send their key, and its answers say "Vary: ..., Authorization": they were stored, and
    # never read back, as the cache keys leave the key out
    url = f"http://{server}/api/varies-on-authorization"
    headers = {"Authorization": "Client-ID SECRET"}
    http_util.get(url, params={"query": "cat"}, headers=headers)
    assert http_util.get(url, params={"query": "cat"}, headers=headers).from_cache
    assert _Handler.hits["/api/varies-on-authorization"] == 1


def test_answers_that_vary_on_cookies_are_read_back_whatever_cookies_came_in(server, cache_dir):
    # Pixabay's answers say "Vary: ..., Cookie": once any host had set a cookie, they weren't read back any more
    url = f"http://{server}/api/varies-on-cookie"
    http_util.get(url, params={"q": "cat"})
    http_util.get(f"http://{server}/sets-cookie")
    assert http_util.get(url, params={"q": "cat"}).from_cache
    assert _Handler.hits["/api/varies-on-cookie"] == 1


# CACHED ONLY (for a source that's skipped for a while: see http_util.Cooldown)


def test_a_cached_only_get_takes_what_the_cache_keeps_and_asks_nothing(server, cache_dir):
    url = f"http://{server}/api/words"
    http_util.get(url, params={"q": "cat"})
    assert http_util.get(url, params={"q": "cat"}, cached_only=True).json() == {"ok": True}
    assert http_util.get(url, params={"q": "dog"}, cached_only=True) is None
    assert _Handler.hits["/api/words"] == 1


def test_a_cached_only_get_finds_nothing_without_the_cache(server):
    assert http_util.get(f"http://{server}/api/words", cached_only=True) is None  # (the tests switch the cache off)
    assert _Handler.hits == {}


def test_a_cached_only_get_takes_the_answer_a_block_of_same_answers_gave(server, monkeypatch):
    monkeypatch.setitem(http_util.CACHE_EXPIRY, server + "/api", timedelta(hours=1))  # (the cache itself is off)
    url = f"http://{server}/api/counter"
    with http_util.same_answers():
        first = http_util.get(url).json()
        assert http_util.get(url, cached_only=True).json() == first
        assert http_util.get(url, params={"q": "other"}, cached_only=True) is None
    assert _Handler.hits["/api/counter"] == 1


def test_errors_are_not_cached(server, cache_dir):
    http_util.get(f"http://{server}/api/missing")
    http_util.get(f"http://{server}/api/missing")
    assert _Handler.hits["/api/missing"] == 2


def test_api_keys_stay_out_of_the_cache(server, cache_dir):
    http_util.get(f"http://{server}/api/photos", params={"q": "dog", "key": "SECRET-ONE"})
    again = http_util.get(f"http://{server}/api/photos", params={"q": "dog", "key": "SECRET-TWO"})
    assert again.from_cache  # the key isn't part of the cache key
    # Read every file of the cache, including SQLite's write-ahead log
    stored = b"".join(path.read_bytes() for path in cache_dir.iterdir() if path.is_file())
    assert b"SECRET-ONE" not in stored
    assert b"SECRET-TWO" not in stored


def test_sign_ins_and_access_tokens_stay_out_of_the_cache(server, cache_dir):
    # How Openverse is searched with a registered app's credentials
    sign_in = {"grant_type": "client_credentials", "client_id": "CLIENT-ID", "client_secret": "CLIENT-SECRET"}
    token = http_util.post(f"http://{server}/api/token", data=sign_in).json()["access_token"]
    http_util.post(f"http://{server}/api/token", data=sign_in)
    assert _Handler.hits["/api/token"] == 2  # never answered from the cache
    headers = {"Authorization": f"Bearer {token}"}
    http_util.get(f"http://{server}/api/images?q=cat", headers=headers)
    assert http_util.get(f"http://{server}/api/images?q=cat", headers=headers).from_cache
    stored = b"".join(path.read_bytes() for path in cache_dir.iterdir() if path.is_file())
    assert b"CLIENT-SECRET" not in stored
    assert b"TOKEN-FROM-THE-SERVER" not in stored


# SAME ANSWERS (for talkgenerator check, which makes every talk twice)


def test_in_a_block_of_same_answers_a_search_gets_the_answer_it_got_before(server, monkeypatch):
    monkeypatch.setitem(http_util.CACHE_EXPIRY, server + "/api", timedelta(hours=1))  # (the cache itself is off)
    url = f"http://{server}/api/counter"
    assert http_util.get(url).json() != http_util.get(url).json()
    with http_util.same_answers():
        first = http_util.get(url, params={"q": "cat"}).json()
        assert http_util.get(url, params={"q": "cat"}).json() == first
        assert http_util.get(url, params={"q": "dog"}).json() != first
    assert http_util.get(url, params={"q": "cat"}).json() != first


def test_an_answer_that_expires_in_a_block_of_same_answers_is_given_again(server, cache_dir, monkeypatch):
    # Pixabay's answers expire after a day: between the two runs of a talk, sometimes
    monkeypatch.setitem(http_util.CACHE_EXPIRY, server + "/api", timedelta(microseconds=1))
    http_util.reset_sessions()
    url = f"http://{server}/api/counter"
    with http_util.same_answers():
        first = http_util.get(url).json()
        assert http_util.get(url).json() == first
    assert _Handler.hits["/api/counter"] == 1
    assert http_util.get(url).json() != first  # (outside the block, the expired answer is asked for again)


def test_what_the_cache_doesnt_keep_is_asked_for_as_always_in_a_block_of_same_answers(server):
    # As GIPHY's searches: its API rules forbid keeping its answers
    with http_util.same_answers():
        assert (
            http_util.get(f"http://{server}/other/counter").json()
            != http_util.get(f"http://{server}/other/counter").json()
        )


def test_threads_share_the_answers_of_a_block_of_same_answers(server, monkeypatch):
    monkeypatch.setitem(http_util.CACHE_EXPIRY, server + "/api", timedelta(hours=1))
    url = f"http://{server}/api/slow-counter"
    answers = []
    with http_util.same_answers():
        threads = [threading.Thread(target=lambda: answers.append(http_util.get(url).json())) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert answers == [{"answer": 1}] * 3
    assert _Handler.hits["/api/slow-counter"] == 1  # (the others waited for the first one's answer)


def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setenv("DISABLE_CACHE", "1")
    http_util.reset_sessions()
    session = http_util.get_session()
    assert isinstance(session, requests.Session)
    assert not isinstance(session, requests_cache.CachedSession)
    http_util.reset_sessions()
