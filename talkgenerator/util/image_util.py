"""Downloading and checking images before they go on a slide.

Images are checked while slides are generated, so that a dead link, a "this image was removed"
placeholder or an unsupported format makes the generator pick another image instead of leaving
an empty frame in the deck. Downloads are cached, so writing the PowerPoint reuses them.

A gif that can't be used, one too large to embed say, can play as its video copy instead (see
fetch_image_data): Reddit has mp4 copies of its gifs.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util, os_util, video_util

logger = logging.getLogger("talkgenerator")

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
MAX_GIF_BYTES = 16 * 1024 * 1024  # gifs stay as they are, to stay animated; many good ones are 10 to 16 MB
# The video copies of gifs too large to embed: as much as a gif, so a deck gets no larger than with gifs (Reddit's
# mp4 copies are mostly a few MB, but some are larger than their gif)
MAX_VIDEO_BYTES = MAX_GIF_BYTES
MAX_DIMENSION = 2400  # pixels; larger photos are scaled down to keep decks small
MAX_UNCONVERTED_BYTES = 3 * 1024 * 1024
MIN_DIMENSION = 50  # anything smaller is an icon or a tracking pixel
_POWERPOINT_FORMATS = {"JPEG", "PNG", "GIF", "BMP"}
# The only formats we open. Pillow recognises a file's format from its contents, so without this
# list a downloaded "image" could reach parsers we never need (EPS through Ghostscript, PDF, TIFF,
# FlashPix, ...), which is where most of Pillow's security fixes have been.
_ACCEPTED_FORMATS = ("JPEG", "MPO", "PNG", "GIF", "WEBP", "AVIF", "BMP")
_NOT_AN_IMAGE_CONTENT_TYPES = ("text/", "application/json", "application/xml", "application/xhtml")

_PROHIBITED_IMAGES_DIR = "data/prohibited_images/"
_FINGERPRINT_SIZE = (16, 16)
_MAX_FINGERPRINT_DIFFERENCE = 12

_CACHE_MAX_BYTES = 96 * 1024 * 1024
_cache: OrderedDict[str, bytes | None] = OrderedDict()
_cache_bytes = 0
_cache_lock = threading.Lock()


def fetch_image(url: str) -> bytes | None:
    """Image bytes that are safe to embed in a pptx, or None if the URL or path isn't a usable image."""
    return _cached(url, lambda: _load(url))


def fetch_video(url: str) -> bytes | None:
    """The bytes of an mp4 video on the web that's small enough to embed in a pptx, or None."""
    return _cached("video " + url, lambda: _load_video(url))


def _cached(key: str, load: Callable[[], bytes | None]) -> bytes | None:
    global _cache_bytes
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    result = load()
    with _cache_lock:
        if key not in _cache:
            _cache[key] = result
            _cache_bytes += len(result or b"")
            while _cache_bytes > _CACHE_MAX_BYTES and len(_cache) > 1:
                _, evicted = _cache.popitem(last=False)
                _cache_bytes -= len(evicted or b"")
    return result


def is_usable_image(url: str) -> bool:
    return fetch_image(url) is not None


def fetch_image_data(image: ImageData) -> bytes | None:
    """Like fetch_image, for an ImageData, which keeps the bytes once they're downloaded. That way the
    image that was checked while generating a slide is the one embedded in the PowerPoint, even if it
    dropped out of the download cache in between.

    An image that can't be used, such as a gif too large to embed, plays its video copy instead, if it
    has one that can: then these are the bytes of the video's poster frame, and image.video_data holds
    the video's."""
    if image.data is None:
        image.data = fetch_image(image.get_image_url())
        if image.data is None and image.video is not None:
            poster = fetch_image(image.video.poster_url)
            video = fetch_video(image.video.url) if poster is not None else None
            if video is not None:
                logger.info("Image %s plays as its video copy", http_util.describe_url(image.get_image_url()))
                image.video_data = video
                image.data = poster
    return image.data


def _load(url: str) -> bytes | None:
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        # Local files are our own assets (such as the 10x10 transparent overlay): use them as they are
        try:
            return Path(url).read_bytes()
        except OSError as e:
            logger.warning("Can't read image file %s: %s", url, e)
            return None
    data = _download(url)
    if data is None:
        return None
    return prepare_image_bytes(data, http_util.describe_url(url))


def _load_video(url: str) -> bytes | None:
    if not url.startswith(("http://", "https://")):
        logger.warning("Video %s is not on the web", url)
        return None
    data = _download(url, MAX_VIDEO_BYTES, "Video")
    if data is not None and not video_util.is_mp4(data):
        logger.info("Video %s is not an mp4", http_util.describe_url(url))
        return None
    return data


