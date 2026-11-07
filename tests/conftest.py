import os

import pytest
from environs import Env

# Tests talk to the live services (or to fakes), never to responses cached by earlier runs
os.environ.setdefault("DISABLE_CACHE", "1")


@pytest.fixture(autouse=True)
def _offline_tests_use_no_real_credentials(request, monkeypatch, tmp_path):
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
    credentials |= {"OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET"}
    # No language model either, unless a test brings its own: offline talks are classic
    credentials |= {"TALKGENERATOR_LLM", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"}
    credentials |= {"TALKGENERATOR_LLM_EFFORT", "DISABLE_LLM"}
    # Nor an image generator (offline talks generate no pictures, unless a test brings its own), nor its keys
    credentials |= {"TALKGENERATOR_IMAGE_GENERATOR", "DISABLE_IMAGE_GENERATION", "TALKGENERATOR_GENERATED_IMAGES"}
    credentials |= {"TALKGENERATOR_IMAGE_COST_LIMIT", "TALKGENERATOR_IMAGE_QUALITY", "GEMINI_API_KEY", "GOOGLE_API_KEY"}
    credentials |= {"BFL_API_KEY", "COMFYUI_URL", "COMFYUI_CHECKPOINT", "COMFYUI_WORKFLOW", "AUTOMATIC1111_URL"}
    for name in sorted(credentials):
        monkeypatch.delenv(name, raising=False)
    # Nor the key that `talkgenerator login` keeps in the user's config folder, nor the pictures generated before
    monkeypatch.setenv("TALKGENERATOR_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("TALKGENERATOR_CACHE_DIR", str(tmp_path / "cache"))
    # Talks are classic unless a test asks for a theme (the default is random: see test_the_default_theme_is_random)
    monkeypatch.setenv("TALKGENERATOR_THEME", "classic")
