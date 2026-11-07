"""`talkgenerator login chatgpt`: Sign in with ChatGPT, so that the models of your ChatGPT plan write your talks
(docs/v5-plan.md, section 5.5). `talkgenerator logout chatgpt` signs out again, and `talkgenerator login chatgpt
--status` says which account is signed in, and which models it has.

It's OpenAI's sign-in for open-source apps that run on your own computer, in preview
(https://developers.openai.com/siwc/token-sharing-open-source): OAuth with PKCE in your browser, which comes back to
talkgenerator on 127.0.0.1. The first sign-in registers talkgenerator with your account, and OpenAI issues it a client
ID of its own, which later sign-ins reuse, as they reuse this computer's host ID (an opaque name, made up once). A
sign-in gives an access token that lasts an hour, and a refresh token that lasts 30 days and is replaced with every
refresh (so a talk a month keeps you signed in). talkgenerator checks the ID token against OpenAI's published keys,
keeps the tokens in its config folder (see talkgenerator.util.credentials), and never logs them. Signing out ends the
sign-in at OpenAI and forgets the tokens; the registration stays, for the next sign-in.

The talks' requests go to OpenAI's Responses API with the access token (talkgenerator.llm.chatgpt), and count toward
your ChatGPT plan's usage (on Plus, a five-hour limit that every app on your plan shares), which you can follow at
https://chatgpt.com/settings/usage. Hosted apps, talkgenerator.com among them, can't offer this yet.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import json
import os
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final, TextIO
from urllib.parse import urlencode

import requests

from talkgenerator import settings
from talkgenerator.llm.base import ProviderUnavailable
from talkgenerator.llm.login import CallbackServer, LoginError, code_challenge, new_verifier
from talkgenerator.util import credentials
from talkgenerator.util.http_util import redact

PROVIDER: Final = "chatgpt"
ISSUER: Final = "https://auth.openai.com"
AUTHORIZE_URL: Final = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL: Final = f"{ISSUER}/api/accounts/oauth/token"
REVOKE_URL: Final = f"{ISSUER}/api/accounts/oauth/revoke"
KEYS_URL: Final = f"{ISSUER}/.well-known/jwks.json"
# The API that the tokens are for, which the talks' requests go to
API_URL: Final = "https://api.openai.com/v1"
USAGE_URL: Final = "https://chatgpt.com/settings/usage"
# The client ID of a first sign-in, which registers talkgenerator with the account, under this name
REGISTRATION: Final = "dynamic_agent_client"
AGENT_NAME: Final = "talkgenerator"
# Permission to use the ChatGPT plan for requests; besides it, who the user is, and staying signed in
PLAN_SCOPE: Final = "chatgpt.tokens.use.direct"
SCOPES: Final = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"
CALLBACK_PATH: Final = "/auth/callback"
WAIT_SECONDS: Final = 300
# Why a sign-in may have been turned down: OpenAI's page then says "A required permission is unavailable", with
# Continue greyed out (as it did for a ChatGPT account without a subscription, the first time this was tried)
NO_PLAN: Final = (
    "If it said that a required permission is unavailable, your ChatGPT plan (or workspace) can't be used in other "
    "apps, such as talkgenerator: that takes a plan like Plus or Pro (and talkgenerator login chatgpt --new-account "
    "signs in with another account)"
)
# An access token with less than this left is refreshed before it's used, so that it can't run out during a request
REFRESH_MARGIN_SECONDS: Final = 300
_TIMEOUT_SECONDS: Final = 30
_REVOKE_BACKOFF_SECONDS = 0.5  # (before trying a sign-out again, doubling)
# Answers to a refresh that mean its refresh token can't be used anymore: then only signing in again helps
_ENDED: Final = frozenset(
    {
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
    }
)
# What signing out forgets (the registration stays: the host ID, client ID and account, for the next sign-in)
_SESSION: Final = (
    "id_token",
    "access_token",
    "refresh_token",
    "token_type",
    "expires_at",
    "earliest_refresh_at",
    "scopes",
    "plan_usage",
    "saved_at",
)
# SHA-256's DER prefix in a PKCS #1 v1.5 signature (RFC 8017, section 9.2), as RS256 signs
_SHA256_INFO: Final = bytes.fromhex("3031300d060960864801650304020105000420")


class SignInNeeded(ProviderUnavailable):
    """No sign-in with ChatGPT that a request can use: the message says what to do."""


class TokenError(LoginError):
    """OpenAI's token endpoint turned a request down, with an OAuth error code (such as invalid_grant)."""

    def __init__(self, status: int, code: str, description: str) -> None:
        super().__init__(f"{status}: {code}" + (f" ({description})" if description else ""))
        self.status, self.code = status, code


