---
name: talkgenerator
description: Writes absurd talks for improvised presentations (PowerPoint karaoke, improvised TED talks, battle decks) and renders them as real PowerPoint files with licensed, credited images, using the talkgenerator package. Use it whenever someone wants slides to present unprepared, a karaoke deck, a fake TED talk, talks for an improv show or a party game, a batch of decks from audience suggestions, or a funny presentation on any topic, even if they don't name talkgenerator; also to fix or render again a talk plan (a talkgenerator plan JSON).
license: MIT
compatibility: Needs Python 3.11+ with the talkgenerator package (version 5 or newer), a shell to run it (or, in Claude Desktop, its MCP server), and internet access for the image sources. Image API keys in a .env file are optional.
---

# Improvised talks with talkgenerator

You write the talk, talkgenerator makes the deck. You decide what every slide says and what its images should show;
talkgenerator searches the image sources, picks images it may use, credits them on the slides, lays everything out,
and saves a PowerPoint. It reports back in JSON, and you fix what didn't work and render again.

A plan holds words and image search queries, never image addresses: finding, licensing and crediting images is
talkgenerator's job, which keeps every deck usable on a stage.

## Before the first talk

Check that the command is there:

```bash
talkgenerator formats
```

If it isn't, or doesn't know `formats`, install or upgrade it (`pip install --upgrade talkgenerator`): this needs
version 5 or newer. The first run downloads some language data, which takes a minute.

Images come from many sources, some of which need free API keys (Unsplash, Pexels, Pixabay, GIPHY, Reddit). They go
in a `.env` file, which talkgenerator looks for in the folder it runs from (and next to its own files);
`.env.example` in talkgenerator's repository lists them, with where to get each. Without keys it still works, with
fewer sources. Every report lists the sources it had to skip, under `sources_without_keys`: that's the list to go
by. If it's long, tell the user once that free keys give better images, and leave it there: the user puts keys in
`.env` themselves, never in a plan or in the chat.

## Making a talk

