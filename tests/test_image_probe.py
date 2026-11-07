"""Offline tests of probing images (talkgenerator.util.image_util.probing): while a talk streams, an image is checked
from its first bytes, as a download would check it, without downloading it whole.

A fake web serves files that are made up as they're read, and counts how much of each is read.
"""

import io
import os
import struct
import threading
from collections import OrderedDict
from types import SimpleNamespace

import pytest
from PIL import Image

from talkgenerator.datastructures.image_data import ImageData, VideoCopy
from talkgenerator.util import http_util, image_util, os_util

MB = 1024 * 1024
KB = 1024


class _Response:
    """A streamed answer, like requests gives: it counts how much of it is read."""

    def __init__(self, url, chunks, content_type, length, status):
        self.url, self.status_code, self.ok = url, status, status == 200
        self.headers = {"Content-Type": content_type}
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self._chunks = chunks
        self.read = 0

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False

    def iter_content(self, chunk_size):
        for chunk in self._chunks:
            self.read += len(chunk)
            yield chunk


def _chunks(start, size, chunk_size=64 * KB):
    """A file of the size, made up as it's read in chunks, which starts with these bytes."""
    for offset in range(0, len(start), chunk_size):
        yield start[offset : offset + chunk_size]
    sent = len(start)
    while sent < size:
        chunk = bytes(min(chunk_size, size - sent))
        sent += len(chunk)
        yield chunk


@pytest.fixture
def web(monkeypatch):
    """The web, as far as http_util.get gets it: the files that serve() puts there. Nothing probed or downloaded
    before is remembered."""
    files = {}
    answers = []

    def serve(url, body, content_type, *, size=None, says_size=True, status=200, final_url=None):
        """Serve the body; with size, a file of that size that starts with the body."""
        size = len(body) if size is None else size
        files[url] = (body, size, content_type, size if says_size else None, status, final_url or url)

    def get(url, **kwargs):
        if url not in files:
            answers.append((url, None))
            return None
        body, size, content_type, length, status, final_url = files[url]
        answer = _Response(final_url, _chunks(body, size), content_type, length, status)
        answers.append((url, answer))
        return answer

    def read(url):
        return sum(answer.read for requested, answer in answers if requested == url and answer is not None)

    monkeypatch.setattr(http_util, "get", get)
    monkeypatch.setattr(image_util, "_probed", OrderedDict())
    monkeypatch.setattr(image_util, "_cache", OrderedDict())
    monkeypatch.setattr(image_util, "_cache_bytes", 0)
    return SimpleNamespace(serve=serve, read=read)


def _image(size=(800, 600), image_format="JPEG", **options):
    output = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(output, image_format, **options)
    return output.getvalue()


def _animated_webp():
    frames = [Image.new("RGB", (640, 360), colour) for colour in ((200, 30, 30), (30, 200, 30))]
    output = io.BytesIO()
    frames[0].save(output, "WEBP", save_all=True, append_images=frames[1:], duration=100)
    return output.getvalue()


def _mp4():
    box = struct.pack(">I", 16) + b"ftypisom" + bytes(4)
    return box + bytes(100)


@pytest.mark.parametrize(
    ("name", "body", "content_type"),
    [
        ("photo.jpg", _image(image_format="JPEG"), "image/jpeg"),
        ("drawing.png", _image(image_format="PNG"), "image/png"),
        ("loop.gif", _image(image_format="GIF"), "image/gif"),
        ("lossy.webp", _image(image_format="WEBP", quality=80), "image/webp"),
        ("lossless.webp", _image(image_format="WEBP", lossless=True), "image/webp"),
        ("animated.webp", _animated_webp(), "image/webp"),
        ("bitmap.bmp", _image(size=(300, 200), image_format="BMP"), "image/bmp"),
    ],
)
def test_an_image_is_checked_from_its_first_bytes(web, name, body, content_type):
    url = f"https://example.com/{name}"
    web.serve(url, body, content_type, size=5 * MB)

    assert image_util.probe(url)

    assert web.read(url) <= 64 * KB  # (only its first chunk, of the five megabytes)
    read = web.read(url)
    assert image_util.probe(url) and web.read(url) == read  # remembered


