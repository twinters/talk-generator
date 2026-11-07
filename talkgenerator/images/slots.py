"""Image slots: what a slide asks of an image, as data instead of a call to a source (docs/v5-plan.md, section 10.1).

A slot says what the image is for (its intent), the queries it searches with (a slot's own, or else the one the plan
or the slide's topic gives), its orientation and size, where a slide's text goes over it, its look (an aesthetic
profile, see talkgenerator.images.profiles), the license classes it may have besides what the talk allows, and the
sources it may come from (all of its look's, without any). The image finder (talkgenerator.images.finder) finds it.

A recipe asks for its images with slots (talkgenerator.plan.kinds.Recipe.images), and v4's content generators are
slots too (talkgenerator.schema.content_generators): called with a presentation context, a slot searches for its
"seed", as v4's image generators did.

Left room for: an image a vision model picks among the candidates, and one that's generated instead (10.4, 10.5):
`generate` says a slot may be generated.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import catalog, profiles
from talkgenerator.images.analysis import Area
from talkgenerator.images.profiles import Orientation
from talkgenerator.models.deck import LicenseClass


@dataclass(frozen=True, eq=False)
class ImageSlot:
    intent: str = ""  # what the image is for, as a slide would describe it ("the photo attached to the post")
    queries: tuple[str, ...] = ()  # its own queries, "{}" standing for the plan's or the topic's (tried in order)
    orientation: Orientation | None = None  # (the look's, without one)
    min_pixels: int = 0  # the fewest pixels it may have (as its source says it has), such as 1_000_000
    text_area: Area | None = None  # where a slide's text goes over it (the look's, without one)
    aesthetic: str = profiles.DEFAULT  # its look: the name of an aesthetic profile, or of a flavour pack
    license_classes: frozenset[LicenseClass] | None = None  # the license classes it may have, of the talk's
    sources: tuple[str, ...] = ()  # the only sources it may come from, of its look's (see talkgenerator.images.catalog)
    backups: tuple[
        str, ...
    ] = ()  # looks that take over, in order, when its own finds none (after the look's fallbacks)
    generate: bool = False  # may be generated instead (docs/v5-plan.md, 10.5): not yet

    def __post_init__(self) -> None:
        for look in (self.aesthetic, *self.backups):
            profiles.profile(look)  # (a ValueError for a look there isn't)
        for name in self.sources:
            catalog.source(name)

    def find(self, query: str | None = None, avoid: Collection[ImageData] = ()) -> ImageData | None:
        """The image for the slot, found with the query (or the slot's own), not one of those to avoid (nor nearly):
        None if none is found."""
        from talkgenerator.images import finder

        return finder.find(self, query, avoid)

    def __call__(self, presentation_context: Mapping[str, Any] | str) -> ImageData | None:
        """v4's image generators' way: the image for the presentation context's seed (its slide's topic), or for the
        word itself."""
        seed = presentation_context.get("seed") if isinstance(presentation_context, Mapping) else presentation_context
        return self.find(str(seed) if seed else None)

    def from_word(self, word: str | None) -> ImageData | None:
        """The image for a word (for v4's generators that pass a word instead of a context)."""
        return self.find(word or None)

    def but(self, **changes: Any) -> ImageSlot:
        """The slot with some of its fields changed, such as `slot.but(orientation="portrait")`."""
        return dataclasses.replace(self, **changes)

    def describe(self) -> dict[str, Any]:
        """The slot as plain data (for the formats' catalog, say)."""
        entry: dict[str, Any] = {"look": self.aesthetic}
        if self.intent:
            entry["intent"] = self.intent
        if self.orientation:
            entry["orientation"] = self.orientation
        if self.backups:
            entry["backups"] = list(self.backups)
        return entry

    def __repr__(self) -> str:
        return f"ImageSlot({self.aesthetic}{', ' + self.intent if self.intent else ''})"
