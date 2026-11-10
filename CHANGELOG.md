# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

talkgenerator 5 brings the 2019 generator up to date. Language models write the talks (OpenRouter's free models, at
no cost), Claude can write them too, and talks come in themes, formats and personas, with more than thirty new kinds
of slides. Every talk is a deck, plain JSON data that the PowerPoint is drawn from and that streams into the browser
on talkgenerator.com. 4.x's command line, settings and `.env` keep working. "Changed" below says what's different by
default, and [Migrating from 4.x](https://github.com/twinters/talk-generator/blob/master/docs/migrating-from-4.md)
how to keep 4.x's talks. The [docs](https://github.com/twinters/talk-generator/tree/master/docs) cover the rest, and
[docs/v5-plan.md](https://github.com/twinters/talk-generator/blob/master/docs/v5-plan.md) the design.

### Language models write the talks

- talkgenerator still picks every slide with the talk's seed, and a language model writes what goes on them, in one
  streamed request per talk: the title, the presenter's job and name, a thesis, and every slide in order, with
  callbacks to earlier slides. A slide the model gets wrong comes from the classic generator, and so does the whole
  talk when the model fails, isn't set up, or finds the topic unsafe. The same seed with the same answers gives the
  same talk.
- `--llm` (or `llm=`, or `TALKGENERATOR_LLM`) picks the model: `openrouter` (OpenRouter's free models, or
  `openrouter:<model>`), `anthropic` (Claude Opus 5.5, or `anthropic:<model>`), `openai:<model>`, `chatgpt` (the
  models of your ChatGPT plan), or `none` for a classic talk (`DISABLE_LLM=1` makes every talk classic that doesn't
  name a model). Their SDKs are extras: `talkgenerator[openai]`, `talkgenerator[anthropic]`, or `talkgenerator[llm]`
  for both.
- Free models first: unless a model is named, your ChatGPT plan's models write the talk once you've signed in with
  ChatGPT, else OpenRouter's free models when there's an OpenRouter key, and else it's classic. A paid model only
  writes when you name it, whatever keys are set.
- How much the model does is the talk's level (`--llm_level`, `llm_level=`, `TALKGENERATOR_LLM_LEVEL`): `basic`, the
  one request above; or `advanced`, the default on a paid model of your own, where the model first plans the talk
  (a thesis, a running gag, and every slide's word to riff on and its idea) and then writes the slides as their ideas
  come in, a few at a time in parallel: cleverer talks, no slower, in five requests for about twice the tokens
  (about $0.003 a talk with Claude Haiku, $0.06 with Sonnet). Free models stay `basic`.
- `talkgenerator login openrouter` signs in to OpenRouter in the browser and keeps a key of its own in your config
  folder, and `talkgenerator login chatgpt` signs in with ChatGPT (OpenAI's sign-in for open-source apps, in
  preview); both have `--status`, and `logout`.
- Talks in Dutch, French, German, Spanish, Italian, Portuguese and Swedish (`--language`), with talkgenerator's own
  words on the slides in the talk's language too.
- The logs and the deck (`usage`) say how many requests a talk made and what they cost, and `budget=` holds a talk
  to a limit. Keys never show up in logs, error messages or decks.

### Claude writes talks too

- The talkgenerator Skill (`skill/`): Claude writes a talk as a plan, renders it, and fixes it from the report. It
  installs as a Claude Code plugin straight from this repository (`/plugin marketplace add twinters/talk-generator`).
- `talkgenerator render plan.json` turns a talk plan into a PowerPoint, its deck JSON and a contact sheet of its
  images, and prints a report in JSON: per slide, whether it came out as planned, and what each image was searched
  with, shows and comes from. `talkgenerator formats` lists the formats, the slides a plan can have (`--details`),
  the image looks, license policies, meme templates and image generators, and `talkgenerator schema plan|deck`
  prints the plan and deck formats as JSON Schemas.
- `talkgenerator mcp`: a local MCP server for Claude Desktop and other MCP clients (`talkgenerator[mcp]`), with tools
  to list and describe the formats, get the plan schema, render a plan and generate a talk. It runs on your computer
  with your keys, saves only in its output folder, and a tool call can't pick a paid model. Nothing is hosted.

### Themes and layouts

- Seventeen families of themes, drawn as shapes on a 1920×1080 canvas: from `clean keynote`, `dark minimal` and
  `Swiss poster` to `hacker terminal`, `blueprint`, `chalkboard` and `newspaper`, with `1997 WordArt`, `Comic Sans
  everywhere` and `clip-art corporate` for laughs. By default (`--theme random`) the talk's seed picks a member of a
  family: its colours, repaired until every text reads on its background by WCAG's contrast rules, its fonts, its
  decoration and its layouts. `--theme` names a family or `classic` (the 2019 template), `--theme_families` limits
  the seed's choice, `--no_extreme_themes` leaves out the ones for laughs, `--theme chaos` gives every slide a theme
  of its own, and `TALKGENERATOR_THEME` sets another default.
- About ninety layouts put every text and picture in its box, give every text the largest size at which it fits, and
  never repeat the slide before's layout when another fits.
- Every family has its own decoration (a terminal's window bar and prompts, a blueprint's grid and title block, a
  chalkboard's wooden frame, a newspaper's masthead...), drawn with the deck's own shapes, and numbers its slides
  ("7/12") in its own style.
- Pictures get their theme's treatment, so that pictures from mixed sources share a look: most a gentle tint, the
  strong filters (grayscale, sepia, a duotone) only in families made for them, and rounded corners, a polaroid frame,
  grain or a vignette as PowerPoint picture effects. Some families' headings get WordArt-style effects (a rainbow in
  an outline, a glow, a hard shadow), as text effects, so they stay text.
- Open fonts come with talkgenerator (`data/fonts`): metric twins of Arial, Calibri, Cambria and Georgia, so texts
  measure the same on every computer, and Google Fonts pairings, which a themed .pptx carries inside it, so that
  PowerPoint shows them where they aren't installed.
- Slides animate: two or three columns appear click by click, a list one thing a click with its punchline last, and
  what belongs to a picture (its frame, its tape) comes in with it.
- `talkgenerator.render.preview` draws decks as pictures (contact sheets, and slides click by click), and
  `talkgenerator.design.themes.catalog()` lists the themes for a settings menu.

### Images

- License classes and policies: every image is `public-domain`, `open` (CC BY and BY-SA), `stock`, `generated` or
  `fair-use`, and `--license_policy` picks the classes a talk allows (`all` by default; `open` is everything but
  fair use). The `ted` format keeps to `open`, the image search keeps to the policy, and credits name open licenses,
  with a link.
- An image finder searches a look's sources a few at a time, in parallel, filters what they find (license, size,
  shape, unsafe descriptions, pictures the talk already has), looks at the thumbnails (detail where the text goes,
  colours that go with the theme, near-duplicates) and picks with the talk's seed. Looks such as `photo`,
  `calm-backdrop`, `vintage`, `museum` and `space-science`, and flavour packs of subreddits (`cursed`, `wholesome`,
  `liminal`...): `talkgenerator formats --looks` lists them.
- New sources: the Met, the Cleveland Museum of Art, the Wellcome Collection, the Smithsonian (with a free
  `DATA_GOV_API_KEY`), NASA's Image and Video Library, Flagpedia's flags and Imgflip's meme templates.
- Generated pictures, when you ask for them (`--image_generator`, never because a key is set): OpenAI's or
  OpenRouter's image models, Google's Gemini, Black Forest Labs' FLUX, or a ComfyUI or Automatic1111 server of your
  own draws what stock photos can't show well (the presenter's weird hobby, the cover of their book). At most three a
  talk (`--generated_images`), priced before they're made (`TALKGENERATOR_IMAGE_COST_LIMIT`), credited
  "AI-generated with <model>", kept on disk, and never of a real person, a brand, gore or sexual content.
