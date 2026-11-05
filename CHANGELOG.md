# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

<!-- Add changes here as you merge them; release.py moves them under the new version at release time. -->

### Fixed

- `--int_seed` (`int_seed` in Python) now makes the same random choices on every run, also
  with `--parallel` (the default). Seeded runs generate their slides one by one: parallel
  threads shared one random generator, and skipped reseeding it for seed 0. Live sources
  can still return other images and texts from one run to the next.

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
