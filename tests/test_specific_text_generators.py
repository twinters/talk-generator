import random
import unittest

import pytest

from talkgenerator.sources import packs

default_number_of_generations = 100
default_arguments = {"seed": "house", "presenter": "A. Nonymous", "topic": "house"}


class SpecificTextGeneratorTest(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def _tracery_tester(self, rule, print_generations=False):
        tracery_generator = packs.pack().tracery(rule)
        generations = [tracery_generator(default_arguments) for _ in range(0, default_number_of_generations)]
        if print_generations:
            print("\n".join(generations))
        self.assertEqual(len(generations), default_number_of_generations)

    def _templated_text_generator_tester(
        self,
        rule,
        print_generations=False,
        number_of_generations=default_number_of_generations,
        seed=default_arguments["seed"],
    ):
        templated_generator = packs.pack().templates(rule)
        arguments = dict(default_arguments)
        arguments["seed"] = seed
        generations = [templated_generator(arguments) for _ in range(0, number_of_generations)]
        if print_generations:
            print("\n".join(generations))
        self.assertEqual(len(generations), number_of_generations)
        return generations

    def test_talk_title_generator(self):
        self._tracery_tester("title.talk_title")

    def test_talk_subtitle_generator(self):
        self._tracery_tester("title.presenter_job")

    @pytest.mark.network  # uses WikiHow
    def test_anecdote_prompt_generator(self):
        self._templated_text_generator_tester("statements.anecdote", True)

    @pytest.mark.network  # uses WikiHow
    def test_captions_generator(self):
        generations = self._templated_text_generator_tester(
            "captions.two_captions",
            True,
            number_of_generations=100,
            seed="cat",
        )

        for generation in generations:
            self.assertTrue("<built-in method" not in generation)


if __name__ == "__main__":
    unittest.main()
