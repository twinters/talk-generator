"""Images from Reddit, through PRAW. Needs REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT.

Reddit's search no longer supports the `url:` operators we used to filter on image links (such
queries now return nothing), so we search on the plain topic and pick the image out of each post
ourselves: direct image links, the first image of a gallery, or the preview image Reddit made.
"""

import html
import logging
import threading
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

import praw
from prawcore.exceptions import (
    OAuthException,
    PrawcoreException,
    RequestException,
    ResponseException,
    ServerError,
    TooManyRequests,
)

from talkgenerator import settings
from talkgenerator.util import http_util

logger = logging.getLogger("talkgenerator")

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")
_thread_local = threading.local()

# When Reddit as a whole fails (bad credentials, rate limit, outage), skip it for a while instead of paying
# PRAW's timeouts and retries on every search. Errors about one subreddit (private, banned...) don't count.
_cooldown = http_util.Cooldown("Reddit")


def _has_credentials() -> bool:
    return not settings.is_source_disabled("REDDIT") and all(settings.reddit_auth().values())


def get_reddit() -> praw.Reddit | None:
    """A read-only Reddit client, one per thread (PRAW isn't thread-safe), or None without credentials."""
    if not _has_credentials():
        return None
    reddit = getattr(_thread_local, "reddit", None)
    if reddit is None:
        credentials = settings.reddit_auth()
        reddit = praw.Reddit(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            user_agent=credentials["user_agent"],
        )
        reddit.read_only = True
        _thread_local.reddit = reddit
    return reddit


def has_reddit_access() -> bool:
    return get_reddit() is not None


def get_subreddit(name: str) -> Any:
    reddit = get_reddit()
    if reddit:
        return reddit.subreddit(name)


@lru_cache(maxsize=128)
def _search_images(name: str, query: str, sort: str, limit: int) -> tuple[tuple[str, str, str | None], ...]:
    # Raises on API errors, so that failures don't end up in the cache
    subreddit = get_subreddit(name)
    submissions = subreddit.search(query, sort=sort, limit=limit) if query else subreddit.hot(limit=limit)
    images = []
    for submission in submissions:
        if vars(submission).get("over_18"):
            continue
        image_url = get_image_url(submission)
        if image_url:
            images.append((image_url, get_source_name(submission), get_post_url(submission)))
    return tuple(images)


def search_images(
    name: str, query: str | None, sort: str = "relevance", limit: int = 100
) -> list[tuple[str, str, str | None]] | None:
    """(image URL, credit, post URL) triples of safe-for-work image posts in (a "+"-joined list of) subreddits.

    Searches for the query, or takes the current hot posts if there's no query. Returns None without
    Reddit access or when Reddit fails.
    """
    if not has_reddit_access():
        logger.debug("No Reddit access")
        return None
    if _cooldown.active:
        return None
    try:
        return list(_search_images(name, (query or "").strip(), sort, limit))
    except PrawcoreException as err:
        cooldown = _cooldown_for(err)
        if cooldown:
            _cooldown.trigger(*cooldown)
        else:
            logger.warning("Reddit search in r/%s failed: %s", name, err)
        return None


def _cooldown_for(error: PrawcoreException) -> tuple[float, str] | None:
    """How long to skip Reddit after this error (and why), or None if only this search failed."""
    status = error.response.status_code if isinstance(error, ResponseException) else None
    if isinstance(error, OAuthException) or status == 401:
        return 60 * 60, f"the REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET were rejected: {error}"
    if isinstance(error, TooManyRequests):
        return 10 * 60, "rate limit reached"
    if isinstance(error, ServerError):
        return 5 * 60, f"HTTP {status}"
    if isinstance(error, RequestException):
        return 5 * 60, f"no connection: {error}"
    return None


def get_image_url(submission: Any) -> str | None:
    """The URL of the image a post shows, if it shows one."""
    # Read the raw data: PRAW would make an extra request for every missing attribute otherwise
    data = vars(submission)
    if data.get("is_video"):
        return None

    url = data.get("url_overridden_by_dest") or data.get("url") or ""
    if urlsplit(url).path.lower().endswith(_IMAGE_EXTENSIONS):
        return url

    media_metadata = data.get("media_metadata") or {}
    if data.get("is_gallery") and media_metadata:
        gallery_items = (data.get("gallery_data") or {}).get("items") or []
        media_ids = [item.get("media_id") for item in gallery_items] or list(media_metadata)
        for media_id in media_ids:
            media = media_metadata.get(media_id) or {}
            if media.get("status") == "valid" and media.get("e") in ("Image", "AnimatedImage"):
                source = media.get("s") or {}
                gallery_url = source.get("gif") or source.get("u")
                if gallery_url:
                    return html.unescape(gallery_url)

    preview_images = (data.get("preview") or {}).get("images") or []
    if preview_images:
        preview = preview_images[0]
        gif_url = (((preview.get("variants") or {}).get("gif") or {}).get("source") or {}).get("url")
        preview_url = gif_url or (preview.get("source") or {}).get("url")
        if preview_url:
            return html.unescape(preview_url)
    return None


def get_post_url(submission: Any) -> str | None:
    permalink = vars(submission).get("permalink")
    return "https://www.reddit.com" + permalink if permalink else None


def get_source_name(submission: Any) -> str:
    data = vars(submission)
    author = data.get("author")
    subreddit = data.get("subreddit_name_prefixed") or "Reddit"
    if author is not None and getattr(author, "name", None):
        return "u/{} (on {})".format(author.name, subreddit)
    return "Reddit ({})".format(subreddit)
