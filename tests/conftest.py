import os

import pytest

# Tests talk to the live services (or to fakes), never to responses cached by earlier runs
os.environ.setdefault("DISABLE_CACHE", "1")


@pytest.fixture(autouse=True)
def _offline_tests_dont_sign_in_to_openverse(request, monkeypatch):
    """Offline tests fake Openverse's searches, so keep them from signing in with real credentials from .env."""
    if request.node.get_closest_marker("network") is None:
        monkeypatch.delenv("OPENVERSE_CLIENT_ID", raising=False)
        monkeypatch.delenv("OPENVERSE_CLIENT_SECRET", raising=False)
