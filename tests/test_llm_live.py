"""Live talks written by a language model's free tier: they need a key, and cost nothing."""

import pytest

from talkgenerator import generator, llm
from talkgenerator.checks.deck import check_deck
from tests.support import requires_keys

pytestmark = [pytest.mark.network]

SLIDES = 6


@requires_keys("OPENROUTER_API_KEY")
def test_openrouters_free_models_write_a_talk():
    _, slide_deck, _ = generator._generate_presentation(
        schema="default",
        slides=SLIDES,
        topic="volcanoes",
        int_seed=1,
        save_ppt=False,
        llm="openrouter",
        budget=llm.Budget(max_cost_usd=0),
    )
    deck = slide_deck.to_deck()
    assert (deck.usage.requests, deck.usage.cost_usd) == (1, 0)
    assert len(deck.slides) == SLIDES
    assert [finding for finding in check_deck(deck, SLIDES) if finding.severity == "error"] == []
    if not deck.usage.failed_requests:  # free models are rate limited at busy times: the talk is classic then
        assert any("Planned:" in slide.notes for slide in deck.slides)
