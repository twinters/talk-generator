# talk-generator v5: design

This document explains how talkgenerator 5 works inside, and why. The code cites its sections, and the decisions in
section 17, by number (D1, D2, ...). The [README](../README.md) and the other files in docs/ explain how to use it.

## Contents

1. [Summary](#1-summary)
2. [Goals and constraints](#2-goals-and-constraints)
3. [What v5 keeps from v4](#3-what-v5-keeps-from-v4)
4. [Architecture: plan, realize, render](#4-architecture-plan-realize-render)
5. [LLMs](#5-llms)
6. [Agent mode: talkgenerator as a Claude Skill](#6-agent-mode-talkgenerator-as-a-claude-skill)
7. [Talk formats](#7-talk-formats)
8. [Slide types and variety](#8-slide-types-and-variety)
9. [Themes, layouts and design quality](#9-themes-layouts-and-design-quality)
10. [Images: sources, aesthetics and generation](#10-images-sources-aesthetics-and-generation)
11. [Text sources and content packs](#11-text-sources-and-content-packs)
12. [Determinism, seeds, tests and the paper baseline](#12-determinism-seeds-tests-and-the-paper-baseline)
13. [talkgenerator.com](#13-talkgeneratorcom)
14. [Automated quality checks](#14-automated-quality-checks)
15. [Releases and compatibility](#15-releases-and-compatibility)
16. [Milestones](#16-milestones)
17. [Decisions](#17-decisions)
18. [Sources](#18-sources)

## 1. Summary

Every talk becomes a deck, versioned JSON data that every renderer draws. A language model or the classic generator
writes the slides Python picks, or Claude plans the talk; talkgenerator finds, licenses and credits the images.

## 2. Goals and constraints

### Goals

1. Talks a language model writes, coherent across slides, in several languages.
2. Many ways to bring a model, Claude through the Skill included.
3. Good talks without a model too: grammars, templates and content packs.
4. Formats beyond the TED talk (section 7).
5. Varied themes and layouts, extremes included.
6. More image sources, weird ones above all, filtered to a look, and generated pictures.
7. Slides that stream, so a browser shows each one once it's ready.

### Constraints

- A deterministic mode without a language model, for tests and as the paper's baseline.
- Automated quality checks (section 14).
- No script for the presenter, who improvises: slide notes reach the PowerPoint only with `--debug_notes`.

## 3. What v5 keeps from v4

The classic generator is v4's, the method of the [2019 paper](https://doi.org/10.1007/978-3-030-16667-0_9). It makes
talks without a language model (`--llm none`) and the slides a model or plan doesn't deliver, and picks those a
model writes:

- `PresentationSchema` gives each slide a seed word: the topic every 3 to 5 slides, related words in between
  (`SideTrackingTopicGenerator`), from ConceptNet (whose public API has been down since late 2025) or Datamuse
  and WordNet.
- Slide generators are picked by weight (`PeakedWeight`: title first, conclusion last), capped by tags
  (`max_allowed_tags`), and repeats are rejected (`allowed_repeated_elements`).
- Content generators combine tracery grammars, templates with pipes (`{seed.plural.title}`) and sources.
- A slide that misses content (`Slide.missing_content()`) makes way for another.

v4's command line, settings and Python API still work ([Migrating from 4.x](migrating-from-4.md)).

## 4. Architecture: plan, realize, render

1. `PresentationSchema` (`talkgenerator.schema.presentation_schema`) picks every slide's seed word, and its slide
   generator as the format and the persona weight them, each from its own seeded random stream (section 12).
2. A planner decides what each slide says: the classic slide generator itself; a language model, in one request or,
   at the Advanced level, after an outline (D68), read while it writes (`talkgenerator.plan.prompt`, `outline`,
   `stream`); or a `TalkPlan` that picks its own slides, by Claude or by hand (`talkgenerator.plan.external`).
3. The realizer (`talkgenerator.plan.realize`) makes each planned slide with its recipe (`talkgenerator.plan.kinds`:
   a slide kind tied to a slide generator), trimming its texts and finding its images (`talkgenerator.images.finder`).
   What can't be made as planned comes from the recipe's classic generator. Slides are realized in parallel and
   settled in order, so none repeats what an earlier one used.
4. The slides become a `Deck` (`SlideDeck.to_deck()`), laid out in its theme by `talkgenerator.design.engine`.
5. `talkgenerator.render.powerpoint.render_pptx` draws a classic deck in the 2019 template and a themed one as shapes
   (`talkgenerator.render.shapes`); `talkgenerator.render.preview` draws previews.

Plans and decks are strict pydantic models with JSON Schemas (`talkgenerator schema plan|deck`). A `TalkPlan` holds
the talk's title, presenter and thesis, and per slide a kind, recipe, concept, texts and image queries (never
addresses). A `Deck` holds the talk's metadata and its slides' elements, credits and notes (in a themed deck, each
element boxed on a 1920×1080 canvas), but no image bytes, so it can be streamed to a browser, saved and drawn again.
`generator.stream_talk()` streams a talk slide by slide, as events (`talkgenerator.models.events`,
[Python](python.md)).

## 5. LLMs

### 5.1 Where LLMs plug in

| Step | With a language model | Classic |
| --- | --- | --- |
| Slides' words | Python's: things that wander from the topic and back (D68: familiar nouns, at most two steps out); at the Advanced level, the model picks or sharpens them | the same, from Datamuse and WordNet |
| Talk spine | title, thesis, the presenter's job and name (section 5.10); at the Advanced level, a running gag | a classic title; a name from the pack or tracery |
| Slide text | every field: titles, captions, statements, chart questions, fake facts, callbacks | the slide's classic generator |
| Image queries | a query per image slot (and a prompt, for a generated picture) | the slide's word |
| Coherence | one thread: a thesis, callbacks, no repeated jokes | independent slides |
| Picking pictures (optional) | a vision model, from one contact sheet per talk (section 10.3) | the image finder's pick |

Content packs are drafted with a language model and curated by hand, never written while a talk is made.

### 5.2 Python picks the structure, the LLM writes the words

talkgenerator picks the talk's skeleton with its seeded random generator, as the 2019 generator picks slides: slide
kinds per position within the format's tag caps, and image sources per slot. The dice add a persona and one of its
angles, whether a made-up person may come back as a running gag (one talk in five, on two slides at most: D80), and
every slide's word to riff on; the model writes the words (`talkgenerator.plan.prompt`). The dice stand in for
temperature, which current Claude models don't take, against models' drift towards the same jokes; the same seed with
recorded answers gives the same talk. Format rules stay in Python, where tests hold them, and the classic generator
can fill any slide of the skeleton.

The system prompt asks for few words, pictures that do the talking, a deadpan expert voice, gaps for the presenter to
fill, lists that set a pattern and break it, callbacks, and no tags tacked on to a line ("twice", "on a Tuesday"),
which `plan.realize.untagged` also takes off English texts (D85).

**Personas** (`talkgenerator.personas`, D47). The seed picks one of 21 (a disgraced professor, a kindergarten
teacher...: `personas.catalog()`) from a stream of its own, before the format, theme and slides; `persona=`
(`--persona`) names one, and `none` gives the format's own talk. A persona brings:

- a voice and angles for the model (the retiree's dice also pick one of 16 old jobs: `Persona.lived`);
- multipliers on the format's slide weights by the generators' tags, in classic and planned talks: tests keep each at
  0.2 or more, and each tag's average over the personas near 1, so the mix of all talks stays the formats';
- a title hint for the model, and templates for half of a classic talk's titles;
- weights over the name styles, how the presenter goes by ("with Prof. before the name"), and the presenter's job;
- multipliers on the theme families, for a random theme, and favourite picture looks, searched first
  (`ImageContext.persona_looks`);
- multipliers on the formats, for a talk whose seed picks it (`schema="random"`, D61; section 7): nine personas, five
  of D79's among them, give a format of their own in about a third of their talks.

`personas=` (`--personas`, D61) limits the seed's pick: it picks among all first, and only when that one isn't
allowed, among those that are, so an allowed persona stays. The deck and `talk.started` have the persona (`name`,
`label`, `voice`, `angle`). `--persona none` with a classic theme, classic names and no model comes closest to a talk
of 2019.

### 5.3 One streamed call per talk

- The request has a static part, the system prompt, and a dynamic part: what the talk is about, its language, format
  and persona, every slide's kind, fields and word, and a JSON Schema for this talk's answer.
- The model writes the spine first, then the slides in order. As some models write properties in alphabetical order,
  the spine is one object, `about`, before `slide_02` to `slide_10`. `plan.stream.ObjectReader` hands over each slide
  as soon as it's complete, so slide 2 is realized while the model writes slide 3: `stream_talk` sends `talk.started`
  once the spine is in, then a `slide.ready` per slide.
- Each slide's texts are checked against its kind (`talkgenerator.plan.realize`); a slide that doesn't come out is
  classic (in another language, see section 5.9).
- At the Advanced level (D68, `talkgenerator.plan.outline`), the model first writes an outline, read as it comes in:
  the spine and a running gag, then every slide's word (one the dice offer, or a sharper one) and idea. The slides are
  written as their ideas come in, in parallel batches (one slide, then two, then three at a time), each with the plan
  so far: five requests for ten slides, done sooner than a Basic talk. An outline that fails before its spine is in
  (an error, a refusal, a spending limit, an unsafe topic) leaves the talk Basic.
- `regenerate_slide` swaps one slide of a finished deck for a classic one, without a model.

### 5.4 Provider interface

`talkgenerator.llm.base`:

```python
class TextProvider(ABC):
    id: str  # "provider:model", such as "anthropic:claude-opus-5-5"
    capabilities: Capabilities  # structured output, streaming, vision, output limit

    def complete(self, request: TextRequest) -> TextResponse: ...
    def stream(self, request: TextRequest, on_text: Callable[[str], None]) -> TextResponse: ...
```

Requests and responses are plain data, the same for every provider. A `TextResponse` has the text, the parsed JSON,
how it finished (`complete`, `truncated` or `refused`), the model that answered, its tokens and its cost. Whatever
goes wrong raises a `ProviderError`, and the talk falls back. `talkgenerator.llm.providers` makes a provider from a
spec (`--llm`, `TALKGENERATOR_LLM`):

| Spec | Extra | Default model |
| --- | --- | --- |
| `openrouter[:<model>,<fallback>...]` | `openai` | the free router, `openrouter/free` |
| `anthropic[:<model>]` | `anthropic` | Claude Opus 5.5 |
| `openai:<model>` | `openai` | none |
| `gemini[:<model>]` (D71) | `gemini` | Gemini 3.8 Flash |
| `chatgpt[:<model>]` | `openai` | the first model the account lists |
| `replay:<cassette.json>` | | recorded answers, by a hash of the request (offline tests, a talk made again) |
| `none` | | classic talks |

`talkgenerator[llm]` installs all three SDKs; without the one it needs, a talk is classic. A request can show
pictures, for the vision pick (`Message.images`): an `ImagePart`'s bytes never go into a cassette or a log, and its
name keys the recorded answer.

### 5.5 Provider facts

Without `TALKGENERATOR_LLM`, your ChatGPT plan's models write talks once you've signed in, else OpenRouter's free
models when there's an OpenRouter key, and else talks are classic (`settings.llm_spec`): a model that costs only
writes when it's asked for.

- OpenRouter (`llm.openrouter`): free models (`:free`) come and go and are rate limited by the minute and the day, so
  the default is the free router, which picks one; a request whose model fails before it writes goes out once more,
  and models named after the first are fallbacks. Only providers that hold to the strict schema get the request
  (`require_parameters`). The free router writes without thinking (effort `none`), so the first slide comes within
  seconds; a model that must think gets the request again at `minimal`. `talkgenerator login openrouter`
  (`llm.login`) gets a key by OpenRouter's OAuth with PKCE.
- Claude (`llm.claude`): no sampling parameters; effort `low` (Opus 5.5 always thinks, so requests leave room for it);
  JSON from structured outputs (`output_config.format`), or the schema as text when Anthropic finds it too large a
  grammar; the system prompt marked for caching. A refusal (`stop_reason: "refusal"`) runs again on the model
  Anthropic recommends where server-side fallbacks exist (`fallbacks: "default"`); refused again, the talk is classic.
- Gemini (`llm.gemini`, D71): structured outputs, or the schema as text when it's too complex; effort `low`. A
  free-tier key looks like a paid one, so talks are Advanced unless they ask for Basic.
- OpenAI (`llm.openai_responses`): the Responses API, with answers not stored (`store=False`).
- Sign in with ChatGPT (`talkgenerator login chatgpt`, `llm.chatgpt_login`) follows
  [OpenAI's docs for open-source apps](https://developers.openai.com/siwc/token-sharing-open-source) that run locally:
  OAuth with PKCE (a callback on `127.0.0.1`), a first sign-in that registers talkgenerator, refreshed tokens, and a
  fresh sign-in after an `invalid_grant`. Requests count toward the plan's usage (Plus or Pro).

### 5.6 What a talk costs

A classic talk makes no request, and a Basic talk one streamed request. An Advanced talk is five requests for ten
slides (an outline and four batches): talks are Advanced by default on models that cost their owner, and Basic on
free models, whose quotas count requests (D68). Asking once more (sections 5.8 and 5.9) and a vision pick add a
request each; generated pictures count apart (section 10.5).

Every request, failed or stopped ones too, goes in the talk's ledger (`talkgenerator.llm.ledger`), which the deck's
`usage` sums up, and a talk can be held to a spending limit, such as free models only.
[Language models](language-models.md#costs) says what each route costs.

### 5.7 Keys, tokens and logs

- Settings: `TALKGENERATOR_LLM`, `TALKGENERATOR_LLM_EFFORT`, `TALKGENERATOR_LLM_LEVEL`, the providers' keys and
  `DISABLE_LLM=1` ([Keys and settings](configuration.md#language-models)).
- `talkgenerator login` keeps keys and tokens in `credentials.json` in talkgenerator's config folder
  (`talkgenerator.util.credentials`), readable only by you; `OPENROUTER_API_KEY` goes before a stored key.
- Keys and tokens never end up in logs, the HTTP cache, deck JSON or error messages: `http_util.redact` takes them
  out, and the cache ignores the parameters and headers that carry them.

### 5.8 Text safety

- The spine has an `unsafe_topic` flag. A model that sets it is asked once more, as free models get it wrong now and
  then; set again, the talk is classic.
- The system prompt rules out quotes attributed to real people (real quotes come from Goodreads and Wikiquote), real
  private persons, slurs, sexual content, mocking people for who they are, and real-world politics unless that's the
  topic.
- As a text is realized, leftover template code (`checks.deck.leftovers_in`) and, in English, real-world politics
  (`checks.deck.real_politics`) leave it out; a slide that misses a text it needs is classic.
- A refusal (Claude's `stop_reason: "refusal"`, a content filter elsewhere) drops what the model wrote: the slides
  are classic, never an error. `talkgenerator check` runs the same checks on decks.

### 5.9 Languages

A language model writes talks in `en`, `nl`, `fr`, `de`, `es`, `it`, `pt` or `sv` (`language=`, `--language`;
Swedish: D41), in the language rather than translated, so its wordplay works. The classic generator stays English
(grammars for every language would be much upkeep), so without a model such a talk is classic and English, as the
logs say.

- `talkgenerator.plan.languages` has talkgenerator's own words ("By ...", "Yes", the closer's) in every language;
  image queries and slides' concepts stay English, which picture sources search best.
- A slide that doesn't come out becomes a picture of its concept without text. Kinds with texts from English sources
  (`texts_from`: real quotes) and the English flavour texts (`facts.look_up`, D84) are left out.
- The request asks for the talk as a native speaker writes it (`prompt.native_line`, D74): no English left in, nothing
  word for word, no look-alikes (`Language.false_friend`: a graph is a "grafiek" in Dutch, not a "graf"), the
  language's title capitals (`Language.capitals`), and its English parts marked as such.
- Words to riff on wander from the topic's English name (`slide_topic_generators.english_name`): the topic when it
  reads as English, or the English article its Wikipedia article links to, if found within three seconds (else they
  don't wander).
- `languages.reads_as_english` reads the streamed spine with NLTK's stopwords: a spine in English stops the stream
  (`llm.base.AnswerStopped`), and the model is asked once more (`talk_request(answered_in_english=True)`), as is one
  that wrote no slide (D80).
- A leading article doesn't count toward a typed title's four words; the spelling fixes only put a known word's
  accents right, and leave compounds as typed in nl, de and sv (`Language.compounds`).
- `check_language` flags texts that read as English, minus words that only look English
  (`Language.english_lookalikes`).
- Each language has its own topic list (`data/topics.<code>.txt`): two thirds of the English topics in its own
  words, a third from its speakers' lives.

### 5.10 Presenter names

`talkgenerator.names`. A talk without a given name gets one in a style its seed picks among those switched on
(`name_styles=`, `--name_styles`; `names.catalog()`), favouring names that could pass for a real person's (D80), as
the persona nudges: `pun` ("Prof. Anna Tomy" for medicine), `fun_surname` ("Linda Hivesworth" for bees), `famous_pun`
("Albert Einstone" for geology, D33), or, off by default, `classic` (tracery's, as in 2019).

- A given name (`presenter=`, `--presenter`, then a plan's `presenter_name`) goes first, and never reaches a
  provider: the title slide is made locally.
- The model writes what the name plays on (`name_plays_on`, not shown), then the name, in the talk's language, then
  the presenter's job, which agrees with it. The prompt shows two names of the style for other topics; a copy is
  turned down.
- `names.clean` also turns down names over 45 characters, with template code, digits, brackets or commas,
  placeholders, dictators', a famous living person's real name as it is (`names._LIVING_PEOPLE`: a pun such as
  "Taylor Swiftly" goes), and real names the pack bends ("Marie Curie"). The list also keeps generated pictures from
  showing those people (`names.real_person`).
- Without a model's name, a topic the pack has (`data/text-templates/presenter_names.json`, D34, drafted with a
  language model and curated by hand) gets one of its names, and others a classic one.
- Style, examples and pack names come from the seed (streams under `presenter`).

### 5.11 Topic or title

What's typed can be a topic ("penguins"), a premise ("Cats are liquid") or a title ("Why I Joined a Penguin Cult")
(D32): `topic_or_title=` in `generate_presentation()` and `stream_talk()` (instead of `topic` and `title`),
`--topic_or_title`, and the MCP server's `generate_talk`. It's read so (D35):

- In quote marks, it's the title, word for word (`titles.quoted`).
- Clearly a title (`titles.clearly_a_title`: a part of four words or more, or a question or exclamation), it stays the
  title, its slips fixed: the model's version when it's recognisably the typed one (`titles.recognisable`), else the
  typed one as talkgenerator fixes it (`titles.polished`). Its topic is its rarest word.
- Anything shorter is the topic or a premise, for a funnier, more specific title of the model's; a misspelled input
  goes with its meaning, and `check_title` warns about a title that echoes the request.
- Misspellings are fixed first (`word_frequency.fix_spelling`): a rare word becomes a far more frequent word one edit
  away; made-up words stay.
- For a short input in an English talk, the dice draw one to three classic titles about the topic (the format's, a
  wikiHow "How to ...") and how they go (`titles.CLASSIC_TITLE_WAYS`): to pick from, as inspiration, or not at all.
- Without a model, or a title from it, `titles.guess` also takes what starts like a title ("How to", "Why", "My", in
  English or the talk's language) or makes a claim ("is", "can") as one, kept as typed; a topic gets the classic
  title.
- The deck and `talk.started` record `topic_or_title` = {`text`, `read_as`}.

## 6. Agent mode: talkgenerator as a Claude Skill

Claude can write the talk, on your own Claude plan, while talkgenerator does what an agent shouldn't improvise:
finding images it may use, crediting them, laying out the slides and rendering the deck.
[Use it with Claude](use-with-claude.md) says how to set it up. Plans written outside talkgenerator, section 4's
`external` planner (D2), go through `talkgenerator.plan.external`:

- `talkgenerator schema plan` prints the plan format as a JSON Schema, and `talkgenerator formats --details [--json]`
  lists a format's slide kinds, with their texts, length limits, image slots and recipes.
- `talkgenerator render plan.json -o talk.pptx` (or `plans/*.json`) validates the plan, realizes it with your keys or
  the keyless sources, renders it, and prints a JSON report: every slide's outcome (`as planned`, `classic` or
  `left out`), its problems and warnings, and what each image was searched with. Claude fixes the plan and renders
  again.
- A plan holds texts, search queries and generation prompts, never image URLs, so licensing, credits and filters stay
  in the library. An image may also be a picture of your own, next to the plan.
- A slide's recipe is one of the format's slide generators, by an id such as `two-captions-gifs`: it makes the slide
  the classic way when the planned one can't be made. A slide without one gets its kind's default.

The Skill is `skill/skills/talkgenerator/`: `SKILL.md` (when to use it, the workflow, what makes a good karaoke deck,
safety rules), the slide references that `talkgenerator formats --details` writes (`tests/test_plans.py` keeps them up
to date) and an example plan. `skill/` is a Claude Code plugin, listed by the repository's
`.claude-plugin/marketplace.json`. Where Claude can't run commands, the Skill has it hand over the plan as a JSON file
for you to render. It works without keys, with fewer sources; neither the package nor the Skill ships any.

`talkgenerator mcp` (`talkgenerator/mcp_server.py`, the `mcp` extra) offers the same functions as tools to clients
without a shell, such as Claude Desktop: `list_formats`, `describe_format`, `get_plan_schema`, `render_plan` and
`generate_talk`. The client starts it on your computer, over stdio, with your keys; there is no hosted MCP endpoint
(D20). The tools save only in the output folder (`--output_folder`), make one talk at a time and send a progress
notification every 5 seconds; `generate_talk` takes the language model from the settings only, so a tool call can't
make a paid model write. The server and the Skill wrap the same `render` code; the Skill adds the know-how.

## 7. Talk formats

A talk format is a kind of talk, and each is a presentation schema (`talkgenerator.schema.presentation_schema_types`).
The TED-like ones are `default` (images from every source), `ted` (copyright-free images only: the `open` license
policy, section 10.2) and `interview` (no slides about the presenter); `test` is for testing talkgenerator. Ten more
each have a module in `talkgenerator.schema.formats`, with a `Format` (D56, D59, D79).
[The command line](command-line.md#formats-and-license-policies) lists them, and
`talkgenerator formats --details --format pitch` shows a format's arc and slides.

A `Format` holds:

- `brief`: what the format is, for the language model, on a line of the request of its own. TED-like talks have none.
- `title_hint` and `job_hint`, given with the persona's: an academic talk's title is a paper's, with a colon and a dry
  subtitle, and its job an affiliation.
- `personas`: weights over the personas, for a talk whose seed picks one (D56). The format's specialist weighs 9 in
  most formats, a few others 1.2 to 2.5.
- `themes`: multipliers on the theme families, with the persona's (`startup` for a pitch, `dark minimal` for a
  keynote, D77's `corkboard` for a court case).
- `arc`, below; `closer`, the slide after the last (D76); and `scene`, its world, for the photo beside the title (D80).

The module also has the format's slide generators, each with a recipe for the language model and a classic version
from the format's content pack (`talkgenerator/data/packs/<format>`, section 11), so a format works without a language
model; and its tag caps (`CAPS`), which let most kinds of slide come once. Classic texts name things made up from the
topic, the same in every run (`talkgenerator.schema.formats.startup`, `species`, `artist` and the like: "Penguinus
giganteus"). A new format needs a module, a content pack, a line in `plan.external.FORMATS`, a weight in
`FORMAT_WEIGHTS` and its schema registered.

The formats reuse the slide types there are (a funnel for a pitch's market, an iceberg for an academic talk's
limitations) and add two (`models.classic.FORMAT_TYPES`): an academic talk's `references` (section 8), and the
`process`, three to five steps joined by arrows that appear one by one, the last one the punchline (a method, how a
product works), side by side when their words are short enough, else one under the other on bands. A court case's crime
is harmless, a museum tour shows no portrait under a made-up name (a museum's portrait may show someone real), and a
wedding toast names no drink.

An arc (`talkgenerator.schema.formats.arcs`, D56) is the parts a format's talks go through, in order, each `Part` with
the fewest and the most slides it takes, and a rank. `Arc.layout` lays a talk out from its length alone, the same in
every run. First a share of the slides between the first and the last stays free (`Arc.free`, D63: a quarter, a fifth
in a documentary, 0.15 in a keynote). Then the parts the talk has room for get their fewest slides, the lowest ranks
first, while a part of text waits for a talk of its `shortest` length (D63). Then they get more slides, by rank, up to
their most, and the free slides go between them.

A part's slide generators weigh in on its slides only (`InPart`), so a persona's multipliers move a part's slides
between its kinds (a founder's traction is KPI tiles more often than a hockey stick) but never out of the part. The
format's other generators (`Free`) fill the free slides: memes, gifs, Reddit's weird pictures, real charts, and the
format's provocation, a striking picture under a word or two ("Disrupt.", "Peer reviewed."; tag `provocation`, a slide
in ten at most). They stand in for a part's slide only when none of its own generators can make it, or now and then
where the part's `others` allows it (an academic talk's references, D82). `talkgenerator check` warns of a talk that
misses a part or has one out of order.

| Format | The talk | Arc | A five-slide talk keeps |
| --- | --- | --- | --- |
| `pitch` (D56) | A startup about the topic, pitched to investors | problem, solution, market (from 11 slides), business model (from 12), traction, competition, team, roadmap, ask | problem, solution, traction, ask |
| `academic` (D56) | Research on the topic, at a conference | motivation, outline (from 12), related work, method, results, limitations, future work, acknowledgements (from 13), references | motivation, method, results, limitations |
| `corporate` (D59) | A company's all-hands or quarterly review | agenda (from 11), KPIs, wins, roadmap, org change, synergies, ask | KPIs, wins, roadmap, org change |
| `keynote` (D59) | A product made of the topic, launched on stage | opening, idea, reveal, features, demo, price, one more thing, closing | opening, reveal, features, one more thing |
| `infomercial` (D79) | A gadget made of the topic, sold on late-night TV | problem, product, demo, testimonials, fine print, price, but wait, call now | problem, product, demo, but wait |
| `documentary` (D79) | The topic as a wild species, narrated in a hush | opening, habitat, behaviour, sighting, ritual, threat, closing | opening, behaviour, sighting, closing |
| `court` (D79) | The topic on trial for a petty crime | charges, evidence (D78's Exhibit A), witness, alibi, objection, closing argument, verdict | charges, evidence, alibi, verdict |
| `museum` (D79) | A tour of a made-up museum and its old master | welcome, masterpiece, artist, eras, artefact, gift shop | welcome, masterpiece, artefact, gift shop |
| `wedding` (D79) | A toast to a best friend who marries the topic | intro, how they met, story, couple, advice, toast | intro, how they met, story, toast |
| `book_report` (D79) | A pupil's report on a made-up book | book, author (from 11), characters, plot, favourite part, moral, rating | book, characters, plot, rating |

A talk can leave its format to its seed: `schema="random"` (`--schema random`, the MCP server's `format="random"`,
D61). The seed picks the persona first, then the format from a random stream of its own (`format`, in
`pick_format`), so the persona, the theme and the slides draw what they would for that format. The odds are
`FORMAT_WEIGHTS` (the TED-like talk 55, the all-hands and the keynote 1.5, the others 1) times the persona's
`Persona.formats` (section 5.2): ×32 for a specialist's format (×21 for the all-hands and the keynote), and none under
0.7, so every format keeps about 1% of every persona's talks. Most talks stay TED-like (D63):

| Persona | TED-like | Their own format | Each other format |
| --- | --- | --- | --- |
| the nine specialists (founder, professor, consultant, motivational speaker, detective, infomercial host, narrator, museum guide, best man) | 55% to 57% | **32% to 33%** | 1% to 3% |
| the other twelve | 76% to 83% | | 1% to 9% (a kindergarten teacher's book reports) |
| over all 21 | **69%** | | pitch 2.8%, academic 2.9%, all-hands 3.4%, keynote 4.0%, infomercial 3.2%, documentary 3.2%, court 3.0%, museum 3.4%, wedding 3.0%, book report 1.8% |
| without a persona | 83% | | 1.5% (all-hands and keynote 2.3%) |

`ted`, `interview` and `test` don't take part: `ted` is a license choice, which any format gets with
`license_policy="open"`, as the arcs need no image that's fair use. A named format weights its personas by its
`personas` instead (D56): a caller who names the format wants its favourite presenters, and one who leaves it wants the
presenter's favourite format. The deck's `schema_name` names the format a talk got.

Slides of figures get pictures (D63). The `big_number` and `kpi` kinds have an optional `background` slot
(`Kind.optional_images`: a slide whose picture isn't found goes without), which three big numbers in four and half the
KPI dashboards ask for, planned or classic (`kinds.pictured`, `slide_texts.BIG_NUMBER_PICTURES`, `KPI_PICTURES`). The
picture goes behind everything under a shade (`v5/big-number` and the KPI layouts), behind a band with the number
(`v5/big-number-band`), or on the slide's right side (`v5/big-number-side`). Its look, `backdrop`, mixes stock photos
with Reddit's weird pictures, NASA's, old photographs and paintings. A statement's backdrop is a calm photo two times
in three, else a backdrop (`content_generators.statement_backdrop_generator`). A pitch's product, a keynote's reveal and
an infomercial's gadget have the `product-shot` look: stock photos of gadgets, or, in a talk that generates pictures, an
advertising shot.

Talks explain their why early, on a `problem` slide (D69): a short heading on a sticker, the problem in three to eight
words (60 characters at most, D73), and a line under it that appears on a click. A picture goes behind the problem
(`background`, half the time: `PROBLEM_BEHIND`) or beside it, showing it as it happens (`photo`), if one is found;
the layouts are `v5/problem`, `v5/problem-band` and `v5/problem-split`. The talk's dice pick an angle
(`kinds.PROBLEM_ANGLES`): weird, everyday, the topic running into another part of life, typical, or real: a wikiHow
how-to about the topic (`facts.howtos`, English talks only, credited to wikiHow). A talk has one at most (tag
`problem_slide`): three pitches in four open their problem part with it, four academic talks in five their
`motivation`, most infomercials their problem, and a quarter to a third of TED-like talks have it as their third slide
(`slide_schemas.PROBLEM_WEIGHT`).

## 8. Slide types and variety

A slide kind (`talkgenerator.plan.kinds.Kind`) names its text fields (`TextField`, each with a description and a length
for the language model), its image slots, and how they become a slide. A `Recipe` ties a kind to a slide generator in
`talkgenerator/schema/slide_schemas.py`, with its brief, hints, the fields and slots it leaves out, and `Variant`s that
the talk's dice pick by weight. Classic talks fill the same slides from templates, content packs and related words. The
kinds added in v5 are made of the deck's own texts, shapes and pictures (D37), which every renderer draws in every
theme.

| Group | Kinds |
| --- | --- |
| From v4 | title, about me, history (a made-up figure's quote, two old photos), full-screen gif, meme or photo, image with title, quote or bold statement over a photo, InspiroBot, anecdote, two or three captioned pictures, charts (yes or no, categories, correlation), a real chart from Reddit, conclusions |
| Structure | agenda, the problem (D69), section divider |
| Figures | trend, ranking, big number, KPI tiles |
| Audience and mock-ups | quiz, social media post, news headline |
| Diagrams | Venn diagram, 2×2 matrix, timeline, pyramid, funnel, cycle, org chart, iceberg, flowchart |
| Memes | a meme template with live captions (D40) |
| From karaoke decks (D49, D57) | fun fact, acronym, dare, tier list, wall of text, alignment chart, red flags, traffic flags, reviews, fake error message |
| Pictures to explain (D78) | Exhibit A, pick one, picture equation, what do you see?, before and after |
| Formats' own (section 7) | process (D56), references (D65), "Questions?" (only for plans written elsewhere: every talk ends with its closer, D76) |

**Caps and weights.** A schema caps each tag per talk (`default_max_allowed_tags`): one slide of most kinds, two memes
with live captions, two exhibits, and shares for diagrams (two in ten slides), charts (three), and quotes, statements
and captioned pictures (two each). A share allows at least one, and caps hold from a talk's first slide (D50,
`presentation_schema.most_slides`). A generator's weight depends on the slide's place: the title comes first, the
about-me slide or the agenda second, the problem or a history slide often third, the conclusions last. The kinds added
in v5 weigh about 1 in a talk's middle, from its third slide to the one before the conclusions. Memes weigh 7, so that
half of the talks have one (D48, D78); dares, walls of text and error messages weigh less, as karaoke decks ration them.
A section divider comes only in talks of ten slides or more. A persona multiplies the weights of the tags it favours.
A slide may reuse few of the texts and pictures earlier slides used (`allowed_repeated_elements`), and never the
layout of the slide before it when another fits.

**Clicks** (D53). A slide that lists things shows its title and its list's frame from the start, and its things a
click each, the punchline last: KPI figures, a quiz's options and then its answer, an agenda's items, a diagram's boxes
(a pyramid's levels from the base up, an org chart's people before their boss), a tier list's tiers from F up to S, red
flags, reviews, a meme's captions, and a ranking's bars from the top down (`ChartSpec.clicks()`). Slides set their
clicks (`DrawnSlide.clicks()`), and `talkgenerator.render.reveal` says what appears when, for PowerPoint, the
previewer's steps (`steps_sheet`) and talk-generator-web. A slide with clicks shows a small ring for each, which fills
on its click (`engine.build_dots`, D80).

**Memes** (D40, D48). A `meme` slide is an Imgflip template (section 10.4) with its captions as live texts on the
picture. `talkgenerator/data/memes.json` measures every caption's box on 46 family-friendly templates, with its style
(white Impact with a black outline, or black text on a pale area) and what it says; a box can repeat another's
(`same_as`). The dice pick the template as one of the recipe's variants, which tells the model what each caption is for
and how long it may be, and fixes the slot's query (`Recipe.queries`); a classic talk takes the TED pack's sentences
for it. The `v5/meme` layout leaves the picture untreated and grows a box that its caption doesn't fit. Memes need fair
use, so `ted` has none. A plan written elsewhere names its template in `template_query`, and
`talkgenerator formats --memes` lists them.

**Karaoke slides** (D49, D57) come from what real karaoke and battle decks have: a fun fact ("Did you know?", with a
made-up source); an acronym for a made-up method; a dare, which is a challenge the presenter keeps up from then on,
something the whole audience does, or a dad joke to tell (D65); a flowchart whose Yes and No lead to the same end; a
tier list, one thing a tier; a wall of text, dense jargon in fine print with one absurd point that a marker highlights
on its click; an alignment chart, chaotic evil last; red flags, or a green, an orange and a red flag (`traffic_flags`);
reviews with drawn stars and "4/5" beside them, so the rating reads in every renderer; and a fake error message whose
last button is the punchline.

**Charts and diagrams** (D64). A matrix has everyday opposites at its axes' ends, and a name in every quadrant, familiar
things as dots where they belong (`MatrixDiagram.dots`), or only the punchline's dot (`kinds.MATRIX_VARIANTS`). A
scatter plot is a cloud in one of eleven shapes (`chart.CORRELATION_SHAPES`), now and then with a fitted line
(`ChartSeries.trendline`, which talk-generator-web fits by the same least squares as PowerPoint) or as two or three
named clusters, which the engine colours apart (`ChartSeries.color`). A diagram has a weird but related picture in one
or two boxes 35% of the time (`BoxPictures`, slots named `<box>_picture`), and a process has one in every step 60% of
the time; a box goes without when its picture isn't found or doesn't fit. A trend's named moment has a picture by its
point half the time (`point_picture`). `charts.trend_plot` puts the plot where talk-generator-web draws it, and a
PowerPoint chart with such a picture has its plot pinned there: change them together.

**Pictures first and pattern breaks** (D73, D85). Three in four charts and diagrams try a picture in their place, under
their title (`Kind.picture_first`, `PICTURE_FIRST_ODDS`): a real chart from the internet or a weird picture, found with the
model's `picture_query` or a classic slide's seed (`PictureFirstSlideGenerator`). Without one, the slide is its
`text_version`, which also stands in until the picture comes when slides have a time limit (D67). A chart's title says
what it shows, never "X vs Y": what it compares goes on the axes (`kinds.axes_from_title`). And a list's or diagram's
punchline breaks its pattern now and then (`kinds.PatternBreak`): a few words where the others are sentences, an emoji
alone or a picture in its place, a word for a KPI's last figure, an agenda's last item off the talk. The third of three
captioned pictures breaks it 60% of the time, and classic slides break theirs too (`slide_texts.broken`).
`DISABLE_PICTURE_FIRST` and `DISABLE_PATTERN_BREAKS` switch these off.

**Pictures to explain** (D78) give the presenter one to three surprising pictures and hardly any words, as improv
suggestions and story cubes do: Exhibit A, an odd picture with an evidence tag (a later exhibit is Exhibit B of the same
case); pick one, two pictures with an "OR" between them; a picture equation, two things that add up to a third, each a
picture or else its emoji; what do you see?, a face in a thing (pareidolia, from Reddit, only with fair use) or an
inkblot that the layout draws from the slide's dice; and before and after, two unrelated pictures, the after on a click.

**Playable at a glance** (D80, D81, D85):

- The model is asked for a slide's title in 45 characters at most (`kinds.TITLE`), a talk's in 50 and the presenter's
  job in 40. The system prompt (`prompt.SYSTEM_PROMPT`) asks for titles of two to five words, ten words a slide or
  fewer, pictures that carry the slide, and lists that set up a pattern and break it last. It asks for no tags tacked on
  to a line, and in an English talk `realize.untagged` takes off those a model adds anyway, such as "twice",
  ", allegedly" or "on a Tuesday" (D85).
- Lists of pictures (D85): in a talk a language model writes, a quiz's options, a tier list's tiers, red and traffic
  flags, an alignment chart's cells and reviews are all pictures in their words' place about half the time
  (`kinds.PicturedItems`, the kind's `pictured`; an alignment chart's nine 40% of the time, reviews 45%). The model
  writes every thing's words and a query for its picture (`<field>_picture_query`); a thing whose picture isn't found
  keeps its words, and such a list breaks no pattern besides. A quiz of pictures has a layout of its own
  (`v5/quiz-pictures`), and flags of pictures go on cards (`engine._in_words`). `DISABLE_PICTURED_LISTS` keeps lists
  in words.
- The kinds of slide that are mostly words (statements, fun facts, acronyms, walls of text, error messages, agendas:
  `kinds.WORDY_KINDS`) count for half their weight when a talk's dice pick its slides, in every format
  (`kinds.wordiness`). Captions are asked for in 24 characters (`kinds.CAPTION`), a conclusion's lessons in four words,
  a post in one short sentence of 60 characters and a big number's label and source in 32 each; the content packs'
  classic texts keep the lengths they were written for. Of 10-slide TED-like talks, about seven content slides in ten
  are pictures (full-screen or captioned ones, memes, gifs, pictures to explain, charts and diagrams that are a
  picture, lists of pictures).
- No hint gives an example with a gap to fill, which a model copies as it is, and a text that ends in such a gap
  ("The time I ...") is a leftover, as template code is (`checks.deck.leftovers_in`).
- A text is kept whole up to what its slides hold (`TextField.room`, `kinds._ROOM`). A longer one is cut where a
  sentence, a clause or a comma ends, if that keeps a third of it, else between words with an ellipsis; a presenter's
  job only where a phrase ends, or not at all (`TextField.phrases`, D81).
- A photo of the talk's world (`Format.scene`, else its persona's) sits beside its title
  (`talkgenerator.title_pictures`), but never one grown-up alone, who would pass for the presenter
  (`ImageSlot.unwanted`, D81).
- A quiz's question starts with a label in the talk's language (`Language.quizzes`). A made-up person recurs in one
  talk in five, on two slides at most (`prompt.RECURRING_CHARACTER_ODDS`).
- A picture whose description speaks of nudity, sex or gore stays out (`safety.unsafe_description`). A real quote has
  100 characters at most (`content_generators.short_quote_generator`, D85) and nothing of self-harm
  (`content_generator_structures.fit_quote`). In an English talk, a
  model's text about real-world politics that the talk isn't about is left out (`checks.deck.real_politics`). A talk in
  another language whose model wrote no slide is asked once more, so that it doesn't come out classic, in English.
- A slot can have its picture generated first (`ImageSlot.generate_first`), with some of the talk's budget kept for it
  (`ImageGeneration.reserve`, section 10.5).

**Callbacks.** The conclusions call back to earlier slides, six words each, with a new twist. An agenda announces up to
three later slides, which pick its items up (`prompt.agenda_cues`). A "Questions?" slide ends on a funny picture, a last
tip, or an earlier slide's picture shown again (D65), picked by the words its query shares with the callback, never a
meme's template (`QuestionsSlide.call_back`).

**References and emoji** (D65). An academic talk's references are numbered as cited, a click each, and most of the time
a picture of one follows: a book's cover or a figure from a paper. A third of the tier lists and alignment charts and a
quarter of the agendas put an emoji in front of every thing (`Variant.emoji`; `data/emoji.json` for classic ones, with
none for faiths, drink, weapons or death). Emoji are measured 1.4 ems wide and drawn in Segoe UI Emoji in a .pptx.

**The prompt lab** (`scripts/prompt_lab`) tunes the prompts on real talks. `run.py` makes talks with talkgenerator's
own code and a stand-in picture for every slot, on fixed setups of topics, formats, personas and languages (`lab.py`).
`judge.py` has judge models compare two variants' talks blind, in alternating order, on five questions: reads at a
glance, gives the presenter something to run with, funny, free of machine tics, and overall. `measure.py` counts words
on a slide, title lengths, English words in other languages, classic fallbacks and cut texts.

## 9. Themes, layouts and design quality

The layout engine (`talkgenerator.design.engine`) places a deck's elements in a theme's style. Every theme but
`classic` draws on a blank 1920×1080 canvas; `classic` keeps the 2019 template and its placeholders.
[Themes](images-and-themes.md#themes) shows what each family looks like.

- Layouts are geometry only: boxes for an element's roles (title, image, captions, chart, credits...) within safe
  margins. The engine picks one per slide with the deck's seed and gives every text the largest size at which it fits.
- Themes are design tokens (`talkgenerator.models.theme.Theme`): a palette (background, surface, text, muted, two
  accents), a font pair with its casing, a background (solid or a gradient, with a pattern of lines, a grid or dots),
  decoration, image treatment and motion.
- A family (`themes.FAMILIES`) says what its members can be: hues and a harmony rule, or palettes of its own, font
  pairs, decoration, casing. The seed picks a member, whose colours are repaired until every text reads (WCAG: 4.5:1 for
  body text, 3:1 for titles). There are 24 families, three of them for laughs (`1997 WordArt`, `Comic Sans everywhere`,
  `clip-art corporate`), which `random` includes unless `extreme_themes` is off. `chaos` gives every slide its own
  theme, and `style_chaos` (0 to 1) a share of them.
- A talk can say which families a random theme can be of (`theme_families`, D62). The seed picks among all of them
  first, by each family's weight times its persona's and format's multipliers, and only when that one isn't allowed,
  again among the allowed ones: so a talk whose family is allowed keeps its theme. A family named as the theme goes
  first.
- Every family has a motif (`talkgenerator.design.motifs`, D43): a fixture on every slide and its big pieces for the
  title, section and closing slides, its accent rationed, never behind a text unless the text reads on it. A motif adds
  shapes behind or over the layout's, and texts of its own (role `decoration`: numbers, symbols and code, which suit
  any language); it may move a text or fit a picture to a frame. It draws with the deck's elements (polygons are
  PowerPoint freeforms and CSS clip paths) and background patterns, so every renderer draws it
  (`talkgenerator.design.geometry`).
- Some families commit to palettes of their own, and some have their own title and section slides (D44). A family can
  have several sets of decoration (`themes.Variant`, D77), of which a member has one: `kids` has crayon drawings, a
  sticker book, a school notebook and paper cut-outs.
- Fonts (`talkgenerator.design.fonts`): installed fonts are measured with bundled twins that share their metrics
  (Liberation, Carlito, Gelasio...) or a table of every character's width (`data/fonts/widths.json`, by
  `scripts/font_widths.py`). Most members have open fonts from Google Fonts instead (D42): bundled, and carried inside
  every .pptx that uses them as uncompressed Embedded OpenType (`talkgenerator.render.embedding`). Where they aren't
  shown (PowerPoint for the web), an installed stand-in is: texts fit both, and runs carry the font's PANOSE. The
  extremes keep Comic Sans MS, Impact and Arial Black. Sizes are the same on every computer; PowerPoint's
  shrink-on-overflow stays on as a safety net.
- Image treatments (`talkgenerator.design.treatments`) give pictures from mixed sources one look: a filter, a rounded
  or polaroid frame, grain, a vignette, or a gentle tint. Strong filters (grayscale, sepia, duotone) belong to the
  families made for them, on backdrops only (`treatment(behind=)`, D45, D80); a slide's own pictures keep their
  colours. PowerPoint applies them as picture effects, previews with Pillow, the browser with CSS filters.
- A shape or text that belongs to an element, such as a picture's frame or tape, names it (`part_of`, D52) and appears
  with it, click by click.
- Every family numbers its slides ("7/12", D65), small and in its own style, where it reads and never over a
  full-screen photo. A streamed talk knows its total from the start (`DeckLayout(total=)`); the closer isn't counted.
  The classic template numbers its slides too.
- A family says how much its slides move as they're presented, with PowerPoint's entrance effects (D83,
  `talkgenerator.design.entrances`).
- The design checks (`talkgenerator.checks.design`, section 14) want no overflow, no text under 12 points, safe
  margins, nothing covering a text, and contrast on what's behind its letters, as the engine breaks its lines: the
  background, both ends of a gradient, and the shapes, patterns and pictures drawn before it (D46). An outlined text
  reads by its fill or its outline. Credits are quiet (D51): 7 points, aligned right, in the colour nearest the
  background that reads at a contrast of 2.5, with no band; over a picture, light with a dark halo. They have floors of
  their own (6 points, 2.5), and a wall of text's fine print has one too (9 points, `engine.FINE_PRINT`).

## 10. Images: sources, aesthetics and generation

`talkgenerator.images` finds every picture a slide asks for. [Images and themes](images-and-themes.md) explains it
for people who make talks, and [Keys and settings](configuration.md#image-sources) lists the keys.

### 10.1 Image slots

Every image a slide asks for is a slot (`talkgenerator.images.slots.ImageSlot`), not a call to a source: its `intent`,
`queries`, `orientation`, `min_pixels`, `text_area`, `aesthetic` (its look, 10.3), `license_classes` and `sources`,
plus `backups` (looks that take over in order), `generate` and `generate_first` (10.5, D80) and `unwanted`
(descriptions it turns down, D81). Recipes ask for their images with slots, and v4's image generators in
`talkgenerator.schema.content_generators` are slots too.

The image finder (`talkgenerator.images.finder`):

1. orders the look's sources that the license policy allows by weight, without putting one back (as v4's
   `CombinedGenerator` did), skipping those without a key or switched off;
2. searches them a few at a time (the look's `breadth`), in parallel, each with its own random stream, so the same
   seed finds the same images whichever search answers first;
3. filters by license class, size, orientation and description, and drops images found twice or already on the slide;
4. picks at random among the first source's images, as v4 did, or, for a look with preferences or in a themed talk,
   among a few candidates whose thumbnails have the look, by weight and by how well their colours go with the theme;
5. checks the winner (`image_util.check_image`), and the next one when it won't do;
6. hands over to the look's `fallback`, then to the slot's `backups`. A persona's favourite looks go first.

The picked image keeps its look and its thumbnail's analysis (`ImageData.look`, `ImageData.analysis`), whose
perceptual hash keeps nearly the same picture off other slides.

### 10.2 License classes

| Class | What |
| --- | --- |
| `public-domain` | public domain and CC0 |
| `open` | CC BY and CC BY-SA |
| `stock` | the Unsplash, Pexels and Pixabay licenses |
| `generated` | AI images, under the provider's terms |
| `fair-use` | Reddit, GIPHY, Imgflip's meme templates, InspiroBot, ShitpostBot |

Every source module declares its classes (`LICENSES`), and its images carry `license_class`, `license` and
`license_url`. Openverse and the Wellcome Collection are only asked for licenses that allow commercial use and
adaptations (no NC or ND), as decks get shown at paid shows and themes recolour their pictures.

A talk's license policy (`talkgenerator.images.licenses`; `license_policy=`, `--license_policy`) is `all` (the
default), `open` (everything but `fair-use`, which the `ted` schema keeps to, as in v4), or classes such as
`public-domain,open`. Slide generators whose slots the policy allows no source for aren't picked, and a plan's recipe
of that kind gets its kind's default. The deck keeps the policy (`Deck.license_policy`) and every image's license,
and credits name the license of open and public domain images.

### 10.3 Aesthetic profiles and filters

A look (`talkgenerator.images.profiles.Profile`) names an aesthetic: its sources with weights (`SourceUse`), query
modifiers, an orientation, a text area, what it `prefers` in a thumbnail, a `treatment` and a `fallback`. v4's
weighted mixes of sources became the weights. Looks include `photo` (the default), `neutral`, `weird-stock`,
`calm-backdrop`, `vintage`, `museum` and `meme-chaos`; a format can map them to its own
(`PresentationSchema(looks=...)`), and `talkgenerator formats --looks` lists them all. Flavour packs
(`profiles.FLAVOURS`) are looks of weird content from curated subreddits, each also a source (`reddit:<pack>`), such
as `cursed`, `wholesome` and `bad-charts`. Reddit's NSFW mark and the finder's filters keep them safe for work.

The filters, cheapest first:

1. The sources' own filters (`SourceUse.params`): colours, orientation, image type, collections, and the museums'
   `type`, `after` and `before` (10.4).
2. Query modifiers: a classic search gets one of the look's words ("business", "office"); a planned query goes as
   written.
3. A look at the sources' thumbnails, with Pillow (`talkgenerator.images.analysis`): brightness, colourfulness,
   monochrome (gray, or one hue as in sepia), detail where the text goes, main colours, and a difference hash.
   `calm-backdrop` prefers at most 0.08 of detail there (a sky has about 0.02), `vintage` monochrome.
4. The vision pick (optional, D58), below.
5. A treatment (`talkgenerator.design.treatments`): the theme's own filter, or else the look's, such as sepia for a
   vintage picture in colour (`treatments.for_look`).

`talkgenerator check` reports an image the policy doesn't allow as an error, and near-duplicates, a credit without its
open license, an untreated vintage picture in colour and a busy calm backdrop as warnings.

The vision pick (`talkgenerator.images.vision`; `vision_pick=`, `--vision_pick`) is off by default and takes only
planned slides. The finder keeps a few runners-up per picture (`ImageData.runners_up`) without drawing from the
talk's dice, and one contact sheet a talk shows them side by side. The model says what each candidate shows before it
picks one or none, which is what makes models that don't think pick well. A pick replaces the finder's picture once
it passes the same checks; a refusal, an error or a late answer keeps the finder's.
[The vision pick](images-and-themes.md#the-vision-pick) has the details.

### 10.4 Image sources

| Source | Name | License class | Key |
| --- | --- | --- | --- |
| Unsplash | `unsplash`, `unsplash-random` | `stock` | `UNSPLASH_ACCESS_KEY` |
| Pexels | `pexels` | `stock` | `PEXELS_KEY` |
| Pixabay | `pixabay` | `stock` | `PIXABAY_KEY` |
| Openverse | `openverse` | `public-domain` or `open`, per image | none (optional: `OPENVERSE_CLIENT_ID`, `OPENVERSE_CLIENT_SECRET`) |
| Wikimedia Commons | `wikimedia` | `public-domain` or `open`, per image | none |
| Art Institute of Chicago | `art-institute` | `public-domain` | none |
| The Met | `met` | `public-domain` | none |
| Cleveland Museum of Art | `cleveland` | `public-domain` | none |
| Wellcome Collection | `wellcome` | `public-domain` or `open`, per image | none |
| Smithsonian Open Access | `smithsonian` | `public-domain` | `DATA_GOV_API_KEY` |
| NASA Image and Video Library | `nasa` | `public-domain` | none |
| Flagpedia | `flags` | `public-domain` | none |
| Imgflip's meme templates | `imgflip` | `fair-use` | none |
| GIPHY | `giphy` | `fair-use` | `GIPHY_API_KEY` |
| InspiroBot | `inspirobot` | `fair-use` | none |
| ShitpostBot 5000 | `shitpostbot` | `fair-use` | none |
| Reddit | `reddit:<pack>` | `fair-use` | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` |

The modules are in `talkgenerator/sources/`, and `talkgenerator.images.catalog` is how the finder sees them. Each
declares `LICENSES` and `DISPLAY` (how a browser may show its images, section 13.1), and keeps its own cache and
cooldown. The museums share one filter vocabulary (`type`, `after`, `before`), which each puts in its API's words.

### 10.5 Generated images

`talkgenerator.images.generators` gives every provider one interface, a sibling of the language models'.
`ImageGenerator.generate(ImageRequest)` takes a prompt, an aspect ratio, a style, what to avoid, a seed and a quality,
and returns a `GeneratedImage` (bytes, model, cost, moderation's flags), or raises `GeneratorUnavailable`,
`GenerationRateLimited` or `GenerationRefused`. A spec, `provider[:model]`, picks the generator (`image_generator=`,
`--image_generator`, `TALKGENERATOR_IMAGE_GENERATOR`):

| Spec | Adapter | Key or server |
| --- | --- | --- |
| `openai` | `openai_images` | `OPENAI_API_KEY` |
| `openrouter` | `openrouter` | `OPENROUTER_API_KEY` |
| `gemini` | `gemini` | `GEMINI_API_KEY` |
| `flux` | `flux` (Black Forest Labs) | `BFL_API_KEY` |
| `comfyui` | `local` | `COMFYUI_URL`, `COMFYUI_WORKFLOW` |
| `automatic1111` | `local` | `AUTOMATIC1111_URL` |

The adapters speak plain HTTP, without SDKs. Default models and list prices are config, as image models come and go:
`talkgenerator/data/image_generators.json`, overridden by an `image_generators.json` in the config folder.

`talkgenerator.images.generation` decides when. A talk generates only when it's given a generator, never because a
key is set, so that a server that holds keys never generates on its own (D7, D38). It generates only on planned
slides, whose texts say what a picture is to show:

- Slots that stock photos can't show well prefer a generated picture (`ImageSlot.generate`), such as the presenter's
  weird hobby or a made-up history's old photos. The language model writes their prompts (`<image>_prompt`). The
  slide comes with a stock photo, which the generated picture replaces once it's in (`slide.updated`).
- A planned slide whose images can't be found gets them generated on its last try.
- `ImageBudget` caps a talk at 3 pictures by default (`--generated_images`), granted in the order of the slides, so
  the same seed generates for the same ones; `TALKGENERATOR_IMAGE_COST_LIMIT` adds a limit by list price.
- A picture is credited "AI-generated with <model>", in the `generated` class, and cached by model, prompt, shape and
  seed, so a deck rendered again generates nothing. The deck names the cached file, with display `copy` (D39).
- `talkgenerator.images.safety` never sends a prompt that names a real person it knows of, the presenter, a brand or
  a trademarked character, or asks for gore or sexual content; every prompt asks for none of that, and the provider's
  moderation comes next. A refused or failed picture keeps the stock photo.

An app can pass a generator made with a visitor's key (`OpenAIImageGenerator(model, api_key=...)`) and an
`ImageBudget`, and show `generation.estimate` first.

## 11. Text sources and content packs

- Datamuse, WordNet, Goodreads, Wikiquote, WikiHow and InspiroBot stay from v4. ConceptNet, whose public API has been
  down since late 2025, is optional (`CONCEPTNET_API_URL`): Datamuse and WordNet stand in. At the Advanced level the
  language model's plan picks each slide's word, among those the dice offer or its own; in classic talks and at the
  Basic level they come from Datamuse and WordNet, and are things only (D68).
- Wikipedia (`talkgenerator.sources.wikipedia`), without a key: an article's lead, short description and whether it's
  in "Category:Living people", its whole text, and a year's events ("1886"). Wikimedia asks for a User-Agent that
  says who's asking and at most 200 requests a minute. Its texts are CC BY-SA 4.0, credited on the slide.
- Open Trivia DB (`talkgenerator.sources.opentdb`): trivia questions under CC BY-SA 4.0, with no key and no search,
  one request every five seconds; a category's come 50 at a time, cached for a week.
- Flavour texts (`talkgenerator.sources.flavour`), from three small keyless APIs: a random useless fact from a pool of
  500 a week (D84), a dad joke from icanhazdadjoke by a whole word of the topic, and an advice slip by its number. A
  slide that shows one credits its site.

Real facts (`talkgenerator.facts`, D60): in a talk a language model writes, up to three slides of history, fun facts,
quizzes and big numbers get a real fact each, from the topic's English Wikipedia lead, with what to do with it: a fun
fact keeps it true and twists it, a quiz asks about it, a big number starts from its figure. Two old photos and a
timeline get a coincidence first (D73): a dated moment of the topic's history and an event of the same year, as if
one caused the other ("In 1938, nylon came to socks", "1938: László Bíró patents the ballpoint pen"). No fact names a
living person or speaks of death, war, disasters, crime, politics, race or faiths. Facts not in eight seconds after
the talk started are left out (`facts.DEADLINE`); the deck records the rest (`Deck.facts`). English talks also get
flavour texts: a fun fact may build on a useless fact, a dare on a dad joke, a closing line on advice. Classic English
talks get real fun facts and Open Trivia DB quizzes half the time. `DISABLE_FACTS=1` turns it all off.

Content packs (`talkgenerator.sources.packs`, D54) hold a format's classic texts as versioned data in
`talkgenerator/data/packs/<format>/`: grammars whose rules are lists of templates, and a manifest, `pack.json`, with
the version, what each version changed, and the slots (the rules the code fills in, their variables, and the text
field whose length they keep to). The `ted` pack has a grammar per kind of slide; the other formats' packs have one
per part of their arc (D56, D59), with variables for their made-up names (`startup`, `method`, `company`, `product`).
`tests/test_content_pack.py` lints every pack: every template fills in with its slot's variables, fits its field with
words of 22 to 24 letters, has no word of the blocklists and speaks of its topic as English does. Better packs improve
the free classic mode and the language model's per-slide fallback at no cost at runtime.

## 12. Determinism, seeds, tests and the paper baseline

- The classic engine is v4's algorithm on the new data model: the default without a language model, the per-slide
  fallback, and the paper baseline: `--llm none --theme classic --name_styles classic --persona none` is the 2019
  method with the 2019 look.
- A talk has one random generator (`random_util.Rng(seed)`), and every part of it a stream derived by hashing its path
  (`rng.child("slide", 3)`), so a seed gives the same talk in parallel and one by one. Nothing else may use the
  `random` module (ruff's `TID251` rule); tracery draws from `random_util` too.
- `talkgenerator.llm.replay` replays recorded answers from a cassette, so a talk a language model wrote can be made
  again, offline. `talkgenerator check` makes every talk twice and compares them.
- Live APIs and language models stay non-deterministic, and so, by design, does a streamed talk with a time limit per
  slide (D67) once a slide runs out of time; spare slides (D66) never change a talk. A saved deck JSON is the
  reproducible artifact: rendering it again ([Python](python.md)) gives the same slides.
- Offline tests use fake sources and models, recorded answers and cassettes. Network tests (`pytest -m network`) run
  weekly against the live APIs (`.github/workflows/canary.yml`), skipping those whose keys aren't set.

## 13. talkgenerator.com

talkgenerator.com streams its talks into the browser with `generator.stream_talk`, as Server-Sent Events, and renders
the PowerPoint from the finished deck on download ([Python](python.md#making-a-talk-stream_talk) documents the events).

### 13.1 Streaming slides into the browser

- `stream_talk()` yields `talk.started`, a `slide.ready` per slide in order, `slide.updated` when a picture comes in
  later, and `talk.finished` with the deck (`talkgenerator.models.events`), each slide laid out in the theme whose
  tokens `talk.started` brings. The events come from the generator's callbacks
  (`talkgenerator.schema.presentation_schema.Progress`), and leaving the loop stops the talk.
- Images are probed, not downloaded (`image_util.probing`), and the browser loads each as its `display` says
  (`direct`, `proxy`, `copy` or `local`; Pixabay's are copies kept with the deck, D30). A slide handed over marks its
  pictures used (`ImageData.mark_used`), as Unsplash asks.
- Spare slides (D66): `spares=N` sends N `slide.spare` events early, for a presenter who catches up with the making:
  kinds drawn without pictures (`SPARE_WEIGHTS`), made in a hundredth of a second from random streams of their own,
  so the talk's slides come out the same.
- A time limit per slide (D67): with `slide_seconds=S`, a slide not made within S seconds of when it could come is
  handed over with what's quick, so one slow slide doesn't hold back the rest: a planned slide as written, with spare
  pictures (`realize(spare_pictures=)`); a chart or diagram that tries a picture first, as text (D73); any other slide,
  as a stand-in of the spare kinds. The real slide still comes once it's made (`slide.updated` with `late`, laid out
  by `DeckLayout.again`), unless it repeats a slide or breaks the talk's caps; `talk.finished` waits for it
  `LATE_SECONDS` (20 s) at most.
- Early versions (D70): a slide's kind and word are known before the model writes, so `early=N` makes the last N
  slides' stand-ins ahead, sent as `slide.early` events at their places (`DeckLayout.early`). A slide that runs out of
  time or can't be made uses its early version, if the deck allows it.
- Progress (D72): `progress=True` sends `talk.progress` from the start and on every change: the talk's stage, every
  slide's, and how many parts of the model's plan are in (`ObjectReader.reading`, `Planning`), as a free model can be
  slow to start.
- The closer (D76): every talk ends with one more slide, in its format's kind and its language
  (`talkgenerator.closers`): a last `slide.ready` with `closer` set, which slide numbers don't count. The end is clear,
  and none of the slides a talk asked for goes to "Questions?".
- `generator.regenerate_slide(deck, index)` replaces a slide of a finished deck, for a live show's operator: a classic
  slide of a kind the format has there, made in seconds without a language model, numbered as the old one. The title
  slide and the closer can't be replaced.

### 13.2 Free by default

- OpenRouter's free models write the site's talks, at the Basic level (D68), unless a visitor brings their own API key
  or OpenRouter account. Their own key, or a paid model of their account, writes Advanced talks.
- A key a visitor types stays in their browser and goes along with each talk's request. The server never stores or
  logs it.
- When the model fails, the talk comes from the classic generator, in English even when another language was
  asked. See [Language models](language-models.md).

## 14. Automated quality checks

`talkgenerator check` (`talkgenerator.checks.benchmark`) makes talks on a set of topics, checks every deck, and makes
each talk again one by one with the same seed and the model's recorded answers (`talkgenerator.llm.replay`), which must
give the same deck. Its JSON report can be compared with an earlier run's
([options](command-line.md#checking-talks-talkgenerator-check)). The offline tests use the same checks.

`talkgenerator.checks.deck.check_deck` checks a deck, and `talkgenerator check` adds `determinism`. An error is a broken
talk, and comes from the first five checks below; the others give warnings, worth a look.

| Check | Finds |
| --- | --- |
| `completeness` | missing slides (the closer not counted), a role the slide type needs, an empty text, chart or diagram label, an image without an address |
| `leftovers` | template variables (`{seed}`), Tracery symbols (`#tag#`), Python objects, a key of the model's answer (`slide_03`) |
| `licenses` | an image whose license class the talk's policy doesn't allow |
| `language` | a talk in another language that reads as English, by its stopwords |
| `determinism` | a talk that comes out differently the second time |
| `title` | the request's words in the title ("Come Up With One: ...") |
| `arc` | a format's arc (section 7) with a part missing or out of order |
| `quiz` | a quiz's explanation that names another option than its answer |
| `politics` | real-world politics in an English talk that isn't about it |
| `images` | an uncredited web image; the same or nearly the same image twice, except a closing slide's callback (D65) |
| `looks` | a picture without its look's preference, such as black and white or sepia for `vintage` |

Themed decks also get the design checks (`talkgenerator.checks.design`): contrast (WCAG's 4.5:1, or 3:1 for large
text), overflow and covered text (errors), small text, margins and the same layout twice in a row (warnings).
`deck_metrics` adds numbers to follow, and `talkgenerator.render.preview` draws a themed deck's slides. None of it
tells whether a deck is funny.

## 15. Releases and compatibility

- Releases go to PyPI from `master`, tagged `vX.Y.Z`: `scripts/release.py bump` prepares one, and publishing the GitHub
  release runs the `Release` workflow (`RELEASING.md`). 4.x gets no more fixes.
- talkgenerator 5 keeps 4.x's command line and `.env` settings. `--schema default|ted|interview|test` picks a format,
  with its license policy (`ted`'s is `open`: no fair use).
- `generator.generate_presentation()` and `SlideDeck.to_slide_deck_dictionary()` keep working throughout 5.x, with a
  `DeprecationWarning`. `to_slide_deck_dictionary()` now gives JSON-ready dictionaries, a breaking change. See
  [Migrating from 4.x](migrating-from-4.md).
- Python 3.11 or newer.
- The README and `CITATION.cff` cite the EvoMUSART 2019 paper, whose method lives on as the classic generator.

## 16. Milestones

The code and tests refer to the milestones talkgenerator 5 was built in ("milestone 6's slide types").

| Milestone | What it brought |
| --- | --- |
| 1. Groundwork | deck JSON and its PowerPoint renderer, seeded random streams, the classic engine on the new data model, `talkgenerator check` |
| 2. LLM talks and the Skill | the TalkPlan schema and planner, the language model adapters, `render`, the Claude Skill, languages |
| 3. Themes and layouts | themes, layouts, text fitting, the shapes renderer, previews, the design checks, the MCP server |
| 4. Streaming and the web view | `stream_talk()`, display policies, spares and time limits (D66, D67), talkgenerator.com's browser view |
| 5. Images | image slots, license policies, aesthetic profiles, generated images, new sources (section 10) |
| 6. More slide types | slide types drawn as texts on shapes (D37), memes, karaoke types, personas, the TED pack (D54), real facts (D60), livelier slides (D63, D64, D65) |
| 7. New talk formats | pitch, academic, corporate and keynote (D56, D59) |
| 8. Integration | talkgenerator.com on talkgenerator 5, the docs, the deprecation warnings |
| 5.0.0 | the release |

## 17. Decisions

The code refers to these decisions by number; numbers that no longer apply are left out and aren't reused.

| # | Decision |
| --- | --- |
| D1 | A talk's deck, versioned JSON (`deck_version`), is its single source of truth; the .pptx and the browser view render it. |
| D2 | Plan, realize, render (section 4): the classic generator, a language model or an agent's plan says what each slide is, the realizer finds its pictures and fallbacks, and renderers draw the deck. |
| D3 | Python picks a talk's structure with its seeded dice, and the language model writes the words (section 5.2). |
| D4 | One provider interface (`talkgenerator.llm`) serves OpenRouter, Anthropic, OpenAI, Gemini, a ChatGPT plan, `replay` and `none`; their SDKs are optional extras. |
| D5 | The classic engine stays: it makes talks without a language model and planned slides that can't be made as planned, and it's the 2019 paper's method (section 12). |
| D6 | No global randomness: a talk has one seeded generator (`random_util.Rng`) with a stream per slide and purpose, so a seed gives the same talk in any thread order, and `replay` makes it again offline. |
| D7 | A key alone never makes a talk generate pictures, so a server with keys, such as talkgenerator.com's, generates them only with a visitor's own key. |
| D10 | Themes are design tokens on a layout engine (`talkgenerator.design`); the .pptx renderer draws shapes, and the 2019 template is the `classic` theme. |
| D11 | Slides ask for images through slots (`ImageSlot`), each with an aesthetic profile and the license classes it may have (section 10). |
| D12 | Plans carry search queries and prompts, never image URLs: finding, licensing and crediting images stays with talkgenerator. |
| D14 | The plan, deck and event models are pydantic v2, with exported JSON Schemas. |
| D19 | A language model can write talks in Dutch, French, German, Spanish, Italian and Portuguese too (section 5.9); classic talks stay English. |
| D20 | The MCP server (`talkgenerator mcp`) runs only locally, with your own keys: nothing of it is hosted, so no one else's requests reach them. |
| D21 | The extreme themes, for laughs (such as `Comic Sans everywhere`), are in the random mix unless a talk leaves them out (`extreme_themes`). |
| D22 | A deck holds no image bytes, only each picture's URL and how a browser may show it (`display`); talkgenerator caches search responses, not pictures. |
| D23 | Reddit's memes and weird pictures stay, beside other weird sources such as InspiroBot and ShitpostBot 5000. |
| D27 | Without `TALKGENERATOR_LLM`, a signed-in ChatGPT plan writes talks, else OpenRouter's free models with an OpenRouter key, else talks are classic (`settings.llm_spec`): a key alone never makes a paid model write. |
| D28 | `random` is the default theme, which the talk's seed picks; `TALKGENERATOR_THEME` or `theme=` sets another (`classic` is the 2019 template), and `themes.catalog()` lists them. |
| D30 | A Pixabay picture's `display` is `copy` (an app shows a copy of its own), as Pixabay doesn't allow permanent hotlinking and its image links expire after 24 hours. |
| D32 | What's typed for a talk (`topic_or_title`) can be its topic, a premise or its title (section 5.11); a topic or a title given as such is taken as it is. |
| D33 | A presenter's name can be a famous-name pun (`famous_pun`), never the real name as it is, nor a dictator's or a criminal's (section 5.10). |
| D34 | Without a language model, a talk's presenter gets a name from a small pack by topic, or else tracery's random names. |
| D35 | What's typed stays the title only in quote marks or when it's clearly one (`titles.clearly_a_title`: four words or more, or a question or exclamation); anything shorter is a topic, which the model gives a funnier title. |
| D36 | GIPHY's searches aren't cached, as its API documentation asks; other search responses are (`http_util.CACHE_EXPIRY`). |
| D37 | Slide types are drawn with the deck's texts, shapes and pictures, so every renderer draws them; appearing on a click is an element's property (`appears_on_click`), which a renderer that plays no clicks ignores. |
| D38 | A talk generates pictures only with an image generator it's given (`--image_generator`), only on planned slides (for slots that stock photos can't show well, or images not found), and a few at most (3 by default), in slide order. |
| D39 | A generated picture is credited `AI-generated with <model>`, in the `generated` license class; a prompt that names a real person, a brand or a trademarked character, or asks for gore or sexual content, is never sent. |
| D40 | Memes are captioned live, never drawn into the picture: the dice pick an Imgflip template (fair use) before the model writes its captions, which go in boxes measured once per template (`data/memes.json`). |
| D41 | Swedish (`sv`) is a talk language too, on D19's terms. |
| D42 | Themes use open fonts from Google Fonts two times in three: bundled, so texts are measured everywhere, embedded in the .pptx (uncompressed EOT), and fitted to an installed stand-in for apps that ignore embedded fonts. |
| D43 | Every theme family has a motif (`talkgenerator.design.motifs`), drawn with the deck's own elements on every slide and in big pieces on title and section slides, never behind a text's letters. |
| D44 | `hacker terminal`, `blueprint`, `chalkboard`, `newspaper` and `Swiss poster` are families, none for laughs, and `kids` is a kindergarten's; some families pick among palettes of their own. |
| D45 | Strong image filters (grayscale, sepia, duotone, black and white) are only in the families made for them, and only on backdrops (D80); other pictures keep their colours. |
| D46 | The design checks judge a text by what's behind its letters (shapes over part of them, a background's pattern), not by what's under its box's middle. |
| D47 | A talk's persona (`talkgenerator.personas`), picked by its seed or named, shapes it with a model or without: its slides' weights, titles, presenter's name and job, a random theme's family, and the model's voice. |
| D48 | Memes with live captions weigh seven times the other middle slides (`MEME_WEIGHT`) in talks that allow fair use, two a talk at most. |
| D49 | Slide types come from real PowerPoint karaoke and battle decks, TED parodies and bad-PowerPoint humour (section 8), drawn as D37 has it, one of each a talk. |
| D50 | Tag caps hold from a talk's first slide (`presentation_schema.most_slides`): an absolute cap counts slides (0 for none), a relative one is a share, rounded down but at least one, so short talks keep every kind of slide. |
| D51 | Image credits are quiet, there for a picture's source and license: 7 points, aligned right, without a band, in the colour nearest the background that reads at a contrast of 2.5, with floors of their own in the design checks. |
| D52 | A theme's frame, shadow, tape or window around a picture names it (`part_of`), so every renderer that plays clicks shows and dims it with the picture. |
| D53 | A slide that lists things shows its title from the start and its things a click each, the punchline last; a slide of one thing shows at once. |
| D54 | A format's classic texts are a content pack (`data/packs/<format>/`): a grammar per kind of slide and a versioned manifest (`pack.json`) of the slots the code fills; tests lint every pack. |
| D55 | A seed gets only wikiHow actions about it (`wikihow.about`), as wikiHow pads searches it knows little about, and none with a word a slide shouldn't make light of (`wikihow.unfit`), though crude ones stay. |
| D56 | A format beyond the TED-like talk is a schema with a `Format`: a brief, its titles and presenter's job, persona and theme weights, and an arc of ranked parts with their fewest and most slides, for a talk of any length (section 7). |
| D57 | A wall of text, an alignment chart, red flags, reviews and a fake error message are karaoke types (section 8); a wall of text's fine print has a floor of its own (9 points). |
| D58 | A vision model can pick a talk's pictures (`vision_pick`, off by default; section 10.3) from a contact sheet of each planned slide's picture and up to three runners-up, in one request. |
| D59 | The all-hands (`corporate`) and the product keynote (`keynote`) are formats as D56 has them, with no new slide type: an all-hands goes from its agenda to the ask, a keynote from its opening to one more thing. |
| D60 | Talks get a few real facts (`talkgenerator.facts`), credited: sentences of the topic's English Wikipedia article, and Open Trivia DB questions for classic quizzes, none about a living person, a grim subject or real-world politics; flavour texts (`talkgenerator.sources.flavour`) add useless facts, dad jokes and advice. |
| D61 | A talk can leave its format to its seed (`schema="random"`), which picks it by `FORMAT_WEIGHTS` times the persona's multipliers (`Persona.formats`). With `personas=`, the dice pick again among the allowed only when theirs isn't, so a talk keeps its persona when it can. |
| D62 | A talk can say which families a random theme can be of (`theme_families=`), picked as D61 picks personas. |
| D63 | Most talks are TED-like, and slides of text get pictures: arcs keep slides free (`Arc.free`) for memes, gifs and pictures, big numbers and KPI tiles get one behind or beside them, and a pitch's product is searched as a gadget. |
| D64 | Diagrams and charts are livelier: matrices of dots (`MatrixDiagram.dots`), scatter clouds with a fitted line (`ChartSeries.trendline`) or clusters, and now and then a picture in a diagram's box or by a trend's named moment. |
| D65 | Dares are real challenges for the presenter or the audience, closing slides end on a funny picture, a tip or a callback, academic references show one of the works, lists have emoji now and then, and slides are numbered ("7/12"). |
| D66 | A streamed talk can have spare slides (`stream_talk(spares=N)`, `slide.spare`) of 15 quick kinds (`SPARE_WEIGHTS`), to show while the next slide isn't in, on random streams of their own so the talk stays the same. |
| D67 | A streamed talk can give each slide a time limit (`slide_seconds`): out of time, it settles with what's quick until the real slide replaces it (`slide.updated`, `late`); off by default, as it makes a talk depend on timing. |
| D68 | A talk's level (`llm_level`) is `basic`, one request, or `advanced` (the default on paid models), an outline (`talkgenerator.plan.outline`) and then batches of slides in parallel. Slides start from familiar nouns, no names, at most two steps from the topic. |
| D69 | A problem slide (`problem`) explains a talk's why early, on an angle the dice pick (one of them a real wikiHow how-to): it opens most pitches and academic talks, and some TED-like talks. |
| D70 | A streamed talk can have early versions of its last slides (`stream_talk(early=N)`, `slide.early`), which stand in for a slide that runs out of time or fails, so what was shown stays. |
| D71 | Gemini writes talks (`--llm gemini`, `talkgenerator[gemini]`, `GEMINI_API_KEY`), held to the talk's JSON schema and reading pictures; talkgenerator can't tell a free-tier key, so Gemini counts as a paid model. |
| D72 | A streamed talk can report its progress (`stream_talk(progress=True)`): `talk.progress` events from its start, with its stage, every slide's state and the parts of the plan that came in. |
| D73 | Less text, more surprise: half of the charts and diagrams try a picture first (`Kind.picture_first`), punchlines break their pattern now and then (`PatternBreak`), chart titles are claims, and history slides pair the topic's past with another event of its year. |
| D74 | Talks in other languages read as their speakers write them: slides wander from the topic's English name (`english_name`), the request asks for a native speaker's words (`prompt.native_line`), and each language has its own topics (`data/topics.<code>.txt`). |
| D75 | A talk can say which formats its seed picks from (`formats=`), as D61 has it, so an app can keep a visitor's talks varied; there's no command-line flag, as one talk has no history. |
| D76 | Every talk ends with a closer (`talkgenerator.closers`), a slide after those it asked for, in its format's kind, language and look, so none spends a slide on questions; slide numbers and checks leave it out (`Deck.counted()`). |
| D77 | A family can have sets of decoration (`themes.Variant`), as `kids` has four; seven more families, none for laughs: `sticky notes`, `corkboard`, `90s desktop`, `spreadsheet`, `Y2K`, `70s retro` and `glossy magazine`. |
| D78 | Slides of a surprising picture to explain, with little text: Exhibit A, Pick one, a picture equation, What do you see? and before and after; standing in, they look nothing up, so an inkblot and an emoji equation are spare kinds (D66). |
| D79 | Six more formats (`infomercial`, `documentary`, `court`, `museum`, `wedding`, `book_report`), each with a content pack and a closer, and eight more personas; the TED-like talk weighs 55 (`FORMAT_WEIGHTS`), so most talks stay TED-like. |
| D80 | Talks are playable at a glance: fewer words (texts kept whole up to `TextField.room`, else cut at a sentence or clause), build dots and other cues, a photo of the talk's world by its title, more pictures, green, orange and red flags, no nudity or self-harm, and prompts tuned in `scripts/prompt_lab`. |
| D81 | The title slide's photo leaves out one grown-up alone, who'd pass for the presenter (`title_pictures.alone`); the presenter's job is kept whole or ends where a phrase of it does (`TextField.phrases`). |
| D82 | An academic talk's references carry no number of their own beside the slide's, a long work is cut after its year, and other slides take their place in about a third of the talks (`Part.others`). |
| D83 | For laughs, a theme moves not at all, some or lots (`Family.motion`), with its family's PowerPoint entrance effects (`talkgenerator.render.entrance_effects`), from a stream of its own so nothing else changes. |
| D84 | Useless facts come from a week's pool of 500 (`flavour.POOL`), in English talks only; a meme whose picture shows how it ends (`at_once` in `data/memes.json`) has its captions from the start, and stays still. |
| D85 | The prompt and the Skill ask for ten words a slide or fewer, so the pictures carry it, and for no tags tacked on to make a line funny; in English talks, a tag a model adds anyway goes (`realize.untagged`). A quiz's options, a tier list's tiers, flags, an alignment chart's cells and reviews are all pictures about half the time (`kinds.PicturedItems`; a quiz of pictures in `v5/quiz-pictures`); the kinds that are mostly words count for half their weight (`kinds.wordiness`); charts and diagrams try a picture first three times in four; captions, lessons, posts and a big number's label and source are asked for in fewer words, and real quotes are 100 characters; no hint has a gap to copy; of a Reddit search's posts, the more upvoted ones' pictures are picked more often (`reddit.upvoted`). |

## 18. Sources

Language models and the Skill:

- OpenRouter: [rate limits](https://openrouter.ai/docs/api-reference/limits), [OAuth PKCE](https://openrouter.ai/docs/use-cases/oauth-pkce).
- Sign in with ChatGPT: [developer docs](https://developers.openai.com/siwc),
  [integrating it in an open-source app](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt),
  [help center](https://help.openai.com/en/articles/20001410-sign-in-with-chatgpt).
- Claude: [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
  [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview).

The image sources of section 10.4:

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
- Imgflip: [API](https://imgflip.com/api).
