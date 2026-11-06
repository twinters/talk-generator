"""Offline tests of talkgenerator's topic list (data/topics.txt), for suggestions and for checks on varied topics."""

import json

from talkgenerator import topics
from talkgenerator.checks import benchmark
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
