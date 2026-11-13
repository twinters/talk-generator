"""Offline tests of images in v5 (docs/v5-plan.md, section 10): license classes and policies, image slots and the
image finder, aesthetic profiles and the look at thumbnails, and the checks of all of them.

The finder searches fake sources (put in the catalog), whose thumbnails are pictures made here: gray ones, sepia ones
and colourful ones, busy ones and calm ones. Nothing goes over the network.
"""

import colorsys
import dataclasses
import io
import random
import threading
import time
import zlib

import pytest
from PIL import Image, ImageDraw, ImageOps

from talkgenerator import generator
from talkgenerator.checks.deck import check_deck, check_licenses, check_looks, deck_metrics
from talkgenerator.datastructures.image_data import ImageData
from talkgenerator.datastructures.slide_generator_data import ConstantWeightFunction, PeakedWeight, SlideGeneratorData
from talkgenerator.design import themes, treatments
from talkgenerator.images import analysis, catalog, context, licenses, profiles
from talkgenerator.images.profiles import Preferences, Profile, SourceUse
from talkgenerator.images.slots import ImageSlot
from talkgenerator.models.deck import Deck, DeckSlide, ImageAsset, ImageElement, ImageTreatment
from talkgenerator.plan.kinds import Recipe, Variant
from talkgenerator.schema.presentation_schema import PresentationSchema
from talkgenerator.schema.slide_topic_generators import IdentityTopicGenerator
from talkgenerator.slide import powerpoint_slide_creator, slide_generator_types, slides
from talkgenerator.util import generator_util, image_util, random_util
from talkgenerator.util.generator_util import StaticGenerator

# PICTURES TO LOOK AT


def _jpeg(picture):
    output = io.BytesIO()
    picture.convert("RGB").save(output, "JPEG", quality=92)
    return output.getvalue()


def _grid(seed, colour):
    """A picture of 4 × 3 blocks, each of a colour colour() draws: a different one for every seed."""
    rng = random.Random(seed)
    picture = Image.new("RGB", (160, 120))
    draw = ImageDraw.Draw(picture)
    for row in range(3):
        for column in range(4):
            draw.rectangle((column * 40, row * 40, column * 40 + 39, row * 40 + 39), fill=colour(rng))
    return picture


def _gray(seed=0):
    if seed:
        return _grid(seed, lambda rng: (level := rng.randrange(256), level, level))
    picture = Image.linear_gradient("L").resize((160, 120)).convert("RGB")
    ImageDraw.Draw(picture).ellipse((20, 20, 80, 80), fill=(40, 40, 40))
    return picture


def _sepia(seed=0):
    return ImageOps.colorize(_gray(seed).convert("L"), treatments.SEPIA[0], treatments.SEPIA[1])


def _colourful(seed=0):
    if seed:
        return _grid(seed, lambda rng: tuple(round(255 * part) for part in colorsys.hsv_to_rgb(rng.random(), 0.9, 0.9)))
    picture = Image.new("RGB", (160, 120), (230, 40, 30))
    draw = ImageDraw.Draw(picture)
    draw.rectangle((0, 60, 160, 120), fill=(20, 110, 230))
    draw.ellipse((40, 10, 100, 70), fill=(250, 220, 30))
    return picture


def _busy(seed=0):
    rng = random.Random(seed)
    picture = Image.new("RGB", (160, 120), (128, 128, 128))
    draw = ImageDraw.Draw(picture)
    for _ in range(300):
        x, y = rng.randrange(160), rng.randrange(120)
        draw.line((x, y, x + rng.randrange(-20, 20), y + rng.randrange(-20, 20)), fill=(255, 255, 255), width=2)
    return picture


def _calm(seed=0):
    picture = Image.new("RGB", (160, 120), (70, 90, 110))
    ImageDraw.Draw(picture).rectangle((0, 100, 160, 120), fill=(40, 50, 60))
    return picture


_PICTURES = {"gray": _gray, "sepia": _sepia, "colourful": _colourful, "busy": _busy, "calm": _calm}


@pytest.fixture(autouse=True)
def pictures(monkeypatch):
    """Thumbnails at https://thumbs/<kind>-<n>.jpg are pictures of that kind; images at https://images/ exist."""
    analysis.forget()
    image = _jpeg(_colourful())

    def download(url):
        name = url.rsplit("/", 1)[-1].removesuffix(".jpg")
        kind, _, number = name.partition("-")
        return _jpeg(_PICTURES[kind](int(number or 0))) if kind in _PICTURES else None

    monkeypatch.setattr(analysis, "_download", download)
    load = image_util.fetch_image
    monkeypatch.setattr(
        image_util, "fetch_image", lambda url: image if url.startswith("https://images/") else load(url)
    )
    monkeypatch.setattr(image_util, "probe", lambda url: url.startswith("https://images/"))  # (while streaming)
    yield
    analysis.forget()


