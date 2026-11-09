"""When a talk generates pictures, and which (docs/v5-plan.md, section 10.5).

A talk generates pictures only when it's given an image generator (generate_presentation's image_generator, or
TALKGENERATOR_IMAGE_GENERATOR: see talkgenerator.images.generators), never because a key is set, and only on planned
slides (by a language model, or a plan from the Skill), whose texts and prompts say what a picture is to show. Then:

- For slots stock photos can't show well (`ImageSlot.generate`): the presenter's weird hobby, the cover of the book
  they wrote, an old photo of a moment in the concept's made-up history, the portrait of a made-up historical figure,
  a made-up news story's photo. Such a slot's stock photo is searched for as before, and the slide comes with it; once
  the slide is settled, its picture is generated in the background, and takes the stock photo's place when it comes
  in (a talk that streams hands the slide over again: slide.updated). A refused or failed one keeps the stock photo.
- As a fallback, for a planned slide whose image the search can't find at all (after its query and its concept): on
  the slide's last try, while it's settled, its picture is generated then and there.

A talk generates a few pictures at most (an ImageBudget: 3 by default, TALKGENERATOR_GENERATED_IMAGES), granted in the
order of the slides, so the same seed generates for the same slides, made in parallel or one by one; and for a paid
generator it estimates their cost first (by list price, see talkgenerator.images.generators.prices), keeping to a
dollar limit if it has one. A talk generates nothing when its topic is one a slide shouldn't make light of, nor a
picture whose prompt breaks talkgenerator's rules (see talkgenerator.images.safety), and the generator's moderation
has its say too. The license policy applies: generated pictures are of the `generated` class, credited "AI-generated
with <model>".

Pictures are kept on disk by what made them (see talkgenerator.images.generators.cache): making the talk again, or
rendering its deck again, generates nothing again. A deck names a generated picture by its file there, which a
browser can't load: its display is `copy`, as for Pixabay's pictures, which an app shows from a copy of its own.
"""

from __future__ import annotations

import contextvars
import io
import logging
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent import futures
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from PIL import Image, UnidentifiedImageError

from talkgenerator import settings
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.images import analysis, licenses, profiles, safety
from talkgenerator.images.generators import cache, generator_from_spec
from talkgenerator.images.generators.base import (
    AspectRatio,
    GeneratedImage,
    GenerationError,
    GenerationRefused,
    ImageGenerator,
    ImageRequest,
    Quality,
)
from talkgenerator.models.usage import Usage
from talkgenerator.util import random_util

if TYPE_CHECKING:
    from talkgenerator.images.slots import ImageSlot
    from talkgenerator.llm.ledger import Ledger
    from talkgenerator.slide.slides import Slide

logger = logging.getLogger("talkgenerator")

PURPOSE: Final = "image"  # (a generated picture's purpose in a talk's ledger)
FIRST: Final = "first"  # a slot whose picture is generated in place of its stock photo
FALLBACK: Final = "fallback"  # a slot whose stock photo couldn't be found
_THREADS: Final = 4  # pictures generated at once, per talk
# How a picture looks, by the look of its slot (a look that isn't here: a photograph)
STYLES: Final[dict[str, str]] = {
    "photo": "a realistic photograph",
    "neutral": "a realistic photograph, as in a news story",
    "weird-stock": "a strange, funny stock photograph",
    "corporate-stock": "a corporate stock photograph, in blues and teals",
    "calm-backdrop": "a calm landscape photograph, with little detail in the middle",
    "backdrop": "a striking photograph, with room for a big number over it",
    # (a made-up product, shown off: D63, "amazing weird visualization" of what a startup pitches)
    "product-shot": "a striking advertising photograph of an absurd, imaginative product, lit as a premium product shot",
    "vintage": "an old black and white photograph from an archive, with film grain and faded edges",
    "old-photo": "an old black and white photograph, with film grain",
    "old-people": "an old painted portrait of a made-up person, as in a museum",
    "portrait": "a painted portrait of a made-up person, as in a museum",
    "museum": "an old master's oil painting, as in a museum",
    "space-science": "a space photograph, as NASA takes them",
    "illustration": "a clean illustration",
    "book-covers": "a book cover, with the book's title on it in large letters",
    "meme-chaos": "an absurd, funny photograph, as if it were real",
    "meme-chaos-still": "an absurd, funny photograph, as if it were real",
    "weird": "an absurd, funny photograph, as if it were real",
}
_DEFAULT_STYLE: Final = "a realistic photograph"
_WRITTEN: Final = frozenset({"book-covers"})  # the looks whose pictures have words on them (a book cover's title)
# The shape of a look's pictures, for a slot without an orientation (a look that isn't here: 4:3)
_SHAPES: Final[dict[str, AspectRatio]] = {
    "book-covers": "2:3",
    "old-people": "3:4",
    "portrait": "3:4",
    "calm-backdrop": "16:9",
    "backdrop": "16:9",
}
_ORIENTATIONS: Final[dict[str, AspectRatio]] = {"landscape": "3:2", "portrait": "2:3", "square": "1:1"}
# What the language model writing a talk is told of a prompt it writes for an image generator
PROMPT_DESCRIPTION: Final = (
    "a prompt for an image generator, which draws this picture instead of searching for it: one English sentence of "
    "10 to 40 words saying what the picture shows, concretely (who or what, doing what, where, and how it looks), as "
    "a photographer or painter would describe it; people in it are made up, never real or famous ones, and it has no "
    "logos, brands or trademarked characters"
)


