"""Module providing language-related operations to manipulate strings"""

import logging
import re
import string
from collections.abc import Callable, Sequence
from functools import cache, lru_cache
from pathlib import Path
from typing import Final

import inflect
import nltk
from wordfreq import zipf_frequency

logger = logging.getLogger("talkgenerator")

# (resource path, downloadable package name). NLTK 3.9 replaced the pickled `punkt` and
# `averaged_perceptron_tagger` models by `punkt_tab` and `averaged_perceptron_tagger_eng`.
REQUIRED_NLTK_RESOURCES = (
    ("tokenizers/punkt_tab", "punkt_tab"),
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    ("corpora/wordnet", "wordnet"),
    ("corpora/stopwords", "stopwords"),  # for the language check (talkgenerator.checks.deck)
)


def check_and_download() -> bool:
    """Make sure the NLTK resources we use are available, downloading missing ones."""
    try:
        for resource_path, package in REQUIRED_NLTK_RESOURCES:
            _check_and_download_corpus(resource_path, package)
    except Exception as e:
        logger.error("Could not prepare NLTK data: %s", e)
        print_corpus_download_warning()
        return False
    return True


def _is_available(resource_path: str) -> bool:
    try:
        nltk.data.find(resource_path)
        return True
    except LookupError:
        try:
            nltk.data.find(resource_path + ".zip")
            return True
        except LookupError:
            return False


def _check_and_download_corpus(resource_path: str, package: str) -> None:
    if _is_available(resource_path):
        return
    logger.info("Downloading NLTK resource '%s'...", package)
    if _download(package):
        return
    # The default download folder can be unusable (read-only, or redirected by a sandbox such as an
    # MSIX-packaged app). ~/nltk_data is on NLTK's search path on every platform, so try that next.
    fallback_dir = Path.home() / "nltk_data"
    if _download(package, str(fallback_dir)) and _is_available(resource_path):
        return
    raise LookupError(f"NLTK resource '{package}' is missing and could not be downloaded")


@cache
def stopwords(language: str) -> frozenset[str]:
    """NLTK's stopwords of a language ("dutch", "english", ...): its most common little words, such as "the" and
    "of". Downloads NLTK's lists the first time they're needed."""
    _check_and_download_corpus("corpora/stopwords", "stopwords")
    from nltk.corpus import stopwords as corpus

    return frozenset(corpus.words(language))


def _download(package: str, download_dir: str | None = None) -> bool:
    try:
        return bool(nltk.download(package, download_dir=download_dir, quiet=True, raise_on_error=True))
    except Exception as e:
        logger.warning("Downloading NLTK resource '%s' to %s failed: %s", package, download_dir or "default folder", e)
        return False


def print_corpus_download_warning() -> None:
    packages = " ".join(package for _, package in REQUIRED_NLTK_RESOURCES)
    corpus_warning = f"""
    Hmm...
    ---------------------

    We had some trouble downloading the NLTK corpora.
    Try running the following from a command line. This should
    download the needed packages, or tell you what the issue is.

    $ python -m nltk.downloader {packages}
    """
    logger.warning(corpus_warning)


# Helpers


def _replace_word_one_case(sentence: str, word: str, replacement: str, flags: int = 0) -> str:
    return re.sub(r"(^|\W)" + word + r"(\W|$)", r"\1" + replacement + r"\2", sentence, flags=flags)


def replace_word(sentence: str, word: str, replacement: str) -> str:
    lowered = _replace_word_one_case(sentence, word.lower(), replacement.lower())
    upper = _replace_word_one_case(lowered, word.upper(), replacement.upper())
    titled = _replace_word_one_case(upper, word.title(), replacement.title())
    result = _replace_word_one_case(titled, word, replacement, re.I)
    return result


def get_pos_tags(word: str) -> list[str]:
    """Returns all possible POS tags for a given word according to nltk"""
    tags = nltk.pos_tag(nltk.word_tokenize(word))
    tags_strings = [tag[1] for tag in tags]
    return tags_strings


# Verbs


def get_verb_index(words: list[str]) -> int:
    seen_adverb = False
    for i in range(len(words)):
        tags = get_pos_tags(words[i])
        # Is verb: return
        if "VB" in tags:
            return i
        # Is adverb: return next non adverb
        if "RB" in tags:
            seen_adverb = True
            continue
        # Something following an adverb thats not an adverb? See as verb
        if seen_adverb:
            return i
    return 0


