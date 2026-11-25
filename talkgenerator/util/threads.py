"""Pools of threads for the work talkgenerator does at once (looking for pictures, fetching them, asking sources), whose
threads end once they've had nothing to do for a while.

concurrent.futures' pools keep every thread they ever started until the process ends. In a process that makes talk
after talk (a web server's), each pool then holds as many threads as it ever ran at once, and together they can hold
more than the host lets the process have: systemd caps a service's tasks (TasksMax), and once the pools' idle threads
took nearly all of them, every talk failed with "can't start new thread" (talkgenerator.com on 2026-11-25: 60 threads,
nearly all of them idle, in a service capped at 64). A Pool starts a thread when work comes and none of its threads is
free, up to its most, and a thread that waits IDLE_SECONDS for work ends. When no thread can be started at all (the
process is at its cap), the work waits for the pool's threads, or runs on the thread that hands it over when the pool
has none: a talk then takes longer, rather than failing.

A thread's HTTP session ends with it (see talkgenerator.util.http_util): the pool's next thread starts a session of its
own, with new connections, which a server closes after every talk anyway (http_util.close_idle_connections)."""

from __future__ import annotations

import collections
import itertools
import logging
import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any, Final, Generic, ParamSpec, TypeVar

logger = logging.getLogger("talkgenerator")

# How long a pool's thread waits for work before it ends
IDLE_SECONDS: Final = 60.0

_P = ParamSpec("_P")
_T = TypeVar("_T")


class Pool(Executor):
    """At most `most` threads, named after the pool ("image finder_3"), each started when work comes and every other one
    is busy, and ended once it's waited `idle` seconds (IDLE_SECONDS by default) for work. Work runs in the order it
    came. Its threads are daemon threads: a program can end while one is still at work, as a talk's slides that ran
    out of time go on by themselves (see presentation_schema._LateSlides)."""

    def __init__(self, most: int, name: str, idle: float | None = None) -> None:
        if most < 1:
            raise ValueError(f"A pool has one thread at least, not {most}")
        self.most = most
        self.name = name
        self._idle = idle
        self._lock = threading.Lock()
        self._work_came = threading.Condition(self._lock)
        self._thread_ended = threading.Condition(self._lock)
        self._work: collections.deque[_Work[Any]] = collections.deque()
        self._threads = 0  # (alive, or being started)
        self._waiting = 0  # (of those, the ones waiting for work)
        self._own: set[int] = set()  # (the threads' idents, for a shutdown from one of them)
        self._numbers = itertools.count()
        self._shut = False
        self._warned = False

    def submit(self, fn: Callable[_P, _T], /, *args: _P.args, **kwargs: _P.kwargs) -> Future[_T]:
        work = _Work(fn, args, kwargs)
        with self._lock:
            if self._shut:
                raise RuntimeError("cannot schedule new futures after shutdown")
            self._work.append(work)
            if self._waiting:
                self._work_came.notify()
            # (a thread more, as long as the work waiting outnumbers the threads waiting for it)
            start = len(self._work) > self._waiting and self._threads < self.most
            if start:
                self._threads += 1
                number = next(self._numbers)
        if start:
            self._start(number)
        return work.future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """No more work: the work that came is done (unless cancel_futures, which drops what hasn't started), and the
        threads end once it is; with wait, once they all have."""
        with self._lock:
            self._shut = True
            if cancel_futures:
                while self._work:
                    self._work.popleft().future.cancel()
            self._work_came.notify_all()
            if wait:
                own = 1 if threading.get_ident() in self._own else 0  # (from one of its threads: all but that one)
                while self._threads > own:
                    self._thread_ended.wait()

    @property
    def threads(self) -> int:
        """How many threads it has (alive, or being started)."""
        with self._lock:
            return self._threads

    @property
    def waiting(self) -> int:
        """How many of its threads are waiting for work."""
        with self._lock:
            return self._waiting

    def _start(self, number: int) -> None:
        thread = threading.Thread(target=self._serve, name=f"{self.name}_{number}", daemon=True)
        try:
            thread.start()
        except RuntimeError as error:  # (the process can't have another thread, or Python is ending)
            with self._lock:
                self._threads -= 1
                self._thread_ended.notify_all()
                # (with no thread of its own left to do it, the work that came runs here)
                orphans: list[_Work[Any]] = []
                if self._threads == 0:
                    orphans, self._work = list(self._work), collections.deque()
                warn, self._warned = not self._warned, True
            if warn:
                logger.warning(
                    "No thread could be started for the %s (%s): its work waits for its threads, or runs on the thread "
                    "that hands it over",
                    self.name,
                    error,
                )
            for work in orphans:
                work.run()

    def _serve(self) -> None:
        me = threading.get_ident()
        with self._lock:
            self._own.add(me)
        while True:
            with self._lock:
                while not self._work:
                    if not self._shut:
                        self._waiting += 1
                        came = self._work_came.wait(IDLE_SECONDS if self._idle is None else self._idle)
                        self._waiting -= 1
                        if came or self._work or self._shut:
                            continue
                    # (shut down, or idle long enough, with no work left: this thread ends, which a submit that comes
                    # after this sees, as it's counted under the same lock)
                    self._threads -= 1
                    self._own.discard(me)
                    self._thread_ended.notify_all()
                    return
                work = self._work.popleft()
            work.run()
            del work


class _Work(Generic[_T]):
    """A function to run (with its arguments) and the future that gets what it gives."""

    __slots__ = ("args", "fn", "future", "kwargs")

    def __init__(self, fn: Callable[..., _T], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self.future: Future[_T] = Future()
        self.fn: Callable[..., _T] | None = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        fn, self.fn = self.fn, None
        args, kwargs, self.args, self.kwargs = self.args, self.kwargs, (), {}
        if fn is None or not self.future.set_running_or_notify_cancel():
            return
        try:
            result = fn(*args, **kwargs)
        except BaseException as error:  # (for whoever waits for it, as concurrent.futures' pools do)
            self.future.set_exception(error)
        else:
            self.future.set_result(result)
