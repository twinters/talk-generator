"""Offline tests of gifs too large to embed, which play as their video copies.

Many gifs on r/gifs are 40 to 60 MB, too large to embed, while Reddit's mp4 copy of one is a few MB. Such a gif's
slide gets the video instead: the deck names the video and its poster frame (a still of the gif), and on the
PowerPoint slide it plays by itself, looping and without sound, as the gif would. Gifs that are small enough stay gifs.
"""

import io
import logging
import struct
import zipfile
from collections import OrderedDict
from types import SimpleNamespace

import pptx
import pytest
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pydantic import ValidationError

from talkgenerator.datastructures.image_data import ImageData, VideoCopy
from talkgenerator.models.deck import Deck, DeckSlide, ImageAsset, ImageElement
from talkgenerator.render.powerpoint import render_pptx, render_slide
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.slide.slide_deck import SlideDeck
from talkgenerator.util import http_util, image_util, video_util

MB = 1024 * 1024
P = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}  # for the XML python-pptx doesn't wrap
BIG_GIF = "https://i.redd.it/big.gif"
VIDEO = "https://preview.redd.it/big.gif?format=mp4&s=video"
POSTER = "https://preview.redd.it/big.gif?format=png8&s=still"
POST = "https://www.reddit.com/r/gifs/comments/big/"
SMALL_GIF = "https://i.redd.it/small.gif"


def _box(kind, payload=b""):
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _mp4(seconds=2.5, *, version=0, more=b""):
    """An mp4, as far as talkgenerator reads one: its file type, and its movie header saying how long it plays."""
    length = round(seconds * 1000)
    times = struct.pack(">QQIQ", 0, 0, 1000, length) if version == 1 else struct.pack(">IIII", 0, 0, 1000, length)
    header = _box(b"mvhd", bytes([version, 0, 0, 0]) + times + bytes(80))
    return _box(b"ftyp", b"isom\x00\x00\x02\x00isomavc1") + _box(b"moov", header + more) + _box(b"mdat", bytes(64))


def _png(size=(400, 300)):
    output = io.BytesIO()
    Image.new("RGB", size, (200, 80, 40)).save(output, "PNG")
    return output.getvalue()


def _gif(size=(120, 90)):
    output = io.BytesIO()
    first, second = Image.new("P", size, 1), Image.new("P", size, 2)
    first.save(output, "GIF", save_all=True, append_images=[second], loop=0)
    return output.getvalue()


def _big_gif(url=BIG_GIF, video=VIDEO, poster=POSTER):
    """A gif from Reddit with its mp4 copy, as the Reddit source gives it."""
    return ImageData(url, source="u/someone (on r/gifs)", source_url=POST, video=VideoCopy(video, poster))


@pytest.fixture(autouse=True)
def empty_download_cache(monkeypatch):
    monkeypatch.setattr(image_util, "_cache", OrderedDict())
    monkeypatch.setattr(image_util, "_cache_bytes", 0)


# THE MP4 FILES


def test_an_mp4_says_how_long_it_plays():
    assert video_util.is_mp4(_mp4())
    assert not video_util.is_mp4(_gif())
    assert video_util.duration(_mp4(2.5)) == 2.5
    assert video_util.duration(_mp4(0.42, version=1)) == pytest.approx(0.42)
    assert video_util.duration(b"not a video at all") is None
    assert video_util.duration(_mp4()[:30]) is None  # cut short


def test_a_fragmented_mp4_says_how_long_it_plays_elsewhere():
    # As Reddit's DASH videos (of Imgur's .gifv) are: their movie header says 0
    extends = _box(b"mvex", _box(b"mehd", bytes(4) + struct.pack(">I", 19_000)))
    assert video_util.duration(_mp4(0, more=extends)) == 19
    reference = struct.pack(">III", 1000, 4 * 15360, 0)  # its size, its duration (at 15360 a second), where it starts
    index = _box(b"sidx", bytes(4) + struct.pack(">IIIIHH", 1, 15360, 0, 0, 0, 2) + reference * 2)
    assert video_util.duration(_mp4(0) + index) == 8


# DOWNLOADING: a gif too large to embed isn't downloaded at all, and its video copy is


class _Response:
    """A streamed answer, like requests gives: it counts how much of it is read."""

    def __init__(self, url, chunks, content_type, length):
        self.url, self.status_code, self.ok = url, 200, True
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


