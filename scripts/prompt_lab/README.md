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
  kinds of slides in the same order. `--only id,id` makes some of them, and `--set nl` ten Dutch ones, of every
  format, instead; `--model` takes `opus`, `sonnet`, `haiku`, `free` (OpenRouter's free router: talkgenerator.com's
  Basic AI, which costs nothing) or `provider:model`, `--level` `advanced` (the default for a paid model) or `basic`
  (the site's, for the free models).
- Each talk also leaves `work/<tag>/<id>.cuts.json`, every text cut to its field's length (the text, the cut, and
  whether it ends at a clause, a comma or mid-sentence, between words), and `<id>.log`, its warnings (why it came out
  classic, say); `costs.json` names the models that answered.
- `measure.py --tag <tag> [--set nl]` measures a variant without judging it: words on a slide, English words in a
  talk in another language, talks that came out classic (in English), and the cuts, mid-sentence ones listed.
- `judge.py` asks each judge to compare a setup's two talks blind (the order alternates) on five questions: reads at a
  glance, gives the presenter something to run with, funny, free of machine tics, overall; and to name the tics it
  sees. `work/judge-<a>-<b>.md` has the score, the metrics of both (words on a slide, title lengths, recurring names,
  real first names), every reason and tic, and what the judging cost.
- An older commit's talks: check it out in a worktree and run `run.py` with that worktree first on `PYTHONPATH` and
  `python -P`, from this checkout (whose `.env` has the keys).

Outputs go to `scripts/prompt_lab/work/`, which git ignores. The keys come from the repository's `.env`
(`ANTHROPIC_API_KEY`, and `OPENAI_API_KEY` for an OpenAI judge).
