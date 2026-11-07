"""Generated pictures, kept on disk by what made them: the model, the prompt (with its style and what it avoids), the
shape, the quality and the seed (for generators that take one: for the others, the seed doesn't change the picture).
Making a talk again with the same seed asks for the same pictures, which come from here, and a deck rendered again
reads its pictures from here: neither generates anything again.

They're in talkgenerator's cache folder (TALKGENERATOR_CACHE_DIR, or your user cache folder), in generated-images/:
every picture next to a small JSON file that says what made it and what it cost.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Final

from talkgenerator import settings
from talkgenerator.images.generators.base import GeneratedImage, ImageRequest

logger = logging.getLogger("talkgenerator")

FOLDER: Final = "generated-images"
_EXTENSIONS: Final = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


def folder() -> Path:
    return Path(settings.cache_dir()) / FOLDER


def key(model: str, request: ImageRequest, seeded: bool) -> str:
    """What a picture is kept under: a hash of the model ("provider:model") and the request as the model gets it."""
    asked = request.model_dump(exclude=None if seeded else {"seed"})
    text = json.dumps({"model": model, "request": asked}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def get(name: str) -> tuple[Path, GeneratedImage] | None:
    """The picture kept under the key, with what made it, if there is one."""
    about = folder() / f"{name}.json"
    try:
        record = json.loads(about.read_text(encoding="utf-8"))
        path = folder() / str(record["file"])
        data = path.read_bytes()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    image = GeneratedImage(
        data=data,
        media_type=str(record.get("media_type") or "image/png"),
        model=str(record.get("model") or ""),
        cost_usd=record.get("cost_usd"),
        flags=tuple(record.get("flags") or ()),
        seed=record.get("seed"),
        revised_prompt=record.get("revised_prompt"),
    )
    return path, image


def put(name: str, image: GeneratedImage, request: ImageRequest) -> Path:
    """Keep the picture under the key (written whole, or not at all), and return its file."""
    directory = folder()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}{_EXTENSIONS.get(image.media_type, '.png')}"
    _write(path, image.data)
    record = {key: value for key, value in asdict(image).items() if key != "data"}
    record.update(file=path.name, request=request.model_dump())
    _write(directory / f"{name}.json", json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8"))
    return path


def _write(path: Path, data: bytes) -> None:
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(data)
    os.replace(partial, path)