# FAKE SOURCES


def _image(name, thumbnail=None, license_class="stock", size=(1600, 1000), description=None, **options):
    return ImageData(
        f"https://images/{name}.jpg",
        source=f"{name} (fake)",
        license_class=license_class,
        license={"stock": "Fake License", "open": "CC BY 4.0", "public-domain": "CC0"}.get(license_class),
        license_url="https://licenses/fake" if license_class != "fair-use" else None,
        thumbnail_url=f"https://thumbs/{thumbnail}.jpg" if thumbnail else None,
        declared_size=size,
        description=description,
        **options,
    )


class FakeSource:
    """A source of images named after the source and the query, with thumbnails of a kind; it remembers what it was
    asked, and takes a random while to answer (so that searches at once come back in any order)."""

    def __init__(self, name, kind="colourful", classes=("stock",), count=6, slow=False):
        self.name, self.kind, self.classes, self.count, self.slow = name, kind, frozenset(classes), count, slow
        self.asked = []
        self._lock = threading.Lock()

    def search(self, search):
        with self._lock:
            self.asked.append(search)
        if self.slow:
            time.sleep(random.random() / 50)  # (not the talk's random: the order things come back in)
        if "nothing" in search.query:
            return []
        license_class = next(iter(sorted(self.classes)))
        found = []
        for n in range(self.count):
            name = f"{self.name}-{search.query.replace(' ', '_')}-{n}"
            found.append((1.0, _image(name, f"{self.kind}-{zlib.crc32(name.encode())}", license_class)))  # (its own)
        return found


@pytest.fixture
def sources(monkeypatch):
    """Install fake sources in the catalog: sources(name, ...) adds one and returns it."""

    def install(name, **options):
        fake = FakeSource(name, **options)
        monkeypatch.setitem(
            catalog.SOURCES,
            name,
            catalog.Source(name, f"fake {name}", fake.classes, fake.search, lambda: True),
        )
        return fake

    return install


@pytest.fixture
def look(monkeypatch):
    """Install a fake look: look(name, uses, **options)."""

    def install(name, uses, **options):
        monkeypatch.setitem(profiles.PROFILES, name, Profile(name, f"fake {name}", tuple(uses), **options))
        return profiles.PROFILES[name]

    return install


def _find(slot, query="owls", seed=1, policy=licenses.ALL, palette=(), looks=None, persona_looks=None):
    talk = context.ImageContext(policy, palette, looks or {}, persona_looks=persona_looks or {})
    with context.for_talk(talk), random_util.use(random_util.Rng(seed)):
        return slot.find(query)


# LICENSES


def test_license_policies():
    assert licenses.policy(None) is licenses.ALL
    assert licenses.policy("open").classes == frozenset(licenses.CLASSES) - {"fair-use"}
    assert licenses.policy("public-domain, open").classes == {"public-domain", "open"}
    assert licenses.policy(["stock"]).name == "stock"
    assert licenses.policy("fair-use,stock,generated,open,public-domain") is licenses.ALL  # (all the classes: "all")
    with pytest.raises(ValueError, match="no license policy"):
        licenses.policy("copyleft")
    assert licenses.OPEN.allows(None)  # (a file of talkgenerator's own, or a plan's)
    assert not licenses.OPEN.allows("fair-use")
    assert licenses.ALL.narrowed({"open", "stock"}).name == "open,stock"


def test_creative_commons_licenses_are_read_and_the_ones_that_arent_open_are_left_out():
    assert licenses.creative_commons("by", "2.0") == (
        "open",
        "CC BY 2.0",
        "https://creativecommons.org/licenses/by/2.0/",
    )
    assert licenses.creative_commons("by-sa")[1] == "CC BY-SA 4.0"
    assert licenses.creative_commons("cc0")[0] == "public-domain"
    assert licenses.creative_commons("pdm")[1] == "public domain"
    assert licenses.creative_commons("by-nc") is None
    assert licenses.creative_commons("by-nd") is None
    assert licenses.from_name("CC BY-SA 4.0") == ("open", "CC BY-SA 4.0")
    assert licenses.from_name("Public domain") == ("public-domain", "Public domain")
    assert licenses.from_name("CC0") == ("public-domain", "CC0")
    assert licenses.from_name(None, "cc-by-sa-3.0") == ("open", "cc-by-sa-3.0")
    assert licenses.from_name("CC BY-NC 2.0") is None
    assert licenses.from_name("") is None


