import logging
from collections.abc import Callable

logger = logging.getLogger("talkgenerator")


class ImageData:
    def __init__(
        self,
        image_url: str,
        source: str | None = None,
        on_use: Callable[[], None] | None = None,
    ):
        self._image_url = image_url
        self._source = source
        # Called once when the image ends up on a slide, e.g. for Unsplash's download tracking
        self._on_use = on_use

    def get_image_url(self) -> str:
        return self._image_url

    def get_source(self) -> str | None:
        return self._source

    def mark_used(self) -> None:
        callback, self._on_use = self._on_use, None
        if callback is not None:
            try:
                callback()
            except Exception as e:  # tracking must never break generation
                logger.debug("Image usage callback failed: %s", e)

    def __str__(self):
        return "ImageData(" + self._image_url + ((", " + self._source) if self._source is not None else "") + ")"

    def __repr__(self):
        return str(self)