- The vision pick (`--vision_pick`, off by default): a vision model picks each picture of a talk's planned slides
  among the finder's and up to three runners-up, in one request a talk.
- Gifs too large to embed play as Reddit's mp4 copy of them.

### More kinds of slides

- More than thirty new kinds, in every theme and in the 2019 template, written by the classic generator or by the
  language model: a big number, KPI tiles, a quiz, a social media post, a news headline, an agenda, a section
  divider, "Questions?" (ending on a funny picture, a last tip, or a callback to an earlier slide's picture), and an
  academic talk's references; diagrams (a timeline, a pyramid, a funnel, a cycle, an org chart, an iceberg, a
  process, a Venn diagram and a 2×2 matrix); trend and ranking charts; memes with live captions on 25 of Imgflip's
  templates; and kinds from real PowerPoint karaoke decks: a fun fact, an acronym, a dare for the presenter or the
  whole audience, a flowchart whose every answer leads to the same end, a tier list, a wall of text, an alignment
  chart, red flags, reviews with stars and a fake error message.
- Livelier slides: big numbers and KPI tiles over a picture of what they're about, a weird but related picture in a
  diagram's box now and then, scatter plots of eleven shapes with a fitted line or named clusters, emoji in front of
  a list's things now and then, and charts labelled in funny ways, or bare.
