# Migrating from talkgenerator 4

talkgenerator 5 keeps 4.x's command line and settings: every option of `talkgenerator` still works, and so do the
`.env` file and its keys. What changes is what a talk looks like by default, who may write it, and the Python API,
where `generator.generate_presentation()` and `SlideDeck.to_slide_deck_dictionary()` give way to streamed talks and
deck JSON. Both keep working throughout talkgenerator 5, with a `DeprecationWarning` that says what to use instead.

The [changelog](https://github.com/twinters/talk-generator/blob/master/CHANGELOG.md) lists everything that's new.

## Installing

talkgenerator 5 still needs Python 3.11 or newer, and `pip install --upgrade talkgenerator` upgrades it. Its one new
dependency is pydantic. The language model SDKs and the MCP SDK are extras, which 4.x didn't have:
`talkgenerator[openai]` (for OpenRouter, OpenAI and your ChatGPT plan), `talkgenerator[anthropic]` (for Claude),
`talkgenerator[gemini]` (for Gemini), `talkgenerator[llm]` (all three) and `talkgenerator[mcp]` (for
`talkgenerator mcp`).

## Talks are classic without a language model

Without a language model, a talk is classic: the 2019 generator's slides, as in 4.x. A language model writes the talk
only when you've set one up, and a paid one only when you ask for it:

- with an OpenRouter key (`OPENROUTER_API_KEY`, or `talkgenerator login openrouter`), OpenRouter's free models write
  your talks, at no cost;
- once you've signed in with ChatGPT (`talkgenerator login chatgpt`), your ChatGPT plan's models do;
- Claude, OpenAI's models and OpenRouter's paid ones only write talks when `--llm` or `TALKGENERATOR_LLM` names them,
  even when their keys are set.

`--llm none` makes a classic talk, and `DISABLE_LLM=1` in your `.env` makes every talk classic that doesn't name a
model with `--llm`. [Language models](language-models.md) has the details.

## What a talk looks like

Seven things changed, and five of them can be set back, to come as close to 4.x's talks as talkgenerator 5 gets:

| | talkgenerator 4 | talkgenerator 5 | To keep 4.x's |
| --- | --- | --- | --- |
| The look | the 2019 template | a theme the talk's seed picks (`--theme random`) | `--theme classic`, or `TALKGENERATOR_THEME=classic` |
| The presenter's made-up name | a random first and last name | a pun on the topic, a fun surname or a famous-name pun: the language model's, or else one of talkgenerator's own, which cover 642 of the 736 topics of its topic list (other topics get a random name) | `--name_styles classic` |
| Who presents it | nobody in particular | a persona the talk's seed picks (a startup founder, a medieval historian...), whose kinds of slides come up more often, and whose own titles half of the classic titles are | `--persona none` |
| Real facts | none | half of a classic talk's fun facts and quizzes are real (Wikipedia's, Open Trivia DB's), and some of its dares and closing lines a real dad joke or piece of advice, credited on the slide | `DISABLE_FACTS=1` |
| Slide numbers | none | slides are numbered ("7/12"), small, in a corner | |
| Charts and diagrams | always drawn | half of them try a picture first, in their place, under their title (a real chart from the internet, a weird picture), and are drawn when none is found | `DISABLE_PICTURE_FIRST=1` |
| The slides | v4's slide types | more than thirty more (big numbers, quizzes, timelines, memes with live captions, tier lists, fake error messages...), and texts from the TED content pack, in a TED talk's voice and about four times as many as 4.x had | |

Classic slides look as they did, and their images come from about the same sources, with a few changes: history
slides prefer old photographs (from museums too) in black and white or sepia, statements' backdrops come from
Pixabay, Unsplash and Pexels, and charts are quieter (no gridlines or made-up numbers along their axes). Charts' own
texts now show on the 2019 template's black, where PowerPoint drew them in black.

## Seeds are reproducible

`--int_seed` now gives the same talk every time, also with `--parallel` (the default) and with seed 0, as long as the
sources answer the same. In 4.x, the slides made in parallel shared one random generator, so a seed could give
another talk on every run. Every talk without a seed gets a random one, which the logs and the deck JSON mention, so
any talk can be made again.

A seed doesn't give the talk it gave in 4.x: the random choices are drawn differently now, and the new slide types
and names come into them. Talks made with 5 come out the same with 5.

## Schemas become formats

`--schema` keeps its values, and picks the talk's format: which kinds of slides it has, and where its images may come
from. The license policy that 4.x's `ted` schema had built in (copyright-free images only) is now an option of every
talk, `--license_policy`:

| `--schema` | In talkgenerator 5 |
| --- | --- |
| `default` | the format `default`, with license policy `all` (every image, memes and gifs too) |
| `ted` | the format `ted`, with license policy `open` (everything but fair use: no memes, gifs or Reddit's posts); the image search now keeps to it too |
| `interview` | the format `interview`, with license policy `all` |
| `test` | the format `test` |

`--license_policy open` makes any talk keep to copyright-free images, and `talkgenerator formats` lists the formats
with their policies (`--list` still lists their slide generators). The new commands for plans, `render` and
`formats`, call the choice `--format`. Four formats are new: `pitch` (a startup pitch), `academic` (a talk at an
academic conference), `corporate` (a company's all-hands or quarterly business review) and `keynote` (a product
keynote). `--schema random` leaves the format to the talk's seed, which picks one that its persona favours.

## `generate_presentation()` gives way to `stream_talk()`

`generator.generate_presentation()` still takes 4.x's arguments, and its own new ones (`theme`, `llm`, `language`,
`name_styles`, `topic_or_title`, `license_policy` and more), and returns what it did: the PowerPoint, the talk, and
the file it saved. Calling it gives a `DeprecationWarning`. Python shows those only for code in `__main__`, and pytest
always: run with `python -W default::DeprecationWarning` to see it elsewhere.

Instead, `generator.stream_talk()` takes the same talk options (but saving), hands over the talk while it's made, and
ends with the whole deck, which `render_pptx` draws as a PowerPoint. In talkgenerator 4:

```python
from talkgenerator import generator

presentation, slide_deck, output_file = generator.generate_presentation(
    schema="default", slides=8, topic="peanuts", int_seed=42, output_folder="output", open_ppt=False
)
```

In talkgenerator 5:

```python
from talkgenerator import generator
from talkgenerator.models.events import TalkFinished
from talkgenerator.render.powerpoint import render_pptx

for event in generator.stream_talk("default", 8, topic="peanuts", int_seed=42):
    if isinstance(event, TalkFinished):
        render_pptx(event.deck).save("peanuts.pptx")
```

The deck is the same as the one `generate_presentation` makes for the same options and seed. To show slides as they
come, as talkgenerator.com does, handle the `slide.ready` events too ([Python](python.md#making-a-talk-stream_talk)).
For a talk that Claude or you planned, `talkgenerator.plan.external.render_plan()` realizes and renders the plan
([Python](python.md#plans-render_plan)).

`stream_talk` probes images rather than downloading them, as a browser loads them itself; `render_pptx` then
downloads them for the PowerPoint. It has no `save_ppt`, `output_folder`, `open_ppt`, `save_json`, `print_logs` or
`debug_notes`: you save the PowerPoint and the deck where you like (`render_pptx(deck, debug_notes=True)` for the
notes), and set up logging as usual (the logger is called `talkgenerator`).

## `SlideDeck.to_slide_deck_dictionary()` gives way to deck JSON

In 4.x, `to_slide_deck_dictionary()` gave every slide's arguments as a dictionary, with image and chart objects in it,
so it wasn't JSON. In talkgenerator 5, a talk is a deck: plain, versioned JSON data, which the PowerPoint, the browser
view on talkgenerator.com and every other renderer draw. `slide_deck.to_deck()` gives it, `deck.to_json()` its JSON,
and `Deck.from_json()` reads it back ([Python](python.md#decks)).

`to_slide_deck_dictionary()` now gives the deck's slides as dictionaries (type, layout, elements, credits and notes),
which are JSON, with a `DeprecationWarning`. That's a breaking change for code that read 4.x's dictionaries: read
the deck instead.

```python
deck = slide_deck.to_deck()
for slide in deck.slides:
    print(slide.type, [element.role for element in slide.elements])
```

## Smaller changes

- The classic chart styles moved from `talkgenerator.sources.chart` to `talkgenerator.render.charts` (the old names
  still work).
- Every slide is drawn from its deck form, so a PowerPoint and its deck JSON always match.
- GIPHY's searches aren't cached any more, as GIPHY's API rules forbid it; the other search APIs still are.
- InspiroBot's posters come from its older posters, drawn with the talk's seed, so no request goes to its API any
  more.
- The new image sources need no key (the Met, the Cleveland Museum of Art, the Wellcome Collection, NASA, Flagpedia,
  Imgflip), except the Smithsonian, which takes a free `DATA_GOV_API_KEY`.
- `--save_json true` saves a talk's deck next to its PowerPoint.
- Talks can be in Dutch, French, German, Spanish, Italian, Portuguese and Swedish, with a language model
  (`--language`).
