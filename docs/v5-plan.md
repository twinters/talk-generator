# talk-generator v5: design and roadmap

Status: approved on 2026-11-05 ([section 17](#17-decisions-and-open-questions) lists the decisions). Milestones 1
to 7 are done, and so is milestone 8 but for its week on the site; 5.0.0 is next ([section 16](#16-milestones)).
Nothing ships until 5.0.0.

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
| Topic expansion | ConceptNet walk around the topic | things per slide that drift away and come back (D68: nouns, familiar, each of a family of its own, two steps out at most); at the Advanced level, the model picks or sharpens each slide's word with the spine in mind | classic walk (Datamuse, WordNet) |
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
name (particular generators, or nudge)". The talk's seed picks one of twenty-one personas (thirteen until D79; from a stream of
its own, `persona`), before the slides are picked. `persona=` names one instead (`--persona`, the MCP server's
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
- **Its formats** (2026-11-08, D61, the user's "shouldn't the format also be tied to persona's (...) although all of
  them should have some chance for all possibilities, albeit much lower than their preferred"): multipliers on the
  formats' weights, for a talk that leaves its format to its seed (`schema="random"`; section 7 has the odds). A
  startup founder has ×12 for `pitch`, a disgraced professor ×12 for `academic`, an over-passionate expert ×3 for
  `academic`; a kindergarten teacher's and a retiree's are under 1, so their talks are TED-like more often.
- **A past, for the retiree** (2026-11-09): the retired lighthouse keeper's every talk was about the lighthouse (both
  of the review set's had it in the title and on 5 and 6 of their 10 slides; the user: "why not retired person? Won't
  it nudge too much to lighthouses?"). The persona is a retiree now, "a retiree with strong opinions, who spent forty
  years working {past} (which comes up on a slide or two)", and the talk's dice pick the past among 16 (as a lighthouse
  keeper, a mail carrier, a zookeeper, a piano tuner, a submarine cook, ...: `Persona.pasts`, `Persona.lived`, on a
  random stream of its own, so other talks stay as they were). One of its three angles is about the old job, the
  others "why the topic was better in the old days" and the topic as the grandchildren explained it; its classic
  titles are an old-timer's ("Back in My Day, Cheese Meant Something"), and the model's are to be "about the topic
  rather than the old job (the title slide has that)". In three talks by OpenRouter's free models ($0), a zookeeper's,
  a forest ranger's and a submarine cook's, the old job was on the title slide's job line and one or two other slides
  (with "now and then" in the voice and no word on titles, on two to four, and in every title): "Curdled Wisdom:
  What My Grandkids Taught Me About Cheese", "When Umbrellas Had Soul: A Ranger's Lament", "Patience Beneath the Hull".
- **Eight more** (2026-11-12, D79, of the new personas, formats and looks proposed that day, which the user answered
  "let's do all of them (unless some of them don't work out great)"): a true-crime detective (`detective`: news,
  timelines, flowcharts and red flags; "The Case of Penguins"; newspaper and vintage paper themes, liminal spaces as
  its weird pictures), an infomercial host (`infomercial_host`: reviews, big numbers, before and after, the fine print
  as a wall of text; WordArt and neon; product shots as its neutral pictures), a nature-documentary narrator
  (`nature_narrator`: full-screen pictures, life cycles and fun facts, few words; dark minimal; places and wholesome
  animals as its pictures), a museum tour guide (`museum_guide`: history, timelines, pictures and quotes; vintage
  paper; museum art and accidental Renaissance), the best man or maid of honour (`best_man`: anecdotes, dares, posts
  and red flags; "To Penguins!"; old photos as its weird pictures), a game-show host (`game_show_host`: quizzes, tier
  lists, dares, polls and D78's Pick one; neon and WordArt; prizes as product shots), an alien anthropologist
  (`alien_anthropologist`: diagrams, charts of properties, life cycles and fun facts, as a field report from another
  planet; old photos of everyday human life as its weird pictures, space as its neutral ones), and IT support
  (`it_support`: error messages, flowcharts, red flags and acronyms; hacker terminal and blueprint; faces in things).
  Five are specialists of a format of their own (section 7, D79): the detective's court case, the host's infomercial,
  the narrator's nature documentary, the guide's museum tour and the best man's wedding toast, about a third of their
  talks each; the game-show host gives more infomercials and keynotes, the alien more documentaries and museum tours,
  IT support more all-hands. With 21 personas, every tag's multiplier still averages 0.91 to 1.31 over them (red flags
  the most favoured, KPI tiles the least) and every theme family comes up 0.82 to 1.21 times as often as without; each
  new persona's talks are in its favourite families 34 to 49% of the time (13 to 26% without). Rebased onto D76 to
  D78 the same day, the personas favour D77's families too (the detective and the conspiracy blogger the corkboard, IT
  support the 90s desktop, the consultant the spreadsheet, the influencer Y2K and the retiree 70s retro, as the
  planning session had them; and a founder's and a teacher's sticky notes, a narrator's, a best man's, a motivational
  speaker's and a life coach's glossy magazines, a game-show host's and a time traveller's 70s retro and Y2K), and
  weigh D78's slides of a picture to explain: D78's own multipliers for the thirteen personas it knew (which it left
  to this work: a conspiracy blogger's exhibits ×3, a kindergarten teacher's equations, an influencer's picks, a
  motivational speaker's befores and afters), and the eight new ones' (a detective's exhibits ×3, a game-show host's
  Pick one ×3, which takes the place of its two captioned pictures, an infomercial host's befores and afters ×3, an
  alien's and IT support's "What do you see?"). Every tag still averages 0.91 to 1.31 over the personas, every family
  0.82 to 1.22 times its share.

A talk can also say which personas its seed picks from (`personas=`, `--personas`; talkgenerator.com's settings switch
some off, D61): the seed picks among all of them first, and only when that one isn't allowed, again among those that
are. So a talk whose persona is allowed keeps it, whichever others aren't, and each allowed one still comes up as
often as the weights say among them. A persona named goes first, as a presenter's name goes before the name styles.

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
- At the Advanced level (D68, `talkgenerator.plan.outline`), the model plans the talk first, in an outline that's
  read while it's written: the spine (title, presenter's job, thesis) and a running gag, then for every slide its word
  to riff on and its idea, the point it makes. The slides are written as their ideas come in, in small batches (the
  second slide alone, then two, then three), each in a request of its own with the plan so far, in parallel. Five
  requests for a talk of ten slides, which comes sooner than a Basic talk; an outline that brings no spine, finds the
  topic unsafe, is declined or can't be afforded leaves the talk Basic.
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
Image generators get a sibling interface ([section 10.5](#105-generated-images)). A request can show pictures
(`Message.images`: an `ImagePart` has the bytes, which a cassette never keeps, and a name, which keys the recorded
answer instead), for the vision pick ([10.3](#103-aesthetic-profiles-and-smart-filters)): the `openrouter`,
`anthropic` and `openai` adapters send them as their APIs take them, and budgets count a picture as Claude does.

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
talkgenerator now does by itself. Left for after 5.0.0 (2026-11-09): a sign-in with Plus or Pro, its models' list,
and a talk (the default model, the first the account lists, and the default effort, `low`, are guesses until then).

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

A 10-slide talk as one call, at about 7,000 to 8,500 input and 900 to 2,700 output tokens with thinking included; at
the Advanced level, five calls (its outline and four batches of slides), at about 16,000 to 20,000 input and 1,700 to
3,000 output tokens in all (measured with Claude Haiku 5.5 and Sonnet 5.5 on 2026-11-09, D68):

| Route | Per talk, Basic | Advanced | Paid by |
| --- | --- | --- | --- |
| Classic (no LLM) | $0 | | nobody |
| OpenRouter `:free` | $0, one request from the daily quota | $0, five requests | nobody |
| Claude Haiku 5.5 | about $0.002 | about $0.003 | the key's owner |
| Claude Sonnet 5.5 | about $0.03 | about $0.06 | the key's owner |
| Claude Opus 5.5 | about $0.06 | about $0.12 (estimated, at twice Sonnet's prices) | the key's owner |
| Sign in with ChatGPT | part of the user's plan allowance | five requests of it | the user |
| Agent mode (Claude Skill) | part of the user's Claude usage | | the user |

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

On 2026-11-09, after the review set of 2026-11-08 (`32-v5-fdc736d-review-set`), where OpenRouter's free models wrote
a Swedish talk in English and copied hints' English examples ("such as 'Outline'", "Related work", "Method") into a
German academic talk, and the closing slides of talks in other languages said an English advice slip word for word:

- The same stopwords tell, as the answer comes in, whether its spine (the title, the thesis and the presenter's job,
  which come before the slides; the thesis is asked for in the talk's language now too) reads as English
  (`languages.reads_as_english`: at least three of English's telling words, and more than twice as many as of the
  language's own). Then no slide of it is looked for, the stream stops, and the model is asked once more, with a line
  saying the last answer was in English (`talk_request(answered_in_english=True)`); that second answer is kept
  whatever its language, as better the model's slides than pictures without text. The stopped request counts in the
  deck's usage (`llm.base.AnswerStopped`: a request of unknown price), as a free tier counts it.
- Every text field a slide asks for says the language ("such as 'Outline', in German"), but a choice of words.
- A talk in another language gets no dad jokes or advice slips (`facts.look_up`): asked for them translated, a free
  model still put "Sing in the shower." on a German closing slide. Useless facts, which a fun fact twists, it gets.

Made again, the three talks came out in their languages throughout, with no language findings (the free models
answered in the language at the first ask; the ask again has its tests). Startup words such as "Traction" and
"Flywheel" stay in a Dutch pitch, as Dutch pitches say them.

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

On 2026-11-11 (D74), at the user's "sometimes translations are weird, like 'graph' is translated to 'graf' in a
Dutch one earlier, and some are literal. How come? Bad LLM? Too small?", probe talks showed where such words come
from: 21 talks in Dutch, French and Swedish before the changes below and 16 after, on the same seeds, by the free
router (the site's Basic AI), Claude Haiku 5.5 at both levels and Gemini 3.8 Flash, each request and answer
recorded (about $0.10 in all):

- The words slides riff on. They come from English sources (Datamuse's related words, while ConceptNet's API is
  down), which took a topic in another language for an English word, or knew nothing of it: Dutch "regen" (rain)
  wandered to "renovation", "redevelopment", "healing" and "reset" (Datamuse's "regen" is regeneration), "kaas"
  (cheese) to "faas" and "aviation", "les vacances" to "primus", "opera" and "composer", and "frietjes", "fietsen" and
  "statistiek" nowhere at all. A topic typed in English wandered in English: "penguins" to the hockey team's "flyers",
  "hockey", "goaltender" and "lightning". Such a word ended up on a Dutch slide as it was, or as a look-alike: the free
  model's "de geheime goaltender" and "middeleeuwse flyers", Gemini's "Vloeibare Healing" and "de Grote Reset", and
  Haiku's Advanced talk on rain became one on soil that was "geherontwikkeld". "graf" for a graph is one of these:
  "graph" is a word to riff on of "algorithms" and "mathematics", both on the English list that talkgenerator.com's ↻
  button gave Dutch visitors.
- The request, all in English: hints with English examples ("such as 'Professor of Applied Sock Theory'": the free
  model's "Professoraat Middeleeuwse Avifauna"), the names of slide kinds ("alignment chart": Haiku's
  "uitlijningstabel"), and the facts, which are English: the free model put "Over duizend soorten kaas bestaan,
  geproduceerd in verscheidene landen" (English's word order) on a Dutch slide, and "There are over 58 million dogs in
  the US" on a French one.
- The models. On the very same requests, Haiku and Gemini told those facts in natural Dutch and French ("Er bestaan
  meer dan duizend soorten kaas") and turned the hockey words into "IJshockeydoelman" and "pamfletten", where the free
  router's models wrote non-words and word-for-word phrases ("Goudgebarsten", "Hoofdleraar", "Strekking van de ziel"),
  and dots-3 mixed English into Dutch sentences ("Kijk, hier comes de netwerk!", "Wat mijn vader me always zei").
  The free router picks between the only two free models on OpenRouter that take a strict JSON schema,
  nvidia/nemotron-3.5-super-vl and dots-studio/dots-3-note-preview (2026-11-11). Haiku and Gemini put English Title
  Case on Dutch and French titles ("Rijpen naar Rust: Word de Kaas van je Leven"), and Gemini once dropped French
  apostrophes ("l accent").
- Not talkgenerator's own words (plan.languages), which read as native, nor the content packs, which only classic
  talks use (in English).

So, D74:

- A talk in another language wanders from what its topic is in English (`slide_topic_generators.english_name`): the
  topic as typed when it reads as English (each of its words one that English knows at least as well as the
  language), or else the title of the English article that its own Wikipedia's article links to, looked up without
  the article it starts with first ("les vacances": Vacation; "l'escargot" as typed is Matisse's "The Snail"),
  without brackets, never a disambiguation page (Dutch "Regen" links to one; the search finds "Regen (neerslag)",
  Rain), within three seconds; when there's none, its seeds don't wander. "kaas" now wanders to curd, cheddar, whey
  and crackers, "frietjes" to fryer and coleslaw, "les vacances" to resorts, beaches and cruise. The lookup is lazy (a
  seed generator that doesn't wander asks nothing), and a slide's stand-in pictures of the topic are searched in
  English too. Wikipedia misses now and then ("la colo", a summer camp, is Mount Colo), and Datamuse knows little of
  some words ("fika": "fly and flop"), but a wrong English word to wander from is rarer than a wrong reading was.
- The request says which of its words are English: a slide's word to riff on ("A word to riff on: umbrella
  (English)"), a fact ("(in English: tell it in Dutch)", with "in your own words, as a Dutch speaker would, never in
  English and never word for word" in the facts' line), a hint's example ("a title such as 'Live demo' (in English:
  yours in Dutch)", as a free model put the keynote's "Live demo" and "Introducing: RegenMax" on a Dutch talk's
  slides), and an Advanced outline's offered words ("Its words (English)"), whose riffs it asks for in the talk's
  language (their ideas stay English). A slide's concept, which
  is searched for pictures, is asked for in English words.
- It asks for the talk as a native speaker of the language writes it for its speakers (`prompt.native_line`, in the
  header of a Basic request, an outline and a batch): in the words and idioms they use, never word for word from
  English, no English words left in, no look-alikes, with one of the language's own (`Language.false_friend`: "a
  graph is a 'grafiek', never a 'graf' (a grave)", Spanish "'embarrassed' is 'avergonzado', never 'embarazada'"), the
  request's examples and English words to be said anew, and a title's capitals as the language has them
  (`Language.capitals`: the first word and names, and in German every noun). English requests are as they were.
- A leading article doesn't count toward the four words that make what's typed a title (`titles.clearly_a_title`):
  French says its topics with one ("le Tour de France", "la cabane à sucre"), and "the office coffee machine" is a
  topic for the model to title too.
- The spelling fixes of what's typed (`word_frequency.fix_spelling`) took rare words of a language for misspellings of
  more frequent ones a letter away, and the model was told the typed topic meant those: "os polvos" (octopuses) was
  "os povos" (peoples), "i polpi" "i colpi" (blows), "lämlar" (lemmings) "lämnar" (leaves), "verkeerskegels" (traffic
  cones) "verkeersregels" (the rules of the road). In another language than English, a word the language knows now
  only gets its accents put right ("faglar": "fåglar"); a word it doesn't know is fixed as before ("pingvner").
  English is as it was.
- Every language has its own topic list (`data/topics.<code>.txt`), for the ↻ button of talkgenerator.com (which gave
  English topics in every language), `topics.random_topics(language=)` and `check --random N --language`: Dutch 427
  topics, French 433, German 428, Spanish 436, Italian 422, Portuguese 432 and Swedish 443, written for this by Claude
  (one language each, then read through), in the sections of English's list: about two thirds of English's topics
  that say well in the language, in its own words and with its articles where it says them ("les pingouins"), and a
  third from its speakers' own lives (the Netherlands and Flanders: het frietkot, pistolets op zondag, op kot gaan and
  op kamers gaan; France, Belgium, Switzerland and Quebec: la drache, la cabane à sucre; Germany, Austria and
  Switzerland: die Kehrwoche, der Röstigraben; Spain and Latin America; Italy and Ticino; Brazil, Portugal and a little
  of Angola, Mozambique and Cape Verde; Sweden and Finland's Swedes), harmless as English's (no living people, brands,
  alcohol, politics, disasters, nor anything contested such as Zwarte Piet). Each one is read as typed, as the site
  reads a topic it suggests: none has a comma (which makes several topics), none is changed by the spelling fixes
  (tests/test_topics.py).

After, on the same seeds: Gemini's Title Case titles went from 5 in 5 talks to none in 4, Haiku's from 1 to none,
and the English words to riff on that ended up on slides from 9 in 21 talks (flyers, hockey, goaltender, healing,
reset...) to 3 in 16 (cheddar, ghee, whey: cheeses Dutch says so too, and the free model's "De Essentie van de
Whey"). The talks stayed on their topics: Haiku's Advanced rain talk riffed on "neerslag", "schaduw" and "hagel". What
stays is the free models': dots-3 still mixed English into Dutch ("niet always") and capitalised every word of its
titles, the instructions notwithstanding; and on the sample decks (folder 43), nemotron still kept an English word to
riff on that was marked English ("les fells sont maudits") and dots-3 the keynote's "Live demo" and "One more thing:"
(which Dutch keynotes borrow too), while Gemini wrote "Maak kennis met WolkSoep One" and "En nog een ding". A better
free model would write better Dutch, but the free router can
pick none: Google's Gemma 4 (free, and made for many languages) takes JSON without a strict schema, so OpenRouter
turns talkgenerator's request down for it (no endpoint for its parameters), and asked with the schema as text, its
free endpoint answered 429 for ten minutes on end (2026-11-11).

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
| `famous_pun` | yes (D33) | a famous name (from history or today, never a dictator's) bent to fit: "Albert Einstone" for geology, "Vincent van Goat" for goats, "Bread Pitt" for baking |
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
  ("Presenter Name", in the talks' languages), names a dictator (a short blocklist, which word beginnings match
  too: "Pol Potter"), is a famous living person's real name as it is ("Dr. Bill Gates", "Prof. Chomsky": a pun on it
  goes), or is the real name of a famous person whose name the pack bends ("Marie Curie"). Then the talk gets the name a talk without a model gets.
- **Famous living people** (`names._LIVING_PEOPLE`, since 2026-11-08, when a free model named a keynote's presenter
  "Umbrella Chomsky"): 175 that models reach for, from presidents to chefs. A presenter's name may pun on them, as
  the user said later that day ("I'm fine with that": till then such a name was turned down, and the request asked
  for a pun on someone no longer alive): "Umbrella Chomsky", "Taylor Swiftly", "Bread Pitt" and "Bill Grates" go.
  Their real name as it is doesn't (`names._real_living_name`): their first name and surname in a row ("Dr. Bill
  Gates", "Mary Berry"), or, titles and initials aside, all of their name ("Yuval Noah Harari", "Beyoncé") or what
  of it is theirs alone ("Prof. Chomsky"); an ordinary name stays ("Dr. Emma Swift", "Dr. Gates"). A test holds
  every classic surname (18,839) and first name (2,297) to that: only Mao goes. The request asks for a pun on "one
  famous person that everyone knows, from history or today", "never the real name as it is, and never a dictator's
  or a criminal's". The same list keeps generated pictures from showing them, puns and all (`names.real_person`): a
  name that's theirs alone counts on its own ("Chomsky", "Oprah", "Zuckerberg"); their ordinary names only together,
  the first name before the surname, as they are or with one of them bent into what no classic name is
  (`names._bent`: starting with the name's first five letters, or a letter off it, two off a long one): "Taylor
  Swiftly", "Gordon Hamsay" and "Tailor Swift" are them, "Dr. Emma Swift", "Tim Cookson" (a classic surname) and
  "Greta Gosling" (a young goose) aren't.
- **The talk's language.** The model writes the name in it, with wordplay that works in that language.
- **Without a model** (none configured, the quota used up, a refusal, or a name that won't do), the name comes
  from talkgenerator's own pack (`data/text-templates/presenter_names.json`, D34): 273 names by style and topic,
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

Live on 2026-11-08, after "Umbrella Chomsky" and with the famous living people turned down: ten famous-name puns
(eight by the free models, two by Claude Haiku 5.5, on topics that tempt puns on the living: linguistics, geese,
cooking, rockets, tennis, pop music, umbrellas, tidying up): nine bent someone who died long ago ("Dr. Leonardo da
Goose", "Nikola TeslARocket", "Dr. Beethovpop", "Prof. Sinta-crates", on Socrates) or no one ("Dr. Umbra the
Scholastic"), and tennis got "Serena Serve", an ordinary first name and a word, which stays. None had to go.

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
  user typed it: the talk's topic, or a premise for it)`, and its spine asks for `a title of your own for the talk,
  in English: funnier and more specific than what the user typed, building on it`, and the model's title goes (its
  own_title rather than an echo of what was typed). The request has no line on the title since 2026-11-08: Claude
  Haiku took its `Title: come up with one, ...` for the title ("Come Up With One: Retrocausal Roasting in Arabica
  Beans", in 3 of 12 talks), and so a talk on a topic given as such has none either (its spine asks for a title of
  the model's own), where a title given as such is the request's `Title:`. `talkgenerator check` warns about a title
  with the request's words about a title in it (the `title` check). The topics are what was typed. A misspelled
  input comes with what it means (`"pengiuns" (as the user typed it, meaning "penguins": ...)`), as the model
  otherwise kept the typo in its title now and then.
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
  Penguin". That helps the classic slides and titles too. And only the actions about the seed, none of the worst
  (D55): wikiHow pads a search it knows little about with its most popular how-tos, which titled a lighthouse talk
  "Never, Ever Make Sex Better". Crude ones about the seed stay.
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

No timing variants: the user decided on 2026-11-08 against Pecha Kucha (20 slides of 20 seconds) and Ignite (20
slides of 15 seconds), and against slides that advance by themselves ("I don't like the automatic progressing").

Decided: TED-like talks get every improvement first, and the new formats come after them: in milestone 7, or in
5.1 if the TED work takes longer. The format machinery itself exists from milestone 2, since the TED talk is a
format too. Every format also works in classic mode through its content pack
([section 11](#11-text-sources-and-content-packs)), so formats cost nothing without an LLM.

**The first two formats** (2026-11-08, D56): the startup pitch (`pitch`) and the academic conference talk
(`academic`), which set the pattern that the corporate all-hands and the product keynote followed the same day (D59,
below; Pecha Kucha's timing is out, at the user's word). A format is a presentation schema with a `Format`
(`talkgenerator.schema.formats`, a module per format):

- **A brief for the language model**, on a line of the request of its own ("The format: a startup pitch to investors,
  as at a demo day: the problem, the solution, the market (TAM, SAM and SOM)..."; the TED-like formats have none, and
  their requests stay as they were), and what its titles and its presenter's job are like, with the persona's: a
  pitch's title is "like a startup pitch's title: the startup's made-up name and its one-line promise", and its job
  the presenter's role at the startup; an academic talk's title is a paper's, with a colon and a dry subtitle, and its
  job an affiliation ("the chair they held before the scandal, in an absurdly specific field, given as an
  affiliation, as on a paper"). The format's catalog says them too, for agents writing plans.
- **Its favourite personas and themes**: weights over the personas for a talk whose seed picks one (the startup
  founder ×6, the consultant ×2, the influencer and the motivational speaker ×1.5 for a pitch; the disgraced professor
  ×6, the over-passionate expert ×2.5, the medieval historian ×1.5 and the time traveller ×1.3 for an academic talk:
  the founder presents 30% of the pitches, against one talk in thirteen before, and every persona still presents
  some), and multipliers on the theme families, with the persona's (`startup` ×4 for a pitch, `academic` ×5 for an
  academic talk). A TED-like talk's seed picks the persona it picked before.
- **An arc** (`talkgenerator.schema.formats.arcs`): the parts its talks go through, in order, each with the fewest and
  the most slides it has, and a rank. The arc lays out a talk of any length from its length alone, the same in every
  run: a short talk keeps the parts of the lowest ranks (a five-slide pitch has its problem, solution, traction and
  ask; an academic talk its outline, method, results and questions), a longer one gives them more slides, by rank, up
  to their most (a pitch's problem, solution and traction two each, an academic talk's method two and results three),
  and what's left are free slides between the parts, for the format's other slides (memes, gifs, press, a quiz, quotes,
  fun facts, real charts from the internet). A part's slide generators weigh in on its slides only, so a persona's
  multipliers move a part's slides between its kinds (a founder's traction is figures on tiles more often than a hockey
  stick) but never out of their part: every persona keeps the arc, in classic talks and planned ones alike. The
  format's other generators stand in, at a hundredth of their weight, for a part's slide that none of the part's
  generators can make, and `talkgenerator check` warns of a talk that misses a part, or has one out of order. A
  format's tag caps let each kind of slide come once, so that a part of two slides has two kinds.

Their slides reuse the slide types there are, with recipes and classic texts of their own. A pitch's problem is a bold
statement or an alarming statistic (a big number); its solution the product in one photo (a picture that prefers to be
generated, 10.5's product shot), life before and after it, or how it works; its market TAM, SAM and SOM in a funnel, or
one enormous number; its business model pricing plans on KPI tiles, a flywheel (a cycle) or its revenue streams (a pie
chart); its traction a hockey stick (a trend chart), figures on tiles, or a happy customer's post; its competition a
2×2 matrix with the startup alone in its best corner, or a ranking it wins; its team three photos of people with
made-up roles, or an org chart whose boss is the punchline; its roadmap a timeline, the ask a big number and the closing
"Questions?". An academic talk's outline is an agenda; its related work a Venn diagram with this work where the fields
meet, a 2×2 matrix of earlier work ("Okafor et al. (2019)"), or the field's history; its method a diagram of its
steps, its equation over a photo, or its setup's odd photo; its results a ranking that its method wins, a correlation
and a line over time, each with a suspicious p-value in its title, or one p-value as a big number ("p = 0.049"); its
limitations an iceberg or an admission over a photo; its future work a timeline, the research cycle, or a flowchart
whose every answer leads to more research; its acknowledgements three photos or a list, its references a list of
made-up references, and questions. One type is new, as nothing drew a method: the **process**, three to five steps
joined by arrows, appearing one by one, the last one the punchline (an academic talk's method, how a pitch's product
works), side by side when their words are short enough for the boxes, and else one under the other, on bands (as
German and Dutch compounds need); a TED-like talk has none yet. A classic pitch's startup and a classic talk's method
get made-up names from the topic ("PenguinBase", "AutoPenguin"), the same on every slide and in every run. Each format
has a content pack (section 11), a grammar per part of its arc: the pitch's 687 templates in 67 slots, the academic
talk's 591 in 60, linted as the TED pack is.

Checked on 2026-11-08, without GIPHY and Unsplash and in random themes: 42 classic talks (both formats, eight topics,
five seeds) had 0 errors, and 5 warnings of one template that said "None of them" (reworded since); 20 by OpenRouter's
free models (six topics, four seeds; 199 of 200 slides by the model, one request a talk, $0, 12 to 39 seconds a talk)
had 0 errors and 0 warnings; every talk came out the same made again. The models' pitches read
as pitch decks ("ChronoLoops: We Fix Your Yesterday Before It Happens", a market from "$4.2T - everyone with a past" to
"$12M - people who admit it", an ask "to build the first franchise in 1994", a closing "Bring money. We will spend it
yesterday."), and their academic talks as conference talks ("Penguins may not consent to mindfulness" under an
iceberg's water, "We occasionally misplace the 14th century" as a limitation). What they needed: a big number's label
repeated its number ("73% / 73% of Antarctic research stations...") and a job its presenter's name, which the hints and
the title slide now keep out; and texts too long for their places were cut mid-phrase, the affiliation of every talk
("Professor of Serenity Studies, Department"), roles in brackets ("Kaito Tanaka (Head of Temporal") and references
("Journal of Caffeine and"): the hints now ask for a few words, and a cut ends after a comma when no clause ends where
it keeps half the text, and before a bracket it would leave open. The second round's affiliations read whole ("Professor
of Delayed Productivity", "Chair of Subterranean Dynamics") and its references were short ("Doe et al. (2022) Journal
of Delay"); what it still had, a big number without its unit ("50000"), and matrices whose quadrants restated their
axes, the hints now ask for too.

**The last two formats** (2026-11-08, D59): the corporate all-hands, or quarterly business review (`corporate`), and
the product keynote (`keynote`), on the same pattern and with no new slide type. An all-hands is a company whose
business is the topic, as its leadership presents the quarter to everyone: its arc goes from the agenda (or an
executive summary nobody can read, the TED pack's wall of corporate jargon) through the KPIs against their targets
(figures on tiles; the target's line climbing and the actual results, on a click, falling away from it; the results by
region, which an unlikely team wins by far; one headline number; or the sales pipeline, a funnel down to "1 deal (my
uncle)"), the quarter's wins (three office photos, the CEO's post, or customers' reviews, a one-star one last), the
roadmap (a timeline, the new process, or the planning cycle), an org change (the new org chart under "The coffee
machine", the new hierarchy as a pyramid, or the company before and after: "12 teams", then "12 teams, new names") and
the synergies (a Venn diagram, or a 2×2 matrix of priorities) to the ask of everyone (a bold statement, or "110%") and
Q&A. A five-slide all-hands keeps its KPIs, its wins, its roadmap and Q&A; from ten slides on the KPIs get a second
slide, and from eleven the wins. A keynote launches a product made of the topic: a big opening statement (over a
photo, one huge number, or a greeting over a full-bleed photo), the one idea (a bold question, or a Venn diagram with
the product where it all meets), the reveal (the product in one photo, a picture that prefers to be generated, or
full-bleed), its features (three photos, specs on tiles, or a chart it wins by far against "A very fast horse"), a live
demo (that crashes, as a fake error message whose last button is "Blame the Wi-Fi"; how it works; or an odd photo to
present as the demo), the price (one big number, the models' prices, or when it ships), the "one more thing" (said over
a photo, or a second product, full-bleed: "One more thing: Penguin Neo for dogs") and a closing line. A five-slide
keynote keeps its opening, the reveal, a feature and the one more thing, and the reveal and the one more thing stay
longest. The management consultant presents an all-hands most often (×6; the startup founder and the motivational
speaker ×1.5, the life coach ×1.2), the startup founder and the motivational speaker a keynote (×5 and ×3.5; the
influencer ×1.5, the time traveller ×1.2); their themes are `corporate` (×5) and `clip-art corporate` (×2.5), and `dark
minimal` (×5) and `clean keynote` (×2.5), more often. An all-hands' photos are office stock photos (`corporate-stock`,
else plain ones). Their classic texts are content packs (section 11), with a made-up company and product named after
the topic ("Penguin Holdings", "Penguin Neo"). Two things the arcs needed: an all-hands' ask has no tags of its kinds,
as a long talk's free quotes and its headline number took the statements' and the big numbers' caps before it came
(as an academic talk's references keep clear of its outline's agenda); and a keynote's classic title launches the
product in words of its own, since its reveal introduces it.

Checked on 2026-11-08, without GIPHY and Unsplash and in random themes: 60 classic talks (both formats, twelve topics,
seeds 1 to 7, of 5, 10, 15 and 20 slides, four with the `open` license policy) had 0 errors and 5 warnings, all of
calm backdrops (too light, or with detail where the text goes); 20 by OpenRouter's free models (198 of 200 slides by
the model, one request a talk, $0) had 0 errors and 2 such warnings, and 4 by Claude Haiku 5.5 (40 of 40, $0.006 in
all) 0 errors and 2; every talk came out the same made again. The models' all-hands read as all-hands ("Q3 Review:
Moving Forward by Looking Backward", "The Council of Birds" at the top of the new hierarchy, the ask "Everyone please
avoid meeting your past self this quarter", a CEO who "watched a seal eat lunch today"), and their keynotes as keynotes
(BrewLine, whose demo "has achieved sentience and refuses to serve you", with buttons "Abort Timeline", "Recall Bean"
and "Sip Anyway"). What they needed: three of four product shots said "It's here." and every CEO's post began "Humbled
and grateful", both copied from their hints, which no longer have them; a bar named "Emperor Elite (Punchline)"; an
initiative in a quadrant cut to "Arctic Expansion (High Impact", as a cut at a comma or a clause's end didn't keep
brackets closed (it does now); and Claude Haiku's job "Dr. Harold Beanmore, Chief Chrono-Roaster" under the name
Harold Beanmore, which the title slide now drops the name from, title and all. One sample deck by Claude Haiku came out
classic but for its title (its answer was paid for, and none of its slides was read), while the same talk made again
came out whole: Anthropic sometimes refuses that talk's schema as too large a grammar, Claude then gets it as text, and
given it so, Haiku wrote every slide inside the spine's object rather than beside it. Slides inside another object of
the answer count now (the recorded answer, replayed, makes 10 of 10 planned slides), and a talk whose answer has no
slide to read says what the answer brought in a warning.

**The format from the persona** (2026-11-08, D61). A talk can leave its format to its seed: `schema="random"`
(`--schema random`, the MCP server's `format="random"`; talkgenerator.com's talks do). The seed picks the persona
first, as for a TED-like talk (uniformly, among the personas the talk allows), and then the format, from a stream of its
own (`format`), so the persona, the theme and the slides draw what they drew before, and a talk of schema random with
the persona it names is the very talk of the format its seed picked. The odds are `FORMAT_WEIGHTS` (in
`presentation_schema_types`: the TED-like talk 8, the pitch, the academic talk, the corporate all-hands and the
product keynote 1 each) times the persona's multipliers (`Persona.formats`, 5.2); without a persona, 67% of the
talks are TED-like (the odds of 2026-11-08: D63 made the TED-like talk more likely, below):

| Persona | TED-like | Pitch | Academic | All-hands | Keynote |
| --- | --- | --- | --- | --- | --- |
| startup founder | 33% | **50%** | 4% | 4% | 8% |
| disgraced professor | 35% | 4% | **52%** | 4% | 4% |
| management consultant | 33% | 8% | 4% | **50%** | 4% |
| motivational speaker | 34% | 6% | 4% | 4% | **51%** |
| over-passionate expert | **57%** | 7% | 21% | 7% | 7% |
| influencer, time traveller, former athlete | **59% to 62%** | 7% to 15% | 4% to 11% | 7% to 12% | 15% |
| the other five | **64% to 83%** | 3% to 8% | 4% to 16% | 3% to 9% | 5% to 17% |
| over all thirteen | 57% | 10% | 11% | 9% | 13% |

Every format keeps at least 3% with every persona, as the user asked, and over all the personas almost 6 talks in 10
stay TED-like: with five formats the TED-like talk's weight of 6 left only half, and the user wanted "a bit higher"
(2026-11-08), so it's 8, which still leaves each specialist's favourite first, at about half of their talks. Only the formats for talks take part. `ted` doesn't: it's the TED-like talk with copyright-free images
only, a choice of license rather than of format, which a talk makes with `license_policy="open"` whatever format its
seed picks (the arcs need no image that's fair use, and the TED-like talk drops the slides whose images the policy has
no source for, as `ted` does); nor do `interview` and `test`. A format named goes as before, its persona weighted by the
format's `personas` (D56): the two directions differ, and both are deliberate, as a caller who names the format wants its
favourite presenters, and one who leaves it wants the presenter's favourite format. The deck's `schema_name`, the
MCP server's report and `talkgenerator check`'s metrics name the format the talk got. The corporate all-hands and the
product keynote joined `FORMAT_WEIGHTS` (×1 each) as they came in (merged together), with the consultant's ×12
for `corporate`, the motivational speaker's ×12 for `keynote`, ×2 keynotes from the founder, the athlete, the life
coach, the influencer and the time traveller, and fewer all-hands and keynotes from the kindergarten teacher and the
lighthouse keeper (a retiree since 2026-11-09).

**More TED-like talks, and pictures on slides of text** (2026-11-09, D63), after the user reviewed 35 sample talks:
"Increase odds of our TED scheme more", "lower the overall odds of [academic] and startup [pitch]", pitch, KPI,
financial and corporate decks with "way too many textual" slides "while it's often images that perform better",
academic talks "pretty boring with mostly boring text and a lot of superfluous slides", and "big number slides should
also have random image in background, and actually most boring text slides should have random image that is somewhat
related, can use multiple different generators for each".

- *The odds*: `FORMAT_WEIGHTS` is now the TED-like talk 20, the pitch and the academic talk 1 each, the all-hands and
  the keynote 1.5 each; the specialists' multipliers are ×15 (founder, professor) and ×10 (consultant, motivational
  speaker), the passionate expert's academic ×2.5, and the smallest ones 0.5 to 0.7 (they were 0.3), so that every
  format keeps at least 2% with every persona. A specialist still favours their format far more than anyone else does
  (37% to 38% of their talks, 5 to 10 times the other personas' average), but no longer in most of their talks: half of
  them are TED-like. Over all thirteen personas, 70% of the talks are TED-like (71% over 2,000 seeds, picked as a talk
  picks them), 80% without a persona:

  | Persona | TED-like | Pitch | Academic | All-hands | Keynote |
  | --- | --- | --- | --- | --- | --- |
  | startup founder | 49% | **37%** | 2% | 4% | 7% |
  | disgraced professor | 51% | 3% | **38%** | 4% | 4% |
  | management consultant | 51% | 5% | 3% | **38%** | 4% |
  | motivational speaker | 51% | 4% | 3% | 4% | **38%** |
  | influencer, time traveller, former athlete | 74% to 75% | 4% to 7% | 2% to 6% | 6% to 8% | 11% |
  | the other six | 76% to 87% | 2% to 4% | 2% to 9% | 3% to 6% | 5% to 12% |
  | over all thirteen | **70%** | 6% | 7% | 7% | 10% |
  | without a persona | 80% | 4% | 4% | 6% | 6% |

- *Free slides first*: an arc has a free share (`Arc.free`), the share of a talk's slides (but its first and last)
  that are free slides whatever its parts, before its parts get theirs: a quarter for the pitch, the academic talk and
  the all-hands (two of ten slides; a ten-slide pitch or academic talk had none, every slide in a part), and 0.15 for
  the keynote (one of ten). And the text-heavy parts wait for longer talks (eleven slides or more): a pitch's market and
  business model, an academic talk's outline and acknowledgements, an all-hands' agenda. A ten-slide pitch: problem,
  solution, a free slide, traction, competition, team, a free slide, the ask, the closing; a ten-slide academic talk:
  related work, method, a free slide, results, limitations, future work, a free slide, references, questions.
- *What the free slides are*: memes more often (live-caption memes weigh 3 in a pitch, 2.5 in an academic talk, 2 in
  an all-hands, 1.6 in a keynote; and 5 in TED-like talks, from 4), gifs, Reddit's weird pictures, real charts from the
  internet (an academic talk's), fewer statements and quotes; and the formats' own provocation (`Provocation (Pitch)`
  and so on): a striking or weird picture of the slide's topic filling the slide under a provocative word or two in the
  format's voice ("Disrupt.", "Peer reviewed.", "Synergy.", "Revolutionary.": each format pack's `free.provocation`,
  their version 2), a slide in ten at most (tag `provocation`).
- *Pictures behind figures*: the `big_number` and `kpi` kinds have an optional image slot, `background`
  (`Kind.optional_images`: a slot that finds nothing leaves the slide without its picture, after searching for the
  slide's concept on the same try, where any other missing picture takes the slide down; a recipe that predates the
  slot leaves it out). Three big numbers in four and half the KPI dashboards ask for one (`kinds.pictured`, the
  classic ones too: `slide_texts.BIG_NUMBER_PICTURES`, `KPI_PICTURES`), in every format: TED-like talks' and the
  formats' (a pitch's problem, market and ask, an all-hands' headline number and dashboard, a keynote's price and
  specs, an academic talk's p-value). Their layouts: the picture behind everything under a statement's shade, the
  number in the theme's accent made light enough to read on the shade and the rest light (`v5/big-number`, and every
  KPI layout, whose tiles read on anything); the number and its label on a band across the shaded picture
  (`v5/big-number-band`); or the picture filling the slide's right side and the texts beside it on the theme's
  background (`v5/big-number-side`). No design finding in any family (every layout, three seeds a family). The kids
  family hangs its bunting across the free side then (the merge's slow sweeps found none on it, 2026-11-09).
- *From many sources*: the pictures behind figures have a look of their own, `backdrop`: stock photos most often, and
  now and then a weird picture from Reddit, a photo from r/pics and the like, a NASA photograph, an old photograph, a
  museum's painting, all of the topic; and a statement's backdrop is a calm photo two times in three, else the
  backdrop look's (`content_generators.statement_backdrop_generator`). Reddit's weird pictures come up more often:
  `meme-chaos` has them 14 to ShitpostBot's 5 (was 10 to 8), `meme-chaos-still` 7 to 4, and `weird-stock` (stock
  photos of weird things) has them too.
- *Fewer slides of text*: the pitch's product slide (`Solution`) weighs 3 against the before-and-after's 1 and how it
  works's 0.6, the team's photos, the all-hands' wins and the keynote's three features weigh more, an academic talk's
  experimental setup (a picture of an odd contraption) more than its equation, and its admitted limitation is ten
  words at most; a classic fun fact has its photo three times in four (as a planned one).
- *The pitch's product, shown off*: its picture's look is `product-shot` (stock photos of gadgets and inventions: a
  classic search puts "gadget", "invention", "machine" or "device" before the topic; a planned slide's query, which
  describes the product, goes as written), and in a talk that generates pictures, the model's prompt draws it as "a
  striking advertising photograph of an absurd, imaginative product, lit as a premium product shot". The keynote's
  reveal has the same look. On talkgenerator.com, a visitor's own key generates pictures (D39); without one, the
  search finds a weird gadget.

Checked on 2026-11-09, without GIPHY and Unsplash: the quick set; new tests (`tests/test_pictures_on_text_slides.py`,
with every layout of a big number or KPI tiles over a picture in every family, three seeds each: no design finding);
9 classic talks of random formats (`check --quick --seeds 1,2,3 --schema random --theme random`): 0 errors, 0
warnings, deterministic 9 of 9; 5 sample decks, two by the free models ($0). Over 400 random-format ten-slide talks,
live-caption memes come up in about half of the TED-like talks, the pitches and the academic talks (ten-slide pitches
and academic talks had none), in a quarter of the all-hands; a provocation in a third of the pitches. Of the
family-wide tests, the design test of runs of every slide type (the new figures' too) passed in all 17 families; the
rest ran in part only (the machine was busy). The generated product shot is tested with a fake generator only.

**The talk's why: problem slides** (2026-11-09, D69), from the user's "what makes a good pitch and a good academic deck
is typically that they explain the WHY / problem really well in the beginning": a slide type of its own, `problem`,
that pitches and academic talks open on most of the time, and some TED-like talks too.

- *The slide*: a short heading on a sticker in the theme's accent, as a fun fact's ("The problem", "The pain",
  "Motivation", "Sound familiar?": the model's, as the talk's kind of talk names it, or the pack's), the problem in big
  words (a few words, three to eight, 60 characters at most since D73, as the user found the first ones' one or two
  sentences of 130 far too long: "it's way funnier if they're much shorter"), and a line under it that makes it hit
  home (how often it happens, to whom, what it costs; 60 at most, 80 before), which appears on a click. Its picture
  is optional, of one of two slots:
  `background`, a picture of it behind the problem (a statement's backdrop: calm photos two times in three), or
  `photo`, a picture beside it that shows the problem as it happens (`weird-stock`, generated in a talk that generates
  pictures: on talkgenerator.com, on a visitor's own key only); a slide whose picture isn't found goes without it.
  Three layouts: `v5/problem` (over the shaded picture, light and aligned left, as a statement over a photo; beside a
  framed photo; or, without a picture, in the middle: the sticker, the problem and the line one under the other, each
  as tall as it comes out, in the middle of the slide's height), `v5/problem-band` (the problem on a band across the
  shaded picture, the sticker over the band's top edge) and `v5/problem-split` (the photo filling the slide's left
  side). Texts, pictures and shapes only, so talk-generator-web draws it unchanged.
- *The angle*, which the talk's dice pick, for a planned slide (a recipe's variant: `kinds.problem_variants`) as for a
  classic one (the pack's rule of that angle): a weird problem nobody has noticed yet, an everyday one everyone in the
  room has had, the topic running into something from another part of life (the word to riff on, or a pack's everyday
  thing: "Monday mornings", "Reviewer 2"), the problem everyone who deals with the topic knows, or a real one: a
  how-to people look up on wikiHow. Each angle has a picture behind the problem half the time, beside it otherwise
  (`PROBLEM_BEHIND`); a pitch weighs everyday and real problems a little more (×1.3, ×1.2), an academic talk typical
  and weird ones, a TED-like talk everyday and weird ones. A classic slide's template is the problem and its line
  ("...|..."), the line kept four times in five.
- *Real problems*: a free, keyless source that passes the facts' checks, wikiHow's public search (which classic talks
  used already): a classic slide on the real angle says a how-to about the slide's seed ("Right now, someone is
  searching how to repair an umbrella."), and gives way to another angle when wikiHow has none; a planned
  slide on it gets one as a flavour text (`facts.howtos`, use `problem`, in English talks only, as dad jokes): the
  topic's how-tos that say what they fix first ("How to Quit Procrastinating", "How to Repel and Keep Pigeons Away
  Naturally"), with the facts' checks (no living people, nothing grim: "How to Stop a Goose Attack" stays out),
  credited "wikiHow" when the slide builds on it. Its line in the request: "Start from this real how-to, which people
  look up on wikiHow".
  Considered, not tried: Wikipedia's lists of unsolved problems (a few fields have one, most topics none) and
  Reddit's complaint subreddits (pictures with titles about anything, which the checks would have to sift).
- *Where it comes up*: one a talk at most (tag `problem_slide`, capped at one in every format; a pitch's `problem`
  part may still have two slides, the second its statement or its number). Over 1,000 seeds of ten-slide talks (picks
  only): **72% of pitches** open their problem part with it, at slide 2 (the problem statement over a photo 9%, the
  alarming number 18%, over 400 seeds; a pitch of 15 slides or more has it in 96%, at slide 2 or 3); **80% of academic
  talks**, at slide 2, in a new first part, `motivation` (its research question over a photo otherwise); and **23% of
  TED-like talks** (32% with the open license policy, whose second slide is history, not the presenter), at slide 3,
  after the presenter's (`slide_schemas.PROBLEM_WEIGHT`, peaked at the third slide); over all the formats a talk's
  seed picks, a quarter of ten-slide talks (25% over 3,000 seeds). All-hands and keynotes have none yet.
- *An academic talk's arc*: `motivation` comes first, rank 1 (kept from three slides on), so a five-slide academic
  talk is its motivation, method, results and questions (no limitations), a ten-slide one its motivation, related
  work, a free slide, method, results, limitations, a free slide, references and questions (no future work), and the
  acknowledgements wait for 13 slides (the outline still for 11). The pitch's arc is as it was.
- *Content packs*: the pitch pack's version 3 (its problem grammar's `kicker`, `weird`, `everyday`, `crossed` with
  `crossing`, `typical` and `real`), the academic pack's version 4 (a `motivation` grammar of the same, and research
  questions) and the TED pack's version 7 (a `problem` grammar, in a TED speaker's voice); linted as every pack is, and
  each line under a problem 80 characters at most.

Checked on 2026-11-09, without GIPHY and Unsplash: the quick set (1,914 passed); `tests/test_problem_slides.py` (74,
its slow ones too: the longest problems and long words in every family and in every open font pairing, every layout);
the family-wide sweeps of `test_design` (long words in every family and pairing, no layout twice in a row, random
themes) and `test_motifs`, which found two things, both fixed: a long heading on the sticker needs body contrast (1997
WordArt), and a problem beside a photo that fills the slide's side gets no decoration or slide number in most
families, as a big number beside its picture doesn't (photo slides' motifs keep off them, D65), which the test now
counts as it counts full-screen pictures. `talkgenerator check --quick --seeds 1,2,3` of classic pitches (9 talks: 0
errors, 0 warnings, deterministic 9 of 9; six open on a problem slide) and academic talks (9 talks: one statement's
backdrop with detail where its text goes, a free slide's; one talk whose fun fact's photo changed between its two runs
while Pexels was in a cooldown, deterministic when made again; all nine open on a problem slide). Five sample decks,
three by the free models ($0), and a free model's pigeons pitch whose problem slide got "How to Repel and Keep Pigeons
Away Naturally" to start from. No OpenAI image generation: the generated picture beside a problem is tested with a fake
generator only.

**Six more formats, and eight more personas** (2026-11-12, D79), of the personas, formats and looks proposed that day,
which the user answered "let's do all of them (unless some of them don't work out great)" (the looks went to a
session of their own, D77). Each is a format as the four before it: a module, a content pack, a brief and hints for
the language model, favourite personas and themes, and an arc with a free share; no new slide type, and none advances
by itself. Every one came out well enough to keep (below), so none was dropped.

- **`infomercial`**: a late-night TV infomercial for a gadget made of the topic, with its made-up name ("Magic
  Penguin", "InstaCoffee": `formats.gadget`). Its arc goes from the everyday problem (the problem slide, "Sound
  familiar?" over "Spilled fish on the sofa?", or someone failing at it full-bleed under "There has to be a better
  way!") through the gadget (a product shot, or full-bleed: "As seen on TV!"), its demonstration (three photos ending in
  "It even folds fitted sheets!", how it works, or the old way and the new), testimonials (five-star reviews, the last
  one absurd; a customer's post; before and after), the fine print (a wall of disclaimers, or a terms dialog whose every
  button agrees; from eleven slides on), the price (prices dropping tile by tile to "$12.99: before our boss finds
  out!", or "3 × $19.99") and "But wait, there's more!" (a free bonus full-bleed, or "2 for 1") to the call to order
  (over a calm photo of a call centre, a 555 number, or the whole room pretending to dial).
- **`documentary`**: a hushed nature documentary about the topic as a wild species with a Latin name ("Penguinus
  giganteus", "Coffeus minimus": `formats.species`): the opening shot (a landscape under a hushed line), its habitat,
  its behaviour (three photos, two, or a day in its life as a cycle), a rare sighting (a weird photo, or the news), its
  rituals, the dangers it faces (everyday ones told as grave ones: "2 left in the wild, and they know it") and a
  closing reflection, "Next time: ...", or the whole room hushed ("Shh. Everyone, stay very still. Penguinus giganteus
  is right behind you.": a closing without a picture, so that a documentary always has one). Its parts are pictures
  already, so a fifth of its slides are free, among them a quiz of its own ("Which of these did our crew film for nine
  months?").
- **`court`**: the topic on trial for one harmless crime, the same all talk ("humming in the quiet carriage",
  "spoiling the season finale": `formats.crime`): the charges (the news, the counts, or "The People versus..."), the
  evidence ("Exhibit A" in one photo the presenter must explain, Exhibits A and B, or a forensic correlation), a
  witness (a post, three photos, or a quiz on where the defendant was), the alibi (the night in question as a
  timeline, a flowchart whose every answer ends in guilt, or "Alibi not found"), an objection, the closing argument
  ("Look at this face") and the verdict (the jury's pie chart, "GUILTY" as a big number, or the room as the jury). The
  evidence and the verdict stay longest. Its evidence is D78's Exhibit A (an odd picture beside its evidence tag; on a
  second slide, Exhibit B, of the same case), or the lab's forensic chart.
- **`museum`**: a guided tour of a made-up museum and its old master ("The Penguin Gallery", "Anna van der Penguin":
  `formats.museum_name`, `artist`): the welcome (the hall, the house rules, or the route, "The gift shop (the
  highlight)"), a masterpiece (public domain art under its label, full-bleed, or before and after a volunteer's
  restoration), the artist (their life as a timeline, a fun fact, or their post from centuries ago: no portrait under a
  made-up name, as museums' portraits show real people), the eras (three periods, "The period with hats"; the
  movements as a tier list; the hierarchy of art), an artefact (behind glass, a quiz on what it was for, or the news of
  its discovery) and the gift shop ("€12,000: a selfie with the guard").
- **`wedding`**: the best man's or maid of honour's toast to their best friend (a name that goes with anyone, "Robin":
  `formats.friend`, always "they"), who marries the topic: who the speaker is ("Me and Jordan, back when they still
  called me"), how they met (a photo, their love story as a timeline, or a happiness chart), the story ("The coffee
  incident", full-bleed; the red flags we all ignored; a post from that night), the couple (a Venn diagram, or the two
  side by side: "Robin: allergic to cats", "Coffee: not a cat"), advice and the toast, the whole room raising their
  glasses (no drink is ever named).
- **`book_report`**: a pupil's report on a made-up book ("Goodnight, Penguin" by Edith Bumbleby, "Time Travel at
  School": `formats.book`, `author`): the book's cover, the author (from eleven slides on), the characters (three
  photos, or who's who: "A talking sandwich", "A suspicious duck"), what happens (a process ending in "To be continued
  (oh no)", or how exciting it is page by page), the favourite part, the moral, the rating ("4 stars: would have been
  higher with a dragon in it"), before its closer says "The End" and asks "Can I sit down now?". The book-covers look is
  Reddit's, so a cover falls back to illustrations under the open license policy, and is drawn in a talk that generates
  pictures.

Ten-slide talks: an infomercial's problem, product, a free slide, demo, testimonials, price, a free slide, "but wait"
and call now; a documentary's opening, habitat, behaviour twice, sighting, a free slide, ritual, threat and closing; a
court case's charges, evidence, a free slide, witness, alibi, objection, a free slide, closing argument and verdict; a
museum tour's welcome, masterpiece twice, a free slide, artist, eras, a free slide, artefact and gift shop; a wedding
toast's intro, how they met twice, a free slide, the story, the couple, a free slide, advice and the toast; a book
report's book, characters, a free slide, plot twice, the favourite part, a free slide, the moral and the rating. Five
slides keep an infomercial's problem, product, demo and "but wait", a documentary's opening, behaviour, sighting and
closing, a court case's charges, evidence, alibi and verdict, a museum tour's welcome, masterpiece, artefact and gift
shop, a toast's intro, how they met, the story and the toast, and a report's book, characters, plot and rating. Their
content packs have 2,530 templates in 305 slots, linted as the others are. Their made-up names all come from the topic,
the same on every slide; the museum's, its old master's and the book's keep the topic's words apart when they're short
("The Time Travel Gallery", "Pieter de Rubber Duck").

The odds, with ten formats beside the TED-like talk and nine specialists among 21 personas: `FORMAT_WEIGHTS` gives the
TED-like talk 55 (it was 20) and every new format 1, the specialists' multipliers are ×32 (×21 for the all-hands and the
keynote, whose weight is 1.5), and no persona's multiplier is under 0.7. So 7 talks in 10 stay TED-like over all the
personas, as the user asked (D63), and a specialist's favourite comes second, in a third of their talks (it was two in
five); every format keeps about 1% (one talk in a hundred) with every persona, "some chance for all possibilities" (the
user's words for D61; it was 2%, which ten formats beside a TED-like talk at 7 in 10 can't all have):

| Persona | TED-like | Their own format | Each other format |
| --- | --- | --- | --- |
| the nine specialists (founder, professor, consultant, motivational speaker, detective, infomercial host, narrator, museum guide, best man) | 55% to 57% | **32% to 33%** | 1% to 3% |
| the other twelve | 76% to 83% | | 1% to 9% (a kindergarten teacher's book reports) |
| over all 21 | **69%** (69.4% over 4,000 seeds, picked as talks pick them) | | pitch 2.8%, academic 2.9%, all-hands 3.4%, keynote 4.0%, infomercial 3.2%, documentary 3.2%, court 3.0%, museum 3.4%, wedding 3.0%, book report 1.8% |
| without a persona | 83% | | 1.5% (all-hands and keynote 2.3%) |

Pitches and academic talks stay rarer than all-hands and keynotes. The book report has no specialist: a kindergarten
teacher gives the most of them (9% of their talks), an alien anthropologist and an influencer some more. A format named
weights its personas as before (D56), its specialist ×9 (the founder, the professor and the consultant had ×6, the
keynote's founder and motivational speaker ×5 and ×3.5, now ×7 and ×5), so that with 21 personas they still present
about 30% of their format's talks. talkgenerator.com lists the personas and the formats from talkgenerator
(`personas.catalog()`, `allowed_formats()`), so the new ones are on the site as soon as it runs this version.

Rebased onto the `v5` that has D76 to D78 (the user's merge order, D79 last; the same day), each new format has its
closer, through D76's hook (a `Closer` in its `Format`, its words in all eight languages in
`talkgenerator.plan.languages`): an infomercial's "Call now!" with "Operators are standing by", a documentary's
"Thanks for watching", a court case's "Court is adjourned", a museum tour's "Thank you for visiting" with "The gift
shop is on your left", a toast's "To the happy couple!", and a book report's "The End" with "Can I sit down now?". So a
book report's own last part, "The End" (a "Questions?" slide, which D76 took out of every format), went: its rating
stays longest after the book and what happens, and its author waits for talks of eleven slides (D76's
`Part.shortest`). A court case's evidence is D78's Exhibit A, its part's tag given by `SlideGeneratorData.weighted`; its
own stand-ins, an image slide and two pictures side by side, went with their texts (its pack's version 3). The formats
favour D77's families as the personas do (5.2): a court case the corkboard, a toast and a documentary glossy magazines,
a book report sticky notes and the corkboard, an infomercial Y2K and 70s retro; and the all-hands the spreadsheet, a
pitch sticky notes.

Checked on 2026-11-12, without GIPHY and Unsplash: the quick set in one process (2,263 passed, 8 of them on a rerun
without `DISABLE_GIPHY` and `DISABLE_UNSPLASH`, which those tests of the two sources need), the slow tests of the
files the work touched (87 passed: every pack's lint, the formats' and the personas' sweeps), every commit of the branch
on its own (before the personas came, 408 of the formats' and the personas' tests passed), ruff and mypy. Offline
classic talks of each new format read as it: an infomercial's "It even folds fitted sheets!" and "$12.99: before our
boss finds out!", a documentary's "Coffeus minimus can hear a biscuit packet open from two kilometres away", a court
case's witness ("The lawyers keep asking about humming in the quiet carriage. I would like to go home."), a museum's
"€12,000: a selfie with the guard", a toast's "Me and Jordan, back when they still called me", a book report's "Can I
sit down now?". Six sample talks (folder 47 of the comparison decks): an infomercial and a court case by Claude Haiku
5.5 (about $0.003 each) read as their formats ("FOOTWEAR FORCEFIELD! The Sock You Cannot Live Without!"; "The People
v. The Office Printer: The Case of the Vanishing Stapler", whose "Alibi not found" error has the button "I Did It
Myself"), and so did the classic documentary, museum tour, wedding toast and book report. What the checks needed: a
documentary could lose its closing slide when its last pictures repeated an earlier one (a hushed room closes it now,
without a picture), a court case named another crime on every slide (one now, from the topic), and the made-up book,
museum and old master joined the topic's words ("TimeTravel at School"). Known: a classic book report's cover is a real
book's, from Reddit, under the made-up title, and half of the charts and diagrams come out as a picture under their
title (D73), which costs the forensic chart and the falling numbers their jokes half the time.

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

**What the live and benchmark runs of 2026-11-08 found** (D50). A cap of none, such as the `interview` format's on
about-me slides, only held after a first slide of its kind (41% of interviews had one, over 300 seeds), and a cap that's
a share of a talk's slides allowed one where it rounds to none (about one 9-slide talk in ten had a section divider,
meant for ten slides or more): caps hold from a talk's first slide now, a share still allows one (a strict rounding
would take memes, diagrams, quotes and captioned pictures out of 4-slide talks, and give 57% of them an about-me slide
and 44% a chart; from 5 slides on, it gives the same talks), and the section divider needs ten slides by its weight. "A
title or none" always gave a title (a generator that gives none on purpose gave way to the title's), so classic
captioned pictures and full-screen photos now go without one half the time. A historical figure's title could make a
61-letter word of a wikiHow action, which overflowed in brutalist (the classic benchmark's two errors): such a word has
20 letters at most now, as every theme fits (`dashes` gives none for a longer one). Milestone 6's classic texts had the
memes' plural slips ("of experts agree that penguins is overrated", "The penguins pyramid"): the TED content pack's
rewrite of the templates fixes them, from a list of them all. A text cut to its length ends where a sentence or a clause
does (in English, also before a word that opens the next one, such as "when"), when that keeps half of it ("Your plants
are not decorations", where a free model's conclusion read "Your plants are not decorations—they"), and conclusions are
asked for six words at most. A quiz's explanation decides its answer when it names one other option than the one marked.
And a model's text about real-world politics that the talk isn't about (a statement on Japan's "history of aggression"
as a lighthouse talk's quote, seed 12) is left out by a cheap check, of phrases that only statements on politics have
and of real countries or peoples with politics' words, which none of the 336 model-written texts in the sample decks
trips; the request asks for none, and `talkgenerator check` warns of what's left (as of a quiz whose explanation names
other options).

Then the pacing, after the user's look at the decks (2026-11-08, D53): with a list shown at once and only its
punchline on a click, it was unclear when to expect the next thing, and presenter and audience both had to read ahead.
Now a list of things comes a click a thing, the punchline last: a KPI slide's figures, a quiz's options (its answer on
the click after them), an agenda's items, a timeline's moments, a pyramid's levels from its base up, a funnel's stages,
a cycle's steps, an org chart's people (who's in charge after them), an iceberg's hidden things, an acronym's words (its
letters are there from the start), a flowchart's Yes and No ways and then its end, a tier list's tiers from the worst up
to S (its letters there from the start), and a meme's captions, of two or more. The slide's title and its list's frame
(a timeline's line, the iceberg and its tip, a cycle's ring, the line over an org chart's people, the question at the
top of a flowchart) are there from the start; what a thing is drawn on (a tile, a badge, a band, an oval, a box, a dot,
a line to it) comes with it, and the punchline keeps its colour. The slides set their clicks (`DrawnSlide.clicks()`),
the layouts give a thing's shapes its click, and the engine numbers a slide's clicks in turn (an empty click goes).
`talkgenerator.render.reveal` says what appears when, for PowerPoint, the previewer's steps (`slide_image(step=)`,
`steps_sheet`) and talk-generator-web alike. Venn diagrams and matrices keep their one punchline click.

**The next karaoke types** (2026-11-08, D57). Of the catalogue's next ones, the funniest five that the deck's texts and
shapes can draw (the user loves the memes and the karaoke slides, so funny came first): a **wall of text**, the
best-known bad-PowerPoint trope, an executive summary of dense jargon in fine print that fills its slide (as large as
fits two columns: the fourteen or so points a language model is asked for come out at 12 to 15 points of type on the
slide, and at 10 to 12 on a page of a report), with one absurd point hidden a little past the middle of them, which a
marker in the theme's second accent highlights on the slide's one click, and "Continued on next slide" under it all in
the talk's language; the design checks give its fine print a floor of its own, 9 points, as they give the credits theirs
(it's unreadable on purpose, and still has to read on what's behind it). An **alignment chart**: nine things in Dungeons
& Dragons' grid, lawful to chaotic across and good to evil down (the axes in the talk's language, as the game's editions
say them), a cell a click in reading order, chaotic evil last, on a tile in the second accent. **Red flags**: three to
five warning signs, each beside a red flag on its pole (a polygon, red that shows on the theme's background), a flag a
click; in rows, or on cards. **Reviews** with stars: two or three made-up reviewers' ratings (five stars drawn, gold as
many as it gives, and "4/5" beside them, so the rating reads in every renderer and font), their words and who they are,
a review a click, a one-star one last most of the time. And a **fake error message**: a generic dialog (no system's
look), its title on a bar in the theme's accent with a ×, a warning sign on a disc, the message, an absurd error code
and two or three buttons, the last one the dialog's default and the punchline ("Retry, Ignore, Panic"), all at once, as
an error doesn't build up. A talk has at most one of each, in its middle; a wall of text and an error message weigh
less, as organisers warn against text-heavy decks and an error breaks the illusion as a dare does. Personas weigh them
(a consultant's walls of text, a life coach's red flags, a startup founder's and a motivational speaker's reviews, a
time traveller's errors). Classic ones come from the TED content pack (version 3): about 40 points of jargon and 14
highlighted punchlines, six or seven things for each of the alignment chart's nine cells, red flags, reviews and
reviewers, error messages, codes and buttons. Over 500 seeds of 10-slide `default` talks, each comes up in 6% to 12% of
talks (11% to 17% in `ted`), about one of the ten karaoke kinds a talk; memes stay in 48% of the language model's talks
(49% before), and in classic ones they go from 49% to 42%, as five more kinds share the middle of a talk. Still waiting:
the spaghetti diagram (thin turned rectangles could draw its links now), the onion, a tournament bracket, a starter
pack, "Exhibit A", a museum label, a text-message conversation and buzzword bingo.

**Livelier diagrams and charts** (2026-11-09, D64), after the user's review of 35 sample talks: the 2×2 matrices were
"weird: overly complex names", the scatter plots had "boring distribution", the flowcharts, processes, cycles and the
rest were boring without pictures, and a chart could show a weird picture at a point of its line. Now a **matrix** has
everyday opposites at the ends of its axes (a word or two: at most 24 letters, where they had 30) and short names in
its quadrants (a word or two, as the language model is asked; still 30 letters at most, for a format's made-up
citations), and comes out one of three ways, which the talk's dice pick (a recipe of its own can say otherwise): a name
in every quadrant (two in five), no names but familiar things as **dots** where they belong (two to four of them, two in
a quadrant at most, each name in its half of the quadrant; two in five), or bare, with only the axes and the
punchline's dot (one in five). The language model writes a quadrant's things as `top_left_things` ("Cats | Sloths"); the
deck's `MatrixDiagram` has them as `dots`, each with its name and place, drawn from the start in the labels' colour (the
punchline's dot stays on its click), and quadrants without labels draw none; classic matrices take the same three shapes
from ConceptNet's related words. The formats' matrices of things in three quadrants (a pitch's competitors, an
all-hands' initiatives, a paper's earlier work) have them as the quadrants' names or, half the time, as dots where they
belong, one a quadrant, with a name only in the best one (`kinds.matrix_landscape`). A **scatter plot** is a cloud of one of eleven shapes (rising, falling, exponential,
saturating, U-shaped, hill, wave, step, no correlation at all, a ring, a smile: a plan can name one, `shape`), as tight
or as loose as the dice say, of a dozen to 150 points on axes of their own size; a line is fitted through a cloud a third
of the time (`ChartSeries.trendline`: PowerPoint's own trendline, linear or a parabola, dashed, which talk-generator-web
fits by the same least squares; a straight line through a U is a joke of its own); and three times in ten (the recipe's
variant) it's two or three **named clusters** instead (`cluster_1`...), each a cloud of its own, in a legend. Nearly half
the themes (293 of 680) have two accents of about one hue, so the layout engine gives a chart's clusters, and a trend's
lines, colours of their own (`ChartSeries.color`): the accent, then the second accent, the text colour or the accent's
hue turned, whichever is far enough from the colours before it, in hue or in lightness, and shows on what's behind the
chart. **Pictures in boxes**: a pyramid, a funnel, a cycle, an iceberg, a process, a flowchart, a Venn diagram and a
matrix have a weird but related picture in one or two of their boxes 35% of the time (a box's picture is an image slot
of its own, `<box>_picture`, of the kind's `BoxPictures`, rolled when the recipe's variant is, on a stream of its own,
and told to the language model, who writes its query), searched for in the `weird-stock` look, or generated in a talk
that generates pictures; a box whose picture isn't found goes without (an optional slot), and the picture appears with
its box's text. The layouts put it beside a pyramid's or a funnel's band where the stack leaves room (in it, at its end,
where it doesn't), beside a process's band or in the top half of its box, in the middle of a cycle's ring (the
title-beside layout has no room there), beside an iceberg's tip and things, at the end of a flowchart's boxes, beside a
Venn diagram's first two circles (none when its labels are beside them) and in a matrix's named quadrants without a dot,
under or over the label as it's drawn; a picture the layout has no room for stays out, and its credit with it. Classic
diagrams get them by the same odds, about their boxes' texts, and so do the formats' classic diagrams and classic trends
(a picture of their named moment). And a **trend's
named moment** gets a picture by its point half the time (`point_picture`), on a click of its own, after the second
line's when it has one: the layout engine puts it where its plot is in talk-generator-web (`charts.trend_plot`, which
mirrors the site's `points()`: change them together), and a PowerPoint chart with such a picture has its plot pinned
there by hand, its value axis from 0 to the same round number, so the picture is by the point in both, clear of the
point's name and of the lines, with a line from the dot to it. Over 500 seeds of 10-slide talks a language model
writes: a diagram with pictures in 18% of `default` talks and 25% of `ted` ones (30% of diagram slides), a trend's picture
in 6% (29% of trends), a matrix of dots in 7% to 8%; a scatter plot is in 3% of talks, as before (its weight is the
formats'). Previews draw a matrix's dots, fitted lines, and trends where their renderers have them. A dot's name that
doesn't fit beside its dot even at 12 points (a long word in a wide font, by a dot near its quadrant's side, as the
merge's slow sweeps found in 8 families) goes across its room just under or over the dot (`diagrams.dot_name_box`).

**Livelier dares, closing slides and references, and emoji** (2026-11-09, D65), from the user's look at 35 sample talks
("shouldn't they be more challenging or an audience interaction?", "the 'any questions' slides are also pretty boring",
"references slides are pretty boring"). A **dare** is now a real challenge for the presenter to keep up from then on (an
accent, a gesture on every slide, a word to work into every slide, a word they may no longer say, only questions for
three slides), or something the presenter has the whole audience do, under "Audience participation" in the talk's
language (a show of hands, a call and response, the front row standing up, a sound everyone makes); a dad joke to tell
stays, as one kind among them. The dare kind has a field for each, and a recipe's variant leaves one out: the language
model's dares are 40% for the audience, 35% challenges and 25% for the presenter as before, which in an English talk may
build on a real dad joke (a variant says whether its slide takes a real fact or a flavour text: `Variant.facts`); the
classic ones (the TED pack's version 6: 45 challenges, 35 audience dares) are a fifth dad jokes, when there's one, and
else as many challenges as audience dares. The **closing slide** ("Questions?") ends a talk on one of three things, as
many of each, in every format that has it (TED-like talks now and then; academic talks, all-hands and pitches always): a
funny picture beside or above the question (a weird stock photo, generated in a talk that generates pictures), a last
tip for the audience as its line (in an English talk, a real piece of advice some of the time), or a callback, an
earlier slide's picture shown again with a line that calls back to it ("Remember this one?"). The deck gives a callback
its picture once the slides before it are in (`QuestionsSlide.call_back`, as it numbers a section), since realizing a
slide knows nothing of the others: the picture whose search query and description share the most words with what the
model says it showed, or else the dice's pick, never a meme's template (no joke without its captions), credited as on
its slide. An academic talk's **references** are a slide type of their own (`references`, a format type as D56's process
is): the works numbered as cited ("[1]"), a click each, and most of the time a picture of one of them on the click after
them, beside the list, as large as it fits whole, with a caption that says which ("Cover of [2]", "[3], Fig. 2"): a
book's cover (Reddit's book covers, generated in a talk that generates pictures; 48% of the model's references) or a
figure from a paper (a real chart from the internet: 32%), and old prints from museums or illustrations where Reddit
can't be had. They're two recipes of the references part, each with one picture slot (so that a plan written elsewhere,
which gets a recipe as it is, searches one picture), and each with its list alone a fifth of the time. **Emoji** come in
front of a list's things now and then, as karaoke decks have them: in a third of the tier lists and alignment charts and
a quarter of the TED-like agendas, a variant whose hints ask for one a thing (the system prompt asks for none anywhere
else) and that talkgenerator fills in where the model wrote none (a free model ignored the hints in a sample talk:
`Variant.emoji`, by the thing's own word in an English talk, else by its place's mood), and in a third of the classic
ones, from a list of their own (`data/emoji.json`: a thing's own emoji by a word of it, of 559 words, or else its
place's mood, a crown for the S tier, a devil for chaotic evil; none for faiths, drink, weapons or death, and no joined
sequences). No theme font has emoji: they're measured 1.4 ems wide (Segoe UI Emoji draws them 1.37), drawn in runs of
their own in Segoe UI Emoji in a .pptx (where it's missing, PowerPoint and browsers fall back to their system's colour
emoji), and in colour by the previewer where it has the font. A list a model writes is read more kindly too, after the
free models' emoji lists: bars that look like its | (a box drawing's) count as it, an emoji written as a thing of its
own goes in front of the thing after it, an emoji takes two characters' room however many it's written with, and a list
too long is cut between its things, never in one (a cut had left a bare emoji). Over 500 seeds of 10-slide `default`
talks, a dare comes up in 9.6% of the language model's talks (7.2% of classic ones), a closing slide in 10.4% (9.6%), a
tier list in 15%, an alignment chart in 11% and an agenda in 7%.

**Less text, more surprise** (2026-11-10, D73), from the user's look at the third round of sample talks: "too much
text on a lot of the talks, which is not really in the spirit of talkgenerator, because the presenter will need to
read it before looking confident that they know their slides"; better pictures, and unexpected ones ("prikkelende":
odd combinations, odd content).

- *Pictures first*: a chart (a yes-or-no or category pie, a correlation, a trend, a ranking) or a diagram (Venn,
  matrix, timeline, pyramid, funnel, cycle, org chart, iceberg, process, flowchart) tries a picture first, in its
  place, half of the time (`Kind.picture_first`, `PICTURE_FIRST_ODDS`; the dice's stream of its own, so the variants'
  draws are as they were: `Recipe.picture_first`): a real chart from the internet for a chart (Reddit's bad charts,
  r/dataisbeautiful's most of all, which found one for each of ten queries tried, in 2 to 13 s), a weird picture for
  a diagram (the `weird-stock` look: 2 to 9 s), filling the slide under the slide's title (a yes-or-no chart's
  question). A planned slide asks the model for the picture's query (`picture_query`; its brief says a picture may go
  under its title in its place, so the title works on its own), and a classic one searches for its seed, after its
  text version's draws (every schema wraps its charts and diagrams: `_picture_first`,
  `PictureFirstSlideGenerator`, the generator itself kept as `text_version`). Without a picture, the slide is its text
  version, as before. With a time limit per slide (D67), the text version comes at once (a planned one as the model
  wrote it, a classic one from the content stream its work has, without pictures in its boxes: `STANDING_IN`) and
  only the picture takes its place, late: the user's "temporarily text, unless an image can be found within slide
  time limits". Over 1,000 random-format 10-slide talks, 9.7% of the slides a model writes try a picture first, in
  60% of the talks (half of their drawn charts and diagrams). `DISABLE_PICTURE_FIRST` switches it off, as offline
  tests do (whose talks look nothing up that they don't fake).
- *Chart titles*: a chart's title says what it shows, never "X vs Y" (the user: "should've probably just put it on the
  axes instead"). The model is told so, and a planned trend's or correlation's title that only names what it compares
  goes on its axes that have no title (`kinds.axes_from_title`: the first thing up, as a plot of y against x is said,
  the title keeping what follows a colon, else none). A classic correlation or trend whose axes have titles gets a
  claim of the TED pack's for its title (`charts.chart_claim`: "The data doesn't lie", "Exhibit A"), and a bare one the
  title that names both, as before (its "vs." and "versus" ones gone).
- *Problem slides of a few words* (D69, section 7): the model's hints say three to eight words, and the TED, pitch and
  academic packs' problems are rewritten so ("You're doing coffee wrong. | So was I. Until Tuesday.").
- *Pattern breaks*: the user missed "playing with the unexpected", which 2019's talks did with a weird picture in the
  last of three columns, and asked for more of it the same day ("even in the org chart or the red flag list, you could
  use an emoji or an image for surprise instead of text"). A slide that lists things, or a diagram with a punchline,
  breaks its pattern now and then in its punchline, its last thing (`kinds.PatternBreak`, `Kind.pattern_break`, which
  `Recipe.varied` draws from a stream of its own, for every format's recipes of the kind): an emoji alone, a few words
  where the others are sentences, or a picture in its place. A list's, 35% of the time: red flags and reviews in a few
  words, an emoji or a picture; an org chart's boss, a tier list's S tier and an alignment chart's chaotic evil as an
  emoji or a picture; KPI tiles with a word, a symbol or an emoji where the last figure's number would be. A diagram's,
  a quarter of the time, as an emoji alone: a timeline's last moment, a pyramid's top, a funnel's narrowest stage, a
  process's last step, an iceberg's deepest thing, a flowchart's end, a Venn diagram's overlap, a matrix's dot. An
  agenda's last item, a fifth of the time: an emoji, or something off the talk. A picture in a punchline's place is an
  optional picture, searched for with a query the model writes (`<field>_picture_query`, weird stock, generated in a
  talk that generates pictures), and the model's words stay where none is found; the five kinds' layouts put it where
  the punchline's text would go (`engine._text_or_picture`: in a red flag's row or card, a review's card or row, the
  boss's box, made a framed portrait, the S tier's band, chaotic evil's tile), and so does the 2019 template, which
  lays them out with the same engine; an emoji alone is drawn as large as its box takes (up to 220 px, `_style`), and
  the deck checks take a thing's picture for the thing. The third of three captioned pictures in a row is unexpected 60% of the time,
  with a query and a caption of its own (that recipe's variants: the user remembered it as usual). Classic, as often:
  the TED schema's lists and diagrams wrapped (`slide_texts.broken`: an emoji, the thing's own by a word of it or else
  one of `emoji.json`'s new "surprise" mood; or a picture of the punchline's words), red flags and reviews in a few
  words too (the TED pack's `karaoke.review_short` and `karaoke.red_flag_short`: "Meh.", "🙄", "This slide."), KPI
  punchlines that are no number ("Ask Bob", "🤷"), and twelve more rows of three captions whose third breaks the first
  two's ("Step 1 | Step 2 | Step 47": 12 of 53), under the weird pictures their second and third columns had since 2019.
  Spares and stand-ins break none: they look nothing up (`slides.STANDING_IN`). Over 1,000 random-format 10-slide
  talks, 42% have a planned slide that breaks its pattern (5.7% of their slides; 15% before the user's follow-up), 24%
  an emoji alone, 10% a picture in a punchline's place. `DISABLE_PATTERN_BREAKS` switches them off, as offline tests
  do.
- *Coincidences* in place of the day's events, for slides of history and fun facts: section 11.

**Pictures to explain** (2026-11-12, D78), at the user's request for slides that "give you a fun visual that surprises
the audience and you have to explain it, so with less text and more fun inspiration for the presenter to justify &
explain the slides and craft a story around", as improv suggestions and story cubes do: five slide types of a picture
or three and hardly any words, from the karaoke catalogue and this section's waiting list. **Exhibit A**: an odd
picture (weird stock photos, generated in a talk that generates pictures) as the evidence in a case, beside an
evidence tag tied to it by a string (a manila card with a hole, "Exhibit A" big, the case's number under a rule, and a
note of a few words, as a police report notes where it was found, half the time), or under an evidence marker (a
yellow tent with the letter) with its words below. The deck letters a talk's exhibits in turn, as it numbers sections:
a later one is Exhibit B, of the first one's case (a cap of two). **Pick one**: two pictures side by side, without
captions, under "Pick one:" (or a heading of the model's or the pack's, a third of the time), an "OR" on a disc in
the accent between them; or the two filling the slide's halves under a band. A **picture equation**, story-cube style:
a thing plus another thing equals a third, the punchline, which comes on a click with its "=". The model writes every
thing as an emoji and the dice pick which are pictures too (all three, two that make an emoji, two emoji that make a
picture, or all emoji), so a thing whose picture isn't found, or doesn't come within a slide's 8 seconds (D67), is its
emoji: an emoji is drawn on a card in the surface colour, as a cube's face, as large as the card takes. **What do you
see?** over a face in something that has none (Reddit's pareidolia, which only talks with fair use have, searched for
the thing the model names, and then for any face: a planned search gets no subreddit's hot posts), or over an
**inkblot**: a slide without a picture is one, drawn by its layout as polygons and ellipses mirrored about a card's
middle, by the slide's dice (a body of ink down the middle, blobs that wobble, drops), the same every time it's laid
out; a quarter of the time in `default` talks, always in `ted`, and whenever its picture isn't found. And a **before
and after**: two pictures that have nothing to do with each other under "Before" and "After", an arrow between them,
the after (and its sticker and the arrow) on a click. Talkgenerator's words are in all eight languages; the deck's
texts, pictures and shapes draw them all (a turned rectangle for the tag's string), so talk-generator-web shows them
as it is. Over 500 seeds of 10-slide talks a language model writes, each comes up in 9% to 12% of `default` talks
(11% to 18% of `ted` ones), 40% of `default` talks have one (54% of `ted` ones), and an Exhibit B comes up in one
`default` talk in 500 (in 170 `ted` ones). Five more kinds in the middle of a talk took memes down from 49% to 40% of
talks, so memes weigh 7 now, from 5 (the user's word): they're in half of the talks again (50%). No persona
weighs them yet: that's left to the work on personas and formats that follows, which reuses them (a court case's
exhibits, a game show's picks).

**Playable at a glance** (2026-11-13, D80), from the user's review of the talks as an improviser presents them:
"it has to support funniness, so unexpected or funny visuals or punchlines, and preferably setting up a pattern and
breaking it", and too much text, "which makes it harder for the presenter, who has to read it first". So:

- *Less to read.* A slide's title has 45 characters (`kinds.TITLE`; a chart's question 60, a quiz's 70), a talk's 50,
  asked for in two to seven words, and the presenter's job 40, on a line of its own under the name (the title slide's
  text breaks there: PowerPoint gets a line break, the site and the previewer draw it as one). A tier holds one thing
  (`slides.TIER_ITEMS`: the best, the first written), a red flag slide has three of them (`slides.RED_FLAGS`), of a few
  words each (`kinds.FLAG`, 50), a post 90 characters, a quiz's options 36, a review 70, a statement 90, a fun fact
  100 and one short sentence (the real facts' asks too: `facts._ASKS`), an alignment chart's cells 32, an agenda's
  items 30; an error message has a message of a few words (60), a code a third of the time and half its weight (0.25).
  The content packs' texts were shortened to the new lengths (TED 10, the others a version each), but for a real dad
  joke a dare wraps and a real piece of advice a closing slide does (their slots keep limits of their own).
  And a fact no longer comes with "a really weird sentence behind it", as the user put it: D73's coincidences (two
  real things of a year) go to the slides that show them side by side, two old photos and a timeline, where the
  presenter ties them together; a made-up figure's quote and a fun fact, which tied them in one sentence ("After
  Jefferson's fries of 1802, Beethoven could only write a moonlight sonata", in a Dutch talk by Claude Opus), build on
  one real thing, and the quote's title names its moment, so that the quote is the figure's line alone.
- *The punchline last.* A ranking has three or four bars (`chart.RANKING_BARS`), two or three that come to next to
  nothing and then the punchline's, and they come a click each from the top down (`ChartReveal` `"categories"`, a
  chart's own clicks, `ChartSpec.clicks()`): in PowerPoint, a build by category, each bar named by its own data label
  (the category axis's names are the chart's background, there from the start), the long one's inside it at its start;
  on the site, bars that grow in from the left; the previewer draws them top down.
- *Pictures from the start.* A trend's picture by its named point is there from the start: the odd picture is what
  the presenter starts explaining.
- *Cues for the presenter.* A quiz's question starts with a label in the talk's language ("Quiz:", "Pop quiz:", "Test
  voor jullie:": `Language.quizzes`, picked by the question's letters, so no random stream moves), replacing one the
  model wrote. And every slide with clicks has a small ring for each of them by its number, which fills on its click
  (`engine.build_dots`: an empty ring left means the next click brings more of the slide, all full the next slide, and
  the last ring the punchline), in the first free corner, in the muted colour made to show; shapes of the deck, so
  PowerPoint, the previewer and the site all draw them (in PowerPoint a chart's or a diagram's own steps take theirs
  along, `animation.join_click`, and a column slide's come with their columns).
- *An agenda that comes back.* An agenda announces up to three later slides, spread over the talk, by their words, and
  those slides pick its items up (`prompt.agenda_cues`, a `PlannedSlide.cue`, at both levels; a classic agenda's
  items speak of the seeds of the slides after it).
- *Variety.* Green, orange and red flags (`traffic_flags`, a type of its own with the red flags' layouts in three
  colours, and their tag: one of the two kinds a talk), the red one the punchline.
- *Pictures where they help.* A photo of the talk's world beside its title (`talkgenerator.title_pictures`: its
  format's `Format.scene`, a wedding toast's wedding, else its persona's, a detective's; searched with the topic first,
  from the talk's start, in the background), which the generic title layout puts on the right (`v5/title-picture`),
  a newspaper's front page in place of two columns of type and a company's title slide on its panel; the families
  whose own title layouts have no room give way to the generic one, whose title widens for a word too wide for it (a
  Dutch compound in a brutalist's capitals), the photo giving way down to 400 pixels. A section divider (70% of the time) and a dare
  (half) over a picture of what they're about (`v5/section-photo`, a dare's card over the shade). A process has a
  picture in every step most of the time (`BoxPictures.every`, 60%), taller boxes with the picture over a caption.
  And strong image filters (duotone, grayscale, sepia; black and white goes grey) are for backdrops alone
  (`treatments.treatment(behind=)`): pictures of a slide's own keep their colours, with the theme's gentle touches.
- *People.* A presenter's name could be a real person's: a real first name and a surname that could be real, at most
  a subtle nod to the topic ("Penn Quinn" for penguins, the user's example, never "Pen Guin"); the styles weigh fun
  surnames 1.5, puns 1 and famous names 0.5 (`Style.weight`). A post's author and a reviewer have real first names.
  A recurring character in one talk in five (`prompt.RECURRING_CHARACTER_ODDS`), on two slides at most; the others'
  callbacks are things and claims. A pitch's e-mail address is at a domain that reads as made up, in the talk's
  language ("trapzo-is-echt-een-bedrijf.biz": `closers._SILLY_DOMAINS`).
- *A layout bug.* A historical figure's quote no longer zig-zags into the corner opposite its portrait (the rows
  layout is for two pictures).
- *A picture no slide should show.* A sample talk by the kindergarten teacher got r/OldSchoolCool's "Isaac Hayes
  Eating Fried Chicken Off of a Naked Woman" as a portrait: Reddit didn't mark it NSFW, and the finder's filter of
  descriptions didn't know "naked". A description, or a post's title, that speaks of nudity, sex or gore now keeps a
  picture out, at the finder and at Reddit's search alike, the classic generators' too
  (`safety.unsafe_description`), but for a naked mole-rat or the naked eye.
- *Generated pictures where they matter.* A slot can have its picture generated first (`ImageSlot.generate_first`):
  a talk that generates pictures keeps a picture of its budget for each such slot its plan has
  (`ImageGeneration.reserve`), so a book report's cover, whose made-up title only a generated picture shows, isn't
  left without one by the slides before it (talkgenerator.com generates three a talk at most).
- *The prompt lab* (`scripts/prompt_lab`, the user's idea, as for Improbotics, with about $50 of Claude to spend):
  talks Claude Opus 5.5 writes (the default of a visitor's own Anthropic key on talkgenerator.com, at the Advanced
  level) through talkgenerator's own code, with a stand-in picture for every slot (a talk in half a minute, about
  $0.11), on 13 fixed setups (topics, formats, personas, one Dutch); judged blind and pairwise by Claude Opus 5.5 and
  GPT-6.1 Sol, the order alternating, on five questions (reads at a glance, gives the presenter something to run
  with, funny, free of machine tics, overall), with the tics each noticed; and measured (words on a slide, title
  lengths, recurring names, real first names). Against v5 before this work, the new limits won 20 to 6 overall (25 to
  1 at a glance, 25 to 1 free of tics), with 12.3 words on a slide on average where there were 14.4, at most 27 where
  there were 35, and talk titles of 34 characters where there were 59; but they were funny no more often (15 to 11)
  and some talks milder. The rules that followed (`prompt.SYSTEM_PROMPT`: short and specific, "one oddly specific
  detail beats a general phrase"; don't finish the joke, nor recap it; a list sets up a pattern and breaks it last;
  no stock formulas such as "Uber for X" or a title with a colon and a subtitle; pictures to explain rather than
  literal ones; made-up people with names a real person could have) won 23 to 3 overall and 21 to 5 for funny, but
  read less at a glance (4 to 21, 13.2 words a slide); fifteen words a slide at most, limits not targets, tighter
  fields (an alignment chart's cells 26 characters, a review 60, a headline 60, a KPI's label 32, an agenda's item
  36, as 30 cut a court case's charges) and conclusions that give an earlier slide a new twist rather than recap it
  took them back to 12.2 words (18 to 3 at a glance) at about the same fun (12 to 14 overall, within the noise of 26
  judgements). The judges' tics then: names that play on the topic (they flag every one; the user wants subtle ones),
  Claude's favourite "Gary", real quotes that run long, and a pitch's "Uber for X". So the styles weigh realistic
  surnames most, the name pack's examples, which the model copies, were curated to names a real person could have
  (as "Penn Quinn"), and a real quote has 160 characters at most (100 for the short ones): that round won 15 to 11
  overall and 16 to 10 for funny, at 12.2 words a slide. Its talks showed two more things: a real quote of
  self-harm on a wedding toast's slide, which no real quote may be any more (`content_generator_structures.fit_quote`,
  the facts' rules and more), and a blue square alone as a list's pattern break, where an emoji alone now has to mean
  something (a face, a thing). The lab spent about $8 of Claude and $1 of OpenAI on these rounds.

The user's questions on that round (2026-11-13: "titles are shorter, but not cut-off sentences I hope? that's worse
than too long"; "the OpenRouter AI sometimes doesn't respect the language: Dutch selected, English content"; "is there
more to gain in the prompts?") went to the lab too, which now also makes talks with talkgenerator.com's free models
(`--model free`, at the Basic level, as the site does: they cost nothing), ten Dutch ones of every format (`--set nl`),
and measures without judging (`measure.py`): the cuts each talk's texts got, and English in a talk in another language.

- *Nothing cut off mid-sentence.* D80's shorter lengths had made the free models' texts cut far more often: 13 cuts in
  13 English talks, 8 of them mid-sentence ("The Data Is Clear: Coffee Correlates", "Head of Grain and Growth at
  Bright"), where v5 before D80 had 2, both at a sentence's end. A field now asks for D80's length but keeps a text
  whole up to what its slides held before (`TextField.room`, by kind and field in `kinds._ROOM`, v5 `4769664`'s
  lengths: a slide's title 60, a statement 140, a quote 160; a talk's title 60 and the presenter's job 56, which every
  title layout holds in every family, `test_the_longest_title_and_job_fit_every_title_layout`; an agenda's item 45;
  an error dialog's button 20, or 14 for one word, as a compound that long fits no theme's button, and one cut ends
  in an ellipsis without the talk's language's little words hanging, where the first live talk's was "Verkoop de";
  a meme's caption what its box holds at 30 pixels, as its captions shrink to 28, `Recipe.rooms`). A cut ends where a
  sentence, a clause or a comma does, if that keeps a third of the text ("Wim Fietsen", of a reviewer "Wim Fietsen,
  de enige die ooit een fiets repareerde..."); one between words, now rare, ends in an ellipsis, so that it reads as
  meant. Measured again: 2 cuts in 13 English talks of the free models (one at a sentence's end), none in 13 of
  Claude Opus.
- *Dutch stays Dutch.* The free models wrote Dutch talks in Dutch (2 to 5 English words in ten talks); but 3 Dutch
  talks in 20 came out classic, and so English, as the free model failed: an answer that broke off after two minutes
  without a slide that could be read, or one that declined a harmless topic. A talk in another language than English
  whose model wrote no slide is now asked once more (as it was for a topic found unsafe, or an answer in English):
  none in 30 came out English since, though a few English words still slip in ("the ask", "one more thing"). (English
  talks of the free models came out classic 3 times in 13 as well, but for them a classic talk is in their language,
  as D25 has it, and asking again would hold the site's one slot for another two minutes: the user kept it so, 2026-11-13.)
- *The wedding toast's best friend.* Its brief said the friend "has a first name that goes with anyone and is
  'they'", which a free model took for the name ("Quentin and They, Bathtime, 1998"): the name is the model's to
  choose now, never "they", and the toast speaks of them as "they".
- *Prompts for the free models.* Judged against v5 before D80, the free models' talks of D80 read better at a glance
  (19 to 5) and were fresher (16 to 4), with the overall verdict even (12 to 14; 10 to 8 where neither talk came out
  classic): D80 holds for the site's Basic AI too.
- *More prompt rounds for Claude?* One more, aimed at the tics the judges still saw in Claude Opus's talks (a title
  with a colon, conclusions that recap, long meme captions), tied 13 to 13 and was funny no more often (11 to 13), as
  its talks leaned on one gag on slide after slide: it was left out. The last rounds are within the noise of 26
  judgements, and the tic the judges flag most, a name that plays on the topic, is what the user asked for ("Penn
  Quinn"): the prompts for Claude are where more rounds give little. These rounds cost about $4 of Claude.

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
- **Allowed families** (2026-11-08, D62, the user's "disabling slideshow styles" in talkgenerator.com's settings): a
  talk can say which families a random theme can be of (`theme_families=`, `--theme_families`), as it says which
  personas its seed picks from (D61). The seed picks among all the families first (the extremes too, unless they're
  left out), and only when that one isn't allowed, again among those that are, by the same weights: the family's own
  times the persona's and the format's multipliers. So a talk whose family is allowed keeps its theme, whichever
  others aren't, and each allowed family comes up as often as the weights say among them; a chaos deck's slides get
  their own themes of the allowed families too. A family named as the theme goes first, and allowing only extremes
  while leaving the extremes out is an error.
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
  credit line keeps clear of a status line under it (a band behind it hugged it then; since D51 it has none).
- **Measured:** 17 saved talks (the site's live ones, the free models' cat, peanuts and time travel in English and
  Swedish, the lighthouse talks with every slide type, the memes) laid out again in all 17 families over 4 seeds:
  15,708 slides, no design finding (the first run found 5, a Swiss poster's diagram labels over its grid lines on red:
  fixed). In the browser, talk-generator-web's dev server drew a deck of the new families as the previewer
  does (kids' title, terminal, blueprint, chalkboard, newspaper, Swiss). Not checked in PowerPoint itself yet.

Then calmer slides, from the user's look at the themed decks (2026-11-08, D51 and D52; the pacing of lists, D53, is in
section 8):

- **Credits** (D51): image credits had a band behind them over photos and across panels, at 9 points in the muted
  colour, links in PowerPoint's own blue. They're for whoever wants to know where a picture came from, and for its
  license, so now they're 7 points, aligned right, in the colour nearest the slide's background that reads at a
  contrast of 2.5 on what's behind their letters (the muted colour mixed into the background, as if see-through: 2.5 to
  3.3 in every family, higher only where a gradient's two ends both need it), their links in the same colour
  (PowerPoint's `hlinkClr` of the text), and no band anywhere. Over a picture, which could be any grey as well as black
  or white, no colour reads, so they're light with a dark halo (a glow of 1.5 points), which PowerPoint, the previewer
  and the browser all draw. The design checks hold them to floors of their own: a contrast of 2.5 (by their halo on a
  picture, which counts as black, white or grey) and 6 points. A chalkboard's tape on a picture's bottom corners moves
  up off the credit line.
- **Frames with their pictures** (D52): a column slide's second column (and every column of three) comes on a click,
  but a family's frame around its picture (kids' sticker border and shadow, brutalist's hard shadow, a terminal's
  window and its name, a blueprint's figure plate, a chalkboard's tape, a newspaper's outline and the rule between its
  columns) was there from the start, around nothing. The deck's shapes and texts gained `part_of`, the role of the
  element they belong to: the motifs set it, and the renderers show and dim them with it. And the split two-column
  layout's panel behind its first half, which looked like a stray background before the second came, is gone: a thin
  rule between the halves comes in with the second.
- **Found** by laying the saved talks out in all 17 families over 6 seeds (scratchpad scripts in the hand-over notes):
  the split layout's panel was the only shape behind one column alone, and the six framing motifs the only decoration
  that showed before its picture.

**Slide numbers** (2026-11-09, D65), the user's "slide numbers in all templates, albeit usually not very visible, and
also have the max number like X/Y, so that you know when you're almost at the end": every family numbers its slides
of the deck's, small (12 to 14 points), in its muted colour or its fixture's, and in its own style: keynote's and dark
minimal's in a corner ("7/12"), corporate's on its tile, academic's in the Beamer footer ("7 / 12") with a dot for
every slide of the deck over the title (the slide's own filled, the ones after it fainter), startup's on a faint pill
of its accent, vintage paper's on a cartouche over its frame's foot, kids' on a sticker, brutalist's on its tag
("07/12"), neon's by its line along the bottom, a terminal's in its status line ("[07/12]"), a blueprint's in its
title block ("# 07/12"), a chalkboard's on a strip of tape on its ledge, a newspaper's as its folio, a Swiss poster's
over its rule, WordArt's on a little yellow sticker, Comic Sans' in a caption box on the panel's border, and
clip-art's in its top right corner. A number goes in the first of its family's spots that's free and where it reads
(not across a WordArt member's frame, nor over neon's grid floor), never over a full-screen photo; a slide laid out by
itself, of no deck, has its number alone ("07"), as before. A talk that streams knows how many slides it'll have from
its start (its size: `DeckLayout(total=)`), and the deck laid out at the end counts its own (a slide that can't be
made is left out). The 2019 template numbers its slides too, in its bottom right corner (where its picture layout has
its slide number), at 11 points in its grey, the credit line ending before it. Measured on the design checks' deck of
every kind of slide in all 17 families over two seeds, and its runs of slides of a type: no finding about a number.

**Sets of decoration** (2026-11-12, D77), after the user's "now all kiddie-presentations all look the same": the kids
family's palettes hardly showed, as its one motif drew the same things in the same seven crayon colours on every deck.
A family can now have several sets of decoration, of which a member has one, and kids has four: crayon drawings, a
sticker book, a school notebook (ruled or squared paper, a margin line, a binding, doodles, an exercise book's cover)
and paper cut-outs (construction paper with small shadows), each with its own title and section slides, picture frames
and slide numbers, all in the member's palette's colours. And seven new families, as the user asked ("let's do
all of them"): `sticky notes` (a workshop's whiteboard), `corkboard`, `90s desktop`, `spreadsheet`, `Y2K`, `70s
retro` and `glossy magazine`, twenty-four in all.

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
- Not yet: icon sets for `illustration` (10.4: Iconify serves SVG only). The museums' date and classification
  filters came with the new sources (10.4), generated images with 10.5, and the vision pick (4.) on 2026-11-08 (D58:
  see "The vision pick, as built" below).
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

**The vision pick, as built** (2026-11-08, `talkgenerator.images.vision`, D58). Off by default; `vision_pick=` on
`generate_presentation`, `stream_talk` and `render_plan`, `--vision_pick` on the command line, `talkgenerator render`
and `talkgenerator check`. Only planned slides take part (a language model's, or a plan's), as their queries say what
a picture is to show:

1. **Candidates.** In a talk with a vision pick, the finder keeps the runners-up of every picture it finds for a
   planned slide (`ImageData.runners_up`): the other candidates of the batch of sources that found it, with a
   thumbnail, not passed over and not on the slide, its own source's first (the finder takes the first source that
   found any; alternating between sources put a second source's memes and screenshots beside the first's stock
   photos), six at most. Taken in order, without a draw of the talk's dice: the talk finds the same pictures with a
   vision pick as without one, before the pick. Their thumbnails are fetched as the slides are settled.
2. **One contact sheet a talk**, once the last slide is settled: a row a picture (the first ten of the talk), one under
   another, each with its number and what it asks for (the slot's intent and the query) on its left, and up to four
   candidates in cells of 200 by 150 pixels (the finder's and three runners-up that have the look's preferences and
   aren't on another slide, nor nearly), in an order the talk's seed shuffles, labelled "3B". About 1,060 pixels wide;
   1,500 tokens as Claude counts them for ten rows. Gifs, InspiroBot's posters, meme templates and flags take no
   part, nor the stock photos that stand in for generated pictures.
3. **One request**, with the sheet, what each slide says (never the presenter's name the talk was given) and a JSON
   schema: for every row, what its candidates show, in a few words each, and then a letter, or "none". Saying what
   they show is what made models that don't think first pick well: without it, both free models answered "none" for
   nearly every row.
4. **The picks** take the finder's pictures' places once they pass the finder's checks (downloaded, or probed while
   the talk streams; not on another slide, nor nearly), and the slides that changed are handed over again
   (`slide.updated`) before `talk.finished`. "None", a row it didn't answer, an error, a refusal, an answer later than
   30 seconds and a budget that doesn't allow the request keep the finder's pictures. Every picture it saw says what
   it made of it (`vision`: `picked`, `kept` or `refused`), the deck says which model it was (`vision_model`), and its
   usage counts the request (`vision_requests`, among `requests`; a request the talk stopped waiting for counts as a
   failed one).
5. **Which model:** `on` (or `True`) asks the talk's own model when it reads pictures (Claude, OpenAI's, a replayed
   talk's cassette), else OpenRouter's free models that do: `nvidia/nemotron-3.5-super-vl:free`, then
   `dots-studio/dots-3-note-preview:free`, without thinking. Of the nine free models that took pictures on
   2026-11-08, the free router sent a drawn test sheet to `nemotron-3-nano-omni`, which couldn't tell a red circle
   from a blue square; Gemma 4's free endpoints turned the request's parameters down or were busy upstream;
   `stealth/crouton-alpha` isn't served in this region. Any model takes its spec (`anthropic:claude-haiku-5-5`:
   about $0.001 a talk by list price).
6. **Replay:** the sheet is named by its candidates (`ImagePart.name`), which keys the recorded answer instead of the
   picture's bytes, which a cassette never keeps; a request without pictures keeps the key it had before. The check
   records the vision model's answers on the talk's cassette, and its second run replays them.

**Measured** (2026-11-08, OpenRouter's free models at $0, GIPHY and Unsplash off, random themes, 10 slides; each talk
written once by the free router and made from that same answer without the pick and with it, so only the pick
differs; scripts and reports in the session's scratchpad `live/`, sample decks in the comparison folder's
`27-v5-cff9bc4-vision-pick`):

- **Pictures that show what they were searched for.** `talkgenerator check`'s `images_matching_their_query` (a
  picture's description shares a word with its query): 24 of 54 without the pick and 28 with it (6 talks), 20 and 23 of
  40 (5 more), 10 and 10 of 13 (one). That measure can't see a picture, so every row the model saw was judged by eye
  too (by Claude, from the sheets, before looking at the picks): whether the picture that ends up on the slide shows
  the subject of its query. With the final setup (12 talks, 74 rows): 27 rows with the finder's pictures (36%), 37 with
  the pick (50%); 14 rows better, 4 worse (where the model's reading of a thumbnail was as defensible as the judge's),
  and in 18 no candidate showed it. On the same 37 rows asked twice, 17 and 18: the free model varies from one answer
  to the next about as much as the prompts tried last did (one that has it name each row's subject first: 18).
- **Models and prompts**, on the first six talks' sheets (25 rows, the finder's pictures 13): Nemotron without
  thinking, saying what each row shows before it picks, 16, in 2 to 7 seconds; dots-3 the same, 16, in 5 to 9;
  Nemotron thinking at most 1,024 tokens, 17, in 8 to 44 seconds; Nemotron at `minimal` effort without saying what each
  row shows, 14, in 10 to 43 seconds and once over a minute (8,145 tokens of thinking, no answer); both without
  thinking or saying, "none" for nearly every row. With the sheet in two columns (7 rows or more), both paired rows
  with the wrong queries (describing row 3's candidates for row 2): hence one column, with what each row asks for on
  it. The runners-up alternating between sources put memes beside stock photos: hence the picked one's source first.
- **Refusals.** Nemotron still answers "none" for rows where its own description shows the subject ("6D: person
  sitting on a rock on a mountain", for a person meditating on a mountain), and once for every row of two talks in a
  `talkgenerator check` (16 rows, the finder's pictures among them showing penguins for penguins): the finder's
  pictures stay then, so a refusal costs a request and nothing else.
- **Seconds a talk.** The request took 3 to 11 seconds (once 19, when Nemotron failed over to dots-3). The slides
  come as fast as without the pick; `talk.finished` comes later: 9 and 24 seconds after the last slide in two talks
  streamed live (their first slides after 16 and 18 seconds, as the free router wrote), 8 to 21 in six streamed from
  recorded answers (the thumbnails fetched after the last slide there; in a live talk, while the model writes).
- **Requests:** one a talk, so two for a talk by a language model: 12 for 6 talks, 10 for 5, $0. `talkgenerator
  check --llm openrouter --vision_pick` (penguins, coffee): 0 errors, 2 of 2 talks the same when made again from the
  recorded answers, 4 requests.

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
- **The site's side** (talk-generator-web, built on 2026-11-08 and merged into its `master`, one "AI pictures" row
  in the Talk tab, as the user chose): pass a visitor's generator with their key
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
  topic drift at the Advanced level; in classic mode and at the Basic level, Datamuse and WordNet keep doing it, with
  things only (D68: Datamuse tags its words' parts of speech).
- **New, keyless sources, as checked on 2026-11-08** (D60): **Wikipedia** (`talkgenerator.sources.wikipedia`): its
  Action API gives an article's lead (its first sentences), its short description and whether it's in "Category:Living
  people" in one request of 1 to 3 KB, and the articles its lead links to in another; an article's whole text (for
  the years of its topic's history: 29 KB for Penguin) and a year's article ("1886", 23 KB; 1969's has 94 events) in
  one request each (D73; D60's day's events from its REST feed, "On this day", are no more). Wikimedia's API usage
  guidelines allow it with a User-Agent that says who's asking (talkgenerator's does) and at most 200 requests a
  minute (a talk makes four to eight); its texts are CC BY-SA 4.0,
  so a slide that builds on one credits its article. **Open Trivia DB** (`talkgenerator.sources.opentdb`): 5,299
  checked questions, CC BY-SA 4.0, no key, one request every five seconds from one address (its HTTP 429 says so),
  and no search: questions come 50 a category at a time (the cache keeps them for a week, so a category's are the
  same all week). Not used: **Wikidata**, whose query service answered a third query within seconds with a 429
  ("retry in 120 seconds"), and whose entities' JSON is 64 KB to 900 KB (Belgium's) with few of the dates and figures
  asked for on the topics talks have (none for penguins, lighthouses, coffee, socks, volcanoes or spreadsheets; some
  for the Titanic and Belgium, which their Wikipedia leads have too); and **REST Countries**, whose keyless v3.1
  answers "This API version has been deprecated" and whose v5 needs a key. The **flavour APIs** (random useless
  facts, icanhazdadjoke's dad jokes, the Advice Slip) state no license or terms for their texts; the user allowed
  them on talkgenerator.com on 2026-11-08, and they give flavour texts (`talkgenerator.sources.flavour`): a
  random useless fact by a number, which the cache keeps for a week (a pool of 12), icanhazdadjoke's search by a
  word (which it finds inside others, "cat" in "catholic", so only whole words are kept) or a page of all 744
  jokes, and an advice slip by its number (of 224), each asked within 4 seconds.
- **Grounding, as built** (2026-11-08, `talkgenerator.facts`, D60): in a talk a language model writes, up to three
  slides of history (a made-up historical figure's quote, two old photos, a timeline), fun facts, quizzes and big
  numbers get a real fact each, on their lines of the request, with what to do with it: a fun fact keeps it true and
  twists it ("Only one species, the Galapagos penguin, lives at the equator" becomes a fun fact about why), a quiz
  asks about it, a big number starts from its figure, a timeline puts it among made-up moments, and a historical
  figure lived through it. The facts are the topic's English Wikipedia lead's sentences (a topic in another language
  through its language's Wikipedia) and its coincidences, which slides of history get first (D73: in place of the
  events of the day the talk was made on, which the user found "a bit confusing", and the same in talk after talk).
  A coincidence is a moment of the topic's history, a sentence that dates something to a year (of the lead, else of
  the rest of the article, but its lists of links; from 1000, the first year titled by its number alone, to ten years
  ago, as recent years' events are mostly the news), and an event of that year's article (`wikipedia.year_events`,
  the first two years' of a talk's), which the slide puts side by side as if the first caused the second: "In 1938,
  nylon came to socks" and "1938: László Bíró patents the ballpoint pen"; "In 2006, Google launched a spreadsheet web
  application" and "2006: NASA's Stardust mission returns the first dust from a comet". A year's events pass the
  facts' checks and some of their own (no heading, no event of the topic's own, none of the news of its day:
  governments, crowns, money, borders, weapons, faiths), twelve of them at most, the lively ones first (firsts,
  inventions, premieres); their names are checked for living people from 1910 on, and a slide that builds on a
  coincidence credits both articles. A fun fact may get one too (as likely as a surprising sentence), and a big
  number or a quiz none. The facts are filtered (no living person, no death, war, disasters, crime, politics, race or
  faiths) and looked up while the talk's seeds are,
  on threads kept from talk to talk, so that they're mostly in before its request is (from the cache in a fraction of
  a second, live in about a second; a new thread's first request, on a computer that twenty Python processes kept
  busy, took six to nine); later than eight seconds from the talk's start, the talk goes without them. A request with
  facts is a few hundred characters longer (three facts at most, of 240 characters at most; a timeline's with its
  year alone). The deck records them (`facts`), and a slide that builds on its fact credits it, in a credit line that
  then starts with "Sources:". In the live checks of 2026-11-08, the free models built on 9 of their last 12 facts
  (every quiz, fun fact, big number and timeline, and 2 of 5 history slides) and Claude Haiku on all 4 of its last:
  "Only one species, the Galapagos penguin, lives at, and slightly north of, the equator, and it always wears a tiny
  scarf"; a quiz "Why have many lighthouses stopped operating?" with its real answer among "They became bird hotels";
  a big number "383/km2: people per square kilometre who now follow my advice daily". Classic talks get real ones
  where they fit: half of the fun facts, a real sentence about the slide's seed with an absurd twist (the TED pack's
  version 4: "Coincidence? I think not."), and half of the quizzes, a real one of Open Trivia DB's, of the topic's
  kind.
- **Content packs** (D54): the classic grammars and templates are versioned data per format and kind of slide,
  `talkgenerator/data/packs/<format>/` (`talkgenerator.sources.packs`): a grammar per kind of slide (`title`,
  `about_me`, `history`, `images`, `statements`, `captions`, `charts`, `diagrams`, `numbers`, `quiz`, `mockups`,
  `structure`, `karaoke`, `memes` and `conclusions`) and a manifest, `pack.json`, with the pack's version, what each
  version changed, and its slots: the rules the code fills in, with the variables their templates may use and the
  text field of a kind whose length their texts keep to. The TED pack (`ted`, for the default, ted, interview and
  test schemas) came first, on 2026-11-08: its version 1 moved v4's templates and milestone 6's there unchanged
  (12,810 texts of 61 generators, compared before and after: the same), and version 2 grew them in a TED talk's
  voice, drafted and curated in Claude Code, from 909 templates to 2,872 (besides the lists of jobs and countries),
  most slots three to six times as many (TED titles 18 to 99, two captions 36 to 98, three captions 4 to 41,
  conclusions' titles 11 to 41, statements 45 to 152, the memes' classic captions 85 to 181). Tests lint every pack
  (`tests/test_content_pack.py`): every template fills in with its slot's variables through talkgenerator's
  functions, keeps to its field's length with words of 22 to 24 letters, has no word of the blocklists (what a slide
  shouldn't make light of, gore, brands, real people, insults, and death, war and drink), speaks of its topic as
  English does, and no rule has a template twice. This makes the free classic mode better for everyone, and the
  language model's per-slide fallback too, and costs nothing at runtime. Measured on the way: one seed gives every
  topic the same templates (with seed 1, 98 of 100 classic `ted` talks had "What if ... ?", and 96 the same
  historical figure), so what repeats takes several seeds to see; over ten seeds, plain words repeated most:
  "Discussion" as a slide's title, "Conclusion 1" as a caption, and the conclusions' six titles. The formats beyond
  TED-like talks came next (section 7, D56): `pitch` (687 templates in 67 slots) and `academic` (591 in 60), a grammar
  per part of their arcs rather than per kind of slide, with the slots' variables for the startup's and the method's
  made-up names (`startup`, `method`), linted by the same tests; and then (D59) `corporate` (596 in 74) and `keynote`
  (391 in 52), with the company's and the product's (`company`, `product`). An all-hands' executive summary borrows
  the TED pack's walls of corporate jargon rather than having its own.

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
  rendering it again gives the same .pptx. And, by choice, a streamed talk with a time limit per slide (D67) once a
  slide runs out of time: that slide then depends on how long its sources took (spares, D66, never change a talk).
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
- **Spare slides** (2026-11-09, D66), the user's idea: a presenter can catch up with a talk that's still being made,
  and then waits for the next slide (talkgenerator.com first held the curtain until a few slides were in). So
  `stream_talk(spares=N)` sends N spare slides early, for a presentation to show instead of waiting, marked as a
  spare, until the next slide is in. To pick their kinds, every classic slide generator of the default and ted
  schemas was timed on its own, as a talk runs it (its images probed), with the topic as its seed and an empty cache:
  all 70 on 6 topics, and 33 candidates on 20 more, odd ones among them ("my grandmother's cat", "death"); wikiHow
  off (its robots.txt), and Unsplash, GIPHY and Pexels too (hourly quotas the site may share). ConceptNet answered
  502 throughout, so the words came from Datamuse (0.13 s a request, one lookup a topic). The slides drawn without
  pictures took 0.00 to 0.01 s at the median and 1.1 s at most (a dare's real dad joke), a quiz up to 2.7 s (a real
  trivia question), and failed on "death" alone, which they won't make light of; the yes/no pie and the bar ranking
  never failed; the property chart failed on 8 topics of 26. A slide with pictures took 0.7 to 5.9 s at the median and
  up to 14.4 s (three captioned pictures): finding an image takes 0.4 to 3.2 s at the median by its look and up to
  11.3 s (a backdrop from the Met), of which Reddit's searches take 1.4 to 1.9 s each, ShitpostBot's 1 s, the Met's
  0.75 s (3 s at the 90th percentile), and checking a picture (a probe) 0.38 s; Openverse didn't answer within 8 s
  and was skipped. Laying a slide out in a theme takes 0.003 to 0.06 s, but a wall of text 0.8 s (its fine print). A
  picture of the topic without text took 2.3 s at the median, 3.9 s at most, and never failed. So a spare is one of
  13 kinds drawn without pictures (`SPARE_WEIGHTS`: a tier list, an alignment chart, red flags, reviews and an
  acronym most often; a quiz, a yes/no pie, an org chart, a timeline, a bar ranking, a dare, an error message and a
  wall of text less often), or in a talk in another language, whose classic slides would be English, a picture of
  the topic without text. Live, a 6-slide classic talk with `spares=3` had its three spares 0.8 to 1.6 s after
  `talk.started`, where its slides 3 to 6 came after 20 to 38 s.
- **A time limit per slide** (2026-11-09, D67), the user's idea after the spares: spare content within a slide puts a
  ceiling on how long a slide takes. Slides settle in order, so one slow slide (its pictures still being looked for:
  the timings above, a slide with pictures 1.9 s at the median, 5.6 s at p90, 8.1 s at p95, 14.4 s at most) holds back
  every slide after it, ready or not. With `stream_talk(slide_seconds=S)`, every slide but the title slide has S
  seconds at most from when it could settle (the slide before it settled, and for a planned slide, its text came in:
  the model's writing doesn't count). Out of time, a planned slide comes at once as the model wrote it, without the
  pictures it can do without and with spare pictures of the talk's topic for the ones it can't (three, found early
  by the "neutral" look; a slot of a kind of its own, a meme's template, a chart, a book's cover, takes none):
  `realize(spare_pictures=)` looks nothing up. Otherwise a stand-in, of the spare kinds, about the slide's own seed
  (in another language, a spare picture of the topic without text), which the talk's tag caps allow. What the slide
  waited for goes on by itself on its daemon thread (the round's end doesn't wait for it), and once it's done, the real
  slide comes after all, in place of what stood in for it (the user's follow-up, the same day): a `slide.updated` with
  `late`, laid out by `DeckLayout.again` in the stand-in's place, and in the deck, checked against the other slides as
  the deck has them by then (no repeats, and the tag caps: a slide after it may have taken the room the stand-in left).
  `talk.finished` waits for it 20 s at most once the other slides are in (`LATE_SECONDS`, which holds
  talkgenerator.com's one generation slot that much longer at worst), and then has the slides as they were handed over
  (laying the deck out at once would lay the slides after a replaced one out anew). A round's pool delivers its work to
  an `_Outcome` from its own thread, which terminating the pool at the round's end doesn't stop. talkgenerator.com's
  presentation keeps showing the stand-in while the presenter is on it, and the real slide once they go on. A chart or
  a diagram that tries a picture first (D73, section 8) stands in as its own text version, planned or classic, before
  an early version (below), as a planned slide stands in as it's planned before one, and only its picture takes its
  place.
  With nothing to stand in, the slide is waited for after all. A slide whose work hasn't started when it's due (the threads busy, with slides that ran out of
  time) starts it then, apart from them: the first live run, without that, made every slide after a slow one a
  stand-in, a quiz of 0.01 s among them, as it timed out in the queue. 8 s, which 5% of those slides took more than, is
  talkgenerator.com's. Live, a 10-slide classic talk that had gaps of up to 10.3 s between its slides (34 s in all)
  had none over 8.1 s with it (30 s, two stand-ins), and a talk a free model wrote had one slide of nine run out.
- **Early versions of the last slides** (2026-11-10, D70), the first layer of the user's layered safety net ("in
  parallel with the language model, some really fast generators first, then medium"): every slide's kind and its own
  topic are known before the model writes, so each of the last slides can have an early version, its stand-in made
  ahead. `stream_talk(early=N)` makes them for the last N slides on a thread of their own from the talk's start, in
  order, and sends each as `slide.early` at its slide's place (`DeckLayout.early`: numbered, from a stream of its own),
  unless the slide is in by then. When a slide runs out of time, its early version stands in for it if the deck
  allows it (no repeats, the caps), and so does a slide that can't be made at all, which used to be left out. The
  early versions avoid repeating each other, but not the talk's fresh stand-ins: live (a classic 8-slide talk, 1.5 s
  limit, early versions of the last 5), two early versions stood in, and two couldn't, as a fresh stand-in before them
  had taken their kind's room. They took 0.04 to 3.4 s each live, not the 0.01 s the picture-free kinds take to draw:
  a dare, an alignment chart or a quiz looks something up. talkgenerator.com asks for early versions of the slides
  that may still be being made when its presentation opens, and its presentation shows a slide's early version at
  its place when the presenter gets there first, until they go on. The second layer, a classic version with
  pictures for slides the model is late on, waits for how often the first one is shown.
- **A talk's progress** (2026-11-10, D72), from the user's look at the site: "above the animation ... the actual
  stage: 'Planning talk'. 'Composing slides'. 'X/Y slides ready' ... Or like a '.' after planning talk for every
  reasoning step or something that we can track". `stream_talk(progress=True)` sends `talk.progress` from the talk's
  very start (before `talk.started`, which waits for the model's spine and first slide) and whenever how far it is
  changes, whole each time: the talk's stage (starting; asking, until the model's first word; planning, while its
  plan comes in; writing; composing; finishing, once every slide is in), every slide's own (waiting, planned,
  written, ready), the parts of the plan in (the spine's fields one by one as the model writes them, which
  `ObjectReader.reading` counts inside the spine's object, and at the Advanced level every slide's idea), and how
  many slides the model writes and wrote. The planned talk tells its Progress (`planning`, a `Planning` snapshot)
  from where its answers come in. Live on talkgenerator.com's free models: `dots-3-note-preview` said its first
  word 6.7 s after it was asked and wrote for 8.5 s (planning 9.8 s, writing 11.2 s, composing 18.3 s, every slide
  in at 28.5 s); `nemotron-3.5-super-vl`, in three talks of four, said nothing for 6.5 to 7.9 s and then sent its
  whole answer at once, so its talks go from asking straight to composing. Claude Haiku's Advanced outline came
  after 22 s of thinking (at `low` effort: the providers don't hand a model's thinking over, so a talk is asking
  meanwhile), then its 15 parts in 4 s, the talk's slides all in at 42 s ($0.0026). Classic talks compose from 0.4
  to 2 s on.
- **talk-generator-web**, on a branch of its own: `POST /api/talks` returns an id; `GET /api/talks/<id>/events`
  streams Server-Sent Events (with nginx's buffering off); `GET /api/talks/<id>` returns the deck JSON as a
  permalink, kept for 7 days like today's outputs; `GET /api/talks/<id>.pptx` renders the .pptx on demand.
- **The Angular renderer** places the elements from the deck JSON on a 16:9 stage (canvas units become
  percentages), turns the theme tokens into CSS variables, loads the theme's web fonts, and has a presenter mode:
  fullscreen, keyboard or clicker, and a download button (no auto-advance: the user's call, 2026-11-08).
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
- **The end of a talk** (2026-11-12, D76), from the user's report: at the end of a slideshow on talkgenerator.com,
  only the presentation's corner said so ("8 / 8", which fades when the pointer rests), and going on did nothing;
  and academic talks and all-hands spent one of their slides on "Questions?". Every talk now ends with its closer,
  a slide after the ones it asked for, of its format's kind and in its language ("Thank you!", "Questions?",
  "Let's talk", "Available today"), which `stream_talk` sends as one more `slide.ready` as soon as the last slide is
  in. talkgenerator.com shows it with "The end" where its number would be, and going on from it brings the curtain
  down, which opens on the talk's overview (Present again, Download, New); a full-screen presentation gives way to
  the window first, as nothing can be drawn over it, the curtain neither.
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
  per talk (the Basic level, D68) and one per regenerated slide. With the $10 of credits on the account, that's up to 1,000 requests a
  day, and at most 20 a minute. A visible switch picks the classic 2019 generator instead.
- **When the quota or the rate limit runs out, or a model fails,** the classic engine takes over without fuss
  (the page says "classic mode"). There's never a paid fallback on the site's key.
- **Fair sharing:** per-visitor caps (a few LLM talks per hour per IP address or session; classic talks as
  today), nginx `limit_req` on the API, quota counters in a small SQLite file, and Cloudflare Turnstile only if
  bots show up.
- **Images:** stock and open sources, as now (Unsplash stays at 50 requests an hour until its production review
  passes), and no AI images on the site's budget. The vision pick (10.3, D58), if the site turns it on, is one more
  free request a talk: two a talk, so 500 talks a day and 10 a minute on the free tier instead of 1,000 and 20.
- **Upgrades paid by the visitor** (decided: all of them): "Connect OpenRouter" (OAuth PKCE: the visitor's own
  free quota or credits, and their choice of model, image models included); an Anthropic or OpenAI key for one
  talk (sent over HTTPS with that request, used once, never stored or logged), whose talks are Advanced (D68), as
  are a paid OpenRouter model's; and Sign in with ChatGPT once
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
| Text | no template leftovers (`{seed}`, `#tag#`, `None`); fits its box at the minimum font size or above; within its length limits; a title without the request's words about it ("Come Up With One: ...", a warning since 2026-11-08) | 100% |
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
| 2 (done: the TalkPlan schema, the planner, the `openrouter`, `anthropic`, `openai` and `chatgpt` adapters, `render`, `schema`, `formats`, the Skill, languages with their check, `login openrouter` and `login chatgpt`, and trend and ranking charts are in; on 2026-11-06, 30 benchmark talks by the free models had 0 errors, one request each, at $0, and 290 of 300 slides by the model. A sign-in with ChatGPT on a Plus or Pro plan is left for after 5.0.0, 5.5) | LLM TED talks and the Claude Skill | TalkPlan schema; the LLM planner (one streamed call, dice, per-slide fallback, safety); `openrouter`, `anthropic` and `openai` adapters; languages, Dutch first; `render plan.json`, `schema`, `formats`; `skill/` with SKILL.md; `login openrouter`; the `chatgpt` adapter (may slip to milestone 3); checks for requests, cost, speed and language | on the benchmark with OpenRouter's free models: no holes, no leftovers, $0 and one request per talk; Dutch talks pass the language check; Claude Code makes a deck end to end with the Skill |
| 3 (done, 2026-11-07: theme families and extremes, procedural palettes with contrast repair, layouts and their variants (never twice in a row), image treatments, WordArt-style heading effects, text fitting with bundled metric twins, the shapes renderer with the classic animations (columns click by click), previews and contact sheets, the design checks and the local MCP server; 0 design findings on 792 benchmark decks in 12 seeds; thumbnails in CI left out, D29) | Themes and layouts | theme tokens and families, extremes on by default; procedural palettes and font pairs; layout variants; text fitting; image treatments; the `classic` theme; thumbnails and contact sheet in CI; the local MCP server | contrast and overflow checks pass on every theme |
| 4 (done, 2026-11-09: `stream_talk()`, probe validation, display policies, presenter names in styles (5.10, for the site's settings) and what's typed read as a topic or a title (5.11, `topic_or_title=`, for the site's Automatic choice) are in; since 2026-11-07, talkgenerator.com runs v5 from GitHub (D31): talks stream into the browser, the .pptx is made on download, Pixabay's images are copied, and classic and LLM talks meet the speed and memory bars on the VPS (section 14), but for the first talk after a restart; then the site deployed the streamed-titles fix (`be09a7e`: on the site, a free model that writes its answer's fields in alphabetical order put `slide_10` before `slide_2`, so slides 2 to 9 fell back to classic ones, or were left out of a Dutch copyright-free talk) and the new settings with 5.10's and 5.11's options, and loads the library before the first talk (its warm-up); on 2026-11-09, spare slides and a time limit per slide came in, for a presenter who catches up with the making (D66, D67)) | Streaming and the web view | `stream_talk()`, display policies, probe validation; in talk-generator-web: the SSE endpoint, the Angular renderer, LLM talks by default with the classic switch, a language choice, Connect OpenRouter and pasted keys, .pptx on download, an Automatic topic-or-title choice (5.11), the site running `v5` from git (D31) | first slide on screen within the calibrated target on the VPS; a 20-slide talk under the memory bar; the downloaded .pptx matches the web view |
| 5 (done, 2026-11-08: image slots and the finder, license classes and policies, aesthetic profiles with local analysis, and the first flavour packs are in, 2026-11-07; generated images too, on the user's own key or server, credited "AI-generated with <model>" in the `generated` class (10.5, D38, D39); and new sources (10.4): the Met, Cleveland, the Wellcome Collection, NASA, Flagpedia's flags, Imgflip's templates and the Smithsonian (with the user's api.data.gov key), with the museums' type and date filters and more subreddits; talkgenerator.com draws them on a visitor's own OpenRouter account or OpenAI key since 2026-11-08 (in the site's `master`, deployed with its next push); and the vision pick, off by default (10.3, D58: a vision model picks each picture among the finder's and three runners-up, in one request a talk, by OpenRouter's free models or the talk's own; 2026-11-08). The Library of Congress, Flickr and Iconify, which need an exception, a paid key or a new dependency, are left for after 5.0.0) | Images | slots, aesthetic profiles and flavour packs, local analysis, license classes; new open and weird sources; AI image generation with the user's own keys; the optional vision pick | license policies enforced; profile checks pass (such as the grayscale share for `vintage`); generated images credited |
| 6 (done, 2026-11-09: fourteen slide types are in, drawn as texts on shapes (D37, section 8); on 2026-11-07, benchmark talks over seeds that bring each of them up had no design, completeness, leftover or language findings: 63 classic talks, and 63 by OpenRouter's free models (620 of 630 slides by the model, at $0), plus 20 classic `ted` talks and 8 Dutch ones, where a long Dutch compound overflowed a narrow box (since, every new layout takes a 20-letter word in every theme, a Venn diagram's labels beside its circles when they don't fit in them); the only other findings were InspiroBot's and Reddit's live answers differing between a talk's two runs. talk-generator-web draws them all unchanged, and needs a small change to hold back what appears on a click in its presentations (merged into the site's master, not deployed yet). Memes with live captions came in later that day (D40); on 2026-11-08 they came to about half of all talks (D48, "I really love the generated memes"), and five slide types from real PowerPoint karaoke decks came in (D49: a fun fact, an acronym, a dare, a flowchart, a tier list), with no findings on them in 36 benchmark talks, 18 classic and 18 by OpenRouter's free models (179 of 180 slides by the model, $0, every talk the same made again), over six seeds and random themes; the same day, so did the user's other two ideas of 2026-11-07: personas that shape a talk (5.2, D47), and bolder themes with subtler, rarer image filters (section 9, D43 to D46). Then the TED content pack (section 11, D54): the classic texts of TED-like talks as data, per kind of slide, grown from 909 templates to 2,872 in a TED talk's voice and linted by tests, with no errors in 184 classic benchmark talks (130 `ted`, the last 30 made twice and the same, and 54 `default`), and a text seen again in a talk on the same topic half as often (9% before, 4% to 5% after). Then five more from the karaoke catalogue (section 8, D57: a wall of text with one point highlighted, an alignment chart, red flags, reviews with stars and a fake error message), with no errors in 62 benchmark talks over seeds that bring each of them up: 39 by OpenRouter's free models in four runs, as the prompt was sharpened between them (longer points for a wall, a one-star review last, buttons and cells of the talk's own, within their lengths, and playful errors, worded as computers word them), 389 of 390 slides by the model, $0, every talk the same made again; and 23 classic ones, 15 `default` and 8 `ted`, every one the same made again. Then real facts (section 11, D60, 2026-11-08): a talk a language model writes gives up to three of its slides of history, fun facts, quizzes and big numbers a real fact each from Wikipedia (the lead of the topic's article, and the day's events), none naming a living person and none of death, war, disasters, crime, politics, race or faiths, which the model twists, and classic talks get half of their fun facts and quizzes real (Wikipedia's with a twist, Open Trivia DB's), credited, and flavour texts (useless facts, dad jokes, advice slips: the user's yes of 2026-11-08); in 49 live talks with them (24 by OpenRouter's free models, $0; 7 by Claude Haiku; 18 classic) no error but one classic talk whose picture came out differently when made again (as the same talk did before the facts), and in the last ones the free models built on 9 of their 12 facts, Claude Haiku on 4 of 4. Then the user's review of 35 sample talks (2026-11-09): more TED-like talks and pictures on slides of text (D63), livelier diagrams and charts (D64), and livelier dares, closing slides, references, emoji and slide numbers (D65). Section 8's other candidates and the karaoke catalogue's are left for after 5.0.0) | More slide types for TED-like talks | native diagrams, big numbers, quiz, memes with live captions, social posts and more; a much larger, curated TED content pack; memes more often; what real PowerPoint karaoke decks do; personas that shape a talk; bolder themes; real facts to build on (section 11) | every new slide type passes the checks in classic and LLM mode |
| 7 (done, 2026-11-08: the startup pitch and the academic conference talk, each with its arc, its recipes, its content pack and its favourite personas and themes, and the process slide type (section 7, D56): 42 classic talks and 20 by OpenRouter's free models (199 of 200 slides by the model, $0) had no errors, every talk the same made again; then the corporate all-hands and the product keynote, the same way and with no new slide type (D59): 60 classic talks, 20 by the free models (198 of 200 slides by the model, $0) and 4 by Claude Haiku 5.5 ($0.006) had no errors, every talk the same made again. Pecha Kucha's timing is out, at the user's word) | New talk formats | pitch, academic, corporate and keynote, with their content packs (or in 5.1 if the TED work takes longer) | every format works in classic and LLM mode and passes the checks |
| 8 (done but for its week: talkgenerator.com has run `v5` since 2026-11-07, from GitHub by commit (D31) instead of a preview behind a switch, so its week ends on 2026-11-14; the docs and the deprecation warnings are in; Sign in with ChatGPT on the site waits for OpenAI's waitlist, after 5.0.0) | Integration | the site runs `v5` on the preview, then in production behind a switch; Sign in with ChatGPT on the site, if OpenAI has admitted it; docs and deprecation warnings | the site runs `v5` for a week without quota or memory incidents |
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
| D33 | Presenter names may be famous-name puns ("Albert Einstone" for geology), on by default: a famous person's name bent to fit the topic, never the real name as it is or a dictator's. Since the user's word of 2026-11-08 ("I'm fine with that"), puns on famous living people go too (till then only on someone no longer alive); their real names as they are don't (section 5.10). Real people's names as they are aren't a style. |
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
| D50 | A format's tag caps hold from a talk's first slide: an absolute cap is a number of slides (0: none at all, as the `interview` format's about-me slides), and a relative one a share of the talk's slides, rounded down but at least one, so that short talks keep every kind of slide (a strict rounding would leave talks of 3 and 4 slides without memes, diagrams, quotes and captioned pictures). A kind that only longer talks have says so by its weight: a section divider, in talks of ten slides or more. |
| D51 | Image credits are quiet: 7 points, aligned right, in the colour nearest the slide's background that reads at a contrast of 2.5 on what's behind their letters, their links in the same colour, and no band behind them anywhere; over a picture (any colour, grey too), light with a dark halo. They're for whoever wants to know a picture's source, and for its license: the design checks hold them to floors of their own (that contrast, by their halo on a picture; 6 points), not to the 4.5 and 12 points of a slide's texts. |
| D52 | What belongs to a picture comes in with it: a theme's frame, shadow, tape, window or rule around it names the element it belongs to (`part_of`), and every renderer that plays clicks shows and dims it with that element. No layout puts a panel behind one column of a slide. |
| D53 | A slide of a list of things shows its title and the list's frame from the start, and its things one by one, a click each, the punchline last (a pyramid from its base up, a tier list from its worst tier up, a quiz's answer after its options, an org chart's boss after its people); the shapes a thing is drawn on come with it. A slide of one thing (a big number, a post, a fun fact, a meme with one caption) shows at once. |
| D54 | A format's classic texts are a content pack, `talkgenerator/data/packs/<format>/`: a grammar per kind of slide, whose rules are lists of templates, and a manifest (`pack.json`) with the pack's version, what each version changed, and its slots, the rules the code fills in, with the variables their templates may use and the text field whose length their texts keep to; a rule is named by its grammar and itself ("karaoke.dare"), the pack's only one. The version goes up whenever the texts change. The TED pack (`ted`) serves the default, ted, interview and test schemas. Its templates speak of the topic as English does: `{seed.generic}` ("penguins", "coffee"), `{seed.one}` ("a penguin", "coffee") and, after a word of the template's own (an article, a possessive, an adjective) or before another noun, `{seed.bare}` ("The moon paradox", "a penguin expert"), never with a verb that has to agree with the topic; tests lint every pack. Presenter names stay in `data/text-templates` (every format's), and a meme template's boxes in `data/memes.json` (its classic captions are the pack's). |
| D55 | A seed gets only wikiHow's actions about it (`wikihow.about`): with one of its telling words in any form (its rarest word, and its others rarer than 5.5 on the Zipf scale), or with one of the telling words of its related words (rarer than 5.0); and none of the worst (`wikihow.unfit`): none with a word a slide shouldn't make light of, a faith, violence, hate, death or hard drugs, but crude ones stay ("Clean Your Penis" for cleaning), as much of classic talks' humour is crude. WikiHow pads a search it knows little about with its most popular how-tos and with loose matches. The user chose both on 2026-11-08: related actions over the seed's own words only and over leaving out just the padding (36 of 39 sample topics and 29 of 39 of the seeds that slides wander to keep some actions), and crude ones in. |
| D56 | A talk format beyond the TED-like talks is a presentation schema with a `Format`: a brief for the language model, on a line of the request of its own, what its titles and its presenter's job are like (with the persona's), weights over the personas and multipliers on the theme families (with the persona's), and an arc: its parts in order, each with the fewest and the most slides it has and a rank, which lays out a talk of any length from its length alone (a short talk keeps the parts of the lowest ranks, a long one gives them more slides and has free slides between them). A part's slide generators weigh in on its slides only, so every persona keeps the arc; the format's other slides fill the free slides, and stand in for a part's slide that can't be made. A format reuses the slide types there are, with recipes and a content pack of its own, and gets a new type only where none draws what it needs (the process, for an academic talk's method). |
| D57 | The next karaoke types (section 8) are picked from the catalogue's next ones for laughs first: a wall of text, an alignment chart, red flags, reviews and a fake error message. A wall of text is fine print on purpose, at the one size that fills its slide, which the design checks hold to a floor of its own (9 points, as the credits have theirs); its one click highlights its punchline. A review's stars are drawn and written ("4/5"), so they read in every renderer and font, and an error message comes up whole, as a fun fact or a dare does. Words talkgenerator adds (an alignment chart's axes, "Continued on next slide") are in the talk's language. |
| D58 | A vision model can pick a talk's pictures (the vision pick, 10.3), off by default (`vision_pick=`, `--vision_pick`), for the pictures of planned slides only, in one request a talk once its last slide is settled: each picture among the finder's own and up to three runners-up, which the finder keeps in order, without a draw of the talk's dice (so a talk finds the same pictures with it or without it, before the pick), its own source's first; on one contact sheet, a row a picture, with what it asks for beside it, the candidates in an order the seed shuffles. The model says what each row's candidates show, then picks one or none; a pick takes the finder's picture's place once it passes the finder's checks, and "none", a failure, an answer later than 30 seconds or a budget that doesn't allow the request keep the finder's. `on` asks the talk's own model when it reads pictures, else OpenRouter's free vision models without thinking (not the free router). The request is the talk's (its ledger and budget), never names the presenter it was given, and replays from a cassette, which keys the sheet by its candidates and never keeps its bytes. talkgenerator.com may turn it on for the free models' talks once it hands over `slide.updated`: one more free request a talk. |
| D59 | The corporate all-hands, or quarterly business review (`corporate`), and the product keynote (`keynote`) are formats as D56 has them, with no new slide type: an all-hands goes from its agenda through the KPIs against their targets, the quarter's wins, the roadmap, an org change and the synergies to the ask of everyone and Q&A, a keynote from a big opening statement through the one idea, the reveal, the features, a live demo and the price to the "one more thing" and a closing line. A management consultant presents more of the all-hands, a startup founder or a motivational speaker more of the keynotes; their themes are the corporate families, and dark minimal and clean keynote, more often. A part's slide whose kind's cap the format's free slides or an earlier part would take first goes without that kind's tag (an all-hands' ask), so that a talk of any length keeps every part. Pecha Kucha's timing is out (the user's call), so these four are milestone 7's formats. |
| D60 | Talks a language model writes get real facts (`talkgenerator.facts`): up to three of a talk's slides of history (a historical figure's quote, two old photos, a timeline), fun facts, quizzes and big numbers get one each, on their lines of the talk's request, with what to do with it (a fun fact keeps it true and twists it); slides of history get one of the day's events first (Wikipedia's "On this day", of the day the talk is made on; D73 replaced them with coincidences), a big number a sentence with a figure, a fun fact one that says how special something is, rather than what the topic is. They're sentences of the lead of the topic's English Wikipedia article (a topic in another language followed there from its language's Wikipedia), and the day's events; none for a topic that's a living person (English Wikipedia's "Category:Living people"), none that names one (of the articles its lead or its event links to), none with a word a slide shouldn't make light of, or of death, war, disasters, crime and accusations, politics or race (but a word of the topic's), none about real-world politics; when Wikipedia can't tell who's living, none that names someone. They're looked up while the talk's seeds are, from the cache of API responses (a week; a day's events a month) or within 8 seconds of the talk's start, after which the talk goes without them (a talk that's late may be a busy computer's: the next one asks again); a talk made again in a block of `same_answers` (a check) gets the facts the first one got (`http_util.keep`). A slide that builds on its fact (two of its telling words are in the slide's texts) credits its article ("Wikipedia: Penguin (CC BY-SA 4.0)", in a credit line that then starts with "Sources:" rather than "Image sources:"); the deck records every fact with its page, license and slide (`Deck.facts`, none for a talk without). Classic talks get them where they fit: half of their fun facts are a real sentence of the lead of the slide's seed's article, with a twist of the TED pack's (its version 4), and half of their quizzes a real question of Open Trivia DB's, of the topic's category by its Wikipedia description (animals for penguins; never celebrities, politics, entertainment, sports or mythology), each credited on its slide. `DISABLE_FACTS`, `DISABLE_WIKIPEDIA` and `DISABLE_OPENTDB` switch them off. Wikidata and REST Countries aren't used (section 11). Flavour texts too, which the user allowed on the public site on 2026-11-08 (`talkgenerator.sources.flavour`): a fun fact may build on a random useless fact (uselessfacts.jsph.pl), a dare dares the presenter to tell a real dad joke (icanhazdadjoke, about the topic's word in the singular if there are any, else of a random page), and the closing slide's line under its title is a real piece of advice (the Advice Slip); classic talks get them in half of their dares and two in five of their closing lines, in framings of the TED pack's version 5. They pass the facts' checks and their own (no insults, drink or faiths), name no living person (their capitalised words, as Wikipedia's articles), and are credited without a license (their sites state none); `DISABLE_USELESS_FACTS`, `DISABLE_DAD_JOKES` and `DISABLE_ADVICE_SLIPS` switch them off. A talk in another language than English gets no dad jokes or advice slips, which a slide says word for word (2026-11-09, section 5.9). |
| D61 | A talk can leave its format to its seed (`schema="random"`): the seed picks the persona first, then the format from a stream of its own, by `FORMAT_WEIGHTS` (the TED-like talk 8, the formats beyond it 1 each) times the persona's multipliers (`Persona.formats`: a startup founder ×12 for a pitch, a disgraced professor ×12 for an academic talk, a management consultant ×12 for an all-hands, a motivational speaker ×12 for a keynote), so each persona's favourite dominates and every format keeps a few talks in a hundred with every persona. Only the formats for talks take part: not `ted`, whose copyright-free images are a license policy (`open`) that goes with any format, nor `interview` and `test`. A format named weights the persona as before (D56). A talk can also say which personas its seed picks from (`personas=`): the seed picks among all of them first and again among those allowed only when that one isn't, so a talk keeps its persona whenever it's allowed. talkgenerator.com's talks leave their format to the seed, with the personas its visitor didn't switch off. |
| D62 | A talk can say which families a random theme can be of (`theme_families=`): the seed picks among all the families first, and again among the allowed ones only when that one isn't, by the same weights (the family's own times the persona's and the format's multipliers), so a talk keeps its theme whenever its family is allowed; a chaos deck's slides get themes of the allowed families too. A family named as the theme goes first. talkgenerator.com's settings let a visitor switch families off for "Surprise me". |
| D63 | Most talks are TED-like, and slides of text get pictures (the user's review of 35 talks, 2026-11-09; section 7). `FORMAT_WEIGHTS`: the TED-like talk 20, pitch and academic 1, all-hands and keynote 1.5; specialists ×15 or ×10: 70% of the talks over all the personas are TED-like (it was 57%), a specialist's favourite comes second to them in about two of five of their talks, pitches and academic talks are the rarest, every format keeps 2% or more with every persona. A format's arc keeps a share of its slides free first (`Arc.free`: a quarter for a pitch, an academic talk and an all-hands, 0.15 for a keynote), whose text-heavy parts wait for longer talks; free slides have more memes, gifs, Reddit's weird pictures and the format's own provocations (a picture filling the slide under a word or two in its voice). Big numbers and KPI tiles have an optional picture behind them or beside it, from a look of many sources (`backdrop`), three big numbers in four and half the dashboards, in every format; a slide whose optional picture isn't found goes without it. Statements' backdrops mix calm photos and the backdrop look. Reddit's weird pictures outweigh ShitpostBot's, memes weigh more. A pitch's product (and a keynote's) is searched as a gadget and, in a talk that generates pictures, drawn as an advertisement's product shot. |
| D64 | Diagrams and charts get livelier (section 8): a matrix has short, everyday names and comes out named, of dots (things where they belong, the deck's `MatrixDiagram.dots`) or bare; a scatter plot has clouds of eleven shapes, a fitted line now and then (`ChartSeries.trendline`, PowerPoint's own trendline) or named clusters in colours the layout engine picks apart (`ChartSeries.color`, a trend's lines' too); a diagram has a weird but related picture in one or two of its boxes 35% of the time, an image element with a box that appears with its box's text (optional image slots: a box without a picture still makes the slide); and a trend's named moment gets a picture by its point, on a click, where every renderer has the point: talk-generator-web's plot, which a PowerPoint chart with a picture is pinned to. The site draws the new deck fields on a branch of its own. |
| D65 | From the user's look at 35 sample talks (2026-11-09): a dare is a real challenge for the presenter to keep up, or something the whole audience does ("Audience participation"), a dad joke one kind among them; a closing slide ends its talk on a funny picture, a last tip or a callback to an earlier slide's picture, which the deck gives it (realizing a slide still knows no other slide); an academic talk's references are a slide type of their own, with a picture of one of the works (a book's cover or a paper's figure) most of the time; emoji come in front of a list's things now and then, only where a variant asks for them, measured 1.4 ems wide and drawn in an emoji font; and every slide is numbered of the deck's ("7/12"), small and in its family's style, the 2019 template's too. A recipe's variant can say that its slide takes no real fact or flavour text (`Variant.facts`). |
| D66 | A streamed talk can have spare slides (`stream_talk(spares=N)`, the user's idea, 13.1): N slides made as soon as the talk has started, one after another on a thread of their own and from random streams of their own (so the talk's slides come out the same with spares or without), each of another of 13 kinds drawn without pictures (`SPARE_WEIGHTS`, by weight times the persona's: a hundredth of a second, timed on 26 topics), about the talk's topic, or in a talk in another language a picture of the topic without text. Each comes as `slide.spare` (which spare, and the slide laid out in the talk's theme without a slide number: `DeckLayout.spare`) until the talk's last slide is settled; none after that, and none in the deck or its PowerPoint. talkgenerator.com shows one when a presentation goes on before the next slide is in, marked "spare" where the slide's number goes, and the next slide once the presenter goes on and it's in. |
| D67 | A streamed talk can give every slide but the title slide a time limit (`stream_talk(slide_seconds=S)`, the user's idea, 13.1), from when it could settle (the slide before it settled, and a planned slide's text came in). Out of time, it settles at once with what's quick: a planned slide as the model wrote it, without the pictures it can do without and with spare pictures of the talk's topic (three, found early) for the others; else a stand-in of the spare kinds about the slide's own seed (in another language, a spare picture without text). It's the talk's slide, in the deck and its PowerPoint, its notes saying it ran out of time, until the real slide comes after all: what it waited for goes on by itself, and once it's done, it takes the stand-in's place (a `slide.updated` with `late`, and in the deck), unless it repeats another slide or the talk's caps are full by then; `talk.finished` waits for it 20 s at most once the other slides are in (`LATE_SECONDS`). With nothing to stand in, it's waited for. Off by default: the same seed gives the same talk as long as no slide runs out of time. talkgenerator.com gives its streamed talks 8 s (5% of the slides with pictures timed for D66 took longer). |
| D68 | How much a language model does is a talk's level (`llm_level=`, `--llm_level`, `TALKGENERATOR_LLM_LEVEL`, and the MCP server's `--llm_level`, never a tool's argument: an Advanced talk costs more, which is the user's call, as the model is): `basic`, one request a talk, as before; `advanced`, where the model plans the talk first (`talkgenerator.plan.outline`), in an outline that's read while it's written: the talk's spine as a Basic request has it (title, presenter's job, thesis, the unsafe flag) and a running gag, then for every slide the word it riffs on (one of the words the dice offer it, its seed and up to three others that would have done, or a sharper one of its own) and its idea, in a short sentence: the point it makes, for a chart what it measures against what, for a diagram what its parts are, never the slide's texts or a description of its pictures (Claude Haiku copied an idea's "a gif titled 'Volcanoes'" onto its slide). Its slides are written as their ideas come in, in batches (`BATCHES`: the second slide alone, so the talk starts soon, then two, then three at a time), each in a request of its own, up to six at once, with the talk's spine and running gag in its system prompt and the plan of the slides before it; they come in any order, and are settled in order. Measured on 2026-11-09 with Claude Haiku 5.5 and Sonnet 5.5, on five talks at both levels: a request per slide made Advanced talks sooner than Basic ones but three and a half times as costly (none of a request's prompt is cached: Claude's cached prefix starts with the request's schema, a slide's own); batches made them sooner still in every talk (the first slide 1.5 to 11 seconds sooner, the whole talk up to 8.5 seconds sooner), in five requests, for about twice the tokens (Haiku about $0.003 a talk, Sonnet about $0.06). So a talk is Advanced by default on a model of your own that costs (Claude, OpenAI's, your ChatGPT plan's, OpenRouter's paid models) and Basic on free ones (whose free quotas count requests, and which are slow) and on any other (`outline.default_level`; the user's call, 2026-11-09, as long as it adds no time); `talkgenerator check` decides it before it records the model's answers. An outline that brings no spine, finds the topic unsafe, starts in English in a talk in another language, is declined (even halfway: what its batches wrote is dropped) or can't be afforded with its batches leaves a Basic talk, from the dice's words, and the deck says which level its slides were written at (`Deck.llm_level`). A real quote is searched for a theme the model writes for its slide (`text_query`, a word or two, at both levels), and then for the slide's concept: the concept ("the slide's subject in two to five words") found nothing on Goodreads and random lines on Wikiquote (an anime quote on a tea talk), where a plain theme finds real quotes about it (the user asked which was better than the model's own sayings, 2026-11-09). talkgenerator.com writes Advanced talks on a visitor's own API key or a paid OpenRouter model (its budget allows the outline and a request per slide), and Basic ones on the free models (Basic AI's, and a visitor's OpenRouter account's: the user's call, 2026-11-09), and says so under Generate and in the Language model tab. The words slides start from are things (from the user's look at a classic volcano talk with "Volcanoes vs. eruptive" and "Do you want glacial?", 2026-11-09): Datamuse tags its related words' parts of speech (`md=p`), and a seed, a language model's word to riff on, and a word a classic template speaks of besides its seed is a noun first of all (WordNet's too), familiar (Zipf 2.5 or more), no name, of a family of its own (no "eruption" after "eruptive", no "musk duck" for rubber ducks), and no word a slide shouldn't make light of; seeds wander two steps from the topic at most (penguins went to leafs, hockey and netball), and a phrase's from its words when its own related words are all of its family. |
| D69 | Talks explain their why early (the user's idea, 2026-11-09; section 7): a slide type of its own, `problem` (a heading on a sticker, the problem, a line under it that appears on a click; a picture of it behind it or one that shows it beside it, generated in a talk that generates pictures), on an angle the talk's dice pick (weird, everyday, the topic running into something else, typical of the topic, or a real how-to people look up on wikiHow: a flavour text for a planned slide in an English talk, a pack's template around one for a classic slide), one a talk at most (tag `problem_slide`). It opens a pitch's problem part in about three pitches in four, an academic talk's new first part, `motivation`, in four in five (which keeps it from three slides on: a ten-slide academic talk goes without future work), and comes third in about a quarter of TED-like talks. |
| D70 | A streamed talk can have early versions of its last slides (`stream_talk(early=N)`, the first layer of the user's layered safety net, 13.1): each that slide's stand-in, made from the talk's start on a thread of its own, about the slide's own topic, sent as `slide.early` at its place before the slide. It's none of the talk's slides, unless the slide runs out of time or can't be made: then it stands in for it if the deck allows it, so what a presentation showed stays. talkgenerator.com asks for them instead of spares, for the slides its presentation may reach before they're made. |
| D71 | Gemini writes talks (the user's "We should add support for Gemini too", 2026-11-10): `--llm gemini` (Gemini 3.8 Flash) or `gemini:<model>`, through Google's `google-genai` SDK (the extra `talkgenerator[gemini]`, 3.0 or later, on httpx2 as the other SDKs; it doesn't install in Windows on Arm's Python, where its tests skip), with `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), the key Gemini's image models take. It streams, holds the answer to the talk's JSON schema (`response_json_schema`; when Gemini finds a schema too complex, a 400 that names it, the schema goes as text, as with Claude's grammar), thinks at `low` (`TALKGENERATOR_LLM_EFFORT` sets Gemini 3's thinking levels; 2.5's models keep their own), reads pictures (so it picks its own talk's pictures), and is priced at the paid tier's list prices, checked on 2026-11-10, with the dates where Gemini 4 Argon's and 3.8 Flash's introductory prices end (`prices.PRICE_CHANGES`). Gemini's free tier is a key's (its Google Cloud project has no billing), not a model's, and talkgenerator can't tell it: a Gemini model counts as paid (Advanced by default, budgets at paid prices), and the docs say to ask for Basic on the free tier. It can't be talkgenerator.com's Basic AI: Google's terms allow only the paid tier for apps that serve people in the EEA, Switzerland or the UK, Google uses what the free tier gets to improve its products (people may read it), and its limits are per project and small (reported in October 2026: 20 requests a day on Gemini 3.8 Flash, 500 on the Flash-Lite models; the site's OpenRouter account has 1,000). The site takes a visitor's own Gemini key, as Anthropic's and OpenAI's (Advanced talks): one of AI Studio's auth keys (`AQ.`, every new key since 2026-05-28) or an older standard key (`AIza`), and `redact()` takes both. Live on 2026-11-10 (an `AQ.` key; samples in talkgenerator-update's folder 41), every slide of three 10-slide talks came as written: Gemini 3.8 Flash at Basic, one request of 2,190 tokens in and 772 out, $0.0045, 41 s; at Advanced, five requests, 6,587 in and 1,288 out, $0.0098, 36 s; Gemini 3.5 Flash-Lite at Advanced, $0.0063, 40 s. |
| D72 | A streamed talk can tell how far it is (`stream_talk(progress=True)`, from the user's feedback of 2026-11-10; 13.1): `talk.progress` from its very start, before `talk.started`, and whenever that changes, whole each time: the talk's stage (starting; asking, until its language model's first word; planning, while the model's plan comes in; writing, while it writes the slides; composing; finishing, once every slide is in and the talk waits for generated pictures, a vision pick or a late slide), every slide's own (waiting; planned, its idea in, at the Advanced level; written, its texts in while its pictures are looked up; ready), the parts of the plan that came in (the spine's fields one by one, counted inside its object as the model writes it, and the slides' ideas: a dot each on the site), and how many slides the model writes and wrote. A model asked again takes the talk back to asking. Off by default, so the events are as before. talkgenerator.com asks for it and shows it above its loading screen's atom: the stage in words with its count, and a mark for every slide that lights up as the slide gets further, with a notch where the curtain opens; its slideshow goes back on a tap on a slide's left third on a phone (on elsewhere; a mouse's click goes on anywhere, as in PowerPoint), keeps a swipe across from the browser's back gesture, and makes 8 slides by default (7 before). |
| D73 | Less text, more surprise (the user's feedback of 2026-11-10, section 8): half of the charts and diagrams try a picture first, in their place, under their title (`Kind.picture_first`: a real chart from the internet for a chart, a weird picture for a diagram), planned (the model writes its query) and classic (every schema wraps them: `PictureFirstSlideGenerator`), and are their text version when none is found; with a time limit per slide (D67), the text version stands in at once (before an early version, D70) and only the picture takes its place (`DISABLE_PICTURE_FIRST` switches it off). A chart's title says what it shows, never "X vs Y": a planned one that does gets the two things on its axes (`axes_from_title`), a classic one whose axes have titles a claim (`charts.chart_claim`). A problem slide's problem is a few words (60 characters, its line 60), in the hints and the TED, pitch and academic packs. A list's or a diagram's punchline breaks its pattern now and then (`PatternBreak`, the kind's, for every format): an emoji alone, a few words, or a picture in its place where the kind's layouts show one (red flags, reviews, an org chart's boss, a tier list's S tier, an alignment chart's chaotic evil: `engine._text_or_picture`), a list's 35% of the time, a diagram's a quarter (an emoji); the third of three captioned pictures 60%; classic ones as often (`slide_texts.broken`, the TED pack's short reviews and red flags, KPIs with no number, 12 of 53 three-caption rows); 42% of random-format talks have one (`DISABLE_PATTERN_BREAKS` switches them off). Slides of history (and fun facts, now and then) get a coincidence in place of the day's events: a moment of the topic's history and an event of the same year (its Wikipedia article's), side by side as if one caused the other, credited to both articles. The packs' versions: TED 8, pitch 4, academic 5. |
| D74 | Talks in other languages read as their speakers write them, and suggest their own topics (the user's request of 2026-11-11: "the random topic list should also have suggestions from that language", and "sometimes translations are weird, like 'graph' is translated to 'graf' in a Dutch one ... How come?"; 5.9). Where the weird words came from, by 37 probe talks on the same seeds: the words slides riff on are English (Datamuse's, which took Dutch "regen", rain, for regeneration's "regen" and wandered to "renovation" and "redevelopment", and knew nothing of "frietjes"), and such an English word ended up on a slide as it was or as a look-alike ("de geheime goaltender", "Vloeibare Healing", "geherontwikkeld"; "graph" is a word to riff on of "algorithms" and "mathematics", on the English list the site's ↻ button gave every language); the request is English, with English examples, kind names and facts (the free model's "Professoraat ...", "Over duizend soorten kaas bestaan", "There are over 58 million dogs in the US" on a French slide); and the models: on the same requests Claude Haiku and Gemini 3.8 Flash wrote natural Dutch and French, where the free router's two models (nemotron-3.5-super-vl and dots-3-note-preview, the only free ones that take a strict schema) wrote word for word and mixed in English ("hier comes de netwerk"). So: a talk in another language wanders from what its topic is in English (`slide_topic_generators.english_name`: the topic as typed when it reads as English, else the English Wikipedia article its own Wikipedia's links to, without its article, never a disambiguation page, within 3 seconds; else no wandering); the request marks its English parts ("A word to riff on: umbrella (English)", a fact "(in English: tell it in Dutch)", a hint's example "(in English: yours in Dutch)", an outline's "Its words (English)", whose riffs are in the talk's language), asks a slide's concept in English words (it's searched for pictures), and asks for the talk as a native speaker writes it (`prompt.native_line`: no English words left in, nothing word for word, no look-alikes, with the language's own example, `Language.false_friend`, and its title capitals, `Language.capitals`); English requests are as they were. A leading article doesn't count toward the four words that make what's typed a title ("le Tour de France", `titles.clearly_a_title`), and in another language the spelling fixes only put a known word's accents right (they made "os polvos", octopuses, "os povos", peoples). Every language has its own topic list (`data/topics.<code>.txt`, 422 to 443 topics: about two thirds of English's that say well in the language, in its words and with its articles, a third of its speakers' own lives, harmless as English's), which `topics.random_topics(language=)`, `check --random N --language` and talkgenerator.com's ↻ button use (the site's copies, `npm run refresh-topics`). After, on the same seeds: no Title Case titles from Gemini (5 before) or Haiku, English words to riff on on slides 3 in 16 talks (9 in 21 before), talks on their topics. What stays the models': the free models' word-for-word Dutch and English words, which the request can't fix; a better free model would (Gemma 4 isn't one the free router can pick: it takes no strict schema). Classic talks stay English (5.9). |
| D75 | A visitor's talks vary (the user's request of 2026-11-12: a talk shouldn't have "the same persona or same slide look ... for at least the next three slideshows", nor two academic talks or two pitches in a row, "but you can always use the default" TED-like talk, "because that one goes really broad"; 13.1): `stream_talk(formats=...)` (and `generate_presentation`'s) names the formats a talk with schema `random` picks from, as `personas` and `theme_families` name the personas and families (`presentation_schema_types.allowed_formats`, `pick_format(..., among=)`): the dice pick among all first and again among the allowed only when theirs isn't, so a talk whose format is allowed keeps it. talkgenerator.com keeps a visitor's last three talks' persona, look and format in their browser and leaves them out of the next talk's picks (the TED-like format never, and those the visitor switched off stay off); when that would leave nothing, the oldest go back in first. No command-line flag or MCP option: a single talk has no history. |
| D76 | Every talk ends clearly, and spends none of its slides on "Questions?" (the user's report of 2026-11-12: at the end of a slideshow on talkgenerator.com only the "8 / 8" in the presentation's corner said so, and going on did nothing; academic talks and all-hands spent one of their N slides on "Questions?" while TED-like talks end on conclusions, so some talks had less real content; 13.1): every talk ends with a closer (`talkgenerator.closers`), a slide after the ones it asked for, of its format's kind and in its language and look: a TED-like talk's "Thank you!" with the presenter's name and a small "Questions?"; an academic talk's "Questions?" with "Thank you for your attention"; a pitch's "Let's talk" with a made-up contact line (the presenter's first name at the domain of the startup its title names before a colon, or of the classic one named after its topic: "anna@penguinly.com"); an all-hands' "Questions?" and "Back to work"; a keynote's "Available today" with its product's name. A format names its closer in its `Format` (`closer=Closer(...)`, one definition a format; a format without one, the TED-like talk among them, gets `closers.DEFAULT`): its big words, the line under them and a small note, each a function of the talk's end (`Ending`: its language's words, presenter, title and topic), and `mark=True` for big words that ask a question. Its texts are talkgenerator's own words, in every talk language (`said("thanks")`, a `Language` field), a format's own words in every talk language (`in_every_language({"en": ..., "nl": ...})`, a ValueError for one left out), the presenter's name (`presenter`), or a function of its own (`contact_line`, `product_line`); so a new format adds its closer in one line of its `Format`, and `tests/test_closers.py` checks every registered format's closer in every talk language and theme family. It's a slide type of its own (`closer`: its words, a line under them, a small note and, under a question, a huge question mark beside them), laid out as the title slide is or with the mark, with the motifs' big pieces; the deck marks it (`DeckSlide.closer`), and its slides' numbers ("7/12") and the checks' counts leave it out (`Deck.counted()`); `stream_talk` sends it as one more `slide.ready`, right after the last slide (before slides that ran out of time come after all), and the .pptx ends with it; a plan written elsewhere gets one after its slides, as it gets its title slide before them. The arcs spend no slide on questions anymore: the academic talk's questions, the all-hands' Q&A and the pitch's closing went, with their pack texts (academic 6, corporate 3, pitch 5), and the TED-like "Questions?" is a plan's recipe alone (weight 0 in talks); D63's parts of text wait for the same lengths as before (`Part.shortest`: an all-hands' agenda for 11 slides, a pitch's market and business model for 11 and 12, an academic outline and acknowledgements for 12 and 13), so the slide "Questions?" had goes to a part of content (an academic talk's future work, a pitch's roadmap, a second KPI slide). talkgenerator.com shows the closer as a slide, with "The end" where its number would be; going on from it (a click, a tap or a key) brings the curtain down, once a full-screen presentation has given way to the window (nothing can be drawn over full screen), and the curtain opens on the talk's overview, at its first slide, with Present again, Download and New; Esc leaves the presentation as before, and a talk without a closer (from a talkgenerator before it) gets the same curtain after its last slide, once it's all made. |
| D77 | Decks of one family differ by more than their colours (the user, 2026-11-12: "now all kiddie-presentations all look the same"; section 9). A family can have several sets of decoration (`themes.Variant`: a motif, how likely a member has it, and the patterns its backgrounds can have with it), of which a member has one, from a stream of its own (so a member's colours, fonts, layouts and treatments are as they were; a family without sets keeps its one motif, `themes.variants`). `kids` has four, each as likely: crayon drawings (as before: bunting, squiggles, confetti, a sun and hills; pictures now in a box a crayon drew, the slide's number in a crayon circle), a sticker book (titles on white labels, stickers along the edges, pictures as stickers with a corner peeling off, a rainbow on the title slide, a prize rosette with a section's number, the number on a sticker), a school notebook (ruled or squared paper in its ink, a margin line that goes behind no text, punched holes or a spiral binding, a ballpoint underline or a highlighter under titles, ballpoint doodles, pictures taped in with washi tape, an exercise book's cover for the title slide, a circled number with doodled rays for a section) and paper cut-outs (construction paper a little uneven, each piece with a small shadow: a pinked strip under titles, layered quarter circles in two corners, hearts, stars, circles and leaves along the edges, pictures on paper mats turned a little, paper hills, sun and clouds around the title's card, a paper flower with a section's number). Their decoration is in the member's palette's colours (`motifs._paints`: its two accents, where one was made darker to read as a text as light as a crayon again, as far as it still shows on the paper, and its paper's own hue as a paint), where crayon drawings had a fixed rainbow of seven, so that kids' palettes show; only a sun stays yellow, a crayon drawing's hills green. And kids has two more palettes, lavender and pink paper (Open Color's), six in all, so that two crayon drawings are less often alike. A section's badge moved from the layout (`v5/kids-section`, which keeps its boxes) to the motifs, each set drawing its own. Only today's element kinds (shapes, texts; no polygon outlines, which the browser doesn't draw) and no outside assets, so PowerPoint, the previewer and talk-generator-web draw them as before. Measured: the design checks' decks (every kind of slide, and 179 slides of runs of a type) in a member of each set in each of kids' six palettes, 4,560 slides: no finding. The other families with one motif can get sets the same way. And seven new families, from the ideas of 2026-11-12 (the user: "let's do all of them"), none for laughs, each with palettes of its own: `sticky notes` (a workshop on a whiteboard: its aluminium frame and a tray with two markers on it, a marker's stroke under titles, sticky notes in Open Color's pastels with ideas scribbled on them as lines, no words, a cluster of them with dot-vote stickers on the big slides, pictures held up by magnets, the slide's number on a sticky flag), `corkboard` (cork with its grain as a pattern, in a wooden frame: the title on a pinned index card, pictures as polaroids, pinned or taped up, index cards pinned in free corners, on the big slides pins with a red string between them, where the string keeps clear of texts and pictures), `90s desktop` (every slide a window: a title bar in the accent with a document's icon, "TALK.PPT" and its three buttons drawn as shapes, bevelled edges, a taskbar with the slide's number in its tray, pictures in windows named as "PIC071.BMP", and a big slide of nothing but texts as a dialog box on the desktop, in the second accent, with a computer's, a folder's and a document's icons and the mouse's pointer: named for its decade, with no trademarked name or logo), `spreadsheet` (a grid, its rows' lines its pattern, with its columns' letters and its rows' numbers in header cells where nothing else is, the title a selected cell, pictures with selection handles, the slide's number on the open sheet's tab, in Calibri; one palette in dark mode), `Y2K` (pastel gradients from its own hues, sparkles and glossy bubbles, pictures in white rounded frames, a CD on the big slides, the slide's number on a glossy pill, and a new heading effect, `chrome`: three shades of silver in a dark outline that reads on the background, with a shadow of its accent), `70s retro` (browns, oranges and mustard on cream, avocado or brown, four rounded stripes along the top and left edges turning their corner, two stripes under titles, a sunset of stripes on the big slides where there's room, pictures as prints with round corners) and `glossy magazine` (big serif headlines, a hairline with a square of its accent along the top, a short thick rule under titles, giant quotation marks before a quote's first line or over it, pictures on an offset block of its accent's tint, the slide's number as the page's folio, an issue's roundel, "N°7", on the big slides). Their personas' favourites are D79's (`personas.py` is that branch's). Twenty-four families now, which moves the family a random theme's seed picks, as D44's five did. Measured as kids', in each of their palettes: 4,180 slides, no finding. |
| D78 | Slides of a surprising picture that the presenter has to explain, with little or no text (the user's request of 2026-11-12, as improv suggestions and story cubes give a performer something to explain; section 8): **Exhibit A** (an odd picture as the evidence in a case, beside an evidence tag or under an evidence marker, with a made-up case number and, half the time, a note of a few words; the deck letters a talk's exhibits in turn, as it numbers sections, so a later one is Exhibit B, of the first one's case: two a talk at most), **Pick one** (two pictures without captions, under "Pick one:" or a heading of the slide's own, an "OR" between them), a **picture equation** (a thing plus another thing equals a third, on a click: each a picture or an emoji, the model writing every thing's emoji and the dice picking which are pictures too, so that a thing whose picture isn't found, or doesn't come within the slide's 8 seconds, D67, is its emoji), **What do you see?** (over a face in something, Reddit's pareidolia, in talks with fair use; or over an inkblot, which a slide without a picture is: its layout draws it, polygons and ellipses mirrored about a card's middle, by the slide's dice, a quarter of the time in `default` talks and always in `ted`) and a **before and after** (two unrelated pictures under "Before" and "After", an arrow between them, the after on a click). One to three pictures a slide, drawn with the deck's texts, pictures and shapes (D37), so talk-generator-web draws them as it is; talkgenerator's words in all eight languages. Each has a kind for plans and the language model (with what each picture's query searches for), classic texts in the TED pack (version 9: notes, headings, titles and questions) with pictures of the slide's seed and its related words, two layouts (an inkblot two of its own), and a weight in the TED-like formats' middle as the karaoke types have (0.7 to 1), but no persona's multipliers yet (the work on personas and formats that follows weighs them, and reuses the types in its formats): over 500 seeds of 10-slide talks a language model writes, each comes up in 9% to 12% of `default` talks and 11% to 18% of `ted` ones (40% and 54% of talks have one), and an Exhibit B in 0.2% (0.6% of `ted` talks); as they took memes down from 49% to 40% of talks, memes weigh 7 now, from 5 (`MEME_WEIGHT`, the user's word of 2026-11-12), which keeps them in half of the talks (50%, 0.64 a talk) (samples in talkgenerator-update's folder 44, made while personas still weighed the new types and memes weighed 5). A slide that stands in for another, or a spare, looks no picture up: its "What do you see?" is an inkblot and its equation emoji, so both are spare kinds too (D66: 15 kinds now). |
| D79 | Six more formats and eight more personas (the user's "let's do all of them (unless some of them don't work out great)", 2026-11-12; sections 5.2 and 7): `infomercial`, `documentary` (a nature documentary), `court`, `museum`, `wedding` (a toast) and `book_report`, each an arc of parts on today's slide kinds with a content pack, a brief and hints, favourite personas and themes, and made-up names from the topic (a gadget, a Latin species, one harmless crime, a museum and its old master, the best friend who marries the topic, a book and its author); the personas `detective`, `infomercial_host`, `nature_narrator`, `museum_guide`, `best_man`, `game_show_host`, `alien_anthropologist` and `it_support`, the first five each the specialist of a new format. `FORMAT_WEIGHTS`: the TED-like talk 55 (was 20), each new format 1; specialists ×32 (×21 for the all-hands and the keynote), no multiplier under 0.7: 69% of talks TED-like over all 21 personas, 83% without one, a specialist's favourite in a third of their talks, every format about 1% with every persona (was 2%). A format named weights its specialist ×9. None dropped. Rebased onto D76 to D78: each new format has its closer, in all eight languages (an infomercial's "Call now!", a court case's "Court is adjourned", a book report's "The End", whose own last part went), the personas and the formats favour D77's families (a detective's and a court case's corkboard, IT support's 90s desktop, a consultant's spreadsheet...), a court case's evidence is D78's Exhibit A, and the personas weigh D78's slides (D78's own multipliers for the thirteen it knew, a game-show host's Pick one ×3). |

| D80 | Talks are playable at a glance (the user's review of 2026-11-13; section 8): fewer words on every slide (titles 45 characters, a talk's 50 in two to seven words, one thing a tier, three red flags, shorter posts, quizzes, reviews, facts and error messages, the content packs shortened to match), the presenter's job on a line of its own; a ranking's bars a click each from the top down, tiny ones and then the punchline's (a category build, each bar named by its data label); a trend's picture there from the start; a quiz labelled as one in the talk's language; build dots by the slide's number, a ring a click that fills on its click, drawn as the deck's shapes by every renderer; an agenda that announces later slides, which pick its items up; green, orange and red flags; a photo of the talk's world beside its title; sections and dares over a picture; a picture in every step of most processes; strong filters on backdrops alone; names a real person could have; a recurring character in a fifth of the talks, on two slides at most; e-mail domains that read as made up; coincidences only side by side, one real thing for a quote or a fun fact; a text kept whole up to what its slides held before D80 (TextField.room), a cut at a sentence, a clause or a comma, else with an ellipsis; a talk in another language asks its model once more before it comes out classic. |
D7 to D9, D13 and D15 to D26 were settled on 2026-11-05, D28 to D42 on 2026-11-07, D43 to D62 on 2026-11-08, D63
to D69 on 2026-11-09, D70 to D73 on 2026-11-10, D74 on 2026-11-11, D75 to D79 on 2026-11-12, and D80 on 2026-11-13; the others
follow from the design.

### Open questions

None. (The last, whether talkgenerator.com may show flavour texts without a license, the user answered on
2026-11-08: it may, D60.)

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
