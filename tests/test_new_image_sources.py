"""Offline tests of the image sources added in milestone 5 (docs/v5-plan.md, 10.4): the Met, the Cleveland Museum of
Art, the Wellcome Collection, the Smithsonian, NASA's Image and Video Library, Flagpedia's flags and Imgflip's meme
templates. Their answers are fixtures: real answers of 2026-11-07, trimmed (tests/fixtures/image_sources)."""

import json
from pathlib import Path

import pytest

from talkgenerator import settings
from talkgenerator.images import catalog, profiles
from talkgenerator.sources import (
    art_institute,
    cleveland,
    flags,
    imgflip,
    memes,
    met,
    nasa,
    smithsonian,
    wellcome,
)
from talkgenerator.util import http_util

FIXTURES = Path(__file__).parent / "fixtures" / "image_sources"
NEW_SOURCES = (met, cleveland, wellcome, smithsonian, nasa, flags, imgflip)


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _Answer:
    def __init__(self, data, status_code=200, headers=None):
        self._data = data
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = headers or {}

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


@pytest.fixture
def answers(monkeypatch):
    """Answer requests from fixtures, by the start of their address; remember the requests (address, parameters).
    Every source starts out of its cooldown."""
    served: dict[str, object] = {}
    requests = []

    def get(url, **kwargs):
        requests.append((url, kwargs.get("params") or {}))
        found = next((answer for prefix, answer in served.items() if url.startswith(prefix)), None)
        if found is None:
            return _Answer({}, 404)
        return found if isinstance(found, _Answer) else _Answer(found)

    monkeypatch.setattr(http_util, "get", get)
    for module in NEW_SOURCES:
        monkeypatch.setattr(module, "_cooldown", http_util.Cooldown(f"{module.__name__} (test)"))
    monkeypatch.setattr(flags, "_codes", None)
    served["requests"] = requests  # (not an address: a handle on them, for the tests)
    return served


def _requests(answers):
    return answers["requests"]


# THE MET


def test_the_met_keeps_its_public_domain_objects(answers):
    answers[met.SEARCH_URL] = fixture("met_search.json")
    for number in (552027, 437112, 436524):
        answers[met.OBJECT_URL.format(number)] = fixture(f"met_object_{number}.json")
    found = met.search_artworks("cat", "painting", before=1900)
    # (437112, Monet's sunflowers, isn't public domain: the API gives no image of it)
    assert [image.get_image_url().rsplit("/", 1)[-1] for image in found] == [
        "LC-04_2_472_EGDP031195.jpg",
        "DP-41223-001.jpg",
    ]
    cat, sunflowers = found
    assert (cat.license_class, cat.license, cat.display) == ("public-domain", "CC0", "direct")
    assert cat.get_source() == "Unknown artist (The Metropolitan Museum of Art)"  # (no artist, no culture)
    assert sunflowers.get_source() == "Vincent van Gogh (The Metropolitan Museum of Art)"
    assert sunflowers.get_credit()[2] == ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/")
    assert sunflowers.description == "Sunflowers (1887)"
    assert "web-large" in sunflowers.thumbnail_url
    search_url, params = _requests(answers)[0]
    assert search_url == met.SEARCH_URL
    assert params["medium"] == "Paintings" and (params["dateBegin"], params["dateEnd"]) == (-5000, 1900)


def test_the_met_backs_off_when_it_cant_answer(answers):
    answers[met.SEARCH_URL] = _Answer({}, 503)
    assert met.search_artworks("cat") == [] and met.search_artworks("dog") == []
    assert len(_requests(answers)) == 1 and not met.available()


# CLEVELAND


def test_cleveland_gives_its_web_copies_and_their_sizes(answers):
    answers[cleveland.API_URL] = fixture("cleveland.json")
    found = cleveland.search_artworks("cat", "painting", after=1600, before=1900)
    assert len(found) == 3  # (the one without images is left out)
    first = found[0]
    # (its web copy, about 900 pixels: its print copy takes seconds to come, its full one is a TIFF)
    assert first.get_image_url().endswith("_web.jpg") and first.thumbnail_url == first.get_image_url()
    assert first.declared_size and 800 <= max(first.declared_size) <= 1300
    assert (first.license_class, first.license) == ("public-domain", "CC0")
    named = [image.get_source() for image in found]
    assert "Min Zhen (Cleveland Museum of Art)" in named  # (the creator's name, without their life)
    _, params = _requests(answers)[0]
    assert (params["type"], params["created_after"], params["created_before"], params["cc0"]) == (
        "Painting",
        1600,
        1900,
        1,
    )


