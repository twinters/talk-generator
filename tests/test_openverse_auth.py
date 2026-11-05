"""Offline tests of searching Openverse as a registered app, with an access token."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from talkgenerator.sources import openverse
from talkgenerator.util import http_util

CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
TOKEN = "test-access-token"


class _Response:
    def __init__(self, data=None, status_code=200):
        self._data = data
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {}

    def json(self):
        if self._data is None:
            raise ValueError("not JSON")
        return self._data


def _token_answer(**data):
    return _Response({"access_token": TOKEN, "scope": "read write groups", "token_type": "Bearer", **data})


def _photos_answer():
    return _Response({"results": [{"url": "https://example.com/1.jpg", "license": "cc0"}]})


class _FakeOpenverse:
    """Answers sign-ins with token_answer and searches with search_answer, and remembers the requests."""

    def __init__(self):
        self.token_answer = _token_answer(expires_in=36000)
        self.search_answer = _photos_answer()
        self.sign_ins = []
        self.searches = []

    def post(self, url, **kwargs):
        self.sign_ins.append((url, kwargs))
        return self.token_answer

    def get(self, url, **kwargs):
        self.searches.append((url, kwargs))
        return self.search_answer

    def authorizations(self):
        return [(kwargs.get("headers") or {}).get("Authorization") for _, kwargs in self.searches]


@pytest.fixture
def api(monkeypatch):
    fake = _FakeOpenverse()
    monkeypatch.setattr(http_util, "post", fake.post)
    monkeypatch.setattr(http_util, "get", fake.get)
    monkeypatch.setattr(openverse, "_cooldown", http_util.Cooldown("Openverse (test)"))
    monkeypatch.setattr(openverse, "_access_token", openverse._AccessToken())
    return fake


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("OPENVERSE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("OPENVERSE_CLIENT_SECRET", CLIENT_SECRET)


@pytest.fixture
def clock(monkeypatch):
    """Lets a test move time.monotonic forward."""
    clock = SimpleNamespace(now=time.monotonic())
    monkeypatch.setattr(time, "monotonic", lambda: clock.now)
    return clock


@pytest.mark.parametrize(
    "variables",
    [{}, {"OPENVERSE_CLIENT_ID": CLIENT_ID}, {"OPENVERSE_CLIENT_SECRET": CLIENT_SECRET}],
    ids=["no credentials", "only a client id", "only a client secret"],
)
def test_without_credentials_searches_anonymously(api, monkeypatch, variables):
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
    assert openverse.search_photos("cat")
    assert api.sign_ins == []
    assert api.authorizations() == [None]


def test_signs_in_once_and_searches_with_the_token(api, credentials):
    assert openverse.search_photos("cat")
    assert openverse.search_photos("dog")
    assert len(api.sign_ins) == 1
    url, kwargs = api.sign_ins[0]
    assert url == "https://api.openverse.org/v1/auth_tokens/token/"
    assert kwargs["data"] == {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    assert api.authorizations() == [f"Bearer {TOKEN}", f"Bearer {TOKEN}"]


def test_the_token_is_renewed_shortly_before_it_expires(api, credentials, clock):
    api.token_answer = _token_answer(expires_in=3600)
    openverse.search_photos("cat")
    clock.now += 3600 - 6 * 60
    openverse.search_photos("dog")
    assert len(api.sign_ins) == 1
    clock.now += 2 * 60  # 4 minutes before it expires
    openverse.search_photos("bird")
    assert len(api.sign_ins) == 2


def test_a_token_without_expiry_is_renewed_within_the_hour(api, credentials, clock):
    api.token_answer = _token_answer()
    openverse.search_photos("cat")
    clock.now += 50 * 60
    openverse.search_photos("dog")
    assert len(api.sign_ins) == 1
    clock.now += 6 * 60
    openverse.search_photos("bird")
    assert len(api.sign_ins) == 2


def test_rejected_credentials_mean_anonymous_searches_for_an_hour(api, credentials, clock, caplog):
    api.token_answer = _Response({"error": "invalid_client"}, status_code=401)
    assert openverse.search_photos("cat")
    assert openverse.search_photos("dog")
    assert len(api.sign_ins) == 1
    assert api.authorizations() == [None, None]
    assert "the OPENVERSE_CLIENT_ID and OPENVERSE_CLIENT_SECRET were rejected" in caplog.text

    api.token_answer = _token_answer(expires_in=36000)
    clock.now += 61 * 60
    assert openverse.search_photos("bird")
    assert len(api.sign_ins) == 2
    assert api.authorizations()[-1] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    "answer",
    [None, _Response(status_code=503), _Response({"detail": "slow down"}, status_code=429), _Response({}), _Response()],
    ids=["no answer", "server error", "rate limited", "no token", "not JSON"],
)
def test_failing_to_sign_in_means_anonymous_searches_for_a_while(api, credentials, answer):
    api.token_answer = answer
    assert openverse.search_photos("cat")
    assert openverse.search_photos("dog")
    assert len(api.sign_ins) == 1
    assert api.authorizations() == [None, None]


def test_signs_in_again_when_openverse_rejects_the_token(api, credentials):
    api.search_answer = _Response({"detail": "Invalid token."}, status_code=401)
    assert openverse.search_photos("cat") == []
    api.search_answer = _photos_answer()
    assert openverse.search_photos("dog")
    assert len(api.sign_ins) == 2


def test_parallel_searches_sign_in_once(api, credentials, monkeypatch):
    def slow_sign_in(url, **kwargs):
        time.sleep(0.2)
        return api.post(url, **kwargs)

    monkeypatch.setattr(http_util, "post", slow_sign_in)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(openverse.search_photos, ["cat"] * 8))
    assert len(api.sign_ins) == 1
    assert api.authorizations() == [f"Bearer {TOKEN}"] * 8


def test_credentials_and_tokens_stay_out_of_the_logs(api, credentials, caplog):
    caplog.set_level(logging.DEBUG, logger="talkgenerator")
    openverse.search_photos("cat")
    api.search_answer = _Response({"detail": "Invalid token."}, status_code=401)
    openverse.search_photos("dog")
    api.token_answer = _Response({"error": "invalid_client"}, status_code=401)
    openverse.search_photos("bird")
    assert "Signed in to Openverse" in caplog.text
    assert "rejected" in caplog.text
    for secret in (CLIENT_ID, CLIENT_SECRET, TOKEN):
        assert secret not in caplog.text
