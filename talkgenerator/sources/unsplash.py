"""Module for interacting with Unsplash."""

import logging
from json import JSONDecodeError
from typing import List, Optional

from pyunsplash import PyUnsplash

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator import settings

logging.getLogger("pyunsplash").setLevel(logging.DEBUG)
logger = logging.getLogger("talkgenerator")


_unsplash_session: Optional[PyUnsplash] = None


def get_unsplash_session() -> Optional[PyUnsplash]:
    """Lazily build the PyUnsplash client. Returns None if disabled or missing key."""
    global _unsplash_session
    if _unsplash_session is not None:
        return _unsplash_session
    if settings.is_source_disabled("UNSPLASH"):
        return None
    creds = settings.unsplash_auth()
    if not creds["unsplash_access_key"]:
        return None
    _unsplash_session = PyUnsplash(api_key=creds["unsplash_access_key"])
    return _unsplash_session


def _map_to_image_data(photo):
    link_download = photo.link_download
    creator_user = photo.body["user"]
    creator_name = None
    if creator_user:
        creator_name = creator_user["name"] + " (Unsplash)"
    return ImageData(image_url=link_download, source=creator_name)


def random(_=None):
    session = get_unsplash_session()
    if not session:
        return None
    try:
        random_image = session.photos(type_="random")
        image_url = random_image.body["links"]["download"]
        creator_name = random_image.body["user"]["name"]
        return ImageData(image_url=image_url, source=creator_name)
    except JSONDecodeError:
        logger.warning("Couldn't get random Unsplash image")
        return None


def random_as_list(_=None):
    result = random(_)
    if result:
        return [result]
    return []


def search_photos(query) -> List[ImageData]:
    session = get_unsplash_session()
    if not session:
        logger.warning("No active Unsplash session (disabled or missing UNSPLASH_ACCESS_KEY).")
        return []
    if query:
        results = session.search(type_="photos", query=query)
        if results and results.body:
            return [_map_to_image_data(photo) for photo in results.entries]
        logger.warning(
            "Unsplash returned no results for %r (check UNSPLASH_ACCESS_KEY)", query
        )
        return []
    return random_as_list()
