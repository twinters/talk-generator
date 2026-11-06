"""Offline tests of picking the image out of Reddit posts."""

from types import SimpleNamespace

import pytest

from talkgenerator.datastructures.image_data import VideoCopy
from talkgenerator.schema.content_generator_structures import RedditImageSearcher
from talkgenerator.sources import reddit
from talkgenerator.util import http_util


def _post(**data):
    data.setdefault("subreddit_name_prefixed", "r/pics")
    return SimpleNamespace(**data)


def _preview(source_url, gif_url=None, mp4_url=None, video_preview_url=None):
    """The `preview` of a post, as Reddit's API returns it (with HTML-escaped URLs)."""
    image = {"source": {"url": source_url, "width": 1200, "height": 900}, "resolutions": [], "variants": {}}
    if gif_url:
        image["variants"]["gif"] = {"source": {"url": gif_url}, "resolutions": []}
    if mp4_url:
        image["variants"]["mp4"] = {"source": {"url": mp4_url}, "resolutions": []}
    preview = {"images": [image], "enabled": True}
    if video_preview_url:
        preview["reddit_video_preview"] = {"fallback_url": video_preview_url, "is_gif": True, "duration": 19}
    return preview


def test_direct_image_link():
    post = _post(url="https://i.redd.it/abc.jpeg")
    assert reddit.get_image_url(post) == "https://i.redd.it/abc.jpeg"


def test_reddit_hosted_image_link_is_used_as_it_is():
    post = _post(
        url="https://i.redd.it/abc.jpeg", preview=_preview("https://preview.redd.it/abc.jpeg?auto=webp&amp;s=x")
    )
    assert reddit.get_image_url(post) == "https://i.redd.it/abc.jpeg"


@pytest.mark.parametrize(
    "url", ["https://i.imgur.com/abc.jpg", "https://I.IMGUR.COM/ABC.PNG", "https://i.ibb.co/x/y.jpeg"]
)
def test_image_hosted_elsewhere_comes_from_reddits_copy(url):
    # i.imgur.com answers talkgenerator.com's server with HTTP 429, while Reddit's copy downloads fine
    post = _post(url=url, preview=_preview("https://external-preview.redd.it/abc.jpg?auto=webp&amp;s=x"))
    assert reddit.get_image_url(post) == "https://external-preview.redd.it/abc.jpg?auto=webp&s=x"


def test_crosspost_of_an_imgur_image_comes_from_reddits_copy():
    post = _post(
        url="https://www.reddit.com/r/pics/comments/abc/title/",
        url_overridden_by_dest="https://i.imgur.com/abc.jpg",
        preview=_preview("https://external-preview.redd.it/abc.jpg?auto=webp&amp;s=x"),
    )
    assert reddit.get_image_url(post) == "https://external-preview.redd.it/abc.jpg?auto=webp&s=x"


def test_gif_hosted_elsewhere_comes_from_reddits_animated_copy():
    post = _post(
        url="https://i.imgur.com/abc.gif",
        preview=_preview(
            "https://external-preview.redd.it/abc.gif?format=png8&amp;s=still",
            gif_url="https://external-preview.redd.it/abc.gif?s=animated",
        ),
    )
    assert reddit.get_image_url(post) == "https://external-preview.redd.it/abc.gif?s=animated"


def test_gif_without_an_animated_copy_keeps_its_link():
    # The preview's source image is a still of the gif's first frame
    post = _post(
        url="https://i.imgur.com/abc.gif",
        preview=_preview("https://external-preview.redd.it/abc.gif?format=png8&amp;s=still"),
    )
    assert reddit.get_image_url(post) == "https://i.imgur.com/abc.gif"


@pytest.mark.parametrize(
    "preview",
    [None, {}, {"images": []}, {"images": [{"source": {}, "variants": {}}]}],
    ids=["no preview", "empty preview", "no preview images", "no source URL"],
)
def test_image_hosted_elsewhere_keeps_its_link_without_a_copy(preview):
    post = _post(url="https://i.imgur.com/abc.jpg", preview=preview)
    assert reddit.get_image_url(post) == "https://i.imgur.com/abc.jpg"


