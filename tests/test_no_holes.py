"""Offline tests: a slide that misses an image is never put in the deck with a hole in it.

Content sources can always fail (a missing API key, a rate limit, a dead link, an outage). A slide that
misses an image is then generated again, or another kind of slide takes its place.
"""

import io
from types import SimpleNamespace

import pytest
from PIL import Image
from prawcore.exceptions import Forbidden, OAuthException, RequestException, ServerError, TooManyRequests

from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, SlideGeneratorData
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types, slides
from talkgenerator.sources import giphy, openverse, pexels, pixabay, reddit, unsplash
from talkgenerator.util import http_util, image_util
from talkgenerator.util.generator_util import StaticGenerator

CONTEXT = {"seed": "cat", "topic": "cat", "presenter": "An O. Nymous", "title": "About cats"}


def _jpeg(size=(400, 300)):
    output = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(output, "JPEG")
    return output.getvalue()


@pytest.fixture
def images(monkeypatch):
    """Serve fake images: URLs in the returned dict are usable, everything else fails to download."""
    served = {}
    downloads = []

    def fetch(url):
        downloads.append(url)
        return served.get(url)

    monkeypatch.setattr(image_util, "fetch_image", fetch)
    return SimpleNamespace(served=served, downloads=downloads)


def _image(images, url="https://example.com/cat.jpg"):
    images.served[url] = _jpeg()
    return ImageData(image_url=url, source="Test")


def _two_images_generator(image_1, image_2):
    return slide_generator_types.TwoColumnImageSlideGenerator.of(
        StaticGenerator("Title"),
        StaticGenerator("Expectation"),
        image_1,
        StaticGenerator("Reality"),
        image_2,
    )


def _generate(generator):
    return generator.generate_slide(CONTEXT, (set(), 0))


def test_slide_with_all_its_images_is_accepted(images):
    image_1, image_2 = _image(images, "https://example.com/1.jpg"), _image(images, "https://example.com/2.jpg")
    assert _generate(_two_images_generator(StaticGenerator(image_1), StaticGenerator(image_2))) is not None


def test_slide_missing_an_image_is_rejected(images):
    # As when GIPHY has no key: the captions are there, but one of the images isn't
    generator = _two_images_generator(StaticGenerator(_image(images)), StaticGenerator(None))
    assert _generate(generator) is None


def test_slide_with_an_unusable_image_is_rejected(images):
    # Sources whose candidates aren't checked up front (or a link that died in the meantime)
    broken = ImageData(image_url="https://example.com/removed.jpg")
    assert _generate(_two_images_generator(StaticGenerator(_image(images)), StaticGenerator(broken))) is None


def test_text_can_fill_an_image_or_text_slot(images):
    # The "Historical Figure Quote" slide puts a quote where the second image would go
    assert _generate(_two_images_generator(StaticGenerator(_image(images)), StaticGenerator("A quote"))) is not None
    assert _generate(_two_images_generator(StaticGenerator(_image(images)), StaticGenerator("  "))) is None


def test_quote_slide_needs_its_text_and_background(images):
    def quote_slide(text, background):
        return slide_generator_types.LarqeQuoteSlideGenerator.of(
            StaticGenerator(None), StaticGenerator(text), StaticGenerator(background)
        )

    assert _generate(quote_slide("Be brave", _image(images))) is not None
    # Without its text, the slide used to silently disappear from the PowerPoint
    assert _generate(quote_slide(None, _image(images))) is None
    assert _generate(quote_slide("Be brave", None)) is None


def test_generator_data_retries_then_gives_up(images):
    attempts = []

    def flaky_image(_):
        attempts.append(1)
        return None

    generator = SlideGeneratorData(
        slide_generator_types.FullImageSlideGenerator.of(StaticGenerator("Look"), flaky_image), retries=3
    )
    assert generator.generate(CONTEXT, set()) is None
    assert len(attempts) == 3


def test_another_kind_of_slide_takes_the_place_of_one_that_misses_images(images):
    image = _image(images)
    broken = SlideGeneratorData(
        slide_generator_types.FullImageSlideGenerator.of(StaticGenerator("Gif"), StaticGenerator(None)),
        weight_function=ConstantWeightFunction(1000),
        name="Needs a gif",
    )
    working = SlideGeneratorData(
        slide_generator_types.FullImageSlideGenerator.of(StaticGenerator("Photo"), StaticGenerator(image)),
        weight_function=ConstantWeightFunction(1),
        name="Photo",
    )
    schema = PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=None,
        title_generator=None,
        slide_generators=[broken, working],
    )
    slide, _, used_generator, _ = schema.generate_slide(CONTEXT, slide_nr=1, num_slides=3, used_elements=set())
    assert used_generator is working
    assert slide.missing_content() == []


def test_the_checked_image_is_the_one_in_the_powerpoint(images):
    image = _image(images)
    result = _generate(_two_images_generator(StaticGenerator(image), StaticGenerator(_image(images, "https://b.jpg"))))
    slide, _ = result
    # The image drops out of the download cache, and can't be downloaded again
    images.served.clear()
    downloads_before = len(images.downloads)

    ppt_slide = slide.create_powerpoint_slide(powerpoint_slide_creator.create_new_powerpoint())

    pictures = [shape for shape in ppt_slide.shapes if shape._element.tag.endswith("}pic")]
    assert len(pictures) == 2
    assert len(images.downloads) == downloads_before


