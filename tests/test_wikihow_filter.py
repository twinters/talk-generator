"""Offline tests of the wikiHow actions that classic talks get: only those about the seed (wikiHow pads a search it
has little on with its most popular how-tos, and with loose matches), and none of the worst, while crude ones stay.
wikiHow's search and the related words are fakes, with the titles wikiHow answered on 2026-11-08."""

from types import SimpleNamespace

import pytest

from talkgenerator.schema import content_generators as cg
from talkgenerator.sources import conceptnet, slide_texts, text_generator, wikihow
from talkgenerator.util import language_util

# What wikiHow's search answered a made-up word with (2026-11-08): the padding of a search it has little on, which
# had a lighthouse talk titled "Never, Ever Make Sex Better"
_PADDING = (
    "How to Kiss",
    "Am I Gay Quiz",
    "How to Take a Screenshot on a Windows PC: 8 Simple Tricks",
    "How to French Kiss",
    "How to Read Palms",
    "25 Different Sex Positions & What They’re Good For",
    "How to Tie a Tie",
    "How to Clear Your Web Browser Cache on Any Platform",
    "How to Masturbate Better (For Women, Men & Folks of All Genders)",
    "How to Make Sex Better",
)


def _page(*titles: str) -> bytes:
    """A page of wikiHow's search with these results, as it shows them."""
    results = "".join(
        f'<a class="result_link" href="https://www.wikihow.com/{index}"><div class="result"><div class="result_data">'
        f'<div class="result_title">{title}</div><ul class="search_results_stats"><li class="sr_view">1,234 views'
        "</li></ul></div></div></a>"
        for index, title in enumerate(titles)
    )
    return f'<html><body><div id="searchresults_list" class="wh_block">{results}</div></body></html>'.encode()


def _clear_caches():
    for cached in (wikihow._actions_about, wikihow._seed_stems, wikihow._related_words, wikihow._little_words):
        cached.cache_clear()


@pytest.fixture(autouse=True)
def search(monkeypatch):
    """Fake wikiHow searches (pages by search words: the padding for any other) and related words (by word)."""
    found = SimpleNamespace(pages={}, related={})
    monkeypatch.delenv("DISABLE_WIKIHOW", raising=False)
    monkeypatch.setattr(wikihow, "basic_search_wikihow", lambda words: found.pages.get(words, _page(*_PADDING)))
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: found.related.get(word, []))
    _clear_caches()
    yield found
    _clear_caches()


def test_a_seed_that_wikihow_has_little_on_gets_none_of_its_padding(search):
    search.pages["lighthouses"] = _page("How to Build a Model Lighthouse", "Category: Model Making", *_PADDING)
    assert wikihow.get_related_wikihow_actions("lighthouses") == ["Build a Model Lighthouse"]
    title = text_generator.apply_variables_to_template("Never, Ever {seed.wikihow_action}", {"seed": "lighthouses"})
    assert title == "Never, Ever Build a Model Lighthouse"
    assert cg.wikihow_title_generator({"seed": "lighthouses"}) == "How to Build a Model Lighthouse"
    # A seed wikiHow has nothing on gets none, so the templates that want one give way
    assert wikihow.get_related_wikihow_actions("alpacas") == []
    assert text_generator.apply_variables_to_template("Never, Ever {seed.wikihow_action}", {"seed": "alpacas"}) is None
    assert cg.wikihow_title_generator({"seed": "alpacas"}) is None


def test_a_seed_gets_none_of_the_loose_matches_either(search):
    search.pages["penguins"] = _page(
        "How to Draw a Penguin",
        "How to Be a Secret Agent",
        "How to Draw a Baby",
        "How to Secretly Tell Someone They Are Being Cheated on",
    )
    assert wikihow.get_related_wikihow_actions("penguins") == ["Draw a Penguin"]