# THE WELLCOME COLLECTION


def test_the_wellcome_collection_asks_for_open_licenses_and_keeps_to_them(answers):
    answers[wellcome.API_URL] = fixture("wellcome.json")
    found = wellcome.search_images("tooth", after=1700, before=1900)
    assert [image.license_class for image in found] == ["public-domain", "open", "open"]  # (not the NC one)
    tooth_drawer = found[0]
    assert tooth_drawer.get_image_url().endswith("/full/!1600,1600/0/default.jpg")
    assert tooth_drawer.thumbnail_url.endswith("/full/400,/0/default.jpg")
    assert tooth_drawer.declared_size == (1600, 1152)  # (by its aspect ratio)
    assert tooth_drawer.get_source() == "Wellcome Collection (public domain)"
    pig_tooth = found[1]
    assert pig_tooth.get_source() == "Kevin Mackenzie, University of Aberdeen (CC BY 4.0, Wellcome Collection)"
    assert pig_tooth.get_credit()[2] == ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
    _, params = _requests(answers)[0]
    assert params["locations.license"] == "cc-by,cc-0,pdm"
    assert (params["source.production.dates.from"], params["source.production.dates.to"]) == (
        "1700-01-01",
        "1900-12-31",
    )
    wellcome.search_images("tooth", classes=frozenset({"public-domain"}))
    assert _requests(answers)[-1][1]["locations.license"] == "cc-0,pdm"


# THE SMITHSONIAN


def test_the_smithsonian_needs_a_key(answers, monkeypatch):
    answers[smithsonian.API_URL] = fixture("smithsonian.json")
    assert not smithsonian.available() and smithsonian.search_images("sunflowers") == []
    assert _requests(answers) == []


def test_the_smithsonian_keeps_its_cc0_images(answers, monkeypatch):
    monkeypatch.setattr(settings, "smithsonian_auth", lambda: {"smithsonian_api_key": "test"})
    answers[smithsonian.API_URL] = fixture("smithsonian.json")
    found = smithsonian.search_images("sunflowers", "painting")
    assert len(found) == 2  # (not the one whose image has usage conditions)
    first = found[0]
    assert first.get_image_url().startswith("https://ids.si.edu/ids/iiif/CHSDM-")
    assert first.get_image_url().endswith("/full/!1600,1600/0/default.jpg")
    assert first.get_source() == "Unknown artist (Cooper Hewitt, Smithsonian Design Museum)"
    assert first.declared_size == (1600, 1416)  # (scaled to what its image server serves)
    _, params = _requests(answers)[0]
    assert params["q"] == 'sunflowers AND online_media_type:Images AND media_usage:CC0 AND object_type:"Paintings"'


# NASA


def test_nasa_describes_its_pictures_and_leaves_out_others_copyrights(answers):
    answers[nasa.API_URL] = fixture("nasa.json")
    found = nasa.search_images("pizza", after=1990, before=2020)
    assert len(found) == 3  # (not the one with someone else's copyright)
    first = found[0]
    assert first.get_image_url().endswith("~large.jpg") and first.thumbnail_url.endswith("~small.jpg")
    assert first.declared_size == (1920, 1280)
    # (its title is only its number, so its description says what it shows)
    assert first.description.startswith("Astronauts David Saint-Jacques and Nick Hague eagerly await pizzas")
    assert first.get_source() == "NASA (NASA Image and Video Library)"
    assert first.get_source_url() == "https://images.nasa.gov/details/iss059e006481"
    assert (first.license_class, first.license) == ("public-domain", "public domain")
    _, params = _requests(answers)[0]
    assert (params["year_start"], params["year_end"], params["media_type"]) == (1990, 2020, "image")


