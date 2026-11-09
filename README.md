# Talk Powerpoint Generator

[![CI](https://github.com/twinters/talk-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/twinters/talk-generator/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/twinters/talk-generator.svg)](https://github.com/twinters/talk-generator/blob/master/LICENSE)

This program automatically generates PowerPoints about any topic.
These presentation slide decks can be used by improvisers for the improvisational comedy format *"Improvised TED talk"* or *"Powerpoint Karaoke"*.
In such games, the actors have to present an unseen presentation slide deck, but pretend to be an expert and explain *"their"* slide show choices.

## Demo

Try out this generator on our online platform: [talkgenerator.com](https://talkgenerator.com/).

### Example

![Automatically Generated](https://media.giphy.com/media/MXXe522nIAA9JZjExI/giphy.gif)

## Install

You need Python 3.11 or newer. Install the generator from [PyPI](https://pypi.org/project/talkgenerator/), ideally in a virtual environment:

```sh
pip install talkgenerator
```

That's all classic talks need. Extras add the language models that write talks, and the MCP server:

| Extra | For |
| --- | --- |
| `talkgenerator[openai]` | [OpenRouter](https://openrouter.ai/)'s free models, OpenAI's models and the models of your ChatGPT plan |
| `talkgenerator[anthropic]` | Claude |
| `talkgenerator[llm]` | both of the above |
| `talkgenerator[mcp]` | `talkgenerator mcp`, for Claude Desktop and other MCP clients |

```sh
pip install 'talkgenerator[llm,mcp]'
```

<!-- Remove this paragraph once 5.0.0 is on PyPI. -->
Until talkgenerator 5.0.0 is on PyPI, `pip install talkgenerator` gets talkgenerator 4. To try 5 before then, install it from GitHub's `v5` branch: `pip install "talkgenerator[llm] @ git+https://github.com/twinters/talk-generator@v5"`.

On its first run, the generator downloads the NLTK data it needs (about 30 MB).
Coming from talkgenerator 4? See [Migrating from 4.x](https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md).

To work on the generator itself, clone this repository and use [uv](https://docs.astral.sh/uv/):

```sh
uv sync                                                   # install the dependencies into .venv
uv run talkgenerator --topic "peanuts" --num_slides 10
```

## Make a talk

```sh
# A 10-slide talk about peanuts, saved in ./output and opened afterwards
talkgenerator --topic "peanuts" --num_slides 10
```

A few more:

```sh
talkgenerator login openrouter                               # from now on, OpenRouter's free models write your talks
talkgenerator --topic_or_title "Why I Joined a Penguin Cult"   # a topic or a title: talkgenerator tells which
talkgenerator --topic penguins --language nl                 # in Dutch (with a language model)
talkgenerator --topic penguins --theme "1997 WordArt"        # a look; by default, the talk's seed picks one
talkgenerator --topic penguins --theme_families "neon,blueprint"   # a look the seed picks, of these families only
talkgenerator --topic penguins --schema ted                  # copyright-free images only, for decks shown in public
talkgenerator --topic penguins --schema pitch                # a startup pitch: the problem, the market, the ask...
talkgenerator --topic penguins --schema academic             # a conference talk: the method, p-values, Reviewer 2
talkgenerator --topic penguins --schema corporate            # an all-hands: KPIs against target, the new org chart
talkgenerator --topic penguins --schema keynote              # a product keynote: the reveal, the demo, one more thing
talkgenerator --topic penguins --persona kindergarten_teacher # who presents it: by default, the seed picks
talkgenerator --topic penguins --schema random               # a format the persona favours: a founder pitches more
talkgenerator --topic penguins --llm none --theme classic --name_styles classic --persona none   # closest to 2019
```

[The command line](https://github.com/twinters/talk-generator/blob/master/docs/command-line.md) lists every option, and the commands for plans, checks, sign-ins and the MCP server.

## How it works

talkgenerator picks a talk's slides with the talk's seed: a title slide, then slides about the presenter, history, bold statements, quotes, captioned images, gifs and memes, charts, diagrams, quizzes and more, each kind in its place and at most a few times, and conclusions at the end.
The seed also picks who presents it, a persona such as a startup founder or a medieval historian, whose favourite kinds of slides come up more often (a founder's KPI tiles, a historian's timelines), and who colours the title, the presenter's name, the theme and the pictures.
The same seed gives the same talk.
Besides TED-like talks, there are startup pitches (`--schema pitch`), academic conference talks (`--schema academic`), all-hands meetings (`--schema corporate`) and product keynotes (`--schema keynote`), whose slides go through their arcs: from the problem to the market, the traction and the ask; from the outline to the method, the results with their p-values and the questions; from the agenda to the KPIs against their targets, the new org chart and Q&A; or from a big opening statement to the reveal, a demo that crashes and one more thing.

- **A language model** can write what goes on those slides: the whole talk in one request, with a thesis, callbacks to earlier slides, and a made-up name and job for the presenter. OpenRouter's free models do so whenever there's an OpenRouter key, at no cost, and so do your ChatGPT plan's once you've signed in with ChatGPT; a paid model only when you ask for it ([Language models](https://github.com/twinters/talk-generator/blob/master/docs/language-models.md)).
- **The classic generator** writes them otherwise, and every slide the model gets wrong: templates and grammars, words related to the topic, quotes, how-tos and pictures from many sources. It's the method of the [EvoMUSART 2019 paper](#credits), with more kinds of slides since: `--llm none --theme classic --name_styles classic --persona none` (the classic generator, the 2019 template, random names and no persona) comes closest to a talk of 2019.
- **Claude** can write the talk too, as a plan that talkgenerator renders, through the Skill or the MCP server ([Use it with Claude](https://github.com/twinters/talk-generator/blob/master/docs/use-with-claude.md)).

Images come from Unsplash, Pexels, Pixabay, Openverse, Wikimedia Commons, the Art Institute of Chicago, Reddit, GIPHY, InspiroBot and ShitpostBot, in a look that fits the slide (stock photos, old photographs, museum art, weird pictures...), each credited on its slide, with its license when it's openly licensed or public domain.
Talks come in themes, from `clean keynote` and `hacker terminal` to `chalkboard` and `1997 WordArt` ([Images and themes](https://github.com/twinters/talk-generator/blob/master/docs/images-and-themes.md)).

Every talk becomes a deck: plain, versioned JSON data with every text, image, credit and layout of its slides.
The PowerPoint is drawn from it, talkgenerator.com shows it in the browser, and a saved deck renders again as the same slides ([Python](https://github.com/twinters/talk-generator/blob/master/docs/python.md#decks)).

## API keys

Every key is optional: without any, talkgenerator makes classic talks with the image sources that need no key.
Copy [`.env.example`](https://github.com/twinters/talk-generator/blob/master/.env.example) to `.env` in the folder you run the generator from, and fill in the keys you have: image sources (Reddit, Unsplash, Pixabay, Pexels, GIPHY, Openverse), and language models (`OPENROUTER_API_KEY` for the free models, which `talkgenerator login openrouter` gets for you too, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
[Keys and settings](https://github.com/twinters/talk-generator/blob/master/docs/configuration.md) says where to get each key, and lists every setting.

| Route | A 10-slide talk costs |
| --- | --- |
| Classic, or OpenRouter's free models (50 talks a day, or 1,000 once the account has bought $10 of credits) | $0 |
| Your ChatGPT plan (`talkgenerator login chatgpt`), or Claude through the Skill | part of your plan's usage |
| Claude Haiku 5.5, Sonnet 5.5 or Opus 5.5, with your own key | about $0.0015, $0.03 or $0.06 |

## Use it with Claude

Claude can write the talk itself, on your own Claude plan, and leave the rest to talkgenerator: finding images it may use, crediting them, laying out the deck and saving the PowerPoint.

- **The Skill**, for [Claude Code](https://claude.com/claude-code): `/plugin marketplace add twinters/talk-generator`, then `/plugin install talkgenerator@talk-generator`. Claude writes a plan, renders it with `talkgenerator render`, and fixes what didn't come out.
- **The MCP server**, for [Claude Desktop](https://claude.ai/download) and other MCP clients: `talkgenerator mcp` gives talkgenerator's commands as tools, on your computer, with your keys. Nothing of it is hosted.

[Use it with Claude](https://github.com/twinters/talk-generator/blob/master/docs/use-with-claude.md) says how to set up each.

## Using it from Python

```python
from talkgenerator import generator
from talkgenerator.models.events import TalkFinished
from talkgenerator.render.powerpoint import render_pptx

for event in generator.stream_talk("default", 8, topic="peanuts", theme="random"):
    print(event.event)  # talk.started, slide.ready (8 times), talk.finished
    if isinstance(event, TalkFinished):
        render_pptx(event.deck).save("peanuts.pptx")
```

`stream_talk` hands over the talk while it's made, a slide at a time, and ends with the whole deck. With `spares=3`,
it also sends three spare slides early on, quick ones about the topic, for a presenter who goes on before the next
slide is in; and with `slide_seconds=8`, a slide that isn't made within 8 seconds comes at once with what's quick.
[Python](https://github.com/twinters/talk-generator/blob/master/docs/python.md) covers the events, decks, plans and the catalogs for a settings menu.
`generator.generate_presentation()`, talkgenerator 4's way, keeps working throughout talkgenerator 5, with a deprecation warning.

## Documentation

- [The command line](https://github.com/twinters/talk-generator/blob/master/docs/command-line.md): every option, and the commands for plans, checks, sign-ins and the MCP server
- [Language models](https://github.com/twinters/talk-generator/blob/master/docs/language-models.md): which model writes a talk, the free models, keys, sign-ins and costs, and languages
- [Keys and settings](https://github.com/twinters/talk-generator/blob/master/docs/configuration.md): the image sources' keys, and every environment variable
- [Images and themes](https://github.com/twinters/talk-generator/blob/master/docs/images-and-themes.md): license classes and policies, image looks, and themes
- [Use it with Claude](https://github.com/twinters/talk-generator/blob/master/docs/use-with-claude.md): the Skill and the MCP server
- [Using it from Python](https://github.com/twinters/talk-generator/blob/master/docs/python.md): streamed talks, decks and plans
- [Migrating from 4.x](https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md)
- [The changelog](https://github.com/twinters/talk-generator/blob/master/CHANGELOG.md), and [the plan for version 5](https://github.com/twinters/talk-generator/blob/master/docs/v5-plan.md)

## Tests

Tests live in `tests/`. Many of them talk to the live APIs, and are marked as `network` tests:

```sh
uv run pytest                     # everything (tests needing missing API keys are skipped)
uv run pytest -m "not network"    # only the offline tests, as in CI
uv run pytest -m "not network and not slow"  # the quick set, while you work: a few minutes
uv run pytest -m "not network" --bundled-fonts-only  # measuring texts as CI does, without this computer's fonts
uv run ruff check . && uv run ruff format --check .
uv run mypy                       # type checking
```

The `slow` tests draw whole decks in every theme family, or sweep every template: about 200 of the offline tests, and
most of their time (over an hour on one core). Run them, or the files of what you change, before you merge.

Type checking is gradual: mypy checks the whole package, and the modules listed under `[[tool.mypy.overrides]]` in `pyproject.toml` must be fully annotated.
Add a module to that list once you've typed it.

On Windows on Arm, the dev dependencies leave out the MCP SDK, which doesn't install there, and the MCP server's tests are skipped.
To run them, use an x64 Python, in a virtual environment of its own outside the repository (so that `.venv` stays as it is): set `UV_PROJECT_ENVIRONMENT` to its folder, and run `uv run --extra mcp --python cpython-3.12-windows-x86_64-none pytest tests/test_mcp_server.py`.

To check the talks themselves, `uv run talkgenerator check` generates talks on a set of topics with the live sources (`--quick` for 3 topics, `--all` for 30), checks them, generates each again with its seed to see that it comes out the same, and writes a report to `output/check-report.json`.
It exits with an error when a talk is broken: a slide without what it needs, or template code such as `{seed}` on a slide.

GitHub Actions runs the linter, the type checker and the offline tests on every push and pull request, and checks the installed dependencies for known vulnerabilities with `pip-audit`.
A weekly "canary" workflow runs the network tests against the live APIs, and opens an issue when one of them broke.
It uses the API keys stored as repository secrets (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `UNSPLASH_ACCESS_KEY`, `PIXABAY_KEY`, `PEXELS_KEY`, `GIPHY_API_KEY`); tests whose keys are missing are skipped.

## Releasing

New versions are published to PyPI from GitHub; see [RELEASING.md](https://github.com/twinters/talk-generator/blob/master/RELEASING.md).

## Credits

This generator is made by
[Thomas Winters](https://github.com/TWinters)
and [Kory Mathewson](https://github.com/korymath),
with contributions from
[Shaun Farrugia](https://github.com/h0h0h0)
and [Julian Faid](https://github.com/jfaid).

If you would like to refer to this project in academic work, please cite the following paper.
Its method lives on as the classic generator, which makes every talk without a language model: `talkgenerator --llm none --theme classic --name_styles classic --persona none` comes closest to the paper's talks, in their look (with the kinds of slides added since).

Winters T., Mathewson K.W. (2019) **Automatically Generating Engaging Presentation Slide Decks**. In: Ekárt A., Liapis A., Castro Pena M. (eds) Computational Intelligence in Music, Sound, Art and Design. EvoMUSART 2019. Lecture Notes in Computer Science, vol 11453. Springer, Cham

```sh
@InProceedings{winters2019tedric,
    author="Winters, Thomas
    and Mathewson, Kory W.",
    editor="Ek{\'a}rt, Anik{\'o}
    and Liapis, Antonios
    and Castro Pena, Mar{\'i}a Luz",
    title="Automatically Generating Engaging Presentation Slide Decks",
    booktitle="Computational Intelligence in Music, Sound, Art and Design",
    year="2019",
    publisher="Springer International Publishing",
    address="Cham",
    pages="127--141",
    isbn="978-3-030-16667-0"
}
```

## License

MIT License. Copyright (c) 2018-2020 [Kory Mathewson](https://github.com/korymath) and [Thomas Winters](https://github.com/TWinters)
