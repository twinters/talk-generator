"""The theme families a random theme can be of (decision D62): a talk says which, as it says which personas its seed
picks from (D61), and a talk whose seed picks one of them keeps its theme.

The talks are the fake ones of test_llm_talks, as in test_personas.
"""

import collections

import pytest

from talkgenerator import generator, personas, runtime_checker
from talkgenerator.design import themes
from talkgenerator.util import random_util
from tests.test_llm_talks import NUM_SLIDES
from tests.test_personas import schema as schema  # the fake schema, with images found at example.com


def _themes(seeds=range(600), favoured=None, among=None, extremes=True):
    """The random themes of talks with these seeds, among the families they allow, as favoured weights them."""
    return [
        themes.pick(themes.RANDOM, random_util.Rng(seed).child("theme"), extremes, favoured, among) for seed in seeds
    ]


def _families(**options):
    return [theme.family for theme in _themes(**options)]


def _deck(int_seed=1, **options):
    """A talk of the fake schema, without a persona (so its random theme is weighted by the families' own weights)."""
    _, slide_deck, _ = generator._generate_presentation(
        schema="fake",
        slides=NUM_SLIDES,
        topic="cats",
        int_seed=int_seed,
        save_ppt=False,
        llm="none",
        persona="none",
        **options,
    )
    return slide_deck.to_deck()


def test_a_talk_says_which_families_its_random_theme_can_be_of():
    assert themes.allowed(None) == tuple(themes.FAMILIES)
    # In the order of FAMILIES, whatever order and case they come in, as a list or separated by commas
    assert themes.allowed(" swiss POSTER,Neon ") == ("neon", "Swiss poster")
    assert themes.allowed(["Swiss poster", "neon", "NEON"]) == ("neon", "Swiss poster")
    with pytest.raises(ValueError, match="There's no theme family 'plaid'; there are clean keynote, dark minimal"):
        themes.allowed("neon,plaid")
    for alone in ("classic", "random", "chaos"):
        with pytest.raises(ValueError, match=f"'{alone}' goes alone, as theme"):
            themes.allowed(["neon", alone])
    for nothing in ("", " , ", []):
        with pytest.raises(ValueError, match="at least one family"):
            themes.allowed(nothing)


def test_without_the_extremes_a_talk_needs_a_family_that_isn_t_one(schema):
    serious = tuple(name for name, family in themes.FAMILIES.items() if not family.extreme)
    assert themes.families() == tuple(themes.FAMILIES) and themes.families(False) == serious
    assert themes.families(False, "neon,1997 WordArt") == ("neon",)
    assert set(_families(extremes=False, among=("neon", "1997 WordArt"))) == {"neon"}
    with pytest.raises(ValueError, match="only families for laughs"):
        themes.families(False, ["1997 WordArt"])
    with pytest.raises(ValueError, match="only families for laughs"):
        _deck(extreme_themes=False, theme_families="clip-art corporate")


def test_a_random_theme_is_of_a_family_the_talk_allows():
    two = ("blueprint", "1997 WordArt")
    picked = collections.Counter(_families(among=two))
    assert set(picked) == set(two)
    # Each as often as its weight says among them: 1997 WordArt's is half the others' (it's one for laughs)
    assert 1.6 < picked["blueprint"] / picked["1997 WordArt"] < 2.5
    assert set(_families(among=["neon"])) == {"neon"}
    # The persona's favourites still weight them: a kindergarten teacher's talks are in kids more often (×5)
    teacher = personas.persona("kindergarten_teacher").themes
    favoured = collections.Counter(_families(favoured=teacher, among=("kids", "neon")))
    assert favoured["kids"] > 3 * favoured["neon"] > 0
    # Allowing all of them is allowing any: the same themes as before there was a choice of them
    assert _themes() == _themes(among=themes.FAMILIES) == _themes(among=",".join(themes.FAMILIES))
    assert _themes(favoured=teacher) == _themes(favoured=teacher, among=themes.FAMILIES)


