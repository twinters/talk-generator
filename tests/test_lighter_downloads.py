"""Offline tests of what keeps downloads quick and light on a small server: a host that hangs is asked once (no retry
after a read timeout), a transfer that breaks off makes a picture unusable rather than failing its slide, a PowerPoint's
pictures are downloaded a few at a time before it's drawn, and only one picture is prepared (decoded, turned, checked)
at a time."""

import http.server
import io
import socket
import threading
import time
from types import SimpleNamespace

import pytest
import requests
import urllib3.connection
from PIL import Image
from urllib3.exceptions import ConnectTimeoutError, MaxRetryError, NewConnectionError, ReadTimeoutError

from talkgenerator.models.deck import Deck, DeckSlide, ImageAsset, ImageElement, TextElement
from talkgenerator.render.powerpoint import render_pptx
from talkgenerator.util import http_util, image_util


@pytest.fixture(autouse=True)
def _nothing_downloaded_before():
    image_util.forget_downloads()
    yield
    image_util.forget_downloads()


def _jpeg(size=(400, 300)):
    data = io.BytesIO()
    Image.new("RGB", size, (20, 120, 200)).save(data, "JPEG")
    return data.getvalue()


# ASKED ONCE


def test_a_timeout_isn_t_retried_but_a_refused_connection_is():
    retry = http_util._Retry(total=2, backoff_factor=0)
    with pytest.raises(ReadTimeoutError):
        retry.increment("GET", "/image.jpg", error=ReadTimeoutError(None, "/image.jpg", "Read timed out."))
    with pytest.raises(MaxRetryError) as raised:
        retry.increment("GET", "/image.jpg", error=ConnectTimeoutError(None, "Connection timed out."))
    assert isinstance(raised.value.reason, ConnectTimeoutError)
    again = retry.increment("GET", "/image.jpg", error=NewConnectionError(None, "refused"))
    assert again.total == 1


