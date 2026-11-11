"""Offline tests of talkgenerator's topic lists (data/topics.txt, and data/topics.<code>.txt for the other languages
talks can be in: D74), for suggestions and for checks on varied topics."""

import json

import pytest

from talkgenerator import titles, topics
from talkgenerator.checks import benchmark
from talkgenerator.plan import languages
from talkgenerator.util import random_util
from tests import test_seeds
from tests.test_checks import fake_schema as fake_schema  # the fake schema (a fixture)


def test_the_list_is_long_and_has_no_repeats():
    every = topics.all_topics()
    assert len(every) >= 500
    assert len({topic.lower() for topic in every}) == len(every)
    assert all(topic == topic.strip() and topic and not topic.startswith("#") for topic in every)


def test_topics_are_short_and_plain():
    # A phone shows about 20 characters of the site's topic field: a few longer ones are fine
    every = topics.all_topics()
    assert max(len(topic) for topic in every) <= 30
    assert sum(len(topic) > 20 for topic in every) < len(every) / 10
    assert not [topic for topic in every if any(mark in topic for mark in "{}#<>|")]


def test_random_topics_come_from_the_seed():
    def draw(seed):
        with random_util.use(random_util.Rng(seed)):
            return topics.random_topics(5)

    assert draw(1) == draw(1) != draw(2)
    assert len(set(draw(1))) == 5 and set(draw(1)) <= set(topics.all_topics())
    with random_util.use(random_util.Rng(1)):
        assert len(topics.random_topics(10**6)) == len(topics.all_topics())


def test_a_check_on_random_topics(fake_schema, tmp_path):
    report = tmp_path / "report.json"
    arguments = ["--random", "2", "--schema", "fake", "--slides", str(test_seeds.NUM_SLIDES), "--no_determinism"]
    assert benchmark.main([*arguments, "--report", str(report)]) == 0
    checked = [talk["topic"] for talk in json.loads(report.read_text(encoding="utf-8"))["talks"]]
    assert len(checked) == 2 and set(checked) <= set(topics.all_topics())
    assert benchmark.main([*arguments, "--report", str(tmp_path / "again.json")]) == 0
    again = [talk["topic"] for talk in json.loads((tmp_path / "again.json").read_text(encoding="utf-8"))["talks"]]
    assert again == checked  # the same first seed draws the same topics


# THE OTHER LANGUAGES' LISTS (D74)

OTHERS = [code for code in languages.LANGUAGES if code != languages.ENGLISH.code]


@pytest.mark.parametrize("language", OTHERS)
def test_every_language_has_a_list_of_its_own(language):
    every = topics.all_topics(language)
    assert len(every) >= 300
    assert len({topic.lower() for topic in every}) == len(every)
    assert all(topic == topic.strip() and topic and not topic.startswith("#") for topic in every)
    # (the site's topic field fits about 27 characters on a phone, with a smaller font)
    assert max(len(topic) for topic in every) <= 27
    # (a comma would make it several topics: see titles.topics_from)
    assert not [topic for topic in every if any(mark in topic for mark in "{}#<>|,")]
    # Its own topics, not English's copied (a few words are the same in both: "yoga", "karaoke")
    english = {topic.lower() for topic in topics.all_topics()}
    assert sum(topic.lower() in english for topic in every) < len(every) / 10


@pytest.mark.parametrize("language", list(languages.LANGUAGES))
def test_every_topic_is_read_as_typed(language):
    # What the site does with a topic it suggests, as with one typed (titles.topics_from): the spelling fixes leave
    # it as it is (they once made Swedish "lämlar", lemmings, "lämnar", and French "le yodel" "le model"), and the
    # longer ones are titles, which the language model gets as they are
    for topic in topics.all_topics(language):
        assert titles.clearly_a_title(topic, language) or titles.topics_from(topic, language) == [topic], topic


def test_random_topics_of_a_language():
    with random_util.use(random_util.Rng(1)):
        drawn = topics.random_topics(5, "nl")
    assert len(set(drawn)) == 5 and set(drawn) <= set(topics.all_topics("nl"))
    assert topics.topics_file() == topics.TOPICS_FILE and topics.topics_file("nl") == "data/topics.nl.txt"


def test_a_language_talks_cant_be_in_has_no_list():
    with pytest.raises(ValueError, match="doesn't know the language 'xx'"):
        topics.random_topics(3, "xx")


def test_a_check_on_random_topics_in_another_language(fake_schema, tmp_path):
    report = tmp_path / "report.json"
    arguments = ["--random", "2", "--language", "nl", "--schema", "fake", "--slides", str(test_seeds.NUM_SLIDES)]
    assert benchmark.main([*arguments, "--no_determinism", "--report", str(report)]) == 0
    checked = [talk["topic"] for talk in json.loads(report.read_text(encoding="utf-8"))["talks"]]
    assert len(checked) == 2 and set(checked) <= set(topics.all_topics("nl"))
