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
