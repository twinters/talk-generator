"""Emoji for classic talks' lists (docs/v5-plan.md, D65): now and then, a tier list's things, an alignment chart's cells
and an agenda's items each get one in front, as a language model's lists do when their recipe's variant asks.

A thing gets its own emoji when a word of it is in talkgenerator's list (data/emoji.json: "Penguins" gets a penguin,
"Fresh bread" bread), and else one of its place's mood (a tier list's S tier a crown or a trophy, its F tier a bin; an
alignment chart's chaotic evil a devil). The list has none for faiths, drink, weapons or death, and no sequences
joined into one emoji, which not every font joins.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from typing import Final

from talkgenerator.util import emoji_util, os_util, random_util

EMOJI_FILE: Final = "data/emoji.json"
CHANCE: Final = 1 / 3  # of the classic tier lists, alignment charts and agendas whose things get emoji


@cache
def _emoji() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """The list's emoji by word (lowercase, singular), and its moods' emoji by mood."""
    data = json.loads(Path(os_util.to_actual_file(EMOJI_FILE)).read_text(encoding="utf-8"))
    return dict(data["words"]), {mood: tuple(emoji) for mood, emoji in data["moods"].items()}


def moods() -> tuple[str, ...]:
    return tuple(_emoji()[1])


def own(thing: str) -> str | None:
    """The thing's own emoji, by a word of it in the list: a phrase of two words first ("ice cream"), then its words
    from the last one (a thing's noun comes last in English: "Fresh bread"), each as it is or in the singular."""
    words, _ = _emoji()
    found = re.findall(r"[a-z]+", thing.lower())
    for first, second in zip(found[-2::-1], found[:0:-1], strict=False):  # (the pairs of words, the last pair first)
        for form in _singulars(second):
            emoji = words.get(f"{first} {form}")
            if emoji is not None:
                return emoji
    for word in reversed(found):
        for form in _singulars(word):
            emoji = words.get(form)
            if emoji is not None:
                return emoji
    return None


def _singulars(word: str) -> list[str]:
    """The word, and what it may be in the singular ("penguins": "penguin"; "berries": "berry"; "boxes": "box")."""
    forms = [word]
    if word.endswith("ies") and len(word) > 4:
        forms.append(word[:-3] + "y")
    if word.endswith("es") and len(word) > 3:
        forms.append(word[:-2])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        forms.append(word[:-1])
    return forms


def pick(thing: str, mood: str, own_words: bool = True) -> str:
    """An emoji for the thing: its own (by its English words, unless own_words is off: a thing in another language),
    or else one of the mood's, with the talk's random stream."""
    return (own(thing) if own_words else None) or random_util.choice(_emoji()[1][mood])


def with_emoji(thing: str, mood: str, own: bool = True) -> str:
    """The thing with an emoji in front of it ("🐧 Penguins"), unless it starts with one already (by its English words
    only when own is)."""
    thing = thing.strip()
    if not thing or _starts_with_emoji(thing):
        return thing
    return f"{pick(thing, mood, own)} {thing}"


def listed(text: str | None, mood: str, own: bool = True) -> str | None:
    """The things of a list written as one text (separated by |), each with an emoji in front of it (one that a
    language model put there stays)."""
    if not text:
        return text
    return " | ".join(with_emoji(thing, mood, own) for thing in text.split("|") if thing.strip())


def _starts_with_emoji(text: str) -> bool:
    runs = emoji_util.runs(text)
    return bool(runs) and runs[0][1]