def test_videos_are_skipped():
    assert reddit.get_image_url(_post(url="https://v.redd.it/abc", is_video=True)) is None


def test_gallery_uses_first_image():
    post = _post(
        url="https://www.reddit.com/gallery/abc",
        is_gallery=True,
        gallery_data={"items": [{"media_id": "two"}, {"media_id": "one"}]},
        media_metadata={
            "one": {"status": "valid", "e": "Image", "s": {"u": "https://preview.redd.it/one.jpg?width=640&amp;s=x"}},
            "two": {"status": "valid", "e": "Image", "s": {"u": "https://preview.redd.it/two.jpg?width=640&amp;s=y"}},
        },
    )
    assert reddit.get_image_url(post) == "https://preview.redd.it/two.jpg?width=640&s=y"


def test_link_post_uses_preview():
    post = _post(
        url="https://imgur.com/a/abc",
        preview={"images": [{"source": {"url": "https://preview.redd.it/p.jpg?auto=webp&amp;s=z"}}]},
    )
    assert reddit.get_image_url(post) == "https://preview.redd.it/p.jpg?auto=webp&s=z"


def test_text_post_has_no_image():
    assert reddit.get_image_url(_post(url="https://www.reddit.com/r/pics/comments/abc/title/")) is None


def test_source_name_with_deleted_author():
    assert reddit.get_source_name(_post(author=None)) == "Reddit (r/pics)"
    assert reddit.get_source_name(_post(author=SimpleNamespace(name="someone"))) == "u/someone (on r/pics)"


# GIFS


def test_a_gifv_comes_from_reddits_animated_copy():
    post = _post(
        url="https://i.imgur.com/AbC12.gifv",
        preview=_preview("https://external-preview.redd.it/x.jpg", gif_url="https://external-preview.redd.it/x.gif"),
    )
    assert reddit.get_image_url(post) == "https://external-preview.redd.it/x.gif"


def test_a_gifv_without_an_animated_copy_comes_from_imgur_itself():
    # Reddit's preview of it is a still of its first frame: the gif is still at Imgur
    post = _post(url="https://imgur.com/AbC12.gifv", preview=_preview("https://external-preview.redd.it/x.jpg"))
    assert reddit.get_image_url(post) == "https://i.imgur.com/AbC12.gif"


@pytest.mark.parametrize(
    ("data", "gif"),
    [
        ({"url": "https://i.redd.it/abc.gif"}, "https://i.redd.it/abc.gif"),
        ({"url": "https://i.redd.it/abc.jpg"}, None),
        ({"url": "https://i.imgur.com/abc12.jpg", "preview": _preview("https://external-preview.redd.it/x.jpg")}, None),
        (
            {
                "url": "https://www.reddit.com/r/gifs/x",
                "preview": _preview("https://p/x.jpg", gif_url="https://p/x.gif"),
            },
            "https://p/x.gif",
        ),
        ({"url": "https://www.reddit.com/r/gifs/x", "preview": _preview("https://p/x.jpg")}, None),
        ({"url": "https://imgur.com/AbC12"}, "https://i.imgur.com/AbC12.gif"),
    ],
)
def test_for_gifs_only_what_moves_counts(data, gif):
    assert reddit.get_image_url(_post(**data), animated=True) == gif


def _big_gif_post(**data):
    """A gif on Reddit, as r/gifs has them: Reddit's mp4 copy of it in the preview, and a PNG still of it."""
    data.setdefault("url", "https://i.redd.it/big.gif")
    data.setdefault(
        "preview",
        _preview(
            "https://preview.redd.it/big.gif?format=png8&amp;s=still",
            gif_url="https://preview.redd.it/big.gif?s=animated",
            mp4_url="https://preview.redd.it/big.gif?format=mp4&amp;s=video",
        ),
    )
    return _post(subreddit_name_prefixed="r/gifs", permalink="/r/gifs/comments/big/", **data)


def test_a_gif_comes_with_reddits_mp4_copy_and_a_still_of_it():
    assert reddit.get_video_copy(_big_gif_post()) == (
        "https://preview.redd.it/big.gif?format=mp4&s=video",
        "https://preview.redd.it/big.gif?format=png8&s=still",
    )


