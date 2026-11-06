"""Offline tests of `talkgenerator login openrouter`: OpenRouter's OAuth flow with PKCE, played by a fake browser and
a fake OpenRouter, and the key it keeps.

The conftest gives every test a config folder of its own (TALKGENERATOR_CONFIG_DIR), so no real key shows up here.
"""

import io
import os
import socket
import sys
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
import requests

from talkgenerator import settings
from talkgenerator.llm import login
from talkgenerator.util import credentials

KEY = "sk-or-v1-0123456789abcdef"


class _Answer:
    def __init__(self, status, data):
        self.status_code = status
        self.ok = status == 200
        self.reason = "Forbidden" if status == 403 else "OK"
        self.text = str(data)
        self._data = data

    def json(self):
        return self._data


@pytest.fixture
def openrouter(monkeypatch):
    """A fake OpenRouter: trades a code for KEY, if the verifier fits the sign-in's challenge."""
    exchanges = []

    def post(url, json, headers, timeout):
        assert url == login.KEYS_URL
        exchanges.append(json)
        signed_in = openrouter.challenges
        if json["code"] == "the-code" and login.code_challenge(json["code_verifier"]) in signed_in:
            return _Answer(200, {"key": KEY})
        return _Answer(403, {"error": {"message": "Invalid code or code_verifier"}})

    monkeypatch.setattr(login.requests, "post", post)
    details = {"label": "talkgenerator", "is_free_tier": True}
    details["free_model_daily_requests"] = {"used": 3, "limit": 50, "remaining": 47}
    monkeypatch.setattr(login, "key_details", lambda key: details if key == KEY else {})
    openrouter.challenges = []
    openrouter.exchanges = exchanges
    return openrouter


def _browser(openrouter, *answers):
    """A browser that goes to OpenRouter's sign-in page and comes back to the callback with each answer in turn
    (query parameters; the sign-in's own state, unless an answer has one). .pages() are the pages it got back."""

    def open_browser(url):
        query = dict(parse_qsl(urlsplit(url).query))
        openrouter.challenges.append(query["code_challenge"])
        callback = query["callback_url"].replace("localhost", "127.0.0.1")  # (Windows tries ::1 first, slowly)

        def come_back():
            for answer in answers:
                response = requests.get(f"{callback}?{urlencode({'state': query['state'], **answer})}", timeout=5)
                got.append((response.status_code, response.text))

        thread = threading.Thread(target=come_back, daemon=True)
        thread.start()
        threads.append(thread)
        open_browser.urls.append(url)
        return True

    def pages():
        for thread in threads:  # the browser may still be reading the last one
            thread.join(timeout=10)
        return got

    got, threads = [], []
    open_browser.pages = pages
    open_browser.urls = []
    return open_browser


def test_the_code_challenge_is_pkces():
    # RFC 7636, appendix B
    assert (
        login.code_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )
    verifier = login.new_verifier()
    assert 43 <= len(verifier) <= 128
    assert login.new_verifier() != verifier


def test_signing_in_in_the_browser_keeps_the_key(openrouter):
    browser = _browser(openrouter, {"code": "the-code"})
    assert settings.openrouter_api_key() == "" and settings.llm_spec() == "none"

    assert login.login(open_browser=browser, out=io.StringIO(), wait_seconds=10) == KEY

    (url,) = browser.urls
    query = dict(parse_qsl(urlsplit(url).query))
    assert url.startswith("https://openrouter.ai/auth?")
    assert query["code_challenge_method"] == "S256" and query["key_label"] == "talkgenerator"
    assert urlsplit(query["callback_url"]).hostname == "localhost"
    ((status, page),) = browser.pages()
    assert status == 200 and "Signed in" in page
    (exchanged,) = openrouter.exchanges
    assert login.code_challenge(exchanged["code_verifier"]) == query["code_challenge"]

    # OpenRouter's free models write talks now
    assert settings.openrouter_api_key() == KEY
    assert settings.llm_spec() == "openrouter"
    assert credentials.stored(settings.config_dir(), "openrouter")["label"] == "talkgenerator"


def test_the_environment_key_goes_first(openrouter, monkeypatch):
    login.login(open_browser=_browser(openrouter, {"code": "the-code"}), out=io.StringIO(), wait_seconds=10)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-from-the-environment")
    assert settings.openrouter_api_key() == "sk-or-v1-from-the-environment"
    assert "OPENROUTER_API_KEY is set as well" in login.signed_in_message(KEY)


def test_a_code_of_another_sign_in_is_turned_away(openrouter):
    browser = _browser(openrouter, {"code": "someone-elses", "state": "not-ours"}, {"code": "the-code"})
    assert login.login(open_browser=browser, out=io.StringIO(), wait_seconds=10) == KEY
    assert [status for status, _ in browser.pages()] == [400, 200]
    assert [exchanged["code"] for exchanged in openrouter.exchanges] == ["the-code"]


