"""InspiroBot (https://inspirobot.me): AI-generated "inspirational" quote posters."""

from typing import Final

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.models.deck import DisplayPolicy, LicenseClass
from talkgenerator.util import http_util, random_util

_GENERATE_URL = "https://inspirobot.me/api?generate=true"
# How a browser may show its posters (see talkgenerator.models.deck.DisplayPolicy): from InspiroBot's own links
# (checked on 2026-11-07: its images load in a browser's <img>, with a referrer and without)
DISPLAY: Final[DisplayPolicy] = "direct"
# The license classes of its posters (see talkgenerator.images.licenses): fair use
LICENSES: Final[frozenset[LicenseClass]] = frozenset({"fair-use"})


def available() -> bool:
    """Whether a poster can be asked for: InspiroBot isn't switched off (DISABLE_INSPIROBOT)."""
    return not settings.is_source_disabled("INSPIROBOT")


def _legacy_random_image_url() -> str:
    # Older posters still live at predictable URLs; used when the generate API doesn't answer.
    return "https://generated.inspirobot.me/0{:02d}/aXm{}xjU.jpg".format(
        random_util.randint(1, 73), random_util.randint(0, 9998)
    )


def get_random_inspirobot_image(_: object = None) -> ImageData:
    response = http_util.get(_GENERATE_URL, timeout=10)
    image_url = response.text.strip() if response is not None and response.ok else ""
    if not image_url.startswith("https://"):
        image_url = _legacy_random_image_url()
    return ImageData(
        image_url=image_url,
        source="InspiroBot",
        source_url="https://inspirobot.me",
        display=DISPLAY,
        license_class="fair-use",
    )
