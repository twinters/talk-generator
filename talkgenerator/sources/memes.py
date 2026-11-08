"""Memes with live captions: Imgflip's templates (talkgenerator.sources.imgflip), and where each has its captions.

Imgflip lists its templates' pictures but not where their captions go, so `data/memes.json` has them for 25 of its
best-known templates, measured on Imgflip's own pictures: every caption's box (as fractions of the picture, from its
top left corner), its style, and what it says (for the language model). A box is "impact" (white Impact with a black
outline, in capitals, over anything) or "plain" (black text on the template's own even area: Drake's white panels,
Gru's boards), whose colour the box keeps (`fill`), so a layout can put it under the text where the picture has it.
A box may repeat another's caption (`same_as`): Gru's fourth board is his third, read again.

A meme slide is the template's picture with its captions as texts on it (talkgenerator.design.engine lays them out):
deck elements every renderer draws already. The language model writes the captions, for a template the talk's dice
pick; a classic talk takes them from each template's own sentences about the slide's topic (`classic`), which the
TED content pack has (`data/packs/ted/memes.json`, a rule per template: see rule_of).
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from talkgenerator.sources import imgflip, packs
from talkgenerator.util import os_util

_DATA: Final = "data/memes.json"
BoxStyle = Literal["impact", "plain"]
# The most captions a template has, and the place a meme's picture gets on a 1920×1080 slide, at most (the layout's)
MOST_CAPTIONS: Final = 4
AREA: Final = (1728.0, 940.0)


@dataclass(frozen=True)
class CaptionBox:
    """Where a caption goes on a template's picture, as fractions of it (from its top left corner), how it looks,
    and what it says; or the caption of another box it repeats (counted from 1)."""

    x: float
    y: float
    w: float
    h: float
    style: BoxStyle
    says: str
    fill: str | None = None  # (a plain box: the colour of the picture there)
    same_as: int | None = None


@dataclass(frozen=True)
class MemeTemplate:
    id: str  # Imgflip's
    name: str
    url: str
    width: int
    height: int
    about: str  # what the template shows, for the language model
    boxes: tuple[CaptionBox, ...]
    # Its captions for classic talks, about the slide's topic ({seed}, {related}): the TED content pack's
    classic: tuple[tuple[str, ...], ...]

    @property
    def captions(self) -> int:
        """How many captions it takes (its boxes but those that repeat another)."""
        return sum(1 for box in self.boxes if box.same_as is None)

    def written(self) -> list[CaptionBox]:
        """The boxes whose captions are written, in order (those that don't repeat another)."""
        return [box for box in self.boxes if box.same_as is None]

    def texts(self, captions: Sequence[str | None]) -> list[str | None]:
        """The text of every box, from the template's captions in order: a box that repeats another gets its caption.
        A ValueError when a caption it needs is missing."""
        written = list(captions[: self.captions])
        if len(written) < self.captions or not all(caption and caption.strip() for caption in written):
            raise ValueError(f"the {self.name} meme needs {self.captions} captions")
        shown: list[str | None] = []
        index = 0
        for box in self.boxes:
            if box.same_as is None:
                shown.append(written[index])
                index += 1
            else:
                shown.append(shown[box.same_as - 1])
        return shown

    def imgflip(self) -> imgflip.Template:
        """The template as Imgflip lists it (as it did when its boxes were measured)."""
        return imgflip.Template(self.id, self.name, self.url, self.width, self.height, len(self.boxes))

    def shown_size(self) -> tuple[float, float]:
        """The size of its picture on a slide, at most (in canvas pixels): as large as fits the layout's area."""
        scale = min(AREA[0] / self.width, AREA[1] / self.height)
        return self.width * scale, self.height * scale

    def room(self, box: CaptionBox, size: float = 40.0) -> int:
        """About how many characters a box holds at a font size (in canvas pixels), on a slide: for the language
        model, a caption's length. (A capital is about half as wide as it's high, and a line 1.2 times its size.)"""
        width, height = self.shown_size()
        per_line = max(1, int(box.w * width / (0.55 * size)))
        lines = max(1, int(box.h * height / (1.2 * size)))
        return per_line * lines


def _box(data: dict[str, object]) -> CaptionBox:
    return CaptionBox(
        x=float(str(data["x"])),
        y=float(str(data["y"])),
        w=float(str(data["w"])),
        h=float(str(data["h"])),
        style="plain" if data.get("style") == "plain" else "impact",
        says=str(data.get("says") or ""),
        fill=str(data["fill"]) if data.get("fill") else None,
        same_as=int(str(data["same_as"])) if data.get("same_as") else None,
    )


@functools.cache
def templates() -> dict[str, MemeTemplate]:
    """The templates talkgenerator knows where to caption, by Imgflip's ID, in the order of the data file."""
    with open(os_util.to_actual_file(_DATA), encoding="utf-8") as file:
        data = json.load(file)
    found: dict[str, MemeTemplate] = {}
    for entry in data["templates"]:
        template = MemeTemplate(
            id=str(entry["id"]),
            name=str(entry["name"]),
            url=str(entry["url"]),
            width=int(entry["width"]),
            height=int(entry["height"]),
            about=str(entry["about"]),
            boxes=tuple(_box(box) for box in entry["boxes"]),
            classic=_classic(str(entry["name"])),
        )
        found[template.id] = template
    return found


def rule_of(name: str) -> str:
    """The rule of a template's classic captions in a content pack's memes grammar: the template's name in lower
    case, its words joined by underscores ("grus_plan", "buff_doge_vs_cheems")."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_")


def _classic(name: str) -> tuple[tuple[str, ...], ...]:
    """A template's captions for classic talks, from the TED content pack: sentences of a caption per box, each
    "first|second|..." in the pack."""
    pack = packs.pack(packs.TED)
    rule = f"memes.{rule_of(name)}"
    sentences = pack.rule(rule) if pack.has(rule) else []
    return tuple(tuple(sentence.split("|")) for sentence in sentences)


def template(key: str | None) -> MemeTemplate | None:
    """The template of an ID, a name ("Drake Hotline Bling", in any case) or a picture's address, if it's known."""
    if not key:
        return None
    wanted = key.strip()
    known = templates()
    if wanted in known:
        return known[wanted]
    return next(
        (
            found
            for found in known.values()
            if wanted in (found.url, found.name) or wanted.lower() == found.name.lower()
        ),
        None,
    )


def of_picture(url: str | None, page: str | None = None) -> MemeTemplate | None:
    """The template of a picture, by its address, or by the template's page its credit links to."""
    return template(url) or template(imgflip.template_id(page))


def known() -> list[imgflip.Template]:
    """The known templates as Imgflip lists them: for a search when Imgflip can't be reached."""
    return [found.imgflip() for found in templates().values()]
