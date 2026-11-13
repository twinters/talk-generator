# Prompt lab

Tune talkgenerator's prompts on real talks (docs/v5-plan.md, D80). A talk is made by talkgenerator's own code (its
prompts, the Advanced level's outline and batches, its realizing of the answers), with a stand-in picture for every
image slot instead of a search: a Claude Opus 5.5 talk takes about half a minute and $0.11.

A variant is the code as it is when its talks are made. Make talks with a tag, change a prompt, make them again with
another tag, and judge the two:

```bash
python scripts/prompt_lab/run.py --tag base --model opus
python scripts/prompt_lab/run.py --tag shorter --model opus
python scripts/prompt_lab/judge.py --a base --b shorter --judges anthropic:claude-opus-5-5,openai:gpt-6.1-sol
```

- `lab.py` has the 13 setups (topic, format, persona, seed, language): two variants' talks of a setup have the same
  kinds of slides in the same order. `--only id,id` makes some of them; `--model` takes `opus`, `sonnet`, `haiku` or
  `provider:model`, `--level` `advanced` (the default for a paid model) or `basic`.
- `judge.py` asks each judge to compare a setup's two talks blind (the order alternates) on five questions: reads at a
  glance, gives the presenter something to run with, funny, free of machine tics, overall; and to name the tics it
  sees. `work/judge-<a>-<b>.md` has the score, the metrics of both (words on a slide, title lengths, recurring names,
  real first names), every reason and tic, and what the judging cost.
- An older commit's talks: check it out in a worktree and run `run.py` with that worktree first on `PYTHONPATH` and
  `python -P`, from this checkout (whose `.env` has the keys).

Outputs go to `scripts/prompt_lab/work/`, which git ignores. The keys come from the repository's `.env`
(`ANTHROPIC_API_KEY`, and `OPENAI_API_KEY` for an OpenAI judge).
