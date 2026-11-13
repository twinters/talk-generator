"""Judge two variants' talks blind, setup by setup (see lab.py), and measure them.

    python scripts/prompt_lab/judge.py --a base --b v2 [--judges anthropic:claude-opus-5-5,openai:gpt-6.1-sol]

Each judge reads both talks of a setup, in an order that alternates, and says which is better on five questions, with
the tics it noticed; work/judge-<a>-<b>.md has the score (wins of b - wins of a - ties), the reasons, the tics, and the
metrics of both, and work/judge-<a>-<b>.json every answer.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab  # noqa: E402

QUESTIONS = ("glance", "springboard", "funny", "fresh", "overall")

SYSTEM = """\
You are an experienced host of PowerPoint karaoke and improvised TED talks: improvisers present slide decks they have \
never seen, and have to make every slide make sense, live, for an audience that came to laugh. You will read two \
decks made for the same setup (the same topic, format and presenter persona, the same kinds of slides in the same \
order); they differ only in their words and the pictures their search queries ask for. A picture is shown as its \
search query in brackets: imagine the stock photo, meme or gif it finds.

For each question, pick the deck that does better, or "tie" when you honestly can't separate them:
- glance: every slide reads at a glance: short titles, few words, no sentences to read out first; a presenter can \
start talking at once (fewer words wins, as long as the slide still says something).
- springboard: every slide hands the presenter something to run with: an odd juxtaposition, a surprising picture to \
explain, a suspiciously specific claim, a pattern to break; not a finished joke, nor an explanation of one.
- funny: an audience would laugh more: surprise, a pattern set up and broken, the punchline last, specific and absurd \
rather than random.
- fresh: no machine tics: made-up names that aren't real names or puns that are too on the nose ("Pen Guin"), the same \
made-up person turning up on slide after slide, "X: The Y of Z" titles, corporate buzzwords everywhere, explaining the \
joke, every slide the same kind of joke.
- overall: the deck you would rather hand an improviser tonight.

List the tics you notice in each deck, in a few words each. Answer with JSON only:
{"glance": "1"|"2"|"tie", "springboard": "1"|"2"|"tie", "funny": "1"|"2"|"tie", "fresh": "1"|"2"|"tie", \
"overall": "1"|"2"|"tie", "tics1": "...", "tics2": "...", "reason": "one or two sentences"}"""

_COST = {"input": 0.0, "output": 0.0}
_PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "gpt-6.1-sol": (2.0, 10.0)}


def chat(judge: str, user: str) -> str:
    provider, model = judge.split(":", 1)
    if provider == "anthropic":
        import anthropic

        from talkgenerator import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
        reply = client.messages.create(
            model=model,
            max_tokens=6000,
            system=SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium"},
        )
        _count(model, reply.usage.input_tokens, reply.usage.output_tokens)
        return "".join(block.text for block in reply.content if block.type == "text")
    if provider == "openai":
        import openai

        from talkgenerator import settings

        client = openai.OpenAI(api_key=settings.openai_api_key())
        reply = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            reasoning_effort="medium",
        )
        _count(model, reply.usage.prompt_tokens, reply.usage.completion_tokens)
        return reply.choices[0].message.content or ""
    raise ValueError(f"No judge {judge!r}")


def _count(model: str, prompt: int, completion: int) -> None:
    price_in, price_out = _PRICES.get(model, (5.0, 25.0))
    _COST["input"] += prompt * price_in / 1e6
    _COST["output"] += completion * price_out / 1e6


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--judges", default="anthropic:claude-opus-5-5")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    judges = args.judges.split(",")
    pairs = []
    for setup in lab.ALL_SETUPS:
        a, b = lab.load(args.a, setup["id"]), lab.load(args.b, setup["id"])
        if a is not None and b is not None:
            pairs.append((setup, a, b))
    jobs = [
        (setup, a, b, judge, (index + number) % 2 == 1)
        for index, (setup, a, b) in enumerate(pairs)
        for number, judge in enumerate(judges)
    ]

    def judge_one(job):
        setup, a, b, judge, flip = job
        first, second = (b, a) if flip else (a, b)
        user = (
            f"Setup: a talk on {setup['topic']!r}, format {setup['schema']}, presenter persona {setup['persona']}"
            f" ({setup.get('language', 'en')}).\n\nDECK 1\n{lab.as_text(first)}\n\nDECK 2\n{lab.as_text(second)}"
        )
        try:
            text = chat(judge, user)
            answer = json.loads(text[text.index("{") : text.rindex("}") + 1])
        except Exception as error:  # (a judge that fails leaves its answer out)
            return {"setup": setup["id"], "judge": judge, "error": str(error)[:300]}

        def who(value: str) -> str:
            return "tie" if value == "tie" else (args.a if (value == "1") != flip else args.b)

        result = {
            "setup": setup["id"],
            "judge": judge,
            **{question: who(answer.get(question, "tie")) for question in QUESTIONS},
        }
        result.update(
            tics_a=answer.get("tics2" if flip else "tics1", ""),
            tics_b=answer.get("tics1" if flip else "tics2", ""),
            reason=answer.get("reason", ""),
        )
        return result

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(judge_one, jobs))
    name = f"judge-{args.a}-{args.b}"
    (lab.WORK / f"{name}.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = [result for result in results if "error" not in result]

    def score(question: str, rows) -> str:
        return (
            f"{sum(row[question] == args.b for row in rows)}-{sum(row[question] == args.a for row in rows)}"
            f"-{sum(row[question] == 'tie' for row in rows)}"
        )

    lines = [f"# {args.b} against {args.a} (wins {args.b} - wins {args.a} - ties)", ""]
    lines.append("| judge | n | " + " | ".join(QUESTIONS) + " |")
    lines.append("| --- | --- |" + " --- |" * len(QUESTIONS))
    for judge in ["all", *judges]:
        rows = [row for row in ok if judge in ("all", row["judge"])]
        lines.append(f"| {judge} | {len(rows)} | " + " | ".join(score(question, rows) for question in QUESTIONS) + " |")
    lines += ["", "## Metrics (mean over setups)", ""]
    for tag in (args.a, args.b):
        measured = [lab.metrics(deck) for setup in lab.ALL_SETUPS if (deck := lab.load(tag, setup["id"])) is not None]
        if measured:
            keys = measured[0].keys()
            lines.append(
                f"- {tag}: "
                + ", ".join(f"{key} {sum(float(row[key]) for row in measured) / len(measured):.2f}" for key in keys)
            )
    lines += ["", "## Reasons and tics", ""]
    for row in ok:
        lines.append(f"- **{row['setup']}** ({row['judge'].split(':')[1]}): overall {row['overall']}. {row['reason']}")
        lines.append(f"  - {args.a}: {row['tics_a']}")
        lines.append(f"  - {args.b}: {row['tics_b']}")
    for row in results:
        if "error" in row:
            lines.append(f"- error, {row['setup']} ({row['judge']}): {row['error']}")
    cost = _COST["input"] + _COST["output"]
    lines += ["", f"Judging cost about ${cost:.2f}."]
    (lab.WORK / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[: 4 + len(judges) + 1 + 4]))
    print(f"Judging cost about ${cost:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
