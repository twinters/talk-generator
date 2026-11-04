import unittest

import pytest

from talkgenerator.sources import shitpostbot

pytestmark = pytest.mark.network


class ShitPostBot(unittest.TestCase):
    def test_shitpostbot_search(self):
        image_urls = shitpostbot.search_images("cat")
        self.assertTrue(len(image_urls) > 0)

    def test_shitpostbot_search_rated(self):
        image_urls = shitpostbot.search_images_rated("cat")
        self.assertTrue(len(image_urls) > 0)
        # Check if the rating of the first one is large
        self.assertTrue(int(image_urls[0][0]) > 20)


if __name__ == "__main__":
    unittest.main()