# WHAT'S KEPT


def stored() -> dict[str, Any]:
    """What talkgenerator keeps of its sign-in with ChatGPT: the registration, and while signed in, the tokens."""
    return credentials.stored(settings.config_dir(), PROVIDER)


def _keep(record: Mapping[str, Any]) -> None:
    credentials.store(settings.config_dir(), PROVIDER, dict(record))


def signed_in(record: Mapping[str, Any]) -> bool:
    return bool(record.get("refresh_token") or record.get("access_token"))


def _signed_out(record: Mapping[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in record.items() if name not in _SESSION}


def host_id() -> str:
    """This computer's host ID, which every sign-in from it sends: made up once, and kept. It's an opaque name, which
    says nothing about the user."""
    record = stored()
    known = record.get("host_id")
    if isinstance(known, str) and known:
        return known
    made = f"urn:uuid:{uuid.uuid4()}"
    _keep({**record, "host_id": made})
    return made


def default_model() -> str:
    """The model that talks use when the spec names none: the first one the account lists (as of the last sign-in or
    --status), or "" when that isn't known."""
    models = stored().get("models")
    return models[0] if isinstance(models, list) and models and isinstance(models[0], str) else ""


# SIGNING IN


def authorization_url(
    *,
    client_id: str,
    host: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    challenge: str,
    id_token_hint: str | None = None,
    login_hint: str | None = None,
    consent: bool = False,
) -> str:
    """OpenAI's sign-in page: to register talkgenerator (with client_id REGISTRATION), or to sign in again with the
    client ID it was issued, without choosing the account again (id_token_hint) or suggesting it (login_hint)."""
    parameters = {"client_id": client_id}
    if client_id == REGISTRATION:
        parameters["agent_name_hint"] = AGENT_NAME
    parameters |= {
        "ext_agent_host_id": host,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "resource": API_URL,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if id_token_hint:
        parameters["id_token_hint"] = id_token_hint
    if login_hint:
        parameters["login_hint"] = login_hint
    if consent:
        parameters["prompt"] = "consent"  # (asking again for the permission to use the plan, turned down before)
    return f"{AUTHORIZE_URL}?{urlencode(parameters)}"


def login(
    *,
    new_account: bool = False,
    open_browser: Callable[[str], bool] | None = None,
    out: TextIO | None = None,
    wait_seconds: float = WAIT_SECONDS,
) -> dict[str, Any]:
    """Sign in with ChatGPT, and keep the sign-in; what's kept. The first sign-in (and one for a new account)
    registers talkgenerator with the account; later ones sign in with that registration."""
    out = out or sys.stdout
    host = host_id()
    record = stored()
    if new_account and record.get("client_id"):
        if signed_in(record):
            _revoke(record)  # (the other account's sign-in ends here)
        _keep({"host_id": host})
    browser = open_browser or webbrowser.open
    try:
        return _sign_in(host, browser, wait_seconds, out)
    except TokenError as error:
        if error.code != "invalid_grant":
            raise
        # OpenAI's advice: drop the code, and sign in afresh with the client ID it issued (a first sign-in's code
        # can be turned down so: it happened in the first sign-in tried for real)
        print("OpenAI turned that sign-in's code down: signing in once more (your browser opens again)...", file=out)
        return _sign_in(host, browser, wait_seconds, out)


def _sign_in(host: str, open_browser: Callable[[str], bool], wait_seconds: float, out: TextIO) -> dict[str, Any]:
    """One sign-in: to register talkgenerator, or with the registration it has."""
    record = stored()
    known = record.get("client_id")
    client_id = known if isinstance(known, str) and known else REGISTRATION
    registering = client_id == REGISTRATION
    hint = record.get("id_token") if not registering else None
    email = record.get("email") if not registering else None
    answer, verifier, nonce, redirect_uri = _authorize(
        client_id=client_id,
        host=host,
        id_token_hint=hint if isinstance(hint, str) and hint else None,
        login_hint=email if isinstance(email, str) and email else None,
        consent=not registering and record.get("plan_usage") is False,
        open_browser=open_browser,
        wait_seconds=wait_seconds,
        out=out,
    )
    if not answer.get("code"):
        why = answer.get("error_description") or answer.get("error")
        message = "ChatGPT didn't sign you in" + (f" ({why})" if why else "")
        if answer.get("error") == "access_denied":
            message += f". {NO_PLAN}"
        raise LoginError(message)
    issued = answer.get("client_id") or ""
    if registering:
        if not issued:
            raise LoginError("OpenAI didn't register talkgenerator: no client ID came back")
        client_id = issued
        record = {"host_id": host, "client_id": client_id}
        _keep(record)  # (a sign-in that fails from here on can try again with it)
    elif issued and issued != client_id:
        raise LoginError("the sign-in came back for another registration of talkgenerator; try again")
    tokens = _token_request(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": answer["code"],
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
            "resource": API_URL,
        }
    )
    id_token = tokens.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise LoginError("OpenAI's answer held no ID token")
    claims = verified_claims(id_token, client_id=client_id, nonce=nonce)
    if record.get("subject") and claims["sub"] != record["subject"]:
        raise LoginError(
            "that's another ChatGPT account than the one talkgenerator is registered with; to switch accounts: "
            "talkgenerator login chatgpt --new-account"
        )
    granted = str(tokens.get("scope") or answer.get("scope") or SCOPES).split()  # (none said: all that was asked)
    kept = {
        **_signed_out(record),
        "host_id": host,
        "client_id": client_id,
        "issuer": ISSUER,
        "subject": claims["sub"],
        "email": claims.get("email") if isinstance(claims.get("email"), str) else "",
        **_session(tokens, scopes=granted),
    }
    if kept["plan_usage"]:
        kept["models"] = list_models(kept["access_token"]) or kept.get("models") or []
    _keep(kept)
    return kept


def _authorize(
    *,
    client_id: str,
    host: str,
    id_token_hint: str | None,
    login_hint: str | None,
    consent: bool,
    open_browser: Callable[[str], bool],
    wait_seconds: float,
    out: TextIO,
) -> tuple[dict[str, str], str, str, str]:
    """Send the user to OpenAI's sign-in page, and wait for the browser to come back from it: the browser's answer,
    and this attempt's verifier, nonce and redirect URI."""
    state, nonce, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(16), new_verifier()
    with CallbackServer(
        state,
        service="ChatGPT",
        path=CALLBACK_PATH,
        host="127.0.0.1",
        strict=True,
        done="talkgenerator is finishing your sign-in with ChatGPT: you can close this tab.",
        refused="ChatGPT didn't sign talkgenerator in. You can close this tab.",
    ) as server:
        redirect_uri = server.callback_url
        page: dict[str, Any] = {
            "client_id": client_id,
            "host": host,
            "redirect_uri": redirect_uri,
            "state": state,
            "nonce": nonce,
            "challenge": code_challenge(verifier),
            "login_hint": login_hint,
            "consent": consent,
        }
        # The address shown leaves the ID token out, so that it stays out of terminals (and what they keep)
        shown = authorization_url(**page)
        print(f"Continue with ChatGPT in your browser. If it doesn't open, go to:\n\n  {shown}\n", file=out)
        if not open_browser(authorization_url(**page, id_token_hint=id_token_hint)):
            print("(No browser to open here: signing in with ChatGPT needs one on this computer.)", file=out)
        print("Waiting for you to sign in (Ctrl+C stops)...", file=out, flush=True)
        answer = server.wait(wait_seconds)
    return answer, verifier, nonce, redirect_uri


def _token_request(form: Mapping[str, str]) -> dict[str, Any]:
    """POST the form to OpenAI's token endpoint: its answer, or TokenError (or LoginError, if it can't be reached)."""
    try:
        response = requests.post(
            TOKEN_URL, data=dict(form), headers={"Accept": "application/json"}, timeout=_TIMEOUT_SECONDS
        )
    except requests.RequestException as error:
        raise LoginError(f"OpenAI can't be reached ({redact(error)})") from None
    answer = _json(response)
    if response.status_code != 200:
        problem: Any = answer.get("error")
        description: Any = answer.get("error_description")
        if isinstance(problem, dict):  # (an error object, as OpenAI's APIs have them)
            problem, description = problem.get("code") or problem.get("type"), problem.get("message")
        reason = str(problem or response.reason or "error")
        raise TokenError(response.status_code, reason, redact(description or "")[:200])
    return answer


def _session(tokens: Mapping[str, Any], *, scopes: Sequence[str], refresh_token: str = "") -> dict[str, Any]:
    """What a sign-in keeps of an answer of the token endpoint: the tokens, when the access token runs out, and what
    the sign-in allows."""
    access = tokens.get("access_token")
    if not isinstance(access, str) or not access:
        raise LoginError("OpenAI's answer held no access token")
    lifetime = tokens.get("expires_in")
    lasts = lifetime if isinstance(lifetime, int | float) and lifetime > 0 else 3600
    session: dict[str, Any] = {
        "access_token": access,
        "refresh_token": tokens.get("refresh_token") or refresh_token,  # (each refresh gives the next one)
        "token_type": tokens.get("token_type") or "Bearer",
        "expires_at": time.time() + lasts,
        "scopes": list(scopes),
        "plan_usage": PLAN_SCOPE in scopes,
        "saved_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if isinstance(tokens.get("id_token"), str):
        session["id_token"] = tokens["id_token"]
    if isinstance(tokens.get("earliest_refresh_at"), int | float):
        session["earliest_refresh_at"] = tokens["earliest_refresh_at"]
    return session


# THE ID TOKEN

_keys: dict[str, tuple[int, int]] = {}  # OpenAI's signing keys, by key ID: (modulus, exponent)
_keys_lock = threading.Lock()


def verified_claims(
    id_token: str, *, client_id: str, nonce: str | None = None, now: float | None = None
) -> dict[str, Any]:
    """The claims of an ID token, once its signature fits one of OpenAI's published keys and it's OpenAI's, for this
    client, not expired, of this sign-in (its nonce), and names the account."""
    try:
        header_part, payload_part, signature_part = id_token.split(".")
        header = json.loads(_unbase64(header_part))
        claims = json.loads(_unbase64(payload_part))
        signature = _unbase64(signature_part)
        signed = f"{header_part}.{payload_part}".encode("ascii")
    except ValueError:
        raise LoginError("OpenAI's ID token can't be read") from None
    if not isinstance(header, dict) or not isinstance(claims, dict) or header.get("alg") != "RS256":
        raise LoginError("OpenAI's ID token isn't signed the way OpenAI signs them (RS256)")
    if not _rs256_valid(signed, signature, *_signing_key(str(header.get("kid", "")))):
        raise LoginError("the ID token's signature doesn't fit OpenAI's keys")
    audience = claims.get("aud")
    audiences = [audience] if isinstance(audience, str) else audience if isinstance(audience, list) else []
    expires = claims.get("exp")
    if claims.get("iss") != ISSUER:
        raise LoginError("the ID token isn't OpenAI's")
    if client_id not in audiences:
        raise LoginError("the ID token is for another app")
    if not isinstance(expires, int | float) or expires < (time.time() if now is None else now) - 60:
        raise LoginError("the ID token has expired")
    if nonce is not None and claims.get("nonce") != nonce:
        raise LoginError("the ID token is of another sign-in")
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise LoginError("the ID token doesn't say which account signed in")
    return claims


def _unbase64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _signing_key(key_id: str) -> tuple[int, int]:
    """OpenAI's signing key with that ID, fetched again when it's new (OpenAI rotates its keys)."""
    with _keys_lock:
        if key_id not in _keys:
            _keys.clear()
            _keys.update(_published_keys())
        key = _keys.get(key_id)
    if key is None:
        raise LoginError("the ID token is signed with a key that OpenAI doesn't publish")
    return key


def _published_keys() -> dict[str, tuple[int, int]]:
    try:
        response = requests.get(KEYS_URL, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise LoginError(f"OpenAI's keys can't be fetched ({redact(error)})") from None
    keys = _json(response).get("keys") if response.ok else None
    found = {}
    for key in keys if isinstance(keys, list) else []:
        if isinstance(key, dict) and key.get("kty") == "RSA" and isinstance(key.get("n"), str):
            if isinstance(key.get("e"), str):
                modulus, exponent = (int.from_bytes(_unbase64(key[part]), "big") for part in ("n", "e"))
                found[str(key.get("kid", ""))] = (modulus, exponent)
    return found


def _rs256_valid(signed: bytes, signature: bytes, modulus: int, exponent: int) -> bool:
    """Whether the signature is the RSA key's PKCS #1 v1.5 signature of the SHA-256 of what's signed (RFC 8017,
    section 8.2.2): raised to the key's exponent, it has to be exactly the padded hash."""
    size = (modulus.bit_length() + 7) // 8
    info = _SHA256_INFO + hashlib.sha256(signed).digest()
    if len(signature) != size or size < len(info) + 11:
        return False
    value = int.from_bytes(signature, "big")
    if value >= modulus:
        return False
    expected = b"\x00\x01" + b"\xff" * (size - len(info) - 3) + b"\x00" + info
    return hmac.compare_digest(pow(value, exponent, modulus).to_bytes(size, "big"), expected)


# THE ACCESS TOKEN, FOR REQUESTS

_refreshing_here = threading.Lock()


def access_token(rejected: str | None = None) -> str:
    """An access token of the sign-in for a request: the kept one, or a refreshed one when it's (nearly) run out or
    a request just turned it down (rejected). SignInNeeded when there's no sign-in to use."""
    record = _usable(stored())
    if rejected is None and not _due(record):
        return str(record["access_token"])
    with _one_refresh_at_a_time():
        record = _usable(stored())  # (another request may have refreshed it in the meantime)
        if record["access_token"] != rejected and not _due(record):
            return str(record["access_token"])
        return str(_refresh(record)["access_token"])


def _usable(record: dict[str, Any]) -> dict[str, Any]:
    if not signed_in(record):
        raise SignInNeeded("ChatGPT's models need you to sign in first: talkgenerator login chatgpt")
    if not record.get("plan_usage"):
        raise SignInNeeded(
            "you didn't allow talkgenerator to use your ChatGPT plan: run talkgenerator login chatgpt again and "
            "allow it (or have another provider write your talks)"
        )
    return record


def _due(record: Mapping[str, Any]) -> bool:
    """Whether the access token needs refreshing before a request: it's (nearly) run out, and OpenAI takes a refresh
    by now."""
    now = time.time()
    expires = record.get("expires_at")
    if not record.get("access_token") or not isinstance(expires, int | float) or now >= expires:
        return True
    earliest = record.get("earliest_refresh_at")
    if isinstance(earliest, int | float) and now < earliest:
        return False
    return now >= expires - REFRESH_MARGIN_SECONDS


def _refresh(record: dict[str, Any]) -> dict[str, Any]:
    """Refresh the sign-in: its new access token, and the refresh token that replaces the one used."""
    refresh_token = record.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        _keep(_signed_out(record))
        raise SignInNeeded("the sign-in with ChatGPT has run out: talkgenerator login chatgpt signs in again")
    try:
        tokens = _token_request(
            {
                "grant_type": "refresh_token",
                "client_id": str(record.get("client_id", "")),
                "refresh_token": refresh_token,
                "resource": API_URL,
            }
        )
        granted = str(tokens["scope"]).split() if tokens.get("scope") else record.get("scopes", [])
        refreshed = {**record, **_session(tokens, scopes=granted, refresh_token=refresh_token)}
    except TokenError as error:
        if error.code in _ENDED:
            _keep(_signed_out(record))  # (a temporary problem never gets here: the tokens stay for those)
            raise SignInNeeded(
                "the sign-in with ChatGPT has ended: talkgenerator login chatgpt signs in again"
            ) from None
        raise ProviderUnavailable(f"the sign-in with ChatGPT can't be refreshed now ({error})") from None
    except LoginError as error:
        raise ProviderUnavailable(f"the sign-in with ChatGPT can't be refreshed now ({error})") from None
    _keep(refreshed)
    return refreshed


@contextmanager
def _one_refresh_at_a_time() -> Iterator[None]:
    """Hold the refresh lock, of this process's threads and (a lock file by the credentials) of other talkgenerator
    processes: a refresh token works once, so two refreshes with the same one would sign the second out."""
    lock_file = credentials.credentials_file(settings.config_dir()).with_name(f"{PROVIDER}.lock")
    with _refreshing_here:
        lock_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        while True:
            try:
                descriptor = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                break
            except FileExistsError:
                try:
                    stale = time.time() - lock_file.stat().st_mtime > 2 * _TIMEOUT_SECONDS
                except FileNotFoundError:
                    continue  # (just let go of)
                if stale:  # (left behind by a process that ended halfway through a refresh)
                    lock_file.unlink(missing_ok=True)
                else:
                    time.sleep(0.05)
        try:
            yield
        finally:
            os.close(descriptor)
            lock_file.unlink(missing_ok=True)


def list_models(token: str) -> list[str]:
    """The models that the signed-in account can use, as OpenAI lists them (their slugs, which requests name), or []
    if it won't say."""
    try:
        response = requests.get(
            f"{API_URL}/models", headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        return []
    answer = _json(response) if response.ok else {}
    entries = answer.get("data", answer.get("models"))
    models = []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("visibility", "list") == "list":
            slug = entry.get("slug") or entry.get("id")
            if isinstance(slug, str) and slug:
                models.append(slug)
    return models


# SIGNING OUT


def _revoke(record: Mapping[str, Any]) -> bool:
    """End the sign-in at OpenAI (revoking its refresh token): whether OpenAI confirmed it. Network trouble and
    OpenAI's own problems are tried again, twice."""
    token, client_id = record.get("refresh_token"), record.get("client_id")
    if not isinstance(token, str) or not token or not isinstance(client_id, str) or not client_id:
        return False
    for attempt in range(3):
        try:
            response = requests.post(
                REVOKE_URL,
                data={"token": token, "token_type_hint": "refresh_token", "client_id": client_id},
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            response = None
        if response is not None and response.status_code < 500:
            return response.status_code == 200  # (also when the token was invalid already)
        if attempt < 2:
            time.sleep(_REVOKE_BACKOFF_SECONDS * 2**attempt)
    return False


def logout(out: TextIO | None = None) -> int:
    out = out or sys.stdout
    record = stored()
    if not signed_in(record):
        print("Not signed in with ChatGPT: nothing to sign out of.", file=out)
        return 0
    confirmed = _revoke(record)
    _keep(_signed_out(record))
    if confirmed:
        print(
            "Signed out of ChatGPT: OpenAI ended talkgenerator's sign-in, and talkgenerator forgot its tokens.",
            file=out,
        )
    else:
        print(
            "talkgenerator forgot its ChatGPT tokens, but OpenAI didn't confirm that the sign-in ended: to be sure, "
            "disconnect talkgenerator in ChatGPT's settings.",
            file=out,
        )
    return 0


# WHAT'S SAID


def status(out: TextIO | None = None) -> int:
    out = out or sys.stdout
    record = stored()
    who = record.get("email") or "your ChatGPT account"
    if not signed_in(record):
        print("Not signed in with ChatGPT: talkgenerator login chatgpt", file=out)
        return 1
    try:
        token = access_token()
    except ProviderUnavailable as error:
        print(f"Signed in with ChatGPT as {who}, but {error}", file=out)
        return 1
    print(f"Signed in with ChatGPT as {who}. Talks use your ChatGPT plan: its usage is at {USAGE_URL}", file=out)
    models = list_models(token)
    if models:
        _keep({**stored(), "models": models})
        print(f"Its models: {', '.join(models)} (talks use {models[0]}; --llm chatgpt:<model> picks another)", file=out)
    return 0


def signed_in_message(record: Mapping[str, Any], *, welcome: bool = False) -> str:
    """What's now true, once signed in: who's signed in, where it's kept, what it does, and what could be in its way.
    With welcome (the first sign-in that may use the plan), what using the plan means."""
    who = record.get("email") or "your ChatGPT account"
    path = credentials.credentials_file(settings.config_dir())
    lines = [f"Signed in with ChatGPT as {who}. talkgenerator keeps the sign-in in {path}."]
    if not record.get("plan_usage"):
        lines.append(
            "But you didn't allow talkgenerator to use your ChatGPT plan, so it won't send ChatGPT's models any "
            "requests: run talkgenerator login chatgpt again and allow it, or have another provider write your talks."
        )
        return "\n".join(lines)
    if welcome:
        lines.append(
            "You're using your ChatGPT plan: talkgenerator's requests to ChatGPT's models count toward its usage (on "
            f"Plus, a five-hour limit that the other apps on your plan share). Manage usage: {USAGE_URL}"
        )
    models = record.get("models") if isinstance(record.get("models"), list) else []
    if models:
        lines.append(f"ChatGPT's models now write your talks: {models[0]} (--llm chatgpt:<model> picks another).")
    else:
        lines.append("ChatGPT's models now write your talks.")
    lines.append(
        "`talkgenerator logout chatgpt` signs out; you can also disconnect talkgenerator in ChatGPT's settings."
    )
    spec = settings.llm_spec()
    if spec == "none":
        lines.append("Note: DISABLE_LLM (or TALKGENERATOR_LLM=none) keeps your talks classic.")
    elif not spec.startswith(PROVIDER):
        lines.append(f"Note: TALKGENERATOR_LLM has {spec} write your talks.")
    if importlib.util.find_spec("openai") is None:
        lines.append("To have the models write talks, install the openai package: pip install 'talkgenerator[openai]'")
    return "\n".join(lines)


def _json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def main(command: str, args: argparse.Namespace) -> int:
    """`talkgenerator login chatgpt` (with --status, or --new-account) and `talkgenerator logout chatgpt`."""
    if command == "logout":
        return logout()
    if args.status:
        return status()
    if args.headless:
        print(
            "Not signed in: signing in with ChatGPT comes back to talkgenerator on this computer (127.0.0.1), so it "
            "needs a browser here.",
            file=sys.stderr,
        )
        return 1
    try:
        record = login(new_account=args.new_account)
    except LoginError as error:
        print(f"Not signed in: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped: not signed in.", file=sys.stderr)
        return 130
    welcome = record.get("plan_usage") is True and not record.get("welcomed")
    print(signed_in_message(record, welcome=welcome))
    if welcome:  # (only the first time)
        _keep({**stored(), "welcomed": True})
    return 0
