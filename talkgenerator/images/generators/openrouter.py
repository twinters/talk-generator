"""OpenRouter's image models (OpenAI's gpt-image-2 by default), through its Image API, on the key that writes talks
too (OPENROUTER_API_KEY, or talkgenerator login openrouter): many providers' models behind one key, none of them free.

Checked on 2026-11-07 (openrouter.ai/docs/features/multimodal/images): POST /api/v1/images takes a model, a prompt, an
aspect ratio, a resolution (1K, ...), a quality (OpenAI's models), an output format and a seed (where the model takes
one), and answers with the pictures in base64 (data[].b64_json, media_type) and what they cost (usage.cost). A failed
generation isn't billed. Which parameters a model takes, and its price per picture (for models priced by the picture),
come from GET /api/v1/images/models/<model>/endpoints, which talkgenerator asks once per model, when it's first used.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.images.generators import prices, web
from talkgenerator.images.generators.base import (
    GeneratedImage,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
)
from talkgenerator.llm.openrouter import APP_HEADERS

API_URL: Final = "https://openrouter.ai/api/v1/images"
MODELS_URL: Final = "https://openrouter.ai/api/v1/images/models"
PROVIDER: Final = "openrouter"
RESOLUTION: Final = "1K"
# The model families that follow instructions in their prompts (what to leave out), as language models do
_INSTRUCTED: Final = ("openai/", "google/")

logger = logging.getLogger("talkgenerator")


@dataclass(frozen=True)
class Endpoint:
    """What OpenRouter says of a model: the parameters it takes, and its price per picture by resolution ("1k"), for
    a model priced by the picture."""

    parameters: frozenset[str] = frozenset()
    price_per_image: dict[str, float] = field(default_factory=dict)


_endpoints: dict[str, Endpoint] = {}
_endpoints_lock = threading.Lock()


class OpenRouterImageGenerator(ImageGenerator):
    def __init__(self, model: str = "", *, api_key: str | None = None, client: web.Client | None = None) -> None:
        self.id = f"{PROVIDER}:{model.strip() or prices.default_model(PROVIDER)}"
        self.terms = prices.terms(PROVIDER)
        self._key = api_key
        self._client = client or web.WEB

    @property  # (asked of OpenRouter when it's first needed, not when the generator is made)
    def capabilities(self) -> GeneratorCapabilities:  # type: ignore[override]
        return GeneratorCapabilities(seed="seed" in self.endpoint().parameters, instructions=_instructed(self.model))

    def generate(self, request: ImageRequest) -> GeneratedImage:
        key = self._key if self._key is not None else settings.openrouter_api_key()
        if not key:
            raise GeneratorUnavailable(
                "OpenRouter's image models need a key: sign in with `talkgenerator login openrouter`, or set "
                "OPENROUTER_API_KEY"
            )
        arguments = self.arguments(request)
        response = self._client.post(
            API_URL,
            json=arguments,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", **APP_HEADERS},
            timeout=web.TIMEOUT_SECONDS,
        )
        data = web.answer(response, "OpenRouter")
        pictures = data.get("data") if isinstance(data, dict) else None
        if not pictures or not isinstance(pictures[0], dict):
            raise GeneratorUnavailable("OpenRouter answered without a picture")
        image = web.decoded(pictures[0].get("b64_json"), "OpenRouter")
        cost = (data.get("usage") or {}).get("cost")
        return GeneratedImage(
            data=image,
            media_type=web.media_type(image, pictures[0].get("media_type")),
            model=self.id,
            cost_usd=float(cost) if isinstance(cost, int | float) else None,
            seed=arguments.get("seed"),
        )

    def arguments(self, request: ImageRequest) -> dict[str, Any]:
        """The request, as OpenRouter's Image API takes it: its prompt, its aspect ratio and one picture, and of the
        rest what the model takes."""
        parameters = self.endpoint().parameters
        arguments: dict[str, Any] = {
            "model": self.model,
            "prompt": request.text(with_avoid=_instructed(self.model)),
            "n": 1,
            "aspect_ratio": request.aspect_ratio,
        }
        if "resolution" in parameters:
            arguments["resolution"] = RESOLUTION
        if "quality" in parameters or (not parameters and self.model.startswith("openai/")):
            arguments["quality"] = request.quality
        if "output_format" in parameters:
            arguments["output_format"] = "jpeg"
        if request.seed is not None and "seed" in parameters:
            arguments["seed"] = request.seed
        return arguments

    def estimate_cost(self, request: ImageRequest) -> float | None:
        """The list price (see talkgenerator.images.generators.prices), or else the price per picture OpenRouter says
        the model has (none for models priced by the token, whose pictures can't be priced beforehand)."""
        listed = prices.price_of(self.id, request.quality)
        if listed is not None:
            return listed
        per_image = self.endpoint().price_per_image
        if not per_image:
            return None
        return per_image.get(RESOLUTION.lower(), max(per_image.values()))

    def endpoint(self) -> Endpoint:
        """What OpenRouter says of the model (asked once, and remembered)."""
        with _endpoints_lock:
            known = _endpoints.get(self.model)
        if known is not None:
            return known
        found = _ask(self.model, self._client)
        with _endpoints_lock:
            _endpoints.setdefault(self.model, found)
            return _endpoints[self.model]


def _instructed(model: str) -> bool:
    return model.startswith(_INSTRUCTED)


def _ask(model: str, client: web.Client) -> Endpoint:
    """What OpenRouter says of a model: its parameters, and its prices per picture. Nothing, if it doesn't say (the
    request then has only the parameters every model takes)."""
    response = client.get(f"{MODELS_URL}/{model}/endpoints", headers={}, timeout=15)
    try:
        data = response.json() if response is not None and response.ok else None
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    endpoints = data.get("endpoints") if isinstance(data, dict) else None
    if not isinstance(endpoints, list) or not endpoints:
        logger.info("OpenRouter doesn't say which parameters %s takes", model)
        return Endpoint()
    parameters: set[str] = set()
    per_image: dict[str, float] = {}
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        supported = endpoint.get("supported_parameters")
        if isinstance(supported, dict):
            parameters |= {str(name) for name in supported}
        for line in endpoint.get("pricing") or []:
            cost = line.get("cost_usd") if isinstance(line, dict) else None
            if isinstance(cost, int | float) and line.get("unit") == "image":
                variant = str(line.get("variant") or RESOLUTION).lower()
                per_image[variant] = max(per_image.get(variant, 0.0), float(cost))
    return Endpoint(frozenset(parameters), per_image)


def forget() -> None:
    """Forget what OpenRouter said of its models (for tests)."""
    with _endpoints_lock:
        _endpoints.clear()
