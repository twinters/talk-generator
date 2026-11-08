import random
import unittest

from talkgenerator.util import language_util


class LanguageUtilTest(unittest.TestCase):
    def setUp(self) -> None:
        random.seed(123)

    def test_check_and_download_no_exception(self):
        language_util.check_and_download()

    def test_to_plural(self):
        self.assertEqual("cats", language_util.to_plural("a cat"))
        self.assertEqual("cats", language_util.to_plural("cat"))
        self.assertEqual("cats", language_util.to_plural("cats"))

    def test_is_noun(self):
        self.assertTrue(language_util.is_noun("cat"))
        self.assertFalse(language_util.is_noun("see"))
        self.assertFalse(language_util.is_noun("because"))

    def test_is_verb(self):
        self.assertTrue(language_util.is_verb("see"))
        self.assertFalse(language_util.is_verb("cat"))
        self.assertFalse(language_util.is_verb("because"))

    def test_to_singular(self):
        self.assertEqual("cat", language_util.to_singular("cat"))
        self.assertEqual("cat", language_util.to_singular("cats"))

    def test_generic(self):
        # Countable nouns in the plural, and mass nouns, plurals, names and phrases with an article as they are
        cases = {
            "penguin": "penguins",
            "lighthouse": "lighthouses",
            "swimming pool": "swimming pools",
            "child": "children",
            "a cat": "cats",
            "coffee": "coffee",
            "happiness": "happiness",
            "running": "running",
            "music": "music",
            "time": "time",  # (whose plural is common, in another sense)
            "art": "art",
            "ice cream": "ice cream",
            "physics": "physics",
            "data": "data",
            "sheep": "sheep",
            "penguins": "penguins",
            "glasses": "glasses",
            "the French Revolution": "the French Revolution",
            "Belgium": "Belgium",
            "a plant that won't die": "a plant that won't die",  # (a clause about its noun: as it is)
            "a message in a bottle": "a message in a bottle",  # (an "a" and words about its noun after it: as it is)
            "a cup of tea": "a cup of tea",
            "an apple in the box": "an apple in the box",
            "game of thrones": "game of thrones",
            "": "",
        }
        self.assertEqual(cases, {phrase: language_util.generic(phrase) for phrase in cases})

    def test_one(self):
        cases = {
            "penguin": "a penguin",
            "owl": "an owl",
            "hour": "an hour",
            "unicorn": "a unicorn",
            "coffee": "coffee",
            "penguins": "penguins",
            "the moon": "the moon",
            "a sofa that eats remotes": "a sofa that eats remotes",
            "a cup of tea": "a cup of tea",  # (not "cup of tea", for its last word, "tea")
            "a day at the beach": "a day at the beach",
        }
        self.assertEqual(cases, {phrase: language_util.one(phrase) for phrase in cases})

    def test_countable_and_plural_nouns(self):
        self.assertTrue(language_util.is_countable("penguin") and language_util.is_countable("swimming pool"))
        self.assertFalse(language_util.is_countable("coffee") or language_util.is_countable("penguins"))
        self.assertTrue(language_util.is_plural_noun("penguins") and language_util.is_plural_noun("glasses"))
        self.assertFalse(language_util.is_plural_noun("bus") or language_util.is_plural_noun("physics"))

    def test_bare(self):
        cases = {
            "penguins": "penguin",
            "the moon": "moon",
            "a cat": "cat",
            "coffee": "coffee",
            "physics": "physics",
            "the French Revolution": "French Revolution",
            "a sofa that eats remotes": "sofa that eats remotes",  # (its clause's words stay)
            "a cup of tea": "cup of tea",
            "game of thrones": "game of thrones",  # (not "game of throne": its noun is "game")
        }
        self.assertEqual(cases, {phrase: language_util.bare(phrase) for phrase in cases})

    def test_title_case(self):
        self.assertEqual("A Plant That Won't Die", language_util.title_case("a plant that won't die"))
        self.assertEqual("The Rise Of AI", language_util.title_case("the rise of AI"))
        self.assertEqual("Penguins", language_util.title_case("penguins"))

    def test_capitalised(self):
        self.assertEqual("French fries", language_util.capitalised("french fries"))
        self.assertEqual("", language_util.capitalised(""))

    def test_ing(self):
        self.assertEqual("toying", language_util.to_ing_form("toy"))
        self.assertEqual("playing", language_util.to_ing_form("play"))
        self.assertEqual("lying", language_util.to_ing_form("lie"))
        self.assertEqual("flying", language_util.to_ing_form("fly"))
        self.assertEqual("fleeing", language_util.to_ing_form("flee"))
        self.assertEqual("making", language_util.to_ing_form("make"))

    def test_verb_detection(self):
        self.assertEqual(
            "ACT like a cat",
            language_util.apply_function_to_verb("act like a cat", str.upper),
        )
        # self.assertEqual("kitten PROOF your house",
        #                  language_util.apply_function_to_verb("kitten proof your house", str.upper))

    def test_to_present_participle(self):
        self.assertEqual("acting like a cat", language_util.to_present_participle("act like a cat"))
        self.assertEqual(
            "quitly acting like a cat",
            language_util.to_present_participle("quitly act like a cat"),
        )

    def test_replace(self):
        self.assertEqual(
            "this is your test",
            language_util.replace_word("this is my test", "my", "your"),
        )
        self.assertEqual(
            "test if morphed, before comma",
            language_util.replace_word("test if changed, before comma", "changed", "morphed"),
        )
        self.assertEqual(
            "Success capital",
            language_util.replace_word("Test capital", "test", "success"),
        )
        self.assertEqual(
            "Your test is testing if your, is changed",
            language_util.replace_word("My test is testing if my, is changed", "my", "your"),
        )
        self.assertEqual(
            "Last word is morphed",
            language_util.replace_word("Last word is changed", "changed", "morphed"),
        )

    def test_get_last_noun_and_article(self):
        self.assertEqual(
            "a cat",
            language_util.get_last_noun_and_article("introduce your family to a cat"),
        )
        self.assertEqual(
            "the family",
            language_util.get_last_noun_and_article("show your cat to the family"),
        )
        self.assertEqual("my cat", language_util.get_last_noun_and_article("What to do with my cat"))
        self.assertEqual("your cat", language_util.get_last_noun_and_article("do you like your cat"))

    def test_replace_pronouns(self):
        self.assertEqual(
            "I care about me and my family",
            language_util.second_to_first_pronouns("I care about you and your family"),
        )

        # def test_is_noun(self):
        #     self.assertTrue(language_util.is_noun("cat"))
        #     self.assertTrue(language_util.is_noun("dog"))
        #     self.assertTrue(language_util.is_noun("food"))
        #     self.assertTrue(language_util.is_noun("pet"))

        # def test_is_verb(self):
        #     self.assertTrue(language_util.is_verb("act"))
        #     self.assertTrue(language_util.is_verb("pet"))
        #     self.assertTrue(language_util.is_verb("kiss"))

        # def test_is_verb_action(self):
        #     self.assertTrue(language_util.is_verb("kill a mockingbird"))
        #     self.assertTrue(language_util.is_verb("act like a cat"))
        #     self.assertTrue(language_util.is_verb("speak English"))

    if __name__ == "__main__":
        unittest.main()
