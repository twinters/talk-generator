"""OpenAI's image models (gpt-image-2 by default), through its Image API with your own key (OPENAI_API_KEY).

Checked on 2026-11-07 (developers.openai.com/api/docs/guides/image-generation): POST /v1/images/generations takes a
model, a prompt, a size (1024x1024, 1536x1024 or 1024x1536 at the list prices), a quality (low, medium, high) and an
output format, and answers with the picture in base64 (data[0].b64_json). Its moderation ("auto" by default) turns a
prompt down with error code "moderation_blocked", and says why in moderation_details. The models take no seed.
"""

from __future__ import annotations

from typing import Any, Final

from talkgenerator import settings
from talkgenerator.images.generators import prices, web
from talkgenerator.images.generators.base import (
    GeneratedImage,
    GenerationRefused,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
)

API_URL: Final = "https://api.openai.com/v1/images/generations"
PROVIDER: Final = "openai"


class OpenAIImageGenerator(ImageGenerator):
    capabilities = GeneratorCapabilities(seed=False, instructions=True)

    def __init__(self, model: str = "", *, api_key: str | None = None, client: web.Client | None = None) -> None:
        self.id = f"{PROVIDER}:{model.strip() or prices.default_model(PROVIDER)}"
        self.terms = prices.terms(PROVIDER)
        self._key = api_key
        self._client = client or web.WEB

    def generate(self, request: ImageRequest) -> GeneratedImage:
        key = self._key if self._key is not None else settings.openai_api_key()
        if not key:
            raise GeneratorUnavailable("OpenAI's image models need a key: set OPENAI_API_KEY")
        response = self._client.post(
            API_URL,
            json=self.arguments(request),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=web.TIMEOUT_SECONDS,
        )
        if response is not None and not response.ok:
            refused = _refusal(response)
            if refused is not None:
                raise refused
        data = web.answer(response, "OpenAI")
        picture = (data.get("data") or [{}])[0] if isinstance(data, dict) else {}
        image = web.decoded(picture.get("b64_json"), "OpenAI")
        revised = picture.get("revised_prompt")
        return GeneratedImage(
            data=image,
            media_type=web.media_type(image, f"image/{data.get('output_format') or 'jpeg'}"),
            model=self.id,
            flags=("revised prompt",) if revised else (),
            revised_prompt=revised if isinstance(revised, str) else None,
        )

    def arguments(self, request: ImageRequest) -> dict[str, Any]:
        """The request, as OpenAI's Image API takes it."""
        return {
            "model": self.model,
            "prompt": request.text(),
            "n": 1,
            "size": size(request),
            "quality": request.quality,
            "output_format": "jpeg",
            "moderation": "auto",
        }


def size(request: ImageRequest) -> str:
    """The size at the list prices nearest to the request's shape."""
    width, height = request.shape()
    if width == height:
        return "1024x1024"
    return "1536x1024" if width > height else "1024x1536"


def _refusal(response: web.Response) -> GenerationRefused | None:
    """The refusal an error answer is, when OpenAI's moderation turned the prompt down (with its categories)."""
    try:
        data = response.json()
    except ValueError:
        return None
    found = data.get("error") if isinstance(data, dict) else None
    if not isinstance(found, dict) or found.get("code") != "moderation_blocked":
        return None
    details = found.get("moderation_details") or {}
    categories = [str(category) for category in details.get("categories") or [] if category]
    flags = ("openai: moderation blocked", *(f"openai: {category}" for category in categories))
    stage = details.get("moderation_stage")
    return GenerationRefused(
        f"OpenAI's moderation turned it down{f' ({stage})' if stage else ''}: {', '.join(categories) or 'no reason'}",
        flags,
    )
