"""Black Forest Labs' FLUX models (FLUX 3 Image Klein by default), through BFL's API with your own key (BFL_API_KEY).

Checked on 2026-11-07 (docs.bfl.ai, bfl.ai/pricing): POST https://api.bfl.ai/v1/<model> starts a picture and answers
with its id, a polling_url and its cost in credits (a credit is a cent). The FLUX 3 models take an aspect ratio and a
resolution ("1k"), the FLUX.2 ones a width and a height; all take a seed, an output format and a safety tolerance
(0, the strictest, to 7; 2 by default). Polling the polling_url (every half second) says the task is Pending,
Generating, Ready (its picture at result.sample, a link that works for ten minutes), Request Moderated or Content
Moderated (turned down), or Error.

FLUX reads its prompt as what to draw, so it gets no list of what to leave out (it would draw what that names).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.images.generators import prices, web
from talkgenerator.images.generators.base import (
    GeneratedImage,
    GenerationError,
    GenerationRefused,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
)

API_URL: Final = "https://api.bfl.ai/v1/"
PROVIDER: Final = "flux"
SAFETY_TOLERANCE: Final = 2  # BFL's default: 0 is the strictest
POLL_SECONDS: Final = 0.5
_WAITING: Final = frozenset({"Pending", "Reasoning", "Generating", "Queued", "Processing"})
_MODERATED: Final = frozenset({"Request Moderated", "Content Moderated"})
_DOLLARS_PER_CREDIT: Final = 0.01
# The FLUX.2 models' sizes, of about a megapixel (which they're priced by) and in multiples of 16
_SIZES: Final = {
    "1:1": (1024, 1024),
    "3:2": (1248, 832),
    "2:3": (832, 1248),
    "4:3": (1152, 864),
    "3:4": (864, 1152),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}


class FluxImageGenerator(ImageGenerator):
    capabilities = GeneratorCapabilities(seed=True, instructions=False)

    def __init__(
        self,
        model: str = "",
        *,
        api_key: str | None = None,
        client: web.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.id = f"{PROVIDER}:{model.strip() or prices.default_model(PROVIDER)}"
        self.terms = prices.terms(PROVIDER)
        self._key = api_key
        self._client = client or web.WEB
        self._sleep = sleep

    def generate(self, request: ImageRequest) -> GeneratedImage:
        key = self._key if self._key is not None else settings.bfl_api_key()
        if not key:
            raise GeneratorUnavailable("FLUX needs a key from Black Forest Labs: set BFL_API_KEY")
        headers = {"x-key": key, "accept": "application/json", "Content-Type": "application/json"}
        started = web.answer(
            self._client.post(API_URL + self.model, json=self.arguments(request), headers=headers, timeout=60),
            "FLUX",
        )
        polling_url = started.get("polling_url") if isinstance(started, dict) else None
        if not polling_url:
            raise GenerationError("FLUX didn't say where its picture would be")
        credits = started.get("cost")
        deadline = time.monotonic() + web.TIMEOUT_SECONDS
        while True:
            result = web.answer(self._client.get(polling_url, headers=headers, timeout=30), "FLUX")
            status = str(result.get("status") or "") if isinstance(result, dict) else ""
            if status == "Ready":
                break
            if status in _MODERATED:
                raise GenerationRefused(f"FLUX's moderation turned it down ({status})", (f"flux: {status}",))
            if status not in _WAITING:
                raise GenerationError(f"FLUX couldn't make the picture ({status or 'no status'})")
            if time.monotonic() > deadline:
                raise GeneratorUnavailable("FLUX took too long")
            self._sleep(POLL_SECONDS)
        sample = (result.get("result") or {}).get("sample")
        if not isinstance(sample, str) or not sample:
            raise GenerationError("FLUX's picture was ready, without a link to it")
        image = web.download(self._client, sample, "FLUX")
        credits = result.get("cost", credits)
        return GeneratedImage(
            data=image,
            media_type=web.media_type(image, "image/jpeg"),
            model=self.id,
            cost_usd=float(credits) * _DOLLARS_PER_CREDIT if isinstance(credits, int | float) else None,
            seed=request.seed,
        )

    def arguments(self, request: ImageRequest) -> dict[str, Any]:
        """The request, as BFL's API takes it for the model: a FLUX 3 model's aspect ratio and resolution, or a
        FLUX.2 model's width and height."""
        arguments: dict[str, Any] = {
            "prompt": request.text(with_avoid=False),
            "safety_tolerance": SAFETY_TOLERANCE,
            "output_format": "jpeg",
        }
        if self.model.startswith("flux-3"):
            arguments.update(aspect_ratio=request.aspect_ratio, resolution="1k")
        else:
            arguments["width"], arguments["height"] = _SIZES[request.aspect_ratio]
        if request.seed is not None:
            arguments["seed"] = request.seed
        return arguments
