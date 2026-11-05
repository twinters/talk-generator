from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger("talkgenerator")


class ImageData:
    def __init__(
        self,
        image_url: str,
        source: str | None = None,
        on_use: Callable[[], None] | None = None,
        source_url: str | None = None,
    ) -> None:
        self._image_url = image_url
        self._source = source
        # Called once when the image ends up on a slide, e.g. for Unsplash's download tracking
        self._on_use = on_use
        # Page that the credit links to (the photographer's profile, the photo's page, ...)
        self._source_url = source_url
        # The checked bytes to embed, once downloaded (see image_util.fetch_image_data)
        self.data: bytes | None = None

    def get_image_url(self) -> str:
        return self._image_url

    def get_source(self) -> str | None:
        return self._source

    def get_source_url(self) -> str | None:
        return self._source_url

    def mark_used(self) -> None:
        callback, self._on_use = self._on_use, None
        if callback is not None:
            try:
                callback()
            except Exception as e:  # tracking must never break generation
                logger.debug("Image usage callback failed: %s", e)

    # The same image is the same element of a deck, wherever it came from: that's how slides avoid repeating it
    def __eq__(self, other: object) -> bool:
        return isinstance(other, ImageData) and other._image_url == self._image_url

    def __hash__(self) -> int:
        return hash(self._image_url)

    def __str__(self) -> str:
        return "ImageData(" + self._image_url + ((", " + self._source) if self._source is not None else "") + ")"

    def __repr__(self) -> str:
        return str(self)