def prompt_field(slot: str) -> str:
    """The field a plan writes a slot's prompt in: image_2_prompt."""
    return f"{slot}_prompt"


@dataclass(frozen=True)
class ImageBudget:
    """How many pictures a talk generates at most (whether the cache has them or not, so the same seed generates for
    the same slides every time), and what they may cost, in dollars by their list prices: None for no limit but their
    number, 0 for free ones only (a local server's)."""

    max_images: int = 3
    max_cost_usd: float | None = None

    @classmethod
    def from_settings(cls) -> ImageBudget:
        """TALKGENERATOR_GENERATED_IMAGES and TALKGENERATOR_IMAGE_COST_LIMIT's."""
        return cls(settings.generated_images(), settings.image_cost_limit())


@dataclass(frozen=True)
class Wish:
    """A picture a slide's slot asks to have generated: the slot (by its name on the slide), why (FIRST: in place of
    its stock photo; FALLBACK: as it has none), what it shows (the subject it was made from), and the request."""

    slot: str
    reason: str
    subject: str
    look: str
    request: ImageRequest


@dataclass(frozen=True)
class Estimate:
    """What a talk's pictures may cost, before any is generated: how many at most, at what list price each (None
    when the price isn't known), and so at most (None, the same)."""

    generator: str
    images: int
    per_image_usd: float | None

    @property
    def total_usd(self) -> float | None:
        return None if self.per_image_usd is None else self.images * self.per_image_usd

    def __str__(self) -> str:
        pictures = f"up to {self.images} picture{'s' if self.images != 1 else ''} with {self.generator}"
        if self.per_image_usd is None:
            return f"{pictures}, at a price talkgenerator doesn't know"
        if self.per_image_usd == 0:
            return f"{pictures}, for nothing"
        return f"{pictures}, at about ${self.per_image_usd:.4f} each: ${self.total_usd:.4f} at most"


def estimate(generator: ImageGenerator | str, budget: ImageBudget | None = None, quality: Quality = "low") -> Estimate:
    """What a talk's pictures may cost with the generator (a spec, or a generator) and budget, by list price: for a
    settings page that asks before a talk spends a visitor's money, say."""
    made = generator_from_spec(generator) if isinstance(generator, str) else generator
    if made is None:
        return Estimate("none", 0, 0.0)
    budget = budget or ImageBudget.from_settings()
    return Estimate(made.id, budget.max_images, made.estimate_cost(ImageRequest(prompt="", quality=quality)))