def _chunks(start, size, chunk_size=256 * 1024):
    """A file of the size, made up as it's read, which starts with these bytes."""
    yield start
    sent = len(start)
    while sent < size:
        chunk = bytes(min(chunk_size, size - sent))
        sent += len(chunk)
        yield chunk


@pytest.fixture
def web(monkeypatch):
    """The web, as far as http_util.get gets it: the files that serve() puts there."""
    files = {}
    answers = []

    def serve(url, body, content_type, *, size=None, says_size=True):
        """Serve the body; with size, a file of that size that starts with the body."""
        size = len(body) if size is None else size
        files[url] = (body, size, content_type, size if says_size else None)

    def get(url, **kwargs):
        if url not in files:
            answers.append((url, None))
            return None
        body, size, content_type, length = files[url]
        answer = _Response(url, _chunks(body, size), content_type, length)
        answers.append((url, answer))
        return answer

    def read(url):
        return sum(answer.read for requested, answer in answers if requested == url and answer is not None)

    monkeypatch.setattr(http_util, "get", get)
    return SimpleNamespace(serve=serve, read=read, requested=lambda: [url for url, _ in answers])


def test_a_gif_too_large_to_embed_isnt_downloaded(web):
    web.serve(BIG_GIF, b"GIF89a", "image/gif", size=50 * MB)
    assert image_util.fetch_image(BIG_GIF) is None
    assert web.read(BIG_GIF) <= 256 * 1024  # its first bytes, which say it's a gif


def test_a_gif_that_doesnt_say_its_size_is_downloaded_up_to_its_limit(web):
    web.serve(BIG_GIF, b"GIF89a", "image/gif", size=50 * MB, says_size=False)
    assert image_util.fetch_image(BIG_GIF) is None
    assert web.read(BIG_GIF) <= image_util.MAX_GIF_BYTES + 256 * 1024


def test_the_gif_limit_is_for_gifs(web):
    # A photo too large for a slide is scaled down, while a gif is embedded as it is, to keep moving
    size = image_util.MAX_GIF_BYTES + MB
    web.serve("https://example.com/photo.jpg", b"\xff\xd8\xff", "image/jpeg", size=size)
    web.serve("https://example.com/long.gif", b"GIF89a", "image/gif", size=size)
    downloaded = image_util._download("https://example.com/photo.jpg")
    assert downloaded is not None and len(downloaded) == size
    assert image_util._download("https://example.com/long.gif") is None


def test_videos_are_mp4s_small_enough_to_embed(web):
    web.serve(VIDEO, _mp4(), "video/mp4")
    web.serve("https://example.com/long.mp4", _mp4(), "video/mp4", size=image_util.MAX_VIDEO_BYTES + 1)
    web.serve("https://example.com/removed.mp4", b"<html>This video was removed</html>", "text/html")
    web.serve("https://example.com/cat.webm", b"\x1aE\xdf\xa3" + bytes(100), "video/webm")

    assert image_util.fetch_video(VIDEO) == _mp4()
    assert image_util.fetch_video("https://example.com/long.mp4") is None
    assert web.read("https://example.com/long.mp4") <= 256 * 1024
    assert image_util.fetch_video("https://example.com/removed.mp4") is None
    assert image_util.fetch_video("https://example.com/cat.webm") is None
    assert image_util.fetch_video("C:/Users/someone/cat.mp4") is None  # videos come from the web


def test_a_gif_too_large_to_embed_plays_as_its_video_copy(web):
    web.serve(BIG_GIF, b"GIF89a", "image/gif", size=50 * MB)
    web.serve(POSTER, _png(), "image/png")
    web.serve(VIDEO, _mp4(), "video/mp4")
    image = _big_gif()

    assert image_util.fetch_image_data(image) == _png()  # what the image checks get: its poster frame
    assert image.video_data == _mp4()
    assert image.get_shown_url() == POSTER
    assert image.get_image_url() == BIG_GIF  # still the same image, to tell repeats by
    assert image == _big_gif()


def test_a_gif_small_enough_stays_a_gif(web):
    web.serve(SMALL_GIF, _gif(), "image/gif")
    image = _big_gif(SMALL_GIF)

    assert image_util.fetch_image_data(image) == _gif()
    assert image.video_data is None
    assert image.get_shown_url() == SMALL_GIF
    assert web.requested() == [SMALL_GIF]  # its video copy isn't even downloaded


