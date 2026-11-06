"""The keys that `talkgenerator login` gets, kept in talkgenerator's config folder (see settings.config_dir).

They're in one JSON file that only the user can read and write (on Windows, the user's AppData folder is theirs
alone already). A stored key is only used when its environment variable isn't set: OPENROUTER_API_KEY goes first.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger("talkgenerator")

FILE_NAME: Final = "credentials.json"

StrPath = str | os.PathLike[str]


def credentials_file(config_dir: StrPath) -> Path:
    return Path(config_dir) / FILE_NAME


def stored(config_dir: StrPath, provider: str) -> dict[str, Any]:
    """What's kept for the provider (its key, label and when it was made), or {}."""
    entry = _read(credentials_file(config_dir)).get(provider)
    return entry if isinstance(entry, dict) else {}


def stored_key(config_dir: StrPath, provider: str) -> str:
    """The provider's stored key, or "" if there's none."""
    key = stored(config_dir, provider).get("key")
    return key.strip() if isinstance(key, str) else ""


def store(config_dir: StrPath, provider: str, entry: dict[str, Any]) -> Path:
    """Keep what's known about the provider's key (the key itself, under "key"), next to the other providers'."""
    path = credentials_file(config_dir)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = _read(path)
    data[provider] = entry
    _write(path, data)
    return path


def forget(config_dir: StrPath, provider: str) -> dict[str, Any] | None:
    """Forget the provider's key; what was kept for it, or None if nothing was."""
    path = credentials_file(config_dir)
    data = _read(path)
    entry = data.pop(provider, None)
    if entry is None:
        return None
    if data:
        _write(path, data)
    else:
        path.unlink(missing_ok=True)
    return entry if isinstance(entry, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        logger.warning("Can't read the keys in %s: sign in again (talkgenerator login) to replace them", path)
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict[str, Any]) -> None:
    # Into a file of the user's alone (mkstemp makes it so on POSIX), moved over the old one: a crash halfway never
    # leaves half a file
    descriptor, temporary = tempfile.mkstemp(prefix=".credentials-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
