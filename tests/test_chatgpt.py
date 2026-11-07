"""Offline tests of Sign in with ChatGPT (`talkgenerator login chatgpt`) and the chatgpt provider.

A fake browser and a fake OpenAI play OpenAI's sign-in for open-source apps: its sign-in page, its token, revocation
and key endpoints (signing ID tokens with an RSA key made up for the tests), and its list of models. The provider
talks to a fake Responses API through the real openai SDK. The conftest gives every test a config folder of its own
(TALKGENERATOR_CONFIG_DIR), so no real sign-in shows up here.
"""

import base64
import hashlib
import io
import json
import math
import secrets
import threading
import time
from functools import cache
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx2
import openai
import pytest
import requests

from talkgenerator import settings
from talkgenerator.llm import chatgpt_login, login, prices, provider_from_spec
from talkgenerator.llm.base import ProviderError, ProviderUnavailable
from talkgenerator.llm.chatgpt import ChatGPTProvider
from talkgenerator.util import credentials, http_util
from tests.test_llm_providers import ANSWER, REQUEST, SCHEMA, Api, _openai_answer, _response_event

# SHA-256's DER prefix in a PKCS #1 v1.5 signature (RFC 8017, section 9.2, note 1)
SHA256_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
ISSUED = "oaiapp_test0001"
SUBJECT = "user-0123456789"
EMAIL = "ann@example.com"
REAL_GET = requests.get


# AN RSA KEY OF THE TESTS' OWN, AND ID TOKENS SIGNED WITH IT


def _probably_prime(number):
    for small in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if number % small == 0:
            return number == small
    odd, twos = number - 1, 0
    while odd % 2 == 0:
        odd, twos = odd // 2, twos + 1
    for _ in range(32):  # (Miller-Rabin)
        witness = pow(secrets.randbelow(number - 3) + 2, odd, number)
        if witness in (1, number - 1):
            continue
        for _ in range(twos - 1):
            witness = pow(witness, 2, number)
            if witness == number - 1:
                break
        else:
            return False
    return True


def _prime(bits):
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _probably_prime(candidate):
            return candidate


@cache
def _key():
    """An RSA key for the tests (1024 bits: quick to make, and plenty for checking signatures): n, e and d."""
    while True:
        p, q = _prime(512), _prime(512)
        phi = (p - 1) * (q - 1)
        if p != q and math.gcd(65537, phi) == 1:
            return p * q, 65537, pow(65537, -1, phi)


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(claims, *, kid="test-key", alg="RS256"):
    """A JSON Web Token of the claims, signed with the tests' key (RS256, as OpenAI signs ID tokens)."""
    n, _, d = _key()
    header = {"alg": alg, "kid": kid, "typ": "JWT"}
    signed = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    size = (n.bit_length() + 7) // 8
    info = SHA256_INFO + hashlib.sha256(signed.encode("ascii")).digest()
    padded = b"\x00\x01" + b"\xff" * (size - len(info) - 3) + b"\x00" + info
    return f"{signed}.{_b64(pow(int.from_bytes(padded, 'big'), d, n).to_bytes(size, 'big'))}"


# A FAKE OPENAI, AND A FAKE BROWSER


class _Answer:
    def __init__(self, status, data=None):
        self.status_code = status
        self.ok = status == 200
        self.reason = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 503: "Service Unavailable"}[status]
        self._data = data
        self.text = json.dumps(data) if data is not None else ""

    def json(self):
        if self._data is None:
            raise ValueError("no JSON")
        return self._data


