import logging

import talkgenerator.settings
import talkgenerator.util.language_util

logger = logging.getLogger("talkgenerator")


def check_runtime_environment():
    check_env = talkgenerator.settings.report_missing_keys()
    if check_env:
        logger.info("Successful check: Environment variables")

    check_ntlk = talkgenerator.util.language_util.check_and_download()
    if check_ntlk:
        logger.info("Successful check: NLTK Dictionaries available")

    return check_ntlk
