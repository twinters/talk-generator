# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

talkgenerator 5 brings the 2019 generator up to date. Language models write the talks (OpenRouter's free models,
at no cost), Claude can write them too, talks come in themes and stream into the browser, and every talk is a deck,
plain JSON data that the PowerPoint is drawn from. 4.x's command line and settings keep working:
[Migrating from 4.x](https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md) says what
changes, and the README and the [docs](https://github.com/twinters/talk-generator/tree/master/docs) cover the rest.
The design is in [docs/v5-plan.md](https://github.com/twinters/talk-generator/blob/master/docs/v5-plan.md).

### Language models write the talks

- talkgenerator still picks every slide with the talk's seed, and a language model writes what goes on them, in one
  streamed request per talk: the title, the presenter's job and name, a thesis, and every slide in order, with
  callbacks to earlier slides. A slide the model gets wrong, whose images can't be found or that repeats one before
  it comes from the classic generator, and so does the whole talk when the model fails, isn't there, or finds the
  topic unsafe (it's asked once more first, as free models turned down "penguins"). The presenter's name you give
  never reaches the model, and the same seed with the same answers gives the same talk.
- Providers, with their SDKs as extras (`talkgenerator[openai]`, `talkgenerator[anthropic]`, or `talkgenerator[llm]`
  for both): `openrouter` (OpenRouter's free router, or `openrouter:<model>[,<fallback>...]`), `anthropic` (Claude
  Opus 5.5, or `anthropic:<model>`), `openai:<model>`, `chatgpt` (the models of your ChatGPT plan), and
  `replay:<cassette.json>` (answers recorded earlier, for tests). `--llm`, `llm=` and `TALKGENERATOR_LLM` pick one;
  `--llm none` and `DISABLE_LLM=1` make classic talks.
- Free models first: without `TALKGENERATOR_LLM`, your ChatGPT plan's models write the talks once you've signed in
  with ChatGPT, else OpenRouter's free models when there's an OpenRouter key, and paid models only when `--llm` or
  `TALKGENERATOR_LLM` names them. The free models write without thinking first, which takes a talk from minutes to
  seconds; `TALKGENERATOR_LLM_EFFORT` sets how hard a model thinks.
- `talkgenerator login openrouter`: sign in to OpenRouter in the browser, and talkgenerator gets a key of its own,
  kept in your config folder (`--headless`, `--status` for the free requests left today, `logout openrouter`).
- `talkgenerator login chatgpt`: Sign in with ChatGPT (OpenAI's sign-in for open-source apps on your own computer, in
  preview), so that the models of your ChatGPT plan (Plus or Pro) write your talks, counting toward the plan's usage
  (`--status`, `--new-account`, `logout chatgpt`).
- Talks in Dutch, French, German, Spanish, Italian and Portuguese (`--language`), with talkgenerator's own words on
  the slides in the talk's language too. A slide that doesn't come out becomes a picture without text instead of an
  English one, and recipes that find English texts, such as real quotes, are left out.
- After every talk, the logs say how many requests it made and what they cost, and so does the deck (`usage`).
  `budget=` holds a talk to a limit (a $0 budget lets only free models write it). Keys never show up in logs, error
  messages or decks.

### Claude writes talks too

- The talkgenerator Skill (`skill/`): Claude writes talks for PowerPoint karaoke and improvised TED talks as plans,
  renders them with `talkgenerator render`, and fixes them from the report. It installs as a Claude Code plugin
  straight from this repository (`/plugin marketplace add twinters/talk-generator`), or as a skill folder.
- `talkgenerator render plan.json` turns a talk plan into a PowerPoint, with the deck's JSON and a contact sheet of
  its images next to it, and prints a report in JSON: per slide, whether it came out as planned, the classic way or
  not at all, and why, and what every image was searched with, what it shows and where it's from. Texts up to an
  eighth over their length limit stay whole, a text cut shorter ends on a whole word, and an image query may name an
  image file of your own.
- `talkgenerator formats` lists the formats (`--details` the slides a plan can have, with their texts, length limits
  and recipes; `--looks` the image looks; `--licenses` the license policies), and `talkgenerator schema plan|deck`
  prints the plan and deck formats as JSON Schemas.
- `talkgenerator mcp`: a local MCP server for Claude Desktop and other MCP clients (`talkgenerator[mcp]`), with the
  tools `list_formats`, `describe_format`, `get_plan_schema`, `render_plan` and `generate_talk`. The client starts it
  on your computer, where it uses your keys and saves only in its output folder, never over a file; a tool call can't
  pick a paid model. Nothing is hosted. On Windows on Arm, the MCP SDK only installs in an x64 Python.

### Themes and layouts

- `--theme`: besides the 2019 template (`classic`), twelve families of themes drawn as shapes on a 1920×1080 canvas,
  from `clean keynote` and `dark minimal` to `vintage paper` and `neon`, with `1997 WordArt`, `Comic Sans everywhere`
  and `clip-art corporate` for laughs. The talk's seed picks a member of the family: its colours (repaired until
  every text reads on its background, by WCAG's contrast rules), font pair, casing, decoration and layouts. `random`
  is the default, `--no_extreme_themes` leaves the ones for laughs out of it, `--theme chaos` gives every slide a
  theme of its own (`--style_chaos`: some of them), and `TALKGENERATOR_THEME` sets another default. A plan can have
  a `theme` too.
- Every kind of slide has its layouts (51 in all), which put every text and picture in its box, give every text the
  largest size at which it fits, and never repeat the layout of the slide before when another fits. Texts are
  measured with the open fonts that come with talkgenerator (Liberation, Carlito, Caladea and Gelasio), which share
  the widths of Arial, Calibri, Cambria, Georgia and the rest.
- Pictures get their theme's treatment, so that pictures from mixed sources share one look: grayscale, sepia, a
  duotone, black and white, rounded corners, a polaroid frame, grain or a vignette, as PowerPoint picture effects
  ("Reset Picture" brings the original back). Some families' headings get WordArt-style effects (1997's rainbow in an
  outline, bent into a wave or an arch; neon's glow; brutalist's hard shadow), as text effects, so texts stay text.
- Themed slides animate as the 2019 template's do: two or three columns appear click by click, the one before
  dimming, and a video plays as its column appears.
- `talkgenerator.render.preview` draws decks as pictures, with a contact sheet of a whole deck, and
  `talkgenerator.design.themes.catalog()` lists the themes with a label and a description, for a settings menu.

### Images

- License classes and policies: every image has a class (`public-domain`, `open` for CC BY and BY-SA, `stock`,
  `generated` or `fair-use`), and a talk's license policy picks the classes it allows (`--license_policy`: `all`, the
  default; `open`, everything but fair use; or classes, as `public-domain,open`). The `ted` format keeps to `open`,
  the image search keeps to the policy, credits name open and public domain licenses ("CC BY 2.0", linking it), and
  `talkgenerator check` reports an image the policy doesn't allow as an error.
- Images come through slots and an image finder, which searches a look's sources a few at a time, in parallel (with
  v4's caches and cooldowns), filters what they find (license, size, orientation, unsafe descriptions, images the talk
  has already), and picks with the talk's seed: the same seed finds the same images, whichever search answers first.
