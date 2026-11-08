"""A look at an image, with Pillow, on a thumbnail (docs/v5-plan.md, section 10.3): what the image finder scores
candidates by, and what the deck keeps of the image it picked (`ImageAnalysis`).

- brightness: how light it is, on average (0 black, 1 white);
- colourfulness: Hasler and Süsstrunk's measure of how colourful it is (0 gray; 1 extremely colourful);
- grayscale: the share of its pixels without colour;
- monochrome: whether it's in one colour: gray, or toned in one tint (sepia, say), as old photographs are;
- detail: how much detail it has in an area (where a slide's text goes over it): the mean strength of its edges;
- colors: its main colours, most first;
- hash: a perceptual hash (a difference hash of 64 bits), which near-duplicates share but for a few bits.

Thumbnails are a few kilobytes, and the look is taken at 96 pixels, so a look takes milliseconds. The same thumbnail
gives the same look on every computer, which keeps talks the same for the same seed.
"""

from __future__ import annotations

import io
import logging
import math
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from talkgenerator.design import color
from talkgenerator.models.deck import ImageAnalysis
from talkgenerator.util import http_util, image_util

logger = logging.getLogger("talkgenerator")

SIZE: Final = 96  # the longest side a look is taken at, in pixels
MAX_THUMBNAIL_BYTES: Final = 1024 * 1024
# A pixel is without colour when its channels are this close (of 255): what JPEG noise leaves in a gray photo
GRAY_CHROMA: Final = 24
# A picture in black and white (or gray) has this share of pixels without colour, or a little less and next to no
# colour; a toned one's coloured pixels share one hue this closely (1: all of them), and it's at most this colourful.
# (Measured on 2026-11-07: Wikimedia Commons' black and white photographs have a gray share of 1.0, most of them;
# sepia photographs one hue at 0.997 to 1.0, at a colourfulness of 0.18 to 0.35; Pixabay's colour photos one hue at
# 0.99 or less, but for one nearly gray one)
GRAY: Final = 0.85
NEARLY_GRAY: Final = (0.6, 0.1)
TONED: Final = 0.995
TONED_COLOURFULNESS: Final = 0.4
# Colourfulness as Hasler and Süsstrunk measure it is about 109 for an "extremely colourful" picture: that's 1 here
_COLOURFUL: Final = 109.0
NEAR_DUPLICATE: Final = 10  # the most bits in which the hashes of two near-duplicates differ (of 64)
_MAX_LOOKS: Final = 2048
_looks: OrderedDict[tuple[str, Area | None], ImageAnalysis | None] = OrderedDict()
# The thumbnails downloaded last (their bytes, or None for one that couldn't be had), for a vision pick's contact
# sheet to show the same pictures that were looked at (see talkgenerator.images.vision), without asking again
_MAX_THUMBNAILS: Final = 256
_thumbnails: OrderedDict[str, bytes | None] = OrderedDict()
_lock = threading.Lock()


@dataclass(frozen=True)
class Area:
    """A part of an image, from its left and its top, as shares (0 to 1) of its width and height."""

    x: float
    y: float
    w: float
    h: float


# Where a slide's big text goes over a picture behind it: in its middle
MIDDLE: Final = Area(0.12, 0.25, 0.76, 0.5)


def analyse(data: bytes, area: Area | None = None) -> ImageAnalysis | None:
    """A look at the image (its bytes): None if it isn't an image Pillow opens. With an area, how much detail is
    there too."""
    try:
        with Image.open(io.BytesIO(data), formats=image_util.accepted_formats()) as opened:
            opened.draft("RGB", (SIZE * 2, SIZE * 2))  # (a JPEG decodes at a fraction of its size: faster)
            picture = _rgb(ImageOps.exif_transpose(opened))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as error:
        logger.debug("Can't look at an image: %s", error)
        return None
    picture.thumbnail((SIZE, SIZE), Image.Resampling.BILINEAR)
    return _look(picture, area)


