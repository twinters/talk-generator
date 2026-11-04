"""Live tests of the sources that need no API key (except GIPHY)."""

import pytest

from talkgenerator.sources import art_institute, giphy, openverse, wikimedia_commons, wikiquote
from tests.support import requires_keys

pytestmark = pytest.mark.network


def _assert_credited_images(images):
    assert len(images) > 0
    assert all(image.get_image_url().startswith("https://") for image in images)
    assert all(image.get_source() for image in images)


def test_openverse():
    _assert_credited_images(openverse.search_photos("volcano"))


def test_wikimedia_commons_historic_photos():
    _assert_credited_images(wikimedia_commons.search_historic_photos("bicycle"))


def test_art_institute():
    _assert_credited_images(art_institute.search_artworks("cat"))


@requires_keys("GIPHY_API_KEY")
def test_giphy():
    _assert_credited_images(giphy.search_gifs("cat"))


def test_wikiquote():
    quotes = wikiquote.search_quotes("cats")
    assert len(quotes) > 5
    assert all(wikiquote.MIN_QUOTE_LENGTH <= len(quote) <= wikiquote.MAX_QUOTE_LENGTH for quote in quotes)