- Looks (aesthetic profiles), with their own sources, filters and preferences: `photo`, `calm-backdrop`, `vintage`,
  `museum`, `space-science`, `corporate-stock`, `illustration`, `meme-chaos` and more, and flavour packs of curated
  subreddits: `cursed`, `wholesome`, `bad-charts`, `medieval`, `liminal`, `retro-futurism`, `accidental-art`,
  `pareidolia` and `corporate-cringe`. `talkgenerator formats --looks` lists them.
- A look at the candidates' thumbnails (brightness, colourfulness, how gray they are, detail where the text goes,
  main colours, a perceptual hash): vintage slots prefer black and white and sepia, calm backdrops little detail
  behind the text, themed talks pictures that go with the theme's colours, and nearly the same picture doesn't come
  back on another slide. A vintage picture in colour turns sepia in a theme without a filter of its own.
- Gifs too large to embed play as Reddit's mp4 copy of them (many on r/gifs are 40 to 90 MB): the video starts by
  itself and loops without sound, as the gif would, with a still as its poster frame.

### New kinds of slides

- Fourteen kinds drawn as texts on shapes, so that they need no image source (but for a post's and a headline's
  photo): a **big number** with what it counts and a made-up source, **KPI tiles**, a **quiz** (the answer on a
  click), a **social media post**, a **news headline**, an **agenda**, a **section** divider, **Questions?**, and
  native diagrams: a **timeline**, a **pyramid**, a **funnel**, a **cycle**, a small **org chart** and an **iceberg**,
  with their punchlines on a click. They come out the classic way too, in every theme and in the 2019 template, and
  a talk has at most one of each.