def look_at(url: str, area: Area | None = None) -> ImageAnalysis | None:
    """A look at the image at the URL (a thumbnail, at most a megabyte), remembered: None if it can't be had."""
    key = (url, area)
    with _lock:
        if key in _looks:
            _looks.move_to_end(key)
            return _looks[key]
    data = thumbnail(url)
    found = analyse(data, area) if data is not None else None
    with _lock:
        _looks[key] = found
        while len(_looks) > _MAX_LOOKS:
            _looks.popitem(last=False)
    return found


def thumbnail(url: str) -> bytes | None:
    """The thumbnail at the URL (at most a megabyte), remembered for a while: None if it can't be had."""
    with _lock:
        if url in _thumbnails:
            _thumbnails.move_to_end(url)
            return _thumbnails[url]
    data = _download(url)
    with _lock:
        _thumbnails[url] = data
        while len(_thumbnails) > _MAX_THUMBNAILS:
            _thumbnails.popitem(last=False)
    return data


def _download(url: str) -> bytes | None:
    response = http_util.get(url, timeout=8, stream=True)
    if response is None:
        return None
    with response:
        if not response.ok or response.headers.get("Content-Type", "").lower().startswith(
            ("text/", "application/json")
        ):
            logger.debug("No thumbnail at %s (HTTP %s)", http_util.describe_url(url), response.status_code)
            return None
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            size += len(chunk)
            if size > MAX_THUMBNAIL_BYTES:
                logger.debug("The thumbnail at %s is too large to look at", http_util.describe_url(url))
                return None
            chunks.append(chunk)
    return b"".join(chunks)


def _rgb(picture: Image.Image) -> Image.Image:
    """The picture in RGB, what's see-through in it on white (a gif: its first frame)."""
    if picture.mode in ("RGBA", "LA", "PA") or (picture.mode == "P" and "transparency" in picture.info):
        rgba = picture.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return picture.convert("RGB")


def _look(picture: Image.Image, area: Area | None) -> ImageAnalysis:
    grayscale, colourfulness, one_hue = colour_of(picture)
    gray = grayscale >= GRAY or (grayscale >= NEARLY_GRAY[0] and colourfulness <= NEARLY_GRAY[1])
    monochrome = gray or (one_hue >= TONED and colourfulness <= TONED_COLOURFULNESS)
    lightness = picture.convert("L")
    return ImageAnalysis(
        brightness=round(ImageStat.Stat(lightness).mean[0] / 255, 3),
        colourfulness=round(colourfulness, 3),
        grayscale=round(grayscale, 3),
        monochrome=monochrome,
        detail=_detail(lightness, area) if area is not None else None,
        colors=_main_colors(picture),
        hash=_difference_hash(lightness),
    )


def colour_of(picture: Image.Image) -> tuple[float, float, float]:
    """How much of the picture (in RGB) is without colour, how colourful it is (Hasler and Süsstrunk's measure, as a
    share of an extremely colourful picture's), and how closely its coloured pixels share one hue (1: all of them;
    a toned picture, such as a sepia photograph, comes close)."""
    pixels = cast(Sequence[tuple[int, int, int]], picture.get_flattened_data())
    count = len(pixels) or 1
    gray = 0
    sum_rg = sum_yb = square_rg = square_yb = 0.0
    hue_x = hue_y = weight = 0.0
    for red, green, blue in pixels:
        chroma = max(red, green, blue) - min(red, green, blue)
        rg, yb = red - green, (red + green) / 2 - blue
        sum_rg += rg
        sum_yb += yb
        square_rg += rg * rg
        square_yb += yb * yb
        if chroma <= GRAY_CHROMA:
            gray += 1
        else:  # (its hue, as an angle, counted by how much colour it has)
            length = math.hypot(rg, yb) or 1.0
            hue_x += chroma * rg / length
            hue_y += chroma * yb / length
            weight += chroma
    mean_rg, mean_yb = sum_rg / count, sum_yb / count
    spread = math.sqrt(max(0.0, square_rg / count - mean_rg**2) + max(0.0, square_yb / count - mean_yb**2))
    colourfulness = min(1.0, (spread + 0.3 * math.hypot(mean_rg, mean_yb)) / _COLOURFUL)
    one_hue = math.hypot(hue_x, hue_y) / weight if weight else 1.0
    return gray / count, colourfulness, one_hue


