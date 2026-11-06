"""`talkgenerator check`: generate talks on a set of topics, check them, and write a report (docs/v5-plan.md, 14).

Every talk is generated in parallel (the CLI's default), checked (talkgenerator.checks.deck), and generated again one
by one with the same seed, which has to give the same deck. The JSON report holds every finding, how long each talk
took and what it asked of language models, to compare with the report of an earlier run.

Talks are classic unless a language model is given (--llm). A model doesn't give the same answer twice, so the
second run replays the answers the first run got: the same answers have to give the same talk.

With live sources, a talk can also come out differently because a source answered differently between the two runs;
the on-disk cache of API responses makes that rare.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

from talkgenerator import __version__, generator
from talkgenerator.checks.deck import Finding, check_deck, deck_metrics
from talkgenerator.llm.base import TextProvider
from talkgenerator.llm.providers import provider_from_spec
from talkgenerator.llm.replay import ReplayProvider
from talkgenerator.models.deck import Deck
from talkgenerator.util import os_util

logger = logging.getLogger("talkgenerator")

# Common nouns, things people do, places, phrases, rare words and names: the kinds of topics audiences shout
DEFAULT_TOPICS: Final = (
    "cat",
    "peanuts",
    "time travel",
    "spreadsheets",
    "Belgium",
    "volcanoes",
    "socks",
    "procrastination",
    "jazz",
    "petrichor",
)
MORE_TOPICS: Final = (
    "bread",
    "the moon",
    "artificial intelligence",
    "pirates",
    "quantum physics",
    "coffee",
    "dinosaurs",
    "taxes",
    "bicycles",
    "mushrooms",
    "penguins",
    "Shakespeare",
    "glaciers",
    "elevators",
    "origami",
    "sourdough",
    "submarines",
    "geese",
    "remote work",
    "umbrellas",
)


@dataclass
class TalkReport:
    topic: str
    seed: int
    seconds: float
    findings: list[Finding] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    deterministic: bool | None = None  # None when that wasn't checked

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.severity == "warning"]


def generate_deck(
    topic: str, seed: int, schema: str, slides: int, parallel: bool, llm: TextProvider | str = "none"
) -> Deck:
    _, slide_deck, _ = generator.generate_presentation(
        schema=schema, slides=slides, topic=topic, int_seed=seed, parallel=parallel, save_ppt=False, llm=llm
    )
    return slide_deck.to_deck(schema_name=schema)


def check_talk(
    topic: str,
    seed: int,
    schema: str = "default",
    slides: int = 10,
    determinism: bool = True,
    llm: str = "none",
) -> TalkReport:
    """Generate a talk and check it; with determinism, generate it again one by one, which has to give the same.

    With a language model (a spec, see talkgenerator.llm.providers), its answers are recorded, and the second run
    replays them."""
    with tempfile.TemporaryDirectory(prefix="talkgenerator-check-") as folder:
        cassette = Path(folder) / "answers.json"
        recording: TextProvider | str = llm
        if llm != "none":
            recording = ReplayProvider(cassette, record=provider_from_spec(llm))
        start = time.monotonic()
        try:
            deck = generate_deck(topic, seed, schema, slides, parallel=True, llm=recording)
        except Exception as error:  # a talk should never fail: if it does, that's what the check found
            logger.exception("Generating a talk about %r crashed", topic)
            crash = Finding("generation", "error", f"generating the talk crashed: {error!r}")
            return TalkReport(topic, seed, time.monotonic() - start, [crash])
        report = TalkReport(topic, seed, time.monotonic() - start, check_deck(deck, slides), deck_metrics(deck))
        if determinism:
            replaying: TextProvider | str = ReplayProvider(cassette) if llm != "none" else "none"
            again = generate_deck(topic, seed, schema, slides, parallel=False, llm=replaying)
            # What the talks asked of language models differs (the second one replayed); their slides may not
            report.deterministic = again.model_copy(update={"usage": deck.usage}).to_json() == deck.to_json()
            if not report.deterministic:
                report.findings.append(Finding("determinism", "error", _differences(deck, again)))
    return report


def run(
    topics: Sequence[str],
    seeds: Sequence[int],
    schema: str = "default",
    slides: int = 10,
    determinism: bool = True,
    on_talk: Callable[[TalkReport], None] | None = None,
    llm: str = "none",
) -> dict[str, Any]:
    """Check a talk for every topic and seed, and return the report."""
    talks = []
    for topic in topics:
        for seed in seeds:
            talk = check_talk(topic, seed, schema, slides, determinism, llm)
            talks.append(talk)
            if on_talk is not None:
                on_talk(talk)
    return _report(talks, schema, slides, seeds, llm)


def _report(talks: list[TalkReport], schema: str, slides: int, seeds: Sequence[int], llm: str) -> dict[str, Any]:
    seconds = [talk.seconds for talk in talks]
    checked = [talk for talk in talks if talk.deterministic is not None]
    return {
        "generator": f"talkgenerator {__version__}",
        "llm": llm,
        "schema": schema,
        "slides": slides,
        "seeds": list(seeds),
        "summary": {
            "talks": len(talks),
            "errors": sum(len(talk.errors) for talk in talks),
            "warnings": sum(len(talk.warnings) for talk in talks),
            "deterministic": f"{sum(1 for talk in checked if talk.deterministic)} of {len(checked)}",
            "seconds_median": round(statistics.median(seconds), 1) if seconds else None,
            "seconds_max": round(max(seconds), 1) if seconds else None,
            "language_model_requests": sum(talk.metrics.get("usage", {}).get("requests", 0) for talk in talks),
            "written_by_language_model": f"{_sum_of(talks, 'written_by_language_model')} of "
            f"{_sum_of(talks, 'slides')} slides",
            "cost_usd": round(sum(talk.metrics.get("usage", {}).get("cost_usd", 0.0) for talk in talks), 6),
        },
        "talks": [
            {
                "topic": talk.topic,
                "seed": talk.seed,
                "seconds": round(talk.seconds, 1),
                "deterministic": talk.deterministic,
                "metrics": talk.metrics,
                "findings": [asdict(finding) for finding in talk.findings],
            }
            for talk in talks
        ],
    }


def _sum_of(talks: list[TalkReport], metric: str) -> int:
    return sum(talk.metrics.get(metric, 0) for talk in talks)


def _differences(deck: Deck, again: Deck) -> str:
    if len(deck.slides) != len(again.slides):
        return f"generated again one by one, the talk had {len(again.slides)} slides instead of {len(deck.slides)}"
    different = []
    for number, (slide, slide_again) in enumerate(zip(deck.slides, again.slides, strict=True), 1):
        if slide != slide_again:
            fields = [name for name in type(slide).model_fields if getattr(slide, name) != getattr(slide_again, name)]
            different.append(f"slide {number} ({', '.join(fields)})")
    if different:
        return "generated again one by one, other slides came out: " + "; ".join(different)
    return "generated again one by one, the deck came out different (not its slides)"


def _count(number: int, thing: str) -> str:
    return f"{number} {thing}{'' if number == 1 else 's'}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="talkgenerator check",
        description="Generate talks on a set of topics, check them, and write a report.",
    )
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--topics", help="comma-separated topics (default: a set of 10)")
    which.add_argument("--quick", action="store_true", help="only the first 3 topics of the default set")
    which.add_argument("--all", action="store_true", help=f"all {len(DEFAULT_TOPICS) + len(MORE_TOPICS)} topics")
    parser.add_argument("--seeds", default="1", help="comma-separated seeds (default: 1)")
    parser.add_argument("--schema", default="default", help="the presentation schema (default: default)")
    parser.add_argument("--slides", type=int, default=10, help="slides per talk (default: 10)")
    parser.add_argument(
        "--llm",
        default="none",
        help="the language model that writes the talks, as provider:model (default: none, for classic talks)",
    )
    parser.add_argument(
        "--no_determinism",
        dest="determinism",
        action="store_false",
        help="don't generate every talk again one by one to compare",
    )
    parser.add_argument("--report", default=str(Path("output") / "check-report.json"), help="where to write it")
    parser.add_argument("--verbose", "-v", action="store_true", help="show the generator's logs")
    args = parser.parse_args(argv)

    if args.topics:
        topics: Sequence[str] = [topic.strip() for topic in args.topics.split(",") if topic.strip()]
    else:
        topics = DEFAULT_TOPICS[:3] if args.quick else DEFAULT_TOPICS + MORE_TOPICS if args.all else DEFAULT_TOPICS
    try:
        seeds = [int(seed) for seed in args.seeds.split(",")]
        generator.get_schema(args.schema)
        provider_from_spec(args.llm)
    except (ValueError, KeyError) as error:
        parser.error(str(error))
    if args.verbose:
        os_util.show_logs(logger)

    def print_talk(talk: TalkReport) -> None:
        print(
            f"{talk.topic!r}, seed {talk.seed}: {_count(len(talk.errors), 'error')},"
            f" {_count(len(talk.warnings), 'warning')}, {talk.seconds:.0f} seconds"
        )
        for finding in talk.findings:
            print(f"    {finding}")

    report = run(topics, seeds, args.schema, args.slides, args.determinism, on_talk=print_talk, llm=args.llm)
    summary = report["summary"]
    print(
        f"\n{_count(summary['talks'], 'talk')}: {_count(summary['errors'], 'error')},"
        f" {_count(summary['warnings'], 'warning')}; deterministic: {summary['deterministic']};"
        f" median {summary['seconds_median']} seconds a talk"
    )
    if args.llm != "none":
        print(
            f"Written by the language model: {summary['written_by_language_model']}, in"
            f" {_count(summary['language_model_requests'], 'request')}, for ${summary['cost_usd']}"
        )
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Report: {path}")
    return 1 if summary["errors"] else 0