- **Venn diagrams** and **2×2 matrices**, with the punchline where the circles overlap or as one named dot, on a
  click.
- Two new charts: a **trend** (a line along two odd axes, going one of eleven ways, from exponential to hockey stick
  to crash, with an optional second line that wipes in as the punchline, and a named moment on the line) and a
  **ranking** (bars that the last one wins by far). Charts with axes get axis titles, and charts come labelled in
  funny ways, or bare, for the presenter to explain.

### Titles and presenter names

- What someone types can be the topic or the title (`--topic_or_title`, `topic_or_title=`): "penguins" as well as
  "Why I Joined a Penguin Cult". What's clearly a title (four words or more, or a question or exclamation) stays the
  title, with its obvious slips fixed; anything shorter is the topic, or a premise ("Cats are liquid"), on which the
  language model builds a funnier, more specific title; in quote marks, it's the title, word for word. Misspelled
  topics are fixed ("pengiuns": "penguins"), and the deck says how what was typed was read.
- Made-up presenter names in styles (`--name_styles`): `pun` ("Prof. Anna Tomy" for medicine), `fun_surname`
  ("Linda Hivesworth" for bees) and `famous_pun` ("Albert Einstone" for geology) by default, and `classic`, the
  random first and last name of 2019. The language model writes the name in the same request, and a name that won't
  do (too long, a placeholder, a real famous name, one on a short blocklist) is turned down. Without a model,
  talkgenerator has names of its own for 642 of the 736 topics in its topic list. A plan can name its presenter
  (`presenter_name`).

### Talks that stream, and decks

- Every talk is a deck (`talkgenerator.models.deck`): plain, versioned JSON data with every text, image, credit and
  layout, which the PowerPoint is drawn from, so the two always match. `--save_json true` saves it next to the
  PowerPoint, `slide_deck.to_deck()` returns it, and `talkgenerator.render.powerpoint.render_pptx` draws a saved deck
  again.
- `generator.stream_talk()` hands a talk over while it's made: `talk.started` once its title is known, a
  `slide.ready` for every slide, in order and laid out in its theme, and `talk.finished` with the whole deck, the same
  deck as a talk made at once. A language model's slides come while it writes the rest, and images are probed rather
  than downloaded, as a browser loads them itself. talkgenerator.com streams its talks this way, and
  `image_util.forget_downloads()` gives back the memory of a PowerPoint's downloaded images, for a server.
- A deck's images say how a browser may show them (`display`: `direct`, `proxy`, `copy` or `local`, as their sources'
  terms allow), their size, their license and their look, and a streamed slide tells Unsplash that its photos were
  used, as a PowerPoint does. What appears on a click is marked on its element (`appears_on_click`), for renderers
  that play clicks.

### Checks

- `talkgenerator check` makes talks on a set of topics (10 by default, `--quick` for 3, `--all` for 30, `--random N`
  from talkgenerator's list of 736 topics), checks every deck (every slide has what it needs, no template leftovers
  such as `{seed}`, images credited and allowed by the license policy, the talk's language, and in themed talks texts
  that read on their backgrounds, fit their boxes and stay on the slide), makes every talk again with its seed to see
  that it comes out the same, and writes a JSON report. `--llm` checks talks a language model writes (the second run
  replays its answers), `--theme` themed talks, and `--decks` saves every deck. `talkgenerator.topics` has the list
  of topics, for suggestions.

### Changed

