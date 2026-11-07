"""Google's Gemini image models (Nano Banana; gemini-3.1-flash-lite-image by default, the fastest and cheapest),
through the Gemini API with your own key (GEMINI_API_KEY, or GOOGLE_API_KEY).

Checked on 2026-11-07 (aistudio.google.com/api-reference/generate-content, /docs/pricing): POST
/v1beta/models/<model>:generateContent with generationConfig.responseModalities ["IMAGE"], an imageConfig (aspectRatio,
imageSize "1K") and a seed, answers with the picture in base64 (candidates[0].content.parts[].inlineData, its mimeType
with it; parts marked as thoughts are drafts). A prompt turned down has promptFeedback.blockReason, and a picture
turned down a finishReason such as IMAGE_SAFETY. There's no free tier for pictures; every one carries Google's SynthID
watermark.
"""

from __future__ import annotations

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

API_URL: Final = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROVIDER: Final = "gemini"
IMAGE_SIZE: Final = "1K"
# The reasons a candidate stops for that mean the picture (or the prompt) was turned down
_REFUSED: Final = frozenset(
    {"SAFETY", "IMAGE_SAFETY", "PROHIBITED_CONTENT", "IMAGE_PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}
)


class GeminiImageGenerator(ImageGenerator):
    capabilities = GeneratorCapabilities(seed=True, instructions=True)

    def __init__(self, model: str = "", *, api_key: str | None = None, client: web.Client | None = None) -> None:
        self.id = f"{PROVIDER}:{model.strip() or prices.default_model(PROVIDER)}"
        self.terms = prices.terms(PROVIDER)
        self._key = api_key
        self._client = client or web.WEB

    def generate(self, request: ImageRequest) -> GeneratedImage:
        key = self._key if self._key is not None else settings.gemini_api_key()
        if not key:
            raise GeneratorUnavailable("Gemini's image models need a key: set GEMINI_API_KEY")
        response = self._client.post(
            API_URL.format(model=self.model),
            json=self.arguments(request),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            timeout=web.TIMEOUT_SECONDS,
        )
        data = web.answer(response, "Gemini")
        if not isinstance(data, dict):
            raise GenerationError("Gemini answered without a picture")
        blocked = (data.get("promptFeedback") or {}).get("blockReason")
        if blocked:
            raise GenerationRefused(f"Gemini turned the prompt down ({blocked})", (f"gemini: {blocked}",))
        candidate = (data.get("candidates") or [{}])[0]
        finish = str(candidate.get("finishReason") or "")
        if finish in _REFUSED:
            raise GenerationRefused(f"Gemini turned the picture down ({finish})", (f"gemini: {finish}",))
        for part in (candidate.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") if isinstance(part, dict) else None
            if isinstance(inline, dict) and not part.get("thought"):
                image = web.decoded(inline.get("data"), "Gemini")
                said = inline.get("mimeType") or inline.get("mime_type")
                return GeneratedImage(
                    data=image, media_type=web.media_type(image, said), model=self.id, seed=request.seed
                )
        raise GenerationError(f"Gemini answered without a picture{f' ({finish})' if finish else ''}")

    def arguments(self, request: ImageRequest) -> dict[str, Any]:
        """The request, as the Gemini API's generateContent takes it."""
        config: dict[str, Any] = {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": request.aspect_ratio, "imageSize": IMAGE_SIZE},
        }
        if request.seed is not None:
            config["seed"] = request.seed
        return {"contents": [{"role": "user", "parts": [{"text": request.text()}]}], "generationConfig": config}
