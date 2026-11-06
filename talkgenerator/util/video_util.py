"""Reading mp4 videos, as far as talkgenerator needs to: whether some bytes are one, and how long it plays.

An mp4 (an ISO base media file) is a row of boxes, each a 4-byte size (of the whole box), a 4-byte type and what it
holds, which can be boxes again. It starts with "ftyp", its file type, and "moov" holds the movie's header, "mvhd",
with its timescale (units a second) and its duration. A fragmented mp4, such as Reddit's DASH videos, has a header
that says 0, and tells its duration in "mvex"/"mehd" or adds it up in its segment index, "sidx".
"""

from __future__ import annotations

import struct
from collections.abc import Iterator

_UNKNOWN = (0, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)  # durations that say nothing: none, or all ones


def is_mp4(data: bytes) -> bool:
    """Whether the bytes start the way an mp4 does: with its file type box."""
    return data[4:8] == b"ftyp"


def duration(data: bytes) -> float | None:
    """How long the mp4 plays, in seconds, or None if it doesn't say."""
    try:
        movie = _find(data, b"moov")
        header = _find(data, b"mvhd", *movie) if movie else None
        if movie is None or header is None:
            return None
        start = header[0]
        if data[start] == 1:  # version 1: 64-bit times
            timescale, length = struct.unpack_from(">IQ", data, start + 20)
        else:
            timescale, length = struct.unpack_from(">II", data, start + 12)
        if not timescale:
            return None
        if length in _UNKNOWN:
            extends = _find(data, b"mvex", *movie)
            fragments = _find(data, b"mehd", *extends) if extends else None
            length = _full_box_number(data, fragments[0]) if fragments else 0
        if length not in _UNKNOWN:
            return float(length / timescale)
        return _indexed_duration(data)
    except (struct.error, IndexError):  # cut short
        return None


def _indexed_duration(data: bytes) -> float | None:
    """What the durations in a fragmented mp4's segment index add up to, in seconds."""
    index = _find(data, b"sidx")
    if index is None:
        return None
    start = index[0]
    timescale = struct.unpack_from(">I", data, start + 8)[0]
    # After the version and flags, reference ID and timescale: the earliest time and first offset (32 or 64 bits
    # each), 2 reserved bytes, the number of references, and then 12 bytes a reference, its duration in the middle
    references = start + (24 if data[start] == 0 else 32)
    count = struct.unpack_from(">H", data, references - 2)[0]
    total = sum(struct.unpack_from(">I", data, references + 12 * number + 4)[0] for number in range(count))
    return total / timescale if timescale and total else None


def _full_box_number(data: bytes, start: int) -> int:
    """The number after a full box's version and flags: 64 bits in version 1, 32 bits otherwise."""
    number: int = struct.unpack_from(">Q" if data[start] == 1 else ">I", data, start + 4)[0]
    return number


def _find(data: bytes, kind: bytes, start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    """Where what the first box of the kind in data[start:end] holds starts, and where the box ends."""
    return next(((inside, box_end) for found, inside, box_end in _boxes(data, start, end) if found == kind), None)


def _boxes(data: bytes, start: int = 0, end: int | None = None) -> Iterator[tuple[bytes, int, int]]:
    """The boxes in data[start:end]: their type, where what they hold starts, and where they end."""
    end = len(data) if end is None else min(end, len(data))
    position = start
    while position + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, position)
        header = 8
        if size == 1:  # a 64-bit size follows
            size = struct.unpack_from(">Q", data, position + 8)[0]
            header = 16
        elif size == 0:  # to the end
            size = end - position
        if size < header:
            return
        yield kind, position + header, min(position + size, end)
        position += size
