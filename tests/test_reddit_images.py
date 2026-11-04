"""Offline tests of picking the image out of Reddit posts."""

from types import SimpleNamespace

from talkgenerator.sources import reddit


def _post(**data):
    data.setdefault("subreddit_name_prefixed", "r/pics")
    return SimpleNamespace(**data)


def test_direct_image_link():
    post = _post(url="https://i.redd.it/abc.jpeg")
    assert reddit.get_image_url(post) == "https://i.redd.it/abc.jpeg"


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
