# coding=utf-8
"""Live tests of related-concept lookups (ConceptNet, or its Datamuse fallback while ConceptNet is down)."""

import unittest

import pytest

from talkgenerator.sources import conceptnet

pytestmark = pytest.mark.network


class ConceptNetTest(unittest.TestCase):
    def test_conceptnet_standard(self):
        related_words = conceptnet.get_weighted_related_words("cat", 10)
        self.assertTrue(len(related_words) <= 10)
        self.assertTrue(0 < len(related_words))

    def test_conceptnet_only_english(self):
        related_words = conceptnet.get_weighted_related_words("crane", 50)
        self.assertFalse("" in related_words)
        self.assertFalse("erav" in related_words)
        self.assertFalse("ždral" in related_words)
        self.assertFalse("dral" in related_words)

    def test_conceptnet_multiword(self):
        related_words = conceptnet.get_weighted_related_words("my lap", 10)
        self.assertTrue(len(related_words) > 0)

    def test_locations_always_has_answers(self):
        locations = conceptnet.get_weighted_related_locations("cat")
        self.assertTrue(len(locations) >= 2)

    def test_properties(self):
        properties = [word for _, word in conceptnet.get_weighted_properties("peanuts")]
        self.assertTrue(len(properties) > 0)


if __name__ == "__main__":
    unittest.main()
