"""The title slide's picture (docs/v5-plan.md, D80): a photo of the talk's world beside its title, so that the first
slide already says what kind of talk it is, for the presenter and the audience alike (the user, 2026-11-13: "some first
slides should hint at what kind of slideshow it is, or which persona: a wedding talk would better have a wedding
picture there already").

A talk's world is its format's (a wedding toast's wedding, a court case's courtroom), or else its persona's (a
detective's, a kindergarten teacher's classroom): a few plain English words, a scene, which the picture is searched for
with the talk's topic first ("penguins wedding") and then alone ("wedding"). A TED-like talk without a persona has none,
and its title slide is as it was. A photo of one person is left out (by its description: see alone), as beside the
title they'd pass for the presenter (D81); a couple, a class or a crowd may come.

The search starts with the talk, in the background (as its real facts are looked up: see talkgenerator.facts), as it
needs nothing the language model writes: by the time the title slide is made, from the model's spine, the picture is
in, and the title slide waits for it no longer than DEADLINE seconds from the talk's start. It's searched with the
talk's own image context (its license policy, its persona's looks) and a random stream of its own, so the same seed
finds the same picture.
"""

from __future__ import annotations

import contextvars
import logging
import re
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

# A photo of one grown-up beside the title passes for the presenter (D81: the user found a keynote speaker's portrait
# on a keynote's title slide, "then it looks like the presenter isn't the person presenting"), but a couple, a class or
# a crowd is a scene of the talk's world (a wedding's couple). Who a description is of: one of these first, ...
_ONE: Final = (
    r"man|woman|person|guy|lady(?! justice)|gentleman|male|female|businessman|businesswoman|businessperson|"
    r"business professional|speaker|presenter|lecturer|professor|teacher|student|doctor|scientist|researcher|"
    r"detective|investigator|chef|barista|athlete|model|influencer|blogger|vlogger|youtuber|worker|employee|bride|"
    r"groom|host|hostess|reporter|journalist|judge|lawyer|attorney|officer|policeman|policewoman|senior|retiree|"
    r"pensioner|grandfather|grandmother|grandpa|grandma|astronaut|pilot|soldier|monk|entrepreneur|founder|ceo|"
    r"executive|manager|boss|coach|consultant|technician|engineer|programmer|developer|hacker|nurse|surgeon|tourist|"
    r"traveler|traveller|hiker|singer|performer|musician|guitarist|pianist|dancer|ballerina|comedian|magician|artist|"
    r"actor|actress|priest|husband|wife|mother|father|teenager|adult|graduate|salesman|saleswoman|customer|someone|"
    r"somebody|individual|he|she"
)
# ... and nobody else of theirs ("speaker addressing a large audience" is one person, as an audience is no subject of
# a photo's; "people attending a conference", "bride and groom" and "couple, wedding" are not)
_MORE: Final = (
    r"people|persons|couples?|newlyweds?|group|groups|crowd|crowds|audience|audiences|men|women|children|kids|students|"
    r"pupils|classmates|team|teams|family|families|friends|colleagues|coworkers|guests|spectators|fans|players|"
    r"employees|workers|businessmen|businesswomen|businesspeople|partners|teammates|scientists|doctors|teachers|"
    r"visitors|tourists|participants|attendees|seniors|parents|grandparents|siblings|twins|dancers|musicians|singers|"
    r"performers|band|choir|staff|crew|adults|boys|girls|ladies|two|three|four|several|they|them"
)
# (a couple and a class anywhere make it a scene of people)
_TOGETHER: Final = re.compile(
    r"\b(?:couples?|newlyweds?|famil(?:y|ies)|friends|together|kiss(?:es|ing)?|hug(?:s|ging)?|embrac(?:e|es|ing)|"
    r"children|kids|students|pupils|classmates|team|group|colleagues|coworkers|parents|siblings|twins|partners)\b",
    re.IGNORECASE,
)
# (and a child in a caption: a child is nobody's presenter; but Pixabay tags a woman a girl as well)
_CHILD: Final = re.compile(r"\b(?:child|kid|girl|boy|baby|toddler|son|daughter)\b", re.IGNORECASE)
_PERSON: Final = re.compile(rf"\b(?:(?P<one>{_ONE})|(?P<more>{_MORE}))\b(?!['’]s)", re.IGNORECASE)
_ONE_TAG: Final = re.compile(rf"(?:[\w-]+ )*(?:{_ONE})", re.IGNORECASE)
_MORE_TAG: Final = re.compile(rf"(?:[\w-]+ )*(?:{_MORE})", re.IGNORECASE)
_PAIRS: Final = ({"man", "woman"}, {"bride", "groom"}, {"husband", "wife"}, {"mother", "father"})
_FIRST_TAGS: Final = 4  # (a list of tags names its subject first: "speaker, speech, presentation, keynote, ...")

# The worlds of the personas' talks (a format's is its own: Format.scene), as a stock photo site finds them: places
# and things, rather than the people in them (D81: "motivational speaker stage" found one speaker in most of its photos,
# and "tinfoil hat" someone wearing one)
PERSONA_SCENES: Final[dict[str, str]] = {
    "disgraced_professor": "lecture hall",
    "startup_founder": "startup office",
    "medieval_historian": "medieval castle",
    "conspiracy_blogger": "conspiracy board",
    "kindergarten_teacher": "kindergarten classroom",
    "consultant": "business meeting",
    "motivational_speaker": "arena stage lights",
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


def alone(description: str) -> bool:
    """Whether a found picture's description is of one grown-up, with nobody else of theirs (see _ONE): beside the
    title, they'd pass for the presenter. A caption is, when the first person it names is one ("A woman giving a speech
    on stage", "Speaker addressing a large audience"), and it names no other ("Bride walking towards the groom") nor a
    scene of people ("A teacher with her pupils"); a list of tags (Pixabay's) is, when one of its first few names one
    ("speaker, speech, keynote") and none of them names more, nor any a couple or a class ("couple"; "man, woman")."""
    tags = [tag.strip() for tag in description.split(",")]
    if len(tags) >= 3 and all(len(tag.split()) <= 4 for tag in tags):
        first_tags = tags[:_FIRST_TAGS]
        words = {word.lower() for tag in tags for word in tag.split()}
        if any(_MORE_TAG.fullmatch(tag) for tag in first_tags) or any(_TOGETHER.search(tag) for tag in tags):
            return False
        return not any(pair <= words for pair in _PAIRS) and any(_ONE_TAG.fullmatch(tag) for tag in first_tags)
    first = _PERSON.search(description)
    if first is None or first.group("more") or _TOGETHER.search(description) or _CHILD.search(description):
        return False
    named, end = {first.group("one").lower(), "he", "she"}, first.end()
    for match in _PERSON.finditer(description, first.end()):
        # (another one, but not the same one again, in other words: "Female judge", "a woman speaker"; "she")
        if match.group("one") and match.group("one").lower() not in named and match.start() > end + 1:
            return False
        end = match.end()
    return True


SLOT: Final = ImageSlot(
    "a photo of the talk's world, beside its title, which says what kind of talk it is", unwanted=alone
)


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
    """Start looking up the talk's title picture (see Lookup), if its format or persona has a world; else None (and
    with DISABLE_TITLE_PICTURES, as offline tests have it, whose searches they fake)."""
    from talkgenerator import settings  # (here: it reads the environment's settings, which tests change)

    if settings.is_source_disabled("TITLE_PICTURES"):
        return None
    world = scene(talk_format, persona)
    if not world or not topic.strip():
        return None
    return Lookup(topic.strip(), world, rng)