- A problem slide, the talk's why, early on: about three pitches in four, four academic talks in five and a quarter
  of TED-like talks open on a problem, weird, everyday, crossed with something else, typical of the topic, or real (a
  how-to people look up on wikiHow), with a picture of it behind it or beside it.
- A talk has at most one of most kinds (memes: two), and a list's things appear a click each, the punchline last.

### Formats and personas

- Four new formats, each going through its arc: `--schema pitch` (a startup pitched to investors, from the problem to
  the ask), `academic` (research at a conference: the method, p-values, the limitations as an iceberg), `corporate`
  (an all-hands: the KPIs against their targets, the new org chart) and `keynote` (a product launch: the reveal, a
  demo that crashes, one more thing). `--schema random` leaves the format to the talk's seed, which makes 7 talks in
  10 TED-like.
- Personas: the talk's seed picks who presents it, one of thirteen (a disgraced professor, a startup founder, a
  medieval historian, a kindergarten teacher, a retiree and their old job...), whose favourite kinds of slides,
  titles, names, themes, formats and pictures come up more often (`--persona`, `--personas`, `--persona none`;
  `talkgenerator.personas.catalog()`).
- What's typed can be the topic or the title (`--topic_or_title`): "penguins" as well as "Why I Joined a Penguin
  Cult", with misspelt topics fixed.
- Made-up presenter names in styles (`--name_styles`): puns on the topic ("Prof. Anna Tomy" for medicine), fun
  surnames ("Linda Hivesworth"), famous-name puns ("Albert Einstone"), or `classic`, 2019's random names. A famous
  living person's real name is never used.

### Real facts and classic texts

- Classic talks take their texts from content packs (`talkgenerator/data/packs`): the TED pack has every classic text
  of TED-like talks, in a TED talk's voice and about four times as many as 4.x had, each speaking of the topic as
  English does and checked by tests. The new formats have packs of their own.
