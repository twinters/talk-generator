"""Downloading and checking images before they go on a slide.

Images are checked while slides are generated, so that a dead link, a "this image was removed"
placeholder or an unsupported format makes the generator pick another image instead of leaving
an empty frame in the deck. Downloads are cached, so writing the PowerPoint reuses them.
"""

from __future__ import annotations

import io
import logging
import os
import threading
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from talkgenerator.util import http_util, os_util

logger = logging.getLogger("talkgenerator")

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024
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
    global _cache_bytes
    with _cache_lock:
        if url in _cache:
            _cache.move_to_end(url)
            return _cache[url]
    result = _load(url)
    with _cache_lock:
        if url not in _cache:
            _cache[url] = result
            _cache_bytes += len(result or b"")
            while _cache_bytes > _CACHE_MAX_BYTES and len(_cache) > 1:
                _, evicted = _cache.popitem(last=False)
                _cache_bytes -= len(evicted or b"")
    return result


def is_usable_image(url: str) -> bool:
    return fetch_image(url) is not None


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


def _download(url: str) -> bytes | None:
    response = http_util.get(url, timeout=15, stream=True)
    if response is None:
        return None
    with response:
        if not response.ok:
            logger.info("Image %s returned HTTP %s", http_util.describe_url(url), response.status_code)
            return None
        if "removed" in Path(response.url.split("?")[0]).name:  # e.g. Imgur's removed.png
            logger.info("Image %s was removed by its host", http_util.describe_url(url))
            return None
        content_type = response.headers.get("Content-Type", "").lower()
        if content_type.startswith(_NOT_AN_IMAGE_CONTENT_TYPES):
            logger.info("%s is not an image but %s", http_util.describe_url(url), content_type)
            return None
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=256 * 1024):
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                logger.info("Image %s is too large to use", http_util.describe_url(url))
                return None
            chunks.append(chunk)
        return b"".join(chunks)


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
