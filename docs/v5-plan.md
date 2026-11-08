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
| Talk spine (new) | none | title, subtitle, thesis, presenter persona, running gag, two or three callbacks, and the presenter's made-up name ([5.10](#510-presenter-names)) | tracery title; the name from talkgenerator's pack or tracery |
| Slide text | templates and grammars | titles, captions, statements, chart questions and categories, fake facts, about-me lines, conclusions that call back to earlier slides | the classic generator for that field |
| Image queries | the slide's seed word, sometimes with a prefix | a search query (and a generation prompt) per image slot, written for the slot's intent and look | seed-based query |
| Coherence | none: slides are independent | the whole talk in one pass, with callbacks and no repeated jokes | none |
| Picking images (optional) | random among valid candidates | a vision model picks from one contact sheet per talk | local scoring |
| Content packs | hand-written | drafted with an LLM and curated by hand, at build time, never at runtime | |

### 5.2 Python picks the structure, the LLM writes the words

The planner first builds a skeleton with the seeded random generator, the way v4 picks slides: slide types per
position, tag caps, image sources per slot, plus "creative dice" for the prompt (a presenter persona, an angle on
the topic, the seed of a running gag, a few related words from Datamuse). The LLM then writes the content for
that skeleton. The user's idea (2026-11-07): a persona that shapes more of the talk than the model's voice, with the
kinds of talk and slides it favours, its titles, and its presenter's name (a style, or a nudge), the same in classic
mode. Why:

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

**Personas** came in on 2026-11-08 (`talkgenerator.personas`, D47), after the user's idea: "having already like random
persona loaded that only has particular types of talks, and that helps inspire llm for title (...) and maybe even for
name (particular generators, or nudge)". The talk's seed picks one of thirteen personas (from a stream of its own,
`persona`), before the slides are picked. `persona=` names one instead (`--persona`, the MCP server's
`generate_talk`), and `none` makes the format's own talk. A persona has:

- **A voice, and its kinds of talk.** The request's "The presenter:" line ("a startup founder who has pivoted eleven
  times", the voices of before, and new ones: a disgraced professor, a conspiracy blogger, a kindergarten teacher),
  and three or four angles of its own, of which the dice pick one ("a pitch for a startup that will disrupt the
  topic"). Before, the dice combined twelve voices with ten angles at random, such as a life coach on "the
  economics of the topic that nobody talks about".
- **The slides it favours, and those it doesn't.** Multipliers on the format's weights, by the slide generators' tags,
  wherever a generator is picked: for classic slides and for the skeleton of a planned talk alike, so the tag caps
  still hold. A medieval historian has ×3 for history and timelines and ×0.3 for KPI tiles; a startup founder ×3 for
  KPI tiles, ×2.5 for funnels and ×0.3 for history; a kindergarten teacher ×3 for quizzes. A generator with several
  tags gets the product. No multiplier is under 0.2, so no kind of slide disappears, and over all the personas they
  average 0.98 to 1.25 per tag, so the mix of all talks stays the formats'. The base weights stay with the slide
  generators (`slide_schemas.py`, where the work on real karaoke decks tunes them); a test fails when a persona names
  a tag that no generator has.
- **Its titles.** A hint for the model in the title's field ("like a startup's pitch, promising to disrupt
  something"), when the model makes the title up (not for a given title, or a typed one it keeps), and four templates
  of its own for classic talks ("Disrupting {seed.title}", "{seed.title} as a Service"), which half of the classic
  titles come from; the format's title generator makes the others. They use the topic as typed, without the classic
  grammar's plurals ("Coffees"). For a short input (5.11), the classic title that goes to the model as an option or as
  inspiration is that same title.
- **A nudge for the presenter's name.** Weights over the default styles (a medieval historian's name is a famous-name
  pun 2.5 times as often as a pun), for the model's names and for talkgenerator's own, and how the presenter goes by,
  in place of "with a title such as Dr. or Prof. if it suits": "with Prof. before the name, a title they still cling
  to"; for a kindergarten teacher, "as the children call their teacher: Miss, Ms. or Mr. and a surname". An explicit
  `name_styles=` goes alone, as before: the dice pick among those styles each as likely, without a manner.

- **A job hint.** What the presenter's job on the title slide is ("founder and CEO of their startup, with its
  made-up name"; "their role at the kindergarten, made to sound grand"), in place of the job field's example
  ('Professor of Applied Sock Theory'), which free models copied whoever presented (below).
- **Its theme families** (2026-11-08, the user's "also particular types of slide themes?", after the bolder themes of
  section 9 were merged into this branch for it): multipliers on the families' weights when the theme is random (an
  explicit `--theme` goes alone, and `chaos` gives its slides their own as before). A kindergarten teacher has ×5 for
  `kids` and ×3 for `chalkboard`, a conspiracy blogger ×5 for `hacker terminal` and ×3 for `newspaper`, a medieval
  historian ×5 for `vintage paper`; each persona's talks are in its favourite families 36 to 47% of the time (13 to
  19% without), and over all the personas every family comes up 0.87 to 1.15 times as often as without (a test keeps
  it within 0.75 to 1.33). The persona is picked before the theme now, from its own stream, so neither moved.
- **Its pictures' looks** ("and what about some image sources?"): favourite looks for some of the looks slides ask
  for, searched first, with their fallbacks, and then the slide's own look (`ImageContext.persona_looks`, `tries`):
  a historian's `weird` pictures are `medieval` art and their `neutral` ones `museum` art, a founder's and a
  consultant's photos `corporate-stock` and their weird ones `corporate-cringe`, a blogger's weird ones `pareidolia`
  and their neutral ones `liminal`, a teacher's weird ones `wholesome`, a time traveller's `retro-futurism` and
  `space-science`. Only those slots change, so it's a nudge rather than a takeover; the license policy and a slot's own
  sources still decide what may be shown, and whether a slide can be made at all is decided by its own looks, as before.

The request stays one per talk, with the persona in its dynamic part, and the presenter's own name still never
reaches a provider. The deck and `talk.started` have the persona (`persona`: `name`, `label`, `voice`, and the `angle`
in a talk a model wrote), for the site to show later, and `talkgenerator check`'s metrics name it. Classic talks get
the slides, the titles and the names, so a classic talk is no longer the formats' own: `--persona none` is part of
what comes closest to a talk of 2019 now.

Measured offline (the picks of 200 seeds' 10-slide talks in the default format, per talk, against no persona): the
kindergarten teacher's talks have 0.42 quizzes (0.15), the startup founder's 0.33 KPI tiles (0.17) and the medieval
historian's 0.03, the historian's 0.25 timelines (0.09) and 0.98 history slides (0.76; at most one a talk), the
conspiracy blogger's 0.40 news headlines (0.20) and 0.18 icebergs (0.06), the motivational speaker's 0.47 InspiroBot
posters (0.10), the influencer's 1.62 gifs (0.77) and the disgraced professor's 0.29.

Live on 2026-11-08, with OpenRouter's free router (10-slide talks, one request each, $0, without GIPHY and Unsplash,
whose hourly quotas other runs share):

- Round one, 8 talks: five personas on penguins with one seed (4), so that only the persona differs, and three seeds
  whose dice picked a lighthouse keeper (coffee), a consultant (volcanoes) and a former athlete (time travel). The
  model wrote all 80 slides, in 18 to 35 s a talk. Every title was the persona's kind: "Penguin Social: Disrupting
  Human Connection" (the founder), "Penguins in the Margins of Medieval Manuscripts" (the historian), "Penguins and the
  Shape of Growing Up" (the teacher), "Penguins: The Cold Truth They Don't Want You to Know" (the blogger), "Penguins:
  The Academic Establishment's Folly" (the professor), "The Brew That Held the Horizon Together" (the keeper), "The
  Volcano Synergy Framework: From Eruption to ROI" (the consultant), "How Losing Is Just Winning in a Different
  Timeline" (the athlete). The names went by the persona's manner: "Marcus Waddleby" and "Percy Pengwin" without a
  title, "Dr. Thomas Aquipenguin" (on Thomas Aquinas), "Ms. Pearl Pinguard", "Prof. Alistair Pengwin", "Silas
  Coffeewell" (the consultant's model wrote a name that wouldn't do, so the pack's "Martin Lavalle" came). The same
  seed's slides moved with the persona: the historian's talk had two old photos from penguins' history and a timeline,
  the founder's a big number and a ranking, the professor's three charts and a pyramid, the blogger's a news
  headline, a post and a Venn diagram; the consultant's had a funnel and a pyramid, the keeper's an anecdote. Three
  jobs of the eight were "Professor of ..." whoever presented ("Ms. Pearl Pinguard, Professor of Applied Penguin
  Studies"), after the job field's example: hence the job hints.
- Round two, with the job hints, 5 talks: the founder, the historian and the teacher on penguins again (seed 4), and
  the consultant and the athlete. The model wrote all 50 slides, in 19 to 28 s a talk, and every job was the
  persona's: "Penny Pengwin, Founder and CEO of Penguin.ly", "Dr. Abbott Penguin, Professor of Medieval Penguin
  Studies", "Mr. Pennyfeather, Director of Waddle Studies", "Peter Vesuvius, Principal Partner, Synergy Volcanics",
  "Marcus Chronos, Olympic sprinter turned philosopher of time". The titles stayed the persona's ("Penguin.ly: Scaling
  Trust to a Billion Users", "Penguins in the Monks' Bestiary", "Pyroclastic Strategy: A Synergy Roadmap for Volcanic
  Disruption", "The Sprinter Who Lost to Tomorrow"), the teacher's the plainest ("Penguins and Growing Up"). Each seed
  picked the same slides as in round one.
- Round three, with themes and looks by persona: the teacher, the historian and the blogger on penguins with seed 36
  and a random theme, each in its own signature family (`kids`, `vintage paper`, `hacker terminal`; the seed gives all
  three the same member, 88). The pictures came from the persona's favourite looks where it has them: the teacher's
  from Pixabay's illustrations and r/aww's wholesome cats, the historian's from museums (the Art Institute of Chicago,
  the Met) and r/Medievalart, a medieval painting under its news headline, the blogger's from r/LiminalSpace and
  r/Pareidolia ("Gentoo are not birds, they are hardware" over an empty road at night). The blogger's first try ran
  to its free model's output cap (11,700 tokens) and came out classic, as designed, still in `hacker terminal` with
  liminal pictures; its second was the model's. The historian's job hint said "a chair", which gave "Dr. Chair of
  Medieval Penguin Studies": it says a professorship now.

### 5.3 One streamed call per talk

- The prompt has a static part (style guide, slide-type catalog with field limits, output schema: about 2,000 to
  3,000 tokens, cached where the provider supports it) and a small dynamic part (topic, format, skeleton, dice,
  language).