def test_every_image_source_declares_its_license_classes():
    from talkgenerator.sources import (
        art_institute,
        giphy,
        inspirobot,
        openverse,
        pexels,
        pixabay,
        reddit,
        shitpostbot,
        unsplash,
        wikimedia_commons,
    )

    declared = {
        module.__name__.rsplit(".", 1)[-1]: module.LICENSES
        for module in (
            art_institute,
            giphy,
            inspirobot,
            openverse,
            pexels,
            pixabay,
            reddit,
            shitpostbot,
            unsplash,
            wikimedia_commons,
        )
    }
    assert declared == {
        "art_institute": {"public-domain"},
        "giphy": {"fair-use"},
        "inspirobot": {"fair-use"},
        "openverse": {"public-domain", "open"},
        "pexels": {"stock"},
        "pixabay": {"stock"},
        "reddit": {"fair-use"},
        "shitpostbot": {"fair-use"},
        "unsplash": {"stock"},
        "wikimedia_commons": {"public-domain", "open"},
    }
    assert all(source.classes for source in catalog.SOURCES.values())


def test_credits_name_open_and_public_domain_licenses():
    open_image = ImageData("https://x/1.jpg", "Ann (via Flickr)", source_url="https://flickr/1", license_class="open")
    open_image.license, open_image.license_url = "CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"
    assert open_image.get_credit() == (
        ("Ann (via Flickr)", "https://flickr/1"),
        (" (", None),
        ("CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"),
        (")", None),
    )
    named = ImageData("https://x/1.jpg", credit=(("Ann (CC BY 2.0)", None),), license_class="open", license="CC BY 2.0")
    assert named.get_credit() == (("Ann (CC BY 2.0)", None),)  # (it names it already)
    stock = ImageData("https://x/1.jpg", "Bo (via Pexels)", license_class="stock", license="Pexels License")
    assert stock.get_credit() == (("Bo (via Pexels)", None),)  # (credited to the photographer and platform only)


# A LOOK AT A PICTURE


def test_a_look_tells_black_and_white_and_sepia_from_colour():
    gray = analysis.analyse(_jpeg(_gray()))
    sepia = analysis.analyse(_jpeg(_sepia()))
    colourful = analysis.analyse(_jpeg(_colourful()))
    assert gray.monochrome and gray.grayscale > 0.95 and gray.colourfulness < 0.05
    assert sepia.monochrome and sepia.grayscale < 0.5  # (toned: one hue)
    assert not colourful.monochrome and colourful.colourfulness > 0.6
    red, green, blue = (int(colourful.colors[0][index : index + 2], 16) for index in (1, 3, 5))
    assert blue > red and blue > green  # (its bottom half, blue, is the most of it)


def test_a_look_tells_how_much_detail_there_is_where_the_text_goes():
    busy = analysis.analyse(_jpeg(_busy()), analysis.MIDDLE)
    calm = analysis.analyse(_jpeg(_calm()), analysis.MIDDLE)
    assert busy.detail > 0.1 > 0.02 > calm.detail
    assert analysis.analyse(_jpeg(_calm())).detail is None  # (no area: nothing goes over it)


def test_near_duplicates_share_their_hash_but_for_a_few_bits():
    picture = _colourful()
    same = analysis.analyse(_jpeg(picture))
    smaller = analysis.analyse(_jpeg(picture.resize((80, 60))))
    other = analysis.analyse(_jpeg(_gray()))
    assert analysis.near_duplicates(same, smaller)
    assert not analysis.near_duplicates(same, other)
    assert not analysis.near_duplicates(same, None)


def test_colours_that_go_with_a_palette_fit_it_better():
    colourful = analysis.analyse(_jpeg(_colourful()))
    assert analysis.palette_fit(colourful, ("#e6281e", "#1e6ee6")) > analysis.palette_fit(colourful, ("#00ff00",))
    assert analysis.palette_fit(colourful, ()) == 0.0


def test_a_look_is_the_same_every_time():
    assert analysis.analyse(_jpeg(_sepia(3)), analysis.MIDDLE) == analysis.analyse(_jpeg(_sepia(3)), analysis.MIDDLE)


def test_what_cant_be_looked_at_gives_no_look():
    assert analysis.analyse(b"not a picture") is None


# THE IMAGE FINDER


def test_a_slot_finds_an_image_from_its_looks_sources_and_notes_its_look(sources, look):
    sources("fake-stock")
    look("fake", [SourceUse("fake-stock")])
    image = _find(ImageSlot(aesthetic="fake"))
    assert image.get_image_url().startswith("https://images/fake-stock-owls-")
    assert image.look == "fake"
    assert image.analysis is not None and image.analysis.hash  # (a look at its thumbnail)
    assert image.usable  # (checked, as before)


