"""Automated quality checks (docs/v5-plan.md, section 14): `talkgenerator.checks.deck` checks a deck, and
`talkgenerator.checks.benchmark` (`talkgenerator check`) checks talks on a set of topics."""

from talkgenerator.checks.deck import Finding, check_deck, deck_metrics

__all__ = ["Finding", "check_deck", "deck_metrics"]
