"""Offline tests of picking the image out of Reddit posts."""

from types import SimpleNamespace

import pytest

from talkgenerator.sources import reddit


def _post(**data):
    data.setdefault("subreddit_name_prefixed", "r/pics")
    return SimpleNamespace(**data)


def _preview(source_url, gif_url=None):
    """The `preview` of a post, as Reddit's API returns it (with HTML-escaped URLs)."""
    image = {"source": {"url": source_url, "width": 1200, "height": 900}, "resolutions": [], "variants": {}}
    if gif_url:
        image["variants"] = {"gif": {"source": {"url": gif_url}, "resolutions": []}}
    return {"images": [image], "enabled": True}


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