def test_the_license_policy_keeps_sources_out_of_the_search(sources, look):
    memes = sources("fake-memes", classes=("fair-use",))
    stock = sources("fake-stock")
    look("fake", [SourceUse("fake-memes", 100), SourceUse("fake-stock")])
    for seed in range(10):
        image = _find(ImageSlot(aesthetic="fake"), seed=seed, policy=licenses.OPEN)
        assert image.license_class == "stock"
    assert memes.asked == [] and stock.asked
    assert _find(ImageSlot(aesthetic="fake"), seed=1, policy=licenses.policy("public-domain")) is None


def test_the_license_policy_keeps_images_of_other_classes_out_one_by_one(sources, look, monkeypatch):
    def mixed(search):
        return [(1.0, _image("by-sa", "colourful-1", "open")), (1.0, _image("pd", "colourful-2", "public-domain"))]

    monkeypatch.setitem(
        catalog.SOURCES,
        "fake-mixed",
        catalog.Source("fake-mixed", "", frozenset({"open", "public-domain"}), mixed, lambda: True),
    )
    look("fake", [SourceUse("fake-mixed")])
    for seed in range(5):
        assert _find(ImageSlot(aesthetic="fake"), seed=seed, policy=licenses.policy("public-domain")).license_class == (
            "public-domain"
        )


def test_a_slot_can_narrow_the_license_classes_and_sources(sources, look):
    sources("fake-pd", classes=("public-domain",))
    sources("fake-stock")
    look("fake", [SourceUse("fake-pd"), SourceUse("fake-stock", 100)])
    assert (
        _find(ImageSlot(aesthetic="fake", license_classes=frozenset({"public-domain"}))).license_class
        == "public-domain"
    )
    assert _find(ImageSlot(aesthetic="fake", sources=("fake-pd",))).license_class == "public-domain"


def test_sources_go_by_weight_and_the_same_seed_finds_the_same(sources, look):
    sources("fake-a")
    sources("fake-b")
    look("fake", [SourceUse("fake-a", 9), SourceUse("fake-b", 1)], breadth=1)
    found = [_find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in range(60)]
    assert found == [_find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in range(60)]
    from_a = sum("fake-a" in url for url in found)
    assert 40 <= from_a < 60  # (about 9 in 10)


def test_sources_searched_at_once_find_the_same_whatever_comes_back_first(sources, look):
    for name in ("fake-a", "fake-b", "fake-c"):
        sources(name, slow=True)
    look("fake", [SourceUse("fake-a"), SourceUse("fake-b"), SourceUse("fake-c")], breadth=3, looks=3)
    for seed in range(8):
        picks = {_find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for _ in range(4)}
        assert len(picks) == 1


def test_a_source_that_cant_be_searched_now_changes_only_what_it_would_have_found(sources, look, monkeypatch):
    # (a cooldown in the middle of a talk, say: the order of the other sources stays as it was)
    sources("fake-a")
    sources("fake-b")
    look("fake", [SourceUse("fake-a"), SourceUse("fake-b")], breadth=1)
    found = {seed: _find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in range(20)}
    monkeypatch.setitem(
        catalog.SOURCES, "fake-a", dataclasses.replace(catalog.SOURCES["fake-a"], available=lambda: False)
    )
    from_b = [seed for seed, url in found.items() if "fake-b" in url]
    assert from_b and all(
        _find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() == found[seed] for seed in from_b
    )
    assert all("fake-b" in _find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in found)


def test_a_look_whose_sources_find_nothing_hands_over_to_its_fallback_and_the_slots_backups(sources, look):
    sources("fake-a")
    sources("fake-b")
    look("empty", [SourceUse("fake-a", query="nothing {}")], fallback="other")
    look("other", [SourceUse("fake-b")])
    assert "fake-b" in _find(ImageSlot(aesthetic="empty")).get_image_url()
    look("alone", [SourceUse("fake-a", query="nothing {}")])
    assert _find(ImageSlot(aesthetic="alone")) is None
    assert "fake-b" in _find(ImageSlot(aesthetic="alone", backups=("other",))).get_image_url()


def test_a_classic_search_gets_a_word_of_its_look_and_a_plan_searches_as_written(sources, look):
    fake = sources("fake-a")
    look("fake", [SourceUse("fake-a", query="{} in a painting")], modifiers=("weird",))
    _find(ImageSlot(aesthetic="fake"), query="owls")
    with generator_util.as_planned():
        _find(ImageSlot(aesthetic="fake"), query="owls")
    assert [search.query for search in fake.asked] == ["weird owls in a painting", "owls in a painting"]


def test_a_plan_gets_one_of_a_sources_best_results(sources, look):
    sources("fake-a", count=40)
    look("fake", [SourceUse("fake-a")])
    with generator_util.as_planned():
        found = {_find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in range(40)}
    assert {int(url.rsplit("-", 1)[-1].removesuffix(".jpg")) for url in found} <= set(range(generator_util.TOP_RESULTS))