class FakeOpenAI:
    """OpenAI's side of the sign-in: what its sign-in page got, and its token, revocation, key and model endpoints."""

    def __init__(self):
        self.pages = []  # the parameters of every sign-in page the browser went to
        self.forms = []  # what the token endpoint got
        self.revoked = []
        self.scope = chatgpt_login.SCOPES  # what sign-ins grant
        self.claims = {}  # (what the ID tokens say otherwise)
        self.refresh_tokens = set()  # the ones that still work (each works once)
        self.access_tokens = set()
        self.made = 0
        self.delay = 0.0  # (how long the token endpoint takes)
        self.revocation_status = 200
        self.codes_turned_down = 0  # (how many of the next codes the token endpoint turns down)
        self.models = [
            {"slug": "gpt-test-sol", "display_name": "GPT Test", "visibility": "list"},
            {"slug": "gpt-test-hidden", "display_name": "GPT Hidden", "visibility": "hide"},
            {"slug": "gpt-test-mini", "display_name": "GPT Test mini", "visibility": "list"},
        ]

    def _tokens(self):
        self.made += 1
        access, refresh = f"access-{self.made}", f"refresh-{self.made}"
        self.access_tokens.add(access)
        self.refresh_tokens.add(refresh)
        return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 3600}

    def post(self, url, data=None, headers=None, timeout=None):
        if url == chatgpt_login.REVOKE_URL:
            self.revoked.append(data)
            if self.revocation_status == 200:
                self.refresh_tokens.discard(data["token"])
            return _Answer(self.revocation_status)
        assert url == chatgpt_login.TOKEN_URL
        self.forms.append(data)
        time.sleep(self.delay)
        if data["client_id"] != ISSUED or data["resource"] != chatgpt_login.API_URL:
            return _Answer(400, {"error": "invalid_client"})
        if data["grant_type"] == "refresh_token":
            if data["refresh_token"] not in self.refresh_tokens:
                return _Answer(400, {"error": "invalid_grant", "error_description": "The refresh token can't be used"})
            self.refresh_tokens.discard(data["refresh_token"])
            return _Answer(200, self._tokens())
        page = self.pages[-1]
        if self.codes_turned_down:
            self.codes_turned_down -= 1
            return _Answer(400, {"error": "invalid_grant"})
        if (data["code"], login.code_challenge(data["code_verifier"]), data["redirect_uri"]) != (
            "the-code",
            page["code_challenge"],
            page["redirect_uri"],
        ):
            return _Answer(400, {"error": "invalid_grant", "error_description": "The code doesn't fit"})
        now = int(time.time())
        claims = {"iss": chatgpt_login.ISSUER, "aud": ISSUED, "sub": SUBJECT, "email": EMAIL, "iat": now}
        claims |= {"exp": now + 3600, "nonce": page["nonce"], **self.claims}
        return _Answer(200, {**self._tokens(), "id_token": _jwt(claims), "scope": self.scope})

    def get(self, url, headers=None, timeout=None, **options):
        if url.startswith("http://127.0.0.1"):  # (the browser, coming back to talkgenerator)
            return REAL_GET(url, headers=headers, timeout=timeout, **options)
        if url == chatgpt_login.KEYS_URL:
            n, e, _ = _key()
            key = {"kty": "RSA", "kid": "test-key", "alg": "RS256", "use": "sig"}
            return _Answer(200, {"keys": [{**key, "n": _b64(n.to_bytes(128, "big")), "e": _b64(e.to_bytes(3, "big"))}]})
        assert url == f"{chatgpt_login.API_URL}/models"
        if (headers or {}).get("Authorization", "").removeprefix("Bearer ") not in self.access_tokens:
            return _Answer(401, {"detail": "Unauthorized"})
        return _Answer(200, {"object": "list", "data": self.models})


@pytest.fixture
def openai_accounts(monkeypatch):
    fake = FakeOpenAI()
    monkeypatch.setattr(chatgpt_login.requests, "post", fake.post)
    monkeypatch.setattr(chatgpt_login.requests, "get", fake.get)
    monkeypatch.setattr(chatgpt_login, "_keys", {})  # (OpenAI's keys, from this fake)
    return fake


def _browser(fake, *answers):
    """A browser that goes to OpenAI's sign-in page and comes back to talkgenerator with each answer in turn: by
    default the code, the page's own state and (on a first sign-in) the client ID that OpenAI issues; None leaves one
    out. .pages() are the pages it got back."""

    def open_browser(url):
        assert url.startswith(chatgpt_login.AUTHORIZE_URL + "?")
        page = dict(parse_qsl(urlsplit(url).query))
        fake.pages.append(page)

        def come_back():
            for answer in answers or ({},):
                query = {"code": "the-code", "state": page["state"], **answer}
                if page["client_id"] == chatgpt_login.REGISTRATION:
                    query = {"client_id": ISSUED, **query}
                query = {name: value for name, value in query.items() if value is not None}
                response = REAL_GET(f"{page['redirect_uri']}?{urlencode(query)}", timeout=5)
                got.append((response.status_code, response.text))

        thread = threading.Thread(target=come_back, daemon=True)
        thread.start()
        threads.append(thread)
        return True

    def pages():
        for thread in threads:  # (the browser may still be reading the last one)
            thread.join(timeout=10)
        return got

    got, threads = [], []
    open_browser.pages = pages
    return open_browser


