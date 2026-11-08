"""Offline tests of talkgenerator.util.wordnet: the places and adjectives WordNet knows, as NLTK's reader tells them,
without NLTK's reader (whose index took more than half of talkgenerator.com's memory at rest).

They read WordNet from NLTK's data, as talkgenerator does (language_util.check_and_download fetches it if it's missing).
"""

import subprocess
import sys

import pytest

from talkgenerator.util import language_util, wordnet


@pytest.fixture(scope="module", autouse=True)
def _wordnet_is_there():
    if not language_util.check_and_download():
        pytest.skip("NLTK's WordNet isn't available")


# Words that test the edges: plurals and irregular plurals, comparatives, phrases, capitals, words WordNet doesn't
# have, words whose most common meaning isn't a place (though a rarer one is), and words that are a noun as well as an
# irregular form of another (whose own meaning comes first)
WORDS = (
    "pond aquarium reef kitchen boxes box bottles bag glasses glass geese goose mice mouse feet teeth wolves knives "
    "leaves churches dishes men women children oxen data criteria cacti fungi alumni analyses bases axes media "
    "park forest garden gardens street road path highway bridge bridges tower house houses hotel shop shops store "
    "supermarket library libraries museum office offices school church castle cave caves mountain mountains lake "
    "river ocean sea beach desert field fields tin cupboard drawer bed beds sofa chair attic basement cellar "
    "garage barn stable zoo prison amphibian penguin penguins cat dog talk happiness idea music coffee machine "
    "volcano volcanoes moon origami computer internet space outer_space under the bed ice cream ice_cream "
    "fluffy salted happier happiest best better worse worst good bad fewer more most bigger biggest larger quick "
    "quicker running day fast red redder sunny sunnier lazy lazier hot cold cute xyzzy qwertyuiop the a of"
).split() + ["New York", "Penguin", "COFFEE", " pond ", "post office", "coffee shop", "parking lot", "", "  "]


def test_places_and_adjectives_are_nltk_s():
    from nltk.corpus import wordnet as nltk_wordnet

    def nltk_place(word):
        synsets = nltk_wordnet.synsets(word.strip().replace(" ", "_"), pos=nltk_wordnet.NOUN)
        if not synsets:
            return False
        names = {hypernym.name() for path in synsets[0].hypernym_paths() for hypernym in path}
        return bool(names & wordnet.PLACE_CATEGORIES)

    def nltk_adjective(word):
        return bool(nltk_wordnet.synsets(word.strip().replace(" ", "_"), pos=nltk_wordnet.ADJ))

    assert [(word, wordnet.is_place(word)) for word in WORDS] == [(word, nltk_place(word)) for word in WORDS]
    assert [(word, wordnet.is_adjective(word)) for word in WORDS] == [(word, nltk_adjective(word)) for word in WORDS]


def test_places_are_places_and_containers_by_their_most_common_meaning():
    for place in ("pond", "aquarium", "kitchen", "boxes", "bottles", "park", "street", "bridge", "parking lot", "cave"):
        assert wordnet.is_place(place), place
    # (glass is a container too, but first a material; a penguin and an idea are no place at all)
    for other in ("glass", "penguin", "idea", "happiness", "talk", "xyzzy", ""):
        assert not wordnet.is_place(other), other


def test_adjectives_are_found_in_any_form():
    for adjective in ("fluffy", "salted", "happier", "best", "worse", "redder", "sunniest"):
        assert wordnet.is_adjective(adjective), adjective
    for other in ("day", "penguin", "xyzzy", ""):
        assert not wordnet.is_adjective(other), other


def test_the_lexicon_is_small():
    lexicon = wordnet.load()
    assert len(lexicon.nouns) > 100_000 and len(lexicon.adjectives) > 20_000
    assert 1_000 < len(lexicon.places) < len(lexicon.nouns)
    # (hashes of 8 bytes a word: about a megabyte, where NLTK's reader keeps about 130 MB)
    assert sum(len(words) for words in (lexicon.nouns, lexicon.places, lexicon.adjectives)) * 8 < 2_000_000


def test_a_set_of_hashes_holds_its_words():
    words = wordnet.Hashes(["pond", "lake", "pond"])
    assert "pond" in words and "lake" in words
    assert "sea" not in words and 3 not in words
    assert len(words) == 2


def test_recognising_places_leaves_nltk_s_wordnet_reader_unloaded():
    # (in a process of its own: other tests load NLTK's reader, to compare)
    script = (
        "from talkgenerator.util import language_util\n"
        "from nltk.corpus import wordnet\n"
        "assert language_util.is_place('pond') and language_util.is_adjective('fluffy')\n"
        "print(type(wordnet).__name__)\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "LazyCorpusLoader"


def test_without_wordnet_nothing_is_a_place_and_everything_may_be_an_adjective(monkeypatch, caplog):
    def missing(name):
        raise LookupError("no WordNet")
        yield  # (a generator, as _lines is)

    monkeypatch.setattr(wordnet, "_lexicon", None)
    monkeypatch.setattr(wordnet, "_lines", missing)
    language_util.is_place.cache_clear()
    language_util.is_adjective.cache_clear()
    try:
        assert language_util.is_place("pond") is False
        assert language_util.is_adjective("penguin") is True
        assert "WordNet is not available" in caplog.text
    finally:
        language_util.is_place.cache_clear()
        language_util.is_adjective.cache_clear()
