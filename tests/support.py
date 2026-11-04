"""Helpers shared by the tests."""

import pytest

from talkgenerator import settings


def requires_keys(*keys):
    """Skip a test when the API keys it needs aren't configured (e.g. in CI)."""
    missing = [key for key in keys if not settings.env.str(key, "").strip()]
    return pytest.mark.skipif(bool(missing), reason="needs " + ", ".join(missing) + " in .env")