- The model writes the spine first, then the slides in order (which is alphabetical order too, as some models
  write the answer that way: the spine is one object, `about`, before `slide_02` to `slide_10`; see
  [13.1](#131-streaming-slides-into-the-browser)). Providers with structured outputs (Anthropic, OpenAI, some
  OpenRouter models) get the JSON Schema; the others write JSON Lines, one slide per line. Either way, an
  incremental parser hands over each slide as soon as it's complete, so slide 1 is being realized and shown while
  the model writes slide 2.
- Each slide is validated against its type (fields, lengths, banned strings). An invalid slide falls back to
  classic content for that slide only.
- Regenerating one slide is one small call, with the spine and the neighbouring slides as context.
- The presenter's name never goes to a provider: plans use a `{presenter}` placeholder that's filled in locally.
  Without a name, the model makes one up in the spine, in the same request ([section 5.10](#510-presenter-names)).

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
`talkgenerator login chatgpt` does it (`talkgenerator.llm.chatgpt_login`, with the `chatgpt` provider), built to
[OpenAI's docs for open-source apps](https://developers.openai.com/siwc/token-sharing-open-source). Tried for real
on 2026-11-07: OpenAI took talkgenerator's registration and showed its consent page ("Connect talkgenerator to
ChatGPT"), but the account had no subscription, so "A required permission is unavailable" kept it from going
on. The first try's code was turned down (`invalid_grant`), which OpenAI's docs answer with a fresh sign-in, as
talkgenerator now does by itself. Still to try before 5.0.0: a sign-in with Plus or Pro, its models' list, and a
talk (the default model, the first the account lists, and the default effort, `low`, are guesses until then).

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
and pt, and since 2026-11-07 sv (the title slide's "By ...", a chart's "Yes" and "No"); a slide of a non-English
talk that doesn't come out becomes a full-screen picture of its concept, without text, rather than an English
classic slide (or is left out, in a format without such pictures); recipes with `texts_from` (real quotes, which
are English) are left out of non-English talks; decks have a `language`; and `check_language` reads a deck's texts
with NLTK's stopwords (only the words that tell the language and English apart), flagging slides and talks that
read as English. Dutch Wikipedia and Wikiquote as sources are still to do.

Swedish (`sv`) joined on 2026-11-07, at the user's request (D41). Besides its own words ("Av ...", "Ja" and "Nej", a
post's "gilla-markeringar" and "delningar", a news story's "JUST NU"), it needed three things the other languages
didn't:

- What's typed reads as a title, without a model, when it starts like a Swedish one ("Hur", "Varför", and "Därför"
  and "Så", where English headlines say "Why" and "How to") or makes a Swedish claim ("är", "måste", ...). But
  English "is" isn't a claim in Swedish, where it means ice ("Pingviner på is").
- The language check leaves out Swedish words that are English stopwords too but missing from NLTK's Swedish list
  (`Language.english_lookalikes`: "in", "all", "just", "be", "by", "is"), which made a terse Swedish slide ("All
  glass in", or a chart of "Is" and "All mat") read as English.
- The spelling fixes of what's typed (`word_frequency.fix_spelling`), which take English words as candidates in
  every language, turned rare words of the talk's language into English ones, and compounds into near words.
  Measured on samples (600 rare words and about 790 made-up compounds per language, wordfreq's lists): 27 Swedish,
  38 Dutch and 65 French rare words became English-leaning ones ("matare", Swedish for a feeder: "mature"; Dutch
  "attractieve": "attractive"), and 17 Swedish, 13 Dutch and 8 German compounds became near words ("tomatbok":
  "tomato"; "maanspion": "mansion"; "Computerkrise": "computerised"). Now a word that the language knows at least
  as well as English only becomes another word of that language. And in a language that writes compounds as one
  word (`Language.compounds`: nl, de and sv), a word made of two or more of its words stays as typed: the first
  word may be joined on with an "s", or lose its last "e" or "a". The exception is a word one edit from a known
  word, which still gets fixed: 2 Swedish, 4 Dutch and 2 German compounds still change, all a letter away from a
  real word ("issekt": "insekt"). The English-leaning changes left (10, 20 and 29) are of words that are more
  English than the language's own. Typos of common words get fixed as often as before in all eight languages (476
  of 540 in Swedish before, 478 now, as "å" joined the letters an edit may use).

Swedish compounds are as long as Dutch ones. Titles with a word over 15 letters already keep off the side
layouts, and the Swedish 20-letter words measured (with å, ä and ö: "Kärnkraftsolyckornas", "Pingvinkaffekulterna")
are no wider than the Dutch word that the long-word tests use, in any theme font: those tests passed with Swedish
words in all twelve families. Words of 22 letters can
still overflow a few narrow boxes in any language (a timeline's moment, a 2×2 matrix's axis end, a slide type's
title at its smallest size), in four of the families.

Live (2026-11-07, OpenRouter's free router, one request a talk, $0): seven Swedish talks, four on what was typed
("kanelbullar", "älgar", "Varför jag gick med i en pingvinsekt", "katter är flytande") and the three sample talks
(cat, peanuts and time travel). There were no language findings, and every title was Swedish: the typed title was
kept as typed, the premise kept its words ("Katter är flytande: En medeltida guide till livets flyt"), and the
topics got titles of their own ("Älgar: De glömda makarna i medeltiden"). So were the names: "Prof. Kanel
Bullarsson", "Prof. Olof Älgkonung", "Prof. Albert Pingvinstein", "Dr. Tor Tidström". The model wrote 62 of the 70
slides: one answer stopped at its output cap (11,700 tokens, where the others needed 674 to 1,008), and that talk's
other eight slides became pictures, as designed. `deck_metrics` counts those pictures as written by the model, as
their notes start with "Planned:". One presenter job came out in English ("Professor of Antarctic Entomology"),
which the check doesn't see on a title slide that also says "Presenterad av". Two three-circle Venn diagrams didn't
fit a long label ("Hantverksföreningar", "Medeltidsentusiaster"); laid out again with the Venn branch's labels
beside their circles (`2126dc5`), both fit. The free models' Swedish has slips that no stopword check can see
("Erdnöten" for jordnötter, a headline that reads Norwegian).

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

### 5.10 Presenter names

Built on 2026-11-07 (`talkgenerator.names`), from the user's idea: "have the chosen LLM model generate something
fun" instead of tracery's random first-plus-last-name combiner. A talk without a given name gets one in a style
its seed picks among the switched-on ones (`name_styles=` on `generate_presentation` and `stream_talk`,
`--name_styles`, the MCP server's `generate_talk`; `names.catalog()` lists them for a settings menu):

| Style | On by default | Example |
| --- | --- | --- |
| `pun` | yes | "Prof. Anna Tomy" for a talk on medicine, "Dr. Matthew Mathics" for maths |
| `fun_surname` | yes | an ordinary first name with a surname that fits too well: "Linda Hivesworth" for bees |
| `famous_pun` | yes (D33) | a historical figure's name bent to fit: "Albert Einstone" for geology, "Vincent van Goat" for goats |
| `classic` | no | tracery's random first and last name, as in 2019 |

- **A given name goes first** (`presenter=`, the site's "custom name"), and never reaches the model: the request
  then has no name field at all.
- **One request.** The model writes the name in the spine, after the title and before the presenter's job, which
  agrees with it (a "Prof." is a professor of something). `talk.started` doesn't wait longer: the spine is in
  before the first slide. The prompt shows two names of the style for other topics than the talk's, drawn by the
  talk's dice from the pack below, with what they play on ("'Anna Tomy' (anatomy) for medicine", "'Albert
  Einstone' (Albert Einstein) for geology"), and a name that copies one of them is turned down, as free models copy
  examples.
- **Checked like the other fields.** A name is turned down when it's longer than 45 characters (a name isn't cut:
  half a name is no name), holds template code or what no name has (digits, brackets, commas), is a placeholder
  ("Presenter Name", in the talks' languages), names a dictator or one of the living people models reach for
  most (a short blocklist, which word beginnings match too: "Donald Trumpet"), or is the real name of a famous person
  whose name the pack bends ("Marie Curie"). Then the talk gets the name a talk without a model gets.
- **The talk's language.** The model writes the name in it, with wordplay that works in that language.
- **Without a model** (none configured, the quota used up, a refusal, or a name that won't do), the name comes
  from talkgenerator's own pack (`data/text-templates/presenter_names.json`, D34): 279 names by style and topic,
  drafted with a language model, for the user to curate by hand. A talk whose topic matches an entry's words
  (singular or plural, phrases word for word) gets one in a switched-on style the pack has for it: puns for 642 of
  the 736 topics of `topics.txt`, fun surnames for 83, famous-name puns for 41. Other talks get a classic name,
  from the same random stream as before, so a seed keeps its classic name.
- **Plans** (the Skill, `render`, the MCP server's `render_plan`) can name the presenter themselves
  (`presenter_name`): the agent is the language model there. `--presenter` goes first; a name that won't do gets
  a note in the report and a made-up name.
- **Determinism.** The style, the examples and the pack's name all come from the talk's seed (streams under
  `presenter`), and the styles' order doesn't matter, so the same seed with the same answers gives the same name,
  streamed or made at once.
- **What it plays on, first.** For a written name, the model first writes what the name will play on
  (`name_plays_on`, not shown: a word about the topic, or a famous person and a word), then the name. The field
  sorts before the slides, also for the free models that write the answer's fields in alphabetical order.

Live on 2026-11-07, with OpenRouter's free router (3-slide talks, seed 1, one request each, $0):

- First round, 11 talks (10 streamed): every name was the model's, and `talk.started` had the deck's name in every
  streamed talk (2 to 11 s after the start). Fun surnames came out well ("Dr. Agnes Hiveborne" for bees, "Dr.
  Alistair Magma" for volcanoes, "Dr. Barnaby Brewster" for coffee), and the Dutch ones best ("Dr. Miauwke Poezema"
  for katten, "Dr. Eva Tandwiel" for fietsen). Puns hit and missed ("Dr. Penny Guine" for penguins, but "Dr.
  Numeralis" for maths and "Dr. Alistair Plague" for medicine), and the famous-name puns bent no one's name ("Dr.
  Bede Stonecrop" for geology, "Prof. Octavius Sockwell" for socks).
- With the examples' meanings in the prompt ("'Anna Tomy' (anatomy) for medicine"): "Prof. Curd N. Whey" for
  cheese, but still no famous name ("Dr. Bede of Stratford" for geology, "Prof. Peter Pillage" for pirates).
- With `name_plays_on` too: famous-name puns that show whose name they bend ("Dr. Leonardo da Stone" for geology,
  on Leonardo da Vinci; "Dr. Joan of Sock" for socks, on Joan of Arc; "Dr. Thom Owlina" for owls, on Thomas
  Aquinas; "Dr. Marco Pillarate" for pirates, on Marco Polo). Puns stay hit and miss with the free models ("Dr.
  Rail Thane" for trains, "Dr. Chayze" for cheese).
- The seed's dice gave every talk the same persona (a medieval historian), which shows in the names ("Bede").

### 5.11 Topic or title

The user's idea (2026-11-07, D32): what a visitor types can be a topic ("penguins") or a title ("Why I Joined a
Penguin Cult"), and a language model can tell which. On talkgenerator.com, the Talk tab's "What you type is" gets a
third choice, **Automatic**, the default, next to Topic and Title.

- **In the same request** (5.2: one per talk). The prompt's dynamic part gives what was typed, and the model says
  in the spine, which it writes first, whether it read a topic or a title.
- **A title** stays the talk's title, with obvious slips fixed (spelling, grammar, capitals) and its wording and
  joke left alone. The topic comes from it, as the rarest word does in classic mode.
- **A topic** gets a title from the model, which picks the best of its own proposal and 1 to 3 classic candidates
  that the seed draws (tracery titles, a wikiHow "How to ..." title), fixing a candidate where it's off. The model's
  own titles stay a good option: the user likes them ("Why I Joined a Penguins Cult and Why You Should Too", by the
  free models on 2026-11-07). The candidates also catch what the classic generators get wrong: an odd wikiHow page,
  a broken plural, a title that makes no sense.
- **Topic or Title, chosen explicitly,** work as now: the model doesn't second-guess the visitor.
- **Without a language model**, Automatic guesses: a title when what's typed has four words or more, starts like
  one ("How to", "Why", "The", "A", "My") or ends in "?" or "!"; a topic otherwise.
- **The API:** a third input next to `topic` and `title` in `generate_presentation()` and `stream_talk()` (say
  `typed=`), whose kind the planner tells. `talk.started` already carries the title the talk settles on, and the deck
  can record how its input was read, for the checks.
- **Checks:** a benchmark of typed inputs, half topics and half titles, some misspelled: the share read right, and
  titles kept recognisable.
- It changes the spine and the prompt, as the presenter names do (5.10), so it's built after them.

Built on 2026-11-07 (`talkgenerator.titles`), after the presenter names and the fix for answers in alphabetical
order (the spine is one object, `about`). After three live rounds (below), the user's call (D35): what's typed
is kept as the title only when it's clearly one; anything shorter is a topic or a premise for a funnier title of
the model's, as "The French Revolution" deserves better than itself.

- **The argument is `topic_or_title=`**, in `generate_presentation()` and `stream_talk()`, instead of `topic` and
  `title` (a ValueError with either). talkgenerator.com sends what's typed as `topic_or_title` (its "What you type
  is" choice is gone since the evening of 2026-11-07), and **what's typed in quote marks is the title, word for
  word** (`titles.quoted`): not even its slips are fixed. Also `--topic_or_title`, and
  the MCP server's `generate_talk(topic_or_title=)` (its `topic` is optional now: a topic, a title or a
  topic_or_title). The Skill needs no argument (Claude is the planner there): its instructions say the same.
- **Clearly a title** (`titles.clearly_a_title`): a part of four words or more, or a question or exclamation. The
  request says `Title: "<typed>" (as the user typed it: keep its words, fixing only its spelling, grammar and
  capitals)`, and the talk gets the model's version when it's recognisably the typed one (about as many words, none
  added or left out but little ones, at least 70% the same letters: `titles.recognisable`) or part of a longer
  title of its own, and else what was typed, with the slips fixed that talkgenerator can fix itself
  (`titles.polished`: misspellings, a capital start for a title typed in lower case). Its topic is its rarest word.
- **Anything shorter is the topic, or a premise** ("Cats are liquid"): the request says `Topic: "<typed>" (as the
  user typed it: the talk's topic, or a premise for it)` and `Title: come up with one, funnier and more specific
  than what the user typed`, and the model's title goes (its own_title rather than an echo of what was typed). The
  topics are what was typed. A misspelled input comes with what it means (`"pengiuns" (as the user typed it,
  meaning "penguins": ...)`), as the model otherwise kept the typo in its title now and then.
- **Misspellings** are fixed before the topics are taken (`word_frequency.fix_spelling`): a rare word becomes the
  likest word one edit away that's a hundred times more frequent ("waht": "what", "joind": "joined"), a word no
  language knows the closest frequent word ("airplain": "airplane"); made-up words stay ("Zorblaxia").
- **The classic titles**, for a short input in an English talk: the talk's dice draw one to three, from the format's
  title generator, a wikiHow "How to ..." title (`content_generators.wikihow_title_generator`) and the title
  generator again, each from a stream of its own, leaving out those that don't mention the topic ("Never, Ever Be A
  Secret Agent" for penguins); about 0.7 s before the request (one wikiHow search, cached after that). The talk's
  dice pick how they go (`titles.CLASSIC_TITLE_WAYS`, a third each): as titles to pick (an `own_title` first, then
  the title, which may be a classic one), as inspiration only (`for inspiration only (write your own)`, and one
  title field), or not at all (no wikiHow search either). The user liked the titles of all three in a live
  comparison (below), and chose to have them all.
- **Without a language model** (or when it writes no title), talkgenerator's guess goes: a title also when it starts
  like one ("How to", "Why", "The", "A", "My") or makes a claim (a form of "to be", or a modal verb), in the talks'
  languages, which stays as typed (polished); a topic gets the classic title.
- **WikiHow's how-tos** are only the pages that teach an action ("How to ...", "4 Easy Ways to ..."): its search now
  also finds lists, quizzes and questions, which the 2019 code cut into actions such as "e 20 Top Games Like Club
  Penguin". That helps the classic slides and titles too.
- **The deck and `talk.started`** record it: `topic_or_title` = {text, `read_as`: topic or title}.

Live on 2026-11-07, with OpenRouter's free router: a benchmark of 20 typed inputs, 10 topics (two misspelled, two
that start like titles: "The French Revolution", "The Beatles") and 10 titles (two misspelled, two short claims:
"Cats are liquid", "Breakfast is overrated"), in talks of 4 slides, one request each but one, $0:

- Round one (seed 1), the model saying in `input_is` which it read: 14 of 20 read right, fewer than talkgenerator's
  guess (16). The free models' label often contradicted their title (dots-3 said "title" for "sourdough bread" and
  wrote a title of its own), and one title came out "Typed: Quantim Physics".
- Round two (seeds 1 and 2), reading by the title the model wrote: 17 and 16 of 20. Clear titles lost to classic
  ones ("10 reasons your toaster hates you": "Never, Ever Clean A Toaster"), which led to keeping clear titles.
- Round three (seed 3), clear titles kept: 19 of 20, every clear title recognisable, slips fixed ("waht my cat taught
  me about taxes": "What my cat taught me about taxes"; "how too become a profesional napper": "How to Become a
  Professional Napper"), and the best titles were the model's own on short inputs ("Cats Are Liquid: The Future of
  Fluid Startups"), while "Breakfast is overrated" stayed as typed: hence D35.
- Topics took a classic title as listed in about half the talks of the three rounds ("How to Make Penguins Your
  Friend", "What Your Sourdough Bread Says About You", "Why Beatles Will Ruin Your Life"); the models' own were often
  spicier ("How Medieval Cheese Will Save Your Startup", "The Hidden Medieval History of Quantum Physics").
- Median 17 to 24 s for a 4-slide talk; all 80 slides of a round by the model.
- The classic titles three ways, with the request asking for a funnier, more specific title (12 short inputs, one
  model, `nvidia/nemotron-3.5-super-vl:free`, seed 2, 3-slide talks): the model never picked a classic title, as
  options or as inspiration, and the titles were as spicy with them as without ("Your Tax Return Is a Peasant's Pig
  Declaration", "The Domesday Deduction: Why Your Tax Return Is a Feudal Confession", "The French Revolution: A
  12th-Century Property Dispute That Got Out of Hand"). With classic titles listed, it kept a typed misspelling
  three times ("Pengiuns: ...", "Quantim Physics ..."): hence the meaning that now goes with it. Seed 2's dice give
  every talk the same persona, a medieval historian, so every title was medieval.

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

In milestone 6 (2026-11-07), fourteen came in, drawn as texts on shapes (D37): a **big number** (with what it
counts and a made-up source) and **KPI tiles** (three or four figures, the last the punchline); a **quiz** (three or
four options, A to D, and on a click the answer: a band behind the right option, its letter on a stamp, and an
explanation); a **social media post** (a made-up poster, their handle, likes and shares in the talk's language, and
a photo) and a **news headline** (breaking news on television over its photo, or a newspaper's front page); an
**agenda** after the title, a **section** divider in the middle (numbered by the deck: 02, 03...) and **Questions?**
as the last slide now and then; and native diagrams: a **timeline**, a **pyramid**, a **funnel**, a **cycle**, a
small **org chart** and an **iceberg**, with their punchlines on a click. Each has a kind with field limits for
plans and the language model, a classic generator (templates and ConceptNet's related words), and two or three
layouts. A talk has at most one of each (sections one per ten slides, diagrams two per ten), from its third slide
to the one before the conclusions: about 1.7 of a 10-slide talk's slides (2.2 in the `ted` format). The quiz's
answer comes on a click rather than on the next slide, as a slide generator makes one slide. Still candidates:
a process with a "???" step, a fake contact slide, a comparison table, the other media and audience slides, and
the academic ones.

**Memes with live captions** came in on 2026-11-07 (D40): a `meme` slide is one of Imgflip's templates (10.4) with
its captions as texts on the picture. Imgflip's API lists its templates' pictures but not where their captions go,
so `data/memes.json` has 25 of its best-known, family-friendly ones (Drake Hotline Bling, Two Buttons, Distracted
Boyfriend, Gru's Plan, Expanding Brain, Change My Mind, Bell Curve...), with every caption's box measured on
Imgflip's own picture, as fractions of it, its style and what it says: white Impact in capitals with a black outline
(a twelfth of the text's size), or plain black text where the template has an even white or pale area (Drake's
panels, Gru's boards), whose colour a label under the text keeps, so the design checks know what's behind it (the
script that sampled those colours also checked that each area is even). Python picks the structure, as everywhere:
the talk's dice pick the template, as one of the recipe's variants (one per template), which tells the language
model the template and what each caption is for (`text_1`: what Drake waves away), about how long each may be (by
its box), and fixes the slot's query to the template's ID (`Recipe.queries`, new), so the model writes no query for
it. A classic talk takes each template's own sentences about the slide's topic (`{seed}`) and a word related to it.
Gru's fourth board repeats his third (`same_as`). The layout (`v5/meme`) puts the picture as large as fits above the
credits, untouched by the theme's treatments (a polaroid frame or sepia would move or hide the captions), and every
caption in its box; a caption whose words don't fit a narrow box (a sign's) at the smallest size gets its box grown
around its middle, within the picture. In the deck it's a picture, texts and shapes, which every renderer draws
already: talk-generator-web unchanged (it draws outlines as `-webkit-text-stroke`). The design check of an outlined
text now asks, per colour that may be behind it, whether its fill or its outline reads there. A talk has at most
one meme, from its third slide on, and only where fair use is allowed (its slot's only source is Imgflip): not in
`ted`. Plans written elsewhere name the template in their `template_query` (`talkgenerator formats --memes` lists
them with what each caption says); a picture whose boxes talkgenerator doesn't know gets its captions at its top and
its bottom.

**Memes more often, and slide types from real PowerPoint karaoke decks** (2026-11-08, D48, D49). The user loves the
memes, so a meme weighs four times what the other slides in a talk's middle weigh, and a talk may have two (never of
one template: the dice avoid the one it has): over 500 seeds of 10-slide `default` talks, a meme with live captions
comes up in 49% of the language model's talks and of classic ones (19% and 16% before), 0.6 a talk, with as many
kinds of slides in a talk as before (9.5). Classic captions now speak of the slide's topic as English does: "Love
coffee", "Love penguins", "Is this a lighthouse?" (template functions `{seed.generic}`, `{seed.one}` and `.cap`: a
noun counts when its plural is about as common as it, by wordfreq), never with a verb that has to agree with it; the
free models' captions, checked live (36 memes), needed sharper hints for four templates, and the Bell Curve's wise one
now says what its simple one said (`same_as`). Then a catalogue of what real karaoke and battle decks, TED parodies and
bad-PowerPoint humour have that talkgenerator lacked (109 pages read, 26 kinds, with their sources, in the hand-over
notes), and the best of it that the deck's texts and shapes can draw: a **fun fact** ("Did you know?", with a made-up
source and a photo), an **acronym** for a made-up method (its last word, the punchline, on a click), a **dare** for the
presenter (organisers put one in a deck at most, so it's rarer: about one talk in twelve), a **flowchart** whose Yes and
No lead to the same end, and a **tier list** from S to F (its S tier on a click); and a recipe variant, a real chart
from the internet under a confident conclusion that it supposedly proves. Waiting: the wall of text (unreadable on
purpose, under the design checks' 24 px floor), the spaghetti diagram (its diagonal links need a line element), the
next in the catalogue (a text-message conversation, buzzword bingo, a labelled photo, famous words as bullet points, a
starter pack, a conspiracy board), and cheap recipe variants ("Pick One:" over two pictures without captions, a second
"In conclusion...", a demotivational frame for InspiroBot, the planet for no reason, charts without numbers, "Not on
Agenda!", a spurious correlation).

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
- **Fonts:** a .pptx names its fonts, and the computer showing it needs to have them, unless they travel inside it.
  So themes use two kinds. Widely installed fonts (Arial, Calibri, Georgia, Verdana, Trebuchet MS, Impact, Comic
  Sans MS, Courier New, Times New Roman...), which the browser view maps to web fonts: measured with bundled open
  fonts that share their metrics (Liberation Sans, Serif and Mono for Arial, Times New Roman and Courier New;
  Carlito for Calibri; Caladea for Cambria; Gelasio for Georgia), and the ones without such a twin (Arial Black,
  Verdana, Trebuchet MS, Impact, Comic Sans MS) with a table of every character's width in them, measured once from
  their own files. And open fonts with more personality (D42): two pairings per family, from Google Fonts (Poppins,
  Space Mono, Crimson Text, Abril Fatface, Audiowide...), which a member has two times in three. They're bundled
  (3.9 MB), so they're measured everywhere; every .pptx that uses them carries them inside it, regular and bold, as
  uncompressed Embedded OpenType, which PowerPoint for Windows shows (tried on 2026-11-07), as PowerPoint for Mac
  and LibreOffice 25.8 should; and the browser view loads them from Google Fonts. Where a deck's own fonts aren't
  used (PowerPoint for the web, most likely Keynote), a stand-in shows: each open font has an installed one, texts
  are fitted to both (a few percent smaller in the fonts narrower than theirs, such as Barlow and Titillium Web),
  and runs carry the font's PANOSE and pitch family, so the stand-in is of the same kind. Lato and Poppins are
  Office cloud fonts, which PowerPoint for the web shows anyway. The extremes keep their installed fonts: Comic Sans
  MS, Impact and Arial Black are the joke. Font sizes are picked deterministically, the same on every computer, and
  text doesn't overflow. Only a character outside the tables gets a safety margin. PowerPoint's shrink-on-overflow
  stays on as a safety net.
- **Rendering:** the pptx renderer draws shapes (text boxes, pictures, shapes, charts) on a blank slide instead
  of filling the template's placeholders. v4's `template.pptx` lives on as the `classic` theme, for the paper
  baseline and for anyone who likes the old look.
- **Image treatments** give images from mixed sources one look: grayscale, sepia, duotone in the theme's colors,
  grain, vignette, rounded or polaroid frames. Pillow applies them for pptx; the browser view uses CSS filters,
  at no cost to the server.
- **Design rules**, all checked automatically ([section 14](#14-automated-quality-checks)): no overflow, minimum
  font sizes, contrast, safe margins, no image enlarged beyond about 1.3× its size, small but legible credits.
- Later: bring-your-own .pptx templates, such as corporate master slides.

The user's direction (2026-11-07): themes should be more than a reskin by font and colour. Families that make
harder choices, such as a childlike kindergarten style with vector shapes, or a hacker style in a monospace font,
green on black, each with decoration and layouts of their own; and image filters that are subtler, rarer, and only
where they fit. Themes made for decks online are the place to look first.

As built (2026-11-08, D43 to D46), after a look at Slidesgo, SlidesCarnival, PresentationGo, SlidesMania, SlideSpeak's
design prompts and open-design's decks (Canva, Behance and Dribbble only by their search results): what sets a strong
theme apart is a fixture on every slide (a status line, a title block, a top rule), its big motif saved for the title
and section slides, a small palette with its accent rationed, a few pieces of decoration a slide and never behind a
text, handmade families tilting things a little where grid families keep everything square, one casing rule, and a
fixed place for its texts; and the sources treat pictures as a family's property, most of them untouched.

- **Motifs** (`talkgenerator.design.motifs`, D43): every family has one, which decorates a slide's placement before
  the engine styles its texts. It draws behind everything (scenery, a frame, a grid), over the layout's shapes (a
  sticker, an underline) or over the content (tape on a photo), writes texts of its own (role `decoration`: a slide's
  number, a prompt, numbers, symbols and code, so any language suits them; the language and leftover checks leave
  them out), and may move a text (for a prompt) or fit a picture to a frame around it. Its texts' colours come from
  what's behind their letters, and its see-through pieces are only as strong as the texts over them allow.
- **Shapes and patterns** for it, in the deck, drawn alike by PowerPoint, the previewer and talk-generator-web (its
  branch `claude/bolder-themes`): polygons (their corners as shares of their box: PowerPoint freeforms, CSS clip
  paths; stars, pennants, bursts, hearts, arrows, waves, and lines drawn as polygons for squiggles and strokes), shapes
  turned around their middle, rounded corners, outlines inside the box, shapes without a fill, and a background
  pattern (lines, a grid or dots: PowerPoint's slide background is a picture of it, which a .pptx keeps once; CSS
  repeating gradients in the browser). `talkgenerator.design.geometry` has what they share.
- **Families** (D44): five new ones, none for laughs: `hacker terminal` (green, amber or cool phosphor on black, a
  window bar, scanlines, prompts before the titles, a block cursor after the talk's title, pictures in windows named
  `./evidence_031.jpg`, a status line), `blueprint` (a white grid on a blueprint's blue, a border with registration
  marks, dimension lines under the titles, figure plates, a title block, a red pencil's punchlines), `chalkboard`
  (a green or slate board in a wooden frame, a ledge with chalk and an eraser, eraser strokes, dashed chalk
  underlines, doodles, taped pictures, handwriting), `newspaper` (newsprint, masthead rules with the edition's numbers,
  a front page for the title slide, rules between columns, grayscale photos) and `Swiss poster` (a grotesk flush left
  on a three-column grid, a heavy black rule, one red block a slide, a big red circle and huge type on the title slide,
  black dividers with a giant number). `kids` became a kindergarten's: crayon colours on cream, bunting on every
  slide, crayon squiggles, confetti, sticker pictures, a title card with a sun, a cloud and hills with flowers, section
  numbers on a sun. The others got theirs: academic's Beamer-like title band, dots counting the slides and footer;
  neon's sunset over a grid floor; vintage paper's ornamented double frame; brutalist's title blocks, hard shadows
  and number tag; corporate's top band and slanted title panel; startup's blobs; Comic Sans' panel border, speech
  balloons and POW; WordArt's starbursts; clip-art's swoosh; keynote's and dark minimal's quieter marks. The families
  that commit to a scheme pick one of a few palettes (repaired as any), some have open fonts more often, and kids,
  neon, Swiss poster, newspaper, academic and corporate have their own title slides (and kids, neon and Swiss poster
  their own section slides), 61 layouts in all. Names stay; a seed still picks a family's member.
- **Image treatments** (D45): the strong filters are for the families made for them, and only where they fit (a
  family's filter can be for backdrops only; black and white never goes behind a slide's texts), and a theme can lay a
  gentle tint over its pictures instead (a warm or cool cast at 7%, its paper at 10%, its accent at 8%): of 3,000
  random themes' pictures, 21% got a strong filter (34% before; black and white 0.5%, 3.9% before), and 30% of themes
  tint theirs.
- **Checks** (D46): a text has to read on what's behind its letters, its lines as the engine breaks them, as tall as
  their letters (not its whole box: a cursor after its last word doesn't count), where a shape over part of them
  counts, and a background's pattern too; diagrams are coloured for the decoration that reaches under them; and the
  band behind credits that need one hugs the credit line, clear of a status line under it.
- **Measured:** 17 saved talks (the site's live ones, the free models' cat, peanuts and time travel in English and
  Swedish, the lighthouse talks with every slide type, the memes) laid out again in all 17 families over 4 seeds:
  15,708 slides, no design finding (the first run found 5, a Swiss poster's diagram labels over its grid lines on red:
  fixed). In the browser, talk-generator-web's dev server drew a deck of the new families as the previewer
  does (kids' title, terminal, blueprint, chalkboard, newspaper, Swiss). Not checked in PowerPoint itself yet.

## 10. Images: sources, aesthetics and generation

### 10.1 Image slots

Every image in a plan is a slot, not a call to a source:
`{intent, queries, orientation, min_pixels, text_area, aesthetic, license_classes, sources}`. An image finder
searches the sources in parallel (with v4's cache and cooldowns), filters the candidates (license, size,
orientation, metadata, prohibited and duplicate images), scores them (fit with the slot's look, local image
analysis, optionally a vision model), validates the winner (download or probe), and picks with the talk's random
generator. v4's weighted mixes of sources become source weights per aesthetic profile.

As built (2026-11-07, `talkgenerator.images`): `ImageSlot` has those fields (and `backups`, looks that take over in
order, and `generate`, for 10.5); a recipe's images are slots, and v4's image generators in `content_generators` are
slots under their old names, so classic slides and recipes ask the same way (a recipe or a variant can leave a slot
out: the builder gets None, and the model writes no query for it). The finder (`finder.py`):

1. orders the look's sources that the talk's license policy allows by weight, without putting one back (what v4's
   `CombinedGenerator` did one at a time), and then leaves out those that can't be searched now (no key, a
   cooldown): the others keep their order, so a cooldown changes only what that source would have found;
2. searches them two at a time for most looks (a look's `breadth`), in parallel, each search in a thread of its own
   with a random stream from one number of the slide's, so the same seed finds the same, whatever comes back first;
3. filters: the license class of every image (Openverse's and Wikimedia's each have their own), size and
   orientation as the source tells them, descriptions that say NSFW, the same address twice, and the slide's own
   images;
4. a look without preferences takes the first source in the order that found any, and one of its images at random
   (a plan's among its source's best five), as v4 did; a look with preferences (or any look in a themed talk) takes
   a look at the thumbnails of a few candidates, drawn by their sources' weights (6 for `vintage` and
   `calm-backdrop`, 6 more when none has the look, 3 for colours in a themed talk), and picks among those that
   have the look, by weight and by how well their colours go with the theme's;
5. checks the winner as before (`check_image`: a probe while streaming, a download otherwise), and the next one
   when it won't do (8 at most per batch of sources);
6. hands over to the look's fallback when its sources find nothing (or none is allowed), then to the slot's backups.

Every picked image gets a look at its thumbnail (one small download, the same while streaming and when made at
once, so a streamed talk stays the talk made at once), whose perceptual hash keeps nearly the same picture off other
slides: the schema's rule that no slide repeats an image now counts near-duplicates, and slide generators keep to it
themselves (they could repeat an image when allowed to repeat something, which parallel generation then rejected
round after round; found by this work's determinism test). Searching two sources at once asks more of them than v4
did (in the speed comparison below, 8 searches at Pexels against 5; cached for a day, as before): to watch on
talkgenerator.com, where Unsplash is at 50 an hour until its review.

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

As built (2026-11-07, `talkgenerator.images.licenses`): every source module declares `LICENSES` next to `DISPLAY`,
and its images carry `license_class`, `license` and `license_url` (Openverse: by the item's license, asking only for
CC0, the public domain mark, CC BY and CC BY-SA, as NC can't be shown at a paid show and ND not in a theme's
colours; Wikimedia Commons: by its `LicenseShortName`, `License` and `LicenseUrl`; the Art Institute: CC0; the stock
sites their own licenses; Reddit, GIPHY, InspiroBot and ShitpostBot fair use, without a license). Credits name the
license of open and public domain images, linking it; stock photos are credited to their photographer and platform,
as the platforms ask. A policy is `all`, `open`, or classes ("public-domain,open"); the `ted` schema keeps to `open`
(its own copyright-free generators, as in v4, and now the search too), and any talk takes `license_policy`. Slide
generators whose recipes' slots the policy allows no source for (gifs, memes, InspiroBot, Reddit's charts, the
about-me book cover, under `open`) aren't picked, and a plan's recipe of that kind gets its kind's default, with a
warning. The deck keeps the policy (`Deck.license_policy`) and every image's class and license; `talkgenerator check`
reports an image the policy doesn't allow as an error.

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

As built (2026-11-07, `profiles.py`, `catalog.py`, `analysis.py`):

- **Looks**: `photo` (v4's copyright-free mix: Unsplash, Pixabay and Pexels 1 each, Openverse 0.1, a random
  Unsplash photo as a classic last resort), `neutral` (that, and Reddit's pictures at 0.93: v4's 1000 to 300),
  `weird-stock`, `corporate-stock` (blue and teal colour filters, "business" and "office"), `calm-backdrop` (Pixabay
  3, Unsplash and Pexels 1, landscape; at most 0.08 of detail where the text goes, where a sky has 0.02, a landscape
  0.06 to 0.09 and a street 0.12 and more; brightness 0.12 to 0.7: statements' backdrops, which were Pixabay's
  only), `vintage` (Reddit's old photos 3, Commons' black and white photographs 2,
  Openverse's archives (NYPL, the Finnish Heritage Agency, DigitaltMuseum, the Smithsonian's archives), Unsplash's
  and Pixabay's black and white; monochrome preferred, sepia applied: history slides, which took Reddit's colourised
  photos and the Art Institute's paintings too), `old-photo`, `old-people` and `portrait` (historical figures),
  `museum` (the Art Institute 3, Openverse's museums 1.5: the Met, Cleveland, the Rijksmuseum, SMK, Brooklyn, the
  Smithsonian American Art Museum; Commons' paintings), `space-science` (Commons' "Images from NASA" 2, Openverse's
  NASA, SpaceX and Air and Space Museum 2, stock "space"), `illustration` (Pixabay's illustrations and vectors,
  Openverse's illustrations and the Biodiversity Heritage Library's drawings), `meme-chaos` (v4's weird punchline
  mix: Reddit's weird 10, ShitpostBot 8, gifs 3 and 3, memes 1), `meme-chaos-still`, `weird`, `gifs` and
  `inspirobot`. The slide types got them through the content generators; a format can map looks to its own
  (`PresentationSchema(looks=...)`, for the new formats); `talkgenerator formats --looks` lists them, and the
  formats' slide references (and the Skill's) name each recipe's image looks.
- **Flavour packs**: v4's sets of subreddits (gifs, memes, weird, pictures, old photos and people, book covers,
  places) and `cursed` (cursedimages, blursedimages, hmmm), `wholesome` (wholesomememes, MadeMeSmile,
  AnimalsBeingBros, aww), `bad-charts` (funnycharts, dataisugly, dataisbeautiful, charts: Reddit's chart slides),
  `medieval` (MedievalMemes, medievalart), `liminal`, `retro-futurism`, `accidental-art`, `pareidolia` and
  `corporate-cringe`; each is a source (`reddit:<pack>`) and a look. All their subreddits were checked on
  2026-11-07: each has pictures among its hot posts (r/MadeMeSmile few, mostly videos: hence r/aww in `wholesome`).
  Reddit's NSFW mark and the finder's NSFW words keep them safe for work.
- **Local analysis**, with Pillow on thumbnails (the sources' own: Unsplash's `thumb`, Pexels' 240 px, Pixabay's
  preview, Openverse's, Commons' 330 px, the Art Institute's 200 px IIIF, Reddit's preview, GIPHY's still,
  ShitpostBot's gallery copy; InspiroBot has none), at 96 pixels: brightness, Hasler and Süsstrunk's colourfulness,
  the share without colour (channels within 24 of 255), monochrome (that share at 0.85, or 0.6 at next to no colour,
  or coloured pixels sharing one hue at 0.995 or more at a colourfulness up to 0.4: calibrated on 75 thumbnails, in
  which Commons' black and white photographs had a gray share of 1.0, sepia ones one hue at 0.997 to 1.0, and
  Pixabay's colour photos one hue at 0.99 or less but for one nearly gray one), detail (mean edge strength) in the
  text area, four main colours, and a difference hash (64 bits; near-duplicates within 10). Looks taken are
  remembered in memory (2048 at most).
- **Checks** (`talkgenerator check`, and every render's report): an image of a class the policy doesn't allow is an
  error; a credit that doesn't name its open license, nearly the same picture on two slides, a vintage picture in
  colour without a monochrome treatment, and a calm backdrop with half again as much detail as it prefers are
  warnings; the report counts per look how many pictures have it (`looks`) and the images per license class.
- **Treatment**: a vintage picture that isn't monochrome gets its look's sepia in a theme without a filter of its
  own (`treatments.for_look`); the classic template keeps its pictures as they are.
- Not yet: icon sets for `illustration` (10.4: Iconify serves SVG only), and the vision pick (4.) and generated
  images (10.5), for which slots have room (`generate`). The museums' date and classification filters came with
  the new sources (10.4).
- **Live** (2026-11-07, `talkgenerator check`, every key, themed talks; the free OpenRouter router for the talks it
  writes; reports in the session's scratchpad, sample decks in the comparison folder's `15-v5-9997e28-image-looks`):
  - Classic talks on the 10 default topics (seed 1) and on 5 topics with seeds 2 and 3: 20 talks, 18 the same made
    one by one. The other two came out differently because Unsplash's demo key ran out of its 50 requests an hour
    while they were made: its cooldown kept it out of the one-by-one run. Talks by the free models (5 topics, seed
    2): 50 of 50 slides by the model, 5 requests, $0, 4 of 5 the same (Unsplash and GIPHY ran out during the first).
    With those two switched off (`DISABLE_UNSPLASH`, `DISABLE_GIPHY`): 5 of 5 classic talks and 3 of 3 talks by the
    free models came out the same (30 of 30 slides by the model, $0), without a finding.
  - `vintage`: 26 of 26 pictures in black and white or sepia (Reddit's old photos and Commons'). `calm-backdrop`:
    18 of 34 at most 0.08 of detail where the text goes, 2 busier than 0.12 (a warning; 3 of 9 in the first run,
    before the finder looked at more candidates when none was calm); every other look's pictures all had it.
  - `ted` (policy `open`): 36 images, all stock, none fair use; 1 of 3 the same (an Unsplash cooldown, and a quote
    or WikiHow statement that came out different the second time). Images by class over all runs: 266 fair use, 135
    stock, 4 public domain, 1 open.
  - Speed, the same 4 classic talks before (`be09a7e`) and after (Unsplash and GIPHY off, seed 5, themed, parallel,
    on this computer): with the search answers cached, a median of 16.6 seconds a talk against 16.2, and 106 calls
    against 97; cold, 37 against 39 seconds, and 421 calls against 163, most of them thumbnails (Reddit's previews,
    Pixabay's and Pexels' CDNs), which the second round had remembered. Search APIs: Pexels 8 against 5, the Art
    Institute 8 against 5, Openverse 7 against 0 (on the site: to watch, with Unsplash at 50 an hour).

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

As built (2026-11-07), each after reading its terms and trying its API; every one loads in a browser's `<img>` from
its own server, with a referrer and without (display `direct`), and its search answers are cached:

| Source | Key, limits | License class | Filters | What its terms and API turned out to be |
| --- | --- | --- | --- | --- |
| The Met (`met`) | none; "80 requests a second" | `public-domain` (CC0) | type (its `medium`), years (`dateBegin`, `dateEnd`) | v1's search was retired on 2026-10-01; v1.1's pages, and gives IDs only, so every object is a request of its own (12 per search, 4 at a time, cached 30 days); it ignores `isPublicDomain`, so objects are kept by their flag (copyrighted ones carry no image), and some IDs it lists answer 404; originals are 2 to 6 MB |
| Cleveland Museum of Art (`cleveland`) | none, no documented limit | `public-domain` (CC0) | type, `created_after`, `created_before` | its search carries the images; its web copies (about 900 px) are what slides take, as its print copies (3,400 px, 4 to 7 MB) take seconds to come; no CORS header (a browser may show them, not read their pixels) |
| Wellcome Collection (`wellcome`) | none, no documented limit | per image: `public-domain` (PDM, CC0) or `open` (CC BY) | years (`source.production.dates`), license; also colour | asked for PDM, CC0 and CC BY only (it has NC, ND and in-copyright images too, 21% of them); IIIF images in any size |
| Smithsonian Open Access (`smithsonian`) | a free api.data.gov key (`DATA_GOV_API_KEY`), 1,000 requests an hour | `public-domain` (CC0) | type (`object_type`) | `media_usage:CC0` keeps to CC0 images; IIIF images (1,600 px), about a second a search; its names come with their lives ("Thomas Eakins, American, b. Philadelphia..."), so credits keep what's before the first comma; its search for space finds the National Air and Space Museum's objects |
| NASA Image and Video Library (`nasa`) | none, no documented limit | `public-domain` | years (`year_start`, `year_end`) | NASA's own pictures aren't under copyright in the US; NASA asks to be credited, forbids implying its endorsement, and (since 2026-10-27) its insignia next to AI-made images, which talkgenerator doesn't add; pictures it notes as someone else's copyright are left out; titles that are only numbers give way to the description; originals over 15 MB are skipped |
| Flagpedia's flags (`flags`) | none | `public-domain` | | "in the public domain and can be used freely"; a link back appreciated (the credits give it); flagcdn.com's list of 306 names maps a country to its flag |
| Imgflip's templates (`imgflip`) | none to list them | `fair-use` | | `get_memes` lists the 100 most captioned of the last 30 days, without where captions go; search is premium; pictures shown from its server must link back to Imgflip (the credits link the template's page) |

Left out for now, and why:

- **Library of Congress**: its JSON API (www.loc.gov `fo=json`) answers programs with a Cloudflare challenge since
  September 2026 (its data-exploration issue 88), which talkgenerator doesn't work around; the Library grants
  exceptions for a User-Agent on request (ask.loc.gov), and its limits are tight (20 requests a minute, else an
  hour's block). Its pictures still come through Openverse's and Commons' collections.
- **Rijksmuseum**: its old API is gone (410), and its new one (data.rijksmuseum.nl) has no free-text search, only
  fields (mostly Dutch titles), gives IDs only, and lists works still in copyright: its collection stays in
  Openverse's `rijksmuseum` source, which the `museum` look searches.
- **Flickr** (Commons, the British Library's and the Internet Archive's book illustrations): API keys are for Pro
  subscribers only since 2025, and its rules ask for a notice that the app isn't endorsed by SmugMug, at most 30
  photos a page and no caching beyond 24 hours. Openverse has Flickr's openly licensed photos.
- **Iconify**: SVG only (no PNG), so icons need an SVG rasteriser (resvg-py, say), a new dependency; and an icon
  is less a slide's picture than a part of an icon grid, a slide type of its own.
- **Europeana**: needs a key; Openverse and Commons have much of it.

More subreddits joined the flavour packs (each checked for pictures among its hot posts, safe for work, and with a
name that reads fine in a slide's credits): `cursed` r/TIHI and r/Cursed_Images, `wholesome` r/rarepuppers and
r/Eyebleach, `bad-charts` r/Infographics and r/MapsWithoutNZ, `accidental-art` r/accidentalart and r/PerfectTiming,
`pareidolia` r/facesinthings, `old-photos` r/OldPhotosInRealLife, `memes` r/HistoryMemes and r/ProgrammerHumor,
`weird` r/Weird and r/notinteresting. Left out: the "...Porn" photography subreddits (their names), r/WTF and
r/AnimalsBeingDerps (mostly videos), r/ABoringDystopia (politics).

The museums share one filter vocabulary in a look's source parameters (`SourceUse.params`): `type` (painting,
photograph, print, drawing, sculpture) and the years `after` and `before`, which each source asks its search for in
its own words, the Art Institute's too (Elasticsearch terms). The new sources joined the looks they fit: `museum`
(the Art Institute 3, the Met 3, Cleveland 2, the Smithsonian 1.5, Openverse's museums, Wellcome, Commons'
paintings), `vintage` (the Met's, the Art Institute's and Cleveland's photographs before 1950, and the
Smithsonian's photographs, next to Reddit's and Commons'), `old-photo`,
`portrait` and `old-people` (the Met's and Cleveland's painted portraits), `space-science` (NASA 4, the
Smithsonian 1),
`illustration` (Wellcome's prints and drawings) and `weird-stock` (NASA's and Wellcome's odd pictures at 0.3 each,
without the look's "weird" words: the `ted` format's copyright-free punchlines). New looks: `meme-templates`
(Imgflip) and `country` (Flagpedia's flags and stock photos), which about-me slides take for where the presenter
comes from.

Live (2026-11-07, `talkgenerator check`, GIPHY and Unsplash switched off, themed talks): every new source found
pictures through the finder on its own (the Met's cat, Cleveland's street photograph, Wellcome's tooth-drawer,
NASA's pizza aboard the space station, Belgium's flag, Drake's template, and once the user's api.data.gov key was in,
the Smithsonian's teapot), and every new source's canary test passed. In whole talks:

- 6 talks by OpenRouter's free models (coffee, lighthouses and penguins; seeds 90 and 114, which the dice give a
  meme, a history slide and an about-me slide): 0 errors, 0 warnings, 6 of 6 the same made one by one, 59 of 60
  slides by the model, 6 requests, $0, a median of 28 s a talk. Every talk had its meme, with captions that fit
  their template ("The ice is cracking, the storm is here, the world is ending" / "This is fine"). On Trade Offer
  the model wrote "I receive:" again, which the picture says already: its boxes now say so, and the talk made
  again wrote "a warm egg" / "your dignity". The history slides' pictures came from Reddit's old photos but one,
  an Art Institute photograph found with the new filters; the models wrote scenes for where the presenter comes
  from ("ethiopian highlands village"), not a country's name, so no flag came up there.
- 8 classic `ted` talks (seeds 1 and 2) and 6 classic default talks (seeds 3 and 4): 0 errors, 1 warning, all the
  same made one by one; by the looks' weights, their pictures all came from the stock sites, Reddit and ShitpostBot.
- 3 classic talks allowing only public domain pictures (`--license_policy public-domain`, seed 5): 0 errors, 0
  warnings, 3 of 3 the same, a median of 45 s; their 33 pictures came from the Wellcome Collection (14), NASA (8),
  Openverse (8), the Art Institute (2) and the Met (1).
- About 21% of talks by a language model get a meme (300 seeds, simulated with the schema's own picks).

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

As built (2026-11-07, `talkgenerator.images.generation` and `talkgenerator.images.generators`; D38, D39):

- **Interface:** `ImageGenerator.generate(ImageRequest)`: a prompt, an aspect ratio (1:1, 3:2, 2:3, 4:3, 3:4, 16:9,
  9:16; a generator makes the nearest it can), a style, what to avoid, a seed and a quality (low by default) in; a
  `GeneratedImage` out, with its bytes, model, cost (as the provider says), moderation's flags, seed and revised
  prompt. Errors are `GenerationError`s: `GeneratorUnavailable` (no key, a key or model turned down, no credits, a
  server error), `GenerationRateLimited`, `GenerationRefused` (moderation's, or our rules'). `estimate_cost` gives a
  picture's list price (none for an unknown one, 0 for a local server's). Capabilities say whether a generator takes
  a seed, follows instructions (what to avoid goes in the prompt for OpenAI's and Gemini's models, as a negative
  prompt on local servers, and not at all for FLUX, which would draw what it names), and runs locally.
- **Adapters**, over plain HTTP (`requests`, through `http_util`: no SDK needed), checked against the providers'
  docs on 2026-11-07: `openai` (`POST /v1/images/generations`: sizes 1024x1024, 1536x1024, 1024x1536, quality,
  JPEG out, moderation `auto`, whose `moderation_blocked` turns into a refusal with its categories); `openrouter` (its
  Image API, `POST /api/v1/images`, sending of resolution, quality, output format and seed only what the model's
  `GET /api/v1/images/models/<model>/endpoints` says it takes, asked once, which also gives a per-picture price for
  a model priced by the picture; usage.cost is what a picture cost); `gemini` (`models/<model>:generateContent` with
  responseModalities IMAGE, an imageConfig and a seed; draft images marked as thoughts are skipped; a blockReason or
  an IMAGE_SAFETY finish is a refusal); `flux` (BFL's `POST /v1/<model>`, FLUX 3's aspect ratio and resolution or
  FLUX.2's width and height of about a megapixel, safety tolerance 2, polling the `polling_url` until Ready, Request
  Moderated or Content Moderated, its cost in credits at a cent each); `comfyui` (a text-to-image workflow in the API
  format with the server's first checkpoint, or `COMFYUI_WORKFLOW`'s own with placeholders, through `/prompt`,
  `/history` and `/view`) and `automatic1111` (`/sdapi/v1/txt2img`, with a negative prompt, switching checkpoints only
  when the spec names one). Specs: `provider[:model]`, as `TALKGENERATOR_IMAGE_GENERATOR` or `--image_generator`
  names them; a talk only generates when it's given one (D38).
- **Models and prices are config** (`talkgenerator/data/image_generators.json`, checked on the providers' pages on
  2026-11-07, and an `image_generators.json` in the config folder over it): OpenAI's gpt-image-2 (the default) $0.006
  a picture at low quality, $0.053 at medium, $0.211 at high (the 2.5 and 2.6 models are priced by the token only, so
  not listed); OpenRouter's gpt-image-2 (its default), FLUX 3 Image Klein $0.009 and Gemini 3.1 Flash-Lite Image
  $0.0336 (none free); Gemini 3.1 Flash-Lite Image (the default) and Nano Banana 2.1 $0.0336, 3.1 Flash Image $0.067,
  3 Pro Image $0.134, 2.5 Flash Image $0.039 (to be shut down on 2027-03-15; no free tier for pictures); FLUX 3 Image
  Klein (the default) $0.009, FLUX 3 Image $0.048, FLUX.2 klein 4B $0.014, 9B $0.015, pro $0.03, flex $0.05, max
  $0.07 (the first megapixel); OpenAI's gpt-image-1 was shut down on 2026-10-23. `talkgenerator formats
  --generators` lists them.
- **When:** only on planned slides (a language model's or a plan's), whose texts say what a picture is to show;
  classic talks generate nothing. Slots that prefer a generated picture (`ImageSlot.generate`): the weird hobby (on
  both about-me slides and its own), the about-me book's cover, history's two old photos and its made-up figure's
  portrait (in `ted` too), and the news story's photo. For those the language model writes a prompt (`<image>_prompt`,
  only in a talk that generates; `SlidePlan.prompts` in a plan), the stock photo is searched for as before and the
  slide comes with it, and once the slide is settled its picture is generated in the background (4 at once), taking
  the stock photo's place, and its credit's, when it's in. A planned slide whose images aren't found at all, after
  its query and its concept, gets them generated on its last try (which runs while it's settled), all of them or
  none, for looks talkgenerator knows how to ask for (photographs, paintings, illustrations, book covers; not gifs,
  memes or InspiroBot's posters). A slot that prefers a generated picture can be served without a source of its own
  (the book cover under `open`). The product shot for a pitch waits for the pitch format (milestone 7).
- **Limits:** 3 pictures a talk by default (`ImageBudget`, `--generated_images`, `TALKGENERATOR_GENERATED_IMAGES`),
  granted in the order of the slides as they're settled, the cache's included (so the same seed generates for the same
  slides, in parallel or one by one, the first time or again), and an optional dollar limit by list price
  (`TALKGENERATOR_IMAGE_COST_LIMIT`; a model without a known price is then not asked). The talk logs its estimate
  ("up to 3 pictures with openai:gpt-image-2, at about $0.0060 each: $0.0180 at most") before its first picture, and
  `generation.estimate(spec, budget)` gives it beforehand, for a settings page. The talk's ledger counts what was
  generated: `Usage.images`, `image_cost_usd`, `unpriced_images`, `failed_images`, apart from its requests.
- **Pictures:** credited "AI-generated with <model>" (the model without its provider: "gpt-image-2"), in the
  `generated` class, under the provider's terms (the deck's `license` and `license_url`; the credit doesn't name
  them), described by their prompt, kept as `generated-images/<hash>.<jpg|png>` in the cache folder with a JSON file
  of what made them, keyed by model, prompt, style, what to avoid, shape, quality and seed (only for generators that
  take a seed). The deck names a picture by that file, with display `copy` (D39). Their look at the bytes
  (`analysis.analyse`) lets a colour "old photo" turn sepia in a theme, as a found one does.
- **Safety** (`talkgenerator.images.safety`): a prompt is screened before it's sent: real people talkgenerator knows
  by name (`names.real_person`: dictators and famous living people, and the famous figures the name pack bends, by
  their whole name or their last name), "a celebrity" and the like, the talk's presenter's name, brands and
  trademarked characters (Disney's, Nintendo's, Coca-Cola, ...; a logo), gore and sexual content, and the words a
  slide shouldn't make light of (`slide_texts.sensitive`). Every prompt then asks for no real or famous people, no
  logos, brands or trademarked characters, no gore, nudity or sexual content, and no writing (but on a book cover).
  A talk whose topic is sensitive generates nothing; one whose topic the language model flags is classic, so it
  generates nothing either. A refused prompt, a picture moderation turns down, or a failed one, keeps the stock photo.
- **Streaming:** `stream_talk` sends `slide.updated` (`SlideUpdated`: the index of the slide.ready it replaces, and
  the slide, laid out as before by `DeckLayout.again`), and `talk.finished` once every picture is in. A cancelled talk
  stops what hasn't started generating.
- **The site's side** (talk-generator-web, not built yet): pass a visitor's generator with their key
  (`OpenAIImageGenerator(model, api_key=...)`, `OpenRouterImageGenerator(model, api_key=...)`, or a `client=` of its
  own, as its language models take a client), with an `ImageBudget`; show `generation.estimate(...)` before a talk
  spends their money; take `slide.updated` as it takes `slide.ready` (the slide at that index), and keep copies of
  its pictures (`display: copy`, which its `keep_copies` already handles, as `fetch_image` reads a local file); log
  the deck's `usage.images` and `image_cost_usd`. Never set `TALKGENERATOR_IMAGE_GENERATOR` on the server (D7, D38).
- **Live** (2026-11-07, with the user's OK for at most 10 pictures, $0.06, on OpenAI's gpt-image-2 at low quality):
  the first request got HTTP 429 `insufficient_quota` (the account had no credits: nothing charged), which now says
  "needs more credits" rather than a rate limit. With credits: one picture through the adapter, 1536x1024 JPEG
  (271 KB) in 13 s, exactly what was asked; then the three usual talks (cat, peanuts, time travel, seed 1, neon),
  written by OpenRouter's free models (one request each, $0), in 29 to 42 s each, each with 3 generated pictures
  (slide 3's two old photos of made-up moments in the topic's history, slide 8's news photo; 9 of 9 generated, none
  refused or failed, all embedded in the .pptx, credited "AI-generated with gpt-image-2"). By list price $0.018 a
  talk (the deck counts the square picture's price, $0.006: the 1536x1024 ones are $0.005), so about $0.05 for the
  whole check. The model's prompts were concrete and on the slides' texts ("a confused man in full medieval plate
  armor standing in a brightly lit modern grocery store aisle, looking at cereal boxes", under "Medieval Knight Found
  in Modern Supermarket"), with no real people or brands; a deck rendered again from its JSON took its 3 pictures
  from the cache and asked nothing. Sample decks: the comparison folder's `19-v5-c4484f9-generated-images`.
  Not tried live: OpenRouter, Gemini, FLUX and the local servers (their adapters are tested against fakes made from
  their docs), and a price per picture from OpenAI's token counts (its answer has them; the list price stands in).

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
  the per-slide fallback, and the paper baseline: `--planner classic --theme classic` (as built: `--llm none --theme
  classic --name_styles classic --persona none`) is the 2019 method with the
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
  arrive in order, and later slides get prepared in parallel. As built (2026-11-07): a slide is handed over whole,
  and `slide.updated` hands it over again, whole, at the same index and laid out as before, once a generated
  picture takes its stock photo's place (10.5); `talk.finished` waits for every picture;
  `talk.started` also names the language model that writes the talk (none: classic), and every image its size in
  pixels. What a browser can't do as PowerPoint does: split black and white at a picture's own median lightness
  (it can't read another site's pixels, so it splits at half), and bend text into an arch, a wave or an inflated
  shape (a slant it can).
- **The answer's order** (fixed on 2026-11-07): some models write the answer's properties in alphabetical order
  instead of the schema's, at every level. `dots-studio/dots-3-note-preview:free`, which the free router often
  picks, wrote `presenter_job`, `presenter_name`, `slide_2`, ..., `thesis`, `title`, `unsafe_topic`. A streamed
  talk took the spine as it was once the first slide was in, so it got a classic title (a WikiHow one: "Never,
  Ever Make A Good Pot Of Coffee") where the same answer made at once got the model's, its title slide's notes
  had no thesis, and slides came in before the unsafe flag. And in a talk of 10 slides or more, `slide_10` comes
  before `slide_2` in that order, which made slides that weren't in yet look skipped (they came out classic). Now
  the answer's order is alphabetical too: the spine is one object, `about`, and slide numbers have as many digits
  as the last one's (`slide_02` to `slide_10`). And a streamed talk waits for all of the spine (or the end of the
  answer) before it takes its title, the presenter's name and job, instead of taking what there is of it once the
  first slide is in: the spine comes first in either order, so `talk.started` comes as early as before, and a
  model that writes the spine last, or its fields one by one, still gives a streamed talk all of it (then
  later). Live (10-slide talks streamed with a $0 budget, as on the site, seed 1, one request each, $0): through
  the free router, 5 talks, 2 of which it gave to dots, whose spine came in alphabetical order inside `about`
  (`name_plays_on`, `presenter_job`, `presenter_name`, `thesis`, `title`, `unsafe_topic`), and 3 to
  `nvidia/nemotron-3.5-super-vl:free`, in the schema's order: every `talk.started` had the model's title, 50 of 50
  slides were the model's, and each talk started 4 to 13 s in, as soon as its first slide's part was in. Pinned to
  dots (`openrouter:dots-studio/dots-3-note-preview:free`, which then thinks as long as it likes, as a model named
  in the spec gets no effort: its answers began after 89 to 124 s, and one ran out of room after `slide_09`), 3
  more (coffee, medicine, bees): the model's title from the start in every one, 29 of 30 slides the model's, each
  talk started the moment its first slide came in. The same 3 on the code before the fix (`68c79e7`): every one
  started with a classic title ("Never, Ever Make A Good Pot Of Coffee", "Never, Ever Get Rid Of Carpenter Bees")
  where the model had written its own ("The Quantum Alchemy of Medieval Coffee"), no title slide had its thesis,
  and the slides came in from `slide_10` on; they were the model's all the same, as dots wrote the rest within
  5 s, faster than slides settle.
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
  Settled on 2026-11-07 (every source's images tried in a browser's `<img>`, with a referrer and without, and their
  terms read): each image's `display` is `direct` for Unsplash (its guidelines require hotlinking), GIPHY ("Do not
  proxy requests to GIPHY", nor store copies), Wikimedia Commons (hotlinking is allowed, if not recommended),
  Pexels, Openverse's hosts, Reddit, InspiroBot and ShitpostBot (all load); `proxy` for the Art Institute of Chicago
  (Cloudflare answers a request without its header with 403 and a challenge, and with it, the image); `copy` for
  Pixabay ("permanent hotlinking of images (using Pixabay URLs in your app) is not allowed", it asks apps to download
  the images they use, and its links stop working after 24 hours, while a deck's permalink lasts 7 days); and
  `local` for talkgenerator's own files. The user's call on Pixabay (D30): the site keeps a copy of a Pixabay
  image for as long as its talk (7 days), and the browser and the .pptx use that copy (talk-generator-web
  `8141582`). A streamed slide tells its images' sources that they were used once it's
  handed over (Unsplash's download tracking), as a PowerPoint does when it gets the slide. To weigh: GIPHY's terms
  forbid storing copies of its media, which a PowerPoint does by embedding a gif (as talkgenerator has since 2019),
  and the site keeps a talk's deck JSON, GIPHY links included, for 7 days. Its API docs (read 2026-11-07) also
  forbid caching its responses and media URLs, which talkgenerator stopped doing (D36), and want searches made in
  the client with what the user typed; more than a beta key's 100 searches an hour takes a review and a talk about
  pricing.
- **Lighter validation:** while streaming, an image gets checked with a probe (its headers and first bytes, for
  type and size) instead of a full download, which saves memory on the 600 MB box. The .pptx is only built when
  someone downloads it, and it's kept no longer than today's outputs (7 days).
- **Privacy:** hotlinked images let those services see visitors' IP addresses, which the site's privacy page
  should mention.
- **Concurrency:** LLM calls mostly wait, so the single slot can become several streams that share a few image
  workers (gunicorn threads), once memory use has been measured.
- **No preview deployment** (D31): since 2026-11-07 the site itself runs `v5`, installed from git by commit, so no
  release is needed for it.

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
- **Switches:** `DISABLE_LLM=1`, `DISABLE_IMAGE_GENERATION=1` (built: no generated pictures at all, even with a
  generator given), and `DISABLE_<PROVIDER>=1` per provider. The site never sets `TALKGENERATOR_IMAGE_GENERATOR`,
  and passes a visitor's own generator per talk (D38).
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
| Images | loads; not enlarged beyond 1.3×; no near-duplicates within a talk; credited with its license; license policy respected; its look's preference (black and white or sepia for `vintage`, little detail behind the text for `calm-backdrop`) | 100% (the near-duplicates, licenses, policy and looks checked since 2026-11-07) |
| Variety | distinct slide types and layouts per talk, no layout twice in a row; across seeds, the share of distinct titles and images | targets per format, set from milestone 1's measurements |
| Image fit | of the images searched for with a query whose source describes them (alt texts, post titles), the share that shares a word with its query (`talkgenerator check` counts them since milestone 2) | a rough signal to follow, without a bar |
| Determinism | the same seed with replay gives an identical deck JSON; serial equals parallel | 100% |
| Safety | blocklist hits in the output; edgy topics screened or falling back | no hits |
| Language | the text is in the requested language (stopword ratio) | every slide |
| Speed | time to first slide and total time, on the site's configuration | on the site, from the request: the title slide within 10 s and the first content slide within 15 s, also for the first talk after a restart (calibrated on 2026-11-07 with classic talks: 0.8 to 9.1 s, and 1.2 to 12 s; LLM talks by the free models: 3.6 to 4.9 s, and 5.6 to 7.1 s, but 19.8 s for both in the first talk after a restart, while the library loads) |
| Requests and cost | LLM requests and estimated cost per talk | on the site's configuration: $0, at most one request per talk |
| Memory | peak memory for a 20-slide talk on the site's configuration | under 450 MB (`MemoryHigh`): met on 2026-11-07 with slides one after the other, a process peak of 328 MB for the talk and at most 413 MB with its .pptx download, then back to about 300 MB (an LLM talk: 326 MB, and 395 MB with its download); not in parallel (444 MB of memory that isn't cache, and throttled) |

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
  or a commit), which is also how talkgenerator.com runs it (D31).
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
| 3 (done, 2026-11-07: theme families and extremes, procedural palettes with contrast repair, layouts and their variants (never twice in a row), image treatments, WordArt-style heading effects, text fitting with bundled metric twins, the shapes renderer with the classic animations (columns click by click), previews and contact sheets, the design checks and the local MCP server; 0 design findings on 792 benchmark decks in 12 seeds; thumbnails in CI left out, D29) | Themes and layouts | theme tokens and families, extremes on by default; procedural palettes and font pairs; layout variants; text fitting; image treatments; the `classic` theme; thumbnails and contact sheet in CI; the local MCP server | contrast and overflow checks pass on every theme |
| 4 (under way: `stream_talk()`, probe validation, display policies, presenter names in styles (5.10, for the site's settings) and what's typed read as a topic or a title (5.11, `topic_or_title=`, for the site's Automatic choice) are in; since 2026-11-07, talkgenerator.com runs v5 from GitHub (D31): talks stream into the browser, the .pptx is made on download, Pixabay's images are copied, and classic and LLM talks meet the speed and memory bars on the VPS (section 14), but for the first talk after a restart; left: deploying the streamed-titles fix (`be09a7e`: on the site, a free model that writes its answer's fields in alphabetical order put `slide_10` before `slide_2`, so slides 2 to 9 fell back to classic ones, or were left out of a Dutch copyright-free talk), the new settings with 5.10's and 5.11's options, and loading the library before the first talk) | Streaming and the web view | `stream_talk()`, display policies, probe validation; in talk-generator-web: the SSE endpoint, the Angular renderer, LLM talks by default with the classic switch, a language choice, Connect OpenRouter and pasted keys, .pptx on download, an Automatic topic-or-title choice (5.11), the site running `v5` from git (D31) | first slide on screen within the calibrated target on the VPS; a 20-slide talk under the memory bar; the downloaded .pptx matches the web view |
| 5 (under way: image slots and the finder, license classes and policies, aesthetic profiles with local analysis, and the first flavour packs are in, 2026-11-07; generated images too, on the user's own key or server, credited "AI-generated with <model>" in the `generated` class (10.5, D38, D39); and new sources (10.4): the Met, Cleveland, the Wellcome Collection, NASA, Flagpedia's flags, Imgflip's templates and the Smithsonian (with the user's api.data.gov key), with the museums' type and date filters and more subreddits; left: the vision pick, generated pictures on talkgenerator.com on a visitor's key, and the Library of Congress, Flickr and Iconify, which need an exception, a paid key or a new dependency) | Images | slots, aesthetic profiles and flavour packs, local analysis, license classes; new open and weird sources; AI image generation with the user's own keys; the optional vision pick | license policies enforced; profile checks pass (such as the grayscale share for `vintage`); generated images credited |
| 6 (under way: fourteen slide types are in, drawn as texts on shapes (D37, section 8); on 2026-11-07, benchmark talks over seeds that bring each of them up had no design, completeness, leftover or language findings: 63 classic talks, and 63 by OpenRouter's free models (620 of 630 slides by the model, at $0), plus 20 classic `ted` talks and 8 Dutch ones, where a long Dutch compound overflowed a narrow box (since, every new layout takes a 20-letter word in every theme, a Venn diagram's labels beside its circles when they don't fit in them); the only other findings were InspiroBot's and Reddit's live answers differing between a talk's two runs. talk-generator-web draws them all unchanged, and needs a small change to hold back what appears on a click in its presentations (merged into the site's master, not deployed yet). Memes with live captions came in later that day (D40); on 2026-11-08 they came to about half of all talks (D48, "I really love the generated memes"), and five slide types from real PowerPoint karaoke decks came in (D49: a fun fact, an acronym, a dare, a flowchart, a tier list), with no findings on them in 36 benchmark talks, 18 classic and 18 by OpenRouter's free models (179 of 180 slides by the model, $0, every talk the same made again), over six seeds and random themes; the same day, so did the user's other two ideas of 2026-11-07: personas that shape a talk (5.2, D47), and bolder themes with subtler, rarer image filters (section 9, D43 to D46). Left: the TED content pack, and section 8's other candidates and the karaoke catalogue's) | More slide types for TED-like talks | native diagrams, big numbers, quiz, memes with live captions, social posts and more; a much larger, curated TED content pack; memes more often; what real PowerPoint karaoke decks do; personas that shape a talk; bolder themes | every new slide type passes the checks in classic and LLM mode |
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
| D27 | Without `TALKGENERATOR_LLM`, OpenRouter's free models write talks when there's an OpenRouter key, and talks are classic otherwise: a paid model only writes talks when it's asked for, since a key alone (an `ANTHROPIC_API_KEY` set for other tools, say) shouldn't make talks cost money. A sign-in with ChatGPT (`talkgenerator login chatgpt`) goes first: signing in asks for it, and its requests count toward the user's plan instead of costing money per request. |
| D28 | `random` is the default theme: a talk that doesn't ask for one gets a theme its seed picks. `TALKGENERATOR_THEME` sets another default (`classic` keeps the 2019 template), and `generate_presentation(theme=...)` takes one per talk, which talk-generator-web can offer in its settings (`themes.catalog()`). |
| D29 | Milestone 3 closes without slide thumbnails in CI: the user reviews decks in PowerPoint and in the comparison folders of sample decks, and the design checks catch what can be measured (contrast, overflow, overlap). |
| D30 | talkgenerator.com keeps a copy of a Pixabay image for as long as its talk (7 days), the one exception to D22: Pixabay's terms don't allow permanent hotlinking, and its links stop working after 24 hours. |
| D31 | talkgenerator.com runs `v5` before 5.0.0, installed from GitHub by commit, instead of a preview deployment on a subdomain: the site's `master` deploys it. There, a talk's slides come one after the other (`TALK_PARALLEL=0`), and the site gives memory back after every talk and download, to stay under the box's 450 MB. |
| D32 | What's typed can be a topic or a title: by default the language model tells which, in the talk's one request, and picks the title among its own proposal and a few classic candidates, fixing what's off; the visitor can still say which it is (section 5.11). |
| D33 | Presenter names may be famous-name puns ("Albert Einstone" for geology), on by default: a historical figure's name bent to fit the topic, never the real name as it is, a living person's or a dictator's. Real historical figures' names as they are aren't a style. |
| D34 | Talks without a language model get a name from a small pack curated by hand (pun names by topic, and a few fun surnames and famous-name puns) when their topic matches one of its entries, and tracery's random names otherwise. |
| D35 | What's typed for a talk (Automatic, topic_or_title) stays its title only when it's clearly one: four words or more, or a question or exclamation, with its slips fixed. Anything shorter is the topic, or a premise, on which the language model builds a funnier, more specific title ("The French Revolution" deserves better than itself); a title in quote marks stays word for word. The talk's dice pick whether the classic titles go with a short input as options, as inspiration only, or not at all. |
| D36 | GIPHY's searches aren't cached: its API rules forbid caching its responses and media URLs. The other search APIs stay cached. |
| D37 | Milestone 6's slide types are built from the deck's texts, shapes and pictures, which the layout engine places, so every renderer draws them as it draws the other slides (talk-generator-web without changes); a classic deck draws them on the 2019 template's blank slide, laid out in the template's look. What appears on a click is a property of an element (`appears_on_click`), which a renderer that plays no clicks ignores. |
| D38 | A talk generates pictures only when it's given an image generator (`image_generator=`, `--image_generator`, `TALKGENERATOR_IMAGE_GENERATOR`), never because a key is set, and only on planned slides, whose texts say what a picture is to show: for the slots that prefer one, in place of a stock photo that stands in until it's in (or for good, when it's refused or fails), and for a planned slide whose images can't be found at all, on its last try. A few per talk (3 by default), granted in the order of the slides, the cache's included, so the same seed generates for the same slides; for a paid generator, a cost estimate by list price first, and an optional dollar limit. talkgenerator.com never sets a generator of its own: it passes a visitor's, with their key (D7). |
| D39 | A generated picture is credited "AI-generated with <model>", in the `generated` class, under its provider's terms (in the deck, not in the credit), kept on disk by model, prompt, shape and seed, and named in the deck by that file, which a browser can't load: its display is `copy`, as for Pixabay's pictures (D30), so an app shows it from a copy of its own. A prompt that names a real person, a brand or a trademarked character, or asks for gore or sexual content, is never sent, and every prompt asks for none of that. |
| D40 | Memes are captioned live by talkgenerator, never drawn into the picture: the template's picture from Imgflip (fair use, so not in talks without fair use), its captions as texts in boxes measured once per template (`data/memes.json`, 25 templates), and the template picked by the talk's dice before the language model writes its captions (a recipe can fix a slot's query). New image sources join only where their terms allow a talk to show them, without working around a bot check, and without the user's paying for a key. |
| D41 | Swedish (`sv`) is a talk language too, on the terms of D19 and D25: a language model writes the talk in Swedish, with talkgenerator's own words in Swedish; without one, the talk is classic and English. |
| D42 | Themes use open fonts from Google Fonts besides the installed ones: two pairings per family (not the extremes), which a member has two times in three. They're bundled, so they're measured everywhere, and embedded in every .pptx that uses them, whole, as uncompressed EOT (python-pptx can't embed fonts; PowerPoint for Windows showed one, regular and bold, on a computer without it). Each has an installed stand-in that its texts fit too, for where embedded fonts are ignored (PowerPoint for the web, Keynote). |
| D43 | Every theme family has a motif of its own (`talkgenerator.design.motifs`): a fixture on every slide and its big pieces on the title and section slides, drawn with the deck's own elements, which gained polygons, turned shapes, rounded corners, outlines, shapes without a fill and background patterns, drawn alike by PowerPoint, the previewer and talk-generator-web. Its texts are numbers, symbols and code (role `decoration`), not the talk's words; no decoration sits behind a text's letters unless the text is made to read on it. |
| D44 | Five new families, none for laughs: `hacker terminal`, `blueprint`, `chalkboard`, `newspaper` and `Swiss poster`; `kids` becomes a kindergarten's. The families that commit to a scheme pick one of a few palettes of their own; some families have title and section layouts of their own. The families keep their names, and a seed still picks a member. |
| D45 | Strong image filters (grayscale, sepia, duotone, black and white) only in the families made for them, and only where they fit: a family's filter can be for backdrops only, and black and white never goes behind a slide's texts. Other themes leave pictures as they are or lay a gentle tint over them (a warm or cool cast, their paper, their accent). |
| D46 | The design checks judge a text by what's behind its letters (its lines as the engine breaks them, as tall as their letters), where a shape over part of them counts and a background's pattern too, rather than by what's under its box's middle. |
| D47 | A talk's persona, which its seed picks (or the talk names; `none` for none), shapes the talk with a language model or without: multipliers on the format's slide weights by the generators' tags (none under 0.2, and about 1 on average over the personas, so the formats' mix holds), its kind of title (a hint for the model, and half of a classic talk's titles from the persona's templates), and weights over the default name styles with how the presenter goes by (an explicit `name_styles` goes alone), besides the model's voice and an angle of the persona's, the presenter's kind of job, multipliers on the theme families' weights for a random theme (an explicit theme goes alone), and favourite looks for some of the looks slides ask for, searched before the slide's own. The deck and `talk.started` record it. |
| D48 | Memes with live captions are what a TED-like talk that allows fair use has most often in its middle: four times the weight of the other slides there, two a talk at most (and two memes of any kind in ten slides), never of one template twice. Classic captions speak of a talk's topic as English does ("coffee", "penguins"), never with a verb that has to agree with it. |
| D49 | New slide types come from what real PowerPoint karaoke and battle decks, TED parodies and bad-PowerPoint humour have (a catalogue with its sources), drawn from the deck's texts, shapes and pictures (D37): one of each a talk, in its middle. Kinds that need a new element (diagonal lines) or text under the design checks' floor wait. |

D7 to D9, D13 and D15 to D26 were settled on 2026-11-05, D28 to D42 on 2026-11-07, and D43 to D49 on 2026-11-08; the
others follow from the design.

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

Checked on 2026-11-07, for the image sources of 10.4:

- The Met: [Collection API](https://metmuseum.github.io/), [open access](https://github.com/metmuseum/openaccess).
- Cleveland Museum of Art: [Open Access API](https://openaccess-api.clevelandart.org/),
  [open access](https://www.clevelandart.org/open-access).
- Wellcome Collection: [catalogue API](https://developers.wellcomecollection.org/docs/catalogue),
  [IIIF](https://developers.wellcomecollection.org/docs/iiif).
- Smithsonian: [Open Access API](https://edan.si.edu/openaccess/apidocs/),
  [api.data.gov](https://api.data.gov/docs/developer-manual/).
- NASA: [Image and Video Library API](https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf),
  [media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/).
- Flags: [Flagpedia's API](https://flagpedia.net/download/api), [terms](https://flagpedia.net/terms).
- Imgflip: [API](https://imgflip.com/api), [terms](https://imgflip.com/terms).
- Left out: [Library of Congress JSON API](https://www.loc.gov/apis/json-and-yaml/) and
  [its challenge](https://github.com/LibraryOfCongress/data-exploration/issues/88),
  [Rijksmuseum data services](https://data.rijksmuseum.nl/docs/search),
  [Flickr API terms](https://www.flickr.com/services/api/tos/), [Iconify API](https://iconify.design/docs/api/).
