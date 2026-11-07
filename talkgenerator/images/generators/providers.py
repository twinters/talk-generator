"""Choosing an image generator from a spec: the provider's name, and after a colon its model (the provider's default
model without one, as talkgenerator/data/image_generators.json names it):

- "openai" (gpt-image-2), or "openai:<model>": OpenAI's Image API, with OPENAI_API_KEY
- "openrouter" (OpenAI's gpt-image-2 there), or "openrouter:<model>", such as
  "openrouter:black-forest-labs/flux-3-image-klein": with OPENROUTER_API_KEY (or talkgenerator login openrouter)
- "gemini" (gemini-3.1-flash-lite-image), or "gemini:<model>": the Gemini API, with GEMINI_API_KEY
- "flux" (FLUX 3 Image Klein), or "flux:<model>", such as "flux:flux-2-pro": Black Forest Labs' API, with BFL_API_KEY
- "comfyui" or "comfyui:<checkpoint>": a ComfyUI server of your own (COMFYUI_URL), for nothing
- "automatic1111" or "automatic1111:<checkpoint>": an Automatic1111-style server of your own (AUTOMATIC1111_URL)
- "none": no generated pictures (the default)

TALKGENERATOR_IMAGE_GENERATOR sets the spec, and DISABLE_IMAGE_GENERATION=1 makes it "none". A talk only generates
pictures when it's asked to: a key alone never makes it (as a key alone never makes a paid language model write a
talk), so that talkgenerator.com, whose server has keys, never generates on its own budget (decision D7).
"""

from __future__ import annotations

from collections.abc import Callable

from talkgenerator import settings
from talkgenerator.images.generators.base import ImageGenerator
from talkgenerator.images.generators.flux import FluxImageGenerator
from talkgenerator.images.generators.gemini import GeminiImageGenerator
from talkgenerator.images.generators.local import Automatic1111Generator, ComfyUIGenerator
from talkgenerator.images.generators.openai_images import OpenAIImageGenerator
from talkgenerator.images.generators.openrouter import OpenRouterImageGenerator

NONE = "none"

# A provider's name -> a function that makes its generator from what follows the name in the spec (its model)
GeneratorFactory = Callable[[str], ImageGenerator]

_FACTORIES: dict[str, GeneratorFactory] = {
    "openai": lambda model: OpenAIImageGenerator(model),
    "openrouter": lambda model: OpenRouterImageGenerator(model),
    "gemini": lambda model: GeminiImageGenerator(model),
    "flux": lambda model: FluxImageGenerator(model),
    "comfyui": lambda model: ComfyUIGenerator(model),
    "automatic1111": lambda model: Automatic1111Generator(model),
}


def register(name: str, factory: GeneratorFactory) -> None:
    if name in _FACTORIES or name == NONE:
        raise ValueError(f"There already is an image generator called {name!r}")
    _FACTORIES[name] = factory


def names() -> list[str]:
    return [*_FACTORIES, NONE]


def generator_from_spec(spec: str | None) -> ImageGenerator | None:
    """The generator a spec stands for (None for "none", or no spec): its provider, and after a colon its model.
    A ValueError for a provider there isn't."""
    name, _, model = (spec or NONE).strip().partition(":")
    if name in ("", NONE):
        return None
    factory = _FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"There's no image generator {name!r} in {spec!r}; there are {', '.join(names())}")
    return factory(model.strip())


def from_settings() -> ImageGenerator | None:
    """The generator TALKGENERATOR_IMAGE_GENERATOR asks for (and DISABLE_IMAGE_GENERATION allows), if any."""
    return generator_from_spec(settings.image_generator_spec())
