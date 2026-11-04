import random
import unittest

from talkgenerator.util import random_util


class RandomUtilTest(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def test_weighted_random_all_appear(self):
        possibilities = (1, "one"), (4, "four"), (6, "six"), (7, "seven")
        results = set()
        for _ in range(10000):
            if len(results) == len(possibilities):
                break
            results.add(random_util.weighted_random(possibilities))
        self.assertEqual({"one", "four", "six", "seven"}, results)

    def test_weighted_random_all_appear_double_values(self):
        possibilities = (0.1, "one"), (0.4, "four"), (0.6, "six"), (0.7, "seven")
        results = set()
        for _ in range(1000):
            if len(results) == len(possibilities):
                break
            results.add(random_util.weighted_random(possibilities))
        self.assertEqual({"one", "four", "six", "seven"}, results)

    def test_weighted_random_all_appear_double_values_appearances(self):
        possibilities = (0.1, "one"), (0.4, "four")
        ones = 0
        fours = 0
        for _ in range(1000):
            generated = random_util.weighted_random(possibilities)
            if generated == "one":
                ones += 1
            elif generated == "four":
                fours += 1

        # Ones should appear 1/5 * 1000 ~ 200 times
        self.assertTrue(150 < ones < 250)
        # Ones should appear 4/5 * 1000 ~ 800 times
        self.assertTrue(750 < fours < 850)


if __name__ == "__main__":
    unittest.main()