def _download(url: str, limit: int = MAX_DOWNLOAD_BYTES, kind: str = "Image") -> bytes | None:
    """The bytes at the URL, unless there are more than the limit (or than MAX_GIF_BYTES, for a gif)."""
    response = http_util.get(url, timeout=15, stream=True)
    if response is None:
        return None
    description = http_util.describe_url(url)
    with response:
        if not response.ok:
            logger.info("%s %s returned HTTP %s", kind, description, response.status_code)
            return None
        if "removed" in Path(response.url.split("?")[0]).name:  # e.g. Imgur's removed.png
            logger.info("%s %s was removed by its host", kind, description)
            return None
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type.startswith(_NOT_AN_IMAGE_CONTENT_TYPES):
            logger.info("%s %s is %s", kind, description, content_type)
            return None
        # Hosts tell a file's size up front, so one that's too large isn't downloaded at all (gifs of 40 to 60 MB
        # are common on r/gifs: they play as their video copy instead)
        declared = _declared_size(response)
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=256 * 1024):
            if not chunks and chunk.startswith(b"GIF8"):  # gifs are used as they are, up to their own limit
                limit = min(limit, MAX_GIF_BYTES)
            size += len(chunk)
            if size > limit or (declared is not None and declared > limit):
                logger.info("%s %s is too large to use", kind, description)
                return None
            chunks.append(chunk)
        return b"".join(chunks)


def _declared_size(response: Any) -> int | None:
    try:
        return int(response.headers.get("Content-Length", ""))
    except ValueError:
        return None


@lru_cache(maxsize=1)
def accepted_formats() -> tuple[str, ...]:
    """The accepted image formats that this Pillow build can open."""
    Image.init()
    return tuple(name for name in _ACCEPTED_FORMATS if name in Image.OPEN)


def prepare_image_bytes(data: bytes, description: str = "image") -> bytes | None:
    """Check that the bytes are a real, allowed image and convert them into something PowerPoint can show."""
    try:
        with Image.open(io.BytesIO(data), formats=accepted_formats()) as image:
            image_format = image.format
            width, height = image.size
            if width < MIN_DIMENSION or height < MIN_DIMENSION:
                logger.info("Image %s is too small (%sx%s)", description, width, height)
                return None
            if is_prohibited(image):
                logger.info("Image %s is a known 'image not available' placeholder", description)
                return None
            if image_format == "GIF":
                # Keep GIFs as they are so that they stay animated
                if len(data) > MAX_GIF_BYTES:
                    logger.info("GIF %s is too large to use", description)
                    return None
                return data
            if (
                image_format in _POWERPOINT_FORMATS
                and max(width, height) <= MAX_DIMENSION
                and len(data) <= MAX_UNCONVERTED_BYTES
            ):
                return data
            # Unsupported format (WebP, AVIF, MPO...) or a huge photo: convert and scale it down
            converted = ImageOps.exif_transpose(image)
            converted.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if converted.mode in ("RGBA", "LA") or (converted.mode == "P" and "transparency" in converted.info):
                converted.save(output, "PNG", optimize=True)
            else:
                converted.convert("RGB").save(output, "JPEG", quality=85, optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as e:
        logger.info("Image %s can't be used: %s", description, e)
        return None


def get_image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data), formats=accepted_formats()) as image:
        width, height = image.size
        return int(width), int(height)


# Placeholder images that hosts serve instead of removed content


def _fingerprint(image: Image.Image) -> bytes:
    # Via RGBA, so palette images with transparency convert cleanly
    return image.convert("RGBA").convert("RGB").resize(_FINGERPRINT_SIZE, Image.Resampling.BILINEAR).tobytes()


@lru_cache(maxsize=1)
def _prohibited_fingerprints() -> tuple[tuple[float, bytes], ...]:
    directory = os_util.to_actual_file(_PROHIBITED_IMAGES_DIR)
    fingerprints = []
    for file_name in sorted(os.listdir(directory)):
        try:
            with Image.open(os.path.join(directory, file_name)) as image:
                fingerprints.append((image.width / image.height, _fingerprint(image)))
        except (UnidentifiedImageError, OSError):
            continue
    return tuple(fingerprints)


def is_prohibited(image: Image.Image) -> bool:
    ratio = image.width / image.height
    fingerprint = None
    for prohibited_ratio, prohibited_fingerprint in _prohibited_fingerprints():
        if abs(prohibited_ratio - ratio) > 0.05:
            continue
        if fingerprint is None:
            fingerprint = _fingerprint(image)
        difference = sum(abs(a - b) for a, b in zip(fingerprint, prohibited_fingerprint, strict=True)) / len(
            fingerprint
        )
        if difference < _MAX_FINGERPRINT_DIFFERENCE:
            return True
    return False
