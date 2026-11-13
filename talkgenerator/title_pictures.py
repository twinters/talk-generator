"""The title slide's picture (docs/v5-plan.md, D80): a photo of the talk's world beside its title, so that the first
slide already says what kind of talk it is, for the presenter and the audience alike (the user, 2026-11-13: "some first
slides should hint at what kind of slideshow it is, or which persona: a wedding talk would better have a wedding
picture there already").

A talk's world is its format's (a wedding toast's wedding, a court case's courtroom), or else its persona's (a
detective's, a kindergarten teacher's classroom): a few plain English words, a scene, which the picture is searched for
with the talk's topic first ("penguins wedding") and then alone ("wedding"). A TED-like talk without a persona has none,
and its title slide is as it was.

The search starts with the talk, in the background (as its real facts are looked up: see talkgenerator.facts), as it
needs nothing the language model writes: by the time the title slide is made, from the model's spine, the picture is
in, and the title slide waits for it no longer than DEADLINE seconds from the talk's start. It's searched with the
talk's own image context (its license policy, its persona's looks) and a random stream of its own, so the same seed
finds the same picture.
"""

from __future__ import annotations

import contextvars
import logging
import threading
import time
from typing import TYPE_CHECKING, Final

from talkgenerator.images.slots import ImageSlot
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.datastructures.image_data import ImageData
    from talkgenerator.personas import Persona
    from talkgenerator.schema.formats import Format

logger = logging.getLogger("talkgenerator")

DEADLINE: Final = 8.0  # seconds from the talk's start that its title slide waits for its picture, at most

SLOT: Final = ImageSlot("a photo of the talk's world, beside its title, which says what kind of talk it is")

# The worlds of the personas' talks (a format's is its own: Format.scene), as a stock photo site finds them
PERSONA_SCENES: Final[dict[str, str]] = {
    "disgraced_professor": "lecture hall",
    "startup_founder": "startup office",
    "medieval_historian": "medieval castle",
    "conspiracy_blogger": "tinfoil hat",
    "kindergarten_teacher": "kindergarten classroom",
    "consultant": "business meeting",
    "motivational_speaker": "motivational speaker stage",
    "influencer": "selfie",
    "time_traveller": "time machine",
    "life_coach": "meditation",
    "retiree": "retirement",
    "former_athlete": "stadium",
    "passionate_expert": "laboratory",
    "detective": "detective",
    "infomercial_host": "tv studio",
    "nature_narrator": "wildlife",
    "museum_guide": "museum",
    "best_man": "wedding",
    "game_show_host": "game show",
    "alien_anthropologist": "ufo",
    "it_support": "computer help desk",
}


def scene(talk_format: Format | None, persona: Persona | None) -> str | None:
    """The talk's world, for its title slide's picture: its format's, or else its persona's (None for neither)."""
    own = getattr(talk_format, "scene", "") if talk_format is not None else ""
    if own:
        return own
    return PERSONA_SCENES.get(persona.name) if persona is not None else None


def queries(topic: str, world: str) -> list[str]:
    """What the picture is searched for, in order: the topic in its world, and then the world alone."""
    return [f"{topic} {world}".strip(), world]


class Lookup:
    """A talk's title picture being looked up in the background, from the talk's start: result() waits for it until
    DEADLINE seconds after that start, and gives None if it isn't found by then."""

    def __init__(self, topic: str, world: str, rng: random_util.Rng, deadline: float = DEADLINE) -> None:
        self._until = time.monotonic() + deadline
        self._done = threading.Event()
        self._picture: ImageData | None = None
        run = contextvars.copy_context().run  # (the talk's image context: its license policy, its persona's looks)
        task = lambda: run(self._find, topic, world, rng)  # noqa: E731
        threading.Thread(target=task, name="title picture", daemon=True).start()

    def _find(self, topic: str, world: str, rng: random_util.Rng) -> None:
        try:
            with random_util.use(rng):
                for query in queries(topic, world):
                    self._picture = SLOT.find(query)
                    if self._picture is not None:
                        break
        except Exception:  # a source that misbehaves shouldn't sink the talk: its title slide goes without
            logger.warning("Could not find a title picture for %r", topic, exc_info=True)
        finally:
            self._done.set()

    def result(self) -> ImageData | None:
        self._done.wait(max(0.0, self._until - time.monotonic()))
        return self._picture if self._done.is_set() else None


def lookup(topic: str, talk_format: Format | None, persona: Persona | None, rng: random_util.Rng) -> Lookup | None:
    """Start looking up the talk's title picture (see Lookup), if its format or persona has a world; else None."""
    world = scene(talk_format, persona)
    if not world or not topic.strip():
        return None
    return Lookup(topic.strip(), world, rng)
