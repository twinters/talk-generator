"""Module providing language-related operations to manipulate strings"""

import logging
import re
import string
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import inflect
import nltk

logger = logging.getLogger("talkgenerator")

# (resource path, downloadable package name). NLTK 3.9 replaced the pickled `punkt` and
# `averaged_perceptron_tagger` models by `punkt_tab` and `averaged_perceptron_tagger_eng`.
REQUIRED_NLTK_RESOURCES = (
    ("tokenizers/punkt_tab", "punkt_tab"),
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    ("corpora/wordnet", "wordnet"),
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
