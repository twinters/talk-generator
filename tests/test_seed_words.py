"""Offline tests: the words a talk's slides start from, and that classic templates speak of, are things (docs/v5-plan.md,
D67). A classic volcano talk of 2026-11-09 had "Volcanoes vs. eruptive" on a scatter plot and "Do you want glacial?"
on a flowchart, with "eruptive", "eruption" and "erupted" on three slides: Datamuse's related words, which are
adjectives, verbs and names as often as things."""

import pytest

from talkgenerator.schema import slide_topic_generators
from talkgenerator.schema.slide_topic_generators import MAX_WANDER, SideTrackingTopicGenerator
from talkgenerator.sources import conceptnet, datamuse, diagram, slide_texts
from talkgenerator.util import language_util, random_util

# What Datamuse says of the words related to volcanoes (its "triggers", with md=p), as it did on 2026-11-09
VOLCANO_WORDS = {
    "volcanology": ("n",),
    "eruptive": ("adj", "n"),
    "scoria": ("n",),
    "erupt": ("v",),
    "subduction": ("n",),
    "cinder": ("n", "v"),
    "volcanic": ("adj", "n"),
    "volcano": ("n", "v"),
    "magma": ("n",),
    "basaltic": ("adj",),
    "lava": ("n",),
    "caldera": ("n",),
    "etna": ("n", "prop"),
    "eruption": ("n",),
    "erupted": ("v",),
    "eruptions": ("n",),
    "crater": ("n", "v"),
    "glacial": ("adj",),
}


@pytest.fixture
def related(monkeypatch):
    """Fake ConceptNet (and Datamuse's parts of speech): the words related to each word, the weightiest first."""
    words: dict[str, list[tuple[float, str]]] = {
        "volcanoes": [(10.0 - index * 0.5, word) for index, word in enumerate(VOLCANO_WORDS)],
    }
    tags = dict(VOLCANO_WORDS)
    monkeypatch.setattr(conceptnet, "get_weighted_related_words", lambda word, limit=50: words.get(word, []))
    monkeypatch.setattr(datamuse, "parts_of_speech", lambda word: tags.get(word))
    return words, tags


def _seeds(topics, slides=10, seed=1, period=range(3, 6)):
    with random_util.use(random_util.Rng(seed)):
        return SideTrackingTopicGenerator(topics, slides, period)


def test_seeds_are_things(related):
    for seed in range(20):
        seeds = _seeds(["volcanoes"], seed=seed).all_seeds()
        assert not {"eruptive", "erupt", "erupted", "volcanic", "basaltic", "glacial"} & set(seeds)  # (no thing)
        assert "etna" not in seeds  # (a name: a slide would have it in small letters)
        assert not {"scoria", "volcanology"} & set(seeds)  # (too rare to know)
        assert set(seeds) <= {"volcanoes", "subduction", "cinder", "magma", "lava", "caldera", "eruption", "crater"}


def test_each_seed_is_a_family_of_its_own(related):
    for seed in range(20):
        seeds = [word for word in _seeds(["volcanoes"], seed=seed).all_seeds() if word != "volcanoes"]
        assert len(seeds) == len(set(seeds))
        assert "volcano" not in seeds  # (the topic's family)
        assert len([word for word in seeds if word.startswith("erupt")]) <= 1


def test_seeds_wander_at_most_two_steps_from_the_topic(related):
    words, tags = related
    # A chain of things: each related to the one before only, and the topic to its first ones
    chain = {"penguins": ["seal", "krill"], "seal": ["walrus"], "walrus": ["tusk"], "tusk": ["ivory"]}
    chain |= {"krill": ["whale"], "whale": ["ocean"], "ocean": ["wave"]}
    for word, others in chain.items():
        words[word] = [(5.0, other) for other in others]
    tags |= {word: ("n",) for others in chain.values() for word in others}
    steps = {"penguins": 0, "seal": 1, "krill": 1, "walrus": 2, "whale": 2, "tusk": 3, "ocean": 3, "ivory": 4}
    for seed in range(10):
        generator = _seeds(["penguins"], slides=12, seed=seed, period=range(6, 7))
        assert max(steps[word] for word in generator.all_seeds()) <= MAX_WANDER, generator.all_seeds()
        assert generator.all_seeds()[:3] in (["penguins", "seal", "walrus"], ["penguins", "krill", "whale"])


def test_a_phrase_wanders_from_its_words_when_its_own_related_words_are_its_family(related):
    words, tags = related
    words["quantum physics"] = [(9.0, "quantum mechanics"), (8.0, "quantum theory")]
    words["physics"] = [(9.0, "chemistry"), (8.0, "astronomy"), (7.0, "physicist")]
    tags |= {word: ("n",) for word in ("quantum mechanics", "quantum theory", "chemistry", "astronomy", "physicist")}
    seeds = _seeds(["quantum physics"], slides=4, period=range(4, 5)).all_seeds()
    assert seeds[0] == seeds[-1] == "quantum physics"
    assert set(seeds[1:3]) <= {"chemistry", "astronomy"} and seeds[1] != seeds[2]