def _detail(lightness: Image.Image, area: Area) -> float:
    """How much detail the area has: the mean strength of its edges (0: none, a plain sky; 0.1 and more: busy)."""
    width, height = lightness.size
    box = (
        round(area.x * width),
        round(area.y * height),
        max(round(area.x * width) + 1, round((area.x + area.w) * width)),
        max(round(area.y * height) + 1, round((area.y + area.h) * height)),
    )
    edges = lightness.crop(box).filter(ImageFilter.FIND_EDGES)
    inside = edges.crop((1, 1, max(2, edges.width - 1), max(2, edges.height - 1)))  # (its own border isn't an edge)
    return round(ImageStat.Stat(inside).mean[0] / 255, 3)


def _main_colors(picture: Image.Image, count: int = 4) -> tuple[str, ...]:
    """Its main colours, most first."""
    quantized = picture.quantize(colors=count, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    found = cast(list[tuple[int, int]], quantized.getcolors() or [])
    ranked = sorted(found, key=lambda entry: (-entry[0], entry[1]))
    return tuple(color.hex_color(*palette[index * 3 : index * 3 + 3]) for _, index in ranked)


def _difference_hash(lightness: Image.Image) -> str:
    """A difference hash: for 8 rows of 9 pixels, whether each pixel is lighter than the next one, as 16 hex digits."""
    small = lightness.resize((9, 8), Image.Resampling.BOX)
    values = cast(Sequence[int], small.get_flattened_data())
    bits = 0
    for row in range(8):
        for column in range(8):
            left, right = values[row * 9 + column], values[row * 9 + column + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def distance(hash_1: str, hash_2: str) -> int:
    """In how many of their 64 bits two hashes differ."""
    return (int(hash_1, 16) ^ int(hash_2, 16)).bit_count()


def near_duplicates(first: ImageAnalysis | None, second: ImageAnalysis | None) -> bool:
    """Whether two looks are of (nearly) the same picture: their hashes differ in a few bits at most."""
    if first is None or second is None or not first.hash or not second.hash:
        return False
    return distance(first.hash, second.hash) <= NEAR_DUPLICATE


def palette_fit(analysis: ImageAnalysis, palette: Sequence[str]) -> float:
    """How well a picture's main colours go with a theme's colours (0 to 1): how close each comes to one of them, the
    picture's main colour counting most. A gray picture fits every theme a little."""
    if not palette or not analysis.colors:
        return 0.0
    weights = (0.5, 0.25, 0.15, 0.1)
    fit = 0.0
    for weight, shown in zip(weights, analysis.colors, strict=False):
        nearest = min(_distance(shown, theme_color) for theme_color in palette)
        fit += weight * max(0.0, 1 - nearest / 160)
    return round(fit / sum(weights[: len(analysis.colors)]), 3)


def _distance(first: str, second: str) -> float:
    """How far apart two colours look: the "redmean" distance, which weighs the channels as eyes do (0 to about 765)."""
    red_1, green_1, blue_1 = color.rgb(first)
    red_2, green_2, blue_2 = color.rgb(second)
    mean = (red_1 + red_2) / 2
    return math.sqrt(
        (2 + mean / 256) * (red_1 - red_2) ** 2
        + 4 * (green_1 - green_2) ** 2
        + (2 + (255 - mean) / 256) * (blue_1 - blue_2) ** 2
    )


def forget() -> None:
    """Forget the looks taken and the thumbnails downloaded (for tests, say)."""
    with _lock:
        _looks.clear()
        _thumbnails.clear()
