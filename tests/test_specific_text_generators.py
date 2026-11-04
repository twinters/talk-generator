import random
import unittest

import pytest

from talkgenerator.schema.content_generator_structures import (
    create_templated_text_generator,
    create_tracery_generator,
)

default_number_of_generations = 100
default_arguments = {"seed": "house", "presenter": "A. Nonymous", "topic": "house"}


class SpecificTextGeneratorTest(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def _tracery_tester(self, file_location, grammar_element="origin", print_generations=False):
        tracery_generator = create_tracery_generator(file_location, grammar_element)
        generations = [tracery_generator(default_arguments) for _ in range(0, default_number_of_generations)]
        if print_generations:
            print("\n".join(generations))
        self.assertEqual(len(generations), default_number_of_generations)

    def _templated_text_generator_tester(
        self,
        file_location,
        print_generations=False,
        number_of_generations=default_number_of_generations,
        seed=default_arguments["seed"],
    ):
        templated_generator = create_templated_text_generator(file_location)
        arguments = dict(default_arguments)
        arguments["seed"] = seed
        generations = [templated_generator(arguments) for _ in range(0, number_of_generations)]
        if print_generations:
            print("\n".join(generations))
        self.assertEqual(len(generations), number_of_generations)
        return generations

    def test_talk_title_generator(self):
        self._tracery_tester("data/text-templates/talk_title.json")

    def test_talk_subtitle_generator(self):
        self._tracery_tester("data/text-templates/talk_subtitle.json", "job")

    @pytest.mark.network  # uses WikiHow
    def test_anecdote_prompt_generator(self):
        self._templated_text_generator_tester("data/text-templates/anecdote_prompt.txt", True)

    @pytest.mark.network  # uses WikiHow
    def test_captions_generator(self):
        generations = self._templated_text_generator_tester(
            "data/text-templates/double_captions.txt",
            True,
            number_of_generations=100,
            seed="cat",
        )

        for generation in generations:
            self.assertTrue("<built-in method" not in generation)


if __name__ == "__main__":
    unittest.main()
