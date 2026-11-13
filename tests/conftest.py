import os

import pytest
from environs import Env

# Tests talk to the live services (or to fakes), never to responses cached by earlier runs
os.environ.setdefault("DISABLE_CACHE", "1")


def pytest_addoption(parser):
    parser.addoption(
        "--bundled-fonts-only",
        action="store_true",
        help="measure texts as a computer without the themes' fonts does (CI's Ubuntu): with talkgenerator's own fonts "
        "and width tables only, and none of this computer's",
    )


def pytest_configure(config):
    if config.getoption("--bundled-fonts-only"):
        from pathlib import Path

        from talkgenerator.design import fonts
        from talkgenerator.util import os_util

        bundled = Path(os_util.to_actual_file("data/fonts"))
        fonts._font_folders = lambda: [bundled]
        fonts._font_index.cache_clear()


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
    credentials |= {"OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET", "DATA_GOV_API_KEY"}
    # No language model either, unless a test brings its own: offline talks are classic
    credentials |= {"TALKGENERATOR_LLM", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"}
    credentials |= {"TALKGENERATOR_LLM_EFFORT", "TALKGENERATOR_LLM_LEVEL", "DISABLE_LLM"}
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
    # And without real facts (Wikipedia's, Open Trivia DB's), unless a test brings fakes of their sources: see
    # tests/test_facts.py
    monkeypatch.setenv("DISABLE_FACTS", "1")
    # And with charts and diagrams as they are, without a picture first in their place (D73), whose search their
    # tests don't fake, and lists and diagrams without pattern breaks (an emoji or a picture in a punchline's place),
    # unless a test asks for them: see tests/test_less_text.py
    monkeypatch.setenv("DISABLE_PICTURE_FIRST", "1")
    monkeypatch.setenv("DISABLE_PATTERN_BREAKS", "1")
    # And title slides without a photo of the talk's world (D80), whose search their tests don't fake, unless a test
    # asks for one: see tests/test_playable.py
    monkeypatch.setenv("DISABLE_TITLE_PICTURES", "1")
