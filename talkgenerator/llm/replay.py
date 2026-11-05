"""Recorded answers: a provider that replays what another provider said.

A cassette is a JSON file of requests and the answers they got, by a hash of the request. Replaying one, the same
requests get the same answers, without a network or a key: offline tests of LLM talks use that, and so does making a
recorded talk again exactly (with its seed). With a provider to record with, requests that aren't on the cassette
are asked for real and added to it.

The file keeps a fixed order (by key) and readable indentation, so that changes to a cassette show up well in diffs.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from talkgenerator.llm.base import Capabilities, ProviderUnavailable, TextProvider, TextRequest, TextResponse

CASSETTE_VERSION: Final = 1


class CassetteMiss(ProviderUnavailable):
    """The cassette has no answer to the request (and there's no provider to record with)."""


def request_key(request: TextRequest) -> str:
    """The key of a request on a cassette: the same request always gives the same key, in every process."""
    canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReplayProvider(TextProvider):
    """Answers from a cassette, and records new answers with `record` when it's given."""

    id = "replay"

    def __init__(self, cassette: str | Path, *, record: TextProvider | None = None, chunk_size: int = 64) -> None:
        self.path = Path(cassette)
        self.record = record
        self.chunk_size = chunk_size
        self.capabilities = record.capabilities if record else Capabilities(structured_output=True, streaming=True)
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = self._load()

    def __len__(self) -> int:
        return len(self._entries)

    def complete(self, request: TextRequest) -> TextResponse:
        return self._answer(request, lambda recorder: recorder.complete(request), lambda response: None)

    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse:
        def replay_in_pieces(response: TextResponse) -> None:
            # In pieces, as if it were being written, so that the incremental reading of a talk gets tested too
            for start in range(0, len(response.text), self.chunk_size):
                on_text(response.text[start : start + self.chunk_size])

        return self._answer(request, lambda recorder: recorder.stream(request, on_text), replay_in_pieces)

    def _answer(
        self,
        request: TextRequest,
        ask: Callable[[TextProvider], TextResponse],
        hand_over: Callable[[TextResponse], None],
    ) -> TextResponse:
        key = request_key(request)
        entry = self._entries.get(key)
        if entry is not None:
            response = TextResponse.model_validate(entry["response"])
            hand_over(response)
            return response
        if self.record is None:
            raise CassetteMiss(f"{self.path} has no answer to this {request.purpose!r} request (key {key[:12]})")
        response = ask(self.record)
        self._add(key, request, response)
        return response

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        cassette = json.loads(self.path.read_text(encoding="utf-8"))
        if cassette.get("cassette_version") != CASSETTE_VERSION:
            raise ValueError(f"{self.path} isn't a cassette of version {CASSETTE_VERSION}")
        entries: dict[str, dict[str, Any]] = cassette["entries"]
        return entries

    def _add(self, key: str, request: TextRequest, response: TextResponse) -> None:
        with self._lock:
            self._entries[key] = {
                "request": request.model_dump(mode="json"),
                "response": response.model_dump(mode="json"),
            }
            text = json.dumps(
                {"cassette_version": CASSETTE_VERSION, "entries": self._entries},
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            # Write it whole or not at all: a test run that's stopped halfway shouldn't leave half a cassette
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
                file.write(text + "\n")
            os.replace(temporary, self.path)
