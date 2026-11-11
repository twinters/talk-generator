"""Topics for talks: a long, varied list of things a talk can be about, in every language talks can be in.

English's is `talkgenerator/data/topics.txt`; every other language has a list of its own beside it,
`topics.<code>.txt` (D74: `topics.nl.txt`, ...), of topics that say well in it and of its own speakers' lives, not
English's translated word for word. For suggestions, such as the random topic button of talk-generator-web (which
keeps a copy of each list, and uses the talk's language's), and for checking talkgenerator on varied topics
(`talkgenerator check --random 20`, in the language of `--language`).
"""

from __future__ import annotations

from functools import cache
from typing import Final

from talkgenerator.plan import languages
from talkgenerator.util import os_util, random_util

TOPICS_FILE: Final = "data/topics.txt"


def topics_file(language: str = languages.ENGLISH.code) -> str:
    """Where a language's topic list is (a ValueError for a language talks can't be in): data/topics.txt for English,
    data/topics.<code>.txt for the others."""
    languages.language(language)
    return TOPICS_FILE if language == languages.ENGLISH.code else f"data/topics.{language}.txt"


@cache
def all_topics(language: str = languages.ENGLISH.code) -> tuple[str, ...]:
    """Every topic of a language's list, in the file's order, without its comments, blank lines and repeats (ignoring
    case)."""
    seen: set[str] = set()
    topics = []
    for line in os_util.read_lines(topics_file(language)):
        topic = line.strip()
        if topic and not topic.startswith("#") and topic.lower() not in seen:
            seen.add(topic.lower())
            topics.append(topic)
    return tuple(topics)


def random_topics(count: int, language: str = languages.ENGLISH.code) -> list[str]:
    """Different topics of a language's list at random, count of them (or all, if there are fewer), from the current
    random stream (so a seeded talk or check draws the same ones)."""
    topics = all_topics(language)
    return random_util.sample(topics, min(count, len(topics)))