# FLAGS


def test_flags_by_a_countrys_name(answers):
    answers[flags.CODES_URL] = fixture("flagcdn_codes.json")
    (belgium,) = flags.search_flags("Belgium")
    assert belgium.get_image_url() == "https://flagcdn.com/w1280/be.png"
    assert belgium.thumbnail_url == "https://flagcdn.com/w320/be.png"
    assert belgium.get_source() == "Flag of Belgium (public domain, via Flagpedia)"
    assert belgium.license_class == "public-domain"
    assert [flags.code(name) for name in ("the Netherlands", "flag of Japan", "Holland", "USA", "Ivory Coast")] == [
        "nl",
        "jp",
        "nl",
        "us",
        "ci",
    ]
    assert flags.code("Côte d'Ivoire") == "ci" and flags.code("Scotland") == "gb-sct"
    assert flags.code("Georgia") == "ge"  # (the country before the US state)
    assert flags.search_flags("Paris") == [] and flags.search_flags("guinea pig") == []
    assert len(_requests(answers)) == 1  # (its list of names, once)


def test_flags_wait_for_flagcdn_when_it_cant_answer(answers):
    answers[flags.CODES_URL] = _Answer({}, 503)
    assert flags.search_flags("Belgium") == []
    assert not flags.available()


# IMGFLIP


def test_imgflip_finds_a_template_by_its_id_or_name(answers):
    answers[imgflip.API_URL] = fixture("imgflip_get_memes.json")
    (drake,) = imgflip.find("181913649")
    assert drake.get_image_url() == "https://i.imgflip.com/30b1gx.jpg"
    assert drake.declared_size == (1200, 1200) and drake.license_class == "fair-use" and drake.display == "direct"
    # (its credit links to the template's page at Imgflip, as Imgflip asks of pictures shown from its server)
    assert drake.get_credit()[0] == ("Drake Hotline Bling", "https://imgflip.com/memetemplate/181913649")
    assert imgflip.template_id(drake.get_source_url()) == "181913649"
    assert [found.get_image_url() for found in imgflip.find("drake hotline bling")] == [drake.get_image_url()]
    assert [found.description for found in imgflip.find("Bernie")] == [
        "the Bernie I Am Once Again Asking For Your Support meme"
    ]


def test_imgflip_s_templates_come_from_memes_json_when_it_cant_answer(answers):
    answers[imgflip.API_URL] = _Answer({}, 500)
    (expanding_brain,) = imgflip.find("93895088", memes.known())
    assert expanding_brain.get_image_url() == "https://i.imgflip.com/1jwhww.jpg"
    assert imgflip.find("93895088") == []  # (none it knows of itself)


def test_imgflip_has_templates_memes_json_doesnt(answers):
    answers[imgflip.API_URL] = fixture("imgflip_get_memes.json")
    (listed,) = imgflip.find("Marked Safe From", memes.known())  # (one of Imgflip's, which memes.json doesn't know)
    assert memes.of_picture(listed.get_image_url(), listed.get_source_url()) is None


# THE ART INSTITUTE'S FILTERS (new with the museums')


def test_the_art_institutes_search_takes_a_type_and_years(answers):
    answers[art_institute.API_URL] = {"data": []}
    art_institute.search_artworks("bicycle", "photograph", after=1850, before=1950)
    _, params = _requests(answers)[0]
    assert params == {
        "q": "bicycle",
        "limit": 20,
        "fields": "id,title,artist_title,image_id,thumbnail",
        "query[bool][must][0][term][is_public_domain]": "true",
        "query[bool][must][1][term][artwork_type_title.keyword]": "Photograph",
        "query[bool][must][2][range][date_start][gte]": "1850",
        "query[bool][must][3][range][date_end][lte]": "1950",
    }
    art_institute.search_artworks("cat")
    assert _requests(answers)[-1][1]["query[term][is_public_domain]"] == "true"


# HOW THE FINDER SEES THEM


