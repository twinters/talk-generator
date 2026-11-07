"""Configuration through environment variables, optionally loaded from a `.env` file.

The `.env` file is looked up in the current working directory first, and then next to the
package and in its parent folders (which covers editable installs from a git checkout).
Variables that are already set in the environment always win.

See `.env.example` for every supported variable.
"""

import functools
import logging
from pathlib import Path

import platformdirs
from environs import Env, EnvError

from talkgenerator.util import credentials

logger = logging.getLogger("talkgenerator")

env = Env()
_cwd_env_file = Path.cwd() / ".env"
if _cwd_env_file.is_file():
    env.read_env(str(_cwd_env_file), recurse=False)
env.read_env()

# Keys needed per source. Sources without their keys skip themselves; the other sources fill in.
required_keys = {
    "Reddit": ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
    "Unsplash": ["UNSPLASH_ACCESS_KEY"],
    "Pixabay": ["PIXABAY_KEY"],
    "Pexels": ["PEXELS_KEY"],
    "GIPHY": ["GIPHY_API_KEY"],
}


def reddit_auth() -> dict[str, str]:
    return {
        "client_id": env.str("REDDIT_CLIENT_ID", ""),
        "client_secret": env.str("REDDIT_CLIENT_SECRET", ""),
        "user_agent": env.str("REDDIT_USER_AGENT", ""),
    }


def unsplash_auth() -> dict[str, str]:
    return {"unsplash_access_key": env.str("UNSPLASH_ACCESS_KEY", "")}


def pixabay_auth() -> dict[str, str]:
    return {"pixabay_key": env.str("PIXABAY_KEY", "")}


def pexels_auth() -> dict[str, str]:
    return {"pexels_key": env.str("PEXELS_KEY", "")}


def giphy_auth() -> dict[str, str]:
    return {"giphy_api_key": env.str("GIPHY_API_KEY", "")}


def data_gov_auth() -> dict[str, str]:
    """An api.data.gov key, which US government APIs take (the Smithsonian's Open Access images, for one). Optional:
    without it, the other museums fill in."""
    return {"data_gov_api_key": env.str("DATA_GOV_API_KEY", "").strip()}


def openverse_auth() -> dict[str, str]:
    """A registered Openverse app's credentials. Optional: without them, Openverse is searched anonymously."""
    return {
        "client_id": env.str("OPENVERSE_CLIENT_ID", "").strip(),
        "client_secret": env.str("OPENVERSE_CLIENT_SECRET", "").strip(),
    }


def unsplash_app_name() -> str:
    """The app name Unsplash knows you by, used in the utm_source of links back to Unsplash."""
    return env.str("UNSPLASH_APP_NAME", "talkgenerator")


def cache_dir() -> str:
    """Folder of the on-disk cache of API responses (default: the user's cache folder)."""
    return env.str("TALKGENERATOR_CACHE_DIR", "") or platformdirs.user_cache_dir("talkgenerator", appauthor=False)


def config_dir() -> str:
    """Folder of what talkgenerator keeps for you, such as the key `talkgenerator login` gets (default: the user's
    config folder)."""
    return env.str("TALKGENERATOR_CONFIG_DIR", "") or platformdirs.user_config_dir("talkgenerator", appauthor=False)


def conceptnet_api_url() -> str:
    """Base URL of the ConceptNet API; point it at a self-hosted instance if you have one."""
    return env.str("CONCEPTNET_API_URL", "https://api.conceptnet.io").rstrip("/")


def theme() -> str:
    """The look of talks that don't ask for one: TALKGENERATOR_THEME, as --theme takes it (see
    talkgenerator.design.themes.catalog). Without it, random: a theme the talk's seed picks; classic is the 2019
    template."""
    return env.str("TALKGENERATOR_THEME", "").strip() or "random"


def llm_spec() -> str:
    """The language model to write talks with, as "provider:model" (see talkgenerator.llm.providers).

    Without TALKGENERATOR_LLM, the models of your ChatGPT plan write the talks once you've signed in with ChatGPT
    (talkgenerator login chatgpt), else OpenRouter's free models when there's an OpenRouter key (they cost nothing;
    see openrouter_api_key), and talks are classic otherwise: a paid model only writes talks when it's asked for.
    With DISABLE_LLM=1, it's "none": talks are then classic, as the 2019 generator made them."""
    if is_source_disabled("LLM"):
        return "none"
    spec = env.str("TALKGENERATOR_LLM", "").strip()
    if spec:
        return spec
    if chatgpt_signed_in():
        return "chatgpt"
    return "openrouter" if openrouter_api_key() else "none"


def chatgpt_signed_in() -> bool:
    """Whether `talkgenerator login chatgpt` signed in, with the permission to use your ChatGPT plan."""
    record = credentials.stored(config_dir(), "chatgpt")
    return record.get("plan_usage") is True and bool(record.get("refresh_token") or record.get("access_token"))


def openrouter_api_key() -> str:
    """OPENROUTER_API_KEY, or else the key that `talkgenerator login openrouter` got."""
    return env.str("OPENROUTER_API_KEY", "").strip() or credentials.stored_key(config_dir(), "openrouter")


def anthropic_api_key() -> str:
    return env.str("ANTHROPIC_API_KEY", "").strip()


def openai_api_key() -> str:
    return env.str("OPENAI_API_KEY", "").strip()


def llm_effort() -> str | None:
    """How hard a language model thinks before it writes (TALKGENERATOR_LLM_EFFORT: low, medium, high, ...), for
    the models that take it. None leaves it to the provider's adapter."""
    return env.str("TALKGENERATOR_LLM_EFFORT", "").strip().lower() or None


def is_source_disabled(name: str) -> bool:
    """Check whether a content source is switched off via DISABLE_<NAME>=1.

    Useful on resource-constrained deployments, or when a source's API has gone stale.
    """
    try:
        return env.bool(f"DISABLE_{name.upper()}", False)
    except EnvError:
        logger.warning("Ignoring DISABLE_%s: expected a boolean such as 1 or 0.", name.upper())
        return False


def sources_without_keys() -> list[str]:
    """The sources that need keys (see required_keys) and have none, leaving out the ones that are switched off."""
    return [name for name, keys in required_keys.items() if not is_source_disabled(name) and _get_missing_keys(keys)]


def _get_missing_keys(key_variables: list[str]) -> list[str]:
    return [key_name for key_name in key_variables if not env.str(key_name, "").strip()]


def check_keys(key_variables: list[str], name: str) -> bool:
    missing = _get_missing_keys(key_variables)
    if missing:
        logger.warning("No %s credentials (missing %s): %s content is skipped.", name, ", ".join(missing), name)
        return False
    return True


def check_environment_variables() -> bool:
    """Report which keyed sources can't be used. Generation still works with the remaining sources."""
    sources_to_check = {name: keys for name, keys in required_keys.items() if not is_source_disabled(name)}
    results = [check_keys(keys, name) for name, keys in sources_to_check.items()]
    valid_env_file = all(results)
    if not valid_env_file:
        print_env_file_warning()
    return valid_env_file


@functools.cache
def report_missing_keys() -> bool:
    """check_environment_variables, once per process: a web server generating many talks logs it only once."""
    return check_environment_variables()


def print_env_file_warning() -> None:
    env_message = """
    Some API keys are missing, so talkgenerator will use fewer image sources.

    Copy .env.example to .env (in the folder you run talkgenerator from) and fill in the keys.
    See https://github.com/twinters/talk-generator#api-keys for where to get them.
    """
    logger.warning(env_message)
