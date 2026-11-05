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
  models through); and list prices. `TALKGENERATOR_LLM` picks the provider (`none` by default; the real ones
  follow), and a deck tells what its talk asked of language models.
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
- New dependency: pydantic.
- A talk without a seed gets a random one, which the logs and the deck JSON mention, so any talk can be made
  again.
- Randomness comes from `talkgenerator.util.random_util`: every slide draws from its own streams of the talk's
  seed. A lint rule keeps the package from using the `random` module directly.

### Fixed

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