def test_no_seed_is_a_word_a_slide_should_not_make_light_of(related):
    words, tags = related
    words["pirates"] = [(9.0, "slave"), (8.0, "treasure"), (7.0, "parrot")]
    tags |= {"slave": ("n", "v"), "treasure": ("n", "v"), "parrot": ("n", "v")}
    for seed in range(10):
        assert "slave" not in _seeds(["pirates"], slides=4, seed=seed, period=range(4, 5)).all_seeds()


def test_a_topic_without_related_things_is_every_seed(related):
    assert _seeds(["frietjes"], slides=5).all_seeds() == ["frietjes"] * 5


def test_seeds_keep_the_words_that_would_have_done_too(related):
    generator = _seeds(["volcanoes"], slides=6, period=range(6, 7))
    first = generator.get_seed(1)
    others = generator.alternatives(1)
    assert 0 < len(others) <= slide_topic_generators.ALTERNATIVES and first not in others
    assert generator.alternatives(0) == ()  # (the topic's slide)


def test_classic_slides_speak_of_related_things(related):
    words, tags = related
    assert [word.lower() for word in slide_texts.related_words("volcanoes")] == [
        "subduction",
        "cinder",
        "magma",
        "lava",
        "caldera",
        "eruption",
        "crater",
    ]
    # (a matrix's quadrants and dots, and a correlation's clusters: things too)
    words["sleep"] = [(9.0, "drowsy"), (8.0, "pillow"), (7.0, "insomnia"), (6.0, "asleep"), (5.0, "dream")]
    words["sleep"] += [(4.0, "bed"), (3.0, "blanket")]
    tags |= {"drowsy": ("adj",), "pillow": ("n",), "insomnia": ("n",), "asleep": ("adj",), "dream": ("n", "v")}
    tags |= {"bed": ("n", "v"), "blanket": ("n", "adj")}
    things = [word for _, word in conceptnet.related_things("sleep")]
    assert things == ["pillow", "insomnia", "dream", "bed", "blanket"]
    assert "drowsy" not in diagram._words(conceptnet.related_things("sleep"), "sleep")


@pytest.mark.parametrize(
    ("phrase", "parts_of_speech", "thing"),
    [
        ("cinder", ("n", "v"), True),
        ("eruptive", ("adj", "n"), False),  # (an adjective first of all)
        ("glacial", None, False),  # (WordNet knows it as an adjective only)
        ("etna", ("n", "prop"), False),
        ("krill", ("n",), True),
        ("scoria", ("n",), False),  # (rare)
        ("albatrosses", ("n",), True),  # (as common as an albatross)
        ("spider plant", ("n",), True),
        ("rhizopus nigricans", ("n",), False),
        ("both", None, False),
        ("threw", ("v",), False),
        ("magma", None, True),
        ("u2", ("n",), False),
    ],
)
def test_what_a_thing_is(phrase, parts_of_speech, thing):
    assert language_util.is_thing(phrase, parts_of_speech) is thing


@pytest.mark.parametrize(
    ("one", "other", "same"),
    [
        ("eruption", "eruptive", True),
        ("erupted", "eruptions", True),
        ("volcanoes", "volcanic", True),
        ("lights", "lighthouses", True),
        ("musk duck", "rubber ducks", True),
        ("ducklings", "rubber ducks", True),
        ("a cup of tea", "teas", True),
        ("glacier", "glacial", True),
        ("cat", "category", False),
        ("bees", "beekeeper", False),
        ("tea", "team", False),
        ("plant", "planet", False),
    ],
)
def test_word_families(one, other, same):
    assert language_util.same_family(one, other) is same
    assert language_util.same_family(other, one) is same


def test_datamuse_tells_the_parts_of_speech_of_the_words_it_found(monkeypatch):
    monkeypatch.setattr(datamuse, "_parts_of_speech", {})
    answers = (("lava", 900, ("n",)), ("eruptive", 800, ("adj", "n")), ("etna", 500, ("n", "prop")))
    monkeypatch.setattr(datamuse, "_query", lambda relation, word, max_results: answers)
    assert [word for _, word in datamuse.query("rel_trg", "volcanoes")] == ["lava", "eruptive", "etna"]
    assert datamuse.parts_of_speech("eruptive") == ("adj", "n")
    assert datamuse.parts_of_speech("etna") == ("n", "prop")
    assert datamuse.parts_of_speech("glacial") is None  # (no answer had it)
    assert datamuse._parts_of(["syn", "n", "results_type:primary_rel", "prop", "f:0.25"]) == ("n", "prop")
