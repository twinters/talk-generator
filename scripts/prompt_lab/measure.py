"""Measure a variant's talks without judging them (see lab.py): words on a slide, English in a talk in another
language, and the texts that were cut to their fields' lengths, mid-sentence ones above all.

    python scripts/prompt_lab/measure.py --tag nl-free [--set nl]

Prints a line a talk and the totals, and writes them to work/measure-<tag>.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--set", default="", help=f"one of {', '.join(lab.SETS)} (default: every setup)")
    args = parser.parse_args()
    setups = lab.SETS[args.set] if args.set else lab.ALL_SETUPS
    costs_path = lab.WORK / args.tag / "costs.json"
    costs = json.loads(costs_path.read_text(encoding="utf-8")) if costs_path.exists() else {}
    lines = [f"# Measured: {args.tag}", ""]
    where: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    talks = 0
    for setup in setups:
        deck = lab.load(args.tag, setup["id"])
        if deck is None:
            continue
        talks += 1
        measured = lab.metrics(deck)
        cut = lab.cuts(args.tag, setup["id"])
        where.update(each["where"] for each in cut)
        english = lab.english_words(deck)
        totals.update(
            {
                "english_slides": measured["english_slides"],
                "english_words": measured["english_words"],
                "language_findings": measured["language_findings"],
                "classic": int(measured["classic"]),
            }
        )
        cost = costs.get(setup["id"], {})
        who = ", ".join(sorted(set(cost.get("answered_by") or []))) or cost.get("model") or "?"
        lines.append(
            f"- **{setup['id']}** ({who}): {measured['words_mean']} words a slide, "
            f"{measured['english_slides']} English slides ({measured['english_words']} words), "
            f"{measured['language_findings']} language findings{', classic' if measured['classic'] else ''}; "
            f"{len(cut)} cuts"
        )
        for number, words in english.items():
            lines.append(f"  - slide {number} English: {' '.join(words[:12])}")
        for each in cut:
            if each["where"] != "clause":
                lines.append(f"  - cut ({each['where']}, {each['length']}): {each['text']!r} -> {each['cut']!r}")
    lines += [
        "",
        f"{talks} talks: {totals['english_slides']} English slides, {totals['english_words']} English words, "
        f"{totals['language_findings']} language findings, {totals['classic']} classic; "
        f"cuts {sum(where.values())} ({', '.join(f'{name} {count}' for name, count in where.most_common())})",
    ]
    text = "\n".join(lines) + "\n"
    (lab.WORK / f"measure-{args.tag}.md").write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