def test_a_connection_without_a_request_doesnt_hold_up_the_code(openrouter):
    # Browsers open connections ahead of time, which may never carry a request
    browser = _browser(openrouter, {"code": "the-code"})

    def open_browser(url):
        port = urlsplit(dict(parse_qsl(urlsplit(url).query))["callback_url"]).port
        idle.append(socket.create_connection(("127.0.0.1", port)))
        return browser(url)

    idle = []
    started = time.monotonic()
    assert login.login(open_browser=open_browser, out=io.StringIO(), wait_seconds=10) == KEY
    assert time.monotonic() - started < 3  # not after the idle connection timed out
    idle[0].close()


def test_saying_no_keeps_nothing(openrouter):
    browser = _browser(openrouter, {"error": "access_denied"})
    with pytest.raises(login.LoginError, match="access_denied"):
        login.login(open_browser=browser, out=io.StringIO(), wait_seconds=10)
    assert "Not signed in" in browser.pages()[0][1]
    assert openrouter.exchanges == []
    assert settings.openrouter_api_key() == ""


def test_a_code_that_doesnt_fit_keeps_nothing(openrouter):
    with pytest.raises(login.LoginError, match="403: Invalid code or code_verifier"):
        login.login(open_browser=_browser(openrouter, {"code": "an-old-code"}), out=io.StringIO(), wait_seconds=10)
    assert not credentials.credentials_file(settings.config_dir()).exists()


def test_waiting_for_the_browser_ends(openrouter):
    with pytest.raises(login.LoginError, match="no answer from the browser"):
        login.login(open_browser=lambda url: True, out=io.StringIO(), wait_seconds=0.5)


def test_without_a_browser_the_code_is_pasted(openrouter):
    out = io.StringIO()

    def paste(prompt):
        url = out.getvalue().split()[out.getvalue().split().index("device:") + 1]
        query = dict(parse_qsl(urlsplit(url).query))
        assert "callback_url" not in query and "state" not in query  # OpenRouter shows the code instead
        openrouter.challenges.append(query["code_challenge"])
        return "  the-code\n"

    assert login.login(headless=True, ask=paste, out=out) == KEY
    assert settings.openrouter_api_key() == KEY


def test_signing_out_forgets_the_key(openrouter, capsys):
    login.login(open_browser=_browser(openrouter, {"code": "the-code"}), out=io.StringIO(), wait_seconds=10)
    assert login.main("logout", []) == 0
    out = capsys.readouterr().out
    assert "forgot its OpenRouter key" in out and login.key_page(KEY) in out
    assert KEY not in out
    assert settings.openrouter_api_key() == ""
    assert not credentials.credentials_file(settings.config_dir()).exists()

    assert login.main("logout", ["openrouter"]) == 0
    assert "nothing to forget" in capsys.readouterr().out


def test_the_messages_say_how_many_free_talks_are_left(openrouter, capsys):
    assert login.main("login", ["--status"]) == 1
    assert "Not signed in" in capsys.readouterr().out
    login.login(open_browser=_browser(openrouter, {"code": "the-code"}), out=io.StringIO(), wait_seconds=10)

    message = login.signed_in_message(KEY)
    assert "47 of today's 50 free requests left" in message and "1,000 a day" in message
    assert KEY not in message and login.key_page(KEY) in message
    assert login.main("login", ["--status"]) == 0
    assert "47 of today's 50 free requests left" in capsys.readouterr().out


def test_a_failed_sign_in_says_why_on_the_command_line(openrouter, monkeypatch, capsys):
    monkeypatch.setattr(login.webbrowser, "open", _browser(openrouter, {"error": "access_denied"}))
    assert login.main("login", []) == 1
    assert "Not signed in: OpenRouter gave no code (access_denied)" in capsys.readouterr().err


def test_the_kept_keys_are_the_users_alone(tmp_path):
    folder = tmp_path / "talkgenerator"
    path = credentials.store(folder, "openrouter", {"key": KEY})
    credentials.store(folder, "other", {"key": "another"})
    assert credentials.stored_key(folder, "openrouter") == KEY
    assert credentials.forget(folder, "other") == {"key": "another"}
    assert credentials.stored_key(folder, "openrouter") == KEY  # the others stay
    assert [entry.name for entry in folder.iterdir()] == ["credentials.json"]  # no temporary files left
    if sys.platform != "win32":  # (Windows keeps AppData to its user)
        assert os.stat(path).st_mode & 0o777 == 0o600
        assert os.stat(folder).st_mode & 0o777 == 0o700

    path.write_text("{not json", encoding="utf-8")
    assert credentials.stored_key(folder, "openrouter") == ""  # broken: no key, and signing in again mends it
    assert credentials.forget(tmp_path / "nowhere", "openrouter") is None