def test_an_action_is_about_a_seed_that_has_one_of_its_telling_words_in_any_form():
    assert wikihow.about("Clean a Microwave", "cleaning")
    assert wikihow.about("Charge a Car Battery", "batteries")
    assert wikihow.about("Be a Successful Student", "success")
    assert wikihow.about("Plan a High School Reunion", "school reunions")
    assert wikihow.about("Find Meaning in Life", "the meaning of life")
    # The words that say little of a seed don't tell it ("days" of rainy days, "school" of school reunions)
    assert not wikihow.about("Have a Good Day", "rainy days")
    assert not wikihow.about("Skip School", "school reunions")
    assert not wikihow.about("Make New Friends Quickly", "the new colleague")
    assert not wikihow.about("Live a Good Life", "the meaning of life")


def test_an_action_is_about_a_seed_that_has_a_telling_word_of_one_related_to_it(search):
    search.related["birdwatching"] = [(10.0, "birds"), (8.0, "binoculars"), (5.0, "set")]
    assert wikihow.about("Draw a Bird", "birdwatching")  # ("birds", singular)
    assert not wikihow.about("Set Up a Violin", "birdwatching")  # ("set" is too common a word to tell anything)
    search.related["haversack"] = [(10.0, "webbing"), (9.0, "backpack")]
    assert wikihow.about("Organize Your Backpack", "haversack")
    assert not wikihow.about("Clear Your Web Browser Cache on Any Platform", "haversack")  # (webbing isn't the web)
    search.pages["birdwatching"] = _page("How to Bird Watch", "How to Draw a Bird", *_PADDING)
    assert wikihow.get_related_wikihow_actions("birdwatching") == ["Bird Watch", "Draw a Bird"]


def test_actions_with_the_worst_words_are_left_out_and_crude_ones_stay(search):
    search.pages["life"] = _page("How to Live a Good Life", "How to Live a Good Christian Life")
    search.pages["patch"] = _page("How to Patch a Tire", "How to Apply a Fentanyl Patch")
    assert wikihow.get_related_wikihow_actions("life") == ["Live a Good Life"]
    assert wikihow.get_related_wikihow_actions("patch") == ["Patch a Tire"]
    for action in ("Live a Good Christian Life", "Apply a Fentanyl Patch", "Make a DIY Smoke Bomb", "Kill a Chicken"):
        assert wikihow.unfit(action), action
    # Much of a classic talk's humour is crude: a how-to about the seed stays, whatever slides leave out
    search.pages["cleaning"] = _page("How to Clean a Microwave", "How to Clean Your Penis")
    search.pages["office plants"] = _page("How to Water Indoor Plants", "How to Hide the Smell of Marijuana Plants")
    assert wikihow.get_related_wikihow_actions("cleaning") == ["Clean a Microwave", "Clean Your Penis"]
    kept = wikihow.get_related_wikihow_actions("office plants")
    assert kept == ["Water Indoor Plants", "Hide the Smell of Marijuana Plants"]
    for action in ("Make Sex Better", "Masturbate Better", "Talk Dirty to a Guy", "Be Romantic in Bed"):
        assert not wikihow.unfit(action), action
    for action in ("Smoke a Cigarette", "Cook Chicken Breasts", "Get a Sexy Bikini Body", "Draw a Penguin"):
        assert not wikihow.unfit(action), action
    # (what slides leave out themselves stays as it was, and hard drugs have fentanyl too)
    assert slide_texts.sensitive("Make Sex Better") and slide_texts.sensitive("Apply a Fentanyl Patch")


def test_an_action_that_wikihow_finds_twice_is_kept_once(search):
    search.pages["golf"] = _page("How to Play Golf", "How to Hit a Golf Ball", "How to Play Golf")
    assert wikihow.get_related_wikihow_actions("golf") == ["Play Golf", "Hit a Golf Ball"]


def test_no_actions_while_wikihow_is_switched_off(search, monkeypatch):
    search.pages["golf"] = _page("How to Play Golf")
    monkeypatch.setenv("DISABLE_WIKIHOW", "1")
    assert wikihow.get_related_wikihow_actions("golf") == []


def test_without_nltks_little_words_a_seed_is_still_told_by_its_rare_words(monkeypatch):
    def unavailable(language):
        raise LookupError("NLTK's stopwords can't be had")

    monkeypatch.setattr(language_util, "stopwords", unavailable)
    wikihow._little_words.cache_clear()
    assert wikihow.about("Ride a Bus", "the night bus")
    assert not wikihow.about("Read the News", "the night bus")
