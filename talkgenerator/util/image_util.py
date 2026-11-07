"""Downloading and checking images before they go on a slide.

Images are checked while slides are generated, so that a dead link, a "this image was removed"
placeholder or an unsupported format makes the generator pick another image instead of leaving
an empty frame in the deck. Downloads are cached, so writing the PowerPoint reuses them.

A gif that can't be used, one too large to embed say, can play as its video copy instead (see
fetch_image_data): Reddit has mp4 copies of its gifs.

While a talk streams into a browser, which loads the images itself, images are probed instead (see probing): only
their first bytes are read, which tell what they are and how large, as a download's checks would. A PowerPoint made
afterwards downloads them then.
"""

from __future__ import annotations

import contextvars
import io
import logging
import os
import struct
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from PIL import Image, ImageOps, UnidentifiedImageError

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import context as image_context
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

# How images are checked while slides are made: downloaded whole, or probed (see probing)
_checks: contextvars.ContextVar[str] = contextvars.ContextVar("image_checks", default="download")
PROBE_BYTES = 64 * 1024  # read at a time: the first 2 KB tell most images' format and size
MAX_PROBE_BYTES = 512 * 1024  # an image that hasn't told its size by then is downloaded whole instead
_MAX_PROBED = 4096
_probed: OrderedDict[str, bool] = OrderedDict()  # what probes found, by URL ("video " and the URL, for videos)
# The size (width, height) of the images that checks let through, by URL: the original's, also when the bytes for a
# PowerPoint are scaled down, so that a probe and a download tell the same
_MAX_SIZES = 16384
_sizes: OrderedDict[str, tuple[int, int]] = OrderedDict()
# What the first bytes of a file can say (see _identify), besides its format and size
_MORE = "more"  # more bytes are needed to tell
_WHOLE = "whole"  # it can only be told from the whole file (an AVIF, say)
_NOT_AN_IMAGE = "not an image"
_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a", b"BM")  # JPEG (and MPO), PNG, GIF, BMP

_T = TypeVar("_T")


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


def forget_downloads() -> None:
    """Empty the cache of downloaded images and videos (up to 96 MB), as a server may once it has made a PowerPoint:
    the next talk or download then doesn't add its own on top. What probes found, and images' sizes, stay."""
    global _cache_bytes
    with _cache_lock:
        _cache.clear()
        _cache_bytes = 0


def is_usable_image(url: str) -> bool:
    """Whether the image at the URL (or path) can go on a slide: downloaded, or probed while probing."""
    if _checks.get() == "probe":
        return probe(url)
    return fetch_image(url) is not None


def check_image(image: ImageData) -> bool:
    """Whether the image can go on a slide: checked once, and remembered (image.usable). It's downloaded, keeping its
    bytes for the PowerPoint, or probed while probing; either way, the check settles whether a gif too large to embed
    plays its video copy (image.plays_video)."""
    if image.usable is None:
        if _checks.get() == "probe" and image.data is None:
            image.usable = _probe_image(image)
        else:
            image.usable = fetch_image_data(image) is not None
        if image.usable:
            image.size = image_size(image.get_shown_url())
    return image.usable


def served_size(
    width: object, height: object, *, max_width: int | None = None, max_side: int | None = None
) -> tuple[int, int] | None:
    """The size in pixels (width, height) of an image as a source serves it: its original size, as the source says
    (None if it doesn't), scaled down to the width or the longest side it's served at, if it's larger."""
    if not isinstance(width, int | float) or not isinstance(height, int | float) or width <= 0 or height <= 0:
        return None
    scale = 1.0
    if max_width is not None and width > max_width:
        scale = max_width / width
    if max_side is not None and max(width, height) * scale > max_side:
        scale = max_side / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def image_size(url: str) -> tuple[int, int] | None:
    """The size in pixels (width, height) of an image that a check let through (probed or downloaded), if known."""
    with _cache_lock:
        return _sizes.get(url)


def _remember_size(url: str, size: tuple[int, int] | None) -> None:
    if size is None:
        return
    with _cache_lock:
        _sizes[url] = size
        _sizes.move_to_end(url)
        while len(_sizes) > _MAX_SIZES:
            _sizes.popitem(last=False)


def _size_of(data: bytes) -> tuple[int, int] | None:
    try:
        return get_image_size(data)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        return None


