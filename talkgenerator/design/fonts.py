"""The fonts themes use, and how wide a text is in them (to pick font sizes at which texts fit their boxes).

A .pptx names its fonts, and the computer showing it needs to have them, so themes stick to fonts that nearly every
computer has. Texts are measured with the font's own file where this computer has it, or with an open font that
shares its metrics (Liberation Sans for Arial, Carlito for Calibri, Gelasio for Georgia...: docs/v5-plan.md,
section 9), in talkgenerator's `data/fonts` folder or the system's. Otherwise the width is estimated from the font's
average character width, generously, so that an estimate errs towards smaller text.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from PIL import ImageFont

from talkgenerator.util import os_util

logger = logging.getLogger("talkgenerator")


@dataclass(frozen=True)
class FontFiles:
    regular: tuple[str, ...]  # the font's own file, then the files of fonts with the same metrics
    bold: tuple[str, ...]
    average: float  # the average character width, as a share of the font size (for estimates)


FONTS: Final[dict[str, FontFiles]] = {
    "Arial": FontFiles(("arial.ttf", "LiberationSans-Regular.ttf"), ("arialbd.ttf", "LiberationSans-Bold.ttf"), 0.52),
    "Arial Black": FontFiles(("ariblk.ttf",), ("ariblk.ttf",), 0.66),
    "Calibri": FontFiles(("calibri.ttf", "Carlito-Regular.ttf"), ("calibrib.ttf", "Carlito-Bold.ttf"), 0.47),
    # (The 2019 template's headings: a little narrower than Calibri, so measured as Calibri where it's missing)
    "Calibri Light": FontFiles(("calibril.ttf", "Carlito-Regular.ttf"), ("calibrib.ttf", "Carlito-Bold.ttf"), 0.46),
    "Cambria": FontFiles(("cambria.ttc", "Caladea-Regular.ttf"), ("cambriab.ttf", "Caladea-Bold.ttf"), 0.5),
    "Georgia": FontFiles(("georgia.ttf", "Gelasio-Regular.ttf"), ("georgiab.ttf", "Gelasio-Bold.ttf"), 0.55),
    "Times New Roman": FontFiles(
        ("times.ttf", "LiberationSerif-Regular.ttf"), ("timesbd.ttf", "LiberationSerif-Bold.ttf"), 0.48
    ),
    "Courier New": FontFiles(
        ("cour.ttf", "LiberationMono-Regular.ttf"), ("courbd.ttf", "LiberationMono-Bold.ttf"), 0.6
    ),
    "Verdana": FontFiles(("verdana.ttf",), ("verdanab.ttf",), 0.6),
    "Trebuchet MS": FontFiles(("trebuc.ttf",), ("trebucbd.ttf",), 0.52),
    "Impact": FontFiles(("impact.ttf",), ("impact.ttf",), 0.5),
    "Comic Sans MS": FontFiles(("comic.ttf",), ("comicbd.ttf",), 0.56),
}
# How much wider than average an estimated text is taken to be: estimates err towards smaller text
ESTIMATE_MARGIN: Final = 1.15
# Texts are measured at this size, and scaled: widths grow with the size
_MEASURING_SIZE: Final = 100


def text_width(text: str, font: str, size: float, bold: bool = False) -> float:
    """How wide the text is in the font, at a font size: both in canvas pixels."""
    path = font_file(font, bold)
    if path is None:
        average = FONTS[font].average if font in FONTS else 0.55
        return len(text) * size * average * (1.08 if bold else 1.0) * ESTIMATE_MARGIN
    return float(_truetype(str(path)).getlength(text)) * size / _MEASURING_SIZE


def font_file(font: str, bold: bool = False) -> Path | None:
    """The file to measure the font with: its own, or one with the same metrics; None if there's neither."""
    files = FONTS.get(font)
    if files is None:
        return None
    index = _font_index()
    for name in files.bold if bold else files.regular:
        path = index.get(name.lower())
        if path is not None:
            return path
    return None


def measured(font: str) -> bool:
    """Whether texts in the font are measured with a font file (and not estimated)."""
    return font_file(font) is not None


@cache
def _truetype(path: str) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, _MEASURING_SIZE)


@cache
def _font_index() -> dict[str, Path]:
    """The font files of this computer, by lowercase file name (talkgenerator's own first)."""
    index: dict[str, Path] = {}
    for folder in _font_folders():
        if not folder.is_dir():
            continue
        for root, _, files in os.walk(folder):
            for name in files:
                if name.lower().endswith((".ttf", ".ttc", ".otf")):
                    index.setdefault(name.lower(), Path(root) / name)
    return index


def _font_folders() -> list[Path]:
    folders = [Path(os_util.to_actual_file("data/fonts"))]
    for variable, subfolder in (("WINDIR", "Fonts"), ("LOCALAPPDATA", "Microsoft/Windows/Fonts")):
        base = os.environ.get(variable)
        if base:
            folders.append(Path(base) / subfolder)
    home = Path.home()
    folders += [home / ".fonts", home / ".local/share/fonts", home / "Library/Fonts"]
    folders += [Path(path) for path in ("/usr/share/fonts", "/usr/local/share/fonts", "/Library/Fonts")]
    folders += [Path("/System/Library/Fonts")]
    return folders
