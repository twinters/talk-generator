"""The image finder: the image for a slot (docs/v5-plan.md, section 10.1).

1. Which sources, in which order: those of the slot's look that the talk's license policy allows, by weight and
   without putting one back (as v4 picked a source by weight, and another one when it found nothing), and of those,
   the ones that can be searched (their keys). One that's skipped for a while (see http_util.Cooldown) stays, and
   finds only what it found before, from its caches.
2. Search them a few at a time (the look's breadth), in parallel, with v4's caches of answers and its cooldowns.
3. Filter the candidates: their license (one by one, for sources whose images each have their own), their size and
   orientation (as the sources tell them), what they're described as (nothing unsafe), the same image found twice,
   and the images the slide has already.
4. Score them: for a look that prefers something (black and white, little detail where the text goes, ...), and in
   a themed talk for colours that go with its theme, a few get a look at their thumbnails
   (talkgenerator.images.analysis). A look without preferences picks among the first source's candidates at random,
   as v4 did.
5. Check the winner as before (see talkgenerator.util.image_util.check_image): probed while a talk streams, else
   downloaded. And another one, if it won't do.

Every choice draws from the talk's random generator (see talkgenerator.util.random_util): the same seed finds the
same images, whatever order the searches come back in, in parallel or not. A look whose sources can't or don't find
anything hands over to its fallback, and then to the slot's backups.

The picked image notes its look and what the look at its thumbnail found (ImageData.look and .analysis), which the
deck keeps, and the checks read (talkgenerator.checks.deck).
"""

from __future__ import annotations

import contextvars
import copy
import functools
import logging
import re
import threading
from collections.abc import Callable, Collection, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Final, TypeVar

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import analysis, catalog, context, licenses, profiles
from talkgenerator.images.analysis import Area
from talkgenerator.images.profiles import Preferences, Profile, SourceUse
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import ImageAnalysis
from talkgenerator.util import generator_util, image_util, random_util

logger = logging.getLogger("talkgenerator")

MAX_TRIES: Final = 8  # candidates checked (downloaded or probed) for one look's sources, at most, as v4 did
PALETTE_LOOKS: Final = 3  # candidates looked at in a themed talk, for colours that go with the theme
# What a candidate's description may not say (beside the sources' own filters, such as Reddit's NSFW mark)
_UNSAFE: Final = re.compile(r"\b(?:nsfw|nude|nudity|porn|porno|gore|hentai)\b", re.IGNORECASE)
_THREADS: Final = 16
_pool: ThreadPoolExecutor | None = None
_pool_lock = threading.Lock()

_T = TypeVar("_T")


@dataclass
class _Candidate:
    image: ImageData
    use: SourceUse
    weight: float  # its share of its source's weight (by its rating, for ShitpostBot)
    look: ImageAnalysis | None = None
    looked: bool = False


def find(slot: ImageSlot, query: str | None, avoid: Collection[ImageData] = ()) -> ImageData | None:
    """The image for the slot, searched with the query (through the slot's own queries, if it has some): None if its
    look, the look's fallbacks and the slot's backups find none that will do."""
    talk = context.current()
    queries = [template.replace("{}", query or "").strip() for template in slot.queries] or [query or ""]
    tried: set[str] = set()
    for first in (slot.aesthetic, *slot.backups):
        name: str | None = talk.look(first)
        while name is not None and name not in tried:
            tried.add(name)
            look = profiles.profile(name)
            for asked in queries:
                found = _find_with(look, slot, asked, avoid, talk)
                if found is not None:
                    return found
            name = talk.look(look.fallback) if look.fallback else None
    return None


def servable(slot: ImageSlot, policy: licenses.LicensePolicy) -> bool:
    """Whether the policy allows the sources of the slot's look, its fallbacks or its backups (whatever their keys),
    or a generated picture, for a slot that prefers one in a talk that generates them (see
    talkgenerator.images.generation)."""
    allowed = policy.narrowed(slot.license_classes)
    talk = context.current()
    if talk.generation is not None and talk.generation.prefers(slot):
        return True
    tried: set[str] = set()
    for first in (slot.aesthetic, *slot.backups):
        name: str | None = talk.look(first)
        while name is not None and name not in tried:
            tried.add(name)
            look = profiles.profile(name)
            if any(_allows(allowed, use, slot) for use in look.sources):
                return True
            name = talk.look(look.fallback) if look.fallback else None
    return False


def _allows(policy: licenses.LicensePolicy, use: SourceUse, slot: ImageSlot) -> bool:
    source = catalog.source(use.source)
    return (not slot.sources or use.source in slot.sources) and bool(source.classes & policy.classes)