def test_what_a_probe_turns_down(web):
    jpeg = _image()
    web.serve("https://example.com/page.jpg", b"<html>Not here</html>" + bytes(100), "text/html")
    web.serve("https://example.com/gone.jpg", jpeg, "image/jpeg", status=404)
    web.serve("https://example.com/moved.jpg", jpeg, "image/png", final_url="https://i.imgur.com/removed.png")
    web.serve("https://example.com/icon.png", _image(size=(20, 20), image_format="PNG"), "image/png", size=MB)
    web.serve("https://example.com/scan.tiff", _image(image_format="TIFF"), "image/tiff", size=MB)
    web.serve("https://example.com/huge.jpg", jpeg, "image/jpeg", size=image_util.MAX_DOWNLOAD_BYTES + 1)
    web.serve("https://example.com/long.gif", _image(image_format="GIF"), "image/gif", size=50 * MB)

    for name in ("page.jpg", "gone.jpg", "moved.jpg", "icon.png", "scan.tiff", "huge.jpg", "long.gif"):
        url = f"https://example.com/{name}"
        assert not image_util.probe(url), name
        assert web.read(url) <= 64 * KB, name  # (none was downloaded whole)
    assert not image_util.probe("https://example.com/nowhere.jpg")


def test_a_small_file_is_checked_whole(web):
    # The whole file came with the first bytes: checked as a download is, also for a known placeholder
    placeholder = os_util.to_actual_file("data/prohibited_images/imgur_removed.jpg")
    with open(placeholder, "rb") as file:
        web.serve("https://example.com/small.png", file.read(), "image/png")
    assert not image_util.probe("https://example.com/small.png")


def test_an_image_shaped_like_a_placeholder_is_downloaded_whole(web):
    # Imgur's "image removed" picture, in a file larger than what's read at first: downloaded to compare it
    placeholder = os_util.to_actual_file("data/prohibited_images/imgur_removed.jpg")
    with open(placeholder, "rb") as file:
        body = file.read()
    web.serve("https://example.com/maybe-gone.png", body, "image/png", size=200 * KB)
    assert not image_util.probe("https://example.com/maybe-gone.png")
    assert web.read("https://example.com/maybe-gone.png") > 200 * KB  # (probed, then downloaded whole)

    # One of the same shape that isn't it passes
    web.serve("https://example.com/banner.png", _image(size=(161, 81), image_format="PNG"), "image/png", size=200 * KB)
    assert image_util.probe("https://example.com/banner.png")


def test_an_image_that_tells_its_size_late_is_downloaded_whole(web):
    # A JPEG with more than half a megabyte of metadata before its frame (and so its size)
    jpeg = _image()
    metadata = b"".join(b"\xff\xef" + struct.pack(">H", 65535) + bytes(65533) for _ in range(9))
    late = jpeg[:2] + metadata + jpeg[2:]
    web.serve("https://example.com/late.jpg", late, "image/jpeg", size=len(late))
    assert image_util.probe("https://example.com/late.jpg")
    assert web.read("https://example.com/late.jpg") > len(late)  # (probed, then downloaded whole)


@pytest.mark.filterwarnings("ignore:image file could not be identified")  # (a Pillow without AVIF support)
def test_an_avif_is_downloaded_whole(web):
    avif = struct.pack(">I", 28) + b"ftypavif" + bytes(16) + bytes(1000)
    web.serve("https://example.com/new.avif", avif, "image/avif", size=len(avif))
    image_util.probe("https://example.com/new.avif")  # (whether it can be used depends on Pillow's AVIF support)
    assert web.read("https://example.com/new.avif") >= 2 * len(avif)


def test_a_gif_too_large_to_embed_plays_its_video_copy_when_probed(web):
    gif = "https://example.com/long.gif"
    video = VideoCopy(url="https://example.com/long.mp4", poster_url="https://example.com/long-poster.jpg")
    web.serve(gif, _image(image_format="GIF"), "image/gif", size=50 * MB)
    web.serve(video.poster_url, _image(), "image/jpeg", size=MB)
    web.serve(video.url, _mp4(), "video/mp4", size=2 * MB)
    image = ImageData(gif, video=video)

    with image_util.probing():
        assert image_util.check_image(image)

    assert image.plays_video and image.get_shown_url() == video.poster_url
    assert (image.data, image.video_data) == (None, None)  # nothing downloaded whole
    assert web.read(video.url) <= 64 * KB
    # A PowerPoint downloads them
    assert image_util.fetch_image_data(image) is not None and image.video_data is not None


