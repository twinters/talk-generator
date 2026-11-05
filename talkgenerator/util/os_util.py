import logging
import os
import sys
from functools import lru_cache

from talkgenerator.datastructures.image_data import ImageData

logger = logging.getLogger("talkgenerator")

_LOG_FORMAT = "[%(levelname)s %(asctime)s %(filename)s:%(lineno)s] %(message)s"


def to_actual_file(filename: str = "") -> str:
    """Return the path to the filename specified.
    This is used most often to get the path of data files."""

    util_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(util_folder, filename)


@lru_cache(maxsize=20)
def read_lines(filename: str) -> list[str]:
    actual_file = to_actual_file(filename)
    with open(actual_file, encoding="utf-8") as file:
        return [line.rstrip("\n") for line in file]


def is_image(content: str | ImageData) -> bool:
    if isinstance(content, ImageData):
        return True
    else:
        return _is_image_path(content)


def _is_image_path(content: str) -> bool:
    if not isinstance(content, str) or not content:
        return False
    lower_url = content.lower()
    return ".jpg" in lower_url or ".gif" in lower_url or ".png" in lower_url or ".jpeg" in lower_url


class _ConsoleHandler(logging.StreamHandler):
    """The handler show_logs adds, so that it can recognise it later."""


def show_logs(given_logger: logging.Logger, level: int = logging.INFO) -> None:
    """Print the logger's messages to stdout (once: calling this again doesn't add duplicate handlers)."""
    given_logger.setLevel(level)
    if not any(isinstance(handler, _ConsoleHandler) for handler in given_logger.handlers):
        console_handler = _ConsoleHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        given_logger.addHandler(console_handler)
    for handler in given_logger.handlers:
        if isinstance(handler, _ConsoleHandler):
            handler.setLevel(level)
    # Don't also pass our messages on to the root logger, which would print everything twice
    given_logger.propagate = False
