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
Image credits on the slides link to the photographer's or the image's page.
Related words used to come from [ConceptNet](https://conceptnet.io/), whose public API has been down since late 2025.
The generator still tries it (or a self-hosted copy set with `CONCEPTNET_API_URL`), and falls back to Datamuse and WordNet when it doesn't answer.

Any source can be switched off with `DISABLE_<SOURCE>=1`, e.g. `DISABLE_WIKIHOW=1` (see `.env.example`).

Search API responses (Datamuse, ConceptNet, Pixabay, Pexels, Unsplash) are cached on disk for one to thirty days, in your user cache folder.
That keeps you within rate limits and is what Pixabay's API terms ask for.
API keys are never stored in the cache.
Set `TALKGENERATOR_CACHE_DIR` to put the cache elsewhere, or `DISABLE_CACHE=1` to turn it off.

### Run arguments

| Argument | Description |
| --- | --- |
| `--topic` | The topic of the generator. This works best if it is a common, well-known noun. Use comma-separated words to generate a slide deck about multiple topics |
| `--num_slides` | The number of slides in the generated presentation (*default: 10*) |
| `--schema` | The presentation schema to use: `default`, `ted` (only copyright-free images), `interview` (no "about me" slides) or `test` |
| `--list` | List the schemas and the slide generators each one uses, then exit |
| `--title` | Title of the presentation. Either `topic` or this one should be set (just setting `topic` is usually more fun though). With only a title, its rarest word becomes the topic |
| `--presenter` | The name that will be present on the first slide. Leave blank for an automatically generated name |
| `--output_folder` | The folder to output the generated presentations (*default: `./output/`*) |
| `--save_ppt` | If this flag is true (*default*), the generated powerpoint will be saved in the `output_folder` |
| `--open_ppt` | If this flag is true (*default*), the generated powerpoint will automatically open after generating |
| `--save_json` | Also save the talk as a deck in JSON (the data the PowerPoint is drawn from), next to the PowerPoint (*default: false*) |
| `--parallel` | If this flag is true (*default*), the generator will generate all slides in parallel |
| `--int_seed` | Seed for the talk's random choices: the same seed gives the same talk, with or without `--parallel` (as long as the sources answer the same). Without one, a random seed is picked, which the logs and the deck JSON mention |
| `--print_logs` / `--verbose` | Print progress (*default: true*); `--verbose` adds debug logs |
| `--debug_notes` | Explain in each slide's speaker notes how it was generated. Off by default, since presenters see the notes |

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
