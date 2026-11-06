"""`talkgenerator login openrouter`: sign in to OpenRouter in your browser, and talkgenerator gets a key of its own,
so OpenRouter's free models write your talks without setting OPENROUTER_API_KEY. `talkgenerator logout openrouter`
forgets it again, and `talkgenerator login openrouter --status` tells how many free requests are left today.

It's OpenRouter's OAuth flow with PKCE (https://openrouter.ai/docs/use-cases/oauth-pkce). talkgenerator opens
OpenRouter's sign-in page with a code challenge and waits on localhost; once you agree, OpenRouter sends your browser
back there with a code, which talkgenerator trades for a key, proving with the code verifier that it was the one that
asked. With --headless (on a server, or over SSH), OpenRouter shows the code instead, and you paste it.

The key is an OpenRouter key like any other: it's called "talkgenerator" in your OpenRouter settings, where you can
give it a limit or revoke it. talkgenerator keeps it in its config folder (see talkgenerator.util.credentials).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import http.server
import importlib.util
import secrets
import socketserver
import sys
import time
import webbrowser
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Final, TextIO
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

from talkgenerator import settings
from talkgenerator.llm.openrouter import APP_HEADERS
from talkgenerator.util import credentials
from talkgenerator.util.http_util import redact

PROVIDER: Final = "openrouter"
AUTH_URL: Final = "https://openrouter.ai/auth"
KEYS_URL: Final = "https://openrouter.ai/api/v1/auth/keys"
KEY_URL: Final = "https://openrouter.ai/api/v1/key"
KEY_LABEL: Final = "talkgenerator"
# How long to wait for the browser to come back from OpenRouter (whose codes last 10 minutes)
WAIT_SECONDS: Final = 300
_TIMEOUT_SECONDS: Final = 30


class LoginError(Exception):
    """Signing in didn't work: the message says why (and never holds a key)."""


# PKCE (RFC 7636)


def new_verifier() -> str:
    return secrets.token_urlsafe(64)  # 86 characters, within PKCE's 43 to 128


def code_challenge(verifier: str) -> str:
    """The S256 code challenge of a verifier: its SHA-256, in URL-safe base64 without padding."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(challenge: str, callback_url: str | None = None, state: str | None = None) -> str:
    """OpenRouter's sign-in page. Without a callback, OpenRouter shows the code, to paste."""
    parameters = {"code_challenge": challenge, "code_challenge_method": "S256", "key_label": KEY_LABEL}
    if callback_url:
        parameters["callback_url"] = callback_url
    if state:
        parameters["state"] = state
    return f"{AUTH_URL}?{urlencode(parameters)}"


def exchange(code: str, verifier: str) -> str:
    """The key OpenRouter gives for a code, to the one that holds its verifier."""
    try:
        response = requests.post(
            KEYS_URL,
            json={"code": code, "code_verifier": verifier, "code_challenge_method": "S256"},
            headers=APP_HEADERS,
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise LoginError(f"OpenRouter can't be reached ({redact(error)})") from None
    if response.status_code != 200:
        raise LoginError(f"OpenRouter gave no key ({response.status_code}: {redact(_error_message(response))})")
    key = _json(response).get("key")
    if not isinstance(key, str) or not key.strip():
        raise LoginError("OpenRouter's answer held no key")
    return key.strip()


def key_details(key: str) -> dict[str, Any]:
    """What OpenRouter says about a key (its label, its credits, the free requests it has left today), or {} when it
    won't say (the key may have been revoked)."""
    try:
        response = requests.get(
            KEY_URL, headers={**APP_HEADERS, "Authorization": f"Bearer {key}"}, timeout=_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        return {}
    details = _json(response).get("data") if response.ok else None
    return details if isinstance(details, dict) else {}


def key_page(key: str) -> str:
    """The key's page in the OpenRouter settings of its owner, where they can give it a limit or revoke it."""
    return f"https://openrouter.ai/keys/{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


def _json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _error_message(response: requests.Response) -> str:
    error = _json(response).get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    return str(error or response.text[:200] or response.reason)


# WAITING FOR THE BROWSER

_PAGE: Final = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>talkgenerator</title></head>'
    '<body style="font-family: system-ui, sans-serif; max-width: 34em; margin: 4em auto; line-height: 1.5">'
    "<h1>{heading}</h1><p>{text}</p></body></html>"
)


class _CallbackServer(http.server.ThreadingHTTPServer):
    """Waits on localhost for the browser to come back from OpenRouter, with a code (or without one, when the user
    said no). Every connection gets a thread of its own, so connections that browsers open ahead of time, without a
    request, don't hold up the one with the code."""

    def __init__(self, state: str) -> None:
        super().__init__(("127.0.0.1", 0), _CallbackHandler)
        self.state = state
        self.answer: dict[str, str] | None = None

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)  # without HTTPServer's lookup of the host's name, which can be slow
        self.server_name, self.server_port = "localhost", self.server_address[1]

    @property
    def callback_url(self) -> str:
        return f"http://localhost:{self.server_port}/callback"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    server: _CallbackServer
    timeout = 5  # (and those connections are dropped after a while)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path != "/callback":
            self._respond(404, "Nothing here", "This is talkgenerator, waiting for you to sign in to OpenRouter.")
            return
        answer = {name: values[0] for name, values in parse_qs(url.query).items()}
        if answer.get("code") and answer.get("state") != self.server.state:
            # A code of another sign-in (which its verifier wouldn't fit anyway): keep waiting for ours
            self._respond(400, "That's not this sign-in", "Go back to talkgenerator, and sign in from there.")
            return
        self.server.answer = answer
        if answer.get("code"):
            self._respond(200, "Signed in", "talkgenerator is getting its key from OpenRouter: you can close this tab.")
        else:
            self._respond(200, "Not signed in", "OpenRouter gave talkgenerator no key. You can close this tab.")

    def _respond(self, status: int, heading: str, text: str) -> None:
        body = _PAGE.format(heading=html.escape(heading), text=html.escape(text)).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # quiet: the requests hold the code


