"""Randomness, seeded per talk.

A talk is a long series of random choices. To make a seed give the same talk every time, every talk gets its own
random generator (`Rng`), and every part of the talk (each slide, and each purpose within it) a stream derived from
it with `Rng.child`. The same seed and path always give the same numbers, however many numbers other parts drew, and
in whatever order threads ran. Code draws from the stream of whatever it's working on: `use` sets it for a block,
and the functions below (`choice`, `uniform`, ...) draw from it.

Outside a talk, they draw from Python's global random generator, so `random.seed()` keeps working for scripts and
tests. Nothing else in talkgenerator may use the `random` module directly (a lint rule checks that).
"""

from __future__ import annotations

import hashlib
import random as _random
from collections.abc import Iterator, MutableSequence, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")


class Rng(_random.Random):
    """The random generator of a talk, or of a part of it (see child).

    Without a seed, a random one is picked; `root_seed` tells which, so that the talk can be made again.
    """

    def __init__(self, seed: int | None = None, *, path: tuple[str | int, ...] = ()) -> None:
        self.root_seed: int = seed if seed is not None else new_seed()
        self.path = path
        super().__init__(_derive(self.root_seed, path))

    def child(self, *parts: str | int) -> Rng:
        """The generator of a part of the talk, such as `child("slide", 3)`."""
        return Rng(self.root_seed, path=self.path + parts)

    def __repr__(self) -> str:
        return f"Rng({self.root_seed}, path={self.path!r})"


def new_seed() -> int:
    """A random seed, for a talk that wasn't given one."""
    return _random.SystemRandom().randrange(2**32)


def _derive(seed: int, path: tuple[str | int, ...]) -> int:
    # Not hash(): Python randomizes the hashes of strings for every process
    digest = hashlib.sha256(repr((seed, path)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class _GlobalRandom(_random.Random):
    """Python's global random generator, for code that runs outside a talk."""

    def random(self) -> float:
        return _random.random()

    def getrandbits(self, k: int) -> int:
        return _random.getrandbits(k)


_GLOBAL = _GlobalRandom()
_current: ContextVar[_random.Random | None] = ContextVar("talkgenerator_random", default=None)


def current() -> _random.Random:
    """The random generator to draw from: the one `use` set, or else Python's global one."""
    rng = _current.get()
    return rng if rng is not None else _GLOBAL


@contextmanager
def use(rng: _random.Random) -> Iterator[_random.Random]:
    """Draw from rng in this block. It only applies to the thread (or task) that runs the block."""
    token = _current.set(rng)
    try:
        yield rng
    finally:
        _current.reset(token)


# The random module's functions, drawing from the current generator


def random() -> float:
    return current().random()


def uniform(a: float, b: float) -> float:
    return current().uniform(a, b)


def gauss(mu: float = 0.0, sigma: float = 1.0) -> float:
    return current().gauss(mu, sigma)


def randint(a: int, b: int) -> int:
    return current().randint(a, b)


def randrange(start: int, stop: int | None = None, step: int = 1) -> int:
    return current().randrange(start, stop, step)


def choice(seq: Sequence[T]) -> T:
    return current().choice(seq)


def choices(population: Sequence[T], weights: Sequence[float] | None = None, *, k: int = 1) -> list[T]:
    return current().choices(population, weights, k=k)


def sample(population: Sequence[T], k: int) -> list[T]:
    return current().sample(population, k)


def shuffle(x: MutableSequence[Any]) -> None:
    current().shuffle(x)


# From https://stackoverflow.com/questions/14992521/python-weighted-random
def weighted_random(pairs: Sequence[tuple[float, T]]) -> T | None:
    if len(pairs) == 0:
        return None
    total = sum(pair[0] for pair in pairs)
    r = uniform(0, total)
    for weight, value in pairs:
        r -= weight
        if r <= 0:
            return value
    return None


def choice_optional(lst: Sequence[T]) -> T | None:
    """A random element, or None if there are none."""
    if len(lst) > 0:
        return choice(lst)
    return None