def _sign_in(fake, *answers, **options):
    return chatgpt_login.login(open_browser=_browser(fake, *answers), out=io.StringIO(), wait_seconds=10, **options)


# SIGNING IN


def test_the_first_sign_in_registers_talkgenerator_and_keeps_the_sign_in(openai_accounts):
    assert settings.llm_spec() == "none"

    record = _sign_in(openai_accounts)

    (page,) = openai_accounts.pages
    assert (page["client_id"], page["agent_name_hint"]) == ("dynamic_agent_client", "talkgenerator")
    assert page["ext_agent_host_id"].startswith("urn:uuid:")
    assert page["scope"].split() == [
        "openid",
        "profile",
        "email",
        "offline_access",
        "resource.invoke",
        "chatgpt.tokens.use.direct",
    ]
    assert (page["response_type"], page["resource"], page["code_challenge_method"]) == (
        "code",
        "https://api.openai.com/v1",
        "S256",
    )
    assert page["state"] and page["nonce"] and page["state"] != page["nonce"]
    redirect = urlsplit(page["redirect_uri"])
    assert (redirect.scheme, redirect.hostname, redirect.path) == ("http", "127.0.0.1", "/auth/callback")
    assert {"id_token_hint", "login_hint", "prompt"}.isdisjoint(page)

    (form,) = openai_accounts.forms
    assert login.code_challenge(form.pop("code_verifier")) == page["code_challenge"]
    assert form == {
        "grant_type": "authorization_code",
        "client_id": ISSUED,
        "code": "the-code",
        "redirect_uri": page["redirect_uri"],
        "resource": "https://api.openai.com/v1",
    }

    kept = chatgpt_login.stored()
    assert kept == record
    assert (kept["client_id"], kept["subject"], kept["email"]) == (ISSUED, SUBJECT, EMAIL)
    assert kept["host_id"] == page["ext_agent_host_id"]
    assert (kept["access_token"], kept["refresh_token"], kept["plan_usage"]) == ("access-1", "refresh-1", True)
    assert kept["expires_at"] == pytest.approx(time.time() + 3600, abs=60)
    assert kept["models"] == ["gpt-test-sol", "gpt-test-mini"]  # (those the account lists)
    # The plan's models write talks now
    assert settings.llm_spec() == "chatgpt"
    assert provider_from_spec("chatgpt").id == "chatgpt:gpt-test-sol"


def test_signing_in_again_uses_the_registration(openai_accounts):
    first = _sign_in(openai_accounts)
    _sign_in(openai_accounts)  # (still signed in)
    assert chatgpt_login.logout(out=io.StringIO()) == 0
    _sign_in(openai_accounts)  # (signed out)

    registering, again, after_signing_out = openai_accounts.pages
    for page in (again, after_signing_out):
        assert page["client_id"] == ISSUED and "agent_name_hint" not in page
        assert page["ext_agent_host_id"] == registering["ext_agent_host_id"]  # (this computer's, kept)
        assert page["login_hint"] == EMAIL
    assert again["id_token_hint"] == first["id_token"]  # (no choosing the account again)
    assert "id_token_hint" not in after_signing_out
    assert len({page["state"] for page in openai_accounts.pages}) == 3  # (fresh for every attempt)
    assert len({page["nonce"] for page in openai_accounts.pages}) == 3


def test_the_address_shown_leaves_the_id_token_out(openai_accounts):
    _sign_in(openai_accounts)
    out = io.StringIO()
    chatgpt_login.login(open_browser=_browser(openai_accounts), out=out, wait_seconds=10)
    assert "id_token_hint" in openai_accounts.pages[-1]  # (the browser got it)
    assert "Continue with ChatGPT" in out.getvalue() and "id_token_hint" not in out.getvalue()