- The words slides start from are things: nouns first (Datamuse's parts of speech), familiar ones, none of a family
  twice, and never far from the topic, so no "Volcanoes vs. eruptive" on a scatter plot. A real quote is searched for
  a theme the language model picks for it.
- Real facts: a talk a language model writes gets up to three facts from Wikipedia (the topic's article, and the
  day's events) for its slides of history, fun facts, quizzes and big numbers, which the model keeps true and twists.
  Classic talks get half of their fun facts from Wikipedia and half of their quizzes from Open Trivia DB, and now and
  then a useless fact, a real dad joke to tell or a piece of advice (the Advice Slip). No fact names a living
  person, or is about death, war, disasters, crime, politics, race or faiths. A slide that uses one credits it, and
  the deck lists them (`facts`). They need no keys, and `DISABLE_FACTS=1` switches them off.

### Talks that stream, and decks

- Every talk is a deck (`talkgenerator.models.deck`): plain, versioned JSON with every text, image, credit and
  layout, which the PowerPoint is drawn from. `--save_json true` saves it, `slide_deck.to_deck()` returns it, and
  `talkgenerator.render.powerpoint.render_pptx(deck)` draws a saved deck again.
- `generator.stream_talk()` hands a talk over while it's made: `talk.started`, a `slide.ready` for every slide in
  order, `slide.updated` when a generated picture comes in, and `talk.finished` with the deck. Images are probed
  rather than downloaded, and each says how a browser may show it (`display`). talkgenerator.com streams its talks
  this way.
- For a presenter who catches up with the making: `early=4` sends an early version of each of the talk's last four
  slides early on (`slide.early`: a quick slide about that slide's own topic, at its place), `spares=3` sends three
  quick spare slides about the talk's topic (`slide.spare`), and `slide_seconds=8` makes a slide that takes longer
  than 8 seconds come at once with what's quick (its early version, if it has one), the real slide taking its place
  once it's made.

### Lighter and faster

- Less memory: WordNet is read from its own files (8 MB instead of about 150 MB), and pictures are decoded and scaled
  to the size their place on the slide needs, so a big photo no longer takes hundreds of megabytes on its way into a
  .pptx, and a .pptx comes out up to a third smaller.
- `parallel` can be a number (at most that many slides at once), a PowerPoint's pictures are downloaded four at a
  time, a host that times out isn't asked again, and a search service that takes more than 8 seconds is skipped for
  5 minutes.

### Checks

- `talkgenerator check` makes talks on a set of topics (`--quick`, `--all`, `--random N`), checks every deck (every
  slide complete, no template leftovers, images credited and allowed, the talk's language, and in themes, texts that
  read on what's behind them and fit their boxes), makes every talk again to see that it comes out the same, and
  writes a JSON report. `--llm` checks talks a language model writes, `--theme` themed ones, and `--decks` saves the
  decks.

### Changed

- A talk's look is a theme its seed picks, not the 2019 template: `--theme classic` or `TALKGENERATOR_THEME=classic`
  keeps the template.
- A talk has a persona, which shapes its mix of slides and its title (`--persona none` gives the format's own), and
  a classic talk's presenter gets a name that puns on its topic when talkgenerator has one (`--name_styles classic`
  keeps the random first and last names).
- Slides are numbered ("7/12"), small, in the 2019 template's bottom right corner too.
- Classic talks look up real facts and flavour texts, as above (`DISABLE_FACTS=1` switches them off), and take their
  texts from the content packs.
- A seed gives another talk than in 4.x: every slide draws from random streams of its own, and the new kinds of
  slides come into it. A talk without a seed gets a random one, which the logs and the deck mention.
- Images come through the image finder, from about the same sources as before, and new ones: history slides prefer
  old photographs (museums' too) in black and white or sepia, statements' backdrops come from Pixabay, Unsplash and
  Pexels, Reddit's chart slides take r/dataisugly's too, and the flavour packs search more subreddits.
- InspiroBot's posters are drawn with the talk's seed from its older posters, so no request goes to its API any more.
- Charts are quieter (no gridlines, tick marks or numbers along their axes), with bigger texts in the template's or
  the theme's font.
- GIPHY's searches aren't cached any more, as GIPHY's API rules forbid it.
- `SlideDeck.to_slide_deck_dictionary()` returns the deck's slides as JSON-ready dictionaries, instead of
  dictionaries holding image and chart objects: a breaking change for code that read those.
- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old names
  still work).
- New dependency: pydantic. New extras: `openai`, `anthropic`, `llm` and `mcp`. requests and lxml are at 2.33 and 6.1 or
  later, past their security advisories.
- The README is shorter, and `docs/` has pages on the command line, language models, keys and settings, images and
  themes, using it with Claude and from Python, and migrating from 4.x.

### Deprecated

- `generator.generate_presentation()` and `SlideDeck.to_slide_deck_dictionary()` keep working throughout
  talkgenerator 5, with a `DeprecationWarning` that says what to use instead: `generator.stream_talk()` (whose
  `talk.finished` event has the deck, which `render_pptx` turns into a PowerPoint) or
  `talkgenerator.plan.external.render_plan()`, and `slide_deck.to_deck()`. talkgenerator's own commands, the MCP
  server and `stream_talk` don't warn.

### Fixed

- `--int_seed` gives the same talk every time, also with `--parallel` (the default), with seed 0 and in every Python
  process, and the notes of chart slides no longer hold memory addresses.
- Classic texts speak of the topic as English does: no more "How many the titanics are "too many the titanics"?" or
  "Plant That Won'T Dies are great". Template variables that share a start (`{seed.plural}` and
  `{seed.plural.title}`) are filled in longest first, and Tracery grammars no longer keep growing in long-running
  processes such as a web app.
- WikiHow's actions are how-tos that teach an action about the slide's seed, and none of the worst: a lighthouse talk
  was titled "Never, Ever Make Sex Better".
- No slide shows a picture of an earlier slide, nor nearly the same one.
- Pictures shown whole keep their shape (a 9:16 picture on a full-picture slide came out 43% too wide), and gif
  slides show gifs that move (animated posts only, Imgur's `.gifv`, up to 16 MB).
- Chart texts are in the template's text colour (they were black, on the 2019 template's black), and column charts
  lost the gridlines that v4 meant to leave out.
- The on-disk cache reads back what it keeps: Unsplash's searches were stored but never read, and Pixabay's, Commons'
  and Openverse's stopped being read once a host had set a cookie. A source that's cooling down after an outage or a
  rate limit still answers what it answered before, from its caches.
- `interview` talks no longer get an about-me slide, and "a title or none" gives none half the time.
- Wikimedia Commons credits no longer name an author twice ("Unknown author Unknown author").
- Quote slides no longer quote a film's or a show's cast list from Wikiquote: an actor's name and their role.

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
