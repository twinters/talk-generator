"""Offline tests of how the newer sources turn API responses into images, quotes and credits."""

import pytest

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.slide import powerpoint_slide_creator, slides
from talkgenerator.sources import art_institute, giphy, openverse, unsplash, wikimedia_commons, wikiquote
from talkgenerator.util import http_util


class _FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        return self._data


@pytest.fixture
def fake_get(monkeypatch):
    """Make http_util.get / get_json return the given data, and remember the requests."""
    requests_made = []

    def install(data, status_code=200):
        def get(url, **kwargs):
            requests_made.append((url, kwargs))
            return _FakeResponse(data, status_code)

        monkeypatch.setattr(http_util, "get", get)
        monkeypatch.setattr(http_util, "get_json", lambda url, **kwargs: get(url, **kwargs).json())
        return requests_made

    return install


def test_openverse(fake_get):
    fake_get(
        {
            "results": [
                {
                    "url": "https://x/1.jpg",
                    "creator": "Ann",
                    "license": "by",
                    "license_version": "2.0",
                    "width": 1024,
                    "height": 768,
                    "foreign_landing_url": "https://flickr/1",
                },
                {"url": "https://x/2.jpg", "creator": None, "license": "pdm", "width": None, "height": None},
                {"url": "https://x/small.jpg", "license": "cc0", "width": 300, "height": 200},
            ]
        }
    )
    images = openverse.search_photos("cat")
    assert [image.get_image_url() for image in images] == ["https://x/1.jpg", "https://x/2.jpg"]  # too small: out
    assert images[0].get_source() == "Ann (CC BY 2.0, via Openverse)"
    assert images[0].get_source_url() == "https://flickr/1"
    assert images[1].get_source() == "Unknown creator (public domain, via Openverse)"


def test_openverse_backs_off_when_rate_limited(fake_get, monkeypatch):
    monkeypatch.setattr(openverse, "_cooldown", http_util.Cooldown("Openverse (test)"))
    requests_made = fake_get({}, status_code=429)
    assert openverse.search_photos("cat") == []
    assert openverse.search_photos("dog") == []
    assert len(requests_made) == 1


def test_wikimedia_commons(fake_get):
    fake_get(
        {
            "query": {
                "pages": [
                    {
                        "index": 2,
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "thumburl": "https://upload/2.jpg",
                                "descriptionurl": "https://commons/File:2",
                            }
                        ],
                    },
                    {
                        "index": 1,
                        "imageinfo": [
                            {
                                "mime": "image/jpeg",
                                "thumburl": "https://upload/1.jpg",
                                "descriptionurl": "https://commons/File:1",
                                "extmetadata": {
                                    "Artist": {"value": '<a href="//x">Jan  de Vries</a>'},
                                    "LicenseShortName": {"value": "Public domain"},
                                },
                            }
                        ],
                    },
                    {"index": 3, "imageinfo": [{"mime": "application/pdf", "url": "https://upload/3.pdf"}]},
                ]
            }
        }
    )
    images = wikimedia_commons.search_historic_photos("bicycle")
    assert [image.get_image_url() for image in images] == ["https://upload/1.jpg", "https://upload/2.jpg"]
    assert images[0].get_source() == "Jan de Vries (Public domain, via Wikimedia Commons)"
    assert images[1].get_source() == "Unknown author (via Wikimedia Commons)"


def test_art_institute(fake_get):
    requests_made = fake_get(
        {
            "config": {"iiif_url": "https://iiif"},
            "data": [{"id": 7, "artist_title": "Mary Cassatt", "image_id": "abc"}, {"id": 8, "image_id": None}],
        }
    )
    (image,) = art_institute.search_artworks("cat")
    assert image.get_image_url() == "https://iiif/abc/full/1686,/0/default.jpg"
    assert image.get_source() == "Mary Cassatt (Art Institute of Chicago)"
    assert image.get_source_url() == "https://www.artic.edu/artworks/7"
    assert requests_made[0][1]["params"]["query[term][is_public_domain]"] == "true"


def test_art_institute_gets_its_identification_header():
    assert "AIC-User-Agent" in http_util._host_headers("https://www.artic.edu/iiif/2/abc/full/843,/0/default.jpg")
    assert "AIC-User-Agent" in http_util._host_headers("https://api.artic.edu/api/v1/artworks/search")
    assert http_util._host_headers("https://example.com/notartic.edu") == {}


def test_giphy(fake_get, monkeypatch):
    monkeypatch.setenv("GIPHY_API_KEY", "test-key")
    fake_get(
        {
            "data": [
                {
                    "username": "catlover",
                    "url": "https://giphy.com/gifs/1",
                    "images": {"original": {"url": "https://media/1.gif"}},
                },
                {"username": "", "images": {"downsized_large": {"url": "https://media/2.gif"}}},
                {"images": {}},
            ]
        }
    )
    images = giphy.search_gifs("cat")
    assert [image.get_image_url() for image in images] == ["https://media/1.gif", "https://media/2.gif"]
    assert images[0].get_source() == "catlover (Powered by GIPHY)"
    assert images[1].get_source() == "GIPHY (Powered by GIPHY)"