def test_an_answer_of_another_sign_in_is_turned_away(openai_accounts):
    browser = _browser(
        openai_accounts, {"state": "not-ours", "code": None, "error": "access_denied"}, {"state": "not-ours"}, {}
    )
    chatgpt_login.login(open_browser=browser, out=io.StringIO(), wait_seconds=10)
    assert [status for status, _ in browser.pages()] == [400, 400, 200]
    assert len(openai_accounts.forms) == 1


def test_saying_no_keeps_no_sign_in(openai_accounts):
    browser = _browser(openai_accounts, {"code": None, "client_id": None, "error": "access_denied"})
    with pytest.raises(login.LoginError, match="access_denied") as said_no:
        chatgpt_login.login(open_browser=browser, out=io.StringIO(), wait_seconds=10)
    assert "a required permission is unavailable" in str(said_no.value) and "Plus or Pro" in str(said_no.value)
    assert "Not signed in" in browser.pages()[0][1]
    assert openai_accounts.forms == []
    assert not chatgpt_login.signed_in(chatgpt_login.stored())
    assert settings.llm_spec() == "none"


def test_a_code_turned_down_is_followed_by_a_sign_in_with_the_registration(openai_accounts):
    # As in the first sign-in tried for real: OpenAI turned the first code down (invalid_grant), and its docs say to
    # sign in afresh with the client ID it issued
    openai_accounts.codes_turned_down = 1
    out = io.StringIO()

    record = chatgpt_login.login(open_browser=_browser(openai_accounts), out=out, wait_seconds=10)

    registering, again = openai_accounts.pages
    assert (registering["client_id"], again["client_id"]) == ("dynamic_agent_client", ISSUED)
    assert "signing in once more" in out.getvalue()
    assert record["plan_usage"] is True and settings.llm_spec() == "chatgpt"


def test_a_code_turned_down_twice_ends_the_sign_in(openai_accounts):
    openai_accounts.codes_turned_down = 2
    with pytest.raises(login.LoginError, match="invalid_grant"):
        _sign_in(openai_accounts)
    assert len(openai_accounts.pages) == 2  # (once more, and no more than that)
    assert not chatgpt_login.signed_in(chatgpt_login.stored())


@pytest.mark.parametrize(
    ("claims", "message"),
    [
        ({"iss": "https://auth.example.com"}, "isn't OpenAI's"),
        ({"aud": "oaiapp_someone_else"}, "for another app"),
        ({"exp": 1_000_000_000}, "expired"),
        ({"nonce": "of-another-sign-in"}, "another sign-in"),
    ],
)
def test_an_id_token_that_doesnt_check_out_signs_nobody_in(openai_accounts, claims, message):
    openai_accounts.claims = claims
    with pytest.raises(login.LoginError, match=message):
        _sign_in(openai_accounts)
    kept = chatgpt_login.stored()
    assert not chatgpt_login.signed_in(kept)
    assert kept["client_id"] == ISSUED  # (the registration stays, for trying again)


def test_the_id_tokens_signature_has_to_fit_openais_keys(openai_accounts):
    claims = {"iss": chatgpt_login.ISSUER, "aud": [ISSUED], "sub": SUBJECT, "exp": time.time() + 60, "nonce": "n"}
    token = _jwt(claims)
    assert chatgpt_login.verified_claims(token, client_id=ISSUED, nonce="n")["sub"] == SUBJECT

    header, _, signature = token.split(".")
    someone_else = _b64(json.dumps({**claims, "sub": "someone-else"}).encode())
    with pytest.raises(login.LoginError, match="signature"):
        chatgpt_login.verified_claims(f"{header}.{someone_else}.{signature}", client_id=ISSUED, nonce="n")
    with pytest.raises(login.LoginError, match="doesn't publish"):
        chatgpt_login.verified_claims(_jwt(claims, kid="another-key"), client_id=ISSUED, nonce="n")
    with pytest.raises(login.LoginError, match="RS256"):
        chatgpt_login.verified_claims(_jwt(claims, alg="HS256"), client_id=ISSUED, nonce="n")
    with pytest.raises(login.LoginError, match="can't be read"):
        chatgpt_login.verified_claims("not.a-token", client_id=ISSUED)