def apply_function_to_verb(action: str, func: Callable[[str], str]) -> str:
    words = action.split(" ")
    verb_index = get_verb_index(words)
    first_word = func(words[verb_index])
    if len(words) == 1:
        return first_word
    return (" ".join(words[:verb_index]) + " " + first_word + " " + " ".join(words[verb_index + 1 :])).strip()


def to_present_participle(action: str) -> str:
    return apply_function_to_verb(action, to_ing_form)


# From https://github.com/arsho/46-Simple-Python-Exercises-Solutions/blob/master/problem_25.py
def _make_ing_form(passed_string: str) -> str:
    passed_string = passed_string.lower()
    letter = list(string.ascii_lowercase)
    vowel = ["a", "e", "i", "o", "u"]
    consonant = [c for c in letter if c not in vowel]
    exception = ["be", "see", "flee", "knee", "lie"]

    if passed_string.endswith("ie"):
        passed_string = passed_string[:-2]
        return passed_string + "ying"

    elif passed_string.endswith("e"):
        if passed_string in exception:
            return passed_string + "ing"
        else:
            passed_string = passed_string[:-1]
            return passed_string + "ing"

    elif passed_string.endswith("y") or passed_string.endswith("w"):
        return passed_string + "ing"

    elif (
        len(passed_string) >= 3
        and passed_string[-1] in consonant
        and passed_string[-2] in vowel
        and passed_string[-3] in consonant
    ):
        passed_string += passed_string[-1]
        return passed_string + "ing"
    else:
        return passed_string + "ing"


def to_ing_form(passed_string: str) -> str:
    result = _make_ing_form(passed_string)
    if passed_string.islower():
        return result.lower()
    if passed_string.isupper():
        return result.upper()
    if passed_string.istitle():
        return result.title()
    return result


inflect_engine = inflect.engine()


def is_singular(word: str) -> bool:
    # inflect >= 7 type-checks its arguments and rejects empty strings
    if not word or not word.strip():
        return True
    return inflect_engine.singular_noun(word) is False


def is_plural(word: str) -> bool:
    if not word or not word.strip():
        return False
    return bool(inflect_engine.singular_noun(word))


def to_plural(word: str) -> str:
    if not word or not word.strip():
        return word
    if is_singular(word):
        if word.startswith("a "):
            word = word[2:]
        return inflect_engine.plural(word)
    return word


def to_singular(word: str) -> str:
    if is_plural(word):
        singular = inflect_engine.singular_noun(word)
        return singular if singular else word
    return word


def add_article(word: str) -> str:
    # TODO: Maybe more checks, some u's cause "an", or some big letters in case it's an abbreviation
    word_lower = word.lower()
    article = "a"
    if word_lower.startswith(("a", "e", "i", "o")):
        article = "an"
    return article + " " + word


# HOW ENGLISH SPEAKS OF A THING IN GENERAL: "I love penguins", but "I love coffee" (not "coffees") and "I love the
# French Revolution". A slide's seed can be any of these, so templates that say "Love {seed.generic}" or "Is this
# {seed.one}?" read right for each (and leave out verbs that would have to agree with it).

# Words that open a phrase with an article of its own: such a phrase stays as it is
_DETERMINERS: Final = frozenset(
    ("the", "a", "an", "my", "your", "our", "their", "his", "her", "its", "this", "that")
    + ("these", "those", "some", "every", "no", "all")
)
# How much rarer than a noun its plural may be in English (on wordfreq's Zipf scale) for the noun to be one English
# counts: "penguins" is about as common as "penguin", "lighthouses" 0.8 rarer than "lighthouse", but "coffees" 1.8
# rarer than "coffee", "music" and "happiness" have no plurals to speak of, and "rains" is a verb as often as not
_RARER_PLURAL: Final = 0.9


@lru_cache(maxsize=4096)
def _zipf(word: str) -> float:
    return float(zipf_frequency(word, "en"))


def _has_article(phrase: str) -> bool:
    words = phrase.lower().split()
    return len(words) > 1 and words[0] in _DETERMINERS


def is_plural_noun(phrase: str) -> bool:
    """Whether the phrase ends in a plural noun ("penguins", "glasses"): one whose singular is a word as common as it,
    give or take (so "bus" and "cactus" are no plurals of "bu" and "cactu", nor "physics" or "data")."""
    last = phrase.split()[-1] if phrase.split() else ""
    if not last:
        return False
    singular = inflect_engine.singular_noun(last)
    return bool(singular) and singular != last and _zipf(singular) >= _zipf(last) - 1.0


