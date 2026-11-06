"""Topics for talks (`talkgenerator/data/topics.txt`): a long, varied list of things a talk can be about.

For suggestions, such as the random topic button of talk-generator-web (which keeps a copy of the file), and for
checking talkgenerator on varied topics (`talkgenerator check --random 20`).
"""

from __future__ import annotations

from functools import cache
from typing import Final

from talkgenerator.util import os_util, random_util

TOPICS_FILE: Final = "data/topics.txt"


@cache
def all_topics() -> tuple[str, ...]:
    """Every topic, in the file's order, without its comments, blank lines and repeats (ignoring case)."""
    seen: set[str] = set()
    topics = []
    for line in os_util.read_lines(TOPICS_FILE):
        topic = line.strip()
        if topic and not topic.startswith("#") and topic.lower() not in seen:
            seen.add(topic.lower())
            topics.append(topic)
    return tuple(topics)


def random_topics(count: int) -> list[str]:
    """Different topics at random, count of them (or all, if there are fewer), from the current random stream (so
    a seeded talk or check draws the same ones)."""
    topics = all_topics()
    return random_util.sample(topics, min(count, len(topics)))