class ImageGeneration:
    """A talk's generated pictures: its generator, its budget, what it granted, and the pictures being generated.

    `wish` makes a slot's request, `fill` generates the pictures of a slide that has none then and there, `settled`
    starts generating what a settled slide wishes for, and `finish` waits for all of them (`close`, for a talk that
    stopped, waits for none)."""

    def __init__(
        self,
        generator: ImageGenerator,
        budget: ImageBudget | None = None,
        *,
        policy: licenses.LicensePolicy = licenses.ALL,
        ledger: Ledger | None = None,
        topics: Iterable[str] = (),
        presenter: str | None = None,
        quality: Quality | None = None,
    ) -> None:
        self.generator = generator
        self.budget = budget or ImageBudget.from_settings()
        self.policy = policy
        self.ledger = ledger
        self.quality: Quality = quality or _quality(settings.image_quality())
        self.private = tuple(name for name in (presenter,) if name)
        # (a talk whose topic a slide shouldn't make light of generates nothing)
        self.refused = safety.screen_topic(topics)
        if self.refused is not None:
            logger.info("This talk generates no pictures: %s", self.refused)
        self.granted = 0  # pictures granted so far (generated, being generated, or failed)
        self._estimated = 0.0  # what the granted pictures cost at most, by list price
        self._lock = threading.Lock()
        self._swaps = threading.Lock()  # (one swap at a time, and one update for whoever follows the talk)
        self._pool: ThreadPoolExecutor | None = None
        self._jobs: list[Future[None]] = []
        self._closed = False

    def generates(self, slot: ImageSlot | Any) -> bool:
        """Whether the talk may generate the slot's picture: its topic allows it, and its license policy (and the
        slot's own classes) allow generated pictures. (A v4 content generator isn't a slot: never.)"""
        from talkgenerator.images.slots import ImageSlot

        if not isinstance(slot, ImageSlot) or self.refused is not None or self.budget.max_images <= 0:
            return False
        return "generated" in self.policy.narrowed(slot.license_classes).classes

    def prefers(self, slot: ImageSlot | Any) -> bool:
        """Whether the slot's picture is to be generated in place of its stock photo (when the talk may)."""
        return bool(getattr(slot, "generate", False)) and self.generates(slot)

    def fills(self, slot: ImageSlot | Any, look: str) -> bool:
        """Whether a generated picture may stand in for the slot's, when its search finds none: when the talk may
        generate it, and its look (as the talk has it) is a still picture talkgenerator knows how to ask for (a
        photograph, a painting, a book cover, ...), not a gif, a meme or an InspiroBot poster."""
        return look in STYLES and self.generates(slot)

    @property
    def active(self) -> bool:
        """Whether the talk may generate any picture at all (its topic allows it, and its budget allows one)."""
        return self.refused is None and self.budget.max_images > 0

    def wish(
        self,
        slot: ImageSlot,
        name: str,
        reason: str,
        subject: str,
        rng: random_util.Rng,
        written: str | None = None,
        look: str | None = None,
    ) -> Wish | None:
        """The request for the slot's picture: what the plan wrote for it, or else a picture of the subject (its
        query, or the slide's concept) as the slot asks for it, in its look's style, and with a seed from the slide's
        stream. None when the prompt breaks talkgenerator's rules (see talkgenerator.images.safety)."""
        look = look or slot.aesthetic
        prompt = " ".join((written or "").split()) or _described(subject, slot.intent)
        if not prompt:
            return None
        why = safety.screen(prompt, self.private)
        if why is not None:
            logger.info("Not generating a picture for %r: %s", prompt, why)
            return None
        profile = profiles.PROFILES.get(look)
        orientation = slot.orientation or (profile.orientation if profile is not None else None)
        request = ImageRequest(
            prompt=prompt,
            aspect_ratio=_ORIENTATIONS[orientation] if orientation else _SHAPES.get(look, "4:3"),
            style=STYLES.get(look, _DEFAULT_STYLE),
            avoid=safety.avoid(writing=look in _WRITTEN),
            seed=rng.randrange(2**31) if self.generator.capabilities.seed else None,
            quality=self.quality,
        )
        return Wish(name, reason, subject, look, request)

    def fill(self, wishes: Sequence[Wish]) -> list[ImageData] | None:
        """The pictures, generated here and now if the budget grants all of them: for the slots of a slide whose
        search found nothing, on its last try (which runs while it's settled), as the slide needs them all. None if
        they aren't granted, or don't all come."""
        if not self._grant(*wishes):
            return None
        pictures = []
        for wish in wishes:
            picture = self._generate(wish)
            if picture is None:
                return None
            pictures.append(picture)
        return pictures

    def settled(self, slide: Slide, on_update: Callable[[], None] | None = None) -> None:
        """Start generating the pictures the settled slide wishes for, in order, as far as the budget grants them,
        in the background: each takes its stock photo's place on the slide once it's in, and on_update hears of it."""
        for stand_in, wish in slide.wishes:
            if self._grant(wish):
                # (in a copy of this context: checking the picture as the talk checks its images, say)
                run = contextvars.copy_context().run
                job = self._executor().submit(run, self._swap_in, slide, stand_in, wish, on_update)
                with self._lock:
                    self._jobs.append(job)

    def finish(self, cancelled: threading.Event | None = None) -> bool:
        """Wait for every picture being generated, so the deck has them all (a .pptx is made once they're in), or
        until cancelled is set (looked at four times a second): whether they're all in."""
        while True:
            with self._lock:
                jobs = [job for job in self._jobs if not job.done()]
            if not jobs:
                break
            futures.wait(jobs, timeout=0.25)
            if cancelled is not None and cancelled.is_set():
                self.close()
                return False
        with self._lock:
            self._jobs = []
        self._shut_down(wait=True)
        return True

    def close(self) -> None:
        """Stop: what hasn't started generating won't, and what has isn't waited for (a talk nobody wants anymore)."""
        with self._lock:
            self._closed = True
            jobs, self._jobs = self._jobs, []
        for job in jobs:
            job.cancel()
        self._shut_down(wait=False)

    def estimate(self) -> Estimate:
        return Estimate(
            self.generator.id,
            self.budget.max_images,
            self.generator.estimate_cost(ImageRequest(prompt="", quality=self.quality)),
        )

    # GRANTING AND GENERATING

    def _grant(self, *wishes: Wish) -> bool:
        """Whether the budget allows the pictures, all of them (counting them, if it does): no more than its most
        pictures, and within its dollars by list price (whether the cache has the pictures or not, so the same seed
        grants the same)."""
        costs = [self.generator.estimate_cost(wish.request) for wish in wishes]
        slots = ", ".join(wish.slot for wish in wishes)
        with self._lock:
            if self._closed or self.granted + len(wishes) > self.budget.max_images:
                return False
            limit = self.budget.max_cost_usd
            if limit is not None:
                if any(cost is None for cost in costs):
                    logger.info("Not generating the picture for %s: its price isn't known", slots)
                    return False
                if self._estimated + sum(cost or 0.0 for cost in costs) > limit + 1e-9:
                    logger.info("Not generating the picture for %s: it would take the talk over $%.4f", slots, limit)
                    return False
            first = self.granted == 0
            self.granted += len(wishes)
            self._estimated += sum(cost or 0.0 for cost in costs)
        if first:
            logger.info("Generating %s", self.estimate())
        return True

    def _swap_in(self, slide: Slide, stand_in: ImageData, wish: Wish, on_update: Callable[[], None] | None) -> None:
        generated = self._generate(wish, stand_in)
        if generated is None:
            return
        with self._swaps:
            with self._lock:
                if self._closed:
                    return
            slide.replace_image(stand_in, generated)
            if on_update is not None:
                try:
                    on_update()
                except Exception:  # (whoever follows the talk stopped following it, say: the picture stays)
                    logger.debug("Couldn't hand over the slide with its generated picture", exc_info=True)

    def _generate(self, wish: Wish, stand_in: ImageData | None = None) -> ImageData | None:
        """The picture for the wish: from the cache, or else generated (and kept there). None if it doesn't come."""
        generator, request = self.generator, wish.request
        key = cache.key(generator.id, request, generator.capabilities.seed)
        kept = cache.get(key)
        if kept is not None:
            path, image = kept
            logger.info("A generated picture for %s comes from the cache: %s", wish.slot, path.name)
        else:
            start = time.monotonic()
            try:
                image = generator.generate(request)
            except GenerationRefused as refused:
                logger.info("The picture for %s was turned down (%s): it keeps its stock photo", wish.slot, refused)
                self._account(Usage(failed_images=1), time.monotonic() - start, str(refused))
                return None
            except GenerationError as error:
                logger.warning(
                    "The picture for %s couldn't be generated (%s): it keeps its stock photo", wish.slot, error
                )
                self._account(Usage(failed_images=1), time.monotonic() - start, str(error))
                return None
            except Exception as error:  # a misbehaving generator shouldn't sink the talk
                logger.exception("Generating the picture for %s crashed", wish.slot)
                self._account(Usage(failed_images=1), time.monotonic() - start, repr(error))
                return None
            cost = image.cost_usd if image.cost_usd is not None else generator.estimate_cost(request)
            self._account(
                Usage(images=1, image_cost_usd=cost or 0.0, unpriced_images=1 if cost is None else 0),
                time.monotonic() - start,
            )
            try:
                path = cache.put(key, image, request)
            except OSError as error:
                logger.warning("Can't keep the generated picture for %s (%s)", wish.slot, error)
                return None
        return self._image_data(path, image, wish, stand_in)

    def _image_data(self, path: Any, image: GeneratedImage, wish: Wish, stand_in: ImageData | None) -> ImageData:
        credit = f"AI-generated with {_model_name(image.model or self.generator.id)}"
        terms = self.generator.terms
        picture = ImageData(
            image_url=str(path),
            source=credit,
            credit=((credit, None),),
            description=wish.request.prompt,
            display="copy",
            license_class="generated",
            license=terms[0] if terms else None,
            license_url=terms[1] if terms else None,
            declared_size=_size(image.data),
        )
        picture.query = stand_in.query if stand_in is not None and stand_in.query else wish.subject
        picture.look = wish.look
        picture.analysis = analysis.analyse(image.data, _area(wish.look))
        # (checked already: it's a picture, of its own size, which a probe of the file couldn't tell any better)
        picture.size = picture.declared_size
        picture.usable = picture.size is not None
        return picture

    def _account(self, usage: Usage, seconds: float, error: str | None = None) -> None:
        if self.ledger is None:
            return
        from talkgenerator.llm.ledger import LedgerEntry

        self.ledger.add(LedgerEntry(self.generator.id, PURPOSE, usage, seconds, error=error))

    def _executor(self) -> ThreadPoolExecutor:
        with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=_THREADS, thread_name_prefix="image generation")
            return self._pool

    def _shut_down(self, wait: bool) -> None:
        with self._lock:
            pool, self._pool = self._pool, None
        if pool is not None:
            pool.shutdown(wait=wait, cancel_futures=not wait)


