"""Fitting text in a box: the largest font size, between a largest and a smallest one, at which the text fits.

Texts break between words, as PowerPoint and browsers break them. Sizes and boxes are in canvas pixels (1920×1080,
where a pixel is half a point in PowerPoint), and the same text in the same box always gets the same size.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from talkgenerator.design.fonts import text_width

# A line's height, as a share of the font size: a little more than PowerPoint's single spacing for most fonts
LINE_HEIGHT: Final = 1.2
# Font sizes go down in steps of this many pixels (a point)
STEP: Final = 2
# How many fits and line breaks are remembered (each): a slide's texts are fitted and broken into lines again and again
# (for each layout the engine tries, each spot a motif tries for its decoration, the design checks), and each time
# measures the text word by word (a fit at every size from the largest down)
FITS_KEPT: Final = 4096


@dataclass(frozen=True)
class Fit:
    size: float
    lines: tuple[str, ...]
    fits: bool  # False when even at the smallest size the text is too wide or too tall for its box


def wrap(text: str, width: float, font: str, size: float, bold: bool = False) -> list[str]:
    """The text's lines at the size, each as wide as fits (a word wider than the box gets a line of its own)."""
    return list(_wrapped(text, width, font, size, bold))


@lru_cache(maxsize=FITS_KEPT)
def _wrapped(text: str, width: float, font: str, size: float, bold: bool) -> tuple[str, ...]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}" if line else word
            if not line or text_width(candidate, font, size, bold) <= width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return tuple(lines)


@lru_cache(maxsize=FITS_KEPT)
def fit(
    text: str,
    width: float,
    height: float,
    font: str,
    largest: float,
    smallest: float,
    bold: bool = False,
    line_height: float = LINE_HEIGHT,
) -> Fit:
    """The largest size from largest down to smallest (in steps of STEP) at which the text fits the box."""
    size = largest
    while True:
        lines = wrap(text, width, font, size, bold)
        wide = any(text_width(line, font, size, bold) > width for line in lines)
        tall = len(lines) * size * line_height > height
        if not wide and not tall:
            return Fit(size, tuple(lines), True)
        if size <= smallest:
            return Fit(smallest, tuple(lines), False)
        size = max(smallest, size - STEP)


def text_height(lines: int, size: float, line_height: float = LINE_HEIGHT) -> float:
    return lines * size * line_height
