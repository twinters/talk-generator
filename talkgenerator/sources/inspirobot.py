"""InspiroBot (https://inspirobot.me): AI-generated "inspirational" quote posters.

A poster is drawn from the talk's random stream (see talkgenerator.util.random_util), so the same seed gives the
same poster, whether the slides are made in parallel or one by one. InspiroBot's API
(https://inspirobot.me/api?generate=true) can't do that: it makes a new poster for every request. Its older posters
live at predictable addresses instead, 73 folders of 9,999 each, from 2015 to 2017 (checked on 2026-11-07: all 150
drawn at random loaded, as JPEGs of 650 by 650 pixels, the size of the posters it makes now).
"""

from typing import Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import random_util

# How a browser may show its posters (see talkgenerator.models.deck.DisplayPolicy): from InspiroBot's own links
# (checked on 2026-11-07: its images load in a browser's <img>, with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its posters (see talkgenerator.images.licenses): fair use
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"fair-use"})
FOLDERS: Final = 73
POSTERS_PER_FOLDER: Final = 9999


def available() -> bool:
    """Whether a poster can be asked for: InspiroBot isn't switched off (DISABLE_INSPIROBOT)."""
    return not settings.is_source_disabled("INSPIROBOT")


def _random_poster_url() -> str:
    folder = random_util.randint(1, FOLDERS)
    number = random_util.randrange(POSTERS_PER_FOLDER)
    return f"https://generated.inspirobot.me/{folder:03d}/aXm{number}xjU.jpg"


def get_random_inspirobot_image(_: object = None) -> ImageData:
    """One of InspiroBot's posters, drawn from the current random stream (without asking InspiroBot's API)."""
    return ImageData(
        image_url=_random_poster_url(),
        source="InspiroBot",
        source_url="https://inspirobot.me",
        display=DISPLAY,
        license_class="fair-use",
    )