def test_a_sign_in_without_the_plans_permission_sends_no_requests(openai_accounts):
    openai_accounts.scope = "openid profile email offline_access"

    record = _sign_in(openai_accounts)

    assert record["plan_usage"] is False and "models" not in record
    assert "didn't allow talkgenerator to use your ChatGPT plan" in chatgpt_login.signed_in_message(record)
    assert settings.llm_spec() == "none"
    with pytest.raises(chatgpt_login.SignInNeeded, match="didn't allow"):
        chatgpt_login.access_token()
    # Signing in again asks for it again
    openai_accounts.scope = chatgpt_login.SCOPES
    assert _sign_in(openai_accounts)["plan_usage"] is True
    assert openai_accounts.pages[-1]["prompt"] == "consent"


def test_another_account_signs_in_with_a_registration_of_its_own(openai_accounts):
    _sign_in(openai_accounts)
    openai_accounts.claims = {"sub": "user-someone-else", "email": "bob@example.com"}
    with pytest.raises(login.LoginError, match="--new-account"):
        _sign_in(openai_accounts)
    assert chatgpt_login.stored()["subject"] == SUBJECT  # (the first account's sign-in stays)

    record = _sign_in(openai_accounts, new_account=True)

    assert openai_accounts.pages[-1]["client_id"] == "dynamic_agent_client"
    assert [revoked["token"] for revoked in openai_accounts.revoked] == ["refresh-1"]  # (the first account's ended)
    assert (record["subject"], record["email"]) == ("user-someone-else", "bob@example.com")


# THE ACCESS TOKEN


def _expired():
    credentials.store(settings.config_dir(), "chatgpt", {**chatgpt_login.stored(), "expires_at": time.time() - 1})


def test_an_access_token_that_runs_out_is_refreshed(openai_accounts):
    _sign_in(openai_accounts)
    assert chatgpt_login.access_token() == "access-1"
    assert len(openai_accounts.forms) == 1  # (no refresh while it lasts)

    _expired()

    assert chatgpt_login.access_token() == "access-2"
    assert openai_accounts.forms[-1] == {
        "grant_type": "refresh_token",
        "client_id": ISSUED,
        "refresh_token": "refresh-1",
        "resource": "https://api.openai.com/v1",
    }
    kept = chatgpt_login.stored()
    assert (kept["access_token"], kept["refresh_token"]) == ("access-2", "refresh-2")  # (replaced together)
    assert kept["expires_at"] > time.time() + 3000 and kept["plan_usage"] is True
    assert chatgpt_login.access_token() == "access-2"


def test_an_access_token_about_to_run_out_is_refreshed_first(openai_accounts):
    _sign_in(openai_accounts)
    credentials.store(settings.config_dir(), "chatgpt", {**chatgpt_login.stored(), "expires_at": time.time() + 60})
    assert chatgpt_login.access_token() == "access-2"


