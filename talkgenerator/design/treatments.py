"""Image treatments: what gives pictures from mixed sources one look in a theme (docs/v5-plan.md, section 9).

A theme can have a filter (grayscale, sepia, a duotone in its own colours, or black and white), a frame for
pictures in a box (rounded corners, or a white polaroid frame, tilted a little), grain and a vignette. The layout
engine puts a picture's treatment in the deck (`ImageTreatment`), and every renderer applies it its own way:
PowerPoint with its picture effects (so the original picture stays in the deck, and "Reset Picture" undoes them),
previews with Pillow (the functions below), and a browser with CSS filters. This module has what they share: the
colours, the geometry of a polaroid and a rounded corner, and the grain.
"""

from __future__ import annotations

import math
from functools import cache
from typing import Final

from PIL import Image, ImageDraw, ImageOps

from talkgenerator.design import color
from talkgenerator.models.deck import Box, ImageTreatment
from talkgenerator.models.theme import Palette, Theme
from talkgenerator.util import random_util

# Sepia: a picture's light mapped from a dark brown to a cream
SEPIA: Final = ("#3b2a1a", "#f2e4c4")
# A rounded corner's radius, as a share of the picture's shorter side
ROUNDED: Final = 0.08
# A polaroid's frame: as wide as this share of its box's shorter side at the top and sides, and five times as wide
# below the picture; a tilt of 1.5 to 4 degrees, either way; and a margin inside its box, so that tilted, it stays in
POLAROID_BORDER: Final = 0.035
POLAROID_TILT: Final = (1.5, 4.0)
POLAROID_MARGIN: Final = 0.05
POLAROID_WHITE: Final = "#fbfbf8"
# A vignette darkens a picture from this share of the way to its edges, as much as its strength says (and grain
# overlays this much noise at a strength of 1)
VIGNETTE_START: Final = 0.55
VIGNETTE_DARKEST: Final = 0.6
GRAIN_SIZE: Final = (480, 270)
# Black and white splits a picture at its median lightness, kept within these
THRESHOLDS: Final = (0.15, 0.85)


def duotone(palette: Palette) -> tuple[str, str]:
    """A theme's duotone: from its darkest colour to its lightest, both tinted with its accent."""
    darkest, lightest = sorted((palette.background, palette.text), key=color.luminance)
    return color.mix(darkest, palette.accent, 0.3), color.mix(lightest, palette.accent, 0.3)


def treatment(theme: Theme, framed: bool) -> ImageTreatment | None:
    """How the theme treats a picture (in a box, if framed, else over a whole slide or half of it, where it gets no
    frame), or None if it leaves it as it is. A polaroid's tilt comes from the current random stream."""
    frame = theme.image_frame if framed else "none"
    if theme.image_filter == "none" and frame == "none" and not theme.image_grain and not theme.image_vignette:
        return None
    dark = light = None
    if theme.image_filter == "sepia":
        dark, light = SEPIA
    elif theme.image_filter == "duotone":
        dark, light = duotone(theme.palette)
    tilt = 0.0
    if frame == "polaroid":
        tilt = round(random_util.uniform(*POLAROID_TILT) * random_util.choice((-1, 1)), 1)
    return ImageTreatment(
        filter=theme.image_filter,
        dark=dark,
        light=light,
        frame=frame,
        tilt=tilt,
        grain=theme.image_grain,
        vignette=theme.image_vignette,
    )


def polaroid(box: Box, width: float, height: float, cover: bool) -> tuple[Box, Box]:
    """Where a polaroid's frame goes in the box (before it's tilted), and where its picture goes in the frame: the
    frame as large as fits, in the middle, around the picture (of width × height, shown whole, or filling the space
    if cover)."""
    margin = POLAROID_MARGIN * min(box.w, box.h)
    inside = Box(x=box.x + margin, y=box.y + margin, w=box.w - 2 * margin, h=box.h - 2 * margin)
    border = POLAROID_BORDER * min(inside.w, inside.h)
    room_w, room_h = inside.w - 2 * border, inside.h - 6 * border
    if cover:
        shown_w, shown_h = room_w, room_h
    else:
        scale = min(room_w / width, room_h / height)
        shown_w, shown_h = width * scale, height * scale
    frame_w, frame_h = shown_w + 2 * border, shown_h + 6 * border
    frame = Box(x=inside.x + (inside.w - frame_w) / 2, y=inside.y + (inside.h - frame_h) / 2, w=frame_w, h=frame_h)
    return frame, Box(x=frame.x + border, y=frame.y + border, w=shown_w, h=shown_h)


