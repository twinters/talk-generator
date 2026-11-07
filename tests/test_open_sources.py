"""Live tests of the sources that need no API key (except GIPHY, the Smithsonian, and Openverse's registered app): the
canaries that tell when a source changed its answers, or went away."""

import pytest

from talkgenerator.sources import (
    art_institute,
    cleveland,
    flags,
    giphy,
    imgflip,
    memes,
    met,
    nasa,
    openverse,
    smithsonian,
    wellcome,
    wikimedia_commons,
    wikiquote,
)
from tests.support import requires_keys

pytestmark = pytest.mark.network


def _assert_credited_images(images):
    assert len(images) > 0
    assert all(image.get_image_url().startswith("https://") for image in images)
    assert all(image.get_source() for image in images)


def test_openverse():
    _assert_credited_images(openverse.search_photos("volcano"))


@requires_keys("OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET")
def test_openverse_as_a_registered_app():
    assert openverse._access_token.get(), "signing in failed: see the logged warning"
    _assert_credited_images(openverse.search_photos("lighthouse"))


def test_wikimedia_commons_historic_photos():
    _assert_credited_images(wikimedia_commons.search_historic_photos("bicycle"))


def test_art_institute():
    _assert_credited_images(art_institute.search_artworks("cat"))


def test_art_institute_old_photographs():
    _assert_credited_images(art_institute.search_artworks("bicycle", "photograph", before=1950))


def test_the_met():
    found = met.search_artworks("cat", "painting")
    _assert_credited_images(found)
    assert all(image.license_class == "public-domain" for image in found)


def test_cleveland():
    _assert_credited_images(cleveland.search_artworks("cat", after=1800, before=1950))


def test_wellcome_collection():
    found = wellcome.search_images("tooth")
    _assert_credited_images(found)
    assert {image.license_class for image in found} <= {"public-domain", "open"}


@requires_keys("SMITHSONIAN_API_KEY")
def test_smithsonian():
    _assert_credited_images(smithsonian.search_images("sunflowers", "painting"))


def test_nasa():
    _assert_credited_images(nasa.search_images("moon landing", before=1975))


def test_flags():
    (belgium,) = flags.search_flags("Belgium")
    assert belgium.get_image_url() == "https://flagcdn.com/w1280/be.png"
    assert flags.code("the Netherlands") == "nl"


def test_imgflip_still_lists_most_of_the_known_templates():
    listed = {template.id: template for template in imgflip.templates()}
    assert len(listed) >= 50
    known = memes.templates()
    still = [template_id for template_id in known if template_id in listed]
    # (its list is the templates most captioned lately, so a few of the known ones may drop out now and then)
    assert len(still) >= len(known) // 2, sorted(set(known) - set(still))
    assert all(listed[template_id].url == known[template_id].url for template_id in still)


@requires_keys("GIPHY_API_KEY")
def test_giphy():
    _assert_credited_images(giphy.search_gifs("cat"))


def test_wikiquote():
    quotes = wikiquote.search_quotes("cats")
    assert len(quotes) > 5
    assert all(wikiquote.MIN_QUOTE_LENGTH <= len(quote) <= wikiquote.MAX_QUOTE_LENGTH for quote in quotes)
