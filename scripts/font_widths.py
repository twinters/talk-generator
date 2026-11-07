#!/usr/bin/env python3
"""Measures every character's width in the fonts themes use that have no open twin in talkgenerator's data/fonts
(Arial Black, Verdana, Trebuchet MS, Impact, Comic Sans MS), from their own files, and writes the widths to
talkgenerator/data/fonts/widths.json. With them, a computer without those fonts (a Linux server, CI) measures texts in
them as a computer with them does (see talkgenerator.design.fonts).

Run it on a computer that has the fonts, as Windows does, when a theme gets such a font or the fonts change (where the
fonts are installed, the tests compare the widths with them):

  uv run python scripts/font_widths.py
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import PIL

from talkgenerator.design import fonts
from talkgenerator.util import os_util

TABLE = Path(os_util.to_actual_file(fonts.WIDTHS_FILE))
# The characters measured: ASCII, Latin-1 and Latin Extended-A (the letters of the languages talks are written in, and
# of most other European ones), and the rest of Windows' code page 1252 (dashes, quotes, the euro sign...)
CHARACTERS = "".join(
    [chr(code) for code in range(0x20, 0x7F)]
    + [chr(code) for code in range(0xA0, 0x180)]
    + list("ƒˆ˜–—‘’‚“”„†‡•…‰‹›€™")
)


def main() -> int:
    bundled = Path(os_util.to_actual_file("data/fonts"))
    tables: dict[str, list[float]] = {}
    for font, files in fonts.FONTS.items():
        if any((bundled / name).is_file() for name in (*files.regular, *files.bold)):
            continue  # (measured with its open twin, everywhere)
        for bold in (False, True):
            own = (files.bold if bold else files.regular)[0]
            path = fonts.font_file(font, bold)
            if path is None or path.name.lower() != own.lower():
                print(f"{font}{' bold' if bold else ''} needs its own file, {own}, which isn't here", file=sys.stderr)
                return 1
            if own.lower() not in tables:
                widths = [fonts.text_width(character, font, fonts.MEASURING_SIZE, bold) for character in CHARACTERS]
                tables[own.lower()] = [int(width) if width.is_integer() else round(width, 2) for width in widths]
    about = (
        f"Every character's width (in pixels, in text {fonts.MEASURING_SIZE} pixels high) in the fonts themes use"
        " that have no open twin here, measured from their own files by scripts/font_widths.py"
    )
    lines = [
        "{",
        f'  "about": {json.dumps(about)},',
        f'  "measured on": {json.dumps(f"{platform.platform()}, Pillow {PIL.__version__}")},',
        f'  "size": {fonts.MEASURING_SIZE},',
        f'  "characters": {json.dumps(CHARACTERS)},',
        '  "fonts": {',
        ",\n".join(
            f"    {json.dumps(name)}: {json.dumps(widths, separators=(',', ':'))}"
            for name, widths in sorted(tables.items())
        ),
        "  }",
        "}",
    ]
    TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(CHARACTERS)} characters' widths in {', '.join(sorted(tables))} to {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