@pytest.mark.parametrize("missing", [VIDEO, POSTER], ids=["no video", "no poster frame"])
def test_a_gif_too_large_without_a_usable_copy_is_left_out(web, missing):
    web.serve(BIG_GIF, b"GIF89a", "image/gif", size=50 * MB)
    if missing != POSTER:
        web.serve(POSTER, _png(), "image/png")
    if missing != VIDEO:
        web.serve(VIDEO, _mp4(), "video/mp4")
    image = _big_gif()

    assert image_util.fetch_image_data(image) is None
    assert image.video_data is None
    assert slides.FullImageSlide("Look at this", image).missing_content() == ["image_url"]  # another image, then


# THE DECK AND THE SLIDE


@pytest.fixture
def served(monkeypatch):
    """What the web serves, by URL: images through fetch_image (not the gif too large to embed), videos through
    fetch_video. Local files (such as the overlay of quote slides) load as usual."""
    images = {POSTER: _png((400, 300)), SMALL_GIF: _gif()}
    videos = {VIDEO: _mp4(2.5)}
    load = image_util.fetch_image
    monkeypatch.setattr(image_util, "fetch_image", lambda url: images.get(url) if url.startswith("http") else load(url))
    monkeypatch.setattr(image_util, "fetch_video", lambda url: videos.get(url))
    return SimpleNamespace(images=images, videos=videos)


def _presentation():
    return powerpoint_slide_creator.create_new_powerpoint()


def _movies(ppt_slide):
    return [shape for shape in ppt_slide.shapes if shape.shape_type == MSO_SHAPE_TYPE.MEDIA]


def _video_part(ppt_slide, movie):
    return ppt_slide.part.related_part(movie._element.xpath("./p:nvPicPr/p:nvPr/a:videoFile/@r:link")[0])


def _frame(presentation, layout, placeholder_id):
    """Where a layout's placeholder is: (left, top, width, height)."""
    placeholders = presentation.slide_layouts[layout].placeholders
    placeholder = next(shape for shape in placeholders if shape.placeholder_format.idx == placeholder_id)
    return placeholder.left, placeholder.top, placeholder.width, placeholder.height


def test_a_deck_says_which_image_plays_as_a_video(served):
    element = slides.FullImageSlide("Look at this", _big_gif()).to_deck_slide().element("content")

    assert isinstance(element, ImageElement)
    assert (element.image.url, element.image.video_url) == (POSTER, VIDEO)
    assert (element.image.source, element.image.source_url) == ("u/someone (on r/gifs)", POST)


def test_a_gif_small_enough_stays_a_gif_in_the_deck_and_on_the_slide(served):
    slide = slides.FullImageSlide("Look at this", _big_gif(SMALL_GIF))

    element = slide.to_deck_slide().element("content")
    assert (element.image.url, element.image.video_url) == (SMALL_GIF, None)
    ppt_slide = slide.create_powerpoint_slide(_presentation())
    assert not _movies(ppt_slide)
    assert ppt_slide.element.find(qn("p:timing")) is None


def test_the_deck_format_has_videos():
    assert "video_url" in Deck.json_schema()["$defs"]["ImageAsset"]["properties"]
    assert ImageAsset(url="https://example.com/cat.jpg").video_url is None
    with pytest.raises(ValidationError):
        ImageAsset(url=POSTER, video=VIDEO)


def test_a_gif_too_large_to_embed_plays_on_its_slide(served):
    ppt_slide = slides.FullImageSlide("Look at this", _big_gif()).create_powerpoint_slide(_presentation())

    (movie,) = _movies(ppt_slide)
    part = _video_part(ppt_slide, movie)
    assert (part.content_type, part.blob) == ("video/mp4", _mp4(2.5))
    assert part.partname.endswith(".mp4")
    assert movie.poster_frame.blob == served.images[POSTER]
    assert len(ppt_slide.element.xpath(".//p:pic")) == 1  # the video took the picture's place


