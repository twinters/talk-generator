import unittest

import pytest

from talkgenerator.sources import unsplash
from tests.support import requires_keys

pytestmark = [pytest.mark.network, requires_keys("UNSPLASH_ACCESS_KEY")]


class UnsplashTest(unittest.TestCase):
    def test_unsplash_access(self):
        images = unsplash.search_photos("office")
        self.assertTrue(len(images) > 0)
        sources = [image.get_source() for image in images if image.get_source() is not None]
        self.assertTrue(len(sources) > 0)

    def test_unsplash_random(self):
        image = unsplash.random()
        print(image)
        self.assertTrue(image)


if __name__ == "__main__":
    unittest.main()
