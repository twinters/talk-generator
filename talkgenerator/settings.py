import logging
from environs import Env


logger = logging.getLogger("talkgenerator")
env = Env()
env.read_env()

reddit_keys = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]
wikihow_keys = ["WIKIHOW_USERNAME", "WIKIHOW_PASSWORD"]
unsplash_keys = [
    "UNSPLASH_ACCESS_KEY",
    "UNSPLASH_SECRET_KEY",
    "UNSPLASH_REDIRECT_URI",
    "UNSPLASH_CODE",
]

all_keys_to_check = {
    "Reddit": reddit_keys,
    "WikiHow": wikihow_keys,
    "Unsplash": unsplash_keys,
}


def reddit_auth():
    return {
        "client_id": env.str("REDDIT_CLIENT_ID", ""),
        "client_secret": env.str("REDDIT_CLIENT_SECRET", ""),
        "user_agent": env.str("REDDIT_USER_AGENT", ""),
    }


def wikihow_auth():
    return {
        "username": env.str("WIKIHOW_USERNAME", ""),
        "password": env.str("WIKIHOW_PASSWORD", ""),
    }


def unsplash_auth():
    return {
        "unsplash_access_key": env.str("UNSPLASH_ACCESS_KEY", ""),
        "unsplash_secret_key": env.str("UNSPLASH_SECRET_KEY", ""),
        "unsplash_redirect_uri": env.str("UNSPLASH_REDIRECT_URI", ""),
        "unsplash_code": env.str("UNSPLASH_CODE", ""),
    }


def pixabay_auth():
    return {"pixabay_key": env.str("PIXABAY_KEY", "")}


def pexels_auth():
    return {"pexels_key": env.str("PEXELS_KEY", "")}


def is_source_disabled(name: str) -> bool:
    """Check whether a content source is disabled via env (DISABLE_<NAME>=1).

    Used by individual source modules (sources/reddit.py, sources/unsplash.py, ...)
    to skip themselves when the operator has flagged them off — useful on resource-
    constrained deployments or when a source's API has gone stale.
    """
    return env.bool(f"DISABLE_{name.upper()}", False)


def _get_missing_keys(key_variables):
    missing = []
    for key_name in key_variables:
        if len(env.str(key_name, "").strip()) == 0:
            missing.append(key_name)
    return missing


def check_keys(key_variables, name):
    missing = _get_missing_keys(key_variables)
    if len(missing) > 0:
        logger.warning("Missing keys for {}: {}".format(name, missing))
        return False
    return True


def check_environment_variables():
    print("CHECKING ENVIRONMENT VARIABLES")
    valid_env_file = all(
        check_keys(all_keys_to_check[element], element) for element in all_keys_to_check
    )

    if not valid_env_file:
        print_env_file_warning()

    return valid_env_file


def print_env_file_warning():
    env_message = """
    Hi! Before you can run talkgenerator you need to set some secret keys in an .env file.

    Which keys?
    -------------
    Take a look at https://github.com/twinters/talk-generator#setting-up-required-authentication

    Creating an .env file
    -------------
    $ touch .env
    $ echo VARIABLE_NEEDED=VALUE >> .env
    $ echo OTHER_VARIABLE_NEEDED=VALUE >> .env

    or you can use your favorite text editor (vi, nano, etc) to create it.
    """

    logger.error(env_message)