def test_giphy_needs_a_key(fake_get, monkeypatch):
    monkeypatch.setenv("GIPHY_API_KEY", "")
    requests_made = fake_get({"data": []})
    assert giphy.search_gifs("cat") == []
    assert requests_made == []


_WIKIQUOTE_PAGE = """
<div class="mw-parser-output">
  <p>Intro about cats.</p>
  <div class="mw-heading mw-heading2"><h2 id="Quotes">Quotes</h2></div>
  <ul><li><b>I think all cats are wild. They only act tame for milk.</b>
    <ul><li><a href="/wiki/Douglas_Adams">Douglas Adams</a>, Last Chance to See (1991).</li></ul></li></ul>
  <ul><li>Too short.</li></ul>
  <ul><li>A cat has absolute emotional honesty.[1]</li></ul>
  <div class="mw-heading mw-heading2"><h2 id="External_links">External links</h2></div>
  <ul><li><a href="https://en.wikipedia.org/wiki/Cat">Cat on Wikipedia, the free encyclopedia</a></li></ul>
</div>
"""


def test_wikiquote_extracts_quotes_without_attributions():
    assert wikiquote.extract_quotes(_WIKIQUOTE_PAGE) == [
        "I think all cats are wild. They only act tame for milk.",
        "A cat has absolute emotional honesty.",
    ]


def test_image_credits_link_to_their_pages():
    slide = slides.ImageSlide(title="Cats", image_url=None)
    slide.add_source("Ann (via Pexels)", "https://www.pexels.com/photo/cat-123/")
    slide.add_source("u/bob (on r/pics)", None)
    ppt_slide = slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())
    runs = [
        run for shape in ppt_slide.shapes if shape.has_text_frame for p in shape.text_frame.paragraphs for run in p.runs
    ]
    text = "".join(run.text for run in runs)
    assert "[Image sources: Ann (via Pexels), u/bob (on r/pics)]" in text
    linked = {run.text: run.hyperlink.address for run in runs if run.hyperlink.address}
    assert linked == {"Ann (via Pexels)": "https://www.pexels.com/photo/cat-123/"}
    assert slide.to_slide_dictionary()["source_urls"][1] is None


def test_unsplash_credit_links_the_photographer_and_unsplash():
    # The attribution Unsplash's API guidelines ask for: "Photo by <photographer> on Unsplash", linking both
    photo = {
        "urls": {"raw": "https://images.unsplash.com/photo-1?ixid=abc"},
        "user": {"name": "Annie Spratt", "links": {"html": "https://unsplash.com/@anniespratt"}},
        "links": {"download_location": "https://api.unsplash.com/photos/1/download?ixid=abc"},
    }
    image = unsplash._map_to_image_data(photo)
    slide = slides.ImageSlide(title="Cats", image_url=None)
    slide.add_source(image.get_source(), image.get_source_url(), image.get_credit())
    ppt_slide = slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())
    runs = [
        run for shape in ppt_slide.shapes if shape.has_text_frame for p in shape.text_frame.paragraphs for run in p.runs
    ]
    assert "[Image sources: Photo by Annie Spratt on Unsplash]" in "".join(run.text for run in runs)
    linked = {run.text: run.hyperlink.address for run in runs if run.hyperlink.address}
    assert linked == {
        "Annie Spratt": "https://unsplash.com/@anniespratt?utm_source=talkgenerator&utm_medium=referral",
        "Unsplash": "https://unsplash.com/?utm_source=talkgenerator&utm_medium=referral",
    }
    assert image.get_source() == "Photo by Annie Spratt on Unsplash"


def test_image_data_keeps_its_link():
    assert ImageData("https://x/1.jpg", "Ann", source_url="https://page").get_source_url() == "https://page"


def test_images_say_what_they_show_when_their_source_does():
    from talkgenerator.sources import pexels

    photo = {
        "urls": {"raw": "https://images.unsplash.com/photo-1"},
        "user": {"name": "Ann", "links": {"html": "https://unsplash.com/@ann"}},
        "alt_description": "a cat   sitting on a windowsill",
    }
    assert unsplash._map_to_image_data(photo).description == "a cat sitting on a windowsill"
    pexel = {"src": {"original": "https://images.pexels.com/1.jpg"}, "photographer": "Bo", "alt": "Owl close up"}
    assert pexels._map_to_image_data(pexel).description == "Owl close up"
    assert giphy._map_gif(
        {"images": {"original": {"url": "https://x/1.gif"}}, "title": "Cat Dance GIF"}
    ).description == ("Cat Dance GIF")
    assert ImageData("https://x/1.jpg").description is None


def test_pixabay_tags_say_what_a_photo_shows(fake_get, monkeypatch):
    from talkgenerator import settings
    from talkgenerator.sources import pixabay

    monkeypatch.setattr(settings, "pixabay_auth", lambda: {"pixabay_key": "test"})
    fake_get({"hits": [{"largeImageURL": "https://x/1.jpg", "user": "Cy", "tags": "owl, bird, feathers"}]})
    (image,) = pixabay.search_photos("owl")
    assert image.description == "owl, bird, feathers"
