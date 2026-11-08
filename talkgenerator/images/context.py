"""What a talk's images are found by while the talk is made: its license policy, its theme's colours, its format's
own looks, its persona's favourite looks, and its generated pictures, if it has any. The talk sets it (see `for_talk`), and the image finder reads
it, in whichever thread finds the images (talkgenerator.util.image_util.carry takes it into a talk's threads)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from talkgenerator.images import licenses

if TYPE_CHECKING:
    from talkgenerator.images.generation import ImageGeneration


@dataclass(frozen=True)
class ImageContext:
    """The license policy of a talk; the colours of its theme (none for the classic one), which its pictures had better
    go with; its format's own looks for the looks its slides ask for (a corporate format's "corporate-stock" for
    "photo", say); its image generation, for a talk that generates pictures (see talkgenerator.images.generation);
    and its persona's favourite looks for some of the looks its slides ask for (a medieval historian's weird medieval
    art for "weird", see talkgenerator.personas), which are searched first, before the slide's own look."""

    policy: licenses.LicensePolicy = licenses.ALL
    palette: tuple[str, ...] = ()
    looks: Mapping[str, str] = field(default_factory=dict)
    generation: ImageGeneration | None = None
    persona_looks: Mapping[str, str] = field(default_factory=dict)

    def look(self, name: str) -> str:
        """The look a slide's look is in this talk (its format's own, if it has one)."""
        return self.looks.get(name, name)

    def tries(self, name: str) -> tuple[str, ...]:
        """The looks a slide's look is searched in, in this talk, in order: the persona's favourite for it first (if it
        has one), and then the look itself, as the talk has it (see look)."""
        own = self.look(name)
        favourite = self.persona_looks.get(name)
        return (favourite, own) if favourite is not None and favourite != own else (own,)


_EVERY_IMAGE = ImageContext()  # (outside a talk)
_CURRENT: ContextVar[ImageContext | None] = ContextVar("talkgenerator_images", default=None)


@contextmanager
def for_talk(context: ImageContext) -> Iterator[ImageContext]:
    """Find images the talk's way in this block (and in the threads that image_util.carry takes it to)."""
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)


def current() -> ImageContext:
    """The context images are found by here: the talk's, or else every license, no theme and no format of its own."""
    return _CURRENT.get() or _EVERY_IMAGE
