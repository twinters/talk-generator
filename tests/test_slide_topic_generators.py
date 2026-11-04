import random
import unittest

import pytest

from talkgenerator.schema.slide_topic_generators import SideTrackingTopicGenerator

pytestmark = pytest.mark.network


class SlideTopicGeneratorsTest(unittest.TestCase):
    def setUp(self) -> None:
        random.seed(123)

    def test_conceptnet_sidetracking_standard(self):
        generator = SideTrackingTopicGenerator(["cat"], 5)
        self.assertTrue(len([seed for seed in generator.all_seeds() if seed is None]) == 0)

    def test_conceptnet_sidetracking_non_existing_topic(self):
        non_existing_word = "nonexistingword-bla-bla"
        generator = SideTrackingTopicGenerator([non_existing_word], 10)
        self.assertTrue(len([seed for seed in generator.all_seeds() if seed == non_existing_word]) == 10)

    def test_conceptnet_sidetracking_hard_topic(self):
        generator = SideTrackingTopicGenerator(["scratch furniture"], 10)
        self.assertTrue(len([seed for seed in generator.all_seeds() if seed is None]) == 0)

    def test_conceptnet_sidetracking_multi_topic(self):
        generator = SideTrackingTopicGenerator(["cat", "house", "dog"], 6)
        seeds = generator.all_seeds()
        print("multi_topic", seeds)
        self.assertTrue(seeds[0] == "cat")
        self.assertTrue(seeds[2] == "house")
        self.assertTrue(seeds[4] == "dog")
        # Nothing is none
        self.assertTrue(len([seed for seed in generator.all_seeds() if seed is None]) == 0)

    def test_conceptnet_sidetracking_multi_topic_one_each(self):
        topics = ["cat", "house", "chicken", "horse", "dog"]
        generator = SideTrackingTopicGenerator(topics, len(topics))
        self.assertEqual(topics, generator.all_seeds())


if __name__ == "__main__":
    unittest.main()
