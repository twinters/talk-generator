from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

logger = logging.getLogger("talkgenerator")

# A part of an image credit as it reads on a slide: its text, and the page it links to (if any)
CreditPart = tuple[str, str | None]


@dataclass(frozen=True)
class VideoCopy:
    """A video of what a gif shows (such as Reddit's mp4 copy of it), and a still of it for the video's poster frame.

    A gif can be too large to embed (r/gifs has many of 40 to 60 MB), while its mp4 copy is a few MB: then the video
    plays in its place, looping and without sound, the way the gif would (see image_util.fetch_image_data).
    """

    url: str
    poster_url: str


class ImageData:
    def __init__(
        self,
        image_url: str,
        source: str | None = None,
        on_use: Callable[[], None] | None = None,
        source_url: str | None = None,
        credit: Sequence[CreditPart] | None = None,
        description: str | None = None,
        video: VideoCopy | None = None,
    ) -> None:
        self._image_url = image_url
        self._source = source
        # What the image shows, as its source describes it (its alt text, title or tags), if it does
        self.description = " ".join(description.split())[:200] if description else None
        # Called once when the image ends up on a slide, e.g. for Unsplash's download tracking
        self._on_use = on_use
        # Page that the credit links to (the photographer's profile, the photo's page, ...)
        self._source_url = source_url
        # The credit in parts, for credits that link more than one page (the photographer and Unsplash, say)
        self._credit = tuple(credit) if credit else None
        # The checked bytes to embed, once downloaded (see image_util.fetch_image_data)
        self.data: bytes | None = None
        # A video copy, for when the image itself can't be used (a gif too large to embed, say)
        self.video = video
        # The checked bytes of the video copy, once it plays in the image's place: data then holds its poster frame's
        self.video_data: bytes | None = None
        # The search that found it, when talkgenerator knows (see found_with)
        self.query: str | None = None

    def found_with(self, query: str) -> ImageData:
        """This image, noting the search that found it: a copy, as a source may hand out the same object again."""
        found = copy.copy(self)
        found.query = query
        return found

    def get_image_url(self) -> str:
        return self._image_url

    def get_shown_url(self) -> str:
        """The URL of the picture a slide shows: the image's own, or its video's poster frame once the video plays in
        the image's place. A deck names an image by this URL."""
        if self.video is not None and self.video_data is not None:
            return self.video.poster_url
        return self._image_url

    def get_source(self) -> str | None:
        return self._source

    def get_source_url(self) -> str | None:
        return self._source_url

    def get_credit(self) -> tuple[CreditPart, ...]:
        """The credit as it reads on a slide: by default the source, linking to the source's page."""
        if self._credit:
            return self._credit
        return ((self._source, self._source_url),) if self._source else ()

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
