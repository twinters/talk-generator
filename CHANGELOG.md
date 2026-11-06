# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

The start of talkgenerator 5 (see [docs/v5-plan.md](docs/v5-plan.md)).

### Added

- The deck format: a generated talk as plain, versioned JSON data (`talkgenerator.models.deck`), which the
  PowerPoint renderer (`talkgenerator.render.powerpoint`) draws. `--save_json` (or `save_json=True`) saves it
  next to the PowerPoint, `slide_deck.to_deck()` returns it, and a saved deck renders again on its own.
- `talkgenerator.llm`, the groundwork for LLM-written talks: one interface for every language model provider; a
  `replay` provider that records answers on a cassette and replays them, for offline tests and for making a
  recorded talk again; a ledger of every talk's requests, tokens and cost; budgets (a $0 budget lets only free
  models through); and list prices. `TALKGENERATOR_LLM` picks the provider, and a deck tells what its talk asked
  of language models.
- Talks a language model writes: Python still picks every slide's generator, and the model writes what goes on
  those slides, in one streamed request whose JSON schema is made for the talk (its title, the presenter's job,
  its thesis, then every slide in order), so slides get ready while the answer comes in. A slide that comes out
  wrong, whose images can't be found, or that repeats what came before, is classic; so is the whole talk when
  the model fails or turns the topic down. The presenter's name never reaches the model, and the same seed with
  the same answers gives the same talk. `--llm provider:model` (or `llm=`, or `TALKGENERATOR_LLM`) picks the
  model, `--language` the language it writes in, and `budget=` what it may cost. Every slide generator has a
  recipe (`talkgenerator.plan.kinds`) that tells the model what to write for it; the plans it writes
  (`talkgenerator.models.plan`) are the format that talks written elsewhere, such as by a Claude Skill, will use
  too.
- Language model providers, with their SDKs as optional extras (`talkgenerator[openai]`,
  `talkgenerator[anthropic]`, or `talkgenerator[llm]` for both):
  - `openrouter`: OpenRouter's free models (its free router by default), with your `OPENROUTER_API_KEY`. They
    write talks whenever there's a key, at no cost, and without thinking first, which takes a talk from minutes
    to seconds (models that have to think do so as little as they can). Models listed after the first
    (`openrouter:<model>,<fallback>`) are fallbacks, and only providers that hold to the talk's schema get the
    request.
  - The prompt tells the model what each field of each slide is for, and that a slide's seed word is a starting
    point, not its title: the free models didn't read that from the schema alone.
  - `anthropic`: Claude, Claude Opus 5.5 by default, with your `ANTHROPIC_API_KEY`: structured outputs, thinking
    at low effort (`TALKGENERATOR_LLM_EFFORT` changes it), and server-side fallbacks when a request is declined.
  - `openai:<model>`: OpenAI's models through the Responses API, with your `OPENAI_API_KEY`.

  Paid models only write talks when `--llm` or `TALKGENERATOR_LLM` names them. A talk that a model declines,
  even halfway, is classic. Budgets check every model a request may end up at, and leave room for thinking. Keys
  never show up in logs or error messages.