def _code_from_browser(challenge: str, open_browser: Callable[[str], bool], wait_seconds: float, out: TextIO) -> str:
    state = secrets.token_urlsafe(16)
    with _CallbackServer(state) as server:
        url = authorization_url(challenge, server.callback_url, state)
        print(f"Sign in to OpenRouter in your browser. If it doesn't open, go to:\n\n  {url}\n", file=out)
        if not open_browser(url):
            print("(No browser to open here: on a computer without one, use --headless.)", file=out)
        print("Waiting for you to sign in (Ctrl+C stops)...", file=out, flush=True)
        server.timeout = 0.1  # (how often to look whether a handler's thread got the answer)
        deadline = time.monotonic() + wait_seconds
        while server.answer is None:
            if time.monotonic() > deadline:
                raise LoginError(f"no answer from the browser in {wait_seconds:g} seconds; try again")
            server.handle_request()
        answer = server.answer
    if not answer.get("code"):
        why = answer.get("error_description") or answer.get("error")
        raise LoginError("OpenRouter gave no code" + (f" ({why})" if why else ": did you say no?"))
    return answer["code"]


def _code_from_paste(challenge: str, ask: Callable[[str], str], out: TextIO) -> str:
    print(f"Sign in to OpenRouter at this address, on any device:\n\n  {authorization_url(challenge)}\n", file=out)
    code = ask("Then paste the code that OpenRouter shows: ").strip()
    if not code:
        raise LoginError("no code pasted")
    return code


# THE COMMANDS


def login(
    *,
    headless: bool = False,
    open_browser: Callable[[str], bool] | None = None,
    ask: Callable[[str], str] | None = None,
    out: TextIO | None = None,
    wait_seconds: float = WAIT_SECONDS,
) -> str:
    """Sign in to OpenRouter, and keep the key it gives talkgenerator; that key."""
    out = out or sys.stdout
    verifier = new_verifier()
    challenge = code_challenge(verifier)
    if headless:
        code = _code_from_paste(challenge, ask or input, out)
    else:
        code = _code_from_browser(challenge, open_browser or webbrowser.open, wait_seconds, out)
    key = exchange(code, verifier)
    created = datetime.now(UTC).isoformat(timespec="seconds")
    credentials.store(settings.config_dir(), PROVIDER, {"key": key, "label": KEY_LABEL, "created": created})
    return key


