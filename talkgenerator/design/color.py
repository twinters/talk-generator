"""Colours as "#rrggbb", and what themes need of them: HSL, mixing, and WCAG contrast (with repair).

WCAG 2's contrast ratio is between 1 (the same colour) and 21 (black on white). The plan's bars: at least 4.5 for
body text, and 3 for large text such as titles.
"""

from __future__ import annotations

import colorsys
from collections.abc import Sequence
from typing import Final

BODY_CONTRAST: Final = 4.5
LARGE_TEXT_CONTRAST: Final = 3.0


def rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if len(value) != 6:
        raise ValueError(f"not a colour: {color!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def hex_color(red: float, green: float, blue: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(channel))):02x}" for channel in (red, green, blue))


def hsl(hue: float, saturation: float, lightness: float) -> str:
    """The colour of a hue (in degrees), saturation and lightness (from 0 to 1)."""
    red, green, blue = colorsys.hls_to_rgb((hue % 360) / 360, _clamp(lightness), _clamp(saturation))
    return hex_color(red * 255, green * 255, blue * 255)


def to_hsl(color: str) -> tuple[float, float, float]:
    red, green, blue = (channel / 255 for channel in rgb(color))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    return hue * 360, saturation, lightness


def mix(color: str, other: str, amount: float) -> str:
    """The colour that amount (0 to 1) of the way from color to other."""
    return hex_color(*(a + (b - a) * amount for a, b in zip(rgb(color), rgb(other), strict=True)))


def luminance(color: str) -> float:
    """WCAG's relative luminance: 0 for black, 1 for white."""

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(color: str, other: str) -> float:
    lighter, darker = sorted((luminance(color), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable(color: str, background: str, minimum: float = BODY_CONTRAST) -> str:
    """The colour, made lighter or darker (keeping its hue) until it reads on the background with at least the
    minimum contrast; black or white if no shade of it does."""
    if contrast(color, background) >= minimum:
        return color
    hue, saturation, lightness = to_hsl(color)
    darker = luminance(background) > 0.18  # on light backgrounds, go darker; on dark ones, lighter
    for step in range(1, 21):
        shade = hsl(hue, saturation, lightness - step * 0.05 if darker else lightness + step * 0.05)
        if contrast(shade, background) >= minimum:
            return shade
    return max(("#000000", "#ffffff"), key=lambda extreme: contrast(extreme, background))


def worst_contrast(color: str, backgrounds: Sequence[str]) -> float:
    """The colour's contrast with the background it reads worst on (say, one end of a gradient)."""
    return min(contrast(color, background) for background in backgrounds)


def readable_on(color: str, backgrounds: Sequence[str], minimum: float = BODY_CONTRAST) -> str:
    """Like readable, on every one of the backgrounds (such as both ends of a gradient): the colour if it reads on
    all of them, else the nearest darker or lighter shade of it that does, else black or white, whichever reads
    best."""
    if worst_contrast(color, backgrounds) >= minimum:
        return color
    hue, saturation, lightness = to_hsl(color)
    shades = []
    for step in range(1, 21):
        shades += [hsl(hue, saturation, lightness - step * 0.05), hsl(hue, saturation, lightness + step * 0.05)]
    for shade in shades:  # (the nearest ones first)
        if worst_contrast(shade, backgrounds) >= minimum:
            return shade
    return max(("#000000", "#ffffff"), key=lambda extreme: worst_contrast(extreme, backgrounds))


def is_dark(color: str) -> bool:
    return luminance(color) < 0.18


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
