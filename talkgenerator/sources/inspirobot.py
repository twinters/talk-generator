"""InspiroBot (https://inspirobot.me): AI-generated "inspirational" quote posters."""

import random

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.util import http_util

_GENERATE_URL = "https://inspirobot.me/api?generate=true"


def _legacy_random_image_url():
    # Older posters still live at predictable URLs; used when the generate API doesn't answer.
    return "https://generated.inspirobot.me/0{:02d}/aXm{}xjU.jpg".format(random.randint(1, 73), random.randint(0, 9998))


def get_random_inspirobot_image(_=None):
    response = http_util.get(_GENERATE_URL, timeout=10)
    image_url = response.text.strip() if response is not None and response.ok else ""
    if not image_url.startswith("https://"):
        image_url = _legacy_random_image_url()
    return ImageData(image_url=image_url, source="InspiroBot", source_url="https://inspirobot.me")
