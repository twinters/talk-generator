"""The image sources as the image finder sees them (talkgenerator.images.finder): what each is called, the license
classes of its images, whether it can be searched now (its keys, and its cooldown), and its search, with the filters
a look asks of it (see talkgenerator.images.profiles).

Every source module declares the license classes of its images (`LICENSES`) and how a browser may show them
(`DISPLAY`), and keeps its own cache of answers and its own cooldown, as in v4. Reddit is a source per flavour pack:
"reddit:memes" searches the memes pack's subreddits.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import profiles
from talkgenerator.models.deck import LicenseClass
from talkgenerator.sources import (
    art_institute,
    giphy,
    inspirobot,
    openverse,
    pexels,
    pixabay,
    reddit,
    shitpostbot,
    unsplash,
    wikimedia_commons,
)
from talkgenerator.util.generator_util import planned

logger = logging.getLogger("talkgenerator")


@dataclass(frozen=True)
class Search:
    """A search at a source: its query (as it reads there), the source's filters for the look, an orientation, and the
    license classes the talk allows (for a source whose images each have their own, such as Openverse)."""

    query: str
    params: Mapping[str, str] = field(default_factory=dict)
    orientation: str | None = None
    classes: frozenset[LicenseClass] = frozenset()


# The candidates a search found, in the order of its results, each with its weight (for ShitpostBot: its rating)
Found = list[tuple[float, ImageData]]


@dataclass(frozen=True)
class Source:
    name: str
    description: str
    classes: frozenset[LicenseClass]
    search: Callable[[Search], Found]
    available: Callable[[], bool]
    needs_query: bool = True
    animated: bool = False


def _plain(images: list[ImageData]) -> Found:
    return [(1.0, image) for image in images]


def _unsplash(search: Search) -> Found:
    return _plain(unsplash.search_photos(search.query, search.params.get("color"), search.orientation))


def _unsplash_random(search: Search) -> Found:
    return _plain(unsplash.random_as_list())


def _pexels(search: Search) -> Found:
    return _plain(pexels.search_photos(search.query, search.params.get("color"), search.orientation))


def _pixabay(search: Search) -> Found:
    return _plain(
        pixabay.search_photos(
            search.query,
            orientation=search.orientation or search.params.get("orientation") or "all",
            colors=search.params.get("colors"),
            image_type=search.params.get("image_type") or "photo",
        )
    )


def _openverse(search: Search) -> Found:
    return _plain(
        openverse.search_photos(
            search.query,
            classes=search.classes & openverse.LICENSES or None,
            category=search.params.get("category"),
            orientation=search.orientation,
            sources=search.params.get("sources"),
        )
    )


def _wikimedia(search: Search) -> Found:
    return _plain(wikimedia_commons.search_images(search.query))


def _art_institute(search: Search) -> Found:
    return _plain(art_institute.search_artworks(search.query))


def _giphy(search: Search) -> Found:
    return _plain(giphy.search_gifs(search.query))


def _inspirobot(search: Search) -> Found:
    return _plain([inspirobot.get_random_inspirobot_image()])


def _shitpostbot(search: Search) -> Found:
    # (as v4: its best rated images for the query, or a random page of them for a classic search that found none)
    rated = shitpostbot.search_images_rated(search.query) or shitpostbot.get_random_images_rated(search.query)
    return [(float(rating), image) for rating, image in rated]


def _reddit(flavour: profiles.Flavour) -> Callable[[Search], Found]:
    subreddits = "+".join(flavour.subreddits)

    def search(search: Search) -> Found:
        found = reddit.search_images(subreddits, search.query, animated=flavour.animated)
        if not found and not planned():  # (as v4: the hot posts, for a classic search that found none)
            found = reddit.search_images(subreddits, None, animated=flavour.animated)
        return _plain([reddit.image_data(image) for image in found or ()])

    return search


SOURCES: Final[dict[str, Source]] = {
    source.name: source
    for source in (
        Source("unsplash", "Unsplash's photos", unsplash.LICENSES, _unsplash, unsplash.available),
        Source(
            "unsplash-random",
            "a random photo of Unsplash's",
            unsplash.LICENSES,
            _unsplash_random,
            unsplash.available,
            needs_query=False,
        ),
        Source("pexels", "Pexels' photos", pexels.LICENSES, _pexels, pexels.available),
        Source(
            "pixabay",
            "Pixabay's photos, illustrations and vector graphics",
            pixabay.LICENSES,
            _pixabay,
            pixabay.available,
        ),
        Source(
            "openverse",
            "openly licensed images from Flickr, museums, Wikimedia and more",
            openverse.LICENSES,
            _openverse,
            openverse.available,
        ),
        Source(
            "wikimedia",
            "Wikimedia Commons' free files",
            wikimedia_commons.LICENSES,
            _wikimedia,
            wikimedia_commons.available,
        ),
        Source(
            "art-institute",
            "the Art Institute of Chicago's public domain artworks",
            art_institute.LICENSES,
            _art_institute,
            art_institute.available,
        ),
        Source("giphy", "GIPHY's gifs", giphy.LICENSES, _giphy, giphy.available, animated=True),
        Source(
            "inspirobot",
            "InspiroBot's posters",
            inspirobot.LICENSES,
            _inspirobot,
            inspirobot.available,
            needs_query=False,
        ),
        Source(
            "shitpostbot", "ShitpostBot 5000's source images", shitpostbot.LICENSES, _shitpostbot, shitpostbot.available
        ),
        *(
            Source(
                profiles.reddit(name),
                f"Reddit: {flavour.description} (r/{', r/'.join(flavour.subreddits)})",
                reddit.LICENSES,
                _reddit(flavour),
                reddit.available,
                animated=flavour.animated,
            )
            for name, flavour in profiles.FLAVOURS.items()
        ),
    )
}


def source(name: str) -> Source:
    found = SOURCES.get(name)
    if found is None:
        raise ValueError(f"There's no image source {name!r}; there are {', '.join(SOURCES)}")
    return found


def describe() -> list[dict[str, Any]]:
    """The sources, for people and agents: name, what it has, and the license classes of its images."""
    return [
        {"name": name, "description": found.description, "licenses": sorted(found.classes)}
        for name, found in SOURCES.items()
    ]
