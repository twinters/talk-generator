"""Offline tests of talkgenerator.util.threads' pools, whose threads end once they've had nothing to do for a while, and
of talks, which leave no thread behind once that's so: a server that makes talk after talk in one process, as
talkgenerator.com does, may only have so many threads (systemd's TasksMax), and its pools' idle threads once took nearly
all of them, until every talk failed with "can't start new thread".

The talks are the fake ones of test_llm_talks and test_streaming.
"""

import logging
import threading
import time

import pytest

from talkgenerator import generator
from talkgenerator.util import image_util, threads
from tests import test_streaming
from tests.test_llm_talks import FakeModel, _jpeg, fake_schema


def _until(condition, seconds=10.0):
    """Whether the condition holds within the seconds."""
    deadline = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.01)
    return True


def _named(name):
    return [thread for thread in threading.enumerate() if thread.name.startswith(f"{name}_")]


def _cant_start(thread):
    raise RuntimeError("can't start new thread")


def test_a_pool_gives_what_its_work_gives():
    pool = threads.Pool(2, "giving")
    assert pool.submit(sum, [1, 2, 3]).result(timeout=5) == 6
    assert list(pool.map(lambda number: number * number, range(6))) == [0, 1, 4, 9, 16, 25]
    with pytest.raises(ValueError, match="not a number"):
        pool.submit(int, "not a number").result(timeout=5)
    pool.shutdown()
    assert pool.threads == 0 and not _named("giving")


def test_a_pool_runs_no_more_work_at_once_than_its_most():
    pool = threads.Pool(3, "busy")
    go_on = threading.Event()
    lock = threading.Lock()
    running, most = 0, 0

    def work():
        nonlocal running, most
        with lock:
            running += 1
            most = max(most, running)
        go_on.wait(5)
        with lock:
            running -= 1

    futures = [pool.submit(work) for _ in range(8)]
    assert _until(lambda: running == 3)
    time.sleep(0.05)
    assert running == 3 and pool.threads == 3 and len(_named("busy")) == 3
    go_on.set()
    for future in futures:
        future.result(timeout=5)
    assert most == 3
    pool.shutdown()


def test_a_pool_starts_a_thread_only_when_its_threads_are_busy():
    pool = threads.Pool(4, "lazy")
    for number in range(5):
        assert pool.submit(lambda number=number: number).result(timeout=5) == number
        assert _until(lambda: pool.waiting == pool.threads)  # (back to waiting for work)
    assert pool.threads == 1
    pool.shutdown()


def test_a_pools_threads_end_once_they_have_had_nothing_to_do():
    pool = threads.Pool(4, "idle", idle=0.1)
    go_on = threading.Event()
    futures = [pool.submit(go_on.wait, 5) for _ in range(4)]
    assert _until(lambda: len(_named("idle")) == 4)
    go_on.set()
    for future in futures:
        assert future.result(timeout=5) is True
    assert _until(lambda: pool.threads == 0 and not _named("idle"))
    # (and work that comes later starts a thread again)
    assert pool.submit(lambda: "again").result(timeout=5) == "again"
    assert _until(lambda: pool.threads == 0 and not _named("idle"))


def test_a_shut_pool_finishes_its_work_or_drops_what_hasnt_started():
    pool = threads.Pool(1, "dropping")
    go_on = threading.Event()
    first = pool.submit(go_on.wait, 5)
    assert _until(first.running)
    second = pool.submit(lambda: "second")
    pool.shutdown(wait=False, cancel_futures=True)
    assert second.cancelled()
    with pytest.raises(RuntimeError, match="after shutdown"):
        pool.submit(lambda: "too late")
    go_on.set()
    assert first.result(timeout=5) is True
    assert _until(lambda: not _named("dropping"))

    pool = threads.Pool(1, "draining")
    go_on.clear()
    first = pool.submit(go_on.wait, 5)
    second = pool.submit(lambda: "second")
    threading.Timer(0.05, go_on.set).start()
    pool.shutdown()  # (waits for both)
    assert first.result(timeout=0) is True and second.result(timeout=0) == "second"
    assert pool.threads == 0


def test_work_runs_on_the_thread_that_hands_it_over_when_no_thread_can_be_started(monkeypatch, caplog):
    pool = threads.Pool(2, "capped")
    monkeypatch.setattr(threading.Thread, "start", _cant_start)
    with caplog.at_level(logging.WARNING, logger="talkgenerator"):
        future = pool.submit(threading.get_ident)
        assert future.done() and future.result() == threading.get_ident()
        assert pool.submit(lambda: "again").result(timeout=0) == "again"
    assert pool.threads == 0
    assert caplog.text.count("No thread could be started for the capped") == 1  # (once)


def test_work_waits_for_the_pools_threads_when_no_more_can_be_started(monkeypatch):
    pool = threads.Pool(2, "full")
    go_on = threading.Event()
    first = pool.submit(go_on.wait, 5)
    assert _until(first.running)
    with monkeypatch.context() as patched:
        patched.setattr(threading.Thread, "start", _cant_start)
        second = pool.submit(threading.get_ident)
        assert not second.done() and pool.threads == 1  # (it waits for the pool's thread, rather than run here)
    go_on.set()
    assert second.result(timeout=5) != threading.get_ident()
    pool.shutdown()


@pytest.fixture
def fakes(monkeypatch):
    """The fake schema of test_llm_talks, and every image at example.com exists (downloaded or probed)."""
    jpeg = _jpeg()
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: jpeg if url.startswith("https://example.com/") else load(url)
    )
    monkeypatch.setattr(
        image_util, "probe", lambda url: url.startswith("https://example.com/") or load(url) is not None
    )
    schema = fake_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)


@pytest.mark.parametrize("llm", ["fake", "none"], ids=["planned", "classic"])
def test_talks_leave_no_threads_behind(llm, fakes, monkeypatch):
    """Talk after talk, as talkgenerator.com makes them (three slides at once, a time limit per slide, early versions):
    once their pools' threads have had nothing to do for a while, the process has the threads it had before."""
    monkeypatch.setattr(threads, "IDLE_SECONDS", 0.1)
    before = set(threading.enumerate())
    for _ in range(3):
        test_streaming._streamed(llm=FakeModel() if llm == "fake" else "none", parallel=3, slide_seconds=8.0, early=2)

    def left():
        return sorted(thread.name for thread in set(threading.enumerate()) - before)

    assert _until(lambda: not left()), left()
