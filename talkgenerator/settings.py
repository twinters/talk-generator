"""Configuration through environment variables, optionally loaded from a `.env` file.

The `.env` file is looked up in the current working directory first, and then next to the
package and in its parent folders (which covers editable installs from a git checkout).
Variables that are already set in the environment always win.

See `.env.example` for every supported variable.
"""

import logging
from pathlib import Path

import platformdirs
from environs import Env, EnvError

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


def unsplash_app_name() -> str:
    """The app name Unsplash knows you by, used in the utm_source of links back to Unsplash."""
    return env.str("UNSPLASH_APP_NAME", "talkgenerator")


def cache_dir() -> str:
    """Folder of the on-disk cache of API responses (default: the user's cache folder)."""
    return env.str("TALKGENERATOR_CACHE_DIR", "") or platformdirs.user_cache_dir("talkgenerator", appauthor=False)


def conceptnet_api_url() -> str:
    """Base URL of the ConceptNet API; point it at a self-hosted instance if you have one."""
    return env.str("CONCEPTNET_API_URL", "https://api.conceptnet.io").rstrip("/")


def is_source_disabled(name: str) -> bool:
    """Check whether a content source is switched off via DISABLE_<NAME>=1.

    Useful on resource-constrained deployments, or when a source's API has gone stale.
    """
    try:
        return env.bool(f"DISABLE_{name.upper()}", False)
    except EnvError:
        logger.warning("Ignoring DISABLE_%s: expected a boolean such as 1 or 0.", name.upper())
        return False


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


def print_env_file_warning() -> None:
    env_message = """
    Some API keys are missing, so talkgenerator will use fewer image sources.

    Copy .env.example to .env (in the folder you run talkgenerator from) and fill in the keys.
    See https://github.com/twinters/talk-generator#api-keys for where to get them.
    """
    logger.warning(env_message)
