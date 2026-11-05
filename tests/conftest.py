import os

import pytest
from environs import Env

# Tests talk to the live services (or to fakes), never to responses cached by earlier runs
os.environ.setdefault("DISABLE_CACHE", "1")


@pytest.fixture(autouse=True)
def _offline_tests_use_no_real_credentials(request, monkeypatch):
    """Run offline tests as in CI: without the API keys from a local .env or the environment.

    environs 15 keeps what it reads from .env inside its Env object instead of os.environ, and
    falls back to it for unset variables, so deleting environment variables alone doesn't hide
    those keys: swap in an Env that never read .env as well. Otherwise offline tests behave
    differently on a machine with keys, and their failure output can print real keys.
    """
    if request.node.get_closest_marker("network") is not None:
        return
    from talkgenerator import settings  # imported here so DISABLE_CACHE is set first

    monkeypatch.setattr(settings, "env", Env())
    credentials = {name for names in settings.required_keys.values() for name in names}
    for name in sorted(credentials | {"OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET"}):
        monkeypatch.delenv(name, raising=False)