1. **Work out what's wanted**: the topic (several topics work too) or the title, as what's asked for can be either
   ("penguins" is a topic, "Why I Joined a Penguin Cult" a title, which stays the talk's title with only its obvious
   slips fixed, never reworded, and a title in quotes stays word for word; a few words such as "Cats are liquid"
   are a premise, to build a funnier, more specific title on); how many slides (a "10-slide deck" is the
   title slide plus 9 slides in the plan, and 10 to 12 slides suit a talk of five minutes); the language; whether
   the presenter's own name should be on the title slide (without it, you make one up, which is part of the fun);
   and the format. The `default` format draws on every image source, Reddit's wilder pictures and gifs too.
   For a deck shown beyond a circle of friends (at a company event, on a stage, online), use `ted`: copyright-free
   images only (its license policy, `open`, allows every image but fair use: no memes, gifs or Reddit's posts).
   Another format can keep to it too: `talkgenerator render plan.json --license_policy open`. For a startup pitch,
   use `pitch`; for a talk at an academic conference, `academic`; for a company's all-hands or quarterly business
   review, `corporate`; for a product keynote, `keynote`; for a late-night TV infomercial, `infomercial`; for a nature
   documentary, `documentary`; for a court case, `court`; for a museum tour, `museum`; for a wedding toast, `wedding`;
   and for a school book report, `book_report`. Don't hold things up with questions: pick sensible defaults and say
   which.
2. **Look up the slides you can use** in the format's reference: [references/slides.md](references/slides.md) for
   `default`, [references/slides-ted.md](references/slides-ted.md) for `ted`,
   [references/slides-pitch.md](references/slides-pitch.md) for `pitch`,
   [references/slides-academic.md](references/slides-academic.md) for `academic`,
   [references/slides-corporate.md](references/slides-corporate.md) for `corporate`,
   [references/slides-keynote.md](references/slides-keynote.md) for `keynote`,
   [references/slides-infomercial.md](references/slides-infomercial.md) for `infomercial`,
   [references/slides-documentary.md](references/slides-documentary.md) for `documentary`,
   [references/slides-court.md](references/slides-court.md) for `court`,
   [references/slides-museum.md](references/slides-museum.md) for `museum`,
   [references/slides-wedding.md](references/slides-wedding.md) for `wedding` and
   [references/slides-book_report.md](references/slides-book_report.md) for `book_report`. They list the slide kinds, their
   texts, length limits, images and recipes. (`ted` has no full-screen images and no recipes for slides about the
   presenter: an about-me slide there is a two- or three-column slide with about-me captions.) The formats beyond
   the TED-like talk have an arc, which their references open with: the parts their slides go through, in order (a
   pitch's problem, solution, market, business model, traction, competition, team, roadmap and ask; an academic
   talk's motivation, outline, related work, method, results, limitations, future work, acknowledgements, references
   and questions; an all-hands' agenda, KPIs, wins, roadmap, org change, synergies, ask and Q&A; a keynote's opening,
   one idea, reveal, features, demo, price, one more thing and closing line; an infomercial's problem, product, demo,
   testimonials, fine print, price, "but wait" and call to order; a documentary's opening, habitat, behaviour,
   sighting, ritual, threat and closing; a court case's charges, evidence, witness, alibi, objection, closing argument
   and verdict; a museum tour's welcome, masterpiece, artist, eras, artefact and gift shop; a wedding toast's intro,
   how they met, the story, the couple, advice and the toast; a book report's book, author, characters, plot,
   favourite part, moral and rating), each with its recipes. A pitch's problem and an academic talk's motivation open on a `problem` slide most of the time: the
   talk's why, a problem that hooks the audience (weird, everyday, or real), with a picture behind it or beside it. Plan their slides in that order, each with a recipe of its part, and write the `title` and
   `presenter_job` as their references say (a pitch's title names its made-up startup; an academic talk's job is an
   affiliation; an all-hands' title is the quarter and a slogan; a keynote's names its made-up product; an
   infomercial's its gadget; a book report's the book).
   `talkgenerator formats --details --format <format>` prints the same for the version that's installed, and
   `talkgenerator schema plan` the plan's JSON Schema.
3. **Write the plan** as a JSON file, like [references/example-plan.json](references/example-plan.json), say
   `plans/birdwatching.json`. It has the talk's `format` (when it isn't `default`), `topic`, `title` (at most 80
   characters), `presenter_job` (at most 50; the title slide reads "By <name>, <job>"), `presenter_name` (a made-up
   name of at most 40 characters: a pun on the topic, such as "Prof. Anna Tomy" for medicine; an ordinary first
   name with a surname that fits the topic too well, such as "Linda Hivesworth" for bees; or a historical figure's
   name bent to fit it, such as "Albert Einstone" for geology; with a title such as Prof., the job agrees),
   `thesis`, and `language` when it isn't English, then its `slides`, and optionally its `theme`: without one, the
   user's default (a random theme, unless their TALKGENERATOR_THEME says otherwise); `classic`, the 2019 template;
   `random`; a family such as `"hacker terminal"`, `"chalkboard"` or `"1997 WordArt"` (`talkgenerator render
   --help` lists them); or `chaos`, every slide its own. The title slide is made for you, from these. Talks can be in
   Dutch (`"nl"`), French (`"fr"`), German (`"de"`), Spanish (`"es"`), Italian (`"it"`), Portuguese (`"pt"`) and
   Swedish (`"sv"`): write every text in that language, and keep the image queries in English.
4. **Render it**:

   ```bash
   talkgenerator render plans/birdwatching.json -o talks/birdwatching.pptx
   ```

   Add `--presenter "Name"` for the presenter's own name, which goes before the plan's `presenter_name` (the
   report's `notes` say when talkgenerator couldn't use that one, and made one up). Without `-o`, the PowerPoint
   goes in `output/`, named after the plan. Next to it come `<name>.deck.json` (the deck as data, which you can
   leave be) and `<name>.images.png` (a contact sheet of all the images). Several plans at once: `talkgenerator
   render plans/*.json --output_folder talks`.
5. **Read the report** (JSON, on stdout). For every slide of the plan (`plan_index` is its place in your `slides`,
   `deck_slide` its place in the deck) it gives the `outcome`: `as planned`, `classic` (talkgenerator made the slide
   its own way, because the plan's version didn't come out), `picture` (in a talk in another language than
   English, where talkgenerator's own slides would be English: a picture of the slide's concept, without text) or
   `left out`, with the `problems` that caused that, and `warnings` about texts that were cut off, fields that don't
   exist, and such. `checks` lists what the deck's automated checks found (a slide missing what it needs, template
   code on a slide, images without credits or shown twice, a talk or slide in the wrong language), and `notes` what
   concerns the whole talk. A field that isn't there means there's nothing to say.
