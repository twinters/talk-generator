# talk-generator v5: design and roadmap

Status: approved on 2026-11-05 ([section 17](#17-decisions-and-open-questions) lists the decisions). Milestone 1,
the groundwork, is done; milestone 2 is under way ([section 16](#16-milestones)). Nothing ships until 5.0.0.

v4.0.0 is the modernized version of the 2019 generator from the EvoMUSART paper. v5 brings it up to 2026
standards: LLM-written talks, generated images, more sources, themes and talk formats, and slides that stream
into the browser on talkgenerator.com. The 4.x line stays on `master` and keeps powering talkgenerator.com
until 5.0 is ready.

## Contents

1. [Summary](#1-summary)
2. [Goals, constraints and non-goals](#2-goals-constraints-and-non-goals)
3. [Where v4 stands](#3-where-v4-stands)
4. [Architecture: plan, realize, render](#4-architecture-plan-realize-render)
5. [LLMs](#5-llms)
6. [Agent mode: talkgenerator as a Claude Skill](#6-agent-mode-talkgenerator-as-a-claude-skill)
7. [Talk formats](#7-talk-formats)
8. [Slide types and variety](#8-slide-types-and-variety)
9. [Themes, layouts and design quality](#9-themes-layouts-and-design-quality)
10. [Images: sources, aesthetics and generation](#10-images-sources-aesthetics-and-generation)
11. [Text sources and content packs](#11-text-sources-and-content-packs)
12. [Determinism, seeds, tests and the paper baseline](#12-determinism-seeds-tests-and-the-paper-baseline)
13. [talkgenerator.com: streaming, $0 operation and limits](#13-talkgeneratorcom-streaming-0-operation-and-limits)
14. [Automated quality checks](#14-automated-quality-checks)
15. [Branches, releases and compatibility](#15-branches-releases-and-compatibility)
16. [Milestones](#16-milestones)
17. [Decisions and open questions](#17-decisions-and-open-questions)
18. [Sources](#18-sources)

## 1. Summary

- **One deck format.** Every talk becomes a versioned Deck JSON document. The .pptx file, the browser view on
  talkgenerator.com and the test thumbnails are all renderers of that document, so slides can be streamed,
  stored, shared and rendered again.
- **Plan, realize, render.** A planner decides the talk (structure and words), a realizer fills in images,
  charts and diagrams, and a renderer draws it. There are three planners: `classic` (v4's templates and
  grammars), `llm` (one streamed LLM call per talk) and `external` (a plan written by Claude through a Skill,
  or later by the visitor's browser).
- **Python picks the structure, the LLM writes the words.** Slide types, their order and their caps come from
  the talk format and a seeded random generator, like v4's weighted picks. The LLM writes the content for that
  skeleton in one pass, which keeps talks coherent and varied and costs one request per talk.
- **Provider-neutral.** A small text-provider interface, with adapters for OpenRouter (the site's free default),
  your own Anthropic or OpenAI key, Sign in with ChatGPT (local CLI), any OpenAI-compatible server (local models),
  and `replay` and `none` for tests and classic mode.
- **Claude as a planner.** An importable Skill, and a local MCP server, let Claude write the talk plan on the
  user's own Claude usage and image keys; `talkgenerator render plan.json` turns it into a deck with licensed,
  credited images.
- **Classic stays.** The v4 algorithm remains the no-LLM default, the per-slide fallback, the deterministic test
  mode and the paper baseline.
- **Design and images.** Themes built from tokens (palettes, font pairs, decoration, image treatments), with the
  extreme ones on by default; layout variants per slide type; native diagrams; image slots with aesthetic
  profiles and license classes; more open sources, and more weird ones like Reddit's memes; AI image generation
  with the user's own keys.
- **Languages.** Dutch, and later other languages, whenever an LLM is available; the classic engine stays English.
- **talkgenerator.com at $0.** LLM talks by default on OpenRouter's free models, with a switch for the classic 2019
  generator, which also takes over when the free quota runs out. Visitors can bring their own OpenRouter account,
  Anthropic key or OpenAI key for more, AI images included.
- **One release.** The work collects milestone by milestone on a long-lived `v5` branch, and ships as one 5.0.0
  once the plan is done; 4.x stays on `master` until then. TED-like talks get every improvement first, and new
  talk formats come after. Once 5.0 ships, 4.x gets no more fixes.

## 2. Goals, constraints and non-goals

### Goals

1. LLM-written talks: topic expansion, per-slide text, coherence across slides.
2. Several ways to bring an LLM: OpenRouter (free tier), your own Anthropic or OpenAI key, Sign in with ChatGPT,
   and Claude itself through an importable Skill.
3. Smarter content without an LLM too: much larger, curated grammars and templates.
4. Talk formats beyond the TED talk: pitch, academic, corporate, keynote and more.
5. Design: themes with randomized fonts and color schemes (extremes included), more layouts, more variety per
   slide type.
6. Images: more sources (weird and flavoured ones like Reddit's memes above all), filters that get a particular
   look per slide and talk type, AI-generated images.
7. talkgenerator.com shows each slide in the browser as soon as it's ready.
8. Talks in Dutch, and later other languages, whenever an LLM is available.

### Constraints

- **$0 for the site** (decided 2026-11-05): free tiers only. AI images only when a visitor brings their own
  account or key.
- **A small server:** talk-generator-web runs on a shared Hetzner box, capped at one CPU core and about 600 MB,
  with one generation slot (see its [README](https://github.com/twinters/talk-generator-web)).
- **4.x keeps working until 5.0:** the site pins `talkgenerator==4.0.x` from PyPI, and 4.x fixes keep shipping
  from `master` until 5.0 is out.
- **A deterministic no-LLM mode** for tests, reproducible seeds, and the paper's method as a runnable baseline.
- **The quality bar** (decided): automated checks at every milestone ([section 14](#14-automated-quality-checks)).

### Non-goals for 5.0

- User accounts, paid features or ads on talkgenerator.com (connecting a provider account is fine).
- Video, animations, transitions and speaker scripts: in PowerPoint karaoke, the presenter shouldn't get a script.
- Training or fine-tuning models, and local GPU inference beyond calling a local OpenAI-compatible server.
- Human or LLM-judged quality ratings (not chosen; section 14 leaves room to add them later).

## 3. Where v4 stands

How a v4 talk is made:

1. [`generator.generate_presentation()`](../talkgenerator/generator.py) picks a schema (`default`, `interview`,
   `ted` or `test`) from [`presentation_schema_types.py`](../talkgenerator/schema/presentation_schema_types.py).
2. [`PresentationSchema`](../talkgenerator/schema/presentation_schema.py) gives each slide a seed word: the topic
   every 3 to 5 slides, related words in between
   ([`SideTrackingTopicGenerator`](../talkgenerator/schema/slide_topic_generators.py), through ConceptNet, with
   Datamuse and WordNet as fallback).
3. Each slide gets a weighted random slide generator ([`slide_schemas.py`](../talkgenerator/schema/slide_schemas.py)).
   The weights depend on the slide's position (`PeakedWeight`: title first, conclusion last), tags cap how often
   a kind of slide appears (`max_allowed_tags`), and repeated content is rejected (`allowed_repeated_elements`).
4. Content generators ([`content_generators.py`](../talkgenerator/schema/content_generators.py)) combine tracery
   grammars, line templates with function pipes (`{seed.plural.title}`) and sources, with weighted mixes and
   backups (`CombinedGenerator`, `BackupGenerator`, `ExternalImageListGenerator`).
5. A [`Slide`](../talkgenerator/slide/slides.py) holds its content as positional arguments. `missing_content()`
   downloads its images and rejects slides with holes, so another slide takes their place.
6. [`powerpoint_slide_creator.py`](../talkgenerator/slide/powerpoint_slide_creator.py) fills the placeholders of
   fixed layouts in `data/powerpoint/template.pptx`.

Worth keeping: the explicit registries, the weighted and capped slide selection (it gives decks their rhythm),
the sources with their caching, cooldowns and credits ([`http_util.py`](../talkgenerator/util/http_util.py),
`ImageData`), the no-holes guarantee, the `DISABLE_<SOURCE>` switches, and the offline test style with fakes.

What holds v5 back:

- **Slides aren't data.** They carry live objects (`ImageData`, python-pptx `ChartData`, chart-modifier
  functions), so `SlideDeck.to_slide_deck_dictionary()` isn't JSON, and nothing but python-pptx can draw a slide.
- **One look.** Layouts and placeholder indices are hard-coded against one template (`LAYOUT_*`, placeholders
  1, 3 and 10 to 16).
- **Seeds aren't reproducible.** All randomness comes from the global `random` module (39 call sites, plus
  tracery's own `random.choice`), reseeded per slide inside a thread pool. With `--parallel` (the default) the
  threads share that state, so the same `--int_seed` can give different decks. Seed 0 also skips the per-slide
  reseeding in parallel mode, since `SlideGeneratorContext.__call__` tests the seed for truthiness.
- **Topic drift needs ConceptNet**, whose public API has been down since late 2025.
- **Little text variety:** about 160 template lines and a handful of grammars, so talks on different topics feel
  alike.
- **All or nothing:** nothing is visible until the whole deck is done, and every image is downloaded and
  embedded first.
- **No accounting** of requests, cost or latency per talk.

## 4. Architecture: plan, realize, render

```
TalkRequest ─▶ Planner ─────────▶ TalkPlan ──────▶ Realizer ────────▶ Deck JSON ───────▶ Renderers
topic, format,   classic           spine and         images, charts,     slides, theme,      .pptx (python-pptx)
slides, seed,    llm               slide plans       diagrams, text,     credits, usage      browser (talk-generator-web)
theme, budget    external                            fallbacks                               thumbnails (LibreOffice, checks)
                 (Skill, browser)
      events, in slide order: talk.started, slide.ready, slide.updated, talk.finished ─────────▶
```

The core types are pydantic v2 models with exported JSON Schemas (the Anthropic and OpenAI SDKs both take
pydantic models for structured outputs):

| Type | Holds |
| --- | --- |
| `TalkRequest` | topics, format, slide count, presenter, title, seed, language, theme, planner and provider, budget, license policy |
| `GenerationContext` | the seeded random streams, the budget and usage ledger, the providers, the elements used so far, the event sink |
| `TalkPlan` | the spine (title, subtitle, thesis, persona, running gag, callbacks) and one `SlidePlan` per slide: type, layout hint, concept, text fields, image slots, chart or diagram spec |
| `Deck` | `deck_version`; metadata (request, seed, planner, model, timings, usage); the resolved theme; slides with positioned elements (text, image, chart, shape, diagram) on a 1920×1080 canvas; credits |

Proposed package layout. v4's `schema/` and `slide/` modules move over step by step, and milestone 1 keeps them
working:

```
talkgenerator/
  api.py        generate_talk(), stream_talk(), render_pptx(); generate_presentation() as a shim
  context.py    GenerationContext, seeded random streams, budget and usage ledger
  models/       TalkRequest, TalkPlan, Deck (and their JSON Schemas)
  plan/         planners (classic, llm, external) and talk formats
  content/      classic text generators and content packs
  images/       slots, aesthetic profiles, the finder (search, filter, score, validate), image generators
  sources/      source modules, old and new, each declaring its license class and display policy
  llm/          provider interface, adapters, prompts, price tables
  design/       themes, palettes, fonts, layouts, text fitting
  render/       pptx renderer (and the classic template), thumbnails
  checks/       automated quality checks and the benchmark runner
  skill/        SKILL.md and its references, for agent mode
```

Python API sketch:

```python
from talkgenerator import TalkRequest, generate_talk, render_pptx, stream_talk

deck = generate_talk(TalkRequest(topic="peanuts", format="pitch", slides=10, seed=42))
render_pptx(deck).save("peanuts.pptx")

for event in stream_talk(TalkRequest(topic="peanuts", llm="openrouter")):
    ...  # talk.started, slide.ready, slide.updated, talk.finished
```

CLI sketch, where today's flags keep working:

```
talkgenerator --topic peanuts                               # as in v4
talkgenerator generate --topic peanuts --format pitch --llm openrouter --theme random -o talk.pptx
talkgenerator generate --topic peanuts -o deck.json         # the deck as JSON
talkgenerator render plan.json -o talk.pptx                 # agent mode: realize and render a plan
talkgenerator schema plan|deck                              # JSON Schemas, for agents and the web app
talkgenerator formats | themes | sources                    # what's available, which keys are set
talkgenerator login openrouter|chatgpt                      # OAuth sign-in for local use
talkgenerator check                                         # automated quality checks (section 14)
```

## 5. LLMs

### 5.1 Where LLMs plug in

| Step | v4 | v5 with an LLM | Fallback |
| --- | --- | --- | --- |
| Topic expansion | ConceptNet walk around the topic | concepts per slide that drift away and come back, chosen with the spine in mind | classic walk (Datamuse, WordNet) |
| Talk spine (new) | none | title, subtitle, thesis, presenter persona, running gag, two or three callbacks | tracery title |
| Slide text | templates and grammars | titles, captions, statements, chart questions and categories, fake facts, about-me lines, conclusions that call back to earlier slides | the classic generator for that field |
| Image queries | the slide's seed word, sometimes with a prefix | a search query (and a generation prompt) per image slot, written for the slot's intent and look | seed-based query |
| Coherence | none: slides are independent | the whole talk in one pass, with callbacks and no repeated jokes | none |
| Picking images (optional) | random among valid candidates | a vision model picks from one contact sheet per talk | local scoring |
| Content packs | hand-written | drafted with an LLM and curated by hand, at build time, never at runtime | |

### 5.2 Python picks the structure, the LLM writes the words

The planner first builds a skeleton with the seeded random generator, the way v4 picks slides: slide types per
position, tag caps, image sources per slot, plus "creative dice" for the prompt (a presenter persona, an angle on
the topic, the seed of a running gag, a few related words from Datamuse). The LLM then writes the content for
that skeleton. Why:

- **Variety.** Current Claude models reject non-default `temperature`, `top_p` and `top_k`, and from API version
  2026-10-21 on every model does. LLMs also drift towards the same jokes. Seeded dice in the prompt take
  temperature's place: another seed gives another prompt and another talk, and the same seed with recorded
  responses gives the same talk.
- **Testable rules.** Format rules (caps, title first, conclusion last) stay in Python, as in v4.
- **Graceful fallback.** The classic engine can fill any slide of the same skeleton when the LLM fails, refuses
  or runs out of quota.
- **One request per talk**, which matters on OpenRouter's free tier: it counts requests, not tokens.

The LLM may flag a slide type that doesn't fit; the planner then swaps it for another allowed type, at most
twice per talk.

The prompt also encodes what makes karaoke decks work: short titles, no paragraphs, odd juxtapositions instead
of explanations, a deadpan expert voice, callbacks, and room for the presenter to justify each slide.

### 5.3 One streamed call per talk

- The prompt has a static part (style guide, slide-type catalog with field limits, output schema: about 2,000 to
  3,000 tokens, cached where the provider supports it) and a small dynamic part (topic, format, skeleton, dice,
  language).
- The model writes the spine first, then the slides in order. Providers with structured outputs (Anthropic,
  OpenAI, some OpenRouter models) get the JSON Schema; the others write JSON Lines, one slide per line. Either
  way, an incremental parser hands over each slide as soon as it's complete, so slide 1 is being realized and
  shown while the model writes slide 2.
- Each slide is validated against its type (fields, lengths, banned strings). An invalid slide falls back to
  classic content for that slide only.
- Regenerating one slide is one small call, with the spine and the neighbouring slides as context.
- The presenter's name never goes to a provider: plans use a `{presenter}` placeholder that's filled in locally.

### 5.4 Provider interface

```python
class TextProvider(Protocol):
    id: str  # "openrouter:<model>", "anthropic:claude-opus-5-5", ...
    capabilities: Capabilities  # structured output, streaming, vision, output limits

    def stream(self, request: TextRequest) -> Iterator[TextChunk]: ...
    def complete(self, request: TextRequest) -> TextResponse: ...  # text or parsed JSON, usage, cost, stop reason
```

| Adapter | Library | For | Notes |
| --- | --- | --- | --- |
| `openrouter` | `openai` SDK, on OpenRouter's OpenAI-compatible API | the site's default (free `:free` models), and anyone with an OpenRouter key or sign-in | free models come and go, so the default is OpenRouter's free router (`openrouter/free`), and models listed after the first are fallbacks; only providers that hold to the schema get the request (`require_parameters`) |
| `anthropic` | `anthropic` SDK | your own Anthropic key | default model `claude-opus-5-5` (configurable); structured outputs, streaming, an explicit `effort`, prompt caching, refusal handling (section 5.5) |
| `openai` | `openai` SDK | your own OpenAI key | Responses API with structured outputs |
| `chatgpt` | `openai` SDK and OAuth | Sign in with ChatGPT, in the local CLI | runs on the user's ChatGPT plan allowance |
| `openai-compatible` | `openai` SDK | other free tiers, local models (Ollama, LM Studio, llama.cpp) | base URL and key from config, capabilities declared there too |
| `replay` | none | tests, and reproducing a talk | recorded responses, keyed by a hash of the request |
| `none` | none | classic mode | |

The SDKs are optional extras: `talkgenerator[anthropic]`, `talkgenerator[openai]` (for OpenRouter, OpenAI,
ChatGPT sign-in and compatible servers) and `talkgenerator[llm]` for both. Without them, v5 works like v4.
Image generators get a sibling interface ([section 10.5](#105-generated-images)).

### 5.5 Provider facts

Checked on 2026-11-05; recheck before building.

**OpenRouter's free models.** Their IDs end in `:free`. The limits are 20 requests a minute, and 50 requests a
day for accounts that have bought less than $10 of credits in total, or 1,000 a day once they have; the account
talkgenerator.com uses has, so the site gets 1,000. Free models get rate limited at peak times and disappear
without notice, and `GET /api/v1/key` shows the limits that apply to a key. Free endpoints can come with looser data policies, so we send only the topic and the skeleton.

**Measured on 2026-11-06**, with one 10-slide talk request each (time to the first visible text, then in all):

| Model (free) | Effort | First text | All | Output tokens | The writing |
| --- | --- | --- | --- | --- | --- |
| `openrouter/free` (picked `dots-3-note-preview` every time) | the model's own | | about 2 minutes, cut off | 11,700 (the limit) | weak: the slides' seed words as titles, before the fields' hints were in the prompt |
| `openrouter/free` (`dots-3-note-preview`) | low | | 95 s | 8,851 | good, once the fields' hints were in the prompt |
| `openrouter/free` (`dots-3-note-preview`) | minimal | 42 s | 49 s (once 160 s, cut off) | 4,378 | good |
| `openrouter/free` (`dots-3-note-preview`, five times) | none | 1 to 6 s | 10 to 15 s | about 650 | good: a running gag, callbacks, concrete image queries |
| `nvidia/nemotron-3.5-super-vl:free` | low | 31 s | 31 s | 4,383 | the best: short and coherent |
| `xingchen-agi/xing4.0-29b-a4b:free` | the model's own | 4 s | 9 s | 688 | ignores the length limits |

So the default is the free router without thinking (effort `none`). Models whose thinking is mandatory
(`stealth/crouton-alpha`, `liquid/lfm-2.5-2.6b:free` on that day) turn `none` down with a 400 ("Reasoning is
mandatory for this endpoint"), and the adapter then asks again at `minimal`. Without thinking, the first slide's
text arrives within seconds, which the web view (milestone 4) needs.

**OpenRouter OAuth (PKCE).** An app sends the user to OpenRouter's auth page with a callback URL (localhost
callbacks work on any port), exchanges the code it gets back at `/api/v1/auth/keys`, and receives a key on the
user's own account, with that account's own free quota or credits. It works for the CLI and for talkgenerator.com.

**Sign in with ChatGPT.** It's live. OpenAI opened ChatGPT plan usage to "open-source projects, personal projects
that run locally, and selected private apps": an OAuth flow with PKCE through the system browser and a
`127.0.0.1` callback, with no client ID to request in advance and no API key, calling the Responses API. Users
need a Plus or Pro plan. Paid or remotely hosted apps, talkgenerator.com included, have to join a waitlist first.
So the CLI can support it in 5.0, and the site has to wait for OpenAI.

**Claude.** First-party prices per million tokens (from the Claude API reference, as cached on 2026-10-06):

| Model | ID | Input | Output |
| --- | --- | --- | --- |
| Claude Opus 5.5 | `claude-opus-5-5` | $4.00 | $20.00 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | $2.00 | $10.00 |
| Claude Haiku 5.5 | `claude-haiku-5-5` | $0.10 | $0.50 (for prompts up to 100K tokens) |

Claude API behaviour the adapter has to respect:

- No sampling parameters (see 5.2).
- Opus 5.5 can't turn thinking off: `effort` is the control, and its default is `medium`. A short creative task
  like this should do well on `low`, to be measured. Haiku 5.5 thinks by default but accepts disabled thinking at
  effort `high` or below; Sonnet 5.5 turns thinking off with `{type: "between_tools"}`.
- Forced `tool_choice` is rejected on Opus 5.5 and Sonnet 5.5, so JSON comes from structured outputs
  (`output_config.format`), not from forced tool calls.
- Responses can stop with `stop_reason: "refusal"`; the adapter opts into server-side fallbacks
  (`fallbacks: "default"`) on the models that support them, and falls back to classic content after that.
- Prompt caching needs at least 512 tokens on current models.
- The Message Batches API halves the price for work that can wait, such as drafting content packs or running
  the benchmark.

### 5.6 What a talk costs

A 10-slide talk as one call, at about 3,000 input and 2,500 output tokens with thinking included (rough figures):

| Route | Per talk | Paid by |
| --- | --- | --- |
| Classic (no LLM) | $0 | nobody |
| OpenRouter `:free` | $0, one request from the daily quota | nobody |
| Claude Haiku 5.5 | about $0.0015 | the key's owner |
| Claude Sonnet 5.5 | about $0.03 | the key's owner |
| Claude Opus 5.5 | about $0.06 | the key's owner |
| Sign in with ChatGPT | part of the user's plan allowance | the user |
| Agent mode (Claude Skill) | part of the user's Claude usage | the user |

A 20-slide talk roughly doubles the output. Generated images cost far more than text: about $0.006 to $0.04 per
image ([section 10.5](#105-generated-images)).

### 5.7 Keys, tokens and logs

- Settings follow v4's environment variables: `TALKGENERATOR_LLM` (such as `openrouter:<model>:free` or
  `anthropic:claude-opus-5-5`), `TALKGENERATOR_LLM_FALLBACKS`, `TALKGENERATOR_LLM_EFFORT`, `OPENROUTER_API_KEY`,
  `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `DISABLE_LLM=1` next to the existing `DISABLE_<SOURCE>` switches.
  (Built so far: all but `TALKGENERATOR_LLM_FALLBACKS`; OpenRouter's fallbacks go in its spec, as
  `openrouter:<model>,<fallback>`.)
- `talkgenerator login openrouter|chatgpt` keeps OAuth tokens in the user's config folder (through platformdirs,
  readable only by the user), or in the OS keyring when available.
- Keys and tokens never end up in logs, the HTTP cache, deck JSON or error messages: `http_util.redact` gets
  extended, with tests.

### 5.8 Text safety

- The topic gets screened first, against a local blocklist and through an `unsafe_topic` flag the plan has to
  fill in. Flagged topics get a polite refusal on the site, or a classic talk on a safe topic.
- Prompt rules: no slurs, sexual content or harassment; no made-up quotes attributed to real people (real quotes
  keep coming from Goodreads and Wikiquote, and LLM-written quotes get fictional authors, like v4's invented
  historical names); nothing about real private persons.
- Refusals (Claude's `stop_reason: "refusal"`, content-filter finish reasons elsewhere) fall back to classic
  content for the affected slides, never to an error page.
- The final text goes through the same blocklist the checks use.

### 5.9 Languages

Built on 2026-11-06: `talkgenerator.plan.languages` has what talkgenerator writes itself in en, nl, fr, de, es, it
and pt (the title slide's "By ...", a chart's "Yes" and "No"); a slide of a non-English talk that doesn't come
out becomes a full-screen picture of its concept, without text, rather than an English classic slide (or is left
out, in a format without such pictures); recipes with `texts_from` (real quotes, which are English) are left
out of non-English talks; decks have a `language`; and `check_language` reads a deck's texts with NLTK's
stopwords (only the words that tell the language and English apart), flagging slides and talks that read as
English. Dutch Wikipedia and Wikiquote as sources are still to do.

Decided: talks in Dutch, and later other languages, whenever an LLM is available. The classic engine and its
grammars stay English: translating them would mean keeping parallel grammars in step for every language, a lot of
upkeep for a mode that only matters when no LLM is around.

- `TalkRequest.language` defaults to `en`. For another language, the LLM writes the talk in that language
  directly instead of translating English output, so the wordplay works. Image search queries stay English, which
  the stock sources handle best.
- Without an LLM (none configured, the quota used up, or a failure), a non-English request falls back to a
  classic English talk and says so.
- Sources that speak the language join in: Dutch Wikipedia and Wikiquote, Dutch-language meme subreddits.
  Datamuse only knows English, so in other languages the LLM picks the related concepts too.
- Safety per language: a Dutch blocklist next to the English one, and the provider's own moderation.
- The checks verify the output language with NLTK's stopword lists, which include Dutch (one small extra NLTK
  download, no new dependency).
- On talkgenerator.com, the site's free OpenRouter quota counts as an available LLM (decided); once it runs out, a
  Dutch request gets a classic English talk with a notice.

## 6. Agent mode: talkgenerator as a Claude Skill

Claude can be the planner, on the user's own Claude usage (in Claude Code, Claude Desktop or claude.ai), while
talkgenerator does what an agent shouldn't improvise: finding licensed images, crediting them, laying out and
rendering the deck.

- The library publishes what Claude needs: `talkgenerator schema plan` (the TalkPlan JSON Schema) and
  `talkgenerator formats --details` (formats, slide types, field limits, examples).
- `talkgenerator render plan.json -o talk.pptx` validates the plan, realizes it with the user's image keys from
  `.env` (or with the keyless sources), renders it, and prints a short JSON report: slides, images used,
  fallbacks, warnings. Claude reads the report, fixes the plan and renders again. `render plans/*.json` does a
  batch, say 20 talks from tonight's audience suggestions.
- Plans carry intents, search queries and generation prompts, never image URLs, so licensing, credits and
  filters stay in the library. Local image paths are allowed, for the user's own pictures.
- `skill/` holds `SKILL.md` (when to use it, the workflow, what makes a good karaoke deck, safety rules) and its
  references (format guides, the slide-type catalog, example plans). It can be installed as a Claude Code plugin
  straight from this repository, copied into `~/.claude/skills/`, or uploaded to claude.ai as a zip. To verify
  for claude.ai: whether its code-execution sandbox can install talkgenerator and reach the image APIs. If it
  can't, claude.ai can only draft plans, and Claude Code is the main target.
- `talkgenerator mcp`, decided to be local only: an MCP server with tools such as `list_formats`, `find_images`
  and `render_talk`, for Claude Desktop and other MCP clients. The client starts it on the user's own computer
  (over stdio) with the user's own keys, so its requests never touch talkgenerator.com or our keys, and there's
  nothing of ours to exploit or overload. We don't host an MCP endpoint: that would put our server, our OpenRouter
  quota and our Unsplash allowance within reach of every MCP client, which a $0 site can't police.
- Keys: the Skill encourages users to get their own free keys (Unsplash, Pexels, Pixabay, GIPHY, Reddit), walks
  them through setting up `.env`, and still works without any, with fewer sources. Neither the package nor the
  Skill ever ships our keys.
- Why both, and which comes first: the Skill carries the know-how (what makes a good karaoke plan, the formats,
  examples, the render-and-fix loop) and runs the CLI wherever Claude has a shell, as in Claude Code. It only
  enters the conversation when it's needed, and it installs as a plugin. The MCP server offers the same functions
  as typed tools to apps that have no shell or aren't Claude, such as Claude Desktop's chat and other MCP clients,
  and writes the deck straight onto the user's disk. Its tool descriptions sit in every conversation where it's
  enabled, and installing it means a config entry or a one-click Claude Desktop extension bundle (to check). Both
  wrap the same `render` functions, so the Skill comes first (milestone 2) and the MCP server is a thin layer on
  top (milestone 3).
- The same plan-in, deck-out path can later let talkgenerator.com accept plans written in the visitor's browser
  with the visitor's own key, so that key never reaches the server.

Built on 2026-11-06: `talkgenerator schema plan|deck`, `talkgenerator formats [--details] [--json]` (the formats
are the presentation schemas for now) and `talkgenerator render`, whose report gives every planned slide's outcome
(`as planned`, `classic` or `left out`), its problems and warnings. A slide's recipe is one of the format's slide
generators, by an id made from its name (`two-captions-gifs`); a kind without a recipe in the plan gets a default,
and a format without that default borrows its copyright-free version. The Skill lives in
`skill/skills/talkgenerator/` (SKILL.md, the slide reference that `formats --details` generates, which a test keeps
up to date, and an example plan); `skill/` is a Claude Code plugin, which `.claude-plugin/marketplace.json` at the
repository's root lists, so `/plugin marketplace add twinters/talk-generator` installs it. For claude.ai: its
sandbox most likely can't install talkgenerator or reach the image APIs (Anthropic's docs say the API's code
execution has no internet access, and say nothing about claude.ai's), so there the Skill writes plans for the user
to render; the SKILL.md frontmatter keeps to the fields claude.ai accepts.

Built on 2026-11-06 as well: `talkgenerator mcp` (`talkgenerator/mcp_server.py`, on the official MCP SDK, 2.3.0, as
the `mcp` extra), with the tools `list_formats`, `describe_format`, `get_plan_schema`, `render_plan` and
`generate_talk`. There's no `find_images`: a plan's queries are searched when it's rendered, and the report says what
they found. The tools save only in the output folder (`--output_folder`, by default a `talkgenerator` folder in the
user's documents, as clients start servers in folders of their own), make one talk at a time, and send a progress
notification every 5 seconds, for clients that keep waiting while they hear from a tool. `generate_talk` takes its
language model from the settings only, so a tool call can't make a paid model write. The SDK needs `cryptography`,
which has had no Windows on Arm wheels since 46.0.4: the dev dependencies leave the SDK out there (the MCP tests
skip, and run in an x64 Python), and users on Windows on Arm install it in an x64 Python. Still to check: a
one-click Claude Desktop extension bundle (`.mcpb`), and how long Claude Desktop waits for a tool.

## 7. Talk formats

A talk format describes a kind of talk: a description (which doubles as the LLM's brief), an arc of sections
with slide-count ranges and allowed slide types, title grammars, tone and vocabulary, preferred theme families
and image looks, optional timing, and tag caps. v4's schemas become formats: `default` becomes `ted`; v4's `ted`
schema (only copyright-free images) becomes `ted` with the `open` license policy
([section 10.2](#102-license-classes)); `interview` stays.

| Format | Arc | Signature slides | Look |
| --- | --- | --- | --- |
| TED talk (exists) | hook, personal story, history, insight, conclusion | about me, history, bold statement, quote, conclusions | clean keynote |
| Interview (exists) | like the TED talk, without about-me slides | | |
| Startup pitch | problem, solution, market, traction, team, competition, the ask | big number, hockey-stick chart, 2×2 competitor matrix, team grid | startup gradients |
| Academic talk or PhD defense | outline, related work, method, results, limitations, future work, questions | diagrams, result charts and tables, an equation, "Questions?" | beamer-like, serif |
| Corporate all-hands | agenda, KPIs, org chart, roadmap, synergies, Q&A | KPI tiles, timeline, org chart, stock photos | corporate blue |
| Product keynote | teaser, the product, features, "one more thing" | full-bleed photos, huge type | dark minimal |
| School lecture | learning goals, facts, quiz, summary | quiz, map, timeline, did-you-know | bright and rounded |
| Travel slideshow | itinerary, photos, mishaps | photo grids, maps, flags | polaroids |
| Museum tour | artworks, artists, eras | public domain art | gallery white |
| Nature documentary | habitat, behaviour, threats | wildlife photos | dark, cinematic |
| Safety briefing | rules, do's and don'ts, quiz | icon grids, warning signs | yellow and black |
| Motivational seminar | struggle, epiphany, method, testimonials | quotes, sunsets, staircase diagram | sunrise gradients |

Timing variants work with any format: Pecha Kucha (20 slides of 20 seconds) and Ignite (20 slides of 15 seconds),
with auto-advance in the browser view.

Decided: TED-like talks get every improvement first, and the new formats come after them: in milestone 7, or in
5.1 if the TED work takes longer. The format machinery itself exists from milestone 2, since the TED talk is a
format too. Every format also works in classic mode through its content pack
([section 11](#11-text-sources-and-content-packs)), so formats cost nothing without an LLM.

## 8. Slide types and variety

v4's slide types stay: title, about me, history, full-screen gif, meme or photo, image with title, large quote over
a photo, InspiroBot, bold statement, anecdote, two and three captions, charts, Reddit chart and conclusions.
Candidates for new ones:

- **Structure:** agenda, section divider, "Questions?", a fake contact or thank-you slide.
- **Native diagrams**, drawn as shapes so they look the same in PowerPoint and in the browser and need no image
  source: timeline, 2×2 matrix, Venn diagram, process with a "???" step, pyramid, funnel, iceberg, cycle, a small
  org chart. Two came early, in milestone 2: Venn diagrams (two or three see-through circles, the punchline where
  they overlap) and 2×2 matrices (a named dot as the punchline), whose punchline appears on a click.
- **Numbers:** big number, KPI tiles, comparison table, and more kinds of charts with written labels (bar, line,
  stacked, gauge). Two came early, in milestone 2: trends (a line along two odd axes, going one of eleven ways,
  with an optional second line that wipes in on a click as the punchline) and rankings (bars that the last one
  wins by far); and charts with axes got axis titles.
- **Media:** meme (a template image with the caption as live text), social media post mockup, news headline,
  book cover, photo grid or polaroid collage, product shot.
- **Audience:** quiz (a question slide, then the answer), poll ("raise your hand if..."), challenge ("turn to your
  neighbour and..."). These play well in karaoke.
- **Academic:** equation, code snippet, results table.

Variety per slide type comes from four axes, each sampled per slide with the talk's random generator:

1. layout: image left or right, full-bleed, framed, split, grid;
2. text: grammar or LLM variants, casing, length;
3. images: the source mix and the look ([section 10.3](#103-aesthetic-profiles-and-smart-filters));
4. decoration: theme accents, frames, stickers, filters.

The rules: never the same layout twice in a row, v4's tag caps per talk, a cap per variant, and on the site an
optional memory of recently shown quotes and images, so popular topics don't keep getting the same quote.

## 9. Themes, layouts and design quality

- **Layouts** are geometry only: named boxes (title, body, image_1, chart, credits and so on) on the 1920×1080
  canvas, with safe margins and text roles.
- **Themes** are design tokens: a palette (background, surface, text, muted, accents), a font pair with its scale,
  weight and casing, a background (solid, gradient, pattern, photo, noise), decoration (accent bars, rounded
  corners, borders, shadows, stickers), image treatment (cover or contain, frame, filter), and the chart and
  credit styles.
- **Families**, each with random members: clean keynote, corporate, academic, startup, vintage paper, kids, dark
  minimal, brutalist, neon. And extremes for laughs: "1997 WordArt", "Comic Sans everywhere", "clip-art
  corporate", and "chaos", where every slide gets its own theme. A `style_chaos` setting goes from one consistent
  theme (0) to a new theme per slide (1). Extreme themes are on by default (decided), since explaining a
  ridiculous deck is half the fun; a switch leaves them out for serious occasions.
- **Procedural themes:** a base hue from the seed, a harmony rule per family (analogous, complementary,
  triadic), lightness limits, and a contrast check (WCAG: at least 4.5:1 for body text, 3:1 for titles) that
  repairs failing colors. Font pairs come from a curated list per family.
- **Fonts:** a .pptx names its fonts, and the computer showing it needs to have them. So pptx themes stick to
  widely installed fonts (Arial, Calibri, Georgia, Verdana, Trebuchet MS, Impact, Comic Sans MS, Courier New,
  Times New Roman...), and the browser view maps each one to a web font. Text gets measured with bundled open
  fonts that share the main fonts' metrics (Liberation Sans, Serif and Mono for Arial, Times New Roman and
  Courier New; Carlito for Calibri; Caladea for Cambria; Gelasio for Georgia), with a safety margin for fonts
  without such a twin, so font sizes are picked deterministically and text doesn't overflow. PowerPoint's
  shrink-on-overflow stays on as a safety net.
- **Rendering:** the pptx renderer draws shapes (text boxes, pictures, shapes, charts) on a blank slide instead
  of filling the template's placeholders. v4's `template.pptx` lives on as the `classic` theme, for the paper
  baseline and for anyone who likes the old look.
- **Image treatments** give images from mixed sources one look: grayscale, sepia, duotone in the theme's colors,
  grain, vignette, rounded or polaroid frames. Pillow applies them for pptx; the browser view uses CSS filters,
  at no cost to the server.
- **Design rules**, all checked automatically ([section 14](#14-automated-quality-checks)): no overflow, minimum
  font sizes, contrast, safe margins, no image enlarged beyond about 1.3× its size, small but legible credits.
- Later: bring-your-own .pptx templates, such as corporate master slides.

## 10. Images: sources, aesthetics and generation

### 10.1 Image slots

Every image in a plan is a slot, not a call to a source:
`{intent, queries, orientation, min_pixels, text_area, aesthetic, license_classes, sources}`. An image finder
searches the sources in parallel (with v4's cache and cooldowns), filters the candidates (license, size,
orientation, metadata, prohibited and duplicate images), scores them (fit with the slot's look, local image
analysis, optionally a vision model), validates the winner (download or probe), and picks with the talk's random
generator. v4's weighted mixes of sources become source weights per aesthetic profile.

### 10.2 License classes

They generalize v4's separate groups of copyright-free slide generators:

| Class | What |
| --- | --- |
| `public-domain` | public domain and CC0 |
| `open` | CC BY and CC BY-SA |
| `stock` | the Unsplash, Pexels and Pixabay licenses |
| `generated` | AI images, under the provider's terms |
| `fair-use` | Reddit, GIPHY, meme templates, InspiroBot, ShitpostBot |

A talk's license policy picks the classes it allows: `open` (v4's `ted` schema) allows everything except
`fair-use`, and the default allows all of them. `ImageData` gains a `license` and a `license_url`, and the credits
on the slides show them.

### 10.3 Aesthetic profiles and smart filters

A profile is a named look, attached to formats and slide types:

| Profile | Sources | Filters and treatment |
| --- | --- | --- |
| `vintage` | Wikimedia Commons, Library of Congress, museum archives | grayscale or sepia, preferred or applied; "old photograph" queries |
| `corporate-stock` | Pexels, Unsplash, Pixabay | "business, office" modifiers; blue and teal color filters |
| `museum` | Art Institute of Chicago, the Met, Cleveland, Rijksmuseum | date and classification filters |
| `space-science` | NASA, ESA | |
| `meme-chaos` | Reddit, GIPHY, Imgflip templates, InspiroBot | |
| `calm-backdrop` | stock sources | for text over a photo: little detail where the text goes, darker or blurred |
| `illustration` | Openverse, Pixabay illustrations, icon sets | |

Weird content gets profiles too, as flavour packs: curated sets of subreddits and other sources per mood, such
as `cursed` (cursed and blursed images, "hmmm"), `wholesome` (wholesome memes, animals with jobs),
`corporate-cringe` (LinkedIn-style posts, how-do-you-do-fellow-kids marketing), `bad-charts` (badly made and
funny charts), `liminal` (empty, eerie spaces), `retro-futurism`, `medieval` (weird medieval art),
`accidental-art` (accidental Renaissance paintings, symmetrical Wes Anderson-like scenes) and `pareidolia` (faces
in things). Slide types and formats ask for flavours, and v4's NSFW filter stays on.

Filters, cheapest first:

1. **API parameters:** Unsplash `color` and `orientation`; Pexels `color`, `orientation` and `size`; Pixabay
   `colors`, `image_type` and `orientation`; Openverse `category`, `aspect_ratio` and `license`; the museums'
   date and classification filters.
2. **Query modifiers** per profile, or queries the LLM writes per slot.
3. **Local analysis with Pillow** on thumbnails: dominant colors against the theme's palette, brightness,
   saturation, grayscale, edge density where the text will go, aspect ratio, resolution, and a perceptual hash
   against the images already in the talk.
4. **A vision pick** (optional): one contact sheet with numbered thumbnails for all slots of a talk, sent to a
   vision model that returns its picks. That's one request per talk, so it fits a free tier; off on the site until
   measured.
5. **Post-processing** to the theme: filters, crops, duotone.

### 10.4 More image sources

Candidates, each to be checked for terms and rate limits before it gets added:

| Source | Key | License | Good for |
| --- | --- | --- | --- |
| The Met Collection API | none | CC0 (Open Access images) | art, history |
| Cleveland Museum of Art | none | CC0 | art |
| Smithsonian Open Access | free api.data.gov key | CC0 | history, science, objects |
| Rijksmuseum | to check (its API changed) | CC0 for public domain works | Dutch masters, history |
| Europeana | free key | per item | European heritage |
| Library of Congress | none | per item, much of it public domain | vintage photos, posters, maps |
| Wellcome Collection | none | mostly CC BY or public domain | medicine, science, odd history |
| NASA Image and Video Library | none | generally public domain | space, science |
| Flickr (Commons and CC search) | key | per photo | vintage, everyday life |
| Iconify | none | per icon set (MIT, Apache, CC BY...) | icon grids, diagrams |
| Flag images | none | generally public domain | about me, travel |
| Imgflip meme templates | none (to list templates) | fair use | memes with live captions |

Reddit stays one of the best sources (decided), and the hunt is on for more like it. Weird and flavoured
candidates, each with its terms still to check:

- more subreddits, grouped into the flavour packs above, plus Dutch-language ones for Dutch talks;
- GIPHY stickers (transparent animated stickers, for decoration and absurd overlays), with the existing GIPHY key;
- Flickr Commons' big public domain uploads: the British Library's and the Internet Archive's millions of old
  book illustrations, which are odd and free to use;
- the Wellcome Collection and NYPL Digital Collections, for strange historical imagery;
- Openclipart (CC0 clip art, for the "clip-art corporate" theme; check that it's up);
- Imgflip's meme templates (in the table above), captioned by the LLM or the grammars.

They join the existing Unsplash, Pexels, Pixabay, Openverse, Wikimedia Commons, Art Institute of Chicago,
Reddit, GIPHY, InspiroBot and ShitpostBot. Each source declares its license class, its display policy in the
browser ([section 13.1](#131-streaming-slides-into-the-browser)) and the filters it supports.

### 10.5 Generated images

- **Interface:** an `ImageGenerator` takes a prompt, a size or aspect ratio, a style and a seed (where supported)
  and returns the image with its model, cost and safety flags. Adapters for OpenRouter's image models, OpenAI,
  Google's Gemini image models and Black Forest Labs' FLUX models, plus a local adapter for ComfyUI or
  Automatic1111-style servers, free for anyone with a GPU.
- **When to generate:** for slots stock search can't deliver: an absurd hobby, a fake book cover, a product shot
  for a pitch, a "historical photo" of an event that never happened. Or as a fallback when search comes up empty.
  A per-talk limit (a few images by default) and, for paid keys, a cost estimate before generating.
- **Cost:** pricing trackers (August to October 2026) put it at about $0.006 per image for OpenAI's gpt-image-2
  at low quality, $0.014 for FLUX.2 klein, $0.03 for FLUX.2 pro, and $0.039 or more for Google's Gemini image
  models. To check on the providers' own pages before building. Several older image models were retired in 2026,
  so model IDs belong in config, not in code.
- **Latency:** seconds to tens of seconds per image, so images are generated in parallel. In the browser, a slide
  can appear with a placeholder or a stock image and receive its generated image in a `slide.updated` event; the
  .pptx gets built once all images are in.
- **Licensing:** provider terms generally give the user the output (to check per provider). Generated images are
  credited as "AI-generated with <model>", in the `generated` class.
- **Safety:** the provider's moderation, plus our own rules (no real, identifiable people, no logos or
  trademarked characters, no gore or sexual content) and the topic screening. A refused prompt gets a stock image.
- **Caching:** generated images are cached on disk by model, prompt, size and seed, so rendering a deck again
  never generates anything again.
- **On talkgenerator.com** (decided): only on the visitor's own account or key, never on the site's budget.

## 11. Text sources and content packs

- **Kept:** Datamuse, WordNet, Goodreads, Wikiquote, WikiHow (brittle, and off on the site), InspiroBot.
- **ConceptNet** becomes optional (the public API has been down since late 2025). The LLM planner takes over
  topic drift; in classic mode, Datamuse and WordNet keep doing it.
- **New, keyless candidates:** Wikipedia's REST API (summaries, and "on this day" for history slides), Wikidata
  (dates, places and people, for timelines, maps and "true fact, absurd twist" slides), Open Trivia DB (quiz
  slides) and REST Countries (about-me and travel facts). Terms to check for each.
- **Weird text, for flavour:** random useless facts (for did-you-know slides), dad jokes, advice slips. Small free
  APIs, each to check for terms and uptime, and always optional.
- **Grounding:** in LLM mode, a few retrieved facts (a Wikipedia summary, some dates) go into the prompt, so
  history and did-you-know slides mix real facts with nonsense. That's funnier, and less made up.
- **Content packs:** the classic grammars and templates become versioned data per format and slide type
  (`content/packs/<format>/`). We grow them a lot with LLM help at build time (drafted in Claude Code or through
  the Batch API, then curated by hand), and tests lint them: every template formats with the known variables,
  fields respect their length limits, nothing hits the blocklist, and there are no duplicates. This makes the
  free classic mode better for everyone, and costs nothing at runtime.

## 12. Determinism, seeds, tests and the paper baseline

- **The classic engine** is v4's algorithm on the new data model. It's the default when no LLM is configured,
  the per-slide fallback, and the paper baseline: `--planner classic --theme classic` is the 2019 method with the
  2019 look.
- **Seeds:** one `random.Random(seed)` per talk, with streams derived per slide and purpose (for instance
  `rng.child("slide", 3, "images")`, derived by hashing), so results don't depend on thread scheduling. There are
  no module-level `random` calls anymore: the 39 current call sites take the context's generator, tracery's
  `random.choice` gets wrapped (or replaced by a small expander of our own), and a lint rule keeps new ones out.
  That fixes the parallel-mode race and the skipped reseeding for seed 0.
- **Replay:** the `replay` provider and recorded HTTP fixtures make the same seed give a byte-identical deck JSON,
  offline. Golden deck files per format; renderer tests on normalized pptx XML; PNG thumbnails through headless
  LibreOffice for the contact sheet.
- **What stays non-deterministic:** live APIs and live LLM calls. A saved deck JSON is the reproducible artifact:
  rendering it again gives the same .pptx.
- **Test layers:** offline unit tests (as now), offline end-to-end tests with replay, and the existing weekly
  network canary, extended with an OpenRouter free-model smoke test (at $0). That test also reports which free
  models still exist and still write valid plans, so the site's model list can change without a release.

## 13. talkgenerator.com: streaming, $0 operation and limits

### 13.1 Streaming slides into the browser

- **The library:** `stream_talk()` yields `talk.started` (title, theme, slide count), `slide.ready` (index and
  slide JSON), `slide.updated` (images that came in late) and `talk.finished` (credits, usage, fallbacks). Slides
  arrive in order, and later slides get prepared in parallel.
- **talk-generator-web**, on a branch of its own: `POST /api/talks` returns an id; `GET /api/talks/<id>/events`
  streams Server-Sent Events (with nginx's buffering off); `GET /api/talks/<id>` returns the deck JSON as a
  permalink, kept for 7 days like today's outputs; `GET /api/talks/<id>.pptx` renders the .pptx on demand.
- **The Angular renderer** places the elements from the deck JSON on a 16:9 stage (canvas units become
  percentages), turns the theme tokens into CSS variables, loads the theme's web fonts, and has a presenter mode:
  fullscreen, keyboard or clicker, auto-advance for Pecha Kucha, and a download button.
- **Images in the browser** (decided): the browser loads each image from its source, and the server caches no
  images. Unsplash requires this anyway (it's also what its production review looks for), and Wikimedia and
  GIPHY allow it. Sources that can't be loaded that way either go through a pass-through proxy that stores
  nothing, or stay out of the web view: the Art Institute of Chicago, whose image server refused our requests
  without an `AIC-User-Agent` header that an `<img>` tag can't send (see `http_util.py`; to test from a browser),
  and Pixabay, whose API terms ask not to hotlink images permanently (to verify). Each source declares its display
  policy, and the deck JSON carries it.
- **Lighter validation:** while streaming, an image gets checked with a probe (its headers and first bytes, for
  type and size) instead of a full download, which saves memory on the 600 MB box. The .pptx is only built when
  someone downloads it, and it's kept no longer than today's outputs (7 days).
- **Privacy:** hotlinked images let those services see visitors' IP addresses, which the site's privacy page
  should mention.
- **Concurrency:** LLM calls mostly wait, so the single slot can become several streams that share a few image
  workers (gunicorn threads), once memory use has been measured.
- **A preview deployment** (on a subdomain) runs `v5`, installed from git by commit, while production stays on
  4.0.x: no release is needed for that.

### 13.2 Running at $0

- **Text:** LLM talks by default (decided), on OpenRouter's free models with an ordered fallback list: one request
  per talk and one per regenerated slide. With the $10 of credits on the account, that's up to 1,000 requests a
  day, and at most 20 a minute. A visible switch picks the classic 2019 generator instead.
- **When the quota or the rate limit runs out, or a model fails,** the classic engine takes over without fuss
  (the page says "classic mode"). There's never a paid fallback on the site's key.
- **Fair sharing:** per-visitor caps (a few LLM talks per hour per IP address or session; classic talks as
  today), nginx `limit_req` on the API, quota counters in a small SQLite file, and Cloudflare Turnstile only if
  bots show up.
- **Images:** stock and open sources, as now (Unsplash stays at 50 requests an hour until its production review
  passes), and no AI images on the site's budget.
- **Upgrades paid by the visitor** (decided: all of them): "Connect OpenRouter" (OAuth PKCE: the visitor's own
  free quota or credits, and their choice of model, image models included); an Anthropic or OpenAI key for one
  talk (sent over HTTPS with that request, used once, never stored or logged); and Sign in with ChatGPT once
  OpenAI admits the site, through the interest form linked from
  [OpenAI's Sign in with ChatGPT docs](https://developers.openai.com/siwc).
- **Switches:** `DISABLE_LLM=1`, `DISABLE_IMAGE_GENERATION=1`, and `DISABLE_<PROVIDER>=1` per provider.
- **Visibility:** one usage line per talk in the logs (requests, tokens, estimated cost, which must stay $0 on the
  site's own key, fallbacks taken, time to first slide), and a daily summary.

## 14. Automated quality checks

Decided: automated checks at every milestone, offline in CI wherever possible. They run on a fixed benchmark of
about 50 topics (common nouns, rare words, phrases, names, plurals, and a few edgy topics for the safety checks) ×
the formats × 3 seeds, in classic mode with replay and, at every milestone, live on OpenRouter's free models
(at $0).

| Area | Check | Proposed bar |
| --- | --- | --- |
| Completeness | no missing slides, every required element present, no empty placeholders | 100% |
| Text | no template leftovers (`{seed}`, `#tag#`, `None`); fits its box at the minimum font size or above; within its length limits | 100% |
| Contrast | text against its background, or against the photo behind it after dimming | at least 4.5:1 for body text, 3:1 for titles |
| Images | loads; not enlarged beyond 1.3×; no near-duplicates within a talk; credited with its license; license policy respected | 100% |
| Variety | distinct slide types and layouts per talk, no layout twice in a row; across seeds, the share of distinct titles and images | targets per format, set from milestone 1's measurements |
| Image fit | of the images searched for with a query whose source describes them (alt texts, post titles), the share that shares a word with its query (`talkgenerator check` counts them since milestone 2) | a rough signal to follow, without a bar |
| Determinism | the same seed with replay gives an identical deck JSON; serial equals parallel | 100% |
| Safety | blocklist hits in the output; edgy topics screened or falling back | no hits |
| Language | the text is in the requested language (stopword ratio) | every slide |
| Speed | time to first slide and total time, on the site's configuration | targets to calibrate in milestones 1 and 4 |
| Requests and cost | LLM requests and estimated cost per talk | on the site's configuration: $0, at most one request per talk |
| Memory | peak memory for a 20-slide talk on the site's configuration | under 450 MB |

Each run writes a JSON report, compared with the previous milestone's, and an HTML contact sheet of thumbnails
for a quick look. These checks catch broken, cramped, unreadable and repetitive decks; they can't tell whether a
deck is funny. Human or LLM-judged ratings are out of scope for now, and could later run on the same benchmark.

## 15. Branches, releases and compatibility

- **Branches:** a long-lived `v5` branch from `master`, created once this plan is approved; feature branches go
  into `v5` through pull requests. Until then `master` stays on 4.x: fixes land there first, and `master` gets
  merged into `v5` regularly. At 5.0.0, `v5` merges into `master` and 4.x is done (decided): no more 4.x fixes,
  though its releases and tags stay available.
- **One release** (decided 2026-11-05): no pre-releases. `v5` collects the work milestone by milestone, and
  5.0.0 ships once, when the plan is done. Until then `pip install talkgenerator` and the site's
  `talkgenerator==4.0.x` pin stay on 4.x, and the changelog's `[Unreleased]` section collects what 5.0.0 brings.
- **Release tooling:** 5.0.0 is released from `master` once `v5` has merged into it, which the release script and
  workflow already handle (an X.Y.Z version, released from `master`). Pull requests into `v5` already run CI;
  adding `v5` to CI's push branches would check direct pushes too.
- **Trying v5 out before 5.0.0:** install it from the branch (`pip install git+https://github.com/twinters/talk-generator@v5`,
  or a commit), which is also how a preview deployment of talkgenerator.com runs it (section 13.1).
- **Compatibility:** `generator.generate_presentation()` stays as a shim, with a deprecation warning, throughout
  5.x (the site calls it). `--schema default|ted|interview|test` maps to formats and license policies.
  `SlideDeck.to_slide_deck_dictionary()` gives way to deck JSON, a breaking change for the changelog. Python 3.11
  or newer, as now.
- **The paper:** the citation stays, and the README documents the classic engine as the paper's method.

## 16. Milestones

Milestones in the agreed order: LLM talks and the Skill right after the groundwork, and every TED-like improvement
before the new formats. A milestone is a checkpoint on `v5`, not a release; only 5.0.0 ships.

| Milestone | Focus | Contents | Done when |
| --- | --- | --- | --- |
| 1 (done, 2026-11-05) | Groundwork | deck JSON and the models; pptx renderer from deck JSON (classic look); seeded random streams (`random_util`), with parallel generation giving the one-by-one talk; the classic engine on the new model; `--save_json`; usage ledger and budgets; `replay` and `none` providers; `talkgenerator check` for completeness, template leftovers and determinism | classic talks look like v4's; the same seed gives the same deck, serial or parallel; v4's offline tests pass |
| 2 (under way: the TalkPlan schema, the planner, the `openrouter`, `anthropic`, `openai` and `chatgpt` adapters, `render`, `schema`, `formats`, the Skill, languages with their check, `login openrouter` and `login chatgpt`, and trend and ranking charts are in; on 2026-11-06, 30 benchmark talks by the free models had 0 errors, one request each, at $0, and 290 of 300 slides by the model) | LLM TED talks and the Claude Skill | TalkPlan schema; the LLM planner (one streamed call, dice, per-slide fallback, safety); `openrouter`, `anthropic` and `openai` adapters; languages, Dutch first; `render plan.json`, `schema`, `formats`; `skill/` with SKILL.md; `login openrouter`; the `chatgpt` adapter (may slip to milestone 3); checks for requests, cost, speed and language | on the benchmark with OpenRouter's free models: no holes, no leftovers, $0 and one request per talk; Dutch talks pass the language check; Claude Code makes a deck end to end with the Skill |
| 3 (under way: theme families and extremes, procedural palettes with contrast repair, layouts and their variants (never twice in a row), image treatments, WordArt-style heading effects, text fitting with bundled metric twins, the shapes renderer with the classic animations (columns click by click), previews, the design checks and the local MCP server are in) | Themes and layouts | theme tokens and families, extremes on by default; procedural palettes and font pairs; layout variants; text fitting; image treatments; the `classic` theme; thumbnails and contact sheet in CI; the local MCP server | contrast and overflow checks pass on every theme |
| 4 | Streaming and the web view | `stream_talk()`, display policies, probe validation; in talk-generator-web: the SSE endpoint, the Angular renderer, LLM talks by default with the classic switch, a language choice, Connect OpenRouter and pasted keys, .pptx on download, a preview deployment that installs `v5` from git | first slide on screen within the calibrated target on the VPS; a 20-slide talk under the memory bar; the downloaded .pptx matches the web view |
| 5 | Images | slots, aesthetic profiles and flavour packs, local analysis, license classes; new open and weird sources; AI image generation with the user's own keys; the optional vision pick | license policies enforced; profile checks pass (such as the grayscale share for `vintage`); generated images credited |
| 6 | More slide types for TED-like talks | native diagrams, big numbers, quiz, memes with live captions, social posts and more; a much larger, curated TED content pack | every new slide type passes the checks in classic and LLM mode |
| 7 | New talk formats | pitch, academic, corporate, keynote and Pecha Kucha timing, with their content packs (or in 5.1 if the TED work takes longer) | every format works in classic and LLM mode and passes the checks |
| 8 | Integration | the site runs `v5` on the preview, then in production behind a switch; Sign in with ChatGPT on the site, if OpenAI has admitted it; docs and deprecation warnings | the site runs `v5` for a week without quota or memory incidents |
| 5.0.0 | The release | freeze and fix; merge `v5` into `master`; release 5.0.0 with the release script; the site pins `talkgenerator==5.0.0`; 4.x ends | |

Running alongside the milestones: new sources (each a small pull request with offline tests and a canary test),
content packs (the TED pack first, then one per format), and the checks (growing with every milestone).

## 17. Decisions and open questions

### Decisions so far

| # | Decision |
| --- | --- |
| D1 | Deck JSON, versioned, is the single source of truth; the .pptx and the browser view are renderers. |
| D2 | Plan, realize, render, with `classic`, `llm` and `external` planners. |
| D3 | Python picks the structure with a seeded random generator, and the LLM writes the words in one streamed call per talk. |
| D4 | A provider-neutral interface: OpenRouter, Anthropic and OpenAI first, then Sign in with ChatGPT (CLI), OpenAI-compatible servers, `replay` and `none`. The SDKs are optional extras. |
| D5 | The classic engine stays: the no-LLM default, the fallback, the test mode and the paper baseline. |
| D6 | No global randomness: one seeded generator per talk with derived streams, plus replay fixtures. |
| D7 | talkgenerator.com runs at $0: free tiers only, and AI images only on the visitor's own account or key. |
| D8 | After the groundwork, LLM talks and the Claude Skill come first. |
| D9 | The quality bar is automated checks at every milestone. |
| D10 | Themes are tokens on a layout engine; the pptx renderer draws shapes; v4's template becomes the `classic` theme. |
| D11 | Images are requested through slots, with an aesthetic profile and license classes. |
| D12 | Plans carry queries and prompts, never image URLs. |
| D13 | No pre-releases: a long-lived `v5` branch collects the work, and merges into `master` for one 5.0.0 release when the plan is done. `master` stays 4.x until then, and gets merged forward. |
| D14 | pydantic v2 for the models and their JSON Schemas. |
| D15 | talkgenerator.com's OpenRouter account has $10 of credits, which lifts the free cap from 50 to 1,000 requests a day. |
| D16 | On talkgenerator.com, LLM talks are the default, with a switch for the classic 2019 generator. |
| D17 | Visitors can bring their own OpenRouter account, their own Anthropic or OpenAI key, and, once OpenAI admits the site, their ChatGPT plan. |
| D18 | TED-like talks get every improvement first; new talk formats come after them. |
| D19 | Dutch, and later other languages, whenever an LLM is available; the classic engine stays English. |
| D20 | The Skill encourages users to get their own keys; an MCP server runs only locally, on the user's computer with the user's keys; we host no MCP endpoint. |
| D21 | Extreme themes are on by default. |
| D22 | Browsers load images from their sources; the server caches no images (only the small search-API responses, as v4 does). |
| D23 | Reddit memes stay, and we look for more weird and flavoured sources like them. |
| D24 | No 4.x fixes once 5.0 ships. |
| D25 | Dutch talks on talkgenerator.com may use the site's free OpenRouter quota; once it runs out, they get a classic English talk with a notice. |
| D26 | The new talk formats come in milestone 7, or move to 5.1 if the TED work takes longer. |
| D27 | Without `TALKGENERATOR_LLM`, OpenRouter's free models write talks when there's an OpenRouter key, and talks are classic otherwise: a paid model only writes talks when it's asked for, since a key alone (an `ANTHROPIC_API_KEY` set for other tools, say) shouldn't make talks cost money. |
| D28 | `random` is the default theme: a talk that doesn't ask for one gets a theme its seed picks. `TALKGENERATOR_THEME` sets another default (`classic` keeps the 2019 template), and `generate_presentation(theme=...)` takes one per talk, which talk-generator-web can offer in its settings (`themes.catalog()`). |

D7 to D9, D13 and D15 to D26 were settled on 2026-11-05, and D28 on 2026-11-07; the others follow from the design.

### Open questions

None right now; new ones go here.

## 18. Sources

Checked on 2026-11-05:

- OpenRouter: [rate limits](https://openrouter.ai/docs/api-reference/limits), [OAuth PKCE](https://openrouter.ai/docs/use-cases/oauth-pkce).
- Sign in with ChatGPT: [developer docs](https://developers.openai.com/siwc),
  [integrating it in an open-source app](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt),
  [help center](https://help.openai.com/en/articles/20001410-sign-in-with-chatgpt).
- Claude: [pricing](https://platform.claude.com/docs/en/about-claude/pricing),
  [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
  [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).
- Image generation prices: [invideo's price list (August 2026)](https://invideo.io/blog/ai-image-model-pricing/)
  and [pricepertoken.com](https://pricepertoken.com/image). These are third-party trackers, so check the
  providers' own pages too.