def _find_with(
    look: Profile, slot: ImageSlot, query: str, avoid: Collection[ImageData], talk: context.ImageContext
) -> ImageData | None:
    policy = talk.policy.narrowed(slot.license_classes)
    if look.needs_query and not query.strip():
        return None
    planned = generator_util.planned()
    # (Drawn among every source the policy allows, then without those that can't be searched: the same order of the
    # others either way. A source that's cooling down keeps its place, so its cooldown changes neither the batches nor
    # what it found before, only what it would have found now)
    order = [use for use in _order([use for use in look.sources if _allows(policy, use, slot)]) if _available(use)]
    # A classic search gets one of the look's words before its query, as v4's did (a plan's goes as written)
    word = random_util.choice(look.modifiers) if look.modifiers and not planned else None
    batches = [order[start : start + max(1, look.breadth)] for start in range(0, len(order), max(1, look.breadth))]
    if not planned and look.last_resort:
        batches.append([use for use in look.last_resort if _allows(policy, use, slot)])
    for batch in batches:
        if not batch:
            continue
        searches = [_search_query(use, query, word, planned) for use in batch]
        found = _search(batch, searches, slot, look, policy)
        candidates = _candidates(batch, found, slot, look, policy, planned)
        picked = _pick(candidates, slot, look, talk, avoid)
        if picked is not None:
            return picked
    return None


def _available(use: SourceUse) -> bool:
    return catalog.source(use.source).available()


def _order(uses: list[SourceUse]) -> list[SourceUse]:
    """The sources in the order they're searched in: by weight, without putting one back."""
    remaining = list(uses)
    order: list[SourceUse] = []
    while remaining:
        chosen = random_util.weighted_random([(use.weight, use) for use in remaining]) or remaining[0]
        order.append(chosen)
        remaining.remove(chosen)
    return order


def _search_query(use: SourceUse, query: str, word: str | None, planned: bool) -> str:
    """The query as it reads at the source: with a word of its own or the look's (in a classic search), put in the
    source's way of searching for the look."""
    modifiers = use.modifiers
    if modifiers and not planned:
        word = random_util.choice(modifiers)
    elif modifiers is not None:
        word = None
    asked = f"{word} {query}" if word and query else query
    return use.query.replace("{}", asked).strip()


def _search(
    batch: Sequence[SourceUse],
    queries: Sequence[str],
    slot: ImageSlot,
    look: Profile,
    policy: licenses.LicensePolicy,
) -> list[catalog.Found]:
    """What every source of the batch found, in the batch's order: searched at the same time, each in a thread of its
    own with a random stream of its own (from one number of the talk's: the same, whatever thread runs first)."""
    seed = random_util.randrange(2**32)
    orientation = slot.orientation or look.orientation

    def search(index: int) -> catalog.Found:
        use = batch[index]
        source = catalog.source(use.source)
        with random_util.use(random_util.Rng(seed).child("source", index, use.source)):
            try:
                return source.search(catalog.Search(queries[index], use.params, orientation, policy.classes))
            except Exception:  # one misbehaving source shouldn't sink the slide
                logger.exception("Searching %s for %r crashed", use.source, queries[index])
                return []

    return _all([functools.partial(search, index) for index in range(len(batch))])


def _candidates(
    batch: Sequence[SourceUse],
    found: Sequence[catalog.Found],
    slot: ImageSlot,
    look: Profile,
    policy: licenses.LicensePolicy,
    planned: bool,
) -> list[_Candidate]:
    """The candidates that may go on the slide, by source, in the order the sources found them: each source's best
    few for a plan, as v4 picked among them."""
    orientation = slot.orientation or look.orientation
    seen: set[str] = set()
    candidates: list[_Candidate] = []
    for use, results in zip(batch, found, strict=True):
        source = catalog.source(use.source)
        kept: list[tuple[float, ImageData]] = []
        for rating, image in results:
            url = image.get_image_url()
            if url in seen or rating <= 0:
                continue
            seen.add(url)
            if image.license_class is None and len(source.classes) == 1:
                image.license_class = next(iter(source.classes))
            if not policy.allows(image.license_class) or image.license_class is None:
                continue
            if not _fits(image.declared_size, orientation, slot.min_pixels):
                continue
            if image.description and _UNSAFE.search(image.description):
                continue
            kept.append((rating, image))
        if planned:
            kept = kept[: generator_util.TOP_RESULTS]
        total = sum(rating for rating, _ in kept)
        candidates += [_Candidate(image, use, use.weight * rating / total) for rating, image in kept]
    return candidates


def _fits(size: tuple[int, int] | None, orientation: str | None, min_pixels: int) -> bool:
    """Whether an image of the size (as its source says it, if it does) has the orientation and the pixels asked for."""
    if size is None:
        return True
    width, height = size
    if min_pixels and width * height < min_pixels:
        return False
    if orientation == "landscape":
        return width >= 1.1 * height
    if orientation == "portrait":
        return height >= 1.1 * width
    if orientation == "square":
        return max(width, height) <= 1.25 * min(width, height)
    return True