def test_a_talk_whose_family_is_allowed_keeps_its_theme_whichever_others_are_left_out():
    every = _themes()
    without = [name for name in themes.FAMILIES if name not in ("neon", "kids", "Comic Sans everywhere")]
    fewer = _themes(among=without)
    for before, after in zip(every, fewer, strict=True):
        assert after == before if before.family in without else after.family in without
    # And the others' themes are shared out among the allowed families as their weights say (about as many as the left
    # out families' share of the weights would have: 67 of 600 with 24 families)
    moved = collections.Counter(after.family for before, after in zip(every, fewer, strict=True) if before != after)
    weights = {name: family.weight for name, family in themes.FAMILIES.items()}
    expected = (
        len(every) * sum(weights[name] for name in themes.FAMILIES if name not in without) / sum(weights.values())
    )
    assert sum(moved.values()) > 0.7 * expected and len(moved) >= 8


def test_a_theme_the_talk_names_goes_before_the_families_it_allows():
    # (as a persona named goes before the personas a talk allows)
    assert themes.pick("neon", random_util.Rng(1), among=["kids"]).family == "neon"
    assert themes.pick(themes.CLASSIC, random_util.Rng(1), among=["kids"]) is None


def test_a_talk_s_random_theme_is_of_a_family_it_allows(schema):
    allowed = ("chalkboard", "newspaper", "Swiss poster")
    for seed in range(1, 6):
        deck = _deck(int_seed=seed, theme="random", theme_families=allowed)
        expected = themes.pick(themes.RANDOM, random_util.Rng(seed).child("theme"), among=allowed)
        assert deck.style.family in allowed and deck.style == expected
    # The same seed and families, the same talk; and in a stream, from its start
    again = _deck(int_seed=3, theme="random", theme_families=allowed)
    assert again.to_json() == _deck(int_seed=3, theme="random", theme_families=allowed).to_json()
    events = list(
        generator.stream_talk(
            "fake",
            NUM_SLIDES,
            topic="cats",
            int_seed=3,
            llm="none",
            persona="none",
            theme="random",
            theme_families=allowed,
        )
    )
    assert events[0].style == events[-1].deck.style == again.style
    # A theme named goes first; and a family there isn't is a ValueError
    assert _deck(theme="neon", theme_families=allowed).style.family == "neon"
    with pytest.raises(ValueError, match="There's no theme family 'plaid'"):
        _deck(theme_families="plaid")
    with pytest.raises(ValueError, match="There's no theme family 'plaid'"):
        list(generator.stream_talk("fake", NUM_SLIDES, topic="cats", llm="none", theme_families="plaid"))


def test_every_slide_of_a_chaos_talk_has_a_theme_of_a_family_it_allows(schema):
    allowed = ("blueprint", "neon")
    deck = _deck(int_seed=2, theme="chaos", theme_families=allowed)
    assert deck.style.family in allowed
    own = [slide.style.family for slide in deck.slides if slide.style is not None]
    assert len(own) == len(deck.slides) and set(own) <= set(allowed)
    # Streamed, its slides come laid out as the finished deck has them
    events = list(
        generator.stream_talk(
            "fake",
            NUM_SLIDES,
            topic="cats",
            int_seed=2,
            llm="none",
            persona="none",
            theme="chaos",
            theme_families=allowed,
        )
    )
    ready = [event.slide for event in events if event.event == "slide.ready"]
    assert [slide.style for slide in ready] == [slide.style for slide in events[-1].deck.slides]
    assert {slide.style.family for slide in ready} <= set(allowed)


def test_the_command_line_takes_the_families_a_random_theme_can_be_of(monkeypatch):
    parser = generator.get_argument_parser()
    args = parser.parse_args(["--topic", "cats", "--theme_families", "Swiss poster,neon", "--print_logs", "false"])
    assert args.theme_families == ("neon", "Swiss poster")
    assert parser.parse_args([]).theme_families is None
    for wrong in ("plaid", "neon,classic", ""):
        with pytest.raises(SystemExit):
            parser.parse_args(["--theme_families", wrong])

    given = {}
    monkeypatch.setattr(runtime_checker, "check_runtime_environment", lambda: True)
    monkeypatch.setattr(generator, "_generate_presentation", lambda **options: given.update(options))
    generator.generate_presentation_using_cli_arguments(args)
    assert given["theme_families"] == ("neon", "Swiss poster")
