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