def test_a_gifv_comes_with_reddits_video_preview():
    # Imgur's .gifv: Reddit has no gif or mp4 variant of it, but a DASH video it made
    post = _post(
        url="https://i.imgur.com/AbC12.gifv",
        preview=_preview(
            "https://external-preview.redd.it/x.jpg?auto=webp&amp;s=still",
            video_preview_url="https://v.redd.it/x/DASH_480.mp4",
        ),
    )
    assert reddit.get_image_url(post, animated=True) == "https://i.imgur.com/AbC12.gif"
    assert reddit.get_video_copy(post) == (
        "https://v.redd.it/x/DASH_480.mp4",
        "https://external-preview.redd.it/x.jpg?auto=webp&s=still",
    )


@pytest.mark.parametrize(
    "preview",
    [
        None,
        _preview("https://p/x.jpg"),
        _preview("https://p/x.gif", gif_url="https://p/x.gif?s=animated"),
        {"images": [{"variants": {"mp4": {"source": {"url": "https://p/x.mp4"}}}}]},
    ],
    ids=["no preview", "a photo", "a gif without an mp4 copy", "no still for a poster frame"],
)
def test_without_an_mp4_copy_and_a_still_theres_no_video(preview):
    assert reddit.get_video_copy(_post(url="https://i.redd.it/abc.gif", preview=preview)) is None


class _Subreddit:
    def __init__(self, posts):
        self.posts = posts

    def search(self, query, sort, limit):
        return self.posts

    def hot(self, limit):
        return self.posts


@pytest.fixture
def subreddit(monkeypatch):
    """Answer searches with the given posts."""

    def install(*posts):
        monkeypatch.setattr(reddit, "_cooldown", http_util.Cooldown("Reddit (test)"))
        monkeypatch.setattr(reddit, "has_reddit_access", lambda: True)
        monkeypatch.setattr(reddit, "get_subreddit", lambda name: _Subreddit(list(posts)))
        reddit._search_images.cache_clear()

    yield install
    reddit._search_images.cache_clear()


def test_a_gif_search_gives_the_gifs_with_their_video_copies(subreddit):
    subreddit(_big_gif_post(), _post(url="https://i.redd.it/small.gif", subreddit_name_prefixed="r/gifs"))

    assert reddit.search_images("gifs", "cats", animated=True) == [
        reddit.RedditImage(
            "https://i.redd.it/big.gif",
            "Reddit (r/gifs)",
            "https://www.reddit.com/r/gifs/comments/big/",
            "https://preview.redd.it/big.gif?format=mp4&s=video",
            "https://preview.redd.it/big.gif?format=png8&s=still",
        ),
        reddit.RedditImage("https://i.redd.it/small.gif", "Reddit (r/gifs)", None),
    ]


def test_reddits_images_know_their_video_copies(subreddit):
    subreddit(_big_gif_post())

    (image,) = RedditImageSearcher("gifs", animated=True)("cats")

    assert image.get_image_url() == "https://i.redd.it/big.gif"
    assert image.video == VideoCopy(
        "https://preview.redd.it/big.gif?format=mp4&s=video", "https://preview.redd.it/big.gif?format=png8&s=still"
    )
    assert image.video_data is None  # until the gif turns out to be too large to embed
    assert image.get_shown_url() == image.get_image_url()


def test_for_gifs_a_gallery_gives_its_first_animated_image():
    media = {
        "a": {"status": "valid", "e": "Image", "s": {"u": "https://preview.redd.it/a.jpg"}},
        "b": {"status": "valid", "e": "AnimatedImage", "s": {"gif": "https://i.redd.it/b.gif", "u": "x"}},
    }
    items = {"items": [{"media_id": "a"}, {"media_id": "b"}]}
    post = _post(url="https://www.reddit.com/gallery/x", is_gallery=True, media_metadata=media, gallery_data=items)
    assert reddit.get_image_url(post, animated=True) == "https://i.redd.it/b.gif"
    assert reddit.get_image_url(post) == "https://preview.redd.it/a.jpg"
