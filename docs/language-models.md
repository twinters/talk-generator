# Language models: free models, keys and costs

A language model can write the talk. talkgenerator still picks the slides, with the talk's seed, the way the 2019
generator did, and the model writes what goes on them, in one request per talk: the title, the presenter's job and a
made-up name, a thesis, and every slide in order, with callbacks to earlier slides. The slides come in while the
model writes the rest.

A slide the model gets wrong (a text that's missing, an image that can't be found, a repeat) comes from the classic
generator instead. So does the whole talk when no model is available, when it fails, or when it turns the topic
down, so a talk never comes out with holes.

A request holds what the talk is about (the topic, or what you typed) and the slides' kinds and words to riff on
(and in an [Advanced](#basic-or-advanced) talk, the plan the model made first).
It never holds the presenter's name you give (`--presenter`), and keys never show up in logs, error messages or
decks.

## Basic or Advanced

How much the model does is the talk's level: `--llm_level`, `llm_level=` in Python, or `TALKGENERATOR_LLM_LEVEL`.

- **Basic**: one request a talk. talkgenerator gives every slide a word to riff on, a related thing that wanders away
  from the topic and back ("penguins": "krill", "seals", "walrus"), and the model writes the talk from those words in
  one go.
- **Advanced**: the model first plans the talk: its title and the presenter's job, a thesis, a running gag, and for
  every slide the word it riffs on (one of the words talkgenerator found for it, or a sharper one) and its idea, the
  point it makes: for a chart, what it measures against what; for a diagram, what its parts are. Its slides are
  written as their ideas come in, a few at a time, in parallel requests (the second slide alone, then two, then three
  at a time), each with the plan so far. Its talks keep one thread, come out cleverer, and are quicker than Basic ones,
  as their slides are written at the same time: five requests for a talk of ten slides, for about twice the tokens
  (see [Costs](#costs)). When the plan fails (an error, a refusal, or a budget that can't afford its requests), the
  talk is written as a Basic one.

Unless a talk asks for a level (or `TALKGENERATOR_LLM_LEVEL` names one), it's Advanced on a model of your own that
costs (Claude, OpenAI's models, Gemini's, your ChatGPT plan's, OpenRouter's paid models), and Basic on free models,
whose free quotas count requests. On [Gemini's free tier](#gemini), ask for Basic: talkgenerator can't tell a free
key from a paid one. On talkgenerator.com, talks on your own API key, or on a paid model of your OpenRouter account,
are Advanced; the site's free models (Basic AI) and your OpenRouter account's free models write Basic talks. A deck
says which level its slides were written at (`llm_level`; none for a classic talk).

At both levels, a slide with a real quote has the model say what it's to be about, in a word or two ("patience",
"tradition"), and talkgenerator finds a real quote about that.

## Real facts

Some slides get a real fact to build on, in the same request: up to three of a talk's slides of history (a made-up
historical figure, old photos, a timeline), fun facts, quizzes and big numbers, from the first sentences of the
topic's English Wikipedia article, or from the events of the day on Wikipedia's main page ("On this day"). The model
keeps what a fact says and twists it: "Only one species, the Galapagos penguin, lives at the equator" becomes a fun
fact about why. No fact names a living person, and none is about death, war, disasters, crime, politics, race or
faiths. A slide that builds on its fact credits the article (CC BY-SA 4.0), in its credit line ("Sources: ..."), and
the deck lists every fact a talk got (`facts`).

The facts come from the cache, or else within eight seconds of the talk's start, while its slides are picked: a talk
whose facts come later, or whose sources are down, goes without them. Classic talks get some too: half of their fun
facts are a real one about the slide's word, with a twist, and half of their quizzes a real question from
[Open Trivia DB](https://opentdb.com). Flavour texts join them: a fun fact may build on a random
[useless fact](https://uselessfacts.jsph.pl), a dare dares the presenter to tell a real
[dad joke](https://icanhazdadjoke.com) about the topic, the closing slide's line can be a real piece of
[advice](https://api.adviceslip.com), in classic talks too, and a problem slide on a real problem's angle (the talk's
why, early on) starts from a real how-to about the topic that people look up on [wikiHow](https://www.wikihow.com)
("How to Repel and Keep Pigeons Away Naturally"). `DISABLE_FACTS=1` switches them all off.

## Which model writes your talks

Free models first: a paid model only writes talks when you ask for it, as a key alone (an `ANTHROPIC_API_KEY` you set
for other tools, say, or a `GEMINI_API_KEY` for generated pictures) shouldn't make talks cost money. talkgenerator
takes the first of:

1. the model `--llm` names (or `llm=` in Python), and else the one `TALKGENERATOR_LLM` names;
2. the models of your ChatGPT plan, once you've signed in with `talkgenerator login chatgpt`;
3. OpenRouter's free models, when there's an OpenRouter key (`OPENROUTER_API_KEY`, or the one
   `talkgenerator login openrouter` got);
4. none: a classic talk, as the 2019 generator made them.

`--llm none` makes a classic talk, and `DISABLE_LLM=1` (or `TALKGENERATOR_LLM=none`) makes every talk classic that
doesn't name a model with `--llm`.

## Providers

| Provider | `--llm` | Key | Install | Cost |
| --- | --- | --- | --- | --- |
| [OpenRouter](https://openrouter.ai/)'s free models | `openrouter` (its free router), or `openrouter:<model>[,<fallback model>...]` | `talkgenerator login openrouter`, or `OPENROUTER_API_KEY` ([free](https://openrouter.ai/settings/keys)) | `pip install 'talkgenerator[openai]'` | free: 50 requests a day, or 1,000 once the account has bought $10 of credits |
| Claude | `anthropic` (Claude Opus 5.5), or `anthropic:<model>`, such as `anthropic:claude-haiku-5-5` | `ANTHROPIC_API_KEY` | `pip install 'talkgenerator[anthropic]'` | a few cents a talk with Claude Opus 5.5 (see [Costs](#costs)) |
| OpenAI | `openai:<model>` | `OPENAI_API_KEY` | `pip install 'talkgenerator[openai]'` | depends on the model |
| [Gemini](#gemini) | `gemini` (Gemini 3.8 Flash), or `gemini:<model>`, such as `gemini:gemini-3.5-flash-lite` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`; [free](https://aistudio.google.com/apikey)) | `pip install 'talkgenerator[gemini]'` | a cent or two a talk with Gemini 3.8 Flash (see [Costs](#costs)); nothing on Gemini's free tier, within its limits |
| The models of your ChatGPT plan | `chatgpt` (the first model your account lists), or `chatgpt:<model>` | `talkgenerator login chatgpt` (Plus or Pro) | `pip install 'talkgenerator[openai]'` | nothing extra: requests count toward your plan's usage |

`pip install 'talkgenerator[llm]'` installs all three SDKs. Without the one a provider needs, its talks are classic,
and the logs say what to install.

### OpenRouter's free models

`openrouter` sends every talk to OpenRouter's free router (`openrouter/free`), which picks one of its free models.
Free models come and go, and get rate limited at busy times, so talkgenerator doesn't depend on one: when the
router's pick fails before it writes anything, the request goes out once more, and may reach another model. A
model you name instead (`openrouter:<model>`) can have fallbacks after it, separated by commas, tried in order. Only
providers that hold to the talk's JSON schema get the request.

The free models answer 20 requests a minute, and 50 a day for accounts that have bought less than $10 of credits in
all, or 1,000 a day once they have. A talk is one request (two with a [vision pick](images-and-themes.md#the-vision-pick),
which has a free model that reads pictures pick the talk's pictures), and `talkgenerator login openrouter --status`
says how many are left today. A request is billed at the price of the model that answers it, so only models whose ids end in
`:free` (and the free router) are sure to cost nothing.

They write without thinking first: thinking made them take minutes, and they write as well without. A model that has
to think does so as little as it can.

### Gemini

Google's Gemini models write talks with a key from [Google AI Studio](https://aistudio.google.com/apikey), in
`GEMINI_API_KEY` (or `GOOGLE_API_KEY`: the same key Gemini's [image models](images-and-themes.md) take), through
Google's `google-genai` SDK. `gemini` is Gemini 3.8 Flash; name another as `gemini:<model>`. Their prices, per million
tokens in and out (the paid tier's, checked on 2026-11-10; the thinking counts as output):

| Model | In | Out |
| --- | --- | --- |
| `gemini-4-argon`, Google's strongest | $2 ($4 from 1 December 2026) | $10 ($20 from 1 December 2026) |
| `gemini-3.8-flash` (and `gemini-3.6-flash`, the one before) | $0.75 ($1.50 from 1 January 2027) | $3.75 ($7.50 from 1 January 2027) |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 |
| `gemini-3.1-flash-lite` | $0.25 | $1.50 |

The answer is held to the talk's JSON schema, and when Gemini finds a schema too complex (a talk with many kinds of
slides can have one), the model gets it as text and writes the JSON by itself. Gemini 3 and later think before they
write: at `low` unless `TALKGENERATOR_LLM_EFFORT` says otherwise (see below).

Gemini has a free tier: a key whose Google Cloud project has no billing account pays nothing, for the Flash and
Flash-Lite models (not Gemini 4 Argon), within limits a minute and a day that Google shows per project in AI Studio
rather than publishes (in October 2026, reported as 5 requests a minute and 20 a day for Gemini 3.8 Flash, and 15 a
minute and 500 a day for the Flash-Lite models). talkgenerator can't tell a free key from a paid one: it prices and
budgets Gemini's requests as the paid tier charges them, and makes their talks Advanced, five requests or more, at
the same time. On the free tier, ask for Basic (`--llm_level basic`, or `TALKGENERATOR_LLM_LEVEL=basic`), one request
a talk, preferably with a Flash-Lite model: `--llm gemini:gemini-3.5-flash-lite --llm_level basic`. Google uses what
the free tier is sent to improve its products (people may read it), and its terms allow only the paid tier for apps
that serve people in the European Economic Area, Switzerland or the United Kingdom.

On Windows on Arm, the SDK doesn't install in Python for Arm (the `cryptography` it needs has no wheels there): use an
x64 Python.

### How hard a model thinks

`TALKGENERATOR_LLM_EFFORT` (such as `none`, `minimal`, `low` or `medium`) sets how hard a model thinks before it
writes, for the models that take it. Unless it's set, Claude, Gemini and your ChatGPT plan's models think at `low`,
OpenRouter's free router at `none`, and a model you name for OpenRouter as it likes. Gemini's levels are `minimal`,
`low`, `medium` and `high` (`none` is `minimal`, and Claude's `xhigh` and `max` are `high`); Gemini 3.8 Flash and
Gemini 4 Argon think at least at `low`, and Gemini 2.5's models as they like (2.5 Flash-Lite doesn't think).

## Costs

A 10-slide Basic talk is one request of about 7,000 to 8,500 tokens in and 900 to 2,700 out; an Advanced one is five
requests of about 16,000 to 20,000 tokens in all and 1,700 to 3,000 out (measured with Claude Haiku 5.5 and Sonnet 5.5
on 2026-11-09; a 20-slide talk has about twice as much):

| Route | A 10-slide talk, Basic | Advanced | Paid by |
| --- | --- | --- | --- |
| Classic, no language model | $0 | | nobody |
| OpenRouter's free models | $0, one request of the day's 50 or 1,000 | $0, five requests | nobody |
| Claude Haiku 5.5 | about $0.002 | about $0.003 | the key's owner |
| Claude Sonnet 5.5 | about $0.03 | about $0.06 | the key's owner |
| Claude Opus 5.5 | about $0.06 | about $0.12 (estimated) | the key's owner |
| Gemini 3.5 Flash-Lite (estimated) | about $0.007 | about $0.01 | the key's owner; nothing on the free tier |
| Gemini 3.8 Flash (estimated) | about $0.01 ($0.03 from 2027) | about $0.02 ($0.04 from 2027) | the key's owner; nothing on the free tier |
| Gemini 4 Argon (estimated) | about $0.03 ($0.07 from December 2026) | about $0.06 ($0.12 from December 2026) | the key's owner |
| Your ChatGPT plan | part of the plan's usage | five requests of it | you, through the plan |
| Claude, through the [Skill](use-with-claude.md) | part of your Claude usage | | you, through your plan |

The Claude prices behind these figures are Anthropic's list prices per million tokens (November 2026): Claude Opus
5.5 $4 in and $20 out, Claude Sonnet 5.5 $2 and $10, Claude Haiku 5.5 $0.10 and $0.50 (for prompts up to 100,000
tokens). Gemini's are [above](#gemini), and its figures estimates from the same tokens (Claude's, thinking
included), not measured. talkgenerator keeps them in `talkgenerator.llm.prices`, with the dates Gemini's go up.

After every talk, the logs tell how many requests it made, how many tokens went in and out, and what they cost, such
as:

```
1 language model request (openrouter:dots-studio/dots-3-note-preview:free): 1,973 tokens in (0 cached), 771 out, $0.0000
```

The talk's deck says the same in its `usage` (with `vision_requests`, those of a vision pick, among its requests),
and which model answered in its `language_model` (and `vision_model`, for a vision pick). In Python, a
`budget` holds a talk to a limit: `talkgenerator.llm.ledger.Budget(max_cost_usd=0)` lets only free models write it,
and `max_requests` caps the requests.

## Signing in

### `talkgenerator login openrouter`

The quickest way to the free models: you sign in to OpenRouter (or sign up, for free) in your browser, and
talkgenerator gets a key of its own, called "talkgenerator" in your OpenRouter settings. It keeps it in your user
config folder, readable only by you (`TALKGENERATOR_CONFIG_DIR` puts it elsewhere). `--headless` signs in on a
computer without a browser (you sign in on another device, and paste the code OpenRouter shows), `--status` says how
many free requests are left today, and `talkgenerator logout openrouter` forgets the key. An `OPENROUTER_API_KEY` goes
before it.

### `talkgenerator login chatgpt`

Sign in with ChatGPT is OpenAI's sign-in for open-source apps that run on your own computer, in preview. Once you've
signed in, the models of your ChatGPT plan (Plus or Pro) write your talks, and their requests count toward the plan's
usage, which you can follow at [chatgpt.com/settings/usage](https://chatgpt.com/settings/usage). On Plus that's a
five-hour limit, which every app on your plan shares.

The first sign-in registers talkgenerator with your account. talkgenerator keeps the sign-in in your config folder,
and refreshes it as it runs out (a talk a month keeps you signed in). `--status` says which account is signed in and
which models it has (talks use the first; `--llm chatgpt:<model>` picks another), `--new-account` switches accounts,
and `talkgenerator logout chatgpt` ends the sign-in. It needs a browser on the computer that runs talkgenerator, and
talkgenerator.com can't offer it: OpenAI only lets hosted apps in from a waitlist.

## Languages

`--language nl` has the model write the talk in Dutch, and so do `fr`, `de`, `es`, `it`, `pt` and `sv` in French,
German, Spanish, Italian, Portuguese and Swedish. talkgenerator's own words on the slides ("By ...", a chart's "Yes" and "No") are in
the talk's language too; the image searches stay in English, which the image sources handle best.

The classic generator only speaks English. So in such a talk, a slide that doesn't come out as the model wrote it
becomes a picture of its subject without text, rather than an English slide, and the talk as a whole is English (and
says so in the logs) when no model writes it. `talkgenerator check --language nl --llm openrouter` checks that the
talks read as Dutch.
