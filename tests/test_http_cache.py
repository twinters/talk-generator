"""Offline tests of the on-disk API response cache, against a local HTTP server."""

import http.server
import threading
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


def test_cache_can_be_disabled(monkeypatch):
    monkeypatch.setenv("DISABLE_CACHE", "1")
    http_util.reset_sessions()
    session = http_util.get_session()
    assert isinstance(session, requests.Session)
    assert not isinstance(session, requests_cache.CachedSession)
    http_util.reset_sessions()
