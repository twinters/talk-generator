"""Image generators (docs/v5-plan.md, section 10.5): one interface for every provider of generated pictures, a
sibling of the language models' (talkgenerator.llm).

- `base`: the interface (`ImageGenerator`, `ImageRequest`, `GeneratedImage`) and its errors.
- adapters: OpenAI's Image API (`openai_images`), OpenRouter's (`openrouter`), Google's Gemini (`gemini`), Black Forest
  Labs' FLUX (`flux`), and servers on your own computer, ComfyUI and Automatic1111's (`local`).
- `providers`: a generator from a spec ("openai:gpt-image-2"), and the one TALKGENERATOR_IMAGE_GENERATOR names.
- `prices`: the providers' models and list prices, as config (talkgenerator/data/image_generators.json).
- `cache`: generated pictures, kept on disk by what made them.

When a talk generates pictures, and which, is talkgenerator.images.generation's.
"""

from talkgenerator.images.generators.base import (
    ASPECT_RATIOS,
    AspectRatio,
    GeneratedImage,
    GenerationError,
    GenerationRateLimited,
    GenerationRefused,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
    Quality,
)
from talkgenerator.images.generators.providers import from_settings, generator_from_spec, names, register

__all__ = [
    "ASPECT_RATIOS",
    "AspectRatio",
    "GeneratedImage",
    "GenerationError",
    "GenerationRateLimited",
    "GenerationRefused",
    "GeneratorCapabilities",
    "GeneratorUnavailable",
    "ImageGenerator",
    "ImageRequest",
    "Quality",
    "from_settings",
    "generator_from_spec",
    "names",
    "register",
]
