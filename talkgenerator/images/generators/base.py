"""The interface every image generator offers (docs/v5-plan.md, section 10.5), a sibling of the language models' (see
talkgenerator.llm.base).

A request says what the picture shows (its prompt), its shape (an aspect ratio), its style, what it's to leave out,
and a seed, for the generators that take one (the same seed and prompt: the same picture). An answer is the picture's
bytes, with the model that made it, what it cost (as the provider says, if it does) and what moderation said of it.
Whatever goes wrong raises a GenerationError, and the talk then keeps the stock photo it had: a talk never fails for
it, and a prompt that's turned down (GenerationRefused) gets a stock photo too.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Final, Literal, get_args

from talkgenerator.models.base import Data

# The shapes a picture can be asked in: square, landscape (3:2, 4:3, 16:9) and portrait (2:3, 3:4, 9:16). A generator
# makes the nearest shape it can.
AspectRatio = Literal["1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16"]
ASPECT_RATIOS: Final[tuple[AspectRatio, ...]] = get_args(AspectRatio)
# How much care (and money) goes into a picture, for the generators that ask: low is plenty for a slide shown for a few
# seconds, and costs the least (OpenAI's gpt-image-2: $0.006 a picture at low, $0.053 at medium)
Quality = Literal["low", "medium", "high"]


class ImageRequest(Data):
    prompt: str  # what the picture shows, as one or two English sentences
    aspect_ratio: AspectRatio = "1:1"
    style: str = ""  # how it looks, such as "an old black and white photograph" (the generators put it in the prompt)
    # What the picture mustn't have (our own rules: no real people, logos, ...): written into the prompt for models that
    # follow instructions, and as a negative prompt for local servers. Diffusion models that read the prompt as a list
    # of things to draw (FLUX) don't get it: they'd draw what it names.
    avoid: str = ""
    seed: int | None = None  # for the generators that take one
    quality: Quality = "low"

    def text(self, with_avoid: bool = True) -> str:
        """The prompt as one text, with its style and (if asked) what to avoid."""
        parts = [self.prompt.strip().rstrip(".") + "."]
        if self.style.strip():
            parts.append(f"Style: {self.style.strip().rstrip('.')}.")
        if with_avoid and self.avoid.strip():
            parts.append(f"Avoid: {self.avoid.strip().rstrip('.')}.")
        return " ".join(parts)

    def shape(self) -> tuple[int, int]:
        """The aspect ratio as numbers (width, height): 3:2 is (3, 2)."""
        width, height = self.aspect_ratio.split(":")
        return int(width), int(height)


@dataclass(frozen=True)
class GeneratedImage:
    """A picture a generator made: its bytes and their type, the model that made it ("provider:model"), what it cost in
    dollars (as the provider says, or None), what moderation said of it (flags such as "revised prompt"), the seed it
    was made with (if the generator takes one), and the prompt as the model rewrote it (some do)."""

    data: bytes
    media_type: str
    model: str
    cost_usd: float | None = None
    flags: tuple[str, ...] = ()
    seed: int | None = None
    revised_prompt: str | None = None


@dataclass(frozen=True)
class GeneratorCapabilities:
    """seed: it takes a seed (the same seed and prompt give the same picture); instructions: it follows instructions
    in its prompt (what to avoid), as models with a language model inside do (OpenAI's, Gemini's), where diffusion
    models draw whatever the prompt names; local: it runs on the user's own computer, for nothing."""

    seed: bool = False
    instructions: bool = True
    local: bool = False
    aspect_ratios: tuple[AspectRatio, ...] = field(default=ASPECT_RATIOS)


class GenerationError(Exception):
    """No picture: the talk keeps the stock photo it had (or makes the slide another way)."""


class GeneratorUnavailable(GenerationError):
    """The generator can't be used: no key, a key it turns down, no credits, a model it doesn't know, or a server
    that's down."""


class GenerationRefused(GenerationError):
    """The prompt (or the picture) was turned down: by the provider's moderation, or by talkgenerator's own rules (see
    talkgenerator.images.safety). flags say what said so."""

    def __init__(self, message: str, flags: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.flags = flags


class GenerationRateLimited(GeneratorUnavailable):
    """The provider's rate limit ran out for now."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ImageGenerator(ABC):
    """An image generator, as talkgenerator uses it."""

    id: str  # "provider:model", such as "openai:gpt-image-2"
    capabilities: GeneratorCapabilities = GeneratorCapabilities()
    # The provider's terms, which generally give the user the pictures (a generated picture's license, in its deck)
    terms: tuple[str, str] | None = None

    @abstractmethod
    def generate(self, request: ImageRequest) -> GeneratedImage:
        """The picture. Raises a GenerationError when there's none."""

    def estimate_cost(self, request: ImageRequest) -> float | None:
        """What a picture would cost in dollars, by the model's list price (see talkgenerator.images.generators.prices),
        or None if that isn't known. A local generator's cost nothing."""
        from talkgenerator.images.generators import prices

        return 0.0 if self.capabilities.local else prices.price_of(self.id, request.quality)

    @property
    def model(self) -> str:
        """The model's name, without the provider's: "gpt-image-2", say (for a generated picture's credit)."""
        return self.id.split(":", 1)[1] if ":" in self.id else self.id

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.id!r})"