def fetch_image_data(image: ImageData) -> bytes | None:
    """Like fetch_image, for an ImageData, which keeps the bytes once they're downloaded. That way the
    image that was checked while generating a slide is the one embedded in the PowerPoint, even if it
    dropped out of the download cache in between.

    An image that can't be used, such as a gif too large to embed, plays its video copy instead, if it
    has one that can: then these are the bytes of the video's poster frame, and image.video_data holds
    the video's. (One a probe found to play its video, whose video can't be downloaded now, shows its poster.)"""
    if image.data is None:
        if not image.plays_video:
            image.data = fetch_image(image.get_image_url())
        if image.data is None and image.video is not None:
            poster = fetch_image(image.video.poster_url)
            video = image.video_data or (fetch_video(image.video.url) if poster is not None else None)
            if poster is not None and video is not None:
                logger.info("Image %s plays as its video copy", http_util.describe_url(image.get_image_url()))
                image.video_data, image.data, image.plays_video = video, poster, True
            elif poster is not None and image.plays_video:
                image.data = poster
    return image.data


# PROBING


@contextmanager
def probing() -> Iterator[None]:
    """Check images with a probe instead of downloading them whole (see probe), in this context and in the threads
    that carry takes it to: for a talk that streams into a browser, which loads its images itself."""
    token = _checks.set("probe")
    try:
        yield
    finally:
        _checks.reset(token)


def carry(function: Callable[..., _T]) -> Callable[..., _T]:
    """The function, checking images the way they're checked here, and finding them as this talk does (by its license
    policy and theme: see talkgenerator.images.context), in whichever thread runs it (a pool's, say)."""
    checks = _checks.get()
    images = image_context.current()

    def run(*args: Any, **kwargs: Any) -> _T:
        token = _checks.set(checks)
        try:
            with image_context.for_talk(images):
                return function(*args, **kwargs)
        finally:
            _checks.reset(token)

    return run


def probe(url: str) -> bool:
    """Whether the image at the URL can go on a slide, from its first bytes (remembered): a page or an error isn't
    one, nor a file too large, nor one in another format, nor an image too small. Only an image whose size isn't told
    early enough, or that's shaped like a known "image not available" placeholder, is downloaded whole to tell."""
    return _remembered(url, lambda: _probe(url))


def probe_video(url: str) -> bool:
    """Whether the video at the URL is an mp4 small enough to embed, from its first bytes (remembered)."""
    return _remembered("video " + url, lambda: _probe_video(url))


def _remembered(key: str, find: Callable[[], bool]) -> bool:
    with _cache_lock:
        if key in _probed:
            _probed.move_to_end(key)
            return _probed[key]
        if key in _cache:  # (downloaded already)
            return _cache[key] is not None
    found = find()
    with _cache_lock:
        _probed[key] = found
        while len(_probed) > _MAX_PROBED:
            _probed.popitem(last=False)
    return found


def _probe_image(image: ImageData) -> bool:
    if probe(image.get_image_url()):
        return True
    if image.video is not None and probe(image.video.poster_url) and probe_video(image.video.url):
        logger.info("Image %s plays as its video copy", http_util.describe_url(image.get_image_url()))
        image.plays_video = True
        return True
    return False