- `talkgenerator render plan.json` turns a talk plan written elsewhere (by Claude through the Skill, by hand, ...)
  into a PowerPoint, with the deck's JSON (`<name>.deck.json`) and a contact sheet of its images
  (`<name>.images.png`) next to it, and prints a report in JSON: per slide, whether it came out as planned, was
  made the classic way instead, or was left out, and why, what every image was searched with and where it's from,
  and warnings about texts that were cut off and fields that don't exist. A slide's recipe (one of the format's slide generators, such as `two-captions-gifs`)
  picks its look and image sources, and an image query may name an image file of the user's own.
  `talkgenerator formats --details` lists the slide kinds, their texts, limits and recipes, and
  `talkgenerator schema plan` prints the plan format as a JSON Schema.
- The talkgenerator Skill (`skill/`): Claude writes talks for PowerPoint karaoke and improvised TED talks, renders
  them with `talkgenerator render`, and fixes them from the report. It installs as a Claude Code plugin straight
  from this repository (`/plugin marketplace add twinters/talk-generator`), or as a skill folder.
- `talkgenerator mcp`: a local MCP server, for Claude Desktop and other MCP clients (`pip install
  'talkgenerator[mcp]'`; the README says how to add it to Claude Desktop's config). The client starts it on the
  user's computer, over stdio, and it makes talks with the user's own keys and settings; nothing is hosted. Its tools:
  `list_formats` (the formats, themes and languages), `describe_format` (a format's slides, as `formats --details`),
  `get_plan_schema`, `render_plan` (a plan as a PowerPoint, with the report of `talkgenerator render`) and
  `generate_talk` (a talk on a topic, written by the language model the settings name, or else the classic way).
  They answer in JSON with the paths of the files they saved, save those only in the output folder
  (`--output_folder`, by default a `talkgenerator` folder in the user's documents) and never over another file, make
  one talk at a time, and tell the client every few seconds that a talk is still being made. A tool call can't pick
  the language model, so only the user's settings make a paid one write talks, and keys never show up in what the
  tools say or log. The Skill tells Claude Desktop users how to set it up. On Windows on Arm, the MCP SDK only
  installs in an x64 Python, as the `cryptography` package it needs has no wheels there.
- Talks in Dutch (`--language nl`), and in French, German, Spanish, Italian and Portuguese, when a language model
  or a plan writes them: talkgenerator's own words on the slides ("By ...", a chart's "Yes" and "No") are in the
  talk's language too, a slide that doesn't come out becomes a picture of its subject without text (the classic
  slides are English), and recipes that find English texts, such as real quotes, aren't used. A deck says its
  language, and a new check reads its texts with NLTK's stopword lists: a talk that reads as English when it
  shouldn't is an error, and such a slide a warning. `talkgenerator check --language nl --llm ...` checks them.
- Themes (`--theme`, docs/v5-plan.md section 9): besides the 2019 template (`classic`, still the default), talks
  can be drawn as shapes on a 1920×1080 canvas, in a theme of one of twelve families, from `clean keynote` and
  `dark minimal` to `vintage paper` and `neon`, with `1997 WordArt`, `Comic Sans everywhere` and `clip-art
  corporate` for laughs. The talk's seed picks a member of the family: its colours (repaired until every text reads
  on its background, gradients included, by WCAG's contrast rules), font pair, casing, decoration and layouts.
  `--theme random` picks the family too (`--no_extreme_themes` leaves the extremes out), `--theme chaos` gives every
  slide its own theme, and `--style_chaos` some of them. A plan can have a `theme` too (or `talkgenerator render
  --theme`), which the Skill knows about. The layout engine (`talkgenerator.design.engine`) puts
  every element in its box and gives every text the largest size at which it fits, measured with the fonts' own
  files or fonts with the same metrics (`talkgenerator.design.fonts`), so a themed deck's JSON holds every
  element's place and style, and every renderer draws it the same way. `talkgenerator.render.shapes` draws it in
  PowerPoint, and `talkgenerator.render.preview` as pictures with Pillow, with a contact sheet of a whole deck.
- Design checks for themed decks (`talkgenerator.checks.design`): every text reads on what's behind it (a photo
  counts as black or white, as shaded), fits its box, isn't too small, and stays on the slide. On 2,376 themed
  decks made from 66 benchmark talks, nothing came up. `talkgenerator check --theme random` checks themed talks.
- Two new kinds of chart. A trend: a line along two odd axes ("Hours since the meeting started" against
  "Times someone said synergy"), going one of eleven ways, from exponential to hockey stick to crash, with an
  optional second line, the punchline, that draws itself across the chart on a click. And a ranking: bars that
  the last one, the punchline, wins by far. Both come out the classic way too, and a talk has at most one of
  each. A trend can also mark a moment on its line, where it takes off, turns or drops ("I got a cat"), and a
  correlation can have one outlier far above the others ("Me"): a big dot with its name. A field of a slide kind
  can be a choice (`TextField.options`, such as a trend's shape), which the language model picks from a list,
  and which the Skill's reference lists.
- Charts come labelled in funny ways, or bare, for the presenter to explain. A slide generator's recipe can have
  variants (`kinds.Variant`), which the talk's seed picks like the slides themselves: a language model writes
  a trend with funny axis titles and named lines, with axis titles only, or bare; a correlation with or without
  axis titles; a ranking with or without a title on its axis. Classic charts get axis titles from templates
  ("Hours spent thinking about cats", "Public opinion of naps"), and a third of them none. A trend's axes may
  stay empty in a plan too.
- Charts with axes get axis titles: the correlation curves now show the two things they correlate (v4 left
  them out), and a language model or a plan can name them (`x_axis` and `y_axis`). A deck's chart says its axis
  titles and whether its series appear one by one (`reveal`).
- Gifs too large to embed play as Reddit's mp4 copy of them: on r/gifs, many are 40 to 90 MB, while their mp4
  copies are mostly a few MB. In the slideshow, the video starts by itself and loops without sound, as the gif
  would, with a still of the gif as its poster frame. A deck's image names the video in `video_url` (a renderer
  that plays no videos shows the still), and gifs of up to 16 MB stay gifs. A file that's too large is now turned
  down as soon as its host says how large it is, instead of after downloading up to 25 MB of it.
- `talkgenerator login openrouter`: sign in to OpenRouter in the browser (OAuth with PKCE), and talkgenerator gets
  a key of its own, which it keeps in the user's config folder (readable only by the user), so OpenRouter's free
  models write talks without an `OPENROUTER_API_KEY`. `--headless` signs in on a computer without a browser,
  `--status` says how many free requests are left today, and `talkgenerator logout openrouter` forgets the key.
- A list of 736 topics for talks (`talkgenerator/data/topics.txt`, read with `talkgenerator.topics`), from cats
  and sourdough to "a printer that jams", inspired by the improv suggestion lists of Impy and
  improbotics-interface: for suggestions (talk-generator-web's random topic button keeps a copy) and for checks
  on varied topics, `talkgenerator check --random 20`, which draws the same topics for the same first seed.
- `talkgenerator check --decks <folder>` saves every talk's deck, to read what the talks say. The report counts
  the images that share a word with their search (of those whose source describes them) and the slides that
  repeat a title from before, and warns about a talk the language model wrote none of.
- `talkgenerator check --llm provider:model` checks talks a language model writes; to check that the same answers
  give the same talk, the second run replays what the first one got. The report says how many slides the model
  wrote.
- `talkgenerator check`: generates talks on a set of topics (10 by default, `--quick` for 3, `--all` for 30),
  checks every deck, generates every talk again one by one with its seed to see that it comes out the same, and
  writes a JSON report. The checks, in `talkgenerator.checks`: every slide has what its type needs, no template
  leftovers such as `{seed}` or `#symbol#` reach a slide, and images are credited and don't come back.

### Changed

- Every slide is now drawn from its deck form, so a .pptx and its deck JSON always match. Slides look the same
  as before.
- `SlideDeck.to_slide_deck_dictionary()` returns the deck format's slides, which are JSON-ready, instead of
  dictionaries holding image and chart objects.
- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old
  names still work).
- New dependency: pydantic. New optional dependencies: anthropic and openai (see the language model providers), and
  mcp (for `talkgenerator mcp`).
- A talk without a seed gets a random one, which the logs and the deck JSON mention, so any talk can be made
  again.
- Randomness comes from `talkgenerator.util.random_util`: every slide draws from its own streams of the talk's
  seed. A lint rule keeps the package from using the `random` module directly.

### Fixed

- Texts that a language model or a plan writes a little longer than their limit (by up to an eighth) stay whole,
  and a text that has to be cut no longer ends on a little word, as in "Cats were the true scholars of the" (in
  every language, with NLTK's stopword lists). The presenter's job may be 50 characters (was 40), and the prompt
  asks for the title and the job in the talk's language: the free models wrote them in English, after the
  English example. Gif slides no longer all get the teaser "Look at this", which the free models took from the
  prompt's example.
- A free model turned down a harmless topic (it said `safe_topic: false`), which made the talk classic. The flag
  now asks the other way around, as the plan had it: `unsafe_topic`, true only for a hateful or harmful topic.
  As another free model then turned down "penguins" that way, a talk a model finds unsafe is asked for once
  more, saying so; it's classic when the second answer finds it unsafe too.
- When the model's provider fails before the model writes anything ("Provider timed out after 11796ms", which
  made one benchmark talk in thirty classic), OpenRouter gets the request once more; the free router may then
  send it to another model.
- The prompt no longer gives examples that the free models copied: half of the yes/no charts answered "Only on
  Tuesdays", every outlier was "Me" or "Finland", most conclusions were titled "Conclusions", and a third of the
  talks had an "Expectation vs Reality" slide.
- A ranking leaves out bars that are only numbers: a free model wrote its scores between the names ("Druids |
  6 | Priests | 4"), which made a number the winner.
- No slide shows an image of a slide before it: conclusions, which may repeat texts as they sum up, could repeat
  a picture too.
- Gif slides show gifs that move. Their Reddit search takes only animated posts (gif subreddits hold photos
  too), an Imgur `.gifv` without Reddit's animated copy comes from Imgur itself instead of as Reddit's still of
  its first frame, and gifs of up to 16 MB (was 8) are used, as many good ones are 10 to 16 MB.
- `--int_seed` gives the same talk every time, also with `--parallel` (the default), with seed 0, and in every
  Python process. Slides generated in parallel are settled in order, so a talk comes out the same as when its
  slides are generated one by one.
- Template variables that share a start, like `{seed.plural}` and `{seed.plural.title}`, are filled in longest
  first: in an unlucky order, the longer one used to come out as garbage.
- Tracery grammars no longer keep growing in long-running processes such as the web app: every text gets a
  fresh grammar.
- The notes of chart slides no longer hold memory addresses (of their chart data and style), which made the
  same talk's deck differ from one run to the next. `talkgenerator check` found it.

## [4.0.1] - 2026-11-05

### Fixed

- The README now starts with `pip install talkgenerator`, and its links work on the
  PyPI project page.
- Corrected the 4.0.0 notes below: 4.0.0 is the first PyPI release since 2.1.4, and
  black was replaced by ruff rather than updated.

## [4.0.0] - 2026-11-05

The first release on [PyPI](https://pypi.org/project/talkgenerator/) since 2.1.4 in 2020
(`pip install talkgenerator`). This is the modernized, still pre-LLM version of the
generator described in the EvoMUSART 2019 paper: the same approach, brought up to date.

### Added

- New image and content sources: Openverse, Wikimedia Commons, the Art Institute of
  Chicago, GIPHY and Wikiquote. Image credits on the slides link back to the source.
- On-disk caching of search API responses (Datamuse, ConceptNet, Pixabay, Pexels,
  Unsplash), which keeps runs within each API's rate limits. Configurable with
  `TALKGENERATOR_CACHE_DIR` and `DISABLE_CACHE`.
- `.env.example`, and a `DISABLE_<SOURCE>` switch for every source.
- Unsplash photo credits (`Photo by <photographer> on Unsplash`), linking both the
  photographer and Unsplash as the API terms require.
- Gradual type checking with mypy, and a weekly "canary" workflow that runs the network
  tests against the live APIs and opens an issue when a source breaks.

### Changed

- Packaging moved to `pyproject.toml` and uv; CircleCI replaced by GitHub Actions.
- Publishing to PyPI through trusted publishing, so no API tokens are stored anywhere.
- Requires Python 3.11+ and Pillow 13 (which closes ~40 known vulnerabilities); the
  image formats the generator accepts are now restricted.
- Schema modules rewritten from star-imports into explicit registries.
- Openverse is used mostly as a fallback photo source, and is searched as a registered
  app when its credentials are set.
- The `ted` schema stays closer to the requested topic.
- Generation details are kept out of the speaker notes by default (`--debug_notes` to
  include them).

### Fixed

- Dead content sources and holes in generated decks.
- A slide whose images don't come through is now replaced by another slide, instead of
  leaving a hole.
- Reddit posts that link to Imgur now load the image from Reddit's own copy.
- ConceptNet failures fall back to Datamuse and WordNet instead of erroring.

### Dependencies

- All dependencies updated to current versions, now declared in `pyproject.toml` and
  locked in `uv.lock`; the old `requirements.txt` and `setup.py` are gone.
- black replaced by ruff for formatting and linting.

## [2.1.4] - 2020-03-26

The previous release on PyPI. Not covered in detail here.

## [Alpha] - 2019-08-06

Historical snapshot of the version accompanying the paper *"Automatically Generating
Engaging Presentation Slide Decks"* (Winters & Mathewson, EvoMUSART 2019). Preserved
as the `Alpha` git tag; it isn't on PyPI and isn't maintained for current Python.

[Unreleased]: https://github.com/twinters/talk-generator/compare/v4.0.1...HEAD
[4.0.1]: https://github.com/twinters/talk-generator/releases/tag/v4.0.1
[4.0.0]: https://github.com/twinters/talk-generator/compare/Alpha...v4.0.0
[2.1.4]: https://pypi.org/project/talkgenerator/2.1.4/
[Alpha]: https://github.com/twinters/talk-generator/tree/Alpha