6. **Look at the images.** "As planned" means every image was found, not that it fits: image search is a lottery.
   Each slide's `images` give what an image was searched with (`searched`: your query, or the slide's concept when
   the query found nothing), what it `shows` according to its source (most stock photos say), its credit, and its
   `page`. If you can look at pictures, look at the contact sheet (`contact_sheet` in the report): every image with
   its slide's number, its search and the slide's texts. Change the query of every image that doesn't fit, or that
   reads badly next to its text (see "Keep it kind").
7. **Render again** with the seed from the first report, `--int_seed <seed>` (and the same `--presenter`): the
   images you didn't change then come out the same, and an old query brings its old image back (Reddit images can
   still change, as Reddit does). Render at most three times in all: a classic slide or an odd image is part of
   the game.
8. **Hand it over**: say where the PowerPoint is, how many slides came out as planned, and the command that renders
   it again (with its seed, so the user can add the presenter's name without changing the slides). Don't spoil the
   talk: for karaoke, the presenter shouldn't see the slides beforehand, so don't describe them unless asked.

For a batch, say ten talks from tonight's audience suggestions, write one plan per topic in a folder and render
them all at once; vary the titles, presenter jobs and slide kinds, so the evening doesn't repeat itself.

## What makes a good karaoke talk

The fun is in watching someone explain slides they've never seen as if they had planned it all. So write slides
that give the presenter something to work with, rather than finished jokes:

- **Keep it short.** Titles of a few words, captions of one to four. No paragraphs, no bullet points: the length
  limits in the slide reference are maximums, not targets.
- **Play it straight.** Write like a confident expert giving a serious talk, however absurd the content. The
  audience laughs at the presenter making sense of it, not at puns on the slides.
- **Leave gaps.** A good slide raises a question the presenter has to answer: an odd juxtaposition, a suspiciously
  specific claim, a chart that needs explaining. Don't explain the joke, or the image.
- **Build one talk.** Give it a thesis and follow it. Later slides call back to earlier ones (a running gag, a
  recurring character, a strange claim from before), and the conclusions call back to several of them.
- **Shape it like a talk.** A common arc: who the presenter is (an about-me slide), maybe an agenda, some history
  (a made-up historical figure, old photos, a timeline), the core (bold statements, contrasts such as Expectation
  and Reality, a three-step build-up, a quiz for the audience, a social media post or a news headline, a meme, a fun
  fact, an acronym for a made-up method, red flags, reviews with stars), the evidence (a chart or two, a big number or
  KPI tiles, a Venn diagram, a 2×2 matrix, a pyramid, an iceberg, a flowchart whose every path leads to the same end, a
  tier list, an alignment chart, an executive summary nobody can read, with one absurd point highlighted), and
  conclusions that call back. (No need for "Questions?" or "Thank you" at the end: talkgenerator ends every talk
  with a closer of its own, after your slides, in its language and format.) A dare for the presenter ("present the
  next slide as a haiku") works once, halfway through, as does a fake error message ("Retry, Ignore, Panic").
  Slides of a surprising picture with hardly any words give the presenter the most to explain: Exhibit A (an odd
  picture as evidence; a later Exhibit B can call back to it), two pictures to pick one of, a picture equation
  (picture + picture = surprise, or emoji), "What do you see?" (a face in something, or an inkblot) and a before
  and after. Mix the kinds: no two charts in a row, and each new kind at most once.
- **Write image queries that find something**: one to three common English words for one subject, such as "owl",
  "ficus", "old watering can" or "dense tropical jungle". Scenes with several parts ("plant on reception desk"),
  actions and moods ("waiting", "alone"), and words that are photo subjects themselves ("camera", "photo") find the
  wrong things. When an image keeps missing, cut its query down to one common noun. The texts can be in any
  language; the queries stay in English, which the image sources know best.
- **Give every slide with images a `concept`**: its subject as a search of one to three words ("medieval bread").
  An image whose query finds nothing is searched for with it (an image that's merely wrong isn't).
- **Pick recipes for flavour.** A slide's `recipe` decides where its images come from, and their look (the
  reference names each image's look, such as `vintage` for old photographs in black and white or sepia, or
  `meme-chaos` for Reddit's weird pictures, gifs and memes). In the default format, many recipes mix in Reddit
  images and gifs, which are wilder, need Reddit or GIPHY keys, and change from one render to the next; recipes
  with `copyright-free` or `crf` in their id use stock photos, artworks and old photos only. Write a query for what
  the image shows, not for its look: "a baker in 1900" for a vintage slot, not "old black and white photo". Some
  recipes find their texts themselves (real quotes, say): the reference says so, and then you don't write that text.
  Those texts are English, so a talk in another language gets the kind's default recipe instead.
- **Memes** (default format only): a `meme` slide's `template_query` is the template's name, and its texts are its
  captions in order; `talkgenerator formats --memes` lists the templates and what each caption says ("Drake Hotline
  Bling": `text_1` what Drake waves away, `text_2` what he points at instead). Keep captions to a few words.
- **Your own pictures**: an image "query" may be the path of an image file, relative to the plan's folder. That
  puts the user's own photo on the slide, for an about-me slide, say.
- **Generated pictures**, only when the user has set up an image generator (`TALKGENERATOR_IMAGE_GENERATOR`, or
  render's `--image_generator`): they cost money on the user's own key, a few per plan at most, so never set one up
  or pass it without the user asking. The images the reference marks "or generated" (the weird hobby, the book's
  cover, history's old photos and made-up figures, the news story's photo) are then generated from the slide's
  `prompts` (by image name: one English sentence of 10 to 40 words saying what the picture shows, with made-up
  people only, no real or famous ones, and no logos or brands; a book cover's title in quotes), or else from the
  image's query, and an image whose search finds nothing may be too. Write the queries as ever: the stock photo
  stays when a picture isn't generated. The report's `generated_images` says what was made and what it cost.

## Keep it kind

- No quotes put in the mouths of real people: quotes on slides belong to made-up people (the history slides are
  for made-up historical figures), or come from talkgenerator's real quotes.
- The presenter's name is made up too: never a real person's name as it is. A pun on a famous name may bend anyone
  famous, from history or today, but never a dictator's or a criminal's.
- Nothing about real private persons, and nothing that mocks people for who they are. No slurs or sexual content.
- Images and texts are read together. A photo of a person under a caption that labels or judges ("Camouflage",
  "Patience", "Reality") can read as a joke about that person: for such captions, search for animals, objects or
  scenes. Replace images of real public figures, and any image that, next to its text, mocks someone's looks,
  origin or body.
- If a topic asks for something hateful or harmful, say no kindly, and offer a talk on a nearby harmless topic.

## Without a shell

Where you can't run commands (in a chat without code execution, say), write the plan anyway and give it to the user
as a JSON file, with the command that renders it on their computer: `talkgenerator render plan.json`. Or, in Claude
Desktop, offer to set up talkgenerator's MCP server (below).

## In Claude Desktop, with the MCP server

talkgenerator's MCP server gives you the commands as tools: `list_formats`, `describe_format`
(`formats --details`), `get_plan_schema` (`schema plan`), `render_plan` (`render`, with the plan itself as its
input, the same report, and `seed` for `--int_seed`), and `generate_talk`, which has talkgenerator write a whole talk
on its own (its `name_styles` pick the kinds of names it makes up for the presenter, which `list_formats` lists).
When you have those tools, use them: the steps above stay the same, and the decks go to the server's output folder
(the report gives their paths).

If the user wants it, the server runs on their own computer, with their own keys. They install it with
`pip install 'talkgenerator[mcp]'` (on Windows on Arm, in an x64 Python), open Claude Desktop's config (Settings >
Developer > Edit Config), add the server, and restart Claude Desktop:

```json
{
  "mcpServers": {
    "talkgenerator": {
      "command": "talkgenerator",
      "args": ["mcp"],
      "env": {
        "UNSPLASH_ACCESS_KEY": "...",
        "PEXELS_KEY": "..."
      }
    }
  }
}
```

`command` is the full path of the `talkgenerator` command when Claude Desktop doesn't find it (or `uvx`, with
`"args": ["--from", "talkgenerator[mcp]", "talkgenerator", "mcp"]`). `env` holds the keys they have, which they fill
in themselves: Claude Desktop starts the server in a folder of its own, so it doesn't see their `.env`. The decks go
to the `talkgenerator` folder in their documents, or to the folder that `"args": ["mcp", "--output_folder",
"<folder>"]` names.
