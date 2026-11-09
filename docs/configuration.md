# Keys and settings

talkgenerator reads its settings from environment variables, which can also go in a `.env` file. Copy
[`.env.example`](https://github.com/twinters/talk-generator/blob/master/.env.example) to `.env` in the folder you run
talkgenerator from, and fill in what you have. It also finds a `.env` next to its own files and in the folders above
them, which covers a clone of the repository. Variables set in the environment go first.

Every key is optional. Without any, talkgenerator makes classic talks with the image sources that need no key.

## Image sources

| Source | Used for | Keys | Where to get them |
| --- | --- | --- | --- |
| Reddit | memes, gifs, weird and vintage pictures, charts | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | [create a "script" app](https://www.reddit.com/prefs/apps); the user agent describes your app with your Reddit username, such as `talkgenerator/5.0 (by u/your_username)` |
| Unsplash | photos | `UNSPLASH_ACCESS_KEY` | [Unsplash developers](https://unsplash.com/oauth/applications) (new apps are limited to 50 requests an hour until approved) |
| Pixabay | photos and illustrations | `PIXABAY_KEY` | [Pixabay API](https://pixabay.com/api/docs/) |
| Pexels | photos | `PEXELS_KEY` | [Pexels API](https://www.pexels.com/api/) |
| GIPHY | gifs, next to Reddit's | `GIPHY_API_KEY` | [GIPHY developers](https://developers.giphy.com/dashboard/) |
| [Openverse](https://openverse.org/) | openly licensed photos, museum and archive collections | `OPENVERSE_CLIENT_ID`, `OPENVERSE_CLIENT_SECRET` (optional: without them, Openverse is searched anonymously, at lower rate limits) | [register an app](https://api.openverse.org/v1/#tag/auth/operation/register), then verify its email address |
| [Smithsonian Open Access](https://www.si.edu/openaccess) | CC0 art, history and science | `DATA_GOV_API_KEY` (optional: the other museums need no key) | [an api.data.gov key](https://api.data.gov/signup/) |

These need no key: [Datamuse](https://www.datamuse.com/api/) and WordNet (related words), Goodreads and
[Wikiquote](https://en.wikiquote.org/) (quotes), WikiHow (actions and titles),
[Wikimedia Commons](https://commons.wikimedia.org/) (old photos, paintings, NASA's images), the
[Art Institute of Chicago](https://api.artic.edu/docs/) (public domain artworks), [The Met](https://metmuseum.github.io/)
and the [Cleveland Museum of Art](https://openaccess-api.clevelandart.org/) (public domain artworks and old
photographs), the [Wellcome Collection](https://developers.wellcomecollection.org/) (medicine, science and odd
history), [NASA's Image and Video Library](https://images.nasa.gov/) (space, and NASA's take on anything),
[Flagpedia](https://flagpedia.net/) (flags), [Imgflip](https://imgflip.com/api) (meme templates, which talkgenerator
captions itself), InspiroBot and ShitpostBot 5000.

Most kinds of content come from more than one source, so a source that's down, rate limited or without its key
leaves no holes: the others fill in. A slide that still can't get all its images (say, a gif slide without Reddit
or GIPHY) makes way for another kind of slide, and the logs say which sources had no keys (so does the report of
`talkgenerator render`, under `sources_without_keys`).

Related words used to come from [ConceptNet](https://conceptnet.io/), whose public API has been down since late
2025. talkgenerator still tries it, or a copy of your own (`CONCEPTNET_API_URL`), and falls back to Datamuse and
WordNet.

## Language models

| Variable | What it does |
| --- | --- |
| `OPENROUTER_API_KEY` | An [OpenRouter key](https://openrouter.ai/settings/keys): OpenRouter's free models then write the talks. `talkgenerator login openrouter` gets one for you instead |
| `ANTHROPIC_API_KEY` | An Anthropic key, for `--llm anthropic` (Claude). It doesn't make Claude write talks on its own |
| `OPENAI_API_KEY` | An OpenAI key, for `--llm openai:<model>`. It doesn't make OpenAI's models write talks on its own |
| `TALKGENERATOR_LLM` | The language model that writes talks that don't name one, as `--llm` takes it, such as `openrouter`, `anthropic:claude-haiku-5-5` or `none` |
| `TALKGENERATOR_LLM_EFFORT` | How hard the model thinks before it writes: `none`, `minimal`, `low`, `medium` or `high`, for the models that take it |
| `TALKGENERATOR_LLM_LEVEL` | How much the model does, as `--llm_level` takes it: `basic` (one request a talk) or `advanced` (two: it plans the talk first, for cleverer talks); *default: `basic`* |
| `DISABLE_LLM` | `1` makes talks classic, unless `--llm` names a model |

[Language models](language-models.md) says which model writes a talk when, and what it costs. A sign-in with
`talkgenerator login` needs no variable: talkgenerator keeps it in your config folder.

## Image generators

| Variable | What it does |
| --- | --- |
| `TALKGENERATOR_IMAGE_GENERATOR` | The image generator of talks that don't name one, as `--image_generator` takes it (*default: none*) |
| `GEMINI_API_KEY`, `BFL_API_KEY` | Keys for `gemini` and `flux` (`openai` takes `OPENAI_API_KEY`, and `openrouter` the key that writes your talks) |
| `COMFYUI_URL`, `COMFYUI_WORKFLOW`, `AUTOMATIC1111_URL` | Servers of your own, for `comfyui` and `automatic1111` |
| `TALKGENERATOR_GENERATED_IMAGES` | How many pictures a talk generates at most (*default: 3*) |
| `TALKGENERATOR_IMAGE_COST_LIMIT` | What a talk's pictures may cost, in dollars |
| `TALKGENERATOR_IMAGE_QUALITY` | `medium` or `high` for OpenAI's models (*default: low*) |
| `DISABLE_IMAGE_GENERATION` | `1` switches them all off |

A key never makes a talk generate pictures on its own. [Generated pictures](images-and-themes.md#generated-pictures)
says what they cost.

## Other settings

| Variable | What it does |
| --- | --- |
| `TALKGENERATOR_THEME` | The look of talks that don't ask for one, as `--theme` takes it (*default: `random`*); `classic` keeps the 2019 template |
| `DISABLE_<SOURCE>` | `1` switches a source off: `REDDIT`, `UNSPLASH`, `PIXABAY`, `PEXELS`, `GIPHY`, `OPENVERSE`, `WIKIMEDIA_COMMONS`, `ART_INSTITUTE`, `WIKIHOW`, `WIKIQUOTE`, `SHITPOSTBOT`, `INSPIROBOT`, `MET`, `CLEVELAND`, `WELLCOME`, `NASA`, `SMITHSONIAN`, `FLAGS`, `IMGFLIP`, `CONCEPTNET`, `WIKIPEDIA`, `OPENTDB` (Open Trivia DB), `USELESS_FACTS`, `DAD_JOKES` or `ADVICE_SLIPS` (the flavour texts), such as `DISABLE_WIKIHOW=1` |
| `DISABLE_FACTS` | `1` switches the [real facts](language-models.md#real-facts) off |
| `CONCEPTNET_API_URL` | A ConceptNet API of your own (*default: the public one, `https://api.conceptnet.io`*) |
| `UNSPLASH_APP_NAME` | Your app's name at Unsplash, for the `utm_source` of the links to photographers (*default: `talkgenerator`*) |
| `TALKGENERATOR_CACHE_DIR` | Where the cache of search answers goes (*default: your user cache folder*) |
| `DISABLE_CACHE` | `1` switches that cache off |
| `TALKGENERATOR_CONFIG_DIR` | Where talkgenerator keeps the sign-ins of `talkgenerator login` (*default: your user config folder*) |
| `NLTK_DATA` | Where NLTK's data lives |

## The cache

The answers of the search APIs (Datamuse, ConceptNet, Pixabay, Pexels, Unsplash, Openverse, Wikimedia Commons, the
Art Institute, the other museums, NASA, Imgflip, Wikiquote, Wikipedia, Open Trivia DB and the flavour texts') are cached on disk for one to thirty days, in your user cache folder. That keeps you
within rate limits, and it's what Pixabay's API terms ask for. GIPHY's searches aren't cached, as its API rules forbid
it, and neither are images and web pages, but for generated pictures, so making a talk again generates nothing again.
Keys are never stored in the cache.

## Language data

On its first run, talkgenerator downloads the NLTK data it needs (about 30 MB). For deployments, prepare it up front
with `python run_nltk_download.py --data-dir <folder>` (from a clone of the repository), and point `NLTK_DATA` to that
folder.
