import unittest

import pytest

from talkgenerator.schema.content_generator_structures import RedditImageSearcher
from talkgenerator.sources import reddit
from tests.support import requires_keys

pytestmark = [pytest.mark.network, requires_keys("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")]


class RedditTest(unittest.TestCase):
    def test_reddit_search_image(self):
        result = reddit.search_images("memes", "cat")
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    def test_reddit_simple(self):
        images = RedditImageSearcher("memes")("cat")
        self.assertTrue(len(images) > 0)
        sources = [image.get_source() for image in images if image.get_source() is not None]
        self.assertTrue(len(sources) > 0)

    def test_reddit_without_query_uses_hot_posts(self):
        images = RedditImageSearcher("gifs")("")
        self.assertTrue(len(images) > 0)


if __name__ == "__main__":
    unittest.main()