def test_image_data_keeps_its_bytes_once_fetched(images):
    image = _image(images)
    assert image_util.fetch_image_data(image) == images.served[image.get_image_url()]
    images.served.clear()
    assert image_util.fetch_image_data(image) is not None


# UNAVAILABLE SOURCES are skipped for a while, instead of costing every search its timeouts and retries


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}
        self.text = ""


@pytest.fixture
def failing_reddit(monkeypatch):
    monkeypatch.setattr(reddit, "_cooldown", http_util.Cooldown("Reddit (test)"))
    monkeypatch.setattr(reddit, "has_reddit_access", lambda: True)
    searches = []

    def install(error):
        def search(*args):
            searches.append(args)
            raise error

        monkeypatch.setattr(reddit, "_search_images", search)
        return searches

    return install


@pytest.mark.parametrize(
    "error",
    [
        TooManyRequests(_Response(429)),
        ServerError(_Response(503)),
        OAuthException(_Response(401), "invalid_grant"),
        RequestException(ConnectionError("unreachable"), (), {}),
    ],
    ids=["rate limit", "outage", "bad credentials", "no connection"],
)
def test_reddit_is_skipped_for_a_while_when_it_fails(failing_reddit, error):
    searches = failing_reddit(error)
    assert reddit.search_images("pics", "cat") is None
    assert reddit.search_images("gifs", "dog") is None
    assert len(searches) == 1


def test_one_failing_subreddit_doesnt_stop_reddit(failing_reddit):
    searches = failing_reddit(Forbidden(_Response(403)))  # e.g. a subreddit that went private
    assert reddit.search_images("private", "cat") is None
    assert reddit.search_images("pics", "cat") is None
    assert len(searches) == 2


@pytest.mark.parametrize("module", [pixabay, pexels, unsplash, giphy, openverse], ids=lambda module: module.__name__)
@pytest.mark.parametrize("status_code", [None, 503], ids=["no answer", "server error"])
def test_image_apis_are_skipped_for_a_while_when_they_are_down(monkeypatch, module, status_code):
    for key in ("PIXABAY_KEY", "PEXELS_KEY", "UNSPLASH_ACCESS_KEY", "GIPHY_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    monkeypatch.setattr(module, "_cooldown", http_util.Cooldown(module.__name__ + " (test)"))
    requests_made = []

    def get(url, **kwargs):
        requests_made.append(url)
        return None if status_code is None else SimpleNamespace(status_code=status_code, ok=False, headers={})

    monkeypatch.setattr(http_util, "get", get)
    search = module.search_gifs if module is giphy else module.search_photos
    assert not search("cat")
    assert not search("dog")
    assert len(requests_made) == 1


def test_openverse_is_skipped_for_a_while_when_it_refuses_this_network(monkeypatch):
    # What talkgenerator.com's server gets: every Openverse request answered with HTTP 403
    monkeypatch.setattr(openverse, "_cooldown", http_util.Cooldown("Openverse (test)"))
    requests_made = []

    def get(url, **kwargs):
        requests_made.append(url)
        return SimpleNamespace(status_code=403, ok=False, headers={})

    monkeypatch.setattr(http_util, "get", get)
    assert openverse.search_photos("cats") == []
    assert openverse.search_photos("predators") == []
    assert len(requests_made) == 1


def test_a_slide_doesnt_show_the_same_image_twice(images):
    # E.g. two slots that both fall back to the same few ShitpostBot images when Reddit is unavailable
    url = "https://example.com/hol-up.jpg"
    same_image_twice = _two_images_generator(StaticGenerator(_image(images, url)), StaticGenerator(_image(images, url)))
    assert _generate(same_image_twice) is None


def test_images_already_in_the_deck_count_as_repeated(images):
    # Different ImageData objects for the same picture are the same element of the deck. A slide may repeat a few
    # texts (conclusions sum up), but never a picture: a picture twice is a picture too few (and the schema settles
    # slides by that rule too, so in parallel they come out as one by one)
    url = "https://example.com/burning-piano.jpg"
    used = {_image(images, url)}
    generator = _two_images_generator(StaticGenerator(_image(images, url)), StaticGenerator(_image(images)))
    assert generator.generate_slide(CONTEXT, (used, 0)) is None
    assert generator.generate_slide(CONTEXT, (used, 1)) is None
    fresh = _two_images_generator(
        StaticGenerator(_image(images, "https://example.com/new.jpg")), StaticGenerator(_image(images))
    )
    assert fresh.generate_slide(CONTEXT, ({"Title"}, 0)) is None  # (its title, used before)
    assert fresh.generate_slide(CONTEXT, ({"Title"}, 1)) is not None


def test_missing_content_lists_what_is_missing(images):
    slide = slides.ThreeColumnImageSlide(
        title="Conclusions",
        image_or_text_1=_image(images),
        image_or_text_2=None,
        image_or_text_3=ImageData(image_url="https://example.com/dead.gif"),
    )
    assert slide.missing_content() == ["image_or_text_2", "image_or_text_3"]