- A talk's look is a theme its seed picks (`--theme random`), not the 2019 template: `--theme classic` or
  `TALKGENERATOR_THEME=classic` keeps the template.
- A classic talk on a topic talkgenerator has presenter names for gets one of them, instead of a random first and
  last name: `--name_styles classic` keeps the random ones.
- A seed gives another talk than in 4.x: every slide draws from its own random streams of the talk's seed now
  (`talkgenerator.util.random_util`), and the new kinds of slides (about one in six of a talk's slides) and names come
  into it. A talk without a seed gets a random one, which the logs and the deck mention, so any talk can be made
  again.
- Images come through the image finder, from about the same sources with about the same weights as before. History
  slides show old photographs in black and white or sepia, statements' backdrops come from Pixabay, Unsplash and
  Pexels (they were Pixabay's only), Reddit's chart slides take charts from r/dataisugly too, and Reddit's images say
  what they show. Searching sources a few at a time asks more of them per image.
- Charts are quieter, so that the joke stands out: no gridlines, tick marks or numbers along their axes. A yes/no
  chart's columns have their shares on top, a doughnut its shares on its ring and a legend, and chart texts are
  bigger, in the template's or the theme's font.
- GIPHY's searches aren't cached any more, as GIPHY's API rules forbid it; the other search APIs still are.
- `SlideDeck.to_slide_deck_dictionary()` returns the deck's slides, which are JSON, instead of dictionaries holding
  image and chart objects: a breaking change for code that read those (see Deprecated).
- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old names
  still work).
- New dependency: pydantic. New extras: `openai`, `anthropic`, `llm` and `mcp`.
- The README is shorter, and `docs/` has pages on the command line, language models, keys and settings, images and
  themes, using it with Claude and from Python, and migrating from 4.x.

### Deprecated

- `generator.generate_presentation()` keeps working throughout talkgenerator 5, with a `DeprecationWarning` that
  points to `generator.stream_talk()` (whose `talk.finished` event has the deck, which `render_pptx` turns into a
  PowerPoint) or to `talkgenerator.plan.external.render_plan()`. talkgenerator's own commands, the MCP server and
  `stream_talk` don't warn.
- `SlideDeck.to_slide_deck_dictionary()` keeps working throughout talkgenerator 5, with a `DeprecationWarning` that
  points to `slide_deck.to_deck()`.

### Fixed

- `--int_seed` gives the same talk every time, also with `--parallel` (the default), with seed 0, and in every Python
  process: slides made in parallel shared one random generator, and seed 0 skipped the reseeding.
- No slide shows an image of a slide before it (nor nearly the same one). Conclusions, which may repeat texts as they
  sum up, could repeat a picture too, and a slide generator allowed to repeat a text could repeat an image, which
  generating in parallel then kept rejecting, round after round.
- Pictures shown whole keep their shape. They were padded by the wrong amount, so a 9:16 picture on a full-picture
  slide came out 43% too wide, and a square picture in an "About me" column 6% too narrow.
- Gif slides show gifs that move: their Reddit search takes only animated posts, an Imgur `.gifv` comes from Imgur
  instead of as Reddit's still of its first frame, and gifs of up to 16 MB are used (was 8). A file that's too large
  is turned down as soon as its host says how large it is.
- The texts on charts, such as a pie's names and shares, showed in black, whatever the chart's font said, so on the
  2019 template's black they didn't show at all; they're in the template's text colour now. Column charts no longer
  have gridlines, which v4 meant to leave out (but misspelt `has_mayor_gridlines`).
- WikiHow's search finds lists, quizzes and questions too, which became odd actions and titles ("e 20 Top Games Like
  Club Penguin"): only pages that teach an action count now.
- Template variables that share a start, like `{seed.plural}` and `{seed.plural.title}`, are filled in longest first:
  in an unlucky order, the longer one came out as garbage.
- Tracery grammars no longer keep growing in long-running processes such as the web app.
- The notes of chart slides no longer hold memory addresses, which made the same talk differ from one run to the
  next.
- Wikimedia Commons credits named some authors twice ("Unknown author Unknown author").

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
