import unittest
from talkgenerator.sources import pixabay

import pytest

from tests.support import requires_keys

pytestmark = [pytest.mark.network, requires_keys("PIXABAY_KEY")]


class PixabayTest(unittest.TestCase):
    def test_pixabay_access(self):
        images = pixabay.search_photos("office chair")
        self.assertTrue(len(images) > 0)
        sources = [
            image.get_source() for image in images if image.get_source() is not None
        ]
        self.assertTrue(len(sources) > 0)


if __name__ == "__main__":
    unittest.main()