def test_requests_at_the_same_time_refresh_once(openai_accounts):
    _sign_in(openai_accounts)
    _expired()
    openai_accounts.delay = 0.3
    tokens = []
    threads = [threading.Thread(target=lambda: tokens.append(chatgpt_login.access_token())) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert tokens == ["access-2"] * 4
    assert [form["grant_type"] for form in openai_accounts.forms] == ["authorization_code", "refresh_token"]
    assert not credentials.credentials_file(settings.config_dir()).with_name("chatgpt.lock").exists()


def test_a_sign_in_that_ended_asks_to_sign_in_again(openai_accounts):
    _sign_in(openai_accounts)
    _expired()
    openai_accounts.refresh_tokens.clear()  # (disconnected in ChatGPT's settings, say)

    with pytest.raises(chatgpt_login.SignInNeeded, match="login chatgpt"):
        chatgpt_login.access_token()

    kept = chatgpt_login.stored()
    assert not chatgpt_login.signed_in(kept) and kept["client_id"] == ISSUED  # (the registration stays)
    assert settings.llm_spec() == "none"


def test_a_refresh_that_cant_get_through_keeps_the_sign_in(openai_accounts, monkeypatch):
    _sign_in(openai_accounts)
    _expired()

    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("no network")

    monkeypatch.setattr(chatgpt_login.requests, "post", unreachable)
    with pytest.raises(ProviderUnavailable, match="can't be refreshed now"):
        chatgpt_login.access_token()
    assert chatgpt_login.stored()["refresh_token"] == "refresh-1"


# SIGNING OUT, AND THE COMMAND LINE


def test_signing_out_ends_the_sign_in_at_openai(openai_accounts, capsys):
    _sign_in(openai_accounts)

    assert login.main("logout", ["chatgpt"]) == 0

    assert "OpenAI ended talkgenerator's sign-in" in capsys.readouterr().out
    assert openai_accounts.revoked == [{"token": "refresh-1", "token_type_hint": "refresh_token", "client_id": ISSUED}]
    kept = chatgpt_login.stored()
    assert {"access_token", "refresh_token", "id_token"}.isdisjoint(kept)
    assert (kept["client_id"], kept["email"]) == (ISSUED, EMAIL)  # (the registration stays, for the next sign-in)
    assert settings.llm_spec() == "none"
    assert login.main("logout", ["chatgpt"]) == 0
    assert "nothing to sign out of" in capsys.readouterr().out


def test_a_sign_out_that_openai_doesnt_confirm_says_so(openai_accounts, monkeypatch, capsys):
    _sign_in(openai_accounts)
    openai_accounts.revocation_status = 503
    monkeypatch.setattr(chatgpt_login, "_REVOKE_BACKOFF_SECONDS", 0)

    assert login.main("logout", ["chatgpt"]) == 0

    assert "didn't confirm" in capsys.readouterr().out
    assert len(openai_accounts.revoked) == 3  # (tried again, twice)
    assert not chatgpt_login.signed_in(chatgpt_login.stored())


def test_the_command_line(openai_accounts, monkeypatch, capsys):
    assert login.main("login", ["chatgpt", "--status"]) == 1
    assert "Not signed in with ChatGPT" in capsys.readouterr().out
    monkeypatch.setattr(chatgpt_login.webbrowser, "open", _browser(openai_accounts))

    assert login.main("login", ["chatgpt"]) == 0
    first = capsys.readouterr().out
    assert f"Signed in with ChatGPT as {EMAIL}" in first and "gpt-test-sol" in first
    assert "You're using your ChatGPT plan" in first and chatgpt_login.USAGE_URL in first
    assert "access-1" not in first and "refresh-1" not in first
    assert login.main("login", ["chatgpt"]) == 0
    assert "You're using your ChatGPT plan" not in capsys.readouterr().out  # (the first time only)

    assert login.main("login", ["chatgpt", "--status"]) == 0
    status = capsys.readouterr().out
    assert EMAIL in status and "gpt-test-sol, gpt-test-mini" in status and "access-" not in status
    assert login.main("login", ["chatgpt", "--headless"]) == 1
    assert "needs a browser here" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        login.main("login", ["openrouter", "--new-account"])


def test_tokens_stay_out_of_messages():
    token = _jwt({"sub": SUBJECT})
    assert token not in http_util.redact(f"the request failed: {token}")
    address = "https://auth.openai.com/api/accounts/authorize?id_token_hint=eyJhbGc.secret&state=1"
    assert "secret" not in http_util.redact(address)


# THE PROVIDER


def _signed_in(**changes):
    """A sign-in, as login keeps it (without signing in)."""
    record = {
        "host_id": "urn:uuid:00000000-0000-4000-8000-000000000000",
        "client_id": ISSUED,
        "subject": SUBJECT,
        "email": EMAIL,
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "token_type": "Bearer",
        "expires_at": time.time() + 3600,
        "scopes": chatgpt_login.SCOPES.split(),
        "plan_usage": True,
        "models": ["gpt-test-sol", "gpt-test-mini"],
        **changes,
    }
    credentials.store(settings.config_dir(), "chatgpt", record)


def _chatgpt(api, model=""):
    """The provider, talking to the fake API through the openai SDK; .tokens are the access tokens it sent."""

    def client_for(token):
        provider.tokens.append(token)
        transport = httpx2.MockTransport(api)
        return openai.OpenAI(
            api_key=token,
            base_url=chatgpt_login.API_URL,
            max_retries=0,
            http_client=openai.DefaultHttpxClient(transport=transport),
        )

    provider = ChatGPTProvider(model, client_for=client_for)
    provider.tokens = []
    return provider


def test_the_plans_models_write_through_the_responses_api(openai_accounts):
    _signed_in()
    api = Api(_openai_answer(*ANSWER))
    pieces = []

    response = _chatgpt(api).stream(REQUEST, pieces.append)

    request = api.requests[-1]
    assert str(request.url) == "https://api.openai.com/v1/responses"
    assert request.headers["authorization"] == "Bearer access-1"
    body = api.body
    assert (body["model"], body["instructions"], body["store"], body["stream"]) == (
        "gpt-test-sol",
        "You write talks.",
        False,
        True,
    )
    assert body["input"] == [{"role": "user", "content": "Topic: cats"}]
    assert body["text"] == {"format": {"type": "json_schema", "name": "answer", "schema": SCHEMA, "strict": True}}
    assert "max_output_tokens" not in body  # (the plan's route turns it down)
    assert body["reasoning"] == {"effort": "low"}
    assert pieces == list(ANSWER)
    assert (response.data, response.model) == ({"title": "Cats"}, "chatgpt:gpt-test-2026")
    assert prices.price_of(response.model) == prices.FREE  # (the plan's usage, not talkgenerator's money)


def test_a_model_can_be_named_and_the_effort_set(openai_accounts, monkeypatch):
    _signed_in()
    monkeypatch.setenv("TALKGENERATOR_LLM_EFFORT", "medium")
    api = Api(_openai_answer(*ANSWER))

    _chatgpt(api, "gpt-test-mini").complete(REQUEST)

    assert (api.body["model"], api.body["reasoning"]) == ("gpt-test-mini", {"effort": "medium"})
    assert provider_from_spec("chatgpt:gpt-test-mini").id == "chatgpt:gpt-test-mini"


def test_a_token_turned_down_is_refreshed_and_tried_again(openai_accounts):
    _sign_in(openai_accounts)
    turned_down = httpx2.Response(
        401,
        json={"error": {"code": "subscription_sharing_invalid_user", "message": "Invalid user", "type": "auth"}},
    )
    api = Api(turned_down, _openai_answer(*ANSWER))
    provider = _chatgpt(api)

    assert provider.complete(REQUEST).data == {"title": "Cats"}

    assert provider.tokens == ["access-1", "access-2"]
    assert [request.headers["authorization"] for request in api.requests] == ["Bearer access-1", "Bearer access-2"]


def test_what_the_plans_route_turns_down_says_why(openai_accounts):
    _signed_in()

    def turned_down(status, code, **error):
        body = {"error": {"code": code, "message": "Turned down", "type": "invalid_request_error", **error}}
        return Api(httpx2.Response(status, json=body))

    with pytest.raises(ProviderUnavailable, match="Usage limit reached") as limit:
        _chatgpt(turned_down(429, "subscription_sharing_usage_limit_exceeded")).complete(REQUEST)
    assert chatgpt_login.USAGE_URL in str(limit.value)
    with pytest.raises(ProviderError, match="text.format"):
        _chatgpt(turned_down(400, "subscription_sharing_unsupported_capability", param="text.format")).complete(REQUEST)
    with pytest.raises(ProviderUnavailable, match="try again later"):
        _chatgpt(turned_down(503, "subscription_sharing_usage_unavailable")).complete(REQUEST)
    failed = _response_event(
        "response.failed", "failed", error={"code": "subscription_sharing_usage_limit_exceeded", "message": "Limit"}
    )
    with pytest.raises(ProviderUnavailable, match="Usage limit reached"):
        _chatgpt(Api(_openai_answer(ANSWER[0], final=failed))).complete(REQUEST)


def test_without_a_sign_in_talks_fall_back(openai_accounts):
    provider = provider_from_spec("chatgpt")
    assert provider.id == "chatgpt:default"
    with pytest.raises(chatgpt_login.SignInNeeded, match="login chatgpt"):
        provider.complete(REQUEST)


def test_a_provider_asked_for_goes_first(openai_accounts, monkeypatch):
    _signed_in()
    assert settings.llm_spec() == "chatgpt"
    monkeypatch.setenv("TALKGENERATOR_LLM", "openrouter")
    assert settings.llm_spec() == "openrouter"
    assert "TALKGENERATOR_LLM has openrouter write your talks" in chatgpt_login.signed_in_message(
        chatgpt_login.stored()
    )