def test_images_of_the_wrong_shape_or_too_small_are_left_out(sources, look, monkeypatch):
    def shapes(search):
        return [
            (1.0, _image("tall", "colourful-1", size=(600, 1200))),
            (1.0, _image("small", "colourful-2", size=(300, 200))),
            (1.0, _image("wide", "colourful-3", size=(1600, 900))),
        ]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-shapes", catalog.Source("fake-shapes", "", frozenset({"stock"}), shapes, lambda: True)
    )
    look("fake", [SourceUse("fake-shapes")])
    for seed in range(6):
        slot = ImageSlot(aesthetic="fake", orientation="landscape", min_pixels=500_000)
        assert "wide" in _find(slot, seed=seed).get_image_url()
    assert "tall" in _find(ImageSlot(aesthetic="fake", orientation="portrait")).get_image_url()


def test_images_described_as_unsafe_are_left_out(look, monkeypatch):
    def described(search):
        return [(1.0, _image("nsfw", "colourful-1", description="NSFW pics")), (1.0, _image("owl", "colourful-2"))]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-d", catalog.Source("fake-d", "", frozenset({"stock"}), described, lambda: True)
    )
    look("fake", [SourceUse("fake-d")])
    assert all("owl" in _find(ImageSlot(aesthetic="fake"), seed=seed).get_image_url() for seed in range(6))


def test_a_description_of_nudity_is_unsafe_but_a_naked_mole_rat_is_not():
    from talkgenerator.images.safety import unsafe_description as unsafe

    # (a post of r/OldSchoolCool that Reddit doesn't mark NSFW, on a kindergarten teacher's slide: D80)
    assert unsafe("Isaac Hayes Eating Fried Chicken Off of a Naked Woman While Drinking Wine (1970s)")
    assert all(unsafe(text) for text in ("Topless sunbathers, 1972", "Nudes by the lake", "Erotica shop", "NSFW"))
    assert not unsafe("A naked mole-rat in its tunnel") and not unsafe("Naked mole rats at the zoo")
    assert not unsafe("A comet visible to the naked eye")
    assert not unsafe("Sussex sheep at the Essex show") and not unsafe(None)  # (words in words; no description)


def test_a_vintage_look_prefers_black_and_white_and_sepia(look, monkeypatch):
    def old_and_new(search):
        return [(1.0, _image(f"new-{n}", f"colourful-{n}")) for n in range(5)] + [
            (1.0, _image("old", "sepia-1")),
            (1.0, _image("older", "gray-2")),
        ]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-o", catalog.Source("fake-o", "", frozenset({"stock"}), old_and_new, lambda: True)
    )
    look("fake-vintage", [SourceUse("fake-o")], prefers=Preferences(monochrome=True), looks=7, treatment="sepia")
    for seed in range(10):
        image = _find(ImageSlot(aesthetic="fake-vintage"), seed=seed)
        assert "old" in image.get_image_url() and image.analysis.monochrome


def test_a_calm_backdrop_has_little_detail_where_the_text_goes(look, monkeypatch):
    def calm_and_busy(search):
        return [(1.0, _image(f"busy-{n}", f"busy-{n}")) for n in range(4)] + [(1.0, _image("calm", "calm-1"))]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-c", catalog.Source("fake-c", "", frozenset({"stock"}), calm_and_busy, lambda: True)
    )
    look("fake-calm", [SourceUse("fake-c")], prefers=Preferences(detail=0.07), looks=5, text_area=analysis.MIDDLE)
    for seed in range(6):
        image = _find(ImageSlot(aesthetic="fake-calm"), seed=seed)
        assert "calm" in image.get_image_url() and image.analysis.detail <= 0.07


def test_in_a_themed_talk_pictures_that_go_with_its_colours_come_first(look, monkeypatch):
    def red_and_gray(search):
        return [(1.0, _image("gray", "gray-1")), (1.0, _image("red", "colourful-0"))]  # (red and blue)

    monkeypatch.setitem(
        catalog.SOURCES, "fake-r", catalog.Source("fake-r", "", frozenset({"stock"}), red_and_gray, lambda: True)
    )
    look("fake", [SourceUse("fake-r")])
    red = sum(
        "red" in _find(ImageSlot(aesthetic="fake"), seed=seed, palette=("#e6281e", "#1e6ee6")).get_image_url()
        for seed in range(60)
    )
    assert red > 33  # (more than the half it gets at random: about two in three)