def _probe(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return fetch_image(url) is not None  # (a file of our own: read as it is)
    response = http_util.get(url, timeout=15, stream=True)
    if response is None:
        return False
    description = http_util.describe_url(url)
    with response:
        if not _answer_holds("Image", response, description):
            return False
        declared = _declared_size(response)
        head = b""
        for chunk in response.iter_content(chunk_size=PROBE_BYTES):
            head += chunk
            seen = _identify(head)
            if seen != _MORE or len(head) >= MAX_PROBE_BYTES:
                break
        else:  # the whole file is in: check it as a download is checked
            usable = prepare_image_bytes(head, description) is not None
            if usable:
                _remember_size(url, _size_of(head))
            return usable
    if isinstance(seen, str):
        if seen == _NOT_AN_IMAGE:
            logger.info("Image %s can't be used: it isn't an image of an accepted format", description)
            return False
        return fetch_image(url) is not None  # (its size isn't told early enough)
    image_format, width, height = seen
    if image_format == "GIF" and declared is None:
        return fetch_image(url) is not None  # (a gif's size decides whether it's embedded, so it's downloaded to tell)
    if declared is not None and declared > (MAX_GIF_BYTES if image_format == "GIF" else MAX_DOWNLOAD_BYTES):
        logger.info("Image %s is too large to use", description)
        return False
    if width < MIN_DIMENSION or height < MIN_DIMENSION:
        logger.info("Image %s is too small (%sx%s)", description, width, height)
        return False
    if _shaped_like_a_placeholder(width, height):
        return fetch_image(url) is not None  # (downloaded, to compare it with them)
    _remember_size(url, (width, height))
    return True


def _probe_video(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        logger.warning("Video %s is not on the web", url)
        return False
    response = http_util.get(url, timeout=15, stream=True)
    if response is None:
        return False
    description = http_util.describe_url(url)
    with response:
        if not _answer_holds("Video", response, description):
            return False
        declared = _declared_size(response)
        head = b""
        for chunk in response.iter_content(chunk_size=64):
            head += chunk
            if len(head) >= 8:
                break
    if not video_util.is_mp4(head):
        logger.info("Video %s is not an mp4", description)
        return False
    if declared is None:
        return fetch_video(url) is not None  # (downloaded, to tell its size)
    if declared > MAX_VIDEO_BYTES:
        logger.info("Video %s is too large to use", description)
        return False
    return True


def _identify(head: bytes) -> tuple[str, int, int] | str:
    """What a file's first bytes say: its format and size (width, height), or _MORE, _WHOLE or _NOT_AN_IMAGE."""
    if len(head) < 32:
        return _MORE
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return _webp_size(head)  # (Pillow only opens a WebP file whole)
    if head[4:12] in (b"ftypavif", b"ftypavis"):
        return _WHOLE
    if not head.startswith(_SIGNATURES):
        return _NOT_AN_IMAGE
    try:
        with Image.open(io.BytesIO(head), formats=accepted_formats()) as image:
            return str(image.format), int(image.width), int(image.height)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, struct.error):
        return _MORE


def _webp_size(head: bytes) -> tuple[str, int, int] | str:
    """A WebP file's size, from the header of its first chunk: a lossy, lossless or extended one."""
    chunk = head[12:16]
    if chunk == b"VP8 ":  # (after the frame tag and the start code: 14 bits each)
        if head[23:26] != b"\x9d\x01\x2a":
            return _NOT_AN_IMAGE
        width, height = struct.unpack_from("<HH", head, 26)
        return "WEBP", width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":  # (after its signature: 14 bits each, less one)
        if head[20] != 0x2F:
            return _NOT_AN_IMAGE
        bits = int.from_bytes(head[21:25], "little")
        return "WEBP", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":  # (the canvas: 24 bits each, less one)
        return "WEBP", int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    return _NOT_AN_IMAGE


def _shaped_like_a_placeholder(width: int, height: int) -> bool:
    """Whether the image could be a known placeholder (see is_prohibited): as wide for its height, and at most twice
    its width."""
    ratio = width / height
    return any(abs(ratio - shape) <= 0.05 and width <= 2 * known for shape, known in _placeholder_shapes())


@lru_cache(maxsize=1)
def _placeholder_shapes() -> tuple[tuple[float, int], ...]:
    """The known placeholders' width-to-height ratios, and widths."""
    directory = os_util.to_actual_file(_PROHIBITED_IMAGES_DIR)
    shapes = []
    for file_name in sorted(os.listdir(directory)):
        try:
            with Image.open(os.path.join(directory, file_name)) as image:
                shapes.append((image.width / image.height, image.width))
        except (UnidentifiedImageError, OSError):
            continue
    return tuple(shapes)


def _load(url: str) -> bytes | None:
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        # Local files are our own assets (such as the 10x10 transparent overlay): use them as they are
        try:
            local = Path(url).read_bytes()
        except OSError as e:
            logger.warning("Can't read image file %s: %s", url, e)
            return None
        _remember_size(url, _size_of(local))
        return local
    data = _download(url)
    if data is None:
        return None
    prepared = prepare_image_bytes(data, http_util.describe_url(url))
    if prepared is not None:
        _remember_size(url, _size_of(data))  # (the original's, before scaling down)
    return prepared


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
        if not _answer_holds(kind, response, description):
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


def _answer_holds(kind: str, response: Any, description: str) -> bool:
    """Whether the answer holds what was asked for: not an error, a host's "removed" image, or a page instead."""
    if not response.ok:
        logger.info("%s %s returned HTTP %s", kind, description, response.status_code)
        return False
    if "removed" in Path(response.url.split("?")[0]).name:  # e.g. Imgur's removed.png
        logger.info("%s %s was removed by its host", kind, description)
        return False
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type.startswith(_NOT_AN_IMAGE_CONTENT_TYPES):
        logger.info("%s %s is %s", kind, description, content_type)
        return False
    return True


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
