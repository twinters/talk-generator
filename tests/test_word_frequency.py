import wordfreq

from talkgenerator.sources import word_frequency


def test_rarest_word():
    assert word_frequency.get_rarest_word("Why I love my cat") == "cat"
    assert word_frequency.get_rarest_word("Peace is what I want most") == "Peace"


def test_unknown_words_are_rarest():
    assert word_frequency.get_rarest_word("My trip to Zorblaxia") == "Zorblaxia"


def test_no_words():
    assert word_frequency.get_rarest_word("") is None
    assert word_frequency.get_rarest_word("  - 123 ") is None


def test_frequency_order():
    assert word_frequency.get_frequency("the") > word_frequency.get_frequency("cat") > 0


# SPELLING FIXES IN THE TALK'S LANGUAGE


def test_a_word_of_the_talks_language_doesnt_become_an_english_one():
    assert word_frequency.fix_spelling("matare", "sv") == "matare"  # (Swedish for a feeder: once "mature")
    assert word_frequency.fix_spelling("attractieve", "nl") == "attractieve"  # (once "attractive")
    assert word_frequency.fix_spelling("pengiuns", "sv") == "penguins"  # (what's typed for a talk may be English)


def test_a_rare_word_of_the_talks_language_doesnt_become_another_of_its_words():
    # (D74: each a hundred times rarer than a word a letter away, which talks were about instead)
    assert word_frequency.fix_spelling("os polvos", "pt") == "os polvos"  # (octopuses: once "povos", peoples)
    assert word_frequency.fix_spelling("i polpi", "it") == "i polpi"  # (octopuses: once "colpi", blows)
    assert word_frequency.fix_spelling("lämlar", "sv") == "lämlar"  # (lemmings: once "lämnar", leaves)
    assert word_frequency.fix_spelling("verkeerskegels", "nl") == "verkeerskegels"  # (once the rules of the road)
    assert word_frequency.fix_spelling("la tarte Tatin", "fr") == "la tarte Tatin"  # (once "Matin")
    assert word_frequency.fix_spelling("faglar", "sv") == "fåglar"  # (but its accents are put right)


def test_compounds_of_the_talks_language_stay_as_typed():
    # Dutch, German and Swedish write them as one word: rarely one that wordfreq knows, yet no misspelling. (They
    # were once taken as near matches: "tomato", "robotar" (robots), "spökar" (haunts), "mansion", "computerised")
    for compound in ("pingvinsekt", "tomatbok", "robotarmé", "spökarmé", "kärnkraftsolycka", "pingvinkaffekult"):
        assert word_frequency.fix_spelling(compound, "sv") == compound
    assert word_frequency.fix_spelling("maanspion", "nl") == "maanspion"
    assert word_frequency.fix_spelling("Computerkrise", "de") == "Computerkrise"
    assert word_frequency.fix_spelling("mutiro", "pt") == "mutirão"  # (Portuguese has no such compounds)


def test_misspellings_in_the_talks_language_are_still_fixed():
    assert word_frequency.fix_spelling("pingvner", "sv") == "pingviner"
    assert word_frequency.fix_spelling("kvallens", "sv") == "kvällens"  # (one edit: the dots left out)
    assert word_frequency.fix_spelling("faglar", "sv") == "fåglar"  # (the ring left out: once "naglar", nails)
    assert word_frequency.fix_spelling("Varför jag gick med i en pingvinsekt", "sv") == (
        "Varför jag gick med i en pingvinsekt"
    )


# THE WORD LISTS IT KEEPS


def _lists() -> int:
    """How many languages' word lists wordfreq keeps (their frequencies and most frequent words come from them)."""
    return wordfreq.get_frequency_list.cache_info().currsize


def test_a_language_whose_list_isnt_kept_has_the_others_forgotten_after_a_quiet_while(monkeypatch):
    # (wordfreq keeps a language's whole list once it's asked a word of it: 58 MB for German, 254 MB for the eight)
    word_frequency.forget_word_lists()
    word_frequency._zipf_frequency.cache_clear()  # (so that every word below is asked of wordfreq)
    assert _lists() == 0
    word_frequency.get_frequency("fiets", "nl")
    word_frequency.get_frequency("bicicleta", "pt")  # (right after a Dutch word: no reason to forget Dutch's list)
    assert _lists() == 2
    monkeypatch.setattr(word_frequency, "QUIET_SECONDS", -1.0)  # (as if a while went by)
    word_frequency.get_frequency("bicycle")  # (English words are no reason to forget the others)
    assert _lists() == 3
    assert word_frequency.get_frequency("cykel", "sv") > 0
    assert _lists() == 1  # (Swedish's alone)
    assert word_frequency.get_frequency("hond", "nl") > 0  # (and a list that went comes back)
    assert _lists() == 1


def test_forgotten_word_lists_come_back_for_spelling_fixes():
    assert word_frequency.fix_spelling("pingvner", "sv") == "pingviner"
    word_frequency.forget_word_lists()
    assert _lists() == 0
    assert word_frequency.fix_spelling("pingvner", "sv") == "pingviner"  # (Swedish's most frequent words, again)
    assert _lists() == 2  # (and English's, which a word may be in too)
