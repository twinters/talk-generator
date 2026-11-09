"""Emoji in a slide's texts (docs/v5-plan.md, D65): which characters are emoji, and a text's runs with and without
them.

Some lists may have emoji (a tier list's things, an alignment chart's cells, an agenda's items), which no theme font
has: renderers draw them in an emoji font (PowerPoint and the previewer in Segoe UI Emoji, browsers in their system's),
where an emoji is wider than a letter. So a text's emoji are measured as that wide (WIDTH, in ems), and drawn in their
own runs, in EMOJI_FONT.
"""

from __future__ import annotations

from typing import Final

# The font emoji are drawn in, in a .pptx and in previews (Windows' colour emoji; elsewhere, renderers fall back to
# their system's own), and how wide an emoji is taken to be, in ems (Segoe UI Emoji's are 1.37)
EMOJI_FONT: Final = "Segoe UI Emoji"
WIDTH: Final = 1.4

# The characters below U+1F000 that are emoji as they are (Unicode's Emoji_Presentation): a watch, a coffee, a
# lightning bolt, sparkles, a star... (others, such as a heart, are emoji when U+FE0F follows them)
_PRESENTED: Final = frozenset(
    [0x231A, 0x231B, 0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23F0, 0x23F3, 0x25FD, 0x25FE, 0x2614, 0x2615]
    + list(range(0x2648, 0x2654))
    + [0x267F, 0x2693, 0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE, 0x26C4, 0x26C5, 0x26CE, 0x26D4, 0x26EA, 0x26F2]
    + [0x26F3, 0x26F5, 0x26FA, 0x26FD, 0x2705, 0x270A, 0x270B, 0x2728, 0x274C, 0x274E, 0x2753, 0x2754, 0x2755]
    + [0x2757, 0x2795, 0x2796, 0x2797, 0x27B0, 0x27BF, 0x2B1B, 0x2B1C, 0x2B50, 0x2B55]
)
_SELECTOR: Final = 0xFE0F  # (emoji presentation: what comes before it is drawn as an emoji)


def _joins(code: int) -> bool:
    """Whether a character belongs to the emoji before it and takes no room of its own: a joiner, a presentation
    selector, a keycap's frame, a skin tone or a flag's tag."""
    return code in (0x200D, 0xFE0E, _SELECTOR, 0x20E3) or 0x1F3FB <= code <= 0x1F3FF or 0xE0020 <= code <= 0xE007F


def _pictograph(code: int) -> bool:
    """Whether a character is an emoji by itself: a pictograph of the planes above U+1F000 (faces, animals, food,
    flags' letters...) or one of the few below that are emoji as they are."""
    return (0x1F000 <= code <= 0x1FAFF and not 0x1F3FB <= code <= 0x1F3FF) or code in _PRESENTED


def runs(text: str) -> list[tuple[str, bool]]:
    """The text in runs of emoji (each with what joins it) and of the rest, in order, each with whether it's emoji:
    "🐧 Penguins" is ("🐧", True), (" Penguins", False). A character followed by U+FE0F is an emoji too ("❤️")."""
    found: list[tuple[str, bool]] = []
    index = 0
    while index < len(text):
        code = ord(text[index])
        selected = index + 1 < len(text) and ord(text[index + 1]) == _SELECTOR
        emoji = _pictograph(code) or (selected and not text[index].isspace())
        end = index + 1
        if emoji:  # (with what joins it: a skin tone, a selector, and through a joiner, the next emoji of a sequence)
            while end < len(text) and (_joins(ord(text[end])) or ord(text[end - 1]) == 0x200D):
                end += 1
        part = text[index:end]
        if found and found[-1][1] == emoji:
            found[-1] = (found[-1][0] + part, emoji)
        else:
            found.append((part, emoji))
        index = end
    return found


def count(text: str) -> int:
    """How many emoji the text has (a sequence joined by U+200D counts each of its emoji, as a renderer whose font
    doesn't join them draws them all)."""
    return sum(
        1
        for index, character in enumerate(text)
        if _pictograph(ord(character))
        or (index + 1 < len(text) and ord(text[index + 1]) == _SELECTOR and not character.isspace())
    )


def room(text: str) -> int:
    """How many characters' room the text takes: two for each of its emoji (as wide as an emoji font draws one),
    however many characters it's written with (a joined one, "🕵️‍♂️", is five), and one for every other character."""
    total = 0
    for part, emoji in runs(text):
        if not emoji:
            total += len(part)
            continue
        # (an emoji begins at a character that isn't joined to the one before it by U+200D, nor joins itself)
        starts = sum(
            1
            for index, character in enumerate(part)
            if not _joins(ord(character)) and (index == 0 or ord(part[index - 1]) != 0x200D)
        )
        total += 2 * starts
    return total


def plain(text: str) -> str:
    """The text without its emoji (and what joins them)."""
    return "".join(part for part, emoji in runs(text) if not emoji)


def has_emoji(text: str) -> bool:
    return count(text) > 0