def is_countable(phrase: str) -> bool:
    """Whether English counts what the phrase ends in ("a penguin, two penguins") rather than speaking of it as an
    amount ("coffee", "happiness", "running", "physics"): whether the plural of its last word is about as common as
    that word, by wordfreq's English frequencies."""
    last = phrase.split()[-1] if phrase.split() else ""
    if not last or is_plural_noun(last):
        return False
    plural = inflect_engine.plural_noun(last)
    if not plural or plural == last:
        return False  # (sheep, fish, news: the same in the plural)
    many = _zipf(plural)
    return many > 0 and _zipf(last) - many < _RARER_PLURAL


def _without_a(phrase: str) -> str:
    """The phrase without an "a" or "an" in front ("a cup": "cup")."""
    words = phrase.split()
    return " ".join(words[1:]) if len(words) > 1 and words[0].lower() in ("a", "an") else phrase


def generic(phrase: str) -> str:
    """The phrase as English speaks of such things in general ("I love ..."): a countable noun in the plural
    ("penguins", "lighthouses"), and as it is a mass noun ("coffee", "happiness"), a plural, a name, or a phrase with
    an article of its own ("the French Revolution")."""
    text = _without_a(phrase.strip())
    if not text or _has_article(text) or is_plural_noun(text) or not is_countable(text):
        return text
    return to_plural(text)


def one(phrase: str) -> str:
    """One of the phrase ("Is this ...?"): a countable noun with its article ("a lighthouse", "an owl", "an hour"),
    and the others as generic has them ("coffee", "penguins", "the French Revolution")."""
    text = _without_a(phrase.strip())
    if not text or _has_article(text) or is_plural_noun(text) or not is_countable(text):
        return text
    return str(inflect_engine.a(text))


def adjunct(phrase: str) -> str | None:
    """The phrase as English puts it before another noun ("the penguin pyramid", "coffee prices"), or after a word that
    counts one of it ("its first penguin"): a plural noun in the singular ("penguins": "penguin", but "physics" and
    "news" stay), and the others as they are. None for a phrase with an article of its own ("the French Revolution"),
    which can't go there: a template that asks for it then gives way to another."""
    text = _without_a(phrase.strip())
    if not text or _has_article(text):
        return None
    if not is_plural_noun(text):
        return text
    *before, last = text.split()
    return " ".join([*before, str(inflect_engine.singular_noun(last))])


# WHICH OF SEVERAL OPTIONS A TEXT NAMES, as a quiz's explanation names its answer

# Words just before an option's words that turn naming it into dismissing it ("not the moon", "unlike Belgium")
_DISMISSING: Final = frozenset(
    ("not", "never", "no", "nor", "neither", "unlike", "instead", "rather", "except", "isn't", "wasn't", "aren't")
)
# A letter that names an option ("Option C", "the answer is (B)", or "B)" opening the text), but not "A" as an article
_LETTER: Final = re.compile(r"\b(?:[Oo]ption|[Aa]nswer(?: is)?|[Cc]hoice)\s+\(?([A-D])\b(?! [a-z])|^\(?([A-D])[).:,]")
_WORDS: Final = re.compile(r"[^\W_]+(?:'[^\W_]+)?")


def _stem(word: str) -> str:
    """The word without the endings English puts on it, roughly: "guides", "guided", "guiding" and "guide" all give
    "guid"."""
    for ending in ("ing", "ed", "es", "s", "e"):
        if len(word) > len(ending) + 2 and word.endswith(ending):
            return word[: -len(ending)]
    return word


