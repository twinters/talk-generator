"""Make a variant's talks (see lab.py): every setup's, or some, with a model at a level, a few at a time.

    python scripts/prompt_lab/run.py --tag base --model opus [--level advanced] [--only id,id] [--jobs 4]

Each talk runs in a process of its own (talkgenerator keeps state per talk); its deck goes to work/<tag>/<id>.deck.json,
and what the variant's talks cost to work/<tag>/costs.json. Run it from the repository's root with its venv, or with
another checkout's code first on PYTHONPATH and python -P (a variant of an older commit).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--model", default="opus", help=f"one of {', '.join(lab.MODELS)}, or provider:model")
    parser.add_argument("--level", default="advanced")
    parser.add_argument("--only", default="")
    parser.add_argument("--set", default="main", help=f"one of {', '.join(lab.SETS)}")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--one", default="", help=argparse.SUPPRESS)  # (a child process: one setup)
    args = parser.parse_args()
    model = lab.MODELS.get(args.model, args.model)
    folder = lab.WORK / args.tag
    folder.mkdir(parents=True, exist_ok=True)
    setups = {setup["id"]: setup for setup in lab.ALL_SETUPS}
    if args.one:
        result = lab.make_talk(setups[args.one], model, args.level, folder)
        print("RESULT " + json.dumps(result))
        return 0
    wanted = [name for name in args.only.split(",") if name] or [setup["id"] for setup in lab.SETS[args.set]]

    def run(name: str) -> dict:
        started = time.monotonic()
        command = [sys.executable, *(["-P"] if sys.flags.safe_path else []), __file__, "--tag", args.tag]
        command += ["--model", model, "--level", args.level, "--one", name]
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (folder / f"{name}.log").write_text(done.stderr, encoding="utf-8")  # (why a talk came out classic, say)
        line = next((line for line in done.stdout.splitlines() if line.startswith("RESULT ")), None)
        result = json.loads(line[7:]) if line else {"id": name, "error": done.stderr[-2000:]}
        result["seconds"] = round(time.monotonic() - started)
        print(name, result.get("cost"), result.get("level"), result.get("seconds"), "s", result.get("error", "")[-300:])
        return result

    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(run, wanted))
    costs = folder / "costs.json"
    earlier = json.loads(costs.read_text(encoding="utf-8")) if costs.exists() else {}
    earlier.update({result["id"]: result for result in results})
    costs.write_text(json.dumps(earlier, indent=1), encoding="utf-8")
    total = sum(result.get("cost") or 0 for result in results)
    print(f"{len(results)} talks, ${total:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