def signed_in_message(key: str) -> str:
    """What's now true, once signed in: where the key is kept, what it does, and what could be in its way."""
    path = credentials.credentials_file(settings.config_dir())
    lines = [f"Signed in to OpenRouter. talkgenerator keeps its key in {path}."]
    free = _free_requests(key_details(key))
    lines.append("OpenRouter's free models now write your talks" + (f": {free}." if free else "."))
    lines.append(
        f"The key is called {KEY_LABEL!r} at {key_page(key)}, where you can give it a limit or revoke it; "
        "`talkgenerator logout openrouter` forgets it here."
    )
    if settings.env.str("OPENROUTER_API_KEY", "").strip():
        lines.append("Note: OPENROUTER_API_KEY is set as well, and goes first. Remove it to use this key.")
    spec = settings.llm_spec()
    if spec == "none":
        lines.append("Note: DISABLE_LLM (or TALKGENERATOR_LLM=none) keeps your talks classic.")
    elif not spec.startswith(PROVIDER):
        lines.append(f"Note: TALKGENERATOR_LLM has {spec} write your talks.")
    if importlib.util.find_spec("openai") is None:
        lines.append("To have the models write talks, install the openai package: pip install 'talkgenerator[openai]'")
    return "\n".join(lines)


def status(out: TextIO | None = None) -> int:
    out = out or sys.stdout
    from_environment = settings.env.str("OPENROUTER_API_KEY", "").strip()
    key = from_environment or credentials.stored_key(settings.config_dir(), PROVIDER)
    if not key:
        print("Not signed in to OpenRouter: talkgenerator login openrouter (or set OPENROUTER_API_KEY)", file=out)
        return 1
    which = "OPENROUTER_API_KEY" if from_environment else "the key from talkgenerator login"
    details = key_details(key)
    if not details:
        print(f"OpenRouter doesn't know {which}: it may have been revoked. Sign in again.", file=out)
        return 1
    label = details.get("label")
    # (OpenRouter names a key without a label after the key itself, masked: that stays out of the terminal too)
    label = f" ({label!r})" if isinstance(label, str) and label and not label.startswith("sk-") else ""
    free = _free_requests(details)
    print(f"Signed in to OpenRouter with {which}{label}" + (f": {free}." if free else "."), file=out)
    return 0


def logout(out: TextIO | None = None) -> int:
    out = out or sys.stdout
    entry = credentials.forget(settings.config_dir(), PROVIDER)
    key = entry.get("key") if entry else None
    if not isinstance(key, str) or not key:
        print("talkgenerator has no OpenRouter key of its own: nothing to forget.", file=out)
    else:
        print(
            f"Signed out: talkgenerator forgot its OpenRouter key. The key works until you revoke it at {key_page(key)}",
            file=out,
        )
    if settings.env.str("OPENROUTER_API_KEY", "").strip():
        print("OPENROUTER_API_KEY is still set, so OpenRouter's models still write your talks.", file=out)
    return 0


def _free_requests(details: dict[str, Any]) -> str:
    """How many free requests (talks) the key has left today, as words, or "" if OpenRouter didn't say."""
    daily = details.get("free_model_daily_requests")
    if not isinstance(daily, dict) or not isinstance(daily.get("remaining"), int):
        return ""
    if not isinstance(daily.get("limit"), int):
        return f"{daily['remaining']} free requests left today, one per talk"
    words = f"{daily['remaining']} of today's {daily['limit']} free requests left, one per talk"
    if details.get("is_free_tier"):
        words += " (1,000 a day once the account has bought $10 of credits)"
    return words


def main(command: str, argv: Sequence[str]) -> int:
    """`talkgenerator login` and `talkgenerator logout`."""
    parser = argparse.ArgumentParser(
        prog=f"talkgenerator {command}",
        description=(
            "Sign in to OpenRouter, so its free models write your talks (talkgenerator keeps the key it gets)."
            if command == "login"
            else "Forget the OpenRouter key that talkgenerator login got."
        ),
    )
    parser.add_argument("provider", nargs="?", default=PROVIDER, choices=[PROVIDER], help="where to sign in")
    if command == "login":
        parser.add_argument(
            "--headless",
            action="store_true",
            help="on a computer without a browser: sign in on another device, and paste the code that OpenRouter shows",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="say whether you're signed in, and how many free requests are left today",
        )
    args = parser.parse_args(argv)
    if command == "logout":
        return logout()
    if args.status:
        return status()
    try:
        key = login(headless=args.headless)
    except LoginError as error:
        print(f"Not signed in: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped: not signed in.", file=sys.stderr)
        return 130
    print(signed_in_message(key))
    return 0
