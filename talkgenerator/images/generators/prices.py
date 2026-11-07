"""The image generators' models and list prices, as config rather than code (docs/v5-plan.md, section 10.5): several
image models were retired in 2026, so the default model of every provider, and the prices a talk estimates its cost
with, are in a data file (talkgenerator/data/image_generators.json), with the date they were checked.

An image_generators.json in talkgenerator's config folder (see talkgenerator.settings.config_dir) adds to it or
changes it, provider by provider, in the same shape: a model of your own, its price, another default. A model without
a price costs what its provider says, which can't be told before it's asked: a talk with a dollar limit on its images
(see talkgenerator.images.generation.ImageBudget) doesn't ask it.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from talkgenerator import settings
from talkgenerator.util import os_util

logger = logging.getLogger("talkgenerator")

FILE_NAME: Final = "image_generators.json"
_PACKAGED: Final = "data/" + FILE_NAME


def config() -> dict[str, Any]:
    """The providers' models and prices: talkgenerator's, with the config folder's file over them."""
    own = Path(settings.config_dir()) / FILE_NAME
    try:
        changed = own.stat().st_mtime
    except OSError:
        changed = None
    return _config(str(own) if changed is not None else None, changed)


@lru_cache(maxsize=4)
def _config(own: str | None, changed: float | None) -> dict[str, Any]:
    with open(os_util.to_actual_file(_PACKAGED), encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)
    if own is None:
        return data
    try:
        extra = json.loads(Path(own).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("Can't read %s (%s): using talkgenerator's own image models and prices", own, error)
        return data
    for name, provider in (extra.get("providers") or {}).items():
        if not isinstance(provider, dict):
            continue
        merged = dict(data["providers"].get(name, {}))
        for key, value in provider.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        data["providers"][name] = merged
    return data


def _provider(name: str) -> dict[str, Any]:
    found = config()["providers"].get(name)
    return found if isinstance(found, dict) else {}


def default_model(provider: str) -> str:
    """The model a provider's generator uses when its spec names none ("" for a local server's own model)."""
    return str(_provider(provider).get("default") or "")


def terms(provider: str) -> tuple[str, str] | None:
    """The provider's terms, which a generated picture is under: their name, and their page."""
    found = _provider(provider).get("terms")
    return (str(found[0]), str(found[1])) if isinstance(found, list) and len(found) == 2 else None


def price_of(model: str, quality: str = "low") -> float | None:
    """What a picture of about a megapixel costs at the model ("provider:model"), in dollars, at that quality (for the
    models that have qualities), or None if its price isn't known."""
    provider, _, name = model.partition(":")
    price = (_provider(provider).get("prices") or {}).get(name)
    if isinstance(price, dict):
        price = price.get(
            quality, max((value for value in price.values() if isinstance(value, int | float)), default=None)
        )
    return float(price) if isinstance(price, int | float) else None


def retiring(model: str) -> str | None:
    """The day a model ("provider:model") is to be retired, if its provider said so."""
    provider, _, name = model.partition(":")
    day = (_provider(provider).get("retiring") or {}).get(name)
    return str(day) if day else None


def catalog() -> list[dict[str, Any]]:
    """The providers' models, for people and agents: provider, model, whether it's the default, and its price."""
    entries = []
    for provider, data in config()["providers"].items():
        for name, price in (data.get("prices") or {}).items():
            entries.append(
                {
                    "provider": provider,
                    "model": name,
                    "default": name == data.get("default"),
                    "price_usd": price,
                    **({"retiring": retiring(f"{provider}:{name}")} if retiring(f"{provider}:{name}") else {}),
                }
            )
    return entries