def test_the_slides_own_images_are_avoided_and_nearly_the_same_ones_too(look, monkeypatch):
    def twins(search):
        return [
            (1.0, _image("one", "colourful-5")),
            (1.0, _image("two", "colourful-5")),
            (1.0, _image("gray", "gray-1")),
        ]

    monkeypatch.setitem(
        catalog.SOURCES, "fake-t", catalog.Source("fake-t", "", frozenset({"stock"}), twins, lambda: True)
    )
    look("fake", [SourceUse("fake-t")])
    with random_util.use(random_util.Rng(3)):
        first = ImageSlot(aesthetic="fake").find("owls")
        second = ImageSlot(aesthetic="fake").find("owls", avoid=[first])
    assert second != first
    if "gray" not in first.get_image_url():  # (one of the twins: the other one is nearly the same)
        assert "gray" in second.get_image_url()


def test_a_format_can_have_looks_of_its_own(sources, look, slot_schema):
    sources("fake-a")
    sources("fake-b")
    look("plain", [SourceUse("fake-a")])
    look("corporate", [SourceUse("fake-b")])
    assert "fake-b" in _find(ImageSlot(aesthetic="plain"), looks={"plain": "corporate"}).get_image_url()
    assert PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context_: "",
        slide_generators=[],
        looks={"photo": "corporate-stock"},
    ).looks == {"photo": "corporate-stock"}
    with pytest.raises(ValueError, match="no look"):
        PresentationSchema(None, IdentityTopicGenerator, None, [], looks={"photo": "glossy"})


def test_a_persona_s_favourite_look_goes_first_and_the_slot_s_own_look_after(sources, look):
    sources("fake-a")
    sources("fake-b")
    sources("fake-memes", classes=("fair-use",))
    look("plain", [SourceUse("fake-a")])
    look("favourite", [SourceUse("fake-b")])
    look("empty", [SourceUse("fake-b", query="nothing {}")])
    look("fair-use", [SourceUse("fake-memes")])
    slot = ImageSlot(aesthetic="plain")
    assert "fake-a" in _find(slot).get_image_url()
    assert "fake-b" in _find(slot, persona_looks={"plain": "favourite"}).get_image_url()
    # Where the favourite finds nothing, or isn't allowed, the slot's own look still does
    assert "fake-a" in _find(slot, persona_looks={"plain": "empty"}).get_image_url()
    assert "fake-a" in _find(slot, policy=licenses.OPEN, persona_looks={"plain": "fair-use"}).get_image_url()
    # (and a slot's own look, as its format has it, comes after the favourite)
    talk = context.ImageContext(looks={"plain": "favourite"}, persona_looks={"plain": "empty"})
    assert talk.tries("plain") == ("empty", "favourite") and talk.tries("other") == ("other",)


def test_a_slot_can_say_the_queries_it_searches_with(sources, look):
    fake = sources("fake-a")
    look("fake", [SourceUse("fake-a")])
    _find(ImageSlot(aesthetic="fake", queries=("{} book cover",)), query="owls")
    assert fake.asked[0].query == "owls book cover"


def test_slots_call_like_v4s_generators():
    slot = ImageSlot(aesthetic="photo")
    assert callable(slot) and callable(slot.from_word)
    with pytest.raises(ValueError, match="no look"):
        ImageSlot(aesthetic="fancy")
    with pytest.raises(ValueError, match="no image source"):
        ImageSlot(sources=("flickr",))


def test_every_look_has_sources_in_the_catalog_and_a_fallback_that_exists():
    for name, look in profiles.PROFILES.items():
        assert look.sources, name
        for use in (*look.sources, *look.last_resort):
            assert use.source in catalog.SOURCES, (name, use.source)
        assert look.fallback is None or look.fallback in profiles.PROFILES, name
    for name in (
        "vintage",
        "corporate-stock",
        "museum",
        "space-science",
        "meme-chaos",
        "calm-backdrop",
        "illustration",
    ):
        assert name in profiles.PROFILES
    for name in ("cursed", "wholesome", "bad-charts", "medieval"):
        assert profiles.reddit(name) in catalog.SOURCES and name in profiles.PROFILES


def test_without_the_open_policy_slides_of_fair_use_images_arent_picked():
    schema = generator.get_schema("default")
    with context.for_talk(context.ImageContext(licenses.OPEN)):
        unservable = {str(generator_) for generator_ in schema.unservable()}
    assert {"Full Screen Gif", "Full Screen Meme", "Inspirobot", "Reddit Chart"} <= unservable
    assert "Historical Figure Quote" not in unservable  # (portraits in museums stand in for Reddit's old photos)
    with context.for_talk(context.ImageContext(licenses.ALL)):
        assert schema.unservable() == frozenset()
    assert generator.get_schema("ted").license_policy == "open"
    assert generator.get_schema("default").license_policy == "all"


# SLOTS IN RECIPES


