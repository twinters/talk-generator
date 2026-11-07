"""Aesthetic profiles: named looks, with the sources that have them and the filters that get them (docs/v5-plan.md,
section 10.3). Slide types and formats ask for looks (see talkgenerator.images.slots), and the image finder gets them
(talkgenerator.images.finder), cheapest filters first:

1. the sources' own filters (an API's colour and orientation parameters, Wikimedia Commons' categories, ...),
2. query modifiers (a classic search gets one of a look's words, as v4's searches did; a plan's goes as written),
3. a look at thumbnails, with Pillow (talkgenerator.images.analysis): a look's preferences in a picture, such as
   black and white for `vintage`, or little detail where the text goes for `calm-backdrop`, and in a themed talk,
   colours that go with its theme's;
4. and a treatment, for a look whose picture didn't come out right: `vintage` turns sepia in a theme that has no
   filter of its own.

A look's sources have weights: v4's weighted mixes of sources (its CombinedGenerators) became them, such as 1000 for
stock photos to 300 for Reddit's pictures in `neutral`. A look the talk's license policy allows none of the sources
of, or whose sources find nothing, hands over to its fallback, such as `meme-chaos` to `weird-stock`.

Flavour packs are looks of weird content, from curated sets of subreddits per mood (`cursed`, `wholesome`,
`bad-charts`, `medieval`, ...): their searches go to those subreddits, and their posts are fair use.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from talkgenerator.images.analysis import MIDDLE, Area, palette_fit
from talkgenerator.models.deck import ImageAnalysis
from talkgenerator.models.theme import ImageFilter

Orientation = Literal["landscape", "portrait", "square"]
# How much colours that go with a themed talk's theme count, for a look that doesn't say
PALETTE: Final = 0.3


@dataclass(frozen=True)
class SourceUse:
    """A source a look searches (by its name in talkgenerator.images.catalog), how often (its weight, against the
    look's other sources), how a query reads there ("{} deepcat:..." puts the query first), its own filters for the
    look (an API's parameters), and words a classic search gets one of there, if the look's own aren't for it."""

    source: str
    weight: float = 1.0
    query: str = "{}"
    params: Mapping[str, str] = field(default_factory=dict)
    modifiers: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Preferences:
    """What a look prefers in a picture, by a look at its thumbnail: in one colour (gray, or toned, as old photographs
    are); little detail where the text goes, at most this much; a brightness and a colourfulness within these; its
    main colours near these; and (in a themed talk) how much colours that go with the theme count."""

    monochrome: bool = False
    detail: float | None = None
    brightness: tuple[float, float] | None = None
    colourfulness: tuple[float, float] | None = None
    colors: tuple[str, ...] = ()
    palette: float = PALETTE

    def met_by(self, look: ImageAnalysis | None) -> bool:
        """Whether a picture has what the look prefers, as far as a look at it tells (a picture that couldn't be
        looked at has none of it, unless the look prefers nothing a look tells)."""
        if look is None:
            return not (self.monochrome or self.detail is not None or self.brightness or self.colourfulness)
        if self.monochrome and not look.monochrome:
            return False
        if self.detail is not None and look.detail is not None and look.detail > self.detail:
            return False
        if self.brightness and not self.brightness[0] <= look.brightness <= self.brightness[1]:
            return False
        return not (self.colourfulness and not self.colourfulness[0] <= look.colourfulness <= self.colourfulness[1])

    def closeness(self, look: ImageAnalysis | None) -> float:
        """How close a picture comes to what the look prefers, from 0 to 1 (1: it has all of it)."""
        if look is None:
            return 0.0
        scores = []
        if self.monochrome:
            scores.append(1.0 if look.monochrome else 0.5 * look.grayscale)
        if self.detail is not None and look.detail is not None:
            scores.append(
                1.0 if look.detail <= self.detail else max(0.0, 1 - (look.detail - self.detail) / self.detail)
            )
        if self.brightness:
            scores.append(_within(look.brightness, self.brightness))
        if self.colourfulness:
            scores.append(_within(look.colourfulness, self.colourfulness))
        if self.colors:
            scores.append(palette_fit(look, self.colors))
        return sum(scores) / len(scores) if scores else 1.0


def _within(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    if low <= value <= high:
        return 1.0
    return max(0.0, 1 - min(abs(value - low), abs(value - high)) / 0.3)


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    sources: tuple[SourceUse, ...]
    # Words a classic search gets one of (picked by the talk's dice) before its query, as v4's searches did
    modifiers: tuple[str, ...] = ()
    orientation: Orientation | None = None
    text_area: Area | None = None  # where a slide's text goes over its pictures
    prefers: Preferences | None = None
    # How many candidates get a look before the pick: 0 picks at random, as v4 did (in a themed talk, a few get a
    # look anyway, for colours that go with the theme)
    looks: int = 0
    treatment: ImageFilter | None = None  # what a picture that doesn't have the look gets, in a theme without a filter
    fallback: str | None = None  # the look that takes over when this one's sources can't or don't find any
    breadth: int = 2  # how many of its sources are searched at once, in parallel
    last_resort: tuple[SourceUse, ...] = ()  # for a classic search that found nothing: random pictures
    animated: bool = False  # only pictures that move (gifs)
    needs_query: bool = True  # (InspiroBot's posters take none)


@dataclass(frozen=True)
class Flavour:
    """A flavour pack: a mood of weird content, from curated subreddits (searched for the query, or their hot posts for
    a classic search that found nothing there)."""

    name: str
    description: str
    subreddits: tuple[str, ...]
    animated: bool = False
    fallback: str | None = None  # the look that stands in for it without Reddit (none: a slide needs its pack)


# FLAVOUR PACKS. The first ones are v4's sets of subreddits, which its slides took their weird images from.
FLAVOURS: Final[dict[str, Flavour]] = {
    flavour.name: flavour
    for flavour in (
        Flavour("gifs", "gifs that move", ("gifs", "gif", "gifextra", "nonononoYES"), animated=True),
        Flavour(
            "memes",
            "memes and comics",
            (
                "meme",
                "memes",
                "MemeEconomy",
                "wholesomememes",
                "dankmemes",
                "AdviceAnimals",
                "comics",
                "HistoryMemes",
                "ProgrammerHumor",
            ),
        ),
        Flavour(
            "weird",
            "odd, confusing and cursed pictures",
            (
                "hmmm",
                "hmm",
                "wtf",
                "wtfstockphotos",
                "weirdstockphotos",
                "darkstockphotos",
                "photoshopbattles",
                "confusing_perspective",
                "cursedimages",
                "HybridAnimals",
                "EyeBleach",
                "natureismetal",
                "195",
                "Weird",
                "notinteresting",
            ),
        ),
        Flavour(
            "pictures",
            "photos and art people are proud of",
            ("Cinemagraphs", "itookapicture", "Art", "artstore", "pics", "analog", "ExposurePorn", "Illustration"),
            fallback="photo",
        ),
        Flavour("old-photos", "old photos of everyday life", ("TheWayWeWere", "100yearsago", "OldPhotosInRealLife")),
        Flavour("old-people", "old photos of people", ("OldSchoolCool",)),
        Flavour(
            "book-covers", "book covers, real and fake", ("BookCovers", "fakebookcovers", "coverdesign", "bookdesign")
        ),
        Flavour(
            "places",
            "buildings, skies and landscapes",
            ("evilbuildings", "itookapicture", "SkyPorn", "EarthPorn"),
            fallback="photo",
        ),
        # And the moods of weird content (docs/v5-plan.md, 10.3)
        Flavour(
            "cursed",
            "cursed and blursed images: pictures that are wrong somehow",
            ("cursedimages", "blursedimages", "hmmm", "TIHI", "Cursed_Images"),
        ),
        Flavour(
            "wholesome",
            "wholesome memes and animals being friends",
            ("wholesomememes", "MadeMeSmile", "AnimalsBeingBros", "aww", "rarepuppers", "Eyebleach"),
        ),
        Flavour(
            "bad-charts",
            "badly made and funny charts and maps",
            ("funnycharts", "dataisugly", "dataisbeautiful", "charts", "Infographics", "MapsWithoutNZ"),
        ),
        Flavour("medieval", "weird medieval art", ("MedievalMemes", "medievalart")),
        Flavour("liminal", "empty, eerie spaces", ("LiminalSpace", "liminalspaces")),
        Flavour("retro-futurism", "the future as the past saw it", ("RetroFuturism",)),
        Flavour(
            "accidental-art",
            "accidental Renaissance paintings, Wes Anderson scenes and perfect timing",
            ("AccidentalRenaissance", "AccidentalWesAnderson", "accidentalart", "PerfectTiming"),
        ),
        Flavour("pareidolia", "faces in things", ("Pareidolia", "facesinthings")),
        Flavour(
            "corporate-cringe",
            "LinkedIn posts and how-do-you-do-fellow-kids marketing",
            ("LinkedInLunatics", "FellowKids", "CorporateFacepalm"),
        ),
    )
}


def reddit(flavour: str) -> str:
    """The name of a flavour pack's subreddits as a source (see talkgenerator.images.catalog)."""
    return f"reddit:{flavour}"


# The stock sites, as v4's copyright-free slides mixed them (Openverse's openly licensed photos now and then)
_STOCK: Final = (
    SourceUse("unsplash"),
    SourceUse("pixabay"),
    SourceUse("pexels"),
    SourceUse("openverse", 0.1, params={"category": "photograph"}),
)
_RANDOM_PHOTO: Final = (SourceUse("unsplash-random"),)
_WEIRD_WORDS: Final = ("weird", "humor", "funny")
# Openverse's collections of museums, and of archives with old photographs (its sources: api.openverse.org/v1/images/stats/)
_MUSEUMS: Final = "met,clevelandmuseum,rijksmuseum,smk,brooklynmuseum,smithsonian_american_art_museum"
_ARCHIVES: Final = "nypl,finnish_heritage_agency,digitaltmuseum,smithsonian_institution_archives"
_PEOPLE: Final = ("historic person", "person", "man", "woman")
# The museums' filters (see talkgenerator.images.catalog): old photographs, and paintings
_OLD_PHOTOGRAPHS: Final = {"type": "photograph", "before": "1950"}
_PAINTINGS: Final = {"type": "painting"}
_PLAIN: Final[tuple[str, ...]] = ()  # (no words of the look's before a classic search there: a museum's isn't stock)

PROFILES: Final[dict[str, Profile]] = {
    profile.name: profile
    for profile in (
        Profile("photo", "stock photos (and Openverse's openly licensed ones)", _STOCK, last_resort=_RANDOM_PHOTO),
        Profile(
            "neutral",
            "stock photos, and now and then photos and art from Reddit",
            (*_STOCK, SourceUse(reddit("pictures"), 0.93)),
            last_resort=_RANDOM_PHOTO,
        ),
        Profile(
            "weird-stock",
            "stock photos of weird and funny things, and now and then NASA's take on them, or an odd old print",
            (
                *_STOCK,
                SourceUse("nasa", 0.3, modifiers=_PLAIN),
                SourceUse("wellcome", 0.3, modifiers=_PLAIN),
            ),
            modifiers=_WEIRD_WORDS,
            last_resort=_RANDOM_PHOTO,
        ),
        Profile(
            "corporate-stock",
            "office stock photos in blues and teals",
            (
                SourceUse("unsplash", params={"color": "blue"}),
                SourceUse("unsplash", 0.5, params={"color": "teal"}),
                SourceUse("pexels", params={"color": "blue"}),
                SourceUse("pixabay", params={"colors": "blue,turquoise"}),
            ),
            modifiers=("business", "office"),
            prefers=Preferences(colors=("#1f4e79", "#2a6f97", "#2a9d8f", "#e9eef3")),
            looks=4,
            fallback="photo",
        ),
        Profile(
            "calm-backdrop",
            "photos for text over them: little detail where the text goes, and not too light",
            (
                SourceUse("pixabay", 3, params={"orientation": "landscape"}),
                SourceUse("unsplash", params={"orientation": "landscape"}),
                SourceUse("pexels", params={"orientation": "landscape"}),
            ),
            orientation="landscape",
            text_area=MIDDLE,
            prefers=Preferences(detail=0.08, brightness=(0.12, 0.7)),
            looks=6,
            fallback="photo",
            last_resort=_RANDOM_PHOTO,
        ),
        Profile(
            "vintage",
            "old photographs, in black and white or sepia",
            (
                SourceUse(reddit("old-photos"), 3),
                SourceUse("wikimedia", 2, query='{} deepcat:"Black and white photographs"'),
                SourceUse("met", 1, params=_OLD_PHOTOGRAPHS),
                SourceUse("art-institute", 0.7, params=_OLD_PHOTOGRAPHS),
                SourceUse("cleveland", 0.5, params=_OLD_PHOTOGRAPHS),
                SourceUse("openverse", 0.5, params={"category": "photograph", "sources": _ARCHIVES}),
                SourceUse("unsplash", 0.5, query="{} vintage", params={"color": "black_and_white"}),
                SourceUse("pixabay", 0.5, query="{} vintage", params={"colors": "grayscale"}),
            ),
            prefers=Preferences(monochrome=True),
            looks=6,
            treatment="sepia",
            fallback="old-photo",
        ),
        Profile(
            "old-photo",
            "old photographs about anything near the query, in black and white or sepia",
            (
                SourceUse("wikimedia", query="{} historical photograph"),
                SourceUse("met", 0.7, params={"type": "photograph"}),
                SourceUse("unsplash", query="{} old photo", params={"color": "black_and_white"}),
                SourceUse("pixabay", query="{} old photo", params={"colors": "grayscale"}),
            ),
            prefers=Preferences(monochrome=True),
            looks=6,
            treatment="sepia",
        ),
        Profile(
            "old-people",
            "old photos of people, and portraits from museums",
            (
                SourceUse(reddit("old-people"), 3),
                SourceUse("art-institute", query="portrait {}"),
                SourceUse("met", 0.7, query="portrait {}", params=_PAINTINGS),
                SourceUse("cleveland", 0.5, query="portrait {}", params=_PAINTINGS),
            ),
            fallback="portrait",
        ),
        Profile(
            "portrait",
            "portraits: in museums' paintings, and stock photos of people",
            (
                SourceUse("art-institute", query="portrait {}"),
                SourceUse("met", 0.7, query="portrait {}", params=_PAINTINGS, modifiers=_PLAIN),
                SourceUse("cleveland", 0.5, query="portrait {}", params=_PAINTINGS, modifiers=_PLAIN),
                *(use for use in _STOCK[:3]),
            ),
            modifiers=_PEOPLE,
        ),
        Profile(
            "museum",
            "public domain art from museums",
            (
                SourceUse("art-institute", 3),
                SourceUse("met", 3),
                SourceUse("cleveland", 2),
                SourceUse("openverse", 1, params={"sources": _MUSEUMS}),
                SourceUse("wellcome", 0.5),
                SourceUse("wikimedia", 0.7, query='{} deepcat:"Paintings"'),
            ),
        ),
        Profile(
            "space-science",
            "space and science, as NASA and the like photograph it",
            (
                SourceUse("nasa", 4),
                SourceUse("wikimedia", 1, query='{} deepcat:"Images from NASA"'),
                SourceUse("openverse", 2, params={"sources": "nasa,spacex,smithsonian_air_and_space_museum"}),
                SourceUse("unsplash", query="{} space"),
                SourceUse("pixabay", query="{} space"),
            ),
            fallback="photo",
        ),
        Profile(
            "illustration",
            "illustrations and drawings",
            (
                SourceUse("pixabay", 2, params={"image_type": "illustration"}),
                SourceUse("pixabay", params={"image_type": "vector"}),
                SourceUse("openverse", params={"category": "illustration"}),
                SourceUse("openverse", 0.5, params={"sources": "bio_diversity"}),  # (old natural history drawings)
                SourceUse("wellcome", 0.5),  # (old prints and drawings of medicine and science)
            ),
            fallback="photo",
        ),
        Profile(
            "meme-chaos",
            "weird pictures, ShitpostBot's images, gifs and memes",
            (
                SourceUse(reddit("weird"), 10),
                SourceUse("shitpostbot", 8),
                SourceUse(reddit("gifs"), 3),
                SourceUse("giphy", 3),
                SourceUse(reddit("memes"), 1),
            ),
            fallback="weird-stock",
        ),
        Profile(
            "meme-chaos-still",
            "weird pictures, ShitpostBot's images and memes, without gifs",
            (SourceUse(reddit("weird"), 4), SourceUse("shitpostbot", 6), SourceUse(reddit("memes"), 1)),
            fallback="weird-stock",
        ),
        Profile(
            "weird",
            "weird pictures from Reddit, else ShitpostBot's",
            (SourceUse(reddit("weird"), 100), SourceUse("shitpostbot", 3)),
            fallback="weird-stock",
        ),
        Profile(
            "gifs",
            "gifs that move, from Reddit and GIPHY",
            (SourceUse(reddit("gifs")), SourceUse("giphy")),
            animated=True,
        ),
        Profile(
            "inspirobot", "InspiroBot's inspirational posters", (SourceUse("inspirobot"),), breadth=1, needs_query=False
        ),
        # (a meme's template, found by its ID or name: see talkgenerator.sources.memes)
        Profile("meme-templates", "Imgflip's meme templates, captioned live", (SourceUse("imgflip"),), breadth=1),
        Profile(
            "country",
            "where someone comes from: its flag now and then (for a country), else photos of it",
            (SourceUse("flags"), *_STOCK[:3]),
            fallback="neutral",
        ),
    )
}
# The flavour packs, each a look of its own (but where a look above has its name, and more sources)
PROFILES.update(
    {
        name: Profile(
            name,
            flavour.description,
            (SourceUse(reddit(name)),),
            breadth=1,
            animated=flavour.animated,
            fallback=flavour.fallback,
        )
        for name, flavour in FLAVOURS.items()
        if name not in PROFILES
    }
)
DEFAULT: Final = "photo"


def profile(name: str) -> Profile:
    """The look of that name: a ValueError for one there isn't."""
    found = PROFILES.get(name)
    if found is None:
        raise ValueError(f"There's no look {name!r}; there are {', '.join(PROFILES)}")
    return found


def catalog() -> list[dict[str, str]]:
    """The looks, for an agent or a settings menu: name, what it is, and whether it's a flavour pack."""
    return [
        {
            "name": name,
            "description": look.description,
            "kind": "flavour pack" if [use.source for use in look.sources] == [reddit(name)] else "look",
        }
        for name, look in PROFILES.items()
    ]