def test_the_video_plays_by_itself_and_loops_without_sound(served):
    ppt_slide = slides.FullImageSlide("Look at this", _big_gif()).create_powerpoint_slide(_presentation())
    (movie,) = _movies(ppt_slide)
    spid = str(movie.shape_id)
    (timing,) = ppt_slide.element.findall(qn("p:timing"))

    # PowerPoint's "Start: Automatically": a Play effect in a step that starts with the main sequence (cTn 2), which
    # starts with the slide, instead of on a click
    (step,) = timing.xpath("./p:tnLst/p:par/p:cTn/p:childTnLst/p:seq/p:cTn[@nodeType='mainSeq']/p:childTnLst/p:par")
    assert step.xpath("./p:cTn/p:stCondLst/p:cond/@delay", namespaces=P) == ["indefinite", "0"]
    assert step.xpath("./p:cTn/p:stCondLst/p:cond[@evt='onBegin']/p:tn/@val", namespaces=P) == ["2"]
    (play,) = timing.xpath(".//p:cTn[@presetClass='mediacall']")
    assert (play.get("presetID"), play.get("nodeType")) == ("1", "afterEffect")
    (command,) = play.xpath(".//p:cmd", namespaces=P)
    assert (command.get("type"), command.get("cmd")) == ("call", "playFrom(0.0)")
    assert command.xpath("./p:cBhvr/p:cTn/@dur", namespaces=P) == ["2500"]  # as long as the video plays
    assert command.xpath(".//p:spTgt/@spid", namespaces=P) == [spid]
    # "Loop until Stopped" and "Mute", instead of python-pptx's timing, which waits for a click
    (media,) = timing.xpath("./p:tnLst/p:par/p:cTn/p:childTnLst/p:video/p:cMediaNode")
    assert media.get("mute") == "1"
    assert media.xpath("./p:cTn/@repeatCount", namespaces=P) == ["indefinite"]
    assert media.xpath("./p:tgtEl/p:spTgt/@spid", namespaces=P) == [spid]
    ids = timing.xpath(".//p:cTn/@id")
    assert len(ids) == len(set(ids))
    # The timing goes after the colour map, as PowerPoint wants
    tags = [child.tag for child in ppt_slide.element]
    assert tags.index(qn("p:timing")) > tags.index(qn("p:clrMapOvr"))


def test_two_videos_on_a_slide_play_together(served):
    other_video, other_poster = "https://preview.redd.it/other.gif?format=mp4", "https://preview.redd.it/other.png"
    served.videos[other_video], served.images[other_poster] = _mp4(4), _png((300, 400))
    other = _big_gif("https://i.redd.it/other.gif", other_video, other_poster)
    slide = slides.TwoColumnImageSlide("Cats", "Expectation", _big_gif(), "Reality", other)

    ppt_slide = slide.create_powerpoint_slide(_presentation())

    movies = _movies(ppt_slide)
    assert [_video_part(ppt_slide, movie).blob for movie in movies] == [_mp4(2.5), _mp4(4)]
    plays = ppt_slide.element.xpath(".//p:timing//p:cTn[@presetClass='mediacall']")
    assert [play.get("nodeType") for play in plays] == ["afterEffect", "withEffect"]  # the second with the first
    played = [play.xpath(".//p:spTgt/@spid", namespaces=P)[0] for play in plays]
    assert played == [str(movie.shape_id) for movie in movies]
    assert [play.xpath(".//p:cmd/p:cBhvr/p:cTn/@dur", namespaces=P)[0] for play in plays] == ["2500", "4000"]
    looping = ppt_slide.element.xpath(".//p:timing//p:video/p:cMediaNode/p:cTn/@repeatCount")
    assert looping == ["indefinite", "indefinite"]
    ids = ppt_slide.element.xpath(".//p:timing//p:cTn/@id")
    assert len(ids) == len(set(ids))


def test_a_video_shown_whole_has_the_shape_of_its_gif(served):
    presentation = _presentation()
    (movie,) = _movies(slides.ImageSlide("Look at this", _big_gif()).create_powerpoint_slide(presentation))

    # As large as fits in the middle of the picture's frame, with the poster's 4:3, uncropped
    left, top, width, height = _frame(presentation, powerpoint_slide_creator.LAYOUT_TITLE_AND_PICTURE, 1)
    assert movie.width / movie.height == pytest.approx(400 / 300, rel=1e-3)
    assert max(movie.width / width, movie.height / height) == pytest.approx(1, abs=1e-6)
    assert movie.left + movie.width / 2 == pytest.approx(left + width / 2, abs=1)
    assert movie.top + movie.height / 2 == pytest.approx(top + height / 2, abs=1)
    assert (movie.crop_left, movie.crop_right, movie.crop_top, movie.crop_bottom) == (0, 0, 0, 0)