def test_a_video_copy_too_large_isnt_used(web):
    gif = "https://example.com/long.gif"
    video = VideoCopy(url="https://example.com/huge.mp4", poster_url="https://example.com/huge-poster.jpg")
    web.serve(gif, _image(image_format="GIF"), "image/gif", size=50 * MB)
    web.serve(video.poster_url, _image(), "image/jpeg", size=MB)
    web.serve(video.url, _mp4(), "video/mp4", size=image_util.MAX_VIDEO_BYTES + 1)
    with image_util.probing():
        assert not image_util.check_image(ImageData(gif, video=video))
    assert web.read(video.url) <= 64 * KB


def test_probing_reaches_the_threads_that_carry_it(web):
    web.serve("https://example.com/photo.jpg", _image(), "image/jpeg", size=5 * MB)
    checked = []

    def check():
        checked.append(image_util.check_image(ImageData("https://example.com/photo.jpg")))

    with image_util.probing():
        thread = threading.Thread(target=image_util.carry(check))
    thread.start()
    thread.join()

    assert checked == [True]
    assert web.read("https://example.com/photo.jpg") < 64 * KB  # probed, not downloaded whole


def test_without_probing_images_are_downloaded(web):
    web.serve("https://example.com/photo.jpg", _image(), "image/jpeg", size=2 * MB)
    image = ImageData("https://example.com/photo.jpg")
    assert image_util.check_image(image) and image.data is not None
    assert web.read("https://example.com/photo.jpg") == 2 * MB


def test_local_files_are_read_as_they_are(web):
    with image_util.probing():
        assert image_util.is_usable_image(os_util.to_actual_file("data/images/black-transparent.png"))
        assert not image_util.is_usable_image(os.path.join("nowhere", "missing.png"))


def test_a_probe_and_a_download_tell_the_same_size(web):
    # The original's, also when the bytes for a PowerPoint are scaled down
    body = _image(size=(4000, 3000))
    web.serve("https://example.com/probed.jpg", body, "image/jpeg")
    web.serve("https://example.com/downloaded.jpg", body, "image/jpeg")
    probed, downloaded = ImageData("https://example.com/probed.jpg"), ImageData("https://example.com/downloaded.jpg")

    with image_util.probing():
        assert image_util.check_image(probed)
    assert image_util.check_image(downloaded)

    assert probed.size == downloaded.size == (4000, 3000)
    assert max(image_util.get_image_size(downloaded.data)) == image_util.MAX_DIMENSION  # (scaled down to embed)


def test_an_image_that_plays_its_video_has_its_posters_size(web):
    gif = "https://example.com/long.gif"
    video = VideoCopy(url="https://example.com/long.mp4", poster_url="https://example.com/long-poster.jpg")
    web.serve(gif, _image(image_format="GIF"), "image/gif", size=50 * MB)
    web.serve(video.poster_url, _image(size=(640, 360)), "image/jpeg", size=MB)
    web.serve(video.url, _mp4(), "video/mp4", size=2 * MB)
    image = ImageData(gif, video=video)
    with image_util.probing():
        assert image_util.check_image(image)
    assert image.size == (640, 360)


def test_a_server_can_forget_the_images_it_downloaded(web):
    url = "https://example.com/photo.jpg"
    web.serve(url, _image(), "image/jpeg", size=2 * MB)
    assert image_util.fetch_image(url) is not None
    assert image_util.fetch_image(url) is not None and web.read(url) == 2 * MB  # (the second from the cache)

    image_util.forget_downloads()

    assert image_util._cache_bytes == 0
    assert image_util.fetch_image(url) is not None and web.read(url) == 4 * MB  # (downloaded again)


def test_the_deck_tells_an_images_size(web):
    from talkgenerator.slide import slides

    web.serve("https://example.com/photo.jpg", _image(size=(1200, 800)), "image/jpeg", size=2 * MB)
    with image_util.probing():
        asset = slides._to_image_asset(ImageData("https://example.com/photo.jpg"))
    assert (asset.width, asset.height) == (1200, 800)
    assert '"width":1200' in asset.model_dump_json()
