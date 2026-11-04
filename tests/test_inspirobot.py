import unittest

import pytest

from talkgenerator.sources.inspirobot import get_random_inspirobot_image

pytestmark = pytest.mark.network


class InspirobotTest(unittest.TestCase):
    def test_something(self):
        image = get_random_inspirobot_image()
        self.assertIsNotNone(image)
        print(image)


if __name__ == "__main__":
    unittest.main()
