"""Image generators on your own computer, for nothing, for anyone with a GPU: a ComfyUI server (comfyui), or an
Automatic1111-style one (automatic1111: AUTOMATIC1111's web UI, Forge and SD.Next share its API), started with its API
on. They have no moderation of their own, so talkgenerator's own rules (see talkgenerator.images.safety) are all that
keep their pictures safe, and what those rule out goes in the negative prompt.

- ComfyUI (COMFYUI_URL, http://127.0.0.1:8188 by default): POST /prompt queues a workflow in its API format, GET
  /history/<id> tells when it's done and where its picture is, and GET /view fetches the picture. The workflow is a
  plain text-to-image one with the server's first checkpoint (or COMFYUI_CHECKPOINT, or the spec's model), or your
  own (COMFYUI_WORKFLOW: a workflow saved in the API format, with "{{prompt}}", "{{negative_prompt}}", "{{seed}}",
  "{{width}}" and "{{height}}" where they go).
- Automatic1111 (AUTOMATIC1111_URL, http://127.0.0.1:7860 by default): POST /sdapi/v1/txt2img answers with the picture
  in base64; the spec's model, if it names one, is the checkpoint it switches to.
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, urlencode

from talkgenerator import settings
from talkgenerator.images.generators import web
from talkgenerator.images.generators.base import (
    GeneratedImage,
    GenerationError,
    GeneratorCapabilities,
    GeneratorUnavailable,
    ImageGenerator,
    ImageRequest,
)

POLL_SECONDS: Final = 0.5
STEPS: Final = 25
CFG_SCALE: Final = 7.0
# Sizes of about a megapixel in multiples of 64, as Stable Diffusion XL models are trained on
_SIZES: Final = {
    "1:1": (1024, 1024),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
}
_LOCAL: Final = GeneratorCapabilities(seed=True, instructions=False, local=True)


def size(request: ImageRequest) -> tuple[int, int]:
    return _SIZES[request.aspect_ratio]


def _seed(request: ImageRequest) -> int:
    return request.seed if request.seed is not None else 0


class ComfyUIGenerator(ImageGenerator):
    capabilities = _LOCAL

    def __init__(
        self,
        model: str = "",
        *,
        url: str | None = None,
        client: web.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.url = (url or settings.comfyui_url()).rstrip("/")
        self._checkpoint = model.strip() or settings.comfyui_checkpoint()
        self._workflow = settings.comfyui_workflow()
        self._client = client or web.WEB
        self._sleep = sleep

    @property
    def id(self) -> str:  # type: ignore[override]
        """comfyui:<its checkpoint> (or <its workflow file's name>): what makes its pictures. (A server that can't be
        asked yet is comfyui:server: it makes no picture either.)"""
        if self._workflow:
            return f"comfyui:{Path(self._workflow).stem}"
        try:
            return f"comfyui:{self.checkpoint()}"
        except GenerationError:
            return "comfyui:server"

    def checkpoint(self) -> str:
        """The checkpoint the workflow loads: the one asked for, or else the server's first."""
        if not self._checkpoint:
            info = web.answer(
                self._client.get(f"{self.url}/object_info/CheckpointLoaderSimple", headers={}, timeout=15), "ComfyUI"
            )
            names = _choices(info, "CheckpointLoaderSimple", "ckpt_name")
            if not names:
                raise GeneratorUnavailable("ComfyUI has no checkpoint to make pictures with")
            self._checkpoint = names[0]
        return self._checkpoint

    def generate(self, request: ImageRequest) -> GeneratedImage:
        queued = web.answer(
            self._client.post(
                f"{self.url}/prompt",
                json={"prompt": self.workflow(request), "client_id": f"talkgenerator-{uuid.uuid4().hex[:8]}"},
                headers={"Content-Type": "application/json"},
                timeout=30,
            ),
            "ComfyUI",
        )
        prompt_id = queued.get("prompt_id") if isinstance(queued, dict) else None
        if not prompt_id:
            raise GenerationError(
                f"ComfyUI didn't queue the workflow ({queued.get('node_errors') if isinstance(queued, dict) else ''})"
            )
        deadline = time.monotonic() + 10 * web.TIMEOUT_SECONDS  # (a local GPU may take its time)
        while True:
            history = web.answer(self._client.get(f"{self.url}/history/{prompt_id}", headers={}, timeout=30), "ComfyUI")
            done = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(done, dict) and (done.get("outputs") or (done.get("status") or {}).get("completed")):
                break
            if time.monotonic() > deadline:
                raise GeneratorUnavailable("ComfyUI took too long")
            self._sleep(POLL_SECONDS)
        status = done.get("status") or {}
        if status.get("status_str") == "error":
            raise GenerationError("ComfyUI's workflow failed")
        for output in (done.get("outputs") or {}).values():
            for picture in (output or {}).get("images") or []:
                if picture.get("type", "output") != "output":
                    continue
                query = urlencode(
                    {"filename": picture["filename"], "subfolder": picture.get("subfolder", ""), "type": "output"},
                    quote_via=quote,
                )
                image = web.download(self._client, f"{self.url}/view?{query}", "ComfyUI")
                return GeneratedImage(
                    data=image,
                    media_type=web.media_type(image, "image/png"),
                    model=self.id,
                    cost_usd=0.0,
                    seed=_seed(request),
                )
        raise GenerationError("ComfyUI's workflow made no picture")

    def workflow(self, request: ImageRequest) -> dict[str, Any]:
        """The workflow for the request, in ComfyUI's API format: COMFYUI_WORKFLOW's with its placeholders filled in,
        or a plain text-to-image one."""
        width, height = size(request)
        values: dict[str, Any] = {
            "prompt": request.text(with_avoid=False),
            "negative_prompt": request.avoid,
            "seed": _seed(request),
            "width": width,
            "height": height,
        }
        if self._workflow:
            try:
                own = json.loads(Path(self._workflow).read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise GeneratorUnavailable(f"Can't read the ComfyUI workflow {self._workflow} ({error})") from error
            if not isinstance(own, dict):
                raise GeneratorUnavailable(f"The ComfyUI workflow {self._workflow} isn't one in the API format")
            filled: dict[str, Any] = _filled(own, values)
            return filled
        workflow: dict[str, Any] = _filled(copy.deepcopy(_TEXT_TO_IMAGE), {**values, "checkpoint": self.checkpoint()})
        return workflow


class Automatic1111Generator(ImageGenerator):
    capabilities = _LOCAL

    def __init__(self, model: str = "", *, url: str | None = None, client: web.Client | None = None) -> None:
        self.url = (url or settings.automatic1111_url()).rstrip("/")
        self._asked = self._model = model.strip()
        self._client = client or web.WEB

    @property
    def id(self) -> str:  # type: ignore[override]
        """automatic1111:<its checkpoint>: the one asked for, or else the one the server has loaded."""
        if not self._model:
            try:
                options = web.answer(
                    self._client.get(f"{self.url}/sdapi/v1/options", headers={}, timeout=15), "Automatic1111"
                )
            except GenerationError:  # (a server that can't be asked yet makes no picture either)
                return "automatic1111:server"
            loaded = options.get("sd_model_checkpoint") if isinstance(options, dict) else None
            self._model = str(loaded or "stable-diffusion")
        return f"automatic1111:{self._model}"

    def generate(self, request: ImageRequest) -> GeneratedImage:
        width, height = size(request)
        arguments: dict[str, Any] = {
            "prompt": request.text(with_avoid=False),
            "negative_prompt": request.avoid,
            "width": width,
            "height": height,
            "seed": _seed(request),
            "steps": STEPS,
            "cfg_scale": CFG_SCALE,
            "batch_size": 1,
            "n_iter": 1,
        }
        if self._asked:
            arguments["override_settings"] = {"sd_model_checkpoint": self._asked}
        data = web.answer(
            self._client.post(
                f"{self.url}/sdapi/v1/txt2img",
                json=arguments,
                headers={"Content-Type": "application/json"},
                timeout=10 * web.TIMEOUT_SECONDS,
            ),
            "Automatic1111",
        )
        pictures = data.get("images") if isinstance(data, dict) else None
        if not pictures:
            raise GenerationError("Automatic1111 made no picture")
        image = web.decoded(pictures[0], "Automatic1111")
        return GeneratedImage(
            data=image, media_type=web.media_type(image, "image/png"), model=self.id, cost_usd=0.0, seed=_seed(request)
        )


def _choices(info: Any, node: str, field: str) -> list[str]:
    """The options of a node's input, as ComfyUI's object_info lists them (["a.safetensors", ...], or the newer
    ["COMBO", {"options": [...]}])."""
    try:
        spec = info[node]["input"]["required"][field]
    except (KeyError, TypeError):
        return []
    if isinstance(spec, list) and spec and isinstance(spec[0], list):
        return [str(name) for name in spec[0]]
    if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict):
        return [str(name) for name in spec[1].get("options") or []]
    return []


def _filled(value: Any, values: dict[str, Any]) -> Any:
    """The workflow with its placeholders ("{{seed}}") filled in: a value that's only a placeholder becomes the value
    itself (a number for a seed), and one in a longer text, its text."""
    if isinstance(value, dict):
        return {key: _filled(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [_filled(item, values) for item in value]
    if isinstance(value, str):
        for name, filled in values.items():
            placeholder = "{{" + name + "}}"
            if value == placeholder:
                return filled
            value = value.replace(placeholder, str(filled))
    return value


# A plain text-to-image workflow, in ComfyUI's API format: a checkpoint, the prompt and the negative prompt, an empty
# latent of the picture's size, a sampler, a decoder and a node that saves the picture
_TEXT_TO_IMAGE: Final[dict[str, Any]] = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "{{checkpoint}}"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}", "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative_prompt}}", "clip": ["1", 1]}},
    "4": {"class_type": "EmptyLatentImage", "inputs": {"width": "{{width}}", "height": "{{height}}", "batch_size": 1}},
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "seed": "{{seed}}",
            "steps": STEPS,
            "cfg": CFG_SCALE,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    },
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "talkgenerator", "images": ["6", 0]}},
}