@pytest.fixture
def hanging_host():
    """A host that takes every connection and never answers: how many connections it got."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    connections = []

    def accept():
        while True:
            try:
                connection, _ = server.accept()
            except OSError:
                return
            connections.append(connection)

    threading.Thread(target=accept, daemon=True).start()
    yield f"http://127.0.0.1:{server.getsockname()[1]}", connections
    server.close()
    for connection in connections:
        connection.close()


def test_a_host_that_won_t_take_the_connection_is_asked_once(monkeypatch):
    attempts = []

    def new_connection(connection):
        attempts.append(connection.host)
        raise ConnectTimeoutError(connection, "Connection timed out.")

    monkeypatch.setattr(urllib3.connection.HTTPConnection, "_new_conn", new_connection)
    monkeypatch.setenv("DISABLE_CACHE", "1")
    http_util.reset_sessions()
    assert http_util.get("http://images.example/photo.jpg", timeout=1) is None  # (a ConnectTimeout, caught)
    assert attempts == ["images.example"]


def test_a_host_that_hangs_is_asked_once(hanging_host, monkeypatch):
    monkeypatch.setenv("DISABLE_CACHE", "1")
    http_util.reset_sessions()
    url, connections = hanging_host
    started = time.monotonic()
    assert http_util.get(url + "/image.jpg", timeout=0.5) is None
    assert time.monotonic() - started < 1.5  # (one timeout, not three)
    assert len(connections) == 1


class _Answer:
    status_code, ok = 200, True

    def json(self):
        return {"found": 1}


@pytest.mark.parametrize("seconds", [1.0, 20.0], ids=["quick", "slow"])
def test_a_search_that_answers_slowly_counts_but_its_service_is_skipped_a_while(seconds, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(http_util, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    def get(url, **kwargs):
        clock[0] += seconds
        return _Answer()

    monkeypatch.setattr(http_util, "get", get)
    cooldown = http_util.Cooldown("A museum")
    assert http_util.search_json("https://museum.example/search", cooldown) == {"found": 1}
    assert cooldown.active == (seconds > http_util.SLOW_SECONDS)


@pytest.fixture
def local_site():
    """A web server here that answers every GET with "ok", and keeps its connections open (HTTP/1.1)."""

    class Answer(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_every_thread_s_idle_connections_are_closed_and_requests_go_on(local_site, monkeypatch):
    monkeypatch.setenv("DISABLE_CACHE", "1")
    http_util.reset_sessions()
    sessions, asked, done = [], threading.Event(), threading.Event()

    def pools(session):
        return sum(len(adapter.poolmanager.pools) for adapter in set(session.adapters.values()))  # (one for both)

    def live_on():  # (as the image finder's threads do: their sessions stay)
        http_util.get(local_site + "/a")
        sessions.append(http_util.get_session())
        asked.set()
        done.wait(5)

    thread = threading.Thread(target=live_on)
    thread.start()
    assert http_util.get(local_site + "/b").status_code == 200
    sessions.append(http_util.get_session())
    asked.wait(5)
    try:
        assert [pools(session) for session in sessions] == [1, 1]
        http_util.close_idle_connections()
        assert [pools(session) for session in sessions] == [0, 0]
        assert http_util.get(local_site + "/c").status_code == 200  # (on a new connection)
    finally:
        done.set()
        thread.join()
    http_util.reset_sessions()


# TRANSFERS THAT BREAK OFF


class _BreakingResponse:
    """A streamed answer whose transfer breaks off after its first chunk."""

    def __init__(self, url, first, sent):
        self.url, self.status_code, self.ok = url, 200, True
        self.headers = {"Content-Type": "image/jpeg", "Content-Length": str(10 * len(first))}
        self._first, self._sent = first, sent

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False

    def iter_content(self, chunk_size):
        yield self._first[: self._sent]
        raise requests.exceptions.ConnectionError("Read timed out.")


@pytest.mark.parametrize("check", ["download", "probe", "video probe"])
def test_a_picture_whose_transfer_breaks_off_can_t_be_used(check, monkeypatch):
    # (before it told what it is: 20 bytes of a JPEG, 4 of a video)
    sent = 4 if check == "video probe" else 20
    monkeypatch.setattr(http_util, "get", lambda url, **kwargs: _BreakingResponse(url, _jpeg(), sent))
    if check == "download":
        assert image_util._download("https://example.com/photo.jpg") is None
    elif check == "probe":
        assert image_util._probe("https://example.com/photo.jpg") is False
    else:
        assert image_util._probe_video("https://example.com/video.mp4") is False


# A FEW AT A TIME


def test_pictures_are_fetched_a_few_at_a_time_each_once(monkeypatch):
    fetching, most, loads = 0, 0, []
    lock = threading.Lock()

    def load(url, longest_side=None):
        nonlocal fetching, most
        with lock:
            fetching += 1
            most = max(most, fetching)
            loads.append(url)
        time.sleep(0.05)
        with lock:
            fetching -= 1
        return _jpeg()

    monkeypatch.setattr(image_util, "_load", load)
    urls = [f"https://example.com/{number}.jpg" for number in range(10)]
    image_util.fetch_all(urls + urls[:3])
    assert sorted(loads) == sorted(urls)
    assert most == image_util.FETCHES_AT_ONCE
    image_util.fetch_image(urls[0])  # (from the cache now)
    assert len(loads) == len(urls)


def test_one_picture_is_prepared_at_a_time(monkeypatch):
    preparing, most = 0, 0
    lock = threading.Lock()
    prepare = image_util._prepare

    def counted(data, description, longest_side=None):
        nonlocal preparing, most
        with lock:
            preparing += 1
            most = max(most, preparing)
        time.sleep(0.02)
        try:
            return prepare(data, description, longest_side)
        finally:
            with lock:
                preparing -= 1

    monkeypatch.setattr(image_util, "_prepare", counted)
    photo = _jpeg((3000, 2000))
    threads = [threading.Thread(target=image_util.prepare_image_bytes, args=(photo,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert most == 1


def test_a_powerpoint_s_pictures_are_downloaded_before_it_s_drawn(monkeypatch):
    fetched, loads = [], []
    fetch_all = image_util.fetch_all

    def spy(images, videos=()):
        fetched.append((list(images), list(videos)))
        fetch_all(images, videos)

    def load(url, longest_side=None):
        loads.append(url)
        return _jpeg()

    monkeypatch.setattr(image_util, "fetch_all", spy)
    monkeypatch.setattr(image_util, "_load", load)
    pictures = [f"https://example.com/{name}.jpg" for name in ("one", "two", "three")]
    deck = Deck(
        generator="test",
        title="Pictures",
        slides=tuple(
            DeckSlide(
                type="image",
                layout="classic/image",
                elements=(
                    TextElement(role="title", text=f"Picture {number}"),
                    ImageElement(role="content", image=ImageAsset(url=url, source="Test")),
                ),
            )
            for number, url in enumerate(pictures)
        ),
    )
    render_pptx(deck)
    assert fetched == [(pictures, [])]
    assert sorted(loads) == sorted(pictures)  # (each once: drawing found them downloaded)


# AS LARGE AS ITS PLACE NEEDS


def test_a_picture_converted_anyway_comes_out_as_large_as_its_place_needs(monkeypatch):
    decoded = []
    thumbnail = Image.Image.thumbnail

    def spy(image, size, *args, **kwargs):
        decoded.append(image.size)
        return thumbnail(image, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "thumbnail", spy)
    photo = _jpeg((4000, 3000))
    small = image_util.prepare_image_bytes(photo, longest_side=800)
    assert decoded == [(1000, 750)]  # (decoded at a quarter of its size: an eighth would be too small)
    assert image_util.get_image_size(small) == (800, 600)
    whole_slide = image_util.prepare_image_bytes(photo)
    assert image_util.get_image_size(whole_slide) == (2000, 1500)  # (as before: a slide's width at least)
    assert image_util.get_image_size(image_util.prepare_image_bytes(photo, longest_side=5000)) == (2400, 1800)
    # (a picture that isn't converted stays as it is, whatever its place)
    modest = _jpeg((1200, 900))
    assert image_util.prepare_image_bytes(modest, longest_side=300) == modest


def _element(fit, box, size=(None, None)):
    image = ImageAsset(url="https://example.com/photo.jpg", width=size[0], height=size[1])
    return ImageElement(role="content", image=image, fit=fit, box=box)


def test_a_picture_s_place_tells_how_large_it_needs_to_be():
    from talkgenerator.models.deck import Box
    from talkgenerator.render.powerpoint import picture_size

    quarter = Box(x=0, y=0, w=430, h=560)
    assert picture_size(_element("contain", quarter)) == 1120  # (twice its box's longest side)
    assert picture_size(_element("contain", None)) is None  # (the classic template's places: a slide's width)
    # (cropped to fill its box: as large as the box's sides need, for its own shape)
    assert picture_size(_element("cover", Box(x=0, y=0, w=1920, h=1080), (3000, 4000))) == 5120
    assert picture_size(_element("cover", quarter)) is None  # (its size unknown)


def test_a_powerpoint_s_pictures_come_as_large_as_their_places_need(monkeypatch):
    from talkgenerator.models.deck import Box

    asked = {}

    def load(url, longest_side=None):
        asked[url] = longest_side
        return _jpeg()

    monkeypatch.setattr(image_util, "_load", load)
    small, large = "https://example.com/small.jpg", "https://example.com/large.jpg"
    elements = [
        ImageElement(role="a", image=ImageAsset(url=small), box=Box(x=0, y=0, w=300, h=200)),
        ImageElement(role="b", image=ImageAsset(url=large), box=Box(x=0, y=0, w=300, h=200)),
        ImageElement(role="c", image=ImageAsset(url=large), box=Box(x=0, y=0, w=900, h=600)),
    ]
    from talkgenerator.render import powerpoint

    deck = Deck(generator="test", slides=(DeckSlide(type="image", layout="v5/test", elements=tuple(elements)),))
    powerpoint._fetch_pictures(deck, None)
    assert asked == {small: 600, large: 1800}  # (a picture in two places: as large as the larger one needs)
