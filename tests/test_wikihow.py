import unittest
from talkgenerator.sources import wikihow

import pytest

pytestmark = pytest.mark.network


class WikiHowTest(unittest.TestCase):
    def test_wrong_wikihow_links_regression_test(self):
        actions = wikihow.get_related_wikihow_actions_basic_search("cat")
        print(actions)
        self.assertFalse("articles from wikiHow" in actions)

    def test_no_views_in_wikihow_action(self):
        actions = wikihow.get_related_wikihow_actions("grass")
        for action in actions:
            # No line breaks allowed
            self.assertFalse("\n" in action)
            # No number of views
            self.assertFalse(" views" in action and "Updated" in action)


if __name__ == "__main__":
    unittest.main()
