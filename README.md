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

## Install and run

You need Python 3.11 or newer. Install the generator from [PyPI](https://pypi.org/project/talkgenerator/), ideally in a virtual environment:

```sh
pip install talkgenerator

# Generate a 10 slide talk about peanuts (saved in ./output and opened afterwards)
talkgenerator --topic "peanuts" --num_slides 10
```

To work on the generator itself, clone this repository and use [uv](https://docs.astral.sh/uv/):

```sh
uv sync                                                   # install the dependencies into .venv
uv run talkgenerator --topic "peanuts" --num_slides 10
```

To have Claude write the talks, with talkgenerator making the decks, see [Use it with Claude](#use-it-with-claude): as a Claude Skill, or as an MCP server for Claude Desktop.

On its first run, the generator downloads the NLTK data it needs (about 30 MB).
For deployments, you can prepare it up front with `python run_nltk_download.py --data-dir <folder>` (from a clone of this repository) and point `NLTK_DATA` to that folder.

### API keys

Images come from several services, some of which need a (free) API key.
Copy [`.env.example`](https://github.com/twinters/talk-generator/blob/master/.env.example) to `.env` in the folder you run the generator from, and fill in the keys you have.
Every key is optional: sources without a key are skipped, and the other sources fill in.

| Source | Used for | Keys | Where to get them |
| --- | --- | --- | --- |
| Reddit | memes, gifs, weird and vintage pictures, charts | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | [create a "script" app](https://www.reddit.com/prefs/apps) |
| Unsplash | photos | `UNSPLASH_ACCESS_KEY` | [Unsplash developers](https://unsplash.com/oauth/applications) (new apps are limited to 50 requests per hour until approved) |
| Pixabay | photos | `PIXABAY_KEY` | [Pixabay API](https://pixabay.com/api/docs/) |
| Pexels | photos | `PEXELS_KEY` | [Pexels API](https://www.pexels.com/api/) |
| GIPHY | gifs, next to Reddit's | `GIPHY_API_KEY` | [GIPHY developers](https://developers.giphy.com/dashboard/) |
| [Openverse](https://openverse.org/) | openly licensed photos | `OPENVERSE_CLIENT_ID`, `OPENVERSE_CLIENT_SECRET` (optional: without them, Openverse is searched anonymously, at lower rate limits) | [register an app](https://api.openverse.org/v1/#tag/auth/operation/register), then verify its email address |

These sources need no key: [Datamuse](https://www.datamuse.com/api/) and WordNet (related words), Goodreads and [Wikiquote](https://en.wikiquote.org/) (quotes), WikiHow (actions), [Wikimedia Commons](https://commons.wikimedia.org/) (old photos), the [Art Institute of Chicago](https://api.artic.edu/docs/) (public domain artworks), InspiroBot and ShitpostBot 5000 (images).
Most kinds of content come from more than one source, so a source that is down or rate limited leaves no holes: the others fill in.
A slide that still can't get all its images (say, a gif slide without Reddit or GIPHY) is replaced by another kind of slide, and the generator logs which sources it skips for lack of keys.
Image credits on the slides link to the photographer's or the image's page, and name the license of openly licensed and public domain images (such as "CC BY 2.0", linking to it).

Related words used to come from [ConceptNet](https://conceptnet.io/), whose public API has been down since late 2025.
The generator still tries it (or a self-hosted copy set with `CONCEPTNET_API_URL`), and falls back to Datamuse and WordNet when it doesn't answer.

Any source can be switched off with `DISABLE_<SOURCE>=1`, e.g. `DISABLE_WIKIHOW=1` (see `.env.example`).

Search API responses (Datamuse, ConceptNet, Pixabay, Pexels, Unsplash) are cached on disk for one to thirty days, in your user cache folder.
That keeps you within rate limits and is what Pixabay's API terms ask for.
GIPHY's searches aren't cached, as its API rules forbid it.
API keys are never stored in the cache.
Set `TALKGENERATOR_CACHE_DIR` to put the cache elsewhere, or `DISABLE_CACHE=1` to turn it off.

### Images: licenses and looks

Every image has a license class: `public-domain` (public domain and CC0), `open` (Creative Commons BY and BY-SA), `stock` (the Unsplash, Pexels and Pixabay licenses), `generated` (AI images, under their provider's terms) or `fair-use` (Reddit's posts, GIPHY's gifs, InspiroBot's posters and ShitpostBot's images).
A talk's license policy picks the classes its images may have: `--license_policy open` allows everything but fair use, for decks shown in public, and `all` (the default) every class; license classes separated by commas work too, such as `public-domain,open`.
The `ted` format keeps to `open` by default.
The search keeps to the policy (slides whose images it allows no source for, such as memes, aren't picked), the deck says each image's class and license, and `talkgenerator check` reports an image the policy doesn't allow as an error.
`talkgenerator formats --licenses` lists the policies.

Every image a slide asks for has a look (an aesthetic profile), with the sources that have it and the filters that get it: `photo` (stock photos), `calm-backdrop` (photos with little detail where a slide's big text goes), `vintage` (old photographs in black and white or sepia), `museum` (public domain art), `space-science` (NASA's photos and the like), `corporate-stock`, `illustration`, `meme-chaos` (Reddit's weird pictures, ShitpostBot's images, gifs and memes), and flavour packs of weird content, curated sets of subreddits such as `cursed`, `wholesome`, `bad-charts`, `medieval` and `liminal`.
The image finder searches a look's sources in parallel, filters what they find (license, size, orientation), takes a look at the thumbnails of a few (their colours, how gray they are, how much detail they have where the text goes, and a perceptual hash that keeps nearly the same picture from coming back on another slide), and picks with the talk's seed: the same seed finds the same images, in parallel or not.
In a themed talk, pictures that go with the theme's colours come first, and a vintage picture that isn't black and white or sepia turns sepia in a theme without a filter of its own.
`talkgenerator formats --looks` lists the looks, and `talkgenerator check` how many of every look's pictures have it.

### Language models

A language model can write the talk: the generator still picks the slides (with the talk's seed), and the model writes what goes on them, as one talk with a thesis, callbacks to earlier slides, and a made-up name and job for the presenter.
A slide the model gets wrong comes from the classic generator instead, and so does the whole talk when the model isn't available.
A name you give with `--presenter` is never sent to the model.

| Provider | `--llm` | Key | Install | Cost |
| --- | --- | --- | --- | --- |
| [OpenRouter](https://openrouter.ai/)'s free models | `openrouter` (the default when there's a key), or `openrouter:<model>[,<fallback model>...]` | `talkgenerator login openrouter`, or `OPENROUTER_API_KEY` ([free](https://openrouter.ai/settings/keys)) | `pip install 'talkgenerator[openai]'` | free: 50 talks a day, or 1,000 once the account has bought $10 of credits |
| Claude | `anthropic` (Claude Opus 5.5), or `anthropic:<model>`, such as `anthropic:claude-haiku-5-5` | `ANTHROPIC_API_KEY` | `pip install 'talkgenerator[anthropic]'` | a few cents a talk with Claude Opus 5.5 |
| OpenAI | `openai:<model>` | `OPENAI_API_KEY` | `pip install 'talkgenerator[openai]'` | depends on the model |
| The models of your ChatGPT plan | `chatgpt` (the default once you've signed in), or `chatgpt:<model>` | `talkgenerator login chatgpt` (Plus or Pro) | `pip install 'talkgenerator[openai]'` | nothing extra: requests count toward your plan's usage |

Only OpenRouter's free models, and your ChatGPT plan's once you've signed in with ChatGPT, write talks without being asked: other models write them when `--llm` or `TALKGENERATOR_LLM` names them.
`talkgenerator login openrouter` is the quickest way to them: you sign in to OpenRouter (or sign up, for free) in your browser, and talkgenerator gets a key of its own, called "talkgenerator" in your OpenRouter settings, which it keeps in your user config folder (`TALKGENERATOR_CONFIG_DIR` puts it elsewhere).
`--headless` signs in on a computer without a browser, `--status` says how many free requests are left today, and `talkgenerator logout openrouter` forgets the key. An `OPENROUTER_API_KEY` goes first.
`talkgenerator login chatgpt` signs in with ChatGPT instead (OpenAI's sign-in for open-source apps on your own computer, in preview): the models of your ChatGPT plan then write your talks, and their requests count toward the plan's usage, which you can follow at [chatgpt.com/settings/usage](https://chatgpt.com/settings/usage) (on Plus, a five-hour limit that every app on your plan shares).
The first sign-in registers talkgenerator with your account; talkgenerator keeps the sign-in in your config folder and refreshes it as it runs out (a talk a month keeps you signed in). `--status` says which account is signed in and which models it has (talks use the first, and `--llm chatgpt:<model>` picks another), `--new-account` switches accounts, and `talkgenerator logout chatgpt` ends the sign-in. It needs a browser on the computer that runs talkgenerator, and talkgenerator.com can't offer it yet: OpenAI only lets hosted apps in from a waitlist.
`--llm none` (or `DISABLE_LLM=1`) makes a classic talk, as the 2019 generator did.
`TALKGENERATOR_LLM_EFFORT` (such as `none`, `minimal`, `low` or `medium`) sets how hard the model thinks before it writes, for the models that take it. Unless it's set, Claude and your ChatGPT plan's models think at `low`, and OpenRouter's free models don't think at all (thinking made them take minutes, and they write as well without), or as little as they can when they have to.
`--language nl` has the model write the talk in Dutch, and so do `fr`, `de`, `es`, `it` and `pt` in French, German, Spanish, Italian and Portuguese; the image searches stay in English.
The classic generator only speaks English, so in such a talk, a slide that doesn't come out as the model wrote it becomes a picture without text instead of a classic slide, and the talk as a whole is English (and says so in the logs) when the model doesn't write it.
After every talk, the logs tell how many requests it made and what they cost, and so does the talk's deck JSON.

### Themes

`--theme` picks a talk's look: by default `random`, a theme the talk's seed picks; `classic` is the 2019 template.
Every other theme draws the slides as shapes on a 1920×1080 canvas: a layout puts every text and image in its box, and every text gets the largest size at which it fits, in fonts nearly every computer has.
The themes come in families: `clean keynote`, `dark minimal`, `corporate`, `academic`, `startup`, `vintage paper`, `kids`, `brutalist` and `neon`, and, for laughs, `1997 WordArt`, `Comic Sans everywhere` and `clip-art corporate`.
A family has many members: the talk's seed picks one, with its own colours (every text reads on its background, by the WCAG contrast rules), fonts, decoration and layouts.
`--theme random` picks a family too, the extremes included unless `--no_extreme_themes` leaves them out, and `--theme chaos` gives every slide a theme of its own (`--style_chaos 0.3` does that for about a third of them).
`TALKGENERATOR_THEME` sets the look of talks that don't ask for one (such as `classic`, to keep the 2019 template), and in Python, `generate_presentation(theme=...)` takes it per talk.
For a settings menu, `talkgenerator.design.themes.catalog()` lists every theme with a label, a line on what it looks like, and whether it's one of those for laughs.
`talkgenerator check --theme random` checks themed talks, and also that their texts read on their backgrounds, fit their boxes and stay on the slide.

### Run arguments

| Argument | Description |
| --- | --- |
| `--topic` | The topic of the generator. This works best if it is a common, well-known noun. Use comma-separated words to generate a slide deck about multiple topics |
| `--num_slides` | The number of slides in the generated presentation (*default: 10*) |
| `--schema` | The presentation schema to use: `default`, `ted` (only copyright-free images), `interview` (no "about me" slides) or `test` |
| `--license_policy` | The license classes the talk's images may have (see [Images: licenses and looks](#images-licenses-and-looks)): `all`, `open` (everything but fair use: no memes, gifs or Reddit's posts), or classes separated by commas (*default: the schema's: `open` for `ted`, else `all`*) |
| `--list` | List the schemas and the slide generators each one uses, then exit |
| `--title` | Title of the presentation. Either `topic` or this one should be set (just setting `topic` is usually more fun though). With only a title, its rarest word becomes the topic |
| `--topic_or_title` | Instead of `--topic` and `--title`: something that could be either, such as `penguins` or `Why I Joined a Penguin Cult`. Four words or more, or a question or exclamation, is the talk's title, with its obvious slips fixed; anything shorter is the topic (or a premise, such as `Cats are liquid`), on which the language model builds a funnier, more specific title. Without a model, it's also a title when it starts like one ("How to", "Why", "The", "A", "My") or makes a claim, and stays as typed. In Python: `generate_presentation(topic_or_title=...)`, and the deck's `topic_or_title` says how it was read |
| `--presenter` | The name that will be present on the first slide. Leave blank for a made-up one (see `--name_styles`) |
| `--name_styles` | Without `--presenter`, the kinds of made-up names the talk's seed picks from, separated by commas: `pun` ("Prof. Anna Tomy" for a talk on medicine), `fun_surname` ("Linda Hivesworth" for bees), `famous_pun` ("Albert Einstone" for geology) and `classic` (a random first and last name, as in 2019). The language model writes the name; without one, talkgenerator has names of its own for many topics, and makes up a classic one otherwise (*default: `pun,fun_surname,famous_pun`*) |
| `--output_folder` | The folder to output the generated presentations (*default: `./output/`*) |
| `--save_ppt` | If this flag is true (*default*), the generated powerpoint will be saved in the `output_folder` |
| `--open_ppt` | If this flag is true (*default*), the generated powerpoint will automatically open after generating |
| `--save_json` | Also save the talk as a deck in JSON (the data the PowerPoint is drawn from), next to the PowerPoint (*default: false*) |
| `--parallel` | If this flag is true (*default*), the generator will generate all slides in parallel |
| `--int_seed` | Seed for the talk's random choices: the same seed gives the same talk, with or without `--parallel` (as long as the sources answer the same). Without one, a random seed is picked, which the logs and the deck JSON mention |
| `--print_logs` / `--verbose` | Print progress (*default: true*); `--verbose` adds debug logs |
| `--debug_notes` | Explain in each slide's speaker notes how it was generated. Off by default, since presenters see the notes |
| `--llm` | The language model that writes the slides, as `provider:model` (see [Language models](#language-models)). `none` makes a classic talk (*default: what `TALKGENERATOR_LLM` says, or else your ChatGPT plan's models once you've signed in with ChatGPT, or else OpenRouter's free models when there's an `OPENROUTER_API_KEY`, or else `none`*) |
| `--language` | The language of the slides: `en`, `nl`, `fr`, `de`, `es`, `it` or `pt`, for talks a language model writes (classic talks are in English) (*default: en*) |
| `--theme` | The look (see [Themes](#themes)): `random`, `classic` (the 2019 template), a family's name such as `"dark minimal"`, or `chaos` (*default: `TALKGENERATOR_THEME`'s, or else random*) |
| `--style_chaos` | How many slides get a theme of their own, from 0 to 1 (*default: 0*) |
| `--no_extreme_themes` | Leave the themes for laughs out of `--theme random` |

### Using it from Python

```python
from talkgenerator import generator

presentation, slide_deck, output_file = generator.generate_presentation(
    schema="default",
    slides=8,
    topic="peanuts",
    output_folder="output",
    open_ppt=False,
)
```

`generator.stream_talk(...)` makes the same talk (with the same options, minus the saving), and hands over its slides while it's made: `talk.started` once its title is known (with the theme's tokens), a `slide.ready` for every slide in order, laid out in the talk's theme, and `talk.finished` with the whole deck.
A language model's slides come while it's still writing the rest of the talk.
Every event is plain data (`talkgenerator.models.events`), whose `event` is its name and whose `to_json()` is what a Server-Sent Event would carry; leaving the loop stops the talk.
While a talk streams, its images are probed instead of downloaded: their first bytes tell what they are and how large, as a browser that shows the slides loads them itself (a PowerPoint made from the deck downloads them then).
Every image in a deck says how a browser may show it (`display`, as its source's terms allow): from its own link (`direct`), through a pass-through proxy (`proxy`), from a copy the app keeps as long as the deck, or not at all (`copy`, for Pixabay), or as a file of talkgenerator's own (`local`).
It also says its license class, its license (with a link), the look it was found for, and what a look at its thumbnail found (brightness, colourfulness, how gray it is, its main colours, and a perceptual hash); `stream_talk` and `generate_presentation` take a `license_policy`.

```python
for event in generator.stream_talk("default", 8, topic="peanuts", theme="random"):
    print(event.event)  # talk.started, slide.ready (8 times), talk.finished
```

## Use it with Claude

Claude can write the talk itself, on your own Claude plan, and leave the rest to talkgenerator: finding images it may use, crediting them on the slides, laying out the deck and saving the PowerPoint.
Claude writes a plan (what every slide says, and what its images should show), talkgenerator turns it into a deck and reports back, and Claude fixes the slides that didn't come out.
There are two ways to set this up, and they work together:

| | The Skill | The MCP server |
| --- | --- | --- |
| What it is | Instructions that teach Claude what makes a good karaoke talk, and how to use talkgenerator's commands | `talkgenerator mcp`: talkgenerator's commands as tools, on your computer |
| Where it works | [Claude Code](https://claude.com/claude-code), and wherever else Claude can run commands; in claude.ai, Claude writes the plan and you render it | [Claude Desktop](https://claude.ai/download), Claude Code and other MCP clients |
| What to install | `pip install talkgenerator` | `pip install 'talkgenerator[mcp]'` |

In Claude Code, the Skill is all you need: Claude runs the commands itself.
In Claude Desktop, add the MCP server, so that Claude can make the decks, and the Skill as well if you like, as it knows more about what makes a good talk.
Nothing goes through talkgenerator.com: talkgenerator works with your own [API keys](#api-keys) and [language model settings](#language-models).

### The Skill

1. Install talkgenerator where Claude runs its commands, `pip install talkgenerator`, and put the API keys you have in a `.env` file (see [API keys](#api-keys)).
2. Add the Skill to Claude:
   - In **Claude Code**, install it as a plugin, straight from this repository:

     ```
     /plugin marketplace add twinters/talk-generator
     /plugin install talkgenerator@talk-generator
     ```

     Or copy the [`skill/skills/talkgenerator`](https://github.com/twinters/talk-generator/tree/master/skill/skills/talkgenerator) folder into `~/.claude/skills/`, for all your projects, or into a project's `.claude/skills/`.
   - In **claude.ai** and the Claude apps, zip that `talkgenerator` folder (so that the zip holds `talkgenerator/SKILL.md`), and upload it under Customize > Skills: "+", then "Create skill", then "Upload a skill". Skills need code execution, which you turn on under Settings > Capabilities.
     Claude's sandbox there may not be able to install talkgenerator or reach the image sources. Claude then gives you the plan as a JSON file, which you render on your computer with `talkgenerator render plan.json`, or which Claude Desktop renders itself with the [MCP server](#the-mcp-server).
3. Ask Claude for, say, "a 10-slide PowerPoint karaoke deck about competitive birdwatching".

The commands the Skill uses work for plans written by hand, or by other tools, too:

| Command | What it does |
| --- | --- |
| `talkgenerator render plan.json [-o talk.pptx]` | Turns a plan (or several: `plans/*.json`) into a PowerPoint, with the deck's JSON and a contact sheet of its images next to it, and prints a report in JSON: per slide, whether it came out as planned, was made the classic way instead, or was left out, and why, and what every image was searched with |
| `talkgenerator formats [--details] [--json]` | The talk formats, and with `--details` the slides a plan can have: their texts, length limits, images and recipes |
| `talkgenerator schema plan` | The plan format, as a JSON Schema (`schema deck` for the deck format) |

[An example plan](https://github.com/twinters/talk-generator/blob/master/skill/skills/talkgenerator/references/example-plan.json) shows what goes in one.

### The MCP server

`talkgenerator mcp` is a local [MCP](https://modelcontextprotocol.io/) server: it gives talkgenerator's commands as tools to Claude Desktop and other MCP clients, so Claude can make decks in a chat, without a shell.
The client starts it on your own computer, where it uses your own keys and saves the decks in a folder of yours. Nothing of it is hosted.

| Tool | What it does |
| --- | --- |
| `list_formats` | The talk formats, themes and languages |
| `describe_format` | The slides a plan for a format can have (as `talkgenerator formats --details --json`) |
| `get_plan_schema` | The plan format, as a JSON Schema (as `talkgenerator schema plan`) |
| `render_plan` | Turns a plan into a PowerPoint, and returns the report of `talkgenerator render`, with the paths of the files it saved |
| `generate_talk` | Makes a whole talk on a topic, as `talkgenerator --topic` does (or with a title, or on a `topic_or_title`): the language model of your settings writes it (OpenRouter's free models, when you have an OpenRouter key), or else the classic generator. Returns where the files are, the talk's seed, and the checks |

1. Install talkgenerator with the MCP SDK on your computer: `pip install 'talkgenerator[mcp]'`.
   On Windows on Arm, install it in an x64 Python: the MCP SDK needs the `cryptography` package, which has no wheels for Windows on Arm.
2. Add the server to your MCP client:
   - In **Claude Desktop**, Settings > Developer > Edit Config opens its config file, `claude_desktop_config.json`. Add the server under `mcpServers`, next to what the file holds already, with the API keys you have under `env`:

     ```json
     {
       "mcpServers": {
         "talkgenerator": {
           "command": "talkgenerator",
           "args": ["mcp"],
           "env": {
             "UNSPLASH_ACCESS_KEY": "...",
             "PEXELS_KEY": "..."
           }
         }
       }
     }
     ```

     Then quit Claude Desktop completely (closing its window leaves it running) and start it again: talkgenerator shows up among the connectors, under the "+" button of a chat.
   - In **Claude Code**, for all your projects (keys go in `--env NAME=value` options, before `--transport`):

     ```sh
     claude mcp add --transport stdio --scope user talkgenerator -- talkgenerator mcp
     ```

   - In **other MCP clients**: the command `talkgenerator`, with the argument `mcp`, over stdio.
3. Ask Claude for, say, "a PowerPoint karaoke deck about competitive birdwatching". The server tells Claude how to write a plan, and when to render it again.

Good to know:

- If the client doesn't find the `talkgenerator` command, give its full path, such as `"/Users/you/talks/.venv/bin/talkgenerator"`, or on Windows `"C:\\Users\\you\\talks\\.venv\\Scripts\\talkgenerator.exe"` (JSON doubles the backslashes). With [uv](https://docs.astral.sh/uv/), there's nothing to install first: use `"command": "uvx"`, with `"args": ["--from", "talkgenerator[mcp]", "talkgenerator", "mcp"]` (on Windows on Arm, put `"--python", "cpython-3.13-windows-x86_64-none"` in front of those).
- Claude Desktop starts the server in a folder of its own, where your `.env` isn't: that's why the keys go under `env`. A key that `talkgenerator login openrouter` got needs no entry, and neither does a sign-in with `talkgenerator login chatgpt`: the server finds them in your config folder. It also finds the `.env` of a clone of this repository when it runs from that clone (installed with `pip install -e '.[mcp]'`).
- Every other setting works under `env` too, such as `TALKGENERATOR_LLM` (see [Language models](#language-models)), which is the only way to have a paid model write the talks: a tool call can't pick one.
- The decks go to a `talkgenerator` folder in your documents, or to the folder that `"args": ["mcp", "--output_folder", "<folder>"]` names, and nowhere else. They never overwrite a file: a deck made again gets a name of its own.
- If the server doesn't show up, run `talkgenerator mcp` in a terminal: it should say that it serves its tools, and wait (Ctrl+C stops it). Claude Desktop keeps what the server logs in `mcp-server-talkgenerator.log`, in its logs folder: on Windows, the `logs` folder next to the config file; on macOS, `~/Library/Logs/Claude`.

## Program structure

See the [wiki](https://github.com/twinters/talk-generator/wiki/Program-structure) to know more about the inner implementation.

## Tests

Tests live in `tests/`. Many of them talk to the live APIs, and are marked as `network` tests:

```sh
uv run pytest                     # everything (tests needing missing API keys are skipped)
uv run pytest -m "not network"    # only the offline tests, as in CI
uv run ruff check . && uv run ruff format --check .
uv run mypy                       # type checking
```

Type checking is gradual: mypy checks the whole package, and the modules listed under `[[tool.mypy.overrides]]` in `pyproject.toml` must be fully annotated.
Add a module to that list once you've typed it.

On Windows on Arm, the dev dependencies leave out the MCP SDK, which doesn't install there, and the MCP server's tests are skipped.
To run them, use an x64 Python, in a virtual environment of its own outside the repository (so that `.venv` stays as it is): set `UV_PROJECT_ENVIRONMENT` to its folder, and run `uv run --extra mcp --python cpython-3.13-windows-x86_64-none pytest tests/test_mcp_server.py`.

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

If you would like to refer to this project in academic work, please cite the following paper:

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