def _pick(
    candidates: list[_Candidate],
    slot: ImageSlot,
    look: Profile,
    talk: context.ImageContext,
    avoid: Collection[ImageData],
) -> ImageData | None:
    """The candidate that wins, once it passes its check (or the next one), with what a look at it found."""
    area = slot.text_area or look.text_area
    looks = look.looks or (PALETTE_LOOKS if talk.palette else 0)
    remaining = list(candidates)
    for _ in range(MAX_TRIES):
        if not remaining:
            return None
        if looks:
            sample = _sample(remaining, looks)
            _look_at([candidate for candidate in sample if not candidate.looked], area)
            prefers = look.prefers
            if prefers is not None and not any(prefers.met_by(candidate.look) for candidate in sample):
                # None of them has the look: a few more get a look, once (they cost a thumbnail each)
                sample = _sample(remaining, 2 * looks)
                _look_at([candidate for candidate in sample if not candidate.looked], area)
            chosen = _best(sample, look.prefers, talk.palette)
        else:  # (as v4: a source by weight, the first in the order that found any, and one of its images at random)
            first = [candidate for candidate in remaining if candidate.use is remaining[0].use]
            chosen = random_util.weighted_random([(candidate.weight, candidate) for candidate in first]) or first[0]
        remaining.remove(chosen)
        if any(chosen.image == other for other in avoid):
            continue
        if not chosen.looked:
            _look_at([chosen], area)
        if any(analysis.near_duplicates(chosen.look, other.analysis) for other in avoid):
            continue
        if not image_util.check_image(chosen.image):
            continue
        found = copy.copy(chosen.image)  # (a source may hand out the same object again: this one is the slide's)
        found.look, found.analysis = look.name, chosen.look
        return found
    return None


def _sample(candidates: list[_Candidate], size: int) -> list[_Candidate]:
    """Up to size candidates, drawn by weight (so a source counts as much as its weight), without putting one back:
    the ones looked at already first, as they cost nothing."""
    looked = [candidate for candidate in candidates if candidate.looked][:size]
    remaining = [candidate for candidate in candidates if not candidate.looked]
    sample = list(looked)
    while remaining and len(sample) < size:
        chosen = random_util.weighted_random([(candidate.weight, candidate) for candidate in remaining]) or remaining[0]
        sample.append(chosen)
        remaining.remove(chosen)
    return sample


def _look_at(candidates: Sequence[_Candidate], area: Area | None) -> None:
    """Take a look at the candidates' thumbnails, all at once."""
    if not candidates:
        return
    looks = _all([functools.partial(_thumbnail_look, candidate.image, area) for candidate in candidates])
    for candidate, found in zip(candidates, looks, strict=True):
        candidate.look, candidate.looked = found, True


def _thumbnail_look(image: ImageData, area: Area | None) -> ImageAnalysis | None:
    return analysis.look_at(image.thumbnail_url, area) if image.thumbnail_url else None


def _best(sample: list[_Candidate], prefers: Preferences | None, palette: Sequence[str]) -> _Candidate:
    """The candidate of the sample to try: one with the look, by weight (and by how well it goes with the theme's
    colours), or else the one closest to it."""
    having = [candidate for candidate in sample if prefers is None or prefers.met_by(candidate.look)]
    if having:
        weighted = [
            (candidate.weight * (0.5 + _colors_fit(candidate, prefers, palette)), candidate) for candidate in having
        ]
        return random_util.weighted_random(weighted) or having[0]
    assert prefers is not None
    return max(sample, key=lambda candidate: prefers.closeness(candidate.look))


def _colors_fit(candidate: _Candidate, prefers: Preferences | None, palette: Sequence[str]) -> float:
    """How well a candidate's colours go with the look's and the theme's (0 to 1)."""
    if candidate.look is None:
        return 0.0
    score = 0.0
    if prefers is not None and prefers.colors:
        score = analysis.palette_fit(candidate.look, prefers.colors)
    if palette:
        weight = prefers.palette if prefers is not None else profiles.PALETTE
        score = max(score, weight / profiles.PALETTE * analysis.palette_fit(candidate.look, palette))
    return min(1.0, score)


# RUNNING THINGS AT ONCE


def _executor() -> ThreadPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=_THREADS, thread_name_prefix="image finder")
        return _pool


def _all(tasks: Sequence[Callable[[], _T]]) -> list[_T]:
    """What the tasks give, in their order: run at once, in the finder's threads (each in a copy of this context, so
    images are checked and found as here). One task runs here, without a thread."""
    if len(tasks) <= 1:
        return [task() for task in tasks]
    futures = [_executor().submit(contextvars.copy_context().run, task) for task in tasks]
    return [future.result() for future in futures]
