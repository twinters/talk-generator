import unittest

import pytest

from talkgenerator.sources import goodreads

pytestmark = pytest.mark.network


class GoodReadsTest(unittest.TestCase):
    def test_cat_search(self):
        cat_quotes = goodreads.search_quotes("cat", 5)
        # Check if starts with quote marks
        self.assertEqual('"', cat_quotes[0][0])

    def test_too_many_quotes_amount(self):
        quotes = goodreads.search_quotes("cat nine tails", 25)
        # Check if starts with quote marks
        self.assertTrue(bool(quotes) and len(quotes) > 0)

    def test_no_quotes(self):
        quotes = goodreads.search_quotes("qsdfqsdfq", 100)
        # Check if starts with quote marks
        self.assertTrue(len(quotes) == 0)


if __name__ == "__main__":
    unittest.main()