def named_options(text: str, options: Sequence[str | None], stopwords_of: str = "english") -> list[int]:
    """Which of the options the text names (their places in the list): the one whose letter it names ("Option C",
    "C) Because..."), and those whose words that say something, and that set them apart from the other options, are
    nearly all in it (two in three, in any form: "guides" for "guiding"), unless a word just before them dismisses
    them ("not the moon"). Options that are None are no options."""
    words = _WORDS.findall(text.lower())
    stems = [_stem(word) for word in words]
    try:
        little = stopwords(stopwords_of)
    except (LookupError, OSError, ValueError):  # (NLTK's lists can't be had: every word says something)
        little = frozenset()
    letters = {letter for found in _LETTER.findall(text.strip()) for letter in found if letter}
    contents: dict[int, list[str]] = {}
    for index, option in enumerate(options):
        own = _WORDS.findall(option.lower()) if option else []
        contents[index] = [_stem(word) for word in own if word not in little] or [_stem(word) for word in own]
    named = []
    for index, content in contents.items():
        if not options[index]:
            continue
        others = {stem for other, stems_of in contents.items() if other != index for stem in stems_of}
        telling = [stem for stem in content if stem not in others] or content  # ("ships" in two options tells none)
        found = [stems.index(stem) for stem in telling if stem in stems]
        if "ABCD"[index] in letters:
            named.append(index)
        elif telling and 3 * len(found) >= 2 * len(telling):
            first = min(found)
            if not any(word in _DISMISSING for word in words[max(0, first - 3) : first]):
                named.append(index)
    return named


def capitalised(text: str) -> str:
    """The text with its first letter in capitals (and the others as they are: "French fries", not "French Fries")."""
    return text[:1].upper() + text[1:]


# Pronouns


def second_to_first_pronouns(sentence: str) -> str:
    sentence = replace_word(sentence, "yours", "mine")
    sentence = replace_word(sentence, "your", "my")
    sentence = replace_word(sentence, "you", "me")
    return sentence


# POS tag checkers


# TODO: These don't work well, but might be useful features in our text generation language
def is_noun(word: str) -> bool:
    return "NN" in get_pos_tags(word)


def is_verb(word: str) -> bool:
    return "VB" in get_pos_tags(word)


# Places (WordNet)

# WordNet categories whose members make sense as an answer to "where can you find X?".
# Countries and regions are left out on purpose: they're rarely related to the topic.
_PLACE_CATEGORIES = frozenset(
    {
        "structure.n.01",  # buildings, bridges, pens, ...
        "room.n.01",
        "container.n.01",  # boxes, bags, bottles, tins, ...
        "furniture.n.01",
        "body_of_water.n.01",
        "geological_formation.n.01",
        "establishment.n.04",  # shops, hotels, ...
        "facility.n.01",
        "tract.n.01",  # fields, gardens, parks, forests, ...
        "way.n.06",  # roads, paths, streets, ...
    }
)


@lru_cache(maxsize=2048)
def is_place(word: str) -> bool:
    """Whether the most common meaning of a noun is a place or a container, according to WordNet."""
    from nltk.corpus import wordnet

    try:
        synsets = wordnet.synsets(word.strip().replace(" ", "_"), pos=wordnet.NOUN)
    except LookupError:
        logger.warning("WordNet is not available; can't recognise places")
        return False
    if not synsets:
        return False
    # Only the first (most common) sense: rarer senses give false positives such as "amphibian" (a vehicle)
    categories = {hypernym.name() for path in synsets[0].hypernym_paths() for hypernym in path}
    return bool(categories & _PLACE_CATEGORIES)


@lru_cache(maxsize=2048)
def is_adjective(word: str) -> bool:
    """Whether WordNet knows the word (or phrase) as an adjective, such as "fluffy" or "salted" (and not "day"). True
    when WordNet isn't available, as it can't tell."""
    from nltk.corpus import wordnet

    try:
        return bool(wordnet.synsets(word.strip().replace(" ", "_"), pos=wordnet.ADJ))
    except LookupError:
        logger.warning("WordNet is not available; can't recognise adjectives")
        return True


# Special operators


def get_last_noun_and_article(sentence: str) -> str | None:
    tokens = nltk.word_tokenize(sentence)
    tags = nltk.pos_tag(tokens)

    noun: str | None = None
    for tag in reversed(tags):
        if "NN" in tag[1]:
            if noun:
                noun = (str(tag[0]) + " " + noun).strip()
            else:
                noun = str(tag[0])

        # If encountering an article while there is a noun found
        elif noun:
            if "DT" in tag[1] or "PRP$" in tag[1]:
                return str(tag[0]) + " " + noun
            return noun

    return None


def replace_non_alphabetical_characters(text: str) -> str:
    return re.sub(r"[^A-Za-z\s\b -]+", "", text)


def is_vowel(character: str) -> bool:
    return character in ["a", "e", "i", "o", "u"]


def is_consonant(character: str) -> bool:
    return not is_vowel(character)
