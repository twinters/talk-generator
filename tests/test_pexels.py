import unittest

from talkgenerator.sources import pexels

import pytest

from tests.support import requires_keys

pytestmark = [pytest.mark.network, requires_keys("PEXELS_KEY")]


class PexelsTest(unittest.TestCase):
    def test_pexels_access(self):
        images = pexels.search_photos("office")
        self.assertTrue(len(images) > 0)
        sources = [
            image.get_source() for image in images if image.get_source() is not None
        ]
        self.assertTrue(len(sources) > 0)


if __name__ == "__main__":
    unittest.main()
