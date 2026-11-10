# Using it from Python

A talk is made in three steps: a planner decides what every slide says (the classic generator, a language model, or
Claude through a plan), the realizer finds its images and charts, and a renderer draws it. In between, the talk is a
deck: plain, versioned JSON data, which the PowerPoint is drawn from. Every way of making a talk ends in a deck, and
every renderer starts from one.

## Making a talk: `stream_talk`

`generator.stream_talk` makes a talk and hands it over while it's made, as events:

```python
from talkgenerator import generator

for event in generator.stream_talk("default", 8, topic="peanuts", int_seed=42):
    print(event.event)  # talk.started, slide.ready (8 times), talk.finished
```

| Event | When | What it holds |
| --- | --- | --- |
| `talk.started` (`TalkStarted`) | once the title is known | the title, presenter, topics, language, seed, how many slides there will be, the theme's name and its tokens (`style`), and which language model writes the talk |
| `slide.ready` (`SlideReady`) | for every slide, in order | its `index` and the `slide`, laid out in the talk's theme |
| `slide.updated` (`SlideUpdated`) | a slide again, before `talk.finished`: with a picture that came in later (an AI picture, or the vision pick's), or with `slide_seconds`, the real slide that came after all | its `index` and the `slide`, laid out in its place; `late` is true for the real slide that came after all, in place of what stood in for it (see [A time limit per slide](#a-time-limit-per-slide)) |
| `slide.spare` (`SlideSpare`) | with `spares`, early on, once each is made | which spare it is (`index`, from 0) and the `slide`, laid out in the talk's theme without a slide number: none of the talk's slides (see [Spare slides](#spare-slides)) |
| `talk.progress` (`TalkProgress`) | with `progress`, from the very start (before `talk.started`) and whenever how far the talk is changes | its `stage`, every slide's own (`slides`), the parts of the plan in (`parts`), and how many slides the model writes and wrote (`writes`, `written`): see [How far a talk is](#how-far-a-talk-is) |
| `talk.finished` (`TalkFinished`) | at the end | the whole `deck` |

The events are in `talkgenerator.models.events`. Each one's `event` is its name, and its `to_json()` is one line of
JSON, as a Server-Sent Event would carry it. A language model's slides come in while it still writes the rest, and
classic slides made in parallel each come once their work is done, in order. Leaving the loop stops the talk; an
error that stopped it comes out of the loop.

While a talk streams, its images are probed rather than downloaded: their first bytes tell their format and size, as
a browser that shows the slides loads them itself. Every image says how a browser may show it (`display`, as its
source's terms allow): from its own link (`direct`), through a pass-through proxy (`proxy`), from a copy the app keeps
as long as the deck (`copy`, for Pixabay), or as a file of talkgenerator's own (`local`). It also says its size in
pixels, its license class, its license (with a link), the look it was found for, and what a look at its thumbnail
found.

The options, after the format (`"default"`, `"ted"`, `"interview"`, `"pitch"`, `"academic"`, `"corporate"`,
`"keynote"` or `"test"`, or `"random"` for one the talk's seed picks after its persona: see
[`--schema random`](command-line.md#formats-and-license-policies)) and the number of slides:

| Option | What it is |
| --- | --- |
| `topic`, `title` | What the talk is about (a string, comma-separated topics, or a list), and its title |
| `topic_or_title` | Instead of `topic` and `title`: what someone typed, which could be either (see [`--topic_or_title`](command-line.md#what-the-talk-is-about)); the deck's `topic_or_title` says how it was read |
| `presenter`, `name_styles` | The presenter's name, which never goes to a language model, or else the styles of made-up names, as a list or separated by commas |
| `persona` | Who presents the talk, such as `"startup_founder"` (see [`--persona`](command-line.md#what-the-talk-is-about)), `"none"`, or `None` for one the talk's seed picks; the deck's `persona` (and `talk.started`'s) says which it was |
| `personas` | The personas the talk's seed picks from, as a list or separated by commas, such as `["startup_founder", "consultant"]`; `None` for all of them. A persona named goes first |
| `language` | `"en"`, `"nl"`, `"fr"`, `"de"`, `"es"`, `"it"`, `"pt"` or `"sv"` |
| `llm` | The language model: a spec, such as `"openrouter"` or `"anthropic:claude-haiku-5-5"`, a provider object, or `None` for your settings' (see [Language models](language-models.md)) |
| `budget` | What the talk may spend: `talkgenerator.llm.ledger.Budget(max_cost_usd=0)` lets only free models write it |
| `theme`, `style_chaos`, `extreme_themes` | The look (see [Themes](images-and-themes.md#themes)) |
| `theme_families` | The families a random theme can be of (a chaos deck's slides' too), as a list or separated by commas, such as `["dark minimal", "Swiss poster"]`; `None` for all of them. A family named as `theme` goes first |
| `license_policy` | The license classes its images may have (see [Licenses](images-and-themes.md#licenses)) |
| `image_generator`, `image_budget` | An image generator, as `--image_generator` names one or an object, and how many pictures it may make (see [Generated pictures](images-and-themes.md#generated-pictures)) |
| `vision_pick` | A vision model that picks the pictures of the slides a language model writes, each among a few candidates (see [The vision pick](images-and-themes.md#the-vision-pick)): `True` (the talk's own model when it reads pictures, else OpenRouter's free models that do), a spec such as `"anthropic:claude-haiku-5-5"`, a provider object, or `None` (off, the default). In `stream_talk`, a slide whose picture it changed comes again, as `slide.updated`, before `talk.finished` |
| `int_seed`, `parallel` | The seed (the same seed gives the same talk, in parallel or not) and whether slides are made at the same time: `True` (all of them; a language model's eight at a time), a number (at most that many at once, as a small server does: each slide being made holds what it found until it's settled), or `False` (one by one) |
| `spares` | `stream_talk` only: how many spare slides to send, for a presenter who goes on before the next slide is in (see [Spare slides](#spare-slides)); 0, the default, for none |
| `slide_seconds` | `stream_talk` only: how long a slide may take at most, after which it comes at once with what's quick (see [A time limit per slide](#a-time-limit-per-slide)); `None`, the default, for no limit |
| `progress` | `stream_talk` only: `True` to get how far the talk is, as `talk.progress` events (see [How far a talk is](#how-far-a-talk-is)); `False`, the default, for none |

### Spare slides

A presenter can catch up with a talk that's still being made: a language model writes its slides one after another,
and a slide's pictures take seconds to find. `stream_talk(..., spares=3)` also sends three spare slides, for a
presentation to show instead of waiting, with a mark of its own ("spare"), until the next slide is in:

```python
from talkgenerator import generator
from talkgenerator.models.events import SlideSpare

spares = []
for event in generator.stream_talk("default", 10, topic="peanuts", spares=3):
    if isinstance(event, SlideSpare):
        spares.append(event.slide)  # to show while the next slide isn't in yet
```

They're made as soon as the talk has started, one after another on a thread of their own, about the talk's topic and
as its persona favours them, and each comes as a `slide.spare` once it's made: kinds of slides that take a hundredth of
a second and hardly ever fail, drawn without pictures from talkgenerator's own templates (a tier list, an alignment
chart, red flags, reviews, an acronym, a quiz, a chart...). In a talk in another language than English, whose classic
slides would be English, a spare is a picture of the topic without text instead. They come laid out in the talk's
theme, without a slide number, until the talk's last slide is in: a spare not made by then is left out, and none comes
after `talk.finished`. A talk on a topic its slides won't make light of (death, say) gets fewer of them, or none.

Spares are none of the talk's slides: they have no place in the deck, the finished deck (and so its PowerPoint)
leaves them out, and as they're made from random streams of their own, the talk's slides come out the same with spares
or without.

### A time limit per slide

Slides come in order, so one slow slide (its pictures still being looked for) holds back every slide after it. With
`stream_talk(..., slide_seconds=8)`, every slide but the title slide has 8 seconds at most, counted from when it could
come: once the slide before it came, and its text, for a slide a language model writes (the model's writing doesn't
count). A slide that isn't made by then comes at once with what's quick instead:

- A slide the model wrote keeps its texts. It comes without the pictures it can do without (a picture behind a big
  number, say), and with spare pictures of the talk's topic for the ones it can't: the talk finds three of those
  early, while the model writes.
- Otherwise, a stand-in takes its place: a slide of the spare slides' kinds, about the slide's own topic, made in a
  hundredth of a second (in a talk in another language, a spare picture of the topic, without text).

That slide is the talk's for now: it's in the deck, at its place, numbered, and its notes say it ran out of time. What
it waited for goes on by itself, and once that's done, the real slide comes after all, in its place: a `slide.updated`
at its index with `late` true, laid out where it stands (the slides after it stay as they were laid out), and in the
deck too, its notes saying how late it came. It doesn't when it would repeat another slide, or when the talk has as
many slides of its kind as its caps allow (a slide after it took that room). Once the other slides are in,
`talk.finished` waits for it 20 seconds at most (`LATE_SECONDS`, in `talkgenerator.schema.presentation_schema`); after
that, what stood in for it stays. A presentation that's on that slide may rather keep showing the stand-in until the
presenter goes on, as talkgenerator.com does. With nothing to stand in (a topic the spare kinds won't make light of), the slide
is waited for after all. Of the slides with pictures timed for D66, 5% took more than 8 s. The same seed gives the same
talk as long as no slide runs out of time; one that does makes the talk depend on how long its sources took.

### How far a talk is

A talk takes a while: a free language model can take seconds to say its first word, and a slide's pictures take
seconds to find. `stream_talk(..., progress=True)` also sends how far the talk is, as a `talk.progress`, from its very
start (before `talk.started`, which waits for the model's title and first slide) and whenever that changes, whole each
time, so the last one says it all:

```python
from talkgenerator import generator
from talkgenerator.models.events import TalkProgress

for event in generator.stream_talk("default", 8, topic="peanuts", llm="openrouter", progress=True):
    if isinstance(event, TalkProgress):
        print(event.stage, event.written, "of", event.writes, "written", event.slides.count("ready"), "ready")
```

Its `stage` is where the talk is: `starting` (its persona, format, theme and its slides' words are being picked),
`asking` (its language model was asked, and hasn't said a word yet: it may be thinking), `planning` (the model's plan
comes in: the talk's title, the presenter's job and name, its thesis, and at the Advanced level every slide's word and
idea), `writing` (the model writes the slides), `composing` (the slides are made, their pictures looked up, and come
in order) and `finishing` (every slide is in, and the talk waits for what comes after them: generated pictures, a
vision pick, a slide that ran out of time). A classic talk goes from `starting` to `composing`, and a model that's asked
again (it found the topic unsafe, or answered in English in a talk in another language) takes the talk back to
`asking`. `slides` has every slide's own stage, by its number: `waiting`, `planned` (its idea is in, at the Advanced
level), `written` (its texts are in, and its pictures are being looked up) or `ready` (it came as a `slide.ready`); a
slide the model doesn't write, such as the title slide, goes from `waiting` to `ready`. `parts` counts the parts of
the model's plan as they come in, the fields of its spine one by one and every slide's idea, `writes` how many slides
the model writes (none in a classic talk), and `written` how many of those it wrote so far. talkgenerator.com shows it
in front of its curtain: the stage in words, a dot for every part of the plan, and a mark for every slide.

## A PowerPoint: `render_pptx`

`talkgenerator.render.powerpoint.render_pptx` draws a deck as a PowerPoint (python-pptx's `Presentation`),
downloading its images first, a few at a time:

```python
from talkgenerator import generator
from talkgenerator.models.events import TalkFinished
from talkgenerator.render.powerpoint import render_pptx

for event in generator.stream_talk("default", 8, topic="peanuts", int_seed=42):
    if isinstance(event, TalkFinished):
        render_pptx(event.deck).save("peanuts.pptx")
```

`render_pptx(deck, debug_notes=True)` explains in every slide's speaker notes how it was made. A classic deck comes
out in the 2019 template, a themed deck as shapes.

## Decks

A deck (`talkgenerator.models.deck.Deck`) is the talk as data: its title, topics, presenter, language, format, seed,
theme and the theme's tokens, the language model that wrote it and what it asked of it (`usage`), its license policy,
and its slides. A slide has a type, a layout and elements (texts, images, charts, diagrams and shapes), its credits
and its notes; in a themed deck, every element has its box on a 1920×1080 canvas and every text its style. It holds
no image bytes and no python-pptx objects, only JSON, so it can be saved, sent, shown in a browser and drawn again.
`deck.to_json()` gives its JSON, and `Deck.from_json()` reads it back. Say you saved a talk's deck with
`talkgenerator --topic peanuts --save_json true`, as `output/peanuts.json`:

```python
from pathlib import Path

from talkgenerator.models.deck import Deck
from talkgenerator.render.powerpoint import render_pptx

deck = Deck.from_json(Path("output/peanuts.json").read_text(encoding="utf-8"))
print(deck.title, deck.seed, deck.usage.cost_usd)
render_pptx(deck).save("peanuts-again.pptx")  # the same slides again
```

The same deck always gives the same JSON, and draws the same slides. `talkgenerator render` and the MCP server save
decks too (as `<name>.deck.json`). `Deck.json_schema()` (or `talkgenerator schema deck`) is the format's JSON Schema,
and `deck_version` changes whenever the format changes in a way older readers can't handle.

talkgenerator.com works this way: `stream_talk` streams a talk into the browser, which draws its slides from their
deck form, and the PowerPoint is drawn from the saved deck when someone downloads it.

## Plans: `render_plan`

A talk plan (`talkgenerator.models.plan.TalkPlan`) is a talk written outside talkgenerator, by Claude through the
[Skill](use-with-claude.md) or by you. `talkgenerator.plan.external.render_plan` realizes it (finds, checks and
credits its images, and makes the slides that don't come out the classic way), saves the PowerPoint with its deck's
JSON and a contact sheet, and returns the report that `talkgenerator render` prints:

```python
from pathlib import Path

from talkgenerator.models.plan import TalkPlan
from talkgenerator.plan.external import render_plan

plan = TalkPlan.model_validate_json(Path("plan.json").read_text(encoding="utf-8"))
report = render_plan(plan, output="talk.pptx")
print(report["summary"])  # how many slides came out as planned, classic, as a picture, or were left out
```

It takes `schema_name`, `presenter`, `theme`, `license_policy`, `name_styles`, `int_seed` and `output_folder` too.

## For a settings menu

| Call | What it lists |
| --- | --- |
| `talkgenerator.design.themes.catalog()` | every theme, with a label, a line on what it looks like, and whether it's one for laughs (`themes.choices()`: just the names) |
| `talkgenerator.names.catalog()` | the name styles, with a label, a description and whether they're on by default |
| `talkgenerator.personas.catalog()` | the personas who can present a talk, with a label and who they are (`personas.choices()`: just the names, with `random` and `none`) |
| `talkgenerator.schema.presentation_schema_types.format_odds(persona)` | how likely a talk with `"random"` for its format is to be of each format, with that persona (or none) |
| `talkgenerator.images.licenses.catalog()` | the license policies |
| `talkgenerator.images.profiles.catalog()` | the image looks and flavour packs |
| `talkgenerator.plan.languages.LANGUAGES` | the languages a talk can be in |
| `talkgenerator.topics.random_topics(count)` | topics at random, from a list of 736 |

## `generate_presentation`

`generator.generate_presentation()`, talkgenerator 4's way to make a talk, keeps working throughout talkgenerator 5,
with a `DeprecationWarning` that says what to use instead. [Migrating from 4.x](migrating-from-4.md) shows how.