def test_a_recipe_can_leave_out_a_slot(monkeypatch):
    from talkgenerator.models.plan import SlidePlan
    from talkgenerator.plan import realize

    searched = []

    def photos(context_):
        searched.append(context_["seed"])
        return ImageData(f"https://images/{context_['seed']}.jpg", source="Fake")

    recipe = Recipe("two_columns", (photos, photos), omit=frozenset({"image_2"}))
    assert recipe.image_queries() == ["image_1"]
    assert [name for name, _ in recipe.slots()] == ["image_1"]
    built = {}

    def build(texts, images, language):
        built.update(images)
        return slides.TwoColumnImageSlide(
            texts.get("title"), texts["caption_1"], images["image_1"], texts["caption_2"], "a text"
        )

    monkeypatch.setitem(
        realize.KINDS,
        "two_columns",
        realize.KINDS["two_columns"].__class__(**{**realize.KINDS["two_columns"].__dict__, "build": build}),
    )
    plan = SlidePlan(
        kind="two_columns", concept="owls", texts={"caption_1": "A", "caption_2": "B"}, images={"image_1": "an owl"}
    )
    result = realize.realize(plan, recipe, {"seed": "owls"}, random_util.Rng(1), 0)
    assert result is not None
    assert searched == ["an owl"] and built["image_2"] is None
    varied = Recipe("image", (photos,), variants=(Variant(1, frozenset({"image"}), "text only"),)).varied(
        random_util.Rng(1)
    )
    assert varied.image_queries() == []


# A TALK WITH SLOTS: THE SAME SEED, THE SAME TALK


def _slot_schema():
    def photo_slide(name, look_name, weight, tags=()):
        slot = ImageSlot(aesthetic=look_name)
        return SlideGeneratorData(
            slide_generator_types.ImageSlideGenerator.of(StaticGenerator(name), slot),
            weight_function=ConstantWeightFunction(weight),
            allowed_repeated_elements=1,
            tags=list(tags),
            name=name,
            llm=Recipe("image", (slot,)),
        )

    title = SlideGeneratorData(
        slide_generator_types.TitleSlideGenerator.of(lambda c: c["title"], lambda c: c["presenter"]),
        weight_function=PeakedWeight((0,), 100000, 0),
        tags=["title"],
        name="Title slide",
    )
    return PresentationSchema(
        powerpoint_slide_creator.create_new_powerpoint,
        seed_generator=IdentityTopicGenerator,
        title_generator=lambda context_: "Talking about " + context_["seed"],
        slide_generators=[
            title,
            photo_slide("Photos", "fake-photo", 3),
            photo_slide("Old photos", "fake-vintage", 2),
            photo_slide("Memes", "fake-memes", 2),
        ],
        max_allowed_tags={"title": 1},
    )


@pytest.fixture
def slot_schema(sources, look, monkeypatch):
    sources("fake-stock", slow=True, count=8)
    sources("fake-old", kind="sepia", slow=True, count=8)
    sources("fake-reddit", classes=("fair-use",), slow=True, count=8)
    look("fake-photo", [SourceUse("fake-stock", 2), SourceUse("fake-old")], breadth=2)
    look(
        "fake-vintage",
        [SourceUse("fake-old"), SourceUse("fake-stock")],
        prefers=Preferences(monochrome=True),
        looks=4,
        treatment="sepia",
    )
    look("fake-memes", [SourceUse("fake-reddit")], fallback=None)
    schema = _slot_schema()
    monkeypatch.setattr(generator, "get_schema", lambda name: schema)
    return schema


def _talk(seed, parallel, theme="classic", license_policy=None):
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=7,
        topic="owls, cats",
        int_seed=seed,
        parallel=parallel,
        save_ppt=False,
        theme=theme,
        license_policy=license_policy,
    )
    return slide_deck.to_deck(schema_name="fake")


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_a_talk_with_slots_is_the_same_in_parallel_and_one_by_one(slot_schema, seed):
    assert _talk(seed, True).to_json() == _talk(seed, False).to_json()


def test_a_streamed_talk_with_slots_is_the_talk_made_at_once(slot_schema):
    events = list(generator.stream_talk("fake", 7, topic="owls, cats", int_seed=4, theme="random"))
    assert events[-1].deck.to_json() == _talk(4, True, theme="random").to_json()


def test_a_talks_deck_keeps_its_policy_and_its_images_licenses_and_looks(slot_schema):
    deck = _talk(5, True, license_policy="open")
    assert deck.license_policy == "open"
    images = [element.image for slide in deck.slides for element in slide.elements if isinstance(element, ImageElement)]
    assert images and all(image.license_class == "stock" for image in images)
    assert all(image.look in ("fake-photo", "fake-vintage") for image in images)
    assert not any(
        slide.notes and "Memes" in slide.notes.split("\n")[1] for slide in deck.slides[1:-1]
    )  # (not its closer)
    assert check_licenses(deck) == []
    assert deck_metrics(deck)["license_classes"] == {"stock": len(images)}