def _quality(value: str) -> Quality:
    return "medium" if value == "medium" else "high" if value == "high" else "low"


def _described(subject: str, intent: str) -> str:
    """A prompt for a picture of the subject, as the slot asks for it ("the presenter's weird hobby: cheese rolling")."""
    subject = " ".join(subject.split())
    intent = " ".join(intent.split())
    if not subject:
        return intent
    return f"{intent}: {subject}" if intent else subject


def _model_name(model: str) -> str:
    return model.split(":", 1)[1] if ":" in model else model


def _area(look: str) -> analysis.Area | None:
    profile = profiles.PROFILES.get(look)
    return profile.text_area if profile is not None else None


def _size(data: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(io.BytesIO(data)) as picture:
            return int(picture.width), int(picture.height)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


def for_talk(
    image_generator: ImageGenerator | str | None,
    budget: ImageBudget | None,
    policy: licenses.LicensePolicy,
    ledger: Ledger | None,
    topics: Iterable[str],
    presenter: str | None,
) -> ImageGeneration | None:
    """The talk's image generation: with the generator it's given (a spec, or a generator), or else the one
    TALKGENERATOR_IMAGE_GENERATOR names; None without one (or when the license policy allows no generated pictures,
    or DISABLE_IMAGE_GENERATION is on, or the budget allows none)."""
    if settings.is_source_disabled("IMAGE_GENERATION"):
        return None
    generator = (
        generator_from_spec(image_generator)
        if isinstance(image_generator, str)
        else image_generator
        if image_generator is not None
        else generator_from_spec(settings.image_generator_spec())
    )
    budget = budget or ImageBudget.from_settings()
    if generator is None or budget.max_images <= 0 or "generated" not in policy.classes:
        return None
    return ImageGeneration(generator, budget, policy=policy, ledger=ledger, topics=topics, presenter=presenter)