def test_a_video_filling_its_frame_is_cropped_like_its_picture(served):
    presentation = _presentation()
    still = slides.FullImageSlide(None, ImageData(POSTER), original_image_size=False)
    (picture,) = [shape for shape in still.create_powerpoint_slide(presentation).shapes if hasattr(shape, "image")]

    video = slides.FullImageSlide(None, _big_gif(), original_image_size=False)
    (movie,) = _movies(video.create_powerpoint_slide(presentation))

    assert (movie.left, movie.top, movie.width, movie.height) == (
        picture.left,
        picture.top,
        picture.width,
        picture.height,
    )
    crops = (picture.crop_left, picture.crop_right, picture.crop_top, picture.crop_bottom)
    assert any(crops)  # a 4:3 still on a 16:9 slide
    assert (movie.crop_left, movie.crop_right, movie.crop_top, movie.crop_bottom) == crops


def test_a_video_behind_a_quote_stays_under_its_overlay(served):
    slide = slides.LarqeQuoteSlide(None, "Be brave, little gif", background_image=_big_gif())

    shapes = list(slide.create_powerpoint_slide(_presentation()).shapes)

    (movie,) = [shape for shape in shapes if shape.shape_type == MSO_SHAPE_TYPE.MEDIA]
    (overlay,) = [shape for shape in shapes if hasattr(shape, "image")]  # the transparent black over the background
    assert shapes.index(movie) < shapes.index(overlay)


def test_the_video_checked_while_generating_is_the_one_on_the_slide(served):
    slide = slides.FullImageSlide("Look at this", _big_gif())
    assert slide.missing_content() == []  # it plays as its video
    served.images.clear()
    served.videos.clear()  # gone from the web, and from the download cache

    ppt_slide = slide.create_powerpoint_slide(_presentation())

    (movie,) = _movies(ppt_slide)
    assert _video_part(ppt_slide, movie).blob == _mp4(2.5)


def test_a_deck_with_a_video_survives_json_and_renders_on_its_own(served):
    slide_deck = SlideDeck(1, title="Gifs")
    slide_deck.add_slide(0, slides.FullImageSlide("Look at this", _big_gif()))
    (drawn,) = slide_deck.save_to_powerpoint(_presentation())
    assert len(_movies(drawn)) == 1
    deck = slide_deck.to_deck()
    text = deck.to_json()
    assert Deck.from_json(text) == deck
    assert f'"video_url": "{VIDEO}"' in text

    (ppt_slide,) = render_pptx(Deck.from_json(text)).slides  # without the generation run: downloaded again

    (movie,) = _movies(ppt_slide)
    assert movie.poster_frame.blob == served.images[POSTER]
    assert _video_part(ppt_slide, movie).blob == _mp4(2.5)


def test_a_video_that_cant_be_downloaded_shows_its_poster_frame(served, caplog):
    caplog.set_level(logging.WARNING, logger="talkgenerator")
    image = ImageAsset(url=POSTER, video_url="https://preview.redd.it/gone.gif?format=mp4")
    deck_slide = DeckSlide(
        type="full_image", layout="classic/full_image", elements=(ImageElement(role="content", image=image),)
    )

    ppt_slide = render_slide(_presentation(), deck_slide)

    assert not _movies(ppt_slide)
    assert len(ppt_slide.element.xpath(".//p:pic")) == 1  # the still
    assert ppt_slide.element.find(qn("p:timing")) is None
    assert "as its poster frame" in caplog.text


def test_a_pptx_with_a_video_saves_and_opens_again(served):
    presentation = _presentation()
    ppt_slide = slides.FullImageSlide("Look at this", _big_gif()).create_powerpoint_slide(presentation)
    partname = _video_part(ppt_slide, _movies(ppt_slide)[0]).partname
    output = io.BytesIO()
    presentation.save(output)

    reopened = pptx.Presentation(io.BytesIO(output.getvalue()))
    assert len(_movies(reopened.slides[len(reopened.slides) - 1])) == 1
    with zipfile.ZipFile(output) as archive:
        assert archive.read(partname.lstrip("/")) == _mp4(2.5)
        assert 'ContentType="video/mp4"' in archive.read("[Content_Types].xml").decode()