def test_the_new_sources_declare_their_licenses_and_display():
    declared = {module.__name__.rsplit(".", 1)[-1]: (module.LICENSES, module.DISPLAY) for module in NEW_SOURCES}
    assert declared == {
        "met": ({"public-domain"}, "direct"),
        "cleveland": ({"public-domain"}, "direct"),
        "wellcome": ({"public-domain", "open"}, "direct"),
        "smithsonian": ({"public-domain"}, "direct"),
        "nasa": ({"public-domain"}, "direct"),
        "flags": ({"public-domain"}, "direct"),
        "imgflip": ({"fair-use"}, "direct"),
    }
    names = {"met", "cleveland", "wellcome", "smithsonian", "nasa", "flags", "imgflip"}
    assert names <= set(catalog.SOURCES)
    assert {entry["name"] for entry in catalog.describe()} >= names


def test_the_looks_filters_reach_the_museums(monkeypatch):
    asked = {}

    def remember(name):
        def search(query, *filters):
            asked[name] = (query, filters)
            return []

        return search

    monkeypatch.setattr(met, "search_artworks", remember("met"))
    monkeypatch.setattr(cleveland, "search_artworks", remember("cleveland"))
    monkeypatch.setattr(nasa, "search_images", remember("nasa"))
    search = catalog.Search("bicycle", {"type": "photograph", "after": "1850", "before": "1950"})
    for name in ("met", "cleveland", "nasa"):
        catalog.SOURCES[name].search(search)
    assert asked == {
        "met": ("bicycle", ("photograph", 1850, 1950)),
        "cleveland": ("bicycle", ("photograph", 1850, 1950)),
        "nasa": ("bicycle", (1850, 1950)),
    }
    catalog.SOURCES["met"].search(catalog.Search("bicycle", {"before": "the twenties"}))  # (not a year: no filter)
    assert asked["met"] == ("bicycle", (None, None, None))


def test_the_new_sources_join_the_looks_they_fit():
    def sources(look):
        return {use.source for use in profiles.profile(look).sources}

    assert {"met", "cleveland", "art-institute", "wellcome"} <= sources("museum")
    assert "nasa" in sources("space-science")
    assert {"met", "art-institute", "cleveland"} <= sources("vintage")
    assert {"met", "cleveland"} <= sources("portrait") and {"met", "cleveland"} <= sources("old-people")
    assert {"nasa", "wellcome"} <= sources("weird-stock")
    assert "flags" in sources("country") and sources("meme-templates") == {"imgflip"}
    # (the vintage look's museums ask for old photographs)
    vintage = {use.source: use for use in profiles.profile("vintage").sources}
    assert vintage["met"].params == {"type": "photograph", "before": "1950"}
    # (a classic search there gets no stock words, such as "weird", before its query)
    weird = {use.source: use for use in profiles.profile("weird-stock").sources}
    assert weird["nasa"].modifiers == ()


def test_nasa_leaves_out_pictures_too_large_to_embed():
    links = [{"href": "https://x/a~orig.jpg", "size": 40_000_000}, {"href": "https://x/a~small.jpg", "size": 50_000}]
    assert nasa._rendition(links, ("large", "medium", "orig")) is None
    assert nasa._rendition(links, ("small", "thumb"))["href"].endswith("~small.jpg")


def test_an_object_the_met_lists_but_doesnt_give_is_no_warning(answers, caplog):
    answers[met.OBJECT_URL.format(1)] = _Answer({}, 404)
    with caplog.at_level("WARNING"):
        assert met._object(1) is None
    assert "404" not in caplog.text and met.available()  # (and no cooldown)


def test_the_countries_of_classic_about_me_slides_have_flags(answers):
    answers[flags.CODES_URL] = fixture("flagcdn_codes.json")  # (all of flagcdn.com's names)
    names = json.loads(
        (Path(__file__).parents[1] / "talkgenerator/data/text-templates/about_me_facts.json").read_text(
            encoding="utf-8"
        )
    )
    without = [name for name in names["country"] if flags.code(name) is None]
    # (the two that no one flag stands for)
    assert without == ["Israel and the Occupied Territories", "Pacific Islands"]
    assert [flags.code(name) for name in ("Trinidad & Tobago", "Russian Federation", "Myanmar/Burma")] == [
        "tt",
        "ru",
        "mm",
    ]