def turned(box: Box, around: tuple[float, float], degrees: float) -> Box:
    """The box moved as it would be by turning it the degrees (clockwise) around the point: its size stays, and it's
    drawn turned around its own middle, by the same degrees."""
    x, y = box.x + box.w / 2 - around[0], box.y + box.h / 2 - around[1]
    angle = math.radians(degrees)
    middle_x = around[0] + x * math.cos(angle) - y * math.sin(angle)
    middle_y = around[1] + x * math.sin(angle) + y * math.cos(angle)
    return Box(x=middle_x - box.w / 2, y=middle_y - box.h / 2, w=box.w, h=box.h)


@cache
def grain(opacity: float) -> Image.Image:
    """Noise to lay over a picture (as RGBA, with the opacity), the same every time (its own seed, not the talk's)."""
    noise = Image.frombytes("L", GRAIN_SIZE, random_util.Rng(7).randbytes(GRAIN_SIZE[0] * GRAIN_SIZE[1]))
    layer = Image.merge("RGB", (noise, noise, noise)).convert("RGBA")
    layer.putalpha(round(255 * opacity))
    return layer


def filtered(picture: Image.Image, look: ImageTreatment) -> Image.Image:
    """The picture (RGB) with the treatment's filter, grain and vignette, as previews show it."""
    if look.filter == "grayscale":
        picture = ImageOps.grayscale(picture).convert("RGB")
    elif look.filter == "black and white":
        cut = round(255 * threshold(picture))
        picture = ImageOps.grayscale(picture).point(lambda value: 255 if value > cut else 0).convert("RGB")
    elif look.filter in ("sepia", "duotone") and look.dark and look.light:
        picture = ImageOps.colorize(ImageOps.grayscale(picture), look.dark, look.light)
    if look.grain:
        noise = grain(look.grain).resize(picture.size)
        picture = Image.alpha_composite(picture.convert("RGBA"), noise).convert("RGB")
    if look.vignette:
        black = Image.new("RGB", picture.size, "#000000")
        picture = Image.composite(black, picture, vignette_mask(picture.size, look.vignette))
    return picture


def threshold(picture: Image.Image) -> float:
    """Where black and white splits a picture: at its median lightness (from 0 to 1), so that a dark picture keeps
    as much white as a light one keeps black, but no further out than THRESHOLDS (a drawing on white, whose median
    is white, splits as if it weren't split by its median)."""
    gray = ImageOps.grayscale(picture)
    gray.thumbnail((128, 128))
    histogram = gray.histogram()
    half, seen = sum(histogram) / 2, 0
    for value, count in enumerate(histogram):
        seen += count
        if seen >= half:
            return min(THRESHOLDS[1], max(THRESHOLDS[0], value / 255))
    return 0.5


def vignette_mask(size: tuple[int, int], strength: float) -> Image.Image:
    """How much a vignette darkens each pixel (0 to 255): not at all in the middle, more from VIGNETTE_START of the
    way out (to the corners), up to VIGNETTE_DARKEST of black at the corners, at a strength of 1."""
    small = Image.new("L", (64, 36))
    for x in range(64):
        for y in range(36):
            reach = math.hypot((x + 0.5) / 32 - 1, (y + 0.5) / 18 - 1) / math.sqrt(2)  # 0 in the middle, 1 at a corner
            share = min(1.0, max(0.0, (reach - VIGNETTE_START) / (1 - VIGNETTE_START)))
            small.putpixel((x, y), round(255 * VIGNETTE_DARKEST * strength * share))
    return small.resize(size, Image.Resampling.BILINEAR)


def rounded_mask(size: tuple[int, int]) -> Image.Image:
    """A mask of a picture with rounded corners."""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), ROUNDED * min(size), fill=255)
    return mask