def test_a_talk_refuses_a_license_policy_there_isnt(slot_schema):
    with pytest.raises(ValueError, match="no license policy"):
        _talk(1, False, license_policy="copyleft")


# CHECKS


def _deck(*images, policy="all", treatment=None):
    elements = tuple(ImageElement(role="content", image=image, treatment=treatment) for image in images)
    return Deck(
        generator="test",
        license_policy=policy,
        slides=(
            DeckSlide(type="title", layout="classic/title"),
            *(DeckSlide(type="image", layout="classic/image", elements=(element,)) for element in elements),
        ),
    )


def _asset(
    name, license_class="stock", look=None, monochrome=True, credit=None, license=None, hash_="0f0f0f0f0f0f0f0f"
):
    from talkgenerator.models.deck import CreditPart, ImageAnalysis

    return ImageAsset(
        url=f"https://images/{name}.jpg",
        source=name,
        credit=tuple(CreditPart(text=text) for text in (credit or (name,))),
        license_class=license_class,
        license=license,
        look=look,
        analysis=ImageAnalysis(
            brightness=0.5,
            colourfulness=0.0 if monochrome else 0.8,
            grayscale=1.0 if monochrome else 0.1,
            monochrome=monochrome,
            hash=hash_,
        ),
    )


def test_the_check_finds_images_the_license_policy_doesnt_allow():
    deck = _deck(
        _asset("meme", "fair-use", hash_="0000000000000001"), _asset("photo", hash_="ffffffffffffffff"), policy="open"
    )
    findings = check_licenses(deck)
    assert [(finding.severity, finding.slide) for finding in findings] == [("error", 2)]
    assert "fair-use image, which the license policy (open) doesn't allow" in findings[0].message
    assert check_licenses(deck.model_copy(update={"license_policy": "all"})) == []


def test_the_check_finds_credits_without_their_license():
    named = _asset("ann", "open", license="CC BY 2.0", credit=("Ann (CC BY 2.0, via Openverse)",))
    unnamed = _asset("bo", "open", license="CC BY 2.0", credit=("Bo (via Openverse)",), hash_="f0f0f0f0f0f0f0f0")
    findings = check_licenses(_deck(named, unnamed))
    assert [(finding.slide, finding.message) for finding in findings] == [
        (3, "its credit doesn't name its license (CC BY 2.0)")
    ]


def test_the_check_finds_nearly_the_same_image_on_two_slides():
    findings = [
        finding
        for finding in check_deck(_deck(_asset("a"), _asset("b", hash_="0f0f0f0f0f0f0f0e")))
        if finding.check == "images"
    ]
    assert [(finding.slide, finding.message) for finding in findings] == [(3, "nearly the same image as slide 2")]


def test_the_check_finds_a_vintage_picture_in_colour_unless_its_turned_sepia():
    colour = _asset("new", look="vintage", monochrome=False)
    findings = check_looks(_deck(colour))
    assert [finding.check for finding in findings] == ["looks"]
    assert "a vintage picture in colour" in findings[0].message
    assert check_looks(_deck(colour, treatment=ImageTreatment(filter="sepia"))) == []
    assert check_looks(_deck(_asset("old", look="vintage"))) == []
    metrics = deck_metrics(_deck(colour, _asset("old", look="vintage", hash_="1111111111111111")))
    assert metrics["looks"] == {"vintage": {"images": 2, "looked_at": 2, "with_the_look": 1}}


# TREATMENTS


def test_a_vintage_picture_in_colour_turns_sepia_in_a_theme_without_a_filter():
    theme = themes.member(themes.FAMILIES["clean keynote"]).model_copy(update={"image_filter": "none"})
    colour = _asset("new", look="vintage", monochrome=False)
    treated = treatments.for_look(None, colour, theme)
    assert treated.filter == "sepia" and (treated.dark, treated.light) == treatments.SEPIA
    assert treatments.for_look(None, _asset("old", look="vintage"), theme) is None  # (black and white already)
    duotone = theme.model_copy(update={"image_filter": "duotone"})
    assert treatments.for_look(None, colour, duotone) is None  # (the theme's own filter gives its pictures one look)
    assert treatments.for_look(None, _asset("photo", look="photo", monochrome=False), theme) is None


def test_a_themed_deck_turns_its_vintage_pictures_in_colour_sepia(slot_schema, monkeypatch):
    from talkgenerator.design import engine

    deck = _deck(_asset("new", look="vintage", monochrome=False))
    theme = themes.member(themes.FAMILIES["clean keynote"]).model_copy(update={"image_filter": "none"})
    laid_out = engine.lay_out(deck, theme)
    images = [element for slide in laid_out.slides for element in slide.elements if isinstance(element, ImageElement)]
    assert images[0].treatment is not None and images[0].treatment.filter == "sepia"
    assert check_looks(laid_out) == []
